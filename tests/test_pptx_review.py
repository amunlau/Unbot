"""PPT 原页保存、页级批注、精确引文与可移植退化路径。"""

import hashlib
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

from lxml import etree
from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn
from pptx.util import Inches


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/review_pptx.py"
NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}


def deck(path):
    prs = Presentation()
    result = prs.slides.add_slide(prs.slide_layouts[6])
    result._element.set("show", "0")
    group = result.shapes.add_group_shape()
    group.shapes.add_textbox(0, 0, Inches(4), Inches(1)).text = "重复，重复。"
    table = result.shapes.add_table(2, 2, 0, Inches(2), Inches(4), Inches(1)).table
    table.cell(1, 1).text = "8 ms"
    pic = Image.new("RGB", (300, 90), "white")
    ImageDraw.Draw(pic).text((30, 25), "ALL LOADS", fill="black")
    picture = BytesIO()
    pic.save(picture, format="PNG")
    picture.seek(0)
    result.shapes.add_picture(picture, Inches(0.5), Inches(4), Inches(2.5))
    data = CategoryChartData()
    data.categories = ["A", "B"]
    data.add_series("Delay", [8, 10])
    result.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(5), Inches(1),
                            Inches(4.5), Inches(4), data)
    result.notes_slide.notes_text_frame.text = "the result was conclusive"
    title = prs.slides.add_slide(prs.slide_layouts[0])
    title.shapes.title.text = "试验范围"
    ids = prs.slides._sldIdLst
    ids.insert(0, ids[-1])  # Visible order differs from physical part numbering.
    prs.save(path)


class PPTReview(unittest.TestCase):
    def setUp(self):
        space = tempfile.TemporaryDirectory()
        self.addCleanup(space.cleanup)
        self.folder = Path(space.name)
        self.src = self.folder / "slide.pptx"
        self.manifest = self.folder / "findings.json"
        deck(self.src)
        self.data = json.loads(self.cli("inspect", self.src).stdout)
        self.page = self.data["slides"][1]

    def cli(self, *args, success=True):
        result = subprocess.run([sys.executable, "-B", "-X", "utf8", str(SCRIPT), *map(str, args)],
                                encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return result

    def finding(self, text, quote):
        p = next(item for item in self.page["paragraphs"] if item["text"] == text)
        return {"paragraph": p["id"], "quote": quote, "comment": "核对范围 <x>。"}

    def save(self, items, digest=None):
        content = {"source_sha256": digest or self.data["source_sha256"], "findings": items}
        self.manifest.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")

    def test_slide_order_group_table_notes_and_unchanged_objects(self):
        self.assertEqual(self.data["slides"][0]["title"], "试验范围")
        self.assertEqual(self.page["page"], 2)
        self.assertTrue(self.page["hidden"])
        items = [dict(self.finding("重复，重复。", "重复"), start=3), self.finding("8 ms", "8 ms"),
                 self.finding("the result was conclusive", "conclusive")]
        self.save(items)
        reviewed = self.folder / "review.pptx"
        self.cli("annotate", self.src, self.manifest, reviewed)
        with ZipFile(reviewed) as dst, ZipFile(self.src) as original:
            for name in original.namelist():
                if name != "[Content_Types].xml" and not name.endswith(".rels"):
                    self.assertEqual(original.read(name), dst.read(name), name)
            actual = etree.fromstring(dst.read("ppt/comments/comment1.xml")).xpath(".//p:text/text()", namespaces=NS)
            self.assertEqual(len(actual), 3)
            self.assertIn("第 4 字起", actual[0])
            self.assertIn("第 2 行第 2 列", actual[1])
            self.assertIn("演讲备注", actual[2])
        checked = json.loads(self.cli("inspect", reviewed).stdout)
        self.assertEqual(self.data["slides"], checked["slides"])
        self.assertTrue(checked["write_blockers"])
        self.save(items, checked["source_sha256"])
        self.cli("annotate", reviewed, self.manifest, self.folder / "mix.pptx", success=False)
        html = self.folder / "notes.html"
        self.cli("annotate", reviewed, self.manifest, html)
        self.assertIn("第 2 页", html.read_text(encoding="utf-8"))
        self.assertIn("&lt;x&gt;", html.read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(self.src.read_bytes()).hexdigest(), self.data["source_sha256"])

    def test_ambiguous_stale_empty_and_no_overwrite(self):
        item = self.finding("重复，重复。", "重复")
        out = self.folder / "review.pptx"
        self.save([item])
        self.cli("annotate", self.src, self.manifest, out, success=False)
        self.save([dict(item, start=0)], "stale")
        self.cli("annotate", self.src, self.manifest, out, success=False)
        self.assertFalse(out.exists())
        self.save([])
        self.cli("annotate", self.src, self.manifest, out)
        self.cli("annotate", self.src, self.manifest, out, success=False)
        self.assertEqual(self.src.read_bytes(), out.read_bytes())

    def test_hidden_title_is_identified_on_a_visible_slide(self):
        prs = Presentation(self.src)
        slide = prs.slides[0]
        title = slide.shapes.title
        title._element.find("./" + qn("p:nvSpPr") + "/" + qn("p:cNvPr")).set("hidden", "1")
        textbox = slide.shapes.add_textbox(0, 0, Inches(4), Inches(1))
        textbox.text = "屏幕上的结论"
        source = self.folder / "hidden-title.pptx"
        prs.save(source)
        data = json.loads(self.cli("inspect", source).stdout)
        page = data["slides"][0]
        self.assertFalse(page["hidden"])
        self.assertTrue(page["title_hidden"])
        self.assertEqual(page["title"], "试验范围")
        p = next(item for item in page["paragraphs"] if item["text"] == textbox.text)
        self.save([{"paragraph": p["id"], "quote": p["text"], "comment": "请注明试验条件。"}],
                  data["source_sha256"])
        out = self.folder / "notes.html"
        self.cli("annotate", source, self.manifest, out)
        self.assertIn("第 1 页　试验范围〔隐藏页题〕</h2>", out.read_text(encoding="utf-8"))

    def test_off_slide_title_and_partially_visible_title(self):
        prs = Presentation()
        for where in ("right", "top", "partly visible"):
            slide = prs.slides.add_slide(prs.slide_layouts[5])
            title = slide.shapes.title
            title.text = where
            if where == "right":
                title.left = prs.slide_width + Inches(1)
            else:
                title.height = Inches(1)
                title.top = -Inches(1) if where == "top" else -Inches(0.5)
            slide.shapes.add_textbox(Inches(1), Inches(2), Inches(4), Inches(1)).text = "试验结果"
        file = self.folder / "accessibility-titles.pptx"
        prs.save(file)
        data = json.loads(self.cli("inspect", file).stdout)
        self.assertEqual([s["title_off_slide"] for s in data["slides"]], [True, True, False])
        first = data["slides"][0]
        self.assertFalse(first["title_hidden"])
        self.assertIn("页题框在画面外", first["paragraphs"][0]["location"])
        self.save([{"paragraph": first["paragraphs"][1]["id"], "quote": "试验结果", "comment": "补充工况。"}],
                  data["source_sha256"])
        html = self.folder / "title.html"
        self.cli("annotate", file, self.manifest, html)
        self.assertIn("right〔页题框在画面外〕</h2>", html.read_text(encoding="utf-8"))

    def test_manual_visual_quotes_and_regions(self):
        picture, chart = self.page["visual_objects"]
        items = [{"object": picture["id"], "quote": "ALL LOADS", "comment": "检查图中适用范围。"},
                 {"object": chart["id"], "region": "右图纵轴", "comment": "刻度缺少延迟单位。"}]
        for bad in (dict(items[0], region="未知"), dict(items[0], object="S998/1"), dict(items[0], start=0)):
            self.save([bad])
            self.cli("annotate", self.src, self.manifest, self.folder / "bad.html", success=False)
        self.save(items)
        ppt = self.folder / "visual.pptx"
        self.cli("annotate", self.src, self.manifest, ppt)
        with ZipFile(ppt) as output:
            root = etree.fromstring(output.read("ppt/comments/comment1.xml"))
            texts = root.xpath(".//p:text/text()", namespaces=NS)
            self.assertTrue(all("人工目视定位" in t for t in texts))
            self.assertIn("图内引文　ALL LOADS", texts[0])
            self.assertIn("图内区域　右图纵轴", texts[1])
            self.assertEqual(len(set(root.xpath(".//p:pos/@y", namespaces=NS))), 2)
        html = self.folder / "visual.html"
        self.cli("annotate", self.src, self.manifest, html)
        content = html.read_text(encoding="utf-8")
        self.assertIn(self.data["source_sha256"], content)
        self.assertIn("图内区域　右图纵轴", content)

    def test_classified_text_and_visual_notes_in_native_and_html_outputs(self):
        self.assertEqual(self.data["finding_schema"], 2)
        chart = self.page["visual_objects"][1]
        items = [
            dict(self.finding("重复，重复。", "重复"), start=3, category="style", issue="空泛复述",
                 comment="后半句没有补充结果。"),
            {"object": chart["id"], "region": "柱状图纵轴", "category": "format", "issue": "刻度标签重叠",
             "comment": "请加宽绘图区，保留完整刻度。"},
        ]
        notes = dict(self.data, findings=items)
        self.manifest.write_text(json.dumps(notes), encoding="utf-8")
        native = self.folder / "classified.pptx"
        self.cli("annotate", self.src, self.manifest, native)
        with ZipFile(native) as archive:
            actual = etree.fromstring(archive.read("ppt/comments/comment1.xml")).xpath(".//p:text/text()", namespaces=NS)
        self.assertEqual(len(actual), 2)
        self.assertTrue(actual[0].startswith("【AI味与文风｜空泛复述】"))
        self.assertIn("第 4 字起", actual[0])
        self.assertIn("后半句没有补充结果。", actual[0])
        self.assertTrue(actual[1].startswith("【格式与排版｜刻度标签重叠】"))
        self.assertIn("柱状图纵轴", actual[1])
        self.assertIn("请加宽绘图区", actual[1])
        html = self.folder / "classified.html"
        self.cli("annotate", self.src, self.manifest, html)
        doc = etree.HTML(html.read_text(encoding="utf-8"))
        self.assertEqual(["".join(li.itertext()) for li in doc.findall(".//li")], actual)
        # A later invalid visual finding must not publish an earlier valid note.
        notes["findings"][1].pop("issue")
        self.manifest.write_text(json.dumps(notes), encoding="utf-8")
        incomplete = self.folder / "incomplete.pptx"
        self.cli("annotate", self.src, self.manifest, incomplete, success=False)
        self.assertFalse(incomplete.exists())

    def test_visible_table_cells_native_diagram_and_duplicates(self):
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        tbl = slide.shapes.add_table(2, 2, 0, 0, Inches(4), Inches(1)).table
        tbl.cell(0, 0).merge(tbl.cell(1, 1))
        tbl.cell(0, 0).text = "可见表头"
        for r, c in ((0, 1), (1, 0), (1, 1)):
            tbl.cell(r, c).text = "合并后隐藏的旧值"
        slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, 0, Inches(2), Inches(1), Inches(1))
        slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, 0, Inches(3), Inches(2), Inches(3))
        file = self.folder / "diagram.pptx"
        prs.save(file)
        data = json.loads(self.cli("inspect", file).stdout)
        pg = data["slides"][0]
        self.assertEqual([p["text"] for p in pg["paragraphs"]], ["可见表头"])
        self.assertEqual([v["kind"] for v in pg["visual_objects"]], ["绘图形状", "连接线"])
        finding = {"object": pg["visual_objects"][1]["id"], "region": "右侧箭头", "comment": "请说明方向。"}
        self.save([finding, finding], data["source_sha256"])
        output = self.folder / "review.pptx"
        self.cli("annotate", file, self.manifest, output, success=False)
        self.assertFalse(output.exists())
        self.save([finding], data["source_sha256"])
        self.cli("annotate", file, self.manifest, output)
        self.assertEqual(json.loads(self.cli("inspect", output).stdout)["slides"], data["slides"])

    def test_custom_and_partial_slide_shows(self):
        prs = Presentation(self.src)
        slide_ids = prs.slides._sldIdLst
        shows = etree.Element(qn("p:custShowLst"))
        prs.part._element.find(qn("p:notesSz")).addnext(shows)
        show = etree.SubElement(shows, qn("p:custShow"), name="反序", id="7")
        entries = etree.SubElement(show, qn("p:sldLst"))
        for sid in reversed(list(slide_ids)):
            etree.SubElement(entries, qn("p:sld"), {qn("r:id"): sid.get(qn("r:id"))})
        props = prs.part.part_related_by(RT.PRES_PROPS)
        xml = etree.fromstring(props.blob)
        settings = etree.Element(qn("p:showPr"))
        xml.insert(0, settings)
        custom = etree.SubElement(settings, qn("p:custShow"), id="7")
        file = self.folder / "selected.pptx"
        props._blob = etree.tostring(xml)
        prs.save(file)
        data = json.loads(self.cli("inspect", file).stdout)
        self.assertEqual(data["slide_show"]["selection"], {"type": "custom", "id": "7"})
        self.assertEqual(data["slide_show"]["custom_shows"], [{"id": "7", "name": "反序", "pages": [2, 1]}])
        settings.remove(custom)
        etree.SubElement(settings, qn("p:sldRg"), st="1", end="1")
        props._blob = etree.tostring(xml)
        prs.save(file)
        data = json.loads(self.cli("inspect", file).stdout)
        self.assertEqual(data["slide_show"]["selection"], {"type": "range", "start": 1, "end": 1})
        self.assertEqual(len(data["slides"]), 2)


if __name__ == "__main__":
    unittest.main()
