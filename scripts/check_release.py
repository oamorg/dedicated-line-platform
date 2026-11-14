#!/usr/bin/env python3
"""Check only approved source files; optionally reject unexpected tracked files."""
from pathlib import Path
import argparse
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TOP_FILES = {
    'README.md', 'LICENSE', 'SECURITY.md', 'CONTRIBUTING.md', '.gitignore',
    '.env.example', 'requirements.txt', 'requirements-dev.txt', 'deploy.sh',
}
DIRECTORIES = {'app', 'web', 'config', 'sql', 'scripts', 'tests', 'docs', '.github'}
SUFFIXES = {'.py', '.js', '.cjs', '.html', '.css', '.json', '.sql', '.md', '.yml', '.yaml'}
IGNORE = {'__pycache__', '.pytest_cache', '.DS_Store'}
PATTERNS = {
    'personal filesystem path': r'/(?:Users|home)/[a-zA-Z][\w.-]+/',
    'private deployment address': r'\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b',
    'seeded password hash': r'pbkdf2_sha256\$\d+\$[^\s]+',
    'private key': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'GitHub token': r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b',
    'phone-like number': r'(?<!\d)1[3-9]\d{9}(?!\d)',
}


def source_files():
    files = [ROOT / name for name in sorted(TOP_FILES)]
    for directory in sorted(DIRECTORIES):
        for path in sorted((ROOT / directory).rglob('*')):
            if any(part in IGNORE for part in path.relative_to(ROOT).parts):
                continue
            if path.is_symlink():
                raise ValueError(f'Symlink not allowed: {path.relative_to(ROOT)}')
            if path.is_file():
                if path.suffix not in SUFFIXES or path.name.startswith('remote_'):
                    raise ValueError(f'Unexpected file: {path.relative_to(ROOT)}')
                files.append(path)
    return files


def check(tracked=False):
    files = source_files()
    issues = []
    for path in files:
        if path.is_symlink() or not path.is_file():
            issues.append(f'Invalid source file: {path.relative_to(ROOT)}')
            continue
        content = path.read_text(encoding='utf-8')
        for name, pattern in PATTERNS.items():
            if re.search(pattern, content):
                issues.append(f'{path.relative_to(ROOT)}: {name}')
    if tracked:
        top = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT, check=True, capture_output=True, text=True)
        if Path(top.stdout.strip()).resolve() != ROOT.resolve():
            raise ValueError('Initialize an independent Git repository in the community source directory first')
        result = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, check=True, capture_output=True, text=True)
        allowed = {str(p.relative_to(ROOT)) for p in files}
        for name in filter(None, result.stdout.split('\0')):
            if name not in allowed:
                issues.append(f'Unexpected tracked file: {name}')
                continue
            staged = subprocess.run(['git', 'show', ':' + name], cwd=ROOT, check=True, capture_output=True, text=True)
            for label, pattern in PATTERNS.items():
                if re.search(pattern, staged.stdout):
                    issues.append(f'Staged {name}: {label}')
    if issues:
        raise ValueError('\n'.join(issues))
    print(f'Release source scan passed: {len(files)} approved text files')
    return files


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tracked', action='store_true')
    args = parser.parse_args()
    try:
        check(args.tracked)
    except ValueError as exc:
        parser.exit(1, str(exc) + '\n')
