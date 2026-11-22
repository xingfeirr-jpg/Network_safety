"""P07 archive preflight and extracted-tree comparison; never build or analyze."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import posixpath
import re
import stat
import sys
import tarfile

from Check_Official_Identity import identity
from Inspect_Archive import inspect, blob

COMMIT = 'f9a3eeb3e09fbea04b1c451ffc422ab2f1e45744'
TREE = 'f719d0fdb368ce101cdee6a4cd34158c7b2aa3a3'
SHA256 = '86f0e8afaf4cd72d806e32afb68e1e84bb2c6e5b0b40de2a34c0970bf8d08c40'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def references(archived, official, download):
    if (archived.get('status') != 'passed' or archived.get('commit') != COMMIT
            or archived.get('rootTreeSHA') != TREE or archived.get('archiveSHA256') != SHA256
            or archived.get('archiveBytes') != 8433965):
        raise ValueError('accepted archive identity differs from the fixed P07 record')
    root = identity(load(download / 'tag-ref-try1/body'),
                    load(download / 'tag-object-try1/body'),
                    load(download / 'git-commit-try1/body'))
    raw_tree = load(download / 'recursive-tree-try1/body')
    if (root != TREE or raw_tree.get('sha') != TREE or raw_tree.get('truncated') is not False
            or official.get('status') != 'passed_official_identity_chain'
            or official.get('commit') != COMMIT or official.get('rootTreeSHA') != TREE
            or official.get('treeTruncated') is not False or official.get('tree') != raw_tree.get('tree')):
        raise ValueError('official identity responses/tree differ from the accepted P07 identity')
    expected = {x['path']: x for x in official['tree'] if x['type'] == 'blob'}
    dirs = {x['path'] for x in official['tree'] if x['type'] == 'tree'}
    if (len(expected) != 208 or len(dirs) != 20 or len(official['tree']) != 228
            or set(expected) != set(archived['files']) | set(archived['links'])
            or len(archived['files']) != 207 or len(archived['links']) != 1):
        raise ValueError('incomplete or unexpected fixed file/directory inventory')
    for rel, ref in {**archived['files'], **archived['links']}.items():
        item = expected[rel]
        if item['sha'] != ref['gitBlobSHA1'] or item['size'] != ref['bytes']:
            raise ValueError('accepted member differs from the official blob: ' + rel)
        if (rel in archived['links']) != (item['mode'] == '120000'):
            raise ValueError('accepted member type differs from the official tree: ' + rel)
    return expected, dirs


def preflight(archive, archived, official, download, source):
    if archive.is_symlink() or not archive.is_file():
        raise ValueError('archive missing or is a link')
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise ValueError('archive bytes no longer match the accepted SHA-256')
    references(archived, official, download)
    actual = inspect(archive, official)
    if actual != archived:
        raise ValueError('recomputed archive inventory differs from the saved accepted inventory')
    if source.exists() or source.is_symlink() or not source.parent.is_dir():
        raise ValueError('source must be absent and its existing parent must be a directory')
    for parent in [source.parent, *source.parent.parents]:
        if parent.is_symlink():
            raise ValueError('source ancestor is a link: ' + str(parent))
    links = archived['links']
    members = set(archived['files']) | set(links) | {x['path'] for x in official['tree'] if x['type'] == 'tree'}
    resolved = {}
    for rel, ref in links.items():
        target = ref['target']
        destination = posixpath.normpath(posixpath.join(posixpath.dirname(rel), target))
        if (not target or target.startswith('/') or destination in ['.', '..']
                or destination.startswith('../') or destination not in archived['files']):
            raise ValueError('link does not resolve to a regular file inside this source: ' + rel)
        resolved[rel] = destination
    for rel in members:
        if any(parent.as_posix() in links for parent in PurePosixPath(rel).parents):
            raise ValueError('archive member is nested beneath a link: ' + rel)
    with tarfile.open(archive, 'r:gz') as tf:
        if any(not (m.isdir() or m.isfile() or m.issym()) for m in tf.getmembers()):
            raise ValueError('hard link or special archive entry is not accepted')
    return {'status': 'passed', 'stage': 'archive preflight only;source not extracted',
            'project': 'P07 Expat', 'commit': COMMIT, 'archiveSHA256': SHA256,
            'regularFiles': 207, 'symlinks': 1, 'directoriesExcludingRoot': 20,
            'linkDestinationsInsideSource': resolved, 'sourceWillBe': str(source),
            'buildAndAnalysis': 'not performed'}


def verify(source, archived, official, download):
    expected, expected_dirs = references(archived, official, download)
    if source.is_symlink() or not source.is_dir():
        raise ValueError('source directory missing or is a link')
    files, links, directories = {}, {}, set()
    for base, dirnames, filenames in os.walk(source, followlinks=False):
        for name in dirnames + filenames:
            path = Path(base) / name
            rel = path.relative_to(source).as_posix()
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                if rel not in archived['links']:
                    raise ValueError('unexpected source link: ' + rel)
                target = os.readlink(path)
                data = target.encode('utf-8', errors='surrogateescape')
                observed = {'target': target, 'bytes': len(data), 'gitBlobSHA1': blob(data),
                            'sha256': hashlib.sha256(data).hexdigest()}
                if observed != archived['links'][rel]:
                    raise ValueError('extracted link target differs: ' + rel)
                links[rel] = observed
            elif stat.S_ISDIR(mode):
                directories.add(rel)
            elif stat.S_ISREG(mode):
                if rel not in archived['files']:
                    raise ValueError('unexpected source file: ' + rel)
                data = path.read_bytes()
                observed = {'bytes': len(data), 'gitBlobSHA1': blob(data),
                            'sha256': hashlib.sha256(data).hexdigest()}
                if observed != archived['files'][rel]:
                    raise ValueError('extracted file content differs: ' + rel)
                if bool(mode & 0o111) != (expected[rel]['mode'] == '100755'):
                    raise ValueError('extracted executable bit differs from Git: ' + rel)
                files[rel] = {**observed, 'permissionsOctal': oct(mode & 0o777)}
            else:
                raise ValueError('special source entry: ' + rel)
    if (set(files) != set(archived['files']) or set(links) != set(archived['links'])
            or directories != expected_dirs):
        raise ValueError('extracted file/link/directory collection differs from the fixed archive')
    header = (source / 'expat/lib/expat.h').read_text(encoding='utf-8')
    for macro, value in [('XML_MAJOR_VERSION', 2), ('XML_MINOR_VERSION', 7), ('XML_MICRO_VERSION', 1)]:
        if not re.search(r'^#define\s+' + macro + r'\s+' + str(value) + r'\b', header, re.M):
            raise ValueError('source version macro differs: ' + macro)
    return {'status': 'passed', 'project': 'P07 Expat', 'version': '2.7.1', 'commit': COMMIT,
            'rootTreeSHA': TREE, 'archiveSHA256': SHA256, 'sourceRoot': str(source),
            'regularFiles': len(files), 'symlinks': len(links), 'directoriesExcludingRoot': len(directories),
            'allContentsMatchAcceptedArchiveAndOfficialGitBlobs': True,
            'files': files, 'links': links, 'directories': sorted(directories),
            'plannedLibraryC': ['expat/lib/xmlparse.c', 'expat/lib/xmlrole.c', 'expat/lib/xmltok.c'],
            'includedImplementationFiles': ['expat/lib/xmltok_impl.c', 'expat/lib/xmltok_ns.c'],
            'actualCompileActions': None, 'buildAndAnalysis': 'not performed'}


if __name__ == '__main__':
    mode, archive_arg, inventory_arg, official_arg, source_arg, output_arg = sys.argv[1:]
    archive, inventory_path, official_path, source, output = map(Path,
        [archive_arg, inventory_arg, official_arg, source_arg, output_arg])
    try:
        archived, official = load(inventory_path), load(official_path)
        if mode == 'preflight':
            result = preflight(archive, archived, official, official_path.parent, source)
        elif mode == 'verify':
            result = verify(source, archived, official, official_path.parent)
        else:
            raise ValueError('unknown verification mode')
    except Exception as exc:
        result = {'status': 'failed', 'stage': mode, 'error': str(exc), 'buildAndAnalysis': 'not performed'}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    if result['status'] != 'passed':
        print('核对失败：' + result['error'], file=sys.stderr)
        raise SystemExit(1)
    if mode == 'preflight':
        print('解压前检查通过：原包SHA、官方身份、完整成员及包内链接目标均符合已验收记录。')
    else:
        print('解压源码身份通过：207个普通文件、1个链接、20个子目录；完整集合、SHA-256及Git blob均一致。')
        print('链接README.md → expat/README.md；目标位于源码目录内。')
        print('库范围初检：3个计划C单元及2个包含型实现均保留；尚未配置、构建或检测。')
        header = (source / 'expat/lib/expat.h').read_text(encoding='utf-8')
        for line in header.splitlines():
            if re.match(r'^#define\s+XML_(?:MAJOR|MINOR|MICRO)_VERSION\b', line):
                print(line)
        print('\nCMake开头：')
        print('\n'.join((source / 'expat/CMakeLists.txt').read_text(encoding='utf-8').splitlines()[:12]))
        print('\nCOPYING开头：')
        print('\n'.join((source / 'expat/COPYING').read_text(encoding='utf-8').splitlines()[:12]))
