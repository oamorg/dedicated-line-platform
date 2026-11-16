"""Exercise the documented release and deployment entry points without production data."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mysql_smoke_helpers', ROOT / 'tests/mysql_smoke.py')
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


@pytest.mark.parametrize('value', ['', 'sqlite://', 'not-a-url',
    'mysql+pymysql://test@example.invalid/demo_test',
    'mysql+pymysql://test@127.0.0.1/live',
    'mysql+pymysql://test@127.0.0.1/'])
def test_mysql_guard_rejects_unsafe_targets(value):
    with pytest.raises(ValueError):
        smoke.validate_test_url(value)


def test_mysql_guard_accepts_disposable_local_database():
    assert smoke.validate_test_url('mysql+pymysql://test@127.0.0.1/example_test').database == 'example_test'


def test_mysql_optimized_python_still_refuses_missing_test_url():
    env = os.environ.copy()
    env.pop('MYSQL_TEST_DATABASE_URL', None)
    env['DATABASE_URL'] = 'mysql+pymysql://test@example.invalid/live'
    result = subprocess.run([sys.executable, '-O', 'tests/mysql_smoke.py'], cwd=ROOT,
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert 'Set MYSQL_TEST_DATABASE_URL' in result.stderr
    assert 'Traceback' not in result.stderr


def test_fresh_deploy_writes_placeholder_then_stops(tmp_path):
    project = tmp_path / 'app with spaces'
    project.mkdir()
    for filename in ['deploy.sh', '.env.example']:
        shutil.copy2(ROOT / filename, project / filename)
    result = subprocess.run(['bash', str(project / 'deploy.sh')], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert 'Configure DATABASE_URL' in result.stdout
    assert (project / '.env').read_text() == (project / '.env.example').read_text()
    assert (project / '.env').stat().st_mode & 0o777 == 0o600
    assert not (project / '.venv').exists()


def test_release_payload_and_checksums(tmp_path):
    from scripts.check_release import source_files
    project = tmp_path / 'project'
    for path in source_files():
        destination = project / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    (project / '.env').write_text('SECRET=synthetic-excluded-fixture\n')
    (project / 'backups').mkdir()
    (project / 'backups' / 'internal.sql.gz').write_bytes(b'excluded fixture')
    result = subprocess.run([sys.executable, 'scripts/build_release.py', '--version', 'test'],
                            cwd=project, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    out = project / 'dist'
    assert {p.name for p in out.iterdir()} == {
        'dedicated-line-community-source-test.tar.gz',
        'dedicated-line-community-release-test.tar.gz',
        'dedicated_line_empty.sql', 'DEPLOYMENT.md', 'SHA256SUMS.txt',
    }
    assert '/blob/vtest/docs/TESTING.md' in (out / 'DEPLOYMENT.md').read_text()
    assert '(TESTING.md)' not in (out / 'DEPLOYMENT.md').read_text()
    guide = (out / 'DEPLOYMENT.md').read_text()
    assert '/blob/vtest/docs/OPERATIONS.md' in guide
    assert '/blob/vtest/docs/PUBLIC_READINESS.md' in guide
    assert not re.findall(r'\]\((?!https?://)[^)]*\.md(?:#[^)]*)?\)', guide)
    first_build = {p.name: p.read_bytes() for p in out.iterdir()}
    subprocess.run([sys.executable, 'scripts/build_release.py', '--version', 'test'],
                   cwd=project, check=True, capture_output=True, timeout=30)
    assert first_build == {p.name: p.read_bytes() for p in out.iterdir()}
    for entry in (out / 'SHA256SUMS.txt').read_text().splitlines():
        checksum, filename = entry.split('  ', 1)
        assert hashlib.sha256((out / filename).read_bytes()).hexdigest() == checksum
    with tarfile.open(out / 'dedicated-line-community-release-test.tar.gz') as archive:
        names = set(archive.getnames())
        assert 'README.md' in names
        assert archive.extractfile('docs/DEPLOYMENT.md').read() == (project / 'docs/DEPLOYMENT.md').read_bytes()
        assert 'Copyright (c) 2026 oamorg' in archive.extractfile('LICENSE').read().decode()
        assert all(member.isfile() and not member.name.startswith('/') and '..' not in Path(member.name).parts
                   for member in archive.getmembers())
        checked = set()
        for entry in archive.extractfile('SHA256SUMS.txt').read().decode().splitlines():
            checksum, filename = entry.split('  ', 1)
            assert hashlib.sha256(archive.extractfile(filename).read()).hexdigest() == checksum
            checked.add(filename)
        assert checked == names - {'SHA256SUMS.txt'}
        for name in names:
            if not name.endswith('.md'):
                continue
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', archive.extractfile(name).read().decode()):
                if '://' not in link and not link.startswith('#'):
                    assert str(Path(name).parent / link.split('#')[0]) in names
        sql = archive.extractfile('db/dedicated_line_empty.sql').read().decode()
        inserts = set(re.findall(r'INSERT\s+(?:IGNORE\s+)?INTO\s+([a-z_]+)', sql, re.I))
        assert inserts == {'auth_permissions', 'auth_roles', 'auth_role_permissions'}
        assert 'pbkdf2_sha256$' not in sql
    with tarfile.open(out / 'dedicated-line-community-source-test.tar.gz') as archive:
        names = set(archive.getnames())
        assert 'dedicated-line-platform/LICENSE' in names
        assert 'dedicated-line-platform/docs/TESTING.md' in names
        assert 'dedicated-line-platform/docs/OPERATIONS.md' in names
        assert 'dedicated-line-platform/scripts/backup.py' in names
        assert 'dedicated-line-platform/scripts/restore_verify.py' in names
        assert 'dedicated-line-platform/config/backup.example.json' in names
        assert 'dedicated-line-platform/.github/workflows/ci.yml' in names
        assert 'Copyright (c) 2026 oamorg' in archive.extractfile('dedicated-line-platform/LICENSE').read().decode()
        assert not any('/backups/' in name or name.endswith('/.env') for name in names)
        assert archive.getmember('dedicated-line-platform/deploy.sh').mode == 0o755


def test_backup_template_has_no_embedded_credentials():
    config = json.loads((ROOT / 'config/backup.example.json').read_text())
    assert set(config) == {'app_dir', 'database', 'backup_root', 'state_dir', 'runtime_dir',
                           'min_free_bytes', 'max_age_hours', 'config_paths'}
    assert all(Path(config[key]).is_absolute() for key in ('app_dir', 'backup_root', 'state_dir', 'runtime_dir'))
    assert config['database'] == 'dedicated_line'
    assert config['min_free_bytes'] > 0 and config['max_age_hours'] > 0


@pytest.mark.parametrize('name', ['backup.py', 'restore_verify.py'])
def test_backup_cli_help_without_deployment_config(name):
    result = subprocess.run([sys.executable, str(ROOT / 'scripts' / name), '--help'],
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and 'usage:' in result.stdout


def test_local_document_links_exist():
    paths = list(ROOT.glob('*.md')) + list((ROOT / 'docs').glob('*.md'))
    for path in paths:
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
            if '://' in link or link.startswith('#'):
                continue
            destination = (path.parent / link.split('#')[0]).resolve()
            assert destination.is_relative_to(ROOT), f'{path.name}: non-portable link'
            assert destination.is_file(), f'{path.name}: missing {link}'


def test_scan_rejects_staged_secret_even_when_worktree_is_clean(tmp_path):
    from scripts.check_release import source_files
    project = tmp_path / 'repo'
    for path in source_files():
        destination = project / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    subprocess.run(['git', 'init', '-b', 'main'], cwd=project, check=True, capture_output=True)
    readme = project / 'README.md'
    clean = readme.read_text()
    readme.write_text(clean + '\n' + 'gh' + 'p_' + 'A' * 36)
    subprocess.run(['git', 'add', 'README.md'], cwd=project, check=True)
    readme.write_text(clean)
    result = subprocess.run([sys.executable, 'scripts/check_release.py', '--tracked'],
                            cwd=project, capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert 'Staged README.md: GitHub token' in result.stderr
    assert 'A' * 36 not in result.stderr
