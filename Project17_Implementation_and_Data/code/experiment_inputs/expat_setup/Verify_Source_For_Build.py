"""Compare the complete P07 source with archive identity and accepted SRC record."""
from pathlib import Path
import hashlib
import json
import sys

sys.dont_write_bytecode = True
from Verify_Extracted_Source import load, verify, SHA256


if __name__ == '__main__':
    source, archive, accepted, official, source_record, output = map(Path, sys.argv[1:7])
    phase = sys.argv[7]
    if phase not in ['before-build', 'after-build', 'after-configure-failure', 'after-build-failure']:
        raise SystemExit('unexpected source guard phase')
    try:
        if archive.is_symlink() or hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
            raise ValueError('fixed archive bytes changed')
        result = verify(source, load(accepted), load(official), official.parent)
        previous = load(source_record)
        for key in ['status', 'commit', 'rootTreeSHA', 'archiveSHA256', 'sourceRoot',
                    'regularFiles', 'symlinks', 'directoriesExcludingRoot', 'files', 'links', 'directories']:
            if previous.get(key) != result.get(key):
                raise ValueError('complete source differs from accepted SRC-P07-001: ' + key)
        result.pop('buildAndAnalysis', None)
        result['acceptedSourceRecordSHA256'] = hashlib.sha256(source_record.read_bytes()).hexdigest()
        result['allContentsAndModesMatchAcceptedSourceRecord'] = True
    except Exception as exc:
        result = {'status': 'failed', 'error': str(exc), 'sourceRoot': str(source)}
    result['callerPhase'] = phase
    result['guardExecutedBuildOrAnalysis'] = False
    result['phaseMeaning'] = 'caller phase label only;configure/build execution is recorded separately'
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    if result['status'] != 'passed':
        print('完整源码身份检查失败：' + result['error'], file=sys.stderr)
        raise SystemExit(1)
    print(f'{phase}：207个普通文件／1链接／20目录与已验收源码及官方blob保持一致。')
