"""P09 release-asset checks. Reads archive in memory; never extracts or executes it."""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, posixpath, re, tarfile, sys
PIN_COMMIT = '7723f50f3f66b9da74376e6d8badb6162464212c'
PIN_SHA = 'aadc97ea91f6ef078b0ae3a62bba69e008d9a7db19b34e4ac973b19b71b4217c'
PIN_URL = 'https://github.com/libjpeg-turbo/libjpeg-turbo/releases/download/3.1.1/libjpeg-turbo-3.1.1.tar.gz'

def sha(b):
    return hashlib.sha256(b).hexdigest()

def load_profile(path):
    p = Path(path)
    v = json.loads(p.read_text(encoding='utf-8'))
    if not (v['commit'] == PIN_COMMIT and v['tag'] == '3.1.1'):
        raise ValueError('validation failed')
    if not (v['assetUrl'] == PIN_URL and v['expectedArchiveSHA256'] == PIN_SHA and (v['expectedArchiveBytes'] == 2506010)):
        raise ValueError('validation failed')
    if not (v['assetId'] == 262668412 and v['releaseId'] == 224372990):
        raise ValueError('validation failed')
    meta = json.loads((p.parent / v['officialMetadata']).read_text(encoding='utf-8'))
    if not meta['tagRefObject'] == {'sha': PIN_COMMIT, 'type': 'commit', 'url': 'https://api.github.com/repos/libjpeg-turbo/libjpeg-turbo/git/commits/' + PIN_COMMIT}:
        raise ValueError('validation failed')
    if not (meta['asset']['digest'] == 'sha256:' + PIN_SHA and meta['asset']['size'] == 2506010):
        raise ValueError('validation failed')
    if not (meta['asset']['browser_download_url'] == PIN_URL and meta['expectedCommit'] == PIN_COMMIT):
        raise ValueError('validation failed')
    for ref in v['referenceFiles']:
        data = (p.parent / 'Official_Identity_Check_20261029' / ref['file']).read_bytes()
        if not (len(data) == ref['bytes'] and sha(data) == ref['sha256']):
            raise ValueError('validation failed')
    return v

def inspect_members(archive, profile):
    root = profile['archiveRoot']
    members = []
    seen = set()
    refmap = {x['file']: x for x in profile['referenceFiles']}
    found = {}
    with tarfile.open(archive, 'r:gz') as tar:
        for m in tar.getmembers():
            name = m.name.rstrip('/')
            parts = PurePosixPath(name).parts
            if not (name and (not name.startswith('/')) and ('\\' not in name) and all((x not in ('.', '..') for x in parts))):
                raise ValueError(('unsafe member', m.name))
            if not (parts[0] == root and name not in seen):
                raise ValueError(('root or duplicate', name))
            seen.add(name)
            rel = '/'.join(parts[1:])
            row = dict(path=rel, type='directory' if m.isdir() else 'file' if m.isfile() else 'symlink' if m.issym() else 'hardlink' if m.islnk() else 'unsupported', mode=m.mode, size=m.size)
            if m.isfile():
                data = tar.extractfile(m).read()
                if not len(data) == m.size:
                    raise ValueError('validation failed')
                row.update(sha256=sha(data), gitBlobSHA1=hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\x00' + data).hexdigest())
                if rel in refmap:
                    if not sha(data) == refmap[rel]['sha256']:
                        raise ValueError(('fixed commit reference mismatch', rel))
                    found[rel] = row['sha256']
            elif m.issym() or m.islnk():
                target = m.linkname
                if not (target and (not target.startswith('/')) and ('\\' not in target)):
                    raise ValueError('validation failed')
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target) if m.issym() else target)
                if not (resolved == root or resolved.startswith(root + '/')):
                    raise ValueError(('link outside archive root', name, target))
                row.update(linkTarget=target, resolvedTarget=resolved)
            elif not m.isdir():
                raise ValueError(('unsupported member type', name))
            members.append(row)
        if not set(found) == set(refmap):
            raise ValueError(('missing fixed reference', set(refmap) - set(found)))
        cm = tar.extractfile(root + '/CMakeLists.txt').read().decode('utf-8')
        if not re.search('^set\\(VERSION\\s+3\\.1\\.1\\)', cm, re.M):
            raise ValueError('validation failed')
    return dict(members=members, regularFiles=sum((x['type'] == 'file' for x in members)), directories=sum((x['type'] == 'directory' for x in members)), symlinks=sum((x['type'] == 'symlink' for x in members)), hardlinks=sum((x['type'] == 'hardlink' for x in members)), fixedCommitReferenceFiles=found, version='3.1.1')

def main():
    a = argparse.ArgumentParser()
    a.add_argument('mode', choices=['profile', 'archive'])
    a.add_argument('profile')
    a.add_argument('archive', nargs='?')
    a.add_argument('output', nargs='?')
    args = a.parse_args()
    v = load_profile(args.profile)
    if args.mode == 'profile':
        print('P09固定发布资产、官方digest及4个固定commit参考文件核对通过。')
        return
    if not (args.archive and args.output):
        raise ValueError('validation failed')
    data = Path(args.archive).read_bytes()
    if not len(data) == v['expectedArchiveBytes']:
        raise ValueError(('size mismatch', len(data)))
    if not sha(data) == v['expectedArchiveSHA256']:
        raise ValueError('official asset digest mismatch')
    result = inspect_members(args.archive, v)
    result.update(archiveBytes=len(data), archiveSHA256=sha(data), matchedOfficialReleaseAssetDigest=True, officialAssetId=v['assetId'], commit=v['commit'], archiveExtracted=False, built=False, scanned=False, wholeArchiveEqualsGitTree='not asserted:official release package may include generated files', digitalSignatureVerified=False)
    with Path(args.output).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(f'正式发布源码包初检通过：{len(data):,}字节；与官方资产SHA-256一致。')
    print(f"版本3.1.1与4个固定commit构建/许可文本一致；普通文件{result['regularFiles']}，目录{result['directories']}，符号链接{result['symlinks']}，硬链接{result['hardlinks']}。")
    print('本步只读取归档内容；尚未解压、配置、构建或运行检测工具。')
if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('P09核对失败：' + str(e), file=sys.stderr)
        sys.exit(1)
