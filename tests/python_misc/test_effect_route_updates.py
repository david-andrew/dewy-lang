"""Effect joins update the actual owner and avoid copying repeated routes."""
from pathlib import Path
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

ROOT=Path(__file__).resolve().parents[2]


def test_effect_route_updates(tmp_path):
    source=SrcFile.from_path(ROOT/'tests/fixtures/effect_route_updates.dewy')
    for result in execute(tmp_path,'effect-route-updates',codegen(source,debug_locations=False)):
        assert result.stdout==''


def test_native_effect_route_updates_allocate_nothing_when_unchanged(tmp_path):
    import subprocess
    from test_bootstrap_structural_text import build_program_driver
    from udewy.cache import cache_artifact
    from udewy.frontend import EntryPointOptions, entry_point
    source=ROOT/'tests/fixtures/effect_route_updates.dewy'
    compiled=subprocess.run([build_program_driver(tmp_path),source,ROOT/'library',tmp_path/'prelude-cache'],
                            text=True,capture_output=True,timeout=180)
    assert compiled.returncode==0,compiled.stderr
    output=tmp_path/'native-effect-routes.udewy'
    output.write_text(compiled.stdout)
    for target in ['x86_64','c']:
        assert entry_point(output,[],EntryPointOptions(compile_only=True,target=target))==0
        run=subprocess.run([cache_artifact(output).resolve(),'zero-allocation'],capture_output=True,text=True,timeout=15)
        assert run.returncode==42,run.stdout+run.stderr
