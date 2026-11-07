"""Backend entry points, stubs, adapters and patching agree with frozen Jo on every native target,
with and without debug information."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

PROGRAMS = {
    'loops.dewy': 'main=()=>{\n    let xs=[1 2 3]\n    loop x in xs {printl(x * 2)}\n    let total=0.5\n    printl(total)\n}\n',
    'calls.dewy': 'twice=(f:<(x:int64):>int64> v:int64):>int64=>f(f(v))\nmain=()=>printl(twice((x:int64)=>x + 3 4))\n',
}
TARGETS = ['x86_64-linux', 'aarch64-linux', 'aarch64-mac', 'x86_64-windows']


def test_backend_stubs_match_twin(compiler, tmp_path, monkeypatch):
    for name, text in PROGRAMS.items():
        (tmp_path / name).write_text(text)
    flags = [extra for t in TARGETS for extra in (('--target', t), ('-g', '--target', t))]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('arm64_ops', 'x64_ops'),
                             [*PROGRAMS, 'tests/cases/dogfood/89_expense_split.dewy'], flags)
    built = [r for r in results if r[2] == 0]
    assert len(built) >= 16 and any(name.endswith('.pdb') for r in built for name in r[5])
