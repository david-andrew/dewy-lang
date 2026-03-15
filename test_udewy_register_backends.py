from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory

import pytest

from udewy import p0, t1
from udewy.backend import get_backend, Backend


TARGETS = ["x86_64", "riscv", "arm"]


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
        (DIRECT_OVERFLOW_SOURCE, 55),
        (INDIRECT_OVERFLOW_SOURCE, 55),
        (SPILL_SOURCE, 78),
    ],
)
@pytest.mark.parametrize("target", TARGETS)
def test_register_backends_run_overflow_calls(target: str, source: str, expected_exit: int) -> None:
    if not toolchain_available(target):
        pytest.skip(f"{target} toolchain not available")

    backend = get_backend(target)
    code = parse_udewy(source, backend)

    with TemporaryDirectory() as tmp_dir:
        output_path = backend.compile_and_link(code, "overflow", Path(tmp_dir))
        exit_code = backend.run(output_path, [])

    assert exit_code == expected_exit
