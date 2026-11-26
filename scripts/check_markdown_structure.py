"""只读比较 Markdown 中已识别的受保护结构；不判断事实、步骤含义或文风。"""

from __future__ import annotations

import argparse
from bisect import bisect_right
import json
import re
import sys
from pathlib import Path


CATEGORIES = ("metadata", "code", "math", "links", "headings", "anchors", "tables", "lists")
FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})([^\n]*)$")
HEADING = re.compile(r"^ {0,3}#{1,6}(?:[ \t]|$)")
LIST = re.compile(r"^([ \t]*)([-+*]|[0-9]{1,9}[.)])(?:[ \t]+|$)")
TASK_BOX = re.compile(r"\[[ xX\t]\](?=[ \t]|$)")
SETEXT = re.compile(r" {0,3}(?:=+|-+)[ \t]*")
HTML_START_TAG = re.compile(r"<[A-Za-z][\w:.-]*(?=[\s/>])((?:[^<>\"'\n]|\"[^\"\n]*\"|'[^'\n]*')*)>")


def escaped(text, index):
    count = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        count += 1
        index -= 1
    return count % 2 == 1


def scan_markdown(text):
    """Return ordered tokens and conservative scan diagnostics for the supported subset.

    Token values are internal comparison material, not emitted by the CLI.
    Line endings are normalized; all other protected text is compared exactly.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    tokens = {name: [] for name in CATEGORIES}
    diagnostics = []
    block_lines = set()
    chars = list(text)
    # CommonMark line endings are CR/LF (normalized above). Python splitlines
    # also splits Unicode separators; masking one inside code would then shift
    # the visible-line indices away from these original offsets.
    parts = text.split("\n")
    lines = [line + ("\n" if index < len(parts) - 1 else "") for index, line in enumerate(parts)]
    offsets = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)

    def mark(category, start, end, value=None, mask=True):
        tokens[category].append((start, text[start:end] if value is None else value))
        if mask:
            for i in range(start, end):
                if chars[i] != "\n":
                    chars[i] = " "

    def diagnostic(start, message):
        diagnostics.append({"line": text.count("\n", 0, start) + 1, "message": message})

    i = 0
    if lines and lines[0].strip() == "---":
        end = next((j for j in range(1, len(lines)) if lines[j].strip() in ("---", "...")), None)
        if end is None:
            diagnostic(0, "开头的 --- 未找到元数据结束标记；也可能是普通分隔线，须人工判断。")
        else:
            mark("metadata", 0, offsets[end] + len(lines[end]))
            block_lines.update(range(end + 1))
            i = end + 1

    while i < len(lines):
        raw = lines[i].rstrip("\n")
        match = FENCE.fullmatch(raw)
        if match and (match[2][0] == "~" or "`" not in match[3]):
            marker = match[2]
            closing = re.compile(r"^ {0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}[ \t]*$")
            end = next((j for j in range(i + 1, len(lines)) if closing.fullmatch(lines[j].rstrip("\n"))), None)
            if end is None:
                diagnostic(offsets[i], "围栏代码未闭合；本工具要求显式结束标记。")
                mark("code", offsets[i], len(text))
                block_lines.update(range(i, len(lines)))
                break
            mark("code", offsets[i], offsets[end] + len(lines[end]))
            block_lines.update(range(i, end + 1))
            i = end + 1
            continue
        # Nested containers and indented code need a real Markdown renderer to
        # disambiguate. Do not silently treat their contents as ordinary prose.
        if re.match(r"^(?: {4}|\t)[ \t]*\S|^\s*>|^\s*(?:[-+*]|\d+[.)])\s+[`~]{3}", raw):
            diagnostic(offsets[i], "含缩进代码或嵌套容器；本工具不完整解析该结构，需人工或渲染复核。")
        i += 1

    def paragraph_boundary(index):
        """Known or possible block boundaries; deliberately not a full parser."""
        raw = lines[index].rstrip("\n")
        return (index in block_lines or not raw.strip(" \t") or HEADING.match(raw)
                or LIST.match(raw) or SETEXT.fullmatch(raw)
                or re.match(r"^ {0,3}(?:\[[^\]]+\]:|>|\$\$|\\[\[\]])", raw)
                or re.fullmatch(r" {0,3}(?:\*[ \t]*){3,}| {0,3}(?:_[ \t]*){3,}", raw))

    visible = "".join(chars)
    i = 0
    while i < len(visible):
        if visible[i] != "`" or escaped(visible, i):
            i += 1
            continue
        run = re.match(r"`+", visible[i:])[0]
        closing = re.search(r"(?<!`)" + re.escape(run) + r"(?!`)", visible[i + len(run):])
        if closing is None:
            diagnostic(i, "行内代码反引号未配对；它可能是普通文字，须人工确认。")
            i += len(run)
        else:
            end = i + len(run) + closing.end()
            first_line = bisect_right(offsets, i) - 1
            last_line = bisect_right(offsets, end - 1) - 1
            if (last_line > first_line
                    and (HEADING.match(lines[first_line])
                         or any(paragraph_boundary(j) for j in range(first_line + 1, last_line + 1)))):
                # Inline parsing cannot join separate blocks. Leave their
                # structures visible even when the caller allows code edits.
                diagnostic(i, "行内反引号之间存在已知或疑似块边界；未按代码屏蔽，须在渲染中人工确认。")
                i += len(run)
                continue
            mark("code", i, end)
            i = end

    # Explicit display/TeX delimiters; unmatched delimiters are not accepted as
    # evidence that the remaining structures were completely checked.
    visible = "".join(chars)
    i = 0
    pairs = {"$$": "$$", r"\[": r"\]", r"\(": r"\)"}
    while i < len(visible):
        opening = next((x for x in pairs if visible.startswith(x, i) and not escaped(visible, i)), None)
        if opening:
            end = i + len(opening)
            while True:
                end = visible.find(pairs[opening], end)
                if end < 0 or not escaped(visible, end):
                    break
                end += len(pairs[opening])
            if end < 0:
                diagnostic(i, "显式公式分隔符未闭合。")
                mark("math", i, len(text))
                break
            end += len(pairs[opening])
            mark("math", i, end)
            i = end
        elif any(visible.startswith(x, i) for x in (r"\]", r"\)")) and not escaped(visible, i):
            diagnostic(i, "发现没有对应起始符的公式结束符。")
            i += 2
        else:
            i += 1

    visible = "".join(chars)
    # Pair single dollars on one line. Escaped dollars belong to the formula
    # content or prose. A rejected closer can still open the next formula.
    opening = None
    for delimiter in re.finditer(r"\$|\n", visible):
        pos = delimiter.start()
        if visible[pos] == "\n":
            opening = None
            continue
        if escaped(visible, pos):
            continue
        following = visible[pos + 1:pos + 2]
        if (opening is not None and pos > opening + 1
                and not visible[pos - 1].isspace() and not following.isdecimal()):
            mark("math", opening, pos + 1)
            opening = None
        else:
            opening = pos if following and not following.isspace() else None

    visible = "".join(chars)
    # Reference definitions are preserved in full, including destinations and
    # optional titles. Multiline definitions are outside this small scanner.
    definition_ids = set()
    for match in re.finditer(r"(?m)^ {0,3}\[([^\]\n]+)\]:[^\n]*", visible):
        definition_ids.add(" ".join(match[1].split()).casefold())
        mark("links", match.start(), match.end())

    visible = "".join(chars)
    i = 0
    link_payload_ends = {}
    while i < len(visible):
        if i in link_payload_ends:
            i = link_payload_ends[i]
            continue
        if visible[i] != "[" or escaped(visible, i):
            i += 1
            continue
        # Nested bracket labels are recognized without interpreting their prose.
        depth, end = 1, i + 1
        while end < len(visible) and depth:
            if not escaped(visible, end):
                if visible[end] == "[":
                    depth += 1
                elif visible[end] == "]":
                    depth -= 1
            end += 1
        if depth:
            i += 1
            continue
        label = visible[i + 1:end - 1]
        kind = "image-" if i and visible[i - 1] == "!" and not escaped(visible, i - 1) else ""
        if end < len(visible) and visible[end] == "(":
            # Balanced target parentheses, angle targets and optional quoted
            # titles. Raw payload is kept, but the link label can be polished.
            cursor, level, angle, quote = end + 1, 1, False, None
            while cursor < len(visible) and level:
                c = visible[cursor]
                if escaped(visible, cursor):
                    cursor += 1
                    continue
                if angle:
                    angle = c != ">"
                elif quote:
                    if c == quote:
                        quote = None
                elif c == "<":
                    angle = True
                elif c in "\"'" and cursor > end + 1 and visible[cursor - 1].isspace():
                    quote = c
                elif c == "(":
                    level += 1
                elif c == ")":
                    level -= 1
                cursor += 1
            if level:
                diagnostic(i, "行内链接目标未闭合。")
            else:
                mark("links", i, cursor, kind + "inline:" + text[end + 1:cursor - 1], mask=False)
                link_payload_ends[end] = cursor
                # Inspect the label too: a linked image has its own target.
                i += 1
                continue
        elif end < len(visible) and visible[end] == "[":
            close = visible.find("]", end + 1)
            if close >= 0 and "\n" not in visible[end:close]:
                ref = visible[end + 1:close] or label
                mark("links", i, close + 1, kind + "reference:" + " ".join(ref.split()).casefold(), mask=False)
                link_payload_ends[end] = close + 1
                i += 1
                continue
        elif " ".join(label.split()).casefold() in definition_ids:
            mark("links", i, end, kind + "reference:" + " ".join(label.split()).casefold(), mask=False)
            i = end
            continue
        # Ordinary square-bracket prose can contain an actual link or image.
        # Only recognized target payloads are skipped, not ordinary outer
        # brackets such as [see [source](a.md)].
        i += 1

    for match in re.finditer(r"<(?:https?://|mailto:)[^<>\s]+>", visible, re.IGNORECASE):
        mark("links", match.start(), match.end(), mask=False)
    for match in HTML_START_TAG.finditer(visible):
        # Tokenize whole attributes so data-id and id-like words inside another
        # attribute's quoted value cannot be mistaken for an actual anchor.
        for attr in re.finditer(r"([^\s=/>]+)(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+))?", match[1]):
            if attr[1].casefold() in ("id", "name"):
                mark("anchors", match.start(1) + attr.start(), match.start(1) + attr.end(), mask=False)
    for match in re.finditer(r"\{#[^{}\s]+\}", visible):
        mark("anchors", match.start(), match.end(), mask=False)

    body_lines = visible.split("\n")

    for index, line in enumerate(body_lines):
        setext_underline = False
        if HEADING.match(line):
            mark("headings", offsets[index], offsets[index] + len(lines[index]), mask=False)
        elif index and SETEXT.fullmatch(line) and not paragraph_boundary(index - 1):
            start = index - 1
            while start and not paragraph_boundary(start - 1):
                start -= 1
            setext_underline = True
            mark("headings", offsets[start], offsets[index] + len(lines[index]), mask=False)
            if start < index - 1:
                diagnostic(offsets[start], "疑似多行 Setext 标题；已记录候选整段，段落边界须在渲染中人工确认。")
        # Match the original marker, never spaces introduced by masking an
        # inline formula or code span. The marker itself must still be visible.
        raw_line = lines[index].rstrip("\n")
        match = LIST.match(raw_line)
        if (match and not setext_underline and index not in block_lines
                and line[match.start(2):match.end(2)] == match[2]):
            box = TASK_BOX.match(raw_line, match.end())
            marker_end = box.end() if box else match.end()
            mark("lists", offsets[index], offsets[index] + marker_end, mask=False)

    # Preserve full rows for simple pipe tables, not merely their pipe counts.
    table_lines = set()
    for index in range(1, len(body_lines)):
        line = body_lines[index].strip().strip("|")
        cells = line.split("|")
        if "|" in body_lines[index] and all(re.fullmatch(r"\s*:?-+:?\s*", c) for c in cells):
            if "|" not in body_lines[index - 1]:
                continue
            table_lines.update((index - 1, index))
            j = index + 1
            # Masked inline code/math is still table content, not a blank line.
            # Markdown blank lines contain only ASCII spaces/tabs after CR/LF
            # normalization; other Unicode whitespace can be a data cell.
            while j < len(body_lines) and lines[j].strip(" \t\n") and not paragraph_boundary(j):
                if "|" not in body_lines[j]:
                    diagnostic(offsets[j], "表格后紧接不含竖线的非空行，可能仍为数据行；须在渲染中核对表格范围。")
                    break
                table_lines.add(j)
                j += 1
    for index in sorted(table_lines):
        mark("tables", offsets[index], offsets[index] + len(lines[index]), mask=False)
    return {name: [value for _, value in sorted(items)] for name, items in tokens.items()}, diagnostics


def compare_markdown(before, after, allow=()):
    unknown = set(allow) - set(CATEGORIES)
    if unknown:
        raise ValueError("未知核对类别：" + ", ".join(sorted(unknown)))
    old, old_diagnostics = scan_markdown(before)
    new, new_diagnostics = scan_markdown(after)
    changed = [name for name in CATEGORIES if old[name] != new[name]]
    blocked = [name for name in changed if name not in allow]
    diagnostics = [{"input": side, **item} for side, values in (("before", old_diagnostics), ("after", new_diagnostics)) for item in values]
    return {
        "status": "scan-incomplete" if diagnostics else "needs-review" if blocked else "no-unapproved-change-found",
        "changed_categories": changed,
        "unapproved_categories": blocked,
        "allowed_categories": [name for name in CATEGORIES if name in allow],
        "token_counts": {name: {"before": len(old[name]), "after": len(new[name])} for name in CATEGORIES},
        "diagnostics": diagnostics,
        "scope": "仅核对已识别的结构与原样片段；未验证事实、数值归属、步骤含义、链接文字归属或渲染结果。",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path, help="原文 UTF-8 Markdown 路径")
    parser.add_argument("after", type=Path, help="成稿 UTF-8 Markdown 路径")
    parser.add_argument("--allow", action="append", choices=CATEGORIES, default=[], help="已有授权可变更的类别；可重复，不免除人工核对")
    parser.add_argument("--json", action="store_true", help="输出类别、数量及行号，不输出原文片段")
    args = parser.parse_args()
    try:
        result = compare_markdown(args.before.read_text(encoding="utf-8-sig"), args.after.read_text(encoding="utf-8-sig"), args.allow)
    except (OSError, UnicodeError) as exc:
        parser.exit(2, f"无法读取 UTF-8 输入文件：{exc}\n")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("待核对的结构变化：" + (", ".join(result["unapproved_categories"]) or "所查类别中未发现未经放行的变化"))
        for item in result["diagnostics"]:
            print(f"{item['input']} 第 {item['line']} 行：{item['message']}")
        if result["allowed_categories"]:
            print("已按参数放行：" + ", ".join(result["allowed_categories"]))
        print(result["scope"])
    return 2 if result["diagnostics"] else int(bool(result["unapproved_categories"]))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
