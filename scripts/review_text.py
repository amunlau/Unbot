"""定位 TXT/Markdown 原句，在副本中交付审阅意见，不修改原稿。"""

import argparse
import codecs
import hashlib
from html import escape
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4

from review_classification import FINDING_SCHEMA, review_findings, review_language

TEXT_SUFFIXES = {".txt", ".md", ".markdown"}


def read_source(path, encoding, *, legacy_manifest=False):
    if path.suffix.lower() not in TEXT_SUFFIXES:
        raise ValueError("输入须为 TXT 或 Markdown。")
    raw = path.read_bytes()
    if raw.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        default = "utf-32"
    elif raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        default = "utf-16"
    else:
        default = "utf-8-sig"
    if encoding:
        # Calling UTF-8 or UTF-16LE by name must not add a BOM to the first line.
        codec = codecs.lookup(encoding).name
        for explicit, marker, bom_aware in (
            ("utf-8", codecs.BOM_UTF8, "utf-8-sig"),
            ("utf-16-le", codecs.BOM_UTF16_LE, "utf-16"),
            ("utf-16-be", codecs.BOM_UTF16_BE, "utf-16"),
            ("utf-32-le", codecs.BOM_UTF32_LE, "utf-32"),
            ("utf-32-be", codecs.BOM_UTF32_BE, "utf-32"),
        ):
            if codec == explicit and raw.startswith(marker):
                encoding = bom_aware
                break
    source = raw.decode(encoding or default)
    if encoding and legacy_manifest:
        # A raw-byte digest cannot distinguish two interpretations of the same file.
        try:
            default_text = raw.decode(default)
        except UnicodeError:
            default_text = None
        if source != default_text:
            raise ValueError("使用其他编码时，请按正确的 --encoding 重新 inspect，并在意见中保留 text_sha256。")
    if "\0" in source:
        raise ValueError("输入含空字符，请核对文本编码。")
    # 单一换行用于定位。源文件的指纹直接取自原始字节，包括 BOM 和换行。
    return source.replace("\r\n", "\n").replace("\r", "\n"), hashlib.sha256(raw).hexdigest()


def locate(source, lines, manifest, digest, text_digest):
    if not isinstance(manifest, dict) or manifest.get("source_sha256") != digest:
        raise ValueError("审阅意见与当前原稿版本不符，请重新读取原稿。")
    if "text_sha256" in manifest and manifest["text_sha256"] != text_digest:
        raise ValueError("解码后的原文与清单不一致，请核对两次使用的 --encoding。")
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line) + 1)
    located = []
    for sequence, (item, comment) in enumerate(review_findings(manifest), 1):
        locator = item.get("paragraph")
        if not isinstance(locator, str) or not re.fullmatch(r"L[0-9]+", locator):
            raise ValueError(f"第 {sequence} 条意见行标识无效。")
        row = int(locator[1:]) - 1
        quote = item.get("quote")
        if not 0 <= row < len(lines) or not isinstance(quote, str) or not quote.strip():
            raise ValueError(f"第 {sequence} 条意见行号或引文无效。")
        offset = offsets[row]
        if "start" in item:
            col = item["start"]
            if type(col) is not int or not 0 <= col < len(lines[row]) or not source.startswith(quote, offset + col):
                raise ValueError(f"{locator} 指定位置的文字不匹配。")
        else:
            end = offset + len(lines[row])
            search_end = min(len(source), end + len(quote) - 1)
            first = source.find(quote, offset, search_end)
            if not offset <= first < end:
                raise ValueError(f"{locator} 没有匹配引文。")
            repeat = source.find(quote, first + 1, search_end)
            if first < repeat < end:
                raise ValueError(f"{locator} 存在相同引文，请用 start 指定列偏移。")
            col = first - offset
        located.append((offset + col, offset + col + len(quote), row + 1, col + 1,
                        comment.strip(), "category" in item))
    located.sort()
    for previous, current in zip(located, located[1:]):
        if previous[1] > current[0]:
            raise ValueError("批注选区有重叠，请合并相同问题或选择较短的不重叠引文。")
    return located


def position(line, col, language):
    return f"Line {line}, column {col}" if language == "en" else f"第 {line} 行第 {col} 列"


def html_review(source, found, title, language="zh"):
    en = language == "en"
    html_lang = "en" if en else "zh-CN"
    note_label = "Comment" if en else "批注"
    notes_heading = "Review comments" if en else "审阅意见"
    chunks, notes, cursor = [], [], 0
    for i, (a, b, line, col, comment, classified) in enumerate(found, 1):
        chunks.extend((escape(source[cursor:a]), f'<mark id="q{i}">{escape(source[a:b])}</mark>'
                       f'<sup><a href="#n{i}" aria-label="{note_label} {i}">[{i}]</a></sup>'))
        link = f'<a href="#q{i}">{position(line, col, language)}</a>'
        body = escape(comment)
        note = f"{body}<br>{link}" if classified else f"{link} {body}"
        notes.append(f'<li id="n{i}">{note}</li>')
        cursor = b
    chunks.append(escape(source[cursor:]))
    heading = escape(title) + (" · Review" if en else " · 审阅")
    empty = "No findings in this review." if en else "本次审阅没有标注项。"
    section = "<ol>" + "".join(notes) + "</ol>" if notes else f"<p>{empty}</p>"
    return (f'<!doctype html><html lang="{html_lang}"><meta charset="utf-8"><title>{heading}</title>'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<style>body{margin:2rem auto;padding:0 1rem;max-width:58rem;font:1rem/1.75 system-ui,sans-serif}'
            'article,li{white-space:pre-wrap;overflow-wrap:anywhere}mark{background:#ffec9e;color:#171717}'
            'sup a{font-weight:bold}li{margin:.55rem 0}:target{outline:2px solid #47566b}</style>'
            f'<h1>{heading}</h1><article>{"".join(chunks)}</article><h2>{notes_heading}</h2>{section}</html>')


def fenced_text(text, language):
    longest = max((len(m[0]) for m in re.finditer(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{language}\n{text}\n{fence}"


def has_open_markdown_block(source):
    """Common top-level blocks which can swallow an appendix even after a blank line."""
    fence = html_end = None
    for line in source.split("\n"):
        if html_end:
            if html_end in line.lower():
                html_end = None
            continue
        match = re.fullmatch(r" {0,3}(`{3,}|~{3,})(.*)", line)
        if fence:
            if match and match[1].startswith(fence) and not match[2].strip(" \t"):
                fence = None
            continue
        if match and (match[1][0] == "~" or "`" not in match[2]):
            fence = match[1]
            continue
        match = re.match(r" {0,3}(<!--|<\?|<!\[CDATA\[|<![A-Z]|<(pre|script|style|textarea)(?=[\s>]|$))",
                         line, re.IGNORECASE)
        if match:
            marker = match[1].lower()
            if match[2]:
                html_end = f"</{match[2].lower()}>"
            else:
                html_end = {"<!--": "-->", "<?": "?>", "<![cdata[": "]]>"}.get(marker, ">")
            if html_end in line[match.end():].lower():
                html_end = None
    return bool(fence or html_end)


def text_review(source, found, markdown, source_view=False, language="zh"):
    en = language == "en"
    quote_label, note_label = ("Quoted text: ", "Comment: ") if en else ("原文　", "批注　")
    heading = "Review comments" if en else "审阅意见"
    notes = []
    for i, (a, b, line, col, comment, classified) in enumerate(found, 1):
        location = f"[{i}] {position(line, col, language)}\n{quote_label}{source[a:b]}"
        notes.append(f"{comment}\n{location}" if classified else f"{location}\n{note_label}{comment}")
    appendix = "\n\n".join(notes) or ("No findings in this review." if en else "本次审阅没有标注项。")
    if markdown:
        if source_view or has_open_markdown_block(source):
            source_heading = "Original Markdown source" if en else "原稿（按 Markdown 源码显示）"
            source = f"## {source_heading}\n\n" + fenced_text(source, "markdown")
        appendix = f"## {heading}\n\n" + fenced_text(appendix, "text")
    else:
        appendix = heading + "\n\n" + appendix
    return source + "\n\n" + appendix + "\n"


def write_new(path, data):
    if path.exists():
        raise FileExistsError(f"输出已存在：{path}")
    payload = data.encode("utf-8")
    # Write beside the destination. An interrupted operation must remain retryable.
    staged = path.with_name(f".unbot-{uuid4().hex}.tmp")
    handle = staged.open("xb")
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == "nt":
            os.rename(staged, path)  # On Windows rename refuses an existing target.
        else:
            os.link(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    inspect = commands.add_parser("inspect", help="读取原文，给出行号及 SHA-256")
    annotate = commands.add_parser("annotate", help="按已判定的意见制作审阅副本")
    for sub in (inspect, annotate):
        sub.add_argument("input", type=Path)
        sub.add_argument("--encoding", help="无 BOM 的非 UTF-8 文件可指定，例如 gb18030")
    inspect.add_argument("--output", type=Path)
    annotate.add_argument("manifest", type=Path)
    annotate.add_argument("output", type=Path)
    annotate.add_argument("--source-view", action="store_true",
                          help="生成 Markdown 同格式副本时，以源码显示正文，使意见独立可见")
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8-sig")) if args.action == "annotate" else None
        legacy_manifest = isinstance(data, dict) and "text_sha256" not in data
        source, digest = read_source(args.input, args.encoding, legacy_manifest=legacy_manifest)
        text_digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        lines = source.split("\n")
        if args.action == "inspect":
            result = {"finding_schema": FINDING_SCHEMA, "source_sha256": digest, "text_sha256": text_digest, "lines": [
                {"id": f"L{i:04}", "text": line} for i, line in enumerate(lines, 1)]}
            output = json.dumps(result, indent=2, ensure_ascii=False)
            if args.output:
                write_new(args.output, output + "\n")
            else:
                print(output)
        else:
            found = locate(source, lines, data, digest, text_digest)
            language = review_language(data)
            ext = args.output.suffix.lower()
            if args.source_view and (ext not in {".md", ".markdown"} or ext != args.input.suffix.lower()):
                raise ValueError("--source-view 只适用于 Markdown 同后缀副本。")
            if ext == ".html":
                output = html_review(source, found, args.input.name, language)
            elif ext == args.input.suffix.lower():
                output = text_review(source, found, ext != ".txt", args.source_view, language)
            else:
                raise ValueError("输出请选择 .html 或原文件后缀。")
            write_new(args.output, output)
            print(f"已写入 {len(found)} 条批注：{args.output}")
    except (OSError, UnicodeError, ValueError, LookupError) as exc:
        parser.exit(2, f"无法完成：{exc}\n")


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
