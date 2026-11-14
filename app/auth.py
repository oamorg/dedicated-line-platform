from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

PBKDF2_ITERATIONS = int(os.getenv("PBKDF2_ITERATIONS", "240000"))
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "12"))

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iter_text, salt, expected_hex = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iter_text)
    except ValueError:
        return False

    computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
    return hmac.compare_digest(computed, expected_hex)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _get_roles(db: Session, user_id: int) -> list[str]:
    sql = text(
        """
        SELECT r.name
        FROM auth_roles r
        JOIN auth_user_roles ur ON ur.role_id = r.id
        WHERE ur.user_id = :user_id
        ORDER BY r.name
        """
    )
    rows = db.execute(sql, {"user_id": user_id}).all()
    return [str(row[0]) for row in rows]


def _get_permissions(db: Session, user_id: int) -> list[str]:
    sql = text(
        """
        SELECT DISTINCT p.code
        FROM auth_permissions p
        JOIN auth_role_permissions rp ON rp.permission_id = p.id
        JOIN auth_user_roles ur ON ur.role_id = rp.role_id
        WHERE ur.user_id = :user_id
        ORDER BY p.code
        """
    )
    rows = db.execute(sql, {"user_id": user_id}).all()
    return [str(row[0]) for row in rows]


def get_user_profile(db: Session, user_id: int) -> Optional[dict[str, Any]]:
    user_sql = text(
        """
        SELECT id, username, display_name, is_active
        FROM auth_users
        WHERE id = :user_id
        """
    )
    user_row = db.execute(user_sql, {"user_id": user_id}).mappings().first()
    if not user_row:
        return None
    if int(user_row["is_active"]) != 1:
        return None

    return {
        "id": int(user_row["id"]),
        "username": str(user_row["username"]),
        "display_name": str(user_row["display_name"] or user_row["username"]),
        "roles": _get_roles(db, int(user_row["id"])),
        "permissions": _get_permissions(db, int(user_row["id"])),
    }


def authenticate_user(db: Session, username: str, password: str) -> Optional[dict[str, Any]]:
    sql = text(
        """
        SELECT id, username, display_name, password_hash, is_active
        FROM auth_users
        WHERE username = :username
        LIMIT 1
        """
    )
    row = db.execute(sql, {"username": username}).mappings().first()
    if not row:
        return None
    if int(row["is_active"]) != 1:
        return None
    if not verify_password(password, str(row["password_hash"])):
        return None

    user_id = int(row["id"])
    return get_user_profile(db, user_id)


def create_session(
    db: Session,
    user_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> tuple[str, datetime]:
    now = datetime.now()
    db.execute(text("DELETE FROM auth_sessions WHERE expires_at <= :now"), {"now": now})

    raw_token = secrets.token_urlsafe(48)
    token_digest = hash_token(raw_token)
    expires_at = now + timedelta(hours=SESSION_TTL_HOURS)
    sql = text(
        """
        INSERT INTO auth_sessions (user_id, token_hash, ip_address, user_agent, expires_at)
        VALUES (:user_id, :token_hash, :ip_address, :user_agent, :expires_at)
        """
    )
    db.execute(
        sql,
        {
            "user_id": user_id,
            "token_hash": token_digest,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "expires_at": expires_at,
        },
    )
    return raw_token, expires_at


def revoke_session(db: Session, raw_token: str) -> None:
    now = datetime.now()
    sql = text(
        """
        UPDATE auth_sessions
        SET revoked_at = :now
        WHERE token_hash = :token_hash AND revoked_at IS NULL
        """
    )
    db.execute(sql, {"token_hash": hash_token(raw_token), "now": now})


def revoke_session_by_id(db: Session, session_id: int) -> int:
    result = db.execute(
        text(
            """
            UPDATE auth_sessions
            SET revoked_at = :now
            WHERE id = :session_id
              AND revoked_at IS NULL
            """
        ),
        {
            "session_id": session_id,
            "now": datetime.now(),
        },
    )
    return int(result.rowcount or 0)


def revoke_sessions_for_user(db: Session, user_id: int, exclude_session_id: Optional[int] = None) -> int:
    sql = """
        UPDATE auth_sessions
        SET revoked_at = :now
        WHERE user_id = :user_id
          AND revoked_at IS NULL
    """
    params: dict[str, Any] = {
        "user_id": user_id,
        "now": datetime.now(),
    }
    if exclude_session_id is not None:
        sql += " AND id <> :exclude_session_id"
        params["exclude_session_id"] = exclude_session_id

    result = db.execute(text(sql), params)
    return int(result.rowcount or 0)


def resolve_user_by_token(db: Session, raw_token: str) -> Optional[dict[str, Any]]:
    token_digest = hash_token(raw_token)
    now = datetime.now()
    sql = text(
        """
        SELECT id, user_id, expires_at
        FROM auth_sessions
        WHERE token_hash = :token_hash
          AND revoked_at IS NULL
          AND expires_at > :now
        LIMIT 1
        """
    )
    session_row = db.execute(sql, {"token_hash": token_digest, "now": now}).mappings().first()
    if not session_row:
        return None

    profile = get_user_profile(db, int(session_row["user_id"]))
    if not profile:
        return None
    profile["session_id"] = int(session_row["id"])
    profile["session_expires_at"] = session_row["expires_at"]
    return profile


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已失效",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = resolve_user_by_token(db, credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已失效",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_permission(permission_code: str):
    def checker(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        permissions = set(current_user.get("permissions", []))
        if permission_code not in permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"缺少权限: {permission_code}")
        return current_user

    return checker
