"""
Parser and code generator for udewy
Uses a backend protocol for target-specific code generation.
"""

from pathlib import Path
from os import PathLike

from . import t0
from .backend.x86_64 import X86_64Backend
from .backend.wasm import Wasm32Backend
from .backend.riscv import RiscvBackend
from .backend.arm import ArmBackend


# ============================================================================
# Import preprocessing
# ============================================================================

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
        # skip whitespace
        while i < n and remaining[i] in ' \t\r\n':
            i = i + 1
        if i >= n:
            break
        
        # skip comments
        if remaining[i] == '#':
            while i < n and remaining[i] != '\n':
                i = i + 1
            continue
        
        # check for import statement
        if remaining[i:i+6] == 'import':
            start = i
            i = i + 6
            
            # skip whitespace
            while i < n and remaining[i] in ' \t':
                i = i + 1
            
            # expect p"
            if i < n and remaining[i] == 'p' and i + 1 < n and remaining[i + 1] == '"':
                i = i + 2  # skip p"
                path_start = i
                
                # read until closing quote
                while i < n and remaining[i] != '"':
                    if remaining[i] == '\\':
                        i = i + 1
                    i = i + 1
                
                if i >= n:
                    raise SyntaxError(f"Unterminated path string in import at position {start}")
                
                import_path_str = remaining[path_start:i]
                i = i + 1  # skip closing quote
                
                # resolve path relative to source file
                import_path = (source_dir / import_path_str).resolve()
                
                if not import_path.exists():
                    raise FileNotFoundError(f"Import file not found: {import_path}")
                
                # recursively process the imported file
                import_content = import_path.read_text()
                processed_import = process_imports(import_content, import_path, imported)
                
                # add the processed import content
                if processed_import:
                    result_parts.append(processed_import)
                
                # replace the import statement with empty (we've handled it)
                remaining = remaining[:start] + remaining[i:]
                n = len(remaining)
                i = start
            else:
                # not a valid import, continue
                i = i + 1
        else:
            # not an import, skip to next whitespace/newline to find next potential statement
            while i < n and remaining[i] not in ' \t\r\n':
                if remaining[i] == '"':
                    # skip strings
                    i = i + 1
                    while i < n and remaining[i] != '"':
                        if remaining[i] == '\\':
                            i = i + 1
                        i = i + 1
                    if i < n:
                        i = i + 1
                elif remaining[i] == '#':
                    # skip to end of line
                    while i < n and remaining[i] != '\n':
                        i = i + 1
                else:
                    i = i + 1
    
    # add the remaining source (with import statements removed)
    result_parts.append(remaining)
    
    return '\n'.join(result_parts)


# ============================================================================
# Type aliases
# ============================================================================
type PackedToken = int
type TokenIdx = int

# Function table entry: [name_start, name_len, label_id, num_args, is_defined]
type FnEntry = list

# Variable entry: [name_start, name_len, stack_offset_or_slot]
type VarEntry = list

# Global variable entry: [name_start, name_len, label_id]
type GlobalEntry = list

# Const entry: [name_start, name_len, value]
type ConstEntry = list


# ============================================================================
# Helper functions for name comparison
# ============================================================================

def name_eq(src: str, start1: int, len1: int, start2: int, len2: int) -> bool:
    if len1 != len2:
        return False
    i = 0
    while i < len1:
        if src[start1 + i] != src[start2 + i]:
            return False
        i = i + 1
    return True


def name_eq_str(src: str, start: int, length: int, target: str) -> bool:
    if length != len(target):
        return False
    i = 0
    while i < length:
        if src[start + i] != target[i]:
            return False
        i = i + 1
    return True


def get_name(src: str, start: int, length: int) -> str:
    return src[start:start + length]


def escape_code_to_value(c: str) -> int:
    if c == 'n': return 10
    if c == '\n': return -1
    if c == 't': return 9
    if c == 'r': return 13
    if c == '0': return 0
    return ord(c)


# ============================================================================
# Symbol table operations
# ============================================================================

def fn_lookup(fn_table: list, src: str, name_start: int, name_len: int) -> int:
    i = 0
    while i < len(fn_table):
        entry = fn_table[i]
        if name_eq(src, entry[0], entry[1], name_start, name_len):
            return i
        i = i + 1
    return -1


def fn_declare(fn_table: list, name_start: int, name_len: int, label_id: int, num_args: int, is_defined: bool) -> int:
    idx = len(fn_table)
    fn_table.append([name_start, name_len, label_id, num_args, is_defined])
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
            var_idx = var_idx + 1
        scope_idx = scope_idx - 1
    return (-1, -1)


def var_declare(scope_stack: list, name_start: int, name_len: int, slot: int) -> None:
    scope_stack[-1].append([name_start, name_len, slot])


def global_lookup(global_table: list, src: str, name_start: int, name_len: int) -> int:
    i = 0
    while i < len(global_table):
        entry = global_table[i]
        if name_eq(src, entry[0], entry[1], name_start, name_len):
            return i
        i = i + 1
    return -1


def global_declare(global_table: list, name_start: int, name_len: int, label_id: int) -> int:
    idx = len(global_table)
    global_table.append([name_start, name_len, label_id])
    return idx


def const_lookup(const_table: list, src: str, name_start: int, name_len: int) -> tuple[bool, int]:
    i = 0
    while i < len(const_table):
        entry = const_table[i]
        if name_eq(src, entry[0], entry[1], name_start, name_len):
            return (True, entry[2])
        i = i + 1
    return (False, 0)


def const_declare(const_table: list, name_start: int, name_len: int, value: int) -> int:
    idx = len(const_table)
    const_table.append([name_start, name_len, value])
    return idx


def push_scope(scope_stack: list) -> None:
    scope_stack.append([])


def pop_scope(scope_stack: list) -> None:
    scope_stack.pop()


# ============================================================================
# Token access helpers
# ============================================================================

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
        raise SyntaxError(f"Expected {t0.kind_to_str(kind)}, got {t0.dump_token(toks[idx], src)} at position {tok_loc(toks, idx)}")
    return idx + 1


# ============================================================================
# Operator precedence
# ============================================================================

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


def kind_to_op(kind: int) -> str:
    if kind == t0.TK_PLUS: return "+"
    if kind == t0.TK_MINUS: return "-"
    if kind == t0.TK_MUL: return "*"
    if kind == t0.TK_IDIV: return "//"
    if kind == t0.TK_MOD: return "%"
    if kind == t0.TK_LEFT_SHIFT: return "<<"
    if kind == t0.TK_RIGHT_SHIFT: return ">>"
    if kind == t0.TK_AND: return "and"
    if kind == t0.TK_OR: return "or"
    if kind == t0.TK_XOR: return "xor"
    if kind == t0.TK_EQ: return "=?"
    if kind == t0.TK_NOT_EQ: return "not=?"
    if kind == t0.TK_GT: return ">?"
    if kind == t0.TK_LT: return "<?"
    if kind == t0.TK_GT_EQ: return ">=?"
    if kind == t0.TK_LT_EQ: return "<=?"
    return ""


# ============================================================================
# Intrinsic detection
# ============================================================================

def is_intrinsic(src: str, name_start: int, name_len: int) -> bool:
    if name_eq_str(src, name_start, name_len, "__syscall0__"): return True
    if name_eq_str(src, name_start, name_len, "__syscall1__"): return True
    if name_eq_str(src, name_start, name_len, "__syscall2__"): return True
    if name_eq_str(src, name_start, name_len, "__syscall3__"): return True
    if name_eq_str(src, name_start, name_len, "__syscall4__"): return True
    if name_eq_str(src, name_start, name_len, "__syscall5__"): return True
    if name_eq_str(src, name_start, name_len, "__syscall6__"): return True
    if name_eq_str(src, name_start, name_len, "__load64__"): return True
    if name_eq_str(src, name_start, name_len, "__store64__"): return True
    if name_eq_str(src, name_start, name_len, "__load8__"): return True
    if name_eq_str(src, name_start, name_len, "__store8__"): return True
    if name_eq_str(src, name_start, name_len, "__load16__"): return True
    if name_eq_str(src, name_start, name_len, "__store16__"): return True
    if name_eq_str(src, name_start, name_len, "__load32__"): return True
    if name_eq_str(src, name_start, name_len, "__store32__"): return True
    return False


def emit_intrinsic(backend, src: str, name_start: int, name_len: int, num_args: int) -> None:
    """Emit intrinsic call via backend."""
    name = get_name(src, name_start, name_len)
    
    if name == "__load64__":
        backend.load_mem(64)
    elif name == "__store64__":
        backend.store_mem(64)
    elif name == "__load8__":
        backend.load_mem(8)
    elif name == "__store8__":
        backend.store_mem(8)
    elif name == "__load16__":
        backend.load_mem(16)
    elif name == "__store16__":
        backend.store_mem(16)
    elif name == "__load32__":
        backend.load_mem(32)
    elif name == "__store32__":
        backend.store_mem(32)
    elif name.startswith("__syscall"):
        backend.syscall(num_args)


# ============================================================================
# Expression parsing
# ============================================================================

def parse_atom(toks: list, idx: int, src: str, backend,
               fn_table: list, scope_stack: list, global_table: list, const_table: list,
               ctx: dict) -> int:
    """Parse an atomic expression, emit via backend. Returns new idx."""
    kind = tok_kind(toks, idx)
    
    if kind == t0.TK_NUMBER:
        val = tok_value(toks, idx)
        backend.push_const_i64(val)
        return idx + 1
    
    if kind == t0.TK_VOID:
        backend.push_void()
        return idx + 1
    
    if kind == t0.TK_STRING:
        start = tok_loc(toks, idx)
        length = tok_value(toks, idx)
        str_content = src[start + 1 : start + length - 1]
        
        processed = []
        i = 0
        while i < len(str_content):
            if str_content[i] == '\\' and i + 1 < len(str_content):
                c = str_content[i + 1]
                val = escape_code_to_value(c)
                if val != -1:
                    processed.append(val)
                i = i + 2
            else:
                processed.append(ord(str_content[i]))
                i = i + 1
        
        label_id = backend.intern_string(bytes(processed))
        backend.push_string_ref(label_id)
        return idx + 1
    
    if kind == t0.TK_IDENT:
        name_start = tok_name_start(toks, idx)
        name_len = tok_name_len(toks, idx)
        
        scope_idx, var_idx = var_lookup(scope_stack, src, name_start, name_len)
        if scope_idx >= 0:
            entry = scope_stack[scope_idx][var_idx]
            slot = entry[2]
            backend.load_local(slot)
            return idx + 1
        
        glob_idx = global_lookup(global_table, src, name_start, name_len)
        if glob_idx >= 0:
            entry = global_table[glob_idx]
            backend.load_global(entry[2])
            return idx + 1
        
        fn_idx = fn_lookup(fn_table, src, name_start, name_len)
        if fn_idx >= 0:
            entry = fn_table[fn_idx]
            backend.push_fn_ref(entry[2])
            return idx + 1
        
        label_id = backend.declare_function(0, 0)
        fn_declare(fn_table, name_start, name_len, label_id, 0, False)
        backend.push_fn_ref(label_id)
        return idx + 1
    
    if kind == t0.TK_IDENT_CALL:
        name_start = tok_name_start(toks, idx)
        name_len = tok_name_len(toks, idx)
        idx = idx + 1
        
        arg_count = 0
        while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_PAREN:
            idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
            backend.save_value()
            arg_count = arg_count + 1
        
        idx = expect(toks, idx, t0.TK_RIGHT_PAREN, src)
        
        if is_intrinsic(src, name_start, name_len):
            if arg_count > 0:
                backend.restore_value()
            emit_intrinsic(backend, src, name_start, name_len, arg_count)
        else:
            fn_idx = fn_lookup(fn_table, src, name_start, name_len)
            if fn_idx < 0:
                label_id = backend.declare_function(0, arg_count)
                fn_idx = fn_declare(fn_table, name_start, name_len, label_id, arg_count, False)
            
            entry = fn_table[fn_idx]
            backend.call_direct(entry[2], arg_count)
        
        return idx
    
    if kind == t0.TK_LEFT_PAREN:
        idx = idx + 1
        idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
        idx = expect(toks, idx, t0.TK_RIGHT_PAREN, src)
        return idx
    
    if kind == t0.TK_LEFT_BRACKET:
        idx = idx + 1
        elem_directives = []
        
        while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACKET:
            elem_kind = tok_kind(toks, idx)
            
            if elem_kind == t0.TK_NUMBER:
                val = tok_value(toks, idx)
                elem_directives.append(val)
                idx = idx + 1
            
            elif elem_kind == t0.TK_IDENT:
                ns = tok_name_start(toks, idx)
                nl = tok_name_len(toks, idx)
                
                found, val = const_lookup(const_table, src, ns, nl)
                if found:
                    elem_directives.append(val)
                    idx = idx + 1
                else:
                    fn_idx = fn_lookup(fn_table, src, ns, nl)
                    if fn_idx >= 0:
                        entry = fn_table[fn_idx]
                        elem_directives.append(backend._fn_labels[entry[2]])
                        idx = idx + 1
                    else:
                        label_id = backend.declare_function(0, 0)
                        fn_declare(fn_table, ns, nl, label_id, 0, False)
                        elem_directives.append(backend._fn_labels[label_id])
                        idx = idx + 1
            
            elif elem_kind == t0.TK_STRING:
                start = tok_loc(toks, idx)
                length = tok_value(toks, idx)
                str_content = src[start + 1 : start + length - 1]
                idx = idx + 1
                
                processed = []
                i = 0
                while i < len(str_content):
                    if str_content[i] == '\\' and i + 1 < len(str_content):
                        c = str_content[i + 1]
                        val = escape_code_to_value(c)
                        if val != -1:
                            processed.append(val)
                        i = i + 2
                    else:
                        processed.append(ord(str_content[i]))
                        i = i + 1
                
                str_label_id = backend.intern_string(bytes(processed))
                elem_directives.append(f"{backend._string_labels[str_label_id]}+8")
            
            else:
                raise SyntaxError(f"Array elements must be constants at {tok_loc(toks, idx)}")
        
        idx = expect(toks, idx, t0.TK_RIGHT_BRACKET, src)
        
        label_id = backend.intern_array(elem_directives)
        backend.push_array_ref(label_id)
        return idx
    
    raise SyntaxError(f"Unexpected token: {t0.dump_token(toks[idx], src)} at {tok_loc(toks, idx)}")


def parse_prefix(toks: list, idx: int, src: str, backend,
                 fn_table: list, scope_stack: list, global_table: list, const_table: list,
                 ctx: dict) -> int:
    kind = tok_kind(toks, idx)

    if kind == t0.TK_NOT:
        idx = idx + 1
        idx = parse_prefix(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
        backend.unary_op("not")
        return idx

    if kind == t0.TK_MINUS:
        idx = idx + 1
        if tok_kind(toks, idx) == t0.TK_NUMBER:
            val = tok_value(toks, idx)
            backend.push_const_i64(-val)
            return idx + 1
        idx = parse_prefix(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
        backend.unary_op("neg")
        return idx

    return parse_atom(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)


def parse_expr(toks: list, idx: int, src: str, backend,
               fn_table: list, scope_stack: list, global_table: list, const_table: list,
               ctx: dict, min_prec: int) -> int:
    idx = parse_prefix(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
    idx = skip_cast_annotation(toks, idx)
    
    while idx < len(toks):
        kind = tok_kind(toks, idx)
        
        if kind == t0.TK_EXPR_CALL:
            backend.save_value()
            idx = idx + 1
            
            arg_count = 0
            while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_PAREN:
                idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
                backend.save_value()
                arg_count = arg_count + 1
            
            idx = expect(toks, idx, t0.TK_RIGHT_PAREN, src)
            backend.call_indirect(arg_count)
            continue
        
        if not is_binop(kind):
            break
        
        prec = get_precedence(kind)
        
        if prec > min_prec and min_prec > 0:
            raise SyntaxError(f"Operator precedence violation at {tok_loc(toks, idx)}")
        
        idx = idx + 1
        backend.save_value()
        
        if kind == t0.TK_PIPE:
            idx = parse_prefix(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
            idx = skip_cast_annotation(toks, idx)
            backend.pipe_call()
        else:
            idx = parse_prefix(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
            idx = skip_cast_annotation(toks, idx)
            backend.binary_op(kind_to_op(kind))
        
        min_prec = prec
    
    return idx


# ============================================================================
# Statement parsing
# ============================================================================

def skip_type_annotation(toks: list, idx: int) -> int:
    if idx >= len(toks):
        return idx
    kind = tok_kind(toks, idx)
    if kind == t0.TK_TYPE:
        idx = idx + 1
        if idx < len(toks) and tok_kind(toks, idx) == t0.TK_TYPE_PARAM:
            idx = idx + 1
    elif kind == t0.TK_TYPE_PARAM:
        idx = idx + 1
    return idx


def skip_fn_type_annotation(toks: list, idx: int) -> int:
    if idx >= len(toks):
        return idx
    kind = tok_kind(toks, idx)
    if kind == t0.TK_FN_TYPE:
        idx = idx + 1
        if idx < len(toks) and tok_kind(toks, idx) == t0.TK_TYPE_PARAM:
            idx = idx + 1
    return idx


def skip_cast_annotation(toks: list, idx: int) -> int:
    if idx < len(toks) and tok_kind(toks, idx) == t0.TK_TRANSMUTE:
        idx = idx + 1
        if idx < len(toks):
            kind = tok_kind(toks, idx)
            if kind == t0.TK_IDENT:
                idx = idx + 1
                if idx < len(toks) and tok_kind(toks, idx) == t0.TK_TYPE_PARAM:
                    idx = idx + 1
            elif kind == t0.TK_TYPE_PARAM:
                idx = idx + 1
    return idx


def parse_var_decl(toks: list, idx: int, src: str, backend,
                   fn_table: list, scope_stack: list, global_table: list, const_table: list,
                   ctx: dict) -> int:
    idx = idx + 1
    
    if tok_kind(toks, idx) != t0.TK_IDENT:
        raise SyntaxError(f"Expected identifier after let")
    
    name_start = tok_name_start(toks, idx)
    name_len = tok_name_len(toks, idx)
    idx = idx + 1
    
    idx = skip_type_annotation(toks, idx)
    
    if idx >= len(toks) or tok_kind(toks, idx) != t0.TK_ASSIGN:
        raise SyntaxError(f"Expected '=' at {tok_loc(toks, idx)}")
    idx = idx + 1
    
    idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
    
    slot = backend.alloc_local()
    var_declare(scope_stack, name_start, name_len, slot)
    backend.store_local(slot)
    
    return idx


def parse_fn_decl(toks: list, idx: int, src: str, backend,
                  fn_table: list, scope_stack: list, global_table: list, const_table: list,
                  ctx: dict) -> int:
    idx = idx + 1
    
    name_start = tok_name_start(toks, idx)
    name_len = tok_name_len(toks, idx)
    fn_name = get_name(src, name_start, name_len)
    idx = idx + 1
    
    idx = expect(toks, idx, t0.TK_ASSIGN, src)
    idx = expect(toks, idx, t0.TK_LEFT_PAREN, src)
    
    params = []
    while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_PAREN:
        if tok_kind(toks, idx) != t0.TK_IDENT:
            raise SyntaxError(f"Expected parameter name")
        param_start = tok_name_start(toks, idx)
        param_len = tok_name_len(toks, idx)
        params.append((param_start, param_len))
        idx = idx + 1
        idx = skip_type_annotation(toks, idx)
    
    idx = expect(toks, idx, t0.TK_RIGHT_PAREN, src)
    idx = skip_fn_type_annotation(toks, idx)
    idx = expect(toks, idx, t0.TK_FN_ARROW, src)
    idx = expect(toks, idx, t0.TK_LEFT_BRACE, src)
    
    fn_idx = fn_lookup(fn_table, src, name_start, name_len)
    if fn_idx >= 0:
        entry = fn_table[fn_idx]
        entry[3] = len(params)
        entry[4] = True
        label_id = entry[2]
    else:
        label_id = backend.declare_function(0, len(params))
        fn_declare(fn_table, name_start, name_len, label_id, len(params), True)
    
    is_main = fn_name == "main"
    backend.begin_function(label_id, fn_name, len(params), is_main)
    
    push_scope(scope_stack)
    
    for i, (param_start, param_len) in enumerate(params):
        slot = backend._param_slots[i]
        var_declare(scope_stack, param_start, param_len, slot)
    
    while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACE:
        idx = parse_statement(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
    
    idx = expect(toks, idx, t0.TK_RIGHT_BRACE, src)
    
    backend.end_function()
    pop_scope(scope_stack)
    
    return idx


def parse_if_stmnt(toks: list, idx: int, src: str, backend,
                   fn_table: list, scope_stack: list, global_table: list, const_table: list,
                   ctx: dict) -> int:
    idx = idx + 1
    
    idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
    backend.begin_if()
    
    idx = expect(toks, idx, t0.TK_LEFT_BRACE, src)
    push_scope(scope_stack)
    
    while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACE:
        idx = parse_statement(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
    
    idx = expect(toks, idx, t0.TK_RIGHT_BRACE, src)
    pop_scope(scope_stack)
    
    nested_if_count = 1
    
    while idx < len(toks) and tok_kind(toks, idx) == t0.TK_ELSE:
        idx = idx + 1
        
        if idx < len(toks) and tok_kind(toks, idx) == t0.TK_IF:
            backend.begin_else()
            idx = idx + 1
            
            idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
            backend.begin_if()
            nested_if_count = nested_if_count + 1
            
            idx = expect(toks, idx, t0.TK_LEFT_BRACE, src)
            push_scope(scope_stack)
            
            while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACE:
                idx = parse_statement(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
            
            idx = expect(toks, idx, t0.TK_RIGHT_BRACE, src)
            pop_scope(scope_stack)
        else:
            backend.begin_else()
            idx = expect(toks, idx, t0.TK_LEFT_BRACE, src)
            push_scope(scope_stack)
            
            while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACE:
                idx = parse_statement(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
            
            idx = expect(toks, idx, t0.TK_RIGHT_BRACE, src)
            pop_scope(scope_stack)
            
            for _ in range(nested_if_count):
                backend.end_if()
            return idx
    
    for _ in range(nested_if_count):
        backend.end_if()
    return idx


def parse_loop_stmnt(toks: list, idx: int, src: str, backend,
                     fn_table: list, scope_stack: list, global_table: list, const_table: list,
                     ctx: dict) -> int:
    idx = idx + 1
    
    backend.begin_loop()
    
    idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
    backend.begin_loop_body()
    
    idx = expect(toks, idx, t0.TK_LEFT_BRACE, src)
    push_scope(scope_stack)
    
    while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACE:
        idx = parse_statement(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
    
    idx = expect(toks, idx, t0.TK_RIGHT_BRACE, src)
    pop_scope(scope_stack)
    
    backend.end_loop()
    return idx


def parse_return_stmnt(toks: list, idx: int, src: str, backend,
                       fn_table: list, scope_stack: list, global_table: list, const_table: list,
                       ctx: dict) -> int:
    idx = idx + 1
    idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
    backend.emit_return()
    return idx


def parse_break_stmnt(toks: list, idx: int, src: str, backend,
                      fn_table: list, scope_stack: list, global_table: list, const_table: list,
                      ctx: dict) -> int:
    idx = idx + 1
    backend.emit_break()
    return idx


def parse_continue_stmnt(toks: list, idx: int, src: str, backend,
                         fn_table: list, scope_stack: list, global_table: list, const_table: list,
                         ctx: dict) -> int:
    idx = idx + 1
    backend.emit_continue()
    return idx


def parse_assign_or_expr(toks: list, idx: int, src: str, backend,
                         fn_table: list, scope_stack: list, global_table: list, const_table: list,
                         ctx: dict) -> int:
    if tok_kind(toks, idx) == t0.TK_IDENT:
        if idx + 1 < len(toks):
            next_kind = tok_kind(toks, idx + 1)
            
            if next_kind == t0.TK_ASSIGN:
                name_start = tok_name_start(toks, idx)
                name_len = tok_name_len(toks, idx)
                idx = idx + 2
                
                idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
                
                scope_idx, var_idx = var_lookup(scope_stack, src, name_start, name_len)
                if scope_idx >= 0:
                    entry = scope_stack[scope_idx][var_idx]
                    backend.store_local(entry[2])
                else:
                    glob_idx = global_lookup(global_table, src, name_start, name_len)
                    if glob_idx >= 0:
                        entry = global_table[glob_idx]
                        backend.store_global(entry[2])
                    else:
                        raise SyntaxError(f"Undefined variable")
                
                return idx
            
            elif next_kind == t0.TK_UPDATE_ASSIGN:
                name_start = tok_name_start(toks, idx)
                name_len = tok_name_len(toks, idx)
                op_kind = tok_value(toks, idx + 1)
                idx = idx + 2
                
                scope_idx, var_idx = var_lookup(scope_stack, src, name_start, name_len)
                if scope_idx >= 0:
                    entry = scope_stack[scope_idx][var_idx]
                    slot = entry[2]
                    backend.load_local(slot)
                else:
                    glob_idx = global_lookup(global_table, src, name_start, name_len)
                    if glob_idx >= 0:
                        entry = global_table[glob_idx]
                        slot = entry[2]
                        backend.load_global(slot)
                    else:
                        raise SyntaxError(f"Undefined variable")
                
                backend.save_value()
                idx = parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)
                backend.binary_op(kind_to_op(op_kind))
                
                if scope_idx >= 0:
                    backend.store_local(slot)
                else:
                    backend.store_global(slot)
                
                return idx
    
    return parse_expr(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx, 0)


def parse_statement(toks: list, idx: int, src: str, backend,
                    fn_table: list, scope_stack: list, global_table: list, const_table: list,
                    ctx: dict) -> int:
    kind = tok_kind(toks, idx)
    
    if kind == t0.TK_LET:
        if idx + 3 < len(toks):
            if tok_kind(toks, idx + 2) == t0.TK_ASSIGN and tok_kind(toks, idx + 3) == t0.TK_LEFT_PAREN:
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


def parse_program(toks: list, src: str, backend,
                  fn_table: list, scope_stack: list, global_table: list, const_table: list,
                  ctx: dict) -> None:
    idx = 0
    
    while idx < len(toks):
        kind = tok_kind(toks, idx)
        
        if kind == t0.TK_LET:
            if idx + 3 < len(toks):
                if tok_kind(toks, idx + 2) == t0.TK_ASSIGN and tok_kind(toks, idx + 3) == t0.TK_LEFT_PAREN:
                    idx = parse_fn_decl(toks, idx, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
                    continue
            
            idx = idx + 1
            
            name_start = tok_name_start(toks, idx)
            name_len = tok_name_len(toks, idx)
            idx = idx + 1
            
            idx = skip_type_annotation(toks, idx)
            idx = expect(toks, idx, t0.TK_ASSIGN, src)
            
            if tok_kind(toks, idx) == t0.TK_NUMBER:
                val = tok_value(toks, idx)
                idx = idx + 1
                
                const_declare(const_table, name_start, name_len, val)
                label_id = backend.define_global(0, val)
                global_declare(global_table, name_start, name_len, label_id)
                
            elif tok_kind(toks, idx) == t0.TK_STRING:
                start = tok_loc(toks, idx)
                length = tok_value(toks, idx)
                str_content = src[start + 1 : start + length - 1]
                idx = idx + 1
                
                processed = []
                i = 0
                while i < len(str_content):
                    if str_content[i] == '\\' and i + 1 < len(str_content):
                        c = str_content[i + 1]
                        val = escape_code_to_value(c)
                        if val != -1:
                            processed.append(val)
                        i = i + 2
                    else:
                        processed.append(ord(str_content[i]))
                        i = i + 1
                
                str_label_id = backend.intern_string(bytes(processed))
                label_id = backend.define_global(0, f"{backend._string_labels[str_label_id]}+8")
                global_declare(global_table, name_start, name_len, label_id)
                
            elif tok_kind(toks, idx) == t0.TK_LEFT_BRACKET:
                idx = idx + 1
                elem_directives = []
                
                while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACKET:
                    elem_kind = tok_kind(toks, idx)
                    
                    if elem_kind == t0.TK_NUMBER:
                        elem_directives.append(tok_value(toks, idx))
                        idx = idx + 1
                    
                    elif elem_kind == t0.TK_IDENT:
                        ns = tok_name_start(toks, idx)
                        nl = tok_name_len(toks, idx)
                        found, val = const_lookup(const_table, src, ns, nl)
                        if found:
                            elem_directives.append(val)
                            idx = idx + 1
                        else:
                            fn_idx = fn_lookup(fn_table, src, ns, nl)
                            if fn_idx >= 0:
                                entry = fn_table[fn_idx]
                                elem_directives.append(backend._fn_labels[entry[2]])
                                idx = idx + 1
                            else:
                                label_id_fn = backend.declare_function(0, 0)
                                fn_declare(fn_table, ns, nl, label_id_fn, 0, False)
                                elem_directives.append(backend._fn_labels[label_id_fn])
                                idx = idx + 1
                    
                    elif elem_kind == t0.TK_STRING:
                        start = tok_loc(toks, idx)
                        length = tok_value(toks, idx)
                        str_content = src[start + 1 : start + length - 1]
                        idx = idx + 1
                        processed = []
                        i = 0
                        while i < len(str_content):
                            if str_content[i] == '\\' and i + 1 < len(str_content):
                                c = str_content[i + 1]
                                val = escape_code_to_value(c)
                                if val != -1:
                                    processed.append(val)
                                i = i + 2
                            else:
                                processed.append(ord(str_content[i]))
                                i = i + 1
                        str_lbl_id = backend.intern_string(bytes(processed))
                        elem_directives.append(f"{backend._string_labels[str_lbl_id]}+8")
                    
                    else:
                        raise SyntaxError(f"Unsupported element type in global array at {tok_loc(toks, idx)}")
                
                idx = expect(toks, idx, t0.TK_RIGHT_BRACKET, src)
                
                arr_label_id = backend.intern_array(elem_directives)
                label_id = backend.define_global(0, f"{backend._array_labels[arr_label_id]}+8")
                global_declare(global_table, name_start, name_len, label_id)
            else:
                raise SyntaxError(f"Global variables must have constant initializers at {tok_loc(toks, idx)}")
        else:
            raise SyntaxError(f"Only declarations allowed at top level, got {t0.dump_token(toks[idx], src)}")


# ============================================================================
# Main entry point
# ============================================================================

def parse(toks: list, src: str, target: str = "x86_64") -> str:
    """Parse tokens and generate code for the specified target."""
    
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
    
    fn_table: list = []
    global_table: list = []
    const_table: list = []
    scope_stack: list = [[]]
    ctx = {}
    
    parse_program(toks, src, backend, fn_table, scope_stack, global_table, const_table, ctx)
    
    for entry in fn_table:
        if not entry[4]:
            name = get_name(src, entry[0], entry[1])
            raise SyntaxError(f"Undefined function: {name}")
    
    return backend.finish_module()


# ============================================================================
# CLI entry point
# ============================================================================

if __name__ == "__main__":
    import sys
    import subprocess
    from pathlib import Path
    
    if len(sys.argv) < 2:
        print("Usage: python -m udewy.p0 [-c] [--target TARGET] <file.udewy> [args...]")
        print("  -c              Compile only, don't run")
        print("  --target TARGET Target backend (x86_64, wasm32, riscv, arm)")
        sys.exit(1)
    
    compile_only = False
    target = "x86_64"
    arg_idx = 1
    
    while arg_idx < len(sys.argv) and sys.argv[arg_idx].startswith("-"):
        if sys.argv[arg_idx] == "-c":
            compile_only = True
            arg_idx += 1
        elif sys.argv[arg_idx] == "--target":
            arg_idx += 1
            target = sys.argv[arg_idx]
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
    asm = parse(toks, src, target)
    
    cache_dir = Path("__dewycache__")
    cache_dir.mkdir(exist_ok=True)
    
    if target == "x86_64":
        asm_path = cache_dir / f"{input_file.stem}.s"
        obj_path = cache_dir / f"{input_file.stem}.o"
        exe_path = cache_dir / input_file.stem
        
        asm_path.write_text(asm)
        
        subprocess.run(["as", str(asm_path), "-o", str(obj_path)], check=True)
        subprocess.run(["ld", str(obj_path), "-o", str(exe_path)], check=True)
        
        if compile_only:
            print(f"Compiled: {exe_path}")
        else:
            result = subprocess.run([str(exe_path)] + script_args)
            sys.exit(result.returncode)
    
    elif target == "wasm32":
        wat_path = cache_dir / f"{input_file.stem}.wat"
        wasm_path = cache_dir / f"{input_file.stem}.wasm"
        js_path = cache_dir / f"{input_file.stem}.js"
        html_path = cache_dir / f"{input_file.stem}.html"
        
        wat_path.write_text(asm)
        
        # Convert WAT to WASM using wat2wasm if available
        try:
            subprocess.run(["wat2wasm", str(wat_path), "-o", str(wasm_path)], check=True)
        except FileNotFoundError:
            print("Warning: wat2wasm not found, WAT file generated but not converted to WASM")
            print(f"Install wabt: https://github.com/WebAssembly/wabt")
            print(f"WAT file: {wat_path}")
            if compile_only:
                sys.exit(0)
            else:
                sys.exit(1)
        
        # Generate JS shim
        js_shim = '''
const memory = new WebAssembly.Memory({ initial: 1 });

const imports = {
    env: {
        memory: memory,
        syscall0: (num) => {
            console.log(`syscall0(${num})`);
            return 0n;
        },
        syscall1: (num, a1) => {
            if (num === 60n) {
                console.log(`exit(${a1})`);
                return a1;
            }
            console.log(`syscall1(${num}, ${a1})`);
            return 0n;
        },
        syscall2: (num, a1, a2) => {
            console.log(`syscall2(${num}, ${a1}, ${a2})`);
            return 0n;
        },
        syscall3: (num, a1, a2, a3) => {
            if (num === 1n) {
                const view = new Uint8Array(memory.buffer);
                const start = Number(a2);
                const len = Number(a3);
                const bytes = view.slice(start, start + len);
                const text = new TextDecoder().decode(bytes);
                if (Number(a1) === 1) {
                    process.stdout.write(text);
                } else if (Number(a1) === 2) {
                    process.stderr.write(text);
                }
                return BigInt(len);
            }
            console.log(`syscall3(${num}, ${a1}, ${a2}, ${a3})`);
            return 0n;
        },
        syscall4: (num, a1, a2, a3, a4) => {
            console.log(`syscall4(${num}, ${a1}, ${a2}, ${a3}, ${a4})`);
            return 0n;
        },
        syscall5: (num, a1, a2, a3, a4, a5) => {
            console.log(`syscall5(${num}, ${a1}, ${a2}, ${a3}, ${a4}, ${a5})`);
            return 0n;
        },
        syscall6: (num, a1, a2, a3, a4, a5, a6) => {
            console.log(`syscall6(${num}, ${a1}, ${a2}, ${a3}, ${a4}, ${a5}, ${a6})`);
            return 0n;
        },
    }
};

async function run() {
    const fs = require('fs');
    const wasmBuffer = fs.readFileSync('WASM_PATH');
    const { instance } = await WebAssembly.instantiate(wasmBuffer, imports);
    
    const result = instance.exports.main();
    console.log(`\\nExit code: ${result}`);
    process.exit(Number(result));
}

run().catch(err => {
    console.error(err);
    process.exit(1);
});
'''.replace('WASM_PATH', str(wasm_path))
        
        js_path.write_text(js_shim)
        
        # Generate HTML for browser
        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <title>{input_file.stem}</title>
</head>
<body>
    <h1>{input_file.stem}</h1>
    <pre id="output"></pre>
    <script>
const memory = new WebAssembly.Memory({{ initial: 1 }});
const output = document.getElementById('output');

const imports = {{
    env: {{
        memory: memory,
        syscall0: (num) => {{ output.textContent += `syscall0(${{num}})\\n`; return 0n; }},
        syscall1: (num, a1) => {{
            if (num === 60n) {{ output.textContent += `exit(${{a1}})\\n`; return a1; }}
            return 0n;
        }},
        syscall2: (num, a1, a2) => {{ return 0n; }},
        syscall3: (num, a1, a2, a3) => {{
            if (num === 1n) {{
                const view = new Uint8Array(memory.buffer);
                const start = Number(a2);
                const len = Number(a3);
                const bytes = view.slice(start, start + len);
                const text = new TextDecoder().decode(bytes);
                output.textContent += text;
                return BigInt(len);
            }}
            return 0n;
        }},
        syscall4: (num, a1, a2, a3, a4) => {{ return 0n; }},
        syscall5: (num, a1, a2, a3, a4, a5) => {{ return 0n; }},
        syscall6: (num, a1, a2, a3, a4, a5, a6) => {{ return 0n; }},
    }}
}};

fetch('{wasm_path.name}')
    .then(r => r.arrayBuffer())
    .then(bytes => WebAssembly.instantiate(bytes, imports))
    .then(result => {{
        const ret = result.instance.exports.main();
        output.textContent += `\\nExit code: ${{ret}}`;
    }})
    .catch(err => {{
        output.textContent += `Error: ${{err}}`;
    }});
    </script>
</body>
</html>
'''
        html_path.write_text(html_content)
        
        if compile_only:
            print(f"Compiled: {wasm_path}")
            print(f"JS shim: {js_path}")
            print(f"HTML: {html_path}")
        else:
            # Run with Node.js
            result = subprocess.run(["node", str(js_path)] + script_args)
            sys.exit(result.returncode)
    
    elif target == "riscv":
        asm_path = cache_dir / f"{input_file.stem}.s"
        obj_path = cache_dir / f"{input_file.stem}.o"
        exe_path = cache_dir / input_file.stem
        
        asm_path.write_text(asm)
        
        # Try different toolchain prefixes
        for prefix in ["riscv64-linux-gnu-", "riscv64-elf-", "riscv64-unknown-elf-"]:
            try:
                subprocess.run([f"{prefix}as", str(asm_path), "-o", str(obj_path)], check=True)
                subprocess.run([f"{prefix}ld", str(obj_path), "-o", str(exe_path)], check=True)
                break
            except FileNotFoundError:
                continue
        else:
            print("Error: RISC-V toolchain not found")
            print(f"Install one of: riscv64-linux-gnu-*, riscv64-elf-*")
            print(f"Assembly file: {asm_path}")
            sys.exit(1)
        
        if compile_only:
            print(f"Compiled: {exe_path}")
        else:
            result = subprocess.run(["qemu-riscv64", str(exe_path)] + script_args)
            sys.exit(result.returncode)
    
    elif target == "arm":
        asm_path = cache_dir / f"{input_file.stem}.s"
        obj_path = cache_dir / f"{input_file.stem}.o"
        exe_path = cache_dir / input_file.stem
        
        asm_path.write_text(asm)
        
        # Try different toolchain prefixes
        for prefix in ["aarch64-linux-gnu-", "aarch64-elf-", "aarch64-unknown-elf-"]:
            try:
                subprocess.run([f"{prefix}as", str(asm_path), "-o", str(obj_path)], check=True)
                subprocess.run([f"{prefix}ld", str(obj_path), "-o", str(exe_path)], check=True)
                break
            except FileNotFoundError:
                continue
        else:
            print("Error: AArch64 toolchain not found")
            print(f"Install one of: aarch64-linux-gnu-*, aarch64-elf-*")
            print(f"Assembly file: {asm_path}")
            sys.exit(1)
        
        if compile_only:
            print(f"Compiled: {exe_path}")
        else:
            result = subprocess.run(["qemu-aarch64", str(exe_path)] + script_args)
            sys.exit(result.returncode)
    
    else:
        print(f"Target {target} not yet implemented")
        sys.exit(1)
