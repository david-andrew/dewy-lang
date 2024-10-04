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
    Void, void, Undefined, undefined, untyped,
    String, IString,
    Flowable, Flow, If, Loop, Default,
    PrototypeIdentifier, Identifier, Express, Declare,
    FunctionLiteral, PrototypePyAction, PyAction, Call,
    Assign,
    Int, Bool,
    Range, IterIn,
    Less, LessEqual, Greater, GreaterEqual, Equal, MemberIn,
    LeftShift, RightShift, LeftRotate, RightRotate, LeftRotateCarry, RightRotateCarry,
    Add, Sub, Mul, Div, IDiv, Mod, Pow,
    And, Or, Xor, Nand, Nor, Xnor,
    Not, UnaryPos, UnaryNeg, UnaryMul, UnaryDiv,
    Spread,
    # DeclarationType,
)

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast, Callable, Any
from functools import cache
from collections import defaultdict
from types import SimpleNamespace
from argparse import ArgumentParser

import pdb



def python_interpreter(path: Path, args: list[str]):
    arg_parser = ArgumentParser(description='Dewy Compiler: Python Interpreter Backend')
    arg_parser.add_argument('--verbose', action='store_true', help='Print verbose output')
    args = arg_parser.parse_args(args)

    # get the source code and tokenize
    src = path.read_text()
    tokens = tokenize(src)
    post_process(tokens)

    # parse tokens into AST
    ast = top_level_parse(tokens)
    ast = post_parse(ast)

    # debug printing
    if args.verbose:
        print_ast(ast)
        print(repr(ast))

    # run the program
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


class MetaNamespaceDict(defaultdict):
    """A defaultdict that preprocesses AST keys to use the classname + memory address as the key"""
    def __init__(self):
        super().__init__(MetaNamespace)

    # add preprocessing to both __getitem__ and __setitem__ to handle AST keys
    # apparently __setitem__ always calls __getitem__ so we only need to override __getitem__
    def __getitem__(self, item: AST) -> Any | None:
        key = f'::{item.__class__.__name__}@{hex(id(item))}'
        return super().__getitem__(key)

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

#DEBUG supporting py3.11
from typing import TypeVar
T = TypeVar('T', bound=AST)
class EvalFunc(Protocol):
    def __call__(self, ast: T, scope: Scope) -> AST: ...

def no_op(ast: T, scope: Scope) -> T:
    """For ASTs that just return themselves when evaluated"""
    return ast

# class EvalFunc[T](Protocol):
#     def __call__(self, ast: T, scope: Scope) -> AST: ...


# def no_op[T](ast: T, scope: Scope) -> T:
#     """For ASTs that just return themselves when evaluated"""
#     return ast

def cannot_evaluate(ast: AST, scope: Scope) -> AST:
    raise ValueError(f'INTERNAL ERROR: evaluation of type {type(ast)} is not possible')


@cache
def get_eval_fn_map() -> dict[type[AST], EvalFunc]:
    return {
        Declare: evaluate_declare,
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
        Flow: evaluate_flow,
        Default: evaluate_default,
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
        Void: no_op,
        #TODO: other AST types here
    }

def evaluate(ast:AST, scope:Scope) -> AST:
    eval_fn_map = get_eval_fn_map()

    ast_type = type(ast)
    if ast_type in eval_fn_map:
        return eval_fn_map[ast_type](ast, scope)

    raise NotImplementedError(f'evaluation not implemented for {ast_type}')


def evaluate_declare(ast: Declare, scope: Scope):
    match ast.target:
        case Identifier(name):
            value = void
            type = untyped
        case TypedIdentifier(id=Identifier(name), type=type): ... # values unpacked by match
        case Assign(left=Identifier(name), right=right):
            value = evaluate(right, scope)
            type = untyped
        case Assign(left=TypedIdentifier(id=Identifier(name), type=type), right=right):
            value = evaluate(right, scope)
        case _:
            raise NotImplementedError(f'Declare not implemented yet for {ast.target=}')

    scope.declare(name, value, type, ast.decltype)
    return void


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
        scope.meta[f].call_args = args, kwargs
        return evaluate_closure(f, scope)
        # attach_args_to_scope(args, kwargs, f.scope)
        # return evaluate(f.fn.body, f.scope)

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


def normalize_signature(signature: AST) -> tuple[list[str], dict[str, AST]]:
    match signature:
        case Identifier(name): return [name], {}
        case Assign(left=Identifier(name), right=right): return [], {name: right}
        case Array(items) | Group(items):
            args, kwargs = [], {}
            for i in items:
                match i:
                    case Identifier(name): args.append(name)
                    case TypedIdentifier(id=Identifier(name)): args.append(name)
                    case Assign(left=Identifier(name), right=right): kwargs[name] = right
                    case Assign(left=TypedIdentifier(id=Identifier(name)), right=right): kwargs[name] = right
                    case _:
                        raise NotImplementedError(f'normalize_signature not implemented yet for {signature=}, {i=}')
            return args, kwargs
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'normalize_signature not implemented yet for {signature=}')

def attach_args_to_scope(signature: AST, args: list[AST], kwargs: dict[str, AST], scope: Scope):
    sig_args, sig_kwargs = normalize_signature(signature)
    for sig_arg, arg in zip(sig_args, args):
        scope.assign(sig_arg, arg)

    #TODO: handle kwargs
    if kwargs:
        pdb.set_trace()
        raise NotImplementedError('kwargs not yet supported')
        for sig_kwarg, kwarg in kwargs.items():
            scope.assign(sig_kwarg, kwarg)


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
    return BidirDict([evaluate(kv, scope) for kv in ast.items])

def evaluate_bidir_points_to(ast: BidirPointsTo, scope: Scope) -> BidirPointsTo:
    return BidirPointsTo(evaluate(ast.left, scope), evaluate(ast.right, scope))

def evaluate_assign(ast: Assign, scope: Scope):
    match ast:
        case Assign(left=Identifier(name), right=right):
            right = evaluate(right, scope)
            scope.assign(name, right)
            return void
        case Assign(left=UnpackTarget() as target, right=right):
            right = evaluate(right, scope)
            unpack_assign(target, right, scope)
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

# def determine_how_many_to_take
def take_n(gen, n:int):
    return [next(gen) for _ in range(n)]

#TODO: this is really only for array unpacking. need to handle object unpacking as well...
#      need to check what type value
def unpack_assign(target: UnpackTarget, value: AST, scope: Scope):

    # current inefficient hack to unpack strings
    if isinstance(value, String):
        value = Array([String(c) for c in value.val])

    # current types supporting unpacking
    if not isinstance(value, (Array, Dict, PointsTo, BidirDict, BidirPointsTo, Undefined)):
        raise NotImplementedError(f'unpack_assign() is not yet implemented for {value=}')

    # determine how many targets will be assigned, and if spread is present
    num_targets = len(target.target)
    num_spread = sum(isinstance(t, Spread) for t in target.target)
    if num_spread > 1: raise RuntimeError(f'Only one spread is allowed in unpacking. {target=}, {value=}')

    # undefined unpacks as many undefineds as there are non-spread targets
    if isinstance(value, Undefined):
        value = Array([undefined for _ in range(num_targets - num_spread)])

    # verify if enough values to unpack, and set up generator (using built in iteration over ASTs children)
    num_values = len([*value.__iter_asts__()])
    spread_size = num_values - num_targets + 1  # if a spread is present, how many elements it will take
    if num_targets - num_spread > num_values: raise RuntimeError(f'Not enough values to unpack. {num_targets=}, {target=}, {value=}')
    gen = value.__iter_asts__()

    for left in target.target:
        match left:
            case Identifier(name):
                scope.assign(name, next(gen))
            # #TODO: object member renamed unpack. need to get the member of the object and assign it to the new name
            # case Assign(left=Identifier(name), right=right):
            #     scope.assign(name, right)
            case UnpackTarget():
                unpack_assign(left, next(gen), scope)
            case Spread(right=Identifier(name)):
                scope.assign(name, Array([next(gen) for _ in range(spread_size)]))
            case Spread(right=UnpackTarget() as left):
                unpack_assign(left, Array([next(gen) for _ in range(spread_size)]), scope)
            case _:
                pdb.set_trace()
                raise NotImplementedError(f'unpack_assign not implemented for {left=} and right={next(gen)}')

    # if there are any remaining values, raise an error
    if (remaining := [*gen]):
        raise RuntimeError(f'Too many values to unpack. {num_targets=}, {target=}, {value=}, {remaining=}')

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
        case Range(left=Int(val=l), right=Void()|Undefined(), brackets=brackets):
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
        case Range(left=Array(items=[Int(val=r0), Int(val=r1)]), right=Void()|Undefined(), brackets=brackets):
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
    args, kwargs = scope.meta[ast].call_args or ([], {})
    signature = ast.fn.args
    attach_args_to_scope(signature, args, kwargs, fn_scope)
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

def evaluate_flow(ast: Flow, scope: Scope):
    for branch in ast.branches:
        #TODO: slightly hacky way to get the child scope created by the branch (so we can check if it was entered)
        child_scope = None
        def save_child_scope(scope: Scope):
            nonlocal child_scope
            child_scope = scope

        match branch:
            case Default(): res = evaluate_default(branch, scope, save_child_scope)
            case If(): res = evaluate_if(branch, scope, save_child_scope)
            case Loop(): res = evaluate_loop(branch, scope, save_child_scope)
            case _:
                pdb.set_trace()
                raise NotImplementedError(f'evaluate_flow not implemented for flow type {branch=}')

        # if the branch was entered, return its result
        assert child_scope.meta[branch].was_entered is not None, f'INTERNAL ERROR: {branch=} .was_entered was not set'
        if child_scope.meta[branch].was_entered:
            return res

    # if no branches were entered, return void
    return void

def evaluate_default(ast: Default, scope: Scope, save_child_scope:Callable[[Scope], None]=lambda _: None):
    scope = Scope(scope)
    save_child_scope(scope)
    scope.meta[ast].was_entered = True
    return evaluate(ast.body, scope)

#TODO: this needs improvements!
#Issue URL: https://github.com/david-andrew/dewy-lang/issues/2
def evaluate_if(ast: If, scope: Scope, save_child_scope:Callable[[Scope], None]=lambda _: None):
    scope = Scope(scope)
    save_child_scope(scope)
    scope.meta[ast].was_entered = False
    if cast(Bool, evaluate(ast.condition, scope)).val:
        scope.meta[ast].was_entered = True
        return evaluate(ast.body, scope)

    # is this correct if the If isn't entered?
    return void

#TODO: this needs improvements!
def evaluate_loop(ast: Loop, scope: Scope, save_child_scope:Callable[[Scope], None]=lambda _: None):
    scope = Scope(scope)
    save_child_scope(scope)
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
        case String(val=l), String(val=r): return Bool(op(l, r))
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

# all references to python functions go through this interface to allow for easy swapping
from functools import partial
class BuiltinFuncs:
    printl=print
    print=partial(print, end='')
    readl=input

#TODO: consider adding a flag repr vs str, where initially str is used, but children get repr. 
# as is, stringifying should put quotes around strings that are children of other objects 
# but top level printed strings should not show their quotes
def py_stringify(ast: AST, scope: Scope) -> str:
    ast = evaluate(ast, scope)
    match ast:
        # types that require special handling (i.e. because they have children that need to be stringified)
        case String(val): return val #TODO: should get quotes if stringified as a child
        case Array(items): return f"[{' '.join(py_stringify(i, scope) for i in items)}]"
        case Dict(items): return f"[{' '.join(py_stringify(kv, scope) for kv in items)}]"
        case PointsTo(left, right): return f'{py_stringify(left, scope)}->{py_stringify(right, scope)}'
        case BidirDict(items): return f"[{' '.join(py_stringify(kv, scope) for kv in items)}]"
        case BidirPointsTo(left, right): return f'{py_stringify(left, scope)}<->{py_stringify(right, scope)}'

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
    BuiltinFuncs.printl()
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
    BuiltinFuncs.print(s.val)
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
