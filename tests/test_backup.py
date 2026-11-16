import datetime as dt
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

spec = importlib.util.spec_from_file_location("backup", Path(__file__).parents[1] / "scripts/backup.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
sys.modules["backup"] = b
restore_spec = importlib.util.spec_from_file_location("restore_verify", Path(__file__).parents[1] / "scripts/restore_verify.py")
r = importlib.util.module_from_spec(restore_spec)
restore_spec.loader.exec_module(r)

SQL = (b"-- MySQL dump\nCREATE TABLE `records` (\n  `id` int NOT NULL,\n"
       b"  PRIMARY KEY (`id`)\n) ENGINE=InnoDB;\n"
       b"INSERT INTO `records` VALUES (1);\nINSERT INTO `records` VALUES (2);\n"
       b"-- Dump completed on 2026-11-15 12:00:00\n")


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.cfg = {key: str(self.root / key) for key in ("app_dir", "backup_root", "state_dir", "runtime_dir")}
        for directory in self.cfg.values():
            Path(directory).mkdir()
        self.input = self.root / "settings.txt"
        self.input.write_text("test config")
        self.cfg.update(database="dedicated_line", config_paths=[str(self.input)], min_free_bytes=0, max_age_hours=30)
        self.dump = self.root / "test.sql.gz"
        self.write_dump(SQL)

    def write_dump(self, value, path=None):
        with gzip.open(path or self.dump, "wb") as out:
            out.write(value)

    def run_good_backup(self, effect=None):
        def fake_dump(cnf, name, target):
            self.write_dump(SQL, target)
        with patch.object(b, "credentials", return_value={"database": "dedicated_line"}), \
             patch.object(b, "inventory", return_value=["records"]), \
             patch.object(b, "dump_database", side_effect=effect or fake_dump), \
             patch.object(b, "log"):
            return b.do_backup(self.cfg)

    def test_dump_fingerprints_and_rows(self):
        self.assertEqual(b.inspect_dump(self.dump)["records"]["rows"], 2)

    def test_empty_gzip_rejected(self):
        self.write_dump(b"")
        with self.assertRaises(b.BackupError):
            b.inspect_dump(self.dump)

    def test_missing_footer_rejected(self):
        self.write_dump(SQL.split(b"-- Dump completed")[0])
        with self.assertRaises(b.BackupError):
            b.inspect_dump(self.dump)

    def test_truncated_gzip_rejected(self):
        self.dump.write_bytes(self.dump.read_bytes()[:-7])
        with self.assertRaises((EOFError, OSError)):
            b.inspect_dump(self.dump)

    def test_extra_sql_after_footer_rejected(self):
        self.write_dump(SQL + b"SELECT 1;\n")
        with self.assertRaises(b.BackupError):
            b.inspect_dump(self.dump)

    def test_production_database_switch_rejected(self):
        self.write_dump(b"USE dedicated_line;\n" + SQL)
        with self.assertRaises(b.BackupError):
            b.inspect_dump(self.dump)

    def test_duplicate_table_rejected(self):
        self.write_dump(SQL + SQL)
        with self.assertRaises(b.BackupError):
            b.inspect_dump(self.dump)

    def test_oversized_line_rejected(self):
        with patch.object(b, "MAX_LINE", 10):
            with self.assertRaises(b.BackupError):
                b.inspect_dump(self.dump)

    def test_changed_value_changes_fingerprint(self):
        before = b.inspect_dump(self.dump)
        self.write_dump(SQL.replace(b"VALUES (2)", b"VALUES (3)"))
        self.assertNotEqual(before, b.inspect_dump(self.dump))

    def test_empty_table_is_valid(self):
        self.write_dump(b"\n".join(line for line in SQL.split(b"\n") if not line.startswith(b"INSERT INTO")))
        self.assertEqual(b.inspect_dump(self.dump)["records"]["rows"], 0)

    def test_success_publishes_verified_backup(self):
        result = self.run_good_backup()
        run = Path(result["run"])
        self.assertEqual(b.verify_run(run)["tables"]["records"]["rows"], 2)
        self.assertEqual((Path(self.cfg["backup_root"]) / "latest").resolve(), run)
        self.assertEqual((run.stat().st_mode & 0o777), 0o700)

    def test_failure_does_not_replace_latest_or_delete_old_backup(self):
        first = self.run_good_backup()
        old = Path(first["run"])
        original = b.digest(old / "database.sql.gz")
        os.utime(old, (1, 1))
        with self.assertRaises(b.BackupError):
            self.run_good_backup(b.BackupError("injected-dump-failure"))
        self.assertEqual((Path(self.cfg["backup_root"]) / "latest").resolve(), old)
        self.assertEqual(b.digest(old / "database.sql.gz"), original)
        partials = list(Path(self.cfg["backup_root"]).glob(".partial-*/FAILED.json"))
        self.assertEqual(len(partials), 1)

    def test_low_disk_rejects_before_dump(self):
        self.cfg["min_free_bytes"] = 10**30
        with self.assertRaisesRegex(b.BackupError, "insufficient-disk-space"):
            self.run_good_backup()
        self.assertFalse((Path(self.cfg["backup_root"]) / "latest").exists())

    def test_non_symlink_latest_is_not_overwritten(self):
        latest = Path(self.cfg["backup_root"]) / "latest"
        latest.write_text("keep me")
        with self.assertRaisesRegex(b.BackupError, "latest-is-not-symlink"):
            self.run_good_backup()
        self.assertEqual(latest.read_text(), "keep me")

    def test_corrupt_backup_rejected_by_checksum(self):
        run = Path(self.run_good_backup()["run"])
        with (run / "database.sql.gz").open("ab") as out:
            out.write(b"corruption")
        with self.assertRaises(b.BackupError):
            b.verify_run(run)

    def test_manifest_traversal_rejected(self):
        run = Path(self.run_good_backup()["run"])
        meta = json.loads((run / "manifest.json").read_text())
        meta["files"]["../../elsewhere"] = meta["files"].pop("database.sql.gz")
        b.atomic_json(run / "manifest.json", meta)
        with self.assertRaises(b.BackupError):
            b.verify_run(run)

    def test_watchdog_success(self):
        self.run_good_backup()
        with patch.object(b.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)), patch.object(b, "log"):
            b.check_freshness(self.cfg)

    def test_watchdog_stale(self):
        self.run_good_backup()
        path = Path(self.cfg["state_dir"]) / "last_success.json"
        value = json.loads(path.read_text())
        value["time"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=31)).isoformat()
        b.atomic_json(path, value)
        with self.assertRaisesRegex(b.BackupError, "expired"):
            b.check_freshness(self.cfg)

    def test_watchdog_failed_attempt(self):
        self.run_good_backup()
        b.atomic_json(Path(self.cfg["state_dir"]) / "status.json", {"status": "failed", "time": b.now()})
        with self.assertRaisesRegex(b.BackupError, "last-backup-attempt-failed"):
            b.check_freshness(self.cfg)

    def test_watchdog_disabled_timer(self):
        self.run_good_backup()
        with patch.object(b.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaisesRegex(b.BackupError, "timer-disabled"):
                b.check_freshness(self.cfg)

    def test_watchdog_inactive_timer(self):
        self.run_good_backup()
        with patch.object(b.subprocess, "run", side_effect=[subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 3)]):
            with self.assertRaisesRegex(b.BackupError, "inactive"):
                b.check_freshness(self.cfg)

    def test_concurrent_backup_rejected(self):
        import fcntl
        with (Path(self.cfg["state_dir"]) / "backup.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(b.BackupError, "already-running"):
                self.run_good_backup()

    def test_missing_config_archive_not_published(self):
        self.input.unlink()
        with self.assertRaisesRegex(b.BackupError, "missing-config"):
            self.run_good_backup()
        self.assertFalse((Path(self.cfg["backup_root"]) / "latest").exists())

    def test_schema_mismatch_not_published(self):
        def different(cnf, name, target):
            self.write_dump(SQL.replace(b"`records`", b"`wrong`"), target)
        with self.assertRaisesRegex(b.BackupError, "inventory-mismatch"):
            self.run_good_backup(different)
        self.assertFalse((Path(self.cfg["backup_root"]) / "latest").exists())

    def test_alert_survives_state_disk_write_failure(self):
        original = b.atomic_json
        def fail_state(path, data):
            if str(path).startswith(self.cfg["state_dir"]):
                raise OSError("disk full")
            return original(path, data)
        with patch.object(b, "atomic_json", side_effect=fail_state), patch.object(b, "log"):
            b.alert(self.cfg, "test-failure")
        self.assertTrue((Path(self.cfg["runtime_dir"]) / "ALERT.json").exists())

    def test_success_clears_own_alert_only(self):
        with patch.object(b, "log"):
            b.alert(self.cfg, "test")
        self.run_good_backup()
        self.assertFalse((Path(self.cfg["state_dir"]) / "ALERT.json").exists())

    def test_client_password_not_in_commandline(self):
        creds = {"host": "127.0.0.1", "user": "test", "password": 'quotes"\\ and spaces\n'}
        with b.client_file(self.cfg["runtime_dir"], creds) as path:
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn('password="quotes\\"\\\\ and spaces\\n"', path.read_text())
            saved = path
        self.assertFalse(saved.exists())

    def test_dump_exit_status_checked_even_if_gzip_valid(self):
        proc = MagicMock()
        proc.__enter__.return_value = proc
        proc.stdout = io.BytesIO(b"")
        proc.wait.return_value = 2
        with patch.object(b.subprocess, "Popen", return_value=proc):
            with self.assertRaisesRegex(b.BackupError, "nonzero-exit"):
                b.dump_database(Path("/private/client.cnf"), "dedicated_line", self.root / "bad.sql.gz")

    def restore_identity(self):
        (self.root / "data").mkdir()
        (self.root / "run").mkdir()
        (self.root / "data/auto.cnf").write_text("[auto]\nserver-uuid=test-instance\n")
        (self.root / "run/mysqld.pid").write_text("99999\n")

    def test_restore_rejects_network_enabled_instance(self):
        self.restore_identity()
        with self.assertRaisesRegex(b.BackupError, "identity-mismatch"):
            r.guard_target(self.root, str(self.root / "data"), False, "test-instance")

    def test_restore_rejects_production_uuid(self):
        self.restore_identity()
        with self.assertRaisesRegex(b.BackupError, "identity-mismatch"):
            r.guard_target(self.root, "/var/lib/mysql/", True, "production-instance")

    def test_restore_accepts_private_direct_datadir(self):
        self.restore_identity()
        r.guard_target(self.root, str(self.root / "data"), True, "test-instance")

    def mount_guard(self, correct):
        original = Path.read_text
        mounts = "\n".join(f"1 2 252:0 {self.root / src if correct else '/var/lib/mysql'} {dest} rw - ext4 /dev/dm0 rw"
                           for dest, src in (("/var/lib/mysql", "data"), ("/run/mysqld", "run"), ("/var/log/mysql", "logs")))
        def read(path, *args, **kwargs):
            if str(path) == "/proc/99999/mountinfo":
                return mounts
            return original(path, *args, **kwargs)
        return patch.object(Path, "read_text", read)

    def test_restore_accepts_verified_private_mounts(self):
        self.restore_identity()
        with self.mount_guard(True):
            r.guard_target(self.root, "/var/lib/mysql/", True, "test-instance")

    def test_restore_rejects_production_mount(self):
        self.restore_identity()
        with self.mount_guard(False):
            with self.assertRaisesRegex(b.BackupError, "private-mount-mismatch"):
                r.guard_target(self.root, "/var/lib/mysql/", True, "test-instance")


if __name__ == "__main__":
    unittest.main(verbosity=2)
