from ..postparse import post_parse
from ..tokenizer import tokenize
from ..postok import post_process
from ..parser import top_level_parse, Scope as ParserScope
from ..syntax import (
    AST,
    Type,
    PointsTo, BidirPointsTo,
    ListOfASTs, Tuple, Block, Array, Group, Range, Object, Dict, BidirDict, UnpackTarget,
    TypedIdentifier,
    Void, void, Undefined, undefined,
    String, IString,
    Flowable, Flow, If, Loop, Default,
    PrototypeIdentifier, Identifier, Express,
    FunctionLiteral, PrototypePyAction, PyAction, Call,
    Assign,
    Int, Bool,
    Range, IterIn,
    Less, LessEqual, Greater, GreaterEqual, Equal, MemberIn,
    LeftShift, RightShift, LeftRotate, RightRotate, LeftRotateCarry, RightRotateCarry,
    Add, Sub, Mul, Div, IDiv, Mod, Pow,
    And, Or, Xor, Nand, Nor, Xnor,
    Not, UnaryPos, UnaryNeg, UnaryMul, UnaryDiv,
    # DeclarationType,
)

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast, Callable, Any
from functools import cache
from collections import defaultdict
from types import SimpleNamespace

import pdb



def python_interpreter(path: Path, args: list[str]):

    with open(path) as f:
        src = f.read()

    tokens = tokenize(src)
    post_process(tokens)

    ast = top_level_parse(tokens)
    ast = post_parse(ast)

    #TODO: put these under a verbose/etc. flag
    print_ast(ast)
    print(repr(ast))
    # from ..postparse import traverse_ast
    # for parent, child in traverse_ast(ast):
    #     print(f'{parent=},\n||||{child=}')
    # pdb.set_trace()

    res = top_level_evaluate(ast)
    if res is not void:
        print(res)

def print_ast(ast: AST):
    """little helper function to print out the equivalent source code of an AST"""
    print('```dewy')
    if isinstance(ast, (Block, Group)):
        for i in ast.__iter_asts__(): print(i)
    else:
        print(ast)
    print('```')


def top_level_evaluate(ast:AST) -> AST:
    scope = Scope.default()
    insert_pyactions(scope)
    return evaluate(ast, scope)


############################ Runtime helper classes ############################

class MetaNamespace(SimpleNamespace):
    """A simple namespace for storing AST meta attributes for use at runtime"""
    def __getattribute__(self, key: str) -> Any | None:
        """Get the attribute associated with the key, or None if it doesn't exist"""
        try:
            return super().__getattribute__(key)
        except AttributeError:
            return None

    def __setattr__(self, key: str, value: Any) -> None:
        """Set the attribute associated with the key"""
        super().__setattr__(key, value)


class MetaNamespaceDict:
    def __init__(self):
        self._dict = defaultdict(MetaNamespace)

    def __getitem__(self, item: AST) -> Any | None:
        key = f'::{item.__class__.__name__}@{hex(id(item))}'
        return self._dict[key]

    def __setitem__(self, key: AST, value: Any) -> None:
        key = f'::{key.__class__.__name__}@{hex(id(key))}'
        self._dict[key] = value

    def __str__(self):
        return str(self._dict)

    def __repr__(self):
        return repr(self._dict)


@dataclass
class Scope(ParserScope):
    """An extension of the Scope used during parsing to support runtime"""
    meta: dict[AST, MetaNamespace] = field(default_factory=MetaNamespaceDict)


class Iter(AST):
    item: AST
    i: int

    def __str__(self):
        return f'Iter({self.item}, i={self.i})'


############################ Evaluation functions ############################

class EvalFunc[T](Protocol):
    def __call__(self, ast: T, scope: Scope) -> AST: ...


def no_op[T](ast: T, scope: Scope) -> T:
    """For ASTs that just return themselves when evaluated"""
    return ast

def cannot_evaluate(ast: AST, scope: Scope) -> AST:
    raise ValueError(f'INTERNAL ERROR: evaluation of type {type(ast)} is not possible')


@cache
def get_eval_fn_map() -> dict[type[AST], EvalFunc]:
    return {
        Call: evaluate_call,
        Block: evaluate_block,
        Group: evaluate_group,
        Array: evaluate_array,
        Dict: evaluate_dict,
        PointsTo: evaluate_points_to,
        BidirDict: evaluate_bidir_dict,
        BidirPointsTo: evaluate_bidir_points_to,
        Assign: evaluate_assign,
        IterIn: evaluate_iter_in,
        FunctionLiteral: evaluate_function_literal,
        Closure: evaluate_closure,
        PyAction: evaluate_pyaction,
        String: no_op,
        IString: evaluate_istring,
        Identifier: cannot_evaluate,
        Express: evaluate_express,
        Int: no_op,
        Bool: no_op,
        Range: no_op,
        If: evaluate_if,
        Loop: evaluate_loop,
        Less: evaluate_less,
        Equal: evaluate_equal,
        And: evaluate_and,
        Or: evaluate_or,
        Not: evaluate_not,
        Add: evaluate_add,
        Mul: evaluate_mul,
        Mod: evaluate_mod,
        Undefined: no_op,
        #TODO: other AST types here
    }

def evaluate(ast:AST, scope:Scope) -> AST:
    eval_fn_map = get_eval_fn_map()

    ast_type = type(ast)
    if ast_type in eval_fn_map:
        return eval_fn_map[ast_type](ast, scope)

    raise NotImplementedError(f'evaluation not implemented for {ast_type}')



def evaluate_call(ast: Call, scope: Scope) -> AST:
    f = ast.f
    if isinstance(f, Group):
        f = evaluate(f, scope)
    if isinstance(f, Identifier):
        f = scope.get(f.name).value
    assert isinstance(f, (PyAction, Closure)), f'expected Function or PyAction, got {f}'

    if isinstance(f, PyAction):
        args, kwargs = collect_args(ast.args, scope)
        return f.action(*args, **kwargs, scope=scope)

    if isinstance(f, Closure):
        args, kwargs = collect_args(ast.args, scope)
        return evaluate(f.fn.body, f.scope)

    pdb.set_trace()
    raise NotImplementedError(f'Function evaluation not implemented yet')

def collect_args(args: AST | None, scope: Scope) -> tuple[list[AST], dict[str, AST]]:
    match args:
        case None: return [], {}
        case Identifier(name): return [scope.get(name).value], {}
        case Assign(): raise NotImplementedError('Assign not implemented yet')
        # case Tuple(items): raise NotImplementedError('Tuple not implemented yet')
        case String() | IString(): return [args], {}
        case Group(items): return [evaluate(i, scope) for i in items], {}
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'collect_args not implemented yet for {args}')


    raise NotImplementedError(f'collect_args not implemented yet for {args}')

def evaluate_group(ast: Group, scope: Scope):

    expressed: list[AST] = []
    for expr in ast.items:
        res = evaluate(expr, scope)
        if res is not void:
            expressed.append(res)
    if len(expressed) == 0:
        return void
    if len(expressed) == 1:
        return expressed[0]
    raise NotImplementedError(f'Block with multiple expressions not yet supported. {ast=}, {expressed=}')


def evaluate_block(ast: Block, scope: Scope):
    scope = Scope(scope)
    return evaluate_group(Group(ast.items), scope)

def evaluate_array(ast: Array, scope: Scope) -> Array:
    return Array([evaluate(i, scope) for i in ast.items])

def evaluate_dict(ast: Dict, scope: Scope) -> Dict:
    return Dict([evaluate(kv, scope) for kv in ast.items])

def evaluate_points_to(ast: PointsTo, scope: Scope) -> PointsTo:
    return PointsTo(evaluate(ast.left, scope), evaluate(ast.right, scope))

def evaluate_bidir_dict(ast: BidirDict, scope: Scope) -> BidirDict:
    return BidirDict([BidirPointsTo(evaluate(kv, scope)) for kv in ast.items])

def evaluate_bidir_points_to(ast: BidirPointsTo, scope: Scope) -> BidirPointsTo:
    return BidirPointsTo(evaluate(ast.left, scope), evaluate(ast.right, scope))

def evaluate_assign(ast: Assign, scope: Scope):
    match ast:
        case Assign(left=Identifier(name), right=right):
            right = evaluate(right, scope)
            scope.assign(name, right)
            return void
    pdb.set_trace()
    raise NotImplementedError('Assign not implemented yet')

def evaluate_iter_in(ast: IterIn, scope: Scope):

    # helper function for progressing the iterator
    def step_iter_in(iter_props: tuple[Callable, Iter], scope: Scope) -> AST:
        binder, iterable = iter_props
        cond, val = iter_next(iterable).items
        binder(val)
        return cond

    # if the iterator properties are already in the scope, use them
    if (res := scope.meta[ast].props) is not None:
        return step_iter_in(cast(tuple[Callable, Iter], res), scope)

    # otherwise initialize since this is the first time we're hitting this IterIn
    match ast:
        case IterIn(left=Identifier(name), right=right):
            right = evaluate(right, scope)
            props = lambda x: scope.assign(name, x), Iter(item=right, i=0)
            scope.meta[ast].props = props
            return step_iter_in(props, scope)
        case IterIn(left=UnpackTarget() as target, right=right):
            right = evaluate(right, scope)
            props = lambda x: unpack_assign(target, x, scope), Iter(item=right, i=0)
            scope.meta[ast].props = props
            return step_iter_in(props, scope)

    pdb.set_trace()
    raise NotImplementedError('IterIn not implemented yet')


def unpack_assign(target: UnpackTarget, value: AST, scope: Scope):
    for left, right in zip(target.target, gen:=value.__iter_asts__()):
        match left:
            case Identifier(name):
                scope.assign(name, right)
            case Assign(left=Identifier(name), right=right):
                scope.assign(name, right)
            case UnpackTarget():
                unpack_assign(left, right, scope)
            # case Spread(): ... #TODO: spread should collect the rest of the values via gen
            # case Spread(): ... #Issue URL: https://github.com/david-andrew/dewy-lang/issues/9
            case _:
                pdb.set_trace()
                raise NotImplementedError(f'unpack_assign not implemented for {left=} and {right=}')


# TODO: probably break this up into one function per type of iterable
def iter_next(iter: Iter):
    match iter.item:
        case Array(items):
            if iter.i >= len(items):
                cond, val = Bool(False), undefined
            else:
                cond, val = Bool(True), items[iter.i]
            iter.i += 1
            return Array([cond, val])
        case Dict(items):
            if iter.i >= len(items):
                cond, val = Bool(False), undefined
            else:
                cond, val = Bool(True), items[iter.i]
            iter.i += 1
            return Array([cond, val])
        case Range(left=Int(val=l), right=Void(), brackets=brackets):
            offset = int(brackets[0] == '(') # handle if first value is exclusive
            cond, val = Bool(True), Int(l + iter.i + offset)
            iter.i += 1
            return Array([cond, val])
        case Range(left=Int(val=l), right=Int(val=r), brackets=brackets):
            offset = int(brackets[0] == '(') # handle if first value is exclusive
            end_offset = int(brackets[1] == ']')
            i = l + iter.i + offset
            if i > r + end_offset - 1:
                cond, val = Bool(False), undefined
            else:
                cond, val = Bool(True), Int(i)
            iter.i += 1
            return Array([cond, val])
        case Range(left=Array(items=[Int(val=r0), Int(val=r1)]), right=Void(), brackets=brackets):
            offset = int(brackets[0] == '(') # handle if first value is exclusive
            step = r1 - r0
            cond, val = Bool(True), Int(r0 + (iter.i + offset) * step)
            iter.i += 1
            return Array([cond, val])
        case Range(left=Array(items=[Int(val=r0), Int(val=r1)]), right=Int(val=r2), brackets=brackets):
            offset = int(brackets[0] == '(') # handle if first value is exclusive
            end_offset = int(brackets[1] == ']')
            step = r1 - r0
            i = r0 + (iter.i + offset) * step
            if i > r2 + end_offset - 1:
                cond, val = Bool(False), undefined
            else:
                cond, val = Bool(True), Int(i)
            iter.i += 1
            return Array([cond, val])
        #TODO: other range cases...
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'iter_next not implemented yet for {iter.item=}')


class Closure(AST):
    fn: FunctionLiteral
    scope: Scope
    # call_args: AST|None=None # TBD how to handle
    def __str__(self):
        return f'Closure({self.fn}, scope={self.scope})'

def evaluate_function_literal(ast: FunctionLiteral, scope: Scope):
    return Closure(fn=ast, scope=scope)

def evaluate_closure(ast: Closure, scope: Scope):
    fn_scope = Scope(ast.scope)
    #TODO: for now we assume everything is 0 args. need to handle args being attached to the closure
    return evaluate(ast.fn.body, fn_scope)

    #grab arguments from scope and put them in fn_scope
    pdb.set_trace()
    ast.fn.args
    raise NotImplementedError('Closure not implemented yet')

def evaluate_pyaction(ast: PyAction, scope: Scope):
    # fn_scope = Scope(ast.scope)
    #TODO: currently just assuming 0 args in and no return
    return ast.action(scope)


def evaluate_istring(ast: IString, scope: Scope) -> String:
    parts = (py_stringify(i, scope) for i in ast.parts)
    return String(''.join(parts))


def evaluate_express(ast: Express, scope: Scope):
    val = scope.get(ast.id.name).value
    return evaluate(val, scope)

#TODO: this needs improvements!
#Issue URL: https://github.com/david-andrew/dewy-lang/issues/2
def evaluate_if(ast: If, scope: Scope):
    scope = Scope(scope)
    scope.meta[ast].was_entered=False
    if cast(Bool, evaluate(ast.condition, scope)).val:
        scope.meta[ast].was_entered = True
        return evaluate(ast.body, scope)

    # is this correct if the If isn't entered?
    return void

#TODO: this needs improvements!
def evaluate_loop(ast: Loop, scope: Scope):
    scope = Scope(scope)
    scope.meta[ast].was_entered = False
    while cast(Bool, evaluate(ast.condition, scope)).val:
        scope.meta[ast].was_entered = True
        evaluate(ast.body, scope)

    # for now loops can't return anything
    return void
    # ast.body
    # ast.condition
    # pdb.set_trace()

class Comparable(Protocol):
    def __lt__(self, other: "Comparable") -> bool: ...
    def __le__(self, other: "Comparable") -> bool: ...
    def __gt__(self, other: "Comparable") -> bool: ...
    def __ge__(self, other: "Comparable") -> bool: ...
    def __eq__(self, other: "Comparable") -> bool: ...
    def __ne__(self, other: "Comparable") -> bool: ...

def evaluate_comparison_op(op: Callable[[Comparable, Comparable], bool], ast: AST, scope: Scope):
    left = evaluate(ast.left, scope)
    right = evaluate(ast.right, scope)
    match left, right:
        case Int(val=l), Int(val=r): return Bool(op(l, r))
        case _:
            raise NotImplementedError(f'{op.__name__} not implemented for {left=} and {right=}')

def evaluate_less(ast: Less, scope: Scope):
    return evaluate_comparison_op(lambda l, r: l < r, ast, scope)

def evaluate_equal(ast: Equal, scope: Scope):
    return evaluate_comparison_op(lambda l, r: l == r, ast, scope)



# TODO: op depends on what type of operands. bools use built-in and/or/etc, but ints need to use the bitwise operators
def evaluate_logical_op(logical_op: Callable[[bool, bool], bool], bitwise_op: Callable[[int, int], int], ast: AST, scope: Scope):
    left = evaluate(ast.left, scope)
    right = evaluate(ast.right, scope)
    match left, right:
        case Bool(val=l), Bool(val=r): return Bool(logical_op(l, r))
        case Int(val=l), Int(val=r): return Int(bitwise_op(l, r))
        case _:
            raise NotImplementedError(f'evaluate logical op not implemented for {left=} and {right=}')

def evaluate_and(ast: And, scope: Scope):
    return evaluate_logical_op(lambda l, r: l and r, lambda l, r: l & r, ast, scope)

def evaluate_or(ast: Or, scope: Scope):
    return evaluate_logical_op(lambda l, r: l or r, lambda l, r: l | r, ast, scope)

def evaluate_not(ast: Not, scope: Scope):
    val = evaluate(ast.operand, scope)
    match val:
        case Bool(val=v): return Bool(not v)
        case Int(val=v): return Int(~v) #TODO: bitwise not depends on the size of the int...
        case _:
            raise NotImplementedError(f'Not not implemented for {val=}')

#TODO: long term, probably convert this into a matrix for all the input types and ops, where pairs can register to it
# def evaluate_arithmetic_op[T](op: Callable[[T, T], T], ast: AST, scope: Scope):
#     left = evaluate(ast.left, scope)
#     right = evaluate(ast.right, scope)
#     match left, right:
#         case Int(val=l), Int(val=r): return Int(op(l, r))
#         case Array(), Array(): return Array(op(left.items, right.items)) #TODO: restrict this to add only...
#         case _:
#             raise NotImplementedError(f'{op.__name__} not implemented for {left=} and {right=}')

#TODO: unified arithmetic evaluation function
def evaluate_add(ast: Add, scope: Scope):
    left = evaluate(ast.left, scope)
    right = evaluate(ast.right, scope)
    match left, right:
        case Int(val=l), Int(val=r): return Int(l + r)
        case Array(items=l), Array(items=r): return Array(l + r)
        case _:
            raise NotImplementedError(f'Add not implemented for {left=} and {right=}')

def evaluate_mul(ast: Mul, scope: Scope):
    left = evaluate(ast.left, scope)
    right = evaluate(ast.right, scope)
    match left, right:
        case Int(val=l), Int(val=r): return Int(l * r)
        case _:
            raise NotImplementedError(f'Mul not implemented for {left=} and {right=}')

def evaluate_mod(ast: Mod, scope: Scope):
    left = evaluate(ast.left, scope)
    right = evaluate(ast.right, scope)
    match left, right:
        case Int(val=l), Int(val=r): return Int(l % r)
        case _:
            raise NotImplementedError(f'Mod not implemented for {left=} and {right=}')

############################ Builtin functions and helpers ############################
def py_stringify(ast: AST, scope: Scope) -> str:
    ast = evaluate(ast, scope)
    match ast:
        # types that require special handling
        case String(val): return val
        case Array(items): return f"[{' '.join(py_stringify(i, scope) for i in items)}]"

        # can use the built-in __str__ method for these types
        case Int() | Bool() | Undefined(): return str(ast)

        # TBD what other types need to be handled
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'stringify not implemented for {type(ast)}')
    pdb.set_trace()


    raise NotImplementedError('stringify not implemented yet')

#TODO: fix the function signatures here! they should not be keyword only for scope.
#Issue URL: https://github.com/david-andrew/dewy-lang/issues/8
#      fixing will involve being able to set default arguments for regular functions
#      then making the pyaction have a default for the string s=''
def py_printl(s:String|IString=None, *, scope: Scope) -> Void:
    # TODO: hacky way of handling no-arg case
    if s is None:
        s = String('')
    py_print(s, scope=scope)
    print()
    return void

def py_print(s:String|IString=None, *, scope: Scope) -> Void:
    # TODO: hacky way of handling no-arg case
    if s is None:
        s = String('')
    if not isinstance(s, (String, IString)):
        s = String(py_stringify(s, scope))
        # raise ValueError(f'py_print expected String or IString, got {type(s)}:\n{s!r}')
    if isinstance(s, IString):
        s = cast(String, evaluate(s, scope))
    print(s.val, end='')
    return void

def py_readl(scope: Scope) -> String:
    return String(input())

def insert_pyactions(scope: Scope):
    """replace pyaction stubs with actual implementations"""
    if 'printl' in scope.vars:
        assert isinstance((proto:=scope.vars['printl'].value), PrototypePyAction)
        scope.vars['printl'].value = PyAction(proto.args, py_printl, proto.return_type)
    if 'print' in scope.vars:
        assert isinstance((proto:=scope.vars['print'].value), PrototypePyAction)
        scope.vars['print'].value = PyAction(proto.args, py_print, proto.return_type)
    if 'readl' in scope.vars:
        assert isinstance((proto:=scope.vars['readl'].value), PrototypePyAction)
        scope.vars['readl'].value = PyAction(proto.args, py_readl, proto.return_type)
