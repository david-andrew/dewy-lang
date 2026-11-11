"""The Dewy and frozen emitters agree on wide search exits and spilled results."""
import pytest

from tests.support import compiler  # noqa: F401
from tests import test_selfhost_x64_emit as emitter_tests


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_wide_search_emitter_twins(compiler, tmp_path, monkeypatch, release):  # noqa: F811
    # Reuse the emitter harness (COW, unwind state, code bytes), exercising the
    # AVX2 flag absent from its general opcode sweep. Keeping all results live
    # forces both register destinations and the saved-r11 spill path.
    driver = emitter_tests.DRIVER.split('main = ():', 1)[0] + '''main = ():
    f = IrFn(nparams=3, ret=0, vtypes=fill(i8(0), 28))
    loop wide in [0, 2]:
        f.code = []
        loop dst in [3..27):
            f.code.push(Ins(.findbyte, dst=i32(dst), a=0, b=1, c=2, imm=wide, pos=2))
        f.code.push(Ins(.mov, dst=27, a=3))
        loop src in [4..27):
            f.code.push(Ins(.add, dst=27, a=27, b=i32(src)))
        f.code.push(Ins(.ret, a=27, pos=3))
        loop windows in [false, true]:
            run(f, false, windows)
            run(f, true, windows)
    print("ok")
'''
    monkeypatch.setattr(emitter_tests, 'DRIVER', driver)
    emitter_tests.test_x64_emitter_twins(compiler, tmp_path, release)
