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
    PrototypeIdentifier, Express, Identifier, TypedIdentifier, TypedGroup, SequenceUnpackTarget, ObjectUnpackTarget, Assign,
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

"""after the main parsing, post parse to handle any remaining prototype asts within the main ast"""
import pdb


def post_parse(ast: AST) -> AST:

    ast = convert_prototype_identifiers(ast)

    # at the end of the post parse process
    if not ast.is_settled():
        raise ValueError(f'INTERNAL ERROR: Parse was incomplete. AST still has prototypes\n{ast!r}')

    return ast

#TODO: this is pretty inefficient memory-wise. more ideal would be in place conversions
def convert_prototype_identifiers(ast: AST) -> AST:
    match ast:
        case PrototypeIdentifier(name=name):
            return Express(Identifier(name))
        case Call(f=PrototypeIdentifier(name=name), args=args):
            return Call(Identifier(name), convert_prototype_identifiers(args) if args else None)
        case Group(items=items):
            return Group([convert_prototype_identifiers(i) for i in items])
        case Block(items=items):
            return Block([convert_prototype_identifiers(i) for i in items])
        case Assign(left=PrototypeIdentifier(name=name), right=right):
            return Assign(left=Identifier(name), right=convert_prototype_identifiers(right))
        case FunctionLiteral(args=args, body=body):
            return FunctionLiteral(convert_prototype_identifiers(args), convert_prototype_identifiers(body))
        case Void():
            return ast
        case Undefined():
            return ast
        case String():
            return ast
        case IString():
            return IString(parts=[convert_prototype_identifiers(i) for i in ast.parts])
        case _:
            raise NotImplementedError(f'conversion not handled for {type(ast)}')
    for i in ast:
        print(repr(i))

    pdb.set_trace()

    return ast
