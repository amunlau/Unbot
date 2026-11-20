"""Check recorded behavior artifacts across Git newline normalization.

These checks protect historical evidence; they do not evaluate writing quality
or require old execution snapshots to match the current skill instructions.
"""

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent / "behavior" / "paragraph-coherence"
GROUPS = {
    "scope-transitions": "runtime-snapshots.json",
    "section-entries": "runtime-snapshot.json",
    "argument-units": "runtime-snapshot.json",
}


def load_manifest(group):
    return json.loads((ROOT / group / GROUPS[group]).read_text(encoding="utf-8"))


class BehaviorArchiveTests(unittest.TestCase):
    def test_archived_artifacts_match_lf_digests_and_coverage(self):
        for group in GROUPS:
            with self.subTest(group=group):
                directory = ROOT / group
                manifest = load_manifest(group)
                self.assertEqual(manifest["archive_hash_method"], "sha256-crlf-to-lf-v1")
                expected = {"cases.json"}
                for folder in ("results", "reviews"):
                    expected.update(
                        path.relative_to(directory).as_posix()
                        for path in (directory / folder).rglob("*")
                        if path.is_file()
                    )
                digests = manifest["archive_lf_sha256"]
                self.assertEqual(set(digests), expected)
                for relative_path, digest in digests.items():
                    with self.subTest(group=group, artifact=relative_path):
                        data = (directory / relative_path).read_bytes().replace(b"\r\n", b"\n")
                        self.assertEqual(hashlib.sha256(data).hexdigest(), digest)

    def test_frozen_rule_collection_hashes_are_self_consistent(self):
        for group in GROUPS:
            manifest = load_manifest(group)
            snapshots = {"snapshot": manifest} if "files" in manifest else {
                name: manifest[name] for name in ("baseline", "candidate", "final")
            }
            for name, snapshot in snapshots.items():
                with self.subTest(group=group, snapshot=name):
                    files = snapshot["files"]
                    self.assertEqual(len(files), 18)
                    self.assertIn("SKILL.md", files)
                    for relative_path, digest in files.items():
                        self.assertRegex(digest, r"^[0-9a-f]{64}$")
                        self.assertNotIn("\\", relative_path)
                    payload = "\n".join(
                        relative_path + "\0" + digest
                        for relative_path, digest in sorted(files.items())
                    ).encode("utf-8")
                    self.assertEqual(hashlib.sha256(payload).hexdigest(), snapshot["sha256"])

    def test_original_artifact_records_have_archive_entries(self):
        for group in GROUPS:
            manifest = load_manifest(group)
            originals = {}
            for field in ("results", "result_sha256", "review_sha256"):
                originals.update(manifest.get(field, {}))
            if "case_file_sha256" in manifest:
                originals["cases.json"] = manifest["case_file_sha256"]
            with self.subTest(group=group):
                self.assertTrue(originals)
                self.assertEqual(set(originals) - {"cases.json"}, set(manifest["archive_lf_sha256"]) - {"cases.json"})
                for relative_path, digest in originals.items():
                    self.assertIn(relative_path, manifest["archive_lf_sha256"])
                    self.assertRegex(digest, r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
