"""从命令行入口回归验证审阅副本、原句定位和文件保护。仅写临时目录。"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ReviewTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.findings = self.folder / "findings.json"

    def cli(self, name, *args, success=True):
        result = subprocess.run([sys.executable, "-B", "-X", "utf8", str(SCRIPTS / name), *map(str, args)],
                                capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode == 0, success, result.stderr or result.stdout)
        return result.stdout

    def manifest(self, inventory, findings):
        data = {"source_sha256": inventory["source_sha256"], "findings": findings}
        self.findings.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_word_title_preserved_at_metadata_limit(self):
        from docx import Document

        text = ("面向多工况连续测量的工程试验报告 / "
                "Experimental characterization under varying loads and temperatures ") * 4
        for length in (255, 256):
            with self.subTest(length=length):
                title = text[:length]
                draft = self.folder / "稿件.json"
                draft.write_text(json.dumps({"title": title, "blocks": [
                    {"type": "paragraph", "text": "各工况的测量程序见表 1。"}
                ]}), encoding="utf-8")
                output = self.folder / f"report-{length}.docx"
                self.cli("write_docx.py", draft, output)
                doc = Document(output)
                self.assertEqual((doc.paragraphs[0].style.name, doc.paragraphs[0].text), ("Title", title))
                self.assertEqual(doc.core_properties.title, title if length == 255 else "")

    def test_redirected_cli_unicode_paths_and_diagnostics(self):
        # Agents capture command output in pipes, including on legacy-code-page hosts.
        folder = self.folder / "中英文 review"
        folder.mkdir()
        env = dict(os.environ, PYTHONIOENCODING="ascii")

        def run(name, *args):
            return subprocess.run([sys.executable, "-B", str(SCRIPTS / name), *map(str, args)],
                                  cwd=folder, env=env, capture_output=True, encoding="utf-8")

        spec = {"title": "试验报告", "blocks": [{"type": "paragraph", "text": "耗时为 12 ms。"}]}
        (folder / "定稿.json").write_text(json.dumps(spec), encoding="utf-8")
        generated = run("write_docx.py", "定稿.json", "试验 报告.docx")
        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.assertIn("已生成", generated.stdout)
        checked = run("review_docx.py", "inspect", "试验 报告.docx")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn("耗时为 12 ms。", [p["text"] for p in json.loads(checked.stdout)["paragraphs"]])

        (folder / "原稿.txt").write_text("阈值 ≤ 5", encoding="utf-8")
        (folder / "终稿.txt").write_text("阈值 ≥ 5", encoding="utf-8")
        changed = run("check_literals.py", "原稿.txt", "终稿.txt")
        self.assertEqual(changed.returncode, 1)
        self.assertEqual(changed.stderr, "")
        self.assertIn("≥5", changed.stdout)

        for script, missing in (("review_text.py", "缺失.txt"), ("review_docx.py", "缺失.docx"),
                                ("review_pptx.py", "缺失.pptx")):
            with self.subTest(script=script):
                error = run(script, "inspect", missing)
                self.assertEqual(error.returncode, 2)
                self.assertIn(missing, error.stderr)

        for name, dep in (("write_docx.py", "python-docx"), ("review_docx.py", "lxml"), ("review_pptx.py", "lxml")):
            with self.subTest(missing_dependency=name):
                # -S skips site-packages to model a fresh Python interpreter.
                missing_dep = subprocess.run([sys.executable, "-S", str(SCRIPTS / name), "--help"],
                                             cwd=folder, env=dict(env, PYTHONPATH=""), capture_output=True,
                                             encoding="utf-8")
                self.assertNotEqual(missing_dep.returncode, 0)
                self.assertIn("当前 Python", missing_dep.stderr)
                self.assertIn(dep, missing_dep.stderr)

    def test_txt_exact_selection_after_repeated_phrase(self):
        path = self.folder / "报告.txt"
        text = "温度\r\n极大改善，极大改善。"
        path.write_bytes(text.encode("utf-16"))
        src = path.read_bytes()
        inventory = json.loads(self.cli("review_text.py", "inspect", path))
        item = {"paragraph": "L0002", "quote": "极大改善", "comment": "表达建议｜第二次评价没有补充指标。"}
        out = self.folder / "审阅.html"
        self.manifest(inventory, [item])
        self.cli("review_text.py", "annotate", path, self.findings, out, success=False)
        self.assertFalse(out.exists())
        self.manifest(inventory, [dict(item, start=5)])
        self.cli("review_text.py", "annotate", path, self.findings, out)
        self.assertIn('极大改善，<mark id="q1">极大改善</mark>', out.read_text(encoding="utf-8"))
        self.assertEqual(src, path.read_bytes())

    def test_markdown_multiline_quote_and_literal_html(self):
        path = self.folder / "paper.md"
        path.write_text("# 条件\n全面\n提升。\n```html\n<img src=x>\n```", encoding="utf-8")
        idx = json.loads(self.cli("review_text.py", "inspect", path))
        self.manifest(idx, [{"paragraph": "L0002", "quote": "全面\n提升", "comment": "请给出比较指标。"}])
        out = self.folder / "审阅.html"
        self.cli("review_text.py", "annotate", path, self.findings, out)
        review = out.read_text(encoding="utf-8")
        self.assertIn('全面\n提升</mark>', review)
        self.assertIn("&lt;img src=x&gt;", review)
        md = self.folder / "审阅.md"
        self.cli("review_text.py", "annotate", path, self.findings, md)
        self.assertTrue(md.read_text(encoding="utf-8").startswith(path.read_text(encoding="utf-8")))

    def test_stale_or_existing_file(self):
        path = self.folder / "data.txt"
        path.write_bytes(b"before")
        idx = json.loads(self.cli("review_text.py", "inspect", path))
        self.manifest(idx, [])
        self.cli("review_text.py", "annotate", path, self.findings, path, success=False)
        self.assertEqual(path.read_bytes(), b"before")
        path.write_bytes(b"changed")
        out = self.folder / "review.txt"
        self.cli("review_text.py", "annotate", path, self.findings, out, success=False)
        self.assertFalse(out.exists())

    def test_word_table_comment_and_existing_output(self):
        spec = {"title": "试验报告", "blocks": [
            {"type": "heading", "level": 1, "text": "1 试验范围"},
            {"type": "paragraph", "text": "仅完成单节点试验。"},
            {"type": "table", "headers": ["环境", "结论"], "rows": [["单节点", "适用于所有部署环境"]]}]}
        draft = self.folder / "draft.json"
        draft.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        path = self.folder / "报告.docx"
        self.cli("write_docx.py", draft, path)
        original = path.read_bytes()
        inventory = json.loads(self.cli("review_docx.py", "inspect", path))
        row = next(p for p in inventory["paragraphs"] if p["text"] == "适用于所有部署环境")
        self.manifest(inventory, [{"paragraph": row["paragraph"], "quote": "所有部署环境",
                                   "comment": "技术含义风险｜试验只覆盖单节点。"}])
        output = self.folder / "报告-审阅.docx"
        self.cli("review_docx.py", "annotate", path, self.findings, output)
        with ZipFile(path) as a, ZipFile(output) as b:
            doc_a = ET.fromstring(a.read("word/document.xml"))
            doc_b = ET.fromstring(b.read("word/document.xml"))
            def paragraphs(root):
                return ["".join(v.text or "" for v in para.iter(W + "t")) for para in root.iter(W + "p")]
            self.assertEqual(paragraphs(doc_a), paragraphs(doc_b))
            cell = doc_b.find(f".//{W}tc//{W}commentRangeStart")
            self.assertIsNotNone(cell)
            comment = ET.fromstring(b.read("word/comments.xml")).find(W + "comment")
            self.assertEqual(cell.get(W + "id"), comment.get(W + "id"))
            self.assertIn("只覆盖单节点", "".join(comment.itertext()))
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        self.cli("review_docx.py", "annotate", path, self.findings, output, success=False)
        self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), digest)
        self.assertEqual(original, path.read_bytes())

    def test_word_hidden_or_space_sensitive_text(self):
        from docx import Document
        from docx.enum.style import WD_STYLE_TYPE

        doc = Document()
        hidden = doc.styles.add_style("Concealed", WD_STYLE_TYPE.CHARACTER)
        hidden.font.hidden = True
        derived = doc.styles.add_style("Internal Note", WD_STYLE_TYPE.CHARACTER)
        derived.base_style = hidden
        doc.add_paragraph().add_run("内部标记", style=derived)
        p = doc.add_paragraph()
        t = p.add_run("  alpha beta  ")._r.find(W + "t")
        del t.attrib["{http://www.w3.org/XML/1998/namespace}space"]
        p.add_run("可见词")
        src = self.folder / "边界.docx"
        doc.save(src)
        idx = json.loads(self.cli("review_docx.py", "inspect", src))
        for quote in ("内部标记", "alpha"):
            entry = next(p for p in idx["paragraphs"] if quote in p["text"])
            self.manifest(idx, [{"paragraph": entry["paragraph"], "quote": quote, "comment": "测试意见"}])
            out = self.folder / "不应写入.docx"
            self.cli("review_docx.py", "annotate", src, self.findings, out, success=False)
            self.assertFalse(out.exists())
        entry = next(p for p in idx["paragraphs"] if "可见词" in p["text"])
        self.manifest(idx, [{"paragraph": entry["paragraph"], "quote": "可见词", "comment": "测试意见"}])
        out = self.folder / "可见段.docx"
        self.cli("review_docx.py", "annotate", src, self.findings, out)
        with ZipFile(out) as z:
            root = ET.fromstring(z.read("word/document.xml"))
            text = next(t for t in root.iter(W + "t") if t.text == "  alpha beta  ")
            self.assertNotIn("{http://www.w3.org/XML/1998/namespace}space", text.attrib)


if __name__ == "__main__":
    unittest.main()
