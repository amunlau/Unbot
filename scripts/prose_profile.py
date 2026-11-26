"""Locate passages for editorial review in Chinese Word or Markdown prose (read only)."""
from __future__ import annotations

import argparse
from importlib.util import module_from_spec, spec_from_file_location
import json
import re
import statistics
import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET


def _load_markdown_rules():
    # File-based hosts and python -I do not put the script's directory on sys.path.
    path = Path(__file__).resolve().with_name("check_markdown_structure.py")
    spec = spec_from_file_location("_unbot_check_markdown_structure", path)
    if not path.is_file() or spec is None or spec.loader is None:
        raise ImportError(f"缺少同目录 Markdown 结构模块：{path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


md = _load_markdown_rules()

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TAIL = re.compile(r"仍需|仍须|尚未|未披露|未公开|不能|不足以|不等于|有待|需要|建议|须要|(?<![响对相顺供适感效反])应(?![用答急付邀聘届征试酬])")
SPLIT = re.compile(r"[。！？!?]+[”’）】」』]*|\.(?=\s|$)")
TOC_STYLE = re.compile(r"toc\s*(?:heading|\d+)|目录(?:标题|\s*\d+)?", re.I)
EXCLUDE_STYLE = re.compile(r"caption|题注|title|subtitle|副标题|标题|bibliography|参考文献|footnote\s*text|endnote\s*text|table\s*of\s*figures", re.I)
HEADING_STYLE = re.compile(r"(?:heading|标题)\s*([1-9])", re.I)
SKIP_INLINE = {W + k for k in ("drawing", "pict", "object", "del", "moveFrom", "pPr", "rPr")}
LABEL = re.compile(r"(?<!附)(?P<kind>图|(?<![图代发])表)[ \t\n\u00a0\u3000]*"
                   r"(?P<number>[0-9]+(?:[.-][0-9]+)*)(?![0-9A-Za-z]|[.-][0-9A-Za-z])")
SHORTHAND = re.compile(r"(?:\s*(?:[、,，/／–—~～]|至|到|及|和|与)\s*(?:图|表)?\s*[0-9]+(?:[.-][0-9]+)*)+")
CAPTION_STYLE = re.compile(r"caption|题注|图题|表题", re.I)
LINK_DEFINITION = re.compile(r"^ {0,3}\[[^\]\n]+\]:[ \t]*\S")
FIGURE_PREDICATE = re.compile(r"所示|给出|展示|列出|说明|显示|表明|汇总|归纳|比较了|"
                              r"中(?:$|[\s，,。:：]|的|所|可见|可以|给出|显示|列出)")
MD_TARGET = r"\((?:\\[^\n]|[^\\()\n]|\((?:\\[^\n]|[^\\()\n])*\))*\)|\[[^\]\n]*\]"
MD_CODE = r"(?<!`)(?P<ticks>`+)(?!`).*?(?<!`)(?P=ticks)(?!`)"
MD_PROTECTED = re.compile(rf"<!--.*?(?:-->|\Z)|{MD_CODE}|"
                          rf"!\[[^\]\n]*\](?:{MD_TARGET})?|(?<=\])(?:{MD_TARGET})|"
                          r"<[^<>\n]+>|^ {0,3}\[[^\]\n]+\]:[^\n]*",
                          re.S | re.M)
MD_READING_LINK = re.compile(rf"(?P<code>{MD_CODE})|(?<!\\)!\[[^\]\n]*\](?:{MD_TARGET})?|"
                             rf"(?<!\\)\[(?P<label>[^\[\]\n]*)\](?:{MD_TARGET})", re.S)


def visible_word_paragraph(paragraph):
    """Return visible text and offsets of cached field results within this paragraph."""
    parts, spans, stack = [], [], []
    offset = 0

    def record(start, instruction):
        command = instruction.strip().split(maxsplit=1)
        if start is not None and start < offset:
            spans.append((start, offset, command[0].upper() if command else ""))

    def visit(node):
        nonlocal offset
        if node.tag in SKIP_INLINE:
            return
        if node.tag == W + "r":
            hidden = node.find(f"{W}rPr/{W}vanish")
            if hidden is not None and hidden.get(W + "val", "1").lower() not in ("0", "false", "off"):
                return
        if node.tag == W + "fldChar":
            marker = node.get(W + "fldCharType")
            if marker == "begin":
                stack.append([[], None])
            elif stack and marker == "separate":
                stack[-1][1] = offset
            elif stack and marker == "end":
                code, start = stack.pop()
                record(start, "".join(code))
        elif node.tag == W + "instrText":
            if stack:
                stack[-1][0].append(node.text or "")
        elif node.tag in (W + "t", W + "tab", W + "br", W + "cr"):
            if any(start is None for _, start in stack):
                return  # A nested result inside an outer field's instruction is not displayed.
            text = (node.text or "") if node.tag == W + "t" else " "
            parts.append(text)
            offset += len(text)
        else:
            start = offset
            for child in node:
                visit(child)
            if node.tag == W + "fldSimple":
                record(start, node.get(W + "instr", ""))

    visit(paragraph)
    raw = "".join(parts)
    trim = len(raw) - len(raw.lstrip())
    return raw.strip(), [(a - trim, b - trim, name) for a, b, name in spans]


def caption_text(text, match):
    """A bare number and title are only a candidate; avoid ordinary figure-led sentences."""
    tail = text[match.end():].lstrip("*_")
    return (not tail or (re.match(r"[\s:：]", tail) and not re.search(r"[。！？!?；;]", tail)
                         and not FIGURE_PREDICATE.match(tail.lstrip())))


def field_source(match, spans):
    start, end = match.span("number")
    # Chapter captions can use separate STYLEREF and SEQ fields (e.g. 2-3).
    last_part = re.split(r"[.-]", match["number"])[-1]
    last_start = end - len(last_part)
    for left, right, command in spans:
        if left <= last_start and right >= end:
            return command if command in ("REF", "SEQ") else "other_field"
    if any(left < end and right > start for left, right, _ in spans):
        return "other_field"
    return "text"


def numbered_mentions(text, kind, loc, spans=(), caption_source="caption_text"):
    """Collect direct visible labels; a caption can only contribute its own leading label."""
    result = []
    for match in LABEL.finditer(text):
        if (match["kind"] == "表" and text[max(0, match.start() - 1):match.start()] == "量"
                and text[match.end():].lstrip().startswith("分")):
            continue
        if kind == "caption" and (result or text[:match.start()].strip(" \t*_")):
            break
        source = field_source(match, spans)
        if kind == "caption" and source == "text":
            source = caption_source
        position = loc
        if loc.startswith("L"):
            position = f"L{int(loc[1:]) + text.count(chr(10), 0, match.start())}"
        excerpt = text[max(0, match.start() - 25):match.end() + 45].strip().replace("\n", " ")
        hit = {"loc": position, "source": source, "excerpt": excerpt}
        shorthand = SHORTHAND.match(text, match.end()) if kind == "body" else None
        if shorthand:
            hit["shorthand"] = match[0] + shorthand[0]
        result.append((match["kind"] + match["number"], hit))
    return result


def markdown_visible(text):
    # Keep offsets and newlines when hiding common inline syntax from the number scan.
    return MD_PROTECTED.sub(lambda m: re.sub(r"[^\n]", " ", m[0]), text)


def markdown_reading_text(text):
    return MD_READING_LINK.sub(lambda m: m["code"] or m["label"] or "", text)


def strip_markdown_comments(line, continuing):
    if continuing:
        _, end, line = line.partition("-->")
        if not end:
            return "", True
    continuing = False

    def strip(match):
        nonlocal continuing
        if match[0].startswith("<!--"):
            continuing = not match[0].endswith("-->")
            return ""
        return match[0]

    visible = MD_PROTECTED.sub(strip, line)
    return visible, continuing


def val(element, path):
    child = element.find(path)
    return child.get(W + "val", "") if child is not None else ""


def word_blocks(path, mentions=None):
    with zipfile.ZipFile(path) as doc:
        body = ET.fromstring(doc.read("word/document.xml")).find(W + "body")
        if body is None:
            raise ValueError("未识别到 Word 主文档正文")
        styles = {}
        if "word/styles.xml" in doc.namelist():
            for style in ET.fromstring(doc.read("word/styles.xml")).findall(W + "style"):
                styles[style.get(W + "styleId")] = style

    def role(p):
        outline = val(p, f"{W}pPr/{W}outlineLvl")
        key = val(p, f"{W}pPr/{W}pStyle")
        seen = set()
        while key and key not in seen:
            seen.add(key)
            style = styles.get(key)
            name = val(style, W + "name") if style is not None else key
            if TOC_STYLE.fullmatch(name) or TOC_STYLE.fullmatch(key):
                return "toc", 0
            if CAPTION_STYLE.fullmatch(name) or CAPTION_STYLE.fullmatch(key):
                return "caption", 0
            if EXCLUDE_STYLE.fullmatch(name) or EXCLUDE_STYLE.fullmatch(key):
                return "other", 0
            if not outline and style is not None:
                outline = val(style, f"{W}pPr/{W}outlineLvl")
            heading = HEADING_STYLE.fullmatch(name) or HEADING_STYLE.fullmatch(key)
            if not outline and heading:
                outline = str(int(heading[1]) - 1)
            key = val(style, W + "basedOn") if style is not None else ""
        if outline.isdigit() and int(outline) <= 8:
            return "heading", int(outline) + 1
        return "body", 0

    def blocks(node):
        for child in node:
            if child.tag in (W + "p", W + "tbl"):
                yield child
            elif child.tag in (W + "sdt", W + "sdtContent", W + "customXml", W + "ins", W + "moveTo"):
                yield from blocks(child)

    for number, block in enumerate(blocks(body), 1):
        loc = f"B{number}"
        if block.tag == W + "tbl":
            yield "table", 0, loc, ""
            continue
        kind, level = role(block)
        content, spans = visible_word_paragraph(block)
        if content:
            lead = LABEL.match(content)
            plain_caption = False
            if kind == "body" and lead:
                source = field_source(lead, spans)
                plain_caption = source == "text" and caption_text(content, lead)
                if source == "SEQ" or plain_caption:
                    kind = "caption"
            if mentions is not None and kind in ("caption", "body"):
                caption_source = "caption_text" if plain_caption else "caption_style"
                hits = numbered_mentions(content, kind, loc, spans, caption_source)
                if hits:
                    mentions[loc] = hits
            yield kind, level, loc, content


def opening_fence(line):
    fence = md.FENCE.fullmatch(line)
    if fence and (fence[2][0] == "~" or "`" not in fence[3]):
        return fence[2]
    return None


def table_cells(line):
    text = line.strip()
    pipes = [i for i, char in enumerate(text) if char == "|" and not md.escaped(text, i)]
    if not pipes:
        return []
    boundaries = [-1, *pipes, len(text)]
    cells = [text[left + 1:right] for left, right in zip(boundaries, boundaries[1:])]
    if pipes[0] == 0:
        cells.pop(0)
    if pipes[-1] == len(text) - 1:
        cells.pop()
    return cells


def markdown_blocks(path, mentions=None):
    # read_text normalizes CR and CRLF. Unicode paragraph/line separators
    # inside a Markdown source line must not shift subsequent L locations.
    lines = path.read_text(encoding="utf-8-sig").split("\n")
    start = i = 0
    buf = []
    in_comment = False

    def prose():
        loc = f"L{start + 1}"
        if mentions is not None:
            visible = markdown_visible("\n".join(buf))
            hits = numbered_mentions(visible, "body", loc)
            if hits:
                mentions[loc] = hits
        return "body", 0, loc, " ".join(buf)

    while i < len(lines):
        line, here = lines[i], i
        i += 1
        kind, level, txt = "", 0, ""
        if in_comment or ("<!--" in line and not opening_fence(line)
                          and (buf or not line.startswith(("    ", "\t")))):
            was_in_comment = in_comment
            line, in_comment = strip_markdown_comments(line, in_comment)
            if was_in_comment and not line.strip() and buf:
                buf.append("")  # Retain the original line offsets within the paragraph.
                continue
        fence = opening_fence(line)
        if fence:
            close = re.compile(r"^ {0,3}" + fence[0] + "{" + str(len(fence)) + r",}[ \t]*$")
            while i < len(lines) and not close.fullmatch(lines[i]):
                i += 1
            i += 1
        elif here == 0 and line.strip() == "---" and any(x.strip() in ("---", "...") for x in lines[i:]):
            while lines[i].strip() not in ("---", "..."):
                i += 1
            i += 1
        elif md.HEADING.match(line):
            prefix = re.match(r"#+", line.lstrip())[0]
            kind, level, txt = "heading", len(prefix), re.sub(r"\s+#+\s*$", "", line.lstrip()[len(prefix):]).strip()
        elif buf and md.SETEXT.fullmatch(line):
            kind, level, txt = "heading", (1 if line.lstrip()[0] == "=" else 2), " ".join(buf)
            here, buf = start, []
        elif line.startswith(("    ", "\t")):
            if buf and line.strip():
                buf.append(line.strip())
                continue
        elif ("|" in line and i < len(lines) and not lines[i].startswith(("    ", "\t"))
              and not md.LIST.match(line) and not line.lstrip().startswith(">")
              and (cells := table_cells(lines[i])) and len(cells) == len(table_cells(line))
              and all(re.fullmatch(r"\s*:?-+:?\s*", col) for col in cells)):
            i += 1
            while (i < len(lines) and table_cells(lines[i])
                   and not (md.HEADING.match(lines[i]) or md.LIST.match(lines[i]) or opening_fence(lines[i])
                            or lines[i].lstrip().startswith((">", "<!--", "<table")))):
                i += 1
            kind = "table"
        elif re.match(r"^\s*<table(?:\s|>)", line, re.I):
            while "</table>" not in lines[i - 1].lower() and i < len(lines):
                i += 1
            kind = "table"
        elif (line.strip() and not md.LIST.match(line) and not LINK_DEFINITION.match(line)
              and not line.lstrip().startswith(">")
              and not (line.lstrip().startswith("![") and not markdown_reading_text(line).strip())
              and not re.fullmatch(r"\s*([-*_])(?:\s*\1){2,}\s*", line)):
            visible = markdown_visible(line).strip().strip("*_")
            lead = LABEL.match(visible)
            wrapped_label = (lead and lead.end() == len(visible)
                             and ((buf and re.search(r"(?:见|如|参照|根据|对照|依据|参考)$", buf[-1]))
                                  or (i < len(lines) and FIGURE_PREDICATE.match(lines[i].lstrip()))))
            if (lead and caption_text(visible, lead)
                    and not wrapped_label
                    and not (i < len(lines) and md.SETEXT.fullmatch(lines[i]))):
                kind, txt = "caption", visible
            else:
                if not buf:
                    start = here
                buf.append(line.strip())
                continue
        if buf:
            yield prose()
            buf = []
        if kind:
            loc = f"L{here + 1}"
            if mentions is not None and kind == "caption":
                mentions[loc] = numbered_mentions(txt, kind, loc)
            yield kind, level, loc, txt
    if buf:
        yield prose()


def figure_table_mentions(blocks, mentions, last_toc):
    items = {}
    for kind, _, loc, _ in blocks[last_toc + 1:]:
        key = "captions" if kind == "caption" else "body_mentions"
        for label, hit in mentions.get(loc, []):
            entry = items.setdefault(label, {"label": label, "captions": [], "body_mentions": []})
            entry[key].append(hit)
    for entry in items.values():
        captions, body = entry["captions"], entry["body_mentions"]
        first = body[0]["loc"] if body else None
        entry["first_body_loc"] = first
        if len(captions) > 1:
            position = "ambiguous_caption"
        elif not captions:
            position = "no_caption"
        elif not first:
            position = "no_body_mention"
        elif int(first[1:]) < int(captions[0]["loc"][1:]):
            position = "before_caption"
        else:
            position = "after_caption"
        entry["position"] = position
    return {
        "scope": "匹配可见的中文图、表和阿拉伯编号。点号或短横线连接的数字按一个编号。"
                 "no_body_mention 仅指已读正文未见这个显式编号。区间和省略列举不展开，shorthand 标出可识别的原文。"
                 "英文 Figure/Table、附图附表、字母编号、图中或表内文字、复杂 Markdown 容器需另查。"
                 "先后相对于题注，独立编号和短标题是题注候选。Word 仅读取段内域的缓存，未更新域或核验书签。"
                 "复合编号按末级数字的域标记来源，其他局部域记为 other_field。text 表示编号内无可辨域标记。",
        "items": list(items.values()),
    }


def profile(path):
    mentions = {}
    is_markdown = path.suffix.lower() in (".md", ".markdown")
    if path.suffix.lower() == ".docx":
        blocks = list(word_blocks(path, mentions))
    elif is_markdown:
        blocks = list(markdown_blocks(path, mentions))
    else:
        raise ValueError("支持 .docx、.md 和 .markdown")
    first_heading = next((i for i, b in enumerate(blocks) if b[0] == "heading"), len(blocks))
    # A cover can precede the TOC. Unheaded prose after its last entry can be an introduction.
    last_toc = -1
    if first_heading < len(blocks):
        last_toc = max((i for i in range(first_heading) if blocks[i][0] == "toc"), default=-1)
    headings = []
    sections = []
    paragraphs = []
    heading_stack = []

    def section(loc, path):
        result = {"loc": loc, "path": path, "paragraphs": [], "subtree_chars": 0}
        sections.append(result)
        return result

    current = None
    for i, (kind, level, loc, text) in enumerate(blocks):
        if kind == "heading":
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            parent_path = heading_stack[-1][1]["path"] if heading_stack else []
            current = section(loc, [*parent_path, text])
            heading_stack.append((level, current))
            headings.append({"loc": loc, "level": level, "title": text})
        elif kind == "body" and i > last_toc:
            reading = markdown_reading_text(text) if is_markdown else text
            if not reading.strip():
                continue
            if current is None:
                current = section(loc, [])
            sentences = [s.strip() for s in SPLIT.split(reading) if s.strip()]
            tail = sentences[-1] if sentences else reading
            p = {"loc": loc, "chars": len(re.sub(r"\s", "", reading)), "sentences": len(sentences),
                 "opening": text[:50], "ending": tail[-100:], "ending_terms": sorted(set(TAIL.findall(tail)))}
            paragraphs.append(p)
            current["paragraphs"].append(p)
            current["subtree_chars"] += p["chars"]
            for _, parent in heading_stack[:-1]:
                parent["subtree_chars"] += p["chars"]

    windows = []
    for s in sections:
        ps = s["paragraphs"]
        s["direct_chars"] = sum(p["chars"] for p in ps)
        for a, b, c in zip(ps, ps[1:], ps[2:]):
            lengths = [p["chars"] for p in (a, b, c)]
            windows.append({"path": s["path"], "loc": [p["loc"] for p in (a, b, c)], "chars": lengths,
                            "relative_range": (max(lengths) - min(lengths)) / statistics.mean(lengths)})
    closest = sorted(windows, key=lambda w: w["relative_range"])[:10]
    for window in closest:
        window["relative_range"] = round(window["relative_range"], 3)
    lengths = [p["chars"] for p in paragraphs]
    return {
        "file": path.name,
        "method": "B为Word正文段或表的顺序号（从1起），L为Markdown行号。段长含标点、不含空白，句数近似。"
                  "Markdown 段首保留行内源码；计算段长与近似末句时，一般链接取可见文字，略过图片标记。"
                  "direct_chars 只计直属正文，subtree_chars 另含下级小节正文。定位词可能属于必要条件或普通词。"
                  "窗口按三个相邻直属正文段的相对极差取样。各项供回读。",
        "scope": "Word读取主文档可识别的正文与大纲样式，略过表格、目录、题注等样式及可识别前置材料。Markdown按常用标题、普通段落、围栏及管线表处理，复杂容器请对照原稿。",
        "body_paragraphs": len(lengths), "title_count": len(headings),
        "tables": sum(b[0] == "table" for b in blocks),
        "paragraph_chars": {"min": min(lengths), "median": statistics.median(lengths), "max": max(lengths),
                            "cv": round(statistics.pstdev(lengths) / statistics.mean(lengths), 3)} if lengths else {},
        "sentence_counts": dict(sorted(Counter(p["sentences"] for p in paragraphs).items())),
        "paragraph_end_hits": sum(bool(p["ending_terms"]) for p in paragraphs),
        "heading_forms": [{"level": lvl, "count": sum(h["level"] == lvl for h in headings),
                           "containing_与": [h for h in headings if h["level"] == lvl and "与" in h["title"]]}
                          for lvl in sorted({h["level"] for h in headings})],
        "closest_three_paragraph_windows": closest,
        "figure_table_mentions": figure_table_mentions(blocks, mentions, last_toc),
        "sections": sections,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        result = profile(args.input)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        parser.exit(2, f"{args.input}: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
