"""P08 archive preflight and extracted-tree comparison; never build or analyze."""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import sys
import tarfile

from Check_Official_Identity import identity
from Inspect_Archive import inspect, blob

COMMIT = '2b978915d82377df13fcbb1fb56660195ded868a'
TREE = '58d40326652c2f414e8a6a4398f0a7c9fd54340d'
SHA256 = 'fba1c8e793f01b493f3f47a926862edbfab487ae4240e02ec67131f1e2bf067f'
LIBRARY_C = ['png.c', 'pngerror.c', 'pngget.c', 'pngmem.c', 'pngpread.c', 'pngread.c', 'pngrio.c', 'pngrtran.c', 'pngrutil.c', 'pngset.c', 'pngtrans.c', 'pngwio.c', 'pngwrite.c', 'pngwtran.c', 'pngwutil.c']
SOURCE_HEADERS = ['png.h', 'pngconf.h', 'pngpriv.h', 'pngdebug.h', 'pnginfo.h', 'pngstruct.h']


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def references(archived, official, download):
    if (archived.get('status') != 'passed' or archived.get('commit') != COMMIT
            or archived.get('rootTreeSHA') != TREE or archived.get('archiveSHA256') != SHA256
            or archived.get('archiveBytes') != 1583920):
        raise ValueError('accepted archive identity differs from the fixed P08 record')
    root = identity(load(download / 'tag-ref-try1/body'),
                    load(download / 'tag-object-try1/body'),
                    load(download / 'git-commit-try1/body'))
    raw_tree = load(download / 'recursive-tree-try1/body')
    if (root != TREE or raw_tree.get('sha') != TREE or raw_tree.get('truncated') is not False
            or official.get('status') != 'passed_official_identity_chain'
            or official.get('commit') != COMMIT or official.get('rootTreeSHA') != TREE
            or official.get('treeTruncated') is not False or official.get('tree') != raw_tree.get('tree')):
        raise ValueError('official identity responses/tree differ from the accepted P08 identity')
    expected = {x['path']: x for x in official['tree'] if x['type'] == 'blob'}
    dirs = {x['path'] for x in official['tree'] if x['type'] == 'tree'}
    if (len(expected) != 599 or len(dirs) != 59 or len(official['tree']) != 658
            or set(expected) != set(archived['files']) | set(archived['links'])
            or len(archived['files']) != 599 or len(archived['links']) != 0):
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
    if archived['links'] or any(x['mode'] not in ['100644', '100755', '040000'] for x in official['tree']):
        raise ValueError('P08 fixed archive does not accept links, submodules or special modes')
    with tarfile.open(archive, 'r:gz') as tf:
        if any(not (m.isdir() or m.isfile()) for m in tf.getmembers()):
            raise ValueError('link or special archive entry is not accepted for P08')
    return {'status': 'passed', 'stage': 'archive preflight only;source not extracted',
            'project': 'P08 libpng', 'commit': COMMIT, 'archiveSHA256': SHA256,
            'regularFiles': 599, 'symlinks': 0, 'directoriesExcludingRoot': 59,
            'sourceWillBe': str(source), 'buildAndAnalysis': 'not performed'}


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
                raise ValueError('links are not part of this fixed P08 source: ' + rel)
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
    header = (source / 'png.h').read_text(encoding='utf-8')
    for macro, value in [('PNG_LIBPNG_VER_MAJOR', 1), ('PNG_LIBPNG_VER_MINOR', 6), ('PNG_LIBPNG_VER_RELEASE', 50), ('PNG_LIBPNG_VER', 10650)]:
        if not re.search(r'^#define\s+' + macro + r'\s+' + str(value) + r'\b', header, re.M):
            raise ValueError('source version macro differs: ' + macro)
    for relative in LIBRARY_C + SOURCE_HEADERS + ['scripts/pnglibconf.h.prebuilt', 'CMakeLists.txt', 'LICENSE']:
        if relative not in files or files[relative]['bytes'] == 0:
            raise ValueError('required library file missing or empty: ' + relative)
    if not re.search(r'^#define\s+PNG_LIBPNG_VER_STRING\s+"1\.6\.50"', header, re.M):
        raise ValueError('source version string differs')
    return {'status': 'passed', 'project': 'P08 libpng', 'version': '1.6.50', 'commit': COMMIT,
            'rootTreeSHA': TREE, 'archiveSHA256': SHA256, 'sourceRoot': str(source),
            'regularFiles': len(files), 'symlinks': len(links), 'directoriesExcludingRoot': len(directories),
            'allContentsMatchAcceptedArchiveAndOfficialGitBlobs': True,
            'files': files, 'links': links, 'directories': sorted(directories),
            'plannedLibraryC': LIBRARY_C, 'sourceHeaders': SOURCE_HEADERS,
            'configurationInput': 'scripts/pnglibconf.h.prebuilt',
            'includedImplementationFiles': [],
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
        print('解压前检查通过：原包SHA、官方身份、完整成员及文件类型符合已验收记录。')
    else:
        print('解压源码身份通过：599个普通文件、0个链接、59个子目录；完整集合、SHA-256及Git blob均一致。')
        print('库范围初检：15个计划C单元、6个源码头及官方预生成配置输入均保留；尚未配置、构建或检测。')
        header = (source / 'png.h').read_text(encoding='utf-8')
        for line in header.splitlines():
            if re.match(r'^#define\s+PNG_LIBPNG_VER(?:_MAJOR|_MINOR|_RELEASE|_STRING)?\s', line):
                print(line)
        print('\nCMake版本与目标准备依据：')
        cmake = (source / 'CMakeLists.txt').read_text(encoding='utf-8')
        for line in cmake.splitlines():
            if re.match(r'\s*(?:set\(PNGLIB_(?:MAJOR|MINOR|REVISION)\b|project\(|option\(PNG_(?:SHARED|STATIC|HARDWARE_OPTIMIZATIONS)\b)', line):
                print(line)
        print('\nLICENSE开头：')
        print('\n'.join((source / 'LICENSE').read_text(encoding='utf-8').splitlines()[:12]))
