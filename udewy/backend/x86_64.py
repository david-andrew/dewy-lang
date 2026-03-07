"""
x86_64 backend for udewy.

Generates GNU assembler syntax targeting Linux x86_64 with System V ABI.
"""

from pathlib import Path
from os import PathLike


class X86_64Backend:
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
    
    def __init__(self) -> None:
        self._code: list[str] = []
        self._data: list[str] = []
        self._next_label: int = 0
        
        # Function state
        self._current_fn_epilogue: str = ""
        self._stack_offset: int = -48  # Start after callee-saved area
        self._param_slots: list[int] = []
        
        # Control flow state
        self._if_stack: list[tuple[str, str, bool]] = []  # (else_label, end_label, else_emitted)
        self._loop_stack: list[tuple[str, str]] = []  # (start_label, end_label)
        
        # Symbol tracking
        self._fn_labels: dict[int, str] = {}
        self._global_labels: dict[int, str] = {}
        self._string_labels: dict[int, str] = {}
        self._array_labels: dict[int, str] = {}
    
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
        output.append("    xorq %rbp, %rbp")
        output.append("    movq (%rsp), %rdi")      # argc
        output.append("    leaq 8(%rsp), %rsi")     # argv
        output.append("    andq $-16, %rsp")        # align stack
        output.append("    call __main__")
        output.append("    movq %rax, %rdi")        # exit code
        output.append("    movq $60, %rax")         # exit syscall
        output.append("    syscall")
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
        
        self._emit_data_label(label)
        self._emit_data(f"    .quad {len(elements)}")
        for elem in elements:
            self._emit_data(f"    .quad {elem}")
        
        return label_id
    
    def define_global(self, name_id: int, value: int | str) -> int:
        """Define a global variable."""
        label_id = self._next_label
        label = self._new_label("global")
        self._global_labels[label_id] = label
        
        self._emit_data_label(label)
        self._emit_data(f"    .quad {value}")
        
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
    
    def load_global(self, label_id: int) -> None:
        """Load value of global onto value stack."""
        label = self._global_labels[label_id]
        self._emit(f"movq {label}(%rip), %rax")
    
    def store_global(self, label_id: int) -> None:
        """Pop value from stack and store to global."""
        label = self._global_labels[label_id]
        self._emit(f"movq %rax, {label}(%rip)")
    
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
        
        # Prologue
        self._emit("pushq %rbp")
        self._emit("movq %rsp, %rbp")
        self._emit("subq $1024, %rsp")
        
        # Save callee-saved registers
        self._emit("movq %rbx, -8(%rbp)")
        self._emit("movq %r12, -16(%rbp)")
        self._emit("movq %r13, -24(%rbp)")
        self._emit("movq %r14, -32(%rbp)")
        self._emit("movq %r15, -40(%rbp)")
        
        # Set up parameters
        arg_regs = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
        self._param_slots = []
        self._stack_offset = -48
        
        for i in range(param_count):
            slot = self._stack_offset
            self._param_slots.append(slot)
            
            if i < 6:
                self._emit(f"movq {arg_regs[i]}, {slot}(%rbp)")
            else:
                caller_offset = 16 + (i - 6) * 8
                self._emit(f"movq {caller_offset}(%rbp), %rax")
                self._emit(f"movq %rax, {slot}(%rbp)")
            
            self._stack_offset -= 8
        
        self._current_fn_epilogue = f"{label}_epilogue"
    
    def end_function(self) -> None:
        """End function definition."""
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
    
    def load_param(self, index: int) -> None:
        """Push parameter value onto the value stack."""
        slot = self._param_slots[index]
        self._emit(f"movq {slot}(%rbp), %rax")
    
    def alloc_local(self) -> int:
        """Allocate a local variable slot."""
        slot = self._stack_offset
        self._stack_offset -= 8
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
    
    def dup_value(self) -> None:
        """Duplicate the top value on the stack."""
        self._emit("pushq %rax")
        self._emit("popq %rax")
    
    def pop_value(self) -> None:
        """Discard the top value on the stack."""
        pass
    
    def save_value(self) -> None:
        """Save the top value to physical stack."""
        self._emit("pushq %rax")
    
    def restore_value(self) -> None:
        """Restore a previously saved value."""
        self._emit("popq %rax")
    
    # ========================================================================
    # Operators
    # ========================================================================
    
    def unary_op(self, op: str) -> None:
        """Apply unary operator to top of stack."""
        if op == "neg":
            self._emit("negq %rax")
        elif op == "not":
            self._emit("notq %rax")
    
    def binary_op(self, op: str) -> None:
        """
        Apply binary operator to top two values on stack.
        
        Assumes left operand was saved via save_value(), right is in rax.
        """
        self._emit("movq %rax, %rcx")  # right in rcx
        self._emit("popq %rax")        # left in rax
        
        if op == "+":
            self._emit("addq %rcx, %rax")
        elif op == "-":
            self._emit("subq %rcx, %rax")
        elif op == "*":
            self._emit("imulq %rcx, %rax")
        elif op == "//":
            self._emit("cqto")
            self._emit("idivq %rcx")
        elif op == "%":
            self._emit("cqto")
            self._emit("idivq %rcx")
            self._emit("movq %rdx, %rax")
        elif op == "<<":
            self._emit("shlq %cl, %rax")
        elif op == ">>":
            self._emit("sarq %cl, %rax")
        elif op == "and":
            self._emit("andq %rcx, %rax")
        elif op == "or":
            self._emit("orq %rcx, %rax")
        elif op == "xor":
            self._emit("xorq %rcx, %rax")
        elif op == "=?":
            self._emit("cmpq %rcx, %rax")
            self._emit("sete %al")
            self._emit("movzbq %al, %rax")
            self._emit("negq %rax")
        elif op == "not=?":
            self._emit("cmpq %rcx, %rax")
            self._emit("setne %al")
            self._emit("movzbq %al, %rax")
            self._emit("negq %rax")
        elif op == ">?":
            self._emit("cmpq %rcx, %rax")
            self._emit("setg %al")
            self._emit("movzbq %al, %rax")
            self._emit("negq %rax")
        elif op == "<?":
            self._emit("cmpq %rcx, %rax")
            self._emit("setl %al")
            self._emit("movzbq %al, %rax")
            self._emit("negq %rax")
        elif op == ">=?":
            self._emit("cmpq %rcx, %rax")
            self._emit("setge %al")
            self._emit("movzbq %al, %rax")
            self._emit("negq %rax")
        elif op == "<=?":
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
        self._emit("popq %rdi")        # arg1
        self._emit("call *%r11")
    
    # ========================================================================
    # Memory operations
    # ========================================================================
    
    def load_mem(self, width: int) -> None:
        """Load from memory address in rax."""
        if width == 64:
            self._emit("movq (%rax), %rax")
        elif width == 32:
            self._emit("movl (%rax), %eax")
        elif width == 16:
            self._emit("movzwq (%rax), %rax")
        elif width == 8:
            self._emit("movzbq (%rax), %rax")
    
    def store_mem(self, width: int) -> None:
        """Store to memory. Stack: [value addr] -> pushes 0."""
        self._emit("popq %rbx")  # value
        if width == 64:
            self._emit("movq %rbx, (%rax)")
        elif width == 32:
            self._emit("movl %ebx, (%rax)")
        elif width == 16:
            self._emit("movw %bx, (%rax)")
        elif width == 8:
            self._emit("movb %bl, (%rax)")
        self._emit("xorq %rax, %rax")  # return 0
    
    # ========================================================================
    # Calls
    # ========================================================================
    
    def prepare_args(self, num_args: int) -> None:
        """Pop arguments from stack into registers for a call."""
        regs = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
        for i in range(min(num_args, 6) - 1, -1, -1):
            self._emit(f"popq {regs[i]}")
    
    def call_direct(self, label_id: int, num_args: int) -> None:
        """Call a function directly by label."""
        self.prepare_args(num_args)
        label = self._fn_labels[label_id]
        self._emit(f"call {label}")
    
    def call_indirect(self, num_args: int) -> None:
        """Call a function indirectly via pointer."""
        self.prepare_args(num_args)
        self._emit("popq %rax")  # fn ptr
        self._emit("call *%rax")
    
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
            self._emit("popq %rax")
            self._emit("syscall")
        elif num_args == 3:
            self._emit("movq %rax, %rsi")
            self._emit("popq %rdi")
            self._emit("popq %rax")
            self._emit("syscall")
        elif num_args == 4:
            self._emit("movq %rax, %rdx")
            self._emit("popq %rsi")
            self._emit("popq %rdi")
            self._emit("popq %rax")
            self._emit("syscall")
        elif num_args == 5:
            self._emit("movq %rax, %r10")
            self._emit("popq %rdx")
            self._emit("popq %rsi")
            self._emit("popq %rdi")
            self._emit("popq %rax")
            self._emit("syscall")
        elif num_args == 6:
            self._emit("movq %rax, %r8")
            self._emit("popq %r10")
            self._emit("popq %rdx")
            self._emit("popq %rsi")
            self._emit("popq %rdi")
            self._emit("popq %rax")
            self._emit("syscall")
        elif num_args == 7:
            self._emit("movq %rax, %r9")
            self._emit("popq %r8")
            self._emit("popq %r10")
            self._emit("popq %rdx")
            self._emit("popq %rsi")
            self._emit("popq %rdi")
            self._emit("popq %rax")
            self._emit("syscall")
    
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
