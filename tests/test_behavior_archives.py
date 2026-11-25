"""Check saved executions without comparing them to evolving runtime rules."""

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent / "behavior"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def lf_digest(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


class BehaviorArchiveTests(unittest.TestCase):
    def archives(self):
        directories = [ROOT / "current-validation-2026-11-25"]
        for directory in directories:
            self.assertTrue(directory.is_dir(), "Current behavior archive missing")
        return directories

    def test_artifact_coverage_and_content(self):
        for directory in self.archives():
            with self.subTest(archive=directory.name):
                manifest = read_json(directory / "archive-manifest.json")
                self.assertEqual(manifest["hash_method"], "sha256-crlf-to-lf-v1")
                digests = manifest["artifacts"]
                expected = {
                    path.relative_to(directory).as_posix()
                    for path in directory.rglob("*") if path.is_file()
                } - {"README.md", "checks.json", "archive-manifest.json"}
                self.assertEqual(set(digests), expected)
                self.assertLessEqual(
                    {"input.md", "output.md", "loaded.json", "runtime-snapshot.json"},
                    expected,
                )
                for name, digest in digests.items():
                    with self.subTest(artifact=name):
                        self.assertRegex(digest, r"^[0-9a-f]{64}$")
                        self.assertEqual(lf_digest(directory / name), digest)

    def test_loaded_rules_and_input_match_frozen_records(self):
        for directory in self.archives():
            with self.subTest(archive=directory.name):
                loaded = read_json(directory / "loaded.json")
                snapshot = read_json(directory / "runtime-snapshot.json")
                paths = [item["path"] for item in loaded["files"]]
                self.assertIn("SKILL.md", paths)
                self.assertEqual(len(paths), len(set(paths)))
                self.assertEqual(loaded["input"]["sha256_lf"], lf_digest(directory / "input.md"))
                for item in loaded["files"]:
                    self.assertEqual(item["sha256_lf"], snapshot["files"][item["path"]])

    def test_rule_collection_fingerprint(self):
        for directory in self.archives():
            with self.subTest(archive=directory.name):
                snapshot = read_json(directory / "runtime-snapshot.json")
                self.assertEqual(snapshot["hash_method"], "sha256-crlf-to-lf-v1")
                files = snapshot["files"]
                self.assertIn("SKILL.md", files)
                for name, digest in files.items():
                    self.assertRegex(name, r"^(?:SKILL\.md|references/[^/]+\.md)$")
                    self.assertRegex(digest, r"^[0-9a-f]{64}$")
                payload = "\n".join(name + "\0" + digest for name, digest in sorted(files.items()))
                self.assertEqual(hashlib.sha256(payload.encode("utf-8")).hexdigest(), snapshot["sha256"])


class RestoredBehaviorArchiveTests(unittest.TestCase):
    """Keep publication integrity separate from historical execution receipts."""

    def setUp(self):
        self.manifest = read_json(ROOT / "restoration-manifest.json")
        self.files = self.manifest["files"]

    def archive_path(self, name):
        self.assertIsInstance(name, str)
        self.assertNotIn("\\", name)
        path = Path(name)
        self.assertFalse(path.is_absolute())
        self.assertNotIn("..", path.parts)
        self.assertEqual(path.as_posix(), name)
        resolved = (ROOT / path).resolve()
        self.assertIn(ROOT.resolve(), resolved.parents)
        return resolved

    def recorded_json(self, name):
        self.assertIn(name, self.files)
        return read_json(self.archive_path(name))

    def at_pointer(self, value, pointer):
        self.assertIsInstance(pointer, list)
        for key in pointer:
            value = value[key]
        return value

    def assert_digest(self, value):
        self.assertIsInstance(value, str)
        self.assertRegex(value, r"^[0-9a-f]{64}$")

    def test_restored_file_coverage_and_publication_hashes(self):
        self.assertEqual(self.manifest["schema_version"], 1)
        self.assertEqual(self.manifest["hash_method"], "sha256-crlf-to-lf-v1")
        expected = set()
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if relative.parts[0] == "current-validation-2026-11-25":
                continue
            if len(relative.parts) == 1 and (
                relative.name == "README.md"
                or (relative.name.startswith("restoration") and relative.suffix == ".json")
            ):
                continue
            expected.add(relative.as_posix())
        self.assertTrue(expected)
        self.assertEqual(set(self.files), expected)
        for name, record in self.files.items():
            with self.subTest(artifact=name):
                for field in ("sha256_lf", "original_sha256_bytes",
                              "original_sha256_lf", "original_sha256_crlf"):
                    self.assert_digest(record[field])
                self.assertEqual(lf_digest(self.archive_path(name)), record["sha256_lf"])

    def test_metadata_edits_preserve_original_task_payloads(self):
        edits = self.manifest["metadata_edits"]
        self.assertEqual(len(edits), len(set(edits)))
        changed = {
            name for name, record in self.files.items()
            if record["sha256_lf"] != record["original_sha256_lf"]
        }
        self.assertEqual(set(edits), changed)
        for name, record in self.files.items():
            with self.subTest(artifact=name):
                path = Path(name)
                protected = (
                    path.name in {
                        "input.md", "cases.json", "output.md", "result.md", "final-result.md",
                        "workflow-boundaries-2026-11-18.md",
                    }
                    or path.name.endswith(("-input.md", "-output.md", "rubric.md"))
                    or ("results" in path.parts and path.suffix == ".md")
                )
                if protected:
                    self.assertNotIn(name, edits, "Original task payload must remain unchanged")
                if name not in edits:
                    data = self.archive_path(name).read_bytes().replace(b"\r\n", b"\n")
                    self.assertEqual(hashlib.sha256(data).hexdigest(), record["original_sha256_lf"])
                    self.assertEqual(
                        hashlib.sha256(data.replace(b"\n", b"\r\n")).hexdigest(),
                        record["original_sha256_crlf"],
                    )

    def test_original_receipts_and_published_rule_collections(self):
        receipts = self.manifest["original_receipts"]
        self.assertTrue(receipts)
        for spec in receipts:
            with self.subTest(receipt=spec["record"], field=spec["field"]):
                value = self.recorded_json(spec["record"])[spec["field"]]
                values = {spec["artifact"]: value} if "artifact" in spec else value
                self.assertIsInstance(values, dict)
                self.assertTrue(values)
                self.assertIn(spec["method"], {"lf", "bytes"})
                for relative, digest in values.items():
                    name = (Path(spec["base"]) / relative).as_posix()
                    self.archive_path(name)
                    record = self.files[name]
                    self.assert_digest(digest)
                    if spec["method"] == "lf":
                        self.assertEqual(digest, record["original_sha256_lf"], name)
                    else:
                        self.assertIn(digest, {
                            record["original_sha256_bytes"],
                            record["original_sha256_lf"],
                            record["original_sha256_crlf"],
                        }, name)
        snapshots = self.manifest["rule_snapshots"]
        self.assertTrue(snapshots)
        identities = [(spec["record"], tuple(spec["pointer"])) for spec in snapshots]
        self.assertEqual(len(identities), len(set(identities)))
        for spec in snapshots:
            with self.subTest(snapshot=spec["record"], pointer=spec["pointer"]):
                document = self.recorded_json(spec["record"])
                files = self.at_pointer(document, spec["pointer"])
                self.assertIn("SKILL.md", files)
                for name, digest in files.items():
                    self.assertRegex(name, r"^(?:SKILL\.md|README\.md|references/[^/]+\.md)$")
                    if isinstance(digest, dict):
                        self.assert_digest(digest["sha256_bytes"])
                        self.assert_digest(digest["sha256_lf"])
                    else:
                        self.assert_digest(digest)
                if "collection_pointer" in spec:
                    collection = self.at_pointer(document, spec["collection_pointer"])
                    payload = "\n".join(name + "\0" + digest for name, digest in sorted(files.items()))
                    self.assertEqual(
                        hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                        collection["published_collection_sha256"],
                    )
                    # The original aggregate may cover a larger historical
                    # collection; do not compare it with the published subset.
                    if "sha256" in collection:
                        self.assert_digest(collection["sha256"])

    def test_execution_loading_records_match_declared_versions(self):
        executions = self.manifest["executions"]
        records = [spec["record"] for spec in executions]
        self.assertEqual(len(records), len(set(records)))
        expected = {
            name for name in self.files
            if Path(name).name == "loaded.json" or Path(name).name.endswith("-loaded.json")
        }
        self.assertTrue(expected)
        self.assertEqual(set(records), expected)
        versions = {
            (spec["record"], tuple(spec["pointer"]))
            for spec in self.manifest["rule_snapshots"]
        }
        for spec in executions:
            with self.subTest(execution=spec["record"]):
                self.assertIn((spec["snapshot"], tuple(spec["snapshot_pointer"])), versions)
                snapshot = self.at_pointer(self.recorded_json(spec["snapshot"]), spec["snapshot_pointer"])
                loaded = self.recorded_json(spec["record"])
                self.assertIn(spec["output"], self.files)
                self.assertTrue(self.archive_path(spec["output"]).is_file())
                self.assertIn(spec["format"], {"paths", "digests"})
                if spec["format"] == "paths":
                    self.assertIsInstance(loaded, list)
                    paths = loaded
                    # A historical path list contains no content digests.
                    # Validate membership without inventing an attestation.
                    for path in paths:
                        self.assertIsInstance(path, str)
                else:
                    entries = loaded[spec["list_key"]]
                    prefix = spec.get("path_prefix", "")
                    paths = []
                    for item in entries:
                        self.assertTrue(item["path"].startswith(prefix))
                        path = item["path"][len(prefix):]
                        paths.append(path)
                        digest = item[spec["digest_key"]]
                        self.assert_digest(digest)
                        expected_digest = snapshot[path]
                        if "snapshot_digest_key" in spec:
                            expected_digest = expected_digest[spec["snapshot_digest_key"]]
                        self.assertEqual(digest, expected_digest, path)
                    if "input" in loaded:
                        self.assertIn("input", spec)
                    if "input" in spec:
                        self.assertIn(spec["input"], self.files)
                        self.assertEqual(
                            loaded["input"][spec["input_digest_key"]],
                            lf_digest(self.archive_path(spec["input"])),
                        )
                self.assertIn("SKILL.md", paths)
                self.assertEqual(len(paths), len(set(paths)))
                self.assertLessEqual(set(paths), set(snapshot))

    def test_task_sets_match_recorded_outputs(self):
        task_sets = self.manifest["task_sets"]
        self.assertTrue(task_sets)
        output_directories = [spec["outputs"] for spec in task_sets]
        self.assertEqual(len(output_directories), len(set(output_directories)))
        for spec in task_sets:
            with self.subTest(tasks=spec["record"], outputs=spec["outputs"]):
                entries = self.recorded_json(spec["record"])[spec["entries_key"]]
                ids = [entry["id"] for entry in entries]
                self.assertTrue(ids)
                self.assertEqual(len(ids), len(set(ids)))
                expected = set(ids)
                if "origins" in spec:
                    self.assertTrue(spec["origins"])
                    expected &= {
                        entry["id"] for entry in entries if entry["origin"] in spec["origins"]
                    }
                if "ids" in spec:
                    self.assertEqual(len(spec["ids"]), len(set(spec["ids"])))
                    self.assertLessEqual(set(spec["ids"]), expected)
                    expected &= set(spec["ids"])
                self.assertTrue(expected)
                directory = self.archive_path(spec["outputs"])
                actual = {path.stem for path in directory.glob("*.md")}
                self.assertEqual(actual, expected)
                for task_id in expected:
                    self.assertIn((Path(spec["outputs"]) / (task_id + ".md")).as_posix(), self.files)


if __name__ == "__main__":
    unittest.main()
