#!/usr/bin/env python3
"""Build a source-only community release using an explicit file allowlist."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path
import re
import tarfile

from check_release import ROOT, check


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive(path, entries):
    # Clear gzip metadata as well as tar metadata for identical repeat builds.
    with path.open('wb') as output:
        with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w') as bundle:
                for name, content, mode in entries:
                    info = tarfile.TarInfo(name)
                    info.size = len(content)
                    info.mode = mode
                    info.mtime = 0
                    bundle.addfile(info, io.BytesIO(content))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', args.version):
        parser.error('Invalid version')
    files = check()
    out = ROOT / 'dist'
    out.mkdir(exist_ok=True)
    source = out / f'dedicated-line-community-source-{args.version}.tar.gz'
    archive(source, [(f'dedicated-line-platform/{p.relative_to(ROOT)}', p.read_bytes(), 0o755 if p.name == 'deploy.sh' else 0o644) for p in files])
    empty = out / 'dedicated_line_empty.sql'
    empty.write_text('-- Empty community schema: no accounts or business rows.\nSET NAMES utf8mb4;\n' + (ROOT / 'sql/01_schema.sql').read_text(encoding='utf-8'), encoding='utf-8')
    contents = [('LICENSE', (ROOT / 'LICENSE').read_bytes(), 0o644),
                (source.name, source.read_bytes(), 0o644),
                ('db/' + empty.name, empty.read_bytes(), 0o644)]
    internal = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n' for name, data, _ in contents)
    contents.append(('SHA256SUMS.txt', internal.encode(), 0o644))
    release = out / f'dedicated-line-community-release-{args.version}.tar.gz'
    archive(release, contents)
    (out / 'SHA256SUMS.txt').write_text(''.join(f'{digest(path)}  {path.name}\n' for path in [source, empty, release]), encoding='utf-8')
    print(f'Community release built in {out}')


if __name__ == '__main__':
    main()
