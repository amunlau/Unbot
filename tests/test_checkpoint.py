"""以独立 CLI 进程验证自动接续、原稿校验及被打断的本地事务。"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "checkpoint.py"


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.temp = Path(tmp.name)
        self.workspace = self.temp / "报告 工作区"
        self.workspace.mkdir()
        self.original = self.workspace / "原稿.md"
        self.original.write_bytes("A 组 12 ms。\n".encode())
        self.args = [sys.executable, "-B", "-X", "utf8", str(SCRIPT), "--workspace", str(self.workspace)]

    def run_cli(self, *args, ok=True, env=None):
        command = [*self.args, *map(str, args)]
        result = subprocess.run(command, cwd=self.temp, env=env, capture_output=True,
                                encoding="utf-8", timeout=25)
        if not ok:
            self.assertNotEqual(0, result.returncode, result.stdout)
            return result
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def start(self, task="检查原稿"):
        return self.run_cli("start", "--task", task, "--mode", "review", "--input", self.original.name)

    def state_file(self, name, done, next_step):
        state = {"done": done, "next": next_step}
        path = self.workspace / name
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        return path

    def test_discovery_disambiguation_and_completed_tasks(self):
        self.assertEqual("none", self.run_cli("resume")["status"])
        self.assertEqual([], self.run_cli("list")["tasks"])
        self.assertFalse((self.workspace / ".unbot").exists())
        first = self.start()
        self.assertEqual(0, first["revision"])
        self.assertEqual(first["id"], self.run_cli("resume")["id"])
        second = self.start("审阅英文摘要")
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual("ambiguous", self.run_cli("resume")["status"])
        self.assertEqual(second["id"], self.run_cli("resume", "--task", "审阅英文摘要")["id"])
        final = self.workspace / "审阅结果.md"
        final.write_text("已审全文。", encoding="utf-8")
        self.run_cli("finish", first["id"], "--revision", 0, "--output", "缺失稿.md", ok=False)
        done = self.run_cli("finish", first["id"], "--revision", 0, "--output", final.name)
        self.assertEqual(1, done["revision"])
        self.assertEqual(second["id"], self.run_cli("resume")["id"])
        self.assertEqual({second["id"]}, {r["id"] for r in self.run_cli("list")["tasks"]})
        self.assertEqual({first["id"], second["id"]}, {r["id"] for r in self.run_cli("list", "--all")["tasks"]})
        saved_output = self.run_cli("show", first["id"])["outputs"][0]["name"]
        final.unlink()
        self.run_cli("restore", first["id"], "--to", "完成稿")
        self.assertEqual("已审全文。", (self.workspace / "完成稿" / saved_output).read_text(encoding="utf-8"))

    def test_failed_first_save_does_not_leave_a_broken_workspace(self):
        self.run_cli("start", "--task", "核对缺失附表", "--mode", "review",
                     "--input", "未收到的附表.txt", ok=False)
        self.assertEqual("none", self.run_cli("resume")["status"])
        self.assertEqual([], self.run_cli("list")["tasks"])
        task = self.start()
        self.assertEqual(task["id"], self.run_cli("resume")["id"])

    def test_resume_uses_input_filesystem_casing(self):
        canonical = self.workspace / "Report.md"
        alias = self.workspace / "report.MD"
        canonical.write_text("12 ms", encoding="utf-8")
        settings = ["--task", "核对指标", "--mode", "review", "--input"]
        if os.name == "nt" and alias.exists():
            task = self.run_cli("start", *settings, alias.name)
            self.assertEqual(canonical.name, task["inputs"][0]["path"])
            self.assertEqual(task["id"], self.run_cli("resume", "--input", canonical.name)["id"])
            self.run_cli("start", *settings, canonical.name, ok=False)
            canonical.unlink()
            self.assertEqual("blocked", self.run_cli("resume", "--input", alias.name)["status"])
        else:
            first = self.run_cli("start", *settings, canonical.name)
            self.assertEqual("none", self.run_cli("resume", "--input", alias.name)["status"])
            if not alias.exists():
                alias.write_text("21 ms", encoding="utf-8")
                second = self.run_cli("start", *settings, alias.name)
                self.assertNotEqual(first["id"], second["id"])

    def test_finish_verifies_each_approved_artifact_atomically(self):
        clean = self.workspace / "报告-润色.txt"
        review = self.workspace / "报告-审阅.txt"
        clean.write_text("响应时间为 12 ms。", encoding="utf-8")
        review.write_text("第 2 节有一条意见。", encoding="utf-8")
        task = self.run_cli("start", "--task", "审阅和润色", "--mode", "review-and-polish",
                            "--artifact", f"qa/clean.txt={clean.name}",
                            "--artifact", f"qa/review.txt={review.name}")
        finish = ["finish", task["id"], "--revision", "0", "--verified-output", f"qa/clean.txt={clean.name}"]
        approved = review.read_bytes()
        review.write_bytes(approved.replace(b"2", b"3"))
        self.run_cli(*finish, "--verified-output", f"qa/review.txt={review.name}", ok=False)
        pending = self.run_cli("show", task["id"])
        self.assertEqual(("active", 0, []), (pending["status"], pending["revision"], pending["outputs"]))
        self.assertNotEqual(approved, review.read_bytes())
        review.write_bytes(approved)
        self.run_cli(*finish, "--verified-output", f"missing.txt={review.name}", ok=False)
        done = self.run_cli(*finish, "--verified-output", f"qa/review.txt={review.name}")
        self.assertEqual(("completed", 2), (done["status"], len(done["outputs"])))
        self.assertEqual([a["sha256"] for a in done["artifacts"]], [o["sha256"] for o in done["outputs"]])

    def test_input_parent_after_link_keeps_the_authors_named_revision(self):
        versions = [self.workspace / version for version in ("first", "second")]
        for folder in versions:
            (folder / "section").mkdir(parents=True)
            (folder / self.original.name).write_text(folder.name, encoding="utf-8")
        link = self.workspace / "selected"
        def select(version):
            if os.name == "nt":
                subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", link.name, str(version / "section")],
                               cwd=self.workspace, capture_output=True, check=True)
            else:
                link.symlink_to(version / "section", target_is_directory=True)

        select(versions[0])
        selected = Path("selected") / ".." / self.original.name
        started = self.run_cli("start", "--task", "版本检查", "--mode", "review", "--input", selected)
        # Ordinary Win32 paths collapse ".." before traversing the junction;
        # POSIX follows the link first. Compare with what an editor would open.
        digest = hashlib.sha256((self.workspace / selected).read_bytes()).hexdigest()
        self.assertEqual(digest, started["inputs"][0]["sha256"])
        link.rename(self.workspace / "previous")
        select(versions[1])
        expected = "ready" if os.name == "nt" else "blocked"
        self.assertEqual(expected, self.run_cli("resume", "--input", selected)["status"])
        if os.name != "nt":
            self.run_cli("start", "--task", "缺少目录", "--mode", "review", "--input",
                         Path("missing") / ".." / self.original.name, ok=False)
        ordinary = self.start()
        self.assertEqual(ordinary["id"], self.run_cli("resume", "--task", "检查原稿", "--input",
                         Path("first") / ".." / self.original.name)["id"])

    def test_changing_directory_link_during_attachment_read_rolls_back_save(self):
        for name in ("old", "new"):
            (self.workspace / name).mkdir()
            (self.workspace / name / "draft.txt").write_text(name, encoding="utf-8")
        for link, target in (("selected", "old"), ("replacement", "new")):
            if os.name == "nt":
                subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", link, target],
                               cwd=self.workspace, capture_output=True, check=True)
            else:
                (self.workspace / link).symlink_to(target, target_is_directory=True)

        task = self.start()
        state = self.state_file("state.json", ["已复核"], "交付")
        hook = """
import runpy, sys
from pathlib import Path
root = Path(sys.argv.pop(1))
open_file = Path.open
def open_then_switch(self, *args, **kwargs):
    handle = open_file(self, *args, **kwargs)
    if self.name == 'draft.txt' and args == ('rb',):
        Path.open = open_file
        (root / 'selected').rename(root / 'previous')
        (root / 'replacement').rename(root / 'selected')
    return handle
Path.open = open_then_switch
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
"""
        command = [*self.args[:4], "-c", hook, str(self.workspace), *self.args[4:], "save", task["id"],
                   "--revision", "0", "--state", state.name, "--artifact", "draft.txt=selected/draft.txt"]
        result = subprocess.run(command, cwd=self.temp, capture_output=True, encoding="utf-8", timeout=25)
        self.assertEqual("new", (self.workspace / "selected/draft.txt").read_text(encoding="utf-8"))
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertIn("读取时文件发生变化", result.stderr)
        restored = self.run_cli("show", task["id"])
        self.assertEqual((0, []), (restored["revision"], restored["artifacts"]))

    def test_restored_bytes_progress_and_no_overwrite(self):
        task = self.start()["id"]
        fragment = self.workspace / "处理中.tmp"
        draft = b"\x00PK\x03\x04\xff" + "审稿记录".encode()
        fragment.write_bytes(draft)
        phase1 = self.state_file("第一阶段.json", ["第一节"], "审第二节")
        self.run_cli("save", task, "--revision", 0, "--state", phase1.name,
                     "--artifact", f"草稿/结果.docx={fragment.name}")
        fragment.unlink()
        phase2 = self.state_file("第二阶段.json", ["第一节", "第二节"], "核对引文")
        self.run_cli("save", task, "--revision", 1, "--state", phase2.name)
        resumed = self.run_cli("resume", "--input", self.original.name)
        self.assertEqual(("ready", 2), (resumed["status"], resumed["revision"]))
        self.assertEqual(["第一节", "第二节"], resumed["state"]["done"])
        self.assertEqual("核对引文", resumed["state"]["next"])
        self.run_cli("restore", task, "--revision", 2, "--to", "恢复")
        path = self.workspace / "恢复" / "草稿" / "结果.docx"
        self.assertEqual(draft, path.read_bytes())
        path.write_bytes(b"author edits")
        self.run_cli("restore", task, "--to", "恢复", ok=False)
        self.assertEqual(b"author edits", path.read_bytes())
        for name in ("../越界", "目录/../../越界", "C:/unexpected", "目录\\..\\越界"):
            with self.subTest(name=name):
                self.run_cli("save", task, "--revision", 2, "--state", phase2.name,
                             "--artifact", f"{name}={phase2.name}", ok=False)
        self.assertEqual(2, self.run_cli("show", task)["revision"])
        self.assertFalse((self.workspace / "越界").exists())
        self.assertFalse((self.temp / "越界").exists())

    def test_resume_after_workspace_move_and_chat_only_draft(self):
        review = self.start()
        moved = self.temp / "移到新位置"
        self.workspace.rename(moved)
        self.workspace = moved
        self.args[-1] = str(moved)
        picked = self.run_cli("resume", "--input", self.original.name, "--mode", "review")
        self.assertEqual(("ready", review["id"]), (picked["status"], picked["id"]))
        notes = self.workspace / "聊天材料.txt"
        notes.write_text("只测 B 组。起草中文方法段。", encoding="utf-8")
        draft = self.run_cli("start", "--task", "起草方法段", "--mode", "draft", "--scope", "方法段",
                             "--artifact", f"材料.txt={notes.name}")
        notes.unlink()
        current = self.run_cli("resume", "--mode", "draft", "--scope", "方法段")
        self.assertEqual(("ready", draft["id"]), (current["status"], current["id"]))
        self.run_cli("restore", draft["id"], "--to", "取回材料")
        self.assertEqual("只测 B 组。起草中文方法段。", (moved / "取回材料" / "材料.txt").read_text(encoding="utf-8"))

    def test_restore_rechecks_source_before_publishing_receipt(self):
        original = self.original.read_bytes()
        task = self.run_cli("start", "--task", "核对稿件", "--mode", "review", "--input", self.original.name,
                            "--artifact", f"draft.md={self.original.name}")
        # Simulate an editor saving the source as the first exported file is
        # flushed, after the restore process checked the original input.
        hook = """
import os, runpy, sys
from pathlib import Path
source = Path(sys.argv.pop(1))
sync = os.fsync
def edit_during_restore(fd):
    os.fsync = sync
    sync(fd)
    source.write_bytes(b"new author revision")
os.fsync = edit_during_restore
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""
        for reference in (False, True):
            with self.subTest(reference=reference):
                self.original.write_bytes(original)
                dest = self.workspace / ("供对照" if reference else "继续编辑")
                command = [*self.args[:4], "-c", hook, str(self.original), *self.args[4:],
                           "restore", task["id"], "--to", str(dest)]
                if reference:
                    command.append("--for-reference")
                result = subprocess.run(command, cwd=self.temp, capture_output=True, encoding="utf-8", timeout=25)
                receipt = dest / ".unbot-restored.json"
                self.assertEqual(b"new author revision", self.original.read_bytes())
                self.assertEqual(original, (dest / "draft.md").read_bytes())
                if reference:
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertEqual("changed", json.loads(receipt.read_text(encoding="utf-8"))["inputs"][0]["status"])
                else:
                    self.assertEqual(2, result.returncode, result.stderr)
                    self.assertFalse(receipt.exists())

    def test_restore_rejects_a_dangling_directory_link(self):
        task = self.run_cli("start", "--task", "恢复草稿", "--mode", "draft",
                            "--artifact", f"draft.md={self.original.name}")
        external = self.temp / "unused"
        external.mkdir()
        dest = self.workspace / "recovery-link"
        if os.name == "nt":
            # A directory junction can be created without symlink privileges.
            subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", dest.name, r"..\unused"],
                           cwd=self.workspace, capture_output=True, check=True)
        else:
            dest.symlink_to(external, target_is_directory=True)
        external.rmdir()
        self.run_cli("restore", task["id"], "--to", dest.name, ok=False)
        self.assertFalse(external.exists())
        self.assertTrue(os.path.lexists(dest))

    def test_source_replaced_or_missing_blocks_reuse(self):
        initial = self.original.read_bytes()
        task = self.run_cli("start", "--task", "对读原稿", "--mode", "polish",
                            "--input", self.original.name, "--artifact", f"记录.txt={self.original.name}")["id"]
        self.original.write_bytes(initial.replace(b"12", b"21"))
        blocked = self.run_cli("resume", "--input", self.original.name)
        self.assertEqual("blocked", blocked["status"])
        self.assertEqual("changed", blocked["inputs"][0]["status"])
        state = self.state_file("状态.json", ["表 1"], "核验图 2")
        self.run_cli("save", task, "--revision", 0, "--state", state.name, ok=False)
        final = self.workspace / "审稿意见.md"
        final.write_text("检查结果。", encoding="utf-8")
        self.run_cli("finish", task, "--revision", 0, "--output", final.name, ok=False)
        self.run_cli("restore", task, "--to", "旧稿", ok=False)
        self.assertFalse((self.workspace / "旧稿").exists())
        self.run_cli("restore", task, "--to", "供核对", "--for-reference")
        self.assertEqual(initial, (self.workspace / "供核对" / "记录.txt").read_bytes())
        self.original.unlink()
        self.assertEqual("missing", self.run_cli("show", task)["inputs"][0]["status"])
        self.original.write_bytes(initial)
        recovered = self.run_cli("resume")
        self.assertEqual(("ready", 0), (recovered["status"], recovered["revision"]))

    def test_two_writers_cannot_replace_same_revision(self):
        task = self.start()["id"]
        states = [self.state_file("A.json", [], "校对 A"), self.state_file("B.json", [], "校对 B")]
        processes = []
        try:
            for state in states:
                command = [*self.args, "save", task, "--revision", "0", "--state", state.name]
                processes.append(subprocess.Popen(command, cwd=self.temp, stdout=subprocess.PIPE,
                                                  stderr=subprocess.PIPE, encoding="utf-8"))
            outputs = [p.communicate(timeout=25) for p in processes]
            successful = [i for i, p in enumerate(processes) if p.returncode == 0]
            self.assertEqual(1, len(successful), outputs)
            winner = states[successful[0]]
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
        current = self.run_cli("show", task)
        self.assertEqual(1, current["revision"])
        self.assertEqual(json.loads(winner.read_text(encoding="utf-8")), current["state"])

    def test_single_named_source_checks_attachments_and_accepts_new_baseline(self):
        attachment = self.workspace / "附表.txt"
        attachment.write_text("表 1：12 ms。", encoding="utf-8")
        settings = ["--task", "核对正文和附表", "--scope", "整篇", "--mode", "review",
                    "--input", self.original.name, "--input", attachment.name]
        old = self.run_cli("start", *settings)["id"]
        self.run_cli("start", *settings, ok=False)
        recovered = self.run_cli("resume", "--input", self.original.name)
        self.assertEqual(("ready", old), (recovered["status"], recovered["id"]))
        attachment.write_text("表 1：21 ms。", encoding="utf-8")
        blocked = self.run_cli("resume", "--input", self.original.name)
        self.assertEqual("blocked", blocked["status"])
        self.assertEqual({self.original.name: "ok", attachment.name: "changed"},
                         {p["path"]: p["status"] for p in blocked["inputs"]})
        new = self.run_cli("start", *settings)["id"]
        self.assertNotEqual(old, new)
        # A new process has no memory of which baseline the previous session selected.
        # Both tasks are still active here, but only the new one matches the current files.
        after_restart = self.run_cli("resume", "--input", self.original.name)
        self.assertEqual(("ready", new), (after_restart["status"], after_restart["id"]))
        self.run_cli("start", *settings, ok=False)
        self.run_cli("retire", old, "--revision", 0)
        current = self.run_cli("resume", "--input", self.original.name)
        self.assertEqual(("ready", new), (current["status"], current["id"]))
        other = self.run_cli("start", "--task", "仅提取术语", "--mode", "review",
                             "--input", self.original.name)["id"]
        attachment.write_text("表 1：31 ms。", encoding="utf-8")
        # Only the independent glossary task still has matching inputs. The caller
        # did not select that task, so it cannot silently replace the report review.
        self.assertEqual("ambiguous", self.run_cli("resume", "--input", self.original.name)["status"])
        self.assertEqual(other, self.run_cli("resume", "--task", "仅提取术语")["id"])

    def test_termination_before_commit_keeps_last_complete_snapshot(self):
        task = self.start()["id"]
        report = self.workspace / "草稿.txt"
        report.write_bytes(b"last complete snapshot")
        state = self.state_file("状态.json", ["方法"], "写结果")
        self.run_cli("save", task, "--revision", 0, "--state", state.name,
                     "--artifact", f"draft.txt={report.name}")
        report.write_bytes(b"partly replaced data" * 16000)
        self.state_file(state.name, ["方法", "结果"], "检查附录")
        # This process exits inside SQLite's COMMIT callback, after the real
        # writer has executed its DML and before SQLite commits the transaction.
        hooks = self.temp / "test_hooks"
        hooks.mkdir()
        (hooks / "sitecustomize.py").write_text(
            "import os, sqlite3\n"
            "connect = sqlite3.connect\n"
            "def instrument(*args, **kw):\n"
            "    db = connect(*args, **kw)\n"
            "    wrote = False\n"
            "    def observe(sql):\n"
            "        nonlocal wrote\n"
            "        verb = sql.lstrip().upper().split(' ', 1)[0]\n"
            "        if verb in ('INSERT', 'UPDATE', 'DELETE', 'REPLACE'):\n"
            "            wrote = True\n"
            "        if wrote and verb == 'COMMIT':\n"
            "            os._exit(87)\n"
            "    db.set_trace_callback(observe)\n"
            "    return db\n"
            "sqlite3.connect = instrument\n",
            encoding="utf-8")
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, [str(hooks), os.getenv("PYTHONPATH")])))
        crashed = self.run_cli("save", task, "--revision", 1, "--state", state.name,
                               "--artifact", f"draft.txt={report.name}", env=env, ok=False)
        self.assertEqual(87, crashed.returncode, crashed.stderr)
        resumed = self.run_cli("resume")
        self.assertEqual(("ready", 1), (resumed["status"], resumed["revision"]))
        self.assertEqual({"done": ["方法"], "next": "写结果"}, resumed["state"])
        self.run_cli("restore", task, "--to", "重开")
        self.assertEqual(b"last complete snapshot", (self.workspace / "重开" / "draft.txt").read_bytes())


if __name__ == "__main__":
    unittest.main()
