"""Validate saved P10 official responses; no network, extraction or execution."""
import json
from pathlib import Path, PurePosixPath
import sys

COMMIT = 'a1b99daa2a3393884220264c927a48ba1251a9c6'
ROOT_TREE = 'b5b227d68996d6e0cdafd9bf4bdb53cf5f05f339'
TAG = 'v2.10.0'
REQUIRED = {'CMakeLists.txt', 'utils.cmake', 'LICENSE.md', 'utf8proc.c',
            'utf8proc.h', 'utf8proc_data.c'}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def identity(ref, commit):
    if (ref.get('ref') != 'refs/tags/' + TAG or
            ref.get('object', {}).get('type') != 'commit' or
            ref['object'].get('sha') != COMMIT):
        raise ValueError('fixed lightweight tag does not point to registered commit')
    if commit.get('sha') != COMMIT or commit.get('tree', {}).get('sha') != ROOT_TREE:
        raise ValueError('commit or pinned root tree SHA mismatch')
    return ROOT_TREE


def reference(ref, commit, tree):
    identity(ref, commit)
    if tree.get('sha') != ROOT_TREE or tree.get('truncated') is not False or not isinstance(tree.get('tree'), list):
        raise ValueError('official recursive tree is mismatched or incomplete')
    seen = set()
    for entry in tree['tree']:
        path = entry.get('path', '')
        if (not path or path in seen or PurePosixPath(path).is_absolute() or
                any(part in ('', '.', '..') for part in path.split('/'))):
            raise ValueError('invalid or duplicate tree path: ' + path)
        seen.add(path)
        if not ((entry.get('type') == 'tree' and entry.get('mode') == '040000') or
                (entry.get('type') == 'blob' and entry.get('mode') in ('100644', '100755', '120000'))):
            raise ValueError('unsupported tree entry: ' + path)
    if not REQUIRED <= seen:
        raise ValueError('required fixed library files missing')
    if len(tree['tree']) != 50 or sum(e['type'] == 'blob' for e in tree['tree']) != 45:
        raise ValueError('fixed full tree member count mismatch')
    return {'status': 'passed_official_identity_chain', 'project': 'P10 utf8proc',
            'version': '2.10.0', 'tag': TAG, 'refType': 'commit', 'commit': COMMIT,
            'rootTreeSHA': ROOT_TREE, 'treeTruncated': False, 'tree': tree['tree'],
            'meaning': 'official Git identity and full tree; downloaded archive checked separately'}


def main():
    mode, *args = sys.argv[1:]
    if mode == 'chain':
        print(identity(*(load(path) for path in args)))
    elif mode == 'tree':
        ref_path, commit_path, tree_path, output = args
        result = reference(load(ref_path), load(commit_path), load(tree_path))
        result['responsePaths'] = [ref_path, commit_path, tree_path]
        with Path(output).open('x', encoding='utf-8') as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        print('官方轻量tag→固定commit→完整递归树核对通过；尚未验收下载原包。')
    else:
        raise ValueError('unknown mode')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
