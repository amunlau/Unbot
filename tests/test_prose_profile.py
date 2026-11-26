import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prose_profile.py"
SPEC = importlib.util.spec_from_file_location("unbot_profile", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
profile = MODULE.profile


class ProseProfileTest(unittest.TestCase):
    def test_cli_and_import_entry_points(self):
        by_file = """
import importlib.util, json, sys
from pathlib import Path
before = list(sys.path)
spec = importlib.util.spec_from_file_location("editor_profile", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert sys.path == before
print(json.dumps(module.profile(Path(sys.argv[2]))))
"""
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "样稿.md"
            source.write_text("# 观测\n时间为 1.5 s。", encoding="utf-8")
            expected = json.loads(json.dumps(profile(source)))
            for flags, cwd in (([str(SCRIPT)], folder), (["-I", str(SCRIPT)], folder),
                               (["-m", "scripts.prose_profile"], ROOT),
                               (["-I", "-c", by_file, str(SCRIPT)], folder)):
                with self.subTest(flags=flags):
                    run = subprocess.run([sys.executable, "-B", "-X", "utf8", *flags, str(source)],
                                         cwd=cwd, capture_output=True, encoding="utf-8")
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertEqual(json.loads(run.stdout), expected)

    def test_markdown_boundaries_and_locations(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.md"
            path.write_text("""---
title: 目录
---
# 主题与任务
这是第一段。
第二行仍属首段。

甲 | 乙
--- | ---
需验证 | 未披露

````python
## 不应成为标题
```
假正文。
````

    不应进入统计。

在独立性检验中出现延迟响应。

该产品尚未披露容量。

工作范围
--------
普通正文。
""", encoding="utf-8")
            result = profile(path)
            self.assertEqual(result["body_paragraphs"], 4)
            self.assertEqual(result["tables"], 1)
            self.assertEqual(result["title_count"], 2)
            self.assertEqual(result["paragraph_end_hits"], 1)
            ps = result["sections"][0]["paragraphs"]
            self.assertEqual(ps[0]["loc"], "L5")
            self.assertEqual(ps[0]["sentences"], 2)
            self.assertEqual(result["closest_three_paragraph_windows"][0]["loc"], [p["loc"] for p in ps])

    def test_markdown_source_lines_comments_and_table_interruptions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.md"
            path.write_text(
                "前言\u2028仍在同一行。\n\n<!-- 暂存\n# 假标题\n-->\n"
                "| 甲\\|乙 | 丙 |\n| --- | --- |\n| 1 | 2 |\n"
                "## 实验 | 结果\nThe value was 1.5. Still stable.\n"
                "    续行属于该段。\n\n    假 | 表\n    --- | ---\n\n"
                "```含`反引号，此行不是围栏。\n\n# 后记\n末段。",
                encoding="utf-8",
            )
            result = profile(path)
            self.assertEqual(result["tables"], 1)
            self.assertEqual(result["title_count"], 2)
            self.assertEqual([s["loc"] for s in result["sections"]], ["L1", "L9", "L18"])
            ps = result["sections"][1]["paragraphs"]
            self.assertEqual([p["loc"] for p in ps], ["L10", "L16"])
            self.assertEqual(ps[0]["sentences"], 3)
            self.assertEqual(ps[0]["ending"], "续行属于该段")

    def test_word_styled_headings_tables_and_prose(self):
        w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        styles = f"""<w:styles xmlns:w="{w}">
        <w:style w:styleId="top"><w:name w:val="heading 1"/></w:style>
        <w:style w:styleId="custom"><w:name w:val="专题"/><w:basedOn w:val="top"/></w:style>
        <w:style w:styleId="idx"><w:name w:val="toc 1"/></w:style>
        <w:style w:styleId="cap"><w:name w:val="caption"/></w:style></w:styles>"""
        def p(text, style=""):
            return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.docx"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("word/styles.xml", styles)
                chunks = [p("封面日期"), p("重复标题", "idx"), p("本报告选取两组负载。"),
                          p("正式标题", "custom"), p("程序响应。"),
                          "<w:tbl><w:tr><w:tc>" + p("不得计入正文", "custom") + "</w:tc></w:tr></w:tbl>",
                          p("表1 结果", "cap"), p("结果仍需复核。")]
                z.writestr("word/document.xml", f'<w:document xmlns:w="{w}"><w:body>{"".join(chunks)}</w:body></w:document>')
            result = profile(path)
            self.assertEqual(result["title_count"], 1)
            self.assertEqual(result["body_paragraphs"], 3)
            self.assertEqual(result["tables"], 1)
            self.assertEqual(result["paragraph_end_hits"], 1)
            intro, section = result["sections"]
            self.assertEqual(intro["path"], [])
            self.assertEqual([(p["loc"], p["opening"]) for p in intro["paragraphs"]], [("B3", "本报告选取两组负载。")])
            self.assertEqual(section["path"], ["正式标题"])
            self.assertEqual([p["loc"] for p in section["paragraphs"]], ["B5", "B8"])

    def test_word_style_ids_and_visible_runs(self):
        w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        styles = f"""<w:styles xmlns:w="{w}">
          <w:style w:styleId="TOC1"><w:name w:val="索引条目"/></w:style>
          <w:style w:styleId="Heading2"><w:name w:val="研究小节"/></w:style>
        </w:styles>"""
        doc = f"""<w:document xmlns:w="{w}"><w:body>
          <w:p><w:r><w:t>封面日期</w:t></w:r></w:p>
          <w:p><w:pPr><w:pStyle w:val="TOC1"/></w:pPr><w:r><w:t>目录项</w:t></w:r></w:p>
          <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>测量</w:t></w:r></w:p>
          <w:moveFrom><w:p><w:r><w:t>原位置</w:t></w:r></w:p></w:moveFrom>
          <w:moveTo><w:p><w:r><w:t>完成。</w:t></w:r><w:r><w:rPr><w:vanish/></w:rPr>
            <w:t>尚未完成。</w:t></w:r></w:p></w:moveTo>
          <w:p><w:del><w:r><w:delText>已删除</w:delText></w:r></w:del>
            <w:moveFrom><w:r><w:t>移出文字</w:t></w:r></w:moveFrom>
            <w:ins><w:r><w:rPr><w:vanish w:val="0"/></w:rPr><w:t>第二行</w:t><w:cr/></w:r></w:ins>
            <w:moveTo><w:r><w:t>继续。</w:t></w:r></w:moveTo></w:p>
        </w:body></w:document>"""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/styles.xml", styles)
                archive.writestr("word/document.xml", doc)
            result = profile(path)
            self.assertEqual(result["title_count"], 1)
            self.assertEqual(result["heading_forms"][0]["level"], 2)
            self.assertEqual(result["body_paragraphs"], 2)
            self.assertEqual(result["paragraph_end_hits"], 0)
            ps = result["sections"][0]["paragraphs"]
            self.assertEqual([(p["loc"], p["opening"]) for p in ps], [("B4", "完成。"), ("B5", "第二行 继续。")])

    def test_no_prose_and_plain_unheaded_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "note.md"
            path.write_text("# 总结\n", encoding="utf-8")
            self.assertEqual(profile(path)["paragraph_chars"], {})
            path.write_text("三组数据。\n\n仍须调整。", encoding="utf-8")
            self.assertEqual(profile(path)["body_paragraphs"], 2)

    def test_markdown_numbered_mentions_and_shorthand(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "figures.md"
            path.write_text(
                "# 表99 只是标题\n说明分两行，\n正文可见[图 1](表85)和表2、3。\n"
                "![表84](chart.png)\n**图 1** 采集装置（复用图9）\n"
                "表2 样本构成\n表3 数据来源\n\n"
                "表4：第一次试验\n\n表4：第二次试验\n\n"
                "图 5 测量结果\n图 5 给出了原始读数。另见图6。\n"
                "记录 `表81`、![表82](src) 和 <!-- 表83 --> 的差异。\n"
                "[索引]: /表86\n\n"
                "| 说明 |\n| --- |\n| 表80 |\n\n"
                "```\n表79 示例\n```\n\n"
                "有图表 2 张，参照附表8、图 A1、Table 7、图12A。\n", encoding="utf-8")
            result = profile(path)
            entries = {x["label"]: x for x in result["figure_table_mentions"]["items"]}
            self.assertEqual(set(entries), {"图1", "表2", "表3", "表4", "图5", "图6"})
            self.assertEqual(entries["图1"]["position"], "before_caption")
            first = entries["图1"]["body_mentions"]
            self.assertEqual([(hit["loc"], hit["source"]) for hit in first], [("L3", "text")])
            self.assertEqual(entries["图1"]["captions"][0]["source"], "caption_text")
            self.assertEqual(entries["表2"]["body_mentions"][0]["shorthand"], "表2、3")
            self.assertEqual(entries["表3"]["position"], "no_body_mention")
            self.assertIsNone(entries["表3"]["first_body_loc"])
            self.assertEqual(entries["表4"]["position"], "ambiguous_caption")
            self.assertEqual([hit["loc"] for hit in entries["表4"]["captions"]], ["L9", "L11"])
            self.assertEqual(entries["图5"]["position"], "after_caption")
            self.assertEqual(entries["图6"]["position"], "no_caption")

    def test_subtree_totals_use_heading_positions_even_with_repeated_titles(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sections.md"
            path.write_text("引言。\n\n# 测试\n## 条件\n甲 乙。\n### 输入\n丙。\n"
                            "## 条件\n丁。\n# 测试\n末句。\n", encoding="utf-8")
            sections = profile(path)["sections"]
            self.assertEqual([(s["direct_chars"], s["subtree_chars"]) for s in sections],
                             [(3, 3), (0, 7), (3, 5), (2, 2), (2, 2), (3, 3)])

    def test_markdown_wrapped_mentions_and_visible_link_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "figures.md"
            path.write_text(
                "测量结果如\n图 1\n所示。另见[表2][图90]。\n\n"
                "图 1 中国人口分布\n表2 中位数估计\n\n"
                "图3\n\n图4\n\n参见图3。\n\n"
                "[图90]: /data/table\n", encoding="utf-8")
            result = profile(path)
            entries = {x["label"]: x for x in result["figure_table_mentions"]["items"]}
            self.assertEqual(set(entries), {"图1", "表2", "图3", "图4"})
            for label, loc in (("图1", "L2"), ("表2", "L3")):
                self.assertEqual(entries[label]["first_body_loc"], loc)
                self.assertEqual(entries[label]["position"], "before_caption")
            self.assertEqual(entries["图3"]["position"], "after_caption")
            self.assertEqual(entries["图4"]["position"], "no_body_mention")
            paragraph = result["sections"][0]["paragraphs"][0]
            self.assertEqual(paragraph["opening"], "测量结果如 图 1 所示。另见[表2][图90]。")

    def test_multiline_markdown_comment_hides_labels_and_keeps_line_positions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "figures.md"
            path.write_text(
                "正文见图1。<!-- 草稿\n表90 旧题注\n# 旧标题\n--> 继续，见表2。\n\n"
                "图1 中心节点\n表2 样本\n\n"
                "```html\n<!--\n```\n正文还见表3。\n\n"
                "字面标记 `<!--` 与图4。\n", encoding="utf-8")
            result = profile(path)
            entries = {x["label"]: x for x in result["figure_table_mentions"]["items"]}
            self.assertEqual(set(entries), {"图1", "表2", "表3", "图4"})
            self.assertEqual(result["title_count"], 0)
            self.assertEqual(result["body_paragraphs"], 3)
            self.assertEqual(entries["图1"]["first_body_loc"], "L1")
            self.assertEqual(entries["表2"]["first_body_loc"], "L4")
            self.assertEqual(entries["图1"]["position"], "before_caption")
            self.assertEqual(entries["表2"]["position"], "before_caption")

    def test_word_field_sources_are_per_number_and_caption_is_not_a_mention(self):
        w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

        def run(text):
            return f"<w:r><w:t>{text}</w:t></w:r>"

        def field_marker(marker):
            return f'<w:r><w:fldChar w:fldCharType="{marker}"/></w:r>'

        def simple_field(instruction, result):
            return f'<w:fldSimple w:instr="{instruction}">{run(result)}</w:fldSimple>'

        ref = (field_marker("begin") + "<w:r><w:instrText> R</w:instrText></w:r>"
               + "<w:r><w:instrText>EF bookmark</w:instrText></w:r>" + field_marker("separate")
               + run("1") + field_marker("end"))
        seq = simple_field(" SEQ 表 ", "1")
        chunks = [
            "<w:p>" + run("  见表 ") + ref + run("。另见表2、表1。") + "</w:p>",
            "<w:p>" + run("表 ") + seq + run(" 甲，附图9") + "</w:p>",
            '<w:p><w:pPr><w:pStyle w:val="Caption"/></w:pPr>' + run("表2 重画自图3。") + "</w:p>",
            "<w:p>" + run("图3：手工编号") + "</w:p>",
            "<w:p>" + simple_field("REF b", "图 3") + run(" 显示差异。") + "</w:p>",
            "<w:p>" + run("表4 手工编号") + "</w:p>",
            "<w:tbl><w:tr><w:tc><w:p>" + run("参见表4") + "</w:p></w:tc></w:tr></w:tbl>",
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "numbered.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml",
                                 f'<w:document xmlns:w="{w}"><w:body>{"".join(chunks)}</w:body></w:document>')
            entries = {x["label"]: x for x in profile(path)["figure_table_mentions"]["items"]}
            self.assertEqual(set(entries), {"表1", "表2", "图3", "表4"})
            self.assertEqual([x["source"] for x in entries["表1"]["body_mentions"]], ["REF", "text"])
            self.assertEqual(entries["表1"]["captions"][0]["source"], "SEQ")
            self.assertEqual(entries["表2"]["captions"][0]["source"], "caption_style")
            self.assertEqual(entries["图3"]["captions"][0]["source"], "caption_text")
            self.assertEqual(entries["图3"]["first_body_loc"], "B5")
            self.assertEqual(entries["图3"]["body_mentions"][0]["source"], "REF")
            self.assertEqual(entries["表4"]["position"], "no_body_mention")

    def test_word_chapter_field_and_local_sequence_in_one_visible_number(self):
        w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

        def run(text):
            return f"<w:r><w:t>{text}</w:t></w:r>"

        def field(instruction, result):
            return f'<w:fldSimple w:instr="{instruction}">{run(result)}</w:fldSimple>'

        chapter = field("STYLEREF 1", "2")
        paragraphs = [
            run("详见") + field("REF chart", "图2-3") + run("。"),
            run("图") + chapter + run("-") + field("SEQ 图", "3") + run(" 中心节点。"),
            run("另见图") + chapter + run("-") + field("REF item", "3") + run("。"),
            run("参见图") + chapter + run("-4。"),
            run("图2-5 中位数分布"),
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "chapter.docx"
            with zipfile.ZipFile(path, "w") as archive:
                body = "".join(f"<w:p>{p}</w:p>" for p in paragraphs)
                archive.writestr("word/document.xml", f'<w:document xmlns:w="{w}"><w:body>{body}</w:body></w:document>')
            result = profile(path)
            entries = {x["label"]: x for x in result["figure_table_mentions"]["items"]}
            self.assertEqual(entries["图2-3"]["position"], "before_caption")
            self.assertEqual([h["source"] for h in entries["图2-3"]["body_mentions"]], ["REF", "REF"])
            self.assertEqual(entries["图2-3"]["captions"][0]["source"], "SEQ")
            self.assertEqual(entries["图2-4"]["body_mentions"][0]["source"], "other_field")
            self.assertEqual(entries["图2-5"]["position"], "no_body_mention")
            self.assertEqual(result["body_paragraphs"], 3)

    def test_inline_image_paired_link_target_and_soft_wrapped_numbers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "figures.md"
            path.write_text(
                "![示意图8](图9(低清).png) 见图\n1。另见[统计记录](数据(旧)/表8.csv)。\n\n"
                "正文还列出表\n2。\n\n[数据源]: /表7.csv\n\n"
                "图1 布置\n表2 数据\n\n![图6](images(1)/图5.png)\n", encoding="utf-8")
            result = profile(path)
            items = {x["label"]: x for x in result["figure_table_mentions"]["items"]}
            self.assertEqual({k: (v["position"], v["first_body_loc"]) for k, v in items.items()},
                             {"图1": ("before_caption", "L1"), "表2": ("before_caption", "L4")})
            self.assertEqual(result["body_paragraphs"], 2)
            first = result["sections"][0]["paragraphs"][0]
            self.assertEqual(first["chars"], len("见图1。另见统计记录。"))
            self.assertEqual(first["ending"], "另见统计记录")
            self.assertIn("低清", first["opening"])

    def test_table_number_distinguished_from_quantities_in_chinese_prose(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "counts.md"
            path.write_text("作者发表2篇论文。蓝线代表1号件，采用量表5分制。工作量表6列出三类任务。\n\n"
                            "表6 任务\n", encoding="utf-8")
            items = profile(path)["figure_table_mentions"]["items"]
            self.assertEqual([(x["label"], x["position"]) for x in items], [("表6", "before_caption")])

    def test_word_field_instructions_do_not_expose_nested_cached_references(self):
        w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        body = """<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r>
          <w:r><w:instrText> IF </w:instrText></w:r>
          <w:fldSimple w:instr="REF old"><w:r><w:t>见图9。</w:t></w:r></w:fldSimple>
          <w:r><w:instrText> = "" "无" "见图1。" </w:instrText></w:r>
          <w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>见图1。</w:t></w:r>
          <w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>"""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fields.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", f'<w:document xmlns:w="{w}"><w:body>{body}</w:body></w:document>')
            result = profile(path)
            self.assertEqual([x["label"] for x in result["figure_table_mentions"]["items"]], ["图1"])
            self.assertEqual(result["sections"][0]["paragraphs"][0]["opening"], "见图1。")

    def test_closest_windows_rank_before_display_rounding(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "windows.md"
            sizes = [3001, 3000, 3000, 3000]
            path.write_text("\n\n".join("甲" * n for n in sizes), encoding="utf-8")
            windows = profile(path)["closest_three_paragraph_windows"]
            self.assertEqual(windows[0]["loc"], ["L3", "L5", "L7"])
            self.assertEqual(windows[0]["relative_range"], windows[1]["relative_range"])


if __name__ == "__main__":
    unittest.main()
