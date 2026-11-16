#!/usr/bin/env python3
"""Restore only to an already running, private, network-disabled test instance."""
import argparse
import configparser
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import backup as b


def schema_fingerprints(path):
    """Normalize only a redundant UTF-8 declaration in a column type prefix."""
    redundant = re.compile(
        rb'^(  `[^`]+` (?:char\(\d+\)|varchar\(\d+\)|(?:tiny|medium|long)?text))'
        rb' CHARACTER SET utf8mb4( COLLATE utf8mb4_unicode_ci)(?= |,|\n)')
    tables, current = {}, None
    with gzip.open(path, 'rb') as src:
        while True:
            line = src.readline(b.MAX_LINE + 1)
            if not line: break
            if len(line) > b.MAX_LINE: raise b.BackupError('sql-line-too-large')
            match = b.CREATE.match(line)
            if match:
                current = match[1].decode('ascii')
                tables[current] = hashlib.sha256()
            if current is not None:
                tables[current].update(redundant.sub(rb'\1\2', line))
                if line.rstrip().endswith(b';'): current = None
    return {name: value.hexdigest() for name, value in tables.items()}


def compare_restore(source, restored_path, expected, restored, counts):
    if set(expected) != set(restored) or set(counts) != set(expected):
        raise b.BackupError('restored-table-inventory-mismatch')
    if any(restored[name]['data_sha256'] != value['data_sha256'] or
           restored[name]['rows'] != value['rows'] or counts[name] != value['rows']
           for name, value in expected.items()):
        raise b.BackupError('restored-data-or-count-mismatch')
    raw_equal = all(restored[name]['schema_sha256'] == value['schema_sha256'] for name, value in expected.items())
    if schema_fingerprints(source) != schema_fingerprints(restored_path):
        raise b.BackupError('restored-schema-mismatch')
    return {'all_schema_and_data_sha256_equal': raw_equal, 'all_data_sha256_equal': True,
            'all_normalized_schema_sha256_equal': True,
            'redundant_charset_declaration_tables': [name for name in expected
                if expected[name]['schema_sha256'] != restored[name]['schema_sha256']]}


def guard_target(base, datadir, isolated, server_uuid):
    identity = configparser.ConfigParser()
    identity.read(base / "data/auto.cnf")
    if not isolated or server_uuid != identity.get("auto", "server-uuid"):
        raise b.BackupError("restore-target-identity-mismatch")
    if Path(datadir).resolve() == base / "data":
        return
    if Path(datadir) != Path("/var/lib/mysql"):
        raise b.BackupError("restore-target-not-isolated")
    pid = int((base / "run/mysqld.pid").read_text().strip())
    mounts = {fields[4]: fields[3] for line in Path(f"/proc/{pid}/mountinfo").read_text().splitlines()
              if len(fields := line.split()) >= 6}
    for destination, source in (("/var/lib/mysql", "data"), ("/run/mysqld", "run"), ("/var/log/mysql", "logs")):
        if mounts.get(destination) != str(base / source):
            raise b.BackupError("restore-private-mount-mismatch")


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--sandbox", required=True)
    parser.add_argument("--database", default="dl_restore_validation")
    args = parser.parse_args()
    base = Path(args.sandbox).resolve()
    if base.parent != Path("/var/lib") or not base.name.startswith("dedicated-line-restore-"):
        raise b.BackupError("invalid-restore-sandbox")
    if not b.NAME.fullmatch(args.database) or not args.database.startswith("dl_restore_"):
        raise b.BackupError("invalid-restore-database-name")
    import pymysql
    creds = {"unix_socket": str(base / "run/mysqld.sock"), "user": "root", "password": "",
             "charset": "utf8mb4", "connect_timeout": 5, "read_timeout": 120, "autocommit": True}
    meta = b.verify_run(args.run)
    started = time.monotonic()
    with pymysql.connect(**creds) as connection:
        with connection.cursor() as cur:
            cur.execute("SELECT @@datadir, @@skip_networking, @@server_uuid")
            datadir, isolated, server_uuid = cur.fetchone()
            guard_target(base, datadir, isolated, server_uuid)
            cur.execute("SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (args.database,))
            if cur.fetchone()[0]:
                raise b.BackupError("restore-database-already-exists")
            cur.execute(f"CREATE DATABASE `{args.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    socket_creds = {"socket": creds["unix_socket"], "user": "root", "password": ""}
    with b.client_file(base / "run", socket_creds) as cnf:
        with (base / "restore.stderr").open("xb") as errors:
            with subprocess.Popen(["/usr/bin/mysql", f"--defaults-file={cnf}", "--binary-mode=1",
                                   "--local-infile=0", args.database], stdin=subprocess.PIPE,
                                  stdout=subprocess.DEVNULL, stderr=errors) as proc:
                try:
                    with gzip.open(Path(args.run) / "database.sql.gz", "rb") as src:
                        for chunk in iter(lambda: src.read(128 * 1024), b""):
                            proc.stdin.write(chunk)
                            time.sleep(0.025)
                    proc.stdin.close()
                    if proc.wait(timeout=600) != 0:
                        raise b.BackupError("restore-client-nonzero-exit")
                except BaseException:
                    proc.kill()
                    proc.wait()
                    raise
        if (base / "restore.stderr").stat().st_size:
            raise b.BackupError("restore-client-reported-diagnostic")
        b.dump_database(cnf, args.database, base / "restored.sql.gz")
    restored = b.inspect_dump(base / "restored.sql.gz")
    counts = {}
    with pymysql.connect(**creds, database=args.database) as connection:
        with connection.cursor() as cur:
            for table in meta["tables"]:
                if not b.NAME.fullmatch(table):
                    raise b.BackupError("invalid-table-name")
                cur.execute(f"SELECT COUNT(*) FROM `{table}`")
                counts[table] = cur.fetchone()[0]
    comparison = compare_restore(Path(args.run) / 'database.sql.gz', base / 'restored.sql.gz',
                                 meta['tables'], restored, counts)
    report = {"status": "passed", "time": b.now(), "duration_seconds": round(time.monotonic() - started, 2),
              "source_run": str(Path(args.run).resolve()), "test_server_uuid": server_uuid,
              "isolated_datadir": str(base / "data"), "network_disabled": True,
              "database": args.database, "table_count": len(counts), "row_counts": counts,
              **comparison}
    b.atomic_json(base / "restore-report.json", report)
    print(json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
