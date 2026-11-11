"""Rare reader constructions agree with frozen Jo: build settings, scoped allocators, `$expect`
operands, large literals, literal method rows, compound assignments and reserved names."""
import subprocess

from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

PROGRAMS = {
    'mode.dewy': "$build.mode = 'release'\nmain=()=>printl(\"mode\")\n",
    'mode_bad.dewy': "$build.mode = 'fast'\nmain=()=>printl(\"mode\")\n",
    'target.dewy': "$target = 'x86_64-linux'\nmain=()=>printl(\"target\")\n",
    'target_bad.dewy': "$target = 'z80-cpm'\nmain=()=>printl(\"target\")\n",
    'twice.dewy': "$build.mode = 'debug'\n$build.mode = 'debug'\nmain=()=>printl(\"twice\")\n",
    'arena.dewy': 'main=()=>{\n    let a=Arena[]\n    let n=$allocator(@a) [1 2 3].length\n    printl(n)\n}\n',
    'expect.dewy': '$test\nsums=()=>$expect 1 + 1 =? 3\n$test\nless=()=>$expect "a<?b" not=? "a<?b"\nmain=()=>printl(0)\n',
    'big.dewy': 'main=()=>{\n    let x=123456789012345678901234567890\n    printl(x * 2)\n    printl(-98765432109876543210)\n}\n',
    'compound.dewy': '$runtime_checks\nmain=()=>{\n    let x:int64=7\n    x+=1 x-=2 x*=3 x//=2 x%=5 x<<=2 x>>=1 x&=6 x|=1 x^=3\n    let b=true\n    b and=false b or=true\n    printl("{x} {b}")\n}\n',
    'reserved.dewy': 'main=()=>{\n    let end=1\n    printl(end)\n}\n',
    'reserved_void.dewy': 'main=()=>{\n    let void=1\n    printl(void)\n}\n',
    'methods.dewy': 'Counter:type=[n:int64]\nmain=()=>{\n    let c=Counter[2]\n    let r=[double=(x:int64)=>x*2 name="row"]\n'
                    '    printl("{c.n} {r.double(c.n)} {r.name}")\n}\n',
    'dropped.dewy': '$supported_targets = ["x86_64-linux" "wasm32"]\nif $target.os =? "windows" {\n    g = () => 1\n}\n'
                    'main=()=>{\n    if $target.arch =? "aarch64" {printl(g())}\n    printl("here")\n}\n',
}


def outcome(binary, tmp_path, label):
    out = tmp_path / label
    out.mkdir()
    results = []
    for name in PROGRAMS:
        r = subprocess.run([binary, 'build', name, '-o', out / name], cwd=tmp_path, capture_output=True,
                           text=True, timeout=120, check=False)
        made = (out / name).read_bytes() if (out / name).exists() else b''
        t = subprocess.run([binary, 'test', name], cwd=tmp_path, capture_output=True, text=True, timeout=120,
                           check=False) if name == 'expect.dewy' else None
        results.append((name, r.returncode, r.stdout, r.stderr.replace(str(binary), 'dewy-core'), made,
                        t and (t.returncode, t.stdout, t.stderr.replace(str(binary), 'dewy-core'))))
    return results


def test_dewy_node_rare_matches_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    for name, text in PROGRAMS.items():
        (tmp_path / name).write_text(text)
    dewy, jo = leaf_compilers(compiler, tmp_path, ('dewy_node_rare',))
    expected = outcome(jo, tmp_path, 'jo')
    assert outcome(dewy, tmp_path, 'dewy') == expected
    by = {r[0]: r for r in expected}
    assert by['mode.dewy'][1] == 0 and by['mode_bad.dewy'][1] != 0 and by['twice.dewy'][1] != 0
    assert "reserved, not a name" in by['reserved.dewy'][3] and by['big.dewy'][1] == 0
