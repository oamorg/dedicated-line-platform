"""Exercise the documented release and deployment entry points without production data."""
import hashlib
import importlib.util
import os
from pathlib import Path
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
    first_build = {p.name: p.read_bytes() for p in out.iterdir()}
    subprocess.run([sys.executable, 'scripts/build_release.py', '--version', 'test'],
                   cwd=project, check=True, capture_output=True, timeout=30)
    assert first_build == {p.name: p.read_bytes() for p in out.iterdir()}
    for entry in (out / 'SHA256SUMS.txt').read_text().splitlines():
        checksum, filename = entry.split('  ', 1)
        assert hashlib.sha256((out / filename).read_bytes()).hexdigest() == checksum
    with tarfile.open(out / 'dedicated-line-community-release-test.tar.gz') as archive:
        for entry in archive.extractfile('SHA256SUMS.txt').read().decode().splitlines():
            checksum, filename = entry.split('  ', 1)
            assert hashlib.sha256(archive.extractfile(filename).read()).hexdigest() == checksum
        sql = archive.extractfile('db/dedicated_line_empty.sql').read().decode()
        assert 'INSERT INTO auth_users' not in sql
        assert 'INSERT INTO customer_line_records' not in sql
    with tarfile.open(out / 'dedicated-line-community-source-test.tar.gz') as archive:
        names = set(archive.getnames())
        assert 'dedicated-line-platform/LICENSE' in names
        assert 'dedicated-line-platform/docs/TESTING.md' in names
        assert 'dedicated-line-platform/.github/workflows/ci.yml' in names
        assert not any('/backups/' in name or name.endswith('/.env') for name in names)
        assert archive.getmember('dedicated-line-platform/deploy.sh').mode == 0o755


def test_local_document_links_exist():
    import re
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
