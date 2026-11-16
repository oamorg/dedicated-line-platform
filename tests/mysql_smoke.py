"""Integration check for a new, empty, disposable local MySQL database."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def validate_test_url(value):
    if not value:
        raise ValueError('Set MYSQL_TEST_DATABASE_URL explicitly; deployment DATABASE_URL is never used')
    try:
        url = make_url(value)
    except Exception:
        raise ValueError('Invalid test database URL') from None
    if url.drivername != 'mysql+pymysql':
        raise ValueError('Test database must use mysql+pymysql')
    if url.host not in {'127.0.0.1', 'localhost'}:
        raise ValueError('Only a local test database is supported')
    if not url.database or not url.database.endswith('_test'):
        raise ValueError('Test database name must end in _test')
    return url


def write_fixture(path, sheet, row):
    from openpyxl import Workbook
    workbook = Workbook()
    workbook.active.title = sheet
    workbook.active.append(list(row))
    workbook.active.append(list(row.values()))
    workbook.save(path)
    workbook.close()


def main():
    try:
        validate_test_url(os.environ.get('MYSQL_TEST_DATABASE_URL', ''))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    # Set before importing the application. Ignore all deployment dotenv files.
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    os.environ['DATABASE_URL'] = os.environ['MYSQL_TEST_DATABASE_URL']
    engine = create_engine(os.environ['DATABASE_URL'], connect_args={'connect_timeout': 10})
    with engine.connect() as conn:
        if conn.exec_driver_sql('SHOW TABLES').first():
            raise SystemExit('Refusing a non-empty database; create a new disposable test database')

    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import engine as app_engine
    from scripts.manage_users import create_user

    marker = 'smoke_' + uuid.uuid4().hex[:12]
    users = {role: marker + '_' + role for role in ['viewer', 'exporter', 'admin']}
    password = uuid.uuid4().hex
    line = {'区域': '示例区', '客户名称': '示例企业（虚构）', '产品类型': '互联网专线',
            '产品号码': marker, '传输接入方式': 'GPON', '用户地址': '192.0.2.10',
            '网关地址': '192.0.2.9', '备注': '原始字段保留测试'}
    onu = {'ONUID': marker, 'ONU名称': '示例ONU', '客户名称': '示例企业（虚构）',
           '产品号码': marker, '业务类型': '互联网专线', 'SN码': marker,
           'ONU密码': 'DEMO-NOT-A-CREDENTIAL'}

    def run_script(script, *args):
        # Do not dump subprocess output that could contain a connection error with credentials.
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *args],
                                cwd=ROOT, env=os.environ.copy(), capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise RuntimeError(f'{script} failed (exit {result.returncode}); inspect in the disposable test environment')

    def count(conn, table):
        return conn.execute(text(f'SELECT COUNT(*) FROM {table} WHERE product_number=:marker'), {'marker': marker}).scalar_one()

    try:
        run_script('build_release.py', '--version', 'mysql-check')
        run_script('init_db.py', str(ROOT / 'dist/dedicated_line_empty.sql'))
        with engine.connect() as conn:
            for table in ['auth_users', 'auth_user_roles', 'auth_sessions', 'auth_login_limits', 'auth_login_rules', 'auth_ip_blocks', 'admin_operation_logs',
                          'customer_line_records', 'onu_inventory', 'import_batches', 'import_errors']:
                assert conn.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar_one() == 0
        for _ in range(2):
            run_script('init_db.py')
        with engine.begin() as conn:
            assert conn.execute(text('SELECT COUNT(*) FROM auth_users')).scalar_one() == 0
            for role, username in users.items():
                create_user(conn, username, password, 'Synthetic ' + role, role)
        with tempfile.TemporaryDirectory(prefix='dl-mysql-fixtures-') as directory:
            directory = Path(directory)
            write_fixture(directory / '互联网专线.xlsx', 'Sheet0', line)
            write_fixture(directory / 'ONU台账.xlsx', 'Sheet1', onu)
            run_script('import_excel.py', '--data-dir', str(directory), '--batch-name', marker + '_dry', '--dry-run')
            with engine.connect() as conn:
                assert count(conn, 'customer_line_records') == 0
                assert count(conn, 'onu_inventory') == 0
                assert conn.execute(text('SELECT status FROM import_batches WHERE batch_name=:name'), {'name': marker + '_dry'}).scalar_one() == 'DRY_RUN'
            for suffix in ['_import', '_repeat']:
                run_script('import_excel.py', '--data-dir', str(directory), '--batch-name', marker + suffix)
                with engine.connect() as conn:
                    assert count(conn, 'customer_line_records') == 1
                    assert count(conn, 'onu_inventory') == 1
                    assert conn.execute(text('SELECT status FROM import_batches WHERE batch_name=:name'), {'name': marker + suffix}).scalar_one() == 'SUCCESS'
        with TestClient(app) as client:
            assert client.get('/health').status_code == 200
            assert client.post('/api/auth/login', json={'username': users['viewer'], 'password': 'wrong'}).status_code == 401
            for role, username in users.items():
                response = client.post('/api/auth/login', json={'username': username, 'password': password})
                assert response.status_code == 200
                headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
                response = client.get('/api/onu/search', params={'sn_code': marker}, headers=headers)
                assert response.status_code == 200 and response.json()['total'] == 1
                response = client.get('/api/lines/search', params={'product_number': marker}, headers=headers)
                assert response.status_code == 200 and response.json()['total'] == 1
                item = response.json()['items'][0]
                detail = client.get(f'/api/lines/{item["id"]}', headers=headers)
                assert detail.status_code == 200 and detail.json()['raw_data'] == line
                for kind in ['lines', 'onu']:
                    export = client.get(f'/api/{kind}/export', params={'product_number': marker}, headers=headers)
                    assert export.status_code == (403 if role == 'viewer' else 200)
                    if role != 'viewer':
                        assert export.json()['count'] == 1
                assert client.get('/api/admin/users', headers=headers).status_code == (200 if role == 'admin' else 403)
                assert client.post('/api/auth/logout', headers=headers).status_code == 200
                assert client.get('/api/auth/me', headers=headers).status_code == 401
    finally:
        # Only remove this run's synthetic rows, retaining tables for diagnosis.
        with engine.begin() as conn:
            existing = {row[0] for row in conn.exec_driver_sql('SHOW TABLES')}
            for table in ['customer_line_records', 'onu_inventory']:
                if table in existing:
                    conn.execute(text(f'DELETE FROM {table} WHERE product_number=:marker'), {'marker': marker})
            for username in users.values():
                if 'auth_users' in existing:
                    conn.execute(text('DELETE FROM auth_users WHERE username=:name'), {'name': username})
            for suffix in ['_dry', '_import', '_repeat']:
                if 'import_batches' in existing:
                    if 'import_errors' in existing:
                        conn.execute(text('DELETE FROM import_errors WHERE batch_id IN (SELECT id FROM import_batches WHERE batch_name=:name)'), {'name': marker + suffix})
                    conn.execute(text('DELETE FROM import_batches WHERE batch_name=:name'), {'name': marker + suffix})
        app_engine.dispose()
        engine.dispose()
    print('MySQL: release SQL restore, migrations, dry-run/import/deduplication, login/query/detail/export/roles/logout passed')


if __name__ == '__main__':
    main()
