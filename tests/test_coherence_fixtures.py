"""回归：篇章衔接夹具存在，且金标准标签仍符合 schema 2。

本文件不评测编辑判断。样稿应否标注，须由维护者按 references/coherence-review.md
做人工或离线检查；测试通过只表示夹具和标签写法仍在。测试全部通过，
不证明这些规则已经能稳定检出错误，也不证明起草或润色已经不会引入同类错误。
"""

from __future__ import annotations

import importlib.util
import json
import re
import unittest
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "coherence"
CLASSIFICATION = ROOT / "scripts" / "review_classification.py"

REQUIRED_CASE_IDS = (
    "01-theme-jump-extrapolation",
    "02-juxtaposition-clear-relation",
    "03-misused-therefore",
    "04-abstract-interval-sign",
    "05-figure-body-value",
    "06-dropped-noload-qualifier",
    "07-secondary-as-main-conclusion",
    "08-theme-not-baton-but-clear",
    "09-group-value-swap",
    "10-methods-packaging-aside",
    "11-table-backed-abstract",
)

MUST_FLAG = {
    "01-theme-jump-extrapolation",
    "03-misused-therefore",
    "04-abstract-interval-sign",
    "05-figure-body-value",
    "06-dropped-noload-qualifier",
    "07-secondary-as-main-conclusion",
    "09-group-value-swap",
    "10-methods-packaging-aside",
}

MUST_NOT_FLAG = {
    "02-juxtaposition-clear-relation",
    "08-theme-not-baton-but-clear",
    "11-table-backed-abstract",
}

GENERATION_FILES = (
    "generation/materials-noload.md",
    "generation/must-not-produce.md",
    "generation/acceptable-draft.md",
    "generation/README.md",
)

HELDOUT_FILES = (
    "heldout/sample-line-scan-calibration.md",
    "heldout/retest-2026-11-11.md",
    "heldout/sample-switchgear-pd-inspection.md",
    "heldout/retest-2026-11-11-switchgear.md",
    "heldout/README.md",
)


def load_classification():
    spec = importlib.util.spec_from_file_location("review_classification", CLASSIFICATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CoherenceFixtures(unittest.TestCase):
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
        has_zh = has_en = False
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
                    text = path.read_text(encoding="utf-8").strip()
                    self.assertGreater(len(text), 20, name)
                    if name.endswith(".zh.md"):
                        has_zh = True
                    if name.endswith(".en.md"):
                        has_en = True
        self.assertTrue(has_zh and has_en)

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
        description = __doc__ or ""
        self.assertIn("不评测编辑判断", description)
        self.assertIn("测试通过只表示夹具和标签写法仍在", description)
        self.assertIn("不证明这些规则已经能稳定检出错误", description)
        self.assertIn("也不证明起草或润色已经不会引入同类错误", description)

    def test_table_backed_abstract_has_a_reproducible_rounding_example(self):
        case = self.cases["11-table-backed-abstract"]
        self.assertFalse(case["must_flag"])
        for filename in case["files"]:
            with self.subTest(filename=filename):
                text = (FIXTURES / filename).read_text(encoding="utf-8")
                abstract, results, _, table = text.strip().split("\n\n")
                reported = re.search(r"\b0\.\d+", abstract)
                self.assertIsNotNone(reported)
                cell = table.splitlines()[-1].strip("|").split("|")
                condition, full_value = (part.strip() for part in cell)
                self.assertIn(condition, abstract)
                self.assertIn("表 1" if filename.endswith(".zh.md") else "Table 1", results)
                self.assertNotIn(full_value, results)
                self.assertNotIn(reported.group(), results)
                self.assertGreater(len(full_value.split(".")[1]), 2)
                rounded = Decimal(full_value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                self.assertEqual(reported.group(), str(rounded))

    def test_noload_example_meets_the_same_device_limit_in_both_languages(self):
        for language, metric, maximum, condition, all_conditions in (
            ("zh", "整机端到端时延", "最大端到端时延", "空载", "所有工况"),
            ("en", "device's end-to-end latency", "maximum measured end-to-end latency",
             "no-load", "all operating conditions"),
        ):
            with self.subTest(language=language):
                path = FIXTURES / f"06-dropped-noload-qualifier.{language}.md"
                results, claim = path.read_text(encoding="utf-8").strip().split("\n\n")
                self.assertIn(metric, results)
                self.assertIn(maximum, results)
                self.assertIn(condition, results)
                self.assertIn(all_conditions, claim)
                # The known no-load maximum already satisfies the device limit.
                values = re.findall(r"(\d+(?:\.\d+)?) ms", results)
                self.assertEqual(len(values), 2)
                limit, observed = map(Decimal, values)
                self.assertLessEqual(observed, limit)

    def test_signed_interval_example_uses_the_same_metric_in_both_languages(self):
        for filename, metric, direction in (
            ("04-abstract-interval-sign.zh.md", "垂直形变速率", "抬升为正"),
            ("04-abstract-interval-sign.en.md", "vertical deformation rates", "uplift defined as positive"),
        ):
            with self.subTest(filename=filename):
                abstract, results = (FIXTURES / filename).read_text(encoding="utf-8").strip().split("\n\n")
                self.assertIn(direction, abstract)
                for paragraph, endpoints in ((abstract, ["5", "20"]), (results, ["−20", "−5"])):
                    self.assertIn(metric, paragraph)
                    self.assertIn("mm/a", paragraph)
                    self.assertEqual(re.findall(r"−?\d+", paragraph), endpoints)

    def test_generation_antipatterns_and_heldout_record_exist(self):
        """锁定生成反例与持出复测记录存在；通过不证明防引入或检出率。"""
        gold = self.gold
        self.assertIn("generation", gold)
        self.assertIn("heldout", gold)
        for name in GENERATION_FILES + HELDOUT_FILES:
            path = FIXTURES / name
            with self.subTest(file=name):
                self.assertTrue(path.is_file(), f"缺少 {name}")
                self.assertGreater(len(path.read_text(encoding="utf-8").strip()), 20, name)
        materials = (FIXTURES / gold["generation"]["materials"]).read_text(encoding="utf-8")
        bad = (FIXTURES / gold["generation"]["must_not_produce"]).read_text(encoding="utf-8")
        good = (FIXTURES / gold["generation"]["acceptable_draft"]).read_text(encoding="utf-8")
        self.assertIn("未接负载", materials)
        for required in ("25 °C", "输入功耗", "0.42 W"):
            self.assertIn(required, materials)
            self.assertIn(required, good)
        self.assertIn("0.42 W", bad)
        self.assertIn("全部负载", bad)
        self.assertIn("空载", good)
        self.assertIn("尚未测量", good)
        self.assertNotIn("全部负载", good)
        exercise = (FIXTURES / gold["heldout_exercise"]["record"]).read_text(encoding="utf-8")
        self.assertIn("规则对照演练", exercise)
        self.assertIn("不能再当作独立持出证据", exercise)
        self.assertIn("09", exercise)
        record = (FIXTURES / gold["heldout"]["record"]).read_text(encoding="utf-8")
        sample = (FIXTURES / gold["heldout"]["sample"]).read_text(encoding="utf-8")
        self.assertIn("不是按夹具", record)
        self.assertIn("不是盲法", record)
        self.assertIn("不能支持“持出复测证明了稳定检出”", record)
        # 新样稿不得复用教学夹具原文数字或包装说明
        for banned in ("620 mm", "450 mm", "380 mm", "双瓦楞", "0.18 mm", "0.31 mm", "0.42 W", "800 lux"):
            self.assertNotIn(banned, sample)
        self.assertIn("heldout_exercise", gold)
        readme_root = (FIXTURES / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("应标。应标。", readme_root)
        self.assertNotIn("不应标。不应标。", readme_root)
        # 01 中英指标一致，02 不含空泛评价
        zh01 = (FIXTURES / "01-theme-jump-extrapolation.zh.md").read_text(encoding="utf-8")
        en01 = (FIXTURES / "01-theme-jump-extrapolation.en.md").read_text(encoding="utf-8")
        self.assertIn("20 ms", zh01)
        self.assertIn("20 ms", en01)
        self.assertNotIn("吞吐量", zh01)
        self.assertNotIn("throughput", en01.lower())
        zh02 = (FIXTURES / "02-juxtaposition-clear-relation.zh.md").read_text(encoding="utf-8")
        en02 = (FIXTURES / "02-juxtaposition-clear-relation.en.md").read_text(encoding="utf-8")
        self.assertNotIn("反应良好", zh02)
        self.assertNotIn("普遍表示接受", zh02)
        self.assertNotIn("responded favorably", en02.lower())
        self.assertNotIn("acceptance", en02.lower())
        # 夹具 05 须提供四步对照所需的图题、可读信息和正文引用
        zh05 = (FIXTURES / "05-figure-body-value.zh.md").read_text(encoding="utf-8")
        self.assertIn("图 3 题", zh05)
        self.assertIn("图 3 可读信息", zh05)
        self.assertIn("0.73", zh05)
        self.assertIn("0.72", zh05)
        self.assertIn("至少应标换题", (FIXTURES / "gold.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
