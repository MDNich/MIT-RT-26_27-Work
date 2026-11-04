"""Publish a reviewed Iris milestone, excluding oversized files and blobs."""
import argparse
import subprocess
from pathlib import Path
from ops import ROOT, disks

REPO = next(p for p in ROOT.parents if (p / '.git').exists())
SCOPE = 'simulation_work/solidprop/iris'
LIMIT = 100_000_000

def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO).decode().strip()

def check_blobs(revision_args):
    objects = git('rev-list', '--objects', *revision_args).splitlines()
    for line in objects:
        sha, _, name = line.partition(' ')
        size = int(git('cat-file', '-s', sha))
        if size >= LIMIT:
            raise RuntimeError(f'Git object too large: {name or sha}: {size} bytes')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('message')
    parser.add_argument('--push', action='store_true')
    parser.add_argument('--paths', nargs='+', help='Repository-relative Iris paths for this milestone')
    args = parser.parse_args()
    disks()
    paths = set(git('ls-files', '--modified', '--others', '--exclude-standard', '--', SCOPE).splitlines())
    for name in paths:
        p = REPO / name
        if p.is_file() and p.stat().st_size >= LIMIT:
            raise RuntimeError(f'File too large to stage: {name}')
    staged = git('diff', '--cached', '--name-only').splitlines()
    if any(not p.startswith(SCOPE + '/') for p in staged):
        raise RuntimeError('Unrelated changes already staged; preserve them.')
    stage=args.paths or [SCOPE]
    if any(not (p==SCOPE or p.startswith(SCOPE+'/')) or '..' in Path(p).parts for p in stage):
        raise RuntimeError('Milestone paths must stay inside Iris')
    git('add', '--', *stage)
    for name in git('diff', '--cached', '--name-only', '--diff-filter=ACMR').splitlines():
        if int(git('cat-file', '-s', ':' + name)) >= LIMIT:
            raise RuntimeError(f'Staged blob too large: {name}')
    git('diff', '--cached', '--check')
    git('commit', '-m', args.message)
    if args.push:
        disks()
        git('fetch', 'origin')
        check_blobs(['origin/main..HEAD'])
        print(git('push', 'origin', 'HEAD:main'))
    print(git('rev-parse', 'HEAD'))

if __name__ == '__main__':
    main()
