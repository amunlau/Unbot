"""按实际页序提取 PPTX 文本和备注，将编辑意见写入副本的页级批注或 HTML 页位清单。"""

import argparse
from collections import defaultdict
from copy import copy
from datetime import datetime, timezone
import hashlib
from html import escape
import json
from pathlib import Path
import posixpath
import shutil
import sys
from tempfile import TemporaryFile
from urllib.parse import unquote
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED

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

from review_docx import CT, PR, REL_TYPE, TYPES, new_output, part, xml


P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
PRESENTATION = "ppt/presentation.xml"
MIME = "application/vnd.openxmlformats-officedocument.presentationml."
AUTHOR = "ppt/commentAuthors.xml"


def rels_name(name):
    folder, base = posixpath.split(name)
    return posixpath.join(folder, "_rels", base + ".rels")


def relationships(z, name):
    path = rels_name(name)
    root = part(z, path) if path in z.NameToInfo else E.Element(PR + "Relationships", nsmap={None: PR[1:-1]})
    targets = {}
    for rel in root.findall(PR + "Relationship"):
        if rel.get("TargetMode") == "External":
            continue
        target = unquote(rel.get("Target", ""))
        path = posixpath.normpath(posixpath.join(posixpath.dirname(name), target)).lstrip("/")
        targets[rel.get("Id")] = (rel.get("Type"), path)
    return root, targets


def read_paragraphs(body, key, label, slide):
    if body is None:
        return
    for i, para in enumerate(body.findall(A + "p"), 1):
        text = []
        for child in para:
            if child.tag == A + "r":
                text.append(child.findtext(A + "t", default=""))
            elif child.tag == A + "br":
                text.append("\n")
            elif child.tag not in {A + "pPr", A + "endParaRPr"}:
                slide["manual_review"].append(f"{label} 第 {i} 段含域、公式或其他内嵌内容")
                break
        else:
            value = "".join(text)
            if value.strip():
                slide["paragraphs"].append({"id": f"{key}/P{i}", "location": f"{label} / 段 {i}", "text": value})


def drawing_kind(shape, placeholder):
    if shape.tag == P + "cxnSp":
        return "连接线"
    props = shape.find(P + "spPr")
    if props is None:
        return None
    if props.find(A + "blipFill") is not None:
        return "图片填充形状"
    textbox = shape.find("./" + P + "nvSpPr/" + P + "cNvSpPr")
    if placeholder is not None or (textbox is not None and textbox.get("txBox") in ("1", "true")):
        return None
    if any(props.find(A + tag) is not None for tag in ("prstGeom", "custGeom")):
        return "绘图形状"
    return None


def title_outside_canvas(shape, canvas):
    """Check a top-level title box when its slide coordinates are unambiguous."""
    transform = shape.find("./" + P + "spPr/" + A + "xfrm")
    if canvas is None or transform is None or int(transform.get("rot", "0")) % 21600000:
        return False
    offset = transform.find(A + "off")
    if offset is None:
        return False
    x, y = int(offset.get("x", "")), int(offset.get("y", ""))
    if x >= canvas[0] or y >= canvas[1]:
        return True
    extent = transform.find(A + "ext")
    if extent is None:
        return False
    width, height = int(extent.get("cx", "")), int(extent.get("cy", ""))
    return (width > 0 and x + width <= 0) or (height > 0 and y + height <= 0)


def read_shapes(tree, key, parent, slide, notes=False, parent_hidden=False, canvas=None):
    if tree is None:
        raise ValueError(f"第 {slide['page']} 页缺少对象树。")
    for shape in tree:
        if shape.tag in (P + "nvGrpSpPr", P + "grpSpPr"):
            continue
        nv = shape.find("./*/" + P + "cNvPr")
        if nv is None:
            slide["manual_review"].append(f"{parent} / {E.QName(shape).localname}")
            continue
        shape_id = nv.get("id", "?")
        loc = f"{parent} / {nv.get('name') or '对象'} (ID {shape_id})"
        shape_key = f"{key}/{shape_id}"
        own_hidden = nv.get("hidden") in ("1", "true")
        hidden = parent_hidden or own_hidden
        if own_hidden:
            loc += "〔隐藏对象〕"
        ph = shape.find("./*/" + P + "nvPr/" + P + "ph")
        kind = ph.get("type", "obj") if ph is not None else None
        is_title = not notes and kind in ("title", "ctrTitle")
        outside = is_title and title_outside_canvas(shape, canvas)
        if outside:
            loc += "〔页题框在画面外〕"
        if notes and kind in ("sldImg", "sldNum", "dt", "hdr", "ftr"):
            continue
        if shape.tag == P + "grpSp":
            read_shapes(shape, shape_key, loc, slide, notes, hidden)
        elif shape.tag in (P + "sp", P + "cxnSp"):
            body = shape.find(P + "txBody")
            before = len(slide["paragraphs"])
            read_paragraphs(body, shape_key, loc, slide)
            if is_title and len(slide["paragraphs"]) > before:
                previous_unshown = slide["title_hidden"] or slide["title_off_slide"]
                if not slide["title"] or (previous_unshown and not (hidden or outside)):
                    slide["title"] = " ".join(p["text"] for p in slide["paragraphs"][before:])
                    slide["title_hidden"] = hidden
                    slide["title_off_slide"] = outside
            drawing = drawing_kind(shape, kind)
            if drawing:
                slide["visual_objects"].append({"id": shape_key, "location": loc, "kind": drawing})
        elif shape.tag == P + "graphicFrame":
            frame = shape.find("./" + A + "graphic/" + A + "graphicData")
            table = frame.find(A + "tbl") if frame is not None else None
            if table is None:
                uri = frame.get("uri", "") if frame is not None else ""
                kind = {"chart": "图表", "diagram": "SmartArt", "ole": "嵌入对象"}.get(uri.rsplit("/", 1)[-1], "图形对象")
                slide["visual_objects"].append({"id": shape_key, "location": loc, "kind": kind})
                continue
            for row, tr in enumerate(table.findall(A + "tr"), 1):
                for col, tc in enumerate(tr.findall(A + "tc"), 1):
                    if any(tc.get(flag) in ("1", "true") for flag in ("hMerge", "vMerge")):
                        # PowerPoint displays only the merge-origin cell. A spanned cell
                        # may retain text that becomes visible only after unmerging.
                        continue
                    read_paragraphs(tc.find(A + "txBody"), f"{shape_key}/R{row}C{col}",
                                    f"{loc} / 第 {row} 行第 {col} 列", slide)
        elif shape.tag == P + "pic":
            slide["visual_objects"].append({"id": shape_key, "location": loc, "kind": "图片或媒体"})
        else:
            slide["manual_review"].append(loc + f"〔{E.QName(shape).localname}〕")


def show_settings(z, presentation, targets, slides):
    pages = {slide["part"]: slide["page"] for slide in slides}
    custom_shows = []
    for show in presentation.findall("./" + P + "custShowLst/" + P + "custShow"):
        sequence = []
        for entry in show.findall("./" + P + "sldLst/" + P + "sld"):
            target = targets.get(entry.get(RID))
            sequence.append(pages.get(target[1]) if target and target[0] == REL_TYPE + "slide" else None)
        custom_shows.append({"id": show.get("id"), "name": show.get("name"), "pages": sequence})
    selection = {"type": "all"}
    for rel_type, target in targets.values():
        if rel_type != REL_TYPE + "presProps":
            continue
        show = part(z, target).find(P + "showPr")
        if show is not None:
            custom = show.find(P + "custShow")
            span = show.find(P + "sldRg")
            if custom is not None:
                selection = {"type": "custom", "id": custom.get("id")}
            elif span is not None:
                selection = {"type": "range", "start": int(span.get("st", "")), "end": int(span.get("end", ""))}
        break
    return {"selection": selection, "custom_shows": custom_shows}


def inspect(z, digest):
    names = z.namelist()
    if len(names) != len(set(names)):
        raise ValueError("压缩包有重名部件，无法唯一定位。")
    presentation = part(z, PRESENTATION)
    if presentation.tag != P + "presentation":
        raise ValueError("仅支持常规 Transitional PPTX。")
    types = part(z, TYPES)
    _, roots = relationships(z, "")
    if (REL_TYPE + "officeDocument", PRESENTATION) not in roots.values() or not any(
        item.get("PartName") == "/" + PRESENTATION and item.get("ContentType") == MIME + "presentation.main+xml"
        for item in types
    ):
        raise ValueError("不支持的演示文稿类型或主部件路径。")
    blockers = []
    sensitive = ("comment", "person+xml", "digital-signature", "vbaproject", "macroenabled", "encrypted", "signature")
    if any(any(token in el.get("ContentType", "").lower() for token in sensitive) for el in types):
        blockers.append("已有批注、人员记录、签名、加密或宏部件")
    if any(n.lower().startswith("_xmlsignatures/") for n in names) or presentation.find(P + "modifyVerifier") is not None:
        blockers.append("数字签名或修改保护")
    _, targets = relationships(z, PRESENTATION)
    size = presentation.find(P + "sldSz")
    canvas = (int(size.get("cx", "")), int(size.get("cy", ""))) if size is not None else None
    slides = []
    seen_parts = set()
    for page, sid in enumerate(presentation.findall("./" + P + "sldIdLst/" + P + "sldId"), 1):
        kind, path = targets[sid.get(RID)]
        if kind != REL_TYPE + "slide" or path in seen_parts:
            raise ValueError("页引用类型或页路径异常。")
        seen_parts.add(path)
        root = part(z, path)
        key = f"S{page:03}"
        slide = {"page": page, "slide_id": sid.get("id"), "part": path, "title": "", "title_hidden": False,
                 "title_off_slide": False,
                 "hidden": root.get("show") in ("0", "false"), "paragraphs": [], "visual_objects": [], "manual_review": []}
        read_shapes(root.find("./" + P + "cSld/" + P + "spTree"), key, "页面", slide, canvas=canvas)
        _, slide_targets = relationships(z, path)
        for rel_type, target in slide_targets.values():
            if rel_type == REL_TYPE + "notesSlide":
                notes = part(z, target)
                read_shapes(notes.find("./" + P + "cSld/" + P + "spTree"), key + "/N", "演讲备注", slide, True)
        if root.find(P + "timing") is not None:
            slide["manual_review"].append("动画出现顺序")
        slides.append(slide)
    return {"source_sha256": digest, "slides": slides, "write_blockers": blockers,
            "slide_show": show_settings(z, presentation, targets, slides),
            "coverage_note": "slides 按文件编辑页序，包含隐藏页。slide_show 列出保存的放映选择与自定义页序，无法解析的自定义页用 null 表示。实际跳转、动画、母版、版式及遮挡另查。visual_objects 只定位对象，图中内容须目视确认。"}


def locate(data, manifest):
    if not isinstance(manifest, dict) or data["source_sha256"] != manifest.get("source_sha256"):
        raise ValueError("意见与原稿版本不符，请重新定位。")
    findings = manifest.get("findings")
    if not isinstance(findings, list):
        raise ValueError("findings 应为数组。")
    index = {}
    visuals = {}
    for slide in data["slides"]:
        for obj in slide["visual_objects"]:
            if obj["id"] in visuals:
                raise ValueError(f"对象标识重复：{obj['id']}")
            visuals[obj["id"]] = (slide, obj)
        for paragraph in slide["paragraphs"]:
            key = paragraph["id"]
            if key in index:
                raise ValueError(f"段标识重复：{key}")
            index[key] = (slide, paragraph)
    result = defaultdict(list)
    for item in findings:
        if not isinstance(item, dict) or not isinstance(item.get("comment"), str) or not item["comment"].strip():
            raise ValueError("意见须为非空文本。")
        comment = item["comment"]
        if "object" in item:
            if not isinstance(item["object"], str) or item["object"] not in visuals:
                raise ValueError("目视意见没有有效对象标识。")
            if (("quote" in item) == ("region" in item) or "paragraph" in item or "start" in item):
                raise ValueError("目视意见须选择 quote（原文）或 region（区域）之一，无字符偏移。")
            quote = item.get("quote", item.get("region"))
            if not isinstance(quote, str) or not quote.strip():
                raise ValueError("目视意见须指明图内原文或区域。")
            slide, obj = visuals[item["object"]]
            label = "图内引文" if "quote" in item else "图内区域"
            result[slide["part"]].append(f"人工目视定位　{obj['location']}〔{obj['kind']}〕\n{label}　{quote}\n批注　{comment}")
            continue
        if not isinstance(item.get("paragraph"), str) or item["paragraph"] not in index:
            raise ValueError("意见没有有效段标识。")
        slide, paragraph = index[item["paragraph"]]
        quote = item.get("quote")
        if not isinstance(quote, str) or not quote.strip() or "region" in item:
            raise ValueError("段落意见须提供非空引文。")
        source = paragraph["text"]
        offset = item.get("start", source.find(quote))
        if type(offset) is not int or offset < 0 or not source.startswith(quote, offset):
            raise ValueError(f"{paragraph['id']} 引文与原稿不匹配。")
        if "start" not in item and source.find(quote, offset + 1) >= 0:
            raise ValueError("段内存在重复引文，请用 start 区分。")
        result[slide["part"]].append(f"{paragraph['location']} / 第 {offset+1} 字起\n原文　{quote}\n批注　{comment}")
    for page, notes in result.items():
        if len(notes) != len(set(notes)):
            raise ValueError(f"{page} 有相同位置、引文和内容的重复意见，请合并。")
    return result


def html_notes(data, located, filename):
    rows = []
    for slide in data["slides"]:
        findings = located.get(slide["part"])
        if findings:
            title = f"第 {slide['page']} 页　{slide['title']}"
            if slide["title_hidden"]:
                title += "〔隐藏页题〕"
            if slide["title_off_slide"]:
                title += "〔页题框在画面外〕"
            if slide["hidden"]:
                title += "〔隐藏页〕"
            rows.append("<h2>" + escape(title) + "</h2><ol>" +
                        "".join("<li>" + escape(n) + "</li>" for n in findings) + "</ol>")
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>PPT 审阅意见</title>'
            '<style>body{max-width:52em;margin:2em auto;font:1rem/1.6 system-ui;padding:0 1em}'
            'li{white-space:pre-wrap;overflow-wrap:anywhere;margin:1em 0}</style><h1>PPT 审阅意见</h1>'
            f'<p>原稿　{escape(filename)}<br>SHA-256　<code>{data["source_sha256"]}</code></p>'
            + ("".join(rows) or "<p>本次未标注意见。</p>") + "</html>")


def add_part(z, changes, types, parent, target, kind, root):
    if target in z.NameToInfo or target in changes:
        raise ValueError(f"部件重名：{target}")
    rels, _ = relationships(z, parent)
    existing = {rel.get("Id") for rel in rels}
    i = 1
    while f"rId{i}" in existing:
        i += 1
    E.SubElement(rels, PR + "Relationship", Id=f"rId{i}", Type=REL_TYPE + kind,
                 Target=posixpath.relpath(target, posixpath.dirname(parent)))
    changes[rels_name(parent)] = xml(rels)
    E.SubElement(types, CT + "Override", PartName="/" + target, ContentType=MIME + kind + "+xml")
    changes[target] = xml(root)


def write_comments(z, dest, located):
    changes = {}
    types = part(z, TYPES)
    authors = E.Element(P + "cmAuthorLst", nsmap={"p": P[1:-1]})
    E.SubElement(authors, P + "cmAuthor", id="0", name="Unbot", initials="UB", clrIdx="0",
                 lastIdx=str(sum(map(len, located.values()))))
    add_part(z, changes, types, PRESENTATION, AUTHOR, "commentAuthors", authors)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    size = part(z, PRESENTATION).find(P + "sldSz")
    # Page sizes are in EMUs; classic note positions in PowerPoint are in eighths of a point.
    rows = max(1, int(size.get("cy")) // (12700 * 25) - 1) if size is not None else 1
    columns = max(1, int(size.get("cx")) // (12700 * 30) - 1) if size is not None else 1
    index = 0
    for page, (parent, notes) in enumerate(located.items(), 1):
        root = E.Element(P + "cmLst", nsmap={"p": P[1:-1]})
        for slot, note in enumerate(notes):
            index += 1
            cm = E.SubElement(root, P + "cm", authorId="0", dt=timestamp, idx=str(index))
            E.SubElement(cm, P + "pos", x=str(48 + slot // rows % columns * 240), y=str(48 + slot % rows * 200))
            E.SubElement(cm, P + "text").text = note
        add_part(z, changes, types, parent, f"ppt/comments/comment{page}.xml", "comments", root)
    changes[TYPES] = xml(types)
    with ZipFile(dest, "w", ZIP_DEFLATED) as new:
        new.comment = z.comment
        for info in z.infolist():
            if info.filename not in changes:
                with z.open(info) as source, new.open(copy(info), "w") as out:
                    shutil.copyfileobj(source, out)
        for name, payload in changes.items():
            new.writestr(name, payload)
    with ZipFile(dest) as check:
        for parent, expected in located.items():
            _, links = relationships(check, parent)
            parts = [path for kind, path in links.values() if kind == REL_TYPE + "comments"]
            if len(parts) != 1 or [t.text for t in part(check, parts[0]).findall("./" + P + "cm/" + P + "text")] != expected:
                raise ValueError(f"{parent} 的批注反读不符。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    a = actions.add_parser("inspect")
    a.add_argument("input", type=Path)
    a.add_argument("--output", type=Path)
    a = actions.add_parser("annotate")
    for arg in ("input", "manifest", "output"):
        a.add_argument(arg, type=Path)
    args = parser.parse_args()
    try:
        if args.input.suffix.lower() != ".pptx":
            raise ValueError("输入须为 .pptx。")
        with TemporaryFile() as snapshot:
            digest = hashlib.sha256()
            with args.input.open("rb") as src:
                for chunk in iter(lambda: src.read(1024 * 1024), b""):
                    digest.update(chunk)
                    snapshot.write(chunk)
            with ZipFile(snapshot) as z:
                data = inspect(z, digest.hexdigest())
                if args.action == "inspect":
                    content = json.dumps(data, ensure_ascii=False, indent=2)
                    if args.output:
                        with new_output(args.output) as tmp:
                            tmp.write_text(content + "\n", encoding="utf-8")
                    else:
                        print(content)
                    return
                manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
                located = locate(data, manifest)
                with new_output(args.output) as tmp:
                    suffix = args.output.suffix.lower()
                    if suffix == ".html":
                        tmp.write_text(html_notes(data, located, args.input.name), encoding="utf-8")
                    elif suffix != ".pptx":
                        raise ValueError("审阅结果请选择 .pptx 或 .html。")
                    elif not located:
                        snapshot.seek(0)
                        with tmp.open("wb") as out:
                            shutil.copyfileobj(snapshot, out)
                    elif data["write_blockers"]:
                        raise ValueError("此原稿须使用原生编辑器或输出 .html：" + "、".join(data["write_blockers"]))
                    else:
                        write_comments(z, tmp, located)
                print(f"已写入 {sum(map(len, located.values()))} 条意见：{args.output}")
    except (BadZipFile, KeyError, OSError, ValueError, E.XMLSyntaxError) as exc:
        parser.exit(2, f"无法完成：{exc}\n")


if __name__ == "__main__":
    main()
