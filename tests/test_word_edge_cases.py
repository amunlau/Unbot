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
from docx.enum.style import WD_STYLE_TYPE
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

    def test_native_scripts_keep_semantics_and_raw_comment_offsets(self):
        doc = Document()
        base = doc.styles.add_style("ChemicalIndex", WD_STYLE_TYPE.CHARACTER)
        base.font.subscript = True
        derived = doc.styles.add_style("DerivedIndex", WD_STYLE_TYPE.CHARACTER)
        derived.base_style = base
        p = doc.add_paragraph("CO")
        p.add_run("2", derived)
        p.add_run("/CO2,m")
        p.add_run("2").font.superscript = True

        elevated = doc.styles.add_style("Elevated", WD_STYLE_TYPE.PARAGRAPH)
        elevated.font.superscript = True
        p = doc.add_paragraph(style=elevated)
        p.add_run("A")
        plain = p.add_run("B")
        plain._r.get_or_add_rPr().get_or_add_vertAlign().set(qn("w:val"), "baseline")
        p.add_run("C", derived)
        manual = doc.add_paragraph("Offset")
        shift = OxmlElement("w:position")
        shift.set(qn("w:val"), "3")
        manual.runs[0]._r.get_or_add_rPr().append(shift)
        doc.save(self.source)

        data = json.loads(self.cli("inspect", self.source).stdout)
        entries = data["paragraphs"]
        ranges = [{"start": 2, "end": 3, "position": "subscript"},
                  {"start": 9, "end": 10, "position": "superscript"}]
        self.assertEqual(entries[0]["text"], "CO2/CO2,m2")
        self.assertEqual(entries[0]["script_ranges"], ranges)
        self.assertEqual(entries[1]["script_ranges"], [
            {"start": 0, "end": 1, "position": "superscript"},
            {"start": 2, "end": 3, "position": "subscript"}])
        self.assertIn("基线", entries[2]["manual_review"])
        self.manifest.write_text(json.dumps({
            "source_sha256": data["source_sha256"],
            "findings": [{"paragraph": entries[0]["paragraph"], "start": 2, "quote": "2",
                          "comment": "核对化学式下标。"}]}), encoding="utf-8")
        self.cli("annotate", self.source, self.manifest, self.output)
        paragraph = Document(self.output).paragraphs[0]
        marked = paragraph._p.find(qn("w:commentRangeStart")).getnext()
        self.assertEqual(marked.find(qn("w:t")).text, "2")
        self.assertEqual(marked.find("./"+qn("w:rPr")+"/"+qn("w:rStyle")).get(qn("w:val")), derived.style_id)
        self.assertEqual(marked.getnext().tag, qn("w:commentRangeEnd"))
        self.assertEqual(json.loads(self.cli("inspect", self.output).stdout)["paragraphs"][0]["script_ranges"], ranges)

    def test_document_defaults_and_conditional_table_scripts(self):
        doc = Document()
        defaults = doc.styles.element.find("./"+qn("w:docDefaults")+"/"+qn("w:rPrDefault")+"/"+qn("w:rPr"))
        align = OxmlElement("w:vertAlign")
        align.set(qn("w:val"), "superscript")
        defaults.append(align)
        doc.add_paragraph("A")
        style = doc.styles.add_style("ConditionalScript", WD_STYLE_TYPE.TABLE)
        first_row = OxmlElement("w:tblStylePr")
        first_row.set(qn("w:type"), "firstRow")
        props = OxmlElement("w:rPr")
        lower = OxmlElement("w:vertAlign")
        lower.set(qn("w:val"), "subscript")
        props.append(lower)
        first_row.append(props)
        style.element.append(first_row)
        doc.add_table(1, 1, style).cell(0, 0).text = "B"
        doc.save(self.source)
        paragraphs = json.loads(self.cli("inspect", self.source).stdout)["paragraphs"]
        self.assertEqual(paragraphs[0]["script_ranges"], [{"start": 0, "end": 1, "position": "superscript"}])
        self.assertNotIn("manual_review", paragraphs[0])
        self.assertNotIn("script_ranges", paragraphs[1])
        self.assertIn("上下标", paragraphs[1]["manual_review"])

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

    def test_word_writer_preserves_windows_and_unix_line_breaks(self):
        draft = self.folder / "draft.json"
        spec = {"title": "试验\r\n报告", "blocks": [
            {"type": "paragraph", "text": "A\r\nB\nC\rD\r\n\r\nE"},
            {"type": "table", "headers": ["压力\r\n(kPa)"], "rows": [["12\r\n15"]]},
        ]}
        draft.write_text(json.dumps(spec), encoding="utf-8")
        subprocess.run([sys.executable, "-B", str(SCRIPT.with_name("write_docx.py")),
                        str(draft), str(self.output)], capture_output=True, check=True)
        saved = Document(self.output)
        self.assertEqual(saved.paragraphs[0].text, "试验\n报告")
        self.assertEqual(saved.paragraphs[1].text, "A\nB\nC\nD\n\nE")
        self.assertEqual(saved.tables[0].cell(0, 0).text, "压力\n(kPa)")
        self.assertEqual(saved.tables[0].cell(1, 0).text, "12\n15")

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

    def test_inline_formula_and_picture_do_not_disappear_from_reading_view(self):
        from io import BytesIO
        from PIL import Image

        doc = Document()
        p = doc.add_paragraph("允许误差为")
        equation = OxmlElement("m:oMath")
        run = OxmlElement("m:r")
        term = OxmlElement("m:t")
        term.text = "±"
        run.append(term)
        equation.append(run)
        p._p.append(equation)
        p.add_run("5%。")
        image = BytesIO()
        Image.new("RGB", (8, 8), "white").save(image, format="PNG")
        image.seek(0)
        doc.add_paragraph().add_run().add_picture(image, width=Inches(1))
        doc.save(self.source)

        data = json.loads(self.cli("inspect", self.source).stdout)
        first, second = data["paragraphs"]
        self.assertEqual(first["reading_text"], "允许误差为〔公式〕5%。")
        self.assertIn("Word", first["manual_review"])
        self.assertEqual(second["reading_text"], "〔图形〕")
        self.assertFalse(second["annotatable"])
        self.assertEqual(first["text"], "允许误差为5%。")
        self.assertEqual(first["editable_ranges"], [[0, 5], [5, 8]])
        self.review_first(data, "为5%", ok=False)
        self.review_first(data, "5%")
        with ZipFile(self.source) as original, ZipFile(self.output) as reviewed:
            self.assertEqual(original.read("word/media/image1.png"), reviewed.read("word/media/image1.png"))
        marked = Document(self.output).paragraphs[0]._p
        start = marked.find(qn("w:commentRangeStart"))
        self.assertEqual(start.getprevious().tag, qn("m:oMath"))
        self.assertEqual(start.getnext().findtext(qn("w:t")), "5%")

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


    def test_inspect_inventory_uses_finding_schema_two(self):
        doc = Document()
        doc.add_paragraph("阈值 12 ms。")
        doc.save(self.source)
        data = json.loads(self.cli("inspect", self.source).stdout)
        self.assertEqual(data["finding_schema"], 2)

    def test_write_docx_error_paths_do_not_overwrite(self):
        writer = SCRIPT.with_name("write_docx.py")
        draft = self.folder / "draft.json"
        output = self.folder / "out.docx"
        spec = {"title": "试验摘录", "blocks": [{"type": "paragraph", "text": "耗时为 12 ms。"}]}
        draft.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        first = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(writer), str(draft), str(output)],
            capture_output=True, encoding="utf-8",
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        original = output.read_bytes()

        again = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(writer), str(draft), str(output)],
            capture_output=True, encoding="utf-8",
        )
        self.assertEqual(again.returncode, 2)
        self.assertIn("目标已存在", again.stderr)
        self.assertEqual(output.read_bytes(), original)

        draft.write_text("{", encoding="utf-8")
        other = self.folder / "other.docx"
        invalid = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(writer), str(draft), str(other)],
            capture_output=True, encoding="utf-8",
        )
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("生成失败", invalid.stderr)
        self.assertFalse(other.exists())

        draft.write_text(json.dumps({"title": "试验摘录", "blocks": [{"type": "unknown", "text": "x"}]}), encoding="utf-8")
        unknown = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(writer), str(draft), str(other)],
            capture_output=True, encoding="utf-8",
        )
        self.assertEqual(unknown.returncode, 2)
        self.assertIn("生成失败", unknown.stderr)
        self.assertFalse(other.exists())
