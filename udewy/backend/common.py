"""
Backend protocol for udewy code generation.

Each backend implements this protocol to generate code for a specific target.
The parser calls these methods during single-pass parsing, and each backend
is responsible for translating the semantic operations into target-specific
code.

The protocol uses a virtual value stack model:
- Expression evaluation pushes values onto the stack
- Operators consume values from the stack and push results
- Only explicit local/global storage persists values
"""

from typing import Protocol
from pathlib import Path
from os import PathLike


class Backend(Protocol):
    """
    Protocol defining the interface between parser and code generator.
    
    Backends track a logical value stack internally. The parser doesn't
    know about registers, physical stacks, or calling conventions - it
    only knows that expressions produce values and operations consume them.
    """
    
    # ========================================================================
    # Module lifecycle
    # ========================================================================
    
    def begin_module(self) -> None:
        """Initialize the module for code generation."""
        ...
    
    def finish_module(self) -> bytes | str:
        """
        Finalize and return the generated artifact.
        
        Returns either raw bytes (for binary formats) or a string
        (for text assembly formats).
        """
        ...
    
    # ========================================================================
    # Data section - strings, arrays, globals
    # ========================================================================
    
    def intern_string(self, content: bytes) -> int:
        """
        Add a string constant to the data section.
        
        The string is stored with a length prefix (8 bytes).
        Returns a handle/label_id that can be used with push_string_ref.
        """
        ...
    
    def intern_array(self, elements: list[int | str]) -> int:
        """
        Add an array constant to the data section.
        
        Elements can be integers or label references (as strings).
        The array is stored with a length prefix (8 bytes).
        Returns a handle/label_id that can be used with push_array_ref.
        """
        ...
    
    def define_global(self, name_id: int, value: int | str) -> int:
        """
        Define a global variable with an initial value.
        
        Value can be an integer or a label reference (string).
        Returns a handle/label_id for the global.
        """
        ...
    
    def push_string_ref(self, label_id: int) -> None:
        """Push address of string data (after length prefix) onto value stack."""
        ...
    
    def push_array_ref(self, label_id: int) -> None:
        """Push address of array data (after length prefix) onto value stack."""
        ...
    
    def push_global_ref(self, label_id: int) -> None:
        """Push address of global onto value stack."""
        ...
    
    def load_global(self, label_id: int) -> None:
        """Load value of global onto value stack."""
        ...
    
    def store_global(self, label_id: int) -> None:
        """Pop value from stack and store to global."""
        ...
    
    # ========================================================================
    # Functions
    # ========================================================================
    
    def declare_function(self, name_id: int, num_params: int) -> int:
        """
        Declare a function (forward reference or definition).
        
        Returns a function label_id.
        """
        ...
    
    def begin_function(self, label_id: int, name: str, param_count: int, is_main: bool) -> None:
        """
        Begin function definition.
        
        Sets up the function prologue and prepares for parameter/local allocation.
        """
        ...
    
    def end_function(self) -> None:
        """
        End function definition.
        
        Emits the function epilogue.
        """
        ...
    
    def load_param(self, index: int) -> None:
        """Push the value of parameter at index onto the value stack."""
        ...
    
    def alloc_local(self) -> int:
        """
        Allocate a local variable slot.
        
        Returns a slot identifier for use with load_local/store_local.
        """
        ...
    
    def load_local(self, slot: int) -> None:
        """Push the value of local variable at slot onto the value stack."""
        ...
    
    def store_local(self, slot: int) -> None:
        """Pop value from stack and store to local variable slot."""
        ...
    
    # ========================================================================
    # Value stack operations
    # ========================================================================
    
    def push_const_i64(self, value: int) -> None:
        """Push a 64-bit integer constant onto the value stack."""
        ...
    
    def push_void(self) -> None:
        """Push void (zero) onto the value stack."""
        ...
    
    def push_fn_ref(self, label_id: int) -> None:
        """Push address of function onto the value stack."""
        ...
    
    def dup_value(self) -> None:
        """Duplicate the top value on the stack."""
        ...
    
    def pop_value(self) -> None:
        """Discard the top value on the stack."""
        ...
    
    def save_value(self) -> None:
        """
        Save the top value to backend-managed temporary storage.
        
        Used when the parser needs to preserve a value across other operations.
        Must be balanced with restore_value.
        """
        ...
    
    def restore_value(self) -> None:
        """
        Restore a previously saved value to the top of the stack.
        
        Must be preceded by save_value.
        """
        ...
    
    # ========================================================================
    # Operators
    # ========================================================================
    
    def unary_op(self, op: str) -> None:
        """
        Apply unary operator to top of stack.
        
        Supported operators:
        - 'neg': arithmetic negation
        - 'not': bitwise not
        """
        ...
    
    def binary_op(self, op: str) -> None:
        """
        Apply binary operator to top two values on stack.
        
        Pops two values (right then left), pushes result.
        
        Supported operators:
        - Arithmetic: '+', '-', '*', '//', '%'
        - Bitwise: 'and', 'or', 'xor', '<<', '>>'
        - Comparison: '=?', 'not=?', '<?', '>?', '<=?', '>=?'
        - Pipe: '|>' (special handling - call RHS with LHS as arg)
        """
        ...
    
    # ========================================================================
    # Memory operations (intrinsics)
    # ========================================================================
    
    def load_mem(self, width: int) -> None:
        """
        Load from memory address on top of stack.
        
        Pops address, pushes loaded value.
        Width is 8, 16, 32, or 64 bits.
        """
        ...
    
    def store_mem(self, width: int) -> None:
        """
        Store to memory.
        
        Stack: [... value addr] -> [...]
        Pops address and value, stores value to address, pushes 0.
        Width is 8, 16, 32, or 64 bits.
        """
        ...
    
    def signed_shr(self) -> None:
        """
        Signed (arithmetic) right shift.
        
        Stack: [... value bits] -> [... result]
        Pops shift amount and value, pushes value >> bits with sign extension.
        """
        ...
    
    # ========================================================================
    # Calls
    # ========================================================================
    
    def call_direct(self, label_id: int, num_args: int) -> None:
        """
        Call a function directly by label.
        
        Pops num_args values from stack, calls function, pushes return value.
        Arguments are consumed in reverse order (last pushed = last arg).
        """
        ...
    
    def call_indirect(self, num_args: int) -> None:
        """
        Call a function indirectly via pointer on stack.
        
        Stack: [... fn_ptr arg1 arg2 ... argN] -> [... result]
        Function pointer was pushed, then args were pushed.
        """
        ...
    
    def syscall(self, num_args: int) -> None:
        """
        Invoke a syscall.
        
        Stack: [... syscall_num arg1 arg2 ... argN] -> [... result]
        Syscall number was pushed first, then args.
        """
        ...
    
    # ========================================================================
    # Control flow
    # ========================================================================
    
    def begin_if(self) -> None:
        """
        Begin an if statement.
        
        Consumes condition from value stack. If zero, jumps to else/end.
        """
        ...
    
    def begin_else(self) -> None:
        """
        Begin the else branch of an if statement.
        
        Must be called after begin_if's then-block.
        """
        ...
    
    def end_if(self) -> None:
        """End an if statement (closes then or else block)."""
        ...
    
    def begin_loop(self) -> None:
        """
        Begin a loop.
        
        Marks the loop start point. Condition should be evaluated after
        this, then begin_loop_body called.
        """
        ...
    
    def begin_loop_body(self) -> None:
        """
        Begin the loop body.
        
        Consumes condition from value stack. If zero, exits loop.
        """
        ...
    
    def end_loop(self) -> None:
        """End a loop (jumps back to condition check)."""
        ...
    
    def emit_break(self) -> None:
        """Emit a break statement (jump to end of current loop)."""
        ...
    
    def emit_continue(self) -> None:
        """Emit a continue statement (jump to start of current loop)."""
        ...
    
    def emit_return(self) -> None:
        """
        Emit a return statement.
        
        Return value should be on top of stack.
        """
        ...


# Type alias for backend constructors
type BackendFactory = type[Backend]
