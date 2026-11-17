"""Verify the accepted P01 build before/after a P08 dependency-only install."""
from pathlib import Path
import hashlib
import json
import os
import re
import sys

SETUP = Path(__file__).resolve().parent
DOCS = SETUP.parents[1]
BASE = Path.home() / 'comp5355'
BUILD = BASE / 'build/zlib-v1.3.2'
SOURCE = BASE / 'sources/zlib-v1.3.2'
PREFIX = BASE / 'deps/zlib-v1.3.2'
INSTALL_MAP = {
    'lib/libz.a': BUILD / 'libz.a',
    'include/zlib.h': SOURCE / 'zlib.h',
    'include/zconf.h': BUILD / 'zconf.h',
    'lib/pkgconfig/zlib.pc': BUILD / 'zlib.pc',
}


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('missing/non-regular input: ' + str(path))
    data = path.read_bytes()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def no_link_ancestors(path):
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise ValueError('linked path/ancestor: ' + str(parent))
        if parent.exists() and not parent.is_dir():
            raise ValueError('non-directory ancestor: ' + str(parent))


def baseline():
    """Match actual source/build bytes to already accepted P01 material."""
    accepted = DOCS / 'review_evidence/zlib_pretest_20261027'
    source_record = load(accepted / 'Source_Identity_Check.json')
    build_record = load(accepted / 'Build_Identity_Check.json')
    if source_record.get('status') != 'passed' or build_record.get('status') != 'passed':
        raise ValueError('P01 accepted baseline unavailable')
    observed = {}
    for item in source_record['files']:
        path = SOURCE / item['relativeFile']
        value = regular(path)
        if value != {'bytes': item['bytes'], 'sha256': item['archiveSHA256']}:
            raise ValueError('P01 source differs: ' + str(path))
        observed[str(path)] = value
    for item in build_record['originalFiles']:
        if not item['copy'].replace('\\', '/').startswith('build_context/'):
            continue
        path = Path(item['linuxSource'])
        if not path.is_relative_to(BUILD):
            raise ValueError('unexpected P01 build baseline path')
        value = regular(path)
        if value != {'bytes': item['bytes'], 'sha256': item['sha256']}:
            raise ValueError('P01 build differs: ' + str(path))
        observed[str(path)] = value
    context = load(SETUP / 'Dependency_Preparation_Context_20261028/Read_Only_Context.json')
    pinned = {str(BUILD / x) for x in ['cmake_install.cmake', 'contrib/cmake_install.cmake',
                                    'CMakeCache.txt', 'zlib.pc', 'libz.a', 'zconf.h']}
    actual_context = {x['linuxPath'] for x in context['files'] if x['exists']}
    if actual_context != pinned:
        raise ValueError('unexpected dependency install context collection')
    for item in context['files']:
        if not item['exists']:
            continue
        path = Path(item['linuxPath'])
        value = regular(path)
        if value != {'bytes': item['bytes'], 'sha256': item['sha256']}:
            raise ValueError('pinned install context changed: ' + str(path))
        observed[str(path)] = value
    header = (SOURCE / 'zlib.h').read_text(encoding='utf-8')
    if not re.search(r'^#define\s+ZLIB_VERSION\s+"1\.3\.2"', header, re.M):
        raise ValueError('zlib header version differs')
    return observed


def preflight():
    for name in ['DESTDIR', 'CMAKE_INSTALL_MODE']:
        if os.environ.get(name):
            raise ValueError('unexpected inherited install environment: ' + name)
    no_link_ancestors(BUILD)
    no_link_ancestors(SOURCE)
    no_link_ancestors(PREFIX.parent)
    if PREFIX.exists() or PREFIX.is_symlink():
        raise ValueError('dependency prefix already exists; do not overwrite')
    manifest = BUILD / 'install_manifest_Development.txt'
    if manifest.exists() or manifest.is_symlink():
        raise ValueError('Development install manifest already exists; inspect progress')
    observed = baseline()
    return {'status': 'passed', 'project': 'P08 libpng dependency preparation',
            'dependency': 'P01 zlib 1.3.2', 'prefix': str(PREFIX),
            'baselineFiles': observed,
            'installMap': {rel: {'source': str(path), **regular(path)}
                           for rel, path in INSTALL_MAP.items()},
            'installationExecuted': False, 'buildAndAnalysis': 'not performed'}


def verify(before):
    observed = baseline()
    if before.get('status') != 'passed' or before.get('prefix') != str(PREFIX):
        raise ValueError('invalid pre-install reference')
    if observed != before['baselineFiles']:
        raise ValueError('P01 source/build/install inputs changed during installation')
    no_link_ancestors(PREFIX)
    actual = {}
    for path in PREFIX.rglob('*'):
        if path.is_symlink():
            raise ValueError('installed dependency contains a link')
        if path.is_dir():
            continue
        rel = path.relative_to(PREFIX).as_posix()
        actual[rel] = regular(path)
    if set(actual) != set(INSTALL_MAP):
        raise ValueError('installed file collection differs from Development scope')
    for rel, source in INSTALL_MAP.items():
        if actual[rel] != regular(source) or actual[rel] != {
                k: before['installMap'][rel][k] for k in ['bytes', 'sha256']}:
            raise ValueError('installed bytes differ from accepted P01 artifact: ' + rel)
    manifest = BUILD / 'install_manifest_Development.txt'
    regular(manifest)
    listed = manifest.read_text(encoding='utf-8').splitlines()
    expected = {str(PREFIX / rel) for rel in INSTALL_MAP}
    if len(listed) != len(expected) or set(listed) != expected:
        raise ValueError('CMake install manifest differs from exact prefix destinations')
    return {'status': 'passed', 'project': 'P08 libpng dependency preparation',
            'dependency': 'P01 zlib 1.3.2', 'prefix': str(PREFIX),
            'component': 'Development', 'installedFiles': actual,
            'installedFilesMatchAcceptedP01Bytes': True,
            'P01SourceBuildInputsUnchanged': True,
            'newBuildMetadata': {'path': str(manifest), **regular(manifest)},
            'buildAndAnalysis': 'not performed',
            'meaning': 'dependency installed only;libpng still not configured/built/analyzed'}


if __name__ == '__main__':
    mode, output_arg, *args = sys.argv[1:]
    try:
        result = preflight() if mode == 'preflight' else verify(load(Path(args[0]))) if mode == 'verify' else None
        if result is None:
            raise ValueError('unknown verification mode')
    except Exception as exc:
        result = {'status': 'failed', 'stage': mode, 'error': str(exc), 'buildAndAnalysis': 'not performed'}
    with Path(output_arg).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    if result['status'] != 'passed':
        print('依赖核对失败：' + result['error'], file=sys.stderr)
        raise SystemExit(1)
    if mode == 'preflight':
        print('依赖安装前核对通过：P01固定源码、头、静态库及安装上下文未变；新前缀可用。')
    else:
        print('固定zlib1.3.2依赖安装核对通过：4个Development文件与P01原件一致。')
        print('前缀：' + result['prefix'])
        print('未重新构建zlib，未配置／构建libpng，未运行检测工具。')
