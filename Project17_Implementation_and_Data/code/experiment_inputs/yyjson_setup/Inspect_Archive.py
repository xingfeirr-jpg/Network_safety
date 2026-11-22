"""Inspect, without extracting, the P06 archive against the fixed official tree."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import re
import sys
import tarfile

COMMIT = '8b4a38dc994a110abaec8a400615567bd996105f'
ROOT = 'yyjson-' + COMMIT
TREE_SHA = 'a51e8386f5e259392d2a77ee2300ea17210f5fa1'


def inspect(archive, reference):
    if reference['sha'] != COMMIT:
        raise ValueError('official reference response does not match the fixed commit lookup')
    if reference['truncated']:
        raise ValueError('official reference tree is truncated')
    expected = {x['path']: x for x in reference['tree'] if x['type'] == 'blob'}
    expected_dirs = {x['path'] for x in reference['tree'] if x['type'] == 'tree'}
    if any(x['type'] not in ['blob', 'tree'] or (x['type'] == 'blob' and x['mode'] not in ['100644', '100755']) for x in reference['tree']):
        raise ValueError('unsupported entry in fixed official tree')
    expected_required = {'CMakeLists.txt', 'LICENSE', 'src/yyjson.c', 'src/yyjson.h'}
    if not expected_required <= set(expected):
        raise ValueError('required library members absent from official tree')
    with tarfile.open(archive, 'r:gz') as tf:
        files = {}
        dirs = set()
        seen = set()
        required_data = {}
        for member in tf.getmembers():
            name = member.name.rstrip('/')
            if name in seen:
                raise ValueError('duplicate archive member: ' + name)
            seen.add(name)
            parts = PurePosixPath(name).parts
            if not parts or parts[0] != ROOT or any(x in ['..', '.'] for x in name.split('/')) or name.startswith('/'):
                raise ValueError('unexpected archive path: ' + name)
            relative = '/'.join(parts[1:])
            if member.isdir():
                if relative:
                    dirs.add(relative)
                continue
            if not member.isfile() or relative not in expected:
                raise ValueError('unexpected/non-regular member: ' + name)
            item = expected[relative]
            if member.size != item['size']:
                raise ValueError('member size mismatch: ' + relative)
            source = tf.extractfile(member)
            if source is None:
                raise ValueError('unreadable member: ' + relative)
            data = source.read()
            blob_sha = hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()
            if blob_sha != item['sha']:
                raise ValueError('Git blob mismatch: ' + relative)
            files[relative] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'gitBlobSHA1': blob_sha}
            if relative in expected_required:
                required_data[relative] = data.decode('utf-8')
        if set(files) != set(expected) or dirs != expected_dirs:
            raise ValueError('incomplete or unexpected archive file/directory set')
    if not re.search(r'^#define\s+YYJSON_VERSION_STRING\s+"0\.12\.0"\s*$', required_data['src/yyjson.h'], re.M):
        raise ValueError('header version mismatch')
    if not re.search(r'project\s*\(\s*yyjson\s+VERSION\s+0\.12\.0\b', required_data['CMakeLists.txt']):
        raise ValueError('CMake version mismatch')
    data = Path(archive).read_bytes()
    return {
        'status': 'passed', 'project': 'P06 yyjson', 'version': '0.12.0', 'commit': COMMIT,
        'archiveRoot': ROOT, 'archiveBytes': len(data), 'archiveSHA256': hashlib.sha256(data).hexdigest(),
        'officialReferenceResponseSHA1': reference['sha'],
        'officialCommitRootTreeSHA1': TREE_SHA, 'regularFiles': len(files),
        'directoriesExcludingRoot': len(dirs), 'sourceFileBytes': sum(x['bytes'] for x in files.values()),
        'allFileContentsMatchOfficialGitBlobs': True, 'files': files,
        'meaning': 'local archive SHA-256 and per-file comparison to fixed official Git tree;not a publisher archive checksum',
        'extractionBuildAndAnalysis': 'not performed by this inspector',
    }


if __name__ == '__main__':
    archive, output, tree = map(Path, sys.argv[1:])
    try:
        result = inspect(archive, json.loads(tree.read_text(encoding='utf-8-sig')))
    except Exception as exc:
        result = {'status': 'failed', 'error': str(exc), 'archive': str(archive), 'extractionBuildAndAnalysis': 'not performed'}
        with output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        print('源码包身份核对失败：' + str(exc), file=sys.stderr)
        raise SystemExit(1)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print('源码包身份初检通过：固定commit完整文件集合、Git blob和0.12.0版本一致。')
    print(f"普通文件{result['regularFiles']}，子目录{result['directoriesExcludingRoot']}；未解压、构建或检测。")
