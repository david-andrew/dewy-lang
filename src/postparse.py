from .syntax import (
    AST,
    Access,
    Declare,
    PointsTo, BidirPointsTo,
    Type,
    ListOfASTs, Tuple, Block, BareRange, Ellipsis, Spread, Array, Group, Range, Object, Dict, BidirDict, TypeParam,
    Void, Undefined, void, undefined, untyped,
    String, IString,
    Flowable, Flow, If, Loop, Default,
    FunctionLiteral, PrototypePyAction, PyAction, Call,
    Index,
    PrototypeIdentifier, Express, Identifier, TypedIdentifier, TypedGroup, UnpackTarget, Assign,
    Int, Bool,
    Range, IterIn,
    Less, LessEqual, Greater, GreaterEqual, Equal, MemberIn,
    LeftShift, RightShift, LeftRotate, RightRotate, LeftRotateCarry, RightRotateCarry,
    Add, Sub, Mul, Div, IDiv, Mod, Pow,
    And, Or, Xor, Nand, Nor, Xnor,
    Not, UnaryPos, UnaryNeg, UnaryMul, UnaryDiv,
    DeclarationType,
    DeclareGeneric, Parameterize,
)
from typing import Generator

"""after the main parsing, post parse to handle any remaining prototype asts within the main ast"""
import pdb


def post_parse(ast: AST) -> AST:

    # any conversions should probably run simplest to most complex
    ast = convert_prototype_tuples(ast)
    ast = convert_prototype_identifiers(ast)

    # at the end of the post parse process
    if not ast.is_settled():
        raise ValueError(f'INTERNAL ERROR: Parse was incomplete. AST still has prototypes\n{ast!r}')

    return ast


def convert_prototype_identifiers(ast: AST) -> AST:
    """Convert all PrototypeIdentifiers to either Identifier or Express, depending on the context"""
    ast = Group([ast])
    for i in (gen := ast.__full_traversal_iter__()):

        # skip ASTs that don't have any Prototypes
        if i.is_settled():
            continue

        match i:
            # if we ever get to a bare identifier, treat it like an express
            case PrototypeIdentifier(name=name):
                gen.send(Express(Identifier(name)))
            case Call(f=PrototypeIdentifier(name=name), args=args):
                gen.send(Call(Identifier(name), args))
            case Call(args=None): ...
            # case Call(args=): ... #TODO: handling when args is not none... generally will be a list of identifiers that need to be converted directly to Identifier
            case Call():
                pdb.set_trace()
                ...
            case Assign(left=PrototypeIdentifier(name=name), right=right):
                gen.send(Assign(Identifier(name), right))
            case Assign(left=Array() as arr, right=right):
                target = convert_prototype_to_unpack_target(arr)
                gen.send(Assign(target, right))
            case Assign():
                pdb.set_trace()
                ...
            case IterIn(left=PrototypeIdentifier(name=name), right=right):
                gen.send(IterIn(Identifier(name), right))
            case IterIn(left=Array() as arr, right=right):
                target = convert_prototype_to_unpack_target(arr)
                gen.send(IterIn(target, right))
            case IterIn():
                pdb.set_trace()
                ...
            case UnpackTarget():
                pdb.set_trace()
                ...
            case Declare():
                pdb.set_trace()
                ...
            case Index():
                pdb.set_trace()
                ...
            case Access():
                pdb.set_trace()
                ...

            # cases that themselves don't get adjusted but may contain nested children that need to be converted
            case IString() | Group() | Block() | Tuple() | Array() | Object() | Dict() | BidirDict() | FunctionLiteral() | Range() | Loop() | If() | Default() \
                | PointsTo() | BidirPointsTo() | Equal() | Less() | LessEqual() | Greater() | GreaterEqual() | LeftShift() | RightShift() | LeftRotate() | RightRotate() | LeftRotateCarry() | RightRotateCarry() | Add() | Sub() | Mul() | Div() | IDiv() | Mod() | Pow() | And() | Or() | Xor() | Nand() | Nor() | Xnor() | MemberIn() \
                | Not() | UnaryPos() | UnaryNeg() | UnaryMul() | UnaryDiv():
                ...
            #TBD cases: Type() | ListOfASTs() | BareRange() | Ellipsis() | Spread() | TypeParam() | Flowable() | Flow() | PrototypePyAction() | PyAction() | Express() | TypedIdentifier() | TypedGroup() | SequenceUnpackTarget() | ObjectUnpackTarget() | DeclarationType() | DeclareGeneric() | Parameterize():
            case _:  # all others are traversed as normal
                raise ValueError(f'Unhandled case {type(i)}')
            #     pdb.set_trace()
            #     ...

    return ast.items[0]


def convert_prototype_to_unpack_target(ast: Array) -> UnpackTarget:
    """Convert an Array of PrototypeIdentifiers or other ASTs to an UnpackTarget"""
    for i in (gen := ast.__full_traversal_iter__()):
        if i.is_settled():
            continue

        match i:
            case PrototypeIdentifier(name=name):
                gen.send(Identifier(name))
            case Assign(left=PrototypeIdentifier(name=name), right=right):
                gen.send(Assign(Identifier(name), right))
            case Array() as arr:
                gen.send(convert_prototype_to_unpack_target(arr))
            case Spread():
                gen.send(Spread())
            case TypedIdentifier():
                gen.send(i)
            case _:
                raise NotImplementedError(f'Unhandled case {type(i)} in convert_prototype_to_unpack_target')

    return UnpackTarget(ast.items)


def convert_prototype_tuples(ast: AST) -> AST:
    """For now, literally just turn all tuples into arrays"""
    ast = Group([ast])
    for i in (gen := ast.__full_traversal_iter__()):
        if isinstance(i, Tuple):
            gen.send(Array(i.items))
    return ast.items[0]