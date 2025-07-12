"""after the main parsing, post parse to handle any remaining prototype asts within the main ast"""

from .syntax import (
    AST,
    Access,
    Declare,
    PointsTo, BidirPointsTo,
    Type,
    ListOfASTs, PrototypeTuple, Block, BareRange, Ellipsis, DotDotDot, CollectInto, SpreadOutFrom, Array, Group, Range, ObjectLiteral, Dict, BidirDict, TypeParam,
    Untyped,
    Void, Undefined, void, undefined, untyped,
    String, IString,
    Flowable, Flow, If, Loop, Default,
    PrototypeFunctionLiteral, PrototypeBuiltin, Call,
    Index,
    PrototypeIdentifier, Express, Identifier, TypedIdentifier, ReturnTyped, SubTyped, UnpackTarget, Assign,
    Int, Bool,
    Range, IterIn,
    Less, LessEqual, Greater, GreaterEqual, Equal, MemberIn,
    LeftShift, RightShift, LeftRotate, RightRotate, LeftRotateCarry, RightRotateCarry,
    Add, Sub, Mul, Div, IDiv, Mod, Pow,
    And, Or, Xor, Nand, Nor, Xnor,
    Not, UnaryPos, UnaryNeg, UnaryMul, UnaryDiv, AtHandle,
    CycleLeft, CycleRight, Suppress,
    BroadcastOp,
    DeclarationType,
    MakeGeneric, Parameterize,
)
from .parser import QJux

from typing import Callable as TypingCallable
from dataclasses import field
import pdb


class Signature(AST):
    pkwargs: list[AST] = field(default_factory=list)
    pargs:   list[AST] = field(default_factory=list)
    kwargs:  list[AST] = field(default_factory=list)
    #TODO: probably keep track of spread args i.e. "spargs"
    rettype: AST = field(default=untyped)

    def _is_delimited(self) -> bool:
        n_args = len(self.pkwargs) + len(self.pargs) + len(self.kwargs)
        if n_args > 1 or n_args == 0:
            return False
        if any(isinstance(i, Assign) for i in self.pkwargs):
            return False
        if len(self.pargs) > 0 or len(self.kwargs) > 0:
            return False
        return True

    def __str__(self):
        pkwargs = ' '.join(str(i) for i in self.pkwargs)
        pargs   = ' '.join(str(i) for i in self.pargs)
        kwargs  = ' '.join(str(i) for i in self.kwargs)
        rettype = f' :> {self.rettype}' if self.rettype is not untyped else ''

        if pargs:
            pargs = f' #pos_only {pargs}'
        if kwargs:
            kwargs = f' #kw_only {kwargs}'

        s = f'{pkwargs}{pargs}{kwargs}'.lstrip()

        if self._is_delimited():
            return f'{s}{rettype}'
        return f'({s}){rettype}'


# basically just convert all the different types of args to a normalized format (i.e. group)
class FunctionLiteral(AST):
    args: Signature
    body: AST
    return_type: AST = field(default_factory=lambda: untyped)

    def __str__(self):
        if self.return_type is untyped:
            return f'{self.args} => {self.body}'
        return f'{self.args}:>{self.return_type} => {self.body}'



def post_parse(ast: AST) -> AST:

    # any conversions should probably run simplest to most complex
    ast = convert_prototype_tuples(ast)
    ast = convert_bare_ranges(ast)
    ast = convert_bare_ellipses(ast)
    ast = convert_bare_flows(ast)
    ast = convert_prototype_function_literals(ast)
    ast = convert_prototype_identifiers(ast)

    # at the end of the post parse process
    if not ast.is_settled():
        raise ValueError(f'INTERNAL ERROR: Parse was incomplete. AST still has prototypes\n{ast!r}')

    return ast


def convert_prototype_identifiers(ast: AST) -> AST:
    """Convert all PrototypeIdentifiers to either Identifier or Express, depending on the context"""
    ast = Group([ast])
    for i in (gen := ast.__iter_asts_full_traversal__(visit_replacement=False)):

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
            case Call(args=None) | Call(f=AtHandle()) | Call(f=Group()): ...
            # case Call(args=args): ... #TODO: handling when args is not none... generally will be a list of identifiers that need to be converted directly to Identifier
            case Call():
                pdb.set_trace()
                ...
            case AtHandle(operand=PrototypeIdentifier(name=name)):
                gen.send(AtHandle(Identifier(name)))
            case AtHandle():
                pdb.set_trace()
                ...
            case Assign(left=PrototypeIdentifier(name=name), right=right):
                gen.send(Assign(Identifier(name), right))
            case Assign(left=Array() as arr, right=right):
                target = convert_prototype_to_unpack_target(arr)
                gen.send(Assign(target, right))
            case Assign(left=Group() as group, right=right):
                target = convert_prototype_to_unpack_target(group)
                gen.send(Assign(target, right))
            case Assign(left=ObjectLiteral() as obj, right=right):
                target = convert_prototype_to_unpack_target(obj)
                gen.send(Assign(target, right))
            case Assign(left=TypedIdentifier(id=_id, type=_type)): ... #typed identifiers are already converted
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
            case Index(): ... # I think all index cases are handled as normal
            case Access(left=left, right=PrototypeIdentifier(name=name)):
                gen.send(Access(left, Identifier(name)))
            case Access(left=left, right=AtHandle(operand=PrototypeIdentifier(name=name))):
                gen.send(Access(left, AtHandle(Identifier(name))))
            case Access():
                pdb.set_trace()
                ...

            # cases that themselves don't get adjusted but may contain nested children that need to be converted
            case IString() | Group() | Block() | PrototypeTuple() | Array() | ObjectLiteral() | Dict() | BidirDict() | FunctionLiteral() | Signature() | Range() | Loop() | If() | Flow() | Default() \
                | PointsTo() | BidirPointsTo() | Equal() | Less() | LessEqual() | Greater() | GreaterEqual() | LeftShift() | RightShift() | LeftRotate() | RightRotate() | LeftRotateCarry() | RightRotateCarry() | Add() | Sub() | Mul() | Div() | IDiv() | Mod() | Pow() | And() | Or() | Xor() | Nand() | Nor() | Xnor() | MemberIn() \
                | BroadcastOp() | SpreadOutFrom() | QJux() \
                | Not() | UnaryPos() | UnaryNeg() | UnaryMul() | UnaryDiv() | CycleLeft() | CycleRight() \
                | TypedIdentifier() | ReturnTyped() | SubTyped() | MakeGeneric() | Parameterize() | TypeParam() | Suppress():
                ...
            #TBD cases: Type() | ListOfASTs() | BareRange() | Ellipsis() | Spread() | TypeParam() | Flowable() | Flow() | PrototypeBuiltin() | Builtin() | Express() | ReturnTyped() | SequenceUnpackTarget() | ObjectUnpackTarget() | DeclarationType() | DeclareGeneric() | Parameterize():
            case _:  # all others are traversed as normal
                pdb.set_trace()
                raise ValueError(f'Unhandled case {type(i)}')
            #     pdb.set_trace()
            #     ...

    return ast.items[0]

#TODO: maybe have one of these for Array, Object, Dict, BidirDict depending on what is to be unpacked
#      hard though because also requires the type of whatever is being unpacked
#      because array unpack and object unpack can look the same syntactically
def convert_prototype_to_unpack_target(ast: Array|Group|ObjectLiteral) -> UnpackTarget:
    """Convert an Array of PrototypeIdentifiers or other ASTs to an UnpackTarget"""
    for i in (gen := ast.__iter_asts_full_traversal__()):
        if i.is_settled():
            continue

        match i:
            case PrototypeIdentifier(name=name):
                gen.send(Identifier(name))
            case Assign(left=PrototypeIdentifier(name=name), right=right):
                gen.send(Assign(Identifier(name), right))
            case Assign(left=Array() as arr, right=right):
                target = convert_prototype_to_unpack_target(arr)
                gen.send(Assign(target, right))
            case Assign(left=Group() as group, right=right):
                target = convert_prototype_to_unpack_target(group)
                gen.send(Assign(target, right))
            case Assign(left=ObjectLiteral() as obj, right=right):
                target = convert_prototype_to_unpack_target(obj)
                gen.send(Assign(target, right))
            case Array() as arr:
                gen.send(convert_prototype_to_unpack_target(arr))
            case CollectInto(): ...
            case TypedIdentifier(): ...
            case _:
                raise NotImplementedError(f'Unhandled case {type(i)} in convert_prototype_to_unpack_target')

    return UnpackTarget(ast.items)


def convert_prototype_tuples(ast: AST) -> AST:
    """For now, literally just turn all tuples into groups"""
    ast = Group([ast])
    for i in (gen := ast.__iter_asts_full_traversal__()):
        if isinstance(i, PrototypeTuple):
            gen.send(Group(i.items))
    return ast.items[0]

def convert_bare_ranges(ast: AST) -> AST:
    """Convert all BareRanges to Ranges with inclusive bounds"""
    ast = Group([ast])
    for i in (gen := ast.__iter_asts_full_traversal__()):
        if isinstance(i, BareRange):
            gen.send(Range(i.left, i.right, '[]'))
    return ast.items[0]


def convert_bare_ellipses(ast: AST) -> AST:
    """Convert all remaining DotDotDots (that were not juxtaposed) to Ellipsis"""
    ast = Group([ast])
    for i in (gen := ast.__iter_asts_full_traversal__()):
        if isinstance(i, DotDotDot):
            gen.send(Ellipsis())
    return ast.items[0]


def convert_bare_flows(ast: AST) -> AST:
    ast = Group([ast])
    for i in (gen := ast.__iter_asts_full_traversal__()):
        if isinstance(i, Flow):
            # this is the lazy/hacky way to do it
            for branch in i.branches:
                branch._is_in_flowable = True
        if isinstance(i, Flowable):
            if not hasattr(i, '_is_in_flowable'):
                i._is_in_flowable = True
                gen.send(Flow([i]))

    return ast.items[0]


def convert_prototype_function_literals(ast: AST) -> AST:
    ast = Group([ast])
    for i in (gen := ast.__iter_asts_full_traversal__()):
        if isinstance(i, PrototypeFunctionLiteral):
            args = normalize_function_args(i.args)
            gen.send(FunctionLiteral(args, i.body))
    return ast.items[0]


def normalize_function_arg(arg: AST) -> tuple[list[AST], list[AST], list[AST]]:
    pkwarg, parg, kwarg = [], [], []
    match arg:
        case Void(): ...
        case PrototypeIdentifier(name=name):
            pkwarg.append(Identifier(name))
        case Identifier() | TypedIdentifier() | Assign():
            pkwarg.append(arg)
        case Array() as arr:
            pdb.set_trace()
            parg.append(convert_prototype_to_unpack_target(arr))
        # case Spread() | UnpackTarget():
        #     pdb.set_trace()
        #     ...
        # case Dict() | BidirDict():
        #     pdb.set_trace()
        #     ...
        #     #copilot suggested these could be kwargs, though I suspect it won't work (i.e. how is default vs no default handled? name -> void)
        #     #think about though. could use identifiers directly instead of strings

        case _:
            pdb.set_trace()
            raise NotImplementedError(f'normalize_signature not implemented yet for {arg=}')

    return pkwarg, parg, kwarg


# def array_items_to_unpack_target(items: list[AST]) -> UnpackTarget:
#     """Convert an Array of ASTs to an UnpackTarget"""
#     unpack_items = []
#     for i in items:
#         match i:
#             case Identifier() | PrototypeIdentifier() | TypedIdentifier() | Assign() | Spread() | UnpackTarget():
#                 unpack_items.append(i)
#             case Array(items):
#                 unpack_items.append(array_items_to_unpack_target(items))
#             case _:
#                 raise NotImplementedError(f'array_items_to_unpack_target not implemented yet for {i=}')
#     return UnpackTarget(unpack_items)


def normalize_function_args(signature: AST) -> Signature:
    """Convert all the different function arg syntax options to a normalized format (group)"""

    # if return type specified, strip off of signature so we can process the args separately
    rettype = untyped
    if isinstance(signature, ReturnTyped):
        signature, rettype = signature.left, signature.right

    # non-grouped arguments count as the whole signature
    if not isinstance(signature, Group):
        signature = Group([signature])
    #     return Signature(*normalize_function_arg(signature), rettype)

    # process each argument
    pkwargs, pargs, kwargs = [], [], []
    for i in signature.items:
        pkw, p, kw = normalize_function_arg(i)
        pkwargs.extend(pkw)
        pargs.extend(p)
        kwargs.extend(kw)

    return Signature(pkwargs, pargs, kwargs, rettype)
