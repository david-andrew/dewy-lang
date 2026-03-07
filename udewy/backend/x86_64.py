from __future__ import annotations

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


class X86_64Backend(Backend):
    name = "x86_64"

    def __init__(self) -> None:
        self.code: list[str] = []
        self.data: list[str] = []
        self.current_epilogue: str = ""

    def begin_module(self) -> None:
        self.code = []
        self.data = []
        self.current_epilogue = ""

    def finish_module(self) -> str:
        output = [".text", ".globl __main__", ""]
        output.extend(self.code)
        output.extend(["", ".data"])
        output.extend(self.data)
        output.extend(["", '.section .note.GNU-stack,"",@progbits', ""])
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
            joined = ", ".join(str(value) for value in values)
            self._emit_data(f"    .byte {joined}")
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
            else:
                raise TypeError(f"Unsupported data value: {value!r}")
        return DataRef(symbol, 8)

    def begin_function(self, fn: FnRef, param_count: int, is_main: bool) -> None:
        label = self._label(fn.symbol)
        if is_main:
            self._emit_label("__main__")
        self._emit_label(label)
        self._emit("pushq %rbp")
        self._emit("movq %rsp, %rbp")
        self._emit("subq $1024, %rsp")
        self._emit("movq %rbx, -8(%rbp)")
        self._emit("movq %r12, -16(%rbp)")
        self._emit("movq %r13, -24(%rbp)")
        self._emit("movq %r14, -32(%rbp)")
        self._emit("movq %r15, -40(%rbp)")
        arg_regs = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
        param_index = 0
        while param_index < param_count:
            ref = LocalRef(param_index)
            offset = self._local_offset(ref)
            if param_index < len(arg_regs):
                self._emit(f"movq {arg_regs[param_index]}, {offset}(%rbp)")
            else:
                caller_offset = 16 + ((param_index - len(arg_regs)) * 8)
                self._emit(f"movq {caller_offset}(%rbp), %rax")
                self._emit(f"movq %rax, {offset}(%rbp)")
            param_index += 1
        self.current_epilogue = self._label(f"{fn.symbol}_epilogue")

    def register_local(self, ref: LocalRef, is_param: bool) -> None:
        _ = (ref, is_param)

    def end_function(self, fn: FnRef) -> None:
        _ = fn
        self._emit_label(self.current_epilogue)
        self._emit("movq -8(%rbp), %rbx")
        self._emit("movq -16(%rbp), %r12")
        self._emit("movq -24(%rbp), %r13")
        self._emit("movq -32(%rbp), %r14")
        self._emit("movq -40(%rbp), %r15")
        self._emit("movq %rbp, %rsp")
        self._emit("popq %rbp")
        self._emit("ret")
        self.current_epilogue = ""

    def push_const_i64(self, value: int) -> None:
        self._emit(f"movq ${value}, %rax")
        self._emit("pushq %rax")

    def push_void(self) -> None:
        self._emit("xorq %rax, %rax")
        self._emit("pushq %rax")

    def push_local(self, ref: LocalRef) -> None:
        offset = self._local_offset(ref)
        self._emit(f"movq {offset}(%rbp), %rax")
        self._emit("pushq %rax")

    def store_local(self, ref: LocalRef) -> None:
        offset = self._local_offset(ref)
        self._emit("popq %rax")
        self._emit(f"movq %rax, {offset}(%rbp)")

    def push_global(self, ref: GlobalRef) -> None:
        self._emit(f"movq {self._label(ref.symbol)}(%rip), %rax")
        self._emit("pushq %rax")

    def store_global(self, ref: GlobalRef) -> None:
        self._emit("popq %rax")
        self._emit(f"movq %rax, {self._label(ref.symbol)}(%rip)")

    def push_fn_ref(self, ref: FnRef) -> None:
        self._emit(f"leaq {self._label(ref.symbol)}(%rip), %rax")
        self._emit("pushq %rax")

    def push_data_ref(self, ref: DataRef) -> None:
        self._emit(f"leaq {self._label(ref.symbol)}+{ref.offset}(%rip), %rax")
        self._emit("pushq %rax")

    def unary_not(self) -> None:
        self._emit("popq %rax")
        self._emit("notq %rax")
        self._emit("pushq %rax")

    def unary_neg(self) -> None:
        self._emit("popq %rax")
        self._emit("negq %rax")
        self._emit("pushq %rax")

    def _binary(self, instr: str) -> None:
        self._emit("popq %rcx")
        self._emit("popq %rax")
        self._emit(instr)
        self._emit("pushq %rax")

    def binary_add(self) -> None:
        self._binary("addq %rcx, %rax")

    def binary_sub(self) -> None:
        self._binary("subq %rcx, %rax")

    def binary_mul(self) -> None:
        self._binary("imulq %rcx, %rax")

    def binary_idiv(self) -> None:
        self._emit("popq %rcx")
        self._emit("popq %rax")
        self._emit("cqto")
        self._emit("idivq %rcx")
        self._emit("pushq %rax")

    def binary_mod(self) -> None:
        self._emit("popq %rcx")
        self._emit("popq %rax")
        self._emit("cqto")
        self._emit("idivq %rcx")
        self._emit("pushq %rdx")

    def binary_shl(self) -> None:
        self._binary("shlq %cl, %rax")

    def binary_shr(self) -> None:
        self._binary("sarq %cl, %rax")

    def binary_and(self) -> None:
        self._binary("andq %rcx, %rax")

    def binary_or(self) -> None:
        self._binary("orq %rcx, %rax")

    def binary_xor(self) -> None:
        self._binary("xorq %rcx, %rax")

    def _compare(self, set_instr: str) -> None:
        self._emit("popq %rcx")
        self._emit("popq %rax")
        self._emit("cmpq %rcx, %rax")
        self._emit(f"{set_instr} %al")
        self._emit("movzbq %al, %rax")
        self._emit("negq %rax")
        self._emit("pushq %rax")

    def binary_eq(self) -> None:
        self._compare("sete")

    def binary_ne(self) -> None:
        self._compare("setne")

    def binary_gt(self) -> None:
        self._compare("setg")

    def binary_lt(self) -> None:
        self._compare("setl")

    def binary_ge(self) -> None:
        self._compare("setge")

    def binary_le(self) -> None:
        self._compare("setle")

    def call_direct(self, ref: FnRef, argc: int) -> None:
        regs = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
        arg_index = argc - 1
        while arg_index >= 0:
            if arg_index < len(regs):
                self._emit(f"popq {regs[arg_index]}")
            arg_index -= 1
        self._emit(f"call {self._label(ref.symbol)}")
        self._emit("pushq %rax")

    def call_indirect(self, argc: int) -> None:
        regs = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
        arg_index = argc - 1
        while arg_index >= 0:
            if arg_index < len(regs):
                self._emit(f"popq {regs[arg_index]}")
            arg_index -= 1
        self._emit("popq %rax")
        self._emit("call *%rax")
        self._emit("pushq %rax")

    def call_pipe(self) -> None:
        self._emit("popq %r11")
        self._emit("popq %rdi")
        self._emit("call *%r11")
        self._emit("pushq %rax")

    def call_intrinsic(self, name: str, argc: int) -> None:
        _ = argc
        if name == "__load__":
            self._emit("popq %rax")
            self._emit("movq (%rax), %rax")
            self._emit("pushq %rax")
            return
        if name == "__store__":
            self._emit("popq %rax")
            self._emit("popq %rbx")
            self._emit("movq %rbx, (%rax)")
            self._emit("xorq %rax, %rax")
            self._emit("pushq %rax")
            return
        if name == "__load8__":
            self._emit("popq %rax")
            self._emit("movzbq (%rax), %rax")
            self._emit("pushq %rax")
            return
        if name == "__store8__":
            self._emit("popq %rax")
            self._emit("popq %rbx")
            self._emit("movb %bl, (%rax)")
            self._emit("xorq %rax, %rax")
            self._emit("pushq %rax")
            return
        if name == "__load16__":
            self._emit("popq %rax")
            self._emit("movzwq (%rax), %rax")
            self._emit("pushq %rax")
            return
        if name == "__store16__":
            self._emit("popq %rax")
            self._emit("popq %rbx")
            self._emit("movw %bx, (%rax)")
            self._emit("xorq %rax, %rax")
            self._emit("pushq %rax")
            return
        if name == "__load32__":
            self._emit("popq %rax")
            self._emit("movl (%rax), %eax")
            self._emit("pushq %rax")
            return
        if name == "__store32__":
            self._emit("popq %rax")
            self._emit("popq %rbx")
            self._emit("movl %ebx, (%rax)")
            self._emit("xorq %rax, %rax")
            self._emit("pushq %rax")
            return
        if name.startswith("__syscall"):
            self._emit_syscall(name)
            return
        raise SyntaxError(f"Unsupported intrinsic for x86_64: {name}")

    def _emit_syscall(self, name: str) -> None:
        argc = int(name[len("__syscall"):len("__syscall") + 1])
        if argc == 0:
            self._emit("popq %rax")
            self._emit("syscall")
            self._emit("pushq %rax")
            return
        regs = ["%rdi", "%rsi", "%rdx", "%r10", "%r8", "%r9"]
        arg_index = argc - 1
        while arg_index >= 1:
            self._emit(f"popq {regs[arg_index - 1]}")
            arg_index -= 1
        self._emit("popq %rax")
        self._emit("syscall")
        self._emit("pushq %rax")

    def begin_if(self, token: str) -> IfState:
        return IfState(token)

    def if_condition(self, state: IfState) -> None:
        self._emit("popq %rax")
        self._emit("testq %rax, %rax")
        self._emit(f"jz {self._label(state.token + '_else')}")

    def begin_else(self, state: IfState) -> None:
        state.has_else = True
        self._emit(f"jmp {self._label(state.token + '_end')}")
        self._emit_label(self._label(state.token + "_else"))

    def end_if(self, state: IfState) -> None:
        if not state.has_else:
            self._emit_label(self._label(state.token + "_else"))
        self._emit_label(self._label(state.token + "_end"))

    def begin_loop(self, token: str) -> LoopState:
        state = LoopState(token)
        self._emit_label(self._label(state.token + "_start"))
        return state

    def loop_condition(self, state: LoopState) -> None:
        self._emit("popq %rax")
        self._emit("testq %rax, %rax")
        self._emit(f"jz {self._label(state.token + '_end')}")

    def end_loop(self, state: LoopState) -> None:
        self._emit(f"jmp {self._label(state.token + '_start')}")
        self._emit_label(self._label(state.token + "_end"))

    def emit_break(self, state: LoopState) -> None:
        self._emit(f"jmp {self._label(state.token + '_end')}")

    def emit_continue(self, state: LoopState) -> None:
        self._emit(f"jmp {self._label(state.token + '_start')}")

    def emit_return(self) -> None:
        self._emit("popq %rax")
        self._emit(f"jmp {self.current_epilogue}")

    def emit_expr_discard(self) -> None:
        self._emit("popq %rax")

    def build(self, module_text: str, input_file: PathLike, cache_dir: PathLike) -> BuildResult:
        input_file = Path(input_file)
        cache_dir = ensure_cache_dir(cache_dir)
        runtime_path = Path(__file__).resolve().parent.parent / "runtime.s"
        asm_path = cache_dir / f"{input_file.stem}.s"
        obj_path = cache_dir / f"{input_file.stem}.o"
        runtime_obj_path = cache_dir / "runtime.o"
        exe_path = cache_dir / input_file.stem
        asm_path.write_text(module_text)
        subprocess.run(["as", str(asm_path), "-o", str(obj_path)], check=True)
        subprocess.run(["as", str(runtime_path), "-o", str(runtime_obj_path)], check=True)
        subprocess.run(["ld", str(obj_path), str(runtime_obj_path), "-o", str(exe_path)], check=True)
        return BuildResult(exe_path, (asm_path, obj_path, runtime_obj_path))

    def run(self, build_result: BuildResult, argv: list[str], cwd: PathLike) -> int:
        result = subprocess.run([str(build_result.artifact_path)] + argv, cwd=Path(cwd))
        return result.returncode

