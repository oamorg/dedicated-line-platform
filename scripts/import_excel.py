#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from openpyxl import load_workbook
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

DEFAULT_FILE_SOURCE_TYPE: dict[str, str] = {
    "传输专线.xlsx": "传输专线",
    "多媒体语音专线.xlsx": "多媒体语音专线",
    "互联网专线.xlsx": "互联网专线",
    "商务快线.xlsx": "商务快线",
    "IPVPN专线.xlsx": "IPVPN专线",
}

DEFAULT_ONU_FILE_NAMES = {"ONU台账.xlsx"}

DEFAULT_SHEET_HINTS: dict[str, str] = {
    "传输专线.xlsx": "Sheet0",
    "多媒体语音专线.xlsx": "Sheet0",
    "互联网专线.xlsx": "Sheet0",
    "商务快线.xlsx": "Sheet0",
    "IPVPN专线.xlsx": "Sheet0",
    "ONU台账.xlsx": "Sheet1",
}


def load_source_mappings() -> tuple[dict[str, str], set[str], dict[str, str]]:
    config_path = Path(__file__).resolve().parents[1] / "config" / "source_files.json"
    if not config_path.exists():
        return DEFAULT_FILE_SOURCE_TYPE, DEFAULT_ONU_FILE_NAMES, DEFAULT_SHEET_HINTS

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        line_files = data.get("line_files", {})
        onu_files = data.get("onu_files", {})

        file_source_type: dict[str, str] = {}
        sheet_hints: dict[str, str] = {}

        def clean(value: Any) -> str | None:
            if value is None:
                return None
            text_value = str(value).strip()
            if text_value == "" or text_value.lower() in {"nan", "nat", "none"}:
                return None
            return text_value

        for file_name, cfg in line_files.items():
            source_type = clean(cfg.get("source_type")) if isinstance(cfg, dict) else None
            sheet_hint = clean(cfg.get("detail_sheet_hint")) if isinstance(cfg, dict) else None
            if source_type:
                file_source_type[file_name] = source_type
            if sheet_hint:
                sheet_hints[file_name] = sheet_hint

        onu_file_names: set[str] = set()
        for file_name, cfg in onu_files.items():
            onu_file_names.add(file_name)
            if isinstance(cfg, dict):
                sheet_hint = clean(cfg.get("detail_sheet_hint"))
                if sheet_hint:
                    sheet_hints[file_name] = sheet_hint

        if not file_source_type:
            file_source_type = DEFAULT_FILE_SOURCE_TYPE
        if not onu_file_names:
            onu_file_names = DEFAULT_ONU_FILE_NAMES
        if not sheet_hints:
            sheet_hints = DEFAULT_SHEET_HINTS

        return file_source_type, onu_file_names, sheet_hints
    except Exception:
        return DEFAULT_FILE_SOURCE_TYPE, DEFAULT_ONU_FILE_NAMES, DEFAULT_SHEET_HINTS


FILE_SOURCE_TYPE, ONU_FILE_NAMES, SHEET_HINTS = load_source_mappings()

LINE_UPSERT_SQL = text(
    """
    INSERT INTO customer_line_records (
      row_hash, import_batch_id, source_type, source_file, source_sheet, source_row_number, source_record_id,
      line_name, area, check_status, check_info, topology_complete,
      customer_city, customer_group_code, customer_name, customer_type,
      service_city, related_city,
      product_number, schedule_product_number, product_instance_code, product_type_code, product_type, sub_product_type,
      order_no, order_type, open_time, service_status, workflow_status, assurance_level, acceptance_status,
      contact_name, contact_phone, bandwidth, upstream_bandwidth, downstream_bandwidth, purpose_desc,
      access_method, transmission_circuit_name, optical_path_name, svlan, cvlan,
      client_county, client_room_address, client_device_name, client_device_port,
      olt_device_name, olt_port_name, onu_device_name, onu_port_name,
      building_code, building_name, data_source, source_channel, business_tag,
      marketing_group_id, marketing_group_name, raw_data
    ) VALUES (
      :row_hash, :import_batch_id, :source_type, :source_file, :source_sheet, :source_row_number, :source_record_id,
      :line_name, :area, :check_status, :check_info, :topology_complete,
      :customer_city, :customer_group_code, :customer_name, :customer_type,
      :service_city, :related_city,
      :product_number, :schedule_product_number, :product_instance_code, :product_type_code, :product_type, :sub_product_type,
      :order_no, :order_type, :open_time, :service_status, :workflow_status, :assurance_level, :acceptance_status,
      :contact_name, :contact_phone, :bandwidth, :upstream_bandwidth, :downstream_bandwidth, :purpose_desc,
      :access_method, :transmission_circuit_name, :optical_path_name, :svlan, :cvlan,
      :client_county, :client_room_address, :client_device_name, :client_device_port,
      :olt_device_name, :olt_port_name, :onu_device_name, :onu_port_name,
      :building_code, :building_name, :data_source, :source_channel, :business_tag,
      :marketing_group_id, :marketing_group_name, :raw_data
    )
    ON DUPLICATE KEY UPDATE
      import_batch_id = VALUES(import_batch_id),
      source_row_number = VALUES(source_row_number),
      source_record_id = VALUES(source_record_id),
      line_name = VALUES(line_name),
      area = VALUES(area),
      check_status = VALUES(check_status),
      check_info = VALUES(check_info),
      topology_complete = VALUES(topology_complete),
      customer_city = VALUES(customer_city),
      customer_group_code = VALUES(customer_group_code),
      customer_name = VALUES(customer_name),
      customer_type = VALUES(customer_type),
      service_city = VALUES(service_city),
      related_city = VALUES(related_city),
      product_number = VALUES(product_number),
      schedule_product_number = VALUES(schedule_product_number),
      product_instance_code = VALUES(product_instance_code),
      product_type_code = VALUES(product_type_code),
      product_type = VALUES(product_type),
      sub_product_type = VALUES(sub_product_type),
      order_no = VALUES(order_no),
      order_type = VALUES(order_type),
      open_time = VALUES(open_time),
      service_status = VALUES(service_status),
      workflow_status = VALUES(workflow_status),
      assurance_level = VALUES(assurance_level),
      acceptance_status = VALUES(acceptance_status),
      contact_name = VALUES(contact_name),
      contact_phone = VALUES(contact_phone),
      bandwidth = VALUES(bandwidth),
      upstream_bandwidth = VALUES(upstream_bandwidth),
      downstream_bandwidth = VALUES(downstream_bandwidth),
      purpose_desc = VALUES(purpose_desc),
      access_method = VALUES(access_method),
      transmission_circuit_name = VALUES(transmission_circuit_name),
      optical_path_name = VALUES(optical_path_name),
      svlan = VALUES(svlan),
      cvlan = VALUES(cvlan),
      client_county = VALUES(client_county),
      client_room_address = VALUES(client_room_address),
      client_device_name = VALUES(client_device_name),
      client_device_port = VALUES(client_device_port),
      olt_device_name = VALUES(olt_device_name),
      olt_port_name = VALUES(olt_port_name),
      onu_device_name = VALUES(onu_device_name),
      onu_port_name = VALUES(onu_port_name),
      building_code = VALUES(building_code),
      building_name = VALUES(building_name),
      data_source = VALUES(data_source),
      source_channel = VALUES(source_channel),
      business_tag = VALUES(business_tag),
      marketing_group_id = VALUES(marketing_group_id),
      marketing_group_name = VALUES(marketing_group_name),
      raw_data = VALUES(raw_data),
      updated_at = CURRENT_TIMESTAMP
    """
)

ONU_UPSERT_SQL = text(
    """
    INSERT INTO onu_inventory (
      row_hash, import_batch_id, source_file, source_sheet, source_row_number,
      onuid, onu_city, onu_name, model, device_type, onu_vendor, auth_mode, sn_code, onu_password,
      olt_mgmt_ip, olt_city, olt_vendor, ponid, product_number, customer_name, service_type, client_county, raw_data
    ) VALUES (
      :row_hash, :import_batch_id, :source_file, :source_sheet, :source_row_number,
      :onuid, :onu_city, :onu_name, :model, :device_type, :onu_vendor, :auth_mode, :sn_code, :onu_password,
      :olt_mgmt_ip, :olt_city, :olt_vendor, :ponid, :product_number, :customer_name, :service_type, :client_county, :raw_data
    )
    ON DUPLICATE KEY UPDATE
      import_batch_id = VALUES(import_batch_id),
      source_row_number = VALUES(source_row_number),
      onuid = VALUES(onuid),
      onu_city = VALUES(onu_city),
      onu_name = VALUES(onu_name),
      model = VALUES(model),
      device_type = VALUES(device_type),
      onu_vendor = VALUES(onu_vendor),
      auth_mode = VALUES(auth_mode),
      sn_code = VALUES(sn_code),
      onu_password = VALUES(onu_password),
      olt_mgmt_ip = VALUES(olt_mgmt_ip),
      olt_city = VALUES(olt_city),
      olt_vendor = VALUES(olt_vendor),
      ponid = VALUES(ponid),
      product_number = VALUES(product_number),
      customer_name = VALUES(customer_name),
      service_type = VALUES(service_type),
      client_county = VALUES(client_county),
      raw_data = VALUES(raw_data),
      updated_at = CURRENT_TIMESTAMP
    """
)

IMPORT_ERROR_SQL = text(
    """
    INSERT INTO import_errors (batch_id, source_file, source_sheet, source_row_number, error_message, raw_data)
    VALUES (:batch_id, :source_file, :source_sheet, :source_row_number, :error_message, :raw_data)
    """
)


def clean_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text_value = str(value).strip()
    if text_value == "" or text_value.lower() in {"nan", "nat", "none"}:
        return None
    return text_value


def pick_value(row: dict[str, Any], *names: str) -> str | None:
    for name in names:
        if name not in row:
            continue
        value = clean_value(row[name])
        if value is not None:
            return value
    return None


def parse_datetime(value: Any) -> datetime | None:
    text_value = clean_value(value)
    if text_value is None:
        return None
    dt = pd.to_datetime(text_value, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.to_pydatetime().replace(tzinfo=None)


def canonical_row(row: dict[str, Any]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in row.items():
        ck = clean_value(key)
        cv = clean_value(value)
        if ck is None or cv is None:
            continue
        cleaned[ck] = cv
    return cleaned


def row_hash(source_type: str, row: dict[str, Any]) -> str:
    payload = {"source_type": source_type, "data": row}
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(serialized.encode("utf-8")).hexdigest()


def chunked(items: list[dict[str, Any]], chunk_size: int) -> list[list[dict[str, Any]]]:
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def pick_sheet(file_name: str, workbook: Any) -> str:
    hint = SHEET_HINTS.get(file_name)
    sheet_names = list(workbook.sheetnames)
    if hint and hint in sheet_names:
        return hint

    best_sheet = sheet_names[0]
    best_score = -1
    for sheet in sheet_names:
        ws = workbook[sheet]
        score = 0
        for idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
            row_score = sum(1 for value in row if clean_value(value) is not None)
            score = max(score, row_score)
            if idx >= 20:
                break
        if score > best_score:
            best_score = score
            best_sheet = sheet
    return best_sheet


def normalize_headers(header_row: tuple[Any, ...]) -> list[str]:
    headers: list[str] = []
    duplicates: dict[str, int] = {}
    for idx, col in enumerate(header_row):
        name = clean_value(col) or f"_col_{idx + 1}"
        duplicates[name] = duplicates.get(name, 0) + 1
        if duplicates[name] > 1:
            name = f"{name}_{duplicates[name]}"
        headers.append(name)
    return headers


def load_sheet_rows(file_path: Path) -> tuple[list[tuple[int, dict[str, Any]]], str]:
    workbook = load_workbook(file_path, read_only=True, data_only=True, keep_links=False)
    sheet_name = pick_sheet(file_path.name, workbook)
    ws = workbook[sheet_name]

    preview_rows: list[tuple[Any, ...]] = []
    header_row_number = 1
    best_score = -1
    for idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        preview_rows.append(row)
        score = sum(1 for value in row if clean_value(value) is not None)
        if score > best_score:
            best_score = score
            header_row_number = idx
        if idx >= 20:
            break

    if not preview_rows:
        return [], sheet_name

    headers = normalize_headers(preview_rows[header_row_number - 1])
    rows: list[tuple[int, dict[str, Any]]] = []
    for row_number, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if row_number <= header_row_number:
            continue
        row_data = {headers[idx]: row[idx] if idx < len(row) else None for idx in range(len(headers))}
        if any(clean_value(value) is not None for value in row_data.values()):
            rows.append((row_number, row_data))

    return rows, sheet_name


def apply_schema(engine: Engine) -> None:
    schema_path = Path(__file__).resolve().parents[1] / "sql" / "01_schema.sql"
    sql_text = schema_path.read_text(encoding="utf-8")

    statements: list[str] = []
    current: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or stripped == "":
            continue
        current.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current))
            current = []

    if current:
        statements.append("\n".join(current))

    with engine.begin() as conn:
        for stmt in statements:
            conn.exec_driver_sql(stmt)


def create_batch(engine: Engine, batch_name: str, files_total: int, status: str) -> int:
    sql = text(
        """
        INSERT INTO import_batches (batch_name, started_at, status, files_total)
        VALUES (:batch_name, :started_at, :status, :files_total)
        """
    )
    with engine.begin() as conn:
        result = conn.execute(
            sql,
            {
                "batch_name": batch_name,
                "started_at": datetime.now(),
                "status": status,
                "files_total": files_total,
            },
        )
        return int(result.lastrowid)


def finish_batch(
    engine: Engine,
    batch_id: int,
    status: str,
    rows_processed: int,
    rows_affected: int,
    rows_failed: int,
    message: str,
) -> None:
    sql = text(
        """
        UPDATE import_batches
        SET
          finished_at = :finished_at,
          status = :status,
          rows_processed = :rows_processed,
          rows_affected = :rows_affected,
          rows_failed = :rows_failed,
          message = :message
        WHERE id = :batch_id
        """
    )
    with engine.begin() as conn:
        conn.execute(
            sql,
            {
                "finished_at": datetime.now(),
                "status": status,
                "rows_processed": rows_processed,
                "rows_affected": rows_affected,
                "rows_failed": rows_failed,
                "message": message[:1000],
                "batch_id": batch_id,
            },
        )


def log_import_error(
    conn: Connection,
    batch_id: int,
    source_file: str,
    source_sheet: str,
    source_row_number: int | None,
    error_message: str,
    raw_data: dict[str, Any] | None,
) -> None:
    conn.execute(
        IMPORT_ERROR_SQL,
        {
            "batch_id": batch_id,
            "source_file": source_file,
            "source_sheet": source_sheet,
            "source_row_number": source_row_number,
            "error_message": error_message[:1000],
            "raw_data": json.dumps(raw_data or {}, ensure_ascii=False),
        },
    )


def build_line_record(
    raw_row: dict[str, Any],
    source_type: str,
    source_file: str,
    source_sheet: str,
    source_row_number: int,
    batch_id: int,
) -> dict[str, Any]:
    return {
        "row_hash": row_hash(source_type, raw_row),
        "import_batch_id": batch_id,
        "source_type": source_type,
        "source_file": source_file,
        "source_sheet": source_sheet,
        "source_row_number": source_row_number,
        "source_record_id": pick_value(raw_row, "ID"),
        "line_name": pick_value(raw_row, "专线名称"),
        "area": pick_value(raw_row, "区域"),
        "check_status": pick_value(raw_row, "核查状态"),
        "check_info": pick_value(raw_row, "核查信息"),
        "topology_complete": pick_value(raw_row, "是否拓扑完整"),
        "customer_city": pick_value(raw_row, "客户所属地市"),
        "customer_group_code": pick_value(raw_row, "客户集团编码", "集团客户编码"),
        "customer_name": pick_value(raw_row, "客户名称"),
        "customer_type": pick_value(raw_row, "客户类型"),
        "service_city": pick_value(raw_row, "业务所属地市"),
        "related_city": pick_value(raw_row, "业务相关地市"),
        "product_number": pick_value(raw_row, "产品号码"),
        "schedule_product_number": pick_value(raw_row, "调度中产品号码"),
        "product_instance_code": pick_value(raw_row, "产品实例编码"),
        "product_type_code": pick_value(raw_row, "产品类型编码"),
        "product_type": pick_value(raw_row, "产品类型", "产品类型名称", "业务类型"),
        "sub_product_type": pick_value(raw_row, "子产品类型"),
        "order_no": pick_value(raw_row, "服开工单号"),
        "order_type": pick_value(raw_row, "工单类型"),
        "open_time": parse_datetime(pick_value(raw_row, "开通时间", "开通日期")),
        "service_status": pick_value(raw_row, "业务状态"),
        "workflow_status": pick_value(raw_row, "流程中业务状态"),
        "assurance_level": pick_value(raw_row, "业务保障等级"),
        "acceptance_status": pick_value(raw_row, "验收交维状态"),
        "contact_name": pick_value(raw_row, "客户配合联系人", "A端客户配合联系人"),
        "contact_phone": pick_value(raw_row, "客户配合联系人电话", "A端客户配合联系人电话"),
        "bandwidth": pick_value(raw_row, "业务带宽"),
        "upstream_bandwidth": pick_value(raw_row, "上行带宽"),
        "downstream_bandwidth": pick_value(raw_row, "下行带宽"),
        "purpose_desc": pick_value(raw_row, "业务用途描述"),
        "access_method": pick_value(raw_row, "传输接入方式", "A端传输接入方式"),
        "transmission_circuit_name": pick_value(raw_row, "传输电路名称", "传输电路路由", "电路名称"),
        "optical_path_name": pick_value(raw_row, "光路名称", "A端光路名称"),
        "svlan": pick_value(raw_row, "SVLAN"),
        "cvlan": pick_value(raw_row, "CVLAN"),
        "client_county": pick_value(raw_row, "客户端设备所属区县", "客户端所属区县", "A端所属区县"),
        "client_room_address": pick_value(raw_row, "客户机房地址", "A端客户机房地址"),
        "client_device_name": pick_value(raw_row, "客户端业务设备名称", "客户端业务设备", "A端客户端业务设备"),
        "client_device_port": pick_value(
            raw_row, "客户端业务设备端口名称", "客户端业务设备端口", "A端客户端业务设备端口"
        ),
        "olt_device_name": pick_value(raw_row, "OLT设备名称"),
        "olt_port_name": pick_value(raw_row, "OLT端口名称"),
        "onu_device_name": pick_value(raw_row, "传输设备或ONU名称", "A端传输设备名称"),
        "onu_port_name": pick_value(raw_row, "传输设备或ONU端口", "A端传输设备端口名称"),
        "building_code": pick_value(raw_row, "楼宇编码", "A端楼宇编码"),
        "building_name": pick_value(raw_row, "楼宇名称", "A端楼宇名称"),
        "data_source": pick_value(raw_row, "数据来源"),
        "source_channel": pick_value(raw_row, "来源类型"),
        "business_tag": pick_value(raw_row, "业务标签"),
        "marketing_group_id": pick_value(raw_row, "营销组实例ID"),
        "marketing_group_name": pick_value(raw_row, "营销组名称"),
        "raw_data": json.dumps(raw_row, ensure_ascii=False),
    }


def build_onu_record(
    raw_row: dict[str, Any],
    source_file: str,
    source_sheet: str,
    source_row_number: int,
    batch_id: int,
) -> dict[str, Any]:
    source_type = "ONU台账"
    return {
        "row_hash": row_hash(source_type, raw_row),
        "import_batch_id": batch_id,
        "source_file": source_file,
        "source_sheet": source_sheet,
        "source_row_number": source_row_number,
        "onuid": pick_value(raw_row, "ONUID"),
        "onu_city": pick_value(raw_row, "ONU所属地市"),
        "onu_name": pick_value(raw_row, "ONU名称"),
        "model": pick_value(raw_row, "型号"),
        "device_type": pick_value(raw_row, "设备种类"),
        "onu_vendor": pick_value(raw_row, "ONU厂家"),
        "auth_mode": pick_value(raw_row, "ONU认证方式"),
        "sn_code": pick_value(raw_row, "SN码"),
        "onu_password": pick_value(raw_row, "ONU密码"),
        "olt_mgmt_ip": pick_value(raw_row, "OLT管理IP"),
        "olt_city": pick_value(raw_row, "OLT所属地市"),
        "olt_vendor": pick_value(raw_row, "OLT厂家"),
        "ponid": pick_value(raw_row, "PONID"),
        "product_number": pick_value(raw_row, "产品号码"),
        "customer_name": pick_value(raw_row, "客户名称"),
        "service_type": pick_value(raw_row, "业务类型"),
        "client_county": pick_value(raw_row, "客户端设备所属区县"),
        "raw_data": json.dumps(raw_row, ensure_ascii=False),
    }


def import_line_file(
    conn: Connection,
    batch_id: int,
    file_path: Path,
    chunk_size: int,
    dry_run: bool,
) -> tuple[int, int, int]:
    sheet_rows, sheet_name = load_sheet_rows(file_path)
    source_type = FILE_SOURCE_TYPE.get(file_path.name, file_path.stem)
    records: list[dict[str, Any]] = []
    failed = 0

    for excel_row_number, row in sheet_rows:
        raw_row = canonical_row(row)
        if not raw_row:
            continue
        try:
            records.append(
                build_line_record(
                    raw_row=raw_row,
                    source_type=source_type,
                    source_file=file_path.name,
                    source_sheet=sheet_name,
                    source_row_number=excel_row_number,
                    batch_id=batch_id,
                )
            )
        except Exception as exc:
            failed += 1
            log_import_error(
                conn=conn,
                batch_id=batch_id,
                source_file=file_path.name,
                source_sheet=sheet_name,
                source_row_number=excel_row_number,
                error_message=f"line row parse failed: {exc}",
                raw_data=raw_row,
            )

    if dry_run or not records:
        return len(records), 0, failed

    affected = 0
    for chunk in chunked(records, chunk_size):
        result = conn.execute(LINE_UPSERT_SQL, chunk)
        affected += int(result.rowcount or 0)
    return len(records), affected, failed


def import_onu_file(
    conn: Connection,
    batch_id: int,
    file_path: Path,
    chunk_size: int,
    dry_run: bool,
) -> tuple[int, int, int]:
    sheet_rows, sheet_name = load_sheet_rows(file_path)
    records: list[dict[str, Any]] = []
    failed = 0

    for excel_row_number, row in sheet_rows:
        raw_row = canonical_row(row)
        if not raw_row:
            continue
        try:
            records.append(
                build_onu_record(
                    raw_row=raw_row,
                    source_file=file_path.name,
                    source_sheet=sheet_name,
                    source_row_number=excel_row_number,
                    batch_id=batch_id,
                )
            )
        except Exception as exc:
            failed += 1
            log_import_error(
                conn=conn,
                batch_id=batch_id,
                source_file=file_path.name,
                source_sheet=sheet_name,
                source_row_number=excel_row_number,
                error_message=f"onu row parse failed: {exc}",
                raw_data=raw_row,
            )

    if dry_run or not records:
        return len(records), 0, failed

    affected = 0
    for chunk in chunked(records, chunk_size):
        result = conn.execute(ONU_UPSERT_SQL, chunk)
        affected += int(result.rowcount or 0)
    return len(records), affected, failed


def discover_excel_files(data_dir: Path) -> list[Path]:
    if not data_dir.exists():
        raise FileNotFoundError(f"data directory not found: {data_dir}")

    configured_names: list[str] = list(FILE_SOURCE_TYPE.keys()) + sorted(ONU_FILE_NAMES)
    configured_files: list[Path] = []
    for file_name in configured_names:
        file_path = data_dir / file_name
        if file_path.exists() and file_path.suffix.lower() == ".xlsx":
            configured_files.append(file_path)

    if configured_files:
        return configured_files

    return sorted([p for p in data_dir.glob("*.xlsx") if not p.name.startswith("~$")])


def summarize_exception(exc: Exception) -> str:
    original = getattr(exc, "orig", None)
    message = str(original or exc).replace("\n", " ").strip()
    return message[:1000] if message else exc.__class__.__name__


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    parser = argparse.ArgumentParser(description="Import dedicated line excel files into MySQL.")
    parser.add_argument(
        "--data-dir",
        default=os.getenv("IMPORT_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "excel")),
        help="Excel directory path",
    )
    parser.add_argument("--chunk-size", type=int, default=500, help="Upsert batch size")
    parser.add_argument("--batch-name", default="", help="Optional batch name")
    parser.add_argument("--init-schema", action="store_true", help="Run sql/01_schema.sql before import")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing business rows; batch/error logs are recorded")
    args = parser.parse_args()

    database_url = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://dedicated_line@127.0.0.1:3306/dedicated_line?charset=utf8mb4",
    )
    engine = create_engine(database_url, pool_pre_ping=True, pool_recycle=1800, future=True)

    if args.init_schema:
        print("[INFO] applying schema ...")
        apply_schema(engine)

    data_dir = Path(args.data_dir)
    excel_files = discover_excel_files(data_dir)
    if not excel_files:
        raise SystemExit(f"[ERROR] no .xlsx files found in: {data_dir}")

    batch_name = args.batch_name or f"excel_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    initial_status = "DRY_RUN" if args.dry_run else "RUNNING"
    batch_id = create_batch(
        engine=engine,
        batch_name=batch_name,
        files_total=len(excel_files),
        status=initial_status,
    )
    print(f"[INFO] batch_id={batch_id}, files={len(excel_files)}")

    rows_processed = 0
    rows_affected = 0
    rows_failed = 0
    batch_status = "SUCCESS"
    message = "ok"

    try:
        for file_path in excel_files:
            print(f"[INFO] importing: {file_path.name}")
            with engine.begin() as conn:
                is_onu = file_path.name in ONU_FILE_NAMES
                if is_onu:
                    processed, affected, failed = import_onu_file(
                        conn=conn,
                        batch_id=batch_id,
                        file_path=file_path,
                        chunk_size=args.chunk_size,
                        dry_run=args.dry_run,
                    )
                else:
                    processed, affected, failed = import_line_file(
                        conn=conn,
                        batch_id=batch_id,
                        file_path=file_path,
                        chunk_size=args.chunk_size,
                        dry_run=args.dry_run,
                    )
            rows_processed += processed
            rows_affected += affected
            rows_failed += failed
            print(
                f"[INFO] {file_path.name}: processed={processed}, affected={affected}, failed={failed}"
            )

        if args.dry_run:
            batch_status = "DRY_RUN"
            message = "dry run completed"
        elif rows_failed > 0:
            batch_status = "PARTIAL_SUCCESS"
            message = f"completed with {rows_failed} row errors"
    except Exception as exc:
        batch_status = "FAILED"
        message = summarize_exception(exc)
        print(f"[ERROR] import aborted: {exc}")
        raise
    finally:
        finish_batch(
            engine=engine,
            batch_id=batch_id,
            status=batch_status,
            rows_processed=rows_processed,
            rows_affected=rows_affected,
            rows_failed=rows_failed,
            message=message,
        )
        print(
            f"[INFO] batch finished: status={batch_status}, processed={rows_processed}, "
            f"affected={rows_affected}, failed={rows_failed}"
        )


if __name__ == "__main__":
    main()
