"""Run only on the disposable local *_test schema after mysql_security.py."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
import os
import sys
import time
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mysql_smoke import validate_test_url


def main():
    value = os.environ.get('MYSQL_TEST_DATABASE_URL', '')
    validate_test_url(value)
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    os.environ['DATABASE_URL'] = value
    from fastapi.testclient import TestClient
    import app.main as api
    from app.security import reserve_login_attempt, ip_bucket_key
    from scripts.init_db import statements
    from scripts.manage_users import create_user
    engine = create_engine(value, pool_size=12)
    with engine.begin() as conn:
        for name in ['auth_users', 'customer_line_records', 'onu_inventory', 'import_batches', 'auth_login_rules', 'auth_ip_blocks']:
            if conn.execute(text(f'SELECT COUNT(*) FROM {name}')).scalar_one():
                raise SystemExit('Refusing a database with accounts, business rows, settings or IP blocks')
        for _ in range(2):
            for statement in statements(ROOT / 'sql/06_login_security_admin.sql'):
                conn.exec_driver_sql(statement)
    prefix = 'login_security_' + uuid.uuid4().hex[:8]
    names = [prefix + '_admin', prefix + '_viewer']
    password = uuid.uuid4().hex
    base = '/api/admin/login-security'
    address = '198.51.100.20'
    with engine.begin() as conn:
        for username, role in zip(names, ['admin', 'viewer']):
            create_user(conn, username, password, 'Synthetic login security', role)
    def snapshot():
        with engine.connect() as conn:
            return {name: conn.execute(text(f'SELECT * FROM {name} ORDER BY 1')).all()
                    for name in ['auth_login_rules', 'auth_ip_blocks', 'auth_login_limits', 'admin_operation_logs']}
    try:
        with TestClient(api.app, raise_server_exceptions=False, client=('192.0.2.10', 1234)) as client:
            result = client.post('/api/auth/login', json={'username': names[0], 'password': password})
            assert result.status_code == 200
            headers = {'Authorization': 'Bearer ' + result.json()['access_token']}
            viewer = client.post('/api/auth/login', json={'username': names[1], 'password': password})
            viewer_headers = {'Authorization': 'Bearer ' + viewer.json()['access_token']}
            assert client.get(base + '/rules', headers=viewer_headers).status_code == 403
            rule = {'window_seconds': 60, 'account_limit': 3, 'ip_limit': 10, 'version': 0}
            before = snapshot()
            with patch.object(api, '_log_admin_action', side_effect=RuntimeError('Synthetic audit failure')):
                assert client.put(base + '/rules', json=rule, headers=headers).status_code == 500
            assert snapshot() == before
            assert client.put(base + '/rules', json=rule, headers=headers).status_code == 200
            assert client.put(base + '/rules', json=rule, headers=headers).status_code == 409
            with engine.begin() as conn:
                conn.execute(text('DELETE FROM auth_login_limits'))
            def attempt(number):
                with Session(engine) as db:
                    return reserve_login_attempt(db, names[1], f'192.0.2.{number+20}')
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(attempt, range(12)))
            assert sum(result == 0 for result in results) == 3
            updated = {**rule, 'version': 1, 'account_limit': 5}
            assert client.put(base + '/rules', json=updated, headers=headers).status_code == 200
            with Session(engine) as db:
                assert reserve_login_attempt(db, names[1], address) == 0
                assert reserve_login_attempt(db, names[1], address) > 0
            def concurrent_edit(_):
                with TestClient(api.app, client=('192.0.2.10', 1234)) as other:
                    return other.put(base + '/rules', json={**updated, 'version': 2}, headers=headers).status_code
            with ThreadPoolExecutor(max_workers=2) as pool:
                assert sorted(pool.map(concurrent_edit, range(2))) == [200, 409]
            print('MySQL login security: dynamic shared rules, audit rollback and concurrent edit protection passed')

            block = {'ip_address': '::ffff:' + address, 'duration_minutes': 5, 'reason': 'Synthetic integration'}
            before = snapshot()
            with patch.object(api, '_log_admin_action', side_effect=RuntimeError('Synthetic audit failure')):
                assert client.post(base + '/ip-blocks', json=block, headers=headers).status_code == 500
            assert snapshot() == before
            first = client.post(base + '/ip-blocks', json=block, headers=headers)
            assert first.status_code == 200 and first.json()['ip_address'] == address
            second = client.post(base + '/ip-blocks', json=block, headers=headers)
            assert second.status_code == 200 and second.json()['revision'] != first.json()['revision']
            release = {'ip_address': address, 'reason': 'Synthetic release', 'revision': second.json()['revision']}
            assert client.post(base + '/ip-blocks/release', json={**release, 'revision': first.json()['revision']}, headers=headers).status_code == 409
            with engine.begin() as conn:
                for statement in statements(ROOT / 'sql/06_login_security_admin.sql'):
                    conn.exec_driver_sql(statement)
            assert client.get(base + '/rules', headers=headers).json()['rules']['account_limit'] == 5
            assert client.get(base + '/ip-blocks', headers=headers).json()['total'] == 1
            with TestClient(api.app, client=(address, 1234)) as blocked:
                rejected = blocked.post('/api/auth/login', json={'username': names[1], 'password': password}, headers={'X-Forwarded-For': '192.0.2.99'})
                assert rejected.status_code == 429 and int(rejected.headers['retry-after']) > 0
            events = client.get(base + '/events', params={'action': 'auth.login_blocked', 'ip_address': address, 'username': names[1]}, headers=headers).json()
            assert events['total'] == 1 and events['items'][0]['target_label'] == names[1]
            assert abs(float(events['items'][0]['occurred_at']) - time.time()) < 10
            assert password not in str(events)
            before = snapshot()
            with patch.object(api, '_log_admin_action', side_effect=RuntimeError('Synthetic audit failure')):
                assert client.post(base + '/ip-blocks/release', json=release, headers=headers).status_code == 500
            assert snapshot() == before
            assert client.post(base + '/ip-blocks/release', json=release, headers=headers).status_code == 200
            with engine.connect() as conn:
                assert conn.execute(text('SELECT COUNT(*) FROM auth_login_limits WHERE bucket_key=:key'), {'key': ip_bucket_key(address)}).scalar_one() == 0
            with TestClient(api.app, client=(address, 1234)) as released:
                assert released.post('/api/auth/login', json={'username': names[1], 'password': password}).status_code == 429  # Account budget is preserved.
                assert released.post('/api/auth/login', json={'username': prefix + '_unknown', 'password': password}).status_code == 401
            client.post(base + '/ip-blocks', json=block, headers=headers).raise_for_status()
            with engine.begin() as conn:
                conn.execute(text('UPDATE auth_ip_blocks SET expires_at=1 WHERE ip_address=:ip'), {'ip': address})
            assert client.get(base + '/ip-blocks', headers=headers).json()['total'] == 0
            with TestClient(api.app, client=(address, 1234)) as expired:
                assert expired.post('/api/auth/login', json={'username': prefix + '_unknown', 'password': password}).status_code == 401
            print('MySQL login security: canonical IPs, real login blocking/expiry/release, preserved account budget, record filtering and migration idempotence passed')
    finally:
        with engine.begin() as conn:
            conn.execute(text('DELETE FROM auth_ip_blocks WHERE ip_address=:ip'), {'ip': address})
            conn.execute(text('DELETE FROM auth_login_rules WHERE id=1'))
            conn.execute(text('DELETE FROM auth_users WHERE username IN (:a,:b)'), {'a': names[0], 'b': names[1]})
        engine.dispose()


if __name__ == '__main__':
    main()
