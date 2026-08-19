from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import builtins
from udewy.backend.arm import ArmBackend
from udewy.backend.c import CBackend
from udewy.backend.riscv import RiscvBackend
from udewy.backend.wasm import Wasm32Backend
from udewy.backend.x86_64 import X86_64Backend


def test_dewy_exposes_every_fixed_udewy_intrinsic() -> None:
    udewy_intrinsics = set().union(*(
        backend._INTRINSIC_ARITIES
        for backend in (
            X86_64Backend,
            ArmBackend,
            RiscvBackend,
            CBackend,
            Wasm32Backend,
        )
    ))

    assert udewy_intrinsics <= set(builtins.udewy_intrinsic_types)
    assert '__static_words__' in builtins.udewy_intrinsic_types


def test_float_bit_conversion_intrinsics_lower_directly() -> None:
    emitted = codegen(SrcFile(None, '''
let roundtrip = (value:int64):>int64 =>
    __f64_bits_to_i64__(__i64_to_f64_bits__(value))
'''))

    assert 'return __f64_bits_to_i64__(__i64_to_f64_bits__(value))' in emitted


def test_wasm_host_intrinsic_lowers_directly() -> None:
    emitted = codegen(SrcFile(None, '''
let write = (data:int64 length:int64):>int64 => __host_log__(data length)
'''))

    assert 'return __host_log__(data length)' in emitted
