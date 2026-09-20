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

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path

from .. import t1

CORE_INTRINSIC_ARITIES: dict[str, int] = {
    "__load_u8__": 1,
    "__load_u16__": 1,
    "__load_u32__": 1,
    "__load_u64__": 1,
    "__store_u8__": 2,
    "__store_u16__": 2,
    "__store_u32__": 2,
    "__store_u64__": 2,
    "__load_i8__": 1,
    "__load_i16__": 1,
    "__load_i32__": 1,
    "__load_i64__": 1,
    "__store_i8__": 2,
    "__store_i16__": 2,
    "__store_i32__": 2,
    "__store_i64__": 2,
    "__load__": 1,
    "__store__": 2,
    "__alloca__": 1,
    "__static_alloca__": 1,
    "__signed_shr__": 2,
    "__unsigned_idiv__": 2,
    "__unsigned_mod__": 2,
    "__unsigned_lt__": 2,
    "__unsigned_gt__": 2,
    "__unsigned_lte__": 2,
    "__unsigned_gte__": 2,
    "__breakpoint__": 0,
}


def wrap_i64(value: int) -> int:
    """Spell a word constant as the native compiler does.

    µDewy words are 64-bit two's complement; the hosted tokenizer keeps
    Python integers, so 0xFFFF_FFFF_FFFF_FFFF and -1 must become the same
    immediate before any backend prints it.
    """
    return ((value + (1 << 63)) & ((1 << 64) - 1)) - (1 << 63)


@dataclass
class RunOptions:
    split_wasm: bool = False
    serve_wasm: bool = False
    input_file: Path | None = None
    link_artifacts: list[Path] = field(default_factory=list)
    env: dict[str, str] | None = None

class Backend(ABC):
    """
    Protocol defining the interface between parser and code generator.
    
    Backends track a logical value stack internally. The parser doesn't
    know about registers, physical stacks, or calling conventions - it
    only knows that expressions produce values and operations consume them.
    """
    
    # Set before parsing. This controls metadata only; source diagnostics and
    # breakpoint instructions remain available when it is false.
    debug_info: bool = True

    # ========================================================================
    # Module lifecycle
    # ========================================================================
    
    @abstractmethod
    def begin_module(self) -> None:
        """Initialize the module for code generation."""
    
    @abstractmethod
    def finish_module(self) -> str:
        """
        Finalize and return a string of the generated artifact (assembly, WAT, etc.).
        """

    @abstractmethod
    def set_module_init(self, name: str | None) -> None:
        """
        Register an optional synthetic module initializer.

        Backends should run this initializer exactly once before user-visible entry
        points when a name is provided.
        """

    def mark_location(self, path: str, line: int, column: int) -> None:
        """
        Note the source position of the code emitted next (debug information).

        The parser reports the position of every statement: by default the
        udewy source's own, or the position a `# @loc path:line:column` comment
        names for the statements that follow it (a compiler emitting udewy uses
        it to point a debugger at the original source). Purely metadata — a
        backend that ignores it produces the same program — so the default does
        nothing.
        """

    def note_local(self, slot: int, name: str, type_name: str, formatter: str | None = None, *, parameter: bool = False) -> None:
        """
        Name a local slot for the debugger (debug information).

        Called after ``alloc_local`` for every declared variable and parameter
        with the source name and a type name: the udewy annotation, or what a
        `# @var name shown formatter type` comment before the declaration
        supplies — a compiler emitting udewy names the original type, and
        ``formatter`` a function in the program a debugger may call to render
        the value. ``parameter`` marks a function parameter (visible
        throughout the function). Metadata only; the default does nothing.
        """

    def begin_scope(self) -> None:
        """A lexical scope opens (debug information; the default does nothing)."""

    def end_scope(self) -> None:
        """The innermost lexical scope closes (debug information; the default does nothing)."""

    def set_imported_sources(self, paths: list[Path]) -> None:
        """
        Receive the resolved udewy source paths imported by the entrypoint.

        The import preprocessor does not interpret these paths beyond recording
        provenance. Backends may use them to recognize target-specific library
        modules without adding backend knowledge to the core loader.
        """
        pass
    
    # ========================================================================
    # Data section - strings and globals
    # ========================================================================
    
    @abstractmethod
    def intern_string(self, content: bytes) -> int:
        """
        Add a string constant to the data section.
        
        The string is stored with a length prefix (8 bytes).
        Returns a handle/label_id that can be used with push_string_ref.
        """
    
    @abstractmethod
    def define_global(self, name: str | None, value: int | str) -> int:
        """
        Define a global variable with an initial value.
        
        Value can be an integer or a label reference (string).
        Returns a handle/label_id for the global.
        """

    @abstractmethod
    def declare_extern_global(self, name: str) -> int:
        """
        Declare a global variable whose storage is provided by a linked artifact.

        Returns a handle/label_id for the global.
        """
    
    @abstractmethod
    def intern_static(self, size: int) -> int:
        """
        Add a zero-initialized static storage block to the data section.

        The block has no length prefix and is returned as raw writable storage.
        Returns a handle/label_id that can be used with push_static_ref.
        """

    @abstractmethod
    def intern_words(self, elements: list[int | str]) -> int:
        """
        Add initialized raw 64-bit words to the data section.

        The block has no length prefix and is returned as raw writable storage.
        Returns a handle/label_id that can be used with push_static_ref.
        """
    
    
    @abstractmethod
    def push_string_ref(self, label_id: int) -> None:
        """Push address of string data (after length prefix) onto value stack."""
    
    @abstractmethod
    def push_global_ref(self, label_id: int) -> None:
        """Push address of global onto value stack."""

    @abstractmethod
    def push_static_ref(self, label_id: int) -> None:
        """Push address of raw static storage onto value stack."""
    
    @abstractmethod
    def load_global(self, label_id: int) -> None:
        """Load value of global onto value stack."""
    
    @abstractmethod
    def store_global(self, label_id: int) -> None:
        """Pop value from stack and store to global."""

    @abstractmethod
    def function_ref(self, label_id: int) -> int | str:
        """Return a backend-native constant reference to a function."""

    @abstractmethod
    def string_ref(self, label_id: int) -> int | str:
        """Return a backend-native constant reference to string data."""

    @abstractmethod
    def static_ref(self, label_id: int) -> int | str:
        """Return a backend-native constant reference to static storage."""
    
    # ========================================================================
    # Functions
    # ========================================================================
    
    @abstractmethod
    def declare_function(self, name: str | None, num_params: int) -> int:
        """
        Declare a function (forward reference or definition).
        
        Returns a function label_id.
        """

    @abstractmethod
    def bind_extern_function(self, label_id: int, name: str) -> None:
        """Bind an existing function label to an externally provided symbol."""

    @abstractmethod
    def declare_extern_function(self, name: str, num_params: int) -> int:
        """
        Declare a function whose implementation is provided by a linked artifact.

        Returns a function label_id.
        """

    def should_warn_unused_extern(self, name: str) -> bool:
        """
        Return whether an unreachable extern declaration should be reported.

        Most backends should warn. Backends with source-level capability modules
        can suppress warnings for intentionally imported optional declarations.
        """
        return True
    
    @abstractmethod
    def begin_function(self, label_id: int, name: str, param_count: int, is_main: bool) -> None:
        """
        Begin function definition.
        
        Sets up the function prologue and prepares for parameter/local allocation.
        """
    
    @abstractmethod
    def end_function(self) -> None:
        """
        End function definition.
        
        Emits the function epilogue.
        """

    @abstractmethod
    def set_reachable_functions(self, label_ids: set[int]) -> None:
        """
        Restrict emitted function bodies in finish_module to this set.

        The parser computes the transitive closure of function references reachable
        from program entry points (main, global initializers, top-level data
        references, externs) and calls this before finish_module so the backend
        can drop unreachable bodies from its output.
        """
    
    @abstractmethod
    def load_param(self, index: int) -> None:
        """Push the value of parameter at index onto the value stack."""
    
    @abstractmethod
    def alloc_local(self) -> int:
        """
        Allocate a local variable slot.
        
        Returns a slot identifier for use with load_local/store_local.
        """
    
    @abstractmethod
    def load_local(self, slot: int) -> None:
        """Push the value of local variable at slot onto the value stack."""
    
    @abstractmethod
    def store_local(self, slot: int) -> None:
        """Pop value from stack and store to local variable slot."""
    
    # ========================================================================
    # Value stack operations
    # ========================================================================
    
    @abstractmethod
    def push_const_i64(self, value: int) -> None:
        """Push a 64-bit integer constant onto the value stack."""
    
    @abstractmethod
    def push_void(self) -> None:
        """Push void (zero) onto the value stack."""
    
    @abstractmethod
    def push_fn_ref(self, label_id: int) -> None:
        """Push address of function onto the value stack."""

    @abstractmethod
    def pop_value(self) -> None:
        """Discard the top value on the stack."""

    @abstractmethod    
    def save_value(self) -> None:
        """
        Preserve the current top value for later backend operations.
        
        The parser uses this before operations that need to keep an earlier value
        alive while evaluating more expressions. A backend may spill the value to
        physical storage, keep it in an auxiliary stack, or rely on a native
        operand stack as long as later parser-driven operations see the expected
        logical ordering.
        """

    @abstractmethod
    def restore_value(self) -> None:
        """
        Re-expose the most recently preserved value on top of the value stack.
        
        This is only used in the parser paths that explicitly need the saved
        value again as the visible top-of-stack value.
        """
    
    # ========================================================================
    # Operators
    # ========================================================================
    
    @abstractmethod
    def unary_op(self, op_kind: t1.Kind) -> None:
        """
        Apply unary operator to top of stack.
        
        Supported operators (token kinds from t1):
        - TK_MINUS: arithmetic negation
        - TK_NOT: bitwise not
        """
    
    @abstractmethod
    def binary_op(self, op_kind: t1.Kind) -> None:
        """
        Apply binary operator to top two values on stack.
        
        Pops two values (right then left), pushes result.
        
        Supported operators (token kinds from t1):
        - Arithmetic: TK_PLUS, TK_MINUS, TK_MUL, TK_IDIV, TK_MOD
        - Bitwise: TK_AND, TK_OR, TK_XOR, TK_LEFT_SHIFT, TK_RIGHT_SHIFT
        - Comparison: TK_EQ, TK_NOT_EQ, TK_LT, TK_GT, TK_LT_EQ, TK_GT_EQ
        """

    def binary_immediate(self, op_kind: t1.Kind, value: int) -> None:
        """Combine the current value with a literal, preserving older operands.

        Targets may consume the literal directly; the ordinary value-stack
        sequence remains the default and defines the operation's semantics.
        """
        self.save_value()
        self.push_const_i64(value)
        self.binary_op(op_kind)

    # ========================================================================
    # Memory operations (intrinsics)
    # ========================================================================
    
    @abstractmethod
    def load_mem(self, width: int, signed: bool = False) -> None:
        """
        Load from memory address on top of stack.
        
        Pops address, pushes loaded value.
        Width is 8, 16, 32, or 64 bits.
        Signed loads sign-extend for sub-64-bit widths.
        """
    
    @abstractmethod
    def store_mem(self, width: int) -> None:
        """
        Store to memory.
        
        Stack: [... value addr] -> [...]
        Pops address and value, stores value to address, pushes 0.
        Width is 8, 16, 32, or 64 bits.
        """
    
    @abstractmethod
    def signed_shr(self) -> None:
        """
        Signed (arithmetic) right shift.
        
        Stack: [... value bits] -> [... result]
        Pops shift amount and value, pushes value >> bits with sign extension.
        """
    
    # ========================================================================
    # Calls
    # ========================================================================
    
    @abstractmethod
    def call_direct(self, label_id: int, num_args: int) -> None:
        """
        Call a function directly by label.
        
        Pops num_args values from stack, calls function, pushes return value.
        Arguments are consumed in reverse order (last pushed = last arg).
        """
    
    @abstractmethod
    def call_indirect(self, num_args: int) -> None:
        """
        Call a function indirectly via pointer on stack.
        
        Stack: [... fn_ptr arg1 arg2 ... argN] -> [... result]
        Function pointer was pushed, then args were pushed.
        """

    @abstractmethod
    def max_call_args(self) -> int | None:
        """
        Return the maximum number of call arguments this backend can marshal.

        Return None when the backend has no practical fixed limit at the code
        generation layer.
        """

    # ========================================================================
    # Control flow
    # ========================================================================
    
    @abstractmethod
    def begin_if(self) -> None:
        """
        Begin an if statement.
        
        Consumes condition from value stack. If zero, jumps to else/end.
        """
    
    @abstractmethod
    def begin_else(self) -> None:
        """
        Begin the else branch of an if statement.
        
        Must be called after begin_if's then-block.
        """
    
    @abstractmethod
    def end_if(self) -> None:
        """End an if statement (closes then or else block)."""
    
    @abstractmethod
    def begin_loop(self) -> None:
        """
        Begin a loop.
        
        Marks the loop start point. Condition should be evaluated after
        this, then begin_loop_body called.
        """
    
    @abstractmethod
    def begin_loop_body(self) -> None:
        """
        Begin the loop body.
        
        Consumes condition from value stack. If zero, exits loop.
        """
    
    @abstractmethod
    def end_loop(self) -> None:
        """End a loop (jumps back to condition check)."""

    @abstractmethod
    def emit_break(self) -> None:
        """Emit a break statement (jump to end of current loop)."""
    
    @abstractmethod
    def emit_continue(self) -> None:
        """Emit a continue statement (jump to start of current loop)."""

    @abstractmethod
    def cond_and_split(self) -> str:
        """After logical-AND left operand is visible. Branch to returned label if zero."""

    @abstractmethod
    def cond_and_join(self, false_label: str) -> None:
        """Complete logical-AND after right operand is visible."""

    @abstractmethod
    def cond_or_split(self) -> str:
        """After logical-OR left operand is visible. Branch to returned label if non-zero."""

    @abstractmethod
    def cond_or_join(self, done_label: str) -> None:
        """Complete logical-OR after optional right operand is visible."""
    
    @abstractmethod
    def emit_return(self) -> None:
        """
        Emit a return statement.
        
        Return value should be on top of stack.
        """
    
    # ========================================================================
    # Intrinsics
    # ========================================================================
    
    @abstractmethod
    def is_intrinsic(self, name: str) -> bool:
        """
        Check if the given name is an intrinsic supported by this backend.
        
        Backends should return True for both core intrinsics (load/store, etc.)
        and any platform-specific intrinsics they support.
        """

    @abstractmethod
    def intrinsic_arity(self, name: str) -> int | None:
        """
        Return the expected arity for a supported intrinsic.

        Return None when the intrinsic is not supported by this backend.
        """

    def intrinsic_static_arg_indices(self, name: str) -> set[int]:
        """
        Return zero-based intrinsic argument indices that must be compile-time
        integer constants and should not be emitted as runtime arguments.
        """
        return set()
    
    @abstractmethod
    def emit_intrinsic(self, name: str, num_args: int, intrinsic_data: object | None = None) -> None:
        """
        Emit code for an intrinsic call.
        
        Called after arguments have been pushed to the stack.
        The backend is responsible for consuming the arguments and
        leaving the result on the stack.
        """
    
    @abstractmethod
    def get_builtin_constants(self) -> dict[str, int]:
        """
        Return a dictionary of built-in constants provided by this backend.
        
        These constants are automatically available in udewy programs
        targeting this backend. Typically used for syscall numbers on
        Linux backends.
        
        Returns: dict mapping constant name to value
        """
    
    # ========================================================================
    # Compilation and execution
    # ========================================================================
    
    @abstractmethod
    def compile_and_link(self, code: str, input_name: str, cache_dir: Path, **options) -> Path:
        """
        Compile and link the generated code.
        
        Takes the output of finish_module() and produces an executable or
        runnable artifact. Returns path to the primary output file.
        
        Args:
            code: The generated code (assembly, WAT, etc.) from finish_module()
            input_name: Name of the input file (without extension)
            cache_dir: Directory to write output files
            **options: Backend-specific options (e.g., split_wasm for WASM,
                link_artifacts for native targets, imported_sources for source
                import provenance)
        
        Returns:
            Path to the primary output file
        """
    
    @abstractmethod
    def run(self, output_path: PathLike, args: list[str], options: RunOptions | None = None) -> int | None:
        """
        Run the compiled output.
        
        Args:
            output_path: Path to the compiled output (from compile_and_link)
            args: Command-line arguments to pass to the program
            options: Backend-specific runtime options
        
        Returns:
            Exit code of the program, or None if running is not supported
            (e.g., WASM needs a browser)
        """

    @abstractmethod    
    def get_compile_message(self, output_path: Path, **options) -> str:
        """
        Get a message to display after successful compilation.
        
        Args:
            output_path: Path to the compiled output
            **options: Backend-specific options
        
        Returns:
            Human-readable message about the output
        """


class LocalRegisterAllocator:
    """Live-interval register allocation for frame-slot locals.

    Mirrors la_* in udewy/bootstrap/backend/common.udewy. Native backends keep
    every local in a frame slot and record each access as a site: the code
    line that reads or writes the slot, the slot's dense key, the other
    operand of the move, and whether it is a store. µDewy has no
    address-of-local operation, so the recorded sites are every use of a
    slot. At the end of a function the sites become live intervals; a linear
    scan hands the busiest intervals registers and the backend rewrites their
    sites into register moves. Slots keep their frame homes, so frame sizes
    and alignment do not change.

    Intervals are line ranges. A value declared before a loop and touched
    inside it lives around the whole loop; a slot allocated inside the loop
    (its `let` is in the body) cannot be read before the body stores it
    again, so such loops never widen its interval. Clobber lines (calls,
    syscalls) split the register file: an interval spanning one may only use
    a register the callee preserves; a call-free interval prefers a scratch
    register.
    """

    def __init__(self) -> None:
        self.begin_function()

    def begin_function(self) -> None:
        self._sites: list[tuple[int, int, str, bool]] = []
        self._scores: list[int] = []
        self._alloc_lines: list[int] = []
        self._pinned: list[bool] = []
        self._loops: list[tuple[int, int]] = []
        self._open_loops: list[int] = []
        self._clobbers: list[int] = []
        self.assignment: list[str | None] = []

    def _ensure_key(self, key: int) -> None:
        while len(self._scores) <= key:
            self._scores.append(0)
            self._alloc_lines.append(-1)
            self._pinned.append(False)

    def note_alloc(self, key: int, line: int) -> None:
        self._ensure_key(key)
        if self._alloc_lines[key] < 0:
            self._alloc_lines[key] = line

    def pin(self, key: int) -> None:
        self._ensure_key(key)
        self._pinned[key] = True

    def loop_depth(self) -> int:
        return len(self._open_loops)

    def note_site(self, line: int, key: int, other: str, store: bool) -> None:
        self._ensure_key(key)
        self._scores[key] += 1 << (3 * min(len(self._open_loops), 3))
        self._sites.append((line, key, other, store))

    def begin_loop(self, line: int) -> None:
        self._open_loops.append(line)

    def end_loop(self, line: int) -> None:
        self._loops.append((self._open_loops.pop(), line))

    def note_clobber(self, line: int) -> None:
        self._clobbers.append(line)

    def assign(self, callee_regs: list[str], caller_regs: list[str]) -> None:
        """Fill `assignment` (key -> register or None)."""
        keys = len(self._scores)
        self.assignment = [None] * keys
        starts = [-1] * keys
        ends = [-1] * keys
        counts = [0] * keys
        for line, key, _other, _store in self._sites:
            if starts[key] < 0 or line < starts[key]:
                starts[key] = line
            if line > ends[key]:
                ends[key] = line
            counts[key] += 1
        # Loops finish inner before outer, so one pass in finishing order
        # widens an interval through every loop that carries it around a
        # back edge.
        for loop_start, loop_end in self._loops:
            for k in range(keys):
                if counts[k] > 0 and self._alloc_lines[k] < loop_start:
                    if starts[k] <= loop_end and ends[k] >= loop_start:
                        starts[k] = min(starts[k], loop_start)
                        ends[k] = max(ends[k], loop_end)
        order = sorted(
            (k for k in range(keys) if counts[k] >= 2 and not self._pinned[k]),
            key=lambda k: starts[k],
        )
        callee_count = len(callee_regs)
        reg_count = callee_count + len(caller_regs)
        holders = [-1] * reg_count
        clobber_cursor = 0
        for key in order:
            start = starts[key]
            end = ends[key]
            for r in range(reg_count):
                if holders[r] >= 0 and ends[holders[r]] < start:
                    holders[r] = -1
            while clobber_cursor < len(self._clobbers) and self._clobbers[clobber_cursor] < start:
                clobber_cursor += 1
            spans_clobber = clobber_cursor < len(self._clobbers) and self._clobbers[clobber_cursor] < end
            last = callee_count if spans_clobber else reg_count
            chosen = -1
            for r in range(0 if spans_clobber else callee_count, last):
                if holders[r] < 0:
                    chosen = r
                    break
            if chosen < 0 and not spans_clobber:
                for r in range(callee_count):
                    if holders[r] < 0:
                        chosen = r
                        break
            if chosen < 0:
                victim = -1
                victim_score = 0
                for r in range(last):
                    holder = holders[r]
                    if holder >= 0 and (victim < 0 or self._scores[holder] < victim_score):
                        victim = r
                        victim_score = self._scores[holder]
                if victim >= 0 and victim_score < self._scores[key]:
                    self.assignment[holders[victim]] = None
                    chosen = victim
            if chosen >= 0:
                holders[chosen] = key
                if chosen < callee_count:
                    self.assignment[key] = callee_regs[chosen]
                else:
                    self.assignment[key] = caller_regs[chosen - callee_count]

    def rewrite(self, code: list[str], format_move) -> None:
        """Rewrite every site of an assigned slot into a register move.

        `format_move(src, dst)` produces the full code line.
        """
        for line, key, other, store in self._sites:
            register = self.assignment[key]
            if register is not None:
                code[line] = format_move(other, register) if store else format_move(register, other)
