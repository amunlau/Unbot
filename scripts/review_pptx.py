"""按实际页序提取 PPTX 文本和备注，将编辑意见写入副本的页级批注或 HTML 页位清单。"""

import argparse
from collections import defaultdict
from copy import copy
from decimal import Decimal, InvalidOperation
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

from review_classification import FINDING_SCHEMA, review_findings, review_language
from review_docx import CT, PR, REL_TYPE, TYPES, add_script_range, new_output, part, xml


P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
PRESENTATION = "ppt/presentation.xml"
MIME = "application/vnd.openxmlformats-officedocument.presentationml."
AUTHOR = "ppt/commentAuthors.xml"
TEXT_STYLE_PARTS = {REL_TYPE + tag for tag in ("slideLayout", "slideMaster", "notesMaster", "theme", "themeOverride")}


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


def baseline(props):
    if props is None or "baseline" not in props.attrib:
        return None
    raw = props.get("baseline")
    try:
        value = Decimal(raw[:-1]) if raw.endswith("%") else int(raw)
        if isinstance(value, Decimal) and not value.is_finite():
            return "unknown"
    except (ValueError, InvalidOperation):
        return "unknown"
    if value > 0:
        return "superscript"
    return "subscript" if value < 0 else "baseline"


def list_baseline(style, level):
    if style is None:
        return None
    return (baseline(style.find(f"{A}lvl{level}pPr/{A}defRPr"))
            or baseline(style.find(f"{A}defPPr/{A}defRPr")))


def read_paragraphs(body, key, label, slide, language, inherited, default_style):
    if body is None:
        return
    for i, para in enumerate(body.findall(A + "p"), 1):
        text, ranges = [], []
        offset, uncertain = 0, False
        props = para.find(A+"pPr")
        level = int(props.get("lvl", "0")) + 1 if props is not None else 1
        fallback = list_baseline(default_style, level) or "baseline"
        if inherited.difference({fallback}):
            fallback = "unknown"
        default = (baseline(para.find(f"{A}pPr/{A}defRPr"))
                   or list_baseline(body.find(A+"lstStyle"), level) or fallback)
        position = f"{label} / Paragraph {i}" if language == "en" else f"{label} / 段 {i}"
        for child in para:
            if child.tag == A + "r":
                value = child.findtext(A + "t", default="")
                script = baseline(child.find(A+"rPr")) or default
                end = offset + len(value)
                add_script_range(ranges, offset, end, script)
                uncertain |= bool(value) and script == "unknown"
                text.append(value)
                offset = end
            elif child.tag == A + "br":
                text.append("\n")
                offset += 1
            elif child.tag not in {A + "pPr", A + "endParaRPr"}:
                slide["manual_review"].append(
                    position + (" contains a field, equation or other embedded content"
                                if language == "en" else " 含域、公式或其他内嵌内容"))
                break
        else:
            value = "".join(text)
            if value.strip():
                entry = {"id": f"{key}/P{i}", "location": position, "text": value}
                if ranges:
                    entry["script_ranges"] = ranges
                if uncertain:
                    slide["manual_review"].append(
                        position + (" — verify inherited or unrecognized baseline formatting in PowerPoint."
                                    if language == "en" else " 的上下标涉及继承或未识别的基线格式，请在 PowerPoint 中核对。"))
                slide["paragraphs"].append(entry)


def drawing_kind(shape, placeholder, language):
    if shape.tag == P + "cxnSp":
        return "Connector" if language == "en" else "连接线"
    props = shape.find(P + "spPr")
    if props is None:
        return None
    if props.find(A + "blipFill") is not None:
        return "Picture-filled shape" if language == "en" else "图片填充形状"
    textbox = shape.find("./" + P + "nvSpPr/" + P + "cNvSpPr")
    if placeholder is not None or (textbox is not None and textbox.get("txBox") in ("1", "true")):
        return None
    if any(props.find(A + tag) is not None for tag in ("prstGeom", "custGeom")):
        return "Drawing shape" if language == "en" else "绘图形状"
    return None


def box_outside_canvas(shape, canvas):
    """Check explicit unrotated boxes in slide coordinates, without inferring text visibility."""
    if canvas is None:
        return False
    transform = (shape.find(P + "xfrm") if shape.tag == P + "graphicFrame"
                 else shape.find("./" + P + "spPr/" + A + "xfrm"))
    if transform is None or int(transform.get("rot", "0")) % 21600000:
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


def read_shapes(tree, key, parent, slide, language, inherited, default_style,
                notes=False, parent_hidden=False, canvas=None):
    if tree is None:
        raise ValueError(f"Slide {slide['page']} has no shape tree." if language == "en"
                         else f"第 {slide['page']} 页缺少对象树。")
    for shape in tree:
        if shape.tag in (P + "nvGrpSpPr", P + "grpSpPr"):
            continue
        nv = shape.find("./*/" + P + "cNvPr")
        if nv is None:
            slide["manual_review"].append(f"{parent} / {E.QName(shape).localname}")
            continue
        shape_id = nv.get("id", "?")
        name = nv.get("name") or ("Object" if language == "en" else "对象")
        loc = f"{parent} / {name} (ID {shape_id})"
        shape_key = f"{key}/{shape_id}"
        own_hidden = nv.get("hidden") in ("1", "true")
        hidden = parent_hidden or own_hidden
        if own_hidden:
            loc += " [hidden object]" if language == "en" else "〔隐藏对象〕"
        ph = shape.find("./*/" + P + "nvPr/" + P + "ph")
        kind = ph.get("type", "obj") if ph is not None else None
        is_title = not notes and kind in ("title", "ctrTitle")
        outside = box_outside_canvas(shape, canvas)
        if outside:
            if is_title:
                loc += " [title outside slide]" if language == "en" else "〔页题框在画面外〕"
            else:
                loc += " [object box outside slide]" if language == "en" else "〔对象框在画面外〕"
        if notes and kind in ("sldImg", "sldNum", "dt", "hdr", "ftr"):
            continue
        if shape.tag == P + "grpSp":
            read_shapes(shape, shape_key, loc, slide, language, inherited, default_style, notes, hidden)
        elif shape.tag in (P + "sp", P + "cxnSp"):
            body = shape.find(P + "txBody")
            before = len(slide["paragraphs"])
            checks_before = len(slide["manual_review"])
            read_paragraphs(body, shape_key, loc, slide, language, inherited, default_style)
            if is_title and len(slide["paragraphs"]) > before:
                previous_unshown = slide["title_hidden"] or slide["title_off_slide"]
                if not slide["title"] or (previous_unshown and not (hidden or outside)):
                    title_parts = slide["paragraphs"][before:]
                    slide["title"] = " ".join(p["text"] for p in title_parts)
                    slide["title_paragraphs"] = [p["id"] for p in title_parts]
                    slide["title_needs_review"] = len(slide["manual_review"]) != checks_before
                    slide["title_hidden"] = hidden
                    slide["title_off_slide"] = outside
            drawing = drawing_kind(shape, kind, language)
            if drawing:
                slide["visual_objects"].append({"id": shape_key, "location": loc, "kind": drawing})
        elif shape.tag == P + "graphicFrame":
            frame = shape.find("./" + A + "graphic/" + A + "graphicData")
            table = frame.find(A + "tbl") if frame is not None else None
            if table is None:
                uri = frame.get("uri", "") if frame is not None else ""
                suffix = uri.rsplit("/", 1)[-1]
                if language == "en":
                    kind = {"chart": "Chart", "diagram": "SmartArt", "ole": "Embedded object"}.get(suffix, "Graphic object")
                else:
                    kind = {"chart": "图表", "diagram": "SmartArt", "ole": "嵌入对象"}.get(suffix, "图形对象")
                slide["visual_objects"].append({"id": shape_key, "location": loc, "kind": kind})
                continue
            for row, tr in enumerate(table.findall(A + "tr"), 1):
                for col, tc in enumerate(tr.findall(A + "tc"), 1):
                    if any(tc.get(flag) in ("1", "true") for flag in ("hMerge", "vMerge")):
                        # PowerPoint displays only the merge-origin cell. A spanned cell
                        # may retain text that becomes visible only after unmerging.
                        continue
                    cell = f"Row {row}, Column {col}" if language == "en" else f"第 {row} 行第 {col} 列"
                    read_paragraphs(tc.find(A + "txBody"), f"{shape_key}/R{row}C{col}",
                                    f"{loc} / {cell}", slide, language, inherited, default_style)
        elif shape.tag == P + "pic":
            slide["visual_objects"].append({"id": shape_key, "location": loc,
                                            "kind": "Picture or media" if language == "en" else "图片或媒体"})
        else:
            element = E.QName(shape).localname
            slide["manual_review"].append(loc + (f" [{element}]" if language == "en" else f"〔{element}〕"))


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


def inherited_baselines(z, targets, cache):
    # A placeholder can inherit from its layout or master. When such parts
    # specify a baseline, their visual result must be checked in PowerPoint.
    positions = set()
    for rel_type, path in targets.values():
        if rel_type not in TEXT_STYLE_PARTS:
            continue
        if path not in cache:
            cache[path] = set()
            root = part(z, path)
            # Only follow the inheritance direction, not a master's child layouts.
            children = {key: value for key, value in relationships(z, path)[1].items()
                        if value[0] != REL_TYPE + "slideLayout"}
            cache[path] = {baseline(r) for r in root.iter(A+"rPr", A+"defRPr") if "baseline" in r.attrib}
            cache[path].update(inherited_baselines(z, children, cache))
        positions.update(cache[path])
    return positions


def inspect(z, digest, language="zh"):
    names = z.namelist()
    if len(names) != len(set(names)):
        raise ValueError("The package contains duplicate part names." if language == "en" else "压缩包有重名部件，无法唯一定位。")
    presentation = part(z, PRESENTATION)
    if presentation.tag != P + "presentation":
        raise ValueError("Only Transitional PPTX is supported." if language == "en" else "仅支持常规 Transitional PPTX。")
    types = part(z, TYPES)
    _, roots = relationships(z, "")
    if (REL_TYPE + "officeDocument", PRESENTATION) not in roots.values() or not any(
        item.get("PartName") == "/" + PRESENTATION and item.get("ContentType") == MIME + "presentation.main+xml"
        for item in types
    ):
        raise ValueError("Unsupported presentation type or main part path." if language == "en" else "不支持的演示文稿类型或主部件路径。")
    blockers = []
    sensitive = ("comment", "person+xml", "digital-signature", "vbaproject", "macroenabled", "encrypted", "signature")
    if any(any(token in el.get("ContentType", "").lower() for token in sensitive) for el in types):
        blockers.append("Existing comments, person records, signatures, encryption or macros" if language == "en"
                        else "已有批注、人员记录、签名、加密或宏部件")
    if any(n.lower().startswith("_xmlsignatures/") for n in names) or presentation.find(P + "modifyVerifier") is not None:
        blockers.append("Digital signature or modification protection" if language == "en" else "数字签名或修改保护")
    _, targets = relationships(z, PRESENTATION)
    size = presentation.find(P + "sldSz")
    canvas = (int(size.get("cx", "")), int(size.get("cy", ""))) if size is not None else None
    slides = []
    first_number = int(presentation.get("firstSlideNum", "1"))
    default_style = presentation.find(P+"defaultTextStyle")
    baseline_cache = {}
    seen_parts = set()
    for page, sid in enumerate(presentation.findall("./" + P + "sldIdLst/" + P + "sldId"), 1):
        kind, path = targets[sid.get(RID)]
        if kind != REL_TYPE + "slide" or path in seen_parts:
            raise ValueError("Invalid slide reference type or repeated slide path." if language == "en" else "页引用类型或页路径异常。")
        seen_parts.add(path)
        root = part(z, path)
        key = f"S{page:03}"
        slide = {"page": page, "slide_number": first_number + page - 1, "slide_id": sid.get("id"),
                 "part": path, "title": "", "title_hidden": False,
                 "title_off_slide": False,
                 "hidden": root.get("show") in ("0", "false"), "paragraphs": [], "visual_objects": [], "manual_review": []}
        _, slide_targets = relationships(z, path)
        read_shapes(root.find("./" + P + "cSld/" + P + "spTree"), key,
                    "Slide" if language == "en" else "页面", slide, language,
                    inherited_baselines(z, slide_targets, baseline_cache), default_style, canvas=canvas)
        for rel_type, target in slide_targets.values():
            if rel_type == REL_TYPE + "notesSlide":
                notes = part(z, target)
                read_shapes(notes.find("./" + P + "cSld/" + P + "spTree"), key + "/N",
                            "Speaker notes" if language == "en" else "演讲备注", slide, language,
                            inherited_baselines(z, relationships(z, target)[1], baseline_cache), None, notes=True)
        if root.find(P + "timing") is not None:
            slide["manual_review"].append("Animation sequence" if language == "en" else "动画出现顺序")
        slides.append(slide)
    return {"finding_schema": FINDING_SCHEMA, "source_sha256": digest, "slides": slides, "write_blockers": blockers,
            "slide_show": show_settings(z, presentation, targets, slides),
            "coverage_note": ("Slides follow the editing order and include hidden slides. slide_show records saved show settings "
                              "and custom orders; null marks an unresolved slide. Verify navigation, animations, masters, "
                              "layouts and occlusion in the presentation. Inspect the content of visual_objects visually."
                              if language == "en" else "slides 按文件编辑页序，包含隐藏页。slide_show 列出保存的放映选择与自定义页序，无法解析的自定义页用 null 表示。实际跳转、动画、母版、版式及遮挡另查。visual_objects 只定位对象，图中内容须目视确认。")}


def page_note(location, item, comment, language):
    if "category" in item:
        return f"{comment}\n{location}"
    label = "Comment: " if language == "en" else "批注　"
    return f"{location}\n{label}{comment}"


def quote_with_formatting(paragraph, offset, quote, language):
    """Plain-text slide comments need a position for native superscripts and subscripts."""
    en = language == "en"
    lines = [("Quoted text: " if en else "原文　") + quote]
    for span in paragraph.get("script_ranges", []):
        start = max(span["start"] - offset, 0)
        end = min(span["end"] - offset, len(quote))
        if end <= start:
            continue
        first, last = start + 1, end  # Position within the quoted text, 1-based and inclusive.
        if en:
            label = "Superscript" if span["position"] == "superscript" else "Subscript"
            where = f"character {first}" if first == last else f"characters {first}–{last}"
            lines.append(f"{label} at {where} of quote: {quote[start:end]}")
        else:
            label = "上标" if span["position"] == "superscript" else "下标"
            where = f"第 {first} 字" if first == last else f"第 {first} 至 {last} 字"
            lines.append(f"引文{where}为{label}：{quote[start:end]}")
    return "\n".join(lines)


def locate(data, manifest):
    if not isinstance(manifest, dict) or data["source_sha256"] != manifest.get("source_sha256"):
        raise ValueError("意见与原稿版本不符，请重新定位。")
    language = review_language(manifest)
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
    for item, comment in review_findings(manifest):
        if "object" in item:
            if not isinstance(item["object"], str) or item["object"] not in visuals:
                raise ValueError("目视意见没有有效对象标识。")
            if (("quote" in item) == ("region" in item) or "paragraph" in item or "start" in item):
                raise ValueError("目视意见须选择 quote（原文）或 region（区域）之一，无字符偏移。")
            quote = item.get("quote", item.get("region"))
            if not isinstance(quote, str) or not quote.strip():
                raise ValueError("目视意见须指明图内原文或区域。")
            slide, obj = visuals[item["object"]]
            if language == "en":
                label = "Quoted text in figure" if "quote" in item else "Figure region"
                location = f"Visual inspection: {obj['location']} [{obj['kind']}]\n{label}: {quote}"
            else:
                label = "图内引文" if "quote" in item else "图内区域"
                location = f"人工目视定位　{obj['location']}〔{obj['kind']}〕\n{label}　{quote}"
            result[slide["part"]].append(page_note(location, item, comment, language))
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
        start_label = f"Character {offset + 1}" if language == "en" else f"第 {offset + 1} 字起"
        location = f"{paragraph['location']} / {start_label}\n" + quote_with_formatting(paragraph, offset, quote, language)
        result[slide["part"]].append(page_note(location, item, comment, language))
    for page, notes in result.items():
        if len(notes) != len(set(notes)):
            raise ValueError(f"{page} 有相同位置、引文和内容的重复意见，请合并。")
    return result


def html_title(slide):
    """Restore the native baseline of characters in the selected title paragraphs."""
    title_ids = set(slide.get("title_paragraphs", ()))
    if not title_ids:
        return escape(slide["title"])
    paragraphs = []
    for paragraph in slide["paragraphs"]:
        if paragraph["id"] not in title_ids:
            continue
        value, cursor, pieces = paragraph["text"], 0, []
        for span in paragraph.get("script_ranges", ()):
            start, end = span["start"], span["end"]
            tag = "sup" if span["position"] == "superscript" else "sub"
            pieces.extend((escape(value[cursor:start]), f"<{tag}>{escape(value[start:end])}</{tag}>"))
            cursor = end
        pieces.append(escape(value[cursor:]))
        paragraphs.append("".join(pieces))
    return " ".join(paragraphs)


def html_notes(data, located, filename, language="zh"):
    en = language == "en"
    html_lang = "en" if en else "zh-CN"
    heading = "PowerPoint review comments" if en else "PPT 审阅意见"
    source_label = "Source file: " if en else "原稿　"
    empty = "No findings in this review." if en else "本次未标注意见。"
    rows = []
    for slide in data["slides"]:
        findings = located.get(slide["part"])
        if findings:
            title = f"Slide {slide['page']}" if en else f"第 {slide['page']} 页"
            number = slide.get("slide_number", slide["page"])
            if number != slide["page"]:
                title += f" (slide number {number})" if en else f"（幻灯片编号 {number}）"
            title += ("  " if en else "　") + html_title(slide)
            if slide.get("title_needs_review"):
                title += " [verify title in original]" if en else "〔页题请核对原稿〕"
            if slide["title_hidden"]:
                title += " [hidden title]" if en else "〔隐藏页题〕"
            if slide["title_off_slide"]:
                title += " [title box off slide]" if en else "〔页题框在画面外〕"
            if slide["hidden"]:
                title += " [hidden slide]" if en else "〔隐藏页〕"
            rows.append("<h2>" + title + "</h2><ol>" +
                        "".join("<li>" + escape(n) + "</li>" for n in findings) + "</ol>")
    return (f'<!doctype html><html lang="{html_lang}"><meta charset="utf-8"><title>{heading}</title>'
            '<style>body{max-width:52em;margin:2em auto;font:1rem/1.6 system-ui;padding:0 1em}'
            'li{white-space:pre-wrap;overflow-wrap:anywhere;margin:1em 0}</style>'
            f'<h1>{heading}</h1>'
            f'<p>{source_label}{escape(filename)}<br>SHA-256 <code>{data["source_sha256"]}</code></p>'
            + ("".join(rows) or f"<p>{empty}</p>") + "</html>")


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
                manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig")) if args.action == "annotate" else None
                language = review_language(manifest) if args.action == "annotate" else "zh"
                data = inspect(z, digest.hexdigest(), language)
                if args.action == "inspect":
                    content = json.dumps(data, ensure_ascii=False, indent=2)
                    if args.output:
                        with new_output(args.output) as tmp:
                            tmp.write_text(content + "\n", encoding="utf-8")
                    else:
                        print(content)
                    return
                located = locate(data, manifest)
                with new_output(args.output) as tmp:
                    suffix = args.output.suffix.lower()
                    if suffix == ".html":
                        tmp.write_text(html_notes(data, located, args.input.name, language), encoding="utf-8")
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
