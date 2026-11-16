#!/usr/bin/env python3
"""Build a source-only community release using an explicit file allowlist."""
import argparse
import gzip
import hashlib
import io
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
    guide = out / 'DEPLOYMENT.md'
    tag = args.version if args.version.startswith('v') else 'v' + args.version
    guide_text = (ROOT / 'docs/DEPLOYMENT.md').read_text(encoding='utf-8')
    # The separately downloaded guide must not depend on sibling Markdown files.
    guide_text = re.sub(r'\(([^()/]+\.md)(#[^)]*)?\)',
        lambda match: f'(https://github.com/oamorg/dedicated-line-platform/blob/{tag}/docs/'
                      f'{match[1]}{match[2] or ""})', guide_text)
    guide.write_text(guide_text, encoding='utf-8')
    readme = f'''# Community deployment bundle {args.version}

Start with [the deployment guide](docs/DEPLOYMENT.md).
Requirements: Python 3.11-3.14 and MySQL 8.0 or 8.4.

- `{source.name}`: complete MIT community source, tests and documentation.
- `db/{empty.name}`: schema, roles and permissions; no accounts or business rows.
- `docs/`: deployment, usage, data, testing and publishing guides.
- `LICENSE`: Copyright (c) 2026 oamorg, MIT License.

Verify the extracted bundle with `sha256sum -c SHA256SUMS.txt`
(macOS: `shasum -a 256 -c SHA256SUMS.txt`).
Extract the source archive, configure your database, then create your administrator
as described in the guide. There is no default administrator or password.
Do not import the empty schema over a production database without a backup.
'''
    contents = [('LICENSE', (ROOT / 'LICENSE').read_bytes(), 0o644),
                ('README.md', readme.encode('utf-8'), 0o644),
                (source.name, source.read_bytes(), 0o644),
                ('db/' + empty.name, empty.read_bytes(), 0o644)]
    contents.extend((str(p.relative_to(ROOT)), p.read_bytes(), 0o644)
                    for p in files if p.relative_to(ROOT).parts[0] == 'docs')
    internal = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n' for name, data, _ in contents)
    contents.append(('SHA256SUMS.txt', internal.encode(), 0o644))
    release = out / f'dedicated-line-community-release-{args.version}.tar.gz'
    archive(release, contents)
    (out / 'SHA256SUMS.txt').write_text(''.join(f'{digest(path)}  {path.name}\n' for path in [source, empty, guide, release]), encoding='utf-8')
    print(f'Community release built in {out}')


if __name__ == '__main__':
    main()
