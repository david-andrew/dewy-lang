"""
ARM backend for udewy.

Generates GNU assembler syntax targeting AArch64 Linux with AAPCS64 ABI.
"""

from os import PathLike
from pathlib import Path

from .. import t0
from .common import Backend

class ArmBackend(Backend):
    """
    AArch64 code generator implementing the Backend protocol.
    
    Value stack model:
    - Top of stack is always in x0 after an expression
    - save_value() pushes x0 to physical stack
    - restore_value() pops from physical stack to x0
    - Binary operators save left, compute right, then operate
    
    Calling convention (AAPCS64):
    - Arguments: x0-x7 (8 registers)
    - Return value: x0
    - Callee-saved: x19-x28, fp (x29), lr (x30)
    - Stack pointer: sp (16-byte aligned)
    
    Syscall convention:
    - Syscall number in x8
    - Arguments in x0-x5
    - Result in x0
    - svc #0 instruction
    """
    
    def __init__(self) -> None:
        self._code: list[str] = []
        self._data: list[str] = []
        self._next_label: int = 0
        
        # Function state
        self._current_fn_epilogue: str = ""
        self._stack_offset: int = -96  # Start after callee-saved area
        self._param_slots: list[int] = []
        
        # Control flow state
        self._if_stack: list[tuple[str, str, bool]] = []
        self._loop_stack: list[tuple[str, str]] = []
        
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
        output.append("    mov x29, xzr")           # clear frame pointer
        output.append("    ldr x0, [sp]")           # argc
        output.append("    add x1, sp, #8")         # argv
        output.append("    mov x9, sp")             # align stack to 16 bytes
        output.append("    bic x9, x9, #15")
        output.append("    mov sp, x9")
        output.append("    bl __main__")
        output.append("    mov x8, #93")            # exit syscall
        output.append("    svc #0")
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
        self._emit_data(f"    .xword {len(content)}")
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
        self._emit_data(f"    .xword {len(elements)}")
        for elem in elements:
            self._emit_data(f"    .xword {elem}")
        
        return label_id
    
    def define_global(self, name_id: int, value: int | str) -> int:
        """Define a global variable."""
        label_id = self._next_label
        label = self._new_label("global")
        self._global_labels[label_id] = label
        
        self._emit_data_label(label)
        self._emit_data(f"    .xword {value}")
        
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
        self._emit(f"adrp x0, {label}")
        self._emit(f"add x0, x0, :lo12:{label}")
        self._emit("add x0, x0, #8")
    
    def push_array_ref(self, label_id: int) -> None:
        """Push address of array data onto value stack."""
        label = self._array_labels[label_id]
        self._emit(f"adrp x0, {label}")
        self._emit(f"add x0, x0, :lo12:{label}")
        self._emit("add x0, x0, #8")
    
    def push_global_ref(self, label_id: int) -> None:
        """Push address of global onto value stack."""
        label = self._global_labels[label_id]
        self._emit(f"adrp x0, {label}")
        self._emit(f"add x0, x0, :lo12:{label}")

    def push_static_ref(self, label_id: int) -> None:
        """Push address of raw static storage onto value stack."""
        label = self._static_labels[label_id]
        self._emit(f"adrp x0, {label}")
        self._emit(f"add x0, x0, :lo12:{label}")
    
    def load_global(self, label_id: int) -> None:
        """Load value of global onto value stack."""
        label = self._global_labels[label_id]
        self._emit(f"adrp x9, {label}")
        self._emit(f"add x9, x9, :lo12:{label}")
        self._emit("ldr x0, [x9]")
    
    def store_global(self, label_id: int) -> None:
        """Pop value from stack and store to global."""
        label = self._global_labels[label_id]
        self._emit(f"adrp x9, {label}")
        self._emit(f"add x9, x9, :lo12:{label}")
        self._emit("str x0, [x9]")

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
        
        if is_main:
            self._emit_label("__main__")
        self._emit_label(label)
        
        # Prologue - save fp/lr with pre-index, then allocate frame
        # Frame layout (1024 bytes total):
        #   sp+0 to sp+80: callee-saved registers (x19-x28)
        #   sp+80 to sp+96: fp (x29), lr (x30)
        #   sp+96 to sp+1024: locals (928 bytes)
        self._emit("stp x29, x30, [sp, #-96]!")   # save fp, lr and decrement sp by 96
        self._emit("stp x27, x28, [sp, #80]")
        self._emit("stp x25, x26, [sp, #64]")
        self._emit("stp x23, x24, [sp, #48]")
        self._emit("stp x21, x22, [sp, #32]")
        self._emit("stp x19, x20, [sp, #16]")
        
        # Allocate space for locals
        self._emit("sub sp, sp, #928")
        
        # Set frame pointer to base of frame
        self._emit("add x29, sp, #928")
        self._emit("mov x19, sp")
        
        # Set up parameters - copy from arg registers to stack
        # Parameters stored at negative offsets from x29
        arg_regs = ["x0", "x1", "x2", "x3", "x4", "x5", "x6", "x7"]
        self._param_slots = []
        self._stack_offset = -16  # Start below saved regs area
        
        for i in range(param_count):
            slot = self._stack_offset
            self._param_slots.append(slot)
            
            if i < 8:
                self._emit(f"str {arg_regs[i]}, [x29, #{slot}]")
            else:
                # Load from caller's stack frame
                caller_offset = (i - 8 + 12) * 8  # +12 to skip saved regs (6 pairs)
                self._emit(f"ldr x9, [x29, #{96 + caller_offset}]")
                self._emit(f"str x9, [x29, #{slot}]")
            
            self._stack_offset -= 8
        
        self._current_fn_epilogue = f"{label}_epilogue"
    
    def end_function(self) -> None:
        """End function definition."""
        self._emit_label(self._current_fn_epilogue)
        
        # Deallocate locals
        self._emit("add sp, sp, #928")
        
        # Restore callee-saved registers
        self._emit("ldp x19, x20, [sp, #16]")
        self._emit("ldp x21, x22, [sp, #32]")
        self._emit("ldp x23, x24, [sp, #48]")
        self._emit("ldp x25, x26, [sp, #64]")
        self._emit("ldp x27, x28, [sp, #80]")
        self._emit("ldp x29, x30, [sp], #96")     # restore fp, lr and increment sp
        
        self._emit("ret")
    
    def load_param(self, index: int) -> None:
        """Push parameter value onto the value stack."""
        slot = self._param_slots[index]
        self._emit(f"ldr x0, [x29, #{slot}]")
    
    def alloc_local(self) -> int:
        """Allocate a local variable slot."""
        slot = self._stack_offset
        self._stack_offset -= 8
        return slot

    def load_local(self, slot: int) -> None:
        """Push local variable value onto the value stack."""
        self._emit(f"ldr x0, [x29, #{slot}]")

    def store_local(self, slot: int) -> None:
        """Pop value from stack and store to local variable."""
        self._emit(f"str x0, [x29, #{slot}]")
    
    # ========================================================================
    # Value stack operations
    # ========================================================================
    
    def push_const_i64(self, value: int) -> None:
        """Push a 64-bit integer constant onto the value stack."""
        if 0 <= value <= 65535:
            self._emit(f"mov x0, #{value}")
        elif -65536 <= value < 0:
            self._emit(f"mov x0, #{value}")
        else:
            # Load large constant via movz/movk sequence
            self._emit(f"ldr x0, ={value}")
    
    def push_void(self) -> None:
        """Push void (zero) onto the value stack."""
        self._emit("mov x0, #0")
    
    def push_fn_ref(self, label_id: int) -> None:
        """Push address of function onto the value stack."""
        label = self._fn_labels[label_id]
        self._emit(f"adrp x0, {label}")
        self._emit(f"add x0, x0, :lo12:{label}")
    
    def dup_value(self) -> None:
        """Duplicate the top value on the stack."""
        pass
    
    def pop_value(self) -> None:
        """Discard the top value on the stack."""
        pass
    
    def save_value(self) -> None:
        """Save the top value to physical stack."""
        self._emit("str x0, [sp, #-16]!")
    
    def restore_value(self) -> None:
        """Restore a previously saved value."""
        self._emit("ldr x0, [sp], #16")
    
    # ========================================================================
    # Operators
    # ========================================================================
    
    def unary_op(self, op_kind: int) -> None:
        """Apply unary operator to top of stack."""
        if op_kind == t0.TK_MINUS:
            self._emit("neg x0, x0")
        elif op_kind == t0.TK_NOT:
            self._emit("mvn x0, x0")
    
    def binary_op(self, op_kind: int) -> None:
        """Apply binary operator to top two values on stack."""
        # Right operand in x0, left on stack
        self._emit("mov x9, x0")       # right in x9
        self._emit("ldr x0, [sp], #16")  # left in x0, pop
        
        if op_kind == t0.TK_PLUS:
            self._emit("add x0, x0, x9")
        elif op_kind == t0.TK_MINUS:
            self._emit("sub x0, x0, x9")
        elif op_kind == t0.TK_MUL:
            self._emit("mul x0, x0, x9")
        elif op_kind == t0.TK_IDIV:
            self._emit("sdiv x0, x0, x9")
        elif op_kind == t0.TK_MOD:
            self._emit("sdiv x10, x0, x9")
            self._emit("msub x0, x10, x9, x0")
        elif op_kind == t0.TK_LEFT_SHIFT:
            self._emit("lsl x0, x0, x9")
        elif op_kind == t0.TK_RIGHT_SHIFT:
            self._emit("lsr x0, x0, x9")
        elif op_kind == t0.TK_AND:
            self._emit("and x0, x0, x9")
        elif op_kind == t0.TK_OR:
            self._emit("orr x0, x0, x9")
        elif op_kind == t0.TK_XOR:
            self._emit("eor x0, x0, x9")
        elif op_kind == t0.TK_EQ:
            self._emit("cmp x0, x9")
            self._emit("csetm x0, eq")
        elif op_kind == t0.TK_NOT_EQ:
            self._emit("cmp x0, x9")
            self._emit("csetm x0, ne")
        elif op_kind == t0.TK_GT:
            self._emit("cmp x0, x9")
            self._emit("csetm x0, gt")
        elif op_kind == t0.TK_LT:
            self._emit("cmp x0, x9")
            self._emit("csetm x0, lt")
        elif op_kind == t0.TK_GT_EQ:
            self._emit("cmp x0, x9")
            self._emit("csetm x0, ge")
        elif op_kind == t0.TK_LT_EQ:
            self._emit("cmp x0, x9")
            self._emit("csetm x0, le")
    
    def pipe_call(self) -> None:
        """Handle pipe operator: call function with left as arg."""
        self._emit("mov x9, x0")       # save fn ptr
        self._emit("ldr x0, [sp], #16")  # arg1
        self._emit("blr x9")
    
    # ========================================================================
    # Memory operations
    # ========================================================================
    
    def load_mem(self, width: int, signed: bool = False) -> None:
        """Load from memory address in x0."""
        if width == 64:
            self._emit("ldr x0, [x0]")
        elif width == 32:
            if signed:
                self._emit("ldrsw x0, [x0]")
            else:
                self._emit("ldr w0, [x0]")
        elif width == 16:
            if signed:
                self._emit("ldrsh x0, [x0]")
            else:
                self._emit("ldrh w0, [x0]")
        elif width == 8:
            if signed:
                self._emit("ldrsb x0, [x0]")
            else:
                self._emit("ldrb w0, [x0]")
    
    def store_mem(self, width: int) -> None:
        """Store to memory. Stack: [value addr] -> pushes 0."""
        self._emit("ldr x9, [sp], #16")  # value
        if width == 64:
            self._emit("str x9, [x0]")
        elif width == 32:
            self._emit("str w9, [x0]")
        elif width == 16:
            self._emit("strh w9, [x0]")
        elif width == 8:
            self._emit("strb w9, [x0]")
        self._emit("mov x0, #0")
    
    def signed_shr(self) -> None:
        """Signed (arithmetic) right shift. Stack: [value bits] -> result."""
        self._emit("mov x9, x0")
        self._emit("ldr x0, [sp], #16")
        self._emit("asr x0, x0, x9")

    def unsigned_idiv(self) -> None:
        """Unsigned division. Stack: [left right] -> quotient."""
        self._emit("mov x9, x0")
        self._emit("ldr x0, [sp], #16")
        self._emit("udiv x0, x0, x9")

    def unsigned_mod(self) -> None:
        """Unsigned remainder. Stack: [left right] -> remainder."""
        self._emit("mov x9, x0")
        self._emit("ldr x0, [sp], #16")
        self._emit("udiv x10, x0, x9")
        self._emit("msub x0, x10, x9, x0")

    def unsigned_cmp(self, kind: str) -> None:
        """Unsigned comparison returning udewy booleans."""
        self._emit("mov x9, x0")
        self._emit("ldr x0, [sp], #16")
        self._emit("cmp x0, x9")
        if kind == "gt":
            self._emit("csetm x0, hi")
        elif kind == "lt":
            self._emit("csetm x0, lo")
        elif kind == "gte":
            self._emit("csetm x0, hs")
        elif kind == "lte":
            self._emit("csetm x0, ls")

    def alloca(self) -> None:
        """Allocate temporary stack storage and return its address."""
        self._emit("add x0, x0, #7")
        self._emit("and x0, x0, #-8")
        self._emit("mov x9, x19")
        self._emit("add x19, x19, x0")
        self._emit("mov x0, x9")
    
    # ========================================================================
    # Calls
    # ========================================================================
    
    def prepare_args(self, num_args: int) -> None:
        """Pop arguments from stack into registers for a call."""
        regs = ["x0", "x1", "x2", "x3", "x4", "x5", "x6", "x7"]
        for i in range(min(num_args, 8) - 1, -1, -1):
            self._emit(f"ldr {regs[i]}, [sp], #16")
    
    def call_direct(self, label_id: int, num_args: int) -> None:
        """Call a function directly by label."""
        self.prepare_args(num_args)
        label = self._fn_labels[label_id]
        self._emit(f"bl {label}")
    
    def call_indirect(self, num_args: int) -> None:
        """Call a function indirectly via pointer."""
        self.prepare_args(num_args)
        self._emit("ldr x9, [sp], #16")  # fn ptr
        self._emit("blr x9")
    
    def syscall(self, num_args: int) -> None:
        """Invoke a syscall using svc #0."""
        # Args pushed in order: syscall_num, arg1, arg2, ...
        # Last arg is in x0, rest on stack (syscall_num is deepest)
        # Need: x8=syscall_num, x0-x5=args
        if num_args == 1:
            # Only syscall_num in x0
            self._emit("mov x8, x0")
            self._emit("svc #0")
        elif num_args == 2:
            # x0=arg1, stack=[syscall_num]
            self._emit("mov x9, x0")         # save arg1
            self._emit("ldr x8, [sp], #16")  # syscall_num
            self._emit("mov x0, x9")
            self._emit("svc #0")
        elif num_args == 3:
            # x0=arg2, stack=[syscall_num, arg1]
            self._emit("mov x1, x0")         # arg2 -> x1
            self._emit("ldr x0, [sp], #16")  # arg1 -> x0
            self._emit("ldr x8, [sp], #16")  # syscall_num -> x8
            self._emit("svc #0")
        elif num_args == 4:
            # x0=arg3, stack=[syscall_num, arg1, arg2]
            self._emit("mov x2, x0")         # arg3 -> x2
            self._emit("ldr x1, [sp], #16")  # arg2 -> x1
            self._emit("ldr x0, [sp], #16")  # arg1 -> x0
            self._emit("ldr x8, [sp], #16")  # syscall_num -> x8
            self._emit("svc #0")
        elif num_args == 5:
            # x0=arg4, stack=[syscall_num, arg1, arg2, arg3]
            self._emit("mov x3, x0")
            self._emit("ldr x2, [sp], #16")
            self._emit("ldr x1, [sp], #16")
            self._emit("ldr x0, [sp], #16")
            self._emit("ldr x8, [sp], #16")
            self._emit("svc #0")
        elif num_args == 6:
            # x0=arg5, stack=[syscall_num, arg1, arg2, arg3, arg4]
            self._emit("mov x4, x0")
            self._emit("ldr x3, [sp], #16")
            self._emit("ldr x2, [sp], #16")
            self._emit("ldr x1, [sp], #16")
            self._emit("ldr x0, [sp], #16")
            self._emit("ldr x8, [sp], #16")
            self._emit("svc #0")
        elif num_args == 7:
            # x0=arg6, stack=[syscall_num, arg1, arg2, arg3, arg4, arg5]
            self._emit("mov x5, x0")
            self._emit("ldr x4, [sp], #16")
            self._emit("ldr x3, [sp], #16")
            self._emit("ldr x2, [sp], #16")
            self._emit("ldr x1, [sp], #16")
            self._emit("ldr x0, [sp], #16")
            self._emit("ldr x8, [sp], #16")
            self._emit("svc #0")
    
    # ========================================================================
    # Control flow
    # ========================================================================
    
    def begin_if(self) -> None:
        """Begin an if statement."""
        else_label = self._new_label("else")
        end_label = self._new_label("if_end")
        self._if_stack.append((else_label, end_label, False))
        
        self._emit("cbz x0, " + else_label)
    
    def begin_else(self) -> None:
        """Begin the else branch."""
        else_label, end_label, _ = self._if_stack[-1]
        self._if_stack[-1] = (else_label, end_label, True)
        self._emit(f"b {end_label}")
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
        self._emit(f"cbz x0, {end_label}")
    
    def end_loop(self) -> None:
        """End a loop."""
        start_label, end_label = self._loop_stack.pop()
        self._emit(f"b {start_label}")
        self._emit_label(end_label)
    
    def emit_break(self) -> None:
        """Emit a break statement."""
        _, end_label = self._loop_stack[-1]
        self._emit(f"b {end_label}")
    
    def emit_continue(self) -> None:
        """Emit a continue statement."""
        start_label, _ = self._loop_stack[-1]
        self._emit(f"b {start_label}")
    
    def emit_return(self) -> None:
        """Emit a return statement."""
        self._emit(f"b {self._current_fn_epilogue}")
    
    # ========================================================================
    # Intrinsics
    # ========================================================================
    
    _CORE_INTRINSICS = {
        "__load_u8__", "__load_u16__", "__load_u32__", "__load_u64__",
        "__store_u8__", "__store_u16__", "__store_u32__", "__store_u64__",
        "__load_i8__", "__load_i16__", "__load_i32__", "__load_i64__",
        "__store_i8__", "__store_i16__", "__store_i32__", "__store_i64__",
        "__load__", "__store__", "__alloca__", "__static_alloca__",
        "__signed_shr__",
        "__unsigned_idiv__", "__unsigned_mod__",
        "__unsigned_lt__", "__unsigned_gt__", "__unsigned_lte__", "__unsigned_gte__",
    }
    
    _PLATFORM_INTRINSICS = {
        "__syscall0__", "__syscall1__", "__syscall2__", "__syscall3__",
        "__syscall4__", "__syscall5__", "__syscall6__",
    }
    
    def is_intrinsic(self, name: str) -> bool:
        """Check if name is an intrinsic supported by this backend."""
        return name in self._CORE_INTRINSICS or name in self._PLATFORM_INTRINSICS
    
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
        """Return AArch64 Linux syscall numbers and common constants."""
        # AArch64 Linux uses the same syscall numbers as RISC-V Linux
        return {
            # File descriptors
            "STDIN": 0,
            "STDOUT": 1,
            "STDERR": 2,
            # Syscall numbers (AArch64 Linux - same as RISC-V)
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
            # AT_FDCWD for *at syscalls
            "AT_FDCWD": -100,
        }
    
    def compile_and_link(self, code: str, input_name: str, cache_dir: Path, **options) -> Path:
        """Compile and link AArch64 assembly to executable."""
        import subprocess
        
        asm_path = cache_dir / f"{input_name}.s"
        obj_path = cache_dir / f"{input_name}.o"
        exe_path = cache_dir / input_name
        
        asm_path.write_text(code)
        
        # Try different toolchain prefixes
        for prefix in ["aarch64-linux-gnu-", "aarch64-elf-", "aarch64-unknown-elf-"]:
            try:
                subprocess.run([f"{prefix}as", str(asm_path), "-o", str(obj_path)], check=True)
                subprocess.run([f"{prefix}ld", str(obj_path), "-o", str(exe_path)], check=True)
                return exe_path
            except FileNotFoundError:
                continue
        
        raise RuntimeError(
            "AArch64 toolchain not found.\n"
            f"Install one of: aarch64-linux-gnu-*, aarch64-elf-*\n"
            f"Assembly file generated at: {asm_path}"
        )
    
    def run(self, output_path: PathLike, args: list[str], **options) -> int | None:
        """Run the compiled executable via QEMU."""
        import subprocess
        output_path = Path(output_path)
        result = subprocess.run(["qemu-aarch64", str(output_path)] + args)
        return result.returncode
    
    def get_compile_message(self, output_path: Path, **options) -> str:
        """Get compilation success message."""
        return f"Compiled: {output_path}"
