from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import (
    authenticate_user,
    bearer_scheme,
    create_session,
    get_current_user,
    hash_password,
    require_permission,
    revoke_session,
    revoke_session_by_id,
    revoke_sessions_for_user,
)
from app.db import get_db

app = FastAPI(
    title="政企集客业务数据中心 API",
    description="政企专线与ONU资源设备查询服务（MySQL）",
    version="1.0.0",
)

BASE_DIR = Path(__file__).resolve().parents[1]
WEB_DIR = BASE_DIR / "web"
IMPORT_SCRIPT = BASE_DIR / "scripts" / "import_excel.py"
IMPORT_LOG_DIR = BASE_DIR / "logs" / "imports"
DEFAULT_IMPORT_DATA_DIR = Path(os.getenv("IMPORT_DATA_DIR", str(BASE_DIR / "data" / "excel")))
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

require_query_permission = require_permission("data.query")
require_export_permission = require_permission("data.export")
require_admin_permission = require_permission("user.manage")


class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class AdminUserCreatePayload(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=12, max_length=128)
    role: str = Field(min_length=1, max_length=64)


class AdminUserUpdatePayload(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=128)
    role: Optional[str] = Field(None, min_length=1, max_length=64)
    is_active: Optional[bool] = None


class AdminPasswordResetPayload(BaseModel):
    password: str = Field(min_length=12, max_length=128)


class AdminImportRunPayload(BaseModel):
    dry_run: bool = False
    init_schema: bool = False
    batch_name: Optional[str] = Field(None, max_length=128)


class AdminSessionRevokePayload(BaseModel):
    reason: Optional[str] = Field(None, max_length=255)


def _row_to_dict(row: Any) -> dict[str, Any]:
    data = dict(row)
    raw = data.get("raw_data")
    if isinstance(raw, str):
        try:
            data["raw_data"] = json.loads(raw)
        except json.JSONDecodeError:
            data["raw_data"] = raw
    return data


def _split_csv(value: Any) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in str(value).split(",") if item and item.strip()]


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _request_user_agent(request: Request) -> str:
    return request.headers.get("user-agent", "").strip()


def _serialize_admin_user(row: Any) -> dict[str, Any]:
    data = dict(row)
    data["roles"] = _split_csv(data.get("roles"))
    data["active_sessions"] = int(data.get("active_sessions") or 0)
    data["is_active"] = bool(data.get("is_active"))
    return data


def _serialize_admin_log(row: Any) -> dict[str, Any]:
    data = dict(row)
    detail = data.get("detail_json")
    if isinstance(detail, str):
        try:
            data["detail_json"] = json.loads(detail)
        except json.JSONDecodeError:
            pass
    return data


def _normalize_display_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        text_value = value.strip()
        return text_value if text_value else None
    return value


def _first_present(*values: Any) -> Any:
    for value in values:
        normalized = _normalize_display_value(value)
        if normalized is not None:
            return normalized
    return None


def _raw_lookup(raw_data: Any, *keys: str) -> Any:
    if not isinstance(raw_data, dict):
        return None
    for key in keys:
        if key not in raw_data:
            continue
        normalized = _normalize_display_value(raw_data.get(key))
        if normalized is not None:
            return normalized
    return None


def _serialize_line_list_row(row: Any) -> dict[str, Any]:
    data = _row_to_dict(row)
    raw_data = data.get("raw_data")
    is_ipvpn = data.get("source_type") == "IPVPN专线"
    user_ip_keys = ("自带客户端互联IP", "用户地址") if is_ipvpn else ("用户地址", "自带客户端互联IP")
    gateway_ip_keys = ("自带局端互联IP", "网关地址") if is_ipvpn else ("网关地址", "自带局端互联IP")

    return {
        "id": data.get("id"),
        "source_type": data.get("source_type"),
        "area": data.get("area"),
        "customer_name": data.get("customer_name"),
        "product_type": data.get("product_type"),
        "product_number": data.get("product_number"),
        "access_method": data.get("access_method"),
        "bandwidth": data.get("bandwidth"),
        "open_time": data.get("open_time"),
        "order_no": data.get("order_no"),
        "assurance_level": data.get("assurance_level"),
        "olt_port_name": data.get("olt_port_name"),
        "splitter_name": _raw_lookup(raw_data, "接入分光器"),
        "user_address": _raw_lookup(raw_data, *user_ip_keys),
        "gateway_address": _raw_lookup(raw_data, *gateway_ip_keys),
        "building_name": data.get("building_name"),
        "onu_port_name": data.get("onu_port_name"),
        "a_end_transport_device_name": _first_present(
            _raw_lookup(raw_data, "A端传输设备名称"),
            data.get("onu_device_name"),
        ),
        "z_end_transport_device_name": _raw_lookup(raw_data, "Z端传输设备名称"),
        "transmission_circuit_display": _first_present(
            data.get("transmission_circuit_name"),
            _raw_lookup(raw_data, "电路名称", "传输电路名称", "传输电路路由"),
        ),
        "related_city": data.get("related_city"),
    }


def _line_export_columns(source_type: Optional[str]) -> list[tuple[str, str]]:
    if source_type in {"互联网专线", "IPVPN专线", "多媒体语音专线"}:
        return [
            ("区域", "area"),
            ("客户名称", "customer_name"),
            ("产品类型", "product_type"),
            ("产品号码", "product_number"),
            ("传输接入方式", "access_method"),
            ("OLT端口名称", "olt_port_name"),
            ("接入分光器", "splitter_name"),
            ("IP地址", "user_address"),
            ("网关地址", "gateway_address"),
        ]
    if source_type == "商务快线":
        return [
            ("区域", "area"),
            ("客户名称", "customer_name"),
            ("产品类型", "product_type"),
            ("产品号码", "product_number"),
            ("传输接入方式", "access_method"),
            ("OLT端口名称", "olt_port_name"),
            ("接入分光器", "splitter_name"),
            ("楼宇名称", "building_name"),
            ("传输设备或ONU端口", "onu_port_name"),
        ]
    if source_type == "传输专线":
        return [
            ("区域", "area"),
            ("客户名称", "customer_name"),
            ("产品类型", "product_type"),
            ("产品号码", "product_number"),
            ("传输接入方式", "access_method"),
            ("A端传输设备名称", "a_end_transport_device_name"),
            ("Z端传输设备名称", "z_end_transport_device_name"),
            ("电路名称", "transmission_circuit_display"),
            ("业务相关地市", "related_city"),
        ]
    return [
        ("区域", "area"),
        ("客户名称", "customer_name"),
        ("产品类型", "product_type"),
        ("产品号码", "product_number"),
        ("业务带宽", "bandwidth"),
        ("传输接入方式", "access_method"),
        ("开通时间", "open_time"),
        ("服开工单号", "order_no"),
        ("业务保障等级", "assurance_level"),
    ]


def _serialize_line_export_row(row: Any, source_type: Optional[str]) -> dict[str, Any]:
    data = _serialize_line_list_row(row)
    export_row: dict[str, Any] = {}
    for label, key in _line_export_columns(source_type):
        export_row[label] = data.get(key)
    return export_row


def _serialize_onu_list_row(row: Any) -> dict[str, Any]:
    data = _row_to_dict(row)
    return {
        "id": data.get("id"),
        "onuid": data.get("onuid"),
        "client_county": data.get("client_county"),
        "customer_name": data.get("customer_name"),
        "service_type": data.get("service_type"),
        "product_number": data.get("product_number"),
        "onu_vendor": data.get("onu_vendor"),
        "model": data.get("model"),
        "sn_code": data.get("sn_code"),
        "onu_password": data.get("onu_password"),
        "onu_name": data.get("onu_name"),
    }


def _serialize_onu_export_row(row: Any) -> dict[str, Any]:
    data = _serialize_onu_list_row(row)
    return {
        "区县": data.get("client_county"),
        "客户名称": data.get("customer_name"),
        "业务类型": data.get("service_type"),
        "产品号码": data.get("product_number"),
        "厂家": data.get("onu_vendor"),
        "型号": data.get("model"),
        "SN码": data.get("sn_code"),
        "ONU密码": data.get("onu_password"),
        "ONU名称": data.get("onu_name"),
    }


def _get_role_id(db: Session, role_name: str) -> int:
    row = db.execute(
        text("SELECT id FROM auth_roles WHERE name = :role_name LIMIT 1"),
        {"role_name": role_name},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=400, detail=f"无效角色: {role_name}")
    return int(row["id"])


def _count_active_admins(db: Session) -> int:
    sql = text(
        """
        SELECT COUNT(DISTINCT u.id) AS total
        FROM auth_users u
        JOIN auth_user_roles ur ON ur.user_id = u.id
        JOIN auth_roles r ON r.id = ur.role_id
        WHERE r.name = 'admin'
          AND u.is_active = 1
        """
    )
    return int(db.execute(sql).scalar_one() or 0)


def _get_admin_user(db: Session, user_id: int) -> Optional[dict[str, Any]]:
    sql = text(
        """
        SELECT
          u.id,
          u.username,
          u.display_name,
          u.is_active,
          u.created_at,
          u.updated_at,
          GROUP_CONCAT(DISTINCT r.name ORDER BY r.name SEPARATOR ',') AS roles,
          COUNT(DISTINCT CASE WHEN s.revoked_at IS NULL AND s.expires_at > :now THEN s.id END) AS active_sessions
        FROM auth_users u
        LEFT JOIN auth_user_roles ur ON ur.user_id = u.id
        LEFT JOIN auth_roles r ON r.id = ur.role_id
        LEFT JOIN auth_sessions s ON s.user_id = u.id
        WHERE u.id = :user_id
        GROUP BY u.id, u.username, u.display_name, u.is_active, u.created_at, u.updated_at
        """
    )
    row = db.execute(sql, {"user_id": user_id, "now": datetime.now()}).mappings().first()
    if not row:
        return None
    return _serialize_admin_user(row)


def _revoke_user_sessions(db: Session, user_id: int) -> None:
    db.execute(
        text(
            """
            UPDATE auth_sessions
            SET revoked_at = :revoked_at
            WHERE user_id = :user_id
              AND revoked_at IS NULL
            """
        ),
        {
            "user_id": user_id,
            "revoked_at": datetime.now(),
        },
    )


def _log_admin_action(
    db: Session,
    actor: dict[str, Any],
    request: Request,
    action_code: str,
    target_type: str,
    target_id: Optional[int],
    target_label: Optional[str],
    detail: Optional[dict[str, Any]] = None,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO admin_operation_logs (
              actor_user_id, actor_username, action_code, target_type, target_id,
              target_label, status, detail_json, ip_address, user_agent
            ) VALUES (
              :actor_user_id, :actor_username, :action_code, :target_type, :target_id,
              :target_label, 'SUCCESS', :detail_json, :ip_address, :user_agent
            )
            """
        ),
        {
            "actor_user_id": int(actor["id"]),
            "actor_username": actor["username"],
            "action_code": action_code,
            "target_type": target_type,
            "target_id": target_id,
            "target_label": target_label,
            "detail_json": json.dumps(detail or {}, ensure_ascii=False),
            "ip_address": _client_ip(request),
            "user_agent": _request_user_agent(request),
        },
    )


def _build_line_filters(
    source_type: Optional[str],
    product_type: Optional[str],
    area: Optional[str],
    customer_name: Optional[str],
    product_number: Optional[str],
    service_status: Optional[str],
    start_date: Optional[date],
    end_date: Optional[date],
    keyword: Optional[str],
) -> tuple[str, dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if source_type:
        conditions.append("source_type = :source_type")
        params["source_type"] = source_type
    if product_type:
        conditions.append("product_type = :product_type")
        params["product_type"] = product_type
    if area:
        conditions.append("area = :area")
        params["area"] = area
    if customer_name:
        conditions.append("customer_name LIKE :customer_name")
        params["customer_name"] = f"%{customer_name}%"
    if product_number:
        conditions.append("product_number = :product_number")
        params["product_number"] = product_number
    if service_status:
        conditions.append("service_status = :service_status")
        params["service_status"] = service_status
    if start_date:
        conditions.append("open_time >= :start_dt")
        params["start_dt"] = datetime.combine(start_date, time.min)
    if end_date:
        conditions.append("open_time <= :end_dt")
        params["end_dt"] = datetime.combine(end_date, time.max)
    if keyword:
        conditions.append(
            "(customer_name LIKE :kw OR product_number LIKE :kw "
            "OR line_name LIKE :kw OR order_no LIKE :kw OR client_room_address LIKE :kw)"
        )
        params["kw"] = f"%{keyword}%"

    where_sql = " AND ".join(conditions) if conditions else "1=1"
    return where_sql, params


@app.get("/", include_in_schema=False)
def serve_home() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.post("/api/auth/login")
def login(payload: LoginPayload, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = authenticate_user(db, payload.username.strip(), payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token, expires_at = create_session(
        db,
        int(user["id"]),
        _client_ip(request),
        _request_user_agent(request),
    )
    db.commit()
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at,
        "user": user,
    }


@app.post("/api/auth/logout")
def logout(
    credentials=Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if credentials and credentials.scheme.lower() == "bearer":
        revoke_session(db, credentials.credentials)
        db.commit()
    return {"message": "ok"}


@app.get("/api/auth/me")
def me(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"user": current_user}


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/admin/roles")
def list_admin_roles(
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_admin_permission),
) -> dict[str, Any]:
    _ = current_user
    rows = db.execute(
        text(
            """
            SELECT name, description
            FROM auth_roles
            ORDER BY name
            """
        )
    ).mappings().all()
    return {"items": [dict(row) for row in rows]}


@app.get("/api/admin/users")
def list_admin_users(
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_admin_permission),
) -> dict[str, Any]:
    _ = current_user
    sql = text(
        """
        SELECT
          u.id,
          u.username,
          u.display_name,
          u.is_active,
          u.created_at,
          u.updated_at,
          GROUP_CONCAT(DISTINCT r.name ORDER BY r.name SEPARATOR ',') AS roles,
          COUNT(DISTINCT CASE WHEN s.revoked_at IS NULL AND s.expires_at > :now THEN s.id END) AS active_sessions
        FROM auth_users u
        LEFT JOIN auth_user_roles ur ON ur.user_id = u.id
        LEFT JOIN auth_roles r ON r.id = ur.role_id
        LEFT JOIN auth_sessions s ON s.user_id = u.id
        GROUP BY u.id, u.username, u.display_name, u.is_active, u.created_at, u.updated_at
        ORDER BY u.username
        """
    )
    rows = db.execute(sql, {"now": datetime.now()}).mappings().all()
    return {"items": [_serialize_admin_user(row) for row in rows]}


@app.post("/api/admin/users")
def create_admin_user(
    payload: AdminUserCreatePayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_admin_permission),
) -> dict[str, Any]:
    exists = db.execute(
        text("SELECT id FROM auth_users WHERE username = :username LIMIT 1"),
        {"username": payload.username.strip()},
    ).mappings().first()
    if exists:
        raise HTTPException(status_code=409, detail="用户名已存在")

    role_id = _get_role_id(db, payload.role.strip())
    result = db.execute(
        text(
            """
            INSERT INTO auth_users (username, display_name, password_hash, is_active)
            VALUES (:username, :display_name, :password_hash, 1)
            """
        ),
        {
            "username": payload.username.strip(),
            "display_name": payload.display_name.strip(),
            "password_hash": hash_password(payload.password),
        },
    )
    user_id = int(result.lastrowid)
    db.execute(
        text("INSERT INTO auth_user_roles (user_id, role_id) VALUES (:user_id, :role_id)"),
        {"user_id": user_id, "role_id": role_id},
    )
    db.commit()

    user = _get_admin_user(db, user_id)
    if not user:
        raise HTTPException(status_code=500, detail="用户创建后查询失败")
    _log_admin_action(
        db,
        current_user,
        request,
        "user.create",
        "auth_user",
        user_id,
        user["username"],
        {
            "role": payload.role.strip(),
            "display_name": payload.display_name.strip(),
            "is_active": True,
        },
    )
    db.commit()
    return {"user": user}


@app.patch("/api/admin/users/{user_id}")
def update_admin_user(
    user_id: int,
    payload: AdminUserUpdatePayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_admin_permission),
) -> dict[str, Any]:
    target = _get_admin_user(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    changes: dict[str, Any] = {}

    if payload.display_name is not None:
        new_display_name = payload.display_name.strip()
        if new_display_name != target["display_name"]:
            changes["display_name"] = {
                "before": target["display_name"],
                "after": new_display_name,
            }
        db.execute(
            text("UPDATE auth_users SET display_name = :display_name WHERE id = :user_id"),
            {"display_name": new_display_name, "user_id": user_id},
        )

    current_roles = set(target.get("roles", []))
    target_role = payload.role.strip() if payload.role else None
    if target_role:
        if int(current_user["id"]) == user_id and target_role != "admin":
            raise HTTPException(status_code=400, detail="不能移除当前登录管理员的 admin 角色")
        if "admin" in current_roles and target_role != "admin" and _count_active_admins(db) <= 1:
            raise HTTPException(status_code=400, detail="系统至少需要保留一个启用状态的管理员")

        role_id = _get_role_id(db, target_role)
        db.execute(text("DELETE FROM auth_user_roles WHERE user_id = :user_id"), {"user_id": user_id})
        db.execute(
            text("INSERT INTO auth_user_roles (user_id, role_id) VALUES (:user_id, :role_id)"),
            {"user_id": user_id, "role_id": role_id},
        )
        if target_role not in current_roles or len(current_roles) != 1:
            changes["role"] = {
                "before": sorted(current_roles),
                "after": [target_role],
            }

    if payload.is_active is not None:
        if int(current_user["id"]) == user_id and not payload.is_active:
            raise HTTPException(status_code=400, detail="不能停用当前登录管理员账号")
        if "admin" in current_roles and not payload.is_active and _count_active_admins(db) <= 1:
            raise HTTPException(status_code=400, detail="系统至少需要保留一个启用状态的管理员")

        if bool(target["is_active"]) != bool(payload.is_active):
            changes["is_active"] = {
                "before": bool(target["is_active"]),
                "after": bool(payload.is_active),
            }
        db.execute(
            text("UPDATE auth_users SET is_active = :is_active WHERE id = :user_id"),
            {"is_active": 1 if payload.is_active else 0, "user_id": user_id},
        )
        if not payload.is_active:
            _revoke_user_sessions(db, user_id)

    db.commit()
    user = _get_admin_user(db, user_id)
    if not user:
        raise HTTPException(status_code=500, detail="用户更新后查询失败")
    if changes:
        _log_admin_action(
            db,
            current_user,
            request,
            "user.update",
            "auth_user",
            user_id,
            user["username"],
            changes,
        )
        db.commit()
    return {"user": user}


@app.post("/api/admin/users/{user_id}/reset-password")
def reset_admin_user_password(
    user_id: int,
    payload: AdminPasswordResetPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_admin_permission),
) -> dict[str, Any]:
    target = _get_admin_user(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    db.execute(
        text(
            """
            UPDATE auth_users
            SET password_hash = :password_hash
            WHERE id = :user_id
            """
        ),
        {
            "password_hash": hash_password(payload.password),
            "user_id": user_id,
        },
    )
    _revoke_user_sessions(db, user_id)
    db.commit()
    _log_admin_action(
        db,
        current_user,
        request,
        "user.reset_password",
        "auth_user",
        user_id,
        target["username"],
        {"revoked_sessions": True},
    )
    db.commit()
    return {"message": "ok"}


@app.delete("/api/admin/users/{user_id}")
def delete_admin_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_admin_permission),
) -> dict[str, Any]:
    target = _get_admin_user(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if int(current_user["id"]) == user_id:
        raise HTTPException(status_code=400, detail="不能删除当前登录管理员账号")

    target_roles = set(target.get("roles", []))
    if "admin" in target_roles and bool(target["is_active"]) and _count_active_admins(db) <= 1:
        raise HTTPException(status_code=400, detail="系统至少需要保留一个启用状态的管理员")

    active_sessions = int(target.get("active_sessions") or 0)
    db.execute(text("DELETE FROM auth_users WHERE id = :user_id"), {"user_id": user_id})
    db.commit()
    _log_admin_action(
        db,
        current_user,
        request,
        "user.delete",
        "auth_user",
        user_id,
        target["username"],
        {
            "roles": sorted(target_roles),
            "display_name": target["display_name"],
            "is_active": bool(target["is_active"]),
            "deleted_active_sessions": active_sessions,
        },
    )
    db.commit()
    return {"message": "ok"}


@app.get("/api/admin/sessions")
def list_admin_sessions(
    user_id: Optional[int] = Query(None),
    include_revoked: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_admin_permission),
) -> dict[str, Any]:
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit_num": limit, "now": datetime.now()}
    if user_id is not None:
        conditions.append("s.user_id = :user_id")
        params["user_id"] = user_id
    if not include_revoked:
        conditions.append("s.revoked_at IS NULL")
        conditions.append("s.expires_at > :now")

    where_sql = " AND ".join(conditions)
    sql = text(
        f"""
        SELECT
          s.id,
          s.user_id,
          u.username,
          u.display_name,
          u.is_active AS user_is_active,
          GROUP_CONCAT(DISTINCT r.name ORDER BY r.name SEPARATOR ',') AS roles,
          s.ip_address,
          s.user_agent,
          s.created_at,
          s.expires_at,
          s.revoked_at,
          CASE
            WHEN s.revoked_at IS NULL AND s.expires_at > :now THEN 1
            ELSE 0
          END AS is_active
        FROM auth_sessions s
        JOIN auth_users u ON u.id = s.user_id
        LEFT JOIN auth_user_roles ur ON ur.user_id = u.id
        LEFT JOIN auth_roles r ON r.id = ur.role_id
        WHERE {where_sql}
        GROUP BY
          s.id, s.user_id, u.username, u.display_name, u.is_active,
          s.ip_address, s.user_agent, s.created_at, s.expires_at, s.revoked_at
        ORDER BY s.created_at DESC, s.id DESC
        LIMIT :limit_num
        """
    )
    rows = db.execute(sql, params).mappings().all()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["roles"] = _split_csv(item.get("roles"))
        item["is_active"] = bool(item.get("is_active"))
        item["user_is_active"] = bool(item.get("user_is_active"))
        item["is_current"] = int(item["id"]) == int(current_user.get("session_id") or 0)
        items.append(item)
    return {"items": items}


@app.post("/api/admin/sessions/{session_id}/revoke")
def revoke_admin_session(
    session_id: int,
    request: Request,
    payload: Optional[AdminSessionRevokePayload] = None,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_admin_permission),
) -> dict[str, Any]:
    session_row = db.execute(
        text(
            """
            SELECT s.id, s.user_id, u.username, u.display_name
            FROM auth_sessions s
            JOIN auth_users u ON u.id = s.user_id
            WHERE s.id = :session_id
            LIMIT 1
            """
        ),
        {"session_id": session_id},
    ).mappings().first()
    if not session_row:
        raise HTTPException(status_code=404, detail="会话不存在")

    affected = revoke_session_by_id(db, session_id)
    db.commit()
    if affected == 0:
        return {"message": "ok", "revoked": 0}

    _log_admin_action(
        db,
        current_user,
        request,
        "session.revoke",
        "auth_session",
        session_id,
        f"{session_row['username']}#{session_id}",
        {
            "user_id": int(session_row["user_id"]),
            "username": session_row["username"],
            "reason": payload.reason if payload else None,
        },
    )
    db.commit()
    return {"message": "ok", "revoked": affected}


@app.post("/api/admin/users/{user_id}/revoke-sessions")
def revoke_admin_user_sessions(
    user_id: int,
    request: Request,
    payload: Optional[AdminSessionRevokePayload] = None,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_admin_permission),
) -> dict[str, Any]:
    target = _get_admin_user(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    exclude_session_id: Optional[int] = None
    if int(current_user["id"]) == user_id:
        exclude_session_id = int(current_user.get("session_id") or 0) or None

    affected = revoke_sessions_for_user(db, user_id, exclude_session_id=exclude_session_id)
    db.commit()
    _log_admin_action(
        db,
        current_user,
        request,
        "session.revoke_all",
        "auth_user",
        user_id,
        target["username"],
        {
            "revoked": affected,
            "reason": payload.reason if payload else None,
            "excluded_current_session": exclude_session_id,
        },
    )
    db.commit()
    return {"message": "ok", "revoked": affected, "excluded_current_session": exclude_session_id}


@app.get("/api/admin/logs")
def list_admin_logs(
    action_code: Optional[str] = Query(None),
    actor_user_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_admin_permission),
) -> dict[str, Any]:
    _ = current_user
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit_num": limit}
    if action_code:
        conditions.append("action_code = :action_code")
        params["action_code"] = action_code
    if actor_user_id is not None:
        conditions.append("actor_user_id = :actor_user_id")
        params["actor_user_id"] = actor_user_id

    where_sql = " AND ".join(conditions)
    sql = text(
        f"""
        SELECT
          id, actor_user_id, actor_username, action_code, target_type,
          target_id, target_label, status, detail_json, ip_address, user_agent, created_at
        FROM admin_operation_logs
        WHERE {where_sql}
        ORDER BY id DESC
        LIMIT :limit_num
        """
    )
    rows = db.execute(sql, params).mappings().all()
    return {"items": [_serialize_admin_log(row) for row in rows]}


@app.get("/api/admin/data/summary")
def admin_data_summary(
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_admin_permission),
) -> dict[str, Any]:
    _ = current_user
    now = datetime.now()
    line_total = int(db.execute(text("SELECT COUNT(*) FROM customer_line_records")).scalar_one() or 0)
    onu_total = int(db.execute(text("SELECT COUNT(*) FROM onu_inventory")).scalar_one() or 0)
    user_total = int(db.execute(text("SELECT COUNT(*) FROM auth_users")).scalar_one() or 0)
    batch_total = int(db.execute(text("SELECT COUNT(*) FROM import_batches")).scalar_one() or 0)
    active_sessions = int(
        db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM auth_sessions
                WHERE revoked_at IS NULL AND expires_at > :now
                """
            ),
            {"now": now},
        ).scalar_one()
        or 0
    )

    line_breakdown = db.execute(
        text(
            """
            SELECT source_type, COUNT(*) AS total
            FROM customer_line_records
            GROUP BY source_type
            ORDER BY total DESC, source_type
            """
        )
    ).mappings().all()
    onu_breakdown = db.execute(
        text(
            """
            SELECT service_type, COUNT(*) AS total
            FROM onu_inventory
            GROUP BY service_type
            ORDER BY total DESC, service_type
            LIMIT 12
            """
        )
    ).mappings().all()
    latest_batch = db.execute(
        text(
            """
            SELECT
              id, batch_name, started_at, finished_at, status,
              files_total, rows_processed, rows_affected, rows_failed, message
            FROM import_batches
            ORDER BY id DESC
            LIMIT 1
            """
        )
    ).mappings().first()

    return {
        "totals": {
            "line_total": line_total,
            "onu_total": onu_total,
            "user_total": user_total,
            "batch_total": batch_total,
            "active_sessions": active_sessions,
        },
        "line_breakdown": [dict(row) for row in line_breakdown],
        "onu_breakdown": [dict(row) for row in onu_breakdown],
        "latest_batch": dict(latest_batch) if latest_batch else None,
        "import_data_dir": str(DEFAULT_IMPORT_DATA_DIR),
    }


@app.get("/api/admin/import/errors")
def list_import_errors(
    batch_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_admin_permission),
) -> dict[str, Any]:
    _ = current_user
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit_num": limit}
    if batch_id is not None:
        conditions.append("e.batch_id = :batch_id")
        params["batch_id"] = batch_id

    where_sql = " AND ".join(conditions)
    sql = text(
        f"""
        SELECT
          e.id, e.batch_id, b.batch_name, e.source_file, e.source_sheet,
          e.source_row_number, e.error_message, e.created_at
        FROM import_errors e
        JOIN import_batches b ON b.id = e.batch_id
        WHERE {where_sql}
        ORDER BY e.id DESC
        LIMIT :limit_num
        """
    )
    rows = db.execute(sql, params).mappings().all()
    return {"items": [dict(row) for row in rows]}


@app.post("/api/admin/import/run")
def run_admin_import(
    payload: AdminImportRunPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_admin_permission),
) -> dict[str, Any]:
    if not IMPORT_SCRIPT.exists():
        raise HTTPException(status_code=500, detail="导入脚本不存在")
    if not DEFAULT_IMPORT_DATA_DIR.exists():
        raise HTTPException(status_code=500, detail=f"导入目录不存在: {DEFAULT_IMPORT_DATA_DIR}")

    running_batch = db.execute(
        text(
            """
            SELECT id, batch_name, started_at
            FROM import_batches
            WHERE status = 'RUNNING'
            ORDER BY id DESC
            LIMIT 1
            """
        )
    ).mappings().first()
    if running_batch:
        raise HTTPException(
            status_code=409,
            detail=f"已有导入任务运行中: batch#{running_batch['id']} {running_batch['batch_name']}",
        )

    IMPORT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_name = payload.batch_name or f"admin_{'dry' if payload.dry_run else 'run'}_{timestamp}"
    # Batch labels are user input; never use them as filesystem paths.
    log_path = IMPORT_LOG_DIR / f"import_{timestamp}_{secrets.token_hex(8)}.log"
    command = [
        sys.executable,
        str(IMPORT_SCRIPT),
        "--data-dir",
        str(DEFAULT_IMPORT_DATA_DIR),
        "--batch-name",
        batch_name,
    ]
    if payload.dry_run:
        command.append("--dry-run")
    if payload.init_schema:
        command.append("--init-schema")

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=str(BASE_DIR),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )

    result = {
        "message": "started",
        "pid": process.pid,
        "batch_name": batch_name,
        "dry_run": payload.dry_run,
        "log_file": str(log_path),
        "data_dir": str(DEFAULT_IMPORT_DATA_DIR),
    }
    _log_admin_action(
        db,
        current_user,
        request,
        "import.run",
        "import_batch",
        None,
        batch_name,
        {
            "dry_run": payload.dry_run,
            "init_schema": payload.init_schema,
            "pid": process.pid,
            "log_file": str(log_path),
            "data_dir": str(DEFAULT_IMPORT_DATA_DIR),
        },
    )
    db.commit()
    return result


@app.get("/api/lines/search")
def search_lines(
    source_type: Optional[str] = Query(None, description="如: 互联网专线 / IPVPN专线"),
    product_type: Optional[str] = Query(None, description="产品类型"),
    area: Optional[str] = Query(None, description="区域"),
    customer_name: Optional[str] = Query(None, description="客户名称(模糊)"),
    product_number: Optional[str] = Query(None, description="产品号码(精确)"),
    service_status: Optional[str] = Query(None, description="业务状态"),
    start_date: Optional[date] = Query(None, description="开通日期起始(YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="开通日期结束(YYYY-MM-DD)"),
    keyword: Optional[str] = Query(None, description="综合关键字"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_query_permission),
) -> dict[str, Any]:
    _ = current_user
    where_sql, params = _build_line_filters(
        source_type=source_type,
        product_type=product_type,
        area=area,
        customer_name=customer_name,
        product_number=product_number,
        service_status=service_status,
        start_date=start_date,
        end_date=end_date,
        keyword=keyword,
    )

    total_sql = text(f"SELECT COUNT(*) AS total FROM customer_line_records WHERE {where_sql}")
    total = db.execute(total_sql, params).scalar_one()

    offset = (page - 1) * size
    query_sql = text(
        f"""
        SELECT *
        FROM customer_line_records
        WHERE {where_sql}
        ORDER BY open_time IS NULL, open_time DESC, id DESC
        LIMIT :limit_num OFFSET :offset_num
        """
    )
    rows = db.execute(query_sql, {**params, "limit_num": size, "offset_num": offset}).mappings().all()

    return {
        "page": page,
        "size": size,
        "total": total,
        "items": [_serialize_line_list_row(r) for r in rows],
    }


@app.get("/api/lines/export")
def export_lines(
    source_type: Optional[str] = Query(None),
    product_type: Optional[str] = Query(None),
    area: Optional[str] = Query(None),
    customer_name: Optional[str] = Query(None),
    product_number: Optional[str] = Query(None),
    service_status: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    keyword: Optional[str] = Query(None),
    limit: int = Query(2000, ge=1, le=20000),
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_export_permission),
) -> dict[str, Any]:
    _ = current_user
    where_sql, params = _build_line_filters(
        source_type=source_type,
        product_type=product_type,
        area=area,
        customer_name=customer_name,
        product_number=product_number,
        service_status=service_status,
        start_date=start_date,
        end_date=end_date,
        keyword=keyword,
    )
    sql = text(
        f"""
        SELECT *
        FROM customer_line_records
        WHERE {where_sql}
        ORDER BY open_time IS NULL, open_time DESC, id DESC
        LIMIT :limit_num
        """
    )
    rows = db.execute(sql, {**params, "limit_num": limit}).mappings().all()
    return {"count": len(rows), "items": [_serialize_line_export_row(r, source_type) for r in rows]}


@app.get("/api/lines/{record_id}")
def get_line_detail(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_query_permission),
) -> dict[str, Any]:
    _ = current_user
    sql = text("SELECT * FROM customer_line_records WHERE id = :record_id")
    row = db.execute(sql, {"record_id": record_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    return _row_to_dict(row)


@app.get("/api/onu/search")
def search_onu(
    service_type: Optional[str] = Query(None, description="业务类型"),
    product_number: Optional[str] = Query(None, description="产品号码"),
    sn_code: Optional[str] = Query(None, description="SN码(模糊)"),
    customer_name: Optional[str] = Query(None, description="客户名称(模糊)"),
    client_county: Optional[str] = Query(None, description="区县"),
    keyword: Optional[str] = Query(None, description="综合关键字"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_query_permission),
) -> dict[str, Any]:
    _ = current_user
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if service_type:
        conditions.append("service_type = :service_type")
        params["service_type"] = service_type
    if product_number:
        conditions.append("product_number = :product_number")
        params["product_number"] = product_number
    if sn_code:
        conditions.append("sn_code LIKE :sn_code")
        params["sn_code"] = f"%{sn_code}%"
    if customer_name:
        conditions.append("customer_name LIKE :customer_name")
        params["customer_name"] = f"%{customer_name}%"
    if client_county:
        conditions.append("client_county = :client_county")
        params["client_county"] = client_county
    if keyword:
        conditions.append(
            "(onuid LIKE :kw OR onu_name LIKE :kw OR sn_code LIKE :kw OR customer_name LIKE :kw OR product_number LIKE :kw)"
        )
        params["kw"] = f"%{keyword}%"

    where_sql = " AND ".join(conditions) if conditions else "1=1"

    total_sql = text(f"SELECT COUNT(*) AS total FROM onu_inventory WHERE {where_sql}")
    total = db.execute(total_sql, params).scalar_one()

    offset = (page - 1) * size
    query_sql = text(
        f"""
        SELECT *
        FROM onu_inventory
        WHERE {where_sql}
        ORDER BY id DESC
        LIMIT :limit_num OFFSET :offset_num
        """
    )
    rows = db.execute(query_sql, {**params, "limit_num": size, "offset_num": offset}).mappings().all()

    return {
        "page": page,
        "size": size,
        "total": total,
        "items": [_serialize_onu_list_row(r) for r in rows],
    }


@app.get("/api/onu/export")
def export_onu(
    service_type: Optional[str] = Query(None),
    product_number: Optional[str] = Query(None),
    sn_code: Optional[str] = Query(None),
    customer_name: Optional[str] = Query(None),
    client_county: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    limit: int = Query(2000, ge=1, le=20000),
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_export_permission),
) -> dict[str, Any]:
    _ = current_user
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if service_type:
        conditions.append("service_type = :service_type")
        params["service_type"] = service_type
    if product_number:
        conditions.append("product_number = :product_number")
        params["product_number"] = product_number
    if sn_code:
        conditions.append("sn_code LIKE :sn_code")
        params["sn_code"] = f"%{sn_code}%"
    if customer_name:
        conditions.append("customer_name LIKE :customer_name")
        params["customer_name"] = f"%{customer_name}%"
    if client_county:
        conditions.append("client_county = :client_county")
        params["client_county"] = client_county
    if keyword:
        conditions.append(
            "(onuid LIKE :kw OR onu_name LIKE :kw OR sn_code LIKE :kw OR customer_name LIKE :kw OR product_number LIKE :kw)"
        )
        params["kw"] = f"%{keyword}%"

    where_sql = " AND ".join(conditions) if conditions else "1=1"
    sql = text(
        f"""
        SELECT *
        FROM onu_inventory
        WHERE {where_sql}
        ORDER BY id DESC
        LIMIT :limit_num
        """
    )
    rows = db.execute(sql, {**params, "limit_num": limit}).mappings().all()
    return {"count": len(rows), "items": [_serialize_onu_export_row(r) for r in rows]}


@app.get("/api/onu/{record_id}")
def get_onu_detail(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_query_permission),
) -> dict[str, Any]:
    _ = current_user
    sql = text("SELECT * FROM onu_inventory WHERE id = :record_id")
    row = db.execute(sql, {"record_id": record_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    return _row_to_dict(row)


@app.get("/api/stats/by-area")
def stats_by_area(
    source_type: Optional[str] = Query(None, description="可选：按来源类型过滤"),
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_query_permission),
) -> dict[str, Any]:
    _ = current_user
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if source_type:
        conditions.append("source_type = :source_type")
        params["source_type"] = source_type
    where_sql = " AND ".join(conditions) if conditions else "1=1"

    sql = text(
        f"""
        SELECT
          area,
          source_type,
          COUNT(*) AS total
        FROM customer_line_records
        WHERE {where_sql}
        GROUP BY area, source_type
        ORDER BY total DESC
        """
    )
    rows = db.execute(sql, params).mappings().all()
    return {"items": [dict(r) for r in rows]}


@app.get("/api/import/batches")
def list_import_batches(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_query_permission),
) -> dict[str, Any]:
    _ = current_user
    sql = text(
        """
        SELECT
          id, batch_name, started_at, finished_at, status,
          files_total, rows_processed, rows_affected, rows_failed, message
        FROM import_batches
        ORDER BY id DESC
        LIMIT :limit_num
        """
    )
    rows = db.execute(sql, {"limit_num": limit}).mappings().all()
    return {"items": [dict(r) for r in rows]}
