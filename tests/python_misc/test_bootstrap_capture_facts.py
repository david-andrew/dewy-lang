"""Caller flow facts cannot specialize a deferred local function body."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_bootstrap_lowering import ARENA, build_native_lowering_driver
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def check_capture_facts(binary, tmp_path):
    for name, fixture in [('capture-facts', 'tests/fixtures/native_capture_facts.dewy'),
                          ('local-captures', 'dewy/tests/local_captures.dewy')]:
        source = tmp_path / f'{name}.dewy'
        source.write_text(ARENA + (ROOT / fixture).read_text())
        native = subprocess.run([binary, source], capture_output=True, text=True, timeout=45)
        assert native.returncode == 0, native.stdout + native.stderr
        for label, code in [('native', native.stdout),
                            ('hosted', codegen(SrcFile.from_path(source), debug_locations=False))]:
            output = tmp_path / f'{name}-{label}.udewy'
            output.write_text(code)
            for target in ['x86_64', 'c']:
                assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
                run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                                     text=True, timeout=15)
                assert run.returncode == 42, (name, label, target, run.returncode, run.stdout, run.stderr)


def test_native_capture_facts(tmp_path):
    check_capture_facts(build_native_lowering_driver(tmp_path), tmp_path)
