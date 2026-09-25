# Encoder edge cases for the direct RISC-V object path, compared with
# llvm-mc (tests/python_misc/test_direct_riscv.py): `li` sequence shapes,
# conditional branches past +/-4 KiB (relaxed to an inverted branch over a
# `jal`), pseudo-instructions with swapped operands, local and external
# calls, float moves, and data relocations with addends.
    .text
f:
    li a0, 0
    li a0, 2047
    li a0, -2048
    li a0, 4096
    li a0, 0x7fffffff
    li a0, -2147483648
    li a0, 0x80000000
    li a0, 0xffffffff
    li a0, 0x123456789abcdef0
    li a0, -1
    li a0, 0x7fffffffffffffff
    li a0, -9223372036854775808
    li a0, 0x17ff
    beq a0, a1, far
    bnez a0, far
    ble a0, a1, near
    bgt a0, a1, far
near:
    j far
    jalr t0
    jalr ra, 8(t0)
    jal g
    call f
    tail h
    .zero 5000
    .zero 4
far:
    sgt a0, a1, a2
    sltu a0, a1, a2
    fmv.x.w a0, ft0
    fcvt.s.l fa0, a0
    fmv.d.x fa0, a0
    fmv.x.d a0, fa0
    fcvt.d.l fa1, a1
    lui a0, 0x12345
    srai a0, a0, 3
    sraw a0, a0, a1
    ret
    .data
d:
    .dword f, far+8, 5
    .word 1, 2
    .byte 1, 255
    .section .bss.x,"aw",@nobits
b:
    .zero 24
    .text
    la a0, b
    la a1, d+16
