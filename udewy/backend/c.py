from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
import subprocess

from .. import t1
from . import sdl_desktop
from .common import Backend, CORE_INTRINSIC_ARITIES, RunOptions


_U64_MASK = (1 << 64) - 1

_CAPABILITY_HEADERS: dict[str, set[str]] = {
    "stdio": {"<stdio.h>"},
    "stdlib": {"<stdlib.h>"},
    "math": {"<math.h>"},
}

_CAPABILITY_LINK_ARGS: dict[str, list[str]] = {
    "math": ["-lm"],
}

_C_CAPABILITY_ROOT = (Path(__file__).parent.parent / "third_party" / "c").resolve()

_KNOWN_EXTERN_CAPABILITIES: dict[str, str] = {
    "putchar": "stdio",
    "puts": "stdio",
    "malloc": "stdlib",
    "calloc": "stdlib",
    "free": "stdlib",
    "exit": "stdlib",
}

_HELPER_DEPS: dict[str, set[str]] = {
    "load_i16": {"load_u16"},
    "load_i32": {"load_u32"},
    "load_i64": {"load_u64"},
}

_PLATFORM_INTRINSIC_ARITIES = {
    "__i64_to_f32_bits__": 1,
    "__i64_to_f64_bits__": 1,
}

_ENDIAN_HELPERS = {
    "load_u16",
    "load_u32",
    "load_u64",
    "load_i16",
    "load_i32",
    "load_i64",
    "store_u16",
    "store_u32",
    "store_u64",
}


def _c_ident_part(name: str | None, fallback: str) -> str:
    if name is None:
        return fallback

    chars = [c if c.isalnum() or c == "_" else "_" for c in name]
    clean = "".join(chars).strip("_")
    if not clean:
        return fallback
    if clean[0].isdigit():
        clean = f"fn_{clean}"
    return clean


def _u64(value: int) -> int:
    return value & _U64_MASK


def _u64_literal(value: int) -> str:
    return f"UINT64_C(0x{_u64(value):016X})"


def _c_capability_for_source(path: Path) -> str | None:
    path = path.resolve()
    if path.suffix != ".udewy":
        return None
    try:
        relative = path.relative_to(_C_CAPABILITY_ROOT)
    except ValueError:
        return None
    return relative.with_suffix("").as_posix()


@dataclass
class _ArrayInit:
    name: str
    elements: list[int | str]


@dataclass
class _FunctionBuilder:
    label_id: int
    name: str
    source_name: str
    param_count: int
    is_main: bool
    lines: list[str] = field(default_factory=list)
    local_count: int = 0
    temp_count: int = 0
    current_expr: str | None = None
    saved_values: list[str] = field(default_factory=list)
    indent: int = 1


class CBackend(Backend):
    _INTRINSIC_ARITIES = CORE_INTRINSIC_ARITIES | _PLATFORM_INTRINSIC_ARITIES

    def __init__(self) -> None:
        self._next_label = 0
        self._module_init_name: str | None = None
        self._reachable_fn_label_ids: set[int] | None = None
        self._c_capabilities: set[str] = set()
        self._required_helpers: set[str] = set()

        self._fn_names: dict[int, str] = {}
        self._fn_source_names: dict[int, str] = {}
        self._fn_param_counts: dict[int, int] = {}
        self._extern_functions: set[int] = set()
        self._defined_functions: set[int] = set()
        self._main_label_id: int | None = None

        self._global_names: dict[int, str] = {}
        self._extern_globals: set[int] = set()
        self._global_initializers: dict[int, int | str] = {}

        self._string_names: dict[int, str] = {}
        self._string_contents: dict[int, bytes] = {}
        self._array_names: dict[int, str] = {}
        self._array_initializers: dict[int, _ArrayInit] = {}
        self._static_names: dict[int, str] = {}
        self._static_sizes: dict[int, int] = {}

        self._function_order: list[int] = []
        self._function_builders: dict[int, _FunctionBuilder] = {}
        self._current_fn: _FunctionBuilder | None = None

    def set_imported_sources(self, paths: list[Path]) -> None:
        for path in paths:
            capability = _c_capability_for_source(path)
            if capability is not None:
                self._c_capabilities.add(capability)

    def _has_capability(self, name: str) -> bool:
        return name in self._c_capabilities

    def _require_helper(self, name: str) -> None:
        self._required_helpers.add(name)

    def should_warn_unused_extern(self, name: str) -> bool:
        capability = _KNOWN_EXTERN_CAPABILITIES.get(name)
        return capability is None or not self._has_capability(capability)

    def _mangle_function_name(self, source_name: str | None, label_id: int) -> str:
        clean = _c_ident_part(source_name, f"fn_{label_id}")
        return f"udewy_fn_{clean}_{label_id}"

    def _alloc_label_id(self) -> int:
        label_id = self._next_label
        self._next_label += 1
        return label_id

    def _current(self) -> _FunctionBuilder:
        assert self._current_fn is not None
        return self._current_fn

    def _emit(self, line: str) -> None:
        fn = self._current()
        fn.lines.append(("    " * fn.indent) + line)

    def _set_current(self, expr: str) -> None:
        self._current().current_expr = expr

    def _current_expr(self) -> str:
        expr = self._current().current_expr
        if expr is None:
            raise RuntimeError("C backend missing current value")
        return expr

    def _emit_temp(self, expr: str) -> str:
        fn = self._current()
        name = f"t{fn.temp_count}"
        fn.temp_count += 1
        self._emit(f"udewy_word {name} = {expr};")
        return name

    def _save_current(self) -> str:
        expr = self._current_expr()
        if expr.startswith("t") and expr[1:].isdigit():
            temp = expr
        elif expr.startswith("local") and expr[5:].isdigit():
            temp = expr
        elif expr.startswith("arg") and expr[3:].isdigit():
            temp = expr
        elif expr.startswith("UINT64_C(") and expr.endswith(")"):
            temp = expr
        else:
            temp = self._emit_temp(expr)
        self._current().saved_values.append(temp)
        return temp

    def _pop_saved(self) -> str:
        fn = self._current()
        if not fn.saved_values:
            raise RuntimeError("C backend saved-value stack underflow")
        return fn.saved_values.pop()

    def _pop_saved_values(self, count: int) -> list[str]:
        if count == 0:
            return []
        fn = self._current()
        if len(fn.saved_values) < count:
            raise RuntimeError("C backend missing saved values")
        values = fn.saved_values[-count:]
        del fn.saved_values[-count:]
        return values

    def _direct_call_expr(self, label_id: int, arg_exprs: list[str]) -> str:
        name = self._fn_names[label_id]
        if label_id in self._extern_functions:
            wrapper_name = self._known_extern_wrapper_name(label_id)
            if wrapper_name is not None:
                return f"{wrapper_name}({', '.join(arg_exprs)})"
            return f"{name}({', '.join(arg_exprs)})"
        return f"{name}({', '.join(arg_exprs)})"

    def _indirect_call_expr(self, fn_expr: str, arg_exprs: list[str]) -> str:
        return f"{self._fn_cast_expr(fn_expr, len(arg_exprs))}({', '.join(arg_exprs)})"

    def _known_extern_wrapper_name(self, label_id: int) -> str | None:
        name = self._fn_names[label_id]
        capability = _KNOWN_EXTERN_CAPABILITIES.get(name)
        if capability is None or not self._has_capability(capability):
            return None
        return f"udewy_c_{capability}_{name}"

    def _symbol_expr(self, name: str) -> str:
        return f"((udewy_word)(uintptr_t)(&{name}))"

    def _fn_addr_expr(self, label_id: int) -> str:
        wrapper_name = self._known_extern_wrapper_name(label_id)
        if wrapper_name is not None:
            return self._symbol_expr(wrapper_name)
        return self._symbol_expr(self._fn_names[label_id])

    def _string_data_expr(self, label_id: int) -> str:
        name = self._string_names[label_id]
        return f"((udewy_word)(uintptr_t)(((unsigned char *)&{name}) + sizeof(udewy_word)))"

    def _array_data_expr(self, label_id: int) -> str:
        name = self._array_names[label_id]
        return f"((udewy_word)(uintptr_t)(((unsigned char *)&{name}) + sizeof(udewy_word)))"

    def _static_data_expr(self, label_id: int) -> str:
        return self._symbol_expr(self._static_names[label_id])

    def _directive_expr(self, value: int | str) -> str:
        if isinstance(value, int):
            return _u64_literal(value)
        return value

    def _fn_cast_expr(self, expr: str, arg_count: int) -> str:
        if arg_count == 0:
            args = "void"
        else:
            args = ", ".join("udewy_word" for _ in range(arg_count))
        return f"((udewy_word (*)({args}))(uintptr_t)({expr}))"

    def _arg_signature(self, param_count: int) -> str:
        if param_count == 0:
            return "void"
        return ", ".join(f"udewy_word arg{i}" for i in range(param_count))

    def _c_string_bytes(self, content: bytes) -> str:
        if not content:
            return "0"
        return ", ".join(str(byte) for byte in content)

    def _pure_int_array(self, elements: list[int | str]) -> bool:
        return all(isinstance(elem, int) for elem in elements)

    def _pure_int_initializer(self, value: int | str) -> bool:
        return isinstance(value, int)

    def _helper_closure(self) -> set[str]:
        helpers = set(self._required_helpers)
        changed = True
        while changed:
            changed = False
            for helper in tuple(helpers):
                for dep in _HELPER_DEPS.get(helper, set()):
                    if dep not in helpers:
                        helpers.add(dep)
                        changed = True
        return helpers

    def _render_endian_detection(self) -> list[str]:
        return [
            "#if defined(__BYTE_ORDER__) && defined(__ORDER_LITTLE_ENDIAN__) && defined(__ORDER_BIG_ENDIAN__)",
            "#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__",
            "#define UDEWY_LITTLE_ENDIAN 1",
            "#elif __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__",
            "#define UDEWY_BIG_ENDIAN 1",
            "#else",
            '#error "unsupported target byte order for udewy C backend"',
            "#endif",
            "#elif defined(_MSC_VER)",
            "#define UDEWY_LITTLE_ENDIAN 1",
            "#elif defined(__LITTLE_ENDIAN__) && !defined(__BIG_ENDIAN__)",
            "#define UDEWY_LITTLE_ENDIAN 1",
            "#elif defined(__BIG_ENDIAN__) && !defined(__LITTLE_ENDIAN__)",
            "#define UDEWY_BIG_ENDIAN 1",
            "#else",
            '#error "cannot determine target byte order for udewy C backend"',
            "#endif",
        ]

    def _render_alloca_prelude(self) -> list[str]:
        return [
            "#if defined(__GNUC__) || defined(__clang__)",
            "#define UDEWY_ALLOCA(size) __builtin_alloca(size)",
            "#elif defined(_MSC_VER)",
            "#include <malloc.h>",
            "#define UDEWY_ALLOCA(size) _alloca(size)",
            "#elif defined(__has_include)",
            "#if __has_include(<alloca.h>)",
            "#include <alloca.h>",
            "#define UDEWY_ALLOCA(size) alloca(size)",
            "#endif",
            "#endif",
            "#ifndef UDEWY_ALLOCA",
            '#error "udewy C backend requires alloca support from the selected C compiler"',
            "#endif",
        ]

    def _render_helper(self, name: str) -> list[str]:
        helpers: dict[str, list[str]] = {
            "bool": [
                "static udewy_word udewy_bool_from_c(int cond) {",
                "    return cond ? UDEWY_TRUE : UINT64_C(0);",
                "}",
            ],
            "signed_div": [
                "static udewy_word udewy_signed_div(udewy_word lhs, udewy_word rhs) {",
                "    if (lhs == UINT64_C(0x8000000000000000) && rhs == UINT64_C(0xFFFFFFFFFFFFFFFF)) {",
                "        return lhs;",
                "    }",
                "    return (udewy_word)(((int64_t)lhs) / ((int64_t)rhs));",
                "}",
            ],
            "signed_mod": [
                "static udewy_word udewy_signed_mod(udewy_word lhs, udewy_word rhs) {",
                "    if (lhs == UINT64_C(0x8000000000000000) && rhs == UINT64_C(0xFFFFFFFFFFFFFFFF)) {",
                "        return UINT64_C(0);",
                "    }",
                "    return (udewy_word)(((int64_t)lhs) % ((int64_t)rhs));",
                "}",
            ],
            "signed_shr": [
                "static udewy_word udewy_signed_shr_impl(udewy_word value, udewy_word bits) {",
                "    uint64_t shift = bits & UINT64_C(63);",
                "    uint64_t raw = value >> shift;",
                "    if (shift == 0) {",
                "        return value;",
                "    }",
                "    if (((int64_t)value) < 0) {",
                "        raw |= (~UINT64_C(0)) << (64 - shift);",
                "    }",
                "    return raw;",
                "}",
            ],
            "i64_to_f32_bits": [
                "static udewy_word udewy_i64_to_f32_bits(udewy_word value) {",
                "    union { float f; uint32_t u; } bits;",
                "    bits.f = (float)(int64_t)value;",
                "    return (udewy_word)bits.u;",
                "}",
            ],
            "i64_to_f64_bits": [
                "static udewy_word udewy_i64_to_f64_bits(udewy_word value) {",
                "    union { double f; uint64_t u; } bits;",
                "    bits.f = (double)(int64_t)value;",
                "    return bits.u;",
                "}",
            ],
            "f32_from_bits": [
                "static float udewy_f32_from_bits(udewy_word value) {",
                "    union { uint32_t u; float f; } bits;",
                "    bits.u = (uint32_t)value;",
                "    return bits.f;",
                "}",
            ],
            "f64_from_bits": [
                "static double udewy_f64_from_bits(udewy_word value) {",
                "    union { uint64_t u; double f; } bits;",
                "    bits.u = (uint64_t)value;",
                "    return bits.f;",
                "}",
            ],
            "load_u8": [
                "static udewy_word udewy_load_u8(udewy_word addr) {",
                "    return (udewy_word)(*(const unsigned char *)(uintptr_t)addr);",
                "}",
            ],
            "load_i8": [
                "static udewy_word udewy_load_i8(udewy_word addr) {",
                "    return (udewy_word)(int64_t)(int8_t)(*(const unsigned char *)(uintptr_t)addr);",
                "}",
            ],
            "load_u16": [
                "static udewy_word udewy_load_u16(udewy_word addr) {",
                "    const unsigned char *p = (const unsigned char *)(uintptr_t)addr;",
                "#if defined(UDEWY_LITTLE_ENDIAN)",
                "    return ((udewy_word)p[0]) | ((udewy_word)p[1] << 8);",
                "#else",
                "    return ((udewy_word)p[0] << 8) | ((udewy_word)p[1]);",
                "#endif",
                "}",
            ],
            "load_i16": [
                "static udewy_word udewy_load_i16(udewy_word addr) {",
                "    return (udewy_word)(int64_t)(int16_t)udewy_load_u16(addr);",
                "}",
            ],
            "load_u32": [
                "static udewy_word udewy_load_u32(udewy_word addr) {",
                "    const unsigned char *p = (const unsigned char *)(uintptr_t)addr;",
                "#if defined(UDEWY_LITTLE_ENDIAN)",
                "    return ((udewy_word)p[0]) | ((udewy_word)p[1] << 8) | ((udewy_word)p[2] << 16) | ((udewy_word)p[3] << 24);",
                "#else",
                "    return ((udewy_word)p[0] << 24) | ((udewy_word)p[1] << 16) | ((udewy_word)p[2] << 8) | ((udewy_word)p[3]);",
                "#endif",
                "}",
            ],
            "load_i32": [
                "static udewy_word udewy_load_i32(udewy_word addr) {",
                "    return (udewy_word)(int64_t)(int32_t)udewy_load_u32(addr);",
                "}",
            ],
            "load_u64": [
                "static udewy_word udewy_load_u64(udewy_word addr) {",
                "    const unsigned char *p = (const unsigned char *)(uintptr_t)addr;",
                "#if defined(UDEWY_LITTLE_ENDIAN)",
                "    return ((udewy_word)p[0]) | ((udewy_word)p[1] << 8) | ((udewy_word)p[2] << 16) | ((udewy_word)p[3] << 24) | ((udewy_word)p[4] << 32) | ((udewy_word)p[5] << 40) | ((udewy_word)p[6] << 48) | ((udewy_word)p[7] << 56);",
                "#else",
                "    return ((udewy_word)p[0] << 56) | ((udewy_word)p[1] << 48) | ((udewy_word)p[2] << 40) | ((udewy_word)p[3] << 32) | ((udewy_word)p[4] << 24) | ((udewy_word)p[5] << 16) | ((udewy_word)p[6] << 8) | ((udewy_word)p[7]);",
                "#endif",
                "}",
            ],
            "load_i64": [
                "static udewy_word udewy_load_i64(udewy_word addr) {",
                "    return udewy_load_u64(addr);",
                "}",
            ],
            "store_u8": [
                "static udewy_word udewy_store_u8(udewy_word value, udewy_word addr) {",
                "    *(unsigned char *)(uintptr_t)addr = (unsigned char)value;",
                "    return UINT64_C(0);",
                "}",
            ],
            "store_u16": [
                "static udewy_word udewy_store_u16(udewy_word value, udewy_word addr) {",
                "    unsigned char *p = (unsigned char *)(uintptr_t)addr;",
                "#if defined(UDEWY_LITTLE_ENDIAN)",
                "    p[0] = (unsigned char)(value >> 0);",
                "    p[1] = (unsigned char)(value >> 8);",
                "#else",
                "    p[0] = (unsigned char)(value >> 8);",
                "    p[1] = (unsigned char)(value >> 0);",
                "#endif",
                "    return UINT64_C(0);",
                "}",
            ],
            "store_u32": [
                "static udewy_word udewy_store_u32(udewy_word value, udewy_word addr) {",
                "    unsigned char *p = (unsigned char *)(uintptr_t)addr;",
                "#if defined(UDEWY_LITTLE_ENDIAN)",
                "    p[0] = (unsigned char)(value >> 0);",
                "    p[1] = (unsigned char)(value >> 8);",
                "    p[2] = (unsigned char)(value >> 16);",
                "    p[3] = (unsigned char)(value >> 24);",
                "#else",
                "    p[0] = (unsigned char)(value >> 24);",
                "    p[1] = (unsigned char)(value >> 16);",
                "    p[2] = (unsigned char)(value >> 8);",
                "    p[3] = (unsigned char)(value >> 0);",
                "#endif",
                "    return UINT64_C(0);",
                "}",
            ],
            "store_u64": [
                "static udewy_word udewy_store_u64(udewy_word value, udewy_word addr) {",
                "    unsigned char *p = (unsigned char *)(uintptr_t)addr;",
                "#if defined(UDEWY_LITTLE_ENDIAN)",
                "    p[0] = (unsigned char)(value >> 0);",
                "    p[1] = (unsigned char)(value >> 8);",
                "    p[2] = (unsigned char)(value >> 16);",
                "    p[3] = (unsigned char)(value >> 24);",
                "    p[4] = (unsigned char)(value >> 32);",
                "    p[5] = (unsigned char)(value >> 40);",
                "    p[6] = (unsigned char)(value >> 48);",
                "    p[7] = (unsigned char)(value >> 56);",
                "#else",
                "    p[0] = (unsigned char)(value >> 56);",
                "    p[1] = (unsigned char)(value >> 48);",
                "    p[2] = (unsigned char)(value >> 40);",
                "    p[3] = (unsigned char)(value >> 32);",
                "    p[4] = (unsigned char)(value >> 24);",
                "    p[5] = (unsigned char)(value >> 16);",
                "    p[6] = (unsigned char)(value >> 8);",
                "    p[7] = (unsigned char)(value >> 0);",
                "#endif",
                "    return UINT64_C(0);",
                "}",
            ],
        }
        return helpers[name]

    def _render_helpers(self) -> list[str]:
        helpers = self._helper_closure()
        ordered_helpers = [
            "bool",
            "signed_div",
            "signed_mod",
            "signed_shr",
            "i64_to_f32_bits",
            "i64_to_f64_bits",
            "f32_from_bits",
            "f64_from_bits",
            "load_u8",
            "load_i8",
            "load_u16",
            "load_i16",
            "load_u32",
            "load_i32",
            "load_u64",
            "load_i64",
            "store_u8",
            "store_u16",
            "store_u32",
            "store_u64",
        ]
        lines: list[str] = []
        if "alloca" in helpers:
            lines.extend(self._render_alloca_prelude())
            lines.append("")
        if helpers & _ENDIAN_HELPERS:
            lines.extend(self._render_endian_detection())
            lines.append("")
        for helper in ordered_helpers:
            if helper in helpers:
                lines.extend(self._render_helper(helper))
                lines.append("")
        return lines

    def _render_function(self, fn: _FunctionBuilder) -> str:
        parts = [f"static udewy_word {fn.name}({self._arg_signature(fn.param_count)}) {{"]
        for slot in range(fn.local_count):
            parts.append(f"    udewy_word local{slot} = UINT64_C(0);")
        parts.extend(fn.lines)
        parts.append("}")
        return "\n".join(parts)

    def _render_backend_init(self) -> str | None:
        lines: list[str] = []

        for array_init in self._array_initializers.values():
            for idx, elem in enumerate(array_init.elements):
                if isinstance(elem, int):
                    continue
                lines.append(f"    {array_init.name}.data[{idx}] = {elem};")

        for label_id, init in self._global_initializers.items():
            if isinstance(init, int):
                continue
            lines.append(f"    {self._global_names[label_id]} = {init};")

        if not lines:
            return None

        return "\n".join(
            [
                "static void udewy_backend_init(void) {",
                *lines,
                "}",
            ]
        )

    def _known_extern_label_ids(self) -> list[int]:
        return [
            label_id
            for label_id in sorted(self._extern_functions)
            if self._known_extern_wrapper_name(label_id) is not None
            and (self._reachable_fn_label_ids is None or label_id in self._reachable_fn_label_ids)
        ]

    def _render_known_extern_wrapper_prototypes(self) -> list[str]:
        prototypes: list[str] = []
        for label_id in self._known_extern_label_ids():
            name = self._known_extern_wrapper_name(label_id)
            assert name is not None
            param_count = self._fn_param_counts.get(label_id, 0)
            prototypes.append(f"static udewy_word {name}({self._arg_signature(param_count)});")
        return prototypes

    def _render_known_extern_wrapper(self, label_id: int) -> str:
        name = self._fn_names[label_id]
        wrapper = self._known_extern_wrapper_name(label_id)
        assert wrapper is not None

        wrappers = {
            "putchar": [
                f"static udewy_word {wrapper}(udewy_word arg0) {{",
                "    return (udewy_word)(int64_t)putchar((int)arg0);",
                "}",
            ],
            "puts": [
                f"static udewy_word {wrapper}(udewy_word arg0) {{",
                "    return (udewy_word)(int64_t)puts((const char *)(uintptr_t)arg0);",
                "}",
            ],
            "malloc": [
                f"static udewy_word {wrapper}(udewy_word arg0) {{",
                "    return (udewy_word)(uintptr_t)malloc((size_t)arg0);",
                "}",
            ],
            "calloc": [
                f"static udewy_word {wrapper}(udewy_word arg0, udewy_word arg1) {{",
                "    return (udewy_word)(uintptr_t)calloc((size_t)arg0, (size_t)arg1);",
                "}",
            ],
            "free": [
                f"static udewy_word {wrapper}(udewy_word arg0) {{",
                "    free((void *)(uintptr_t)arg0);",
                "    return UINT64_C(0);",
                "}",
            ],
            "exit": [
                f"static udewy_word {wrapper}(udewy_word arg0) {{",
                "    exit((int)arg0);",
                "    return UINT64_C(0);",
                "}",
            ],
        }
        return "\n".join(wrappers[name])

    def _render_known_extern_wrappers(self) -> list[str]:
        return [
            self._render_known_extern_wrapper(label_id)
            for label_id in self._known_extern_label_ids()
        ]

    def _render_data_defs(self) -> list[str]:
        parts: list[str] = []

        for label_id in sorted(self._string_names):
            name = self._string_names[label_id]
            content = self._string_contents[label_id]
            width = max(1, len(content))
            parts.append(
                "\n".join(
                    [
                        f"static struct {{ udewy_word len; unsigned char data[{width}]; }} {name} = {{",
                        f"    {_u64_literal(len(content))},",
                        f"    {{ {self._c_string_bytes(content)} }},",
                        "};",
                    ]
                )
            )

        for label_id in sorted(self._array_names):
            array_init = self._array_initializers[label_id]
            width = max(1, len(array_init.elements))
            if self._pure_int_array(array_init.elements):
                init_values = ", ".join(_u64_literal(elem) for elem in array_init.elements)
                if not init_values:
                    init_values = "UINT64_C(0)"
            else:
                init_values = "UINT64_C(0)"
            parts.append(
                "\n".join(
                    [
                        f"static struct {{ udewy_word len; udewy_word data[{width}]; }} {array_init.name} = {{",
                        f"    {_u64_literal(len(array_init.elements))},",
                        f"    {{ {init_values} }},",
                        "};",
                    ]
                )
            )

        for label_id in sorted(self._static_names):
            name = self._static_names[label_id]
            size = max(1, self._static_sizes[label_id])
            parts.append(f"static unsigned char {name}[{size}] = {{0}};")

        for label_id in sorted(self._global_names):
            name = self._global_names[label_id]
            if label_id in self._extern_globals:
                parts.append(f"extern udewy_word {name};")
                continue

            init = self._global_initializers[label_id]
            if self._pure_int_initializer(init):
                parts.append(f"static udewy_word {name} = {_u64_literal(init)};")
            else:
                parts.append(f"static udewy_word {name} = UINT64_C(0);")

        return parts

    def _render_prototypes(self, emitted_labels: list[int]) -> list[str]:
        prototypes: list[str] = []

        for label_id in emitted_labels:
            if label_id in self._extern_functions:
                continue
            name = self._fn_names[label_id]
            param_count = self._fn_param_counts.get(label_id, 0)
            prototypes.append(f"static udewy_word {name}({self._arg_signature(param_count)});")

        for label_id in sorted(self._extern_functions):
            if self._known_extern_wrapper_name(label_id) is not None:
                continue
            name = self._fn_names[label_id]
            param_count = self._fn_param_counts.get(label_id, 0)
            prototypes.append(f"extern udewy_word {name}({self._arg_signature(param_count)});")

        prototypes.extend(self._render_known_extern_wrapper_prototypes())
        return prototypes

    def _render_main_wrapper(self) -> str:
        lines = ["int main(int argc, char **argv) {", "    (void)argc;", "    (void)argv;"]

        if self._render_backend_init() is not None:
            lines.append("    udewy_backend_init();")

        if self._module_init_name is not None:
            module_init_name = self._module_init_name
            for label_id, source_name in self._fn_source_names.items():
                if source_name == self._module_init_name:
                    module_init_name = self._fn_names[label_id]
                    break
            lines.append(f"    {module_init_name}();")

        if self._main_label_id is None:
            lines.append("    return 0;")
        else:
            lines.append(f"    return (int){self._fn_names[self._main_label_id]}();")

        lines.append("}")
        return "\n".join(lines)

    # ========================================================================
    # Module lifecycle
    # ========================================================================

    def begin_module(self) -> None:
        pass

    def finish_module(self) -> str:
        emitted_labels = [
            label_id
            for label_id in self._function_order
            if label_id not in self._extern_functions
            and (self._reachable_fn_label_ids is None or label_id in self._reachable_fn_label_ids)
        ]
        helper_init = self._render_backend_init()
        include_lines = ["#include <stdint.h>", "#include <stddef.h>"]
        capability_headers = set[str]()
        for capability in self._c_capabilities:
            capability_headers.update(_CAPABILITY_HEADERS.get(capability, set()))
        include_lines.extend(sorted(f"#include {header}" for header in capability_headers))
        include_lines.append("")

        sections = [
            *include_lines,
            "typedef uint64_t udewy_word;",
            "#define UDEWY_TRUE (~UINT64_C(0))",
            "",
        ]
        sections.extend(self._render_helpers())

        data_defs = self._render_data_defs()
        prototypes = self._render_prototypes(emitted_labels)
        extern_wrappers = self._render_known_extern_wrappers()
        fn_defs = [self._render_function(self._function_builders[label_id]) for label_id in emitted_labels]

        if data_defs:
            sections.extend(data_defs)
            sections.append("")

        if prototypes:
            sections.extend(prototypes)
            sections.append("")

        if extern_wrappers:
            sections.extend(extern_wrappers)
            sections.append("")

        if helper_init is not None:
            sections.append(helper_init)
            sections.append("")

        sections.extend(fn_defs)
        if fn_defs:
            sections.append("")

        sections.append(self._render_main_wrapper())
        sections.append("")
        return "\n".join(sections)

    def set_module_init(self, name: str | None) -> None:
        self._module_init_name = None
        if name is None:
            return
        for label_id, source_name in self._fn_source_names.items():
            if source_name == name:
                self._module_init_name = self._fn_names[label_id]
                return
        self._module_init_name = name

    # ========================================================================
    # Data section - strings, arrays, globals
    # ========================================================================

    def intern_string(self, content: bytes) -> int:
        label_id = self._alloc_label_id()
        self._string_names[label_id] = f"udewy_string_{label_id}"
        self._string_contents[label_id] = content
        return label_id

    def intern_array(self, elements: list[int | str]) -> int:
        label_id = self._alloc_label_id()
        name = f"udewy_array_{label_id}"
        self._array_names[label_id] = name
        self._array_initializers[label_id] = _ArrayInit(name=name, elements=elements)
        return label_id

    def define_global(self, name: str | None, value: int | str) -> int:
        label_id = self._alloc_label_id()
        global_name = name if name is not None else f"udewy_global_{label_id}"
        self._global_names[label_id] = global_name
        self._global_initializers[label_id] = value
        return label_id

    def declare_extern_global(self, name: str) -> int:
        label_id = self._alloc_label_id()
        self._global_names[label_id] = name
        self._global_initializers[label_id] = 0
        self._extern_globals.add(label_id)
        return label_id

    def intern_static(self, size: int) -> int:
        label_id = self._alloc_label_id()
        self._static_names[label_id] = f"udewy_static_{label_id}"
        self._static_sizes[label_id] = size
        return label_id

    def push_string_ref(self, label_id: int) -> None:
        self._set_current(self._string_data_expr(label_id))

    def push_array_ref(self, label_id: int) -> None:
        self._set_current(self._array_data_expr(label_id))

    def push_global_ref(self, label_id: int) -> None:
        self._set_current(self._symbol_expr(self._global_names[label_id]))

    def push_static_ref(self, label_id: int) -> None:
        self._set_current(self._static_data_expr(label_id))

    def load_global(self, label_id: int) -> None:
        self._set_current(self._global_names[label_id])

    def store_global(self, label_id: int) -> None:
        self._emit(f"{self._global_names[label_id]} = {self._current_expr()};")

    def function_ref(self, label_id: int) -> str:
        return self._fn_addr_expr(label_id)

    def string_ref(self, label_id: int) -> str:
        return self._string_data_expr(label_id)

    def array_ref(self, label_id: int) -> str:
        return self._array_data_expr(label_id)

    def static_ref(self, label_id: int) -> str:
        return self._static_data_expr(label_id)

    # ========================================================================
    # Functions
    # ========================================================================

    def declare_function(self, name: str | None, num_params: int) -> int:
        label_id = self._alloc_label_id()
        fn_name = self._mangle_function_name(name, label_id)
        self._fn_names[label_id] = fn_name
        self._fn_source_names[label_id] = name or fn_name
        self._fn_param_counts[label_id] = num_params
        return label_id

    def bind_extern_function(self, label_id: int, name: str) -> None:
        self._fn_names[label_id] = name
        self._fn_source_names[label_id] = name
        self._extern_functions.add(label_id)

    def declare_extern_function(self, name: str, num_params: int) -> int:
        label_id = self.declare_function(name, num_params)
        self.bind_extern_function(label_id, name)
        self._fn_param_counts[label_id] = num_params
        return label_id

    def begin_function(self, label_id: int, name: str, param_count: int, is_main: bool) -> None:
        if label_id not in self._extern_functions:
            self._fn_names[label_id] = self._mangle_function_name(name, label_id)
        fn = _FunctionBuilder(
            label_id=label_id,
            name=self._fn_names[label_id],
            source_name=name,
            param_count=param_count,
            is_main=is_main,
        )
        self._fn_source_names[label_id] = name
        self._fn_param_counts[label_id] = param_count
        self._current_fn = fn
        self._function_builders[label_id] = fn
        self._function_order.append(label_id)
        self._defined_functions.add(label_id)
        if is_main:
            self._main_label_id = label_id

    def end_function(self) -> None:
        if self._current_fn is None:
            raise RuntimeError("C backend end_function without active function")
        self._current_fn = None

    def set_reachable_functions(self, label_ids: set[int]) -> None:
        self._reachable_fn_label_ids = label_ids

    def load_param(self, index: int) -> None:
        self._set_current(f"arg{index}")

    def alloc_local(self) -> int:
        fn = self._current()
        slot = fn.local_count
        fn.local_count += 1
        return slot

    def load_local(self, slot: int) -> None:
        self._set_current(f"local{slot}")

    def store_local(self, slot: int) -> None:
        self._emit(f"local{slot} = {self._current_expr()};")

    # ========================================================================
    # Value stack operations
    # ========================================================================

    def push_const_i64(self, value: int) -> None:
        self._set_current(_u64_literal(value))

    def push_void(self) -> None:
        self._set_current("UINT64_C(0)")

    def push_fn_ref(self, label_id: int) -> None:
        self._set_current(self._fn_addr_expr(label_id))

    def pop_value(self) -> None:
        pass

    def save_value(self) -> None:
        self._save_current()

    def restore_value(self) -> None:
        self._set_current(self._pop_saved())

    # ========================================================================
    # Operators
    # ========================================================================

    def unary_op(self, op_kind: t1.Kind) -> None:
        value = self._current_expr()
        if op_kind == t1.Kind.TK_MINUS:
            self._set_current(self._emit_temp(f"(udewy_word)(UINT64_C(0) - {value})"))
        elif op_kind == t1.Kind.TK_NOT:
            self._set_current(self._emit_temp(f"~{value}"))
        else:
            raise RuntimeError(f"unsupported unary operator: {op_kind}")

    def binary_op(self, op_kind: t1.Kind) -> None:
        rhs = self._current_expr()
        lhs = self._pop_saved()

        if op_kind == t1.Kind.TK_PLUS:
            expr = f"{lhs} + {rhs}"
        elif op_kind == t1.Kind.TK_MINUS:
            expr = f"{lhs} - {rhs}"
        elif op_kind == t1.Kind.TK_MUL:
            expr = f"{lhs} * {rhs}"
        elif op_kind == t1.Kind.TK_IDIV:
            self._require_helper("signed_div")
            expr = f"udewy_signed_div({lhs}, {rhs})"
        elif op_kind == t1.Kind.TK_MOD:
            self._require_helper("signed_mod")
            expr = f"udewy_signed_mod({lhs}, {rhs})"
        elif op_kind == t1.Kind.TK_LEFT_SHIFT:
            expr = f"{lhs} << ({rhs} & UINT64_C(63))"
        elif op_kind == t1.Kind.TK_RIGHT_SHIFT:
            expr = f"{lhs} >> ({rhs} & UINT64_C(63))"
        elif op_kind == t1.Kind.TK_AND:
            expr = f"{lhs} & {rhs}"
        elif op_kind == t1.Kind.TK_OR:
            expr = f"{lhs} | {rhs}"
        elif op_kind == t1.Kind.TK_XOR:
            expr = f"{lhs} ^ {rhs}"
        elif op_kind == t1.Kind.TK_EQ:
            self._require_helper("bool")
            expr = f"udewy_bool_from_c({lhs} == {rhs})"
        elif op_kind == t1.Kind.TK_NOT_EQ:
            self._require_helper("bool")
            expr = f"udewy_bool_from_c({lhs} != {rhs})"
        elif op_kind == t1.Kind.TK_GT:
            self._require_helper("bool")
            expr = f"udewy_bool_from_c((int64_t){lhs} > (int64_t){rhs})"
        elif op_kind == t1.Kind.TK_LT:
            self._require_helper("bool")
            expr = f"udewy_bool_from_c((int64_t){lhs} < (int64_t){rhs})"
        elif op_kind == t1.Kind.TK_GT_EQ:
            self._require_helper("bool")
            expr = f"udewy_bool_from_c((int64_t){lhs} >= (int64_t){rhs})"
        elif op_kind == t1.Kind.TK_LT_EQ:
            self._require_helper("bool")
            expr = f"udewy_bool_from_c((int64_t){lhs} <= (int64_t){rhs})"
        else:
            raise RuntimeError(f"unsupported binary operator: {op_kind}")
        self._set_current(self._emit_temp(expr))

    def pipe_call(self) -> None:
        fn_expr = self._current_expr()
        arg_expr = self._pop_saved()
        self._set_current(self._emit_temp(f"{self._fn_cast_expr(fn_expr, 1)}({arg_expr})"))

    # ========================================================================
    # Memory operations (intrinsics)
    # ========================================================================

    def load_mem(self, width: int, signed: bool = False) -> None:
        suffix = f"{'i' if signed else 'u'}{width}"
        self._require_helper(f"load_{suffix}")
        self._set_current(self._emit_temp(f"udewy_load_{suffix}({self._current_expr()})"))

    def store_mem(self, width: int) -> None:
        addr = self._current_expr()
        value = self._pop_saved()
        self._require_helper(f"store_u{width}")
        self._emit(f"udewy_store_u{width}({value}, {addr});")
        self._set_current("UINT64_C(0)")

    def signed_shr(self) -> None:
        bits = self._current_expr()
        value = self._pop_saved()
        self._require_helper("signed_shr")
        self._set_current(self._emit_temp(f"udewy_signed_shr_impl({value}, {bits})"))

    # ========================================================================
    # Calls
    # ========================================================================

    def call_direct(self, label_id: int, num_args: int) -> None:
        arg_exprs = self._pop_saved_values(num_args)
        self._set_current(self._emit_temp(self._direct_call_expr(label_id, arg_exprs)))

    def call_indirect(self, num_args: int) -> None:
        values = self._pop_saved_values(num_args + 1)
        fn_expr = values[0]
        arg_exprs = values[1:]
        self._set_current(self._emit_temp(self._indirect_call_expr(fn_expr, arg_exprs)))

    def max_call_args(self) -> int | None:
        return None

    # ========================================================================
    # Control flow
    # ========================================================================

    def begin_if(self) -> None:
        fn = self._current()
        self._emit(f"if ({self._current_expr()} != UINT64_C(0)) {{")
        fn.indent += 1

    def begin_else(self) -> None:
        fn = self._current()
        fn.indent -= 1
        self._emit("} else {")
        fn.indent += 1

    def end_if(self) -> None:
        fn = self._current()
        fn.indent -= 1
        self._emit("}")

    def begin_loop(self) -> None:
        fn = self._current()
        self._emit("for (;;) {")
        fn.indent += 1

    def begin_loop_body(self) -> None:
        self._emit(f"if ({self._current_expr()} == UINT64_C(0)) {{")
        self._emit("    break;")
        self._emit("}")

    def end_loop(self) -> None:
        fn = self._current()
        fn.indent -= 1
        self._emit("}")

    def emit_break(self) -> None:
        self._emit("break;")

    def emit_continue(self) -> None:
        self._emit("continue;")

    def emit_return(self) -> None:
        self._emit(f"return {self._current_expr()};")

    # ========================================================================
    # Intrinsics
    # ========================================================================

    def is_intrinsic(self, name: str) -> bool:
        return name in self._INTRINSIC_ARITIES or self._mixed_extern_arg_slots(name) is not None

    def intrinsic_arity(self, name: str) -> int | None:
        mixed_args = self._mixed_extern_arg_slots(name)
        if mixed_args is not None:
            return 1 + (mixed_args * 2)
        return self._INTRINSIC_ARITIES.get(name)

    def intrinsic_static_arg_indices(self, name: str) -> set[int]:
        mixed_args = self._mixed_extern_arg_slots(name)
        if mixed_args is None:
            return set()
        return set(range(1, 1 + mixed_args * 2, 2))

    def _mixed_extern_arg_slots(self, name: str) -> int | None:
        prefix = "__call_extern_mixed_"
        suffix = "__"
        if not name.startswith(prefix) or not name.endswith(suffix):
            return None
        count_str = name[len(prefix) : -len(suffix)]
        if not count_str.isdigit():
            return None
        return int(count_str)

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

    def _mixed_c_arg_type(self, tag: int) -> str:
        if tag == 0:
            return "udewy_word"
        if tag == 1:
            return "float"
        if tag == 2:
            return "double"
        raise RuntimeError(f"unsupported mixed extern tag: {tag}")

    def _mixed_c_arg_expr(self, tag: int, expr: str) -> str:
        if tag == 0:
            return expr
        if tag == 1:
            self._require_helper("f32_from_bits")
            return f"udewy_f32_from_bits({expr})"
        if tag == 2:
            self._require_helper("f64_from_bits")
            return f"udewy_f64_from_bits({expr})"
        raise RuntimeError(f"unsupported mixed extern tag: {tag}")

    def _call_extern_mixed(self, type_tags: list[int]) -> None:
        if not type_tags:
            fn_expr = self._current_expr()
            arg_exprs: list[str] = []
        else:
            current_arg = self._current_expr()
            saved = self._pop_saved_values(len(type_tags))
            fn_expr = saved[0]
            arg_exprs = [*saved[1:], current_arg]

        arg_types = ", ".join(self._mixed_c_arg_type(tag) for tag in type_tags)
        if not arg_types:
            arg_types = "void"
        converted_args = [
            self._mixed_c_arg_expr(tag, expr)
            for tag, expr in zip(type_tags, arg_exprs)
        ]
        call_expr = f"((udewy_word (*)({arg_types}))(uintptr_t)({fn_expr}))({', '.join(converted_args)})"
        self._set_current(self._emit_temp(call_expr))

    def emit_intrinsic(self, name: str, num_args: int, intrinsic_data: object | None = None) -> None:
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
        elif name == "__alloca__":
            self._require_helper("alloca")
            size = self._current_expr()
            aligned_size = f"(({size} + UINT64_C(7)) & ~UINT64_C(7))"
            self._set_current(self._emit_temp(f"((udewy_word)(uintptr_t)UDEWY_ALLOCA((size_t){aligned_size}))"))
        elif name == "__static_alloca__":
            raise RuntimeError("__static_alloca__ should be lowered before intrinsic emission")
        elif name == "__signed_shr__":
            self.signed_shr()
        elif name == "__unsigned_idiv__":
            rhs = self._current_expr()
            lhs = self._pop_saved()
            self._set_current(self._emit_temp(f"{lhs} / {rhs}"))
        elif name == "__unsigned_mod__":
            rhs = self._current_expr()
            lhs = self._pop_saved()
            self._set_current(self._emit_temp(f"{lhs} % {rhs}"))
        elif name == "__unsigned_lt__":
            self._require_helper("bool")
            rhs = self._current_expr()
            lhs = self._pop_saved()
            self._set_current(self._emit_temp(f"udewy_bool_from_c({lhs} < {rhs})"))
        elif name == "__unsigned_gt__":
            self._require_helper("bool")
            rhs = self._current_expr()
            lhs = self._pop_saved()
            self._set_current(self._emit_temp(f"udewy_bool_from_c({lhs} > {rhs})"))
        elif name == "__unsigned_lte__":
            self._require_helper("bool")
            rhs = self._current_expr()
            lhs = self._pop_saved()
            self._set_current(self._emit_temp(f"udewy_bool_from_c({lhs} <= {rhs})"))
        elif name == "__unsigned_gte__":
            self._require_helper("bool")
            rhs = self._current_expr()
            lhs = self._pop_saved()
            self._set_current(self._emit_temp(f"udewy_bool_from_c({lhs} >= {rhs})"))
        elif name == "__i64_to_f32_bits__":
            self._require_helper("i64_to_f32_bits")
            self._set_current(self._emit_temp(f"udewy_i64_to_f32_bits({self._current_expr()})"))
        elif name == "__i64_to_f64_bits__":
            self._require_helper("i64_to_f64_bits")
            self._set_current(self._emit_temp(f"udewy_i64_to_f64_bits({self._current_expr()})"))
        else:
            self._call_extern_mixed(self._mixed_extern_type_tags(name, intrinsic_data))

    def get_builtin_constants(self) -> dict[str, int]:
        return {}

    # ========================================================================
    # Compilation and execution
    # ========================================================================

    def compile_and_link(self, code: str, input_name: str, cache_dir: Path, **options) -> Path:
        c_path = cache_dir / f"{input_name}.c"
        exe_path = cache_dir / input_name
        self.set_imported_sources([Path(path) for path in options.get("imported_sources", [])])
        link_artifacts = [str(Path(path)) for path in options.get("link_artifacts", [])]
        link_args: list[str] = []
        for capability in sorted(self._c_capabilities):
            link_args.extend(_CAPABILITY_LINK_ARGS.get(capability, []))

        c_path.write_text(code)

        command = ["cc", "-std=c99", "-o", str(exe_path), str(c_path), *link_artifacts, *link_args]
        subprocess.run(command, check=True)
        return exe_path

    def run(self, output_path: PathLike, args: list[str], options: RunOptions | None = None) -> int | None:
        output = Path(output_path)
        if options is None:
            options = RunOptions()
        env = sdl_desktop.apply_run_hook(
            input_file=options.input_file,
            output_path=output,
            link_artifacts=options.link_artifacts,
            env=options.env,
        )
        result = subprocess.run([str(output), *args], env=env)
        return result.returncode

    def get_compile_message(self, output_path: Path, **options) -> str:
        return f"Compiled: {output_path}"
