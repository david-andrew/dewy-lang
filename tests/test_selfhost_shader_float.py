"""gl_float in glsl_emit and ml_float in msl_stmts, and their glsl_stmts caller, match frozen Jo."""
import random
import struct
import subprocess

import pytest

from tests import selfhost_lsp_double
from tests.selfhost_build_double import build_all
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_shader_nan import PROGRAM

pytestmark = pytest.mark.nightly


def bit_cases():
    # Both zero signs, subnormals, normal/exponent transitions, f32 rounding
    # ties/overflow, infinities and signed quiet/signaling NaN payloads.
    edges = [0, 1, 0x000fffffffffffff, 0x0010000000000000,
             0x3fefffffffffffff, 0x3ff0000000000000, 0x3ff0000000000001,
             0x7fefffffffffffff, 0x7ff0000000000000, 0x7ff0000000000001,
             0x7ff8000000000000, 0x7fffffffffffffff]
    for x in (0.1, 1e-7, 1e20, 1e300, 1 + 2**-24, 1 + 2**-23,
              2**-149, 2**-150, 2**-126, (2 - 2**-23) * 2**127):
        edges.append(struct.unpack('>Q', struct.pack('>d', x))[0])
    rng = random.Random(441)
    return sorted(set(edges + [v | (1 << 63) for v in edges] +
                      [rng.getrandbits(64) for _ in range(96)]))


def word(v):
    low = f'u64({v & ((1 << 63) - 1)})'
    return f'({low} | (u64(1) << 63))' if v >> 63 else low


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_shader_float_match_twins(compiler, tmp_path, monkeypatch, release):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    bits = bit_cases()
    driver = '''use 'main.jo'
use 'glsl_emit.dewy'
use 'msl_stmts.dewy'
main = ():
    if args().len() > 1 and args()[1] == "float-values":
        bits: u64[] = [BITS]
        loop b in bits:
            x = f64_from_bits(b)
            print("{b}\\t{gl_float(x)}\\t{ml_float(x)}")
    else:
        lower_test_cli()
'''.replace('BITS', ', '.join(map(word, bits)))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', driver)
    original = selfhost_lsp_double.cached_driver
    monkeypatch.setattr(selfhost_lsp_double, 'cached_driver',
                        lambda compiler, path, _, modules: original(compiler, path, release, modules))
    binaries = selfhost_lsp_double.leaf_compilers(
        compiler, tmp_path, ('glsl_emit', 'msl_stmts', 'glsl_stmts'))
    outputs = [subprocess.run([b, 'float-values'], capture_output=True, timeout=30)
               for b in binaries]
    assert all(p.returncode == 0 and not p.stderr for p in outputs)
    assert outputs[0].stdout == outputs[1].stdout
    rows = {int(b): (g, m) for b, g, m in
            (line.split('\t') for line in outputs[0].stdout.decode().splitlines())}
    assert set(rows) == set(bits)
    assert rows[0] == ('0.0', '0.0f')
    assert rows[1 << 63] == ('-0.0', '-0.0f')
    assert rows[0x7ff0000000000000] == ('uintBitsToFloat(0x7f800000u)', 'INFINITY')
    assert rows[0xfff0000000000000] == ('uintBitsToFloat(0xff800000u)', '(-INFINITY)')
    for v in (0x7ff0000000000001, 0xfff8000000000000):
        assert rows[v] == ('uintBitsToFloat(0x7fc00000u)', 'NAN')
    # Preserve the existing order: nonfinite tests precede f32 narrowing.
    assert rows[0x7fefffffffffffff][1] == 'inf.0f'

    (tmp_path / 'nan_shader.dewy').write_text(PROGRAM)
    paths = ['nan_shader.dewy', ROOT / 'tests/cases/game/polyline_joins.dewy']
    results, glsl, metal = [], [], []
    for binary, label in zip(binaries, ('dewy', 'jo')):
        native = build_all(binary, tmp_path, label + '_native', paths)
        run_dir = tmp_path / (label + '_run')
        run_dir.mkdir()
        ran = subprocess.run([tmp_path / (label + '_native') / 'p0-0'],
                             cwd=run_dir, capture_output=True, timeout=10)
        assert ran.returncode == 0, (ran.stdout, ran.stderr)
        glsl.append({p.name: p.read_bytes() for p in run_dir.glob('q.*')})
        dump = tmp_path / (label + '_msl')
        dump.mkdir()
        with monkeypatch.context() as mode:
            mode.setenv('DEWY_MSL_DUMP', str(dump))
            mac = build_all(binary, tmp_path, label + '_metal', paths,
                            flags=(('--target', 'aarch64-mac'),))
        metal.append({p.name: p.read_bytes() for p in dump.glob('*.metal')})
        assert all(r[2] == 0 for r in native + mac)
        results.append(native + mac)
    assert results[0] == results[1]
    assert glsl[0] == glsl[1] and set(glsl[0]) == {'q.vert', 'q.frag'}
    assert metal[0] == metal[1] and len(metal[0]) >= 2
