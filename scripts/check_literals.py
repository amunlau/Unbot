"""比较两份 UTF-8 文本中的数字和指定原样保留的片段。"""

import argparse
from html import unescape
import re
import sys
from collections import Counter
from pathlib import Path


# 保留数值的界限、正负号、上标指数和百分号。数字与符号间的排版空格不影响计数。
GAP = r"[ \t\u00a0\u2000-\u200a\u202f\u3000]*"
SUPERSCRIPT = r"(?:[⁺⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+[⁺⁻]?|[⁺⁻])"
SUBSCRIPT = r"(?:[₊₋]?[₀₁₂₃₄₅₆₇₈₉]+[₊₋]?|[₊₋])"
SCRIPT_DIGITS = {
    "sup": str.maketrans("0123456789+-−", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻"),
    "sub": str.maketrans("0123456789+-−", "₀₁₂₃₄₅₆₇₈₉₊₋₋"),
}
# Chinese technical prose can contain fullwidth comparison and arithmetic signs.
RELATION = r"(?:[<＜>＞!！=＝][=＝]|[<＜≤>＞≥=＝≠]|\\(?:leq?|geq?|lt|gt|neq?)(?![A-Za-z]))"
SIGN = r"[+＋−－-]"
# A following numeric operand already takes its own leading relation. Attach a
# trailing relation to the first number when the next operand is an expression.
EXPRESSION_START = rf"(?:{SIGN}{GAP})?(?:[^\W\d_]|[|｜‖∥(（\[［{{｛√]|\\[A-Za-z])"
MATH_BLOCK = re.compile(r"\$\$|\\\[|\\begin\{((?:equation|align|alignat|flalign|gather|multline|eqnarray)\*?"
                        r"|aligned|alignedat|gathered|displaymath|math|split|cases)\}")
FENCE = re.compile(r"(`{3,}|~{3,})(.*)")
HTML_TAG = re.compile(r"""</?([A-Za-z][A-Za-z0-9-]*)(?=[\s/>])(?:[^<>"']|"[^"]*"|'[^']*')*>""")
HTML_SCRIPT = re.compile(r"""<(sup|sub)(?=[\s>])((?:[^<>"']|"[^"]*"|'[^']*')*)>([^<>]*)</\1\s*>""", re.I)
TEX_SCRIPT = re.compile(r"([_^])\{([+−-]?[0-9]+[+−-]?)\}")
NUMBER = re.compile(
    rf"(?:(?:{RELATION}|[±∓]){GAP})?(?:{SIGN}{GAP})?"
    rf"(?:\d+(?:\.\d+)?|\.\d+)(?:[eE]{SIGN}?\d+)?(?:{SUPERSCRIPT}|{SUBSCRIPT})?(?:{GAP}[%％‰])?"
    rf"(?:{GAP}{RELATION}(?={GAP}{EXPRESSION_START}))?"
    rf"|{SUPERSCRIPT}|{SUBSCRIPT}"
)


def without_list_markers(text):
    """Ignore ordinary Markdown bullets, preserving signs in display math and code."""
    lines = text.split("\n")
    fence = None
    math_end = None
    block_quote_depth = 0
    for index, line in enumerate(lines):
        prefix = re.match(r"((?: {0,3}>[ \t]?)*) {0,3}", line)
        quote_depth = prefix[1].count(">")
        content = line[prefix.end():]
        if quote_depth < block_quote_depth:
            fence = math_end = None
        if fence:
            closing = FENCE.fullmatch(content) if quote_depth == block_quote_depth else None
            if closing and closing[1].startswith(fence) and not closing[2].strip():
                fence = None
            continue
        if math_end:
            if math_end in content:
                math_end = None
            continue

        # A list item can itself start a fenced example or a display formula.
        bullet = re.match(r"(?:[-+*]|[0-9]{1,9}[.)])[ \t]+", content)
        if bullet:
            if content[0] in "+-":
                lines[index] = line[:prefix.end()] + content[1:]
            content = content[bullet.end():]
        marker = FENCE.fullmatch(content)
        if marker and (marker[1].startswith("~") or "`" not in marker[2]):
            fence = marker[1]
            block_quote_depth = quote_depth
        elif (opening := MATH_BLOCK.match(content)):
            if opening[1]:
                closing = rf"\end{{{opening[1]}}}"
            else:
                closing = "$$" if opening[0] == "$$" else r"\]"
            if closing not in content[opening.end():]:
                math_end = closing
                block_quote_depth = quote_depth
    return "\n".join(lines)


def number_counts(text, *, markdown=False):
    if markdown:
        text = without_list_markers(text)
    # Compare explicit numeric script notation in the same form as Unicode.
    # Keep numbers from the original tag attributes independently of the exponent.
    counts = Counter()

    def html_script(match):
        value = unescape(match[3]).strip()
        if not re.fullmatch(r"[+−-]?[0-9]+[+−-]?|[+−-]", value):
            return match[0]
        counts.update("".join(token.split()) for token in NUMBER.findall(match[2]))
        return value.translate(SCRIPT_DIGITS[match[1].lower()])

    text = HTML_SCRIPT.sub(html_script, text)
    text = TEX_SCRIPT.sub(lambda m: m[2].translate(SCRIPT_DIGITS["sup" if m[1] == "^" else "sub"]), text)
    text = re.sub(r"\\(pm|mp)(?![A-Za-z])", lambda m: "±" if m[1] == "pm" else "∓", text)
    text = text.replace(r"\%", "%")
    # Preserve numbers in element text and attributes. Delimiters of paired HTML
    # tags in Markdown (e.g. 5<sup>2</sup>) are not mathematical relations.
    tags = {name.lower() for name in re.findall(r"</([A-Za-z][A-Za-z0-9-]*)\s*>", text)}
    tags.update(("br", "hr", "img", "wbr"))

    def mask_delimiters(match):
        tag = match[0]
        if match[1].lower() in tags or tag.endswith("/>"):
            return " " + tag[1:-1] + " "
        return tag

    text = HTML_TAG.sub(mask_delimiters, text)
    counts.update("".join(token.split()) for token in NUMBER.findall(text))
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path, help="原文路径")
    parser.add_argument("after", type=Path, help="成稿路径")
    parser.add_argument("--keep", action="append", default=[], metavar="片段",
                        help="需原样保留的连续文字，可多次指定")
    args = parser.parse_args()
    try:
        before = args.before.read_text(encoding="utf-8-sig")
        after = args.after.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        parser.exit(2, f"无法读取输入文件：{exc}\n")

    changes = []
    for literal in dict.fromkeys(args.keep):
        if not literal or literal not in before:
            parser.error(f"指定片段为空或未出现在原文中：{literal!r}")
        old_count, new_count = before.count(literal), after.count(literal)
        if old_count != new_count:
            changes.append(("指定片段", literal, old_count, new_count))

    markdown_suffixes = {".md", ".markdown"}
    old_numbers = number_counts(before, markdown=args.before.suffix.lower() in markdown_suffixes)
    new_numbers = number_counts(after, markdown=args.after.suffix.lower() in markdown_suffixes)
    for number in sorted(old_numbers.keys() | new_numbers.keys()):
        if old_numbers[number] != new_numbers[number]:
            changes.append(("数字", number, old_numbers[number], new_numbers[number]))

    for kind, token, old_count, new_count in changes:
        print(f"{kind} {token!r}：原文 {old_count} 处，成稿 {new_count} 处")
    if not changes:
        print("所查数字与指定片段的出现次数一致。")
    print("请另行核对数值归属、单位、公式运算、条件、否定范围与引文归属。")
    return 1 if changes else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
