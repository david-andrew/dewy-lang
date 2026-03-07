from __future__ import annotations

import shutil
import subprocess
from os import PathLike
from pathlib import Path

from .common import (
    Backend,
    BuildResult,
    DataRef,
    DataRefValue,
    DataValue,
    FnDataValue,
    FnRef,
    GlobalRef,
    IfState,
    IntDataValue,
    LocalRef,
    LoopState,
    ensure_cache_dir,
)


class RiscvBackend(Backend):
    name = "riscv"

    def __init__(self) -> None:
        self.code: list[str] = []
        self.data: list[str] = []
        self.current_epilogue: str = ""

    def begin_module(self) -> None:
        self.code = []
        self.data = []
        self.current_epilogue = ""

    def finish_module(self) -> str:
        output = [
            ".text",
            ".globl _start",
            ".globl __main__",
            "",
            "_start:",
            "    ld a0, 0(sp)",
            "    addi a1, sp, 8",
            "    call __main__",
            "    mv a0, a0",
            "    li a7, 93",
            "    ecall",
            "",
        ]
        output.extend(self.code)
        output.extend(["", ".data"])
        output.extend(self.data)
        output.append("")
        return "\n".join(output)

    def _emit(self, instr: str) -> None:
        self.code.append(f"    {instr}")

    def _emit_label(self, label: str) -> None:
        self.code.append(f"{label}:")

    def _emit_data(self, directive: str) -> None:
        self.data.append(directive)

    def _emit_data_label(self, label: str) -> None:
        self.data.append(f"{label}:")

    def _label(self, symbol: str) -> str:
        return f".L{symbol}"

    def _local_offset(self, ref: LocalRef) -> int:
        return -48 - (ref.slot * 8)

    def note_function(self, fn: FnRef) -> None:
        _ = fn

    def define_global_int(self, ref: GlobalRef, value: int) -> None:
        self._emit_data_label(self._label(ref.symbol))
        self._emit_data(f"    .quad {value}")

    def define_global_data(self, ref: GlobalRef, data_ref: DataRef) -> None:
        self._emit_data_label(self._label(ref.symbol))
        self._emit_data(f"    .quad {self._label(data_ref.symbol)}+{data_ref.offset}")

    def intern_string(self, symbol: str, values: list[int]) -> DataRef:
        self._emit_data_label(self._label(symbol))
        self._emit_data(f"    .quad {len(values)}")
        if values:
            self._emit_data("    .byte " + ", ".join(str(value) for value in values))
        return DataRef(symbol, 8)

    def intern_array(self, symbol: str, values: list[DataValue]) -> DataRef:
        self._emit_data_label(self._label(symbol))
        self._emit_data(f"    .quad {len(values)}")
        for value in values:
            if isinstance(value, IntDataValue):
                self._emit_data(f"    .quad {value.value}")
            elif isinstance(value, FnDataValue):
                self._emit_data(f"    .quad {self._label(value.fn.symbol)}")
            elif isinstance(value, DataRefValue):
                self._emit_data(f"    .quad {self._label(value.ref.symbol)}+{value.ref.offset}")
        return DataRef(symbol, 8)

    def begin_function(self, fn: FnRef, param_count: int, is_main: bool) -> None:
        label = self._label(fn.symbol)
        if is_main:
            self._emit_label("__main__")
        self._emit_label(label)
        self._emit("addi sp, sp, -1040")
        self._emit("sd ra, 1032(sp)")
        self._emit("sd s0, 1024(sp)")
        self._emit("sd s1, 1016(sp)")
        self._emit("sd s2, 1008(sp)")
        self._emit("sd s3, 1000(sp)")
        self._emit("sd s4, 992(sp)")
        self._emit("addi s0, sp, 1040")
        arg_regs = ["a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7"]
        param_index = 0
        while param_index < param_count:
            offset = self._local_offset(LocalRef(param_index))
            if param_index < len(arg_regs):
                self._emit(f"sd {arg_regs[param_index]}, {offset}(s0)")
            param_index += 1
        self.current_epilogue = self._label(f"{fn.symbol}_epilogue")

    def register_local(self, ref: LocalRef, is_param: bool) -> None:
        _ = (ref, is_param)

    def end_function(self, fn: FnRef) -> None:
        _ = fn
        self._emit_label(self.current_epilogue)
        self._emit("ld ra, 1032(sp)")
        self._emit("ld s0, 1024(sp)")
        self._emit("ld s1, 1016(sp)")
        self._emit("ld s2, 1008(sp)")
        self._emit("ld s3, 1000(sp)")
        self._emit("ld s4, 992(sp)")
        self._emit("addi sp, sp, 1040")
        self._emit("ret")

    def push_const_i64(self, value: int) -> None:
        self._emit(f"li t0, {value}")
        self._emit("addi sp, sp, -8")
        self._emit("sd t0, 0(sp)")

    def push_void(self) -> None:
        self.push_const_i64(0)

    def push_local(self, ref: LocalRef) -> None:
        self._emit(f"ld t0, {self._local_offset(ref)}(s0)")
        self._emit("addi sp, sp, -8")
        self._emit("sd t0, 0(sp)")

    def store_local(self, ref: LocalRef) -> None:
        self._emit("ld t0, 0(sp)")
        self._emit("addi sp, sp, 8")
        self._emit(f"sd t0, {self._local_offset(ref)}(s0)")

    def push_global(self, ref: GlobalRef) -> None:
        self._emit(f"la t0, {self._label(ref.symbol)}")
        self._emit("ld t0, 0(t0)")
        self._emit("addi sp, sp, -8")
        self._emit("sd t0, 0(sp)")

    def store_global(self, ref: GlobalRef) -> None:
        self._emit("ld t1, 0(sp)")
        self._emit("addi sp, sp, 8")
        self._emit(f"la t0, {self._label(ref.symbol)}")
        self._emit("sd t1, 0(t0)")

    def push_fn_ref(self, ref: FnRef) -> None:
        self._emit(f"la t0, {self._label(ref.symbol)}")
        self._emit("addi sp, sp, -8")
        self._emit("sd t0, 0(sp)")

    def push_data_ref(self, ref: DataRef) -> None:
        self._emit(f"la t0, {self._label(ref.symbol)}")
        if ref.offset:
            self._emit(f"addi t0, t0, {ref.offset}")
        self._emit("addi sp, sp, -8")
        self._emit("sd t0, 0(sp)")

    def unary_not(self) -> None:
        self._emit("ld t0, 0(sp)")
        self._emit("not t0, t0")
        self._emit("sd t0, 0(sp)")

    def unary_neg(self) -> None:
        self._emit("ld t0, 0(sp)")
        self._emit("neg t0, t0")
        self._emit("sd t0, 0(sp)")

    def _pop2(self) -> None:
        self._emit("ld t1, 0(sp)")
        self._emit("addi sp, sp, 8")
        self._emit("ld t0, 0(sp)")
        self._emit("addi sp, sp, 8")

    def _push_t0(self) -> None:
        self._emit("addi sp, sp, -8")
        self._emit("sd t0, 0(sp)")

    def binary_add(self) -> None:
        self._pop2()
        self._emit("add t0, t0, t1")
        self._push_t0()

    def binary_sub(self) -> None:
        self._pop2()
        self._emit("sub t0, t0, t1")
        self._push_t0()

    def binary_mul(self) -> None:
        self._pop2()
        self._emit("mul t0, t0, t1")
        self._push_t0()

    def binary_idiv(self) -> None:
        self._pop2()
        self._emit("div t0, t0, t1")
        self._push_t0()

    def binary_mod(self) -> None:
        self._pop2()
        self._emit("rem t0, t0, t1")
        self._push_t0()

    def binary_shl(self) -> None:
        self._pop2()
        self._emit("sll t0, t0, t1")
        self._push_t0()

    def binary_shr(self) -> None:
        self._pop2()
        self._emit("sra t0, t0, t1")
        self._push_t0()

    def binary_and(self) -> None:
        self._pop2()
        self._emit("and t0, t0, t1")
        self._push_t0()

    def binary_or(self) -> None:
        self._pop2()
        self._emit("or t0, t0, t1")
        self._push_t0()

    def binary_xor(self) -> None:
        self._pop2()
        self._emit("xor t0, t0, t1")
        self._push_t0()

    def _cmp(self, instr: str) -> None:
        self._pop2()
        self._emit(f"{instr} t0, t0, t1")
        self._emit("neg t0, t0")
        self._push_t0()

    def binary_eq(self) -> None:
        self._pop2()
        self._emit("xor t0, t0, t1")
        self._emit("seqz t0, t0")
        self._emit("neg t0, t0")
        self._push_t0()

    def binary_ne(self) -> None:
        self._pop2()
        self._emit("xor t0, t0, t1")
        self._emit("snez t0, t0")
        self._emit("neg t0, t0")
        self._push_t0()

    def binary_gt(self) -> None:
        self._cmp("sgt")

    def binary_lt(self) -> None:
        self._cmp("slt")

    def binary_ge(self) -> None:
        self._pop2()
        self._emit("slt t0, t0, t1")
        self._emit("xori t0, t0, 1")
        self._emit("neg t0, t0")
        self._push_t0()

    def binary_le(self) -> None:
        self._pop2()
        self._emit("sgt t0, t0, t1")
        self._emit("xori t0, t0, 1")
        self._emit("neg t0, t0")
        self._push_t0()

    def call_direct(self, ref: FnRef, argc: int) -> None:
        regs = ["a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7"]
        arg_index = argc - 1
        while arg_index >= 0:
            if arg_index < len(regs):
                self._emit(f"ld {regs[arg_index]}, 0(sp)")
                self._emit("addi sp, sp, 8")
            arg_index -= 1
        self._emit(f"call {self._label(ref.symbol)}")
        self._emit("addi sp, sp, -8")
        self._emit("sd a0, 0(sp)")

    def call_indirect(self, argc: int) -> None:
        regs = ["a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7"]
        arg_index = argc - 1
        while arg_index >= 0:
            if arg_index < len(regs):
                self._emit(f"ld {regs[arg_index]}, 0(sp)")
                self._emit("addi sp, sp, 8")
            arg_index -= 1
        self._emit("ld t0, 0(sp)")
        self._emit("addi sp, sp, 8")
        self._emit("jalr ra, 0(t0)")
        self._emit("addi sp, sp, -8")
        self._emit("sd a0, 0(sp)")

    def call_pipe(self) -> None:
        self._emit("ld t0, 0(sp)")
        self._emit("addi sp, sp, 8")
        self._emit("ld a0, 0(sp)")
        self._emit("addi sp, sp, 8")
        self._emit("jalr ra, 0(t0)")
        self._emit("addi sp, sp, -8")
        self._emit("sd a0, 0(sp)")

    def call_intrinsic(self, name: str, argc: int) -> None:
        _ = argc
        if name == "__load__":
            self._emit("ld t0, 0(sp)")
            self._emit("ld t0, 0(t0)")
            self._emit("sd t0, 0(sp)")
            return
        if name == "__store__":
            self._emit("ld t0, 0(sp)")
            self._emit("addi sp, sp, 8")
            self._emit("ld t1, 0(sp)")
            self._emit("sd t1, 0(t0)")
            self._emit("li t0, 0")
            self._emit("sd t0, 0(sp)")
            return
        if name == "__load8__":
            self._emit("ld t0, 0(sp)")
            self._emit("lbu t0, 0(t0)")
            self._emit("sd t0, 0(sp)")
            return
        if name == "__store8__":
            self._emit("ld t0, 0(sp)")
            self._emit("addi sp, sp, 8")
            self._emit("ld t1, 0(sp)")
            self._emit("sb t1, 0(t0)")
            self._emit("li t0, 0")
            self._emit("sd t0, 0(sp)")
            return
        if name == "__load16__":
            self._emit("ld t0, 0(sp)")
            self._emit("lhu t0, 0(t0)")
            self._emit("sd t0, 0(sp)")
            return
        if name == "__store16__":
            self._emit("ld t0, 0(sp)")
            self._emit("addi sp, sp, 8")
            self._emit("ld t1, 0(sp)")
            self._emit("sh t1, 0(t0)")
            self._emit("li t0, 0")
            self._emit("sd t0, 0(sp)")
            return
        if name == "__load32__":
            self._emit("ld t0, 0(sp)")
            self._emit("lwu t0, 0(t0)")
            self._emit("sd t0, 0(sp)")
            return
        if name == "__store32__":
            self._emit("ld t0, 0(sp)")
            self._emit("addi sp, sp, 8")
            self._emit("ld t1, 0(sp)")
            self._emit("sw t1, 0(t0)")
            self._emit("li t0, 0")
            self._emit("sd t0, 0(sp)")
            return
        if name.startswith("__syscall"):
            argc = int(name[len("__syscall"):len("__syscall") + 1])
            regs = ["a0", "a1", "a2", "a3", "a4", "a5"]
            arg_index = argc - 1
            while arg_index >= 1:
                self._emit(f"ld {regs[arg_index - 1]}, 0(sp)")
                self._emit("addi sp, sp, 8")
                arg_index -= 1
            self._emit("ld a7, 0(sp)")
            self._emit("addi sp, sp, 8")
            self._emit("ecall")
            self._emit("addi sp, sp, -8")
            self._emit("sd a0, 0(sp)")
            return
        raise SyntaxError(f"Unsupported intrinsic for riscv: {name}")

    def begin_if(self, token: str) -> IfState:
        return IfState(token)

    def if_condition(self, state: IfState) -> None:
        self._emit("ld t0, 0(sp)")
        self._emit("addi sp, sp, 8")
        self._emit(f"beqz t0, {self._label(state.token + '_else')}")

    def begin_else(self, state: IfState) -> None:
        state.has_else = True
        self._emit(f"j {self._label(state.token + '_end')}")
        self._emit_label(self._label(state.token + "_else"))

    def end_if(self, state: IfState) -> None:
        if not state.has_else:
            self._emit_label(self._label(state.token + "_else"))
        self._emit_label(self._label(state.token + "_end"))

    def begin_loop(self, token: str) -> LoopState:
        self._emit_label(self._label(token + "_start"))
        return LoopState(token)

    def loop_condition(self, state: LoopState) -> None:
        self._emit("ld t0, 0(sp)")
        self._emit("addi sp, sp, 8")
        self._emit(f"beqz t0, {self._label(state.token + '_end')}")

    def end_loop(self, state: LoopState) -> None:
        self._emit(f"j {self._label(state.token + '_start')}")
        self._emit_label(self._label(state.token + "_end"))

    def emit_break(self, state: LoopState) -> None:
        self._emit(f"j {self._label(state.token + '_end')}")

    def emit_continue(self, state: LoopState) -> None:
        self._emit(f"j {self._label(state.token + '_start')}")

    def emit_return(self) -> None:
        self._emit("ld a0, 0(sp)")
        self._emit("addi sp, sp, 8")
        self._emit(f"j {self.current_epilogue}")

    def emit_expr_discard(self) -> None:
        self._emit("addi sp, sp, 8")

    def build(self, module_text: str, input_file: PathLike, cache_dir: PathLike) -> BuildResult:
        input_file = Path(input_file)
        cache_dir = ensure_cache_dir(cache_dir)
        asm_path = cache_dir / f"{input_file.stem}.riscv.s"
        obj_path = cache_dir / f"{input_file.stem}.riscv.o"
        exe_path = cache_dir / f"{input_file.stem}.riscv"
        asm_path.write_text(module_text)
        assembler = shutil.which("riscv64-linux-gnu-as")
        linker = shutil.which("riscv64-linux-gnu-ld")
        if assembler is None or linker is None:
            return BuildResult(asm_path)
        subprocess.run([assembler, str(asm_path), "-o", str(obj_path)], check=True)
        subprocess.run([linker, str(obj_path), "-o", str(exe_path)], check=True)
        return BuildResult(exe_path, (asm_path, obj_path))

    def run(self, build_result: BuildResult, argv: list[str], cwd: PathLike) -> int:
        runner = shutil.which("qemu-riscv64")
        if runner is None or build_result.artifact_path.suffix == ".s":
            raise RuntimeError("Running riscv artifacts requires qemu-riscv64 and cross-binutils")
        result = subprocess.run([runner, str(build_result.artifact_path)] + argv, cwd=Path(cwd))
        return result.returncode

