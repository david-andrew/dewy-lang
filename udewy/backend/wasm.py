"""
wasm32 backend for udewy.

Generates WebAssembly Text format (WAT) with browser-focused host function imports.

Semantic choices:
- All udewy values are i64 (wasm i64)
- Pointers are i64 values but truncated to i32 at every memory operation
- Strings/arrays use the same length-prefixed layout (length at ptr-8)
- Browser functionality via imported JS host functions (no syscall emulation)

Host functions provided by JS:
- host_log(ptr, len): Output text to console/output element
- host_exit(code): Signal program exit
- host_time() -> i64: Current timestamp in milliseconds
- host_random() -> i64: Random 64-bit integer
"""

from pathlib import Path


class Wasm32Backend:
    """
    WebAssembly code generator implementing the Backend protocol.
    
    Value stack model:
    - Uses wasm's native operand stack directly
    - i64 values throughout
    - Addresses truncated to i32 at memory operations
    """
    
    def __init__(self) -> None:
        self._imports: list[str] = []
        self._functions: list[str] = []
        self._current_fn: list[str] = []
        self._data_segments: list[tuple[int, bytes]] = []
        self._next_label: int = 0
        self._data_offset: int = 1024  # Start data after initial memory
        
        # Function state
        self._current_fn_name: str = ""
        self._local_count: int = 0
        self._param_count: int = 0
        
        # Control flow state - track block nesting depth
        self._if_stack: list[int] = []  # block depths
        self._loop_stack: list[tuple[str, str]] = []  # (loop_label, block_label)
        self._block_depth: int = 0
        
        # Symbol tracking
        self._fn_labels: dict[int, str] = {}
        self._fn_indices: dict[int, int] = {}
        self._global_offsets: dict[int, int] = {}
        self._global_labels: dict[int, str] = {}
        self._string_offsets: dict[int, int] = {}
        self._string_labels: dict[int, str] = {}
        self._array_offsets: dict[int, int] = {}
        self._array_labels: dict[int, str] = {}
        
        # Track which functions are defined
        self._defined_fns: set[int] = set()
        
        # Next function index (after imports)
        self._next_fn_index: int = 0
        
        # Setup imports for syscalls
        self._setup_imports()
    
    def _setup_imports(self) -> None:
        """Setup JS host function imports for browser functionality."""
        host_imports = [
            # Direct browser APIs
            '(import "env" "host_log" (func $host_log (param i64 i64) (result i64)))',
            '(import "env" "host_exit" (func $host_exit (param i64) (result i64)))',
            '(import "env" "host_time" (func $host_time (result i64)))',
            '(import "env" "host_random" (func $host_random (result i64)))',
            # DOM manipulation
            '(import "env" "host_dom_set_text" (func $host_dom_set_text (param i64 i64) (result i64)))',
            '(import "env" "host_dom_append" (func $host_dom_append (param i64 i64) (result i64)))',
            '(import "env" "host_dom_clear" (func $host_dom_clear (result i64)))',
            '(import "env" "host_dom_append_int" (func $host_dom_append_int (param i64) (result i64)))',
            '(import "env" "host_log_int" (func $host_log_int (param i64) (result i64)))',
        ]
        self._imports.extend(host_imports)
        self._next_fn_index = 9  # 9 host function imports
    
    def _new_label(self, prefix: str = "L") -> str:
        label = f"${prefix}{self._next_label}"
        self._next_label += 1
        return label
    
    def _emit(self, instr: str) -> None:
        """Emit an instruction to current function."""
        self._current_fn.append("    " + instr)
    
    def _alloc_data(self, data: bytes) -> int:
        """Allocate data in linear memory, return offset."""
        offset = self._data_offset
        self._data_segments.append((offset, data))
        self._data_offset += len(data)
        # Align to 8 bytes
        if self._data_offset % 8 != 0:
            self._data_offset += 8 - (self._data_offset % 8)
        return offset
    
    # ========================================================================
    # Module lifecycle
    # ========================================================================
    
    def begin_module(self) -> None:
        """Initialize the module for code generation."""
        pass
    
    def finish_module(self) -> str:
        """Finalize and return the generated WAT."""
        output = []
        output.append("(module")
        
        # Memory import (for JS interop)
        output.append('  (import "env" "memory" (memory 1))')
        
        # Syscall imports
        for imp in self._imports:
            output.append(f"  {imp}")
        
        # Functions
        for fn in self._functions:
            output.append(fn)
        
        # Data segments
        for offset, data in self._data_segments:
            hex_data = "".join(f"\\{b:02x}" for b in data)
            output.append(f'  (data (i32.const {offset}) "{hex_data}")')
        
        # Export main
        output.append('  (export "main" (func $main))')
        
        output.append(")")
        return "\n".join(output)
    
    # ========================================================================
    # Data section
    # ========================================================================
    
    def intern_string(self, content: bytes) -> int:
        """Add a string constant to the data section."""
        label_id = self._next_label
        self._next_label += 1
        
        # Length prefix (8 bytes, little-endian i64)
        length_bytes = len(content).to_bytes(8, 'little')
        full_data = length_bytes + content
        
        offset = self._alloc_data(full_data)
        self._string_offsets[label_id] = offset
        self._string_labels[label_id] = f".str{label_id}"
        
        return label_id
    
    def intern_array(self, elements: list[int | str]) -> int:
        """Add an array constant to the data section."""
        label_id = self._next_label
        self._next_label += 1
        
        # Length prefix
        length_bytes = len(elements).to_bytes(8, 'little')
        
        # Elements
        elem_bytes = b""
        for elem in elements:
            if isinstance(elem, int):
                elem_bytes += elem.to_bytes(8, 'little', signed=True)
            elif isinstance(elem, str) and "+8" in elem:
                # String/array reference
                ref_part = elem.replace("+8", "")
                ref_offset = 0
                for sid, slabel in self._string_labels.items():
                    if slabel == ref_part:
                        ref_offset = self._string_offsets[sid] + 8
                        break
                elem_bytes += ref_offset.to_bytes(8, 'little', signed=True)
            else:
                elem_bytes += b"\x00" * 8
        
        full_data = length_bytes + elem_bytes
        offset = self._alloc_data(full_data)
        self._array_offsets[label_id] = offset
        self._array_labels[label_id] = f".arr{label_id}"
        
        return label_id
    
    def define_global(self, name_id: int, value: int | str) -> int:
        """Define a global variable."""
        label_id = self._next_label
        self._next_label += 1
        
        if isinstance(value, int):
            actual_value = value
        elif isinstance(value, str):
            # Parse the reference to extract the actual offset
            # Format: ".strN+8" or ".arrN+8" or ".globalN"
            if "+8" in value:
                # It's a reference to string/array data (skip length prefix)
                ref_part = value.replace("+8", "")
                # Find the base offset from our labels
                for sid, slabel in self._string_labels.items():
                    if slabel == ref_part:
                        actual_value = self._string_offsets[sid] + 8
                        break
                else:
                    for aid, alabel in self._array_labels.items():
                        if alabel == ref_part:
                            actual_value = self._array_offsets[aid] + 8
                            break
                    else:
                        actual_value = 0
            else:
                actual_value = 0
        else:
            actual_value = 0
        
        data = actual_value.to_bytes(8, 'little', signed=True)
        offset = self._alloc_data(data)
        self._global_offsets[label_id] = offset
        self._global_labels[label_id] = f".global{label_id}"
        
        return label_id
    
    def push_string_ref(self, label_id: int) -> None:
        """Push address of string data onto value stack."""
        offset = self._string_offsets[label_id] + 8  # Skip length prefix
        self._emit(f"i64.const {offset}")
    
    def push_array_ref(self, label_id: int) -> None:
        """Push address of array data onto value stack."""
        offset = self._array_offsets[label_id] + 8  # Skip length prefix
        self._emit(f"i64.const {offset}")
    
    def push_global_ref(self, label_id: int) -> None:
        """Push address of global onto value stack."""
        offset = self._global_offsets[label_id]
        self._emit(f"i64.const {offset}")
    
    def load_global(self, label_id: int) -> None:
        """Load value of global onto value stack."""
        offset = self._global_offsets[label_id]
        self._emit(f"i32.const {offset}")
        self._emit("i64.load")
    
    def store_global(self, label_id: int) -> None:
        """Pop value from stack and store to global."""
        offset = self._global_offsets[label_id]
        self._emit(f"i32.const {offset}")
        self._emit("i64.store")
    
    # ========================================================================
    # Functions
    # ========================================================================
    
    def declare_function(self, name_id: int, num_params: int) -> int:
        """Declare a function."""
        label_id = self._next_label
        self._next_label += 1
        fn_name = f"$fn{label_id}"
        self._fn_labels[label_id] = fn_name
        self._fn_indices[label_id] = self._next_fn_index
        self._next_fn_index += 1
        return label_id
    
    def begin_function(self, label_id: int, name: str, param_count: int, is_main: bool) -> None:
        """Begin function definition."""
        self._defined_fns.add(label_id)
        
        if is_main:
            fn_name = "$main"
            self._fn_labels[label_id] = fn_name
        else:
            fn_name = self._fn_labels.get(label_id, f"$fn{label_id}")
        
        self._current_fn_name = fn_name
        self._current_fn = []
        self._param_count = param_count
        self._local_count = 0
        self._block_depth = 0
        
        # Build function signature
        params = " ".join(f"(param $p{i} i64)" for i in range(param_count))
        self._current_fn.append(f"  (func {fn_name} {params} (result i64)")
        
        # Pre-allocate scratch locals for swap operations
        self._current_fn.append("    (local $swap0 i64)")
        self._current_fn.append("    (local $swap1 i32)")
        
        # Param slots for compatibility with x86 backend
        self._param_slots = list(range(param_count))
    
    def end_function(self) -> None:
        """End function definition."""
        # Default return 0 if nothing on stack
        self._emit("i64.const 0")
        self._emit("return")
        self._current_fn.append("  )")
        self._functions.append("\n".join(self._current_fn))
    
    def load_param(self, index: int) -> None:
        """Push parameter value onto the value stack."""
        self._emit(f"local.get $p{index}")
    
    def alloc_local(self) -> int:
        """Allocate a local variable slot."""
        slot = self._param_count + self._local_count
        self._local_count += 1
        # Insert local declaration after function signature
        local_decl = f"    (local $l{slot} i64)"
        # Find position after params line
        self._current_fn.insert(1, local_decl)
        return slot
    
    def load_local(self, slot: int) -> None:
        """Push local variable value onto the value stack."""
        if slot < self._param_count:
            self._emit(f"local.get $p{slot}")
        else:
            self._emit(f"local.get $l{slot}")
    
    def store_local(self, slot: int) -> None:
        """Pop value from stack and store to local variable."""
        if slot < self._param_count:
            self._emit(f"local.set $p{slot}")
        else:
            self._emit(f"local.set $l{slot}")
    
    # ========================================================================
    # Value stack operations
    # ========================================================================
    
    def push_const_i64(self, value: int) -> None:
        """Push a 64-bit integer constant onto the value stack."""
        self._emit(f"i64.const {value}")
    
    def push_void(self) -> None:
        """Push void (zero) onto the value stack."""
        self._emit("i64.const 0")
    
    def push_fn_ref(self, label_id: int) -> None:
        """Push function index onto the value stack."""
        fn_idx = self._fn_indices.get(label_id, 0)
        self._emit(f"i64.const {fn_idx}")
    
    def dup_value(self) -> None:
        """Duplicate the top value - wasm doesn't have dup, use local."""
        # This would need a temp local; for now just note it's not ideal
        pass
    
    def pop_value(self) -> None:
        """Discard the top value on the stack."""
        self._emit("drop")
    
    def save_value(self) -> None:
        """Save value - in wasm, values stay on stack."""
        pass
    
    def restore_value(self) -> None:
        """Restore value - in wasm, values stay on stack."""
        pass
    
    # ========================================================================
    # Operators
    # ========================================================================
    
    def unary_op(self, op: str) -> None:
        """Apply unary operator to top of stack."""
        if op == "neg":
            self._emit("i64.const -1")
            self._emit("i64.mul")
        elif op == "not":
            self._emit("i64.const -1")
            self._emit("i64.xor")
    
    def binary_op(self, op: str) -> None:
        """Apply binary operator to top two values on stack."""
        if op == "+":
            self._emit("i64.add")
        elif op == "-":
            self._emit("i64.sub")
        elif op == "*":
            self._emit("i64.mul")
        elif op == "//":
            self._emit("i64.div_s")
        elif op == "%":
            self._emit("i64.rem_s")
        elif op == "<<":
            self._emit("i64.shl")
        elif op == ">>":
            self._emit("i64.shr_u")
        elif op == "and":
            self._emit("i64.and")
        elif op == "or":
            self._emit("i64.or")
        elif op == "xor":
            self._emit("i64.xor")
        elif op == "=?":
            self._emit("i64.eq")
            self._emit("i64.extend_i32_s")
            self._emit("i64.const 0")
            self._emit("i64.sub")
        elif op == "not=?":
            self._emit("i64.ne")
            self._emit("i64.extend_i32_s")
            self._emit("i64.const 0")
            self._emit("i64.sub")
        elif op == ">?":
            self._emit("i64.gt_s")
            self._emit("i64.extend_i32_s")
            self._emit("i64.const 0")
            self._emit("i64.sub")
        elif op == "<?":
            self._emit("i64.lt_s")
            self._emit("i64.extend_i32_s")
            self._emit("i64.const 0")
            self._emit("i64.sub")
        elif op == ">=?":
            self._emit("i64.ge_s")
            self._emit("i64.extend_i32_s")
            self._emit("i64.const 0")
            self._emit("i64.sub")
        elif op == "<=?":
            self._emit("i64.le_s")
            self._emit("i64.extend_i32_s")
            self._emit("i64.const 0")
            self._emit("i64.sub")
    
    def pipe_call(self) -> None:
        """Handle pipe operator."""
        # Stack: [arg fn_ptr]
        # For wasm, we'd need indirect calls via table
        # For now, just swap and call
        self._emit("call_indirect (type $fn1)")
    
    # ========================================================================
    # Memory operations
    # ========================================================================
    
    def load_mem(self, width: int) -> None:
        """Load from memory address on top of stack."""
        # Truncate i64 address to i32
        self._emit("i32.wrap_i64")
        if width == 64:
            self._emit("i64.load")
        elif width == 32:
            self._emit("i64.load32_u")
        elif width == 16:
            self._emit("i64.load16_u")
        elif width == 8:
            self._emit("i64.load8_u")
    
    def store_mem(self, width: int) -> None:
        """Store to memory. Stack: [value addr] -> pushes 0."""
        # WASM store expects [addr value], we have [value addr]
        # Use scratch locals to swap
        self._emit("i32.wrap_i64")      # Convert addr to i32: [value addr32]
        self._emit("local.set $swap1")  # Save addr32: [value]
        self._emit("local.set $swap0")  # Save value: []
        self._emit("local.get $swap1")  # Push addr32: [addr32]
        self._emit("local.get $swap0")  # Push value: [addr32 value]
        if width == 64:
            self._emit("i64.store")
        elif width == 32:
            self._emit("i64.store32")
        elif width == 16:
            self._emit("i64.store16")
        elif width == 8:
            self._emit("i64.store8")
        self._emit("i64.const 0")
    
    def signed_shr(self) -> None:
        """Signed (arithmetic) right shift. Stack: [value bits] -> result."""
        self._emit("i64.shr_s")
    
    # ========================================================================
    # Calls
    # ========================================================================
    
    def prepare_args(self, num_args: int) -> None:
        """Args are already on stack in wasm."""
        pass
    
    def call_direct(self, label_id: int, num_args: int) -> None:
        """Call a function directly by label."""
        fn_name = self._fn_labels.get(label_id, f"$fn{label_id}")
        self._emit(f"call {fn_name}")
    
    def call_indirect(self, num_args: int) -> None:
        """Call a function indirectly via table."""
        self._emit("i32.wrap_i64")
        self._emit(f"call_indirect (type $fn{num_args})")
    
    def syscall(self, num_args: int) -> None:
        """Syscalls are not supported on WASM. Use host function intrinsics instead."""
        raise NotImplementedError(
            "Syscalls are not supported on the WASM backend. "
            "Use WASM host function intrinsics (__host_log__, __host_exit__, etc.) instead, "
            "or create a platform abstraction layer."
        )
    
    def emit_host_log(self) -> None:
        """Emit a call to host_log(ptr, len). Stack: [ptr len] -> [bytes_written]"""
        self._emit("call $host_log")
    
    def emit_host_exit(self) -> None:
        """Emit a call to host_exit(code). Stack: [code] -> [code]"""
        self._emit("call $host_exit")
    
    def emit_host_time(self) -> None:
        """Emit a call to host_time(). Stack: [] -> [timestamp_ms]"""
        self._emit("call $host_time")
    
    def emit_host_random(self) -> None:
        """Emit a call to host_random(). Stack: [] -> [random_i64]"""
        self._emit("call $host_random")
    
    def emit_host_dom_set_text(self) -> None:
        """Emit a call to host_dom_set_text(ptr, len). Stack: [ptr len] -> [0]"""
        self._emit("call $host_dom_set_text")
    
    def emit_host_dom_append(self) -> None:
        """Emit a call to host_dom_append(ptr, len). Stack: [ptr len] -> [len]"""
        self._emit("call $host_dom_append")
    
    def emit_host_dom_clear(self) -> None:
        """Emit a call to host_dom_clear(). Stack: [] -> [0]"""
        self._emit("call $host_dom_clear")
    
    def emit_host_dom_append_int(self) -> None:
        """Emit a call to host_dom_append_int(value). Stack: [value] -> [value]"""
        self._emit("call $host_dom_append_int")
    
    def emit_host_log_int(self) -> None:
        """Emit a call to host_log_int(value). Stack: [value] -> [value]"""
        self._emit("call $host_log_int")
    
    # ========================================================================
    # Control flow
    # ========================================================================
    
    def begin_if(self) -> None:
        """Begin an if statement."""
        self._emit("i64.const 0")
        self._emit("i64.ne")
        self._emit("if")
        self._block_depth += 1
        self._if_stack.append(self._block_depth)
    
    def begin_else(self) -> None:
        """Begin the else branch."""
        self._emit("else")
    
    def end_if(self) -> None:
        """End an if statement."""
        self._emit("end")
        self._if_stack.pop()
        self._block_depth -= 1
    
    def begin_loop(self) -> None:
        """Begin a loop."""
        loop_label = self._new_label("loop")
        block_label = self._new_label("block")
        self._loop_stack.append((loop_label, block_label))
        self._emit(f"block {block_label}")
        self._emit(f"loop {loop_label}")
        self._block_depth += 2
    
    def begin_loop_body(self) -> None:
        """Begin the loop body after condition check."""
        _, block_label = self._loop_stack[-1]
        self._emit("i64.eqz")
        self._emit(f"br_if {block_label}")
    
    def end_loop(self) -> None:
        """End a loop."""
        loop_label, _ = self._loop_stack.pop()
        self._emit(f"br {loop_label}")
        self._emit("end")
        self._emit("end")
        self._block_depth -= 2
    
    def emit_break(self) -> None:
        """Emit a break statement."""
        _, block_label = self._loop_stack[-1]
        self._emit(f"br {block_label}")
    
    def emit_continue(self) -> None:
        """Emit a continue statement."""
        loop_label, _ = self._loop_stack[-1]
        self._emit(f"br {loop_label}")
    
    def emit_return(self) -> None:
        """Emit a return statement."""
        self._emit("return")
