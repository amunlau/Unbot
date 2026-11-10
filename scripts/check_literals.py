"""比较两份 UTF-8 文本中的数字和指定原样保留的片段。"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path


# 保留数值的界限、正负号、上标指数和百分号。数字与符号间的排版空格不影响计数。
GAP = r"[ \t\u00a0\u2000-\u200a\u202f\u3000]*"
SUPERSCRIPT = r"[⁺⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+"
# Chinese technical prose can contain fullwidth comparison and arithmetic signs.
RELATION = r"(?:[<＜>＞!！=＝][=＝]|[<＜≤>＞≥=＝≠])"
SIGN = r"[+＋−－-]"
HTML_TAG = re.compile(r"""</?([A-Za-z][A-Za-z0-9-]*)(?=[\s/>])(?:[^<>"']|"[^"]*"|'[^']*')*>""")
NUMBER = re.compile(
    # Spaced ASCII '-' and '+' can be Markdown list markers.
    rf"(?:(?:{RELATION}|±){GAP})?(?:[+-]|[＋−－]{GAP})?"
    rf"(?:\d+(?:\.\d+)?|\.\d+)(?:[eE]{SIGN}?\d+)?(?:{SUPERSCRIPT})?(?:{GAP}[%％‰])?"
    # In a range such as '0 < x ≤ 1', the first relation follows its number.
    rf"(?:{GAP}{RELATION}(?={GAP}[^\W\d_]))?"
    rf"|{SUPERSCRIPT}"
)


def number_counts(text):
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
    return Counter("".join(token.split()) for token in NUMBER.findall(text))


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

    old_numbers = number_counts(before)
    new_numbers = number_counts(after)
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
