#!/usr/bin/env python3
"""Apply the project's SQL files to an explicitly configured database."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def statements(path: Path):
    current = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("--"):
            continue
        current.append(line)
        if line.rstrip().endswith(";"):
            yield "\n".join(current)
            current = []
    if current:
        raise ValueError(f"Unterminated SQL in {path.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    url = os.environ.get("DATABASE_URL", "")
    if not url or "CHANGE_ME" in url:
        parser.error("Set DATABASE_URL in .env before initialization")
    if make_url(url).get_backend_name() != "mysql":
        parser.error("Initialization requires a MySQL database")
    files = args.files or sorted((ROOT / "sql").glob("*.sql"))
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            for path in files:
                print(f"Applying {path.name}")
                for statement in statements(path):
                    conn.exec_driver_sql(statement)
            conn.execute(text("SELECT 1"))
    finally:
        engine.dispose()
    print("Database initialization complete; no administrator is seeded")


if __name__ == "__main__":
    main()
