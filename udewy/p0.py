"""
Parser and multi-backend code generator for udewy.
"""

from __future__ import annotations

from os import PathLike
from pathlib import Path
import sys

from . import t0
from .backend.common import (
    Backend,
    DataRef,
    DataRefValue,
    FnDataValue,
    FnRef,
    GlobalRef,
    IntDataValue,
    LocalRef,
)


def process_imports(source: str, source_path: PathLike, imported: set[Path] | None = None) -> str:
    """
    Process import statements, recursively including imported files.
    Returns the combined source with all imports prepended.
    """
    source_path = Path(source_path).resolve()

    if imported is None:
        imported = set()

    if source_path in imported:
        return ""
    imported.add(source_path)

    source_dir = source_path.parent
    result_parts: list[str] = []
    remaining = source

    i = 0
    n = len(remaining)

    while i < n:
        while i < n and remaining[i] in " \t\r\n":
            i += 1
        if i >= n:
            break

        if remaining[i] == "#":
            while i < n and remaining[i] != "\n":
                i += 1
            continue

        if remaining[i:i + 6] == "import":
            start = i
            i += 6

            while i < n and remaining[i] in " \t":
                i += 1

            if i < n and remaining[i] == "p" and i + 1 < n and remaining[i + 1] == '"':
                i += 2
                path_start = i

                while i < n and remaining[i] != '"':
                    if remaining[i] == "\\":
                        i += 1
                    i += 1

                if i >= n:
                    raise SyntaxError(f"Unterminated path string in import at position {start}")

                import_path_str = remaining[path_start:i]
                i += 1

                import_path = (source_dir / import_path_str).resolve()
                if not import_path.exists():
                    raise FileNotFoundError(f"Import file not found: {import_path}")

                import_content = import_path.read_text()
                processed_import = process_imports(import_content, import_path, imported)
                if processed_import:
                    result_parts.append(processed_import)

                remaining = remaining[:start] + remaining[i:]
                n = len(remaining)
                i = start
            else:
                i += 1
        else:
            while i < n and remaining[i] not in " \t\r\n":
                if remaining[i] == '"':
                    i += 1
                    while i < n and remaining[i] != '"':
                        if remaining[i] == "\\":
                            i += 1
                        i += 1
                    if i < n:
                        i += 1
                elif remaining[i] == "#":
                    while i < n and remaining[i] != "\n":
                        i += 1
                else:
                    i += 1

    result_parts.append(remaining)
    return "\n".join(result_parts)


type PackedToken = int
type TokenIdx = int
type FnEntry = list
type VarEntry = list
type GlobalEntry = list
type ConstEntry = list


def name_eq(src: str, start1: int, len1: int, start2: int, len2: int) -> bool:
    if len1 != len2:
        return False
    i = 0
    while i < len1:
        if src[start1 + i] != src[start2 + i]:
            return False
        i += 1
    return True


def name_eq_str(src: str, start: int, length: int, target: str) -> bool:
    if length != len(target):
        return False
    i = 0
    while i < length:
        if src[start + i] != target[i]:
            return False
        i += 1
    return True


def get_name(src: str, start: int, length: int) -> str:
    return src[start:start + length]


def escape_code_to_value(c: str) -> int:
    if c == "n":
        return 10
    if c == "\n":
        return -1
    if c == "t":
        return 9
    if c == "r":
        return 13
    if c == "0":
        return 0
    return ord(c)


def process_string_content(raw: str) -> list[int]:
    processed: list[int] = []
    i = 0
    while i < len(raw):
        if raw[i] == "\\" and i + 1 < len(raw):
            value = escape_code_to_value(raw[i + 1])
            if value != -1:
                processed.append(value)
            i += 2
        else:
            processed.append(ord(raw[i]))
            i += 1
    return processed


def fn_lookup(fn_table: list, src: str, name_start: int, name_len: int) -> int:
    i = 0
    while i < len(fn_table):
        entry = fn_table[i]
        if name_eq(src, entry[0], entry[1], name_start, name_len):
            return i
        i += 1
    return -1


def fn_declare(
    fn_table: list,
    backend: Backend,
    name_start: int,
    name_len: int,
    fn_ref: FnRef,
    num_args: int,
    is_defined: bool,
) -> int:
    idx = len(fn_table)
    fn_table.append([name_start, name_len, fn_ref, num_args, is_defined])
    backend.note_function(fn_ref)
    return idx


def var_lookup(scope_stack: list, src: str, name_start: int, name_len: int) -> tuple[int, int]:
    scope_idx = len(scope_stack) - 1
    while scope_idx >= 0:
        scope = scope_stack[scope_idx]
        var_idx = 0
        while var_idx < len(scope):
            entry = scope[var_idx]
            if name_eq(src, entry[0], entry[1], name_start, name_len):
                return (scope_idx, var_idx)
            var_idx += 1
        scope_idx -= 1
    return (-1, -1)


def var_declare(scope_stack: list, name_start: int, name_len: int, local_ref: LocalRef) -> None:
    scope_stack[-1].append([name_start, name_len, local_ref])


def global_lookup(global_table: list, src: str, name_start: int, name_len: int) -> int:
    i = 0
    while i < len(global_table):
        entry = global_table[i]
        if name_eq(src, entry[0], entry[1], name_start, name_len):
            return i
        i += 1
    return -1


def global_declare(global_table: list, name_start: int, name_len: int, ref: GlobalRef) -> int:
    idx = len(global_table)
    global_table.append([name_start, name_len, ref])
    return idx


def const_lookup(const_table: list, src: str, name_start: int, name_len: int) -> tuple[bool, int]:
    i = 0
    while i < len(const_table):
        entry = const_table[i]
        if name_eq(src, entry[0], entry[1], name_start, name_len):
            return (True, entry[2])
        i += 1
    return (False, 0)


def const_declare(const_table: list, name_start: int, name_len: int, value: int) -> int:
    idx = len(const_table)
    const_table.append([name_start, name_len, value])
    return idx


def push_scope(scope_stack: list) -> None:
    scope_stack.append([])


def pop_scope(scope_stack: list) -> None:
    scope_stack.pop()


def tok_kind(toks: list, idx: int) -> int:
    return t0.kindof(toks[idx])


def tok_value(toks: list, idx: int) -> int:
    return toks[idx] >> 64


def tok_loc(toks: list, idx: int) -> int:
    return (toks[idx] >> 16) & 0xFFFF_FFFF_FFFF


def tok_name_start(toks: list, idx: int) -> int:
    return tok_loc(toks, idx)


def tok_name_len(toks: list, idx: int) -> int:
    return tok_value(toks, idx)


def expect(toks: list, idx: int, kind: int, src: str) -> int:
    if idx >= len(toks):
        raise SyntaxError(f"Unexpected end of input, expected {t0.kind_to_str(kind)}")
    if tok_kind(toks, idx) != kind:
        raise SyntaxError(
            f"Expected {t0.kind_to_str(kind)}, got {t0.dump_token(toks[idx], src)} at position {tok_loc(toks, idx)}"
        )
    return idx + 1


PREC_OR = 1
PREC_XOR = 2
PREC_AND = 3
PREC_EQ = 4
PREC_CMP = 5
PREC_SHIFT = 6
PREC_ADD = 7
PREC_MUL = 8
PREC_PIPE = 9


def get_precedence(kind: int) -> int:
    if kind == t0.TK_OR:
        return PREC_OR
    if kind == t0.TK_XOR:
        return PREC_XOR
    if kind == t0.TK_AND:
        return PREC_AND
    if kind == t0.TK_EQ or kind == t0.TK_NOT_EQ:
        return PREC_EQ
    if kind == t0.TK_GT or kind == t0.TK_LT or kind == t0.TK_GT_EQ or kind == t0.TK_LT_EQ:
        return PREC_CMP
    if kind == t0.TK_LEFT_SHIFT or kind == t0.TK_RIGHT_SHIFT:
        return PREC_SHIFT
    if kind == t0.TK_PLUS or kind == t0.TK_MINUS:
        return PREC_ADD
    if kind == t0.TK_MUL or kind == t0.TK_IDIV or kind == t0.TK_MOD:
        return PREC_MUL
    if kind == t0.TK_PIPE:
        return PREC_PIPE
    return 0


def is_binop(kind: int) -> bool:
    return get_precedence(kind) > 0


INTRINSICS = {
    "__syscall0__",
    "__syscall1__",
    "__syscall2__",
    "__syscall3__",
    "__syscall4__",
    "__syscall5__",
    "__syscall6__",
    "__load__",
    "__store__",
    "__load8__",
    "__store8__",
    "__load16__",
    "__store16__",
    "__load32__",
    "__store32__",
}


def is_intrinsic(src: str, name_start: int, name_len: int) -> bool:
    return get_name(src, name_start, name_len) in INTRINSICS


def new_symbol(ctx: dict, prefix: str) -> str:
    symbol = f"{prefix}{ctx['next_label']}"
    ctx["next_label"] += 1
    return symbol


def new_local_ref(ctx: dict, backend: Backend, is_param: bool) -> LocalRef:
    ref = LocalRef(ctx["next_local_slot"])
    ctx["next_local_slot"] += 1
    backend.register_local(ref, is_param)
    return ref


def get_or_create_fn_ref(
    backend: Backend,
    fn_table: list,
    src: str,
    name_start: int,
    name_len: int,
    num_args: int,
    ctx: dict,
) -> FnRef:
    fn_idx = fn_lookup(fn_table, src, name_start, name_len)
    if fn_idx >= 0:
        return fn_table[fn_idx][2]
    fn_ref = FnRef(new_symbol(ctx, "fn"), num_args)
    fn_declare(fn_table, backend, name_start, name_len, fn_ref, num_args, False)
    return fn_ref


def skip_type_annotation(toks: list, idx: int) -> int:
    if idx >= len(toks):
        return idx
    kind = tok_kind(toks, idx)
    if kind == t0.TK_TYPE:
        idx += 1
        if idx < len(toks) and tok_kind(toks, idx) == t0.TK_TYPE_PARAM:
            idx += 1
    elif kind == t0.TK_TYPE_PARAM:
        idx += 1
    return idx


def skip_fn_type_annotation(toks: list, idx: int) -> int:
    if idx >= len(toks):
        return idx
    if tok_kind(toks, idx) == t0.TK_FN_TYPE:
        idx += 1
        if idx < len(toks) and tok_kind(toks, idx) == t0.TK_TYPE_PARAM:
            idx += 1
    return idx


def skip_cast_annotation(toks: list, idx: int) -> int:
    if idx < len(toks) and tok_kind(toks, idx) == t0.TK_TRANSMUTE:
        idx += 1
        if idx < len(toks):
            kind = tok_kind(toks, idx)
            if kind == t0.TK_IDENT:
                idx += 1
                if idx < len(toks) and tok_kind(toks, idx) == t0.TK_TYPE_PARAM:
                    idx += 1
            elif kind == t0.TK_TYPE_PARAM:
                idx += 1
    return idx


def parse_const_string(src: str, start: int, length: int) -> list[int]:
    return process_string_content(src[start + 1:start + length - 1])


def parse_const_array(
    toks: list,
    idx: int,
    src: str,
    backend: Backend,
    fn_table: list,
    const_table: list,
    ctx: dict,
) -> tuple[DataRef, int]:
    idx += 1
    values = []
    while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACKET:
        kind = tok_kind(toks, idx)
        if kind == t0.TK_NUMBER:
            values.append(IntDataValue(tok_value(toks, idx)))
            idx += 1
            continue
        if kind == t0.TK_IDENT:
            name_start = tok_name_start(toks, idx)
            name_len = tok_name_len(toks, idx)
            found, value = const_lookup(const_table, src, name_start, name_len)
            if found:
                values.append(IntDataValue(value))
                idx += 1
                continue
            fn_ref = get_or_create_fn_ref(backend, fn_table, src, name_start, name_len, 0, ctx)
            values.append(FnDataValue(fn_ref))
            idx += 1
            continue
        if kind == t0.TK_STRING:
            values_raw = parse_const_string(src, tok_loc(toks, idx), tok_value(toks, idx))
            values.append(DataRefValue(backend.intern_string(new_symbol(ctx, "str"), values_raw)))
            idx += 1
            continue
        raise SyntaxError(
            f"Array elements must be compile-time constants (numbers, strings, const identifiers, or functions) at {tok_loc(toks, idx)}"
        )
    idx = expect(toks, idx, t0.TK_RIGHT_BRACKET, src)
    return (backend.intern_array(new_symbol(ctx, "arr"), values), idx)


def parse_atom(
    toks: list,
    idx: int,
    src: str,
    backend: Backend,
    fn_table: list,
    scope_stack: list,
    global_table: list,
    const_table: list,
    ctx: dict,
) -> int:
    kind = tok_kind(toks, idx)

    if kind == t0.TK_NUMBER:
        backend.push_const_i64(tok_value(toks, idx))
        return idx + 1

    if kind == t0.TK_VOID:
        backend.push_void()
        return idx + 1

    if kind == t0.TK_STRING:
        values = parse_const_string(src, tok_loc(toks, idx), tok_value(toks, idx))
        backend.push_data_ref(backend.intern_string(new_symbol(ctx, "str"), values))
        return idx + 1

    if kind == t0.TK_IDENT:
        name_start = tok_name_start(toks, idx)
        name_len = tok_name_len(toks, idx)
        scope_idx, var_idx = var_lookup(scope_stack, src, name_start, name_len)
        if scope_idx >= 0:
            backend.push_local(scope_stack[scope_idx][var_idx][2])
            return idx + 1
        glob_idx = global_lookup(global_table, src, name_start, name_len)
        if glob_idx >= 0:
            backend.push_global(global_table[glob_idx][2])
            return idx + 1
        backend.push_fn_ref(get_or_create_fn_ref(backend, fn_table, src, name_start, name_len, 0, ctx))
        return idx + 1

    if kind == t0.TK_IDENT_CALL:
        name_start = tok_name_start(toks, idx)
        name_len = tok_name_len(toks, idx)
        idx += 1
        arg_count = 0
        while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_PAREN:
            idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
            arg_count += 1
        idx = expect(toks, idx, t0.TK_RIGHT_PAREN, src)
        name = get_name(src, name_start, name_len)
        if is_intrinsic(src, name_start, name_len):
            backend.call_intrinsic(name, arg_count)
        else:
            backend.call_direct(
                get_or_create_fn_ref(backend, fn_table, src, name_start, name_len, arg_count, ctx),
                arg_count,
            )
        return idx

    if kind == t0.TK_LEFT_PAREN:
        idx += 1
        idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
        return expect(toks, idx, t0.TK_RIGHT_PAREN, src)

    if kind == t0.TK_LEFT_BRACKET:
        data_ref, idx = parse_const_array(toks, idx, src, backend, fn_table, const_table, ctx)
        backend.push_data_ref(data_ref)
        return idx

    raise SyntaxError(f"Unexpected token in expression: {t0.dump_token(toks[idx], src)} at {tok_loc(toks, idx)}")


def parse_prefix(
    toks: list,
    idx: int,
    src: str,
    backend: Backend,
    fn_table: list,
    scope_stack: list,
    global_table: list,
    const_table: list,
    ctx: dict,
) -> int:
    kind = tok_kind(toks, idx)
    if kind == t0.TK_NOT:
        idx += 1
        idx = parse_prefix(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
        backend.unary_not()
        return idx
    if kind == t0.TK_MINUS:
        idx += 1
        if tok_kind(toks, idx) == t0.TK_NUMBER:
            backend.push_const_i64(-tok_value(toks, idx))
            return idx + 1
        idx = parse_prefix(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
        backend.unary_neg()
        return idx
    return parse_atom(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)


def emit_binop(backend: Backend, kind: int) -> None:
    if kind == t0.TK_PLUS:
        backend.binary_add()
    elif kind == t0.TK_MINUS:
        backend.binary_sub()
    elif kind == t0.TK_MUL:
        backend.binary_mul()
    elif kind == t0.TK_IDIV:
        backend.binary_idiv()
    elif kind == t0.TK_MOD:
        backend.binary_mod()
    elif kind == t0.TK_LEFT_SHIFT:
        backend.binary_shl()
    elif kind == t0.TK_RIGHT_SHIFT:
        backend.binary_shr()
    elif kind == t0.TK_AND:
        backend.binary_and()
    elif kind == t0.TK_OR:
        backend.binary_or()
    elif kind == t0.TK_XOR:
        backend.binary_xor()
    elif kind == t0.TK_EQ:
        backend.binary_eq()
    elif kind == t0.TK_NOT_EQ:
        backend.binary_ne()
    elif kind == t0.TK_GT:
        backend.binary_gt()
    elif kind == t0.TK_LT:
        backend.binary_lt()
    elif kind == t0.TK_GT_EQ:
        backend.binary_ge()
    elif kind == t0.TK_LT_EQ:
        backend.binary_le()
    else:
        raise SyntaxError(f"Unsupported operator: {kind}")


def parse_expr(
    toks: list,
    idx: int,
    src: str,
    backend: Backend,
    fn_table: list,
    scope_stack: list,
    global_table: list,
    const_table: list,
    ctx: dict,
    min_prec: int,
) -> int:
    idx = parse_prefix(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
    idx = skip_cast_annotation(toks, idx)

    while idx < len(toks):
        kind = tok_kind(toks, idx)
        if kind == t0.TK_EXPR_CALL:
            idx += 1
            arg_count = 0
            while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_PAREN:
                idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
                arg_count += 1
            idx = expect(toks, idx, t0.TK_RIGHT_PAREN, src)
            backend.call_indirect(arg_count)
            continue
        if not is_binop(kind):
            break
        prec = get_precedence(kind)
        if prec > min_prec and min_prec > 0:
            raise SyntaxError(f"Operator precedence violation: use parentheses to clarify at position {tok_loc(toks, idx)}")
        idx += 1
        if kind == t0.TK_PIPE:
            idx = parse_prefix(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
            idx = skip_cast_annotation(toks, idx)
            backend.call_pipe()
        else:
            idx = parse_prefix(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
            idx = skip_cast_annotation(toks, idx)
            emit_binop(backend, kind)
        min_prec = prec
    return idx


def parse_var_decl(
    toks: list,
    idx: int,
    src: str,
    backend: Backend,
    fn_table: list,
    scope_stack: list,
    global_table: list,
    const_table: list,
    ctx: dict,
) -> int:
    idx += 1
    if tok_kind(toks, idx) != t0.TK_IDENT:
        raise SyntaxError(f"Expected identifier after let, got {t0.dump_token(toks[idx], src)}")
    name_start = tok_name_start(toks, idx)
    name_len = tok_name_len(toks, idx)
    idx += 1
    idx = skip_type_annotation(toks, idx)
    if idx >= len(toks) or tok_kind(toks, idx) != t0.TK_ASSIGN:
        raise SyntaxError(f"Expected '=' in variable declaration at {tok_loc(toks, idx)}")
    idx += 1
    idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
    local_ref = new_local_ref(ctx, backend, False)
    var_declare(scope_stack, name_start, name_len, local_ref)
    backend.store_local(local_ref)
    return idx


def parse_fn_decl(
    toks: list,
    idx: int,
    src: str,
    backend: Backend,
    fn_table: list,
    scope_stack: list,
    global_table: list,
    const_table: list,
    ctx: dict,
) -> int:
    idx += 1
    name_start = tok_name_start(toks, idx)
    name_len = tok_name_len(toks, idx)
    idx += 1
    idx = expect(toks, idx, t0.TK_ASSIGN, src)
    idx = expect(toks, idx, t0.TK_LEFT_PAREN, src)

    saved_local_slot = ctx["next_local_slot"]
    ctx["next_local_slot"] = 0
    params: list[tuple[int, int, LocalRef]] = []
    while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_PAREN:
        if tok_kind(toks, idx) != t0.TK_IDENT:
            raise SyntaxError(f"Expected parameter name, got {t0.dump_token(toks[idx], src)}")
        param_start = tok_name_start(toks, idx)
        param_len = tok_name_len(toks, idx)
        idx += 1
        idx = skip_type_annotation(toks, idx)
        local_ref = new_local_ref(ctx, backend, True)
        params.append((param_start, param_len, local_ref))
    idx = expect(toks, idx, t0.TK_RIGHT_PAREN, src)
    idx = skip_fn_type_annotation(toks, idx)
    idx = expect(toks, idx, t0.TK_FN_ARROW, src)
    idx = expect(toks, idx, t0.TK_LEFT_BRACE, src)

    fn_idx = fn_lookup(fn_table, src, name_start, name_len)
    if fn_idx >= 0:
        entry = fn_table[fn_idx]
        entry[3] = len(params)
        entry[4] = True
        fn_ref = entry[2]
    else:
        fn_ref = FnRef(new_symbol(ctx, "fn"), len(params))
        fn_declare(fn_table, backend, name_start, name_len, fn_ref, len(params), True)

    fn_name = get_name(src, name_start, name_len)
    backend.begin_function(fn_ref, len(params), fn_name == "main")
    push_scope(scope_stack)
    for param_start, param_len, local_ref in params:
        backend.register_local(local_ref, True)
        var_declare(scope_stack, param_start, param_len, local_ref)

    saved_loop_stack = ctx["loop_stack"]
    ctx["loop_stack"] = []

    while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACE:
        idx = parse_statement(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)

    idx = expect(toks, idx, t0.TK_RIGHT_BRACE, src)
    backend.end_function(fn_ref)

    pop_scope(scope_stack)
    ctx["loop_stack"] = saved_loop_stack
    ctx["next_local_slot"] = saved_local_slot
    return idx


def parse_if_stmnt(
    toks: list,
    idx: int,
    src: str,
    backend: Backend,
    fn_table: list,
    scope_stack: list,
    global_table: list,
    const_table: list,
    ctx: dict,
) -> int:
    idx += 1
    idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
    state = backend.begin_if(new_symbol(ctx, "if"))
    backend.if_condition(state)

    idx = expect(toks, idx, t0.TK_LEFT_BRACE, src)
    push_scope(scope_stack)
    while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACE:
        idx = parse_statement(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
    idx = expect(toks, idx, t0.TK_RIGHT_BRACE, src)
    pop_scope(scope_stack)

    if idx < len(toks) and tok_kind(toks, idx) == t0.TK_ELSE:
        backend.begin_else(state)
        idx += 1
        if idx < len(toks) and tok_kind(toks, idx) == t0.TK_IF:
            idx = parse_if_stmnt(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
        else:
            idx = expect(toks, idx, t0.TK_LEFT_BRACE, src)
            push_scope(scope_stack)
            while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACE:
                idx = parse_statement(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
            idx = expect(toks, idx, t0.TK_RIGHT_BRACE, src)
            pop_scope(scope_stack)

    backend.end_if(state)
    return idx


def parse_loop_stmnt(
    toks: list,
    idx: int,
    src: str,
    backend: Backend,
    fn_table: list,
    scope_stack: list,
    global_table: list,
    const_table: list,
    ctx: dict,
) -> int:
    idx += 1
    state = backend.begin_loop(new_symbol(ctx, "loop"))
    ctx["loop_stack"].append(state)
    idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
    backend.loop_condition(state)
    idx = expect(toks, idx, t0.TK_LEFT_BRACE, src)
    push_scope(scope_stack)
    while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACE:
        idx = parse_statement(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
    idx = expect(toks, idx, t0.TK_RIGHT_BRACE, src)
    pop_scope(scope_stack)
    ctx["loop_stack"].pop()
    backend.end_loop(state)
    return idx


def parse_return_stmnt(
    toks: list,
    idx: int,
    src: str,
    backend: Backend,
    fn_table: list,
    scope_stack: list,
    global_table: list,
    const_table: list,
    ctx: dict,
) -> int:
    idx += 1
    idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
    backend.emit_return()
    return idx


def parse_break_stmnt(
    toks: list,
    idx: int,
    src: str,
    backend: Backend,
    fn_table: list,
    scope_stack: list,
    global_table: list,
    const_table: list,
    ctx: dict,
) -> int:
    _ = (src, fn_table, scope_stack, global_table, const_table)
    if not ctx["loop_stack"]:
        raise SyntaxError(f"break outside of loop at {tok_loc(toks, idx)}")
    backend.emit_break(ctx["loop_stack"][-1])
    return idx + 1


def parse_continue_stmnt(
    toks: list,
    idx: int,
    src: str,
    backend: Backend,
    fn_table: list,
    scope_stack: list,
    global_table: list,
    const_table: list,
    ctx: dict,
) -> int:
    _ = (src, fn_table, scope_stack, global_table, const_table)
    if not ctx["loop_stack"]:
        raise SyntaxError(f"continue outside of loop at {tok_loc(toks, idx)}")
    backend.emit_continue(ctx["loop_stack"][-1])
    return idx + 1


def parse_assign_or_expr(
    toks: list,
    idx: int,
    src: str,
    backend: Backend,
    fn_table: list,
    scope_stack: list,
    global_table: list,
    const_table: list,
    ctx: dict,
) -> int:
    if tok_kind(toks, idx) == t0.TK_IDENT and idx + 1 < len(toks):
        next_kind = tok_kind(toks, idx + 1)
        if next_kind == t0.TK_ASSIGN:
            name_start = tok_name_start(toks, idx)
            name_len = tok_name_len(toks, idx)
            idx += 2
            idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
            scope_idx, var_idx = var_lookup(scope_stack, src, name_start, name_len)
            if scope_idx >= 0:
                backend.store_local(scope_stack[scope_idx][var_idx][2])
            else:
                glob_idx = global_lookup(global_table, src, name_start, name_len)
                if glob_idx < 0:
                    raise SyntaxError(f"Undefined variable for assignment at {tok_loc(toks, idx)}")
                backend.store_global(global_table[glob_idx][2])
            return idx
        if next_kind == t0.TK_UPDATE_ASSIGN:
            name_start = tok_name_start(toks, idx)
            name_len = tok_name_len(toks, idx)
            op_kind = tok_value(toks, idx + 1)
            idx += 2
            scope_idx, var_idx = var_lookup(scope_stack, src, name_start, name_len)
            if scope_idx >= 0:
                local_ref = scope_stack[scope_idx][var_idx][2]
                backend.push_local(local_ref)
                idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
                emit_binop(backend, op_kind)
                backend.store_local(local_ref)
            else:
                glob_idx = global_lookup(global_table, src, name_start, name_len)
                if glob_idx < 0:
                    raise SyntaxError(f"Undefined variable for assignment at {tok_loc(toks, idx)}")
                global_ref = global_table[glob_idx][2]
                backend.push_global(global_ref)
                idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
                emit_binop(backend, op_kind)
                backend.store_global(global_ref)
            return idx
    idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
    backend.emit_expr_discard()
    return idx


def parse_statement(
    toks: list,
    idx: int,
    src: str,
    backend: Backend,
    fn_table: list,
    scope_stack: list,
    global_table: list,
    const_table: list,
    ctx: dict,
) -> int:
    kind = tok_kind(toks, idx)
    if kind == t0.TK_LET:
        if idx + 3 < len(toks) and tok_kind(toks, idx + 2) == t0.TK_ASSIGN and tok_kind(toks, idx + 3) == t0.TK_LEFT_PAREN:
            return parse_fn_decl(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
        return parse_var_decl(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
    if kind == t0.TK_IF:
        return parse_if_stmnt(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
    if kind == t0.TK_LOOP:
        return parse_loop_stmnt(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
    if kind == t0.TK_RETURN:
        return parse_return_stmnt(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
    if kind == t0.TK_BREAK:
        return parse_break_stmnt(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
    if kind == t0.TK_CONTINUE:
        return parse_continue_stmnt(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
    return parse_assign_or_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)


def parse_program(
    toks: list,
    src: str,
    backend: Backend,
    fn_table: list,
    scope_stack: list,
    global_table: list,
    const_table: list,
    ctx: dict,
) -> None:
    idx = 0
    while idx < len(toks):
        kind = tok_kind(toks, idx)
        if kind != t0.TK_LET:
            raise SyntaxError(f"Only function and variable declarations allowed at top level, got {t0.dump_token(toks[idx], src)}")
        if idx + 3 < len(toks) and tok_kind(toks, idx + 2) == t0.TK_ASSIGN and tok_kind(toks, idx + 3) == t0.TK_LEFT_PAREN:
            idx = parse_fn_decl(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
            continue
        idx += 1
        name_start = tok_name_start(toks, idx)
        name_len = tok_name_len(toks, idx)
        idx += 1
        idx = skip_type_annotation(toks, idx)
        idx = expect(toks, idx, t0.TK_ASSIGN, src)
        global_ref = GlobalRef(new_symbol(ctx, "global"))
        global_declare(global_table, name_start, name_len, global_ref)
        if tok_kind(toks, idx) == t0.TK_NUMBER:
            value = tok_value(toks, idx)
            const_declare(const_table, name_start, name_len, value)
            backend.define_global_int(global_ref, value)
            idx += 1
            continue
        if tok_kind(toks, idx) == t0.TK_STRING:
            values = parse_const_string(src, tok_loc(toks, idx), tok_value(toks, idx))
            backend.define_global_data(global_ref, backend.intern_string(new_symbol(ctx, "str"), values))
            idx += 1
            continue
        if tok_kind(toks, idx) == t0.TK_LEFT_BRACKET:
            data_ref, idx = parse_const_array(toks, idx, src, backend, fn_table, const_table, ctx)
            backend.define_global_data(global_ref, data_ref)
            continue
        raise SyntaxError(f"Global variables must have constant initializers at {tok_loc(toks, idx)}")


def parse(toks: list, src: str, backend: Backend) -> str:
    backend.begin_module()
    fn_table: list = []
    global_table: list = []
    const_table: list = []
    scope_stack: list = [[]]
    ctx = {
        "next_label": 0,
        "next_local_slot": 0,
        "loop_stack": [],
    }
    parse_program(toks, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
    i = 0
    while i < len(fn_table):
        entry = fn_table[i]
        if not entry[4]:
            raise SyntaxError(f"Undefined function: {get_name(src, entry[0], entry[1])}")
        i += 1
    return backend.finish_module()


def make_backend(name: str) -> Backend:
    if name == "x86_64":
        from .backend.x86_64 import X86_64Backend

        return X86_64Backend()
    if name == "wasm32":
        from .backend.wasm import WasmBackend

        return WasmBackend()
    if name == "riscv":
        from .backend.riscv import RiscvBackend

        return RiscvBackend()
    if name == "arm":
        from .backend.arm import ArmBackend

        return ArmBackend()
    raise ValueError(f"Unknown backend: {name}")


def parse_cli(argv: list[str]) -> tuple[str, bool, int]:
    backend = "x86_64"
    compile_only = False
    arg_idx = 1
    while arg_idx < len(argv):
        arg = argv[arg_idx]
        if arg == "-c":
            compile_only = True
            arg_idx += 1
            continue
        if arg == "--backend":
            if arg_idx + 1 >= len(argv):
                raise SystemExit("Error: --backend requires a value")
            backend = argv[arg_idx + 1]
            arg_idx += 2
            continue
        if arg.startswith("--backend="):
            backend = arg.split("=", 1)[1]
            arg_idx += 1
            continue
        break
    return backend, compile_only, arg_idx


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m udewy.p0 [--backend BACKEND] [-c] <file.udewy> [args...]")
        print("  --backend BACKEND    one of: x86_64, wasm32, riscv, arm")
        print("  -c                   compile only, don't run")
        sys.exit(1)

    backend_name, compile_only, arg_idx = parse_cli(sys.argv)
    if arg_idx >= len(sys.argv):
        print("Error: No input file specified")
        sys.exit(1)

    input_file = Path(sys.argv[arg_idx])
    script_args = sys.argv[arg_idx + 1:]
    raw_src = input_file.read_text()
    src = process_imports(raw_src, input_file)
    toks = t0.tokenize(src)
    backend = make_backend(backend_name)
    module_text = parse(toks, src, backend)
    cache_dir = Path("__dewycache__")
    build_result = backend.build(module_text, input_file, cache_dir)

    if compile_only:
        print(f"Compiled: {build_result.artifact_path}")
        for extra_path in build_result.extra_paths:
            print(f"Generated: {extra_path}")
        sys.exit(0)

    sys.exit(backend.run(build_result, script_args, Path.cwd()))
