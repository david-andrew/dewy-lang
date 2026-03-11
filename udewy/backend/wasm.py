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
        self._stack_local: str = "$stack_base"
        self._alloc_size_local: str = "$alloc_size"
        self._alloc_ptr_local: str = "$alloc_ptr"
        
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
            # Canvas graphics
            '(import "env" "host_canvas_init" (func $host_canvas_init (param i64 i64) (result i64)))',
            '(import "env" "host_canvas_width" (func $host_canvas_width (result i64)))',
            '(import "env" "host_canvas_height" (func $host_canvas_height (result i64)))',
            '(import "env" "host_canvas_present" (func $host_canvas_present (result i64)))',
            '(import "env" "host_frame_count" (func $host_frame_count (result i64)))',
            '(import "env" "host_frame_time" (func $host_frame_time (result i64)))',
            '(import "env" "host_window_width" (func $host_window_width (result i64)))',
            '(import "env" "host_window_height" (func $host_window_height (result i64)))',
        ]
        self._imports.extend(host_imports)
        self._next_fn_index = 17  # 17 host function imports
    
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
        
        # Memory import (for JS interop) - must come first
        # 16 pages = 1MB, enough for reasonable canvas sizes
        output.append('  (import "env" "memory" (memory 16))')
        
        # Host function imports - must come before any definitions
        for imp in self._imports:
            output.append(f"  {imp}")
        
        # Global definitions - after imports, before functions
        output.append('  (global $stack_ptr (mut i32) (i32.const 131072))')
        
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
        """Pop value from stack and store to global. Stack: [value] -> []"""
        offset = self._global_offsets[label_id]
        # WASM i64.store expects [addr, value], but we have [value]
        # Use scratch local to reorder
        self._emit("local.set $swap0")  # Save value
        self._emit(f"i32.const {offset}")  # Push address
        self._emit("local.get $swap0")  # Push value back
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
        self._current_fn.append(f"    (local {self._stack_local} i32)")
        self._current_fn.append(f"    (local {self._alloc_size_local} i32)")
        self._current_fn.append(f"    (local {self._alloc_ptr_local} i32)")
        self._emit("global.get $stack_ptr")
        self._emit(f"local.set {self._stack_local}")
        
        # Param slots for compatibility with x86 backend
        self._param_slots = list(range(param_count))
    
    def end_function(self) -> None:
        """End function definition."""
        # Default return 0 if nothing on stack
        self._emit(f"local.get {self._stack_local}")
        self._emit("global.set $stack_ptr")
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
    
    def load_mem(self, width: int, signed: bool = False) -> None:
        """Load from memory address on top of stack."""
        # Truncate i64 address to i32
        self._emit("i32.wrap_i64")
        if width == 64:
            self._emit("i64.load")
        elif width == 32:
            if signed:
                self._emit("i64.load32_s")
            else:
                self._emit("i64.load32_u")
        elif width == 16:
            if signed:
                self._emit("i64.load16_s")
            else:
                self._emit("i64.load16_u")
        elif width == 8:
            if signed:
                self._emit("i64.load8_s")
            else:
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

    def alloca(self) -> None:
        """Allocate temporary linear-memory storage and return its address."""
        self._emit("i32.wrap_i64")
        self._emit("i32.const 7")
        self._emit("i32.add")
        self._emit("i32.const -8")
        self._emit("i32.and")
        self._emit(f"local.set {self._alloc_size_local}")
        self._emit("global.get $stack_ptr")
        self._emit(f"local.get {self._alloc_size_local}")
        self._emit("i32.sub")
        self._emit(f"local.tee {self._alloc_ptr_local}")
        self._emit("global.set $stack_ptr")
        self._emit(f"local.get {self._alloc_ptr_local}")
        self._emit("i64.extend_i32_u")

    def unsigned_idiv(self) -> None:
        """Unsigned division. Stack: [left right] -> quotient."""
        self._emit("i64.div_u")

    def unsigned_mod(self) -> None:
        """Unsigned remainder. Stack: [left right] -> remainder."""
        self._emit("i64.rem_u")

    def unsigned_cmp(self, kind: str) -> None:
        """Unsigned comparison returning udewy booleans."""
        if kind == "gt":
            self._emit("i64.gt_u")
        elif kind == "lt":
            self._emit("i64.lt_u")
        elif kind == "gte":
            self._emit("i64.ge_u")
        elif kind == "lte":
            self._emit("i64.le_u")
        self._emit("i64.extend_i32_s")
        self._emit("i64.const 0")
        self._emit("i64.sub")
    
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
    
    def emit_canvas_init(self) -> None:
        """Emit a call to host_canvas_init(width, height). Stack: [width height] -> [buffer_ptr]"""
        self._emit("call $host_canvas_init")
    
    def emit_canvas_width(self) -> None:
        """Emit a call to host_canvas_width(). Stack: [] -> [width]"""
        self._emit("call $host_canvas_width")
    
    def emit_canvas_height(self) -> None:
        """Emit a call to host_canvas_height(). Stack: [] -> [height]"""
        self._emit("call $host_canvas_height")
    
    def emit_canvas_present(self) -> None:
        """Emit a call to host_canvas_present(). Stack: [] -> [0]"""
        self._emit("call $host_canvas_present")
    
    def emit_frame_count(self) -> None:
        """Emit a call to host_frame_count(). Stack: [] -> [frame_number]"""
        self._emit("call $host_frame_count")
    
    def emit_frame_time(self) -> None:
        """Emit a call to host_frame_time(). Stack: [] -> [ms_since_start]"""
        self._emit("call $host_frame_time")
    
    def emit_window_width(self) -> None:
        """Emit a call to host_window_width(). Stack: [] -> [width]"""
        self._emit("call $host_window_width")
    
    def emit_window_height(self) -> None:
        """Emit a call to host_window_height(). Stack: [] -> [height]"""
        self._emit("call $host_window_height")
    
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
        self._emit(f"local.get {self._stack_local}")
        self._emit("global.set $stack_ptr")
        self._emit("return")
    
    # ========================================================================
    # Intrinsics
    # ========================================================================
    
    _CORE_INTRINSICS = {
        "__load_u8__", "__load_u16__", "__load_u32__", "__load_u64__",
        "__store_u8__", "__store_u16__", "__store_u32__", "__store_u64__",
        "__load_i8__", "__load_i16__", "__load_i32__", "__load_i64__",
        "__store_i8__", "__store_i16__", "__store_i32__", "__store_i64__",
        "__load__", "__store__", "__alloca__",
        "__signed_shr__",
        "__unsigned_idiv__", "__unsigned_mod__",
        "__unsigned_lt__", "__unsigned_gt__", "__unsigned_lte__", "__unsigned_gte__",
    }
    
    _PLATFORM_INTRINSICS = {
        "__host_log__", "__host_exit__", "__host_time__", "__host_random__",
        "__dom_set_text__", "__dom_append__", "__dom_clear__",
        "__dom_append_int__", "__log_int__",
        "__canvas_init__", "__canvas_width__", "__canvas_height__",
        "__canvas_present__", "__frame_count__", "__frame_time__",
        "__window_width__", "__window_height__",
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
        elif name == "__host_log__":
            self.emit_host_log()
        elif name == "__host_exit__":
            self.emit_host_exit()
        elif name == "__host_time__":
            self.emit_host_time()
        elif name == "__host_random__":
            self.emit_host_random()
        elif name == "__dom_set_text__":
            self.emit_host_dom_set_text()
        elif name == "__dom_append__":
            self.emit_host_dom_append()
        elif name == "__dom_clear__":
            self.emit_host_dom_clear()
        elif name == "__dom_append_int__":
            self.emit_host_dom_append_int()
        elif name == "__log_int__":
            self.emit_host_log_int()
        elif name == "__canvas_init__":
            self.emit_canvas_init()
        elif name == "__canvas_width__":
            self.emit_canvas_width()
        elif name == "__canvas_height__":
            self.emit_canvas_height()
        elif name == "__canvas_present__":
            self.emit_canvas_present()
        elif name == "__frame_count__":
            self.emit_frame_count()
        elif name == "__frame_time__":
            self.emit_frame_time()
        elif name == "__window_width__":
            self.emit_window_width()
        elif name == "__window_height__":
            self.emit_window_height()
    
    def get_builtin_constants(self) -> dict[str, int]:
        """WASM browser backend has no built-in constants."""
        return {}
    
    def compile_and_link(self, code: str, input_name: str, cache_dir: Path, **options) -> Path:
        """Compile WAT to WASM and generate HTML wrapper."""
        import subprocess
        import base64
        
        split_wasm = options.get('split_wasm', False)
        
        wat_path = cache_dir / f"{input_name}.wat"
        wasm_path = cache_dir / f"{input_name}.wasm"
        html_path = cache_dir / f"{input_name}.html"
        
        wat_path.write_text(code)
        
        # Convert WAT to WASM
        try:
            subprocess.run(["wat2wasm", str(wat_path), "-o", str(wasm_path)], check=True)
        except FileNotFoundError:
            raise RuntimeError(
                "wat2wasm not found. Install wabt: https://github.com/WebAssembly/wabt\n"
                f"WAT file generated at: {wat_path}"
            )
        
        # Generate HTML with JS host functions
        host_functions_js = self._get_host_functions_js()
        
        if split_wasm:
            html_content = self._get_split_html_template(input_name, wasm_path.name, host_functions_js)
        else:
            wasm_bytes = wasm_path.read_bytes()
            wasm_b64 = base64.b64encode(wasm_bytes).decode('ascii')
            html_content = self._get_embedded_html_template(input_name, wasm_b64, host_functions_js)
        
        html_path.write_text(html_content)
        
        return html_path if not split_wasm else wasm_path
    
    def run(self, output_path: Path, args: list[str]) -> int | None:
        """WASM runs in browser - return None to indicate manual running needed."""
        return None
    
    def get_compile_message(self, output_path: Path, **options) -> str:
        """Get compilation success message."""
        split_wasm = options.get('split_wasm', False)
        cache_dir = output_path.parent
        
        if split_wasm:
            html_path = output_path.with_suffix('.html')
            return (
                f"Split mode output:\n"
                f"  WASM: {output_path}\n"
                f"  HTML: {html_path}\n"
                f"Serve with: python -m http.server -d {cache_dir}"
            )
        else:
            return (
                f"Compiled: {output_path}\n"
                f"(single file with embedded WASM)"
            )
    
    def _get_host_functions_js(self) -> str:
        """Return JavaScript code implementing WASM host functions."""
        return '''
const memory = new WebAssembly.Memory({ initial: 16 });
let outputElement = null;

// Canvas state
let canvas = null;
let ctx = null;
let canvasBuffer = null;
let canvasBufferPtr = 0;
let canvasWidth = 0;
let canvasHeight = 0;
let frameCount = 0;
let startTime = 0;
let canvasMode = false;
let wasmInstance = null;

function decodeString(ptr, len) {
    const view = new Uint8Array(memory.buffer);
    const bytes = view.slice(Number(ptr), Number(ptr) + Number(len));
    return new TextDecoder().decode(bytes);
}

function appendOutput(text) {
    console.log(text);
    if (outputElement) {
        outputElement.textContent += text;
    }
}

const imports = {
    env: {
        memory: memory,
        // Direct browser APIs
        host_log: (ptr, len) => {
            const text = decodeString(ptr, len);
            console.log(text);
            return len;
        },
        host_exit: (code) => {
            appendOutput(`\\nExit code: ${code}\\n`);
            return code;
        },
        host_time: () => BigInt(Date.now()),
        host_random: () => BigInt(Math.floor(Math.random() * Number.MAX_SAFE_INTEGER)),
        // DOM manipulation
        host_dom_set_text: (ptr, len) => {
            const text = decodeString(ptr, len);
            if (outputElement) {
                outputElement.textContent = text;
            }
            return 0n;
        },
        host_dom_append: (ptr, len) => {
            const text = decodeString(ptr, len);
            if (outputElement) {
                outputElement.textContent += text;
            }
            return len;
        },
        host_dom_clear: () => {
            if (outputElement) {
                outputElement.textContent = '';
            }
            return 0n;
        },
        host_dom_append_int: (value) => {
            if (outputElement) {
                outputElement.textContent += String(value);
            }
            return value;
        },
        host_log_int: (value) => {
            console.log(String(value));
            return value;
        },
        // Canvas graphics
        host_canvas_init: (width, height) => {
            // Only initialize once - subsequent calls return existing buffer
            if (canvas && canvasMode) {
                return BigInt(canvasBufferPtr);
            }
            
            canvasWidth = Number(width);
            canvasHeight = Number(height);
            canvasMode = true;
            startTime = performance.now();
            
            // Create or resize canvas
            canvas = document.getElementById('canvas');
            if (!canvas) {
                canvas = document.createElement('canvas');
                canvas.id = 'canvas';
                document.body.insertBefore(canvas, document.body.firstChild);
            }
            canvas.width = canvasWidth;
            canvas.height = canvasHeight;
            canvas.style.display = 'block';
            ctx = canvas.getContext('2d');
            
            // Hide text output in canvas mode
            if (outputElement) {
                outputElement.style.display = 'none';
            }
            const h1 = document.querySelector('h1');
            if (h1) h1.style.display = 'none';
            
            // Allocate buffer in WASM memory (RGBA: 4 bytes per pixel)
            // Use a fixed location after the stack (at 256KB)
            canvasBufferPtr = 262144;
            
            return BigInt(canvasBufferPtr);
        },
        host_canvas_width: () => BigInt(canvasWidth),
        host_canvas_height: () => BigInt(canvasHeight),
        host_canvas_present: () => {
            if (!ctx || !canvas) return 0n;
            
            // Read pixel data from WASM memory
            const view = new Uint8ClampedArray(memory.buffer, canvasBufferPtr, canvasWidth * canvasHeight * 4);
            const imageData = new ImageData(view, canvasWidth, canvasHeight);
            ctx.putImageData(imageData, 0, 0);
            
            return 0n;
        },
        host_frame_count: () => BigInt(frameCount),
        host_frame_time: () => BigInt(Math.floor(performance.now() - startTime)),
        host_window_width: () => BigInt(window.innerWidth),
        host_window_height: () => BigInt(window.innerHeight),
    }
};

function animationLoop() {
    if (!canvasMode || !wasmInstance) return;
    
    frameCount++;
    wasmInstance.exports.main();
    requestAnimationFrame(animationLoop);
}
'''
    
    def _get_split_html_template(self, title: str, wasm_filename: str, host_js: str) -> str:
        """Return HTML template for split WASM mode."""
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }}
        body.canvas-mode {{ max-width: none; margin: 0; padding: 0; overflow: hidden; background: #000; }}
        h1 {{ color: #333; }}
        #output {{ background: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 4px; white-space: pre-wrap; font-family: monospace; min-height: 100px; }}
        #canvas {{ display: none; image-rendering: pixelated; }}
        body.canvas-mode #canvas {{ display: block; width: 100vw; height: 100vh; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <pre id="output"></pre>
    <script>
{host_js}

async function run() {{
    outputElement = document.getElementById('output');
    try {{
        const response = await fetch('{wasm_filename}');
        const bytes = await response.arrayBuffer();
        const {{ instance }} = await WebAssembly.instantiate(bytes, imports);
        wasmInstance = instance;
        const result = instance.exports.main();
        if (canvasMode) {{
            document.body.classList.add('canvas-mode');
            requestAnimationFrame(animationLoop);
        }} else {{
            appendOutput(`\\nExit code: ${{result}}`);
        }}
    }} catch (err) {{
        appendOutput(`Error: ${{err}}`);
    }}
}}

run();
    </script>
</body>
</html>
'''
    
    def _get_embedded_html_template(self, title: str, wasm_b64: str, host_js: str) -> str:
        """Return HTML template with embedded base64 WASM."""
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }}
        body.canvas-mode {{ max-width: none; margin: 0; padding: 0; overflow: hidden; background: #000; }}
        h1 {{ color: #333; }}
        #output {{ background: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 4px; white-space: pre-wrap; font-family: monospace; min-height: 100px; }}
        #canvas {{ display: none; image-rendering: pixelated; }}
        body.canvas-mode #canvas {{ display: block; width: 100vw; height: 100vh; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <pre id="output"></pre>

    <script id="wasm-module" type="application/wasm-b64">
{wasm_b64}
    </script>

    <script>
{host_js}

async function loadEmbeddedWasm() {{
    const b64 = document.getElementById('wasm-module').textContent.trim();
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    return WebAssembly.instantiate(bytes, imports);
}}

async function run() {{
    outputElement = document.getElementById('output');
    try {{
        const {{ instance }} = await loadEmbeddedWasm();
        wasmInstance = instance;
        const result = instance.exports.main();
        if (canvasMode) {{
            document.body.classList.add('canvas-mode');
            requestAnimationFrame(animationLoop);
        }} else {{
            appendOutput(`\\nExit code: ${{result}}`);
        }}
    }} catch (err) {{
        appendOutput(`Error: ${{err}}`);
    }}
}}

run();
    </script>
</body>
</html>
'''
