#!/usr/bin/env python3
"""Validated, non-pruning MySQL backups configured by a local JSON file."""
import argparse
import contextlib
import datetime as dt
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid

NAME = re.compile(r"^[A-Za-z0-9_]+$")
CREATE = re.compile(rb"^CREATE TABLE `([A-Za-z0-9_]+)` \(")
INSERT = re.compile(rb"^INSERT INTO `([A-Za-z0-9_]+)` VALUES \(")
MAX_LINE = 32 * 1024 * 1024


class BackupError(Exception):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as out:
            os.chmod(temporary, 0o600)
            json.dump(value, out, sort_keys=True, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def inspect_dump(path):
    """Stream bounded mysqldump rows; never deserialize business values."""
    tables = {}
    schema = None
    last = b""
    with gzip.open(path, "rb") as src:
        while True:
            line = src.readline(MAX_LINE + 1)
            if not line:
                break
            if len(line) > MAX_LINE:
                raise BackupError("sql-line-too-large")
            if line.strip():
                last = line.strip()
            if re.match(rb"^(USE |CREATE DATABASE |DROP DATABASE )", line):
                raise BackupError("database-switch-in-dump")
            match = CREATE.match(line)
            if match:
                key = match[1].decode("ascii")
                if key in tables or schema is not None:
                    raise BackupError("duplicate-or-malformed-schema")
                tables[key] = {"rows": 0, "data": hashlib.sha256(), "schema": hashlib.sha256()}
                schema = key
            if schema is not None:
                tables[schema]["schema"].update(line)
                if line.rstrip().endswith(b";"):
                    schema = None
            match = INSERT.match(line)
            if match:
                key = match[1].decode("ascii")
                if key not in tables or not line.rstrip().endswith(b");"):
                    raise BackupError("malformed-insert")
                tables[key]["rows"] += 1
                tables[key]["data"].update(line)
    if not tables or schema is not None or not last.startswith(b"-- Dump completed on "):
        raise BackupError("empty-or-incomplete-dump")
    return {key: {"rows": entry["rows"], "data_sha256": entry["data"].hexdigest(),
                  "schema_sha256": entry["schema"].hexdigest()}
            for key, entry in sorted(tables.items())}


def log(message, error=False):
    print(message, flush=True)
    try:
        subprocess.run(["/usr/bin/logger", "-t", "dedicated-line-backup", "-p",
                        "daemon.err" if error else "daemon.info", "--", message],
                       timeout=5, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        pass


def alert(cfg, reason):
    # Only bounded internal codes enter notifications; no DB error text or credentials.
    reason = re.sub(r"[^A-Za-z0-9_.:-]", "_", reason)[:120]
    value = {"status": "failure", "time": now(), "reason": reason}
    written = False
    for base in (cfg["state_dir"], cfg["runtime_dir"]):
        try:
            atomic_json(Path(base) / "ALERT.json", value)
            written = True
        except OSError:
            pass
    log("BACKUP ALERT: " + reason, error=True)
    if not written:
        print("ALERT_STATE_WRITE_FAILED", file=sys.stderr, flush=True)


def config(path):
    cfg = json.loads(Path(path).read_text())
    for key in ("app_dir", "backup_root", "state_dir", "runtime_dir"):
        if not Path(cfg[key]).is_absolute():
            raise BackupError("non-absolute-config-path")
    if not NAME.fullmatch(cfg["database"]):
        raise BackupError("invalid-database-name")
    return cfg


def credentials(cfg):
    from dotenv import dotenv_values
    from urllib.parse import urlsplit, unquote
    url = urlsplit(dotenv_values(Path(cfg["app_dir"]) / ".env")["DATABASE_URL"])
    name = unquote(url.path.lstrip("/"))
    if name != cfg["database"] or url.hostname not in ("127.0.0.1", "localhost"):
        raise BackupError("unexpected-database-target")
    return {"host": url.hostname, "port": url.port or 3306, "user": unquote(url.username or ""),
            "password": unquote(url.password or ""), "database": name}


def inventory(creds):
    import pymysql
    with pymysql.connect(**creds, charset="utf8mb4", connect_timeout=5, read_timeout=30,
                         write_timeout=30, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT TABLE_NAME, ENGINE, TABLE_TYPE FROM information_schema.TABLES "
                        "WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME", (creds["database"],))
            tables = cur.fetchall()
            if not tables or any(not NAME.fullmatch(t[0]) or t[1] != "InnoDB" or t[2] != "BASE TABLE" for t in tables):
                raise BackupError("unsupported-table-layout")
            for source, column in (("TRIGGERS", "TRIGGER_SCHEMA"), ("ROUTINES", "ROUTINE_SCHEMA"), ("EVENTS", "EVENT_SCHEMA")):
                cur.execute(f"SELECT COUNT(*) FROM information_schema.{source} WHERE {column}=%s", (creds["database"],))
                if cur.fetchone()[0]:
                    raise BackupError("stored-objects-require-restore-policy-review")
            cur.execute("SELECT DISTINCT TABLE_NAME FROM information_schema.STATISTICS "
                        "WHERE TABLE_SCHEMA=%s AND INDEX_NAME='PRIMARY'", (creds["database"],))
            if {row[0] for row in cur.fetchall()} != {t[0] for t in tables}:
                raise BackupError("primary-key-required-for-verification")
            return [t[0] for t in tables]


def cnf_quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r") + '"'


@contextlib.contextmanager
def client_file(runtime, creds):
    Path(runtime).mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="client-", dir=runtime) as directory:
        path = Path(directory) / "client.cnf"
        with path.open("x") as out:
            os.chmod(path, 0o600)
            out.write("[client]\n")
            for key in ("host", "port", "user", "password", "socket"):
                if key in creds:
                    out.write(key + "=" + cnf_quote(creds[key]) + "\n")
            out.write("protocol=" + ("SOCKET" if "socket" in creds else "TCP") + "\n")
        yield path


def dump_database(cnf, name, target):
    args = ["/usr/bin/mysqldump", f"--defaults-file={cnf}", "--single-transaction", "--quick",
            "--skip-lock-tables", "--no-tablespaces", "--set-gtid-purged=OFF", "--hex-blob",
            "--skip-extended-insert", "--order-by-primary", "--no-autocommit",
            "--default-character-set=utf8mb4", name]
    error_path = target.with_suffix(target.suffix + ".stderr")
    with error_path.open("xb") as errors:
        with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=errors) as process:
            try:
                with gzip.open(target, "wb", compresslevel=6) as out:
                    shutil.copyfileobj(process.stdout, out, 1024 * 1024)
            except BaseException:
                process.kill()
                process.wait()
                raise
            finally:
                process.stdout.close()
            if process.wait() != 0:
                raise BackupError("mysqldump-nonzero-exit")
    if error_path.stat().st_size:
        raise BackupError("mysqldump-reported-diagnostic")
    with target.open("rb") as src:
        os.fsync(src.fileno())


def check_space(cfg):
    if shutil.disk_usage(cfg["backup_root"]).free < cfg.get("min_free_bytes", 1073741824):
        raise BackupError("insufficient-disk-space")


def archive_config(cfg, target):
    with tarfile.open(target, "w:gz", compresslevel=6) as out:
        for name in cfg["config_paths"]:
            path = Path(name)
            if not path.exists():
                raise BackupError("missing-config-backup-input")
            out.add(path, arcname=str(path).lstrip("/"), recursive=True)
    # Read all regular members to validate the gzip stream and archive payloads.
    with tarfile.open(target, "r:gz") as src:
        for member in src:
            if member.isfile():
                with src.extractfile(member) as stream:
                    for _ in iter(lambda: stream.read(1024 * 1024), b""):
                        pass
    with target.open("rb") as src:
        os.fsync(src.fileno())


def verify_run(directory):
    directory = Path(directory)
    meta = json.loads((directory / "manifest.json").read_text())
    if meta.get("format") != 1 or meta.get("status") != "validated":
        raise BackupError("manifest-not-validated")
    if set(meta["files"]) != {"database.sql.gz", "project_config.tar.gz"}:
        raise BackupError("unexpected-manifest-files")
    for name, expected in meta["files"].items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != expected["bytes"] or digest(path) != expected["sha256"]:
            raise BackupError("backup-file-integrity-failed")
    if inspect_dump(directory / "database.sql.gz") != meta["tables"]:
        raise BackupError("sql-manifest-mismatch")
    return meta


def do_backup(cfg):
    root, state = Path(cfg["backup_root"]), Path(cfg["state_dir"])
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    stage = "lock"
    partial = None
    with (state / "backup.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BackupError("backup-already-running")
        try:
            stage = "preflight"
            check_space(cfg)
            creds = credentials(cfg)
            expected = inventory(creds)
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
            partial = root / (".partial-" + stamp)
            partial.mkdir(mode=0o700)
            atomic_json(state / "status.json", {"status": "running", "time": now(), "run": stamp})
            stage = "dump"
            with client_file(cfg["runtime_dir"], creds) as cnf:
                dump_database(cnf, creds["database"], partial / "database.sql.gz")
            stage = "sql-validation"
            tables = inspect_dump(partial / "database.sql.gz")
            if sorted(tables) != expected or inventory(creds) != expected:
                raise BackupError("schema-inventory-mismatch")
            stage = "config-archive"
            archive_config(cfg, partial / "project_config.tar.gz")
            meta = {"format": 1, "status": "validated", "time": now(), "database": cfg["database"], "tables": tables,
                    "files": {name: {"bytes": (partial / name).stat().st_size, "sha256": digest(partial / name)}
                              for name in ("database.sql.gz", "project_config.tar.gz")}}
            atomic_json(partial / "manifest.json", meta)
            verify_run(partial)
            stage = "publish"
            latest = root / "latest"
            if latest.exists() and not latest.is_symlink():
                raise BackupError("latest-is-not-symlink")
            published = root / stamp
            os.rename(partial, published)
            partial = None
            temp_link = root / (".latest-" + uuid.uuid4().hex)
            temp_link.symlink_to(published.name)
            os.replace(temp_link, latest)
            sync_directory(root)
            success = {"status": "success", "time": now(), "run": str(published), "tables": len(tables),
                       "rows": sum(t["rows"] for t in tables.values()), "manifest_sha256": digest(published / "manifest.json")}
            atomic_json(state / "last_success.json", success)
            atomic_json(state / "status.json", success)
            for base in (state, Path(cfg["runtime_dir"])):
                (base / "ALERT.json").unlink(missing_ok=True)
            log("BACKUP SUCCESS: " + stamp + " tables=" + str(len(tables)))
            return success
        except Exception as exc:
            reason = f"{stage}:" + (str(exc) if isinstance(exc, BackupError) else type(exc).__name__)
            if partial is not None:
                try:
                    atomic_json(partial / "FAILED.json", {"status": "failed", "time": now(), "reason": reason})
                except OSError:
                    pass
            try:
                atomic_json(state / "status.json", {"status": "failed", "time": now(), "reason": reason})
            except OSError:
                pass
            raise BackupError(reason) from None


def check_freshness(cfg):
    check_space(cfg)
    state = Path(cfg["state_dir"])
    last = json.loads((state / "last_success.json").read_text())
    age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(last["time"])).total_seconds()
    if age < -300 or age > cfg.get("max_age_hours", 30) * 3600:
        raise BackupError("backup-expired-or-clock-changed")
    run = Path(last["run"])
    if run.parent.resolve() != Path(cfg["backup_root"]).resolve():
        raise BackupError("last-success-outside-backup-root")
    if digest(run / "manifest.json") != last["manifest_sha256"]:
        raise BackupError("manifest-integrity-failed")
    meta = json.loads((run / "manifest.json").read_text())
    for name, item in meta["files"].items():
        if name not in ("database.sql.gz", "project_config.tar.gz") or digest(run / name) != item["sha256"]:
            raise BackupError("latest-backup-integrity-failed")
    status = json.loads((state / "status.json").read_text())
    if status["status"] == "failed":
        raise BackupError("last-backup-attempt-failed")
    if status["status"] == "running" and (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(status["time"])).total_seconds() > 1800:
        raise BackupError("backup-stuck")
    for operation in ("is-enabled", "is-active"):
        timer = subprocess.run(["/usr/bin/systemctl", operation, "dedicated-line-backup.timer"],
                               capture_output=True, timeout=10)
        if timer.returncode != 0:
            raise BackupError("backup-timer-disabled-or-inactive")
    log("BACKUP WATCHDOG OK")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/etc/dedicated-line-backup.json")
    parser.add_argument("action", choices=["backup", "check", "alert", "verify"])
    parser.add_argument("--run")
    parser.add_argument("--reason", default="systemd-job-failed")
    args = parser.parse_args()
    os.umask(0o077)
    cfg = None
    try:
        cfg = config(args.config)
        if args.action == "backup":
            do_backup(cfg)
        elif args.action == "check":
            check_freshness(cfg)
        elif args.action == "alert":
            alert(cfg, args.reason)
        elif args.action == "verify":
            if not args.run:
                raise BackupError("run-required")
            verify_run(args.run)
            log("BACKUP VERIFY OK")
        return 0
    except Exception as exc:
        reason = str(exc) if isinstance(exc, BackupError) else type(exc).__name__
        if cfg is not None:
            alert(cfg, reason)
        else:
            log("BACKUP ALERT: invalid-configuration", error=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
