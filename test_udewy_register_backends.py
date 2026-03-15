from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory

import pytest

from udewy import p0, t1
from udewy.backend import get_backend, Backend


TARGETS = ["x86_64", "riscv", "arm"]
MANY_LOCALS_COUNT = 200


DIRECT_OVERFLOW_SOURCE = """
let sum10 = (a:int b:int c:int d:int e:int f:int g:int h:int i:int j:int):>int => {
    return a + b + c + d + e + f + g + h + i + j
}

let main = ():>int => {
    return sum10(1 2 3 4 5 6 7 8 9 10)
}
"""


INDIRECT_OVERFLOW_SOURCE = """
let sum10 = (a:int b:int c:int d:int e:int f:int g:int h:int i:int j:int):>int => {
    return a + b + c + d + e + f + g + h + i + j
}

let main = ():>int => {
    let fn_ptr:int = sum10
    return (fn_ptr)(1 2 3 4 5 6 7 8 9 10)
}
"""


SPILL_SOURCE = """
let inc = (n:int):>int => {
    return n + 1
}

let sum12 = (a:int b:int c:int d:int e:int f:int g:int h:int i:int j:int k:int l:int):>int => {
    return a + b + c + d + e + f + g + h + i + j + k + l
}

let main = ():>int => {
    return sum12(
        inc(0)
        inc(1)
        inc(2)
        inc(3)
        inc(4)
        inc(5)
        inc(6)
        inc(7)
        inc(8)
        inc(9)
        inc(10)
        inc(11)
    )
}
"""

ALLOCA_ALIGNMENT_SOURCE = """
let main = ():>int => {
    let tmp2:int = __alloca__(1)
    let tmp3:int = __alloca__(1)
    return tmp2 - tmp3
}
"""


MANY_LOCALS_SOURCE = "\n".join(
    [
        "let main = ():>int => {",
        *[f"    let v{i}:int = {i}" for i in range(MANY_LOCALS_COUNT)],
        f"    return v0 + v{MANY_LOCALS_COUNT - 1}",
        "}",
    ]
)


DIRECT_EXPECTATIONS = {
    "x86_64": ["subq $32, %rsp", "movq %rax, 24(%rsp)", "movq %rax, 0(%rsp)", "movq 16(%rbp), %rax", "movq 40(%rbp), %rax"],
    "riscv": ["addi sp, sp, -16", "sd t0, 8(sp)", "sd t0, 0(sp)", "ld t0, 0(s0)", "ld t0, 8(s0)"],
    "arm": ["sub sp, sp, #16", "str x9, [sp, #8]", "str x9, [sp, #0]", "ldr x9, [x29, #96]", "ldr x9, [x29, #104]"],
}


INDIRECT_EXPECTATIONS = {
    "x86_64": ["movq %rax, 24(%rsp)", "call *%r11"],
    "riscv": ["sd t0, 8(sp)", "jalr ra, t5, 0"],
    "arm": ["str x9, [sp, #8]", "blr x9"],
}


SPILL_EXPECTATIONS = {
    "x86_64": ["movq %rax, %r12", "movq %rax, %r13", "movq %rax, %r14", "subq $16, %rsp", "movq %rax, (%rsp)"],
    "riscv": ["mv s2, a0", "mv s3, a0", "mv s4, a0", "addi sp, sp, -16", "sd a0, 0(sp)"],
    "arm": ["mov x20, x0", "mov x21, x0", "mov x22, x0", "mov x23, x0", "sub sp, sp, #16", "str x0, [sp]"],
}

ALLOCA_ALIGNMENT_EXPECTATIONS = {
    "x86_64": ["andq $-8, %rax", "subq %rax, %rsp"],
    "riscv": ["andi a0, a0, -16", "sub t0, sp, a0"],
    "arm": ["and x0, x0, #-16", "sub x9, sp, x0"],
}

ALLOCA_ALIGNMENT_RESULTS = {
    "x86_64": 8,
    "riscv": 16,
    "arm": 16,
}

MANY_LOCALS_EXPECTATIONS = {
    "x86_64": [f"subq $1648, %rsp", f"movq %rax, -1640(%rbp)", f"movq -1640(%rbp), %rax"],
    "riscv": [f"addi sp, sp, -1712", f"sd a0, -1704(s0)", f"ld a0, -1704(s0)"],
    "arm": [f"sub sp, sp, #1616", f"sub x9, x9, #1608", f"str x0, [x9]", f"ldr x0, [x9]"],
}


def parse_udewy(src: str, backend: Backend) -> str:
    toks = t1.tokenize(src)
    return p0.parse(toks, src, backend)


def toolchain_available(target: str) -> bool:
    if target == "x86_64":
        return which("as") is not None and which("ld") is not None
    if target == "riscv":
        return (
            any(which(f"{prefix}as") and which(f"{prefix}ld") for prefix in ["riscv64-linux-gnu-", "riscv64-elf-", "riscv64-unknown-elf-"])
            and which("qemu-riscv64") is not None
        )
    if target == "arm":
        return (
            any(which(f"{prefix}as") and which(f"{prefix}ld") for prefix in ["aarch64-linux-gnu-", "aarch64-elf-", "aarch64-unknown-elf-"])
            and which("qemu-aarch64") is not None
        )
    raise ValueError(f"unknown target {target}")


@pytest.mark.parametrize("target", TARGETS)
def test_direct_overflow_call_codegen(target: str) -> None:
    backend = get_backend(target)
    code = parse_udewy(DIRECT_OVERFLOW_SOURCE, backend)

    for expected in DIRECT_EXPECTATIONS[target]:
        assert expected in code


@pytest.mark.parametrize("target", TARGETS)
def test_indirect_overflow_call_codegen(target: str) -> None:
    backend = get_backend(target)
    code = parse_udewy(INDIRECT_OVERFLOW_SOURCE, backend)

    for expected in INDIRECT_EXPECTATIONS[target]:
        assert expected in code


@pytest.mark.parametrize("target", TARGETS)
def test_virtual_stack_cache_and_spill_codegen(target: str) -> None:
    backend = get_backend(target)
    code = parse_udewy(SPILL_SOURCE, backend)

    for expected in SPILL_EXPECTATIONS[target]:
        assert expected in code


@pytest.mark.parametrize("target", TARGETS)
def test_alloca_alignment_codegen(target: str) -> None:
    backend = get_backend(target)
    code = parse_udewy(ALLOCA_ALIGNMENT_SOURCE, backend)

    for expected in ALLOCA_ALIGNMENT_EXPECTATIONS[target]:
        assert expected in code


@pytest.mark.parametrize("target", TARGETS)
def test_fixed_frames_expand_for_many_locals(target: str) -> None:
    backend = get_backend(target)
    code = parse_udewy(MANY_LOCALS_SOURCE, backend)

    for expected in MANY_LOCALS_EXPECTATIONS[target]:
        assert expected in code


@pytest.mark.parametrize("target", TARGETS)
def test_syscall_intrinsic_arity_is_checked(target: str) -> None:
    src = """
let main = ():>int => {
    return __syscall3__(SYS_WRITE STDOUT 1)
}
"""

    with pytest.raises(SyntaxError, match=r"Intrinsic '__syscall3__' expects 4 arguments, got 3 arguments"):
        backend = get_backend(target)
        parse_udewy(src, backend)


@pytest.mark.parametrize(
    ("source", "expected_exit"),
    [
        (ALLOCA_ALIGNMENT_SOURCE, None),
        (DIRECT_OVERFLOW_SOURCE, 55),
        (INDIRECT_OVERFLOW_SOURCE, 55),
        (SPILL_SOURCE, 78),
        (MANY_LOCALS_SOURCE, 199),
    ],
)
@pytest.mark.parametrize("target", TARGETS)
def test_register_backends_run_overflow_calls(target: str, source: str, expected_exit: int | None) -> None:
    if not toolchain_available(target):
        pytest.skip(f"{target} toolchain not available")

    backend = get_backend(target)
    code = parse_udewy(source, backend)

    with TemporaryDirectory() as tmp_dir:
        output_path = backend.compile_and_link(code, "overflow", Path(tmp_dir))
        exit_code = backend.run(output_path, [])

    if expected_exit is None:
        assert exit_code == ALLOCA_ALIGNMENT_RESULTS[target]
    else:
        assert exit_code == expected_exit
