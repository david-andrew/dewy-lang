"""
ARM backend for udewy.

Generates GNU assembler syntax targeting AArch64 Linux with AAPCS64 ABI.
"""

from os import PathLike
import os
from pathlib import Path

from .. import t1
from .common import Backend, CORE_INTRINSIC_ARITIES, LocalRegisterAllocator, RunOptions, wrap_i64
from .linux import LINUX_SYSCALL_INTRINSIC_ARITIES, linux_builtin_constants

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
    _ARG_REGS = ["x0", "x1", "x2", "x3", "x4", "x5", "x6", "x7"]
    _VALUE_CACHE_REGS = ["x20", "x21", "x22", "x23"]
    _SAVE_AREA_BYTES = 96
    _MAX_STACK_ADJUST_IMM = 4080
    _FP_ARG_REGS = [f"v{i}" for i in range(8)]
    
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
        self._stack_offset: int = -96  # Start after callee-saved area
        self._param_slots: list[int] = []
        self._saved_depth: int = 0
        self._spilled_depth: int = 0
        self._min_slot_offset: int = 0
        self._frame_setup_index: int = -1
        
        # Control flow state
        self._if_stack: list[tuple[str, str, bool]] = []
        self._loop_stack: list[tuple[str, str]] = []
        self._locals = LocalRegisterAllocator()
        # The visible value may be pending rather than in x0: the flags of the
        # last comparison (the condition that would make it -1) or a local not
        # yet loaded. Branches, saves and comparisons consume pending values
        # directly; every other emitter flushes them first.
        self._pending_cc: str | None = None
        self._pending_slot: int | None = None
        
        # Symbol tracking
        self._fn_labels: dict[int, str] = {}
        self._global_labels: dict[int, str] = {}
        self._string_labels: dict[int, str] = {}
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

    def _local_area_bytes(self) -> int:
        required_bytes = max(0, -self._min_slot_offset)
        return (required_bytes + 15) & -16

    def _sp_adjust_instrs(self, op: str, amount: int) -> list[str]:
        instrs: list[str] = []
        while amount > 0:
            chunk = min(amount, self._MAX_STACK_ADJUST_IMM)
            chunk &= -16
            instrs.append(f"    {op} sp, sp, #{chunk}")
            amount -= chunk
        return instrs

    def _frame_pointer_setup_instrs(self, local_bytes: int) -> list[str]:
        instrs = ["    mov x29, sp"]
        remaining = local_bytes
        while remaining > 0:
            chunk = min(remaining, 4095)
            instrs.append(f"    add x29, x29, #{chunk}")
            remaining -= chunk
        return instrs

    def _frame_slot_operand(self, slot: int) -> str | None:
        if -256 <= slot <= 255:
            return f"[x29, #{slot}]"
        if slot >= 0 and slot % 8 == 0 and slot <= 32760:
            return f"[x29, #{slot}]"
        return None

    def _materialize_frame_addr(self, reg: str, slot: int) -> None:
        if slot == 0:
            self._emit(f"mov {reg}, x29")
            return
        if slot > 0:
            remaining = slot
            self._emit(f"mov {reg}, x29")
            while remaining > 0:
                chunk = min(remaining, 4095)
                self._emit(f"add {reg}, {reg}, #{chunk}")
                remaining -= chunk
            return

        remaining = -slot
        self._emit(f"mov {reg}, x29")
        while remaining > 0:
            chunk = min(remaining, 4095)
            self._emit(f"sub {reg}, {reg}, #{chunk}")
            remaining -= chunk

    def _load_frame_slot(self, dst: str, slot: int) -> None:
        operand = self._frame_slot_operand(slot)
        if operand is not None:
            self._emit(f"ldr {dst}, {operand}")
            return
        self._materialize_frame_addr("x9", slot)
        self._emit(f"ldr {dst}, [x9]")

    def _store_frame_slot(self, src: str, slot: int) -> None:
        operand = self._frame_slot_operand(slot)
        if operand is not None:
            self._emit(f"str {src}, {operand}")
            return
        self._materialize_frame_addr("x9", slot)
        self._emit(f"str {src}, [x9]")

    def _save_reg(self, reg: str) -> None:
        if self._spilled_depth > 0:
            self._emit("sub sp, sp, #16")
            self._emit(f"str {reg}, [sp]")
            self._spilled_depth += 1
        elif self._saved_depth < len(self._VALUE_CACHE_REGS):
            self._emit(f"mov {self._VALUE_CACHE_REGS[self._saved_depth]}, {reg}")
        else:
            for cache_reg in self._VALUE_CACHE_REGS[:self._saved_depth]:
                self._emit("sub sp, sp, #16")
                self._emit(f"str {cache_reg}, [sp]")
            self._emit("sub sp, sp, #16")
            self._emit(f"str {reg}, [sp]")
            self._spilled_depth = self._saved_depth + 1
        self._saved_depth += 1

    def _pop_saved_into(self, reg: str) -> None:
        self._saved_depth -= 1
        if self._spilled_depth > 0:
            self._emit(f"ldr {reg}, [sp], #16")
            self._spilled_depth -= 1
        elif self._saved_depth < len(self._VALUE_CACHE_REGS):
            cache_reg = self._VALUE_CACHE_REGS[self._saved_depth]
            if cache_reg != reg:
                self._emit(f"mov {reg}, {cache_reg}")
    
    def _prepare_call_args(self, num_args: int, fn_reg: str | None = None) -> int:
        reg_count = min(num_args, len(self._ARG_REGS))
        stack_count = num_args - reg_count
        stack_bytes = ((stack_count * 8) + 15) & -16
        consumed_values = num_args + (1 if fn_reg is not None else 0)

        if self._spilled_depth > 0:
            self._emit("mov x10, sp")
            if stack_bytes > 0:
                self._emit(f"sub sp, sp, #{stack_bytes}")
                for offset in range(stack_count):
                    src_offset = (stack_count - 1 - offset) * 16
                    self._emit(f"ldr x9, [x10, #{src_offset}]")
                    self._emit(f"str x9, [sp, #{offset * 8}]")

            for reg_idx in range(reg_count - 1, -1, -1):
                src_offset = (stack_count + (reg_count - 1 - reg_idx)) * 16
                self._emit(f"ldr {self._ARG_REGS[reg_idx]}, [x10, #{src_offset}]")

            if fn_reg is not None:
                self._emit(f"ldr {fn_reg}, [x10, #{num_args * 16}]")

            self._saved_depth -= consumed_values
            self._spilled_depth -= consumed_values
            return stack_bytes + consumed_values * 16

        if stack_bytes > 0:
            self._emit(f"sub sp, sp, #{stack_bytes}")
            for offset in range(stack_count - 1, -1, -1):
                self._pop_saved_into("x9")
                self._emit(f"str x9, [sp, #{offset * 8}]")

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
        output.append("    mov x29, xzr")           # clear frame pointer
        output.append("    ldr x0, [sp]")           # argc
        output.append("    add x1, sp, #8")         # argv
        output.append("    mov x9, sp")             # align stack to 16 bytes
        output.append("    bic x9, x9, #15")
        output.append("    mov sp, x9")
        if self._module_init_name is not None:
            output.append(f"    bl {self._module_init_name}")
        output.append("    bl __main__")
        output.append("    mov x8, #94")            # exit_group syscall
        output.append("    svc #0")
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
        output.append("    .xword 0")
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
        self._emit_data(f"    .xword {len(content)}")
        if len(content) > 0:
            bytes_str = ", ".join(str(b) for b in content)
            self._emit_data(f"    .byte {bytes_str}")
        
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
        self._emit_data(f"    .xword {value}")
        
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

    def intern_words(self, elements: list[int | str]) -> int:
        """Add initialized raw 64-bit words to the data section."""
        label_id = self._next_label
        label = self._new_label("static")
        self._static_labels[label_id] = label

        self._emit_data(f".section .data.{label},\"aw\",@progbits")
        self._emit_data("    .balign 8")
        self._emit_data_label(label)
        for element in elements:
            self._emit_data(f"    .xword {element}")

        return label_id
    
    def push_string_ref(self, label_id: int) -> None:
        """Push address of string data onto value stack."""
        self._flush()
        label = self._string_labels[label_id]
        self._emit(f"adrp x0, {label}")
        self._emit(f"add x0, x0, :lo12:{label}")
        self._emit("add x0, x0, #8")
    
    def push_global_ref(self, label_id: int) -> None:
        """Push address of global onto value stack."""
        self._flush()
        label = self._global_labels[label_id]
        self._emit(f"adrp x0, {label}")
        self._emit(f"add x0, x0, :lo12:{label}")

    def push_static_ref(self, label_id: int) -> None:
        """Push address of raw static storage onto value stack."""
        self._flush()
        label = self._static_labels[label_id]
        self._emit(f"adrp x0, {label}")
        self._emit(f"add x0, x0, :lo12:{label}")
    
    def load_global(self, label_id: int) -> None:
        """Load value of global onto value stack."""
        self._flush()
        label = self._global_labels[label_id]
        self._emit(f"adrp x9, {label}")
        self._emit(f"add x9, x9, :lo12:{label}")
        self._emit("ldr x0, [x9]")
    
    def store_global(self, label_id: int) -> None:
        """Pop value from stack and store to global."""
        self._flush()
        label = self._global_labels[label_id]
        self._emit(f"adrp x9, {label}")
        self._emit(f"add x9, x9, :lo12:{label}")
        self._emit("str x0, [x9]")

    def function_ref(self, label_id: int) -> str:
        return self._fn_labels[label_id]

    def string_ref(self, label_id: int) -> str:
        return f"{self._string_labels[label_id]}+8"

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
    
    # Local register allocation: x19 and x24-x28 are preserved by the ABI and
    # are not expression scratch (x20-x23 cache operands); x11-x15 are free
    # between calls and syscalls.
    _CALLEE_LOCAL_REGS = ["x19", "x24", "x25", "x26", "x27", "x28"]
    _CALLER_LOCAL_REGS = ["x11", "x12", "x13", "x14", "x15"]

    def _slot_key(self, slot: int) -> int:
        return (-slot - 16) >> 3

    def _note_local_access(self, slot: int, other: str, store: bool) -> None:
        """Slots beyond the single-instruction offset range keep their frame homes.

        The register form of a slot access is a move: `mov REG, other` for a
        store, `mov other, REG` for a load.
        """
        assert self._current_fn_code is not None
        if self._frame_slot_operand(slot) is None:
            self._locals.pin(self._slot_key(slot))
        elif store:
            self._locals.note_site(len(self._current_fn_code), self._slot_key(slot), '    mov ', f', {other}')
        else:
            self._locals.note_site(len(self._current_fn_code), self._slot_key(slot), f'    mov {other}, ', '')

    def _note_clobber(self) -> None:
        assert self._current_fn_code is not None
        self._locals.note_clobber(len(self._current_fn_code))

    _INVERSE_CC = {'eq': 'ne', 'ne': 'eq', 'lt': 'ge', 'ge': 'lt', 'gt': 'le', 'le': 'gt',
                   'hi': 'ls', 'ls': 'hi', 'lo': 'hs', 'hs': 'lo'}

    def _load_pending_slot(self, register: str) -> None:
        """Load a pending local straight into `register` (its site is recorded)."""
        slot, self._pending_slot = self._pending_slot, None
        assert slot is not None
        self._note_local_access(slot, register, False)
        self._load_frame_slot(register, slot)

    def _flush(self) -> None:
        """Materialize a pending value into x0."""
        if self._pending_cc is not None:
            cc, self._pending_cc = self._pending_cc, None
            self._emit(f'csetm x0, {cc}')
        elif self._pending_slot is not None:
            self._load_pending_slot('x0')

    def _branch_pending(self, label: str, when_true: bool) -> bool:
        """Consume a pending condition as a branch taken when it holds or fails."""
        if self._pending_cc is None:
            return False
        cc, self._pending_cc = self._pending_cc, None
        if not when_true:
            cc = self._INVERSE_CC[cc]
        self._emit(f'b.{cc} {label}')
        return True

    def _operands(self) -> None:
        """The right operand goes to x9 and the saved left operand to x0."""
        if self._pending_cc is not None:
            self._flush()
        if self._pending_slot is not None:
            self._load_pending_slot('x9')
        else:
            self._emit('mov x9, x0')
        self._pop_saved_into('x0')

    def _allocate_locals(self) -> None:
        """Debug builds retain their existing stack locations (as on x86-64)."""
        if self.debug_info:
            return
        assert self._current_fn_code is not None
        self._locals.assign(self._CALLEE_LOCAL_REGS, self._CALLER_LOCAL_REGS)
        self._locals.rewrite(self._current_fn_code)

    def begin_function(self, label_id: int, name: str, param_count: int, is_main: bool) -> None:
        """Begin function definition."""
        label = self._fn_labels[label_id]
        self._saved_depth = 0
        self._spilled_depth = 0
        self._min_slot_offset = 0
        self._pending_cc = None
        self._pending_slot = None
        self._locals.begin_function()
        
        self._current_fn_code = []
        self._function_code.append((label_id, self._current_fn_code))
        
        self._current_fn_code.append(f".section .text.{label},\"ax\",@progbits")
        if is_main:
            self._emit_label("__main__")
        self._emit_label(label)
        
        # Prologue - save fp/lr with pre-index, then allocate the fixed frame.
        self._emit("stp x29, x30, [sp, #-96]!")   # save fp, lr and decrement sp by 96
        self._emit("stp x27, x28, [sp, #80]")
        self._emit("stp x25, x26, [sp, #64]")
        self._emit("stp x23, x24, [sp, #48]")
        self._emit("stp x21, x22, [sp, #32]")
        self._emit("stp x19, x20, [sp, #16]")
        
        self._frame_setup_index = len(self._current_fn_code)
        self._emit("    # local frame setup")
        
        # Set up parameters - copy from arg registers to stack
        # Parameters stored at negative offsets from x29
        self._param_slots = []
        self._stack_offset = -16  # Start below saved regs area
        
        for i in range(param_count):
            slot = self._stack_offset
            self._param_slots.append(slot)
            self._note_slot(slot)
            self._locals.note_alloc(self._slot_key(slot), len(self._current_fn_code))
            
            if i < 8:
                self._note_local_access(slot, self._ARG_REGS[i], True)
                self._store_frame_slot(self._ARG_REGS[i], slot)
            else:
                # Load from caller's stack frame
                caller_offset = 96 + (i - 8) * 8
                self._load_frame_slot("x9", caller_offset)
                self._note_local_access(slot, "x9", True)
                self._store_frame_slot("x9", slot)
            
            self._stack_offset -= 8
        
        self._current_fn_epilogue = f"{label}_epilogue"
    
    def end_function(self) -> None:
        """End function definition."""
        assert self._current_fn_code is not None
        self._flush()
        # Sites index the body as emitted; rewrite before the prologue is spliced in.
        self._allocate_locals()
        local_bytes = self._local_area_bytes()
        self._current_fn_code[self._frame_setup_index:self._frame_setup_index + 1] = (
            self._sp_adjust_instrs("sub", local_bytes)
            + self._frame_pointer_setup_instrs(local_bytes)
        )
        self._emit_label(self._current_fn_epilogue)
        
        # Drop any dynamic stack allocations before restoring saved registers.
        self._emit("mov sp, x29")
        
        # Restore callee-saved registers
        self._emit("ldp x19, x20, [sp, #16]")
        self._emit("ldp x21, x22, [sp, #32]")
        self._emit("ldp x23, x24, [sp, #48]")
        self._emit("ldp x25, x26, [sp, #64]")
        self._emit("ldp x27, x28, [sp, #80]")
        self._emit("ldp x29, x30, [sp], #96")     # restore fp, lr and increment sp
        
        self._emit("ret")
        self._current_fn_code = None
    
    def load_param(self, index: int) -> None:
        """Push parameter value onto the value stack."""
        self.load_local(self._param_slots[index])
    
    def alloc_local(self) -> int:
        """Allocate a local variable slot."""
        self._flush()
        slot = self._stack_offset
        self._stack_offset -= 8
        self._note_slot(slot)
        assert self._current_fn_code is not None
        self._locals.note_alloc(self._slot_key(slot), len(self._current_fn_code))
        return slot

    def load_local(self, slot: int) -> None:
        """Push local variable value onto the value stack."""
        self._flush()
        self._pending_slot = slot

    def store_local(self, slot: int) -> None:
        """Pop value from stack and store to local variable."""
        self._flush()
        self._note_local_access(slot, "x0", True)
        self._store_frame_slot("x0", slot)
    
    # ========================================================================
    # Value stack operations
    # ========================================================================
    
    def push_const_i64(self, value: int) -> None:
        """Push a 64-bit integer constant onto the value stack."""
        self._flush()
        value = wrap_i64(value)
        if 0 <= value <= 65535:
            self._emit(f"mov x0, #{value}")
        elif -65536 <= value < 0:
            self._emit(f"mov x0, #{value}")
        else:
            # Load large constant via movz/movk sequence
            self._emit(f"ldr x0, ={value}")
    
    def push_void(self) -> None:
        """Push void (zero) onto the value stack."""
        self._flush()
        self._emit("mov x0, #0")
    
    def push_fn_ref(self, label_id: int) -> None:
        """Push address of function onto the value stack."""
        self._flush()
        label = self._fn_labels[label_id]
        self._emit(f"adrp x0, {label}")
        self._emit(f"add x0, x0, :lo12:{label}")
    
    def pop_value(self) -> None:
        """Discard the top value; one never materialized costs nothing."""
        self._pending_cc = None
        self._pending_slot = None
    
    def save_value(self) -> None:
        """Save the top value to physical stack."""
        if self._pending_slot is not None and self._spilled_depth == 0 and self._saved_depth < len(self._VALUE_CACHE_REGS):
            self._load_pending_slot(self._VALUE_CACHE_REGS[self._saved_depth])
            self._saved_depth += 1
            return
        self._flush()
        self._save_reg("x0")
    
    def restore_value(self) -> None:
        """Restore a previously saved value."""
        self._flush()
        self._pop_saved_into("x0")
    
    # ========================================================================
    # Operators
    # ========================================================================
    
    def unary_op(self, op_kind: t1.Kind) -> None:
        """Apply unary operator to top of stack."""
        # A pending condition is exactly -1 or 0, so `not` is its inverse.
        if op_kind == t1.Kind.TK_NOT and self._pending_cc is not None:
            self._pending_cc = self._INVERSE_CC[self._pending_cc]
            return
        self._flush()
        if op_kind == t1.Kind.TK_MINUS:
            self._emit("neg x0, x0")
        elif op_kind == t1.Kind.TK_NOT:
            self._emit("mvn x0, x0")
    
    def binary_op(self, op_kind: t1.Kind) -> None:
        """Apply binary operator to top two values on stack."""
        self._operands()
        if op_kind == t1.Kind.TK_PLUS:
            self._emit("add x0, x0, x9")
        elif op_kind == t1.Kind.TK_MINUS:
            self._emit("sub x0, x0, x9")
        elif op_kind == t1.Kind.TK_MUL:
            self._emit("mul x0, x0, x9")
        elif op_kind == t1.Kind.TK_IDIV:
            self._emit_signed_sdiv()
        elif op_kind == t1.Kind.TK_MOD:
            self._emit_signed_mod()
        elif op_kind == t1.Kind.TK_LEFT_SHIFT:
            self._emit("lsl x0, x0, x9")
        elif op_kind == t1.Kind.TK_RIGHT_SHIFT:
            self._emit("lsr x0, x0, x9")
        elif op_kind == t1.Kind.TK_AND:
            self._emit("and x0, x0, x9")
        elif op_kind == t1.Kind.TK_OR:
            self._emit("orr x0, x0, x9")
        elif op_kind == t1.Kind.TK_XOR:
            self._emit("eor x0, x0, x9")
        elif op_kind == t1.Kind.TK_EQ:
            self._emit("cmp x0, x9")
            self._pending_cc = "eq"
        elif op_kind == t1.Kind.TK_NOT_EQ:
            self._emit("cmp x0, x9")
            self._pending_cc = "ne"
        elif op_kind == t1.Kind.TK_GT:
            self._emit("cmp x0, x9")
            self._pending_cc = "gt"
        elif op_kind == t1.Kind.TK_LT:
            self._emit("cmp x0, x9")
            self._pending_cc = "lt"
        elif op_kind == t1.Kind.TK_GT_EQ:
            self._emit("cmp x0, x9")
            self._pending_cc = "ge"
        elif op_kind == t1.Kind.TK_LT_EQ:
            self._emit("cmp x0, x9")
            self._pending_cc = "le"
    
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
        self._pop_saved_into("x9")     # value
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
        self._pop_saved_into("x0")
        self._emit("asr x0, x0, x9")

    def _emit_signed_sdiv(self) -> None:
        """x0=lhs, x9=rhs -> lhs // rhs (RISC-V div semantics)."""
        div_zero = self._new_label("div_zero")
        done = self._new_label("div_done")
        do_sdiv = self._new_label("div_sdiv")
        self._emit("cmp x9, #0")
        self._emit(f"beq {div_zero}")
        self._emit("ldr x10, =0x8000000000000000")
        self._emit("cmp x0, x10")
        self._emit(f"bne {do_sdiv}")
        self._emit("mov x10, #-1")
        self._emit("cmp x9, x10")
        self._emit(f"bne {do_sdiv}")
        self._emit(f"b {done}")
        self._emit_label(do_sdiv)
        self._emit("sdiv x0, x0, x9")
        self._emit(f"b {done}")
        self._emit_label(div_zero)
        self._emit("mov x0, #-1")
        self._emit_label(done)

    def _emit_signed_mod(self) -> None:
        """x0=lhs, x9=rhs -> lhs % rhs (RISC-V rem semantics)."""
        mod_zero = self._new_label("mod_zero")
        done = self._new_label("mod_done")
        do_sdiv = self._new_label("mod_sdiv")
        self._emit("cmp x9, #0")
        self._emit(f"beq {mod_zero}")
        self._emit("ldr x10, =0x8000000000000000")
        self._emit("cmp x0, x10")
        self._emit(f"bne {do_sdiv}")
        self._emit("mov x10, #-1")
        self._emit("cmp x9, x10")
        self._emit(f"bne {do_sdiv}")
        self._emit("mov x0, #0")
        self._emit(f"b {done}")
        self._emit_label(do_sdiv)
        self._emit("sdiv x10, x0, x9")
        self._emit("msub x0, x10, x9, x0")
        self._emit(f"b {done}")
        self._emit_label(mod_zero)
        self._emit_label(done)

    def _emit_unsigned_udiv(self) -> None:
        """x0=lhs, x9=rhs -> unsigned quotient (RISC-V divu semantics)."""
        div_zero = self._new_label("udiv_zero")
        done = self._new_label("udiv_done")
        self._emit("cmp x9, #0")
        self._emit(f"beq {div_zero}")
        self._emit("udiv x0, x0, x9")
        self._emit(f"b {done}")
        self._emit_label(div_zero)
        self._emit("mov x0, #-1")
        self._emit_label(done)

    def _emit_unsigned_mod(self) -> None:
        """x0=lhs, x9=rhs -> unsigned remainder (RISC-V remu semantics)."""
        mod_zero = self._new_label("umod_zero")
        done = self._new_label("umod_done")
        self._emit("cmp x9, #0")
        self._emit(f"beq {mod_zero}")
        self._emit("udiv x10, x0, x9")
        self._emit("msub x0, x10, x9, x0")
        self._emit(f"b {done}")
        self._emit_label(mod_zero)
        self._emit_label(done)

    def unsigned_idiv(self) -> None:
        """Unsigned division. Stack: [left right] -> quotient."""
        self._emit("mov x9, x0")
        self._pop_saved_into("x0")
        self._emit_unsigned_udiv()

    def unsigned_mod(self) -> None:
        """Unsigned remainder. Stack: [left right] -> remainder."""
        self._emit("mov x9, x0")
        self._pop_saved_into("x0")
        self._emit_unsigned_mod()

    def unsigned_cmp(self, kind: str) -> None:
        """Unsigned comparison returning udewy booleans."""
        self._operands()
        self._emit("cmp x0, x9")
        self._pending_cc = {"gt": "hi", "lt": "lo", "gte": "hs", "lte": "ls"}[kind]

    def alloca(self) -> None:
        """Keep expression spills below storage that lives until return.

        Merely moving sp puts the buffer between saved operands and their
        eventual pops. Slide those words down with the stack top, copying
        forward because the regions overlap for small allocations.
        """
        spilled = self._spilled_depth * 16
        if spilled > 4080:
            raise ValueError("__alloca__ under more than 255 pending values")
        if spilled:
            self._emit("mov x10, sp")
        self._emit("add x0, x0, #15")
        self._emit("and x0, x0, #-16")
        self._emit("sub x9, sp, x0")
        self._emit("mov sp, x9")
        for offset in range(0, spilled, 16):
            self._emit(f"ldr x9, [x10, #{offset}]")
            self._emit(f"str x9, [sp, #{offset}]")
        if spilled:
            self._emit(f"add x0, sp, #{spilled}")
        else:
            self._emit("mov x0, x9")
    
    # ========================================================================
    # Calls
    # ========================================================================
    
    def call_direct(self, label_id: int, num_args: int) -> None:
        """Call a function directly by label."""
        self._flush()
        stack_bytes = self._prepare_call_args(num_args)
        label = self._fn_labels[label_id]
        self._note_clobber()
        self._emit(f"bl {label}")
        if stack_bytes > 0:
            self._emit(f"add sp, sp, #{stack_bytes}")
    
    def call_indirect(self, num_args: int) -> None:
        """Call a function indirectly via pointer."""
        self._flush()
        stack_bytes = self._prepare_call_args(num_args, "x9")
        self._note_clobber()
        self._emit("blr x9")
        if stack_bytes > 0:
            self._emit(f"add sp, sp, #{stack_bytes}")

    def max_call_args(self) -> int | None:
        return None
    
    def syscall(self, num_args: int) -> None:
        """Invoke a syscall using svc #0."""
        self._note_clobber()
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
            self._pop_saved_into("x8")       # syscall_num
            self._emit("mov x0, x9")
            self._emit("svc #0")
        elif num_args == 3:
            # x0=arg2, stack=[syscall_num, arg1]
            self._emit("mov x1, x0")         # arg2 -> x1
            self._pop_saved_into("x0")       # arg1 -> x0
            self._pop_saved_into("x8")       # syscall_num -> x8
            self._emit("svc #0")
        elif num_args == 4:
            # x0=arg3, stack=[syscall_num, arg1, arg2]
            self._emit("mov x2, x0")         # arg3 -> x2
            self._pop_saved_into("x1")       # arg2 -> x1
            self._pop_saved_into("x0")       # arg1 -> x0
            self._pop_saved_into("x8")       # syscall_num -> x8
            self._emit("svc #0")
        elif num_args == 5:
            # x0=arg4, stack=[syscall_num, arg1, arg2, arg3]
            self._emit("mov x3, x0")
            self._pop_saved_into("x2")
            self._pop_saved_into("x1")
            self._pop_saved_into("x0")
            self._pop_saved_into("x8")
            self._emit("svc #0")
        elif num_args == 6:
            # x0=arg5, stack=[syscall_num, arg1, arg2, arg3, arg4]
            self._emit("mov x4, x0")
            self._pop_saved_into("x3")
            self._pop_saved_into("x2")
            self._pop_saved_into("x1")
            self._pop_saved_into("x0")
            self._pop_saved_into("x8")
            self._emit("svc #0")
        elif num_args == 7:
            # x0=arg6, stack=[syscall_num, arg1, arg2, arg3, arg4, arg5]
            self._emit("mov x5, x0")
            self._pop_saved_into("x4")
            self._pop_saved_into("x3")
            self._pop_saved_into("x2")
            self._pop_saved_into("x1")
            self._pop_saved_into("x0")
            self._pop_saved_into("x8")
            self._emit("svc #0")

    def _mixed_extern_arg_slots(self, name: str) -> int | None:
        prefix = "__call_extern_mixed_"
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

    def _emit_move_to_fp(self, kind: int, fp_reg: str) -> None:
        if kind == 1:
            fp_scalar = fp_reg.replace("v", "s", 1)
            self._emit(f"fmov {fp_scalar}, w0")
            return
        if kind == 2:
            fp_scalar = fp_reg.replace("v", "d", 1)
            self._emit(f"fmov {fp_scalar}, x0")
            return
        raise RuntimeError(f"unsupported FP intrinsic kind: {kind}")

    def _call_extern_fp_mixed(self, type_tags: list[int]) -> None:
        gp_slots: list[int] = []
        fp_slots: list[int] = []
        gp_count = 0
        fp_count = 0
        for kind in type_tags:
            if kind == 0:
                gp_slots.append(gp_count)
                fp_slots.append(-1)
                gp_count += 1
            elif kind in (1, 2):
                gp_slots.append(-1)
                fp_slots.append(fp_count)
                fp_count += 1
            else:
                raise RuntimeError(f"unsupported mixed FP intrinsic kind: {kind}")

        if gp_count > len(self._ARG_REGS):
            raise RuntimeError("mixed FP intrinsic exceeds supported GP argument register count")
        if fp_count > len(self._FP_ARG_REGS):
            raise RuntimeError("mixed FP intrinsic exceeds supported FP argument register count")

        for arg_index in range(len(type_tags) - 1, -1, -1):
            kind = type_tags[arg_index]
            if kind == 0:
                dst_reg = self._ARG_REGS[gp_slots[arg_index]]
                if dst_reg != "x0":
                    self._emit(f"mov {dst_reg}, x0")
            else:
                self._emit_move_to_fp(kind, self._FP_ARG_REGS[fp_slots[arg_index]])

            if arg_index > 0:
                self._pop_saved_into("x0")

        self._pop_saved_into("x9")
        self._note_clobber()
        self._emit("blr x9")

    def _mixed_extern_type_tags(self, name: str, intrinsic_data: object | None) -> list[int]:
        mixed_args = self._mixed_extern_arg_slots(name)
        if mixed_args is None:
            raise RuntimeError(f"unsupported intrinsic {name!r}")
        if not isinstance(intrinsic_data, dict) or "static_args" not in intrinsic_data:
            raise RuntimeError(f"missing static arguments for intrinsic {name!r}")
        static_args = intrinsic_data["static_args"]
        if not isinstance(static_args, dict):
            raise RuntimeError(f"invalid static arguments for intrinsic {name!r}")

        type_tags: list[int] = []
        for arg_index in range(1, 1 + mixed_args * 2, 2):
            tag = static_args.get(arg_index)
            if not isinstance(tag, int) or tag not in (0, 1, 2):
                raise RuntimeError(f"mixed extern intrinsic {name!r} requires type tags 0, 1, or 2")
            type_tags.append(tag)
        return type_tags
    
    # ========================================================================
    # Control flow
    # ========================================================================
    
    def begin_if(self) -> None:
        """Begin an if statement."""
        else_label = self._new_label("else")
        end_label = self._new_label("if_end")
        self._if_stack.append((else_label, end_label, False))
        if self._branch_pending(else_label, False):
            return
        self._flush()
        self._emit("cbz x0, " + else_label)
    
    def begin_else(self) -> None:
        """Begin the else branch."""
        self._flush()
        else_label, end_label, _ = self._if_stack[-1]
        self._if_stack[-1] = (else_label, end_label, True)
        self._emit(f"b {end_label}")
        self._emit_label(else_label)
    
    def end_if(self) -> None:
        """End an if statement."""
        self._flush()
        else_label, end_label, else_emitted = self._if_stack.pop()
        if not else_emitted:
            self._emit_label(else_label)
        self._emit_label(end_label)
    
    def begin_loop(self) -> None:
        """Begin a loop."""
        self._flush()
        start_label = self._new_label("loop_start")
        end_label = self._new_label("loop_end")
        self._loop_stack.append((start_label, end_label))
        assert self._current_fn_code is not None
        self._locals.begin_loop(len(self._current_fn_code))
        self._emit_label(start_label)
    
    def begin_loop_body(self) -> None:
        """Begin the loop body after condition check."""
        _, end_label = self._loop_stack[-1]
        if self._branch_pending(end_label, False):
            return
        self._flush()
        self._emit(f"cbz x0, {end_label}")

    def cond_and_split(self) -> str:
        false_label = self._new_label("cond_and_false")
        if self._branch_pending(false_label, False):
            return false_label
        self._flush()
        self._emit(f"cbz x0, {false_label}")
        return false_label

    def cond_and_join(self, false_label: str) -> None:
        self._flush()
        done_label = self._new_label("cond_and_done")
        self._emit(f"b {done_label}")
        self._emit_label(false_label)
        self._emit("mov x0, #0")
        self._emit_label(done_label)

    def cond_or_split(self) -> str:
        done_label = self._new_label("cond_or_done")
        if self._pending_cc is not None:
            # The taken path must carry the true value; mov leaves the flags alone.
            self._emit("mov x0, #-1")
            self._branch_pending(done_label, True)
            return done_label
        self._flush()
        self._emit(f"cbnz x0, {done_label}")
        return done_label

    def cond_or_join(self, done_label: str) -> None:
        self._flush()
        self._emit_label(done_label)
    
    def end_loop(self) -> None:
        """End a loop."""
        self._flush()
        start_label, end_label = self._loop_stack.pop()
        self._emit(f"b {start_label}")
        self._emit_label(end_label)
        assert self._current_fn_code is not None
        self._locals.end_loop(len(self._current_fn_code))
    
    def emit_break(self) -> None:
        """Emit a break statement."""
        self._flush()
        _, end_label = self._loop_stack[-1]
        self._emit(f"b {end_label}")
    
    def emit_continue(self) -> None:
        """Emit a continue statement."""
        self._flush()
        start_label, _ = self._loop_stack[-1]
        self._emit(f"b {start_label}")
    
    def emit_return(self) -> None:
        """Emit a return statement."""
        self._flush()
        self._emit(f"b {self._current_fn_epilogue}")
    
    # ========================================================================
    # Intrinsics
    # ========================================================================
    
    _INTRINSIC_ARITIES = (
        CORE_INTRINSIC_ARITIES
        | LINUX_SYSCALL_INTRINSIC_ARITIES
        | {
            "__i64_to_f32_bits__": 1,
            "__i64_to_f64_bits__": 1,
            "__f32_bits_to_i64__": 1,
            "__f64_bits_to_i64__": 1,
        }
    )
    
    def is_intrinsic(self, name: str) -> bool:
        """Check if name is an intrinsic supported by this backend."""
        return name in self._INTRINSIC_ARITIES or self._mixed_extern_arg_slots(name) is not None

    def intrinsic_arity(self, name: str) -> int | None:
        """Return the expected arity for a supported intrinsic."""
        mixed_args = self._mixed_extern_arg_slots(name)
        if mixed_args is not None:
            return 1 + (mixed_args * 2)
        return self._INTRINSIC_ARITIES.get(name)

    def intrinsic_static_arg_indices(self, name: str) -> set[int]:
        mixed_args = self._mixed_extern_arg_slots(name)
        if mixed_args is None:
            return set()
        return set(range(1, 1 + mixed_args * 2, 2))
    
    def emit_intrinsic(self, name: str, num_args: int, intrinsic_data: object | None = None) -> None:
        """Emit code for an intrinsic call."""
        self._flush()
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
        elif name == "__breakpoint__":
            self._emit("brk #0")   # a debugger attached to the process stops here
            self.push_void()
        elif name == "__i64_to_f32_bits__":
            self._emit("scvtf s0, x0")
            self._emit("fmov w0, s0")
        elif name == "__i64_to_f64_bits__":
            self._emit("scvtf d0, x0")
            self._emit("fmov x0, d0")
        elif name == "__f32_bits_to_i64__":
            self._emit("fmov s0, w0")
            self._emit("fcvtzs x0, s0")
        elif name == "__f64_bits_to_i64__":
            self._emit("fmov d0, x0")
            self._emit("fcvtzs x0, d0")
        elif name.startswith("__syscall"):
            self.syscall(num_args)
        else:
            self._call_extern_fp_mixed(self._mixed_extern_type_tags(name, intrinsic_data))
    
    def get_builtin_constants(self) -> dict[str, int]:
        """Return AArch64 Linux syscall numbers and common constants."""
        return linux_builtin_constants("newstyle")
    
    def compile_and_link(self, code: str, input_name: str, cache_dir: Path, **options) -> Path:
        """Compile and link AArch64 assembly to executable."""
        import subprocess
        
        cache_dir.mkdir(parents=True, exist_ok=True)
        asm_path = cache_dir / f"{input_name}.s"
        obj_path = cache_dir / f"{input_name}.o"
        exe_path = cache_dir / input_name
        link_artifacts = [str(Path(path)) for path in options.get("link_artifacts", [])]
        
        # The direct path writes the object in process (UDEWY_OBJECT=direct);
        # only the linker is still needed.
        direct = os.environ.get("UDEWY_OBJECT") == "direct"
        if direct:
            from .aarch64_object import assemble
            obj_path.write_bytes(assemble(code))
        else:
            asm_path.write_text(code)
        
        # Try different toolchain prefixes
        for prefix in ["aarch64-linux-gnu-", "aarch64-elf-", "aarch64-unknown-elf-"]:
            try:
                if not direct:
                    subprocess.run([f"{prefix}as", str(asm_path), "-o", str(obj_path)], check=True)
                subprocess.run([f"{prefix}ld", "--gc-sections", "-e", "_start", str(obj_path), *link_artifacts, "-o", str(exe_path)], check=True)
                return exe_path
            except FileNotFoundError:
                continue
        
        raise RuntimeError(
            "AArch64 toolchain not found.\n"
            f"Install one of: aarch64-linux-gnu-*, aarch64-elf-*\n"
            f"Assembly file generated at: {asm_path}"
        )
    
    def run(self, output_path: PathLike, args: list[str], options: RunOptions | None = None) -> int | None:
        """Run the compiled executable via QEMU."""
        import subprocess
        output_path = Path(output_path)
        result = subprocess.run(["qemu-aarch64", str(output_path)] + args)
        return result.returncode
    
    def get_compile_message(self, output_path: Path, **options) -> str:
        """Get compilation success message."""
        return f"Compiled: {output_path}"
