"""Word 保护设置、包关系和可见文字上的批注回归。"""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches
from lxml import etree


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "review_docx.py"


class WordEdgeCases(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.source = self.folder / "source.docx"
        self.output = self.folder / "review.docx"
        self.manifest = self.folder / "findings.json"

    def cli(self, *args, ok=True):
        result = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(SCRIPT), *map(str, args)],
            encoding="utf-8", capture_output=True,
        )
        self.assertEqual(result.returncode == 0, ok, result.stderr)
        return result

    def review_first(self, inventory, quote="结果", ok=True):
        findings = [{"paragraph": inventory["paragraphs"][0]["paragraph"],
                     "quote": quote, "comment": "请复核适用范围。"}]
        self.manifest.write_text(
            json.dumps({"source_sha256": inventory["source_sha256"], "findings": findings}),
            encoding="utf-8",
        )
        return self.cli("annotate", self.source, self.manifest, self.output, ok=ok)

    def test_modification_password_and_readonly_recommendation(self):
        doc = Document()
        doc.add_paragraph("结果")
        flag = OxmlElement("w:writeProtection")
        flag.set(qn("w:hash"), "9oN7nWkCAyEZib1RomSJTjmPpCY=")
        doc.settings.element.insert(0, flag)
        doc.save(self.source)
        inventory = json.loads(self.cli("inspect", self.source).stdout)
        self.review_first(inventory, ok=False)
        self.assertTrue(inventory["write_blockers"])
        self.assertFalse(self.output.exists())
        self.assertEqual(sha256(self.source.read_bytes()).hexdigest(), inventory["source_sha256"])

        flag.attrib.clear()
        flag.set(qn("w:recommended"), "1")
        doc.save(self.source)
        inventory = json.loads(self.cli("inspect", self.source).stdout)
        self.assertFalse(inventory["write_blockers"])
        self.review_first(inventory)
        with ZipFile(self.source) as src, ZipFile(self.output) as out:
            self.assertEqual(src.read("word/settings.xml"), out.read("word/settings.xml"))

    def test_explicitly_visible_runs_and_existing_classic_comment(self):
        doc = Document()
        p = doc.add_paragraph()
        p.add_run("试验结").font.hidden = False
        p.add_run("果有效。").bold = True
        doc.add_paragraph("既有批注")
        original = self.folder / "original.docx"
        doc.save(original)
        first = json.loads(self.cli("inspect", original).stdout)
        self.manifest.write_text(json.dumps({
            "source_sha256": first["source_sha256"], "findings": [
                {"paragraph": first["paragraphs"][1]["paragraph"], "quote": "既有批注", "comment": "保留原意见"}
            ]}), encoding="utf-8")
        self.cli("annotate", original, self.manifest, self.source)
        inventory = json.loads(self.cli("inspect", self.source).stdout)
        self.assertTrue(inventory["paragraphs"][0]["annotatable"])
        self.review_first(inventory)
        reopened = Document(self.output)
        self.assertEqual([p.text for p in doc.paragraphs], [p.text for p in reopened.paragraphs])
        with ZipFile(self.output) as archive:
            comments = etree.fromstring(archive.read("word/comments.xml"))
            self.assertEqual([node.text for node in comments.iter(qn("w:t"))],
                             ["保留原意见", "请复核适用范围。"])
        self.assertTrue(next(r for r in reopened.paragraphs[0].runs if r.text == "果").bold)

    def test_active_main_part_is_checked_before_extracting(self):
        doc = Document()
        doc.add_paragraph("旧版正文")
        doc.save(self.source)
        alternate = self.folder / "alternate.docx"
        with ZipFile(self.source) as src, ZipFile(alternate, "w") as out:
            for item in src.infolist():
                data = src.read(item)
                if item.filename == "_rels/.rels":
                    root = etree.fromstring(data)
                    rel = next(e for e in root if e.get("Type", "").endswith("/officeDocument"))
                    rel.set("Target", "word/alternate.xml")
                    data = etree.tostring(root)
                elif item.filename == "[Content_Types].xml":
                    root = etree.fromstring(data)
                    main = next(e for e in root if e.get("PartName") == "/word/document.xml")
                    etree.SubElement(root, main.tag, PartName="/word/alternate.xml",
                                     ContentType=main.get("ContentType"))
                    data = etree.tostring(root)
                out.writestr(item.filename, data)
            out.writestr("word/alternate.xml", src.read("word/document.xml").replace(
                "旧版正文".encode(), "现行正文".encode()))
        self.assertEqual(Document(alternate).paragraphs[0].text, "现行正文")
        result = self.cli("inspect", alternate, ok=False)
        self.assertIn("主部件", result.stderr)

    def test_english_classified_note_alongside_existing_legacy_comment(self):
        doc = Document()
        doc.add_paragraph("Prior observation.")
        doc.add_paragraph("We therefore use scale K.")
        original = self.folder / "original.docx"
        doc.save(original)
        first = json.loads(self.cli("inspect", original).stdout)
        self.assertEqual(first["finding_schema"], 2)
        legacy = {
            "source_sha256": first["source_sha256"],
            "findings": [{"paragraph": first["paragraphs"][0]["paragraph"], "quote": "Prior observation",
                          "comment": "Original reviewer note."}],
        }
        self.manifest.write_text(json.dumps(legacy), encoding="utf-8")
        self.cli("annotate", original, self.manifest, self.source)
        current = json.loads(self.cli("inspect", self.source).stdout)
        current["review_language"] = "en"
        current["findings"] = [{
            "paragraph": current["paragraphs"][1]["paragraph"], "quote": "scale K",
            "category": "logic", "issue": "Missing premise",
            "comment": "Define K before using it to choose the procedure.",
        }]
        self.manifest.write_text(json.dumps(current), encoding="utf-8")
        self.cli("annotate", self.source, self.manifest, self.output)
        with ZipFile(self.output) as archive:
            notes = etree.fromstring(archive.read("word/comments.xml")).findall(qn("w:comment"))
            note_texts = ["".join(node.itertext()) for node in notes]
        self.assertEqual(len(note_texts), 2)
        self.assertEqual(note_texts[0], "Original reviewer note.")
        self.assertTrue(note_texts[1].startswith("[Logic and coherence | Missing premise]"))
        self.assertIn(current["findings"][0]["comment"], note_texts[1])
        self.assertEqual(Document(self.output).paragraphs[1].text, doc.paragraphs[1].text)
        current["findings"][0].pop("category")
        self.manifest.write_text(json.dumps(current), encoding="utf-8")
        incomplete = self.folder / "incomplete.docx"
        self.cli("annotate", self.source, self.manifest, incomplete, ok=False)
        self.assertFalse(incomplete.exists())

    def test_merged_continuation_text_is_not_visible_or_annotatable(self):
        doc = Document()
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "纵向首格"
        table.cell(0, 0).merge(table.cell(1, 0))
        table._tbl.tr_lst[1].tc_lst[0].p_lst[0].add_r().add_t("纵向续格内留存的字")
        table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "水平首格"
        table.cell(0, 1).text = "水平续格内留存的字"
        for cell, val in zip(table._tbl.tr_lst[0].tc_lst, ("restart", "continue")):
            flag = OxmlElement("w:hMerge")
            flag.set(qn("w:val"), val)
            cell.get_or_add_tcPr().append(flag)
        doc.save(self.source)
        data = json.loads(self.cli("inspect", self.source).stdout)
        entries = data["paragraphs"]
        self.assertEqual([p["text"] for p in entries if p["annotatable"]], ["纵向首格", "水平首格"])
        skipped = [p for p in entries if "续格" in p.get("skip_reason", "")]
        self.assertEqual(len(skipped), 2)
        self.assertTrue(all(p["text"] == "" and not p["editable_ranges"] for p in skipped))

    def test_generated_bilingual_document_sets_chinese_proofing_language(self):
        spec = {"title": "采样试验", "blocks": [
            {"type": "paragraph", "text": "两组使用相同的输入。"},
            {"type": "paragraph", "text": "The inputs were identical."},
        ]}
        draft = self.folder / "draft.json"
        draft.write_text(json.dumps(spec), encoding="utf-8")
        subprocess.run([sys.executable, "-B", str(SCRIPT.with_name("write_docx.py")),
                        str(draft), str(self.output)], capture_output=True, check=True)
        normal = Document(self.output).styles["Normal"].element
        lang = normal.find(f"{qn('w:rPr')}/{qn('w:lang')}")
        self.assertEqual(lang.get(qn("w:eastAsia")), "zh-CN")

    def test_font_symbol_preserves_position_and_requires_readback(self):
        doc = Document()
        p = doc.add_paragraph("公差范围 ")
        symbol = OxmlElement("w:sym")
        symbol.set(qn("w:font"), "Symbol")
        symbol.set(qn("w:char"), "F0B1")  # Plus-or-minus in this font.
        p.add_run()._r.append(symbol)
        p.add_run("5 ms。")
        doc.save(self.source)
        data = json.loads(self.cli("inspect", self.source).stdout)
        entry = data["paragraphs"][0]
        self.assertEqual(entry["text"], "公差范围 \ufffc5 ms。")
        self.assertTrue(entry["partial"])
        self.assertIn("U+FFFC", entry["manual_review"])
        self.review_first(data, "\ufffc5 ms", ok=False)
        self.review_first(data, "5 ms")
        reopened = Document(self.output).paragraphs[0]._p
        marker = reopened.find(qn("w:commentRangeStart"))
        self.assertEqual(marker.getnext().findtext(qn("w:t")), "5 ms")
        self.assertEqual(marker.getprevious().find(qn("w:sym")).get(qn("w:char")), "F0B1")

    def test_tab_stops_and_inline_hyphens_in_comment_offsets(self):
        doc = Document()
        p = doc.add_paragraph()
        p.paragraph_format.tab_stops.add_tab_stop(Inches(1))
        p.add_run("结果")
        p.add_run().add_tab()
        p.add_run("near")
        p.add_run()._r.append(OxmlElement("w:noBreakHyphen"))
        p.add_run("field")
        p.add_run()._r.append(OxmlElement("w:softHyphen"))
        p.add_run("结果")
        doc.save(self.source)
        expected = "结果\tnear\u2011field\u00ad结果"
        data = json.loads(self.cli("inspect", self.source).stdout)
        entry = data["paragraphs"][0]
        self.assertEqual(entry["text"], expected)
        self.manifest.write_text(json.dumps({
            "source_sha256": data["source_sha256"], "findings": [
                {"paragraph": entry["paragraph"], "quote": "结果", "start": expected.rindex("结果"),
                 "comment": "复核末尾的量值。"}]}), encoding="utf-8")
        self.cli("annotate", self.source, self.manifest, self.output)
        p = Document(self.output).paragraphs[0]._p
        marker = p.find(qn("w:commentRangeStart"))
        self.assertEqual(marker.getnext().findtext(qn("w:t")), "结果")
        self.assertEqual(marker.getprevious().find(qn("w:softHyphen")).tag, qn("w:softHyphen"))
