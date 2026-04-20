"""
x86_64 backend for udewy.

Generates GNU assembler syntax targeting Linux x86_64 with System V ABI.
"""

from os import PathLike
from pathlib import Path

from .. import t1
from .common import Backend, CORE_INTRINSIC_ARITIES, LINUX_SYSCALL_INTRINSIC_ARITIES, RunOptions
from . import sdl_desktop

class X86_64Backend(Backend):
    """
    x86_64 code generator implementing the Backend protocol.
    
    Value stack model:
    - Top of stack is always in %rax after an expression
    - save_value() pushes %rax to physical stack
    - restore_value() pops from physical stack to %rax
    - Binary operators save left, compute right, then operate
    
    Calling convention (System V ABI):
    - Arguments: rdi, rsi, rdx, rcx, r8, r9, then stack
    - Return value: rax
    - Callee-saved: rbx, r12, r13, r14, r15
    """
    _ARG_REGS = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
    _VALUE_CACHE_REGS = ["%r12", "%r13", "%r14"]
    _FIXED_FRAME_BYTES = 48
    _XMM_ARG_REGS = [f"%xmm{i}" for i in range(8)]
    
    def __init__(self) -> None:
        self._function_code: list[tuple[int, list[str]]] = []
        self._current_fn_code: list[str] | None = None
        self._reachable_fn_label_ids: set[int] | None = None
        self._data: list[str] = []
        self._next_label: int = 0
        self._extern_symbols: set[str] = set()
        self._module_init_name: str | None = None
        
        # Function state
        self._current_fn_epilogue: str = ""
        self._stack_offset: int = -48  # Start after callee-saved area
        self._param_slots: list[int] = []
        self._saved_depth: int = 0
        self._spilled_depth: int = 0
        self._min_slot_offset: int = 0
        self._frame_subtract_index: int = -1
        
        # Control flow state
        self._if_stack: list[tuple[str, str, bool]] = []  # (else_label, end_label, else_emitted)
        self._loop_stack: list[tuple[str, str]] = []  # (start_label, end_label)
        
        # Symbol tracking
        self._fn_labels: dict[int, str] = {}
        self._global_labels: dict[int, str] = {}
        self._string_labels: dict[int, str] = {}
        self._array_labels: dict[int, str] = {}
        self._static_labels: dict[int, str] = {}
    
    def _emit(self, instr: str) -> None:
        """Emit an instruction."""
        assert self._current_fn_code is not None
        self._current_fn_code.append("    " + instr)
    
    def _emit_label(self, label: str) -> None:
        """Emit a label."""
        assert self._current_fn_code is not None
        self._current_fn_code.append(label + ":")
    
    def _emit_data(self, directive: str) -> None:
        """Emit to data section."""
        self._data.append(directive)
    
    def _emit_data_label(self, label: str) -> None:
        """Emit label to data section."""
        self._data.append(label + ":")
    
    def _new_label(self, prefix: str = "L") -> str:
        """Generate a new unique label."""
        label = f".{prefix}{self._next_label}"
        self._next_label += 1
        return label

    def _note_slot(self, slot: int) -> None:
        if slot < self._min_slot_offset:
            self._min_slot_offset = slot

    def _frame_bytes(self) -> int:
        required_bytes = max(self._FIXED_FRAME_BYTES, -self._min_slot_offset)
        return (required_bytes + 15) & -16

    def _save_reg(self, reg: str) -> None:
        if self._spilled_depth > 0:
            self._emit("subq $16, %rsp")
            self._emit(f"movq {reg}, (%rsp)")
            self._spilled_depth += 1
        elif self._saved_depth < len(self._VALUE_CACHE_REGS):
            self._emit(f"movq {reg}, {self._VALUE_CACHE_REGS[self._saved_depth]}")
        else:
            for cache_reg in self._VALUE_CACHE_REGS[:self._saved_depth]:
                self._emit("subq $16, %rsp")
                self._emit(f"movq {cache_reg}, (%rsp)")
            self._emit("subq $16, %rsp")
            self._emit(f"movq {reg}, (%rsp)")
            self._spilled_depth = self._saved_depth + 1
        self._saved_depth += 1

    def _pop_saved_into(self, reg: str) -> None:
        self._saved_depth -= 1
        if self._spilled_depth > 0:
            self._emit(f"movq (%rsp), {reg}")
            self._emit("addq $16, %rsp")
            self._spilled_depth -= 1
        elif self._saved_depth < len(self._VALUE_CACHE_REGS):
            cache_reg = self._VALUE_CACHE_REGS[self._saved_depth]
            if cache_reg != reg:
                self._emit(f"movq {cache_reg}, {reg}")
    
    def _prepare_call_args(self, num_args: int, fn_reg: str | None = None) -> int:
        reg_count = min(num_args, len(self._ARG_REGS))
        stack_count = num_args - reg_count
        stack_bytes = ((stack_count * 8) + 15) & -16
        consumed_values = num_args + (1 if fn_reg is not None else 0)

        if self._spilled_depth > 0:
            self._emit("movq %rsp, %r10")
            if stack_bytes > 0:
                self._emit(f"subq ${stack_bytes}, %rsp")
                for offset in range(stack_count):
                    src_offset = (stack_count - 1 - offset) * 16
                    self._emit(f"movq {src_offset}(%r10), %rax")
                    self._emit(f"movq %rax, {offset * 8}(%rsp)")

            for reg_idx in range(reg_count - 1, -1, -1):
                src_offset = (stack_count + (reg_count - 1 - reg_idx)) * 16
                self._emit(f"movq {src_offset}(%r10), {self._ARG_REGS[reg_idx]}")

            if fn_reg is not None:
                self._emit(f"movq {num_args * 16}(%r10), {fn_reg}")

            self._saved_depth -= consumed_values
            self._spilled_depth -= consumed_values
            return stack_bytes + consumed_values * 16

        if stack_bytes > 0:
            self._emit(f"subq ${stack_bytes}, %rsp")
            for offset in range(stack_count - 1, -1, -1):
                self._pop_saved_into("%rax")
                self._emit(f"movq %rax, {offset * 8}(%rsp)")

        for reg_idx in range(reg_count - 1, -1, -1):
            self._pop_saved_into(self._ARG_REGS[reg_idx])

        if fn_reg is not None:
            self._pop_saved_into(fn_reg)

        return stack_bytes
    
    # ========================================================================
    # Module lifecycle
    # ========================================================================
    
    def begin_module(self) -> None:
        """Initialize the module for code generation."""
        pass

    def set_module_init(self, name: str | None) -> None:
        self._module_init_name = name

    def set_reachable_functions(self, label_ids: set[int]) -> None:
        self._reachable_fn_label_ids = label_ids
    
    def finish_module(self) -> str:
        """Finalize and return the generated assembly."""
        output = []
        output.append(".text")
        output.append(".globl _start")
        for symbol in sorted(self._extern_symbols):
            output.append(f".extern {symbol}")
        output.append("")
        
        # Emit _start entry point
        output.append("_start:")
        output.append("    xorq %rbp, %rbp")
        output.append("    movq (%rsp), %rdi")      # argc
        output.append("    leaq 8(%rsp), %rsi")     # argv
        output.append("    andq $-16, %rsp")        # align stack
        if self._module_init_name is not None:
            output.append(f"    call {self._module_init_name}")
        output.append("    call __main__")
        output.append("    movq %rax, %rdi")        # exit code
        output.append("    movq $231, %rax")        # exit_group syscall
        output.append("    syscall")
        output.append("")
        
        for label_id, lines in self._function_code:
            if self._reachable_fn_label_ids is not None and label_id not in self._reachable_fn_label_ids:
                continue
            output.extend(lines)
        output.append("")
        output.append(".data")
        output.append(".hidden __dso_handle")
        output.append(".weak __dso_handle")
        output.append("__dso_handle:")
        output.append("    .quad 0")
        output.extend(self._data)
        output.append("")
        output.append(".section .note.GNU-stack,\"\",@progbits")
        output.append("")
        return "\n".join(output)
    
    # ========================================================================
    # Data section
    # ========================================================================
    
    def intern_string(self, content: bytes) -> int:
        """Add a string constant to the data section."""
        label_id = self._next_label
        label = self._new_label("str")
        self._string_labels[label_id] = label
        
        self._emit_data(f".section .data.{label},\"aw\",@progbits")
        self._emit_data_label(label)
        self._emit_data(f"    .quad {len(content)}")
        if len(content) > 0:
            bytes_str = ", ".join(str(b) for b in content)
            self._emit_data(f"    .byte {bytes_str}")
        
        return label_id
    
    def intern_array(self, elements: list[int | str]) -> int:
        """Add an array constant to the data section."""
        label_id = self._next_label
        label = self._new_label("arr")
        self._array_labels[label_id] = label
        
        self._emit_data(f".section .data.{label},\"aw\",@progbits")
        self._emit_data_label(label)
        self._emit_data(f"    .quad {len(elements)}")
        for elem in elements:
            self._emit_data(f"    .quad {elem}")
        
        return label_id
    
    def define_global(self, name: str | None, value: int | str) -> int:
        """Define a global variable."""
        label_id = self._next_label
        if name is None:
            label = self._new_label("global")
        else:
            label = name
            self._next_label += 1
        self._global_labels[label_id] = label
        
        self._emit_data(f".section .data.{label},\"aw\",@progbits")
        self._emit_data_label(label)
        self._emit_data(f"    .quad {value}")
        
        return label_id

    def declare_extern_global(self, name: str) -> int:
        """Declare an externally provided global variable."""
        label_id = self._next_label
        self._next_label += 1
        self._global_labels[label_id] = name
        self._extern_symbols.add(name)
        return label_id

    def intern_static(self, size: int) -> int:
        """Add a zero-initialized static storage block to the data section."""
        label_id = self._next_label
        label = self._new_label("static")
        self._static_labels[label_id] = label

        self._emit_data(f".section .bss.{label},\"aw\",@nobits")
        self._emit_data_label(label)
        if size > 0:
            self._emit_data(f"    .zero {size}")

        return label_id
    
    def push_string_ref(self, label_id: int) -> None:
        """Push address of string data onto value stack."""
        label = self._string_labels[label_id]
        self._emit(f"leaq {label}+8(%rip), %rax")
    
    def push_array_ref(self, label_id: int) -> None:
        """Push address of array data onto value stack."""
        label = self._array_labels[label_id]
        self._emit(f"leaq {label}+8(%rip), %rax")
    
    def push_global_ref(self, label_id: int) -> None:
        """Push address of global onto value stack."""
        label = self._global_labels[label_id]
        self._emit(f"leaq {label}(%rip), %rax")

    def push_static_ref(self, label_id: int) -> None:
        """Push address of raw static storage onto value stack."""
        label = self._static_labels[label_id]
        self._emit(f"leaq {label}(%rip), %rax")
    
    def load_global(self, label_id: int) -> None:
        """Load value of global onto value stack."""
        label = self._global_labels[label_id]
        self._emit(f"movq {label}(%rip), %rax")
    
    def store_global(self, label_id: int) -> None:
        """Pop value from stack and store to global."""
        label = self._global_labels[label_id]
        self._emit(f"movq %rax, {label}(%rip)")

    def function_ref(self, label_id: int) -> str:
        return self._fn_labels[label_id]

    def string_ref(self, label_id: int) -> str:
        return f"{self._string_labels[label_id]}+8"

    def array_ref(self, label_id: int) -> str:
        return f"{self._array_labels[label_id]}+8"

    def static_ref(self, label_id: int) -> str:
        return self._static_labels[label_id]
    
    # ========================================================================
    # Functions
    # ========================================================================
    
    def declare_function(self, name: str | None, num_params: int) -> int:
        """Declare a function."""
        label_id = self._next_label
        if name is None:
            label = self._new_label("fn")
        else:
            label = name
            self._next_label += 1
        self._fn_labels[label_id] = label
        return label_id

    def bind_extern_function(self, label_id: int, name: str) -> None:
        self._fn_labels[label_id] = name
        self._extern_symbols.add(name)

    def declare_extern_function(self, name: str, num_params: int) -> int:
        label_id = self.declare_function(name, num_params)
        self._extern_symbols.add(name)
        return label_id
    
    def begin_function(self, label_id: int, name: str, param_count: int, is_main: bool) -> None:
        """Begin function definition."""
        label = self._fn_labels[label_id]
        self._saved_depth = 0
        self._spilled_depth = 0
        self._min_slot_offset = 0
        
        self._current_fn_code = []
        self._function_code.append((label_id, self._current_fn_code))
        
        self._current_fn_code.append(f".section .text.{label},\"ax\",@progbits")
        if is_main:
            self._emit_label("__main__")
        self._emit_label(label)
        
        # Prologue
        self._emit("pushq %rbp")
        self._emit("movq %rsp, %rbp")
        self._frame_subtract_index = len(self._current_fn_code)
        self._emit("    # frame setup")
        
        # Save callee-saved registers
        self._emit("movq %rbx, -8(%rbp)")
        self._emit("movq %r12, -16(%rbp)")
        self._emit("movq %r13, -24(%rbp)")
        self._emit("movq %r14, -32(%rbp)")
        self._emit("movq %r15, -40(%rbp)")
        
        # Set up parameters
        self._param_slots = []
        self._stack_offset = -48
        
        for i in range(param_count):
            slot = self._stack_offset
            self._param_slots.append(slot)
            self._note_slot(slot)
            
            if i < 6:
                self._emit(f"movq {self._ARG_REGS[i]}, {slot}(%rbp)")
            else:
                caller_offset = 16 + (i - 6) * 8
                self._emit(f"movq {caller_offset}(%rbp), %rax")
                self._emit(f"movq %rax, {slot}(%rbp)")
            
            self._stack_offset -= 8
        
        self._current_fn_epilogue = f"{label}_epilogue"
    
    def end_function(self) -> None:
        """End function definition."""
        assert self._current_fn_code is not None
        frame_bytes = self._frame_bytes()
        self._current_fn_code[self._frame_subtract_index] = f"    subq ${frame_bytes}, %rsp"
        self._emit_label(self._current_fn_epilogue)
        
        # Restore callee-saved registers
        self._emit("movq -8(%rbp), %rbx")
        self._emit("movq -16(%rbp), %r12")
        self._emit("movq -24(%rbp), %r13")
        self._emit("movq -32(%rbp), %r14")
        self._emit("movq -40(%rbp), %r15")
        self._emit("movq %rbp, %rsp")
        self._emit("popq %rbp")
        self._emit("ret")
        self._current_fn_code = None
    
    def load_param(self, index: int) -> None:
        """Push parameter value onto the value stack."""
        slot = self._param_slots[index]
        self._emit(f"movq {slot}(%rbp), %rax")
    
    def alloc_local(self) -> int:
        """Allocate a local variable slot."""
        slot = self._stack_offset
        self._stack_offset -= 8
        self._note_slot(slot)
        return slot
    
    def load_local(self, slot: int) -> None:
        """Push local variable value onto the value stack."""
        self._emit(f"movq {slot}(%rbp), %rax")
    
    def store_local(self, slot: int) -> None:
        """Pop value from stack and store to local variable."""
        self._emit(f"movq %rax, {slot}(%rbp)")
    
    # ========================================================================
    # Value stack operations
    # ========================================================================
    
    def push_const_i64(self, value: int) -> None:
        """Push a 64-bit integer constant onto the value stack."""
        self._emit(f"movq ${value}, %rax")
    
    def push_void(self) -> None:
        """Push void (zero) onto the value stack."""
        self._emit("xorq %rax, %rax")
    
    def push_fn_ref(self, label_id: int) -> None:
        """Push address of function onto the value stack."""
        label = self._fn_labels[label_id]
        self._emit(f"leaq {label}(%rip), %rax")
    
    def pop_value(self) -> None:
        """Discard the top value on the stack."""
        pass
    
    def save_value(self) -> None:
        """Save the top value to physical stack."""
        self._save_reg("%rax")
    
    def restore_value(self) -> None:
        """Restore a previously saved value."""
        self._pop_saved_into("%rax")
    
    # ========================================================================
    # Operators
    # ========================================================================
    
    def unary_op(self, op_kind: t1.Kind) -> None:
        """Apply unary operator to top of stack."""
        if op_kind == t1.Kind.TK_MINUS:
            self._emit("negq %rax")
        elif op_kind == t1.Kind.TK_NOT:
            self._emit("notq %rax")
    
    def binary_op(self, op_kind: t1.Kind) -> None:
        """
        Apply binary operator to top two values on stack.
        
        Assumes left operand was saved via save_value(), right is in rax.
        """
        self._emit("movq %rax, %rcx")  # right in rcx
        self._pop_saved_into("%rax")   # left in rax
        
        if op_kind == t1.Kind.TK_PLUS:
            self._emit("addq %rcx, %rax")
        elif op_kind == t1.Kind.TK_MINUS:
            self._emit("subq %rcx, %rax")
        elif op_kind == t1.Kind.TK_MUL:
            self._emit("imulq %rcx, %rax")
        elif op_kind == t1.Kind.TK_IDIV:
            self._emit("cqto")
            self._emit("idivq %rcx")
        elif op_kind == t1.Kind.TK_MOD:
            self._emit("cqto")
            self._emit("idivq %rcx")
            self._emit("movq %rdx, %rax")
        elif op_kind == t1.Kind.TK_LEFT_SHIFT:
            self._emit("shlq %cl, %rax")
        elif op_kind == t1.Kind.TK_RIGHT_SHIFT:
            self._emit("shrq %cl, %rax")
        elif op_kind == t1.Kind.TK_AND:
            self._emit("andq %rcx, %rax")
        elif op_kind == t1.Kind.TK_OR:
            self._emit("orq %rcx, %rax")
        elif op_kind == t1.Kind.TK_XOR:
            self._emit("xorq %rcx, %rax")
        elif op_kind == t1.Kind.TK_EQ:
            self._emit("cmpq %rcx, %rax")
            self._emit("sete %al")
            self._emit("movzbq %al, %rax")
            self._emit("negq %rax")
        elif op_kind == t1.Kind.TK_NOT_EQ:
            self._emit("cmpq %rcx, %rax")
            self._emit("setne %al")
            self._emit("movzbq %al, %rax")
            self._emit("negq %rax")
        elif op_kind == t1.Kind.TK_GT:
            self._emit("cmpq %rcx, %rax")
            self._emit("setg %al")
            self._emit("movzbq %al, %rax")
            self._emit("negq %rax")
        elif op_kind == t1.Kind.TK_LT:
            self._emit("cmpq %rcx, %rax")
            self._emit("setl %al")
            self._emit("movzbq %al, %rax")
            self._emit("negq %rax")
        elif op_kind == t1.Kind.TK_GT_EQ:
            self._emit("cmpq %rcx, %rax")
            self._emit("setge %al")
            self._emit("movzbq %al, %rax")
            self._emit("negq %rax")
        elif op_kind == t1.Kind.TK_LT_EQ:
            self._emit("cmpq %rcx, %rax")
            self._emit("setle %al")
            self._emit("movzbq %al, %rax")
            self._emit("negq %rax")
    
    def pipe_call(self) -> None:
        """
        Handle pipe operator: call function with left as arg.
        
        Right (function pointer) is in rax, left (arg) was saved.
        """
        self._emit("movq %rax, %r11")  # save fn ptr
        self._pop_saved_into("%rdi")   # arg1
        self._emit("call *%r11")
    
    # ========================================================================
    # Memory operations
    # ========================================================================
    
    def load_mem(self, width: int, signed: bool = False) -> None:
        """Load from memory address in rax."""
        if width == 64:
            self._emit("movq (%rax), %rax")
        elif width == 32:
            if signed:
                self._emit("movslq (%rax), %rax")
            else:
                self._emit("movl (%rax), %eax")
        elif width == 16:
            if signed:
                self._emit("movswq (%rax), %rax")
            else:
                self._emit("movzwq (%rax), %rax")
        elif width == 8:
            if signed:
                self._emit("movsbq (%rax), %rax")
            else:
                self._emit("movzbq (%rax), %rax")
    
    def store_mem(self, width: int) -> None:
        """Store to memory. Stack: [value addr] -> pushes 0."""
        self._pop_saved_into("%rbx")  # value
        if width == 64:
            self._emit("movq %rbx, (%rax)")
        elif width == 32:
            self._emit("movl %ebx, (%rax)")
        elif width == 16:
            self._emit("movw %bx, (%rax)")
        elif width == 8:
            self._emit("movb %bl, (%rax)")
        self._emit("xorq %rax, %rax")  # return 0
    
    def signed_shr(self) -> None:
        """Signed (arithmetic) right shift. Stack: [value bits] -> result."""
        self._emit("movq %rax, %rcx")
        self._pop_saved_into("%rax")
        self._emit("sarq %cl, %rax")

    def unsigned_idiv(self) -> None:
        """Unsigned division. Stack: [left right] -> quotient."""
        self._emit("movq %rax, %rcx")
        self._pop_saved_into("%rax")
        self._emit("xorq %rdx, %rdx")
        self._emit("divq %rcx")

    def unsigned_mod(self) -> None:
        """Unsigned remainder. Stack: [left right] -> remainder."""
        self._emit("movq %rax, %rcx")
        self._pop_saved_into("%rax")
        self._emit("xorq %rdx, %rdx")
        self._emit("divq %rcx")
        self._emit("movq %rdx, %rax")

    def unsigned_cmp(self, kind: str) -> None:
        """Unsigned comparison returning udewy booleans."""
        self._emit("movq %rax, %rcx")
        self._pop_saved_into("%rax")
        self._emit("cmpq %rcx, %rax")
        if kind == "gt":
            self._emit("seta %al")
        elif kind == "lt":
            self._emit("setb %al")
        elif kind == "gte":
            self._emit("setae %al")
        elif kind == "lte":
            self._emit("setbe %al")
        self._emit("movzbq %al, %rax")
        self._emit("negq %rax")

    def alloca(self) -> None:
        """Allocate temporary stack storage and return its address."""
        self._emit("addq $7, %rax")
        self._emit("andq $-8, %rax")
        self._emit("subq %rax, %rsp")
        self._emit("movq %rsp, %rax")
    
    # ========================================================================
    # Calls
    # ========================================================================
    
    def call_direct(self, label_id: int, num_args: int) -> None:
        """Call a function directly by label."""
        stack_bytes = self._prepare_call_args(num_args)
        label = self._fn_labels[label_id]
        self._emit(f"call {label}")
        if stack_bytes > 0:
            self._emit(f"addq ${stack_bytes}, %rsp")
    
    def call_indirect(self, num_args: int) -> None:
        """Call a function indirectly via pointer."""
        stack_bytes = self._prepare_call_args(num_args, "%r11")
        self._emit("call *%r11")
        if stack_bytes > 0:
            self._emit(f"addq ${stack_bytes}, %rsp")

    def max_call_args(self) -> int | None:
        return None
    
    def syscall(self, num_args: int) -> None:
        """Invoke a syscall."""
        # Args are on stack: syscall_num, arg1, arg2, ...
        # Need to rearrange into: rax=num, rdi=arg1, rsi=arg2, rdx=arg3, r10=arg4, r8=arg5, r9=arg6
        if num_args == 1:
            # syscall_num in rax
            self._emit("syscall")
        elif num_args == 2:
            # rax=num, arg1 on stack -> rdi
            self._emit("movq %rax, %rdi")
            self._pop_saved_into("%rax")
            self._emit("syscall")
        elif num_args == 3:
            self._emit("movq %rax, %rsi")
            self._pop_saved_into("%rdi")
            self._pop_saved_into("%rax")
            self._emit("syscall")
        elif num_args == 4:
            self._emit("movq %rax, %rdx")
            self._pop_saved_into("%rsi")
            self._pop_saved_into("%rdi")
            self._pop_saved_into("%rax")
            self._emit("syscall")
        elif num_args == 5:
            self._emit("movq %rax, %r10")
            self._pop_saved_into("%rdx")
            self._pop_saved_into("%rsi")
            self._pop_saved_into("%rdi")
            self._pop_saved_into("%rax")
            self._emit("syscall")
        elif num_args == 6:
            self._emit("movq %rax, %r8")
            self._pop_saved_into("%r10")
            self._pop_saved_into("%rdx")
            self._pop_saved_into("%rsi")
            self._pop_saved_into("%rdi")
            self._pop_saved_into("%rax")
            self._emit("syscall")
        elif num_args == 7:
            self._emit("movq %rax, %r9")
            self._pop_saved_into("%r8")
            self._pop_saved_into("%r10")
            self._pop_saved_into("%rdx")
            self._pop_saved_into("%rsi")
            self._pop_saved_into("%rdi")
            self._pop_saved_into("%rax")
            self._emit("syscall")

    def _mixed_intrinsic_arg_slots(self, name: str) -> int | None:
        prefix = "__call_extern_xmm_mixed_"
        suffix = "__"
        if not name.startswith(prefix) or not name.endswith(suffix):
            return None
        value = name[len(prefix) : -len(suffix)]
        if not value.isdigit():
            return None
        arg_slots = int(value)
        if arg_slots < 1 or arg_slots > 8:
            return None
        return arg_slots

    def _emit_move_to_xmm(self, kind: int, xmm_reg: str) -> None:
        if kind == 1:
            self._emit(f"movd %eax, {xmm_reg}")
            return
        if kind == 2:
            self._emit(f"movq %rax, {xmm_reg}")
            return
        raise RuntimeError(f"unsupported XMM intrinsic kind: {kind}")

    def _call_extern_xmm_mixed(self, type_tags: list[int]) -> None:
        gp_slots: list[int] = []
        xmm_slots: list[int] = []
        gp_count = 0
        xmm_count = 0
        for kind in type_tags:
            if kind == 0:
                gp_slots.append(gp_count)
                xmm_slots.append(-1)
                gp_count += 1
            elif kind in (1, 2):
                gp_slots.append(-1)
                xmm_slots.append(xmm_count)
                xmm_count += 1
            else:
                raise RuntimeError(f"unsupported mixed XMM intrinsic kind: {kind}")

        if gp_count > len(self._ARG_REGS):
            raise RuntimeError("mixed XMM intrinsic exceeds supported GP argument register count")
        if xmm_count > len(self._XMM_ARG_REGS):
            raise RuntimeError("mixed XMM intrinsic exceeds supported XMM argument register count")

        for arg_index in range(len(type_tags) - 1, -1, -1):
            kind = type_tags[arg_index]
            if kind == 0:
                dst_reg = self._ARG_REGS[gp_slots[arg_index]]
                if dst_reg != "%rax":
                    self._emit(f"movq %rax, {dst_reg}")
            else:
                self._emit_move_to_xmm(kind, self._XMM_ARG_REGS[xmm_slots[arg_index]])

            if arg_index > 0:
                self._pop_saved_into("%rax")

        self._pop_saved_into("%r11")
        self._emit("call *%r11")
    
    # ========================================================================
    # Control flow
    # ========================================================================
    
    def begin_if(self) -> None:
        """Begin an if statement."""
        else_label = self._new_label("else")
        end_label = self._new_label("if_end")
        self._if_stack.append((else_label, end_label, False))
        
        self._emit("testq %rax, %rax")
        self._emit(f"jz {else_label}")
    
    def begin_else(self) -> None:
        """Begin the else branch."""
        else_label, end_label, _ = self._if_stack[-1]
        self._if_stack[-1] = (else_label, end_label, True)
        self._emit(f"jmp {end_label}")
        self._emit_label(else_label)
    
    def end_if(self) -> None:
        """End an if statement."""
        else_label, end_label, else_emitted = self._if_stack.pop()
        if not else_emitted:
            self._emit_label(else_label)
        self._emit_label(end_label)
    
    def begin_loop(self) -> None:
        """Begin a loop."""
        start_label = self._new_label("loop_start")
        end_label = self._new_label("loop_end")
        self._loop_stack.append((start_label, end_label))
        self._emit_label(start_label)
    
    def begin_loop_body(self) -> None:
        """Begin the loop body after condition check."""
        _, end_label = self._loop_stack[-1]
        self._emit("testq %rax, %rax")
        self._emit(f"jz {end_label}")
    
    def end_loop(self) -> None:
        """End a loop."""
        start_label, end_label = self._loop_stack.pop()
        self._emit(f"jmp {start_label}")
        self._emit_label(end_label)
    
    def emit_break(self) -> None:
        """Emit a break statement."""
        _, end_label = self._loop_stack[-1]
        self._emit(f"jmp {end_label}")
    
    def emit_continue(self) -> None:
        """Emit a continue statement."""
        start_label, _ = self._loop_stack[-1]
        self._emit(f"jmp {start_label}")
    
    def emit_return(self) -> None:
        """Emit a return statement."""
        self._emit(f"jmp {self._current_fn_epilogue}")
    
    # ========================================================================
    # Intrinsics
    # ========================================================================
    
    _INTRINSIC_ARITIES = (
        CORE_INTRINSIC_ARITIES
        | LINUX_SYSCALL_INTRINSIC_ARITIES
        | {
            "__i64_to_f32_bits__": 1,
            "__i64_to_f64_bits__": 1,
        }
    )
    
    def is_intrinsic(self, name: str) -> bool:
        """Check if name is an intrinsic supported by this backend."""
        return name in self._INTRINSIC_ARITIES or self._mixed_intrinsic_arg_slots(name) is not None

    def intrinsic_arity(self, name: str) -> int | None:
        """Return the expected arity for a supported intrinsic."""
        mixed_args = self._mixed_intrinsic_arg_slots(name)
        if mixed_args is not None:
            return 1 + (mixed_args * 2)
        return self._INTRINSIC_ARITIES.get(name)
    
    def emit_intrinsic(self, name: str, num_args: int, intrinsic_data: object | None = None) -> None:
        """Emit code for an intrinsic call."""
        if name == "__load_u8__":
            self.load_mem(8, signed=False)
        elif name == "__load_u16__":
            self.load_mem(16, signed=False)
        elif name == "__load_u32__":
            self.load_mem(32, signed=False)
        elif name == "__load_u64__" or name == "__load__":
            self.load_mem(64, signed=False)
        elif name == "__store_u8__":
            self.store_mem(8)
        elif name == "__store_u16__":
            self.store_mem(16)
        elif name == "__store_u32__":
            self.store_mem(32)
        elif name == "__store_u64__" or name == "__store__":
            self.store_mem(64)
        elif name == "__load_i8__":
            self.load_mem(8, signed=True)
        elif name == "__load_i16__":
            self.load_mem(16, signed=True)
        elif name == "__load_i32__":
            self.load_mem(32, signed=True)
        elif name == "__load_i64__":
            self.load_mem(64, signed=True)
        elif name == "__store_i8__":
            self.store_mem(8)
        elif name == "__store_i16__":
            self.store_mem(16)
        elif name == "__store_i32__":
            self.store_mem(32)
        elif name == "__store_i64__":
            self.store_mem(64)
        elif name == "__signed_shr__":
            self.signed_shr()
        elif name == "__unsigned_idiv__":
            self.unsigned_idiv()
        elif name == "__unsigned_mod__":
            self.unsigned_mod()
        elif name == "__unsigned_lt__":
            self.unsigned_cmp("lt")
        elif name == "__unsigned_gt__":
            self.unsigned_cmp("gt")
        elif name == "__unsigned_lte__":
            self.unsigned_cmp("lte")
        elif name == "__unsigned_gte__":
            self.unsigned_cmp("gte")
        elif name == "__alloca__":
            self.alloca()
        elif name == "__i64_to_f32_bits__":
            self._emit("cvtsi2ss %rax, %xmm0")
            self._emit("movd %xmm0, %eax")
        elif name == "__i64_to_f64_bits__":
            self._emit("cvtsi2sd %rax, %xmm0")
            self._emit("movq %xmm0, %rax")
        elif name.startswith("__syscall"):
            self.syscall(num_args)
        else:
            mixed_args = self._mixed_intrinsic_arg_slots(name)
            if mixed_args is None:
                raise RuntimeError(f"unsupported intrinsic {name!r}")
            if not isinstance(intrinsic_data, dict) or "type_tags" not in intrinsic_data:
                raise RuntimeError(f"missing type tags for intrinsic {name!r}")
            type_tags = intrinsic_data["type_tags"]
            if not isinstance(type_tags, list) or len(type_tags) != mixed_args:
                raise RuntimeError(f"invalid type tags for intrinsic {name!r}")
            self._call_extern_xmm_mixed(type_tags)
    
    def get_builtin_constants(self) -> dict[str, int]:
        """Return x86_64 Linux syscall numbers and common constants."""
        return {
            # File descriptors
            "STDIN": 0,
            "STDOUT": 1,
            "STDERR": 2,
            # Syscall numbers (x86_64 Linux)
            "SYS_READ": 0,
            "SYS_WRITE": 1,
            "SYS_OPEN": 2,
            "SYS_CLOSE": 3,
            "SYS_STAT": 4,
            "SYS_FSTAT": 5,
            "SYS_LSEEK": 8,
            "SYS_MMAP": 9,
            "SYS_MUNMAP": 11,
            "SYS_BRK": 12,
            "SYS_IOCTL": 16,
            "SYS_PIPE": 22,
            "SYS_DUP": 32,
            "SYS_DUP2": 33,
            "SYS_GETPID": 39,
            "SYS_FORK": 57,
            "SYS_EXECVE": 59,
            "SYS_EXIT": 60,
            "SYS_WAIT4": 61,
            "SYS_KILL": 62,
            "SYS_GETCWD": 79,
            "SYS_CHDIR": 80,
            "SYS_MKDIR": 83,
            "SYS_RMDIR": 84,
            "SYS_CREAT": 85,
            "SYS_UNLINK": 87,
            "SYS_GETUID": 102,
            "SYS_GETGID": 104,
            "SYS_GETEUID": 107,
            "SYS_GETEGID": 108,
            "SYS_CLOCK_GETTIME": 228,
            "SYS_EXIT_GROUP": 231,
            # Open flags
            "O_RDONLY": 0,
            "O_WRONLY": 1,
            "O_RDWR": 2,
            "O_CREAT": 64,
            "O_TRUNC": 512,
            "O_APPEND": 1024,
            # mmap flags
            "PROT_NONE": 0,
            "PROT_READ": 1,
            "PROT_WRITE": 2,
            "PROT_EXEC": 4,
            "MAP_SHARED": 1,
            "MAP_PRIVATE": 2,
            "MAP_ANONYMOUS": 32,
            "MAP_FIXED": 16,
        }

    def compile_and_link(self, code: str, input_name: str, cache_dir: Path, **options) -> Path:
        """Compile and link x86_64 assembly to ELF executable."""
        import subprocess
        
        asm_path = cache_dir / f"{input_name}.s"
        obj_path = cache_dir / f"{input_name}.o"
        exe_path = cache_dir / input_name
        link_artifacts = [Path(path) for path in options.get("link_artifacts", [])]
        static_artifacts = [str(path) for path in link_artifacts if ".so" not in path.name]
        shared_artifacts = [str(path) for path in link_artifacts if ".so" in path.name]
        
        asm_path.write_text(code)
        
        subprocess.run(["as", str(asm_path), "-o", str(obj_path)], check=True)
        if shared_artifacts:
            dynamic_linker = None
            for candidate in (
                Path("/usr/lib64/ld-linux-x86-64.so.2"),
                Path("/lib64/ld-linux-x86-64.so.2"),
            ):
                if candidate.exists():
                    dynamic_linker = candidate
                    break
            if dynamic_linker is None:
                raise RuntimeError("Could not find the x86_64 Linux dynamic linker for shared-library linking")

            command = ["ld", "-e", "_start", "--gc-sections", "--dynamic-linker", str(dynamic_linker), str(obj_path)]
            if static_artifacts:
                command.extend(["--start-group", *static_artifacts, "--end-group"])
            command.extend(shared_artifacts)
        else:
            command = ["ld", "-static", "-e", "_start", "--gc-sections", str(obj_path)]
            if static_artifacts:
                command.extend(["--start-group", *static_artifacts, "--end-group"])
        command.extend(["-o", str(exe_path)])
        subprocess.run(command, check=True)
        
        return exe_path
    
    def run(self, output_path: PathLike, args: list[str], options: RunOptions | None = None) -> int | None:
        """Run the compiled executable."""
        import subprocess
        output_path = Path(output_path)
        if options is None:
            options = RunOptions()
        env = sdl_desktop.apply_run_hook(
            input_file=options.input_file,
            output_path=output_path,
            link_artifacts=options.link_artifacts,
            env=options.env,
        )
        result = subprocess.run([str(output_path)] + args, env=env)
        return result.returncode
    
    def get_compile_message(self, output_path: Path, **options) -> str:
        """Get compilation success message."""
        return f"Compiled: {output_path}"
