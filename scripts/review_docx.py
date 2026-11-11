"""Inspect a DOCX, then anchor editor-supplied comments to exact text in a new copy."""

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import posixpath
import shutil
import sys
import tempfile
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED

from review_classification import FINDING_SCHEMA, review_findings

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")

try:
    from lxml import etree as E
except ImportError as exc:
    if __name__ != "__main__":
        raise
    raise SystemExit("当前 Python 无法加载 lxml。请先安装 requirements.txt 中的依赖。") from exc


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
PR = "{http://schemas.openxmlformats.org/package/2006/relationships}"
CT = "{http://schemas.openxmlformats.org/package/2006/content-types}"
REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
DOC = "word/document.xml"
RELS = "word/_rels/document.xml.rels"
TYPES = "[Content_Types].xml"
COMMENTS_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
HIDDEN_TAGS = {W+"vanish", W+"webHidden", W+"specVanish"}
OFF_VALUES = {"0", "false", "off"}
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
INLINE_OBJECTS = {
    M+"oMath": "公式", M+"oMathPara": "公式", W+"drawing": "图形", W+"pict": "图形",
    W+"object": "嵌入对象", W+"footnoteReference": "脚注标记", W+"endnoteReference": "尾注标记",
    MC+"AlternateContent": "兼容性替代内容",
}


def part(z, name):
    parser = E.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    root = E.fromstring(z.read(name), parser)
    if root.getroottree().docinfo.doctype:
        raise ValueError(f"不支持含 DTD 的 XML 部件：{name}")
    return root


def xml(root):
    return E.tostring(root.getroottree(), encoding="UTF-8", xml_declaration=True)


@contextmanager
def new_output(path):
    """Publish once, on the same filesystem, after all checks and writes succeed."""
    if path.exists():
        raise FileExistsError(f"输出已存在：{path}")
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    os.close(fd)
    tmp = Path(tmp)
    try:
        yield tmp
        if os.name == "nt":
            os.rename(tmp, path)  # Windows rejects an existing destination.
        else:
            os.link(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def plain_run(r):
    if (r.tag != W+"r" or len(r.findall(W+"t")) != 1
            or any(c.tag not in (W+"rPr", W+"t") for c in r)):
        return False
    t = r.find(W+"t")
    value = t.text or ""
    # Word can suppress unpreserved whitespace at run boundaries. Splitting
    # such a run and setting xml:space could expose previously invisible text.
    return value == value.strip() or t.get(XML_SPACE) == "preserve"


def text_pieces(p, fragment=None, *, mark_objects=False):
    # A legacy symbol's glyph depends on its font. Keep a visible-text offset
    # for it without guessing a Unicode character from the font's code point.
    special = {W+"tab": "\t", W+"br": "\n", W+"cr": "\n", W+"sym": "\ufffc",
               W+"noBreakHyphen": "\u2011", W+"softHyphen": "\u00ad"}
    walk = E.iterwalk(fragment if fragment is not None else p, events=("start",))
    for _, e in walk:
        if e.tag == W+"p" and e is not p:
            walk.skip_subtree()
            continue
        if mark_objects and e.tag in INLINE_OBJECTS:
            yield None, f"〔{INLINE_OBJECTS[e.tag]}〕"
            walk.skip_subtree()
            continue
        # Paragraph tab stops are also named w:tab, but only run children
        # contribute text.
        if (e.tag == W+"t" or e.tag in special) and e.getparent().tag == W+"r":
            yield e.getparent(), special.get(e.tag, e.text or "")


def display_text(p, fragment=None):
    return "".join(value for _, value in text_pieces(p, fragment))


def add_script_range(ranges, start, end, position):
    """Ranges use original Unicode offsets, including any preceding special characters."""
    if end == start or position not in ("superscript", "subscript"):
        return
    if ranges and ranges[-1]["end"] == start and ranges[-1]["position"] == position:
        ranges[-1]["end"] = end
    else:
        ranges.append({"start": start, "end": end, "position": position})


def run_offsets(p):
    """Account for visible text in complex inline objects without modifying it."""
    pos = 0
    for child in p:
        end = pos + len(display_text(p, child))
        yield child, pos, end
        pos = end


def plain_ranges(p):
    intervals = []
    start = None
    end = 0
    for child, left, right in run_offsets(p):
        if plain_run(child):
            if start is None:
                start = left
            end = right
        elif start is not None:
            if start < end:
                intervals.append([start, end])
            start = None
    if start is not None and start < end:
        intervals.append([start, end])
    return intervals


def revised_cell(p):
    flags = {W+s for s in ("ins", "del", "cellIns", "cellDel", "cellMerge")}
    props = {W+"tr": W+"trPr", W+"tc": W+"tcPr"}
    for ancestor in p.iterancestors():
        if ancestor.tag in props:
            settings = ancestor.find(props[ancestor.tag])
            if settings is not None and any(item.tag in flags for item in settings.iter()):
                return True
    return False


def merged_continuation(p):
    for cell in p.iterancestors(W+"tc"):
        for tag in ("vMerge", "hMerge"):
            flag = cell.find(f"{W}tcPr/{W}{tag}")
            if flag is not None and flag.get(W+"val", "continue") == "continue":
                return True
    return False


class WordBaselines:
    def __init__(self, styles):
        self.styles = {}
        self.defaults = {}
        self.cache = {}
        self.document = None
        if styles is not None:
            self.document = styles.find(f"{W}docDefaults/{W}rPrDefault/{W}rPr")
            for style in styles.findall(W+"style"):
                key = style.get(W+"styleId")
                self.styles[key] = style
                if style.get(W+"default", "0") not in OFF_VALUES:
                    self.defaults[style.get(W+"type")] = key

    @staticmethod
    def property(props, prop):
        if props is None:
            return None
        item = props.find(W+prop)
        return item.get(W+"val", "unknown") if item is not None else None

    def style_property(self, key, prop):
        if (key, prop) in self.cache:
            return self.cache[key, prop]
        seen = set()
        current = key
        value = None
        while current is not None:
            if current in seen or current not in self.styles:
                value = "unknown"
                break
            seen.add(current)
            style = self.styles[current]
            if style.find(f"{W}tblStylePr/{W}rPr/{W}{prop}") is not None:
                value = "unknown"
                break
            value = self.property(style.find(W+"rPr"), prop)
            if value is not None:
                break
            current = self.property(style, "basedOn")
        self.cache[key, prop] = value
        return value

    def paragraph(self, p):
        style = self.property(p.find(W+"pPr"), "pStyle") or self.defaults.get("paragraph")
        table = next(p.iterancestors(W+"tbl"), None)
        table_style = None
        if table is not None:
            table_style = self.property(table.find(W+"tblPr"), "tblStyle") or self.defaults.get("table")
        inherited = {}
        for prop in ("vertAlign", "position"):
            inherited[prop] = (self.style_property(style, prop) or self.style_property(table_style, prop)
                               or self.property(self.document, prop))
        ranges, uncertain = [], False
        offset = 0
        for run, value in text_pieces(p):
            props = run.find(W+"rPr")
            char_style = self.property(props, "rStyle") or self.defaults.get("character")
            align = (self.property(props, "vertAlign") or self.style_property(char_style, "vertAlign")
                     or inherited["vertAlign"])
            shift = (self.property(props, "position") or self.style_property(char_style, "position")
                     or inherited["position"])
            if align not in (None, "baseline", "superscript", "subscript") or shift not in (None, "0"):
                uncertain = True
            end = offset + len(value)
            add_script_range(ranges, offset, end, align)
            offset = end
        return ranges, uncertain


def paragraph_styles(z, rels):
    """Conservative closure, including inherited paragraph/character/table styles."""
    def has_hiding(node):
        return any(e.tag in HIDDEN_TAGS and e.get(W+"val") not in OFF_VALUES for e in node.iter())

    styles_rel = next((r for r in rels if r.get("Type") == REL_TYPE+"styles"), None)
    if styles_rel is None:
        return False, set(), WordBaselines(None)
    styles = part(z, target_part(styles_rel))
    defs = {s.get(W+"styleId"):s for s in styles.findall(W+"style")}
    hidden = {key for key,s in defs.items() if has_hiding(s)}
    base = {key:s.find(W+"basedOn").get(W+"val") for key,s in defs.items()
            if s.find(W+"basedOn") is not None}
    while True:
        derived = {key for key,parent in base.items() if parent in hidden}
        if derived <= hidden:
            break
        hidden.update(derived)
    defaults = styles.find(W+"docDefaults")
    default_hidden = defaults is not None and has_hiding(defaults)
    default_hidden |= any(key in hidden and s.get(W+"default","0") not in OFF_VALUES for key,s in defs.items())
    return default_hidden, hidden, WordBaselines(styles)


def uses_hidden_style(p, hidden):
    for n in p.iter():
        if n.tag in (W+"pStyle", W+"rStyle") and n.get(W+"val") in hidden:
            return True
    for tbl in p.iterancestors(W+"tbl"):
        style = tbl.find(f"{W}tblPr/{W}tblStyle")
        if style is not None and style.get(W+"val") in hidden:
            return True
    return False


def inventory(body, default_hidden, hidden, baselines):
    """Use XML order and physical cells. Do not duplicate merged cells."""
    entries, nodes = [], {}
    field_depth = 0
    active_ranges = set()
    starts = {W + s + "Start": s for s in
              ("commentRange", "perm", "moveFromRange", "moveToRange",
               "customXmlInsRange", "customXmlDelRange", "customXmlMoveFromRange",
               "customXmlMoveToRange")}
    ends = {W + s + "End": s for s in starts.values()}
    restricted = set(starts) | set(ends) | {W+s for s in
        ("rPrChange", "pPrChange", "del", "ins", "moveFrom", "moveTo",
         "fldChar", "instrText", "commentReference")}
    for _, e in E.iterwalk(body, events=("start",)):
        if e.tag in starts:
            active_ranges.add((starts[e.tag], e.get(W + "id")))
        elif e.tag in ends:
            active_ranges.discard((ends[e.tag], e.get(W + "id")))
        elif e.tag == W + "fldChar":
            action = e.get(W + "fldCharType")
            if action == "begin":
                field_depth += 1
            elif action == "end":
                field_depth = max(0, field_depth - 1)
        if e.tag != W + "p":
            continue
        pid = f"P{len(entries) + 1:04d}"
        nodes[pid] = e
        reason = None
        chain = {a.tag for a in e.iterancestors()}
        plain_ancestors = {W + s for s in ("tc", "tr", "tbl", "body", "document")}
        continuation = merged_continuation(e)
        if continuation:
            reason = "合并单元格的续格，留存文字不作为独立可见正文"
        elif chain - plain_ancestors:
            reason = "嵌入对象、修订、内容控件或扩展结构"
        elif field_depth or active_ranges:
            reason = "位于跨段域、已有批注或标记范围内"
        elif any(n.tag in restricted or (n.tag in HIDDEN_TAGS and n.get(W+"val") not in OFF_VALUES)
                 for n in e.iter()):
            reason = "段内含复杂域、既有批注范围、修订或隐藏文字"
        elif default_hidden or (hidden and uses_hidden_style(e, hidden)):
            reason = "默认或继承样式含隐藏属性，需在 Word 中核实"
        elif revised_cell(e):
            reason = "表格行或单元格带修订"
        text = "" if continuation else display_text(e)
        intervals = [] if reason else plain_ranges(e)
        if not intervals and not reason and (text.strip() or any(c.tag != W+"pPr" for c in e)):
            reason = "缺少可独立定位的普通文本片段"
        style = e.find(f"{W}pPr/{W}pStyle")
        entry = {"paragraph": pid, "location": e.getroottree().getpath(e),
                 "style": style.get(W + "val") if style is not None else None,
                 "text": text, "annotatable": bool(text.strip() and intervals),
                 "editable_ranges": intervals}
        checks = []
        if not continuation and next(e.iter(*INLINE_OBJECTS), None) is not None:
            # Keep existing text, quote and start offsets stable for saved manifests.
            reading = "".join(value for _, value in text_pieces(e, mark_objects=True))
            if reading != text:
                entry["reading_text"] = reading
                checks.append("reading_text 标示对象位置。请在 Word 中核对对象内容及其与邻近文字的关系。")
        if text:
            ranges, uncertain = baselines.paragraph(e)
            if ranges:
                entry["script_ranges"] = ranges
            if uncertain:
                checks.append("文字存在额外的基线位移或无法解析的样式，请在 Word 中核对上下标。")
        if "\ufffc" in text:
            checks.append("对象替代符（U+FFFC）所在位置请在 Word 中目视核对。旧式字体符号按此标出。")
        if checks:
            entry["manual_review"] = " ".join(checks)
        if reason:
            entry["skip_reason"] = reason
        if entry["annotatable"] and any(c.tag != W+"pPr" and not plain_run(c) for c in e):
            entry["partial"] = True
        entries.append(entry)
    return entries, nodes


def target_part(rel, base="word"):
    target = rel.get("Target", "")
    if rel.get("TargetMode") == "External" or not target or "\\" in target:
        raise ValueError("不支持此外部或无效关系")
    return posixpath.normpath(posixpath.join(base, target)).lstrip("/")


def package(z):
    names = z.namelist()
    if len(names) != len(set(names)):
        raise ValueError("包中有重名部件")
    main_rels = [r for r in part(z, "_rels/.rels") if r.get("Type") == REL_TYPE+"officeDocument"]
    if len(main_rels) != 1 or target_part(main_rels[0], base="") != DOC:
        raise ValueError("不支持的 Word 主部件路径或文档类型，请在 Word 中核实")
    doc = part(z, DOC)
    body = doc.find(W + "body")
    if doc.tag != W+"document" or body is None:
        raise ValueError("仅支持常规 Transitional DOCX 正文")
    types = part(z, TYPES)
    rels = part(z, RELS) if RELS in names else E.Element(PR+"Relationships", nsmap={None: PR[1:-1]})
    blocked = []
    content_types = [e.get("ContentType", "").lower() for e in types]
    main_type = next((e.get("ContentType", "") for e in types if e.get("PartName")=="/"+DOC), "")
    if main_type != "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml":
        blocked.append("主部件不是常规 docx 文档")
    if any("digital-signature" in t for t in content_types) or any(n.startswith("_xmlsignatures/") for n in names):
        blocked.append("文件包含数字签名")
    if any("comments" in t and t != COMMENTS_TYPE for t in content_types):
        blocked.append("含扩展批注元数据，请在 Word 中保留会话后批注")
    for rel in rels:
        if rel.get("Type") == REL_TYPE + "settings":
            settings = part(z, target_part(rel))
            protection = settings.find(W + "documentProtection")
            if protection is not None and protection.get(W+"enforcement", "0") not in ("0", "off", "false"):
                blocked.append("文档启用了编辑保护")
            write_protection = settings.find(W + "writeProtection")
            if write_protection is not None and set(write_protection.attrib) != {W+"recommended"}:
                blocked.append("文档启用了修改密码或写保护")
    return doc, body, rels, types, blocked


def resolve_findings(manifest, fingerprint, entries):
    if not isinstance(manifest, dict) or manifest.get("source_sha256") != fingerprint:
        raise ValueError("文件指纹不匹配；请重新 inspect 当前原稿")
    lookup = {e["paragraph"]: e for e in entries}
    plans = defaultdict(list)
    for i, (item, comment) in enumerate(review_findings(manifest), 1):
        pid, quote = item.get("paragraph"), item.get("quote")
        if not all(isinstance(s, str) and s.strip() for s in (pid, quote)):
            raise ValueError(f"第 {i} 条须有非空段号、引文")
        entry = lookup.get(pid)
        if not entry or not entry["annotatable"]:
            raise ValueError(f"{pid} 不在可批注范围")
        text = entry["text"]
        if "start" in item:
            start = item["start"]
            if type(start) is not int or start < 0 or not text.startswith(quote, start):
                raise ValueError(f"{pid} 指定位置与引文不一致")
        else:
            start = text.find(quote)
            if start < 0 or text.find(quote, start + 1) >= 0:
                raise ValueError(f"{pid} 引文不存在或不唯一；重复时须指定 start")
        if not any(a <= start and start+len(quote) <= b for a,b in entry["editable_ranges"]):
            raise ValueError(f"{pid} 引文位于或跨越受保护结构，请转入定位清单")
        plans[pid].append((start, start+len(quote), comment))
    for pid, intervals in plans.items():
        intervals.sort()
        if any(a[1] > b[0] for a, b in zip(intervals, intervals[1:])):
            raise ValueError(f"{pid} 的批注范围重叠；请合并意见或缩小范围")
    return plans


def split_at(p, offset):
    """Return the run starting at a text offset, splitting only plain text runs."""
    for r, pos, end in run_offsets(p):
        if not plain_run(r):
            continue
        t = r.find(W+"t")
        if t is None or not t.text:
            continue
        if pos == offset:
            return r
        if pos < offset < end:
            right = deepcopy(r)
            right_t = right.find(W+"t")
            t.text, right_t.text = t.text[:offset-pos], t.text[offset-pos:]
            for fragment in (t, right_t):
                if fragment.text != fragment.text.strip():
                    fragment.set(XML_SPACE, "preserve")
            r.addnext(right)
            return right
    return None


def add_notes(p, intervals, comments, next_id):
    # Split all runs before inserting any anchors, including adjacent findings.
    for offset in sorted({pt for start,end,_ in intervals for pt in (start,end)}, reverse=True):
        split_at(p, offset)
    first, last = {}, {}
    for r, pos, end in run_offsets(p):
        if not plain_run(r):
            continue
        t = r.find(W+"t")
        if t is None or not t.text:
            continue
        first[pos] = r
        last[end] = r
    for start, end, note in intervals:
        attrs = {W+"id":str(next_id)}
        first[start].addprevious(E.Element(W+"commentRangeStart", attrs))
        marker = E.Element(W+"commentRangeEnd", attrs)
        last[end].addnext(marker)
        ref_run = E.Element(W+"r")
        E.SubElement(ref_run, W+"commentReference", attrs)
        marker.addnext(ref_run)
        c = E.SubElement(comments, W+"comment", attrs)
        c.set(W+"author", "Unbot")
        c.set(W+"date", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        for index,line in enumerate(note.splitlines()):
            cp = E.SubElement(c, W+"p")
            if index == 0:
                E.SubElement(E.SubElement(cp,W+"r"), W+"annotationRef")
            t = E.SubElement(E.SubElement(cp, W+"r"), W+"t")
            t.text = line
            if line != line.strip():
                t.set(XML_SPACE, "preserve")
        next_id += 1
    return next_id


def verify_notes(output, name, expected):
    """Reopen the serialized package and check each range, reference and note."""
    with ZipFile(output) as z:
        comments = part(z, name)
        actual_notes = {}
        for comment in comments.findall(W+"comment"):
            ident = comment.get(W+"id")
            if ident in expected:
                actual_notes[ident] = "\n".join(
                    "".join(t.text or "" for t in p.iter(W+"t")) for p in comment.findall(W+"p")
                )
        found = set()
        body = part(z, DOC).find(W+"body")
        target_ids = {record[0] for record in expected.values()}
        for i, p in enumerate(body.iter(W+"p"), 1):
            pid = f"P{i:04d}"
            if pid not in target_ids:
                continue
            starts, ends, refs = {}, {}, set()
            text = display_text(p)
            for child,pos,_ in run_offsets(p):
                if child.tag == W+"commentRangeStart":
                    starts[child.get(W+"id")] = pos
                elif child.tag == W+"commentRangeEnd":
                    ends[child.get(W+"id")] = pos
                elif child.tag == W+"r":
                    refs.update(r.get(W+"id") for r in child.findall(W+"commentReference"))
            for ident in refs & expected.keys():
                record = (pid, text, starts.get(ident), ends.get(ident), actual_notes.get(ident))
                if expected[ident] != record:
                    raise ValueError(f"{pid} 的批注未通过落盘复核")
                found.add(ident)
        if found != expected.keys():
            raise ValueError("批注部件与正文锚点不匹配")


def write_review(z, tmp, doc, rels, types, nodes, plans):
    changes = {}
    related = [r for r in rels if r.get("Type") == REL_TYPE+"comments"]
    if related:
        if len(related) != 1:
            raise ValueError("存在多份批注关系")
        name = target_part(related[0])
        comments = part(z, name)
        if comments.tag != W+"comments":
            raise ValueError("批注部件结构无效")
    else:
        name = "word/comments.xml"
        if name in z.namelist() or any(e.get("PartName")=="/"+name for e in types):
            raise ValueError("已有未关联的批注部件，需在 Word 中核实")
        comments = E.Element(W+"comments", nsmap={"w":W[1:-1]})
        ids = {r.get("Id") for r in rels}
        i = 1
        while f"rId{i}" in ids:
            i += 1
        E.SubElement(rels, PR+"Relationship", Id=f"rId{i}", Type=REL_TYPE+"comments", Target="comments.xml")
        E.SubElement(types, CT+"Override", PartName="/"+name, ContentType=COMMENTS_TYPE)
        changes.update({RELS:xml(rels), TYPES:xml(types)})
    id_tags = {W+s for s in ("comment","commentRangeStart","commentRangeEnd","commentReference")}
    ids = (int(e.get(W+"id")) for root in (doc,comments) for e in root.iter() if e.tag in id_tags)
    number = max(ids, default=-1) + 1
    expected = {}
    for pid, intervals in plans.items():
        original = display_text(nodes[pid])
        for index, (start, end, note) in enumerate(intervals):
            expected[str(number+index)] = (pid, original, start, end, "\n".join(note.splitlines()))
        number = add_notes(nodes[pid], intervals, comments, number)
    changes.update({DOC:xml(doc), name:xml(comments)})
    with ZipFile(tmp, "w", compression=ZIP_DEFLATED) as result:
        result.comment = z.comment
        for info in z.infolist():
            if info.filename in changes:
                result.writestr(deepcopy(info), changes.pop(info.filename))
            else:
                with z.open(info) as src, result.open(deepcopy(info),"w") as dst:
                    shutil.copyfileobj(src, dst)
        for new_name, data in changes.items():
            result.writestr(new_name, data)
    verify_notes(tmp, name, expected)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="cmd", required=True)
    inspect = sub.add_parser("inspect", help="提取段号、原文和覆盖范围")
    inspect.add_argument("source", type=Path)
    inspect.add_argument("--output", type=Path, help="另存 UTF-8 JSON")
    annotate = sub.add_parser("annotate", help="将编辑确认的问题标为原生批注")
    annotate.add_argument("source", type=Path)
    annotate.add_argument("findings", type=Path)
    annotate.add_argument("output", type=Path)
    args = cli.parse_args()
    try:
        if args.source.suffix.lower() != ".docx":
            raise ValueError("输入须为 DOCX；其他格式请先生成可审阅副本")
        with tempfile.TemporaryFile() as source:
            digest = hashlib.sha256()
            with args.source.open("rb") as original:
                for chunk in iter(lambda:original.read(1024*1024), b""):
                    digest.update(chunk)
                    source.write(chunk)
            fingerprint = digest.hexdigest()
            source.seek(0)
            with ZipFile(source) as z:
                doc, body, rels, types, blocked = package(z)
                entries, nodes = inventory(body, *paragraph_styles(z, rels))
                if args.cmd == "inspect":
                    other = [r.get("Target") for r in rels if (r.get("Type") or "").split("/")[-1]
                             in {"header","footer","footnotes","endnotes","aFChunk"}]
                    data = {"finding_schema": FINDING_SCHEMA, "source_sha256":fingerprint, "write_blockers":blocked,
                            "out_of_scope_parts":other,
                            "coverage":{"paragraphs":len(entries),
                                        "annotatable":sum(e["annotatable"] for e in entries),
                                        "partial":sum(e.get("partial",False) for e in entries),
                                        "skip_reasons":dict(Counter(e["skip_reason"] for e in entries if "skip_reason" in e))},
                            "paragraphs":entries}
                    report = json.dumps(data, ensure_ascii=False, indent=2)
                    if args.output:
                        with new_output(args.output) as tmp:
                            tmp.write_text(report+"\n",encoding="utf-8")
                    else:
                        print(report)
                    return
                if args.output.suffix.lower() != ".docx":
                    raise ValueError("输出文件名须以 .docx 结尾")
                manifest = json.loads(args.findings.read_text(encoding="utf-8-sig"))
                plans = resolve_findings(manifest, fingerprint, entries)
                if plans and blocked:
                    raise ValueError("；".join(blocked))
                with new_output(args.output) as tmp:
                    if plans:
                        write_review(z,tmp,doc,rels,types,nodes,plans)
                    else:
                        source.seek(0)
                        with tmp.open("wb") as out:
                            shutil.copyfileobj(source, out)
                print(f"新增批注 {sum(len(v) for v in plans.values())} 条")
    except (OSError, ValueError, KeyError, BadZipFile, E.XMLSyntaxError, RuntimeError) as error:
        cli.exit(2,f"错误：{error}\n")


if __name__ == "__main__":
    main()
