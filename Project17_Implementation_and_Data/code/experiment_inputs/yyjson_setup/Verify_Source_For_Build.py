"""Reuse fixed source verification with an explicit outer-build-stage label."""
from pathlib import Path
import json
import runpy
import sys

source, accepted, official, output = map(Path, sys.argv[1:5])
phase = sys.argv[5]
if phase not in ['before-build', 'after-build']:
    raise SystemExit('unexpected source guard phase')
verify = runpy.run_path(str(Path(__file__).with_name('Verify_Extracted_Source.py')))['verify']
try:
    result = verify(source, json.loads(accepted.read_text(encoding='utf-8-sig')),
                    json.loads(official.read_text(encoding='utf-8-sig')))
except Exception as exc:
    result = {'status': 'failed', 'error': str(exc), 'sourceRoot': str(source)}
result.pop('buildAndAnalysis', None)
result['callerPhase'] = phase
result['guardExecutedBuildOrAnalysis'] = False
result['phaseMeaning'] = 'caller phase label only;actual configure/build status is in separate command and exit-code records'
with output.open('x', encoding='utf-8') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
if result['status'] != 'passed':
    print('源码身份检查失败：' + result['error'], file=sys.stderr)
    raise SystemExit(1)
print(f"{phase}：{result['regularFiles']}文件／{result['directoriesExcludingRoot']}子目录源码身份保持一致。")
