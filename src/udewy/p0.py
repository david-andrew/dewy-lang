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

def parse(toks:list[t0.PackedToken], backend=x84_64) -> str:
    # TODO: recursive descent parser for LL(1) grammar
    # minor complexity around throwing an error for expressions that increase in precedence level from left to right
    pdb.set_trace()

def parse_program(toks: list[t0.PackedToken], src:str, scope:Scope, fn_decls:list[FnDecl]):
    while len(toks) > 0:
        parse_statement(toks)

def parse_statement(toks: list[t0.PackedToken], src:str, scope:Scope, fn_decls:list[FnDecl]):
    if t0.kindof(toks[0]) == t0.TK_LET:
        parse_let_statement(toks, src, scope, fn_decls)
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
    for tok in toks:
        print(t0.dump_token(tok, src))