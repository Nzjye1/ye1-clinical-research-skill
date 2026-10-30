"""One local invocation from canonical input to private model and aggregate artifacts."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

import adapter
import provider


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--request', type=Path, help='Local normalized canonical provider request JSON')
    source.add_argument('--demo', action='store_true', help='Small built-in synthetic example; no database connection')
    parser.add_argument('--algorithm', choices=list(provider.METHODS.values()), default='random_forest')
    parser.add_argument('--output', type=Path, required=True, help='A new output directory')
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print('{"ok":false,"reason_code":"OUTPUT_ALREADY_EXISTS"}'); return 2
    for name in ('private', 'tables', 'figures'):
        (output / name).mkdir()
    if args.demo:
        sys.path.insert(0, str(provider.MODULE_ROOT / 'tests'))
        from support import request
        method = next(k for k, v in provider.METHODS.items() if v == args.algorithm)
        req = request(method)
    else:
        req = adapter.strict_load(args.request.read_bytes())
    adapter.write_json(output / 'private/request.json', req)
    proc = subprocess.run([sys.executable, '-B', str(provider.MODULE_ROOT / 'adapter.py'),
                           str(output / 'private/request.json'), str(output / 'private/response.json')], capture_output=True, text=True)
    (output / 'private/provider.log').write_text(proc.stdout + proc.stderr, encoding='utf-8')
    response = adapter.strict_load((output / 'private/response.json').read_bytes())
    if not response['ok'] or response['record']['status'] == 'BLOCKED_ESTIMATION':
        reason = response.get('reason_code') or response['record'].get('reason_code')
        adapter.write_json(output / 'result.json', {'schema_version': 'nonlinear-module-preview/1.0.0',
            'execution_status': 'blocked', 'reason_code': reason, 'test_only': True,
            'scientific_review': 'pending', 'export_status': 'local_only',
            'counts': response.get('record', {}).get('counts', {}), 'metrics': None})
        (output / 'METHODS-AND-RESULTS.md').write_text('SYNTHETIC_TEST_ONLY. Estimation blocked: ' + reason +
            '. No model, validation performance, or clinical conclusion was produced. Available denominators are in result.json.\n', encoding='utf-8')
        print(json.dumps({'ok': False, 'reason_code': reason})); return 2
    lock = adapter.strict_load((provider.CORE_ROOT / 'runtime-lock.json').read_bytes())
    render = subprocess.run([lock['rscript'], '--vanilla', str(provider.MODULE_ROOT / 'tests/render.R'),
                             str(provider.CORE_ROOT), str(provider.MODULE_ROOT), str(output)], capture_output=True, text=True)
    (output / 'private/render.log').write_text(render.stdout + render.stderr, encoding='utf-8')
    if render.returncode:
        print('{"ok":false,"reason_code":"MODULE_PROJECTION_FAILED"}'); return 2
    print(json.dumps({'ok': True, 'method_id': req['method_id'], 'output': str(output),
                      'status': 'SYNTHETIC_TEST_ONLY', 'scientific_review': 'pending'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
