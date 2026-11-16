import json
import os
from pathlib import Path
from unittest.mock import Mock

os.environ['DATABASE_URL'] = 'sqlite://'

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.auth import create_session, get_current_user, hash_password, resolve_user_by_token, verify_password
from app.main import app, _serialize_line_list_row, _line_export_columns
import app.main as api
from scripts.init_db import statements
from scripts.manage_users import read_password, reset_password

ROOT = Path(__file__).resolve().parents[1]


def test_login_security_filter_options_are_real_html_elements():
    from html.parser import HTMLParser
    class Options(HTMLParser):
        active = False
        values = None
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'select' and attrs.get('name') == 'action':
                self.active = True
                self.values = []
            if tag == 'option' and self.active:
                self.values.append(attrs.get('value'))
        def handle_endtag(self, tag):
            if tag == 'select':
                self.active = False
    parser = Options()
    parser.feed((ROOT / 'web/index.html').read_text())
    assert parser.values == ['all', 'auth.login_limited', 'auth.login_blocked', 'auth.login_failed']


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize('path', [
    '/api/auth/me', '/api/lines/search', '/api/onu/search',
    '/api/lines/export', '/api/onu/export', '/api/lines/1', '/api/onu/1',
    '/api/admin/users', '/api/admin/roles', '/api/admin/sessions',
    '/api/admin/logs', '/api/admin/data/summary',
])
def test_private_endpoints_require_auth(client, path):
    assert client.get(path).status_code == 401


def test_public_assets_and_openapi(client):
    for path in ['/', '/static/app.js', '/static/styles.css', '/openapi.json']:
        assert client.get(path).status_code == 200


def test_viewer_cannot_export_or_manage(client):
    app.dependency_overrides[get_current_user] = lambda: {'id': 1, 'permissions': ['data.query']}
    for path in ['/api/lines/export', '/api/onu/export', '/api/admin/users']:
        assert client.get(path).status_code == 403
    assert client.post('/api/admin/import/run', json={'dry_run': True}).status_code == 403


def test_ipvpn_address_precedence_and_details():
    raw = {'用户地址': '192.0.2.1', '自带客户端互联IP': '192.0.2.10/29|192.0.2.11/29',
           '网关地址': '192.0.2.2', '自带局端互联IP': '192.0.2.9/29', '额外字段': '保留'}
    row = {'source_type': 'IPVPN专线', 'raw_data': json.dumps(raw)}
    result = _serialize_line_list_row(row)
    assert result['user_address'] == raw['自带客户端互联IP']
    assert result['gateway_address'] == raw['自带局端互联IP']
    row['source_type'] = '互联网专线'
    assert _serialize_line_list_row(row)['user_address'] == raw['用户地址']
    assert api._row_to_dict(row)['raw_data'] == raw


def test_all_source_export_order():
    assert [key for _, key in _line_export_columns(None)][4:6] == ['bandwidth', 'access_method']
    assert [key for _, key in _line_export_columns('互联网专线')][4] == 'access_method'


def test_no_seeded_accounts():
    parsed = list(statements(ROOT / 'sql/01_schema.sql'))
    assert not any('INSERT INTO auth_users' in sql or 'INSERT IGNORE INTO auth_user_roles' in sql for sql in parsed)
    assert any('INSERT INTO auth_roles' in sql for sql in parsed)
    for path in (ROOT / 'sql').glob('*.sql'):
        assert list(statements(path))


def test_password_and_session_revocation():
    engine = create_engine('sqlite://')
    with Session(engine) as db:
        for sql in [
            'CREATE TABLE auth_users (id INTEGER PRIMARY KEY, username TEXT, display_name TEXT, password_hash TEXT, is_active INTEGER, auth_version INTEGER DEFAULT 0)',
            'CREATE TABLE auth_roles (id INTEGER PRIMARY KEY, name TEXT)',
            'CREATE TABLE auth_permissions (id INTEGER PRIMARY KEY, code TEXT)',
            'CREATE TABLE auth_user_roles (user_id INTEGER, role_id INTEGER)',
            'CREATE TABLE auth_role_permissions (role_id INTEGER, permission_id INTEGER)',
            'CREATE TABLE auth_sessions (id INTEGER PRIMARY KEY, user_id INTEGER, token_hash TEXT, ip_address TEXT, user_agent TEXT, expires_at DATETIME, revoked_at DATETIME, auth_version INTEGER DEFAULT 0)',
        ]:
            db.execute(text(sql))
        hashed = hash_password('fictional-test-password')
        assert verify_password('fictional-test-password', hashed)
        assert not verify_password('wrong', hashed)
        assert hashed != hash_password('fictional-test-password')
        db.execute(text('INSERT INTO auth_users VALUES (1, :name, :name, :hash, 1, 0)'), {'name': 'demo', 'hash': hashed})
        token, _ = create_session(db, 1, expected_version=0)
        assert resolve_user_by_token(db, token)['username'] == 'demo'
        reset_password(db, 'demo', 'fictional-replacement-password')
        assert resolve_user_by_token(db, token) is None
        assert verify_password('fictional-replacement-password', db.execute(text('SELECT password_hash FROM auth_users')).scalar_one())
    engine.dispose()


def test_cli_password_prompt(monkeypatch):
    entries = iter(['fictional-test-password', 'fictional-test-password'])
    monkeypatch.setattr('scripts.manage_users.getpass', lambda _: next(entries))
    assert read_password(None) == 'fictional-test-password'
    with pytest.raises(ValueError):
        read_password('short')


def test_import_log_path_is_independent_of_batch_name(tmp_path, monkeypatch):
    monkeypatch.setenv('IMPORT_LOCK_FILE', str(tmp_path / '.import.lock'))
    log_dir = tmp_path / 'logs'
    monkeypatch.setattr(api, 'IMPORT_LOG_DIR', log_dir)
    monkeypatch.setattr(api, 'DEFAULT_IMPORT_DATA_DIR', tmp_path)
    monkeypatch.setattr(api, '_log_admin_action', Mock())
    process = Mock(pid=123)
    monkeypatch.setattr(api.subprocess, 'Popen', Mock(return_value=process))
    db = Mock()
    db.execute.return_value.mappings.return_value.first.return_value = None
    result = api.run_admin_import(api.AdminImportRunPayload(batch_name='../../outside', dry_run=True), Mock(), db, {'id': 1})
    assert Path(result['log_file']).parent == log_dir
    assert len(list(log_dir.glob('import_*.log'))) == 1
    assert result['batch_name'] == '../../outside'


def test_onu_sn_filter_search_and_export(client):
    app.dependency_overrides[get_current_user] = lambda: {'id': 1, 'permissions': ['data.query', 'data.export']}
    db = Mock()
    db.execute.return_value.scalar_one.return_value = 0
    db.execute.return_value.mappings.return_value.all.return_value = []
    app.dependency_overrides[api.get_db] = lambda: db
    for endpoint in ['search', 'export']:
        db.reset_mock()
        assert client.get(f'/api/onu/{endpoint}', params={'sn_code': "DEMO' OR 1=1 --"}).status_code == 200
        for call in db.execute.call_args_list:
            assert 'sn_code LIKE :sn_code' in str(call.args[0])
            assert call.args[1]['sn_code'] == "%DEMO' OR 1=1 --%"
