"""The instruction sequence an assembler uses for RISC-V `li rd, imm` (RV64, no extensions).

This follows LLVM's RISCVMatInt (the sequence `llvm-mc` emits for the base
ISA with M, F and D), so a direct object matches the reference assembler's
instruction for instruction. Each step is (opcode, immediate), where the
opcode is 'lui', 'addi', 'addiw', 'slli', 'srli' or 'xori'; the first step
reads x0 unless it is `lui`. Mirrors the native materializer in
`udewy/bootstrap/backend/riscv_object.udewy`.
"""
from __future__ import annotations

MASK = (1 << 64) - 1


def _signed(value: int, bits: int = 64) -> int:
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >> (bits - 1) else value


def _fits(value: int, bits: int) -> bool:
    return -(1 << (bits - 1)) <= value < (1 << (bits - 1))


def _trailing_zeros(value: int) -> int:
    value &= MASK
    return (value & -value).bit_length() - 1 if value else 64


def _leading_zeros(value: int) -> int:
    return 64 - (value & MASK).bit_length()


def _impl(value: int, out: list[tuple[str, int]]) -> None:
    value = _signed(value)
    if _fits(value, 32):
        hi20 = ((value + 0x800) >> 12) & 0xFFFFF
        lo12 = _signed(value, 12)
        if hi20:
            out.append(('lui', hi20))
        if lo12 or hi20 == 0:
            # ADDIW only where ADDI would differ: when the sign-extended LUI
            # value plus the low bits leaves 32 bits.
            upper = _signed(hi20 << 12, 32)
            out.append(('addiw' if hi20 and not _fits(upper + lo12, 32) else 'addi', lo12))
        return
    lo12 = _signed(value, 12)
    value = _signed(value - lo12)
    shift = 0
    if not _fits(value, 32):
        shift = _trailing_zeros(value)
        value >>= shift
        if shift > 12 and not _fits(value, 12) and _fits(_signed(value << 12), 32):
            shift -= 12
            value = _signed(value << 12)
    _impl(value, out)
    if shift:
        out.append(('slli', shift))
    if lo12:
        out.append(('addi', lo12))


def _leading_zero_form(value: int, sequence: list[tuple[str, int]]) -> list[tuple[str, int]]:
    zeros = _leading_zeros(value)
    shifted = ((value << zeros) & MASK) | ((1 << zeros) - 1)
    trial: list[tuple[str, int]] = []
    _impl(shifted, trial)
    if len(trial) + 1 < len(sequence) or (not sequence and len(trial) < 8):
        trial.append(('srli', zeros))
        sequence = trial
    shifted &= ~((1 << zeros) - 1) & MASK
    trial = []
    _impl(shifted, trial)
    if len(trial) + 1 < len(sequence) or (not sequence and len(trial) < 8):
        trial.append(('srli', zeros))
        sequence = trial
    return sequence


def materialize(value: int) -> list[tuple[str, int]]:
    value = _signed(value)
    sequence: list[tuple[str, int]] = []
    _impl(value, sequence)
    # Trailing zeros with nonzero low bits: build the shifted constant and
    # restore the zeros with a final slli, if that is shorter.
    if value & 0xFFF and not value & 1 and len(sequence) >= 2:
        zeros = _trailing_zeros(value)
        shifted = value >> zeros
        trial: list[tuple[str, int]] = []
        _impl(shifted, trial)
        if len(trial) + 1 < len(sequence) or _fits(shifted, 6):
            trial.append(('slli', zeros))
            sequence = trial
    if len(sequence) <= 2:
        return sequence
    # Low 13 bits like 0x17ff: build value + 1 ... and add the difference back.
    if value & 0xFFF and (value & 0x1800) == 0x1000:
        imm12 = -(0x800 - (value & 0xFFF))
        trial = []
        _impl(value - imm12, trial)
        if len(trial) + 1 < len(sequence):
            trial.append(('addi', imm12))
            sequence = trial
    if value > 0 and len(sequence) > 2:
        sequence = _leading_zero_form(value, sequence)
    if value < 0 and len(sequence) > 3:
        trial = _leading_zero_form(~value & MASK, [])
        if trial and len(trial) + 1 < len(sequence):
            trial.append(('xori', -1))
            sequence = trial
    return sequence
