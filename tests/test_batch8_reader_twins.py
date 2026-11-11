"""Prefix attachment and Q19 agree between the complete reader and its seed twin."""
import subprocess

from tools.compiler.parser_diff import build_pair, compare, environment
from tests.support import ROOT, compiler  # noqa: F401


def test_batch8_reader_twins(compiler, tmp_path):  # noqa: F811
    pair = build_pair(compiler, tmp_path, release=False)
    sources = sorted((ROOT / 'tests/cases/metatag_prefix').glob('*.dewy'))
    deep = tmp_path / 'deep.dewy'
    deep.write_text('main=()=>{\n' + '    $runtime_checks\n' * 300 + '    printl(42)\n}\n')
    for binary in pair:
        result = subprocess.run([binary, 'check', deep], capture_output=True, text=True, timeout=30, env=environment(ROOT / 'lib'))
        assert result.returncode != 0 and 'expression is nested too deeply' in result.stderr, result.stderr
    stacked = tmp_path / 'stacked.dewy'
    stacked.write_text('$extern\n$runtime_checks\nlabs=(x:int64):>int64\nmain=()=>printl($unsafe labs(42))\n')
    for binary in pair:
        result = subprocess.run([binary, 'check', stacked], capture_output=True, text=True, timeout=30, env=environment(ROOT / 'lib'))
        assert result.returncode == 0, result.stderr
    invalid = []
    for i, source in enumerate(['$extern\nx=42\n', '$extern\n$runtime_checks\nx=42\n', '$extern\n$runtime_checks\n', '$extern\n$intrinsic\nx=42\n']):
        path = tmp_path / f'misplaced-{i}.dewy'
        path.write_text(source)
        invalid.append(path)
        for binary in pair:
            result = subprocess.run([binary, 'check', path], capture_output=True, text=True, timeout=30, env=environment(ROOT / 'lib'))
            assert result.returncode != 0 and 'function declaration' in result.stderr, result.stderr
    differences = compare(pair, [*sources, deep, stacked, *invalid], tmp_path, release=False, workers=1)
    assert differences == []
