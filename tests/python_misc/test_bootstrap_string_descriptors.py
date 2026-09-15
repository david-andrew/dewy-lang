"""Shared native string descriptors retain values without per-copy allocation."""
import subprocess

from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point
from test_bootstrap_structural_text import build_program_driver, check_structural_text
from test_bootstrap_lowering import ROOT


def test_native_string_descriptor_sharing(tmp_path):
    binary = build_program_driver(tmp_path)
    cases = [(ROOT / 'tests/fixtures' / f'{name}.dewy').read_text() for name in (
        'native_string_descriptor_sharing', 'native_string_lifetimes',
        'native_string_scratch', 'native_string_materialization',
        'native_static_strings',
    )]
    # Allocation budgets belong to native lowering. Hosted strings retain
    # their existing frame-region policy, so test those semantics separately.
    for index, text in enumerate(cases):
        source = tmp_path / f'case-{index}.dewy'
        source.write_text(text)
        compiled = subprocess.run([binary, source, ROOT / 'library', tmp_path / 'prelude-cache'],
                                  capture_output=True, text=True, timeout=120)
        assert compiled.returncode == 0, compiled.stderr
        output = source.with_suffix('.udewy')
        output.write_text(compiled.stdout)
        for target in ('x86_64', 'c'):
            assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
            result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=15)
            assert result.returncode == 42, (index, target, result)
    (tmp_path / 'text').mkdir()
    check_structural_text(binary, tmp_path / 'text', cases=[
        "let f=(s:string):>string=>s\nlet main=():>int64=>{let s=f('ab'+'cd') let old=s s='x' return if old=?'abcd' and s=?'x' 42 else 0}",
    ], errors=[])
