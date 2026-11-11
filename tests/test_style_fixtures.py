"""回归：文风夹具存在，金标准标签仍符合 schema 2。

本文件不评测编辑判断。样稿应否标注，须由维护者按 references/style-review.md
做人工或离线检查；测试通过只表示夹具和标签写法仍在。测试全部通过，
不证明这些规则已经能稳定检出错误，也不证明起草或润色已经不会引入同类表达。
heldout 记录在包内，不等于盲法或检出率已经成立。
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "style"
CLASSIFICATION = ROOT / "scripts" / "review_classification.py"

REQUIRED_CASE_IDS = (
    "01-empty-evaluation",
    "01b-acceptance-claim",
    "02-keep-technical-term",
    "03-formulaic-transition",
    "04-necessary-background",
    "05-empty-emphasis",
    "06-unwarranted-parallelism",
    "07-real-enumeration",
    "08-unsourced-generalization",
    "08b-field-record-missing",
    "09-supported-field-record",
    "10-methods-passive",
    "11-approval-role",
)

MUST_FLAG = {
    "01-empty-evaluation",
    "01b-acceptance-claim",
    "03-formulaic-transition",
    "05-empty-emphasis",
    "06-unwarranted-parallelism",
    "08-unsourced-generalization",
    "08b-field-record-missing",
    "11-approval-role",
}

MUST_NOT_FLAG = {
    "02-keep-technical-term",
    "04-necessary-background",
    "07-real-enumeration",
    "09-supported-field-record",
    "10-methods-passive",
}

GENERATION_FILES = (
    "generation/materials.md",
    "generation/must-not-produce.md",
    "generation/acceptable-draft.md",
    "generation/README.md",
)


def load_classification():
    spec = importlib.util.spec_from_file_location("review_classification", CLASSIFICATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StyleFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_classification()
        cls.gold = json.loads((FIXTURES / "gold.json").read_text(encoding="utf-8"))
        cls.cases = {item["id"]: item for item in cls.gold["cases"]}

    def test_fixture_catalog_and_required_cases_exist(self):
        self.assertTrue((FIXTURES / "README.md").is_file())
        self.assertTrue((FIXTURES / "gold.json").is_file())
        self.assertEqual(set(REQUIRED_CASE_IDS), set(self.cases))
        self.assertTrue(MUST_FLAG.isdisjoint(MUST_NOT_FLAG))
        readme = (FIXTURES / "README.md").read_text(encoding="utf-8")
        self.assertIn("不评测应否标注", readme)
        self.assertIn("不证明规则已能稳定检出文风问题", readme)
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
                    text = path.read_text(encoding="utf-8").strip()
                    self.assertGreater(len(text), 20, name)

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
        self.assertIn("也不证明起草或润色已经不会引入同类表达", description)
        self.assertIn("不等于盲法或检出率已经成立", description)

    def test_markdown_cases_retain_the_documented_cues(self):
        zh01 = (FIXTURES / "01-empty-evaluation.zh.md").read_text(encoding="utf-8")
        en01 = (FIXTURES / "01-empty-evaluation.en.md").read_text(encoding="utf-8")
        self.assertIn("15.2 ms", zh01)
        self.assertIn("重要应用价值", zh01)
        self.assertIn("尚未测试", zh01)
        self.assertIn("15.2 ms", en01)
        self.assertIn("significant practical value", en01)

        keep = (FIXTURES / "02-keep-technical-term.zh.md").read_text(encoding="utf-8")
        self.assertIn("闭环控制器根据压力反馈调节阀位", keep)
        self.assertIn("p = 0.013", keep)

        padded = (FIXTURES / "03-formulaic-transition.zh.md").read_text(encoding="utf-8")
        self.assertIn("随着信息技术的不断发展", padded)
        self.assertIn("不仅仅是算法问题", padded)
        self.assertIn("命中率", padded)

        background = (FIXTURES / "04-necessary-background.zh.md").read_text(encoding="utf-8")
        self.assertIn("2025 年 7 月 1 日", background)
        self.assertIn("未收录该日之前采集的样本", background)

        emphasis = (FIXTURES / "05-empty-emphasis.zh.md").read_text(encoding="utf-8")
        self.assertIn("值得特别指出的是", emphasis)
        self.assertIn("15.2 ms", emphasis)

        parallel = (FIXTURES / "06-unwarranted-parallelism.zh.md").read_text(encoding="utf-8")
        self.assertIn("低 18%", parallel)
        self.assertIn("均未进行并发测试", parallel)
        self.assertIn("值得肯定、值得重视、值得关注", parallel)

        enum = (FIXTURES / "07-real-enumeration.zh.md").read_text(encoding="utf-8")
        self.assertIn("退出码为 0", enum)
        self.assertIn("禁止重启", enum)

        unsourced = (FIXTURES / "08-unsourced-generalization.zh.md").read_text(encoding="utf-8")
        self.assertIn("大量研究证明", unsourced)
        self.assertIn("多个现场反复验证", unsourced)
        self.assertIn("2.7 kW", unsourced)

        supported = (FIXTURES / "09-supported-field-record.zh.md").read_text(encoding="utf-8")
        self.assertIn("甲、乙两个现场", supported)
        self.assertIn("我们在两个现场", supported)

    def test_evaluation_and_acceptance_claim_share_the_measured_context(self):
        evaluation = self.cases["01-empty-evaluation"]
        acceptance = self.cases["01b-acceptance-claim"]
        self.assertEqual(evaluation["category"], "style")
        self.assertEqual(acceptance["category"], "evidence")
        for language in ("zh", "en"):
            with self.subTest(language=language):
                surrounding_text = []
                for case in (evaluation, acceptance):
                    sample = (FIXTURES / f"{case['id']}.{language}.md").read_text(encoding="utf-8")
                    quote = case[f"quote_{language}"]
                    self.assertEqual(sample.count(quote), 1)
                    surrounding_text.append(sample.split(quote))
                self.assertEqual(*surrounding_text)

    def test_missing_citations_and_field_records_have_separate_evidence_anchors(self):
        literature = self.cases["08-unsourced-generalization"]
        fieldwork = self.cases["08b-field-record-missing"]
        self.assertEqual(literature["files"], fieldwork["files"])
        for case in (literature, fieldwork):
            self.assertEqual(case["category"], "evidence")
            self.assertNotIn("虚构", case["gold_note_zh"])
        for language in ("zh", "en"):
            sample = (FIXTURES / f"08-unsourced-generalization.{language}.md").read_text(encoding="utf-8")
            first = literature[f"quote_{language}"]
            second = fieldwork[f"quote_{language}"]
            self.assertEqual(sample.count(first), 1)
            self.assertEqual(sample.count(second), 1)
            self.assertLessEqual(sample.index(first) + len(first), sample.index(second))

    def test_english_passives_distinguish_method_from_approval_authority(self):
        method = self.cases["10-methods-passive"]
        approval = self.cases["11-approval-role"]
        methods_text = (FIXTURES / method["files"][0]).read_text(encoding="utf-8")
        procedure = (FIXTURES / approval["files"][0]).read_text(encoding="utf-8")
        self.assertIn("output voltage was measured after a 30 s settling period", methods_text)
        self.assertFalse(method["must_flag"])
        self.assertIn("test engineer and the shift supervisor", procedure)
        self.assertEqual(procedure.count(approval["quote_en"]), 1)
        self.assertTrue(approval["must_flag"])
        self.assertEqual(approval["category"], "technical")
        self.assertIn("Approver", approval["issue_en"])

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
        self.assertIn("峰值内存", materials)
        self.assertIn("低 18%", materials)
        self.assertIn("未测", materials)
        self.assertIn("效率、体验和价值", bad)
        self.assertIn("多个大型集群", bad)
        self.assertIn("峰值内存比方案 A 低 18%", good)
        self.assertIn("均未进行并发测试", good)
        self.assertIn("不证明起草或润色已经不会引入", readme)

    def test_heldout_record_exists_and_states_its_limits(self):
        gold = self.gold
        self.assertIn("heldout", gold)
        note = gold["heldout"]["note"]
        self.assertIn("非盲法", note)
        self.assertIn("不能支撑检出率", note)
        sample = (FIXTURES / gold["heldout"]["sample"]).read_text(encoding="utf-8")
        record = (FIXTURES / gold["heldout"]["record"]).read_text(encoding="utf-8")
        readme = (FIXTURES / "heldout/README.md").read_text(encoding="utf-8")
        self.assertIn("4.8 mm/s", sample)
        self.assertIn("4.5 mm/s", sample)
        self.assertIn("值得强调的是", sample)
        self.assertIn("效率、可靠性和智慧运维", sample)
        self.assertIn("坚实基础", sample)
        self.assertNotIn("15.2 ms", sample)
        self.assertNotIn("窗口 W", sample)
        self.assertNotIn("2.7 kW", sample)
        self.assertNotIn("93.4%", sample)
        self.assertIn("非盲法", record)
        self.assertIn("不能支撑检出率", record)
        self.assertIn("由单次试运行外推度汛能力", record)
        self.assertIn("空泛评价", record)
        self.assertIn("无内容的强调", record)
        self.assertIn("按防汛办", record)
        self.assertIn("非盲法", readme)


if __name__ == "__main__":
    unittest.main()
