"""Run after mysql_smoke.py, only on its disposable localhost *_test database."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import patch
import os
import sys
import tempfile
import time
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mysql_smoke import validate_test_url, write_fixture


def main():
    value = os.environ.get('MYSQL_TEST_DATABASE_URL', '')
    validate_test_url(value)
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    os.environ['DATABASE_URL'] = value
    from fastapi.testclient import TestClient
    import app.main as api
    from app.auth import authenticate_user, create_session, resolve_user_by_token, revoke_sessions_for_user
    from app.security import reserve_login_attempt, ACCOUNT_LIMIT
    from scripts.init_db import statements
    from scripts.manage_users import create_user, reset_password
    from scripts.import_excel import recover_interrupted_batches
    from app.import_lock import import_lock, ImportBusy
    engine = create_engine(value, pool_size=12)
    with engine.begin() as conn:
        for table in ['auth_users', 'customer_line_records', 'onu_inventory', 'import_batches']:
            if conn.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar_one():
                raise SystemExit('Refusing database with accounts/business rows/batches; run on an empty disposable test database')
        # Reconstruct the old column shape, then verify the upgrade can be repeated.
        conn.execute(text('ALTER TABLE auth_sessions DROP COLUMN auth_version'))
        conn.execute(text('ALTER TABLE auth_users DROP COLUMN auth_version'))
        for _ in range(2):
            for statement in statements(ROOT / 'sql/05_upgrade_security.sql'):
                conn.exec_driver_sql(statement)
    prefix = 'security_' + uuid.uuid4().hex[:10]
    password = uuid.uuid4().hex
    usernames = [prefix + '_admin', prefix + '_target']
    with engine.begin() as conn:
        for name, role in zip(usernames, ['admin', 'viewer']):
            create_user(conn, name, password, 'Synthetic', role)
        uid = conn.execute(text('SELECT id FROM auth_users WHERE username=:name'), {'name': usernames[1]}).scalar_one()

    def login(client, name, value):
        response = client.post('/api/auth/login', json={'username': name, 'password': value})
        assert response.status_code == 200, response.status_code
        return {'Authorization': 'Bearer ' + response.json()['access_token']}

    def snapshot():
        with engine.connect() as conn:
            return {table: conn.execute(text(f'SELECT * FROM {table} ORDER BY 1')).all()
                    for table in ['auth_users', 'auth_sessions', 'auth_user_roles', 'admin_operation_logs']}

    try:
        with TestClient(api.app, raise_server_exceptions=False) as client:
            headers = login(client, usernames[0], password)
            login(client, usernames[1], password)
            with engine.connect() as conn:
                sid = conn.execute(text('SELECT id FROM auth_sessions WHERE user_id=:id'), {'id': uid}).scalar_one()
            operations = [
                ('POST', '/api/admin/users', {'username': prefix + '_new', 'display_name': 'Synthetic', 'password': password, 'role': 'viewer'}),
                ('PATCH', f'/api/admin/users/{uid}', {'display_name': 'Changed'}),
                ('POST', f'/api/admin/users/{uid}/reset-password', {'password': uuid.uuid4().hex}),
                ('DELETE', f'/api/admin/users/{uid}', None),
                ('POST', f'/api/admin/sessions/{sid}/revoke', {}),
                ('POST', f'/api/admin/users/{uid}/revoke-sessions', {}),
            ]
            for method, path, body in operations:
                before = snapshot()
                with patch.object(api, '_log_admin_action', side_effect=RuntimeError('Synthetic storage failure')):
                    assert client.request(method, path, json=body, headers=headers).status_code == 500
                assert snapshot() == before
            response = client.patch(f'/api/admin/users/{uid}', json={'display_name': 'Synthetic updated'},
                                    headers={**headers, 'user-agent': 'A' * 300})
            assert response.status_code == 200
            with engine.connect() as conn:
                assert conn.execute(text("SELECT CHAR_LENGTH(user_agent) FROM admin_operation_logs WHERE action_code='user.update' ORDER BY id DESC LIMIT 1")).scalar_one() == 255
            with tempfile.TemporaryDirectory(prefix='dl-api-import-') as directory:
                directory = Path(directory)
                write_fixture(directory / '互联网专线.xlsx', 'Sheet0', {'区域': '示例区', '客户名称': '虚构企业', '产品号码': prefix})
                lock_path = directory / '.import.lock'
                with patch.dict(os.environ, {'IMPORT_LOCK_FILE': str(lock_path)}), \
                     patch.object(api, 'DEFAULT_IMPORT_DATA_DIR', directory), \
                     patch.object(api, 'IMPORT_LOG_DIR', directory / 'logs'):
                    response = client.post('/api/admin/import/run', json={'dry_run': True, 'batch_name': prefix + '_api'}, headers=headers)
                    assert response.status_code == 200, response.status_code
                    deadline = time.monotonic() + 30
                    while True:
                        with engine.connect() as conn:
                            batch = conn.execute(text('SELECT status FROM import_batches WHERE batch_name=:name'), {'name': prefix + '_api'}).scalar_one_or_none()
                        if batch == 'DRY_RUN':
                            try:
                                with import_lock(lock_path):
                                    break
                            except ImportBusy:
                                pass
                        assert batch != 'FAILED', 'API child failed; inspect disposable import log'
                        assert time.monotonic() < deadline, 'API child timed out'
                        time.sleep(0.05)
                with engine.begin() as conn:
                    assert conn.execute(text('SELECT COUNT(*) FROM customer_line_records')).scalar_one() == 0
                    conn.execute(text('DELETE FROM import_batches WHERE batch_name=:name'), {'name': prefix + '_api'})
        print('MySQL security: old-schema migration twice; six mutation rollbacks; long header normalization passed')
        print('MySQL security: actual API child inherited lock, passed audit gate, completed dry-run and released lock')

        for action in ['password', 'revoke']:
            ready, resume = Event(), Event()
            def late_login():
                with Session(engine) as db:
                    validated = authenticate_user(db, usernames[1], password)
                    assert validated
                    ready.set()
                    assert resume.wait(10)
                    try:
                        token, _ = create_session(db, uid, expected_version=validated['_auth_version'])
                        db.commit()
                    except api.HTTPException as exc:
                        assert exc.status_code == 401
                        return
                with Session(engine) as db:
                    assert resolve_user_by_token(db, token) is None
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(late_login)
                try:
                    assert ready.wait(10)
                    with engine.begin() as conn:
                        if action == 'password':
                            reset_password(conn, usernames[1], password)
                        else:
                            revoke_sessions_for_user(conn, uid)
                finally:
                    resume.set()
                future.result(timeout=15)
        print('MySQL security: concurrent password-reset/revoke-all fencing passed')

        with engine.begin() as conn:
            conn.execute(text('DELETE FROM auth_login_limits'))
        def attempt(n):
            with Session(engine) as db:
                return reserve_login_attempt(db, usernames[1].upper() if n % 2 else usernames[1], f'192.0.2.{n+1}')
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(16)))
        assert sum(result == 0 for result in results) == ACCOUNT_LIMIT, results
        assert sum(result > 0 for result in results) == 16 - ACCOUNT_LIMIT
        with Session(engine) as db:
            assert reserve_login_attempt(db, usernames[1], '198.51.100.99') > 0
        print('MySQL security: shared concurrent account limit and case aliases passed')

        with engine.begin() as conn:
            conn.execute(text("INSERT INTO import_batches (batch_name, status, started_at) VALUES (:name, 'RUNNING', NOW())"), {'name': prefix})
        recover_interrupted_batches(engine)
        with engine.connect() as conn:
            assert conn.execute(text('SELECT status FROM import_batches WHERE batch_name=:name'), {'name': prefix}).scalar_one() == 'FAILED'
        print('MySQL security: orphan batch recovery passed')
    finally:
        with engine.begin() as conn:
            conn.execute(text('DELETE FROM auth_users WHERE username IN (:a,:b,:c)'), {'a': usernames[0], 'b': usernames[1], 'c': prefix + '_new'})
            conn.execute(text('DELETE FROM import_batches WHERE batch_name=:name'), {'name': prefix})
        engine.dispose()


if __name__ == '__main__':
    main()
