from __future__ import annotations

from os import PathLike
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import quote
import webbrowser

from .common import (
    Backend,
    BuildResult,
    DataRef,
    DataRefValue,
    DataValue,
    FnDataValue,
    FnRef,
    GlobalRef,
    IfState,
    IntDataValue,
    LocalRef,
    LoopState,
    ensure_cache_dir,
)


class WasmBackend(Backend):
    name = "wasm32"

    def __init__(self) -> None:
        self.code: list[str] = []
        self.globals: list[str] = []
        self.data_segments: list[str] = []
        self.fn_order: list[str] = []
        self.fn_indices: dict[str, int] = {}
        self.arity_types: set[int] = set()
        self.data_offsets: dict[str, int] = {}
        self.data_end = 8
        self.indent = 0
        self.current_param_count = 0
        self.current_max_slot = -1
        self.current_function_lines: list[str] = []
        self.current_is_main = False
        self.main_arity = 0

    def begin_module(self) -> None:
        self.code = []
        self.globals = []
        self.data_segments = []
        self.fn_order = []
        self.fn_indices = {}
        self.arity_types = set()
        self.data_offsets = {}
        self.data_end = 8
        self.indent = 0
        self.current_param_count = 0
        self.current_max_slot = -1
        self.current_function_lines = []
        self.current_is_main = False
        self.main_arity = 0

    def _align(self, size: int) -> int:
        remainder = size % 8
        if remainder == 0:
            return size
        return size + (8 - remainder)

    def _line(self, text: str) -> None:
        self.current_function_lines.append(f"{'  ' * self.indent}{text}")

    def _escape_bytes(self, data: bytes) -> str:
        chars = []
        for byte in data:
            if 32 <= byte < 127 and byte not in (34, 92):
                chars.append(chr(byte))
            else:
                chars.append(f"\\{byte:02x}")
        return "".join(chars)

    def _data_offset(self, ref: DataRef) -> int:
        return self.data_offsets[ref.symbol] + ref.offset

    def _global_name(self, ref: GlobalRef) -> str:
        return f"$g_{ref.symbol}"

    def _fn_name(self, ref: FnRef) -> str:
        return f"$f_{ref.symbol}"

    def _slot_name(self, slot: int) -> str:
        return f"$v{slot}"

    def _tmp_name(self, idx: int) -> str:
        return f"$t{idx}"

    def note_function(self, fn: FnRef) -> None:
        if fn.symbol not in self.fn_indices:
            self.fn_indices[fn.symbol] = len(self.fn_order)
            self.fn_order.append(fn.symbol)
        self.arity_types.add(fn.arity)

    def define_global_int(self, ref: GlobalRef, value: int) -> None:
        self.globals.append(f'  (global {self._global_name(ref)} (mut i64) (i64.const {value}))')

    def define_global_data(self, ref: GlobalRef, data_ref: DataRef) -> None:
        self.globals.append(
            f'  (global {self._global_name(ref)} (mut i64) (i64.const {self._data_offset(data_ref)}))'
        )

    def intern_string(self, symbol: str, values: list[int]) -> DataRef:
        raw = len(values).to_bytes(8, "little", signed=False) + bytes(values)
        offset = self._align(self.data_end)
        self.data_offsets[symbol] = offset
        self.data_end = offset + len(raw)
        self.data_segments.append(f'  (data (i32.const {offset}) "{self._escape_bytes(raw)}")')
        return DataRef(symbol, 8)

    def intern_array(self, symbol: str, values: list[DataValue]) -> DataRef:
        raw = len(values).to_bytes(8, "little", signed=False)
        for value in values:
            if isinstance(value, IntDataValue):
                raw += int(value.value).to_bytes(8, "little", signed=True)
            elif isinstance(value, FnDataValue):
                raw += int(self.fn_indices[value.fn.symbol]).to_bytes(8, "little", signed=True)
            elif isinstance(value, DataRefValue):
                raw += int(self._data_offset(value.ref)).to_bytes(8, "little", signed=True)
            else:
                raise TypeError(f"Unsupported data value: {value!r}")
        offset = self._align(self.data_end)
        self.data_offsets[symbol] = offset
        self.data_end = offset + len(raw)
        self.data_segments.append(f'  (data (i32.const {offset}) "{self._escape_bytes(raw)}")')
        return DataRef(symbol, 8)

    def begin_function(self, fn: FnRef, param_count: int, is_main: bool) -> None:
        self.current_function_lines = []
        self.current_param_count = param_count
        self.current_max_slot = param_count - 1
        self.current_is_main = is_main
        if is_main:
            self.main_arity = param_count
        header = [f"(func {self._fn_name(fn)}"]
        for slot in range(param_count):
            header.append(f"(param {self._slot_name(slot)} i64)")
        header.append("(result i64)")
        self.code.append("  " + " ".join(header))
        local_names = []
        slot = param_count
        while slot <= self.current_max_slot:
            local_names.append(f"(local {self._slot_name(slot)} i64)")
            slot += 1
        temp_index = 0
        while temp_index < 16:
            local_names.append(f"(local {self._tmp_name(temp_index)} i64)")
            temp_index += 1
        if local_names:
            self.code.append("    " + " ".join(local_names))
        self.indent = 2

    def register_local(self, ref: LocalRef, is_param: bool) -> None:
        _ = is_param
        if ref.slot > self.current_max_slot:
            self.current_max_slot = ref.slot

    def end_function(self, fn: FnRef) -> None:
        _ = fn
        self.code.extend(self.current_function_lines)
        self.code.append("    i64.const 0")
        self.code.append("  )")
        if self.current_is_main:
            self.code.append(f'  (export "__main__" (func {self._fn_name(fn)}))')
        self.current_function_lines = []
        self.current_param_count = 0
        self.current_max_slot = -1
        self.current_is_main = False
        self.indent = 0

    def push_const_i64(self, value: int) -> None:
        self._line(f"i64.const {value}")

    def push_void(self) -> None:
        self._line("i64.const 0")

    def push_local(self, ref: LocalRef) -> None:
        self._line(f"local.get {self._slot_name(ref.slot)}")

    def store_local(self, ref: LocalRef) -> None:
        self._line(f"local.set {self._slot_name(ref.slot)}")

    def push_global(self, ref: GlobalRef) -> None:
        self._line(f"global.get {self._global_name(ref)}")

    def store_global(self, ref: GlobalRef) -> None:
        self._line(f"global.set {self._global_name(ref)}")

    def push_fn_ref(self, ref: FnRef) -> None:
        self._line(f"i64.const {self.fn_indices[ref.symbol]}")

    def push_data_ref(self, ref: DataRef) -> None:
        self._line(f"i64.const {self._data_offset(ref)}")

    def unary_not(self) -> None:
        self._line("i64.const -1")
        self._line("i64.xor")

    def unary_neg(self) -> None:
        self._line("i64.const -1")
        self._line("i64.mul")

    def binary_add(self) -> None:
        self._line("i64.add")

    def binary_sub(self) -> None:
        self._line("i64.sub")

    def binary_mul(self) -> None:
        self._line("i64.mul")

    def binary_idiv(self) -> None:
        self._line("i64.div_s")

    def binary_mod(self) -> None:
        self._line("i64.rem_s")

    def binary_shl(self) -> None:
        self._line("i64.shl")

    def binary_shr(self) -> None:
        self._line("i64.shr_s")

    def binary_and(self) -> None:
        self._line("i64.and")

    def binary_or(self) -> None:
        self._line("i64.or")

    def binary_xor(self) -> None:
        self._line("i64.xor")

    def _compare(self, op: str) -> None:
        self._line(op)
        self._line("i64.extend_i32_u")
        self._line("i64.const -1")
        self._line("i64.mul")

    def binary_eq(self) -> None:
        self._compare("i64.eq")

    def binary_ne(self) -> None:
        self._compare("i64.ne")

    def binary_gt(self) -> None:
        self._compare("i64.gt_s")

    def binary_lt(self) -> None:
        self._compare("i64.lt_s")

    def binary_ge(self) -> None:
        self._compare("i64.ge_s")

    def binary_le(self) -> None:
        self._compare("i64.le_s")

    def call_direct(self, ref: FnRef, argc: int) -> None:
        _ = argc
        self._line(f"call {self._fn_name(ref)}")

    def call_indirect(self, argc: int) -> None:
        index_name = self._tmp_name(15)
        for arg_index in range(argc - 1, -1, -1):
            self._line(f"local.set {self._tmp_name(arg_index)}")
        self._line(f"local.set {index_name}")
        arg_index = 0
        while arg_index < argc:
            self._line(f"local.get {self._tmp_name(arg_index)}")
            arg_index += 1
        self._line(f"local.get {index_name}")
        self._line("i32.wrap_i64")
        self._line(f"call_indirect (type $t$arity_{argc})")

    def call_pipe(self) -> None:
        self._line(f"local.set {self._tmp_name(15)}")
        self._line(f"local.set {self._tmp_name(0)}")
        self._line(f"local.get {self._tmp_name(0)}")
        self._line(f"local.get {self._tmp_name(15)}")
        self._line("i32.wrap_i64")
        self._line("call_indirect (type $t$arity_1)")

    def call_intrinsic(self, name: str, argc: int) -> None:
        if name == "__load__":
            self._line("i32.wrap_i64")
            self._line("i64.load")
            return
        if name == "__store__":
            self._line(f"local.set {self._tmp_name(15)}")
            self._line(f"local.set {self._tmp_name(14)}")
            self._line(f"local.get {self._tmp_name(15)}")
            self._line("i32.wrap_i64")
            self._line(f"local.get {self._tmp_name(14)}")
            self._line("i64.store")
            self._line("i64.const 0")
            return
        if name == "__load8__":
            self._line("i32.wrap_i64")
            self._line("i64.load8_u")
            return
        if name == "__store8__":
            self._line(f"local.set {self._tmp_name(15)}")
            self._line(f"local.set {self._tmp_name(14)}")
            self._line(f"local.get {self._tmp_name(15)}")
            self._line("i32.wrap_i64")
            self._line(f"local.get {self._tmp_name(14)}")
            self._line("i64.store8")
            self._line("i64.const 0")
            return
        if name == "__load16__":
            self._line("i32.wrap_i64")
            self._line("i64.load16_u")
            return
        if name == "__store16__":
            self._line(f"local.set {self._tmp_name(15)}")
            self._line(f"local.set {self._tmp_name(14)}")
            self._line(f"local.get {self._tmp_name(15)}")
            self._line("i32.wrap_i64")
            self._line(f"local.get {self._tmp_name(14)}")
            self._line("i64.store16")
            self._line("i64.const 0")
            return
        if name == "__load32__":
            self._line("i32.wrap_i64")
            self._line("i64.load32_u")
            return
        if name == "__store32__":
            self._line(f"local.set {self._tmp_name(15)}")
            self._line(f"local.set {self._tmp_name(14)}")
            self._line(f"local.get {self._tmp_name(15)}")
            self._line("i32.wrap_i64")
            self._line(f"local.get {self._tmp_name(14)}")
            self._line("i64.store32")
            self._line("i64.const 0")
            return
        if name.startswith("__syscall"):
            _ = argc
            self._line(f"call ${name}")
            return
        raise SyntaxError(f"Unsupported intrinsic for wasm32: {name}")

    def begin_if(self, token: str) -> IfState:
        return IfState(token)

    def if_condition(self, state: IfState) -> None:
        _ = state
        self._line("i64.const 0")
        self._line("i64.ne")
        self._line("if")
        self.indent += 1

    def begin_else(self, state: IfState) -> None:
        state.has_else = True
        self.indent -= 1
        self._line("else")
        self.indent += 1

    def end_if(self, state: IfState) -> None:
        _ = state
        self.indent -= 1
        self._line("end")

    def begin_loop(self, token: str) -> LoopState:
        state = LoopState(token)
        self._line(f"block ${token}_end")
        self.indent += 1
        self._line(f"loop ${token}_start")
        self.indent += 1
        return state

    def loop_condition(self, state: LoopState) -> None:
        self._line("i64.eqz")
        self._line(f"br_if ${state.token}_end")

    def end_loop(self, state: LoopState) -> None:
        self._line(f"br ${state.token}_start")
        self.indent -= 1
        self._line("end")
        self.indent -= 1
        self._line("end")

    def emit_break(self, state: LoopState) -> None:
        self._line(f"br ${state.token}_end")

    def emit_continue(self, state: LoopState) -> None:
        self._line(f"br ${state.token}_start")

    def emit_return(self) -> None:
        self._line("return")

    def emit_expr_discard(self) -> None:
        self._line("drop")

    def finish_module(self) -> str:
        lines = ["(module"]
        lines.append('  (memory (export "memory") 1)')
        lines.append(f'  (global $__udewy_data_end (mut i64) (i64.const {self._align(self.data_end)}))')
        lines.append('  (export "__udewy_data_end" (global $__udewy_data_end))')
        arity = 0
        while arity <= 8:
            if arity in self.arity_types or arity == 1:
                params = " ".join("(param i64)" for _ in range(arity))
                lines.append(f"  (type $t$arity_{arity} (func {params} (result i64)))")
            arity += 1
        host_arity = 0
        while host_arity <= 6:
            params = " ".join("(param i64)" for _ in range(host_arity + 1))
            lines.append(f'  (import "env" "__syscall{host_arity}__" (func $__syscall{host_arity}__ {params} (result i64)))')
            host_arity += 1
        if self.fn_order:
            lines.append(f"  (table {len(self.fn_order)} funcref)")
        lines.extend(self.globals)
        lines.extend(self.code)
        if self.fn_order:
            fn_refs = " ".join(f"$f_{symbol}" for symbol in self.fn_order)
            lines.append(f"  (elem (i32.const 0) {fn_refs})")
        lines.extend(self.data_segments)
        lines.append(")")
        return "\n".join(lines) + "\n"

    def build(self, module_text: str, input_file: PathLike, cache_dir: PathLike) -> BuildResult:
        input_file = Path(input_file)
        cache_dir = ensure_cache_dir(cache_dir)
        wat_path = cache_dir / f"{input_file.stem}.wat"
        wasm_path = cache_dir / f"{input_file.stem}.wasm"
        js_path = cache_dir / f"{input_file.stem}.js"
        html_path = cache_dir / f"{input_file.stem}.html"
        wat_path.write_text(module_text)
        if shutil.which("wat2wasm") is not None:
            subprocess.run(["wat2wasm", str(wat_path), "-o", str(wasm_path)], check=True)
        else:
            wasm_path.write_bytes(b"")
        js_path.write_text(self._build_js(wat_path.name, wasm_path.name))
        html_path.write_text(self._build_html(js_path.name))
        return BuildResult(html_path, (wat_path, wasm_path, js_path))

    def _build_html(self, js_name: str) -> str:
        return "\n".join(
            [
                "<!doctype html>",
                "<html>",
                "  <head><meta charset=\"utf-8\"><title>udewy wasm32</title></head>",
                "  <body>",
                "    <pre id=\"output\"></pre>",
                f"    <script type=\"module\" src=\"{js_name}\"></script>",
                "  </body>",
                "</html>",
                "",
            ]
        )

    def _build_js(self, wat_name: str, wasm_name: str) -> str:
        return f"""
const output = document.getElementById("output");
const decoder = new TextDecoder();
const encoder = new TextEncoder();

function append(text) {{
  output.textContent += text;
}}

async function compileModule() {{
  const wasmResp = await fetch("{wasm_name}");
  const wasmBytes = await wasmResp.arrayBuffer();
  if (wasmBytes.byteLength > 0) {{
    return wasmBytes;
  }}
  const wabtMod = await import("https://esm.sh/wabt@1.0.34");
  const wabt = await wabtMod.default();
  const watText = await fetch("{wat_name}").then((resp) => resp.text());
  const parsed = wabt.parseWat("{wat_name}", watText);
  const binary = parsed.toBinary({{}});
  return binary.buffer;
}}

function hostImports(memoryRef) {{
  const importFn = (arity) => (num, ...args) => {{
    const syscall = Number(num);
    const mem = new Uint8Array(memoryRef.value.buffer);
    if (syscall === 1 && args.length >= 3) {{
      const ptr = Number(args[1]);
      const len = Number(args[2]);
      append(decoder.decode(mem.slice(ptr, ptr + len)));
      return 0n;
    }}
    if (syscall === 60 && args.length >= 1) {{
      return BigInt(Number(args[0]));
    }}
    console.warn("unhandled host syscall", arity, syscall, args);
    return 0n;
  }};
  return {{
    __syscall0__: importFn(0),
    __syscall1__: importFn(1),
    __syscall2__: importFn(2),
    __syscall3__: importFn(3),
    __syscall4__: importFn(4),
    __syscall5__: importFn(5),
    __syscall6__: importFn(6),
  }};
}}

async function main() {{
  const wasmBytes = await compileModule();
  const memoryRef = {{ value: null }};
  const imports = {{ env: hostImports(memoryRef) }};
  const {{ instance }} = await WebAssembly.instantiate(wasmBytes, imports);
  memoryRef.value = instance.exports.memory;
  if ({self.main_arity} === 0) {{
    instance.exports.__main__();
    return;
  }}
  const args = new URLSearchParams(location.search).getAll("arg");
  const mem = new Uint8Array(memoryRef.value.buffer);
  let heap = Number(instance.exports.__udewy_data_end.value);
  const argvPtr = heap;
  heap += (args.length + 1) * 8;
  const view = new DataView(memoryRef.value.buffer);
  for (let i = 0; i < args.length; i += 1) {{
    const raw = encoder.encode(args[i]);
    const ptr = heap;
    mem.set(raw, ptr);
    mem[ptr + raw.length] = 0;
    view.setBigUint64(argvPtr + (i * 8), BigInt(ptr), true);
    heap += raw.length + 1;
  }}
  view.setBigUint64(argvPtr + (args.length * 8), 0n, true);
  const callArgs = [];
  if ({self.main_arity} >= 1) {{
    callArgs.push(BigInt(args.length));
  }}
  if ({self.main_arity} >= 2) {{
    callArgs.push(BigInt(argvPtr));
  }}
  while (callArgs.length < {self.main_arity}) {{
    callArgs.push(0n);
  }}
  instance.exports.__main__(...callArgs);
}}

main().catch((error) => {{
  console.error(error);
  append(`\\nERROR: ${{error}}\\n`);
}});
"""

    def run(self, build_result: BuildResult, argv: list[str], cwd: PathLike) -> int:
        cwd = Path(cwd)
        html_path = build_result.artifact_path
        if not html_path.is_absolute():
            html_path = cwd / html_path
        query = ""
        if argv:
            query = "?" + "&".join(f"arg={quote(arg)}" for arg in argv)
        rel_path = html_path.relative_to(cwd)
        url = f"http://127.0.0.1:8000/{rel_path.as_posix()}{query}"
        subprocess.Popen(
            [sys.executable, "-m", "http.server", "8000"],
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        webbrowser.open(url)
        return 0

