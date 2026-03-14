"""
RISC-V backend for udewy.

Generates GNU assembler syntax targeting RISC-V 64-bit Linux with LP64 ABI.
"""

from os import PathLike
from pathlib import Path

from .. import t0
from .common import Backend, CORE_INTRINSIC_ARITIES, LINUX_SYSCALL_INTRINSIC_ARITIES

class RiscvBackend(Backend):
    """
    RISC-V code generator implementing the Backend protocol.
    
    Value stack model:
    - Top of stack is always in a0 after an expression
    - save_value() pushes a0 to physical stack
    - restore_value() pops from physical stack to a0
    - Binary operators save left, compute right, then operate
    
    Calling convention (RISC-V LP64):
    - Arguments: a0-a7 (8 registers)
    - Return value: a0
    - Callee-saved: s0-s11, ra
    - Stack pointer: sp (16-byte aligned)
    
    Syscall convention:
    - Syscall number in a7
    - Arguments in a0-a5
    - Result in a0
    """
    _ARG_REGS = ["a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7"]
    _VALUE_CACHE_REGS = ["s2", "s3", "s4"]
    
    def __init__(self) -> None:
        self._code: list[str] = []
        self._data: list[str] = []
        self._next_label: int = 0
        
        # Function state
        self._current_fn_epilogue: str = ""
        self._stack_offset: int = -64  # Start after callee-saved area
        self._param_slots: list[int] = []
        self._saved_depth: int = 0
        self._spilled_depth: int = 0
        
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
        self._code.append("    " + instr)
    
    def _emit_label(self, label: str) -> None:
        """Emit a label."""
        self._code.append(label + ":")
    
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

    def _save_reg(self, reg: str) -> None:
        if self._spilled_depth > 0:
            self._emit("addi sp, sp, -16")
            self._emit(f"sd {reg}, 0(sp)")
            self._spilled_depth += 1
        elif self._saved_depth < len(self._VALUE_CACHE_REGS):
            self._emit(f"mv {self._VALUE_CACHE_REGS[self._saved_depth]}, {reg}")
        else:
            for cache_reg in self._VALUE_CACHE_REGS[:self._saved_depth]:
                self._emit("addi sp, sp, -16")
                self._emit(f"sd {cache_reg}, 0(sp)")
            self._emit("addi sp, sp, -16")
            self._emit(f"sd {reg}, 0(sp)")
            self._spilled_depth = self._saved_depth + 1
        self._saved_depth += 1

    def _pop_saved_into(self, reg: str) -> None:
        self._saved_depth -= 1
        if self._spilled_depth > 0:
            self._emit(f"ld {reg}, 0(sp)")
            self._emit("addi sp, sp, 16")
            self._spilled_depth -= 1
        elif self._saved_depth < len(self._VALUE_CACHE_REGS):
            cache_reg = self._VALUE_CACHE_REGS[self._saved_depth]
            if cache_reg != reg:
                self._emit(f"mv {reg}, {cache_reg}")
    
    def _prepare_call_args(self, num_args: int, fn_reg: str | None = None) -> int:
        reg_count = min(num_args, len(self._ARG_REGS))
        stack_count = num_args - reg_count
        stack_bytes = ((stack_count * 8) + 15) & -16
        consumed_values = num_args + (1 if fn_reg is not None else 0)

        if self._spilled_depth > 0:
            self._emit("mv t6, sp")
            if stack_bytes > 0:
                self._emit(f"addi sp, sp, -{stack_bytes}")
                for offset in range(stack_count):
                    src_offset = (stack_count - 1 - offset) * 16
                    self._emit(f"ld t0, {src_offset}(t6)")
                    self._emit(f"sd t0, {offset * 8}(sp)")

            for reg_idx in range(reg_count - 1, -1, -1):
                src_offset = (stack_count + (reg_count - 1 - reg_idx)) * 16
                self._emit(f"ld {self._ARG_REGS[reg_idx]}, {src_offset}(t6)")

            if fn_reg is not None:
                self._emit(f"ld {fn_reg}, {num_args * 16}(t6)")

            self._saved_depth -= consumed_values
            self._spilled_depth -= consumed_values
            return stack_bytes + consumed_values * 16

        if stack_bytes > 0:
            self._emit(f"addi sp, sp, -{stack_bytes}")
            for offset in range(stack_count - 1, -1, -1):
                self._pop_saved_into("t0")
                self._emit(f"sd t0, {offset * 8}(sp)")

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
    
    def finish_module(self) -> str:
        """Finalize and return the generated assembly."""
        output = []
        output.append(".text")
        output.append(".globl _start")
        output.append("")
        
        # Emit _start entry point
        output.append("_start:")
        output.append(".option push")
        output.append(".option norelax")
        output.append("    la gp, __global_pointer$")  # init global pointer
        output.append(".option pop")
        output.append("    li s0, 0")               # clear frame pointer
        output.append("    ld a0, 0(sp)")           # argc
        output.append("    addi a1, sp, 8")         # argv
        output.append("    andi sp, sp, -16")       # align stack
        output.append("    call __main__")
        output.append("    li a7, 93")              # exit syscall
        output.append("    ecall")
        output.append("")
        
        output.extend(self._code)
        output.append("")
        output.append(".data")
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
        
        self._emit_data_label(label)
        self._emit_data(f"    .dword {len(content)}")
        if len(content) > 0:
            bytes_str = ", ".join(str(b) for b in content)
            self._emit_data(f"    .byte {bytes_str}")
        
        return label_id
    
    def intern_array(self, elements: list[int | str]) -> int:
        """Add an array constant to the data section."""
        label_id = self._next_label
        label = self._new_label("arr")
        self._array_labels[label_id] = label
        
        self._emit_data_label(label)
        self._emit_data(f"    .dword {len(elements)}")
        for elem in elements:
            self._emit_data(f"    .dword {elem}")
        
        return label_id
    
    def define_global(self, name_id: int, value: int | str) -> int:
        """Define a global variable."""
        label_id = self._next_label
        label = self._new_label("global")
        self._global_labels[label_id] = label
        
        self._emit_data_label(label)
        self._emit_data(f"    .dword {value}")
        
        return label_id

    def intern_static(self, size: int) -> int:
        """Add a zero-initialized static storage block to the data section."""
        label_id = self._next_label
        label = self._new_label("static")
        self._static_labels[label_id] = label

        self._emit_data_label(label)
        if size > 0:
            self._emit_data(f"    .zero {size}")

        return label_id
    
    def push_string_ref(self, label_id: int) -> None:
        """Push address of string data onto value stack."""
        label = self._string_labels[label_id]
        self._emit(f"la a0, {label}")
        self._emit("addi a0, a0, 8")

    def push_array_ref(self, label_id: int) -> None:
        """Push address of array data onto value stack."""
        label = self._array_labels[label_id]
        self._emit(f"la a0, {label}")
        self._emit("addi a0, a0, 8")
    
    def push_global_ref(self, label_id: int) -> None:
        """Push address of global onto value stack."""
        label = self._global_labels[label_id]
        self._emit(f"la a0, {label}")

    def push_static_ref(self, label_id: int) -> None:
        """Push address of raw static storage onto value stack."""
        label = self._static_labels[label_id]
        self._emit(f"la a0, {label}")
    
    def load_global(self, label_id: int) -> None:
        """Load value of global onto value stack."""
        label = self._global_labels[label_id]
        self._emit(f"la t0, {label}")
        self._emit("ld a0, 0(t0)")
    
    def store_global(self, label_id: int) -> None:
        """Pop value from stack and store to global."""
        label = self._global_labels[label_id]
        self._emit(f"la t0, {label}")
        self._emit("sd a0, 0(t0)")

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
    
    def declare_function(self, name_id: int, num_params: int) -> int:
        """Declare a function."""
        label_id = self._next_label
        label = self._new_label("fn")
        self._fn_labels[label_id] = label
        return label_id
    
    def begin_function(self, label_id: int, name: str, param_count: int, is_main: bool) -> None:
        """Begin function definition."""
        label = self._fn_labels[label_id]
        self._saved_depth = 0
        self._spilled_depth = 0
        
        if is_main:
            self._emit_label("__main__")
        self._emit_label(label)
        
        # Prologue - allocate frame (1024 bytes for locals + callee-saved)
        self._emit("addi sp, sp, -1024")
        
        # Save callee-saved registers and return address
        self._emit("sd ra, 1016(sp)")
        self._emit("sd s0, 1008(sp)")
        self._emit("sd s1, 1000(sp)")
        self._emit("sd s2, 992(sp)")
        self._emit("sd s3, 984(sp)")
        self._emit("sd s4, 976(sp)")
        self._emit("sd s5, 968(sp)")
        self._emit("sd s6, 960(sp)")
        self._emit("sd s7, 952(sp)")
        self._emit("sd s8, 944(sp)")
        self._emit("sd s9, 936(sp)")
        self._emit("sd s10, 928(sp)")
        self._emit("sd s11, 920(sp)")
        
        # Set frame pointer
        self._emit("addi s0, sp, 1024")
        self._emit("mv s1, sp")
        
        # Set up parameters - copy from arg registers to stack
        self._param_slots = []
        self._stack_offset = -64  # After callee-saved area
        
        for i in range(param_count):
            slot = self._stack_offset
            self._param_slots.append(slot)
            
            if i < 8:
                self._emit(f"sd {self._ARG_REGS[i]}, {slot}(s0)")
            else:
                # Load from caller's stack frame
                caller_offset = (i - 8) * 8
                self._emit(f"ld t0, {caller_offset}(s0)")
                self._emit(f"sd t0, {slot}(s0)")
            
            self._stack_offset -= 8
        
        self._current_fn_epilogue = f"{label}_epilogue"
    
    def end_function(self) -> None:
        """End function definition."""
        self._emit_label(self._current_fn_epilogue)
        
        # Restore callee-saved registers
        self._emit("ld ra, 1016(sp)")
        self._emit("ld s0, 1008(sp)")
        self._emit("ld s1, 1000(sp)")
        self._emit("ld s2, 992(sp)")
        self._emit("ld s3, 984(sp)")
        self._emit("ld s4, 976(sp)")
        self._emit("ld s5, 968(sp)")
        self._emit("ld s6, 960(sp)")
        self._emit("ld s7, 952(sp)")
        self._emit("ld s8, 944(sp)")
        self._emit("ld s9, 936(sp)")
        self._emit("ld s10, 928(sp)")
        self._emit("ld s11, 920(sp)")
        
        # Deallocate frame and return
        self._emit("addi sp, sp, 1024")
        self._emit("ret")
    
    def load_param(self, index: int) -> None:
        """Push parameter value onto the value stack."""
        slot = self._param_slots[index]
        self._emit(f"ld a0, {slot}(s0)")

    def alloc_local(self) -> int:
        """Allocate a local variable slot."""
        slot = self._stack_offset
        self._stack_offset -= 8
        return slot

    def load_local(self, slot: int) -> None:
        """Push local variable value onto the value stack."""
        self._emit(f"ld a0, {slot}(s0)")

    def store_local(self, slot: int) -> None:
        """Pop value from stack and store to local variable."""
        self._emit(f"sd a0, {slot}(s0)")
    
    # ========================================================================
    # Value stack operations
    # ========================================================================
    
    def push_const_i64(self, value: int) -> None:
        """Push a 64-bit integer constant onto the value stack."""
        if -2048 <= value <= 2047:
            self._emit(f"li a0, {value}")
        else:
            # Load large constant via lui/addi sequence
            self._emit(f"li a0, {value}")
    
    def push_void(self) -> None:
        """Push void (zero) onto the value stack."""
        self._emit("li a0, 0")
    
    def push_fn_ref(self, label_id: int) -> None:
        """Push address of function onto the value stack."""
        label = self._fn_labels[label_id]
        self._emit(f"la a0, {label}")
    
    def dup_value(self) -> None:
        """Duplicate the top value on the stack."""
        self._save_reg("a0")
    
    def pop_value(self) -> None:
        """Discard the top value on the stack."""
        pass
    
    def save_value(self) -> None:
        """Save the top value to physical stack."""
        self._save_reg("a0")
    
    def restore_value(self) -> None:
        """Restore a previously saved value."""
        self._pop_saved_into("a0")
    
    # ========================================================================
    # Operators
    # ========================================================================
    
    def unary_op(self, op_kind: t0.Kind) -> None:
        """Apply unary operator to top of stack."""
        if op_kind == t0.Kind.TK_MINUS:
            self._emit("neg a0, a0")
        elif op_kind == t0.Kind.TK_NOT:
            self._emit("not a0, a0")
    
    def binary_op(self, op_kind: t0.Kind) -> None:
        """Apply binary operator to top two values on stack."""
        # Right operand in a0, left on stack
        self._emit("mv t0, a0")        # right in t0
        self._pop_saved_into("a0")     # left in a0
        
        if op_kind == t0.Kind.TK_PLUS:
            self._emit("add a0, a0, t0")
        elif op_kind == t0.Kind.TK_MINUS:
            self._emit("sub a0, a0, t0")
        elif op_kind == t0.Kind.TK_MUL:
            self._emit("mul a0, a0, t0")
        elif op_kind == t0.Kind.TK_IDIV:
            self._emit("div a0, a0, t0")
        elif op_kind == t0.Kind.TK_MOD:
            self._emit("rem a0, a0, t0")
        elif op_kind == t0.Kind.TK_LEFT_SHIFT:
            self._emit("sll a0, a0, t0")
        elif op_kind == t0.Kind.TK_RIGHT_SHIFT:
            self._emit("srl a0, a0, t0")
        elif op_kind == t0.Kind.TK_AND:
            self._emit("and a0, a0, t0")
        elif op_kind == t0.Kind.TK_OR:
            self._emit("or a0, a0, t0")
        elif op_kind == t0.Kind.TK_XOR:
            self._emit("xor a0, a0, t0")
        elif op_kind == t0.Kind.TK_EQ:
            self._emit("sub t1, a0, t0")
            self._emit("seqz a0, t1")
            self._emit("neg a0, a0")
        elif op_kind == t0.Kind.TK_NOT_EQ:
            self._emit("sub t1, a0, t0")
            self._emit("snez a0, t1")
            self._emit("neg a0, a0")
        elif op_kind == t0.Kind.TK_GT:
            self._emit("sgt a0, a0, t0")
            self._emit("neg a0, a0")
        elif op_kind == t0.Kind.TK_LT:
            self._emit("slt a0, a0, t0")
            self._emit("neg a0, a0")
        elif op_kind == t0.Kind.TK_GT_EQ:
            self._emit("slt a0, a0, t0")
            self._emit("seqz a0, a0")
            self._emit("neg a0, a0")
        elif op_kind == t0.Kind.TK_LT_EQ:
            self._emit("sgt a0, a0, t0")
            self._emit("seqz a0, a0")
            self._emit("neg a0, a0")
    
    def pipe_call(self) -> None:
        """Handle pipe operator: call function with left as arg."""
        self._emit("mv t5, a0")      # save fn ptr
        self._pop_saved_into("a0")   # arg1
        self._emit("jalr ra, t5, 0")
    
    # ========================================================================
    # Memory operations
    # ========================================================================
    
    def load_mem(self, width: int, signed: bool = False) -> None:
        """Load from memory address in a0."""
        if width == 64:
            self._emit("ld a0, 0(a0)")
        elif width == 32:
            if signed:
                self._emit("lw a0, 0(a0)")
            else:
                self._emit("lwu a0, 0(a0)")
        elif width == 16:
            if signed:
                self._emit("lh a0, 0(a0)")
            else:
                self._emit("lhu a0, 0(a0)")
        elif width == 8:
            if signed:
                self._emit("lb a0, 0(a0)")
            else:
                self._emit("lbu a0, 0(a0)")
    
    def store_mem(self, width: int) -> None:
        """Store to memory. Stack: [value addr] -> pushes 0."""
        self._pop_saved_into("t0")   # value
        if width == 64:
            self._emit("sd t0, 0(a0)")
        elif width == 32:
            self._emit("sw t0, 0(a0)")
        elif width == 16:
            self._emit("sh t0, 0(a0)")
        elif width == 8:
            self._emit("sb t0, 0(a0)")
        self._emit("li a0, 0")
    
    def signed_shr(self) -> None:
        """Signed (arithmetic) right shift. Stack: [value bits] -> result."""
        self._emit("mv t0, a0")
        self._pop_saved_into("a0")
        self._emit("sra a0, a0, t0")

    def unsigned_idiv(self) -> None:
        """Unsigned division. Stack: [left right] -> quotient."""
        self._emit("mv t0, a0")
        self._pop_saved_into("a0")
        self._emit("divu a0, a0, t0")

    def unsigned_mod(self) -> None:
        """Unsigned remainder. Stack: [left right] -> remainder."""
        self._emit("mv t0, a0")
        self._pop_saved_into("a0")
        self._emit("remu a0, a0, t0")

    def unsigned_cmp(self, kind: str) -> None:
        """Unsigned comparison returning udewy booleans."""
        self._emit("mv t0, a0")
        self._pop_saved_into("a0")
        if kind == "gt":
            self._emit("sltu a0, t0, a0")
        elif kind == "lt":
            self._emit("sltu a0, a0, t0")
        elif kind == "gte":
            self._emit("sltu a0, a0, t0")
            self._emit("seqz a0, a0")
        elif kind == "lte":
            self._emit("sltu a0, t0, a0")
            self._emit("seqz a0, a0")
        self._emit("neg a0, a0")

    def alloca(self) -> None:
        """Allocate temporary stack storage and return its address."""
        self._emit("addi a0, a0, 7")
        self._emit("andi a0, a0, -8")
        self._emit("mv t0, s1")
        self._emit("add s1, s1, a0")
        self._emit("mv a0, t0")
    
    # ========================================================================
    # Calls
    # ========================================================================
    
    def call_direct(self, label_id: int, num_args: int) -> None:
        """Call a function directly by label."""
        stack_bytes = self._prepare_call_args(num_args)
        label = self._fn_labels[label_id]
        self._emit(f"call {label}")
        if stack_bytes > 0:
            self._emit(f"addi sp, sp, {stack_bytes}")
    
    def call_indirect(self, num_args: int) -> None:
        """Call a function indirectly via pointer."""
        stack_bytes = self._prepare_call_args(num_args, "t5")
        self._emit("jalr ra, t5, 0")
        if stack_bytes > 0:
            self._emit(f"addi sp, sp, {stack_bytes}")

    def max_call_args(self) -> int | None:
        return None
    
    def syscall(self, num_args: int) -> None:
        """Invoke a syscall using ecall."""
        # Args pushed in order: syscall_num, arg1, arg2, ...
        # Last arg is in a0, rest on stack (syscall_num is deepest)
        # Need: a7=syscall_num, a0-a5=args
        if num_args == 1:
            # Only syscall_num in a0
            self._emit("mv a7, a0")
            self._emit("ecall")
        elif num_args == 2:
            # a0=arg1, stack=[syscall_num]
            self._emit("mv t0, a0")      # save arg1
            self._pop_saved_into("a7")   # syscall_num
            self._emit("mv a0, t0")
            self._emit("ecall")
        elif num_args == 3:
            # a0=arg2, stack=[syscall_num, arg1]
            self._emit("mv a1, a0")      # arg2 -> a1
            self._pop_saved_into("a0")   # arg1 -> a0
            self._pop_saved_into("a7")   # syscall_num -> a7
            self._emit("ecall")
        elif num_args == 4:
            # a0=arg3, stack=[syscall_num, arg1, arg2]
            self._emit("mv a2, a0")      # arg3 -> a2
            self._pop_saved_into("a1")   # arg2 -> a1
            self._pop_saved_into("a0")   # arg1 -> a0
            self._pop_saved_into("a7")   # syscall_num -> a7
            self._emit("ecall")
        elif num_args == 5:
            # a0=arg4, stack=[syscall_num, arg1, arg2, arg3]
            self._emit("mv a3, a0")
            self._pop_saved_into("a2")
            self._pop_saved_into("a1")
            self._pop_saved_into("a0")
            self._pop_saved_into("a7")
            self._emit("ecall")
        elif num_args == 6:
            # a0=arg5, stack=[syscall_num, arg1, arg2, arg3, arg4]
            self._emit("mv a4, a0")
            self._pop_saved_into("a3")
            self._pop_saved_into("a2")
            self._pop_saved_into("a1")
            self._pop_saved_into("a0")
            self._pop_saved_into("a7")
            self._emit("ecall")
        elif num_args == 7:
            # a0=arg6, stack=[syscall_num, arg1, arg2, arg3, arg4, arg5]
            self._emit("mv a5, a0")
            self._pop_saved_into("a4")
            self._pop_saved_into("a3")
            self._pop_saved_into("a2")
            self._pop_saved_into("a1")
            self._pop_saved_into("a0")
            self._pop_saved_into("a7")
            self._emit("ecall")
    
    # ========================================================================
    # Control flow
    # ========================================================================
    
    def begin_if(self) -> None:
        """Begin an if statement."""
        else_label = self._new_label("else")
        end_label = self._new_label("if_end")
        self._if_stack.append((else_label, end_label, False))
        
        self._emit("beqz a0, " + else_label)
    
    def begin_else(self) -> None:
        """Begin the else branch."""
        else_label, end_label, _ = self._if_stack[-1]
        self._if_stack[-1] = (else_label, end_label, True)
        self._emit(f"j {end_label}")
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
        self._emit(f"beqz a0, {end_label}")
    
    def end_loop(self) -> None:
        """End a loop."""
        start_label, end_label = self._loop_stack.pop()
        self._emit(f"j {start_label}")
        self._emit_label(end_label)
    
    def emit_break(self) -> None:
        """Emit a break statement."""
        _, end_label = self._loop_stack[-1]
        self._emit(f"j {end_label}")
    
    def emit_continue(self) -> None:
        """Emit a continue statement."""
        start_label, _ = self._loop_stack[-1]
        self._emit(f"j {start_label}")
    
    def emit_return(self) -> None:
        """Emit a return statement."""
        self._emit(f"j {self._current_fn_epilogue}")
    
    # ========================================================================
    # Intrinsics
    # ========================================================================
    
    _INTRINSIC_ARITIES = CORE_INTRINSIC_ARITIES | LINUX_SYSCALL_INTRINSIC_ARITIES
    
    def is_intrinsic(self, name: str) -> bool:
        """Check if name is an intrinsic supported by this backend."""
        return name in self._INTRINSIC_ARITIES

    def intrinsic_arity(self, name: str) -> int | None:
        """Return the expected arity for a supported intrinsic."""
        return self._INTRINSIC_ARITIES.get(name)
    
    def emit_intrinsic(self, name: str, num_args: int) -> None:
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
        elif name.startswith("__syscall"):
            self.syscall(num_args)
    
    def get_builtin_constants(self) -> dict[str, int]:
        """Return RISC-V Linux syscall numbers and common constants."""
        return {
            # File descriptors
            "STDIN": 0,
            "STDOUT": 1,
            "STDERR": 2,
            # Syscall numbers (RISC-V Linux)
            "SYS_GETCWD": 17,
            "SYS_DUP": 23,
            "SYS_DUP3": 24,
            "SYS_IOCTL": 29,
            "SYS_MKDIRAT": 34,
            "SYS_UNLINKAT": 35,
            "SYS_FTRUNCATE": 46,
            "SYS_FACCESSAT": 48,
            "SYS_CHDIR": 49,
            "SYS_OPENAT": 56,
            "SYS_CLOSE": 57,
            "SYS_PIPE2": 59,
            "SYS_LSEEK": 62,
            "SYS_READ": 63,
            "SYS_WRITE": 64,
            "SYS_READV": 65,
            "SYS_WRITEV": 66,
            "SYS_FSTAT": 80,
            "SYS_EXIT": 93,
            "SYS_EXIT_GROUP": 94,
            "SYS_KILL": 129,
            "SYS_GETPID": 172,
            "SYS_GETUID": 174,
            "SYS_GETEUID": 175,
            "SYS_GETGID": 176,
            "SYS_GETEGID": 177,
            "SYS_BRK": 214,
            "SYS_MUNMAP": 215,
            "SYS_CLONE": 220,
            "SYS_EXECVE": 221,
            "SYS_MMAP": 222,
            "SYS_WAIT4": 260,
            # Open flags (same across Linux architectures)
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
            # AT_FDCWD for *at syscalls
            "AT_FDCWD": -100,
        }
    
    def compile_and_link(self, code: str, input_name: str, cache_dir: Path, **options) -> Path:
        """Compile and link RISC-V assembly to executable."""
        import subprocess
        
        asm_path = cache_dir / f"{input_name}.s"
        obj_path = cache_dir / f"{input_name}.o"
        exe_path = cache_dir / input_name
        
        asm_path.write_text(code)
        
        # Try different toolchain prefixes
        for prefix in ["riscv64-linux-gnu-", "riscv64-elf-", "riscv64-unknown-elf-"]:
            try:
                subprocess.run([f"{prefix}as", str(asm_path), "-o", str(obj_path)], check=True)
                subprocess.run([f"{prefix}ld", str(obj_path), "-o", str(exe_path)], check=True)
                return exe_path
            except FileNotFoundError:
                continue
        
        raise RuntimeError(
            "RISC-V toolchain not found.\n"
            f"Install one of: riscv64-linux-gnu-*, riscv64-elf-*\n"
            f"Assembly file generated at: {asm_path}"
        )
    
    def run(self, output_path: PathLike, args: list[str], **options) -> int | None:
        """Run the compiled executable via QEMU."""
        import subprocess
        output_path = Path(output_path)
        result = subprocess.run(["qemu-riscv64", str(output_path)] + args)
        return result.returncode
    
    def get_compile_message(self, output_path: Path, **options) -> str:
        """Get compilation success message."""
        return f"Compiled: {output_path}"
