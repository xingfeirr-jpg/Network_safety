"""Read the extracted P06 tree; writes its inventory only to the new record path."""
from pathlib import Path
import hashlib
import json
import os
import re
import sys


def verify(source, archived, official):
    if source.is_symlink() or not source.is_dir():
        raise ValueError('source directory missing or is a symlink')
    if archived.get('status') != 'passed' or archived.get('commit') != '8b4a38dc994a110abaec8a400615567bd996105f':
        raise ValueError('wrong accepted archive identity')
    if archived.get('archiveSHA256') != '94e9c90f8f12d8329f2c0756782d21e5c278729023cd2c5fe47e323a35947ed6':
        raise ValueError('wrong accepted archive SHA-256')
    if official.get('sha') != archived['commit'] or official.get('truncated') is not False:
        raise ValueError('wrong or incomplete official reference')
    expected = archived['files']
    official_files = {x['path']: x for x in official['tree'] if x['type'] == 'blob'}
    expected_dirs = {x['path'] for x in official['tree'] if x['type'] == 'tree'}
    if (len(official_files) != 903 or len(expected_dirs) != 25
            or len(official_files) + len(expected_dirs) != len(official['tree'])
            or any(x['mode'] not in ['100644', '100755'] for x in official_files.values())
            or set(expected) != set(official_files)):
        raise ValueError('fixed official tree or accepted inventory is incomplete')
    for relative, ref in expected.items():
        item = official_files[relative]
        if ref['bytes'] != item['size'] or ref['gitBlobSHA1'] != item['sha']:
            raise ValueError('accepted inventory differs from official blob: ' + relative)
    found = {}
    directories = set()
    for base, dirs, files in os.walk(source, followlinks=False):
        for name in dirs:
            path = Path(base) / name
            if path.is_symlink():
                raise ValueError('unexpected source symlink: ' + str(path))
            directories.add(path.relative_to(source).as_posix())
        for name in files:
            path = Path(base) / name
            rel = path.relative_to(source).as_posix()
            if path.is_symlink() or not path.is_file() or rel not in expected:
                raise ValueError('unexpected source entry: ' + rel)
            data = path.read_bytes()
            size = len(data)
            digest = hashlib.sha256(data).hexdigest()
            blob = hashlib.sha1(b'blob ' + str(size).encode('ascii') + b'\0' + data).hexdigest()
            ref = expected[rel]
            if size != ref['bytes'] or digest != ref['sha256'] or blob != ref['gitBlobSHA1']:
                raise ValueError('extracted file content mismatch: ' + rel)
            found[rel] = {'bytes': size, 'sha256': digest, 'gitBlobSHA1': blob,
                          'permissionsOctal': oct(path.stat().st_mode & 0o777)}
    if set(found) != set(expected) or directories != expected_dirs:
        raise ValueError('source file/directory set differs from fixed archive')
    header = (source / 'src/yyjson.h').read_text(encoding='utf-8')
    cmake = (source / 'CMakeLists.txt').read_text(encoding='utf-8')
    if not re.search(r'^#define\s+YYJSON_VERSION_STRING\s+"0\.12\.0"\s*$', header, re.M):
        raise ValueError('header version mismatch')
    if not re.search(r'project\s*\(\s*yyjson\s+VERSION\s+0\.12\.0\b', cmake):
        raise ValueError('CMake version mismatch')
    return {'status': 'passed', 'project': 'P06 yyjson', 'version': '0.12.0',
            'commit': archived['commit'], 'sourceRoot': str(source),
            'archiveSHA256': archived['archiveSHA256'], 'regularFiles': len(found),
            'directoriesExcludingRoot': len(directories), 'symlinks': 0,
            'allContentsMatchAcceptedArchiveAndOfficialGitBlobs': True,
            'permissionsMeaning': 'observed extraction modes recorded;content identity is checked separately',
            'files': found, 'directories': sorted(directories),
            'plannedLibraryC': ['src/yyjson.c'], 'plannedLibraryHeaders': ['src/yyjson.h'],
            'buildAndAnalysis': 'not performed'}


if __name__ == '__main__':
    source, archived, official, output = map(Path, sys.argv[1:])
    try:
        result = verify(source, json.loads(archived.read_text(encoding='utf-8-sig')),
                        json.loads(official.read_text(encoding='utf-8-sig')))
    except Exception as exc:
        result = {'status': 'failed', 'error': str(exc), 'sourceRoot': str(source), 'buildAndAnalysis': 'not performed'}
        with output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        print('源码核对失败：' + str(exc), file=sys.stderr)
        raise SystemExit(1)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(f"解压源码身份通过：{result['regularFiles']}个普通文件、{result['directoriesExcludingRoot']}个子目录；完整集合、SHA-256和Git blob均一致。")
    print('库范围初检：src/yyjson.c与src/yyjson.h存在且非空；尚未构建或检测。')
    header = (source / 'src/yyjson.h').read_text(encoding='utf-8')
    for line in header.splitlines():
        if re.match(r'^#define\s+YYJSON_VERSION_(?:MAJOR|MINOR|PATCH|HEX|STRING)\b', line):
            print(line)
    print('\nCMake开头：')
    print('\n'.join((source / 'CMakeLists.txt').read_text(encoding='utf-8').splitlines()[:7]))
    print('\nLICENSE开头：')
    print('\n'.join((source / 'LICENSE').read_text(encoding='utf-8').splitlines()[:10]))
