"""Login-security management regression with synthetic accounts and addresses."""
import json
import time

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

import app.main as api
from app.auth import get_current_user
from app.security import blocked_login_retry, ip_bucket_key, login_rules, normalize_ip, reserve_login_attempt
from test_security import engine, client, PASSWORD  # Reuse the isolated SQLite fixtures.

BASE = '/api/admin/login-security'
RULES = {'window_seconds': 60, 'account_limit': 3, 'ip_limit': 10, 'version': 0}
BLOCK = {'ip_address': '198.51.100.20', 'duration_minutes': 5, 'reason': 'Synthetic regression'}


def admin():
    api.app.dependency_overrides[get_current_user] = lambda: {'id': 1, 'username': 'synthetic-admin', 'permissions': ['user.manage']}


@pytest.mark.parametrize('method,path,body', [
    ('GET', '/rules', None), ('PUT', '/rules', RULES), ('GET', '/events', None),
    ('GET', '/ip-blocks', None), ('POST', '/ip-blocks', BLOCK),
    ('POST', '/ip-blocks/release', {**BLOCK, 'revision': 'a' * 32}),
])
def test_admin_only(client, method, path, body):
    assert client.request(method, BASE + path, json=body).status_code == 401
    for permission in [['data.query'], ['data.query', 'data.export']]:
        api.app.dependency_overrides[get_current_user] = lambda: {'id': 2, 'permissions': permission}
        assert client.request(method, BASE + path, json=body).status_code == 403


def test_rules_apply_without_resetting_existing_window(client, engine):
    admin()
    assert client.get(BASE + '/rules').json()['rules']['version'] == 0
    with Session(engine) as db:
        assert reserve_login_attempt(db, 'synthetic-target', BLOCK['ip_address'], now=1000) == 0
    response = client.put(BASE + '/rules', json=RULES)
    assert response.status_code == 200 and response.json()['rules']['version'] == 1
    assert client.put(BASE + '/rules', json=RULES).status_code == 409
    with Session(engine) as db:
        assert login_rules(db)['account_limit'] == 3
        for _ in range(2):
            assert reserve_login_attempt(db, 'synthetic-target', BLOCK['ip_address'], now=1001) == 0
        detail = {}
        assert reserve_login_attempt(db, 'synthetic-target', BLOCK['ip_address'], now=1001, details=detail) == 899
        assert detail['dimension'] == 'account'
        assert reserve_login_attempt(db, 'synthetic-target', BLOCK['ip_address'], now=1900) == 0
        assert db.execute(text('SELECT reset_at FROM auth_login_limits WHERE bucket_key=:key'),
                          {'key': ip_bucket_key(BLOCK['ip_address'])}).scalar_one() == 1960
    updated = client.put(BASE + '/rules', json={**RULES, 'version': 1, 'account_limit': 4})
    assert updated.status_code == 200 and updated.json()['rules']['version'] == 2


@pytest.mark.parametrize('change', [
    {'window_seconds': 0}, {'window_seconds': 3601}, {'window_seconds': True},
    {'account_limit': 2}, {'account_limit': 101}, {'ip_limit': 9}, {'ip_limit': 1001},
    {'account_limit': 20, 'ip_limit': 10}, {'version': -1}, {'window_seconds': 60.5},
])
def test_reject_invalid_rules(client, change):
    admin()
    assert client.put(BASE + '/rules', json={**RULES, **change}).status_code == 422
    assert client.get(BASE + '/rules').json()['rules']['version'] == 0


@pytest.mark.parametrize('address', ['127.0.0.1', '::1', '::ffff:127.0.0.1', '0.0.0.0', '::', '224.0.0.1', 'ff02::1', 'fe80::1'])
def test_protected_addresses(client, address):
    admin()
    assert client.post(BASE + '/ip-blocks', json={**BLOCK, 'ip_address': address}).status_code == 400


@pytest.mark.parametrize('change', [
    {'ip_address': 'invalid'}, {'ip_address': '198.51.100.0/24'}, {'ip_address': 'fe80::1%eth0'},
    {'duration_minutes': 0}, {'duration_minutes': 10081}, {'duration_minutes': True},
    {'reason': '   '}, {'reason': 'invalid\x00reason'},
])
def test_invalid_blocks(client, change):
    admin()
    assert client.post(BASE + '/ip-blocks', json={**BLOCK, **change}).status_code == 422


def test_cannot_block_current_source(client, monkeypatch):
    admin()
    monkeypatch.setattr(api, '_client_ip', lambda request: BLOCK['ip_address'])
    assert client.post(BASE + '/ip-blocks', json=BLOCK).status_code == 400


def test_block_expiry_login_audit_and_release(client, engine, monkeypatch):
    admin()
    now = int(time.time())
    monkeypatch.setattr(api, 'epoch_time', lambda: now)
    monkeypatch.setattr('app.security.time.time', lambda: now)
    response = client.post(BASE + '/ip-blocks', json={**BLOCK, 'ip_address': '::ffff:198.51.100.20'})
    assert response.status_code == 200
    assert response.json()['ip_address'] == BLOCK['ip_address']
    revision = response.json()['revision']
    with Session(engine) as db:
        assert blocked_login_retry(db, BLOCK['ip_address'], now=now) == 300
        assert blocked_login_retry(db, BLOCK['ip_address'], now=now + 300) == 0
        reserve_login_attempt(db, 'synthetic-target', BLOCK['ip_address'], now=now)
    monkeypatch.setattr(api, '_client_ip', lambda request: BLOCK['ip_address'])
    denied = client.post('/api/auth/login', json={'username': 'synthetic-target', 'password': PASSWORD})
    assert denied.status_code == 429 and denied.headers['retry-after'] == '300'
    events = client.get(BASE + '/events', params={'action': 'auth.login_blocked', 'ip_address': BLOCK['ip_address'], 'username': 'synthetic-target'}).json()
    assert events['total'] == 1 and events['items'][0]['detail_json']['dimension'] == 'manual_ip'
    assert PASSWORD not in json.dumps(events)
    released = client.post(BASE + '/ip-blocks/release', json={**BLOCK, 'revision': revision, 'reason': 'Synthetic release'})
    assert released.status_code == 200
    with Session(engine) as db:
        assert blocked_login_retry(db, BLOCK['ip_address']) == 0
        assert db.execute(text('SELECT COUNT(*) FROM auth_login_limits WHERE bucket_key=:key'), {'key': ip_bucket_key(BLOCK['ip_address'])}).scalar_one() == 0
        assert db.execute(text('SELECT COUNT(*) FROM auth_login_limits')).scalar_one() == 1
    allowed = client.post('/api/auth/login', json={'username': 'synthetic-target', 'password': PASSWORD})
    assert allowed.status_code == 200


def test_expired_blocks_hidden_and_revision_guards_release(client, monkeypatch):
    admin()
    now = 2000000000
    monkeypatch.setattr(api, 'epoch_time', lambda: now)
    first = client.post(BASE + '/ip-blocks', json=BLOCK).json()
    second = client.post(BASE + '/ip-blocks', json=BLOCK).json()
    assert first['revision'] != second['revision']
    assert client.post(BASE + '/ip-blocks/release', json={**BLOCK, 'revision': first['revision']}).status_code == 409
    assert client.get(BASE + '/ip-blocks').json()['total'] == 1
    monkeypatch.setattr(api, 'epoch_time', lambda: now + 300)
    assert client.get(BASE + '/ip-blocks').json()['total'] == 0


@pytest.mark.parametrize('operation', ['rules', 'block', 'release'])
def test_security_changes_rollback_with_audit_failure(client, engine, monkeypatch, operation):
    admin()
    revision = client.post(BASE + '/ip-blocks', json=BLOCK).json()['revision']
    def snapshot():
        with engine.connect() as connection:
            return {name: connection.execute(text(f'SELECT * FROM {name}')).all()
                    for name in ['auth_ip_blocks', 'auth_login_rules', 'auth_login_limits', 'admin_operation_logs']}
    with Session(engine) as db:
        reserve_login_attempt(db, 'synthetic-target', BLOCK['ip_address'])
    before = snapshot()
    def fail(*args, **kwargs):
        raise RuntimeError('Synthetic audit failure')
    monkeypatch.setattr(api, '_log_admin_action', fail)
    if operation == 'rules':
        response = client.put(BASE + '/rules', json=RULES)
    elif operation == 'block':
        response = client.post(BASE + '/ip-blocks', json={**BLOCK, 'duration_minutes': 10})
    else:
        response = client.post(BASE + '/ip-blocks/release', json={**BLOCK, 'revision': revision})
    assert response.status_code == 500
    assert snapshot() == before


def test_event_pagination_filters_and_no_passwords(client):
    admin()
    for _ in range(12):
        client.post('/api/auth/login', json={'username': 'synthetic-target', 'password': 'not-recorded-password'})
    limited = client.get(BASE + '/events', params={'action': 'auth.login_limited', 'size': 1}).json()
    assert limited['total'] == 2 and len(limited['items']) == 1
    assert limited['items'][0]['detail_json']['dimension'] == 'account'
    assert abs(limited['items'][0]['occurred_at'] - int(time.time())) < 10
    second = client.get(BASE + '/events', params={'action': 'auth.login_limited', 'size': 1, 'page': 2}).json()
    assert second['items'][0]['id'] != limited['items'][0]['id']
    assert client.get(BASE + '/events', params={'username': "' OR 1=1 --"}).json()['total'] == 0
    assert client.get(BASE + '/events', params={'action': 'security.rules_updated'}).status_code == 422
    assert client.get(BASE + '/events', params={'ip_address': 'invalid'}).status_code == 422
    assert client.get(BASE + '/events', params={'size': 1001}).status_code == 422
    assert 'not-recorded-password' not in json.dumps(client.get(BASE + '/events').json())


def test_ipv6_canonicalization():
    assert normalize_ip('2001:0db8:0:0:0:0:0:1') == '2001:db8::1'
    assert normalize_ip('::ffff:198.51.100.20') == '198.51.100.20'
