from . import t0
from .backend import x84_64, qbe, c

import pdb

type Address = int
type FnName = str
type NumArgs = int
type FnDecl = tuple[FnName, NumArgs, Address]

type VarName = str
type VarDecl = tuple[VarName, Address]
type Scope = tuple[list[VarDecl], Scope|None]

#TODO: probably get rid of structs since they add so much complexity / basically require type checking
"""
udewy Grammar:

program ::= statement*

statement ::= 
      fn_decl        # may only appear at the top level
    | var_decl
    | assign_stmnt
    | if_stmnt
    | loop_stmnt
    | break_stmnt
    | continue_stmnt
    | return_stmnt
    | expr

fn_decl ::= id '=' '(' (id type)* ')' fn_type '=>' '{' statement* '}'
var_decl ::= id type ('=' expr)?
assign_stmnt ::= (id '=' expr) | (id in_place_op expr)
if_stmnt ::= 'if' expr '{' statement* '}' else_if_stmnt* else_stmnt?
else_if_stmnt ::= 'else if' expr '{' statement* '}' else_if_stmnt* else_stmnt?
else_stmnt ::= 'else' '{' statement* '}'
loop_stmnt ::= 'loop' expr '{' statement* '}'
break_stmnt ::= 'break'
continue_stmnt ::= 'continue'
return_stmnt ::= 'return' expr   # expr is mandatory. use `void` if don't want to return anything

# note: expressions don't have precedence and are parsed left-associative. 
# Would be nice if parser could detect when this breaks precedence order of full dewy and emit an error
# e.g. `1 * 2 + 3` is fine, but `1 + 2 * 3` would throw an error
# perhaps we could keep a running min_precedence when parsing expr, and if any new operator has higher precedence, we error 
# note all of these operators have corresponding tokens from t0.py
expr ::=
    | (expr '+' expr)
    | (expr '-' expr)
    | (expr '*' expr)
    | (expr '//' expr)
    | (expr '%' expr)
    | (expr '>>' expr)
    | (expr '<<' expr)
    # note boolean operators are for both bitwise and logical operations. The representation of booleans is such that applying bitwise operations equates to logical operations
    # boolean formats are `true = 0xFFFF_FFFF_FFFF_FFFF` and `false = 0x0000_0000_0000_0000`
    | (expr 'and' expr)
    | (expr 'or' expr)
    | (expr 'xor' expr)
    | ('not' expr)
    | (expr '=?' expr)
    | (expr 'not=?' expr)
    | (expr '>?' expr)
    | (expr '<?' expr)
    | (expr '>=?' expr)
    | (expr '<=?' expr)
    | ('(' expr ')')
    | ('[' expr* ']')
    
    # calls
    | (expr '|>' expr)        # right expr is assumed to be a fn pointer
    | (ident_call expr* ')')
    | (expr expr_call expr* ')')
    
    # index
    | (expr ident_index expr* ']')
    
    # dot access
    | (expr ident_dot expr* '.')   # this converts to a regular index access using the named member's index in the struct declaration
    
    # basic atoms
    | id
    | num
    | '-' num
    | str

var_type_note ::= type | (type type_param) | type_param   # e.g. `:int` `:array<int>` `<int>` (in context examples: `x:int` `y:array<int>` `x<int>` `a<int|string>`)
fn_type_note ::= fn_type | (fn_type fn_type_param)        # e.g. `:>int` `:>array<int>` # udewy won't support `:> <arbitrary_type_block>` without some identifier in between, even though it would be a valid dewy type expression

# atoms from tokenization
id ::= [a-zA-Z_][a-zA-Z0-9_]*
num ::= [0-9]+ | '0x'[0-9a-fA-F]+ | '0b'[01]+ | 'true' | 'false'
str ::= '"' ( ~'"' | ('\'ξ) )* '"'   # note ξ is any ascii character (i.e. [0x09 0x0a 0x0d 0x20-0x7e])
type ::= ':' id
type_param ::= '<' (type or type expressions or etc) '>'  # inside is unchecked
fn_type ::= ':>' id
ident_call ::= id '('
expr_call ::= '('  # where prev was ')' (i.e. `(expr)(...)`)
ident_index ::= id '['
"""

def parse(toks:list[t0.PackedToken], backend=x84_64) -> str:
    # TODO: recursive descent parser for LL(1) grammar
    # minor complexity around throwing an error for expressions that increase in precedence level from left to right
    pdb.set_trace()

def parse_program(toks: list[t0.PackedToken], src:str, scope:Scope, fn_decls:list[FnDecl]):
    while len(toks) > 0:
        parse_statement(toks)

def parse_statement(toks: list[t0.PackedToken], idx:int, src:str, scope:Scope, fn_decls:list[FnDecl], is_root:bool=False):
    if t0.kindof(toks[idx]) == t0.TK_LET:
        assert idx + 1 < len(toks) and t0.kindof(toks[idx +1]) == t0.TK_IDENT, f"LET must be followed by an identifier. got {t0.dump_token(toks[idx+1], src)} at idx {idx+1}"
        if is_root and idx + 2 < len(toks) and t0.kindof(toks[idx + 2]) == t0.TK_ASSIGN:
            parse_fn_decl(toks, idx, src, scope, fn_decls)
        parse_var_decl(toks, idx, src, scope, fn_decls)
    elif t0.kindof(toks[0]) == t0.TK_IF:
        parse_if_statement(toks, src, scope, fn_decls)
    elif t0.kindof(toks[0]) == t0.TK_LOOP:
        parse_loop_statement(toks, src, scope, fn_decls)
    elif t0.kindof(toks[0]) == t0.TK_RETURN:
        parse_return_statement(toks, src, scope, fn_decls)
    elif t0.kindof(toks[0]) == t0.TK_BREAK:
        parse_break_statement(toks, src, scope, fn_decls)
    elif t0.kindof(toks[0]) == t0.TK_CONTINUE:
        parse_continue_statement(toks, src, scope, fn_decls)
    else: 
        parse_expression(toks, src, scope, fn_decls)




if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python t0.py <file>")
        sys.exit(1)
    with open(sys.argv[1], "r") as f:
        src = f.read()
    toks = t0.tokenize(src)
    ...