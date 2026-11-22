"""P10 accepted-archive preflight and extracted-tree verification only."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

from Check_Official_Identity import COMMIT, ROOT_TREE, reference
from Inspect_Archive import blob, inspect

ARCHIVE_SHA256 = '43f09c9d0a2d3fcbb4eba77729dd603b0ac470ccace59a2961f82a8b6323445f'
ARCHIVE_BYTES = 198916


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def checked_archive(archive, download, accepted):
    if (accepted.get('status') != 'passed' or accepted.get('commit') != COMMIT or
            accepted.get('rootTreeSHA') != ROOT_TREE or accepted.get('archiveSHA256') != ARCHIVE_SHA256 or
            accepted.get('archiveBytes') != ARCHIVE_BYTES):
        raise ValueError('fixed accepted archive identity mismatch')
    if archive.is_symlink() or not archive.is_file():
        raise ValueError('archive missing or is a link')
    raw = archive.read_bytes()
    if len(raw) != ARCHIVE_BYTES or hashlib.sha256(raw).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('archive bytes no longer match accepted download')
    for filename, key in [('archive-check.json', 'archiveCheckSHA256'),
                          ('official-reference.json', 'officialReferenceSHA256')]:
        path = download / filename
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != accepted[key]:
            raise ValueError('saved download identity record changed: ' + filename)
    saved = load(download / 'archive-check.json')
    official = load(download / 'official-reference.json')
    raw_reference = reference(load(download / 'tag-ref-try1/body'),
                              load(download / 'git-commit-try1/body'),
                              load(download / 'recursive-tree-try1/body'))
    if (official.get('tree') != raw_reference['tree'] or
            official.get('commit') != COMMIT or official.get('rootTreeSHA') != ROOT_TREE):
        raise ValueError('official identity chain differs from saved accepted tree')
    actual = inspect(archive, official)
    if actual['status'] != 'passed' or actual != saved:
        raise ValueError('archive reinspection differs from accepted full inventory')
    if actual['regularFiles'] != 45 or actual['directoriesExcludingRoot'] != 5 or actual['symlinks']:
        raise ValueError('fixed complete inventory differs')
    return actual, official


def preflight(archive, download, accepted, source):
    archived, official = checked_archive(archive, download, accepted)
    if source.exists() or source.is_symlink() or not source.parent.is_dir():
        raise ValueError('source must not exist and its parent must already be a directory')
    for parent in [source.parent, *source.parent.parents]:
        if parent.is_symlink():
            raise ValueError('source ancestor is a symbolic link')
    return {'status': 'passed', 'project': 'P10 utf8proc', 'phase': 'preflight',
            'archiveSHA256': ARCHIVE_SHA256, 'archiveBytes': ARCHIVE_BYTES,
            'sourceDirectory': str(source), 'regularFiles': archived['regularFiles'],
            'directoriesExcludingRoot': 5, 'sourceWasAbsent': True,
            'extractionBuildAndAnalysis': 'not performed'}


def verify(archive, download, accepted, source):
    archived, official = checked_archive(archive, download, accepted)
    if source.is_symlink() or not source.is_dir():
        raise ValueError('source directory missing or is a link')
    expected = archived['files']
    expected_dirs = {entry['path'] for entry in official['tree'] if entry['type'] == 'tree'}
    actual_files, actual_dirs, seen = {}, set(), set()
    for current, dirs, files in os.walk(source, followlinks=False):
        for name in dirs + files:
            path = Path(current) / name
            relative = path.relative_to(source).as_posix()
            mode = path.lstat().st_mode
            if path.is_symlink():
                raise ValueError('unexpected extracted link: ' + relative)
            seen.add(relative)
            if stat.S_ISDIR(mode):
                actual_dirs.add(relative)
                continue
            if not stat.S_ISREG(mode) or relative not in expected:
                raise ValueError('unexpected extracted file/type: ' + relative)
            data = path.read_bytes()
            item = expected[relative]
            if (len(data) != item['bytes'] or blob(data) != item['gitBlobSHA1'] or
                    hashlib.sha256(data).hexdigest() != item['sha256'] or
                    bool(mode & 0o111) != (item['gitMode'] == '100755')):
                raise ValueError('extracted bytes/size/executable bit mismatch: ' + relative)
            actual_files[relative] = {'bytes': len(data), 'sha256': item['sha256'],
                                      'gitBlobSHA1': item['gitBlobSHA1'], 'gitMode': item['gitMode']}
    if set(actual_files) != set(expected) or actual_dirs != expected_dirs:
        raise ValueError('extracted full file/directory set differs from accepted archive')
    return {'status': 'passed', 'project': 'P10 utf8proc', 'version': '2.10.0',
            'phase': 'extracted_source', 'commit': COMMIT, 'rootTreeSHA': ROOT_TREE,
            'archiveSHA256': ARCHIVE_SHA256, 'sourceDirectory': str(source),
            'regularFiles': len(actual_files), 'directoriesExcludingRoot': len(actual_dirs),
            'symlinks': 0, 'allFileSetsSizesSHA256GitBlobsAndExecutableBitsMatch': True,
            'files': actual_files, 'directories': sorted(actual_dirs),
            'plannedIndependentTranslationUnits': ['utf8proc.c'],
            'includedTable': 'utf8proc_data.c', 'projectHeader': 'utf8proc.h',
            'configurationBuildAndAnalysis': 'not performed'}


def main():
    phase, archive, download, accepted_path, source, output = sys.argv[1:]
    try:
        operation = {'preflight': preflight, 'verify': verify}[phase]
        result = operation(Path(archive), Path(download), load(accepted_path), Path(source))
    except Exception as error:
        result = {'status': 'failed', 'phase': phase, 'error': str(error),
                  'configurationBuildAndAnalysis': 'not performed'}
    with Path(output).open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    if result['status'] != 'passed':
        print(result['error'], file=sys.stderr)
        raise SystemExit(1)
    if phase == 'preflight':
        print('解压前复核通过：原包SHA、官方固定身份及完整成员与已验收记录一致。')
    else:
        print('解压源码核对通过：45普通文件／5子目录，无链接；完整集合、大小、SHA-256、Git blob和执行位一致。')
        print('版本2.10.0、头、包含型Unicode数据表及许可证保持；尚未配置、构建或检测。')


if __name__ == '__main__':
    main()
