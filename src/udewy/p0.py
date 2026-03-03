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

def parse_program(toks: list[t0.PackedToken], scope:Scope, fn_decls:list[FnDecl]):
    while len(toks) > 0:
        parse_statement(toks)

def parse_statement(toks: list[t0.PackedToken]):
    ...

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