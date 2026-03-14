"""
Parser and code generator for udewy.

The frontend stays single-pass and emits directly through the backend protocol,
but it uses ordinary Python data structures for symbol tracking.
"""

from dataclasses import dataclass
from os import PathLike
from pathlib import Path

from . import t0
from .backend.x86_64 import X86_64Backend
from .backend.wasm import Wasm32Backend
from .backend.riscv import RiscvBackend
from .backend.arm import ArmBackend
from .backend.common import Backend


# ============================================================================
# Import preprocessing
# ============================================================================

def process_imports(source: str, source_path: PathLike, imported: set[Path] | None = None) -> str:
    """
    Process leading import directives, recursively including imported files.
    Returns the combined source with imported content prepended.
    """
    source_path = Path(source_path).resolve()
    
    if imported is None:
        imported = set()
    
    if source_path in imported:
        return ""
    imported.add(source_path)
    
    source_dir = source_path.parent
    result_parts: list[str] = []
    body_parts: list[str] = []

    i = 0
    body_cursor = 0
    n = len(source)

    # TODO: pull / combine pieces of this from t0
    def skip_trivia(idx: int) -> int:
        while idx < n:
            if source[idx] in ' \t\r\n':
                idx = idx + 1
                continue
            if source[idx] == '#':
                while idx < n and source[idx] != '\n':
                    idx = idx + 1
                continue
            break
        return idx

    # TODO: pull this from t0
    def is_ident_char(c: str) -> bool:
        return c == '_' or ('a' <= c <= 'z') or ('A' <= c <= 'Z') or ('0' <= c <= '9')

    while True:
        i = skip_trivia(i)
        if i >= n:
            break

        if source[i:i + 6] != 'import':
            break

        end_kw = i + 6
        if end_kw < n and is_ident_char(source[end_kw]):
            break

        body_parts.append(source[body_cursor:i])

        i = end_kw
        while i < n and source[i] in ' \t':
            i = i + 1

        if i >= n or source[i] != 'p' or i + 1 >= n or source[i + 1] != '"':
            raise SyntaxError(f"Expected path string after import at position {end_kw}")

        i = i + 2
        path_start = i

        while i < n and source[i] != '"':
            if source[i] == '\\':
                i = i + 1
            i = i + 1

        if i >= n:
            raise SyntaxError(f"Unterminated path string in import at position {path_start - 2}")

        import_path_str = source[path_start:i]
        i = i + 1

        while i < n and source[i] in ' \t':
            i = i + 1

        if i < n and source[i] == '#':
            while i < n and source[i] != '\n':
                i = i + 1

        if i < n and source[i] not in '\r\n':
            raise SyntaxError(f"Unexpected trailing content after import at position {i}")

        while i < n and source[i] in '\r\n':
            i = i + 1

        import_path = (source_dir / import_path_str).resolve()

        if not import_path.exists():
            raise FileNotFoundError(f"Import file not found: {import_path}")

        import_content = import_path.read_text()
        processed_import = process_imports(import_content, import_path, imported)
        if processed_import:
            result_parts.append(processed_import)

        body_cursor = i

    body_parts.append(source[body_cursor:])
    result_parts.append(''.join(body_parts))
    
    return '\n'.join(result_parts)


# ============================================================================
# Frontend state
# ============================================================================

TokenIdx = int


@dataclass
class FunctionEntry:
    label_id: int
    num_args: int | None
    is_defined: bool


@dataclass
class ParseContext:
    builtin_consts: dict[str, int]
    loop_depth: int = 0


FunctionTable = dict[str, FunctionEntry]
GlobalTable = dict[str, int]
ConstTable = dict[str, int]
Scope = dict[str, int]
ScopeStack = list[Scope]

@dataclass
class ParseState:
    src: str
    backend: Backend
    fn_table: FunctionTable
    global_table: GlobalTable
    const_table: ConstTable
    scope_stack: ScopeStack
    ctx: ParseContext

# ============================================================================
# Helper functions
# ============================================================================


def get_name(src: str, start: int, length: int) -> str:
    return src[start:start + length]


def get_token_name(toks: list[t0.Token], idx: int, src: str) -> str:
    return get_name(src, tok_name_start(toks, idx), tok_name_len(toks, idx))


def escape_code_to_value(c: str) -> int:
    if c == 'n': return 10
    if c == '\n': return -1
    if c == 't': return 9
    if c == 'r': return 13
    if c == '0': return 0
    return ord(c)


def decode_string_literal(src: str, start: int, length: int) -> bytes:
    str_content = src[start + 1 : start + length - 1]
    processed: list[int] = []
    i = 0
    while i < len(str_content):
        if str_content[i] == '\\' and i + 1 < len(str_content):
            val = escape_code_to_value(str_content[i + 1])
            if val != -1:
                processed.append(val)
            i = i + 2
            continue
        processed.append(ord(str_content[i]))
        i = i + 1
    return bytes(processed)


# ============================================================================
# Symbol table operations
# ============================================================================

def fn_lookup(fn_table: FunctionTable, name: str) -> FunctionEntry | None:
    return fn_table.get(name)


def fn_declare(
    fn_table: FunctionTable,
    name: str,
    label_id: int,
    num_args: int | None,
    is_defined: bool,
) -> FunctionEntry:
    entry = FunctionEntry(label_id=label_id, num_args=num_args, is_defined=is_defined)
    fn_table[name] = entry
    return entry


def var_lookup(scope_stack: ScopeStack, name: str) -> int | None:
    for scope in reversed(scope_stack):
        slot = scope.get(name)
        if slot is not None:
            return slot
    return None


def var_declare(scope_stack: ScopeStack, name: str, slot: int) -> None:
    scope_stack[-1][name] = slot


def global_lookup(global_table: GlobalTable, name: str) -> int | None:
    return global_table.get(name)


def global_declare(global_table: GlobalTable, name: str, label_id: int) -> int:
    global_table[name] = label_id
    return label_id


def const_lookup(const_table: ConstTable, name: str, builtin_consts: dict[str, int] | None = None) -> int | None:
    value = const_table.get(name)
    if value is not None:
        return value
    if builtin_consts is not None:
        return builtin_consts.get(name)
    return None


def const_declare(const_table: ConstTable, name: str, value: int) -> int:
    const_table[name] = value
    return value


def push_scope(scope_stack: ScopeStack) -> None:
    scope_stack.append({})


def pop_scope(scope_stack: ScopeStack) -> None:
    scope_stack.pop()


def tok_name_start(toks: list[t0.Token], idx: int) -> int:
    return toks[idx].location


def tok_name_len(toks: list[t0.Token], idx: int) -> int:
    value = toks[idx].value
    assert isinstance(value, int)
    return value


def expect(toks: list[t0.Token], idx: int, kind: t0.Kind, state: ParseState) -> int:
    if idx >= len(toks):
        raise SyntaxError(f"Unexpected end of input, expected {kind.name}")
    if toks[idx].kind != kind:
        raise SyntaxError(f"Expected {kind.name}, got {t0.dump_token(toks[idx], state.src)} at position {toks[idx].location}")
    return idx + 1


def looks_like_fn_decl(toks: list[t0.Token], idx: int) -> bool:
    if idx + 3 >= len(toks):
        return False
    if toks[idx + 2].kind != t0.Kind.TK_ASSIGN or toks[idx + 3].kind != t0.Kind.TK_LEFT_PAREN:
        return False

    depth = 1
    scan = idx + 4
    while scan < len(toks) and depth > 0:
        kind = toks[scan].kind
        if kind == t0.Kind.TK_LEFT_PAREN:
            depth = depth + 1
        elif kind == t0.Kind.TK_RIGHT_PAREN:
            depth = depth - 1
        scan = scan + 1

    if depth != 0 or scan >= len(toks):
        return False
    if toks[scan].kind != t0.Kind.TK_FN_TYPE:
        return False

    scan = scan + 1
    if scan < len(toks) and toks[scan].kind == t0.Kind.TK_TYPE_PARAM:
        scan = scan + 1
    return scan < len(toks) and toks[scan].kind == t0.Kind.TK_FN_ARROW


def require_type_annotation(toks: list[t0.Token], idx: int, subject: str, state: ParseState) -> int:
    if idx >= len(toks):
        raise SyntaxError(f"Expected type annotation for {subject} before end of input")
    kind = toks[idx].kind
    if kind == t0.Kind.TK_TYPE:
        idx = idx + 1
        if idx < len(toks) and toks[idx].kind == t0.Kind.TK_TYPE_PARAM:
            idx = idx + 1
        return idx
    if kind == t0.Kind.TK_TYPE_PARAM:
        return idx + 1
    raise SyntaxError(f"Expected type annotation for {subject} at position {toks[idx].location}")


def require_fn_type_annotation(toks: list[t0.Token], idx: int, fn_name: str, state: ParseState) -> int:
    if idx >= len(toks):
        raise SyntaxError(f"Expected return type annotation for function {fn_name!r} before end of input")
    if toks[idx].kind != t0.Kind.TK_FN_TYPE:
        raise SyntaxError(f"Expected return type annotation for function {fn_name!r} at position {toks[idx].location}")
    idx = idx + 1
    if idx < len(toks) and toks[idx].kind == t0.Kind.TK_TYPE_PARAM:
        idx = idx + 1
    return idx


def validate_call_arity(backend: Backend, arg_count: int, loc: int) -> None:
    max_args = backend.max_call_args()
    if max_args is not None and arg_count > max_args:
        raise SyntaxError(
            f"Calls with {arg_count} arguments exceed the backend limit of {max_args} at position {loc}"
        )


def note_function_reference(
    backend: Backend,
    fn_table: FunctionTable,
    name: str,
    num_args: int | None,
    loc: int,
) -> FunctionEntry:
    entry = fn_lookup(fn_table, name)
    if entry is None:
        label_id = backend.declare_function(0, num_args or 0)
        return fn_declare(fn_table, name, label_id, num_args, False)

    if num_args is not None:
        if entry.num_args is None:
            entry.num_args = num_args
        elif entry.num_args != num_args:
            raise SyntaxError(
                f"Function {name!r} used with conflicting arities {entry.num_args} and {num_args} at position {loc}"
            )

    return entry


# ============================================================================
# Operator precedence
# ============================================================================

PREC_OR = 1
PREC_XOR = 2
PREC_AND = 3
PREC_CMP = 4
PREC_SHIFT = 5
PREC_ADD = 6
PREC_MUL = 7
PREC_PIPE = 8


def get_precedence(kind: t0.Kind) -> int:
    if kind == t0.Kind.TK_OR:
        return PREC_OR
    if kind == t0.Kind.TK_XOR:
        return PREC_XOR
    if kind == t0.Kind.TK_AND:
        return PREC_AND
    if kind == t0.Kind.TK_EQ or kind == t0.Kind.TK_NOT_EQ:
        return PREC_CMP
    if kind == t0.Kind.TK_GT or kind == t0.Kind.TK_LT or kind == t0.Kind.TK_GT_EQ or kind == t0.Kind.TK_LT_EQ:
        return PREC_CMP
    if kind == t0.Kind.TK_LEFT_SHIFT or kind == t0.Kind.TK_RIGHT_SHIFT:
        return PREC_SHIFT
    if kind == t0.Kind.TK_PLUS or kind == t0.Kind.TK_MINUS:
        return PREC_ADD
    if kind == t0.Kind.TK_MUL or kind == t0.Kind.TK_IDIV or kind == t0.Kind.TK_MOD:
        return PREC_MUL
    if kind == t0.Kind.TK_PIPE:
        return PREC_PIPE
    return 0


def is_binop(kind: int) -> bool:
    return get_precedence(kind) > 0


# ============================================================================
# Intrinsic detection (delegated to backend)
# ============================================================================

def is_intrinsic(backend, name: str) -> bool:
    """Check if the given name is an intrinsic supported by the backend."""
    return backend.is_intrinsic(name)


def emit_intrinsic(backend, name: str, num_args: int) -> None:
    """Emit intrinsic call via backend."""
    backend.emit_intrinsic(name, num_args)


def parse_static_alloca_size(toks: list[t0.Token], idx: int, state: ParseState) -> tuple[int, int]:
    """Parse the single compile-time size argument to __static_alloca__."""
    if idx >= len(toks):
        raise SyntaxError("__static_alloca__ expects one constant size argument")

    kind = toks[idx].kind
    if kind == t0.Kind.TK_NUMBER:
        size_value = toks[idx].value
        assert isinstance(size_value, int)
        size = size_value
        idx = idx + 1
    elif kind == t0.Kind.TK_IDENT:
        name = get_token_name(toks, idx, state.src)
        size = const_lookup(state.const_table, name, state.ctx.builtin_consts)
        if size is None:
            raise SyntaxError(f"__static_alloca__ size must be a compile-time constant at {toks[idx].location}")
        idx = idx + 1
    else:
        raise SyntaxError(f"__static_alloca__ size must be a compile-time constant at {toks[idx].location}")

    if idx >= len(toks) or toks[idx].kind != t0.Kind.TK_RIGHT_PAREN:
        raise SyntaxError(f"__static_alloca__ expects exactly one constant size argument at {toks[idx].location}")
    if size < 0:
        raise SyntaxError(f"__static_alloca__ size must be non-negative at {toks[idx - 1].location}")

    return size, idx + 1


# ============================================================================
# Expression parsing
# ============================================================================

def parse_atom( toks: list[t0.Token], idx: int, state: ParseState) -> int:
    """Parse an atomic expression, emit via backend. Returns new idx."""
    backend = state.backend
    kind = toks[idx].kind
    
    if kind == t0.Kind.TK_NUMBER:
        value = toks[idx].value
        assert isinstance(value, int)
        val = value
        backend.push_const_i64(val)
        return idx + 1
    
    if kind == t0.Kind.TK_VOID:
        backend.push_void()
        return idx + 1
    
    if kind == t0.Kind.TK_STRING:
        label_id = backend.intern_string(
            decode_string_literal(state.src, toks[idx].location, tok_name_len(toks, idx))
        )
        backend.push_string_ref(label_id)
        return idx + 1
    
    if kind == t0.Kind.TK_IDENT:
        name = get_token_name(toks, idx, state.src)

        slot = var_lookup(state.scope_stack, name)
        if slot is not None:
            backend.load_local(slot)
            return idx + 1

        global_label = global_lookup(state.global_table, name)
        if global_label is not None:
            backend.load_global(global_label)
            return idx + 1

        value = const_lookup(state.const_table, name, state.ctx.builtin_consts)
        if value is not None:
            backend.push_const_i64(value)
            return idx + 1

        entry = fn_lookup(state.fn_table, name)
        if entry is not None:
            backend.push_fn_ref(entry.label_id)
            return idx + 1

        entry = note_function_reference(backend, state.fn_table, name, None, toks[idx].location)
        backend.push_fn_ref(entry.label_id)
        return idx + 1

    if kind == t0.Kind.TK_IDENT_CALL:
        call_loc = toks[idx].location
        name = get_token_name(toks, idx, state.src)
        idx = idx + 1

        if name == "__static_alloca__":
            size, idx = parse_static_alloca_size(toks, idx, state)
            label_id = backend.intern_static(size)
            backend.push_static_ref(label_id)
            return idx

        arg_count = 0
        while idx < len(toks) and toks[idx].kind != t0.Kind.TK_RIGHT_PAREN:
            idx = parse_expr(toks, idx, state, 0)
            backend.save_value()
            arg_count = arg_count + 1

        idx = expect(toks, idx, t0.Kind.TK_RIGHT_PAREN, state)

        if is_intrinsic(backend, name):
            if arg_count > 0:
                backend.restore_value()
            emit_intrinsic(backend, name, arg_count)
        else:
            validate_call_arity(backend, arg_count, call_loc)
            entry = note_function_reference(backend, state.fn_table, name, arg_count, call_loc)
            backend.call_direct(entry.label_id, arg_count)

        return idx

    if kind == t0.Kind.TK_LEFT_PAREN:
        idx = idx + 1
        idx = parse_expr(toks, idx, state, 0)
        idx = expect(toks, idx, t0.Kind.TK_RIGHT_PAREN, state)
        return idx

    if kind == t0.Kind.TK_LEFT_BRACKET:
        idx = idx + 1
        elem_directives: list[int | str] = []

        while idx < len(toks) and toks[idx].kind != t0.Kind.TK_RIGHT_BRACKET:
            elem_kind = toks[idx].kind

            if elem_kind == t0.Kind.TK_NUMBER:
                value = toks[idx].value
                assert isinstance(value, int)
                elem_directives.append(value)
                idx = idx + 1

            elif elem_kind == t0.Kind.TK_IDENT:
                name = get_token_name(toks, idx, state.src)
                value = const_lookup(state.const_table, name, state.ctx.builtin_consts)
                if value is not None:
                    elem_directives.append(value)
                else:
                    entry = note_function_reference(backend, state.fn_table, name, None, toks[idx].location)
                    elem_directives.append(backend.function_ref(entry.label_id))
                idx = idx + 1

            elif elem_kind == t0.Kind.TK_STRING:
                str_label_id = backend.intern_string(
                    decode_string_literal(state.src, toks[idx].location, tok_name_len(toks, idx))
                )
                idx = idx + 1
                elem_directives.append(backend.string_ref(str_label_id))
            
            else:
                raise SyntaxError(f"Array elements must be constants at {toks[idx].location}")
        
        idx = expect(toks, idx, t0.Kind.TK_RIGHT_BRACKET, state)
        
        label_id = backend.intern_array(elem_directives)
        backend.push_array_ref(label_id)
        return idx

    raise SyntaxError(f"Unexpected token: {t0.dump_token(toks[idx], state.src)} at {toks[idx].location}")


def parse_prefix( toks: list[t0.Token], idx: int, state: ParseState) -> int:
    backend = state.backend
    kind = toks[idx].kind

    if kind == t0.Kind.TK_NOT:
        idx = idx + 1
        idx = parse_prefix(toks, idx, state)
        backend.unary_op(t0.Kind.TK_NOT)
        return idx

    if kind == t0.Kind.TK_MINUS:
        idx = idx + 1
        if toks[idx].kind == t0.Kind.TK_NUMBER:
            value = toks[idx].value
            assert isinstance(value, int)
            val = value
            backend.push_const_i64(-val)
            return idx + 1
        idx = parse_prefix(toks, idx, state)
        backend.unary_op(t0.Kind.TK_MINUS)
        return idx

    return parse_atom(toks, idx, state)


def parse_expr(toks: list[t0.Token], idx: int, state: ParseState, min_prec: int) -> int:
    backend = state.backend
    idx = parse_prefix(toks, idx, state)
    idx = skip_cast_annotation(toks, idx)
    
    while idx < len(toks):
        kind = toks[idx].kind
        
        if kind == t0.Kind.TK_EXPR_CALL:
            backend.save_value()
            idx = idx + 1
            
            arg_count = 0
            while idx < len(toks) and toks[idx].kind != t0.Kind.TK_RIGHT_PAREN:
                idx = parse_expr(toks, idx, state, 0)
                backend.save_value()
                arg_count = arg_count + 1
            
            idx = expect(toks, idx, t0.Kind.TK_RIGHT_PAREN, state)
            validate_call_arity(backend, arg_count, toks[idx - 1].location)
            backend.call_indirect(arg_count)
            continue
        
        if not is_binop(kind):
            break
        
        prec = get_precedence(kind)
        
        if prec > min_prec and min_prec > 0:
            raise SyntaxError(f"Operator precedence violation at {toks[idx].location}")
        
        idx = idx + 1
        backend.save_value()
        
        if kind == t0.Kind.TK_PIPE:
            idx = parse_prefix(toks, idx, state)
            idx = skip_cast_annotation(toks, idx)
            backend.pipe_call()
        else:
            idx = parse_prefix(toks, idx, state)
            idx = skip_cast_annotation(toks, idx)
            backend.binary_op(kind)
        
        min_prec = prec
    
    return idx


# ============================================================================
# Statement parsing
# ============================================================================

def skip_type_annotation(toks: list, idx: int) -> int:
    if idx >= len(toks):
        return idx
    kind = toks[idx].kind
    if kind == t0.Kind.TK_TYPE:
        idx = idx + 1
        if idx < len(toks) and toks[idx].kind == t0.Kind.TK_TYPE_PARAM:
            idx = idx + 1
    elif kind == t0.Kind.TK_TYPE_PARAM:
        idx = idx + 1
    return idx


def skip_fn_type_annotation(toks: list, idx: int) -> int:
    if idx >= len(toks):
        return idx
    kind = toks[idx].kind
    if kind == t0.Kind.TK_FN_TYPE:
        idx = idx + 1
        if idx < len(toks) and toks[idx].kind == t0.Kind.TK_TYPE_PARAM:
            idx = idx + 1
    return idx


def skip_cast_annotation(toks: list, idx: int) -> int:
    if idx < len(toks) and toks[idx].kind == t0.Kind.TK_TRANSMUTE:
        idx = idx + 1
        if idx < len(toks):
            kind = toks[idx].kind
            if kind == t0.Kind.TK_IDENT:
                idx = idx + 1
                if idx < len(toks) and toks[idx].kind == t0.Kind.TK_TYPE_PARAM:
                    idx = idx + 1
            elif kind == t0.Kind.TK_TYPE_PARAM:
                idx = idx + 1
    return idx


def parse_var_decl(toks: list[t0.Token], idx: int, state: ParseState) -> int:
    backend = state.backend
    idx = idx + 1
    
    if toks[idx].kind != t0.Kind.TK_IDENT:
        raise SyntaxError("Expected identifier after let")
    
    name = get_token_name(toks, idx, state.src)
    idx = idx + 1
    
    idx = require_type_annotation(toks, idx, f"variable {name!r}", state)
    
    if idx >= len(toks) or toks[idx].kind != t0.Kind.TK_ASSIGN:
        raise SyntaxError(f"Expected '=' at {toks[idx].location}")
    idx = idx + 1
    
    idx = parse_expr(toks, idx, state, 0)
    
    slot = backend.alloc_local()
    var_declare(state.scope_stack, name, slot)
    backend.store_local(slot)
    
    return idx


def parse_fn_decl(toks: list[t0.Token], idx: int, state: ParseState) -> int:
    backend = state.backend
    idx = idx + 1
    
    fn_name = get_token_name(toks, idx, state.src)
    idx = idx + 1
    
    idx = expect(toks, idx, t0.Kind.TK_ASSIGN, state)
    idx = expect(toks, idx, t0.Kind.TK_LEFT_PAREN, state)
    
    params: list[str] = []
    while idx < len(toks) and toks[idx].kind != t0.Kind.TK_RIGHT_PAREN:
        if toks[idx].kind != t0.Kind.TK_IDENT:
            raise SyntaxError(f"Expected parameter name at position {toks[idx].location}")
        param_name = get_token_name(toks, idx, state.src)
        params.append(param_name)
        idx = idx + 1
        idx = require_type_annotation(toks, idx, f"parameter {param_name!r}", state)
    
    idx = expect(toks, idx, t0.Kind.TK_RIGHT_PAREN, state)
    idx = require_fn_type_annotation(toks, idx, fn_name, state)
    idx = expect(toks, idx, t0.Kind.TK_FN_ARROW, state)
    idx = expect(toks, idx, t0.Kind.TK_LEFT_BRACE, state)
    
    entry = fn_lookup(state.fn_table, fn_name)
    if entry is not None:
        if entry.is_defined:
            raise SyntaxError(f"Function {fn_name!r} is already defined at position {toks[idx - 1].location}")
        if entry.num_args is not None and entry.num_args != len(params):
            raise SyntaxError(
                f"Function {fn_name!r} defined with {len(params)} arguments after being used with {entry.num_args} at position {toks[idx - 1].location}"
            )
        entry.num_args = len(params)
        entry.is_defined = True
        label_id = entry.label_id
    else:
        label_id = backend.declare_function(0, len(params))
        fn_declare(state.fn_table, fn_name, label_id, len(params), True)
    
    is_main = fn_name == "main"
    backend.begin_function(label_id, fn_name, len(params), is_main)
    
    push_scope(state.scope_stack)
    
    for i, param_name in enumerate(params):
        slot = backend.alloc_local()
        backend.load_param(i)
        backend.store_local(slot)
        var_declare(state.scope_stack, param_name, slot)
    
    idx, body_returns = parse_block(toks, idx, state)
    
    idx = expect(toks, idx, t0.Kind.TK_RIGHT_BRACE, state)
    if not body_returns:
        raise SyntaxError(f"Function {fn_name!r} must explicitly return before position {toks[idx - 1].location}")
    
    backend.end_function()
    pop_scope(state.scope_stack)
    
    return idx


def parse_if_stmnt(toks: list[t0.Token], idx: int, state: ParseState) -> tuple[int, bool]:
    backend = state.backend
    idx = idx + 1
    
    idx = parse_expr(toks, idx, state, 0)
    backend.begin_if()
    
    idx = expect(toks, idx, t0.Kind.TK_LEFT_BRACE, state)
    push_scope(state.scope_stack)
    idx, all_branches_return = parse_block(toks, idx, state)
    idx = expect(toks, idx, t0.Kind.TK_RIGHT_BRACE, state)
    pop_scope(state.scope_stack)

    nested_if_count = 1
    saw_final_else = False
    
    while idx < len(toks) and toks[idx].kind == t0.Kind.TK_ELSE:
        idx = idx + 1
        
        if idx < len(toks) and toks[idx].kind == t0.Kind.TK_IF:
            backend.begin_else()
            idx = idx + 1
            
            idx = parse_expr(toks, idx, state, 0)
            backend.begin_if()
            nested_if_count = nested_if_count + 1
            
            idx = expect(toks, idx, t0.Kind.TK_LEFT_BRACE, state)
            push_scope(state.scope_stack)
            idx, branch_returns = parse_block(toks, idx, state)
            idx = expect(toks, idx, t0.Kind.TK_RIGHT_BRACE, state)
            pop_scope(state.scope_stack)
            all_branches_return = all_branches_return and branch_returns
        else:
            saw_final_else = True
            backend.begin_else()
            idx = expect(toks, idx, t0.Kind.TK_LEFT_BRACE, state)
            push_scope(state.scope_stack)
            idx, else_returns = parse_block(toks, idx, state)
            idx = expect(toks, idx, t0.Kind.TK_RIGHT_BRACE, state)
            pop_scope(state.scope_stack)
            
            for _ in range(nested_if_count):
                backend.end_if()
            return idx, all_branches_return and else_returns
    
    for _ in range(nested_if_count):
        backend.end_if()
    return idx, all_branches_return and saw_final_else


def parse_loop_stmnt(toks: list[t0.Token], idx: int, state: ParseState) -> int:
    backend = state.backend
    idx = idx + 1
    
    backend.begin_loop()
    
    idx = parse_expr(toks, idx, state, 0)
    backend.begin_loop_body()
    
    idx = expect(toks, idx, t0.Kind.TK_LEFT_BRACE, state)
    push_scope(state.scope_stack)
    state.ctx.loop_depth = state.ctx.loop_depth + 1
    idx, _ = parse_block(toks, idx, state)
    state.ctx.loop_depth = state.ctx.loop_depth - 1
    idx = expect(toks, idx, t0.Kind.TK_RIGHT_BRACE, state)
    pop_scope(state.scope_stack)
    
    backend.end_loop()
    return idx


def parse_return_stmnt(toks: list[t0.Token], idx: int, state: ParseState) -> int:
    backend = state.backend
    idx = idx + 1
    idx = parse_expr(toks, idx, state, 0)
    backend.emit_return()
    return idx


def parse_break_stmnt(toks: list[t0.Token], idx: int, state: ParseState) -> int:
    if state.ctx.loop_depth == 0:
        raise SyntaxError(f"`break` may only appear inside a loop at position {toks[idx].location}")
    idx = idx + 1
    state.backend.emit_break()
    return idx


def parse_continue_stmnt(toks: list[t0.Token], idx: int, state: ParseState) -> int:
    if state.ctx.loop_depth == 0:
        raise SyntaxError(f"`continue` may only appear inside a loop at position {toks[idx].location}")
    idx = idx + 1
    state.backend.emit_continue()
    return idx


def parse_assign_or_expr(toks: list[t0.Token], idx: int, state: ParseState) -> int:
    backend = state.backend
    if toks[idx].kind == t0.Kind.TK_IDENT:
        if idx + 1 < len(toks):
            next_kind = toks[idx + 1].kind
            
            if next_kind == t0.Kind.TK_ASSIGN:
                name = get_token_name(toks, idx, state.src)
                idx = idx + 2
                
                idx = parse_expr(toks, idx, state, 0)

                slot = var_lookup(state.scope_stack, name)
                if slot is not None:
                    backend.store_local(slot)
                else:
                    global_label = global_lookup(state.global_table, name)
                    if global_label is not None:
                        backend.store_global(global_label)
                    else:
                        raise SyntaxError(f"Undefined variable {name!r} at position {toks[idx - 2].location}")
                
                return idx
            
            elif next_kind == t0.Kind.TK_UPDATE_ASSIGN:
                name = get_token_name(toks, idx, state.src)
                op_kind = toks[idx + 1].value
                assert isinstance(op_kind, t0.Kind)
                idx = idx + 2
                
                slot = var_lookup(state.scope_stack, name)
                is_local = slot is not None
                if is_local:
                    backend.load_local(slot)
                else:
                    global_label = global_lookup(state.global_table, name)
                    if global_label is not None:
                        slot = global_label
                        backend.load_global(slot)
                    else:
                        raise SyntaxError(f"Undefined variable {name!r} at position {toks[idx - 2].location}")
                
                backend.save_value()
                idx = parse_expr(toks, idx, state, 0)
                backend.binary_op(op_kind)
                
                if is_local:
                    backend.store_local(slot)
                else:
                    backend.store_global(slot)
                
                return idx
    
    idx = parse_expr(toks, idx, state, 0)
    backend.pop_value()  # Drop unused expression value
    return idx


def parse_statement(toks: list[t0.Token], idx: int, state: ParseState) -> tuple[int, bool]:
    kind = toks[idx].kind
    
    if kind == t0.Kind.TK_LET:
        if looks_like_fn_decl(toks, idx):
            raise SyntaxError(f"Functions may only be declared at top level at position {toks[idx].location}")
        return parse_var_decl(toks, idx, state), False
    
    if kind == t0.Kind.TK_IF:
        return parse_if_stmnt(toks, idx, state)
    
    if kind == t0.Kind.TK_LOOP:
        return parse_loop_stmnt(toks, idx, state), False
    
    if kind == t0.Kind.TK_RETURN:
        return parse_return_stmnt(toks, idx, state), True
    
    if kind == t0.Kind.TK_BREAK:
        return parse_break_stmnt(toks, idx, state), False
    
    if kind == t0.Kind.TK_CONTINUE:
        return parse_continue_stmnt(toks, idx, state), False
    
    return parse_assign_or_expr(toks, idx, state), False


def parse_block(toks: list[t0.Token], idx: int, state: ParseState) -> tuple[int, bool]:
    block_returns = False
    while idx < len(toks) and toks[idx].kind != t0.Kind.TK_RIGHT_BRACE:
        idx, statement_returns = parse_statement(toks, idx, state)
        if statement_returns:
            block_returns = True
    return idx, block_returns


def parse_program(toks: list[t0.Token], state: ParseState) -> None:
    backend = state.backend
    idx = 0
    
    while idx < len(toks):
        kind = toks[idx].kind
        
        if kind == t0.Kind.TK_LET:
            if looks_like_fn_decl(toks, idx):
                idx = parse_fn_decl(toks, idx, state)
                continue
            
            idx = idx + 1
            
            name = get_token_name(toks, idx, state.src)
            idx = idx + 1
            
            idx = require_type_annotation(toks, idx, f"constant {name!r}", state)
            idx = expect(toks, idx, t0.Kind.TK_ASSIGN, state)
            
            if toks[idx].kind == t0.Kind.TK_NUMBER:
                value = toks[idx].value
                assert isinstance(value, int)
                val = value
                idx = idx + 1
                
                const_declare(state.const_table, name, val)
                label_id = backend.define_global(0, val)
                global_declare(state.global_table, name, label_id)
                
            elif toks[idx].kind == t0.Kind.TK_STRING:
                str_label_id = backend.intern_string(
                    decode_string_literal(state.src, toks[idx].location, tok_name_len(toks, idx))
                )
                idx = idx + 1
                label_id = backend.define_global(0, backend.string_ref(str_label_id))
                global_declare(state.global_table, name, label_id)
                
            elif toks[idx].kind == t0.Kind.TK_LEFT_BRACKET:
                idx = idx + 1
                elem_directives: list[int | str] = []
                
                while idx < len(toks) and toks[idx].kind != t0.Kind.TK_RIGHT_BRACKET:
                    elem_kind = toks[idx].kind
                    
                    if elem_kind == t0.Kind.TK_NUMBER:
                        value = toks[idx].value
                        assert isinstance(value, int)
                        elem_directives.append(value)
                        idx = idx + 1
                    
                    elif elem_kind == t0.Kind.TK_IDENT:
                        ident_name = get_token_name(toks, idx, state.src)
                        value = const_lookup(state.const_table, ident_name, state.ctx.builtin_consts)
                        if value is not None:
                            elem_directives.append(value)
                        else:
                            entry = note_function_reference(
                                backend, state.fn_table, ident_name, None, toks[idx].location
                            )
                            elem_directives.append(backend.function_ref(entry.label_id))
                        idx = idx + 1
                    
                    elif elem_kind == t0.Kind.TK_STRING:
                        str_lbl_id = backend.intern_string(
                            decode_string_literal(state.src, toks[idx].location, tok_name_len(toks, idx))
                        )
                        idx = idx + 1
                        elem_directives.append(backend.string_ref(str_lbl_id))
                    
                    else:
                        raise SyntaxError(f"Unsupported element type in global array at {toks[idx].location}")
                
                idx = expect(toks, idx, t0.Kind.TK_RIGHT_BRACKET, state)
                
                arr_label_id = backend.intern_array(elem_directives)
                label_id = backend.define_global(0, backend.array_ref(arr_label_id))
                global_declare(state.global_table, name, label_id)
            elif toks[idx].kind == t0.Kind.TK_IDENT_CALL:
                call_name = get_token_name(toks, idx, state.src)
                if call_name != "__static_alloca__":
                    raise SyntaxError(f"Global variables must have constant initializers at {toks[idx].location}")

                idx = idx + 1
                size, idx = parse_static_alloca_size(toks, idx, state)
                static_label_id = backend.intern_static(size)
                label_id = backend.define_global(0, backend.static_ref(static_label_id))
                global_declare(state.global_table, name, label_id)
            else:
                raise SyntaxError(f"Global variables must have constant initializers at {toks[idx].location}")
        else:
            raise SyntaxError(f"Only declarations allowed at top level, got {t0.dump_token(toks[idx], state.src)}")


# ============================================================================
# Main entry point
# ============================================================================

def parse(toks: list[t0.Token], src: str, target: str = "x86_64") -> tuple[str, Backend]:
    """Parse tokens and generate code for the specified target.
    
    Returns:
        Tuple of (generated_code, backend) where backend can be used for
        compile_and_link and run operations.
    """
    if target == "x86_64":
        backend = X86_64Backend()
    elif target == "wasm32":
        backend = Wasm32Backend()
    elif target == "riscv":
        backend = RiscvBackend()
    elif target == "arm":
        backend = ArmBackend()
    else:
        raise ValueError(f"Unknown target: {target}")
    
    backend.begin_module()
    
    fn_table: FunctionTable = {}
    global_table: GlobalTable = {}
    const_table: ConstTable = {}
    scope_stack: ScopeStack = [{}]
    ctx = ParseContext(builtin_consts=backend.get_builtin_constants())
    state = ParseState(
        src=src,
        backend=backend,
        fn_table=fn_table,
        global_table=global_table,
        const_table=const_table,
        scope_stack=scope_stack,
        ctx=ctx,
    )
    
    parse_program(toks, state)
    
    for name, entry in fn_table.items():
        if not entry.is_defined:
            raise SyntaxError(f"Undefined function: {name}")
    
    return backend.finish_module(), backend
# ============================================================================
# CLI entry point
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m udewy.p0 [-c] [--target TARGET] [--split-wasm] [--serve-wasm] <file.udewy> [args...]")
        print("  -c              Compile only, don't run")
        print("  --target TARGET Target backend (x86_64, wasm32, riscv, arm)")
        print("  --split-wasm    For wasm32: output separate .wasm file instead of embedded HTML")
        print("  --serve-wasm    For wasm32: serve the generated HTML over HTTP")
        sys.exit(1)
    
    compile_only = False
    target = "x86_64"
    split_wasm = False
    serve_wasm = False
    arg_idx = 1
    
    while arg_idx < len(sys.argv) and sys.argv[arg_idx].startswith("-"):
        if sys.argv[arg_idx] == "-c":
            compile_only = True
            arg_idx += 1
        elif sys.argv[arg_idx] == "--target":
            arg_idx += 1
            target = sys.argv[arg_idx]
            arg_idx += 1
        elif sys.argv[arg_idx] == "--split-wasm":
            split_wasm = True
            arg_idx += 1
        elif sys.argv[arg_idx] == "--serve-wasm":
            serve_wasm = True
            arg_idx += 1
        else:
            break
    
    if arg_idx >= len(sys.argv):
        print("Error: No input file specified")
        sys.exit(1)
    
    input_file = Path(sys.argv[arg_idx])
    script_args = sys.argv[arg_idx + 1:]
    
    raw_src = input_file.read_text()
    src = process_imports(raw_src, input_file)
    toks = t0.tokenize(src)
    asm, backend = parse(toks, src, target)
    
    cache_dir = Path("__dewycache__")
    cache_dir.mkdir(exist_ok=True)
    
    # Use the backend to compile and link
    try:
        output_path = backend.compile_and_link(
            asm, 
            input_file.stem, 
            cache_dir,
            split_wasm=split_wasm
        )
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    if compile_only:
        print(backend.get_compile_message(output_path, split_wasm=split_wasm))
    else:
        exit_code = backend.run(output_path, script_args, split_wasm=split_wasm, serve_wasm=serve_wasm)
        if exit_code is not None:
            sys.exit(exit_code)
        else:
            print(backend.get_compile_message(output_path, split_wasm=split_wasm))
