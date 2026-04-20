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

from os import PathLike
from pathlib import Path

from .. import t1
from .common import Backend, CORE_INTRINSIC_ARITIES, RunOptions

class Wasm32Backend(Backend):
    """
    WebAssembly code generator implementing the Backend protocol.
    
    Value stack model:
    - Uses wasm's native operand stack directly
    - i64 values throughout
    - Addresses truncated to i32 at memory operations
    """
    
    def __init__(self) -> None:
        self._imports: list[str] = []
        self._functions: dict[int, str] = {}
        self._current_fn: list[str] = []
        self._current_fn_label_id: int = -1
        self._reachable_fn_label_ids: set[int] | None = None
        self._data_segments: list[tuple[int, bytes]] = []
        self._next_label: int = 0
        self._data_offset: int = 1024  # Start data after initial memory
        self._module_init_name: str | None = None
        self._user_main_name = "$__main__"
        
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
        self._fn_param_counts: dict[int, int] = {}
        self._fn_table_ids: list[int] = []
        self._indirect_arities: set[int] = set()
        self._global_offsets: dict[int, int] = {}
        self._global_labels: dict[int, str] = {}
        self._string_offsets: dict[int, int] = {}
        self._string_labels: dict[int, str] = {}
        self._array_offsets: dict[int, int] = {}
        self._array_labels: dict[int, str] = {}
        self._static_offsets: dict[int, int] = {}
        self._static_labels: dict[int, str] = {}
        
        # Track which functions are defined
        self._defined_fns: set[int] = set()
        
        # Next table index for user-defined functions
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
            '(import "env" "host_canvas_set_aspect_lock" (func $host_canvas_set_aspect_lock (param i64) (result i64)))',
            '(import "env" "host_frame_count" (func $host_frame_count (result i64)))',
            '(import "env" "host_frame_time" (func $host_frame_time (result i64)))',
            '(import "env" "host_window_width" (func $host_window_width (result i64)))',
            '(import "env" "host_window_height" (func $host_window_height (result i64)))',
            # Pointer input
            '(import "env" "host_pointer_x" (func $host_pointer_x (result i64)))',
            '(import "env" "host_pointer_y" (func $host_pointer_y (result i64)))',
            '(import "env" "host_pointer_down" (func $host_pointer_down (result i64)))',
            # Keyboard input
            '(import "env" "host_key_down" (func $host_key_down (param i64 i64) (result i64)))',
            '(import "env" "host_key_pressed" (func $host_key_pressed (param i64 i64) (result i64)))',
            '(import "env" "host_key_released" (func $host_key_released (param i64 i64) (result i64)))',
            # Audio (one-shot)
            '(import "env" "host_audio_init" (func $host_audio_init (param i64 i64 i64) (result i64)))',
            '(import "env" "host_audio_play" (func $host_audio_play (result i64)))',
            '(import "env" "host_audio_sample_rate" (func $host_audio_sample_rate (result i64)))',
            # Audio (streaming)
            '(import "env" "host_audio_stream_init" (func $host_audio_stream_init (param i64 i64) (result i64)))',
            '(import "env" "host_audio_stream_write" (func $host_audio_stream_write (result i64)))',
            '(import "env" "host_audio_stream_needs_samples" (func $host_audio_stream_needs_samples (result i64)))',
            # WebGL fullscreen shader
            '(import "env" "host_webgl_init" (func $host_webgl_init (param i64 i64 i64 i64) (result i64)))',
            '(import "env" "host_webgl_uniform1i" (func $host_webgl_uniform1i (param i64 i64 i64) (result i64)))',
            '(import "env" "host_webgl_uniform2i" (func $host_webgl_uniform2i (param i64 i64 i64 i64) (result i64)))',
            '(import "env" "host_webgl_uniform1iv" (func $host_webgl_uniform1iv (param i64 i64 i64 i64) (result i64)))',
            '(import "env" "host_webgl_uniform2iv" (func $host_webgl_uniform2iv (param i64 i64 i64 i64) (result i64)))',
            '(import "env" "host_webgl_render" (func $host_webgl_render (result i64)))',
            # General-purpose 3D GPU surface (textured + vertex-colored, batched)
            '(import "env" "host_gpu_init" (func $host_gpu_init (param i64 i64) (result i64)))',
            '(import "env" "host_gpu_set_viewport" (func $host_gpu_set_viewport (param i64 i64) (result i64)))',
            '(import "env" "host_gpu_clear" (func $host_gpu_clear (param i64 i64 i64) (result i64)))',
            '(import "env" "host_gpu_set_perspective_frustum" (func $host_gpu_set_perspective_frustum (param i64 i64 i64 i64 i64 i64) (result i64)))',
            '(import "env" "host_gpu_set_view_matrix" (func $host_gpu_set_view_matrix (param i64) (result i64)))',
            '(import "env" "host_gpu_set_texture" (func $host_gpu_set_texture (param i64) (result i64)))',
            '(import "env" "host_gpu_set_blend" (func $host_gpu_set_blend (param i64) (result i64)))',
            '(import "env" "host_gpu_set_depth_test" (func $host_gpu_set_depth_test (param i64) (result i64)))',
            '(import "env" "host_gpu_set_depth_write" (func $host_gpu_set_depth_write (param i64) (result i64)))',
            '(import "env" "host_gpu_set_line_width" (func $host_gpu_set_line_width (param i64) (result i64)))',
            '(import "env" "host_gpu_submit" (func $host_gpu_submit (param i64 i64 i64) (result i64)))',
            '(import "env" "host_gpu_overlay_begin" (func $host_gpu_overlay_begin (param i64 i64) (result i64)))',
            '(import "env" "host_gpu_overlay_end" (func $host_gpu_overlay_end (result i64)))',
            '(import "env" "host_gpu_create_texture" (func $host_gpu_create_texture (param i64 i64 i64 i64 i64) (result i64)))',
            '(import "env" "host_gpu_present" (func $host_gpu_present (result i64)))',
            '(import "env" "host_gpu_window_width" (func $host_gpu_window_width (result i64)))',
            '(import "env" "host_gpu_window_height" (func $host_gpu_window_height (result i64)))',
            # Audio queue (general-purpose ring buffer pushed from WASM)
            '(import "env" "host_audio_queue_init" (func $host_audio_queue_init (param i64 i64) (result i64)))',
            '(import "env" "host_audio_queue_push" (func $host_audio_queue_push (param i64 i64) (result i64)))',
            '(import "env" "host_audio_queue_size" (func $host_audio_queue_size (result i64)))',
        ]
        self._imports.extend(host_imports)
    
    def _new_label(self, prefix: str = "L") -> str:
        label = f"${prefix}{self._next_label}"
        self._next_label += 1
        return label

    def _resolve_data_ref(self, value: str) -> int:
        if value.endswith("+8"):
            ref_part = value.removesuffix("+8")
            for sid, slabel in self._string_labels.items():
                if slabel == ref_part:
                    return self._string_offsets[sid] + 8
            for aid, alabel in self._array_labels.items():
                if alabel == ref_part:
                    return self._array_offsets[aid] + 8
            raise ValueError(f"Unknown wasm data reference: {value}")

        for sid, slabel in self._static_labels.items():
            if slabel == value:
                return self._static_offsets[sid]
        for gid, glabel in self._global_labels.items():
            if glabel == value:
                return self._global_offsets[gid]
        raise ValueError(f"Unknown wasm data reference: {value}")
    
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

    def _fn_type_name(self, arity: int) -> str:
        return f"$type_fn{arity}"

    def _spill_top_value(self) -> None:
        self._emit("local.set $swap0")
        self._emit("global.get $stack_ptr")
        self._emit("i32.const 8")
        self._emit("i32.sub")
        self._emit("local.tee $swap1")
        self._emit("global.set $stack_ptr")
        self._emit("local.get $swap1")
        self._emit("local.get $swap0")
        self._emit("i64.store")

    def _restore_saved_value(self) -> None:
        self._emit("global.get $stack_ptr")
        self._emit("i64.load")
        self._emit("global.get $stack_ptr")
        self._emit("i32.const 8")
        self._emit("i32.add")
        self._emit("global.set $stack_ptr")
    
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
        """Finalize and return the generated WAT."""
        output = []
        output.append("(module")
        
        # Memory import (for JS interop) - must come first.
        # 32 pages = 2MB; large enough for a streaming vertex scratch buffer
        # plus a few hundred KB of game-side static_alloca.
        output.append('  (import "env" "memory" (memory 32))')
        
        # Host function imports - must come before any definitions
        for imp in self._imports:
            output.append(f"  {imp}")

        for arity in sorted(self._indirect_arities):
            params = " ".join("(param i64)" for _ in range(arity))
            output.append(f"  (type {self._fn_type_name(arity)} (func {params} (result i64)))")
        
        # Global definitions - after imports, before functions
        output.append('  (global $stack_ptr (mut i32) (i32.const 2097152))')
        if self._module_init_name is not None:
            output.append('  (global $__udewy_module_init_done (mut i32) (i32.const 0))')

        if self._fn_table_ids:
            output.append(f"  (table {len(self._fn_table_ids)} funcref)")
        
        # Functions: emit in declaration order so table indices stay correct.
        # Unreachable functions become tiny stubs so the function-table layout
        # is preserved while the heavy body is dropped.
        for label_id in self._fn_table_ids:
            if self._reachable_fn_label_ids is not None and label_id not in self._reachable_fn_label_ids:
                fn_name = self._fn_labels[label_id]
                param_count = self._fn_param_counts[label_id]
                params = " ".join("(param i64)" for _ in range(param_count))
                output.append(f"  (func {fn_name} {params} (result i64) i64.const 0)")
            else:
                output.append(self._functions[label_id])

        output.append("  (func $main (result i64)")
        if self._module_init_name is not None:
            output.append("    global.get $__udewy_module_init_done")
            output.append("    if")
            output.append("    else")
            output.append("      i32.const 1")
            output.append("      global.set $__udewy_module_init_done")
            output.append(f"      call ${self._module_init_name}")
            output.append("      drop")
            output.append("    end")
        output.append(f"    call {self._user_main_name}")
        output.append("  )")

        if self._fn_table_ids:
            refs = " ".join(self._fn_labels[label_id] for label_id in self._fn_table_ids)
            output.append(f"  (elem (i32.const 0) {refs})")
        
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
                elem_bytes += (elem & 0xFFFF_FFFF_FFFF_FFFF).to_bytes(8, 'little', signed=False)
            elif isinstance(elem, str):
                ref_offset = self._resolve_data_ref(elem)
                elem_bytes += (ref_offset & 0xFFFF_FFFF_FFFF_FFFF).to_bytes(8, 'little', signed=False)
            else:
                raise TypeError(f"Unsupported wasm array element directive: {elem!r}")
        
        full_data = length_bytes + elem_bytes
        offset = self._alloc_data(full_data)
        self._array_offsets[label_id] = offset
        self._array_labels[label_id] = f".arr{label_id}"
        
        return label_id
    
    def define_global(self, name: str | None, value: int | str) -> int:
        """Define a global variable."""
        label_id = self._next_label
        self._next_label += 1
        
        if isinstance(value, int):
            actual_value = value
        elif isinstance(value, str):
            actual_value = self._resolve_data_ref(value)
        else:
            raise TypeError(f"Unsupported wasm global initializer: {value!r}")
        
        data = (actual_value & 0xFFFF_FFFF_FFFF_FFFF).to_bytes(8, 'little', signed=False)
        offset = self._alloc_data(data)
        self._global_offsets[label_id] = offset
        self._global_labels[label_id] = f".global{label_id}"
        
        return label_id

    def declare_extern_global(self, name: str) -> int:
        raise RuntimeError("extern globals are not supported on the wasm32 backend")

    def intern_static(self, size: int) -> int:
        """Reserve a static storage block. WebAssembly linear memory is
        zero-initialised on instantiation, so we just bump the bump-allocator
        without emitting a data segment full of zero bytes.
        """
        label_id = self._next_label
        self._next_label += 1

        offset = self._data_offset
        self._data_offset += size
        if self._data_offset % 8 != 0:
            self._data_offset += 8 - (self._data_offset % 8)

        self._static_offsets[label_id] = offset
        self._static_labels[label_id] = f".static{label_id}"

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

    def push_static_ref(self, label_id: int) -> None:
        """Push address of raw static storage onto value stack."""
        offset = self._static_offsets[label_id]
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

    def function_ref(self, label_id: int) -> int:
        return self._fn_indices[label_id]

    def string_ref(self, label_id: int) -> int:
        return self._string_offsets[label_id] + 8

    def array_ref(self, label_id: int) -> int:
        return self._array_offsets[label_id] + 8

    def static_ref(self, label_id: int) -> int:
        return self._static_offsets[label_id]
    
    # ========================================================================
    # Functions
    # ========================================================================
    
    def declare_function(self, name: str | None, num_params: int) -> int:
        """Declare a function."""
        label_id = self._next_label
        self._next_label += 1
        if name is None:
            fn_name = f"$fn{label_id}"
        elif name == "main":
            fn_name = self._user_main_name
        else:
            fn_name = f"${name}"
        self._fn_labels[label_id] = fn_name
        self._fn_indices[label_id] = self._next_fn_index
        self._fn_param_counts[label_id] = num_params
        self._fn_table_ids.append(label_id)
        self._next_fn_index += 1
        return label_id

    def bind_extern_function(self, label_id: int, name: str) -> None:
        raise RuntimeError("extern functions are not supported on the wasm32 backend")

    def declare_extern_function(self, name: str, num_params: int) -> int:
        raise RuntimeError("extern functions are not supported on the wasm32 backend")
    
    def begin_function(self, label_id: int, name: str, param_count: int, is_main: bool) -> None:
        """Begin function definition."""
        self._defined_fns.add(label_id)

        fn_name = self._fn_labels.get(label_id, f"$fn{label_id}")
        self._fn_param_counts[label_id] = param_count
        
        self._current_fn_name = fn_name
        self._current_fn = []
        self._current_fn_label_id = label_id
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
        self._functions[self._current_fn_label_id] = "\n".join(self._current_fn)
    
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
        """Push function table index onto the value stack."""
        fn_idx = self._fn_indices[label_id]
        self._emit(f"i64.const {fn_idx}")
    
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
    
    def unary_op(self, op_kind: t1.Kind) -> None:
        """Apply unary operator to top of stack."""
        if op_kind == t1.Kind.TK_MINUS:
            self._emit("i64.const -1")
            self._emit("i64.mul")
        elif op_kind == t1.Kind.TK_NOT:
            self._emit("i64.const -1")
            self._emit("i64.xor")
    
    def binary_op(self, op_kind: t1.Kind) -> None:
        """Apply binary operator to top two values on stack."""
        if op_kind == t1.Kind.TK_PLUS:
            self._emit("i64.add")
        elif op_kind == t1.Kind.TK_MINUS:
            self._emit("i64.sub")
        elif op_kind == t1.Kind.TK_MUL:
            self._emit("i64.mul")
        elif op_kind == t1.Kind.TK_IDIV:
            self._emit("i64.div_s")
        elif op_kind == t1.Kind.TK_MOD:
            self._emit("i64.rem_s")
        elif op_kind == t1.Kind.TK_LEFT_SHIFT:
            self._emit("i64.shl")
        elif op_kind == t1.Kind.TK_RIGHT_SHIFT:
            self._emit("i64.shr_u")
        elif op_kind == t1.Kind.TK_AND:
            self._emit("i64.and")
        elif op_kind == t1.Kind.TK_OR:
            self._emit("i64.or")
        elif op_kind == t1.Kind.TK_XOR:
            self._emit("i64.xor")
        elif op_kind == t1.Kind.TK_EQ:
            self._emit("i64.eq")
            self._emit("i64.extend_i32_s")
            self._emit("i64.const 0")
            self._emit("i64.sub")
        elif op_kind == t1.Kind.TK_NOT_EQ:
            self._emit("i64.ne")
            self._emit("i64.extend_i32_s")
            self._emit("i64.const 0")
            self._emit("i64.sub")
        elif op_kind == t1.Kind.TK_GT:
            self._emit("i64.gt_s")
            self._emit("i64.extend_i32_s")
            self._emit("i64.const 0")
            self._emit("i64.sub")
        elif op_kind == t1.Kind.TK_LT:
            self._emit("i64.lt_s")
            self._emit("i64.extend_i32_s")
            self._emit("i64.const 0")
            self._emit("i64.sub")
        elif op_kind == t1.Kind.TK_GT_EQ:
            self._emit("i64.ge_s")
            self._emit("i64.extend_i32_s")
            self._emit("i64.const 0")
            self._emit("i64.sub")
        elif op_kind == t1.Kind.TK_LT_EQ:
            self._emit("i64.le_s")
            self._emit("i64.extend_i32_s")
            self._emit("i64.const 0")
            self._emit("i64.sub")
    
    def pipe_call(self) -> None:
        """Handle pipe operator."""
        self._indirect_arities.add(1)
        self._emit("i32.wrap_i64")
        self._emit(f"call_indirect (type {self._fn_type_name(1)})")
    
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

    def i64_to_f32_bits(self) -> None:
        """Convert i64 to f32 then return its IEEE-754 bit pattern (zero-extended to i64)."""
        self._emit("f32.convert_i64_s")
        self._emit("i32.reinterpret_f32")
        self._emit("i64.extend_i32_u")

    def i64_to_f64_bits(self) -> None:
        """Convert i64 to f64 then return its IEEE-754 bit pattern (i64)."""
        self._emit("f64.convert_i64_s")
        self._emit("i64.reinterpret_f64")

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
        self._indirect_arities.add(num_args)
        for _ in range(num_args + 1):
            self._spill_top_value()

        self._restore_saved_value()
        self._emit("i32.wrap_i64")
        self._emit("local.set $swap1")

        for _ in range(num_args):
            self._restore_saved_value()

        self._emit("local.get $swap1")
        self._emit(f"call_indirect (type {self._fn_type_name(num_args)})")

    def max_call_args(self) -> int | None:
        return None
    
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

    def emit_canvas_set_aspect_lock(self) -> None:
        """Emit a call to host_canvas_set_aspect_lock(enabled). Stack: [enabled] -> [0]"""
        self._emit("call $host_canvas_set_aspect_lock")
    
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
    
    def emit_pointer_x(self) -> None:
        """Emit a call to host_pointer_x(). Stack: [] -> [x]"""
        self._emit("call $host_pointer_x")
    
    def emit_pointer_y(self) -> None:
        """Emit a call to host_pointer_y(). Stack: [] -> [y]"""
        self._emit("call $host_pointer_y")
    
    def emit_pointer_down(self) -> None:
        """Emit a call to host_pointer_down(). Stack: [] -> [down]"""
        self._emit("call $host_pointer_down")
    
    def emit_key_down(self) -> None:
        """Emit a call to host_key_down(code_ptr, code_len). Stack: [ptr len] -> [down]"""
        self._emit("call $host_key_down")
    
    def emit_key_pressed(self) -> None:
        """Emit a call to host_key_pressed(code_ptr, code_len). Stack: [ptr len] -> [pressed]"""
        self._emit("call $host_key_pressed")
    
    def emit_key_released(self) -> None:
        """Emit a call to host_key_released(code_ptr, code_len). Stack: [ptr len] -> [released]"""
        self._emit("call $host_key_released")
    
    def emit_audio_init(self) -> None:
        """Emit a call to host_audio_init(sample_rate, num_samples, channels). Stack: [sr ns ch] -> [buffer_ptr]"""
        self._emit("call $host_audio_init")
    
    def emit_audio_play(self) -> None:
        """Emit a call to host_audio_play(). Stack: [] -> [0]"""
        self._emit("call $host_audio_play")
    
    def emit_audio_sample_rate(self) -> None:
        """Emit a call to host_audio_sample_rate(). Stack: [] -> [sample_rate]"""
        self._emit("call $host_audio_sample_rate")
    
    def emit_audio_stream_init(self) -> None:
        """Emit a call to host_audio_stream_init(sample_rate, buffer_size). Stack: [sr bs] -> [buffer_ptr]"""
        self._emit("call $host_audio_stream_init")
    
    def emit_audio_stream_write(self) -> None:
        """Emit a call to host_audio_stream_write(). Stack: [] -> [next_buffer_ptr]"""
        self._emit("call $host_audio_stream_write")
    
    def emit_audio_stream_needs_samples(self) -> None:
        """Emit a call to host_audio_stream_needs_samples(). Stack: [] -> [bool]"""
        self._emit("call $host_audio_stream_needs_samples")
    
    def emit_webgl_init(self) -> None:
        """Emit a call to host_webgl_init(shader_ptr, shader_len, width, height). Stack: [ptr len w h] -> [0]"""
        self._emit("call $host_webgl_init")
    
    def emit_webgl_uniform1i(self) -> None:
        """Emit a call to host_webgl_uniform1i(name_ptr, name_len, value). Stack: [ptr len value] -> [0]"""
        self._emit("call $host_webgl_uniform1i")
    
    def emit_webgl_uniform2i(self) -> None:
        """Emit a call to host_webgl_uniform2i(name_ptr, name_len, x, y). Stack: [ptr len x y] -> [0]"""
        self._emit("call $host_webgl_uniform2i")
    
    def emit_webgl_uniform1iv(self) -> None:
        """Emit a call to host_webgl_uniform1iv(name_ptr, name_len, values_ptr, count). Stack: [ptr len values count] -> [0]"""
        self._emit("call $host_webgl_uniform1iv")
    
    def emit_webgl_uniform2iv(self) -> None:
        """Emit a call to host_webgl_uniform2iv(name_ptr, name_len, values_ptr, count). Stack: [ptr len values count] -> [0]"""
        self._emit("call $host_webgl_uniform2iv")
    
    def emit_webgl_render(self) -> None:
        """Emit a call to host_webgl_render(). Stack: [] -> [0]"""
        self._emit("call $host_webgl_render")

    def emit_gpu_init(self) -> None:
        self._emit("call $host_gpu_init")

    def emit_gpu_set_viewport(self) -> None:
        self._emit("call $host_gpu_set_viewport")

    def emit_gpu_clear(self) -> None:
        self._emit("call $host_gpu_clear")

    def emit_gpu_set_perspective_frustum(self) -> None:
        self._emit("call $host_gpu_set_perspective_frustum")

    def emit_gpu_set_view_matrix(self) -> None:
        self._emit("call $host_gpu_set_view_matrix")

    def emit_gpu_set_texture(self) -> None:
        self._emit("call $host_gpu_set_texture")

    def emit_gpu_set_blend(self) -> None:
        self._emit("call $host_gpu_set_blend")

    def emit_gpu_set_depth_test(self) -> None:
        self._emit("call $host_gpu_set_depth_test")

    def emit_gpu_set_depth_write(self) -> None:
        self._emit("call $host_gpu_set_depth_write")

    def emit_gpu_set_line_width(self) -> None:
        self._emit("call $host_gpu_set_line_width")

    def emit_gpu_submit(self) -> None:
        self._emit("call $host_gpu_submit")

    def emit_gpu_overlay_begin(self) -> None:
        self._emit("call $host_gpu_overlay_begin")

    def emit_gpu_overlay_end(self) -> None:
        self._emit("call $host_gpu_overlay_end")

    def emit_gpu_create_texture(self) -> None:
        self._emit("call $host_gpu_create_texture")

    def emit_gpu_present(self) -> None:
        self._emit("call $host_gpu_present")

    def emit_gpu_window_width(self) -> None:
        self._emit("call $host_gpu_window_width")

    def emit_gpu_window_height(self) -> None:
        self._emit("call $host_gpu_window_height")

    def emit_audio_queue_init(self) -> None:
        self._emit("call $host_audio_queue_init")

    def emit_audio_queue_push(self) -> None:
        self._emit("call $host_audio_queue_push")

    def emit_audio_queue_size(self) -> None:
        self._emit("call $host_audio_queue_size")
    
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
    
    _PLATFORM_INTRINSIC_ARITIES = {
        "__host_log__": 2,
        "__host_exit__": 1,
        "__host_time__": 0,
        "__host_random__": 0,
        "__dom_set_text__": 2,
        "__dom_append__": 2,
        "__dom_clear__": 0,
        "__dom_append_int__": 1,
        "__log_int__": 1,
        "__canvas_init__": 2,
        "__canvas_width__": 0,
        "__canvas_height__": 0,
        "__canvas_present__": 0,
        "__canvas_set_aspect_lock__": 1,
        "__frame_count__": 0,
        "__frame_time__": 0,
        "__window_width__": 0,
        "__window_height__": 0,
        "__pointer_x__": 0,
        "__pointer_y__": 0,
        "__pointer_down__": 0,
        "__key_down__": 2,
        "__key_pressed__": 2,
        "__key_released__": 2,
        "__audio_init__": 3,
        "__audio_play__": 0,
        "__audio_sample_rate__": 0,
        "__audio_stream_init__": 2,
        "__audio_stream_write__": 0,
        "__audio_stream_needs_samples__": 0,
        "__webgl_init__": 4,
        "__webgl_uniform1i__": 3,
        "__webgl_uniform2i__": 4,
        "__webgl_uniform1iv__": 4,
        "__webgl_uniform2iv__": 4,
        "__webgl_render__": 0,
        "__gpu_init__": 2,
        "__gpu_set_viewport__": 2,
        "__gpu_clear__": 3,
        "__gpu_set_perspective_frustum__": 6,
        "__gpu_set_view_matrix__": 1,
        "__gpu_set_texture__": 1,
        "__gpu_set_blend__": 1,
        "__gpu_set_depth_test__": 1,
        "__gpu_set_depth_write__": 1,
        "__gpu_set_line_width__": 1,
        "__gpu_submit__": 3,
        "__gpu_overlay_begin__": 2,
        "__gpu_overlay_end__": 0,
        "__gpu_create_texture__": 5,
        "__gpu_present__": 0,
        "__gpu_window_width__": 0,
        "__gpu_window_height__": 0,
        "__audio_queue_init__": 2,
        "__audio_queue_push__": 2,
        "__audio_queue_size__": 0,
        "__i64_to_f32_bits__": 1,
        "__i64_to_f64_bits__": 1,
    }
    _INTRINSIC_ARITIES = CORE_INTRINSIC_ARITIES | _PLATFORM_INTRINSIC_ARITIES
    
    def is_intrinsic(self, name: str) -> bool:
        """Check if name is an intrinsic supported by this backend."""
        return name in self._INTRINSIC_ARITIES

    def intrinsic_arity(self, name: str) -> int | None:
        """Return the expected arity for a supported intrinsic."""
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
        elif name == "__canvas_set_aspect_lock__":
            self.emit_canvas_set_aspect_lock()
        elif name == "__frame_count__":
            self.emit_frame_count()
        elif name == "__frame_time__":
            self.emit_frame_time()
        elif name == "__window_width__":
            self.emit_window_width()
        elif name == "__window_height__":
            self.emit_window_height()
        elif name == "__pointer_x__":
            self.emit_pointer_x()
        elif name == "__pointer_y__":
            self.emit_pointer_y()
        elif name == "__pointer_down__":
            self.emit_pointer_down()
        elif name == "__key_down__":
            self.emit_key_down()
        elif name == "__key_pressed__":
            self.emit_key_pressed()
        elif name == "__key_released__":
            self.emit_key_released()
        elif name == "__audio_init__":
            self.emit_audio_init()
        elif name == "__audio_play__":
            self.emit_audio_play()
        elif name == "__audio_sample_rate__":
            self.emit_audio_sample_rate()
        elif name == "__audio_stream_init__":
            self.emit_audio_stream_init()
        elif name == "__audio_stream_write__":
            self.emit_audio_stream_write()
        elif name == "__audio_stream_needs_samples__":
            self.emit_audio_stream_needs_samples()
        elif name == "__webgl_init__":
            self.emit_webgl_init()
        elif name == "__webgl_uniform1i__":
            self.emit_webgl_uniform1i()
        elif name == "__webgl_uniform2i__":
            self.emit_webgl_uniform2i()
        elif name == "__webgl_uniform1iv__":
            self.emit_webgl_uniform1iv()
        elif name == "__webgl_uniform2iv__":
            self.emit_webgl_uniform2iv()
        elif name == "__webgl_render__":
            self.emit_webgl_render()
        elif name == "__gpu_init__":
            self.emit_gpu_init()
        elif name == "__gpu_set_viewport__":
            self.emit_gpu_set_viewport()
        elif name == "__gpu_clear__":
            self.emit_gpu_clear()
        elif name == "__gpu_set_perspective_frustum__":
            self.emit_gpu_set_perspective_frustum()
        elif name == "__gpu_set_view_matrix__":
            self.emit_gpu_set_view_matrix()
        elif name == "__gpu_set_texture__":
            self.emit_gpu_set_texture()
        elif name == "__gpu_set_blend__":
            self.emit_gpu_set_blend()
        elif name == "__gpu_set_depth_test__":
            self.emit_gpu_set_depth_test()
        elif name == "__gpu_set_depth_write__":
            self.emit_gpu_set_depth_write()
        elif name == "__gpu_set_line_width__":
            self.emit_gpu_set_line_width()
        elif name == "__gpu_submit__":
            self.emit_gpu_submit()
        elif name == "__gpu_overlay_begin__":
            self.emit_gpu_overlay_begin()
        elif name == "__gpu_overlay_end__":
            self.emit_gpu_overlay_end()
        elif name == "__gpu_create_texture__":
            self.emit_gpu_create_texture()
        elif name == "__gpu_present__":
            self.emit_gpu_present()
        elif name == "__gpu_window_width__":
            self.emit_gpu_window_width()
        elif name == "__gpu_window_height__":
            self.emit_gpu_window_height()
        elif name == "__audio_queue_init__":
            self.emit_audio_queue_init()
        elif name == "__audio_queue_push__":
            self.emit_audio_queue_push()
        elif name == "__audio_queue_size__":
            self.emit_audio_queue_size()
        elif name == "__i64_to_f32_bits__":
            self.i64_to_f32_bits()
        elif name == "__i64_to_f64_bits__":
            self.i64_to_f64_bits()
    
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
    
    def run(self, output_path: PathLike, args: list[str], options: RunOptions | None = None) -> int | None:
        """Open or serve the generated HTML wrapper."""
        output_path = Path(output_path)
        if options is None:
            options = RunOptions()
        split_wasm = options.split_wasm
        serve_wasm = options.serve_wasm
        html_path = output_path if output_path.suffix == ".html" else output_path.with_suffix(".html")
        
        if split_wasm or serve_wasm:
            self._serve_html(html_path)
            return 0
        
        print(f"Opening {html_path}")
        self._open_browser(html_path.resolve().as_uri())
        return 0
    
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
                f"(single file with embedded WASM)\n"
                f"Open directly in a browser, or serve with: python -m http.server -d {cache_dir}"
            )
    
    def _open_browser(self, target: str) -> None:
        """Launch the browser without tying its output to the terminal."""
        import os
        import subprocess
        import sys
        import webbrowser
        
        if sys.platform.startswith("linux"):
            command = ["xdg-open", target]
        elif sys.platform == "darwin":
            command = ["open", target]
        elif sys.platform == "win32":
            os.startfile(target)
            return
        else:
            webbrowser.open(target)
            return
        
        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except FileNotFoundError:
            webbrowser.open(target)
    
    def _serve_html(self, html_path: Path) -> None:
        """Serve a generated WASM HTML file over HTTP until interrupted."""
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
        import time
        
        html_path = html_path.resolve()
        cache_dir = html_path.parent
        startup_timeout = 30.0
        heartbeat_timeout = 15.0
        state = {
            "page_loaded": False,
            "last_seen": time.monotonic(),
            "shutdown_requested": False,
        }
        
        class WasmServeHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, directory=str(cache_dir), **kwargs)
            
            def log_message(self, format: str, *args) -> None:
                if self.path.startswith("/__udewy_"):
                    return
                super().log_message(format, *args)
            
            def do_GET(self) -> None:
                if self.path == "/__udewy_heartbeat__":
                    state["page_loaded"] = True
                    state["last_seen"] = time.monotonic()
                    self.send_response(204)
                    self.end_headers()
                    return
                
                if self.path == f"/{html_path.name}":
                    state["page_loaded"] = True
                    state["last_seen"] = time.monotonic()
                
                super().do_GET()
            
            def do_POST(self) -> None:
                if self.path == "/__udewy_close__":
                    state["shutdown_requested"] = True
                    self.send_response(204)
                    self.end_headers()
                    return
                
                self.send_error(404)
        
        with ThreadingHTTPServer(("127.0.0.1", 0), WasmServeHandler) as server:
            server.timeout = 0.5
            host, port, *_ = server.server_address
            host = host.decode() if isinstance(host, bytes) else host
            url = f"http://{host}:{port}/{html_path.name}"
            print(f"Serving {html_path} at {url}")
            print("The server exits when the tab closes")
            self._open_browser(url)
            try:
                deadline = time.monotonic() + startup_timeout
                while True:
                    server.handle_request()
                    now = time.monotonic()
                    if state["shutdown_requested"]:
                        print("Stopped WASM server")
                        break
                    if state["page_loaded"] and now - state["last_seen"] > heartbeat_timeout:
                        print("Stopped WASM server after browser disconnect")
                        break
                    if not state["page_loaded"] and now > deadline:
                        print("Stopped WASM server after waiting for the browser")
                        break
            except KeyboardInterrupt:
                print("\nStopped WASM server")
    
    def _get_host_functions_js(self) -> str:
        """Return JavaScript code implementing WASM host functions."""
        return '''
const memory = new WebAssembly.Memory({ initial: 32 });
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
let canvasAspectWidth = 0;
let canvasAspectHeight = 0;

// Audio state (one-shot mode)
let audioCtx = null;
let audioSampleRate = 44100;
let audioNumSamples = 0;
let audioChannels = 1;
let audioBufferPtr = 0;
let audioPendingPlay = false;
let audioResumePending = false;
let audioPromptTimer = null;

// Audio streaming state
let audioStreamMode = false;

// WebGL fullscreen shader state
let webglCanvas = null;
let webglContext = null;
let webglProgram = null;
let webglPositionBuffer = null;
let webglMode = false;
let pointerInstalled = false;
let keyboardInstalled = false;
let pointerX = 0;
let pointerY = 0;
let pointerDown = false;
const keysDown = new Set();
const keysPressedFrame = new Set();
const keysReleasedFrame = new Set();
let audioStreamBufferSize = 0;
let audioStreamStarted = false;
let audioScriptNode = null;

// General-purpose audio queue (ring of Int16 samples) driven from WASM.
// Reuses the global `audioCtx` so the existing `requestAudioUnlock()` user-
// gesture path also unlocks queued playback.
let audioQueueRate = 44100;
let audioQueueChannels = 1;
let audioQueueRing = null;
let audioQueueRead = 0;
let audioQueueWrite = 0;
let audioQueueCount = 0;
let audioQueueCapacity = 0;
let audioQueueNode = null;
let audioQueueMode = false;
const AUDIO_QUEUE_BLOCK = 2048;

function audioQueueEnsureContext() {
    if (audioQueueNode) return;
    if (!audioCtx) {
        audioCtx = new AudioContext({ sampleRate: audioQueueRate });
    }
    audioQueueNode = audioCtx.createScriptProcessor(AUDIO_QUEUE_BLOCK, 0, audioQueueChannels);
    audioQueueNode.onaudioprocess = (e) => {
        const ch = e.outputBuffer.getChannelData(0);
        for (let i = 0; i < AUDIO_QUEUE_BLOCK; i++) {
            if (audioQueueCount > 0) {
                const s = audioQueueRing[audioQueueRead];
                audioQueueRead = (audioQueueRead + 1) % audioQueueCapacity;
                audioQueueCount--;
                ch[i] = s / 32768.0;
            } else {
                ch[i] = 0;
            }
        }
    };
    audioQueueNode.connect(audioCtx.destination);
    requestAudioUnlock();
}

// General-purpose 3D GPU state (WebGL1, batched textured+vertex-color)
let gpuMode = false;
let gpuCanvas = null;
let gpuGL = null;
let gpuProgram = null;
let gpuVbo = null;
let gpuQuadIbo = null;
let gpuQuadIboCount = 0;
let gpuStripIbo = null;
let gpuStripIboCount = 0;
let gpuTextures = [null];  // 1-indexed; index 0 reserved
let gpuWhiteTex = null;
let gpuCurrentTex = 0;
let gpuOverlayActive = false;
let gpuSavedDepthTest = true;
let gpuSavedDepthWrite = true;
let gpuLocPos = -1;
let gpuLocUV = -1;
let gpuLocColor = -1;
let gpuLocProj = null;
let gpuLocView = null;
let gpuLocSampler = null;
let gpuLocUseTex = null;
let gpuProj = new Float32Array(16);
let gpuView = new Float32Array(16);
let gpuOrthoProj = new Float32Array(16);
let gpuIdentity = new Float32Array([1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]);

// Double-buffer for audio: WASM writes to one, audio reads from other
let audioWriteBuffer = 0;  // 0 or 1
let audioReadBuffer = 0;
let audioBuffer0Ready = false;
let audioBuffer1Ready = false;
const AUDIO_SCRIPT_BUFFER_SIZE = 8192;  // Larger buffer for less crackling
const AUDIO_BUFFER_0_OFFSET = 786432;
const AUDIO_BUFFER_1_OFFSET = 786432 + (AUDIO_SCRIPT_BUFFER_SIZE * 2);  // samples * 2 bytes

function decodeString(ptr, len) {
    const view = new Uint8Array(memory.buffer);
    const bytes = view.slice(Number(ptr), Number(ptr) + Number(len));
    return new TextDecoder().decode(bytes);
}

function decodeI64Array(ptr, count) {
    const values = new Int32Array(Number(count));
    const view = new DataView(memory.buffer);
    const base = Number(ptr);
    for (let i = 0; i < Number(count); i++) {
        values[i] = Number(view.getBigInt64(base + (i * 8), true));
    }
    return values;
}

function appendOutput(text) {
    console.log(text);
}

function getDisplayCanvas() {
    return webglCanvas || canvas;
}

function updateCanvasLayout() {
    const displayCanvas = getDisplayCanvas();
    if (!displayCanvas || (!canvasMode && !webglMode)) {
        return;
    }

    if (canvasAspectWidth > 0 && canvasAspectHeight > 0) {
        const targetAspect = canvasAspectWidth / canvasAspectHeight;
        let displayWidth = window.innerWidth;
        let displayHeight = Math.floor(displayWidth / targetAspect);
        if (displayHeight > window.innerHeight) {
            displayHeight = window.innerHeight;
            displayWidth = Math.floor(displayHeight * targetAspect);
        }

        displayCanvas.style.position = 'fixed';
        displayCanvas.style.left = '50%';
        displayCanvas.style.top = '50%';
        displayCanvas.style.transform = 'translate(-50%, -50%)';
        displayCanvas.style.width = `${displayWidth}px`;
        displayCanvas.style.height = `${displayHeight}px`;
    } else {
        displayCanvas.style.position = 'fixed';
        displayCanvas.style.left = '0';
        displayCanvas.style.top = '0';
        displayCanvas.style.transform = 'none';
        displayCanvas.style.width = '100vw';
        displayCanvas.style.height = '100vh';
    }
}

window.addEventListener('resize', updateCanvasLayout);

function lockCanvasAspect() {
    const displayCanvas = getDisplayCanvas();
    if (displayCanvas) {
        canvasAspectWidth = displayCanvas.width;
        canvasAspectHeight = displayCanvas.height;
    } else if (canvasWidth > 0 && canvasHeight > 0) {
        canvasAspectWidth = canvasWidth;
        canvasAspectHeight = canvasHeight;
    }
    updateCanvasLayout();
}

function unlockCanvasAspect() {
    canvasAspectWidth = 0;
    canvasAspectHeight = 0;
    updateCanvasLayout();
}

function hideAudioPrompt() {
    if (audioPromptTimer !== null) {
        clearTimeout(audioPromptTimer);
        audioPromptTimer = null;
    }
    const overlay = document.getElementById('audio-play-overlay');
    if (overlay) {
        overlay.remove();
    }
}

function showAudioPrompt() {
    let overlay = document.getElementById('audio-play-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'audio-play-overlay';
        overlay.style.cssText = 'position:fixed; top:16px; left:16px; z-index:9999; pointer-events:none;';

        const button = document.createElement('button');
        button.id = 'audio-play-btn';
        button.textContent = 'Click to Enable Audio';
        button.style.cssText = 'pointer-events:auto; font-size:1em; padding:0.75em 1em; cursor:pointer; background:rgba(24,24,24,0.92); color:white; border:1px solid rgba(255,255,255,0.18); border-radius:999px; box-shadow:0 4px 16px rgba(0,0,0,0.35);';
        button.onclick = () => {
            requestAudioUnlock(true);
        };

        overlay.appendChild(button);
        document.body.appendChild(overlay);
    }
}

function playAudioBuffer() {
    const buffer = audioCtx.createBuffer(audioChannels, audioNumSamples, audioSampleRate);
    const view = new Int16Array(memory.buffer, audioBufferPtr, audioNumSamples * audioChannels);

    for (let ch = 0; ch < audioChannels; ch++) {
        const channelData = buffer.getChannelData(ch);
        for (let i = 0; i < audioNumSamples; i++) {
            const idx = audioChannels > 1 ? i * audioChannels + ch : i;
            channelData[i] = view[idx] / 32768.0;
        }
    }

    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(audioCtx.destination);
    source.start();
}

function flushPendingAudio() {
    if (!audioCtx || audioCtx.state !== 'running') {
        return;
    }

    hideAudioPrompt();

    if (audioPendingPlay) {
        audioPendingPlay = false;
        playAudioBuffer();
    }

    if (audioStreamMode && !audioStreamStarted && audioScriptNode) {
        audioScriptNode.connect(audioCtx.destination);
        audioStreamStarted = true;
    }
}

function scheduleAudioPrompt() {
    if (audioPromptTimer !== null) {
        return;
    }

    audioPromptTimer = window.setTimeout(() => {
        audioPromptTimer = null;
        if (audioCtx && audioCtx.state !== 'running') {
            showAudioPrompt();
        }
    }, 150);
}

function requestAudioUnlock(forceRetry=false) {
    if (!audioCtx) {
        return;
    }

    if (audioCtx.state === 'running') {
        flushPendingAudio();
        return;
    }

    scheduleAudioPrompt();

    if (audioResumePending && !forceRetry) {
        return;
    }

    audioResumePending = true;
    Promise.resolve(audioCtx.resume())
        .catch(() => null)
        .then(() => {
            audioResumePending = false;
            if (audioCtx && audioCtx.state === 'running') {
                flushPendingAudio();
            } else {
                showAudioPrompt();
            }
        });
}

function getInputCanvas() {
    return getDisplayCanvas();
}

function clampPointer(value, limit) {
    if (limit <= 0) return 0;
    if (value < 0) return 0;
    if (value >= limit) return limit - 1;
    return value;
}

function updatePointerFromEvent(event) {
    const targetCanvas = getInputCanvas();
    if (!targetCanvas) {
        pointerX = Math.floor(event.clientX);
        pointerY = Math.floor(event.clientY);
        return;
    }

    const rect = targetCanvas.getBoundingClientRect();
    const scaleX = rect.width ? targetCanvas.width / rect.width : 1;
    const scaleY = rect.height ? targetCanvas.height / rect.height : 1;
    const localX = Math.floor((event.clientX - rect.left) * scaleX);
    const localY = Math.floor((event.clientY - rect.top) * scaleY);

    pointerX = clampPointer(localX, targetCanvas.width);
    pointerY = clampPointer(localY, targetCanvas.height);
}

function ensurePointerHandlers() {
    if (pointerInstalled) return;
    pointerInstalled = true;

    window.addEventListener('pointermove', (event) => {
        updatePointerFromEvent(event);
    });

    window.addEventListener('pointerdown', (event) => {
        pointerDown = true;
        updatePointerFromEvent(event);
        requestAudioUnlock(true);
    });

    window.addEventListener('pointerup', (event) => {
        pointerDown = false;
        updatePointerFromEvent(event);
    });

    window.addEventListener('pointercancel', () => {
        pointerDown = false;
    });
}

function clearKeyboardFrameState() {
    keysPressedFrame.clear();
    keysReleasedFrame.clear();
}

function releaseAllKeys() {
    keysDown.clear();
    clearKeyboardFrameState();
}

function ensureKeyboardHandlers() {
    if (keyboardInstalled) return;
    keyboardInstalled = true;

    window.addEventListener('keydown', (event) => {
        const code = event.code || event.key;
        if (canvasMode || webglMode) {
            event.preventDefault();
        }
        if (!keysDown.has(code)) {
            keysPressedFrame.add(code);
        }
        keysDown.add(code);
        requestAudioUnlock(true);
    });

    window.addEventListener('keyup', (event) => {
        const code = event.code || event.key;
        if (canvasMode || webglMode) {
            event.preventDefault();
        }
        if (keysDown.has(code)) {
            keysReleasedFrame.add(code);
        }
        keysDown.delete(code);
    });

    window.addEventListener('blur', releaseAllKeys);
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            releaseAllKeys();
        }
    });
}

function compileWebglShader(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        const info = gl.getShaderInfoLog(shader) || 'unknown shader compile error';
        gl.deleteShader(shader);
        throw new Error(info);
    }
    return shader;
}

function createWebglProgram(gl, fragmentSource) {
    const vertexSource = `
attribute vec2 a_position;

void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
}
`;
    const vertexShader = compileWebglShader(gl, gl.VERTEX_SHADER, vertexSource);
    const fragmentShader = compileWebglShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
    const program = gl.createProgram();
    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);
    gl.deleteShader(vertexShader);
    gl.deleteShader(fragmentShader);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        const info = gl.getProgramInfoLog(program) || 'unknown program link error';
        gl.deleteProgram(program);
        throw new Error(info);
    }
    return program;
}

function q16ToF32(v) {
    return Number(v) / 65536.0;
}

function gpuEnsureQuadIndices(quadCount) {
    if (gpuQuadIboCount >= quadCount) return;
    const cap = Math.max(quadCount * 2, 64);
    const indices = new Uint16Array(cap * 6);
    for (let i = 0; i < cap; i++) {
        const v = i * 4;
        const o = i * 6;
        indices[o] = v;
        indices[o + 1] = v + 1;
        indices[o + 2] = v + 2;
        indices[o + 3] = v;
        indices[o + 4] = v + 2;
        indices[o + 5] = v + 3;
    }
    if (!gpuQuadIbo) gpuQuadIbo = gpuGL.createBuffer();
    gpuGL.bindBuffer(gpuGL.ELEMENT_ARRAY_BUFFER, gpuQuadIbo);
    gpuGL.bufferData(gpuGL.ELEMENT_ARRAY_BUFFER, indices, gpuGL.STATIC_DRAW);
    gpuQuadIboCount = cap;
}

function gpuEnsureStripIndices(vertCount) {
    if (gpuStripIboCount >= vertCount) return;
    const cap = Math.max(vertCount * 2, 64);
    const triCount = (cap - 2);
    const indices = new Uint16Array(Math.max(triCount, 0) * 3);
    let o = 0;
    for (let i = 0; i + 2 < cap; i++) {
        if ((i & 1) === 0) {
            indices[o++] = i;
            indices[o++] = i + 1;
            indices[o++] = i + 2;
        } else {
            indices[o++] = i + 1;
            indices[o++] = i;
            indices[o++] = i + 2;
        }
    }
    if (!gpuStripIbo) gpuStripIbo = gpuGL.createBuffer();
    gpuGL.bindBuffer(gpuGL.ELEMENT_ARRAY_BUFFER, gpuStripIbo);
    gpuGL.bufferData(gpuGL.ELEMENT_ARRAY_BUFFER, indices, gpuGL.STATIC_DRAW);
    gpuStripIboCount = cap;
}

function gpuMakeFrustum(out, l, r, b, t, n, f) {
    const rl = r - l, tb = t - b, fn = f - n;
    out[0] = (2 * n) / rl;
    out[1] = 0; out[2] = 0; out[3] = 0;
    out[4] = 0;
    out[5] = (2 * n) / tb;
    out[6] = 0; out[7] = 0;
    out[8] = (r + l) / rl;
    out[9] = (t + b) / tb;
    out[10] = -(f + n) / fn;
    out[11] = -1;
    out[12] = 0; out[13] = 0;
    out[14] = -(2 * f * n) / fn;
    out[15] = 0;
}

function gpuMakeOrtho(out, l, r, b, t, n, f) {
    const rl = r - l, tb = t - b, fn = f - n;
    out[0] = 2 / rl;
    out[1] = 0; out[2] = 0; out[3] = 0;
    out[4] = 0;
    out[5] = 2 / tb;
    out[6] = 0; out[7] = 0;
    out[8] = 0; out[9] = 0;
    out[10] = -2 / fn;
    out[11] = 0;
    out[12] = -(r + l) / rl;
    out[13] = -(t + b) / tb;
    out[14] = -(f + n) / fn;
    out[15] = 1;
}

function gpuCreateProgram(gl) {
    const vs = `
attribute vec3 a_pos;
attribute vec2 a_uv;
attribute vec4 a_color;
uniform mat4 u_proj;
uniform mat4 u_view;
varying vec2 v_uv;
varying vec4 v_color;
void main() {
    gl_Position = u_proj * u_view * vec4(a_pos, 1.0);
    v_uv = a_uv;
    v_color = a_color;
}
`;
    const fs = `
precision mediump float;
varying vec2 v_uv;
varying vec4 v_color;
uniform sampler2D u_tex;
uniform float u_use_tex;
void main() {
    vec4 tex = texture2D(u_tex, v_uv);
    vec4 textured = v_color * tex;
    gl_FragColor = mix(v_color, textured, u_use_tex);
}
`;
    const vsh = compileWebglShader(gl, gl.VERTEX_SHADER, vs);
    const fsh = compileWebglShader(gl, gl.FRAGMENT_SHADER, fs);
    const prog = gl.createProgram();
    gl.attachShader(prog, vsh);
    gl.attachShader(prog, fsh);
    gl.linkProgram(prog);
    gl.deleteShader(vsh);
    gl.deleteShader(fsh);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
        const info = gl.getProgramInfoLog(prog) || 'gpu program link error';
        gl.deleteProgram(prog);
        throw new Error(info);
    }
    return prog;
}

function gpuBindTextureSlot(slot) {
    const gl = gpuGL;
    let tex;
    if (slot === 0 || !gpuTextures[slot]) {
        tex = gpuWhiteTex;
        gl.uniform1f(gpuLocUseTex, 0.0);
    } else {
        tex = gpuTextures[slot];
        gl.uniform1f(gpuLocUseTex, 1.0);
    }
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.uniform1i(gpuLocSampler, 0);
    gpuCurrentTex = slot;
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
            updateCanvasLayout();
            ensurePointerHandlers();
            ctx = canvas.getContext('2d');
            
            // Hide text output in canvas mode
            if (outputElement) {
                outputElement.style.display = 'none';
            }
            
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
        host_canvas_set_aspect_lock: (enabled) => {
            if (Number(enabled) !== 0) {
                lockCanvasAspect();
            } else {
                unlockCanvasAspect();
            }
            return 0n;
        },
        host_frame_count: () => BigInt(frameCount),
        host_frame_time: () => BigInt(Math.floor(performance.now() - startTime)),
        host_window_width: () => BigInt(window.innerWidth),
        host_window_height: () => BigInt(window.innerHeight),
        host_pointer_x: () => BigInt(pointerX),
        host_pointer_y: () => BigInt(pointerY),
        host_pointer_down: () => (pointerDown ? 1n : 0n),
        host_key_down: (ptr, len) => {
            ensureKeyboardHandlers();
            return keysDown.has(decodeString(ptr, len)) ? 1n : 0n;
        },
        host_key_pressed: (ptr, len) => {
            ensureKeyboardHandlers();
            return keysPressedFrame.has(decodeString(ptr, len)) ? 1n : 0n;
        },
        host_key_released: (ptr, len) => {
            ensureKeyboardHandlers();
            return keysReleasedFrame.has(decodeString(ptr, len)) ? 1n : 0n;
        },
        // Audio
        host_audio_init: (sampleRate, numSamples, channels) => {
            audioSampleRate = Number(sampleRate);
            audioNumSamples = Number(numSamples);
            audioChannels = Number(channels);
            // Allocate buffer after canvas buffer (at 768KB)
            // Each sample is i16 (2 bytes), per channel
            audioBufferPtr = 786432;
            return BigInt(audioBufferPtr);
        },
        host_audio_play: () => {
            if (!audioCtx) {
                audioCtx = new AudioContext({ sampleRate: audioSampleRate });
            }

            audioPendingPlay = true;
            requestAudioUnlock();
            return 0n;
        },
        host_audio_sample_rate: () => BigInt(audioSampleRate),
        // Audio streaming using ScriptProcessorNode with double-buffering
        host_audio_stream_init: (sampleRate, bufferSize) => {
            audioSampleRate = Number(sampleRate);
            audioStreamBufferSize = AUDIO_SCRIPT_BUFFER_SIZE;
            audioChannels = 1;
            audioStreamMode = true;
            audioStreamStarted = false;
            audioWriteBuffer = 0;
            audioReadBuffer = 0;
            audioBuffer0Ready = false;
            audioBuffer1Ready = false;
            
            if (!audioCtx) {
                audioCtx = new AudioContext({ sampleRate: audioSampleRate });
            }
            
            // Create ScriptProcessorNode with larger buffer
            audioScriptNode = audioCtx.createScriptProcessor(AUDIO_SCRIPT_BUFFER_SIZE, 0, 1);
            
            audioScriptNode.onaudioprocess = (e) => {
                const output = e.outputBuffer.getChannelData(0);
                const bufSize = AUDIO_SCRIPT_BUFFER_SIZE;
                
                // Read from the ready buffer
                let bufferOffset, hasData;
                if (audioReadBuffer === 0 && audioBuffer0Ready) {
                    bufferOffset = AUDIO_BUFFER_0_OFFSET;
                    hasData = true;
                    audioBuffer0Ready = false;
                    audioReadBuffer = 1;
                } else if (audioReadBuffer === 1 && audioBuffer1Ready) {
                    bufferOffset = AUDIO_BUFFER_1_OFFSET;
                    hasData = true;
                    audioBuffer1Ready = false;
                    audioReadBuffer = 0;
                } else if (audioBuffer0Ready) {
                    bufferOffset = AUDIO_BUFFER_0_OFFSET;
                    hasData = true;
                    audioBuffer0Ready = false;
                    audioReadBuffer = 1;
                } else if (audioBuffer1Ready) {
                    bufferOffset = AUDIO_BUFFER_1_OFFSET;
                    hasData = true;
                    audioBuffer1Ready = false;
                    audioReadBuffer = 0;
                } else {
                    hasData = false;
                }
                
                if (hasData) {
                    const view = new Int16Array(memory.buffer, bufferOffset, bufSize);
                    for (let i = 0; i < bufSize; i++) {
                        output[i] = view[i] / 32768.0;
                    }
                } else {
                    // Silence if no buffer ready
                    for (let i = 0; i < bufSize; i++) {
                        output[i] = 0;
                    }
                }
            };
            
            // Return pointer to write buffer 0
            audioBufferPtr = AUDIO_BUFFER_0_OFFSET;
            return BigInt(audioBufferPtr);
        },
        host_audio_stream_write: () => {
            if (!audioStreamMode || !audioCtx) return 0n;

            requestAudioUnlock();
            
            // Mark current write buffer as ready and switch to other buffer
            if (audioWriteBuffer === 0) {
                audioBuffer0Ready = true;
                audioWriteBuffer = 1;
                audioBufferPtr = AUDIO_BUFFER_1_OFFSET;
            } else {
                audioBuffer1Ready = true;
                audioWriteBuffer = 0;
                audioBufferPtr = AUDIO_BUFFER_0_OFFSET;
            }
            
            // Return next buffer pointer for WASM to write to
            return BigInt(audioBufferPtr);
        },
        host_audio_stream_needs_samples: () => {
            // Returns true (-1) if we need more samples, false (0) if buffers are full
            if (!audioStreamMode) return 0n;
            // Need samples if the current write buffer is not marked ready
            if (audioWriteBuffer === 0 && !audioBuffer0Ready) return -1n;
            if (audioWriteBuffer === 1 && !audioBuffer1Ready) return -1n;
            return 0n;
        },
        // WebGL fullscreen fragment shader
        host_webgl_init: (shaderPtr, shaderLen, width, height) => {
            if (webglMode) return 0n;

            const w = Number(width);
            const h = Number(height);
            const fragmentSource = decodeString(shaderPtr, shaderLen);

            webglCanvas = document.getElementById('canvas');
            if (!webglCanvas) {
                webglCanvas = document.createElement('canvas');
                webglCanvas.id = 'canvas';
                document.body.insertBefore(webglCanvas, document.body.firstChild);
            }
            webglCanvas.width = w;
            webglCanvas.height = h;
            webglCanvas.style.display = 'block';
            updateCanvasLayout();
            ensurePointerHandlers();

            webglContext = webglCanvas.getContext('webgl');
            if (!webglContext) {
                console.error('WebGL not supported');
                if (outputElement) {
                    outputElement.textContent = 'WebGL not supported in this browser';
                }
                return -1n;
            }

            try {
                webglProgram = createWebglProgram(webglContext, fragmentSource);
            } catch (err) {
                console.error('WebGL shader setup failed:', err);
                if (outputElement) {
                    outputElement.textContent = `WebGL shader setup failed:\n${String(err)}`;
                }
                return -1n;
            }

            webglPositionBuffer = webglContext.createBuffer();
            webglContext.bindBuffer(webglContext.ARRAY_BUFFER, webglPositionBuffer);
            webglContext.bufferData(
                webglContext.ARRAY_BUFFER,
                new Float32Array([
                    -1.0, -1.0,
                    3.0, -1.0,
                    -1.0, 3.0,
                ]),
                webglContext.STATIC_DRAW,
            );

            webglContext.useProgram(webglProgram);
            const positionLocation = webglContext.getAttribLocation(webglProgram, 'a_position');
            if (positionLocation >= 0) {
                webglContext.enableVertexAttribArray(positionLocation);
                webglContext.vertexAttribPointer(positionLocation, 2, webglContext.FLOAT, false, 0, 0);
            }

            if (outputElement) {
                outputElement.style.display = 'none';
            }

            webglMode = true;
            startTime = performance.now();
            updateCanvasLayout();
            return 0n;
        },
        host_webgl_uniform1i: (namePtr, nameLen, value) => {
            if (!webglMode || !webglContext || !webglProgram) return 0n;

            const name = decodeString(namePtr, nameLen);
            const location = webglContext.getUniformLocation(webglProgram, name);
            if (location === null) return -1n;
            webglContext.useProgram(webglProgram);
            webglContext.uniform1i(location, Number(value));
            return 0n;
        },
        host_webgl_uniform2i: (namePtr, nameLen, x, y) => {
            if (!webglMode || !webglContext || !webglProgram) return 0n;

            const name = decodeString(namePtr, nameLen);
            const location = webglContext.getUniformLocation(webglProgram, name);
            if (location === null) return -1n;
            webglContext.useProgram(webglProgram);
            webglContext.uniform2i(location, Number(x), Number(y));
            return 0n;
        },
        host_webgl_uniform1iv: (namePtr, nameLen, valuesPtr, count) => {
            if (!webglMode || !webglContext || !webglProgram) return 0n;

            const name = decodeString(namePtr, nameLen);
            const location = webglContext.getUniformLocation(webglProgram, name);
            if (location === null) return -1n;
            webglContext.useProgram(webglProgram);
            webglContext.uniform1iv(location, decodeI64Array(valuesPtr, count));
            return 0n;
        },
        host_webgl_uniform2iv: (namePtr, nameLen, valuesPtr, count) => {
            if (!webglMode || !webglContext || !webglProgram) return 0n;

            const name = decodeString(namePtr, nameLen);
            const location = webglContext.getUniformLocation(webglProgram, name);
            if (location === null) return -1n;
            webglContext.useProgram(webglProgram);
            webglContext.uniform2iv(location, decodeI64Array(valuesPtr, Number(count) * 2));
            return 0n;
        },
        host_webgl_render: () => {
            if (!webglMode || !webglContext || !webglProgram) return 0n;

            webglContext.viewport(0, 0, webglCanvas.width, webglCanvas.height);
            webglContext.useProgram(webglProgram);
            webglContext.drawArrays(webglContext.TRIANGLES, 0, 3);
            return 0n;
        },
        // General-purpose batched 3D GPU surface
        host_gpu_init: (width, height) => {
            if (gpuMode) return 0n;
            const w = Number(width);
            const h = Number(height);
            gpuCanvas = document.getElementById('canvas');
            if (!gpuCanvas) {
                gpuCanvas = document.createElement('canvas');
                gpuCanvas.id = 'canvas';
                document.body.insertBefore(gpuCanvas, document.body.firstChild);
            }
            gpuCanvas.width = w;
            gpuCanvas.height = h;
            gpuCanvas.style.display = 'block';
            webglCanvas = gpuCanvas;
            webglMode = true;
            updateCanvasLayout();
            ensurePointerHandlers();
            ensureKeyboardHandlers();

            gpuGL = gpuCanvas.getContext('webgl', { antialias: true, depth: true, alpha: false, preserveDrawingBuffer: false });
            if (!gpuGL) {
                console.error('WebGL not supported');
                return -1n;
            }
            try {
                gpuProgram = gpuCreateProgram(gpuGL);
            } catch (err) {
                console.error('GPU shader setup failed:', err);
                return -1n;
            }
            gpuGL.useProgram(gpuProgram);
            gpuLocPos = gpuGL.getAttribLocation(gpuProgram, 'a_pos');
            gpuLocUV = gpuGL.getAttribLocation(gpuProgram, 'a_uv');
            gpuLocColor = gpuGL.getAttribLocation(gpuProgram, 'a_color');
            gpuLocProj = gpuGL.getUniformLocation(gpuProgram, 'u_proj');
            gpuLocView = gpuGL.getUniformLocation(gpuProgram, 'u_view');
            gpuLocSampler = gpuGL.getUniformLocation(gpuProgram, 'u_tex');
            gpuLocUseTex = gpuGL.getUniformLocation(gpuProgram, 'u_use_tex');

            gpuVbo = gpuGL.createBuffer();
            gpuWhiteTex = gpuGL.createTexture();
            gpuGL.bindTexture(gpuGL.TEXTURE_2D, gpuWhiteTex);
            gpuGL.texImage2D(gpuGL.TEXTURE_2D, 0, gpuGL.RGBA, 1, 1, 0, gpuGL.RGBA, gpuGL.UNSIGNED_BYTE, new Uint8Array([255, 255, 255, 255]));
            gpuGL.texParameteri(gpuGL.TEXTURE_2D, gpuGL.TEXTURE_MIN_FILTER, gpuGL.NEAREST);
            gpuGL.texParameteri(gpuGL.TEXTURE_2D, gpuGL.TEXTURE_MAG_FILTER, gpuGL.NEAREST);
            gpuGL.texParameteri(gpuGL.TEXTURE_2D, gpuGL.TEXTURE_WRAP_S, gpuGL.CLAMP_TO_EDGE);
            gpuGL.texParameteri(gpuGL.TEXTURE_2D, gpuGL.TEXTURE_WRAP_T, gpuGL.CLAMP_TO_EDGE);

            gpuGL.uniformMatrix4fv(gpuLocView, false, gpuIdentity);
            gpuGL.uniformMatrix4fv(gpuLocProj, false, gpuIdentity);
            gpuBindTextureSlot(0);

            gpuGL.enable(gpuGL.DEPTH_TEST);
            gpuGL.depthFunc(gpuGL.LEQUAL);
            gpuGL.disable(gpuGL.BLEND);

            if (outputElement) outputElement.style.display = 'none';
            gpuMode = true;
            startTime = performance.now();
            updateCanvasLayout();
            return 0n;
        },
        host_gpu_set_viewport: (w, h) => {
            if (!gpuMode) return 0n;
            gpuGL.viewport(0, 0, Number(w), Number(h));
            return 0n;
        },
        host_gpu_clear: (r_q, g_q, b_q) => {
            if (!gpuMode) return 0n;
            gpuGL.clearColor(q16ToF32(r_q), q16ToF32(g_q), q16ToF32(b_q), 1.0);
            gpuGL.clear(gpuGL.COLOR_BUFFER_BIT | gpuGL.DEPTH_BUFFER_BIT);
            return 0n;
        },
        host_gpu_set_perspective_frustum: (l_q, r_q, b_q, t_q, n_q, f_q) => {
            if (!gpuMode) return 0n;
            gpuMakeFrustum(gpuProj, q16ToF32(l_q), q16ToF32(r_q), q16ToF32(b_q), q16ToF32(t_q), q16ToF32(n_q), q16ToF32(f_q));
            gpuGL.useProgram(gpuProgram);
            gpuGL.uniformMatrix4fv(gpuLocProj, false, gpuProj);
            return 0n;
        },
        host_gpu_set_view_matrix: (matPtr) => {
            if (!gpuMode) return 0n;
            const view = new Float32Array(memory.buffer, Number(matPtr), 16);
            for (let i = 0; i < 16; i++) gpuView[i] = view[i];
            gpuGL.useProgram(gpuProgram);
            gpuGL.uniformMatrix4fv(gpuLocView, false, gpuView);
            return 0n;
        },
        host_gpu_set_texture: (texId) => {
            if (!gpuMode) return 0n;
            gpuGL.useProgram(gpuProgram);
            gpuBindTextureSlot(Number(texId));
            return 0n;
        },
        host_gpu_set_blend: (mode) => {
            if (!gpuMode) return 0n;
            const m = Number(mode);
            if (m === 0) {
                gpuGL.disable(gpuGL.BLEND);
            } else if (m === 1) {
                gpuGL.enable(gpuGL.BLEND);
                gpuGL.blendFunc(gpuGL.SRC_ALPHA, gpuGL.ONE_MINUS_SRC_ALPHA);
            } else {
                gpuGL.enable(gpuGL.BLEND);
                gpuGL.blendFunc(gpuGL.SRC_ALPHA, gpuGL.ONE);
            }
            return 0n;
        },
        host_gpu_set_depth_test: (on) => {
            if (!gpuMode) return 0n;
            if (Number(on) !== 0) gpuGL.enable(gpuGL.DEPTH_TEST);
            else gpuGL.disable(gpuGL.DEPTH_TEST);
            return 0n;
        },
        host_gpu_set_depth_write: (on) => {
            if (!gpuMode) return 0n;
            gpuGL.depthMask(Number(on) !== 0);
            return 0n;
        },
        host_gpu_set_line_width: (w_q) => {
            if (!gpuMode) return 0n;
            gpuGL.lineWidth(q16ToF32(w_q));
            return 0n;
        },
        host_gpu_submit: (kind, ptr, count) => {
            if (!gpuMode) return 0n;
            const k = Number(kind);
            const n = Number(count);
            if (n <= 0) return 0n;
            const gl = gpuGL;
            const stride = 9 * 4;
            const verts = new Float32Array(memory.buffer, Number(ptr), n * 9);
            gl.useProgram(gpuProgram);
            gl.bindBuffer(gl.ARRAY_BUFFER, gpuVbo);
            gl.bufferData(gl.ARRAY_BUFFER, verts, gl.STREAM_DRAW);
            gl.enableVertexAttribArray(gpuLocPos);
            gl.vertexAttribPointer(gpuLocPos, 3, gl.FLOAT, false, stride, 0);
            if (gpuLocUV >= 0) {
                gl.enableVertexAttribArray(gpuLocUV);
                gl.vertexAttribPointer(gpuLocUV, 2, gl.FLOAT, false, stride, 12);
            }
            if (gpuLocColor >= 0) {
                gl.enableVertexAttribArray(gpuLocColor);
                gl.vertexAttribPointer(gpuLocColor, 4, gl.FLOAT, false, stride, 20);
            }
            if (k === 0) {
                const quads = (n / 4) | 0;
                gpuEnsureQuadIndices(quads);
                gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, gpuQuadIbo);
                gl.drawElements(gl.TRIANGLES, quads * 6, gl.UNSIGNED_SHORT, 0);
            } else if (k === 1) {
                gpuEnsureStripIndices(n);
                gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, gpuStripIbo);
                gl.drawElements(gl.TRIANGLES, Math.max(n - 2, 0) * 3, gl.UNSIGNED_SHORT, 0);
            } else if (k === 2) {
                gl.drawArrays(gl.TRIANGLES, 0, n);
            } else if (k === 3) {
                gl.drawArrays(gl.LINES, 0, n);
            }
            return 0n;
        },
        host_gpu_overlay_begin: (sw, sh) => {
            if (!gpuMode) return 0n;
            const w = Number(sw);
            const h = Number(sh);
            gpuMakeOrtho(gpuOrthoProj, 0, w, h, 0, -1, 1);
            gpuGL.useProgram(gpuProgram);
            gpuGL.uniformMatrix4fv(gpuLocProj, false, gpuOrthoProj);
            gpuGL.uniformMatrix4fv(gpuLocView, false, gpuIdentity);
            gpuSavedDepthTest = gpuGL.getParameter(gpuGL.DEPTH_TEST);
            gpuSavedDepthWrite = gpuGL.getParameter(gpuGL.DEPTH_WRITEMASK);
            gpuGL.disable(gpuGL.DEPTH_TEST);
            gpuGL.depthMask(false);
            gpuOverlayActive = true;
            return 0n;
        },
        host_gpu_overlay_end: () => {
            if (!gpuMode) return 0n;
            gpuGL.useProgram(gpuProgram);
            gpuGL.uniformMatrix4fv(gpuLocProj, false, gpuProj);
            gpuGL.uniformMatrix4fv(gpuLocView, false, gpuView);
            if (gpuSavedDepthTest) gpuGL.enable(gpuGL.DEPTH_TEST);
            gpuGL.depthMask(!!gpuSavedDepthWrite);
            gpuOverlayActive = false;
            return 0n;
        },
        host_gpu_create_texture: (width, height, pixelsPtr, repeat, nearest) => {
            if (!gpuMode) return 0n;
            const gl = gpuGL;
            const w = Number(width);
            const h = Number(height);
            const pixels = new Uint8Array(memory.buffer, Number(pixelsPtr), w * h * 4);
            const tex = gl.createTexture();
            gl.bindTexture(gl.TEXTURE_2D, tex);
            gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(pixels));
            const filter = (Number(nearest) !== 0) ? gl.NEAREST : gl.LINEAR;
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filter);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
            const wrap = (Number(repeat) !== 0) ? gl.REPEAT : gl.CLAMP_TO_EDGE;
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, wrap);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, wrap);
            gpuTextures.push(tex);
            return BigInt(gpuTextures.length - 1);
        },
        host_gpu_present: () => {
            return 0n;
        },
        host_gpu_window_width: () => BigInt(gpuCanvas ? gpuCanvas.width : 0),
        host_gpu_window_height: () => BigInt(gpuCanvas ? gpuCanvas.height : 0),
        host_audio_queue_init: (sampleRate, channels) => {
            audioQueueRate = Number(sampleRate);
            audioQueueChannels = Number(channels);
            audioQueueCapacity = audioQueueRate * 2;  // ~2 s of buffer
            audioQueueRing = new Int16Array(audioQueueCapacity);
            audioQueueRead = 0;
            audioQueueWrite = 0;
            audioQueueCount = 0;
            try {
                audioQueueEnsureContext();
            } catch (err) {
                console.error('Audio queue init failed:', err);
                return -1n;
            }
            return 0n;
        },
        host_audio_queue_push: (ptr, nBytes) => {
            if (!audioQueueRing) return 0n;
            const samples = Number(nBytes) >> 1;
            const view = new Int16Array(memory.buffer, Number(ptr), samples);
            for (let i = 0; i < samples; i++) {
                if (audioQueueCount >= audioQueueCapacity) break;
                audioQueueRing[audioQueueWrite] = view[i];
                audioQueueWrite = (audioQueueWrite + 1) % audioQueueCapacity;
                audioQueueCount++;
            }
            return BigInt(samples * 2);
        },
        host_audio_queue_size: () => BigInt(audioQueueCount * 2),
    }
};

function animationLoop() {
    if ((!canvasMode && !audioStreamMode && !webglMode && !gpuMode) || !wasmInstance) return;

    frameCount++;
    wasmInstance.exports.main();
    clearKeyboardFrameState();
    requestAnimationFrame(animationLoop);
}
'''
    
    def _get_server_lifecycle_js(self) -> str:
        """Return JS hooks for shutting down the local HTTP server."""
        return '''
function setupServerLifecycle() {
    if (window.location.protocol !== 'http:' && window.location.protocol !== 'https:') {
        return;
    }

    const heartbeat = () => {
        fetch('/__udewy_heartbeat__', { cache: 'no-store' }).catch(() => {});
    };

    heartbeat();
    const timer = setInterval(heartbeat, 2000);
    const notifyClose = () => {
        clearInterval(timer);
        navigator.sendBeacon('/__udewy_close__', '');
    };

    window.addEventListener('pagehide', notifyClose, { once: true });
    window.addEventListener('beforeunload', notifyClose, { once: true });
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
        #output {{ background: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 4px; white-space: pre-wrap; font-family: monospace; }}
        #output:empty {{ display: none; }}
        #canvas {{ display: none; image-rendering: pixelated; }}
        body.canvas-mode #canvas {{ display: block; width: 100vw; height: 100vh; }}
    </style>
</head>
<body>
    <pre id="output"></pre>
    <script>
{host_js}
{self._get_server_lifecycle_js()}

async function run() {{
    outputElement = document.getElementById('output');
    setupServerLifecycle();
    try {{
        const response = await fetch('{wasm_filename}');
        const bytes = await response.arrayBuffer();
        const {{ instance }} = await WebAssembly.instantiate(bytes, imports);
        wasmInstance = instance;
        const result = instance.exports.main();
        console.log('Exit code:', result);
        if (canvasMode || webglMode || gpuMode) {{
            document.body.classList.add('canvas-mode');
            requestAnimationFrame(animationLoop);
        }} else if (audioStreamMode) {{
            requestAnimationFrame(animationLoop);
        }}
    }} catch (err) {{
        console.error('Error:', err);
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
        #output {{ background: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 4px; white-space: pre-wrap; font-family: monospace; }}
        #output:empty {{ display: none; }}
        #canvas {{ display: none; image-rendering: pixelated; }}
        body.canvas-mode #canvas {{ display: block; width: 100vw; height: 100vh; }}
    </style>
</head>
<body>
    <pre id="output"></pre>

    <script id="wasm-module" type="application/wasm-b64">
{wasm_b64}
    </script>

    <script>
{host_js}
{self._get_server_lifecycle_js()}

async function loadEmbeddedWasm() {{
    const b64 = document.getElementById('wasm-module').textContent.trim();
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    return WebAssembly.instantiate(bytes, imports);
}}

async function run() {{
    outputElement = document.getElementById('output');
    setupServerLifecycle();
    try {{
        const {{ instance }} = await loadEmbeddedWasm();
        wasmInstance = instance;
        const result = instance.exports.main();
        console.log('Exit code:', result);
        if (canvasMode || webglMode || gpuMode) {{
            document.body.classList.add('canvas-mode');
            requestAnimationFrame(animationLoop);
        }} else if (audioStreamMode) {{
            requestAnimationFrame(animationLoop);
        }}
    }} catch (err) {{
        console.error('Error:', err);
    }}
}}

run();
    </script>
</body>
</html>
'''
