"""Regression tests using synthetic data; never read deployment dotenv files."""
import os
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

os.environ['PYTHON_DOTENV_DISABLED'] = '1'
os.environ['DATABASE_URL'] = 'sqlite://'

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

import app.main as api
from app.auth import authenticate_user, create_session, get_current_user, hash_password, resolve_user_by_token, revoke_sessions_for_user
from app.import_lock import ImportBusy, import_lock
from app.security import reserve_login_attempt, ACCOUNT_LIMIT, IP_LIMIT, WINDOW_SECONDS
from scripts.import_excel import load_sheet_rows, recover_interrupted_batches
from scripts.manage_users import reset_password

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = 'synthetic-regression-password'


@pytest.fixture
def engine():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    with engine.begin() as conn:
        for sql in [
            'CREATE TABLE auth_users (id INTEGER PRIMARY KEY, username TEXT UNIQUE COLLATE NOCASE, display_name TEXT, password_hash TEXT, is_active INTEGER, auth_version INTEGER DEFAULT 0)',
            'CREATE TABLE auth_roles (id INTEGER PRIMARY KEY, name TEXT)',
            'CREATE TABLE auth_permissions (id INTEGER PRIMARY KEY, code TEXT)',
            'CREATE TABLE auth_user_roles (user_id INTEGER, role_id INTEGER)',
            'CREATE TABLE auth_role_permissions (role_id INTEGER, permission_id INTEGER)',
            'CREATE TABLE auth_sessions (id INTEGER PRIMARY KEY, user_id INTEGER, token_hash TEXT, ip_address TEXT, user_agent TEXT CHECK(length(user_agent)<=255), expires_at DATETIME, revoked_at DATETIME, auth_version INTEGER DEFAULT 0)',
            'CREATE TABLE auth_login_limits (bucket_key TEXT PRIMARY KEY, attempts INTEGER, reset_at INTEGER)',
            'CREATE TABLE auth_login_rules (id INTEGER PRIMARY KEY, window_seconds INTEGER, account_limit INTEGER, ip_limit INTEGER, version INTEGER, updated_at INTEGER)',
            'CREATE TABLE auth_ip_blocks (ip_address TEXT PRIMARY KEY, expires_at INTEGER, blocked_at INTEGER, blocked_by INTEGER, reason TEXT, revision TEXT)',
            'CREATE TABLE admin_operation_logs (id INTEGER PRIMARY KEY, actor_user_id INTEGER, actor_username TEXT, action_code TEXT, target_type TEXT, target_id INTEGER, target_label TEXT, status TEXT, detail_json TEXT, ip_address TEXT, user_agent TEXT CHECK(length(user_agent)<=255), created_at DATETIME DEFAULT CURRENT_TIMESTAMP)',
            'CREATE TABLE import_batches (id INTEGER PRIMARY KEY, status TEXT, finished_at DATETIME, message TEXT)',
        ]:
            conn.execute(text(sql))
        for uid, name in [(1, 'synthetic-admin'), (2, 'synthetic-target')]:
            conn.execute(text('INSERT INTO auth_users VALUES (:id,:name,:name,:hash,1,0)'),
                         {'id': uid, 'name': name, 'hash': hash_password(PASSWORD)})
        conn.execute(text("INSERT INTO auth_roles VALUES (1, 'viewer')"))
        conn.execute(text('INSERT INTO auth_user_roles VALUES (2, 1)'))
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine, monkeypatch):
    def database():
        with Session(engine) as db:
            yield db
    def sqlite_admin_user(db, user_id):
        # Only the MySQL-specific GROUP_CONCAT helper is replaced in unit tests.
        row = db.execute(text('SELECT * FROM auth_users WHERE id=:id'), {'id': user_id}).mappings().first()
        return {**row, 'roles': ['viewer'], 'active_sessions': 1} if row else None
    monkeypatch.setattr(api, '_get_admin_user', sqlite_admin_user)
    api.app.dependency_overrides.clear()
    api.app.dependency_overrides[api.get_db] = database
    with TestClient(api.app, raise_server_exceptions=False) as client:
        yield client
    api.app.dependency_overrides.clear()


OPERATIONS = [
    ('POST', '/api/admin/users', {'username': 'synthetic-new', 'display_name': 'Synthetic', 'password': PASSWORD, 'role': 'viewer'}),
    ('PATCH', '/api/admin/users/2', {'display_name': 'Changed'}),
    ('POST', '/api/admin/users/2/reset-password', {'password': 'synthetic-new-password'}),
    ('DELETE', '/api/admin/users/2', None),
    ('POST', '/api/admin/sessions/1/revoke', {}),
    ('POST', '/api/admin/users/2/revoke-sessions', {}),
]


def snapshot(engine):
    with engine.connect() as conn:
        return {table: conn.execute(text(f'SELECT * FROM {table} ORDER BY 1')).all()
                for table in ['auth_users', 'auth_sessions', 'auth_user_roles', 'admin_operation_logs']}


@pytest.mark.parametrize('method,path,body', OPERATIONS)
@pytest.mark.parametrize('fail_audit', [False, True])
def test_admin_changes_and_audit_are_atomic(client, engine, monkeypatch, method, path, body, fail_audit):
    with Session(engine) as db:
        create_session(db, 2, expected_version=0)
        db.commit()
    api.app.dependency_overrides[get_current_user] = lambda: {'id': 1, 'username': 'synthetic-admin', 'permissions': ['user.manage']}
    before = snapshot(engine)
    if fail_audit:
        def fail(*args, **kwargs):
            raise RuntimeError('synthetic audit storage failure')
        monkeypatch.setattr(api, '_log_admin_action', fail)
    result = client.request(method, path, json=body, headers={'user-agent': 'A' * 300})
    if fail_audit:
        assert result.status_code == 500
        assert snapshot(engine) == before
    else:
        assert result.status_code == 200
        with engine.connect() as conn:
            assert conn.execute(text('SELECT COUNT(*) FROM admin_operation_logs')).scalar_one() == 1
            assert len(conn.execute(text('SELECT user_agent FROM admin_operation_logs')).scalar_one()) == 255


@pytest.mark.parametrize('method,path,body', OPERATIONS + [('POST', '/api/admin/import/run', {})])
def test_mutation_permission_boundaries(client, method, path, body):
    assert client.request(method, path, json=body).status_code == 401
    api.app.dependency_overrides[get_current_user] = lambda: {'id': 2, 'permissions': ['data.query']}
    assert client.request(method, path, json=body).status_code == 403


def test_login_account_budget_and_audit(client, engine):
    for _ in range(ACCOUNT_LIMIT):
        assert client.post('/api/auth/login', json={'username': 'synthetic-admin', 'password': 'wrong'}).status_code == 401
    result = client.post('/api/auth/login', json={'username': 'SYNTHETIC-ADMIN', 'password': PASSWORD})
    assert result.status_code == 429 and int(result.headers['retry-after']) > 0
    with engine.connect() as conn:
        logs = conn.execute(text('SELECT action_code, detail_json FROM admin_operation_logs')).all()
        assert len(logs) == ACCOUNT_LIMIT + 1
        assert logs[-1][0] == 'auth.login_limited'
        assert all(PASSWORD not in str(log) and 'wrong' not in str(log) for log in logs)


def test_shared_login_limits_and_expiry(engine):
    for n in range(ACCOUNT_LIMIT):
        with Session(engine) as worker:
            assert reserve_login_attempt(worker, 'synthetic-admin', f'192.0.2.{n+1}', now=1000) == 0
    with Session(engine) as worker:
        assert reserve_login_attempt(worker, 'SYNTHETIC-ADMIN', '192.0.2.200', now=1001) > 0
        assert reserve_login_attempt(worker, 'synthetic-admin', '192.0.2.200', now=1000 + WINDOW_SECONDS) == 0
    for n in range(IP_LIMIT):
        with Session(engine) as worker:
            assert reserve_login_attempt(worker, f'unknown-{n}', '198.51.100.1', now=5000) == 0
    with Session(engine) as worker:
        assert reserve_login_attempt(worker, 'another-name', '198.51.100.1', now=5000) > 0


@pytest.mark.parametrize('action', ['password', 'revoke'])
def test_old_validation_cannot_issue_session_after_invalidation(engine, action):
    with Session(engine) as db:
        validated = authenticate_user(db, 'synthetic-target', PASSWORD)
        db.commit()
        if action == 'password':
            reset_password(db, 'synthetic-target', 'synthetic-new-password')
        else:
            revoke_sessions_for_user(db, 2)
        db.commit()
        with pytest.raises(api.HTTPException) as error:
            create_session(db, 2, expected_version=validated['_auth_version'])
        assert error.value.status_code == 401


def test_all_sessions_revoked_except_current_and_epoch_checked(engine):
    with Session(engine) as db:
        current, _ = create_session(db, 2, expected_version=0)
        other, _ = create_session(db, 2, expected_version=0)
        keep = resolve_user_by_token(db, current)['session_id']
        assert revoke_sessions_for_user(db, 2, exclude_session_id=keep) == 1
        db.commit()
        assert resolve_user_by_token(db, current) is not None
        assert resolve_user_by_token(db, other) is None
        # Even an unrevoked late row with the old epoch cannot authenticate.
        db.execute(text('UPDATE auth_sessions SET revoked_at=NULL WHERE id<>:id'), {'id': keep})
        db.commit()
        assert resolve_user_by_token(db, other) is None


def test_headers_and_untrusted_forwarding(client):
    request = Request({'type': 'http', 'headers': [(b'x-forwarded-for', b'198.51.100.99')], 'client': ('192.0.2.1', 1)})
    assert api._client_ip(request) == '192.0.2.1'
    for path in ['/', '/api/auth/me']:
        response = client.get(path)
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-frame-options'] == 'DENY'


def workbook(tmp_path, rows):
    path = tmp_path / '互联网专线.xlsx'
    book = Workbook()
    book.active.title = 'Sheet0'
    for row in rows:
        book.active.append(row)
    book.save(path)
    book.close()
    return path


def test_header_not_selected_by_density(tmp_path):
    path = workbook(tmp_path, [['区域', '客户名称', '产品号码', None], ['示例区', '虚构A', 'DEMO-A', 'extra'], ['示例区', '虚构B', 'DEMO-B', 'extra']])
    rows, _ = load_sheet_rows(path)
    assert len(rows) == 2 and rows[0][0] == 2
    assert rows[0][1]['客户名称'] == '虚构A'
    assert rows[0][1]['_col_4'] == 'extra'


@pytest.mark.parametrize('rows', [
    [['区域', '客户名称'], ['示例区', '虚构A']],
    [['区域', '客户名称', '产品号码', '产品号码']],
    [['区域', '客户名称', '产品号码'], ['区域', '客户名称', '产品号码']],
    [['unknown', 'template'], ['A', 'B']],
])
def test_ambiguous_or_invalid_headers_rejected(tmp_path, rows):
    with pytest.raises(ValueError):
        load_sheet_rows(workbook(tmp_path, rows))


def test_title_row_is_not_header(tmp_path):
    rows, _ = load_sheet_rows(workbook(tmp_path, [['Report title'], ['区域', '客户名称', '产品号码'], ['示例区', '虚构A', 'DEMO']]))
    assert len(rows) == 1 and rows[0][0] == 3


def test_explicit_header_still_validates_and_unknown_file_rejected(tmp_path, monkeypatch):
    import scripts.import_excel as importer
    (tmp_path / 'config').mkdir()
    config = tmp_path / 'config/source_files.json'
    config.write_text(json.dumps({'line_files': {'互联网专线.xlsx': {'header_row': 2}}}))
    monkeypatch.setattr(importer, 'PROJECT_ROOT', tmp_path)
    path = workbook(tmp_path, [['Report'], ['区域', '客户名称', '产品号码'], ['示例区', '虚构A', 'DEMO']])
    assert len(load_sheet_rows(path)[0]) == 1
    config.write_text(json.dumps({'line_files': {'互联网专线.xlsx': {'header_row': 1}}}))
    with pytest.raises(ValueError):
        load_sheet_rows(path)
    unknown = tmp_path / 'unconfigured.xlsx'
    path.rename(unknown)
    with pytest.raises(ValueError, match='Unconfigured'):
        load_sheet_rows(unknown)


def test_import_lock_transfers_to_child_and_recovers_after_crash(tmp_path):
    path = tmp_path / '.import.lock'
    child = None
    try:
        with import_lock(path) as fd:
            child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], pass_fds=(fd,))
        with pytest.raises(ImportBusy):
            with import_lock(path):
                pass
        child.kill()
        child.wait(timeout=10)
        with import_lock(path):
            pass
    finally:
        if child and child.poll() is None:
            child.kill()
            child.wait(timeout=10)


def test_orphan_batch_recovery(engine):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO import_batches (status) VALUES ('RUNNING'), ('SUCCESS')"))
    recover_interrupted_batches(engine)
    with engine.connect() as conn:
        assert conn.execute(text('SELECT status FROM import_batches ORDER BY id')).scalars().all() == ['FAILED', 'SUCCESS']


def test_import_not_released_before_audit_commit(tmp_path, monkeypatch):
    monkeypatch.setenv('IMPORT_LOCK_FILE', str(tmp_path / '.import.lock'))
    monkeypatch.setattr(api, 'DEFAULT_IMPORT_DATA_DIR', tmp_path)
    monkeypatch.setattr(api, 'IMPORT_LOG_DIR', tmp_path / 'logs')
    process = Mock(pid=123)
    monkeypatch.setattr(api.subprocess, 'Popen', Mock(return_value=process))
    monkeypatch.setattr(api, '_log_admin_action', Mock(side_effect=RuntimeError('audit failure')))
    with pytest.raises(RuntimeError):
        api.run_admin_import(api.AdminImportRunPayload(), Mock(), Mock(), {}, )
    process.stdin.write.assert_not_called()
    process.terminate.assert_called_once()
    with import_lock(tmp_path / '.import.lock'):
        pass


@pytest.mark.parametrize('dry_run', [False, True])
def test_running_lock_rejects_api_and_cli(tmp_path, monkeypatch, dry_run):
    path = tmp_path / '.import.lock'
    monkeypatch.setenv('IMPORT_LOCK_FILE', str(path))
    with import_lock(path):
        with pytest.raises(api.HTTPException) as error:
            api.run_admin_import(api.AdminImportRunPayload(dry_run=dry_run), Mock(), Mock(), {})
        assert error.value.status_code == 409
        with pytest.raises(ImportBusy):
            with import_lock(path):
                pass


def test_failed_spawn_releases_lock(tmp_path, monkeypatch):
    path = tmp_path / '.import.lock'
    monkeypatch.setenv('IMPORT_LOCK_FILE', str(path))
    monkeypatch.setattr(api, 'DEFAULT_IMPORT_DATA_DIR', tmp_path)
    monkeypatch.setattr(api, 'IMPORT_LOG_DIR', tmp_path / 'logs')
    monkeypatch.setattr(api.subprocess, 'Popen', Mock(side_effect=OSError('synthetic spawn failure')))
    with pytest.raises(OSError):
        api.run_admin_import(api.AdminImportRunPayload(), Mock(), Mock(), {})
    with import_lock(path):
        pass
