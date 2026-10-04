"""
wasm32 backend for udewy.

Generates WebAssembly Text format (WAT) with browser-focused host function imports.

Semantic choices:
- All udewy values are i64 (wasm i64)
- Pointers are i64 values but truncated to i32 at every memory operation
- Strings use a length-prefixed layout (length at ptr-8)
- Browser functionality via imported JS host functions (no syscall emulation)

Host functions provided by JS:
- host_log(ptr, len): Output text to console/output element
- host_exit(code): Signal program exit
- host_time() -> i64: Current timestamp in milliseconds
- host_random() -> i64: Random 64-bit integer
"""

from os import PathLike
import os
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
    
    bytecode_target = 'wasm32'

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
        self._extern_fn_label_ids: set[int] = set()
        self._global_offsets: dict[int, int] = {}
        self._global_labels: dict[int, str] = {}
        self._string_offsets: dict[int, int] = {}
        self._string_labels: dict[int, str] = {}
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
            '(import "env" "host_log" (func $__host_log__ (param i64 i64) (result i64)))',
            '(import "env" "host_exit" (func $__host_exit__ (param i64) (result i64)))',
            '(import "env" "host_time" (func $__host_time__ (result i64)))',
            '(import "env" "host_random" (func $__host_random__ (result i64)))',
            # DOM manipulation
            '(import "env" "host_dom_set_text" (func $__host_dom_set_text__ (param i64 i64) (result i64)))',
            '(import "env" "host_dom_append" (func $__host_dom_append__ (param i64 i64) (result i64)))',
            '(import "env" "host_dom_clear" (func $__host_dom_clear__ (result i64)))',
            '(import "env" "host_dom_append_int" (func $__host_dom_append_int__ (param i64) (result i64)))',
            '(import "env" "host_log_int" (func $__host_log_int__ (param i64) (result i64)))',
            # Canvas graphics
            '(import "env" "host_canvas_init" (func $__host_canvas_init__ (param i64 i64) (result i64)))',
            '(import "env" "host_canvas_width" (func $__host_canvas_width__ (result i64)))',
            '(import "env" "host_canvas_height" (func $__host_canvas_height__ (result i64)))',
            '(import "env" "host_canvas_present" (func $__host_canvas_present__ (result i64)))',
            '(import "env" "host_canvas_set_aspect_lock" (func $__host_canvas_set_aspect_lock__ (param i64) (result i64)))',
            '(import "env" "host_frame_count" (func $__host_frame_count__ (result i64)))',
            '(import "env" "host_frame_time" (func $__host_frame_time__ (result i64)))',
            '(import "env" "host_window_width" (func $__host_window_width__ (result i64)))',
            '(import "env" "host_window_height" (func $__host_window_height__ (result i64)))',
            # Pointer input
            '(import "env" "host_pointer_x" (func $__host_pointer_x__ (result i64)))',
            '(import "env" "host_pointer_y" (func $__host_pointer_y__ (result i64)))',
            '(import "env" "host_pointer_down" (func $__host_pointer_down__ (result i64)))',
            '(import "env" "host_pointer_buttons" (func $__host_pointer_buttons__ (result i64)))',
            '(import "env" "host_pointer_wheel" (func $__host_pointer_wheel__ (result i64)))',
            # Keyboard input
            '(import "env" "host_key_down" (func $__host_key_down__ (param i64 i64) (result i64)))',
            '(import "env" "host_key_pressed" (func $__host_key_pressed__ (param i64 i64) (result i64)))',
            '(import "env" "host_key_released" (func $__host_key_released__ (param i64 i64) (result i64)))',
            # Audio (one-shot)
            '(import "env" "host_audio_init" (func $__host_audio_init__ (param i64 i64 i64) (result i64)))',
            '(import "env" "host_audio_play" (func $__host_audio_play__ (result i64)))',
            '(import "env" "host_audio_sample_rate" (func $__host_audio_sample_rate__ (result i64)))',
            # Audio (streaming)
            '(import "env" "host_audio_stream_init" (func $__host_audio_stream_init__ (param i64 i64) (result i64)))',
            '(import "env" "host_audio_stream_write" (func $__host_audio_stream_write__ (result i64)))',
            '(import "env" "host_audio_stream_needs_samples" (func $__host_audio_stream_needs_samples__ (result i64)))',
            # WebGL fullscreen shader
            '(import "env" "host_webgl_init" (func $__host_webgl_init__ (param i64 i64 i64 i64) (result i64)))',
            '(import "env" "host_webgl_uniform1i" (func $__host_webgl_uniform1i__ (param i64 i64 i64) (result i64)))',
            '(import "env" "host_webgl_uniform2i" (func $__host_webgl_uniform2i__ (param i64 i64 i64 i64) (result i64)))',
            '(import "env" "host_webgl_uniform1iv" (func $__host_webgl_uniform1iv__ (param i64 i64 i64 i64) (result i64)))',
            '(import "env" "host_webgl_uniform2iv" (func $__host_webgl_uniform2iv__ (param i64 i64 i64 i64) (result i64)))',
            '(import "env" "host_webgl_render" (func $__host_webgl_render__ (result i64)))',
            # General-purpose 3D GPU surface (textured + vertex-colored, batched)
            '(import "env" "host_gpu_init" (func $__host_gpu_init__ (param i64 i64) (result i64)))',
            '(import "env" "host_gpu_set_viewport" (func $__host_gpu_set_viewport__ (param i64 i64) (result i64)))',
            '(import "env" "host_gpu_clear" (func $__host_gpu_clear__ (param i64 i64 i64) (result i64)))',
            '(import "env" "host_gpu_set_perspective_frustum" (func $__host_gpu_set_perspective_frustum__ (param i64 i64 i64 i64 i64 i64) (result i64)))',
            '(import "env" "host_gpu_set_view_matrix" (func $__host_gpu_set_view_matrix__ (param i64) (result i64)))',
            '(import "env" "host_gpu_set_texture" (func $__host_gpu_set_texture__ (param i64) (result i64)))',
            '(import "env" "host_gpu_set_blend" (func $__host_gpu_set_blend__ (param i64) (result i64)))',
            '(import "env" "host_gpu_set_depth_test" (func $__host_gpu_set_depth_test__ (param i64) (result i64)))',
            '(import "env" "host_gpu_set_depth_write" (func $__host_gpu_set_depth_write__ (param i64) (result i64)))',
            '(import "env" "host_gpu_set_line_width" (func $__host_gpu_set_line_width__ (param i64) (result i64)))',
            '(import "env" "host_gpu_submit" (func $__host_gpu_submit__ (param i64 i64 i64) (result i64)))',
            '(import "env" "host_gpu_overlay_begin" (func $__host_gpu_overlay_begin__ (param i64 i64) (result i64)))',
            '(import "env" "host_gpu_overlay_end" (func $__host_gpu_overlay_end__ (result i64)))',
            '(import "env" "host_gpu_create_texture" (func $__host_gpu_create_texture__ (param i64 i64 i64 i64 i64) (result i64)))',
            '(import "env" "host_gpu_present" (func $__host_gpu_present__ (result i64)))',
            '(import "env" "host_gpu_window_width" (func $__host_gpu_window_width__ (result i64)))',
            '(import "env" "host_gpu_window_height" (func $__host_gpu_window_height__ (result i64)))',
            # Audio queue (general-purpose ring buffer pushed from WASM)
            '(import "env" "host_audio_queue_init" (func $__host_audio_queue_init__ (param i64 i64) (result i64)))',
            '(import "env" "host_audio_queue_push" (func $__host_audio_queue_push__ (param i64 i64) (result i64)))',
            '(import "env" "host_audio_queue_size" (func $__host_audio_queue_size__ (result i64)))',
            # Editor primitives (playground / contenteditable surfaces).
            '(import "env" "ud_dom_get_text_len" (func $__ud_dom_get_text_len__ (param i64) (result i64)))',
            '(import "env" "ud_dom_get_text" (func $__ud_dom_get_text__ (param i64 i64 i64) (result i64)))',
            '(import "env" "ud_dom_get_caret" (func $__ud_dom_get_caret__ (param i64) (result i64)))',
            '(import "env" "ud_dom_set_caret" (func $__ud_dom_set_caret__ (param i64 i64) (result i64)))',
            '(import "env" "ud_dom_add_event_listener" (func $__ud_dom_add_event_listener__ (param i64 i64 i64 i64) (result i64)))',
            '(import "env" "ud_dom_value" (func $__ud_dom_value__ (param i64 i64 i64) (result i64)))',
            '(import "env" "ud_dom_focus" (func $__ud_dom_focus__ (param i64) (result i64)))',
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
        
        # Function type declarations must come before imports so the implicit
        # type entries created by inline import signatures don't collide with
        # our named $type_fnN entries.
        for arity in sorted(self._indirect_arities):
            params = " ".join("(param i64)" for _ in range(arity))
            output.append(f"  (type {self._fn_type_name(arity)} (func {params} (result i64)))")

        # Memory import (for JS interop). Size is whatever is needed to fit the
        # statics block (which includes any __static_alloca__ reservations) plus
        # the trailing string/data pool, rounded up to 64K pages, with a small
        # extra cushion for the heap/stack and runtime scratch.
        page_size = 65536
        # The stack grows down from above all data: 2 MiB, or 1 MiB past the
        # data when that is higher (a large static reservation must not meet
        # the stack).
        stack_top = max(2097152, (self._data_offset + 15) // 16 * 16 + 1048576)
        required = max(self._data_offset + 2 * page_size, stack_top)
        pages = max(32, (required + page_size - 1) // page_size)
        output.append(f'  (import "env" "memory" (memory {pages}))')

        # Host function imports - must come before any definitions.
        for imp in self._imports:
            output.append(f"  {imp}")
        
        # Global definitions - after imports, before functions
        output.append(f'  (global $stack_ptr (mut i32) (i32.const {stack_top}))')
        if self._module_init_name is not None:
            output.append('  (global $__udewy_module_init_done (mut i32) (i32.const 0))')

        if self._fn_table_ids:
            output.append(f"  (table $__udewy_fn_table {len(self._fn_table_ids)} funcref)")
        
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
        main_arity = 0
        for label_id in self._fn_table_ids:
            if self._fn_labels.get(label_id) == self._user_main_name:
                main_arity = self._fn_param_counts.get(label_id, 0)
                break
        for _ in range(main_arity):
            output.append("    i64.const 0")
        output.append(f"    call {self._user_main_name}")
        output.append("  )")

        if self._fn_table_ids:
            refs = " ".join(self._fn_labels[label_id] for label_id in self._fn_table_ids)
            output.append(f"  (elem (i32.const 0) {refs})")
        
        # Data segments
        for offset, data in self._data_segments:
            hex_data = "".join(f"\\{b:02x}" for b in data)
            output.append(f'  (data (i32.const {offset}) "{hex_data}")')
        
        # Export main and the function table so JS host code can dispatch
        # callbacks held by udewy code (event listeners etc.) through
        # `instance.exports.__udewy_fn_table.get(idx)(...)`.
        output.append('  (export "main" (func $main))')
        if self._fn_table_ids:
            output.append('  (export "__udewy_fn_table" (table $__udewy_fn_table))')
        
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

    def intern_words(self, elements: list[int | str]) -> int:
        """Add initialized raw 64-bit words to linear memory."""
        label_id = self._next_label
        self._next_label += 1

        data = b""
        for element in elements:
            value = element if isinstance(element, int) else self._resolve_data_ref(element)
            data += (value & 0xFFFF_FFFF_FFFF_FFFF).to_bytes(8, "little")

        offset = self._alloc_data(data)
        self._static_offsets[label_id] = offset
        self._static_labels[label_id] = f".static{label_id}"

        return label_id
    
    def push_string_ref(self, label_id: int) -> None:
        """Push address of string data onto value stack."""
        offset = self._string_offsets[label_id] + 8  # Skip length prefix
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
        fn_name = f"${name}"
        self._fn_labels[label_id] = fn_name
        self._extern_fn_label_ids.add(label_id)
        param_count = self._fn_param_counts[label_id]
        params = " ".join("(param i64)" for _ in range(param_count))
        import_line = f'(import "env" "{name}" (func {fn_name} {params} (result i64)))'
        if import_line not in self._imports:
            self._imports.append(import_line)

    def declare_extern_function(self, name: str, num_params: int) -> int:
        label_id = self._next_label
        self._next_label += 1
        self._fn_param_counts[label_id] = num_params
        self.bind_extern_function(label_id, name)
        return label_id
    
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
        self._current_fn.append("    (local $div_lhs i64)")
        self._current_fn.append("    (local $div_rhs i64)")
        self._current_fn.append("    (local $sc_tmp i64)")
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
        if label_id in self._extern_fn_label_ids:
            raise RuntimeError("extern function references are not supported on the wasm32 backend")
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
    
    def _emit_bool_from_i32(self) -> None:
        """A wasm comparison's i32 0/1 as a udewy boolean, -1/0 as on the other
        targets: `not` is bitwise, so true must be all ones."""
        self._emit("i64.extend_i32_s")
        self._emit("i64.const -1")
        self._emit("i64.mul")

    def binary_op(self, op_kind: t1.Kind) -> None:
        """Apply binary operator to top two values on stack."""
        if op_kind == t1.Kind.TK_PLUS:
            self._emit("i64.add")
        elif op_kind == t1.Kind.TK_MINUS:
            self._emit("i64.sub")
        elif op_kind == t1.Kind.TK_MUL:
            self._emit("i64.mul")
        elif op_kind == t1.Kind.TK_IDIV:
            self._emit_signed_idiv()
        elif op_kind == t1.Kind.TK_MOD:
            self._emit_signed_mod()
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
            self._emit_bool_from_i32()
        elif op_kind == t1.Kind.TK_NOT_EQ:
            self._emit("i64.ne")
            self._emit_bool_from_i32()
        elif op_kind == t1.Kind.TK_GT:
            self._emit("i64.gt_s")
            self._emit_bool_from_i32()
        elif op_kind == t1.Kind.TK_LT:
            self._emit("i64.lt_s")
            self._emit_bool_from_i32()
        elif op_kind == t1.Kind.TK_GT_EQ:
            self._emit("i64.ge_s")
            self._emit_bool_from_i32()
        elif op_kind == t1.Kind.TK_LT_EQ:
            self._emit("i64.le_s")
            self._emit_bool_from_i32()
    
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

    def f32_bits_to_i64(self) -> None:
        """Interpret low 32 bits as f32 and convert to signed i64."""
        self._emit("i32.wrap_i64")
        self._emit("f32.reinterpret_i32")
        self._emit("i64.trunc_f32_s")

    def f64_bits_to_i64(self) -> None:
        """Interpret all 64 bits as f64 and convert to signed i64."""
        self._emit("f64.reinterpret_i64")
        self._emit("i64.trunc_f64_s")

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

    def _emit_signed_idiv(self) -> None:
        """Stack: lhs, rhs (rhs on top). Emit udewy signed division semantics."""
        self._emit("local.set $div_rhs")
        self._emit("local.set $div_lhs")
        self._emit("local.get $div_rhs")
        self._emit("i64.eqz")
        self._emit("if (result i64)")
        self._emit("  i64.const -1")
        self._emit("else")
        self._emit("  local.get $div_lhs")
        self._emit("  i64.const 0x8000000000000000")
        self._emit("  i64.eq")
        self._emit("  if (result i64)")
        self._emit("    local.get $div_rhs")
        self._emit("    i64.const -1")
        self._emit("    i64.eq")
        self._emit("    if (result i64)")
        self._emit("      local.get $div_lhs")
        self._emit("    else")
        self._emit("      local.get $div_lhs")
        self._emit("      local.get $div_rhs")
        self._emit("      i64.div_s")
        self._emit("    end")
        self._emit("  else")
        self._emit("    local.get $div_lhs")
        self._emit("    local.get $div_rhs")
        self._emit("    i64.div_s")
        self._emit("  end")
        self._emit("end")

    def _emit_signed_mod(self) -> None:
        """Stack: lhs, rhs (rhs on top). Emit udewy signed remainder semantics."""
        self._emit("local.set $div_rhs")
        self._emit("local.set $div_lhs")
        self._emit("local.get $div_rhs")
        self._emit("i64.eqz")
        self._emit("if (result i64)")
        self._emit("  local.get $div_lhs")
        self._emit("else")
        self._emit("  local.get $div_lhs")
        self._emit("  i64.const 0x8000000000000000")
        self._emit("  i64.eq")
        self._emit("  if (result i64)")
        self._emit("    local.get $div_rhs")
        self._emit("    i64.const -1")
        self._emit("    i64.eq")
        self._emit("    if (result i64)")
        self._emit("      i64.const 0")
        self._emit("    else")
        self._emit("      local.get $div_lhs")
        self._emit("      local.get $div_rhs")
        self._emit("      i64.rem_s")
        self._emit("    end")
        self._emit("  else")
        self._emit("    local.get $div_lhs")
        self._emit("    local.get $div_rhs")
        self._emit("    i64.rem_s")
        self._emit("  end")
        self._emit("end")

    def _emit_unsigned_idiv(self) -> None:
        """Stack: lhs, rhs (rhs on top). Emit udewy unsigned division semantics."""
        self._emit("local.set $div_rhs")
        self._emit("local.set $div_lhs")
        self._emit("local.get $div_rhs")
        self._emit("i64.eqz")
        self._emit("if (result i64)")
        self._emit("  i64.const -1")
        self._emit("else")
        self._emit("  local.get $div_lhs")
        self._emit("  local.get $div_rhs")
        self._emit("  i64.div_u")
        self._emit("end")

    def _emit_unsigned_mod(self) -> None:
        """Stack: lhs, rhs (rhs on top). Emit udewy unsigned remainder semantics."""
        self._emit("local.set $div_rhs")
        self._emit("local.set $div_lhs")
        self._emit("local.get $div_rhs")
        self._emit("i64.eqz")
        self._emit("if (result i64)")
        self._emit("  local.get $div_lhs")
        self._emit("else")
        self._emit("  local.get $div_lhs")
        self._emit("  local.get $div_rhs")
        self._emit("  i64.rem_u")
        self._emit("end")

    def unsigned_idiv(self) -> None:
        """Unsigned division. Stack: [left right] -> quotient."""
        self._emit_unsigned_idiv()

    def unsigned_mod(self) -> None:
        """Unsigned remainder. Stack: [left right] -> remainder."""
        self._emit_unsigned_mod()

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
        self._emit_bool_from_i32()
    
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
        self._emit("call $__host_log__")
    
    def emit_host_exit(self) -> None:
        """Emit a call to host_exit(code). Stack: [code] -> [code]"""
        self._emit("call $__host_exit__")
    
    def emit_host_time(self) -> None:
        """Emit a call to host_time(). Stack: [] -> [timestamp_ms]"""
        self._emit("call $__host_time__")
    
    def emit_host_random(self) -> None:
        """Emit a call to host_random(). Stack: [] -> [random_i64]"""
        self._emit("call $__host_random__")
    
    def emit_host_dom_set_text(self) -> None:
        """Emit a call to host_dom_set_text(ptr, len). Stack: [ptr len] -> [0]"""
        self._emit("call $__host_dom_set_text__")
    
    def emit_host_dom_append(self) -> None:
        """Emit a call to host_dom_append(ptr, len). Stack: [ptr len] -> [len]"""
        self._emit("call $__host_dom_append__")
    
    def emit_host_dom_clear(self) -> None:
        """Emit a call to host_dom_clear(). Stack: [] -> [0]"""
        self._emit("call $__host_dom_clear__")
    
    def emit_host_dom_append_int(self) -> None:
        """Emit a call to host_dom_append_int(value). Stack: [value] -> [value]"""
        self._emit("call $__host_dom_append_int__")
    
    def emit_host_log_int(self) -> None:
        """Emit a call to host_log_int(value). Stack: [value] -> [value]"""
        self._emit("call $__host_log_int__")
    
    def emit_canvas_init(self) -> None:
        """Emit a call to host_canvas_init(width, height). Stack: [width height] -> [buffer_ptr]"""
        self._emit("call $__host_canvas_init__")
    
    def emit_canvas_width(self) -> None:
        """Emit a call to host_canvas_width(). Stack: [] -> [width]"""
        self._emit("call $__host_canvas_width__")
    
    def emit_canvas_height(self) -> None:
        """Emit a call to host_canvas_height(). Stack: [] -> [height]"""
        self._emit("call $__host_canvas_height__")
    
    def emit_canvas_present(self) -> None:
        """Emit a call to host_canvas_present(). Stack: [] -> [0]"""
        self._emit("call $__host_canvas_present__")

    def emit_canvas_set_aspect_lock(self) -> None:
        """Emit a call to host_canvas_set_aspect_lock(enabled). Stack: [enabled] -> [0]"""
        self._emit("call $__host_canvas_set_aspect_lock__")
    
    def emit_frame_count(self) -> None:
        """Emit a call to host_frame_count(). Stack: [] -> [frame_number]"""
        self._emit("call $__host_frame_count__")
    
    def emit_frame_time(self) -> None:
        """Emit a call to host_frame_time(). Stack: [] -> [ms_since_start]"""
        self._emit("call $__host_frame_time__")
    
    def emit_window_width(self) -> None:
        """Emit a call to host_window_width(). Stack: [] -> [width]"""
        self._emit("call $__host_window_width__")
    
    def emit_window_height(self) -> None:
        """Emit a call to host_window_height(). Stack: [] -> [height]"""
        self._emit("call $__host_window_height__")
    
    def emit_pointer_x(self) -> None:
        """Emit a call to host_pointer_x(). Stack: [] -> [x]"""
        self._emit("call $__host_pointer_x__")
    
    def emit_pointer_y(self) -> None:
        """Emit a call to host_pointer_y(). Stack: [] -> [y]"""
        self._emit("call $__host_pointer_y__")
    
    def emit_pointer_down(self) -> None:
        """Emit a call to host_pointer_down(). Stack: [] -> [down]"""
        self._emit("call $__host_pointer_down__")
    
    def emit_pointer_buttons(self) -> None:
        """Emit a call to host_pointer_buttons(). Stack: [] -> [mask]"""
        self._emit("call $__host_pointer_buttons__")
    
    def emit_pointer_wheel(self) -> None:
        """Emit a call to host_pointer_wheel(). Stack: [] -> [steps]"""
        self._emit("call $__host_pointer_wheel__")
    
    def emit_key_down(self) -> None:
        """Emit a call to host_key_down(code_ptr, code_len). Stack: [ptr len] -> [down]"""
        self._emit("call $__host_key_down__")
    
    def emit_key_pressed(self) -> None:
        """Emit a call to host_key_pressed(code_ptr, code_len). Stack: [ptr len] -> [pressed]"""
        self._emit("call $__host_key_pressed__")
    
    def emit_key_released(self) -> None:
        """Emit a call to host_key_released(code_ptr, code_len). Stack: [ptr len] -> [released]"""
        self._emit("call $__host_key_released__")
    
    def emit_audio_init(self) -> None:
        """Emit a call to host_audio_init(sample_rate, num_samples, channels). Stack: [sr ns ch] -> [buffer_ptr]"""
        self._emit("call $__host_audio_init__")
    
    def emit_audio_play(self) -> None:
        """Emit a call to host_audio_play(). Stack: [] -> [0]"""
        self._emit("call $__host_audio_play__")
    
    def emit_audio_sample_rate(self) -> None:
        """Emit a call to host_audio_sample_rate(). Stack: [] -> [sample_rate]"""
        self._emit("call $__host_audio_sample_rate__")
    
    def emit_audio_stream_init(self) -> None:
        """Emit a call to host_audio_stream_init(sample_rate, buffer_size). Stack: [sr bs] -> [buffer_ptr]"""
        self._emit("call $__host_audio_stream_init__")
    
    def emit_audio_stream_write(self) -> None:
        """Emit a call to host_audio_stream_write(). Stack: [] -> [next_buffer_ptr]"""
        self._emit("call $__host_audio_stream_write__")
    
    def emit_audio_stream_needs_samples(self) -> None:
        """Emit a call to host_audio_stream_needs_samples(). Stack: [] -> [bool]"""
        self._emit("call $__host_audio_stream_needs_samples__")
    
    def emit_webgl_init(self) -> None:
        """Emit a call to host_webgl_init(shader_ptr, shader_len, width, height). Stack: [ptr len w h] -> [0]"""
        self._emit("call $__host_webgl_init__")
    
    def emit_webgl_uniform1i(self) -> None:
        """Emit a call to host_webgl_uniform1i(name_ptr, name_len, value). Stack: [ptr len value] -> [0]"""
        self._emit("call $__host_webgl_uniform1i__")
    
    def emit_webgl_uniform2i(self) -> None:
        """Emit a call to host_webgl_uniform2i(name_ptr, name_len, x, y). Stack: [ptr len x y] -> [0]"""
        self._emit("call $__host_webgl_uniform2i__")
    
    def emit_webgl_uniform1iv(self) -> None:
        """Emit a call to host_webgl_uniform1iv(name_ptr, name_len, values_ptr, count). Stack: [ptr len values count] -> [0]"""
        self._emit("call $__host_webgl_uniform1iv__")
    
    def emit_webgl_uniform2iv(self) -> None:
        """Emit a call to host_webgl_uniform2iv(name_ptr, name_len, values_ptr, count). Stack: [ptr len values count] -> [0]"""
        self._emit("call $__host_webgl_uniform2iv__")
    
    def emit_webgl_render(self) -> None:
        """Emit a call to host_webgl_render(). Stack: [] -> [0]"""
        self._emit("call $__host_webgl_render__")

    def emit_gpu_init(self) -> None:
        self._emit("call $__host_gpu_init__")

    def emit_gpu_set_viewport(self) -> None:
        self._emit("call $__host_gpu_set_viewport__")

    def emit_gpu_clear(self) -> None:
        self._emit("call $__host_gpu_clear__")

    def emit_gpu_set_perspective_frustum(self) -> None:
        self._emit("call $__host_gpu_set_perspective_frustum__")

    def emit_gpu_set_view_matrix(self) -> None:
        self._emit("call $__host_gpu_set_view_matrix__")

    def emit_gpu_set_texture(self) -> None:
        self._emit("call $__host_gpu_set_texture__")

    def emit_gpu_set_blend(self) -> None:
        self._emit("call $__host_gpu_set_blend__")

    def emit_gpu_set_depth_test(self) -> None:
        self._emit("call $__host_gpu_set_depth_test__")

    def emit_gpu_set_depth_write(self) -> None:
        self._emit("call $__host_gpu_set_depth_write__")

    def emit_gpu_set_line_width(self) -> None:
        self._emit("call $__host_gpu_set_line_width__")

    def emit_gpu_submit(self) -> None:
        self._emit("call $__host_gpu_submit__")

    def emit_gpu_overlay_begin(self) -> None:
        self._emit("call $__host_gpu_overlay_begin__")

    def emit_gpu_overlay_end(self) -> None:
        self._emit("call $__host_gpu_overlay_end__")

    def emit_gpu_create_texture(self) -> None:
        self._emit("call $__host_gpu_create_texture__")

    def emit_gpu_present(self) -> None:
        self._emit("call $__host_gpu_present__")

    def emit_gpu_window_width(self) -> None:
        self._emit("call $__host_gpu_window_width__")

    def emit_gpu_window_height(self) -> None:
        self._emit("call $__host_gpu_window_height__")

    def emit_audio_queue_init(self) -> None:
        self._emit("call $__host_audio_queue_init__")

    def emit_audio_queue_push(self) -> None:
        self._emit("call $__host_audio_queue_push__")

    def emit_audio_queue_size(self) -> None:
        self._emit("call $__host_audio_queue_size__")
    
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

    def cond_and_split(self) -> str:
        self._emit("local.set $sc_tmp")
        self._emit("local.get $sc_tmp")
        self._emit("i64.eqz")
        self._emit("if (result i64)")
        self._emit("  i64.const 0")
        self._emit("else")
        return ""

    def cond_and_join(self, false_label: str) -> None:
        self._emit("end")

    def cond_or_split(self) -> str:
        self._emit("local.set $sc_tmp")
        self._emit("local.get $sc_tmp")
        self._emit("i64.eqz")
        self._emit("if (result i64)")
        return ""

    def cond_or_join(self, done_label: str) -> None:
        self._emit("else")
        self._emit("  local.get $sc_tmp")
        self._emit("end")
    
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
        "__pointer_buttons__": 0,
        "__pointer_wheel__": 0,
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
        "__f32_bits_to_i64__": 1,
        "__f64_bits_to_i64__": 1,
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
        elif name == "__breakpoint__":
            # no debugger protocol for the browser target: a breakpoint is a no-op
            self.push_void()
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
        elif name == "__pointer_buttons__":
            self.emit_pointer_buttons()
        elif name == "__pointer_wheel__":
            self.emit_pointer_wheel()
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
        elif name == "__f32_bits_to_i64__":
            self.f32_bits_to_i64()
        elif name == "__f64_bits_to_i64__":
            self.f64_bits_to_i64()
    
    def get_builtin_constants(self) -> dict[str, int]:
        """WASM browser backend has no built-in constants."""
        return {}
    
    def compile_and_link(self, code: str, input_name: str, cache_dir: Path, **options) -> Path:
        """Compile WAT to WASM and generate HTML wrapper."""
        import subprocess
        
        cache_dir.mkdir(parents=True, exist_ok=True)
        wat_path = cache_dir / f"{input_name}.wat"
        wasm_path = cache_dir / f"{input_name}.wasm"
        
        # The direct path encodes the binary module in process
        # (UDEWY_OBJECT=direct) instead of running wat2wasm.
        if os.environ.get("UDEWY_OBJECT") == "direct":
            from .wasm_binary import assemble
            wasm_path.write_bytes(assemble(code))
        else:
            wat_path.write_text(code)
            # Convert WAT to WASM
            try:
                subprocess.run(["wat2wasm", str(wat_path), "-o", str(wasm_path)], check=True)
            except FileNotFoundError:
                raise RuntimeError(
                    "wat2wasm not found. Install wabt: https://github.com/WebAssembly/wabt\n"
                    f"WAT file generated at: {wat_path}"
                )
        return self.wrap(wasm_path, input_name, cache_dir, **options)
    
    def wrap(self, wasm_path: Path, input_name: str, cache_dir: Path, **options) -> Path:
        """Write the page (wasm_harness/) for the module at `wasm_path`: one HTML
        file with the module embedded, or with `split_wasm` a page that loads
        the module beside it. Returns the file to open or serve."""
        import base64
        import shutil
        
        split_wasm = options.get('split_wasm', False)
        link_artifacts = [Path(path) for path in options.get("link_artifacts", [])]
        
        cache_dir.mkdir(parents=True, exist_ok=True)
        html_path = cache_dir / f"{input_name}.html"
        served = cache_dir / f"{input_name}.wasm"
        module = wasm_path.read_bytes()
        if split_wasm and served.resolve() != wasm_path.resolve():
            shutil.copy2(wasm_path, served)
        
        browser_link_js: list[str] = []
        browser_link_wasm: dict[str, str] = {}
        for artifact in link_artifacts:
            if artifact.suffix == ".js":
                browser_link_js.append(artifact.read_text())
            elif artifact.suffix == ".wasm":
                if split_wasm:
                    shutil.copy2(artifact, cache_dir / artifact.name)
                else:
                    browser_link_wasm[artifact.name] = base64.b64encode(artifact.read_bytes()).decode('ascii')
            else:
                raise RuntimeError(f"Unsupported wasm32 link artifact: {artifact}")
        
        values = {
            "MEMORY_PAGES": str(memory_pages(module)),
            "TITLE": input_name,
            "WASM_FILE": served.name,
            "WASM_B64": base64.b64encode(module).decode('ascii'),
            "LINKED_WASM": "\n".join(
                f'    <script data-wasm-artifact="{name}" type="application/wasm-b64">\n{data}\n    </script>'
                for name, data in browser_link_wasm.items()
            ),
        }
        values["HOST_JS"] = "\n".join([fill_harness(harness("host.js"), values), *browser_link_js])
        html_path.write_text(fill_harness(harness("split.html" if split_wasm else "embedded.html"), values))
        
        return html_path if not split_wasm else served
    
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


HARNESS = Path(__file__).parent / "wasm_harness"


def harness(name: str) -> str:
    """One of the page templates every wasm32 module runs in (wasm_harness/README.md)."""
    return (HARNESS / name).read_text()


def fill_harness(template: str, values: dict[str, str]) -> str:
    """Replace each `@@NAME@@` in `template` by `values[NAME]`, in one pass:
    a value is not searched for placeholders."""
    import re
    return re.sub(r"@@([A-Z0-9_]+)@@", lambda match: values[match.group(1)], template)


def memory_pages(module: bytes) -> int:
    """The minimum page count of the memory a wasm module imports (1 when it
    imports none), read from its import section."""
    at = 8
    def leb() -> int:
        nonlocal at
        result, shift = 0, 0
        while True:
            byte = module[at]
            at += 1
            result |= (byte & 0x7F) << shift
            shift += 7
            if byte < 0x80:
                return result
    def skip_name() -> None:
        nonlocal at
        length = leb()
        at += length
    while at < len(module):
        section = module[at]
        at += 1
        size = leb()
        end = at + size
        if section == 2:
            for _ in range(leb()):
                skip_name()
                skip_name()
                kind = module[at]
                at += 1
                if kind == 0:
                    leb()
                elif kind == 1:
                    at += 1
                    flags = leb()
                    leb()
                    if flags & 1:
                        leb()
                elif kind == 2:
                    flags = leb()
                    return leb()
                else:
                    at += 2
        at = end
    return 1
