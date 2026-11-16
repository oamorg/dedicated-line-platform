#!/usr/bin/env python3
from __future__ import annotations

import argparse
from getpass import getpass
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.auth import hash_password, revoke_sessions_for_user


def ensure_role(conn, role_name: str) -> int:
    role_row = conn.execute(
        text("SELECT id FROM auth_roles WHERE name = :role_name LIMIT 1"),
        {"role_name": role_name},
    ).mappings().first()
    if not role_row:
        raise ValueError(f"role not found: {role_name}")
    return int(role_row["id"])


def create_user(conn, username: str, password: str, display_name: str, role_name: str) -> None:
    role_id = ensure_role(conn, role_name)
    user_row = conn.execute(
        text("SELECT id FROM auth_users WHERE username = :username LIMIT 1"),
        {"username": username},
    ).mappings().first()
    if user_row:
        raise ValueError(f"user already exists: {username}")

    password_hash = hash_password(password)
    result = conn.execute(
        text(
            """
            INSERT INTO auth_users (username, display_name, password_hash, is_active)
            VALUES (:username, :display_name, :password_hash, 1)
            """
        ),
        {
            "username": username,
            "display_name": display_name,
            "password_hash": password_hash,
        },
    )
    user_id = int(result.lastrowid)
    conn.execute(
        text("INSERT INTO auth_user_roles (user_id, role_id) VALUES (:user_id, :role_id)"),
        {"user_id": user_id, "role_id": role_id},
    )


def set_role(conn, username: str, role_name: str) -> None:
    role_id = ensure_role(conn, role_name)
    user_row = conn.execute(
        text("SELECT id FROM auth_users WHERE username = :username LIMIT 1"),
        {"username": username},
    ).mappings().first()
    if not user_row:
        raise ValueError(f"user not found: {username}")

    user_id = int(user_row["id"])
    conn.execute(text("DELETE FROM auth_user_roles WHERE user_id = :user_id"), {"user_id": user_id})
    conn.execute(
        text("INSERT INTO auth_user_roles (user_id, role_id) VALUES (:user_id, :role_id)"),
        {"user_id": user_id, "role_id": role_id},
    )


def reset_password(conn, username: str, new_password: str) -> None:
    user_row = conn.execute(
        text("SELECT id FROM auth_users WHERE username = :username LIMIT 1"),
        {"username": username},
    ).mappings().first()
    if not user_row:
        raise ValueError(f"user not found: {username}")

    conn.execute(
        text(
            """
            UPDATE auth_users
            SET password_hash = :password_hash
            WHERE username = :username
            """
        ),
        {"password_hash": hash_password(new_password), "username": username},
    )
    revoke_sessions_for_user(conn, int(user_row["id"]))


def list_users(conn) -> None:
    rows = conn.execute(
        text(
            """
            SELECT
              u.username,
              u.display_name,
              u.is_active,
              GROUP_CONCAT(r.name ORDER BY r.name SEPARATOR ', ') AS roles
            FROM auth_users u
            LEFT JOIN auth_user_roles ur ON ur.user_id = u.id
            LEFT JOIN auth_roles r ON r.id = ur.role_id
            GROUP BY u.id, u.username, u.display_name, u.is_active
            ORDER BY u.username
            """
        )
    ).mappings().all()

    if not rows:
        print("no users")
        return
    for row in rows:
        print(
            f"username={row['username']}, display_name={row['display_name']}, "
            f"active={row['is_active']}, roles={row['roles'] or '-'}"
        )


def read_password(value: str | None) -> str:
    password = value if value is not None else getpass("Password: ")
    if value is None and password != getpass("Confirm password: "):
        raise ValueError("passwords do not match")
    if len(password) < 12 or len(password) > 128:
        raise ValueError("password must contain 12 to 128 characters")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage auth users and roles.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_create = subparsers.add_parser("create-user", help="Create a user and assign role")
    p_create.add_argument("--username", required=True)
    p_create.add_argument("--password", help="Omit for a hidden interactive prompt")
    p_create.add_argument("--display-name", required=True)
    p_create.add_argument("--role", required=True, choices=["viewer", "exporter", "admin"])

    p_set = subparsers.add_parser("set-role", help="Replace user role")
    p_set.add_argument("--username", required=True)
    p_set.add_argument("--role", required=True, choices=["viewer", "exporter", "admin"])

    p_reset = subparsers.add_parser("reset-password", help="Reset password")
    p_reset.add_argument("--username", required=True)
    p_reset.add_argument("--password", help="Omit for a hidden interactive prompt")

    subparsers.add_parser("list-users", help="List users")
    subparsers.add_parser("prune-login-limits", help="Remove budgets and IP blocks expired for more than one day")

    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    database_url = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://dedicated_line@127.0.0.1:3306/dedicated_line?charset=utf8mb4",
    )
    engine = create_engine(database_url, future=True, pool_pre_ping=True)

    if args.command in {"create-user", "reset-password"}:
        try:
            args.password = read_password(args.password)
        except ValueError as exc:
            parser.error(str(exc))

    with engine.begin() as conn:
        if args.command == "create-user":
            create_user(conn, args.username, args.password, args.display_name, args.role)
            print(f"created user: {args.username}, role={args.role}")
        elif args.command == "set-role":
            set_role(conn, args.username, args.role)
            print(f"updated role: {args.username} -> {args.role}")
        elif args.command == "reset-password":
            reset_password(conn, args.username, args.password)
            print(f"password reset done: {args.username}")
        elif args.command == "list-users":
            list_users(conn)
        elif args.command == "prune-login-limits":
            result = conn.execute(text("DELETE FROM auth_login_limits WHERE reset_at < :cutoff"), {"cutoff": int(time.time()) - 86400})
            print(f"removed expired login budgets: {result.rowcount}")
            blocks = conn.execute(text("DELETE FROM auth_ip_blocks WHERE expires_at < :cutoff"), {"cutoff": int(time.time()) - 86400})
            print(f"removed expired IP blocks: {blocks.rowcount}")


if __name__ == "__main__":
    main()
