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


class ArmBackend(Backend):
    name = "arm"

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
            "    ldr x0, [sp]",
            "    add x1, sp, #8",
            "    bl __main__",
            "    mov x8, #93",
            "    svc #0",
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
        return -56 - (ref.slot * 8)

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
        self._emit("stp x29, x30, [sp, #-16]!")
        self._emit("mov x29, sp")
        self._emit("sub sp, sp, #1040")
        self._emit("str x19, [x29, #-8]")
        self._emit("str x20, [x29, #-16]")
        self._emit("str x21, [x29, #-24]")
        self._emit("str x22, [x29, #-32]")
        self._emit("str x23, [x29, #-40]")
        arg_regs = ["x0", "x1", "x2", "x3", "x4", "x5", "x6", "x7"]
        param_index = 0
        while param_index < param_count:
            offset = self._local_offset(LocalRef(param_index))
            if param_index < len(arg_regs):
                self._emit(f"stur {arg_regs[param_index]}, [x29, #{offset}]")
            param_index += 1
        self.current_epilogue = self._label(f"{fn.symbol}_epilogue")

    def register_local(self, ref: LocalRef, is_param: bool) -> None:
        _ = (ref, is_param)

    def end_function(self, fn: FnRef) -> None:
        _ = fn
        self._emit_label(self.current_epilogue)
        self._emit("ldr x19, [x29, #-8]")
        self._emit("ldr x20, [x29, #-16]")
        self._emit("ldr x21, [x29, #-24]")
        self._emit("ldr x22, [x29, #-32]")
        self._emit("ldr x23, [x29, #-40]")
        self._emit("add sp, sp, #1040")
        self._emit("ldp x29, x30, [sp], #16")
        self._emit("ret")

    def push_const_i64(self, value: int) -> None:
        self._emit(f"ldr x9, ={value}")
        self._emit("sub sp, sp, #16")
        self._emit("str x9, [sp]")

    def push_void(self) -> None:
        self.push_const_i64(0)

    def push_local(self, ref: LocalRef) -> None:
        self._emit(f"ldur x9, [x29, #{self._local_offset(ref)}]")
        self._emit("sub sp, sp, #16")
        self._emit("str x9, [sp]")

    def store_local(self, ref: LocalRef) -> None:
        self._emit("ldr x9, [sp]")
        self._emit("add sp, sp, #16")
        self._emit(f"stur x9, [x29, #{self._local_offset(ref)}]")

    def _global_addr(self, ref: GlobalRef) -> None:
        self._emit(f"adrp x9, {self._label(ref.symbol)}")
        self._emit(f"add x9, x9, :lo12:{self._label(ref.symbol)}")

    def push_global(self, ref: GlobalRef) -> None:
        self._global_addr(ref)
        self._emit("ldr x9, [x9]")
        self._emit("sub sp, sp, #16")
        self._emit("str x9, [sp]")

    def store_global(self, ref: GlobalRef) -> None:
        self._emit("ldr x10, [sp]")
        self._emit("add sp, sp, #16")
        self._global_addr(ref)
        self._emit("str x10, [x9]")

    def push_fn_ref(self, ref: FnRef) -> None:
        self._emit(f"adrp x9, {self._label(ref.symbol)}")
        self._emit(f"add x9, x9, :lo12:{self._label(ref.symbol)}")
        self._emit("sub sp, sp, #16")
        self._emit("str x9, [sp]")

    def push_data_ref(self, ref: DataRef) -> None:
        self._emit(f"adrp x9, {self._label(ref.symbol)}")
        self._emit(f"add x9, x9, :lo12:{self._label(ref.symbol)}")
        if ref.offset:
            self._emit(f"add x9, x9, #{ref.offset}")
        self._emit("sub sp, sp, #16")
        self._emit("str x9, [sp]")

    def unary_not(self) -> None:
        self._emit("ldr x9, [sp]")
        self._emit("mvn x9, x9")
        self._emit("str x9, [sp]")

    def unary_neg(self) -> None:
        self._emit("ldr x9, [sp]")
        self._emit("neg x9, x9")
        self._emit("str x9, [sp]")

    def _pop2(self) -> None:
        self._emit("ldr x10, [sp]")
        self._emit("add sp, sp, #16")
        self._emit("ldr x9, [sp]")
        self._emit("add sp, sp, #16")

    def _push_x9(self) -> None:
        self._emit("sub sp, sp, #16")
        self._emit("str x9, [sp]")

    def binary_add(self) -> None:
        self._pop2()
        self._emit("add x9, x9, x10")
        self._push_x9()

    def binary_sub(self) -> None:
        self._pop2()
        self._emit("sub x9, x9, x10")
        self._push_x9()

    def binary_mul(self) -> None:
        self._pop2()
        self._emit("mul x9, x9, x10")
        self._push_x9()

    def binary_idiv(self) -> None:
        self._pop2()
        self._emit("sdiv x9, x9, x10")
        self._push_x9()

    def binary_mod(self) -> None:
        self._pop2()
        self._emit("sdiv x11, x9, x10")
        self._emit("msub x9, x11, x10, x9")
        self._push_x9()

    def binary_shl(self) -> None:
        self._pop2()
        self._emit("lsl x9, x9, x10")
        self._push_x9()

    def binary_shr(self) -> None:
        self._pop2()
        self._emit("asr x9, x9, x10")
        self._push_x9()

    def binary_and(self) -> None:
        self._pop2()
        self._emit("and x9, x9, x10")
        self._push_x9()

    def binary_or(self) -> None:
        self._pop2()
        self._emit("orr x9, x9, x10")
        self._push_x9()

    def binary_xor(self) -> None:
        self._pop2()
        self._emit("eor x9, x9, x10")
        self._push_x9()

    def _cmp(self, cond: str) -> None:
        self._pop2()
        self._emit("cmp x9, x10")
        self._emit(f"cset w9, {cond}")
        self._emit("neg x9, x9")
        self._push_x9()

    def binary_eq(self) -> None:
        self._cmp("eq")

    def binary_ne(self) -> None:
        self._cmp("ne")

    def binary_gt(self) -> None:
        self._cmp("gt")

    def binary_lt(self) -> None:
        self._cmp("lt")

    def binary_ge(self) -> None:
        self._cmp("ge")

    def binary_le(self) -> None:
        self._cmp("le")

    def call_direct(self, ref: FnRef, argc: int) -> None:
        regs = ["x0", "x1", "x2", "x3", "x4", "x5", "x6", "x7"]
        arg_index = argc - 1
        while arg_index >= 0:
            if arg_index < len(regs):
                self._emit(f"ldr {regs[arg_index]}, [sp]")
                self._emit("add sp, sp, #16")
            arg_index -= 1
        self._emit(f"bl {self._label(ref.symbol)}")
        self._emit("sub sp, sp, #16")
        self._emit("str x0, [sp]")

    def call_indirect(self, argc: int) -> None:
        regs = ["x0", "x1", "x2", "x3", "x4", "x5", "x6", "x7"]
        arg_index = argc - 1
        while arg_index >= 0:
            if arg_index < len(regs):
                self._emit(f"ldr {regs[arg_index]}, [sp]")
                self._emit("add sp, sp, #16")
            arg_index -= 1
        self._emit("ldr x9, [sp]")
        self._emit("add sp, sp, #16")
        self._emit("blr x9")
        self._emit("sub sp, sp, #16")
        self._emit("str x0, [sp]")

    def call_pipe(self) -> None:
        self._emit("ldr x9, [sp]")
        self._emit("add sp, sp, #16")
        self._emit("ldr x0, [sp]")
        self._emit("add sp, sp, #16")
        self._emit("blr x9")
        self._emit("sub sp, sp, #16")
        self._emit("str x0, [sp]")

    def call_intrinsic(self, name: str, argc: int) -> None:
        _ = argc
        if name == "__load__":
            self._emit("ldr x9, [sp]")
            self._emit("ldr x9, [x9]")
            self._emit("str x9, [sp]")
            return
        if name == "__store__":
            self._emit("ldr x9, [sp]")
            self._emit("add sp, sp, #16")
            self._emit("ldr x10, [sp]")
            self._emit("str x10, [x9]")
            self._emit("mov x9, #0")
            self._emit("str x9, [sp]")
            return
        if name == "__load8__":
            self._emit("ldr x9, [sp]")
            self._emit("ldrb w9, [x9]")
            self._emit("str x9, [sp]")
            return
        if name == "__store8__":
            self._emit("ldr x9, [sp]")
            self._emit("add sp, sp, #16")
            self._emit("ldr x10, [sp]")
            self._emit("strb w10, [x9]")
            self._emit("mov x9, #0")
            self._emit("str x9, [sp]")
            return
        if name == "__load16__":
            self._emit("ldr x9, [sp]")
            self._emit("ldrh w9, [x9]")
            self._emit("str x9, [sp]")
            return
        if name == "__store16__":
            self._emit("ldr x9, [sp]")
            self._emit("add sp, sp, #16")
            self._emit("ldr x10, [sp]")
            self._emit("strh w10, [x9]")
            self._emit("mov x9, #0")
            self._emit("str x9, [sp]")
            return
        if name == "__load32__":
            self._emit("ldr x9, [sp]")
            self._emit("ldr w9, [x9]")
            self._emit("str x9, [sp]")
            return
        if name == "__store32__":
            self._emit("ldr x9, [sp]")
            self._emit("add sp, sp, #16")
            self._emit("ldr x10, [sp]")
            self._emit("str w10, [x9]")
            self._emit("mov x9, #0")
            self._emit("str x9, [sp]")
            return
        if name.startswith("__syscall"):
            argc = int(name[len("__syscall"):len("__syscall") + 1])
            regs = ["x0", "x1", "x2", "x3", "x4", "x5"]
            arg_index = argc - 1
            while arg_index >= 1:
                self._emit(f"ldr {regs[arg_index - 1]}, [sp]")
                self._emit("add sp, sp, #16")
                arg_index -= 1
            self._emit("ldr x8, [sp]")
            self._emit("add sp, sp, #16")
            self._emit("svc #0")
            self._emit("sub sp, sp, #16")
            self._emit("str x0, [sp]")
            return
        raise SyntaxError(f"Unsupported intrinsic for arm: {name}")

    def begin_if(self, token: str) -> IfState:
        return IfState(token)

    def if_condition(self, state: IfState) -> None:
        self._emit("ldr x9, [sp]")
        self._emit("add sp, sp, #16")
        self._emit("cbz x9, " + self._label(state.token + "_else"))

    def begin_else(self, state: IfState) -> None:
        state.has_else = True
        self._emit("b " + self._label(state.token + "_end"))
        self._emit_label(self._label(state.token + "_else"))

    def end_if(self, state: IfState) -> None:
        if not state.has_else:
            self._emit_label(self._label(state.token + "_else"))
        self._emit_label(self._label(state.token + "_end"))

    def begin_loop(self, token: str) -> LoopState:
        self._emit_label(self._label(token + "_start"))
        return LoopState(token)

    def loop_condition(self, state: LoopState) -> None:
        self._emit("ldr x9, [sp]")
        self._emit("add sp, sp, #16")
        self._emit("cbz x9, " + self._label(state.token + "_end"))

    def end_loop(self, state: LoopState) -> None:
        self._emit("b " + self._label(state.token + "_start"))
        self._emit_label(self._label(state.token + "_end"))

    def emit_break(self, state: LoopState) -> None:
        self._emit("b " + self._label(state.token + "_end"))

    def emit_continue(self, state: LoopState) -> None:
        self._emit("b " + self._label(state.token + "_start"))

    def emit_return(self) -> None:
        self._emit("ldr x0, [sp]")
        self._emit("add sp, sp, #16")
        self._emit("b " + self.current_epilogue)

    def emit_expr_discard(self) -> None:
        self._emit("add sp, sp, #16")

    def build(self, module_text: str, input_file: PathLike, cache_dir: PathLike) -> BuildResult:
        input_file = Path(input_file)
        cache_dir = ensure_cache_dir(cache_dir)
        asm_path = cache_dir / f"{input_file.stem}.arm64.s"
        obj_path = cache_dir / f"{input_file.stem}.arm64.o"
        exe_path = cache_dir / f"{input_file.stem}.arm64"
        asm_path.write_text(module_text)
        assembler = shutil.which("aarch64-linux-gnu-as")
        linker = shutil.which("aarch64-linux-gnu-ld")
        if assembler is None or linker is None:
            return BuildResult(asm_path)
        subprocess.run([assembler, str(asm_path), "-o", str(obj_path)], check=True)
        subprocess.run([linker, str(obj_path), "-o", str(exe_path)], check=True)
        return BuildResult(exe_path, (asm_path, obj_path))

    def run(self, build_result: BuildResult, argv: list[str], cwd: PathLike) -> int:
        runner = shutil.which("qemu-aarch64")
        if runner is None or build_result.artifact_path.suffix == ".s":
            raise RuntimeError("Running arm artifacts requires qemu-aarch64 and cross-binutils")
        result = subprocess.run([runner, str(build_result.artifact_path)] + argv, cwd=Path(cwd))
        return result.returncode

