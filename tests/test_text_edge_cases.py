"""文本定位的解码边界、Markdown 未闭合结构与科技数字的回归用例。"""

import codecs
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class TextEdgeCases(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.folder = Path(workspace.name)

    def cli(self, script, *args, status=0):
        result = subprocess.run([sys.executable, "-B", "-X", "utf8", str(SCRIPTS / script), *map(str, args)],
                                capture_output=True, encoding="utf-8")
        self.assertEqual(status, result.returncode, result.stderr or result.stdout)
        return result.stdout

    def test_explicit_bom_codecs_and_positions(self):
        path = self.folder / "sample.txt"
        text = "测量值\r\n为 2。"
        for codec, bom in (("utf-8", codecs.BOM_UTF8), ("utf-16le", codecs.BOM_UTF16_LE),
                           ("utf-32be", codecs.BOM_UTF32_BE)):
            with self.subTest(codec=codec):
                source = bom + text.encode(codec)
                path.write_bytes(source)
                inventory = json.loads(self.cli("review_text.py", "inspect", path, "--encoding", codec))
                self.assertEqual(inventory["lines"][0]["text"], "测量值")
                self.assertEqual(inventory["source_sha256"], hashlib.sha256(source).hexdigest())
                self.assertEqual(inventory["text_sha256"],
                                 hashlib.sha256(text.replace("\r\n", "\n").encode()).hexdigest())

    def test_wrong_codec_cannot_reuse_decoded_manifest(self):
        path = self.folder / "sample.txt"
        path.write_bytes("OK 热".encode("gbk"))
        item = json.loads(self.cli("review_text.py", "inspect", path, "--encoding", "gbk"))
        item["findings"] = [{"paragraph": "L0001", "quote": "OK", "category": "language",
                             "issue": "术语拼写", "comment": "措辞待核。"}]
        manifest = self.folder / "items.json"
        manifest.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
        out = self.folder / "view.html"
        self.cli("review_text.py", "annotate", path, manifest, out, "--encoding", "latin1", status=2)
        self.assertFalse(out.exists())
        self.cli("review_text.py", "annotate", path, manifest, out, "--encoding", "gbk")
        self.assertIn("热", out.read_text(encoding="utf-8"))

    def test_legacy_manifest_cannot_publish_a_different_decoding(self):
        path = self.folder / "记录.txt"
        path.write_bytes("OK 热".encode("gbk"))
        data = {"source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "findings": [{"paragraph": "L0001", "quote": "OK", "comment": "请核对工况。"}]}
        manifest = self.folder / "意见.json"
        manifest.write_text(json.dumps(data), encoding="utf-8")
        out = self.folder / "审阅.html"
        self.cli("review_text.py", "annotate", path, manifest, out, "--encoding", "latin1", status=2)
        self.assertFalse(out.exists())
        # Legacy manifests remain usable when an explicit codec reproduces the default text.
        path.write_bytes("OK 热".encode("utf-8-sig"))
        data["source_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(data), encoding="utf-8")
        self.cli("review_text.py", "annotate", path, manifest, out, "--encoding", "utf-8")
        self.assertIn("热", out.read_text(encoding="utf-8"))

    def test_interrupted_review_does_not_publish_a_partial_output(self):
        source = self.folder / "原稿.txt"
        source.write_text("调试记录。", encoding="utf-8")
        manifest = json.loads(self.cli("review_text.py", "inspect", source))
        manifest["findings"] = [{"paragraph": "L0001", "quote": "记录", "category": "evidence",
                                 "issue": "缺少记录编号", "comment": "请核实。"}]
        findings = self.folder / "意见.json"
        findings.write_text(json.dumps(manifest), encoding="utf-8")
        out = self.folder / "审阅.html"
        # Simulate termination after the first bytes reach disk, bypassing any
        # cleanup the review process would perform on a Python exception.
        interruption = """
import os, runpy, sys
from pathlib import Path
original_open = Path.open
def interrupted_open(path, mode="r", *args, **kwargs):
    handle = original_open(path, mode, *args, **kwargs)
    if mode == "xb":
        handle.write(b"partial")
        handle.flush()
        os._exit(83)
    return handle
Path.open = interrupted_open
sys.argv = sys.argv[1:]
sys.path.insert(0, str(Path(sys.argv[0]).parent))
runpy.run_path(sys.argv[0], run_name="__main__")
"""
        crash = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", interruption,
                                str(SCRIPTS / "review_text.py"), "annotate", str(source), str(findings), str(out)],
                               capture_output=True)
        self.assertEqual(83, crash.returncode, crash.stderr)
        self.assertFalse(out.exists())
        self.cli("review_text.py", "annotate", source, findings, out)
        self.assertIn("请核实。", out.read_text(encoding="utf-8"))

    def test_markdown_appendix_after_open_or_closed_blocks(self):
        cases = {
            "````text\n```\n结束": True,
            "~~~\n内容": True,
            "<!-- 未结束": True,
            "<PRE class='diag'>\na": True,
            "```html\n<!--\n<pre>\n```": False,
            "请保留行内的 `<!--`、`<pre>` 和 ``` 标记。": False,
            "<!-- 已结束 -->\n<PRE>样例</PRE>": False,
        }
        src = self.folder / "sample.md"
        for sequence, (tail, source_view) in enumerate(cases.items()):
            with self.subTest(tail=tail):
                original = "原句\n\n" + tail
                src.write_bytes(original.encode())
                data = json.loads(self.cli("review_text.py", "inspect", src))
                data["findings"] = [{"paragraph": "L0001", "quote": "原句", "category": "evidence",
                                     "issue": "引文出处待核", "comment": "复核。"}]
                manifest = self.folder / "review.json"
                manifest.write_text(json.dumps(data), encoding="utf-8")
                out = self.folder / f"review-{sequence}.md"
                self.cli("review_text.py", "annotate", src, manifest, out)
                review = out.read_text(encoding="utf-8")
                self.assertEqual(review.startswith("## 原稿（按 Markdown 源码显示）"), source_view)
                self.assertIn(original, review)
                self.assertIn("\n\n## 审阅意见\n", review)
                self.assertIn("第 1 行第 1 列", review)
                self.assertEqual(src.read_bytes(), original.encode())

    def test_source_view_isolates_notes_from_html_disclosure(self):
        src = self.folder / "报告.md"
        original = "测量结果\n\n<details>\n<summary>计算记录</summary>\n\n运行记录。\n"
        src.write_bytes(original.encode("utf-8"))
        data = json.loads(self.cli("review_text.py", "inspect", src))
        data["findings"] = [{"paragraph": "L0001", "quote": "测量结果", "category": "evidence",
                             "issue": "未交代测量工况", "comment": "请注明工况。"}]
        manifest = self.folder / "意见.json"
        manifest.write_text(json.dumps(data), encoding="utf-8")
        out = self.folder / "审阅.md"
        self.cli("review_text.py", "annotate", src, manifest, out, "--source-view")
        review = out.read_text(encoding="utf-8")
        self.assertIn("```markdown\n" + original + "\n```\n\n## 审阅意见", review)
        self.assertIn("第 1 行第 1 列", review)
        self.assertIn("请注明工况。", review)
        self.assertEqual(src.read_bytes(), original.encode("utf-8"))
        html = self.folder / "审阅.html"
        self.cli("review_text.py", "annotate", src, manifest, html, "--source-view", status=2)
        self.assertFalse(html.exists())

    def test_categories_visible_in_same_format_and_html_reviews(self):
        cases = [
            ("style", "AI味与文风", "空泛评价", "具有重要意义", "请指出这项结果对哪一项设计决定有影响。"),
            ("logic", "篇章与逻辑", "概念未引入", "采用分级指标 K", "此处首次使用 K，请说明定义或指向计算方法。"),
            ("format", "格式与排版", "标题编号重复", "2.2 试验结果", "前一节已使用 2.2，请按实际层级重新编号。"),
            ("language", "文字与语法", "字词重复", "运行时时间", "请核对多出的“时”字。"),
            ("technical", "事实与技术", "组别互换", "乙组为 8 ms", "表 1 将该值列于甲组，请核对组别。"),
            ("evidence", "依据待核", "数据来源缺失", "效率提高 12%", "所引表未随稿提供，请核对比较基准。"),
        ]
        original = "\n".join(quote for _, _, _, quote, _ in cases)
        for suffix in (".txt", ".md"):
            src = self.folder / ("原稿" + suffix)
            src.write_text(original, encoding="utf-8")
            data = json.loads(self.cli("review_text.py", "inspect", src))
            self.assertEqual(data["finding_schema"], 2)
            data["findings"] = [
                {"paragraph": line["id"], "quote": quote, "category": code, "issue": issue, "comment": comment}
                for line, (code, _, issue, quote, comment) in zip(data["lines"], cases)
            ]
            manifest = self.folder / "意见.json"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            for extension in (suffix, ".html"):
                with self.subTest(input=suffix, output=extension):
                    out = self.folder / ("review-" + src.name + extension)
                    self.cli("review_text.py", "annotate", src, manifest, out)
                    text = out.read_text(encoding="utf-8")
                    for _, label, issue, _, explanation in cases:
                        self.assertIn(f"【{label}｜{issue}】", text)
                        self.assertIn(explanation, text)
                    if extension == suffix:
                        self.assertTrue(text.startswith(original))

    def test_classification_errors_leave_no_output(self):
        src = self.folder / "原稿.txt"
        src.write_text("缺少依据", encoding="utf-8")
        inventory = json.loads(self.cli("review_text.py", "inspect", src))
        finding = {"paragraph": "L0001", "quote": "依据", "category": "evidence",
                   "issue": "缺少原始记录", "comment": "请提供记录编号。"}
        manifest = self.folder / "notes.json"
        out = self.folder / "审阅.html"
        for invalid in (
            {"findings": [{key: value for key, value in finding.items() if key != "category"}]},
            {"findings": [dict(finding, category="unknown")]},
            {"findings": [dict(finding, issue="  ")]},
            {"findings": [dict(finding, issue="依据待核")]},
            {"findings": [dict(finding, comment="")]},
            {"findings": [], "finding_schema": 999},
            {"findings": [], "review_language": "eng"},
        ):
            with self.subTest(invalid=invalid):
                manifest.write_text(json.dumps(dict(inventory, **invalid)), encoding="utf-8")
                self.cli("review_text.py", "annotate", src, manifest, out, status=2)
                self.assertFalse(out.exists())
        # Unversioned manifests with newly supplied category fields also receive validation.
        partial = {key: value for key, value in finding.items() if key != "issue"}
        manifest.write_text(json.dumps({"source_sha256": inventory["source_sha256"],
                                        "findings": [partial]}), encoding="utf-8")
        self.cli("review_text.py", "annotate", src, manifest, out, status=2)
        self.assertFalse(out.exists())
        manifest.write_text(json.dumps(dict(inventory, findings=[])), encoding="utf-8")
        self.cli("review_text.py", "annotate", src, manifest, out)
        self.assertNotIn("<mark id=", out.read_text(encoding="utf-8"))

    def test_numeric_bounds_uncertainty_exponents_and_percent(self):
        src = self.folder / "before.txt"
        dst = self.folder / "after.txt"
        src.write_text("阈值 ≤ 5，结果 0.8 ± 0.2，比例 76 %，范围 10⁻³ m²", encoding="utf-8")
        dst.write_text("阈值 ≥ 5，结果 0.8 和 0.2，比例 76，范围 10³ m³", encoding="utf-8")
        output = self.cli("check_literals.py", src, dst, status=1)
        for token in ("≤5", "≥5", "±0.2", "76%", "10⁻³", "10³", "²", "³"):
            self.assertIn(repr(token), output)
        dst.write_text("阈值 ≤5，结果 0.8 ±0.2，比例 76\u202f%，范围 10⁻³ m²", encoding="utf-8")
        self.cli("check_literals.py", src, dst)

    def test_fullwidth_bounds_and_spaced_mathematical_sign(self):
        before = self.folder / "before.md"
        after = self.folder / "after.md"
        before.write_text("误差＜5 ms，温差为 − 3 °C，判据为 n ≠ 0。", encoding="utf-8")
        after.write_text("误差＞5 ms，温差为 3 °C，判据为 n = 0。", encoding="utf-8")
        output = self.cli("check_literals.py", before, after, status=1)
        for token in ("＜5", "＞5", "−3", "≠0", "=0"):
            self.assertIn(repr(token), output)
        before.write_text("- 3 个试样，阈值＜＝ 5，温差为 − 3 °C。", encoding="utf-8")
        after.write_text("3 个试样，阈值＜＝5，温差为 −3 °C。", encoding="utf-8")
        self.cli("check_literals.py", before, after)

    def test_chained_bounds_and_engineering_comparisons(self):
        before = self.folder / "before.md"
        after = self.folder / "after.md"
        for original, changed, expected in (
            ("0 < x ≤ 1", "0 > x ≤ 1", ("0<", "0>")),
            ("status != 0", "status == 0", ("!=0", "==0")),
            ("p <\u20090.05", "p >\u20090.05", ("<0.05", ">0.05")),
        ):
            with self.subTest(original=original):
                before.write_text(original, encoding="utf-8")
                after.write_text(changed, encoding="utf-8")
                output = self.cli("check_literals.py", before, after, status=1)
                for token in expected:
                    self.assertIn(repr(token), output)
        before.write_text("0 < x ≤ 1，p <\u20090.05。", encoding="utf-8")
        after.write_text("0<x≤1，p<0.05。", encoding="utf-8")
        self.cli("check_literals.py", before, after)
        before.write_text('5<sup>2</sup>，<span title="a > b">3</span>，5<br>7。', encoding="utf-8")
        after.write_text("5，2，3，5，7。", encoding="utf-8")
        self.cli("check_literals.py", before, after)


if __name__ == "__main__":
    unittest.main()
