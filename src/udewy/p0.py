"""
Parser and x86_64 code generator for udewy
Designed in low-level style for future translation to assembly
"""

from . import t0

# ============================================================================
# Type aliases (for documentation, not enforced)
# ============================================================================
type PackedToken = int
type TokenIdx = int

# ============================================================================
# Parser state - all mutable state passed explicitly
# ============================================================================

# Function table entry: (name_start, name_len, label_id, num_args, is_defined)
# name_start/len index into src string
# label_id is the numeric label for the function
# is_defined tracks if we've seen the actual definition vs just a forward reference
type FnEntry = list  # [name_start, name_len, label_id, num_args, is_defined]

# Variable entry: (name_start, name_len, stack_offset)
# stack_offset is negative relative to rbp for locals
type VarEntry = list  # [name_start, name_len, stack_offset]

# Global variable entry: (name_start, name_len, label_id)
type GlobalEntry = list  # [name_start, name_len, label_id]

# Const entry: (name_start, name_len, value)
# value is the computed integer value of the const
type ConstEntry = list  # [name_start, name_len, value]

# ============================================================================
# Helper functions for name comparison (low-level style)
# ============================================================================

def name_eq(src: str, start1: int, len1: int, start2: int, len2: int) -> bool:
    """Compare two identifier spans in src"""
    if len1 != len2:
        return False
    i = 0
    while i < len1:
        if src[start1 + i] != src[start2 + i]:
            return False
        i = i + 1
    return True

def name_eq_str(src: str, start: int, length: int, target: str) -> bool:
    """Compare an identifier span to a literal string"""
    if length != len(target):
        return False
    i = 0
    while i < length:
        if src[start + i] != target[i]:
            return False
        i = i + 1
    return True

def get_name(src: str, start: int, length: int) -> str:
    """Extract name string from src (for labels/debugging)"""
    return src[start:start + length]

# ============================================================================
# Symbol table operations (low-level style with linear search)
# ============================================================================

def fn_lookup(fn_table: list, src: str, name_start: int, name_len: int) -> int:
    """Find function in table, returns index or -1"""
    i = 0
    while i < len(fn_table):
        entry = fn_table[i]
        if name_eq(src, entry[0], entry[1], name_start, name_len):
            return i
        i = i + 1
    return -1

def fn_declare(fn_table: list, name_start: int, name_len: int, label_id: int, num_args: int, is_defined: bool) -> int:
    """Add function to table, returns index"""
    idx = len(fn_table)
    fn_table.append([name_start, name_len, label_id, num_args, is_defined])
    return idx

def var_lookup(scope_stack: list, src: str, name_start: int, name_len: int) -> tuple[int, int]:
    """Find variable in scope chain. Returns (scope_idx, var_idx) or (-1, -1)"""
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

def var_declare(scope_stack: list, name_start: int, name_len: int, stack_offset: int) -> None:
    """Add variable to current scope"""
    scope_stack[-1].append([name_start, name_len, stack_offset])

def global_lookup(global_table: list, src: str, name_start: int, name_len: int) -> int:
    """Find global in table, returns index or -1"""
    i = 0
    while i < len(global_table):
        entry = global_table[i]
        if name_eq(src, entry[0], entry[1], name_start, name_len):
            return i
        i = i + 1
    return -1

def global_declare(global_table: list, name_start: int, name_len: int, label_id: int) -> int:
    """Add global to table, returns index"""
    idx = len(global_table)
    global_table.append([name_start, name_len, label_id])
    return idx

def const_lookup(const_table: list, src: str, name_start: int, name_len: int) -> tuple[bool, int]:
    """Find const in table, returns (found, value)"""
    i = 0
    while i < len(const_table):
        entry = const_table[i]
        if name_eq(src, entry[0], entry[1], name_start, name_len):
            return (True, entry[2])
        i = i + 1
    return (False, 0)

def const_declare(const_table: list, name_start: int, name_len: int, value: int) -> int:
    """Add const to table, returns index"""
    idx = len(const_table)
    const_table.append([name_start, name_len, value])
    return idx

def push_scope(scope_stack: list) -> None:
    """Enter new scope"""
    scope_stack.append([])

def pop_scope(scope_stack: list) -> None:
    """Exit current scope"""
    scope_stack.pop()

# ============================================================================
# Assembly emission helpers
# ============================================================================

def emit(code: list, instr: str) -> None:
    """Emit an instruction to code buffer"""
    code.append("    " + instr)

def emit_label(code: list, label: str) -> None:
    """Emit a label"""
    code.append(label + ":")

def emit_comment(code: list, comment: str) -> None:
    """Emit a comment"""
    code.append("    # " + comment)

def emit_data(data: list, directive: str) -> None:
    """Emit to data section"""
    data.append(directive)

def emit_data_label(data: list, label: str) -> None:
    """Emit label to data section"""
    data.append(label + ":")

# ============================================================================
# Token access helpers
# ============================================================================

def tok_kind(toks: list, idx: int) -> int:
    """Get kind of token at idx"""
    return t0.kindof(toks[idx])

def tok_value(toks: list, idx: int) -> int:
    """Get value of token at idx"""
    return toks[idx] >> 64

def tok_loc(toks: list, idx: int) -> int:
    """Get location of token at idx"""
    return (toks[idx] >> 16) & 0xFFFF_FFFF_FFFF

def tok_name_start(toks: list, idx: int) -> int:
    """For IDENT/IDENT_CALL/TYPE/FN_TYPE, get start position in src"""
    return tok_loc(toks, idx)

def tok_name_len(toks: list, idx: int) -> int:
    """For IDENT/IDENT_CALL/TYPE/FN_TYPE, get length"""
    return tok_value(toks, idx)

def expect(toks: list, idx: int, kind: int, src: str) -> int:
    """Assert current token is expected kind, return next idx"""
    if idx >= len(toks):
        raise SyntaxError(f"Unexpected end of input, expected {t0.kind_to_str(kind)}")
    if tok_kind(toks, idx) != kind:
        raise SyntaxError(f"Expected {t0.kind_to_str(kind)}, got {t0.dump_token(toks[idx], src)} at position {tok_loc(toks, idx)}")
    return idx + 1

# ============================================================================
# Operator precedence (for left-to-right validation)
# Higher number = higher precedence (binds tighter)
# ============================================================================

PREC_OR = 1
PREC_XOR = 2
PREC_AND = 3
PREC_EQ = 4      # =? not=?
PREC_CMP = 5     # >? <? >=? <=?
PREC_SHIFT = 6   # << >>
PREC_ADD = 7     # + -
PREC_MUL = 8     # * // %
PREC_PIPE = 9    # |>

def get_precedence(kind: int) -> int:
    """Get precedence of binary operator token kind"""
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
    """Check if token kind is a binary operator"""
    return get_precedence(kind) > 0

# ============================================================================
# Intrinsic detection
# ============================================================================

def is_intrinsic(src: str, name_start: int, name_len: int) -> bool:
    """Check if name is an intrinsic"""
    if name_eq_str(src, name_start, name_len, "__syscall0__"):
        return True
    if name_eq_str(src, name_start, name_len, "__syscall1__"):
        return True
    if name_eq_str(src, name_start, name_len, "__syscall2__"):
        return True
    if name_eq_str(src, name_start, name_len, "__syscall3__"):
        return True
    if name_eq_str(src, name_start, name_len, "__syscall4__"):
        return True
    if name_eq_str(src, name_start, name_len, "__syscall5__"):
        return True
    if name_eq_str(src, name_start, name_len, "__syscall6__"):
        return True
    if name_eq_str(src, name_start, name_len, "__load__"):
        return True
    if name_eq_str(src, name_start, name_len, "__store__"):
        return True
    if name_eq_str(src, name_start, name_len, "__load8__"):
        return True
    if name_eq_str(src, name_start, name_len, "__store8__"):
        return True
    return False

# ============================================================================
# Code generation for intrinsics
# ============================================================================

def emit_intrinsic_call(code: list, src: str, name_start: int, name_len: int, num_args: int) -> None:
    """Emit inline code for intrinsic. Args are on stack, top = last arg."""
    name = get_name(src, name_start, name_len)
    
    if name == "__load__":
        # load 64-bit from address in rax
        emit(code, "movq (%rax), %rax")
    elif name == "__store__":
        # store: args are (val, ptr) - ptr in rax, val on stack
        emit(code, "popq %rbx")         # val
        emit(code, "movq %rbx, (%rax)") # store val to ptr
        emit(code, "xorq %rax, %rax")   # return 0
    elif name == "__load8__":
        # load byte from address in rax, zero-extend
        emit(code, "movzbq (%rax), %rax")
    elif name == "__store8__":
        # store byte: args are (val, ptr)
        emit(code, "popq %rbx")         # val
        emit(code, "movb %bl, (%rax)")  # store low byte
        emit(code, "xorq %rax, %rax")   # return 0
    elif name == "__syscall0__":
        # syscall num in rax
        emit(code, "syscall")
    elif name == "__syscall1__":
        # num, arg1
        emit(code, "movq %rax, %rdi")   # arg1
        emit(code, "popq %rax")         # syscall num
        emit(code, "syscall")
    elif name == "__syscall2__":
        # num, arg1, arg2
        emit(code, "movq %rax, %rsi")   # arg2
        emit(code, "popq %rdi")         # arg1
        emit(code, "popq %rax")         # syscall num
        emit(code, "syscall")
    elif name == "__syscall3__":
        # num, arg1, arg2, arg3
        emit(code, "movq %rax, %rdx")   # arg3
        emit(code, "popq %rsi")         # arg2
        emit(code, "popq %rdi")         # arg1
        emit(code, "popq %rax")         # syscall num
        emit(code, "syscall")
    elif name == "__syscall4__":
        # num, arg1, arg2, arg3, arg4
        emit(code, "movq %rax, %r10")   # arg4
        emit(code, "popq %rdx")         # arg3
        emit(code, "popq %rsi")         # arg2
        emit(code, "popq %rdi")         # arg1
        emit(code, "popq %rax")         # syscall num
        emit(code, "syscall")
    elif name == "__syscall5__":
        # num, arg1, arg2, arg3, arg4, arg5
        emit(code, "movq %rax, %r8")    # arg5
        emit(code, "popq %r10")         # arg4
        emit(code, "popq %rdx")         # arg3
        emit(code, "popq %rsi")         # arg2
        emit(code, "popq %rdi")         # arg1
        emit(code, "popq %rax")         # syscall num
        emit(code, "syscall")
    elif name == "__syscall6__":
        # num, arg1, arg2, arg3, arg4, arg5, arg6
        emit(code, "movq %rax, %r9")    # arg6
        emit(code, "popq %r8")          # arg5
        emit(code, "popq %r10")         # arg4
        emit(code, "popq %rdx")         # arg3
        emit(code, "popq %rsi")         # arg2
        emit(code, "popq %rdi")         # arg1
        emit(code, "popq %rax")         # syscall num
        emit(code, "syscall")

# ============================================================================
# Expression parsing and code generation
# ============================================================================

def parse_atom(toks: list, idx: int, src: str, code: list, data: list,
               fn_table: list, scope_stack: list, global_table: list, const_table: list,
               ctx: dict) -> int:
    """Parse an atomic expression, emit code, result in rax. Returns new idx."""
    kind = tok_kind(toks, idx)
    
    # Number literal
    if kind == t0.TK_NUMBER:
        val = tok_value(toks, idx)
        emit(code, f"movq ${val}, %rax")
        return idx + 1
    
    # Void
    if kind == t0.TK_VOID:
        emit(code, "xorq %rax, %rax")
        return idx + 1
    
    # String literal
    if kind == t0.TK_STRING:
        start = tok_loc(toks, idx)
        length = tok_value(toks, idx)
        # String includes quotes, extract content
        str_content = src[start + 1 : start + length - 1]
        
        # Process escape sequences
        processed = []
        i = 0
        while i < len(str_content):
            if str_content[i] == '\\' and i + 1 < len(str_content):
                c = str_content[i + 1]
                if c == 'n':
                    processed.append(10)
                elif c == 't':
                    processed.append(9)
                elif c == 'r':
                    processed.append(13)
                elif c == '\\':
                    processed.append(92)
                elif c == '"':
                    processed.append(34)
                elif c == '0':
                    processed.append(0)
                else:
                    processed.append(ord(c))
                i = i + 2
            else:
                processed.append(ord(str_content[i]))
                i = i + 1
        
        # Emit to data section with length prefix
        label_id = ctx["next_label"]
        ctx["next_label"] = ctx["next_label"] + 1
        label = f".Lstr{label_id}"
        
        emit_data_label(data, label)
        emit_data(data, f"    .quad {len(processed)}")  # length prefix
        # Emit bytes
        if len(processed) > 0:
            bytes_str = ", ".join([str(b) for b in processed])
            emit_data(data, f"    .byte {bytes_str}")
        
        # Load address of data (skip length prefix for pointer to start of string data)
        emit(code, f"leaq {label}+8(%rip), %rax")
        return idx + 1
    
    # Identifier (variable reference)
    if kind == t0.TK_IDENT:
        name_start = tok_name_start(toks, idx)
        name_len = tok_name_len(toks, idx)
        
        # Check local variables first
        scope_idx, var_idx = var_lookup(scope_stack, src, name_start, name_len)
        if scope_idx >= 0:
            entry = scope_stack[scope_idx][var_idx]
            offset = entry[2]
            emit(code, f"movq {offset}(%rbp), %rax")
            return idx + 1
        
        # Check globals
        glob_idx = global_lookup(global_table, src, name_start, name_len)
        if glob_idx >= 0:
            entry = global_table[glob_idx]
            label = f".Lglobal{entry[2]}"
            emit(code, f"movq {label}(%rip), %rax")
            return idx + 1
        
        # Check functions (load address)
        fn_idx = fn_lookup(fn_table, src, name_start, name_len)
        if fn_idx >= 0:
            entry = fn_table[fn_idx]
            label = f".Lfn{entry[2]}"
            emit(code, f"leaq {label}(%rip), %rax")
            return idx + 1
        
        # Unknown identifier - create forward reference as function
        label_id = ctx["next_label"]
        ctx["next_label"] = ctx["next_label"] + 1
        fn_declare(fn_table, name_start, name_len, label_id, 0, False)
        label = f".Lfn{label_id}"
        emit(code, f"leaq {label}(%rip), %rax")
        return idx + 1
    
    # Function call: ident(args...)
    if kind == t0.TK_IDENT_CALL:
        name_start = tok_name_start(toks, idx)
        name_len = tok_name_len(toks, idx)
        idx = idx + 1
        
        # Parse arguments, push to stack
        arg_count = 0
        while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_PAREN:
            idx = parse_expr(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx, 0)
            emit(code, "pushq %rax")
            arg_count = arg_count + 1
        
        idx = expect(toks, idx, t0.TK_RIGHT_PAREN, src)
        
        # Check if intrinsic
        if is_intrinsic(src, name_start, name_len):
            # Pop last arg back to rax for intrinsic
            if arg_count > 0:
                emit(code, "popq %rax")
            emit_intrinsic_call(code, src, name_start, name_len, arg_count)
            # Intrinsics consume all their args from stack, no cleanup needed
        else:
            # Regular function call - use System V calling convention
            # Args are on stack in reverse order (first arg deepest)
            # Pop into registers: rdi, rsi, rdx, rcx, r8, r9
            regs = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
            
            # Pop args into temp storage, then move to registers
            # Stack has args in order: first pushed = first arg = deepest
            # We need to reverse them
            if arg_count > 0:
                # Pop all to get them in correct order
                i = arg_count - 1
                while i >= 0:
                    if i < 6:
                        emit(code, f"popq {regs[i]}")
                    else:
                        # Leave extra args on stack for now
                        pass
                    i = i - 1
            
            # Look up or create function
            fn_idx = fn_lookup(fn_table, src, name_start, name_len)
            if fn_idx < 0:
                # Forward reference
                label_id = ctx["next_label"]
                ctx["next_label"] = ctx["next_label"] + 1
                fn_idx = fn_declare(fn_table, name_start, name_len, label_id, arg_count, False)
            
            entry = fn_table[fn_idx]
            label = f".Lfn{entry[2]}"
            emit(code, f"call {label}")
        
        return idx
    
    # Parenthesized expression
    if kind == t0.TK_LEFT_PAREN:
        idx = idx + 1
        idx = parse_expr(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx, 0)
        idx = expect(toks, idx, t0.TK_RIGHT_PAREN, src)
        return idx
    
    # Array literal
    if kind == t0.TK_LEFT_BRACKET:
        start_idx = idx
        idx = idx + 1
        
        # First pass: try to collect all elements as compile-time constants
        const_elements = []
        all_const = True
        elem_count = 0
        scan_idx = idx
        
        while scan_idx < len(toks) and tok_kind(toks, scan_idx) != t0.TK_RIGHT_BRACKET:
            elem_count = elem_count + 1
            if tok_kind(toks, scan_idx) == t0.TK_NUMBER:
                const_elements.append(tok_value(toks, scan_idx))
                scan_idx = scan_idx + 1
            elif tok_kind(toks, scan_idx) == t0.TK_IDENT:
                name_start = tok_name_start(toks, scan_idx)
                name_len = tok_name_len(toks, scan_idx)
                found, val = const_lookup(const_table, src, name_start, name_len)
                if found:
                    const_elements.append(val)
                    scan_idx = scan_idx + 1
                else:
                    # Not a const - need runtime evaluation
                    all_const = False
                    break
            else:
                # Some other expression - need runtime evaluation
                all_const = False
                break
        
        if all_const:
            # All elements are constants - emit to .data section
            idx = scan_idx
            idx = expect(toks, idx, t0.TK_RIGHT_BRACKET, src)
            
            label_id = ctx["next_label"]
            ctx["next_label"] = ctx["next_label"] + 1
            label = f".Larr{label_id}"
            
            emit_data_label(data, label)
            emit_data(data, f"    .quad {len(const_elements)}")  # length prefix
            i = 0
            while i < len(const_elements):
                emit_data(data, f"    .quad {const_elements[i]}")
                i = i + 1
            
            # Load address (points to first element, after length)
            emit(code, f"leaq {label}+8(%rip), %rax")
            return idx
        else:
            # Some runtime values - build array on stack
            # Need to re-parse and evaluate each element
            idx = start_idx + 1  # restart after [
            
            # Count elements first (scan to ])
            # Track bracket depth and paren depth to only count top-level expressions
            elem_count = 0
            bracket_depth = 1
            paren_depth = 0
            count_idx = idx
            while count_idx < len(toks) and bracket_depth > 0:
                k = tok_kind(toks, count_idx)
                if k == t0.TK_LEFT_BRACKET:
                    bracket_depth = bracket_depth + 1
                elif k == t0.TK_RIGHT_BRACKET:
                    bracket_depth = bracket_depth - 1
                    if bracket_depth == 0:
                        break
                # Count elements only at top level (bracket depth 1, paren depth 0)
                # BEFORE updating paren depth so IDENT_CALL counts as element
                if bracket_depth == 1 and paren_depth == 0:
                    if k == t0.TK_NUMBER or k == t0.TK_IDENT or k == t0.TK_STRING or k == t0.TK_IDENT_CALL or k == t0.TK_LEFT_PAREN or k == t0.TK_LEFT_BRACKET or k == t0.TK_MINUS or k == t0.TK_NOT:
                        elem_count = elem_count + 1
                # Update paren depth AFTER counting
                if k == t0.TK_LEFT_PAREN or k == t0.TK_IDENT_CALL:
                    paren_depth = paren_depth + 1
                elif k == t0.TK_RIGHT_PAREN:
                    paren_depth = paren_depth - 1
                count_idx = count_idx + 1
            
            # Allocate stack space: 8 bytes for length + 8 bytes per element
            arr_size = 8 + elem_count * 8
            emit(code, f"subq ${arr_size}, %rsp")
            
            # Store length
            emit(code, f"movq ${elem_count}, (%rsp)")
            
            # Evaluate and store each element
            elem_idx = 0
            while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACKET:
                # Parse the expression for this element
                idx = parse_expr(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx, 0)
                
                # Store element at offset (skip length prefix)
                offset = 8 + elem_idx * 8
                emit(code, f"movq %rax, {offset}(%rsp)")
                elem_idx = elem_idx + 1
            
            idx = expect(toks, idx, t0.TK_RIGHT_BRACKET, src)
            
            # Load address of first element (after length)
            emit(code, "leaq 8(%rsp), %rax")
            return idx
    
    # Unary not
    if kind == t0.TK_NOT:
        idx = idx + 1
        idx = parse_atom(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
        emit(code, "notq %rax")
        return idx
    
    # Unary minus (for negative numbers)
    if kind == t0.TK_MINUS:
        idx = idx + 1
        if tok_kind(toks, idx) == t0.TK_NUMBER:
            val = tok_value(toks, idx)
            emit(code, f"movq ${-val}, %rax")
            return idx + 1
        else:
            # General case: negate expression
            idx = parse_atom(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
            emit(code, "negq %rax")
            return idx
    
    raise SyntaxError(f"Unexpected token in expression: {t0.dump_token(toks[idx], src)} at {tok_loc(toks, idx)}")


def parse_expr(toks: list, idx: int, src: str, code: list, data: list,
               fn_table: list, scope_stack: list, global_table: list, const_table: list,
               ctx: dict, min_prec: int) -> int:
    """Parse expression with precedence validation. Result in rax."""
    
    # Parse left-hand side (atom or call expression)
    idx = parse_atom(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
    
    # Handle binary operators (left to right, validate precedence)
    while idx < len(toks):
        kind = tok_kind(toks, idx)
        
        # Check for expr call: )(
        if kind == t0.TK_EXPR_CALL:
            # Result of previous expression is function pointer in rax
            emit(code, "pushq %rax")  # Save function pointer
            idx = idx + 1
            
            # Parse arguments
            arg_count = 0
            while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_PAREN:
                idx = parse_expr(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx, 0)
                emit(code, "pushq %rax")
                arg_count = arg_count + 1
            
            idx = expect(toks, idx, t0.TK_RIGHT_PAREN, src)
            
            # Set up call - pop args to registers
            regs = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
            i = arg_count - 1
            while i >= 0:
                if i < 6:
                    emit(code, f"popq {regs[i]}")
                i = i - 1
            
            # Pop function pointer and call
            emit(code, "popq %rax")
            emit(code, "call *%rax")
            continue
        
        if not is_binop(kind):
            break
        
        prec = get_precedence(kind)
        
        # Check precedence: in left-to-right parsing, we error if precedence increases
        if prec > min_prec and min_prec > 0:
            raise SyntaxError(f"Operator precedence violation: use parentheses to clarify at position {tok_loc(toks, idx)}")
        
        idx = idx + 1
        
        # Save left operand
        emit(code, "pushq %rax")
        
        # Handle pipe specially - RHS is function to call with LHS as arg
        if kind == t0.TK_PIPE:
            # Parse RHS (should be function name or expression)
            idx = parse_atom(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
            # rax = function pointer, stack top = argument
            emit(code, "movq %rax, %r11")  # save fn ptr
            emit(code, "popq %rdi")        # arg1
            emit(code, "call *%r11")
        else:
            # Parse right operand
            idx = parse_atom(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
            
            # Pop left operand to rbx
            emit(code, "movq %rax, %rcx")  # right in rcx
            emit(code, "popq %rax")        # left in rax
            
            # Emit operation
            if kind == t0.TK_PLUS:
                emit(code, "addq %rcx, %rax")
            elif kind == t0.TK_MINUS:
                emit(code, "subq %rcx, %rax")
            elif kind == t0.TK_MUL:
                emit(code, "imulq %rcx, %rax")
            elif kind == t0.TK_IDIV:
                emit(code, "cqto")              # sign extend rax to rdx:rax
                emit(code, "idivq %rcx")        # rax = quotient
            elif kind == t0.TK_MOD:
                emit(code, "cqto")
                emit(code, "idivq %rcx")
                emit(code, "movq %rdx, %rax")   # remainder in rdx
            elif kind == t0.TK_LEFT_SHIFT:
                emit(code, "shlq %cl, %rax")
            elif kind == t0.TK_RIGHT_SHIFT:
                emit(code, "sarq %cl, %rax")    # arithmetic shift
            elif kind == t0.TK_AND:
                emit(code, "andq %rcx, %rax")
            elif kind == t0.TK_OR:
                emit(code, "orq %rcx, %rax")
            elif kind == t0.TK_XOR:
                emit(code, "xorq %rcx, %rax")
            elif kind == t0.TK_EQ:
                emit(code, "cmpq %rcx, %rax")
                emit(code, "sete %al")
                emit(code, "movzbq %al, %rax")
                emit(code, "negq %rax")         # 0 -> 0, 1 -> -1 (all 1s)
            elif kind == t0.TK_NOT_EQ:
                emit(code, "cmpq %rcx, %rax")
                emit(code, "setne %al")
                emit(code, "movzbq %al, %rax")
                emit(code, "negq %rax")
            elif kind == t0.TK_GT:
                emit(code, "cmpq %rcx, %rax")
                emit(code, "setg %al")
                emit(code, "movzbq %al, %rax")
                emit(code, "negq %rax")
            elif kind == t0.TK_LT:
                emit(code, "cmpq %rcx, %rax")
                emit(code, "setl %al")
                emit(code, "movzbq %al, %rax")
                emit(code, "negq %rax")
            elif kind == t0.TK_GT_EQ:
                emit(code, "cmpq %rcx, %rax")
                emit(code, "setge %al")
                emit(code, "movzbq %al, %rax")
                emit(code, "negq %rax")
            elif kind == t0.TK_LT_EQ:
                emit(code, "cmpq %rcx, %rax")
                emit(code, "setle %al")
                emit(code, "movzbq %al, %rax")
                emit(code, "negq %rax")
        
        min_prec = prec
    
    return idx

# ============================================================================
# Statement parsing
# ============================================================================

def skip_type_annotation(toks: list, idx: int) -> int:
    """Skip type annotation tokens (:type or :type<param> or <param>)"""
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
    """Skip function return type annotation (:>type or :>type<param>)"""
    if idx >= len(toks):
        return idx
    kind = tok_kind(toks, idx)
    if kind == t0.TK_FN_TYPE:
        idx = idx + 1
        if idx < len(toks) and tok_kind(toks, idx) == t0.TK_TYPE_PARAM:
            idx = idx + 1
    return idx


def parse_var_decl(toks: list, idx: int, src: str, code: list, data: list,
                   fn_table: list, scope_stack: list, global_table: list, const_table: list,
                   ctx: dict) -> int:
    """Parse variable declaration: let name:type = expr"""
    # Skip 'let' or 'const'
    idx = idx + 1
    
    # Get name
    if tok_kind(toks, idx) != t0.TK_IDENT:
        raise SyntaxError(f"Expected identifier after let, got {t0.dump_token(toks[idx], src)}")
    
    name_start = tok_name_start(toks, idx)
    name_len = tok_name_len(toks, idx)
    idx = idx + 1
    
    # Skip type annotation
    idx = skip_type_annotation(toks, idx)
    
    # Check for = (might not have initializer in some contexts, but we require it)
    if idx >= len(toks) or tok_kind(toks, idx) != t0.TK_ASSIGN:
        raise SyntaxError(f"Expected '=' in variable declaration at {tok_loc(toks, idx)}")
    idx = idx + 1
    
    # Parse initializer expression
    idx = parse_expr(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx, 0)
    
    # Allocate stack space and store
    offset = ctx["stack_offset"]
    ctx["stack_offset"] = offset - 8
    
    var_declare(scope_stack, name_start, name_len, offset)
    emit(code, f"movq %rax, {offset}(%rbp)")
    
    return idx


def parse_fn_decl(toks: list, idx: int, src: str, code: list, data: list,
                  fn_table: list, scope_stack: list, global_table: list, const_table: list,
                  ctx: dict) -> int:
    """Parse function declaration: let name = (args):>rettype => { body }"""
    # Skip 'let' or 'const'
    idx = idx + 1
    
    # Get name
    name_start = tok_name_start(toks, idx)
    name_len = tok_name_len(toks, idx)
    idx = idx + 1
    
    # Skip '='
    idx = expect(toks, idx, t0.TK_ASSIGN, src)
    
    # Skip '('
    idx = expect(toks, idx, t0.TK_LEFT_PAREN, src)
    
    # Parse parameters
    params = []  # list of (name_start, name_len)
    while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_PAREN:
        if tok_kind(toks, idx) != t0.TK_IDENT:
            raise SyntaxError(f"Expected parameter name, got {t0.dump_token(toks[idx], src)}")
        param_start = tok_name_start(toks, idx)
        param_len = tok_name_len(toks, idx)
        params.append((param_start, param_len))
        idx = idx + 1
        
        # Skip type annotation
        idx = skip_type_annotation(toks, idx)
    
    idx = expect(toks, idx, t0.TK_RIGHT_PAREN, src)
    
    # Skip return type annotation
    idx = skip_fn_type_annotation(toks, idx)
    
    # Skip '=>'
    idx = expect(toks, idx, t0.TK_FN_ARROW, src)
    
    # Skip '{'
    idx = expect(toks, idx, t0.TK_LEFT_BRACE, src)
    
    # Register or update function in table
    fn_idx = fn_lookup(fn_table, src, name_start, name_len)
    if fn_idx >= 0:
        # Update existing forward reference
        entry = fn_table[fn_idx]
        entry[3] = len(params)
        entry[4] = True
        label_id = entry[2]
    else:
        # New function
        label_id = ctx["next_label"]
        ctx["next_label"] = ctx["next_label"] + 1
        fn_declare(fn_table, name_start, name_len, label_id, len(params), True)
    
    # Generate function label
    fn_name = get_name(src, name_start, name_len)
    label = f".Lfn{label_id}"
    
    # Check for main function
    if fn_name == "main":
        emit_label(code, "__main__")
    emit_label(code, label)
    
    # Function prologue
    emit(code, "pushq %rbp")
    emit(code, "movq %rsp, %rbp")
    
    # Allocate space for local variables (fixed 256 bytes, 32 slots)
    # This comes BEFORE saving callee-saved registers so locals are at known offsets
    emit(code, "subq $256, %rsp")
    
    # Save callee-saved registers we might use (at fixed positions in local area)
    emit(code, "movq %rbx, -8(%rbp)")
    emit(code, "movq %r12, -16(%rbp)")
    emit(code, "movq %r13, -24(%rbp)")
    emit(code, "movq %r14, -32(%rbp)")
    emit(code, "movq %r15, -40(%rbp)")
    
    # Create new scope for function body
    push_scope(scope_stack)
    
    # Set up parameters as local variables
    # Args come in: rdi, rsi, rdx, rcx, r8, r9, then stack
    arg_regs = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
    stack_offset = -48  # Start locals at -48 (after saved regs area)
    
    i = 0
    while i < len(params):
        param_start, param_len = params[i]
        
        if i < 6:
            # Copy from register to stack
            emit(code, f"movq {arg_regs[i]}, {stack_offset}(%rbp)")
        else:
            # Copy from caller's stack frame
            caller_offset = 16 + (i - 6) * 8  # +16 for return addr and saved rbp
            emit(code, f"movq {caller_offset}(%rbp), %rax")
            emit(code, f"movq %rax, {stack_offset}(%rbp)")
        
        var_declare(scope_stack, param_start, param_len, stack_offset)
        stack_offset = stack_offset - 8
        i = i + 1
    
    # Save stack offset for local variables
    saved_stack_offset = ctx["stack_offset"]
    ctx["stack_offset"] = stack_offset
    
    # Save loop context
    saved_loop_start = ctx["loop_start_label"]
    saved_loop_end = ctx["loop_end_label"]
    ctx["loop_start_label"] = ""
    ctx["loop_end_label"] = ""
    
    # Set epilogue label for return statements
    saved_epilogue = ctx["current_fn_epilogue"]
    ctx["current_fn_epilogue"] = f".Lfn{label_id}_epilogue"
    
    # Parse function body
    while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACE:
        idx = parse_statement(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
    
    idx = expect(toks, idx, t0.TK_RIGHT_BRACE, src)
    
    # Implicit return (in case no explicit return)
    emit_label(code, f".Lfn{label_id}_epilogue")
    emit(code, "movq -8(%rbp), %rbx")
    emit(code, "movq -16(%rbp), %r12")
    emit(code, "movq -24(%rbp), %r13")
    emit(code, "movq -32(%rbp), %r14")
    emit(code, "movq -40(%rbp), %r15")
    emit(code, "movq %rbp, %rsp")
    emit(code, "popq %rbp")
    emit(code, "ret")
    
    # Restore context
    pop_scope(scope_stack)
    ctx["stack_offset"] = saved_stack_offset
    ctx["loop_start_label"] = saved_loop_start
    ctx["loop_end_label"] = saved_loop_end
    ctx["current_fn_epilogue"] = saved_epilogue
    
    return idx


def parse_if_stmnt(toks: list, idx: int, src: str, code: list, data: list,
                   fn_table: list, scope_stack: list, global_table: list, const_table: list,
                   ctx: dict) -> int:
    """Parse if statement: if expr { body } else if expr { body } else { body }"""
    # Generate labels
    end_label_id = ctx["next_label"]
    ctx["next_label"] = ctx["next_label"] + 1
    end_label = f".Lif_end{end_label_id}"
    
    else_label_id = ctx["next_label"]
    ctx["next_label"] = ctx["next_label"] + 1
    else_label = f".Lelse{else_label_id}"
    
    # Skip 'if'
    idx = idx + 1
    
    # Parse condition
    idx = parse_expr(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx, 0)
    
    # Test condition (check if any bit is set)
    emit(code, "testq %rax, %rax")
    emit(code, f"jz {else_label}")
    
    # Parse then block
    idx = expect(toks, idx, t0.TK_LEFT_BRACE, src)
    push_scope(scope_stack)
    
    while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACE:
        idx = parse_statement(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
    
    idx = expect(toks, idx, t0.TK_RIGHT_BRACE, src)
    pop_scope(scope_stack)
    
    emit(code, f"jmp {end_label}")
    emit_label(code, else_label)
    
    # Check for else if / else
    while idx < len(toks) and tok_kind(toks, idx) == t0.TK_ELSE:
        idx = idx + 1
        
        if idx < len(toks) and tok_kind(toks, idx) == t0.TK_IF:
            # else if
            idx = idx + 1
            
            else_label_id = ctx["next_label"]
            ctx["next_label"] = ctx["next_label"] + 1
            else_label = f".Lelse{else_label_id}"
            
            # Parse condition
            idx = parse_expr(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx, 0)
            emit(code, "testq %rax, %rax")
            emit(code, f"jz {else_label}")
            
            # Parse block
            idx = expect(toks, idx, t0.TK_LEFT_BRACE, src)
            push_scope(scope_stack)
            
            while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACE:
                idx = parse_statement(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
            
            idx = expect(toks, idx, t0.TK_RIGHT_BRACE, src)
            pop_scope(scope_stack)
            
            emit(code, f"jmp {end_label}")
            emit_label(code, else_label)
        else:
            # else block
            idx = expect(toks, idx, t0.TK_LEFT_BRACE, src)
            push_scope(scope_stack)
            
            while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACE:
                idx = parse_statement(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
            
            idx = expect(toks, idx, t0.TK_RIGHT_BRACE, src)
            pop_scope(scope_stack)
            break
    
    emit_label(code, end_label)
    return idx


def parse_loop_stmnt(toks: list, idx: int, src: str, code: list, data: list,
                     fn_table: list, scope_stack: list, global_table: list, const_table: list,
                     ctx: dict) -> int:
    """Parse loop statement: loop expr { body }"""
    # Generate labels
    start_label_id = ctx["next_label"]
    ctx["next_label"] = ctx["next_label"] + 1
    start_label = f".Lloop_start{start_label_id}"
    
    end_label_id = ctx["next_label"]
    ctx["next_label"] = ctx["next_label"] + 1
    end_label = f".Lloop_end{end_label_id}"
    
    # Save outer loop labels
    saved_start = ctx["loop_start_label"]
    saved_end = ctx["loop_end_label"]
    ctx["loop_start_label"] = start_label
    ctx["loop_end_label"] = end_label
    
    # Skip 'loop'
    idx = idx + 1
    
    # Loop start
    emit_label(code, start_label)
    
    # Parse condition
    idx = parse_expr(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx, 0)
    
    # Test condition
    emit(code, "testq %rax, %rax")
    emit(code, f"jz {end_label}")
    
    # Parse body
    idx = expect(toks, idx, t0.TK_LEFT_BRACE, src)
    push_scope(scope_stack)
    
    while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACE:
        idx = parse_statement(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
    
    idx = expect(toks, idx, t0.TK_RIGHT_BRACE, src)
    pop_scope(scope_stack)
    
    # Jump back to start
    emit(code, f"jmp {start_label}")
    emit_label(code, end_label)
    
    # Restore outer loop labels
    ctx["loop_start_label"] = saved_start
    ctx["loop_end_label"] = saved_end
    
    return idx


def parse_return_stmnt(toks: list, idx: int, src: str, code: list, data: list,
                       fn_table: list, scope_stack: list, global_table: list, const_table: list,
                       ctx: dict) -> int:
    """Parse return statement: return expr"""
    # Skip 'return'
    idx = idx + 1
    
    # Parse expression (result goes in rax)
    idx = parse_expr(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx, 0)
    
    # Jump to function epilogue
    emit(code, f"jmp {ctx['current_fn_epilogue']}")
    
    return idx


def parse_break_stmnt(toks: list, idx: int, src: str, code: list, data: list,
                      fn_table: list, scope_stack: list, global_table: list, const_table: list,
                      ctx: dict) -> int:
    """Parse break statement"""
    idx = idx + 1
    
    if ctx["loop_end_label"] == "":
        raise SyntaxError(f"break outside of loop at {tok_loc(toks, idx - 1)}")
    
    emit(code, f"jmp {ctx['loop_end_label']}")
    return idx


def parse_continue_stmnt(toks: list, idx: int, src: str, code: list, data: list,
                         fn_table: list, scope_stack: list, global_table: list, const_table: list,
                         ctx: dict) -> int:
    """Parse continue statement"""
    idx = idx + 1
    
    if ctx["loop_start_label"] == "":
        raise SyntaxError(f"continue outside of loop at {tok_loc(toks, idx - 1)}")
    
    emit(code, f"jmp {ctx['loop_start_label']}")
    return idx


def parse_assign_or_expr(toks: list, idx: int, src: str, code: list, data: list,
                         fn_table: list, scope_stack: list, global_table: list, const_table: list,
                         ctx: dict) -> int:
    """Parse assignment or expression statement"""
    # Check if this is identifier followed by = or update-assign
    if tok_kind(toks, idx) == t0.TK_IDENT:
        if idx + 1 < len(toks):
            next_kind = tok_kind(toks, idx + 1)
            
            if next_kind == t0.TK_ASSIGN:
                # Simple assignment
                name_start = tok_name_start(toks, idx)
                name_len = tok_name_len(toks, idx)
                idx = idx + 2  # skip ident and =
                
                # Parse RHS
                idx = parse_expr(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx, 0)
                
                # Find variable
                scope_idx, var_idx = var_lookup(scope_stack, src, name_start, name_len)
                if scope_idx >= 0:
                    entry = scope_stack[scope_idx][var_idx]
                    offset = entry[2]
                    emit(code, f"movq %rax, {offset}(%rbp)")
                else:
                    glob_idx = global_lookup(global_table, src, name_start, name_len)
                    if glob_idx >= 0:
                        entry = global_table[glob_idx]
                        label = f".Lglobal{entry[2]}"
                        emit(code, f"movq %rax, {label}(%rip)")
                    else:
                        raise SyntaxError(f"Undefined variable for assignment at {tok_loc(toks, idx)}")
                
                return idx
            
            elif next_kind == t0.TK_UPDATE_ASSIGN:
                # Update assignment (+=, -=, etc.)
                name_start = tok_name_start(toks, idx)
                name_len = tok_name_len(toks, idx)
                op_kind = tok_value(toks, idx + 1)  # The operator kind stored in value
                idx = idx + 2  # skip ident and op=
                
                # Find variable and load current value
                scope_idx, var_idx = var_lookup(scope_stack, src, name_start, name_len)
                if scope_idx >= 0:
                    entry = scope_stack[scope_idx][var_idx]
                    offset = entry[2]
                    var_loc = f"{offset}(%rbp)"
                else:
                    glob_idx = global_lookup(global_table, src, name_start, name_len)
                    if glob_idx >= 0:
                        entry = global_table[glob_idx]
                        var_loc = f".Lglobal{entry[2]}(%rip)"
                    else:
                        raise SyntaxError(f"Undefined variable for assignment at {tok_loc(toks, idx)}")
                
                # Load current value
                emit(code, f"movq {var_loc}, %rbx")
                emit(code, "pushq %rbx")
                
                # Parse RHS
                idx = parse_expr(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx, 0)
                
                # rax = RHS, pop old value to rbx
                emit(code, "movq %rax, %rcx")
                emit(code, "popq %rax")
                
                # Apply operation
                if op_kind == t0.TK_PLUS:
                    emit(code, "addq %rcx, %rax")
                elif op_kind == t0.TK_MINUS:
                    emit(code, "subq %rcx, %rax")
                elif op_kind == t0.TK_MUL:
                    emit(code, "imulq %rcx, %rax")
                elif op_kind == t0.TK_IDIV:
                    emit(code, "cqto")
                    emit(code, "idivq %rcx")
                elif op_kind == t0.TK_MOD:
                    emit(code, "cqto")
                    emit(code, "idivq %rcx")
                    emit(code, "movq %rdx, %rax")
                elif op_kind == t0.TK_LEFT_SHIFT:
                    emit(code, "shlq %cl, %rax")
                elif op_kind == t0.TK_RIGHT_SHIFT:
                    emit(code, "sarq %cl, %rax")
                elif op_kind == t0.TK_AND:
                    emit(code, "andq %rcx, %rax")
                elif op_kind == t0.TK_OR:
                    emit(code, "orq %rcx, %rax")
                elif op_kind == t0.TK_XOR:
                    emit(code, "xorq %rcx, %rax")
                
                # Store result
                emit(code, f"movq %rax, {var_loc}")
                return idx
    
    # Just an expression statement
    return parse_expr(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx, 0)


def parse_statement(toks: list, idx: int, src: str, code: list, data: list,
                    fn_table: list, scope_stack: list, global_table: list, const_table: list,
                    ctx: dict) -> int:
    """Parse a single statement, emit code, return new idx"""
    kind = tok_kind(toks, idx)
    
    if kind == t0.TK_LET:
        # Check if function declaration (look for '(' after ident and '=')
        if idx + 3 < len(toks):
            if tok_kind(toks, idx + 2) == t0.TK_ASSIGN and tok_kind(toks, idx + 3) == t0.TK_LEFT_PAREN:
                return parse_fn_decl(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
        return parse_var_decl(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
    
    if kind == t0.TK_IF:
        return parse_if_stmnt(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
    
    if kind == t0.TK_LOOP:
        return parse_loop_stmnt(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
    
    if kind == t0.TK_RETURN:
        return parse_return_stmnt(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
    
    if kind == t0.TK_BREAK:
        return parse_break_stmnt(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
    
    if kind == t0.TK_CONTINUE:
        return parse_continue_stmnt(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
    
    # Assignment or expression
    return parse_assign_or_expr(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)


def parse_program(toks: list, src: str, code: list, data: list,
                  fn_table: list, scope_stack: list, global_table: list, const_table: list,
                  ctx: dict) -> None:
    """Parse entire program (top-level statements)"""
    idx = 0
    
    while idx < len(toks):
        kind = tok_kind(toks, idx)
        
        # At top level, only allow function declarations and global variable declarations
        if kind == t0.TK_LET:
            # Check if function or variable
            if idx + 3 < len(toks):
                if tok_kind(toks, idx + 2) == t0.TK_ASSIGN and tok_kind(toks, idx + 3) == t0.TK_LEFT_PAREN:
                    idx = parse_fn_decl(toks, idx, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
                    continue
            
            # Global variable declaration
            idx = idx + 1  # skip let
            
            name_start = tok_name_start(toks, idx)
            name_len = tok_name_len(toks, idx)
            idx = idx + 1
            
            idx = skip_type_annotation(toks, idx)
            idx = expect(toks, idx, t0.TK_ASSIGN, src)
            
            # For globals, only allow constant expressions
            if tok_kind(toks, idx) == t0.TK_NUMBER:
                val = tok_value(toks, idx)
                idx = idx + 1
                
                # Add to const_table for compile-time array literal resolution
                const_declare(const_table, name_start, name_len, val)
                
                label_id = ctx["next_label"]
                ctx["next_label"] = ctx["next_label"] + 1
                global_declare(global_table, name_start, name_len, label_id)
                
                emit_data_label(data, f".Lglobal{label_id}")
                emit_data(data, f"    .quad {val}")
            elif tok_kind(toks, idx) == t0.TK_STRING:
                # String constant
                start = tok_loc(toks, idx)
                length = tok_value(toks, idx)
                str_content = src[start + 1 : start + length - 1]
                idx = idx + 1
                
                # Process escapes
                processed = []
                i = 0
                while i < len(str_content):
                    if str_content[i] == '\\' and i + 1 < len(str_content):
                        c = str_content[i + 1]
                        if c == 'n':
                            processed.append(10)
                        elif c == 't':
                            processed.append(9)
                        elif c == 'r':
                            processed.append(13)
                        # elif c == '\\':
                        #     processed.append(92)
                        # elif c == '"':
                        #     processed.append(34)
                        elif c == '0':
                            processed.append(0)
                        else:
                            processed.append(ord(c))
                        i = i + 2
                    else:
                        processed.append(ord(str_content[i]))
                        i = i + 1
                
                str_label_id = ctx["next_label"]
                ctx["next_label"] = ctx["next_label"] + 1
                
                emit_data_label(data, f".Lstr{str_label_id}")
                emit_data(data, f"    .quad {len(processed)}")
                if len(processed) > 0:
                    bytes_str = ", ".join([str(b) for b in processed])
                    emit_data(data, f"    .byte {bytes_str}")
                
                # Global holds pointer to string data
                label_id = ctx["next_label"]
                ctx["next_label"] = ctx["next_label"] + 1
                global_declare(global_table, name_start, name_len, label_id)
                
                emit_data_label(data, f".Lglobal{label_id}")
                emit_data(data, f"    .quad .Lstr{str_label_id}+8")
            elif tok_kind(toks, idx) == t0.TK_LEFT_BRACKET:
                # Array literal
                idx = idx + 1
                elements = []
                while idx < len(toks) and tok_kind(toks, idx) != t0.TK_RIGHT_BRACKET:
                    if tok_kind(toks, idx) == t0.TK_NUMBER:
                        elements.append(tok_value(toks, idx))
                        idx = idx + 1
                    elif tok_kind(toks, idx) == t0.TK_IDENT:
                        ns = tok_name_start(toks, idx)
                        nl = tok_name_len(toks, idx)
                        # Check const_table for identifier
                        found, val = const_lookup(const_table, src, ns, nl)
                        if found:
                            elements.append(val)
                        else:
                            raise SyntaxError(f"Only constant values in global array at {tok_loc(toks, idx)}")
                        idx = idx + 1
                    else:
                        raise SyntaxError(f"Only constant values in global array at {tok_loc(toks, idx)}")
                idx = expect(toks, idx, t0.TK_RIGHT_BRACKET, src)
                
                arr_label_id = ctx["next_label"]
                ctx["next_label"] = ctx["next_label"] + 1
                
                emit_data_label(data, f".Larr{arr_label_id}")
                emit_data(data, f"    .quad {len(elements)}")
                i = 0
                while i < len(elements):
                    emit_data(data, f"    .quad {elements[i]}")
                    i = i + 1
                
                label_id = ctx["next_label"]
                ctx["next_label"] = ctx["next_label"] + 1
                global_declare(global_table, name_start, name_len, label_id)
                
                emit_data_label(data, f".Lglobal{label_id}")
                emit_data(data, f"    .quad .Larr{arr_label_id}+8")
            else:
                raise SyntaxError(f"Global variables must have constant initializers at {tok_loc(toks, idx)}")
        else:
            raise SyntaxError(f"Only function and variable declarations allowed at top level, got {t0.dump_token(toks[idx], src)}")


# ============================================================================
# Main entry point
# ============================================================================

def parse(toks: list, src: str) -> str:
    """Parse tokens and generate x86_64 assembly"""
    
    # Output buffers
    code: list[str] = []
    data: list[str] = []
    
    # Symbol tables
    fn_table: list = []
    global_table: list = []
    const_table: list = []  # Const values for compile-time evaluation
    scope_stack: list = [[]]  # Start with global scope
    
    # Context for codegen
    ctx = {
        "next_label": 0,
        "stack_offset": -8,
        "loop_start_label": "",
        "loop_end_label": "",
        "current_fn_epilogue": "",
    }
    
    # Parse program
    parse_program(toks, src, code, data, fn_table, scope_stack, global_table, const_table, ctx)
    
    # Check for undefined forward references
    i = 0
    while i < len(fn_table):
        entry = fn_table[i]
        if not entry[4]:
            name = get_name(src, entry[0], entry[1])
            raise SyntaxError(f"Undefined function: {name}")
        i = i + 1
    
    # Assemble output
    output = []
    output.append(".text")
    output.append(".globl __main__")
    output.append("")
    output.extend(code)
    output.append("")
    output.append(".data")
    output.extend(data)
    output.append("")
    output.append(".section .note.GNU-stack,\"\",@progbits")
    output.append("")
    
    return "\n".join(output)


# ============================================================================
# CLI entry point
# ============================================================================

if __name__ == "__main__":
    import sys
    import subprocess
    from pathlib import Path
    
    if len(sys.argv) < 2:
        print("Usage: python -m src.udewy.p0 [-c] <file.udewy> [args...]")
        print("  -c    Compile only, don't run")
        sys.exit(1)
    
    compile_only = False
    arg_idx = 1
    
    if sys.argv[arg_idx] == "-c":
        compile_only = True
        arg_idx += 1
    
    if arg_idx >= len(sys.argv):
        print("Error: No input file specified")
        sys.exit(1)
    
    input_file = Path(sys.argv[arg_idx])
    script_args = sys.argv[arg_idx + 1:]
    
    src = input_file.read_text()
    toks = t0.tokenize(src)
    asm = parse(toks, src)
    
    cache_dir = Path("__dewycache__")
    cache_dir.mkdir(exist_ok=True)
    
    runtime_path = Path(__file__).parent / "runtime.s"
    asm_path = cache_dir / f"{input_file.stem}.s"
    obj_path = cache_dir / f"{input_file.stem}.o"
    runtime_obj_path = cache_dir / "runtime.o"
    exe_path = cache_dir / input_file.stem
    
    asm_path.write_text(asm)
    
    subprocess.run(["as", str(asm_path), "-o", str(obj_path)], check=True)
    subprocess.run(["as", str(runtime_path), "-o", str(runtime_obj_path)], check=True)
    subprocess.run(["ld", str(obj_path), str(runtime_obj_path), "-o", str(exe_path)], check=True)
    
    if compile_only:
        print(f"Compiled: {exe_path}")
    else:
        result = subprocess.run([str(exe_path)] + script_args)
        sys.exit(result.returncode)
