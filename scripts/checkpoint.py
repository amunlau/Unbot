"""在文稿工作区保存及找回 Unbot 的本地任务。只依赖 Python 标准库。"""

import argparse
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import sqlite3
import stat
import sys
import unicodedata
import uuid


MODES = ("draft", "polish", "review", "review-and-polish")
CHUNK = 1024 * 1024
DB_NAME = "checkpoints.sqlite3"
RECEIPT = ".unbot-restored.json"
OUTPUT_DIR = "__outputs__"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stored_path(root, value):
    # Keep the author's named input even if a symlink is later redirected to a new revision.
    path = root / value
    if os.name == "nt":
        path = Path(os.path.abspath(path))
    elif ".." in path.parts:
        # POSIX traverses each directory before interpreting "..". Collapsing a
        # symlink (or a missing directory) here can silently select another draft.
        current = Path(path.anchor)
        for component in path.parts[1:]:
            if component == ".." and current.name != ".." and current.is_dir() and not current.is_symlink():
                current = current.parent
            else:
                current = current / component
        path = current
    target = path.resolve()
    store = root / ".unbot"
    if target.parent == store and target.name.casefold().startswith(DB_NAME):
        raise ValueError("任务数据库不能作为文稿、状态文件或交付件。")
    # Windows resolves the on-disk spelling. Preserve it when moving to Linux,
    # while keeping an explicitly named symlink as the source of future checks.
    if path == target:
        path = target
    return path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)


def input_key(root, name):
    if os.name != "nt":
        return name
    # Older records may contain the caller's casing. A file ID distinguishes
    # identically spelt names in Windows directories with case sensitivity on.
    try:
        info = (root / name).stat()
        file_id = (info.st_dev, info.st_ino)
    except (OSError, ValueError):
        file_id = None
    return os.path.normcase(name), file_id


def baseline(root, records):
    return {input_key(root, i["path"]): i["sha256"] for i in records}


def stable_read(path, consume=None):
    """对同一次读取计算指纹、大小；即使文件被重命名替换也检查到。"""
    def identity(s):
        return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

    if not path.is_file():
        raise FileNotFoundError(f"找不到普通文件：{path}")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"并非普通文件：{path}")
        for sequence, block in enumerate(iter(lambda: handle.read(CHUNK), b"")):
            digest.update(block)
            size += len(block)
            if consume:
                consume(sequence, block)
        # On Windows stat(path).st_ctime and fstat(fd).st_ctime may describe
        # different timestamps. Reopen by name and compare two handle-based stats.
        with path.open("rb") as current:
            unchanged = identity(before) == identity(os.fstat(handle.fileno())) == identity(os.fstat(current.fileno()))
        if not unchanged:
            raise ValueError(f"读取时文件发生变化，请重试：{path}")
    return digest.hexdigest(), size


def state_from(root, filename):
    if filename is None:
        return {"done": [], "next": "核对任务范围及材料"}
    path = root / stored_path(root, filename)
    blocks = []
    stable_read(path, lambda _, block: blocks.append(block))
    state = json.loads(b"".join(blocks).decode("utf-8-sig"))
    if not isinstance(state, dict) or not isinstance(state.get("done"), list):
        raise ValueError("state 必须是 JSON 对象，包含 done 数组和 next 字符串。")
    if not all(isinstance(s, str) and s.strip() for s in state["done"]):
        raise ValueError("done 只能包含非空字符串，可为空数组。")
    if not isinstance(state.get("next"), str) or not state["next"].strip():
        raise ValueError("next 必须说明下一步工作。")
    return state


@contextmanager
def database(root, command):
    store = root / ".unbot"
    db = store / DB_NAME
    if not root.is_dir():
        raise ValueError("工作区必须是已存在的文稿目录。")
    if store.resolve() != store or db.resolve() != db:
        raise ValueError("断点目录或数据库不能是指向其他位置的链接。")
    new_allowed = command == "start"
    if not db.exists() and not new_allowed:
        if command in ("resume", "list"):
            yield None
            return
        raise ValueError("工作区尚无断点库。")
    if new_allowed:
        store.mkdir(exist_ok=True, mode=0o700)
        try:
            with (store / ".gitignore").open("x", encoding="ascii") as ignore:
                ignore.write("*\n")
        except FileExistsError:
            pass
    mode = "rwc" if new_allowed else "rw"
    with closing(sqlite3.connect(db.as_uri() + "?mode=" + mode, uri=True,
                                 isolation_level=None, timeout=15)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        # EXTRA also syncs the rollback journal's directory after committing.
        conn.execute("PRAGMA synchronous=EXTRA")
        write = command in ("start", "save", "finish", "retire")
        conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        empty = version == 0 and not conn.execute("SELECT 1 FROM sqlite_master").fetchone()
        if empty and command in ("list", "resume"):
            yield None
            return
        if empty and new_allowed:
            conn.execute("""CREATE TABLE tasks (
                id TEXT PRIMARY KEY, task TEXT NOT NULL, mode TEXT NOT NULL, scope TEXT NOT NULL,
                revision INTEGER NOT NULL, status TEXT NOT NULL, updated TEXT NOT NULL,
                state TEXT NOT NULL, inputs TEXT NOT NULL)""")
            conn.execute("""CREATE TABLE files (
                task_id TEXT REFERENCES tasks(id), name TEXT, kind TEXT NOT NULL, path TEXT,
                sha256 TEXT NOT NULL, size INTEGER NOT NULL, PRIMARY KEY(task_id,name))""")
            conn.execute("""CREATE TABLE chunks (
                task_id TEXT, name TEXT, seq INTEGER, data BLOB NOT NULL,
                PRIMARY KEY(task_id,name,seq),
                FOREIGN KEY(task_id,name) REFERENCES files(task_id,name) ON DELETE CASCADE)""")
            conn.execute("PRAGMA user_version=1")
        elif version != 1:
            raise ValueError("断点数据库格式不受支持。请保留原文件。")
        yield conn
        conn.commit()


def current_digest(root, name):
    # Foreign absolute paths do not identify a local file after a cross-OS move.
    if (os.name != "nt" and PureWindowsPath(name).is_absolute()) or (os.name == "nt" and name.startswith("/")):
        raise FileNotFoundError(name)
    return stable_read(root / name)[0]


def input_checks(root, records):
    results = []
    for original in records:
        item = dict(original)
        try:
            actual = current_digest(root, item["path"])
            item["status"] = "ok" if actual == item["sha256"] else "changed"
        except FileNotFoundError:
            item["status"] = "missing"
        except (OSError, ValueError):
            item["status"] = "unreadable"
        results.append(item)
    return results


def require_inputs(checks):
    gaps = [f"{i['path']} ({i['status']})" for i in checks if i["status"] != "ok"]
    if gaps:
        raise ValueError("原始材料与断点基准不符：" + "、".join(gaps))


def summary(row):
    return {k: row[k] for k in ("id", "task", "mode", "scope", "revision", "status", "updated")}


def details(conn, root, row, checks=None):
    result = summary(row)
    result["state"] = json.loads(row["state"])
    result["inputs"] = checks if checks is not None else input_checks(root, json.loads(row["inputs"]))
    entries = list(conn.execute("SELECT name,path,sha256,size,kind FROM files WHERE task_id=? ORDER BY name", (row["id"],)))
    result["artifacts"] = [{k: f[k] for k in ("name", "sha256", "size")} for f in entries if f["kind"] == "artifact"]
    outputs = [{k: f[k] for k in ("name", "path", "sha256", "size")} for f in entries if f["kind"] == "output"]
    result["outputs"] = input_checks(root, outputs)
    return result


def lookup(conn, task_id):
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if row is None:
        raise ValueError(f"找不到任务 {task_id}。")
    return row


def candidates(conn, args, root):
    if conn is None:
        return []
    rows = conn.execute("SELECT * FROM tasks WHERE status='active' ORDER BY updated DESC, id")
    wanted = {input_key(root, stored_path(root, p)) for p in args.input}
    return [r for r in rows if all(getattr(args, k) is None or getattr(args, k) == r[k]
                                  for k in ("mode", "task", "scope"))
            and wanted.issubset(input_key(root, i["path"]) for i in json.loads(r["inputs"]))]


def portable_name(name):
    # Validate on both platforms before storing so that a Linux archive restores on Windows.
    for segment in name.split("/"):
        if (not segment or segment in (".", "..") or segment.endswith((" ", "."))
                or re.search(r'[<>:"\\|?*\x00-\x1f]', segment)
                or re.fullmatch(r"CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|(?:COM|LPT)[0-9¹²³]",
                                segment.split(".")[0].rstrip(" "), re.I)
                or len(segment.encode("utf-8")) > 255):
            raise ValueError(f"不可移植或不安全的快照文件名：{name!r}")
    return unicodedata.normalize("NFC", name)


def store_file(conn, root, task_id, name, source, kind):
    path = stored_path(root, source)
    conn.execute("DELETE FROM files WHERE task_id=? AND name=?", (task_id, name))
    conn.execute("INSERT INTO files VALUES(?,?,?,?,?,?)", (task_id, name, kind, path if kind == "output" else None, "", 0))

    def add_chunk(seq, block):
        conn.execute("INSERT INTO chunks VALUES(?,?,?,?)", (task_id, name, seq, block))

    digest, size = stable_read(root / path, add_chunk)
    conn.execute("UPDATE files SET sha256=?,size=? WHERE task_id=? AND name=?", (digest, size, task_id, name))
    return digest


def save_artifacts(conn, root, task_id, arguments):
    existing = {r[0] for r in conn.execute("SELECT name FROM files WHERE task_id=?", (task_id,))}
    batch = {}
    for spec in arguments:
        name, sep, source = spec.partition("=")
        if not sep or not source:
            raise ValueError("--artifact 需要 NAME=FILE。")
        name = portable_name(name)
        if name in batch or name.split("/")[0].casefold() in {OUTPUT_DIR, RECEIPT}:
            raise ValueError(f"重复或保留的快照文件名：{name}")
        batch[name] = source
    files = existing | set(batch)
    # Reject both file/directory collisions and case-only aliases at each path component.
    components = {}
    for name in files:
        prefix = ""
        for segment in name.split("/"):
            prefix = prefix + "/" + segment if prefix else segment
            key = prefix.casefold()
            if (prefix in files and prefix != name) or components.setdefault(key, prefix) != prefix:
                raise ValueError(f"快照文件及目录名称有冲突：{name}")
    for name, source in batch.items():
        store_file(conn, root, task_id, name, source, "artifact")


def restore(conn, root, row, args):
    if not args.for_reference:
        require_inputs(input_checks(root, json.loads(row["inputs"])))
    # Create the named directory before resolving it. A dangling link or junction
    # already occupies that name, even when its destination has disappeared.
    dest = root / args.to
    dest.mkdir(mode=0o700)
    dest = dest.resolve()
    entries = conn.execute("SELECT name,sha256,size FROM files WHERE task_id=? ORDER BY name", (row["id"],))
    for entry in entries:
        name = portable_name(entry["name"])
        path = dest / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.resolve().is_relative_to(dest):
            raise ValueError("导出路径超出目标目录。")
        digest = hashlib.sha256()
        with path.open("xb") as handle:
            for block, in conn.execute("SELECT data FROM chunks WHERE task_id=? AND name=? ORDER BY seq", (row["id"], name)):
                handle.write(block)
                digest.update(block)
            if handle.tell() != entry["size"] or digest.hexdigest() != entry["sha256"]:
                raise ValueError(f"快照校验失败：{name}。请保留数据库。")
            handle.flush()
            os.fsync(handle.fileno())
    # The author can edit an input while a large snapshot is being unpacked.
    # Derive receipt status from the files at the end of the restoration.
    result = details(conn, root, row)
    if not args.for_reference:
        require_inputs(result["inputs"])
    # An interruption leaves an expendable directory. A completed restore has a receipt.
    result["restored_to"] = str(dest)
    result["for_reference"] = args.for_reference
    temp_receipt = dest / (".receipt-" + uuid.uuid4().hex)
    with temp_receipt.open("x", encoding="utf-8") as receipt:
        json.dump(result, receipt, ensure_ascii=False, indent=2)
        receipt.flush()
        os.fsync(receipt.fileno())
    temp_receipt.rename(dest / RECEIPT)
    return result


def run(conn, root, args):
    command = args.command
    if command == "list":
        query = "SELECT * FROM tasks " + ("" if args.all else "WHERE status='active' ") + "ORDER BY updated DESC, id"
        return {"tasks": [dict(summary(r), inputs=[i["path"] for i in json.loads(r['inputs'])])
                          for r in conn.execute(query)] if conn else []}
    if command == "resume":
        matches = candidates(conn, args, root)
        checks = None
        if len(matches) > 1:
            baselines = [json.loads(r["inputs"]) for r in matches]
            signatures = [baseline(root, records) for records in baselines]
            identities = {(r["task"], r["mode"], r["scope"], frozenset(signature))
                          for r, signature in zip(matches, signatures)}
            # A crash can leave both the original and its replacement task active.
            # They are interchangeable candidates only when the complete identities
            # match; quantify which whole input revision is actually on disk.
            if len(identities) == 1 and baselines[0]:
                actual = {}
                for item in baselines[0]:
                    name = item["path"]
                    try:
                        actual[input_key(root, name)] = current_digest(root, name)
                    except (OSError, ValueError):
                        break
                valid = [(r, records) for r, records, signature in zip(matches, baselines, signatures)
                         if actual == signature]
                if len(valid) == 1:
                    row, records = valid[0]
                    matches = [row]
                    checks = [dict(i, status="ok") for i in records]
        if len(matches) != 1:
            return {"status": "ambiguous" if matches else "none",
                    "candidates": [dict(summary(r), inputs=[i["path"] for i in json.loads(r["inputs"])])
                                   for r in matches]}
        result = details(conn, root, matches[0], checks)
        result["status"] = "ready" if all(i["status"] == "ok" for i in result["inputs"]) else "blocked"
        return result
    if command == "start":
        if not args.task.strip():
            raise ValueError("请填写任务说明。")
        paths = [stored_path(root, p) for p in args.input]
        paths = sorted({input_key(root, p): p for p in paths}.values())
        inputs = []
        for path in paths:
            digest, size = stable_read(root / path)
            inputs.append({"path": path, "sha256": digest, "size": size})
        signature = baseline(root, inputs)
        for r in candidates(conn, args, root):
            if signature == baseline(root, json.loads(r["inputs"])):
                raise ValueError(f"相同任务已存在，请使用 resume 或 show {r['id']}。")
        task_id = uuid.uuid4().hex
        conn.execute("INSERT INTO tasks VALUES(?,?,?,?,0,'active',?,?,?)", (
            task_id, args.task, args.mode, args.scope, now(), json.dumps(state_from(root, args.state)),
            json.dumps(inputs)))
        save_artifacts(conn, root, task_id, args.artifact)
        result = details(conn, root, lookup(conn, task_id))
        require_inputs(result["inputs"])
        return result
    row = lookup(conn, args.id)
    if command == "show":
        return details(conn, root, row)
    if args.revision is not None and args.revision != row["revision"]:
        raise ValueError(f"断点版本已改变，当前为 {row['revision']}。请重新读取后继续。")
    if command == "restore":
        return restore(conn, root, row, args)
    if row["status"] != "active":
        raise ValueError("任务已经完成或封存。")
    inputs = json.loads(row["inputs"])
    status, state = "active", row["state"]
    if command == "save":
        state = json.dumps(state_from(root, args.state))
        save_artifacts(conn, root, row["id"], args.artifact)
    elif command == "finish":
        status = "completed"
        outputs = [(p, None) for p in args.output or []]
        for spec in args.verified_output or []:
            artifact, sep, destination = spec.partition("=")
            if not sep or not destination:
                raise ValueError("--verified-output 需要 已验收附件名=交付文件。")
            saved = conn.execute("SELECT sha256 FROM files WHERE task_id=? AND name=? AND kind='artifact'",
                                 (row["id"], portable_name(artifact))).fetchone()
            if saved is None:
                raise ValueError(f"找不到已验收的附件：{artifact}")
            outputs.append((destination, saved["sha256"]))
        paths = []
        sources = [root / i["path"] for i in inputs]
        for count, (destination, expected) in enumerate(outputs, 1):
            path = root / stored_path(root, destination)
            if any(os.path.samefile(path, other) for other in sources + paths):
                raise ValueError("交付件必须独立于原稿，且不可重复。")
            paths.append(path)
            name = portable_name(f"{OUTPUT_DIR}/{count:03d}/{path.name}")
            digest = store_file(conn, root, row["id"], name, path, "output")
            if expected is not None and digest != expected:
                raise ValueError(f"交付件内容与已验收附件不符，请核对后重新登记：{path}")
    elif command == "retire":
        status = "retired"
    checks = input_checks(root, inputs)
    if command != "retire":
        require_inputs(checks)
    conn.execute("UPDATE tasks SET revision=revision+1, status=?,state=?,updated=? WHERE id=?",
                 (status, state, now(), row["id"]))
    result = details(conn, root, lookup(conn, row["id"]), checks)
    if command == "finish" and any(i["status"] != "ok" for i in result["outputs"]):
        raise ValueError("登记期间交付件发生变化。请重新核对实际文件。")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list").add_argument("--all", action="store_true")
    for command in ("start", "resume"):
        sub = commands.add_parser(command)
        sub.add_argument("--task", required=command == "start")
        sub.add_argument("--mode", choices=MODES, required=command == "start")
        sub.add_argument("--scope", default="" if command == "start" else None)
        sub.add_argument("--input", action="append", default=[])
        if command == "start":
            sub.add_argument("--state")
            sub.add_argument("--artifact", action="append", default=[])
    for command in ("show", "save", "restore", "finish", "retire"):
        sub = commands.add_parser(command)
        sub.add_argument("id")
        if command != "show":
            sub.add_argument("--revision", type=int, required=command != "restore")
        if command == "save":
            sub.add_argument("--state", required=True)
            sub.add_argument("--artifact", action="append", default=[])
        if command == "restore":
            sub.add_argument("--to", required=True)
            sub.add_argument("--for-reference", action="store_true")
        if command == "finish":
            output = sub.add_mutually_exclusive_group(required=True)
            output.add_argument("--output", action="append", metavar="FILE")
            output.add_argument("--verified-output", action="append", metavar="ARTIFACT=FILE",
                                help="按已保存在该任务中的附件核验成品，可重复指定")
    args = parser.parse_args()
    root = args.workspace.resolve()
    try:
        with database(root, args.command) as conn:
            result = run(conn, root, args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(2, f"断点操作失败：{exc}\n")


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
