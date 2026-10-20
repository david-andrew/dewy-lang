"""Scalar replacement must preserve independent record values and places."""
from pathlib import Path

import pytest

from tests.support import compiler, run_value_batch

FIXTURES = Path(__file__).parent / 'fixtures' / 'records_sra'


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_records_sra_values(compiler, tmp_path, release, target):
    cases = {path.stem: path.read_text() for path in sorted(FIXTURES.glob('*.dewy'))}
    outcomes = run_value_batch(compiler, tmp_path, cases, release, target)
    for name, (code, diagnostic) in outcomes.items():
        assert code == '42', f'{name}: {code}\n{diagnostic}'


@pytest.mark.core_quick
def test_records_sra_game_codegen(compiler, tmp_path):
    import re
    import subprocess
    from tools.compiler.bench import prepare_source

    source = prepare_source('game', tmp_path)
    built = subprocess.run([compiler, 'build', source, '--release', '--ir',
                            '-o', tmp_path / 'game'], capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    functions = re.split(r'^fn ', built.stdout, flags=re.MULTILINE)
    simulate = next(body for body in functions if body.startswith('f_simulate_'))
    assert re.search(r'\bloop a=', simulate), simulate
    # Check the emitted IR, not slot declarations (which can remain after SRA).
    assert not re.search(r'\bcopy .*imm=24\b', simulate), simulate
    assert not re.search(r'\bcall[ic]? a=', simulate), simulate


@pytest.mark.core_quick
def test_records_sra_large_copy_codegen(compiler, tmp_path):
    import re
    import subprocess

    built = subprocess.run([compiler, 'build', FIXTURES / 'large_game.dewy', '--release', '--ir',
                            '-o', tmp_path / 'large-game'], capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    main = next(body for body in re.split(r'^fn ', built.stdout, flags=re.MULTILINE)
                if body.startswith('f_main_'))
    lines = main.splitlines()
    start = next(i for i, line in enumerate(lines) if re.search(r'\bloop a=', line))
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = next(i for i in range(start + 1, len(lines))
               if lines[i].startswith(' ' * indent + 'end '))
    loop = '\n'.join(lines[start:end])
    # The six-lane record remains in memory. Its five copies per tick become
    # three: the owning-argument and return intermediates have no observer.
    assert len(re.findall(r'\bcopy .*imm=48\b', loop)) == 3, loop
