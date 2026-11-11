"""回归：格式与版式夹具存在，金标准标签仍符合 schema 2。

本文件不评测编辑判断。样稿应否标注，须由维护者按 references/format-review.md
做人工或离线检查；测试通过只表示夹具和标签写法仍在。对演示文稿，测试还锁定可见页与隐藏页的文字分布、夹具 07、17 的结论框尺寸与位置、
占位符文字和画面外坐标；对 Word 夹具，还锁定域指令、缺失书签、目次缓存与页眉文字。
测试全部通过，不证明这些规则已经能稳定检出错误，也不证明起草或润色已经不会引入同类错误。
结构检查不证明画面裁切已经发生。Office 桌面复核另见 07–11 和 17 的样稿说明。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Inches


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "format"
CLASSIFICATION = ROOT / "scripts" / "review_classification.py"
INSPECT = ROOT / "scripts" / "review_pptx.py"

REQUIRED_CASE_IDS = (
    "01-figure-citation-gap",
    "02-table-caption-below",
    "03-broken-cross-ref",
    "04-numbering-and-captions-consistent",
    "05-hidden-appendix-definition",
    "06-definition-on-visible-slide",
    "07-text-readable",
    "08-broken-cross-ref-field",
    "09-stale-toc-header",
    "10-placeholder-title",
    "11-text-off-slide",
    "12-si-space-inconsistent",
    "13-si-space-and-plane-angle",
    "14-citation-number-gap",
    "15-citation-numbers-consistent",
    "16-reading-references-not-cited",
    "17-text-clipped-at-slide-edge",
    "18-preprint-access-date-missing",
    "19-preprint-date-and-doi",
    "20-excerpt-with-partial-lists",
    "21-table-caption-template",
)

MUST_FLAG = {
    "01-figure-citation-gap",
    "02-table-caption-below",
    "03-broken-cross-ref",
    "05-hidden-appendix-definition",
    "17-text-clipped-at-slide-edge",
    "18-preprint-access-date-missing",
    "08-broken-cross-ref-field",
    "09-stale-toc-header",
    "10-placeholder-title",
    "11-text-off-slide",
    "12-si-space-inconsistent",
    "14-citation-number-gap",
}

MUST_NOT_FLAG = {
    "07-text-readable",
    "19-preprint-date-and-doi",
    "20-excerpt-with-partial-lists",
    "21-table-caption-template",
    "04-numbering-and-captions-consistent",
    "06-definition-on-visible-slide",
    "13-si-space-and-plane-angle",
    "15-citation-numbers-consistent",
    "16-reading-references-not-cited",
}

GENERATION_FILES = (
    "generation/materials-window-w.md",
    "generation/must-not-produce.md",
    "generation/acceptable-draft.md",
    "generation/README.md",
)


def load_classification():
    spec = importlib.util.spec_from_file_location("review_classification", CLASSIFICATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect_pptx(path: Path) -> dict:
    result = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(INSPECT), "inspect", str(path)],
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def slide_texts(page: dict) -> str:
    return "\n".join(item["text"] for item in page.get("paragraphs", []))


def has_no_autofit(shape) -> bool:
    body = shape.text_frame._txBody.find(qn("a:bodyPr"))
    if body is None:
        return False
    return body.find(qn("a:noAutofit")) is not None


class FormatFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_classification()
        gold_path = FIXTURES / "gold.json"
        cls.gold = json.loads(gold_path.read_text(encoding="utf-8"))
        cls.cases = {item["id"]: item for item in cls.gold["cases"]}

    def test_fixture_catalog_and_required_cases_exist(self):
        self.assertTrue((FIXTURES / "README.md").is_file())
        self.assertTrue((FIXTURES / "gold.json").is_file())
        self.assertEqual(set(REQUIRED_CASE_IDS), set(self.cases))
        self.assertTrue(MUST_FLAG.isdisjoint(MUST_NOT_FLAG))
        self.assertEqual(set(self.cases), MUST_FLAG | MUST_NOT_FLAG)
        readme = (FIXTURES / "README.md").read_text(encoding="utf-8")
        self.assertIn("不评测应否标注", readme)
        self.assertIn("不证明规则已能稳定检出格式错误", readme)
        self.assertIn("全绿不证明防引入", readme)
        for case_id, case in self.cases.items():
            with self.subTest(case=case_id):
                self.assertEqual(case["must_flag"], case_id in MUST_FLAG)
                self.assertGreaterEqual(len(case["files"]), 1)
                self.assertTrue(case["gold_note_zh"].strip())
                if case["must_flag"]:
                    self.assertTrue(case["gold_note_zh"].startswith("应标"))
                    self.assertFalse(case["gold_note_zh"].startswith("应标。应标。"))
                else:
                    self.assertTrue(case["gold_note_zh"].startswith("不应标"))
                    self.assertFalse(case["gold_note_zh"].startswith("不应标。不应标。"))
                    self.assertNotIn("category", case)
                    self.assertNotIn("issue_zh", case)
                for name in case["files"]:
                    path = FIXTURES / name
                    self.assertTrue(path.is_file(), f"缺少样稿 {name}")
                    if name.endswith(".pptx"):
                        self.assertGreater(path.stat().st_size, 1000, name)
                        with ZipFile(path) as archive:
                            self.assertTrue(any(n.startswith("ppt/slides/slide") for n in archive.namelist()))
                    elif name.endswith(".docx"):
                        self.assertGreater(path.stat().st_size, 1000, name)
                        with ZipFile(path) as archive:
                            self.assertIn("word/document.xml", archive.namelist())
                    else:
                        excerpt = path.read_text(encoding="utf-8").strip()
                        self.assertGreater(len(excerpt), 20, name)

    def test_documented_labels_match_schema_two_and_category_names(self):
        categories = self.mod.CATEGORIES
        findings_zh = []
        findings_en = []
        readme = (FIXTURES / "README.md").read_text(encoding="utf-8")
        for case_id, case in self.cases.items():
            if not case["must_flag"]:
                continue
            with self.subTest(case=case_id):
                category = case["category"]
                issue_zh = case["issue_zh"].strip()
                issue_en = case["issue_en"].strip()
                self.assertIn(category, categories)
                zh_name, en_name = categories[category]
                for issue in (issue_zh, issue_en):
                    self.assertTrue(issue)
                    self.assertEqual(len(issue.splitlines()), 1)
                    self.assertNotIn(issue.casefold(), {
                        category, zh_name.casefold(), en_name.casefold(),
                    })
                expected = f"【{zh_name}｜{issue_zh}】"
                self.assertIn(expected, case["gold_note_zh"])
                self.assertIn(expected, readme)
                findings_zh.append({
                    "category": category,
                    "issue": issue_zh,
                    "comment": f"{case_id} 的金标准标签，仅用于核对写法。",
                })
                findings_en.append({
                    "category": category,
                    "issue": issue_en,
                    "comment": f"Schema check for {case_id} only.",
                })

        rendered_zh = list(self.mod.review_findings({
            "finding_schema": self.mod.FINDING_SCHEMA,
            "review_language": "zh",
            "findings": findings_zh,
        }))
        self.assertEqual(self.mod.FINDING_SCHEMA, 2)
        self.assertEqual(len(rendered_zh), len(MUST_FLAG))
        for item, text in rendered_zh:
            zh_name, _ = categories[item["category"]]
            self.assertTrue(text.startswith(f"【{zh_name}｜{item['issue']}】"))

        rendered_en = list(self.mod.review_findings({
            "finding_schema": self.mod.FINDING_SCHEMA,
            "review_language": "en",
            "findings": findings_en,
        }))
        self.assertEqual(len(rendered_en), len(MUST_FLAG))
        for item, text in rendered_en:
            _, en_name = categories[item["category"]]
            self.assertTrue(text.startswith(f"[{en_name} | {item['issue']}]"))

    def test_test_module_does_not_claim_to_judge_the_drafts(self):
        source = __doc__ or ""
        self.assertIn("不评测编辑判断", source)
        self.assertIn("测试通过只表示夹具和标签写法仍在", source)
        self.assertIn("不证明这些规则已经能稳定检出错误", source)
        self.assertIn("也不证明起草或润色已经不会引入同类错误", source)
        self.assertIn("不证明画面裁切已经发生", source)

    def test_markdown_cases_retain_the_documented_cues(self):
        zh01 = (FIXTURES / "01-figure-citation-gap.zh.md").read_text(encoding="utf-8")
        en01 = (FIXTURES / "01-figure-citation-gap.en.md").read_text(encoding="utf-8")
        self.assertIn("图 6", zh01)
        self.assertIn("图 4", zh01)
        self.assertIn("图 5", zh01)
        self.assertNotIn("图 6　", zh01)
        self.assertIn("Fig. 6", en01)
        self.assertIn("Fig. 4", en01)
        self.assertIn("Fig. 5", en01)

        zh02 = (FIXTURES / "02-table-caption-below.zh.md").read_text(encoding="utf-8")
        self.assertIn("未指定相反模板", zh02)
        self.assertTrue(zh02.rstrip().endswith("表 2　插入损耗"))
        self.assertIn("通道", zh02.split("表 2")[0])

        zh03 = (FIXTURES / "03-broken-cross-ref.zh.md").read_text(encoding="utf-8")
        en03 = (FIXTURES / "03-broken-cross-ref.en.md").read_text(encoding="utf-8")
        self.assertIn("错误！未定义书签", zh03)
        self.assertIn("Error! Bookmark not defined", en03)

        examples = (
            ("zh", "表 1 列出", "见图 1", "表 1　中位插入损耗", "通道\t中位插入损耗", "（图位于此处）", "图 1　通道 1 的输出光谱"),
            ("en", "Table 1 lists", "shown in Fig. 1", "Table 1  Median insertion loss", "Channel\tMedian insertion loss", "(Figure appears here.)", "Fig. 1  Output spectrum of channel 1"),
        )
        for language, table_ref, figure_ref, table_title, table_header, figure, figure_title in examples:
            with self.subTest(language=language):
                sample = (FIXTURES / f"04-numbering-and-captions-consistent.{language}.md").read_text(encoding="utf-8")
                self.assertLess(sample.index(table_ref), sample.index(table_title))
                self.assertLess(sample.index(table_title), sample.index(table_header))
                self.assertLess(sample.index(figure_ref), sample.index(figure))
                self.assertLess(sample.index(figure), sample.index(figure_title))

    def test_missing_reference_claims_depend_on_a_complete_inventory(self):
        examples = (
            ("zh", "插入损耗随波长的变化见图 6。", "全文图清单", "随摘录提供的图题", "参考文献节选"),
            ("en", "The insertion loss versus wavelength is shown in Fig. 6.", "Complete figure inventory",
             "Figure captions accompanying the excerpt", "Selected references"),
        )
        for language, cross_ref, inventory, partial_figures, partial_refs in examples:
            with self.subTest(language=language):
                complete = (FIXTURES / f"01-figure-citation-gap.{language}.md").read_text(encoding="utf-8")
                excerpt = (FIXTURES / f"20-excerpt-with-partial-lists.{language}.md").read_text(encoding="utf-8")
                self.assertIn(cross_ref, complete)
                self.assertIn(cross_ref, excerpt)
                self.assertIn(inventory, complete)
                self.assertIn(partial_figures, excerpt)
                paragraph, references = excerpt.split(partial_refs)
                self.assertIn("[3]", paragraph)
                self.assertNotIn("[3]", references)

    def test_below_table_caption_depends_on_the_supplied_template(self):
        regular = (FIXTURES / "02-table-caption-below.zh.md").read_text(encoding="utf-8")
        exception = (FIXTURES / "21-table-caption-template.zh.md").read_text(encoding="utf-8")
        regular_heading, regular_table = regular.split("\n", 1)
        template_heading, template_table = exception.split("\n", 1)
        self.assertIn("未指定相反模板", regular_heading)
        self.assertIn("项目模板规定表题位于表下", template_heading)
        self.assertEqual(regular_table.rstrip(), template_table.rstrip())

    def test_hidden_appendix_fixture_keeps_definition_off_visible_slides(self):
        path = FIXTURES / "05-hidden-appendix-definition.pptx"
        data = inspect_pptx(path)
        self.assertEqual(len(data["slides"]), 2)
        visible, hidden = data["slides"]
        self.assertFalse(visible["hidden"])
        self.assertTrue(hidden["hidden"])
        visible_text = slide_texts(visible)
        hidden_text = slide_texts(hidden)
        self.assertIn("窗口 W", visible_text)
        self.assertIn("超时", visible_text)
        self.assertNotIn("样本数", visible_text)
        self.assertNotIn("定义为", visible_text)
        self.assertIn("窗口 W", hidden_text)
        self.assertIn("定义为", hidden_text)
        self.assertIn("样本数", hidden_text)
        self.assertIn("附录", hidden_text)

    def test_visible_definition_counterexample_keeps_definition_on_visible_path(self):
        path = FIXTURES / "06-definition-on-visible-slide.pptx"
        data = inspect_pptx(path)
        self.assertEqual(len(data["slides"]), 3)
        first, second, appendix = data["slides"]
        self.assertFalse(first["hidden"])
        self.assertFalse(second["hidden"])
        self.assertTrue(appendix["hidden"])
        first_text = slide_texts(first)
        second_text = slide_texts(second)
        appendix_text = slide_texts(appendix)
        self.assertIn("窗口 W 定义为", first_text)
        self.assertIn("样本数", first_text)
        self.assertIn("窗口 W", second_text)
        self.assertIn("超时", second_text)
        self.assertIn("示例", appendix_text)
        self.assertIn("50 kHz", appendix_text)
        self.assertIn("主讲页已经给出定义", appendix_text)

    def test_readable_and_clipped_slides_share_content_but_differ_in_position(self):
        boxes = []
        for case_id in ("07-text-readable", "17-text-clipped-at-slide-edge"):
            prs = Presentation(FIXTURES / f"{case_id}.pptx")
            self.assertEqual(len(prs.slides), 1)
            slide = prs.slides[0]
            self.assertNotEqual(slide._element.get("show"), "0")
            candidates = [
                shape for shape in slide.shapes
                if shape.has_text_frame and "12 dB，可提交验收" in shape.text
            ]
            self.assertEqual(len(candidates), 1)
            box = candidates[0]
            self.assertTrue(has_no_autofit(box))
            self.assertEqual(box.height, Inches(0.55))
            self.assertEqual(box.width, Inches(4.2))
            if case_id == "07-text-readable":
                self.assertLess(box.top + box.height, prs.slide_height)
            else:
                self.assertLess(box.top, prs.slide_height)
                self.assertGreater(box.top + box.height, prs.slide_height)
            boxes.append(box)
        self.assertEqual(boxes[0].text, boxes[1].text)

    def test_generation_antipatterns_exist_and_do_not_claim_prevention(self):
        gold = self.gold
        self.assertIn("generation", gold)
        self.assertIn("不证明生成路径已防引入", gold["generation"]["note"])
        for name in GENERATION_FILES:
            path = FIXTURES / name
            with self.subTest(file=name):
                self.assertTrue(path.is_file(), f"缺少 {name}")
                self.assertGreater(len(path.read_text(encoding="utf-8").strip()), 20, name)
        materials = (FIXTURES / gold["generation"]["materials"]).read_text(encoding="utf-8")
        bad = (FIXTURES / gold["generation"]["must_not_produce"]).read_text(encoding="utf-8")
        good = (FIXTURES / gold["generation"]["acceptable_draft"]).read_text(encoding="utf-8")
        readme = (FIXTURES / "generation/README.md").read_text(encoding="utf-8")
        self.assertIn("窗口 W", materials)
        self.assertIn("样本数", materials)
        self.assertIn("隐藏", bad)
        self.assertIn("窗口 W", bad)
        self.assertIn("可见", good)
        self.assertIn("样本数", good)
        self.assertIn("切换日志及失败次数尚未提供", materials)
        self.assertIn("失败次数待按该判据统计", good)
        self.assertIn("不证明起草或润色已经不会引入", readme)
        # 未做格式类持出复测，目录中不应冒充 heldout 证据
        self.assertFalse((FIXTURES / "heldout").exists())
        self.assertNotIn("heldout", gold)

    def test_word_field_fixture_points_to_missing_bookmark(self):
        path = FIXTURES / "08-broken-cross-ref-field.docx"
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        with ZipFile(path) as archive:
            root = etree.fromstring(archive.read("word/document.xml"))
        instr = " ".join(root.xpath("//w:instrText/text()", namespaces=ns))
        result = root.xpath("//w:r[w:fldChar/@w:fldCharType='separate']/following-sibling::w:r[1]/w:t/text()", namespaces=ns)
        bookmarks = root.xpath("//w:bookmarkStart/@w:name", namespaces=ns)
        self.assertIn("REF", instr)
        self.assertIn("_RefDoesNotExist", instr)
        self.assertIn("错误！未定义书签。", result)
        self.assertNotIn("_RefDoesNotExist", bookmarks)

    def test_stale_toc_and_header_keep_old_heading_text(self):
        path = FIXTURES / "09-stale-toc-header.docx"
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        with ZipFile(path) as archive:
            root = etree.fromstring(archive.read("word/document.xml"))
            headers = [etree.fromstring(archive.read(name)) for name in archive.namelist() if name.startswith("word/header") and name.endswith(".xml")]
        instr = " ".join(root.xpath("//w:instrText/text()", namespaces=ns))
        toc_result = root.xpath("//w:r[w:fldChar/@w:fldCharType='separate']/following-sibling::w:r[1]/w:t/text()", namespaces=ns)
        heading_blob = "".join(
            "".join(para.xpath(".//w:t/text()", namespaces=ns))
            for para in root.xpath("//w:p", namespaces=ns)
            if para.xpath("./w:pPr/w:pStyle[starts-with(@w:val,'Heading')]", namespaces=ns)
        )
        self.assertIn("TOC", instr)
        self.assertIn("3 试验结果 ........ 3", toc_result)
        self.assertIn("3 讨论", heading_blob)
        header_text = "".join(t for header in headers for t in header.xpath("//w:t/text()", namespaces=ns))
        self.assertIn("3 试验结果", header_text)
        for header in headers:
            self.assertFalse(header.xpath("//w:fldSimple | //w:instrText", namespaces=ns))

    def test_placeholder_and_off_slide_fixtures_keep_constructed_layout(self):
        title_path = FIXTURES / "10-placeholder-title.pptx"
        prs = Presentation(str(title_path))
        titles = []
        subtitles = []
        for shape in prs.slides[0].shapes:
            if not shape.has_text_frame:
                continue
            text = "\n".join(p.text for p in shape.text_frame.paragraphs)
            if "单击此处添加标题" in text:
                titles.append(shape)
            if "单击此处添加副标题" in text:
                subtitles.append(shape)
        self.assertEqual(len(titles), 1)
        self.assertEqual(len(subtitles), 1)
        self.assertTrue(titles[0].is_placeholder)
        self.assertTrue(subtitles[0].is_placeholder)

        off_path = FIXTURES / "11-text-off-slide.pptx"
        prs = Presentation(str(off_path))
        off = on = None
        for shape in prs.slides[0].shapes:
            if not shape.has_text_frame:
                continue
            text = "\n".join(p.text for p in shape.text_frame.paragraphs)
            if "0.42 MPa" in text:
                off = shape
            if "管路暂缓交付" in text:
                on = shape
        self.assertIsNotNone(off)
        self.assertIsNotNone(on)
        self.assertLessEqual(off.left + off.width, 0)
        self.assertGreaterEqual(on.left, 0)
        self.assertGreaterEqual(on.top, 0)
        self.assertLessEqual(on.left + on.width, prs.slide_width)
        self.assertLessEqual(on.top + on.height, prs.slide_height)
        self.assertIn("0.35 MPa", off.text)
        self.assertNotIn("0.42 MPa", on.text)
        self.assertNotIn("0.35 MPa", on.text)

    def test_si_and_citation_markdown_cases_retain_the_documented_cues(self):
        bad_si = (FIXTURES / "12-si-space-inconsistent.zh.md").read_text(encoding="utf-8")
        good_si = (FIXTURES / "13-si-space-and-plane-angle.zh.md").read_text(encoding="utf-8")
        self.assertIn("采用 SI", bad_si)
        self.assertIn("37°C", bad_si)
        self.assertIn("25mL", bad_si)
        self.assertNotRegex(bad_si, r"\d\s+(?:°C|mL)")
        self.assertIn("25 °C", good_si)
        self.assertIn("15°", good_si)
        self.assertNotIn("15 °", good_si)

        gap = (FIXTURES / "14-citation-number-gap.zh.md").read_text(encoding="utf-8")
        ok = (FIXTURES / "15-citation-numbers-consistent.zh.md").read_text(encoding="utf-8")
        self.assertIn("GB/T 7714—2025", gap)
        self.assertIn("顺序编码制", gap)
        self.assertIn("本稿完整清单", gap)
        self.assertIn("[3]", gap)
        self.assertIn("[1]", gap)
        self.assertIn("[2]", gap)
        self.assertNotIn("[3]", gap.split("参考文献")[1])
        self.assertIn("见[1]", ok)
        self.assertIn("[2]", ok)
        self.assertIn("[1] 李某", ok)
        self.assertIn("[2] 王某", ok)

        reading = (FIXTURES / "16-reading-references-not-cited.zh.md").read_text(encoding="utf-8")
        self.assertIn("GB/T 7714—2025", reading)
        self.assertIn("顺序编码制", reading)
        self.assertIn("见[1]", reading)
        self.assertIn("[2]", reading)
        self.assertIn("阅读型参考文献", reading)
        self.assertIn("[3] 赵某", reading.split("阅读型参考文献")[1])
        self.assertNotIn("[3]", reading.split("阅读型参考文献")[0])

        missing_date = (FIXTURES / "18-preprint-access-date-missing.zh.md").read_text(encoding="utf-8")
        complete = (FIXTURES / "19-preprint-date-and-doi.zh.md").read_text(encoding="utf-8")
        self.assertIn("[PP/OL]", complete)
        self.assertIn("https://doi.org/10.48550/arXiv.1112.6136", complete)
        self.assertNotIn("DOI:", complete)
        self.assertIn("(2012-03-08)[2026-11-11]", complete)
        self.assertEqual(complete.replace("[2026-11-11]", ""), missing_date)



if __name__ == "__main__":
    unittest.main()
