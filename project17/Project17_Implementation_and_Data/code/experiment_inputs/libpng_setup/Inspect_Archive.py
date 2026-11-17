"""Read the downloaded P08 archive; never extract, build or run libpng."""
from pathlib import Path,PurePosixPath
import hashlib
import json
import re
import sys
import tarfile

COMMIT='2b978915d82377df13fcbb1fb56660195ded868a'
PREFIX='libpng-'+COMMIT


def blob(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


def inspect(archive,reference):
    if reference.get('status')!='passed_official_identity_chain' or reference.get('commit')!=COMMIT or reference.get('treeTruncated') is not False:
        raise ValueError('official identity chain/tree not validated')
    tree=reference['tree']; expected={x['path']:x for x in tree if x['type']=='blob'}
    gitlinks=[x for x in tree if x['type']=='commit']
    directories={x['path'] for x in tree if x['type']=='tree'}
    files={};links={};dirs=set();seen=set();content={};mismatches=[]
    with tarfile.open(archive,'r:gz') as tf:
        for m in tf.getmembers():
            name=m.name.rstrip('/'); parts=PurePosixPath(name).parts
            if name in seen or not parts or parts[0]!=PREFIX or name.startswith('/') or any(p in ['.','..',''] for p in name.split('/')):
                raise ValueError('invalid/duplicate archive path: '+name)
            seen.add(name);relative='/'.join(parts[1:])
            if m.isdir():
                if relative:dirs.add(relative)
                continue
            if relative not in expected:raise ValueError('unexpected archive member: '+relative)
            x=expected[relative]
            if m.issym() and x['mode']=='120000':
                data=m.linkname.encode('utf-8',errors='surrogateescape')
                links[relative]={'target':m.linkname,'bytes':len(data),'gitBlobSHA1':blob(data),'sha256':hashlib.sha256(data).hexdigest()}
            elif m.isfile() and x['mode'] in ['100644','100755']:
                f=tf.extractfile(m)
                if f is None:raise ValueError('unreadable regular member: '+relative)
                data=f.read()
                files[relative]={'bytes':len(data),'gitBlobSHA1':blob(data),'sha256':hashlib.sha256(data).hexdigest()}
                if bool(m.mode&0o111)!=(x['mode']=='100755'):mismatches.append({'path':relative,'reason':'Git executable bit mismatch'})
                if relative in ['CMakeLists.txt','LICENSE','png.h'] or relative.endswith('.gitattributes'):
                    content[relative]=data.decode('utf-8',errors='replace')
            else:raise ValueError('unsupported member type/mode: '+relative)
            if len(data)!=x.get('size') or blob(data)!=x['sha']:
                mismatches.append({'path':relative,'reason':'size or Git blob mismatch;export-subst must be reviewed if applicable'})
    missing=sorted(set(expected)-set(files)-set(links)); missing_dirs=sorted(directories-dirs); extra_dirs=sorted(dirs-directories)
    h=content.get('png.h','')
    for macro,value in [('PNG_LIBPNG_VER_MAJOR',1),('PNG_LIBPNG_VER_MINOR',6),('PNG_LIBPNG_VER_RELEASE',50),('PNG_LIBPNG_VER',10650)]:
        if not re.search(r'^#define\s+'+macro+r'\s+'+str(value)+r'\b',h,re.M):
            raise ValueError('header version mismatch: '+macro)
    if not re.search(r'^#define\s+PNG_LIBPNG_VER_STRING\s+"1\.6\.50"',h,re.M):
        raise ValueError('header version string mismatch')
    cmake=content.get('CMakeLists.txt','')
    for variable,value in [('PNGLIB_MAJOR',1),('PNGLIB_MINOR',6),('PNGLIB_REVISION',50)]:
        if not re.search(r'set\(\s*'+variable+r'\s+'+str(value)+r'\s*\)',cmake):
            raise ValueError('CMake version mismatch: '+variable)
    required={'pngset.c', 'pngstruct.h', 'pngtrans.c', 'pngpriv.h', 'pngrutil.c', 'pngdebug.h', 'png.c', 'pngrio.c', 'pngmem.c', 'pngwio.c', 'pngwrite.c', 'pngerror.c', 'pngpread.c', 'pngget.c', 'CMakeLists.txt', 'pngwutil.c', 'LICENSE', 'png.h', 'pnginfo.h', 'pngrtran.c', 'pngconf.h', 'pngwtran.c', 'scripts/pnglibconf.h.prebuilt', 'pngread.c'}
    if not required<=set(files):raise ValueError('required library members absent from archive')
    if 'PNG Reference Library License version 2' not in content.get('LICENSE',''):
        raise ValueError('expected libpng-2.0 license text not found')
    complete=not missing and not missing_dirs and not extra_dirs and not mismatches and not gitlinks
    data=Path(archive).read_bytes()
    return {'status':'passed' if complete else 'pending_archive_export_or_dependency_scope_review',
        'project':'P08 libpng','version':'1.6.50','commit':COMMIT,'rootTreeSHA':reference['rootTreeSHA'],
        'archiveRoot':PREFIX,'archiveBytes':len(data),'archiveSHA256':hashlib.sha256(data).hexdigest(),
        'regularFiles':len(files),'symlinks':len(links),'directoriesExcludingRoot':len(dirs),
        'files':files,'links':links,'missingGitBlobMembers':missing,'missingDirectories':missing_dirs,
        'extraDirectories':extra_dirs,'contentMismatches':mismatches,'gitlinks':gitlinks,
        'attributeFiles':{k:v for k,v in content.items() if k.endswith('.gitattributes')},
        'allArchiveMembersMatchFullOfficialGitTree':complete,
        'scopePolicy':'if export-ignore/subst or gitlinks affect equality,retain differences for explicit review;no generic attribute parser or silent exclusions',
        'meaning':'local archive SHA is not an upstream published archive checksum;link targets checked as Git blobs without dereferencing',
        'extractionBuildAndAnalysis':'not performed'}


if __name__=='__main__':
    archive,output,reference=map(Path,sys.argv[1:])
    try:
        result=inspect(archive,json.loads(reference.read_text(encoding='utf-8-sig')))
    except Exception as exc:
        result={'status':'failed','error':str(exc),'extractionBuildAndAnalysis':'not performed'}
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    if result['status']=='passed':
        print('libpng1.6.50原包身份初检通过：完整文件／目录集合及Git blob一致。')
        print(f"普通文件{result['regularFiles']}、链接{result['symlinks']}、子目录{result['directoriesExcludingRoot']}；未解压／构建／检测。")
    else:
        print('原包检查状态：'+result['status']+'；记录已保存，请返回输出核对。',file=sys.stderr)
        if 'error' in result:print(result['error'],file=sys.stderr)
        raise SystemExit(2 if result['status'].startswith('pending') else 1)
