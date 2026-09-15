"""Warm measurements rebuild the executable and isolate priming observations."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('mode,invocations', [('cold', 1), ('warm', 2)])
def test_measurement_cache_state(tmp_path, mode, invocations):
    source = tmp_path / 'main.dewy'
    source.write_text('let main=():>int64=>42\n')
    compiler = tmp_path / 'compiler'
    compiler.write_text(f'''#!{sys.executable}
import json
import sys
from pathlib import Path
from udewy.cache import cache_artifact
source = Path(sys.argv[-1])
binary = cache_artifact(source)
# An up-to-date executable would bypass compilation; the warm tool must
# remove it while retaining the parse/prelude cache.
assert not binary.exists()
cache = Path('__dewycache__/prelude/retained.pickle')
number = int(cache.read_text()) + 1 if cache.exists() else 1
cache.parent.mkdir(parents=True, exist_ok=True)
cache.write_text(str(number))
binary.parent.mkdir(parents=True, exist_ok=True)
binary.write_text('executable placeholder')
Path('phases.json').write_text(json.dumps({{'checking_seconds': number}}))
with Path('phase-events.jsonl').open('a') as events:
    events.write(str(number) + '\\n')
print('dewy timing frontend', number * 10, 'ns', file=sys.stderr)
''')
    compiler.chmod(0o755)
    output = tmp_path / 'measurement'
    result = subprocess.run([
        sys.executable, ROOT / 'tools/measure_compiler.py', source,
        '--native-executable', compiler, '--output', output,
        '--cache-state', mode, '--phase-timings',
    ], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    record, = [json.loads(line) for line in (output / 'results.jsonl').read_text().splitlines()]
    assert record['status'] == 0
    assert record['checking_seconds'] == invocations
    assert record['reported_phase_nanoseconds'] == {'frontend': invocations * 10}
    work = output / 'run-00'
    assert (work / 'phase-events.jsonl').read_text() == f'{invocations}\n'
    assert (work / '__dewycache__/prelude/retained.pickle').read_text() == str(invocations)
    assert json.loads((output / 'metadata.json').read_text())['cache_mode'] == mode
    if mode == 'warm':
        assert record['priming']['status'] == 0
        assert (work / 'priming/phase-events.jsonl').read_text() == '1\n'
        assert json.loads((work / 'priming/phases.json').read_text()) == {'checking_seconds': 1}
    else:
        assert 'priming' not in record


def test_failed_prime_is_not_a_warm_sample(tmp_path):
    source = tmp_path / 'main.dewy'
    source.write_text('void\n')
    compiler = tmp_path / 'compiler'
    compiler.write_text('#!/bin/sh\nexit 7\n')
    compiler.chmod(0o755)
    output = tmp_path / 'measurement'
    result = subprocess.run([
        sys.executable, ROOT / 'tools/measure_compiler.py', source,
        '--native-executable', compiler, '--output', output, '--cache-state', 'warm',
    ], capture_output=True, text=True, timeout=20)
    assert result.returncode == 1, result.stdout + result.stderr
    record = json.loads((output / 'results.jsonl').read_text())
    assert record['status'] == 'priming_failed'
    assert record['priming']['status'] == 7
    assert 'wall_seconds' not in record
    assert not (output / 'run-00/stdout.log').exists()
