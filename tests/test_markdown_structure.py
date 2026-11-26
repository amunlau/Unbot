"""Structure-checker regressions, not an evaluation of Chinese writing quality."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_markdown_structure.py"
SPEC = importlib.util.spec_from_file_location("check_markdown_structure", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class MarkdownStructureTests(unittest.TestCase):
    def check(self, before, after, expected=(), allow=()):
        result = MOD.compare_markdown(before, after, allow)
        self.assertEqual(result["unapproved_categories"], list(expected))
        self.assertFalse(result["diagnostics"], result["diagnostics"])
        return result

    def test_plain_language_edit_with_protected_content(self):
        original = '# 测量方法\n对输出进行测量。使用 `measure --safe`。\n'
        self.check(original, original.replace('对输出进行测量', '测量输出'))

    def test_fenced_code_not_parsed_as_heading_or_link(self):
        before = '```python\n# 标题\nprint("[来源](a)")\n```\n'
        result = self.check(before, before.replace('(a)', '(b)'), ('code',))
        self.assertEqual(result['token_counts']['headings']['before'], 0)
        self.assertEqual(result['token_counts']['links']['before'], 0)

    def test_fence_info_and_code_are_preserved(self):
        self.check('~~~sh\nrun --safe\n~~~~\n', '~~~sh\nrun --force\n~~~~\n', ('code',))
        self.check('```sh\nrun\n```\n', '```text\nrun\n```\n', ('code',))

    def test_inline_code_exact_backtick_length_and_escapes(self):
        self.check(r'字面 \`；命令 ``x`y``。', r'字面 \`；命令 ``x`z``。', ('code',))

    def test_inline_code_cannot_hide_structures_across_blocks(self):
        examples = (
            ('文字 `用于说明。\n\n# 原标题\n\n另一段 ` 文字。', 'headings', '原标题', '新标题'),
            ('文字 `用于说明。\n# 原标题\n另一行 ` 文字。', 'headings', '原标题', '新标题'),
            ('# `原标题\n下一段 ` 文字。', 'headings', '原标题', '新标题'),
            ('文字 `用于说明。\n- 事项\n另一行 ` 文字。', 'lists', '- 事项', '+ 事项'),
            ('文字 `用于说明。\n1. 事项\n另一行 ` 文字。', 'lists', '1. 事项', '2. 事项'),
            ('文字 `用于说明。\n```text\n正文\n```\n# 原标题\n另一行 ` 文字。',
             'headings', '原标题', '新标题'),
        )
        for before, category, old, new in examples:
            with self.subTest(before=before):
                result = MOD.compare_markdown(before, before.replace(old, new), ('code',))
                self.assertEqual(result['status'], 'scan-incomplete')
                self.assertIn(category, result['unapproved_categories'])

    def test_inline_code_retains_soft_line_breaks(self):
        before = '执行 `command\nparameter`。\n'
        self.check(before, before.replace('parameter', 'argument'), ('code',))

    def test_non_markdown_line_separators_do_not_shift_offsets(self):
        for separator in ('\v', '\f', '\x85', '\u2028', '\u2029'):
            with self.subTest(separator=repr(separator)):
                before = '正文 `a' + separator + 'b`\n# 原标题\n'
                self.check(before, before.replace('原标题', '新标题'), ('headings',), ('code',))

    def test_inline_code_cannot_cross_a_fenced_block(self):
        before = '文字 `说明。\n~~~text\n例子\n~~~\n另一段 ` 文字。\n'
        result = MOD.compare_markdown(before, before, ('code',))
        self.assertEqual(result['status'], 'scan-incomplete')
        self.assertEqual(result['token_counts']['code']['before'], 1)

    def test_unclosed_code_is_diagnostic_even_when_allowed(self):
        for value in ('```sh\nrun\n', '执行 `run 命令。'):
            with self.subTest(value=value):
                result = MOD.compare_markdown(value, value, ('code',))
                self.assertEqual(result['status'], 'scan-incomplete')
                self.assertTrue(result['diagnostics'])

    def test_unsupported_nested_code_is_not_silent_pass(self):
        for value in ('    command\n', '> ```\n> command\n> ```\n', '- ```\n  command\n  ```\n'):
            result = MOD.compare_markdown(value, value)
            self.assertTrue(result['diagnostics'])

    def test_math_and_code_delimiters(self):
        for before, after in ((r'$x^2$。', r'$x^3$。'), ('$x$。', '$y$。'),
                              ('$$x < 2$$', '$$x > 2$$'), (r'\[x < 2\]', r'\[x > 2\]'),
                              (r'\(x=2\)', r'\(x=3\)')):
            with self.subTest(before=before):
                self.check(before, after, ('math',))
        self.check('单价 $5；总价 $6。', '单价 $5；合计 $6。')
        result = MOD.compare_markdown(r'\[x=2', r'\[x=2')
        self.assertTrue(result['diagnostics'])

    def test_single_dollar_math_respects_escaped_dollars(self):
        for before in (r'Cost $C+\$5$ per run.', r'Cost $C+\$$ per run.',
                       r'After a literal backslash: \\$C$'):
            with self.subTest(before=before):
                result = self.check(before, before.replace('$C', '$D'), ('math',))
                self.assertEqual(result['token_counts']['math'], {'before': 1, 'after': 1})
        for prose in (r'Prices \$5 and \$8', '$5 per unit at $8 each',
                      'Unpaired $x\nand y$ on another line.'):
            with self.subTest(prose=prose):
                result = self.check(prose, prose)
                self.assertEqual(result['token_counts']['math']['before'], 0)

    def test_inline_links_nested_targets_titles_and_images(self):
        examples = ('[说明](folder(a).md "标题")', '[说明](<目录/a b.md>)',
                    '![图](images/a.png)', '[带[嵌套]标签](a.md)', '<https://example.org/a>')
        for value in examples:
            with self.subTest(value=value):
                self.check(value, value.replace('a', 'z', 1), ('links',))

    def test_reference_definitions_and_uses(self):
        before = '[原标签][id]\n\n[id]: a.md "题名"\n'
        self.check(before, before.replace('原标签', '新标签'))
        self.check(before, before.replace('a.md', 'b.md'), ('links',))
        self.check(before, before.replace('[原标签][id]', '[原标签][missing]'), ('links',))
        self.check('[id][]\n\n[id]: a.md\n', '[id]\n\n[id]: a.md\n')

    def test_autolinks_accept_case_insensitive_schemes(self):
        for value in ('<HTTPS://example.org/a>', '<Http://example.org/a>', '<MAILTO:a@example.org>'):
            with self.subTest(value=value):
                self.check(value, value.replace('/a>', '/b>').replace(':a@', ':b@'), ('links',))

    def test_linked_images_and_image_kind_are_protected(self):
        self.check('[![图](a.png)](details.md)', '[![图](b.png)](details.md)', ('links',))
        self.check('![图](a.png)', '[图](a.png)', ('links',))
        self.check('![图][id]\n\n[id]: a.png\n', '[图][id]\n\n[id]: a.png\n', ('links',))

    def test_links_inside_ordinary_square_brackets(self):
        for before, after in (
                ('[参见 [来源](a.md)]', '[参见 [来源](b.md)]'),
                ('[插图 ![图](a.png)]', '[插图 ![图](b.png)]'),
                ('[参见 [来源][id]]\n\n[id]: a.md\n',
                 '[参见 [来源][other]]\n\n[id]: a.md\n')):
            with self.subTest(before=before):
                self.check(before, after, ('links',))
        # Brackets in a recognized destination/title are payload, not links.
        before = '[说明](<folder/[nested](file).md> "[title](other.md)")'
        result = self.check(before, before)
        self.assertEqual(result['token_counts']['links']['before'], 1)

    def test_unclosed_inline_link(self):
        result = MOD.compare_markdown('[说明](a.md', '[说明](a.md')
        self.assertTrue(result['diagnostics'])

    def test_titles_and_explicit_anchors(self):
        self.check('# 原标题\n', '# 新标题\n', ('headings',))
        self.check('原标题\n===\n', '新标题\n===\n', ('headings',))
        self.check('`命令`\n===\n', '`命令`\n---\n', ('headings',))
        self.check('<a id="old"></a>\n', '<a id="new"></a>\n', ('anchors',))
        self.check('标题 {#old}\n', '标题 {#new}\n', ('anchors',))

    def test_non_anchor_attributes_are_not_treated_as_ids(self):
        before = '<span data-id="old" data-name="old" title="id=old">内容</span>'
        self.check(before, before.replace('old', 'new'))
        self.check('<a title="id=old" ID="actual"></a>', '<a title="id=new" ID="changed"></a>', ('anchors',))

    def test_anchor_attributes_after_quoted_angle_brackets(self):
        for before in ('<a title="x > y" id="old"></a>',
                       "<a title='x < y > z' name='old'></a>"):
            with self.subTest(before=before):
                self.check(before, before.replace('old', 'new'), ('anchors',))
        self.check('<a title="x > y id=old" data-id="old"></a>',
                   '<a title="x > y id=new" data-id="new"></a>')

    def test_multiline_setext_is_not_silent_pass(self):
        before = 'first line\nsecond line\n===\n'
        result = MOD.compare_markdown(before, before.replace('first', 'changed'))
        self.assertEqual(result['status'], 'scan-incomplete')
        self.assertEqual(result['unapproved_categories'], ['headings'])
        self.assertEqual(result['diagnostics'][0]['line'], 1)
        result = MOD.compare_markdown(before, before, ('headings',))
        self.assertEqual(result['status'], 'scan-incomplete')
        self.check('# 章节\n单行标题\n===\n', '# 章节\n新标题\n===\n', ('headings',))
        self.check('正文\n\n单行标题\n---\n', '文字\n\n单行标题\n---\n')

    def test_setext_does_not_capture_prior_block(self):
        for before, after, changed in (
                ('# 标题\n---\n', '# 新标题\n---\n', ('headings',)),
                ('```\ncode\n```\n---\n', '```\nchanged\n```\n---\n', ('code',)),
                ('$$x$$\n---\n', '$$y$$\n---\n', ('math',))):
            with self.subTest(before=before):
                self.check(before, after, changed)

    def test_tables_protect_full_rows_not_just_shape(self):
        before = '| 组别 | 值 |\n| --- | ---: |\n| 甲 | 12 |\n| 乙 | 8 |\n'
        self.check(before, before.replace('甲 | 12', '甲 | 8').replace('乙 | 8', '乙 | 12'), ('tables',))
        self.check(before, before.replace('| 乙 | 8 |\n', ''), ('tables',))

    def test_tables_allow_short_delimiter_cells(self):
        for delimiter in ('| - | - |', '| :-: | -: |', ':-: | -----------:'):
            with self.subTest(delimiter=delimiter):
                before = '| 组别 | 值 |\n' + delimiter + '\n| 甲 | 12 |\n| 乙 | 8 |\n'
                after = before.replace('甲 | 12', '甲 | 8').replace('乙 | 8', '乙 | 12')
                self.check(before, after, ('tables',))

    def test_pipe_free_table_continuation_is_not_silent_pass(self):
        before = '| 组别 | 值 |\n| --- | --- |\n| 甲 | 12 |\n乙\n'
        result = MOD.compare_markdown(before, before.replace('\n乙\n', '\n丙\n'), ('tables',))
        self.assertEqual(result['status'], 'scan-incomplete')
        self.assertEqual(result['diagnostics'][0]['line'], 4)
        # A blank line or a new block really ends the table.
        for suffix in ('\n正文\n', '# 标题\n', '- 事项\n'):
            self.check(before.replace('乙\n', suffix), before.replace('乙\n', suffix))

    def test_masked_or_unicode_table_rows_are_not_blank_lines(self):
        for row in ('`code`', '$x$', '\u00a0', '\u2028'):
            with self.subTest(row=repr(row)):
                before = '| 组别 | 值 |\n| - | - |\n' + row + '\n| 乙 | 8 |\n'
                after = before.replace('乙 | 8', '乙 | 80')
                result = MOD.compare_markdown(before, after)
                self.assertEqual(result['status'], 'scan-incomplete')
                self.assertEqual(result['diagnostics'][0]['line'], 3)

    def test_list_markers_and_known_semantic_limit(self):
        before = '1. 断电\n2. 开盖\n'
        self.check(before, before.replace('2.', '3.'), ('lists',))
        # Same markers, opposite operational meaning: deliberately outside scope.
        self.check(before, '1. 开盖\n2. 断电\n')

    def test_task_completion_state_is_protected_separately_from_item_text(self):
        self.check('- [ ] 复核\n', '- [x] 复核\n', ('lists',))
        self.check('1. [X] 启动\n', '1. 启动\n', ('lists',))
        self.check('- [x] 检查日志\n', '- [x] 核对日志\n')
        self.check('- [x](log.md)\n', '- [y](log.md)\n')
        self.check('```md\n- [ ] 复核\n```\n', '```md\n- [x] 复核\n```\n', ('code',))

    def test_list_markers_are_independent_of_masked_inline_content(self):
        for before, after, category in (
                ('- $x$\n', '- $y$\n', 'math'),
                ('1. $x$\n', '1. $longer$\n', 'math'),
                ('- `run`\n', '- `run --safe`\n', 'code')):
            with self.subTest(before=before):
                self.check(before, after, (category,))
                self.check(before, after, (), (category,))
        # Marker-looking text inside a display formula or code span is not a list.
        self.check('$$\n- x\n$$\n', '$$\n2. x\n$$\n', ('math',))
        self.check('`command\nparameter`\n', '`command\nargument`\n', ('code',))

    def test_empty_list_items_and_setext_underline(self):
        self.check('1.\n', '2.\n', ('lists',))
        self.check('-\n', '+\n', ('lists',))
        self.check('1.\n', '1. 文字\n', ('lists',))
        # A one-dash Setext underline follows paragraph text, not an empty item.
        before = '标题\n-\n'
        result = self.check(before, before)
        self.assertEqual(result['token_counts']['lists']['before'], 0)

    def test_link_label_assignment_is_not_semantic_validation(self):
        before = '[甲](a.md)，[乙](b.md)。'
        self.check(before, '[乙](a.md)，[甲](b.md)。')
        self.check('甲组12 ms，乙组8 ms。', '甲组8 ms，乙组12 ms。')

    def test_allow_does_not_mask_other_categories(self):
        before = '# 结果\n执行 `run --safe`。'
        after = '# 试验结果\n执行 `run --force`。'
        result = self.check(before, after, ('code',), ('headings',))
        self.assertEqual(result['changed_categories'], ['code', 'headings'])
        with self.assertRaises(ValueError):
            MOD.compare_markdown(before, after, ('all',))

    def test_metadata_and_newline_normalization(self):
        before = '---\ntitle: 试验\n---\n正文\n'
        self.check(before, before.replace('试验', '测量'), ('metadata',))
        self.check(before, '\ufeff' + before.replace('\n', '\r\n'))

    def cli(self, *args):
        return subprocess.run([sys.executable, '-B', str(SCRIPT), *map(str, args)],
                              capture_output=True, encoding='utf-8', check=False)

    def test_cli_chinese_paths_json_and_readonly(self):
        with tempfile.TemporaryDirectory(prefix='unbot-md-') as folder:
            before, after = Path(folder) / '原稿.md', Path(folder) / '成稿.md'
            before.write_text('# 方法\n执行 `run`。\n', encoding='utf-8-sig')
            after.write_text('# 方法\n运行 `run`。\n', encoding='utf-8')
            originals = (before.read_bytes(), after.read_bytes())
            result = self.cli(before, after, '--json')
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data['status'], 'no-unapproved-change-found')
            self.assertNotIn('运行', result.stdout)
            self.assertEqual(originals, (before.read_bytes(), after.read_bytes()))
            after.write_text('# 方法\n运行 `changed`。\n', encoding='utf-8')
            self.assertEqual(self.cli(before, after).returncode, 1)
            after.write_text('执行 `run', encoding='utf-8')
            self.assertEqual(self.cli(before, after).returncode, 2)

    def test_cli_unreadable_and_non_utf8(self):
        with tempfile.TemporaryDirectory(prefix='unbot-md-') as folder:
            missing, invalid = Path(folder) / '缺失.md', Path(folder) / '非UTF8.md'
            invalid.write_bytes(b'\xff\xfe\x00')
            self.assertEqual(self.cli(missing, missing).returncode, 2)
            self.assertEqual(self.cli(invalid, invalid).returncode, 2)


if __name__ == '__main__':
    unittest.main()
