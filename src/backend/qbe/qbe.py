from ...tokenizer import tokenize
from ...postok import post_process
from ...dtypes import (
    Scope as DTypesScope,
    typecheck_call, typecheck_index, typecheck_multiply,
    register_typeof, short_circuit,
    CallableBase, IndexableBase, IndexerBase, MultipliableBase, ObjectBase,
)
from ...parser import top_level_parse, QJux
from ...syntax import (
    AST,
    Type, TypeParam,
    PointsTo, BidirPointsTo,
    ListOfASTs, PrototypeTuple, Block, Array, Group, Range, ObjectLiteral, Dict, BidirDict, UnpackTarget,
    TypedIdentifier,
    Void, void, Undefined, undefined, untyped,
    String, IString,
    Flowable, Flow, If, Loop, Default,
    Identifier, Express, Declare,
    PrototypePyAction, Call, Access, Index,
    Assign,
    Int, Bool,
    Range, IterIn,
    BinOp,
    Less, LessEqual, Greater, GreaterEqual, Equal, MemberIn,
    LeftShift, RightShift, LeftRotate, RightRotate, LeftRotateCarry, RightRotateCarry,
    Add, Sub, Mul, Div, IDiv, Mod, Pow,
    And, Or, Xor, Nand, Nor, Xnor,
    UnaryPrefixOp, UnaryPostfixOp,
    Not, UnaryPos, UnaryNeg, UnaryMul, UnaryDiv, AtHandle,
    CycleLeft, CycleRight, Suppress,
    BroadcastOp,
    CollectInto, SpreadOutFrom,
)

from ...postparse import post_parse, FunctionLiteral, Signature, normalize_function_args
from ...utils import Options

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast, Callable as TypingCallable, Any, Generic
from functools import cache
from collections import defaultdict
from types import SimpleNamespace


import pdb



from pathlib import Path
from ...utils import Options

# command to compile a .qbe file to an executable
# qbe <file>.ssa | gcc -x assembler -static -o hello 

def qbe_compiler(path: Path, args: list[str], options: Options) -> None:
    # get the source code and tokenize
    src = path.read_text()
    tokens = tokenize(src)
    post_process(tokens)

    # parse tokens into AST
    ast = top_level_parse(tokens)
    ast = post_parse(ast)

    # debug printing
    if options.verbose:
        print(repr(ast))

    # run the program
    ssa = top_level_compile(ast)
    print(ssa)



def top_level_compile(ast: AST) -> str:
    pdb.set_trace()
    ...