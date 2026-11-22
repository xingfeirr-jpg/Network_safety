"""Validate saved official GitHub responses; no network or extraction."""
from pathlib import Path
import json
import re
import sys

COMMIT='f9a3eeb3e09fbea04b1c451ffc422ab2f1e45744'
TAG='R_2_7_1'
TAG_OBJECT='436d5aa84b32fd2826c883ca543ddda6145d6a5a'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def identity(ref, tag, commit):
    if ref.get('ref')!='refs/tags/'+TAG or ref.get('object',{}).get('type')!='tag' or ref['object'].get('sha')!=TAG_OBJECT:
        raise ValueError('tag ref does not match the registered fixed tag object')
    if tag.get('sha')!=TAG_OBJECT or tag.get('tag')!=TAG or tag.get('object',{}).get('type')!='commit' or tag['object'].get('sha')!=COMMIT:
        raise ValueError('annotated tag does not point to the registered fixed commit')
    if commit.get('sha')!=COMMIT:
        raise ValueError('git commit response SHA mismatch')
    tree=commit.get('tree',{}).get('sha','')
    if not re.fullmatch(r'[a-f0-9]{40}',tree):
        raise ValueError('commit response lacks a valid root tree SHA')
    return tree


def main():
    mode,*args=sys.argv[1:]
    if mode=='chain':
        ref,tag,commit=map(load,args)
        print(identity(ref,tag,commit))
    elif mode=='tree':
        ref_path,tag_path,commit_path,tree_path,output=args
        root=identity(load(ref_path),load(tag_path),load(commit_path))
        tree=load(tree_path)
        if tree.get('sha')!=root or tree.get('truncated') is not False or not isinstance(tree.get('tree'),list):
            raise ValueError('recursive tree is mismatched, incomplete or truncated')
        seen=set()
        for x in tree['tree']:
            path=x.get('path','')
            if not path or path in seen or path.startswith('/') or any(y in ['.','..',''] for y in path.split('/')):
                raise ValueError('invalid/duplicate tree path: '+path)
            seen.add(path)
            valid=((x['type']=='tree' and x['mode']=='040000') or
                (x['type']=='blob' and x['mode'] in ['100644','100755','120000']) or
                (x['type']=='commit' and x['mode']=='160000'))
            if not valid:raise ValueError('unsupported tree entry: '+path)
        required={'expat/CMakeLists.txt','expat/COPYING','expat/lib/expat.h','expat/lib/xmlparse.c','expat/lib/xmlrole.c',
            'expat/lib/xmltok.c','expat/lib/xmltok_impl.c','expat/lib/xmltok_ns.c','expat/expat_config.h.cmake'}
        if not required<=seen:raise ValueError('fixed library files missing from official tree: '+str(sorted(required-seen)))
        result={'status':'passed_official_identity_chain','project':'P07 Expat','version':'2.7.1','tag':TAG,
            'tagObject':TAG_OBJECT,'commit':COMMIT,'rootTreeSHA':root,'treeTruncated':False,'tree':tree['tree'],
            'responsePaths':[ref_path,tag_path,commit_path,tree_path],
            'meaning':'full official Git tree;archive export scope and actual member contents are checked separately'}
        with Path(output).open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
        print('官方tag→tag object→commit及完整递归树身份通过；尚未验收原包内容。')
    else:raise ValueError('unknown mode')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(str(exc),file=sys.stderr)
        raise SystemExit(1)
