"""Check the accepted complete P10 source before/after a user-run build."""
import hashlib
import json
from pathlib import Path
import sys

from Verify_Extracted_Source import load, verify


def check(source, archive, download, archive_acceptance, source_acceptance, source_record):
    accepted = load(source_acceptance)
    if (accepted.get('status') != 'passed' or accepted.get('runId') != 'SRC-P10-001' or
            accepted.get('commit') != 'a1b99daa2a3393884220264c927a48ba1251a9c6' or
            accepted.get('regularFiles') != 45 or accepted.get('directoriesExcludingRoot') != 5):
        raise ValueError('P10 extracted source has not been accepted')
    if source_record.is_symlink() or not source_record.is_file():
        raise ValueError('accepted SRC source-check.json missing or linked')
    if hashlib.sha256(source_record.read_bytes()).hexdigest() != accepted['sourceCheckSHA256']:
        raise ValueError('SRC-P10-001 source identity record changed')
    for path in [source, *source.parents]:
        if path.is_symlink():
            raise ValueError('source or ancestor is a symbolic link')
    actual = verify(archive, download, load(archive_acceptance), source)
    if actual != load(source_record):
        raise ValueError('complete source differs from accepted SRC-P10-001 inventory')
    actual['configurationBuildAndAnalysis'] = 'source identity check only; build status recorded separately'
    actual['sourceAcceptanceSHA256'] = hashlib.sha256(source_acceptance.read_bytes()).hexdigest()
    return actual


def main():
    source, archive, download, archive_acceptance, source_acceptance, source_record, phase, output = sys.argv[1:]
    try:
        result = check(*map(Path, [source, archive, download, archive_acceptance,
                                  source_acceptance, source_record]))
        result['phase'] = phase
    except Exception as error:
        result = {'status': 'failed', 'phase': phase, 'error': str(error)}
    with Path(output).open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    if result['status'] != 'passed':
        print(result['error'], file=sys.stderr)
        raise SystemExit(1)
    print(phase + ': 45普通文件／5子目录的完整集合、SHA-256、Git blob和执行位与SRC原件保持一致。')


if __name__ == '__main__':
    main()
