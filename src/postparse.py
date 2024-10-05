"""after the main parsing, post parse to handle any remaining prototype asts within the main ast"""

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
    PrototypeFunctionLiteral, PrototypePyAction, Call,
    Index,
    PrototypeIdentifier, Express, Identifier, TypedIdentifier, TypedGroup, UnpackTarget, Assign,
    Int, Bool,
    Range, IterIn,
    Less, LessEqual, Greater, GreaterEqual, Equal, MemberIn,
    LeftShift, RightShift, LeftRotate, RightRotate, LeftRotateCarry, RightRotateCarry,
    Add, Sub, Mul, Div, IDiv, Mod, Pow,
    And, Or, Xor, Nand, Nor, Xnor,
    Not, UnaryPos, UnaryNeg, UnaryMul, UnaryDiv, AtHandle,
    DeclarationType,
    DeclareGeneric, Parameterize,
)

from typing import Callable as TypingCallable

import pdb


# basically just convert all the different types of args to a normalized format (i.e. group)
class FunctionLiteral(AST):
    args: Group
    body: AST

    def __str__(self):
        return f'{self.args} => {self.body}'



def post_parse(ast: AST) -> AST:

    # any conversions should probably run simplest to most complex
    ast = convert_prototype_tuples(ast)
    ast = convert_bare_ranges(ast)
    ast = convert_prototype_function_literals(ast)
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

        # if we ever get to a bare identifier, treat it like an express
        if isinstance(i, PrototypeIdentifier):
            gen.send(Express(Identifier(i.name)))
            continue

        match i:
            case Call(f=PrototypeIdentifier(name=name), args=args):
                gen.send(Call(Identifier(name), args))
            case Call(args=None) | Call(f=AtHandle()): ...
            # case Call(args=args): ... #TODO: handling when args is not none... generally will be a list of identifiers that need to be converted directly to Identifier
            case Call():
                pdb.set_trace()
                ...
            case AtHandle(operand=PrototypeIdentifier(name=name)):
                gen.send(AtHandle(Identifier(name)))
            case AtHandle():
                pdb.set_trace()
                ...
            case FunctionLiteral(args=Group(items=items), body=body):
                converted_args = convert_prototype_to_unpack_target(Array(items))
                gen.send(FunctionLiteral(Group(converted_args.target), body))
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
            case UnpackTarget(): #TODO: may not need this one
                pdb.set_trace()
                ...
            case Declare(decltype=decltype, target=PrototypeIdentifier(name=name)):
                gen.send(Declare(decltype, Identifier(name)))
            case Declare(decltype=decltype, target=Array() as arr):
                pdb.set_trace()
                ...
            case Declare(decltype=decltype, target=Group() as group):
                pdb.set_trace()
                ...
            case Declare(): ... # all other declare cases are handled as normal
            case Index():
                pdb.set_trace()
                ...
            case Access():
                pdb.set_trace()
                ...

            # cases that themselves don't get adjusted but may contain nested children that need to be converted
            case IString() | Group() | Block() | Tuple() | Array() | Object() | Dict() | BidirDict() | FunctionLiteral() | Range() | Loop() | If() | Flow() | Default() \
                | PointsTo() | BidirPointsTo() | Equal() | Less() | LessEqual() | Greater() | GreaterEqual() | LeftShift() | RightShift() | LeftRotate() | RightRotate() | LeftRotateCarry() | RightRotateCarry() | Add() | Sub() | Mul() | Div() | IDiv() | Mod() | Pow() | And() | Or() | Xor() | Nand() | Nor() | Xnor() | MemberIn() \
                | Not() | UnaryPos() | UnaryNeg() | UnaryMul() | UnaryDiv() \
                | TypedIdentifier():
                ...
            #TBD cases: Type() | ListOfASTs() | BareRange() | Ellipsis() | Spread() | TypeParam() | Flowable() | Flow() | PrototypePyAction() | PyAction() | Express() | TypedGroup() | SequenceUnpackTarget() | ObjectUnpackTarget() | DeclarationType() | DeclareGeneric() | Parameterize():
            case _:  # all others are traversed as normal
                raise ValueError(f'Unhandled case {type(i)}')
            #     pdb.set_trace()
            #     ...

    return ast.items[0]

#TODO: maybe have one of these for Array, Object, Dict, BidirDict depending on what is to be unpacked
#      hard though because also requires the type of whatever is being unpacked
#      because array unpack and object unpack can look the same syntactically
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
            case Spread(): ...
            case TypedIdentifier(): ...
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

def convert_bare_ranges(ast: AST) -> AST:
    """Convert all BareRanges to Ranges with inclusive bounds"""
    ast = Group([ast])
    for i in (gen := ast.__full_traversal_iter__()):
        if isinstance(i, BareRange):
            gen.send(Range(i.left, i.right, '[]'))
    return ast.items[0]


def convert_prototype_function_literals(ast: AST) -> AST:
    ast = Group([ast])
    for i in (gen := ast.__full_traversal_iter__()):
        if isinstance(i, PrototypeFunctionLiteral):
            args = normalize_function_args(i.args)
            gen.send(FunctionLiteral(args, i.body))
    return ast.items[0]


def normalize_function_args(signature: AST) -> Group:
    """Convert all the different function arg syntax options to a normalized format (group)"""
    match signature:
        case Void():
            return Group([])
        case Identifier() | PrototypeIdentifier() | TypedIdentifier() | Assign():
            return Group([signature])
        case Spread() | UnpackTarget():
            pdb.set_trace()
            ...
        case Array(items):
            assert all(isinstance(i, (Identifier, PrototypeIdentifier, TypedIdentifier, Assign, Spread, UnpackTarget)) for i in items), f'Unpack Function args must all be one of Identifier(), TypedIdentifier(), Assign(), Spread(), or UnpackTarget(). Got {items}'
            return Group([UnpackTarget(items)])
        case Group() as group:
            return group
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'normalize_signature not implemented yet for {signature=}')