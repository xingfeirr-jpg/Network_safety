"""Read a P10 codeload archive against the official tree; never extract it."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import re
import sys
import tarfile

from Check_Official_Identity import COMMIT, REQUIRED, ROOT_TREE

PREFIX = 'utf8proc-' + COMMIT


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def inspect(archive, reference):
    if (reference.get('status') != 'passed_official_identity_chain' or
            reference.get('commit') != COMMIT or reference.get('rootTreeSHA') != ROOT_TREE or
            reference.get('treeTruncated') is not False):
        raise ValueError('validated fixed official identity/tree required')
    tree = reference['tree']
    expected = {entry['path']: entry for entry in tree if entry['type'] == 'blob'}
    directories = {entry['path'] for entry in tree if entry['type'] == 'tree'}
    files, links, content = {}, {}, {}
    dirs, seen = set(), set()
    mismatches = []
    with tarfile.open(archive, 'r:gz') as handle:
        for member in handle.getmembers():
            name = member.name.rstrip('/')
            parts = PurePosixPath(name).parts
            if (name in seen or not parts or parts[0] != PREFIX or name.startswith('/') or
                    any(part in ('', '.', '..') for part in name.split('/'))):
                raise ValueError('invalid/duplicate archive member: ' + name)
            seen.add(name)
            relative = '/'.join(parts[1:])
            if member.isdir():
                if relative:
                    dirs.add(relative)
                continue
            if relative not in expected:
                raise ValueError('unexpected archive member: ' + relative)
            entry = expected[relative]
            if member.issym() and entry['mode'] == '120000':
                data = member.linkname.encode('utf-8', errors='surrogateescape')
                links[relative] = {'target': member.linkname, 'bytes': len(data),
                                   'gitBlobSHA1': blob(data), 'sha256': hashlib.sha256(data).hexdigest()}
            elif member.isfile() and entry['mode'] in ('100644', '100755'):
                stream = handle.extractfile(member)
                if stream is None:
                    raise ValueError('unreadable archive member: ' + relative)
                data = stream.read()
                files[relative] = {'bytes': len(data), 'gitBlobSHA1': blob(data),
                                   'sha256': hashlib.sha256(data).hexdigest(),
                                   'gitMode': entry['mode']}
                if bool(member.mode & 0o111) != (entry['mode'] == '100755'):
                    mismatches.append({'path': relative, 'reason': 'Git executable bit mismatch'})
                if relative in REQUIRED:
                    content[relative] = data.decode('utf-8', errors='replace')
            else:
                raise ValueError('unsupported member type/mode: ' + relative)
            if len(data) != entry.get('size') or blob(data) != entry['sha']:
                mismatches.append({'path': relative, 'reason': 'size or Git blob mismatch'})
    missing = sorted(set(expected) - set(files) - set(links))
    missing_dirs = sorted(directories - dirs)
    extra_dirs = sorted(dirs - directories)
    if not REQUIRED <= set(files):
        raise ValueError('required library/table/license files absent')
    header = content['utf8proc.h']
    for macro, value in [('UTF8PROC_VERSION_MAJOR', 2), ('UTF8PROC_VERSION_MINOR', 10), ('UTF8PROC_VERSION_PATCH', 0)]:
        if not re.search(r'^#define\s+' + macro + r'\s+' + str(value) + r'\b', header, re.M):
            raise ValueError('header version mismatch: ' + macro)
    if not re.search(r'project\s*\(\s*utf8proc\s+VERSION\s+2\.10\.0\s+LANGUAGES\s+C\s*\)', content['CMakeLists.txt']):
        raise ValueError('CMake fixed API version mismatch')
    if not re.search(r'^\s*#\s*include\s*"utf8proc_data\.c"', content['utf8proc.c'], re.M):
        raise ValueError('included Unicode data table relationship missing')
    if 'Permission is hereby granted' not in content['LICENSE.md'] or 'Unicode' not in content['LICENSE.md']:
        raise ValueError('core and Unicode data license text missing')
    complete = not (missing or missing_dirs or extra_dirs or mismatches)
    archive_bytes = Path(archive).read_bytes()
    return {'status': 'passed' if complete else 'pending_archive_export_scope_review',
            'project': 'P10 utf8proc', 'version': '2.10.0', 'commit': COMMIT,
            'rootTreeSHA': ROOT_TREE, 'archiveRoot': PREFIX,
            'archiveBytes': len(archive_bytes), 'archiveSHA256': hashlib.sha256(archive_bytes).hexdigest(),
            'regularFiles': len(files), 'symlinks': len(links), 'directoriesExcludingRoot': len(dirs),
            'files': files, 'links': links, 'missingGitBlobMembers': missing,
            'missingDirectories': missing_dirs, 'extraDirectories': extra_dirs,
            'contentMismatches': mismatches, 'allArchiveMembersMatchFullOfficialGitTree': complete,
            'logicalLibraryInputs': ['utf8proc.c', 'utf8proc.h', 'utf8proc_data.c'],
            'plannedIndependentTranslationUnits': ['utf8proc.c'],
            'meaning': 'local archive SHA-256 is not an upstream published checksum; included table is not a second translation unit',
            'extractionBuildAndAnalysis': 'not performed'}


def main():
    archive, output, reference_path = map(Path, sys.argv[1:])
    try:
        result = inspect(archive, json.loads(reference_path.read_text(encoding='utf-8-sig')))
    except Exception as error:
        result = {'status': 'failed', 'error': str(error), 'extractionBuildAndAnalysis': 'not performed'}
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    if result['status'] != 'passed':
        print('原包初检：' + result['status'] + '；原件及检查结果已保留。', file=sys.stderr)
        if 'error' in result:
            print(result['error'], file=sys.stderr)
        raise SystemExit(2 if result['status'].startswith('pending') else 1)
    print('utf8proc2.10.0原包身份初检通过：完整集合、大小和Git blob与固定官方树一致。')
    print(f"普通文件{result['regularFiles']}、链接{result['symlinks']}、子目录{result['directoriesExcludingRoot']}；版本与数据表包含关系通过。")
    print('本步未解压、配置、构建或运行三个检测工具。')


if __name__ == '__main__':
    main()
