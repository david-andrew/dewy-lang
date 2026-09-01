"""`$prototype`: unproven obligations defer to runtime checks that panic."""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _dewy(*argv: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, 'PYTHONPATH': str(REPO_ROOT), 'DEWY_FAILURE_LOG': '0'}
    return subprocess.run([sys.executable, '-m', 'dewy', *argv], cwd=cwd, env=env, capture_output=True, text=True, check=False)


def test_deferred_proofs_warn_at_compile_and_panic_at_runtime(tmp_path: Path) -> None:
    program = tmp_path / 'p.dewy'
    program.write_text('$prototype\nmain = (argv:array<string>) => {\n    printl(argv[0])\n    printl(argv[5])\n    return 0\n}\n')
    result = _dewy('p.dewy', cwd=tmp_path)
    assert result.returncode == 102
    assert result.stderr.count('Warning: prototype: array index is not proven in bounds') == 2
    assert 'deferred to a runtime check by `$prototype`' in result.stderr
    # `argv[0]` passed its check and printed; `argv[5]` panicked with the deferred report
    assert result.stdout.strip().endswith('p')
    assert 'a `$prototype` runtime check failed' in result.stderr
    assert 'the index interval here is `5..5`' in result.stderr


def test_refinement_and_narrowing_checks_pass_when_the_values_behave(tmp_path: Path) -> None:
    program = tmp_path / 'p.dewy'
    program.write_text(
        '$prototype\n'
        'half = (n:int64 d:int64<i => i not=? 0>):>int64 => n // d\n'
        'main = (argv:array<string>) => {\n'
        '    printl(half(10 argv.length))\n'
        '    return 0\n'
        '}\n'
    )
    result = _dewy('p.dewy', cwd=tmp_path)
    assert result.returncode == 0 and result.stdout.strip() == '10'
    assert 'Warning: prototype: cannot prove refinement' in result.stderr


def test_prototype_warnings_false_silences_the_deferral_notes(tmp_path: Path) -> None:
    program = tmp_path / 'p.dewy'
    program.write_text('$prototype\n$prototype_warnings = false\nmain = (argv:array<string>) => {\n    printl(argv[0])\n    return 0\n}\n')
    result = _dewy('p.dewy', cwd=tmp_path)
    assert result.returncode == 0
    assert 'Warning: prototype' not in result.stderr


def test_prototype_belongs_in_the_entry_module(tmp_path: Path) -> None:
    (tmp_path / 'helper.dewy').write_text('$prototype\nx = 1\n')
    (tmp_path / 'p.dewy').write_text('import [path="helper.dewy"]\nmain = () => { return 0 }\n')
    result = _dewy('p.dewy', cwd=tmp_path)
    assert result.returncode != 0 and '`$prototype` belongs in the entry module' in result.stderr


def test_without_the_metatag_proofs_still_gate_compilation(tmp_path: Path) -> None:
    program = tmp_path / 'p.dewy'
    program.write_text('main = (argv:array<string>) => {\n    printl(argv[5])\n    return 0\n}\n')
    result = _dewy('p.dewy', cwd=tmp_path)
    assert result.returncode != 0 and 'array index is not proven in bounds' in result.stderr
