"""将已定稿的有序内容块写入新的可编辑 Word 文档。依赖 python-docx。"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")

try:
    from docx import Document
    from docx.enum.style import WD_STYLE_TYPE
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
except ImportError as exc:
    raise SystemExit("当前 Python 缺少 python-docx 或其依赖。请使用具备该库的文档运行环境。") from exc


def require_text(value, field, *, empty_ok=False):
    if not isinstance(value, str) or (not empty_ok and not value.strip()):
        raise ValueError(f"{field} 需要{'字符串' if empty_ok else '非空文本'}")
    # python-docx turns CR and LF into separate Word breaks, even in a CRLF pair.
    return value.replace("\r\n", "\n").replace("\r", "\n")


def require_fields(value, fields, location):
    if not isinstance(value, dict) or set(value) != fields:
        expected = "、".join(sorted(fields))
        raise ValueError(f"{location} 的字段应为 {expected}")


def set_typeface(style, size, bold=False):
    font = style.font
    font.name = "Times New Roman"
    font.size = Pt(size)
    font.bold = bold
    font.italic = False
    font.color.rgb = RGBColor(0, 0, 0)
    props = style.element.get_or_add_rPr()
    fonts = props.rFonts
    fonts.attrib.clear()  # The bundled headings specify theme fonts that override ascii/hAnsi.
    for slot in ("ascii", "hAnsi", "cs"):
        fonts.set(qn(f"w:{slot}"), "Times New Roman")
    fonts.set(qn("w:eastAsia"), "宋体")
    props.color.attrib.clear()
    props.color.set(qn("w:val"), "000000")


def configure_document(doc):
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(2.54)
    section.left_margin = section.right_margin = Cm(2.8)
    normal = doc.styles["Normal"]
    set_typeface(normal, 12)
    # Set Chinese proofing independently of the inherited language for Latin text.
    lang = OxmlElement("w:lang")
    lang.set(qn("w:eastAsia"), "zh-CN")
    normal.element.get_or_add_rPr().append(lang)
    normal.paragraph_format.line_spacing = 1.45
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.widow_control = True

    body = doc.styles.add_style("Unbot Body", WD_STYLE_TYPE.PARAGRAPH)
    body.base_style = normal
    indent = body.element.get_or_add_pPr().get_or_add_ind()
    indent.set(qn("w:firstLineChars"), "200")
    title = doc.styles["Title"]
    set_typeface(title, 20, bold=True)
    title.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.keep_with_next = True
    for border in title.element.xpath("./w:pPr/w:pBdr"):
        border.getparent().remove(border)
    title.paragraph_format.space_after = Pt(14)

    for level, size in enumerate((16, 14, 12), start=1):
        heading = doc.styles[f"Heading {level}"]
        set_typeface(heading, size, bold=True)
        heading.next_paragraph_style = body
        heading.paragraph_format.space_before = Pt(12)
        heading.paragraph_format.space_after = Pt(4)
    for name, size, bold in (("Unbot Warning", 12, True), ("Unbot Table Text", 10.5, False)):
        style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style.base_style = normal
        set_typeface(style, size, bold=bold)
        style.paragraph_format.space_after = Pt(3)
    doc.styles["Unbot Warning"].paragraph_format.keep_together = True
    caption = doc.styles["Caption"]
    set_typeface(caption, 10.5)
    caption.paragraph_format.keep_with_next = True
    caption.paragraph_format.space_after = Pt(3)


def add_table(doc, block, location):
    require_fields(block, {"type", "headers", "rows"}, location)
    headers, rows = block["headers"], block["rows"]
    if not isinstance(headers, list) or not 1 <= len(headers) <= 63:
        raise ValueError(f"{location} 需要 1 至 63 个表头")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{location} 缺少数据行")
    table = doc.add_table(rows=0, cols=len(headers))
    table.style = "Table Grid"
    for index, values in enumerate([headers, *rows]):
        if not isinstance(values, list) or len(values) != len(headers):
            raise ValueError(f"{location} 的第 {index + 1} 行与表头列数不符")
        row = table.add_row()
        if index == 0:
            row._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
        for cell, value in zip(row.cells, values):
            para = cell.paragraphs[0]
            para.style = "Unbot Table Text"
            run = para.add_run(require_text(value, location, empty_ok=index > 0))
            if index == 0:
                run.bold = True


def build(spec):
    require_fields(spec, {"title", "blocks"}, "文档")
    title = require_text(spec["title"], "title")
    if not isinstance(spec["blocks"], list) or not spec["blocks"]:
        raise ValueError("blocks 需要至少一个正文内容块")
    doc = Document()
    configure_document(doc)
    # python-docx limits the optional metadata field to 255 characters.
    # The title paragraph below can hold the full title at any supported length.
    doc.core_properties.title = title if len(title) <= 255 else ""
    doc.core_properties.author = ""
    doc.core_properties.last_modified_by = ""
    doc.core_properties.comments = ""
    doc.core_properties.created = doc.core_properties.modified = datetime.now(timezone.utc)
    doc.add_paragraph(title, style="Title")
    styles = {"paragraph": "Unbot Body", "warning": "Unbot Warning", "caption": "Caption"}
    for index, block in enumerate(spec["blocks"], 1):
        location = f"第 {index} 个内容块"
        kind = block.get("type") if isinstance(block, dict) else None
        if kind == "table":
            add_table(doc, block, location)
        elif kind == "heading":
            require_fields(block, {"type", "level", "text"}, location)
            level = block["level"]
            if type(level) is not int or level not in (1, 2, 3):
                raise ValueError(f"{location} 需要 1、2 或 3 级标题")
            doc.add_heading(require_text(block["text"], location), level=level)
        elif isinstance(kind, str) and kind in styles:
            require_fields(block, {"type", "text"}, location)
            doc.add_paragraph(require_text(block["text"], location), style=styles[kind])
        else:
            raise ValueError(f"{location} 含未知的内容类型 {kind!r}")
    return doc


def save_new(doc, path):
    if path.suffix.lower() != ".docx":
        raise ValueError("输出文件扩展名应为 .docx")
    if path.exists():
        raise FileExistsError(f"目标已存在，请使用新的文件名：{path}")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        staged = Path(handle.name)
    try:
        doc.save(staged)
        Document(staged)  # Verify package readability before publishing.
        if os.name == "nt":
            os.rename(staged, path)  # On Windows, rename fails if the target now exists.
        else:
            os.link(staged, path)  # Atomic no-replace publication on the same filesystem.
    finally:
        staged.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path, help="UTF-8 编码的 JSON 定稿")
    parser.add_argument("output", type=Path, help="新建的 .docx 文件")
    args = parser.parse_args()
    try:
        spec = json.loads(args.draft.read_text(encoding="utf-8-sig"))
        save_new(build(spec), args.output)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"生成失败：{exc}\n")
    print(f"已生成：{args.output}")


if __name__ == "__main__":
    main()
