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
    Identifier, Express, Declare,
    PrototypePyAction, Call,
    Assign,
    Int, Bool,
    Range, IterIn,
    BinOp,
    Less, LessEqual, Greater, GreaterEqual, Equal, MemberIn,
    LeftShift, RightShift, LeftRotate, RightRotate, LeftRotateCarry, RightRotateCarry,
    Add, Sub, Mul, Div, IDiv, Mod, Pow,
    And, Or, Xor, Nand, Nor, Xnor,
    UnaryPrefixOp,
    Not, UnaryPos, UnaryNeg, UnaryMul, UnaryDiv, AtHandle,
    Spread,
)

from ..postparse import FunctionLiteral

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast, Callable as TypingCallable, Any
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

class PyActionArgsPreprocessor(Protocol):
    def __call__(self, args: list[AST], kwargs: dict[str, AST], scope: Scope) -> tuple[list[Any], dict[str, Any]]: ...

class PyAction(AST):
    signature: Group
    preprocessor: PyActionArgsPreprocessor
    action: TypingCallable[..., AST]
    return_type: AST

    def __str__(self):
        return f'{self.signature}: {self.return_type} => {self.action}'

class Closure(AST):
    fn: FunctionLiteral
    scope: Scope

    def __str__(self):
        scope_lines = []
        for name, var in self.scope.vars.items():
            line = f'{var.decltype.name.lower()} {name}'
            if var.type is not untyped:
                line += f': {var.type}'
            if var.value is self:
                line += ' = <self>'
            elif var.value is not void:
                line += f' = {var.value}'
            scope_lines.append(line)
        scope_contents = ', '.join(scope_lines)
        return f'{self.fn} with scope=[{scope_contents}]'


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
        UnaryNeg: evaluate_unary_neg,
        Add: evaluate_add,
        Mul: evaluate_mul,
        Mod: evaluate_mod,
        AtHandle: evaluate_at_handle,
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


def evaluate_call(call: Call, scope: Scope) -> AST:
    f = call.f

    # get the expression of the group
    if isinstance(f, Group):
        f = evaluate(f, scope)

    # get the value pointed to by the identifier
    if isinstance(f, Identifier):
        f = scope.get(f.name).value

    # if this is a handle, do a partial evaluation rather than a call
    if isinstance(f, AtHandle):
        return apply_partial_eval(f.operand, call.args, scope)

    # AST being called must be TypingCallable
    assert isinstance(f, (PyAction, Closure)), f'expected Function or PyAction, got {f}'

    # save the args of the call as metadata for the function AST
    call_args, call_kwargs = collect_calling_args(call.args, scope)
    scope.meta[f].call_args = call_args, call_kwargs

    # run the function and return the result
    if isinstance(f, PyAction):
        return evaluate_pyaction(f, scope)
    if isinstance(f, Closure):
        return evaluate_closure(f, scope)

    pdb.set_trace()
    raise NotImplementedError(f'Function evaluation not implemented yet')

def collect_calling_args(args: AST | None, scope: Scope) -> tuple[list[AST], dict[str, AST]]:
    """
    Collect the arguments that a function is being called with
    e.g. `let fn = (a, b, c) => a + b + c; fn(1, c=2, 3)`
    then the calling args are [1, 3] and {c: 2}

    Args:
        args: the arguments being passed to the function. If None, then treat as a no-arg call
        scope: the scope in which the function is being called

    Returns:
        a tuple of the positional arguments and keyword arguments
    """
    match args:
        case None | Void(): return [], {}
        case Identifier(name): return [scope.get(name).value], {}
        case Assign(): raise NotImplementedError('Assign not implemented yet') #called recursively if a calling arg was an keyword arg rather than positional
        case Spread(right=right):
            pdb.set_trace()
            ... #right should be iterable, so extend with the values it expresses
                #whether to add to args or kwargs depends on each type from right
            val = evaluate(right, scope)
            match val:
                case Array(items): ... #return [collect_calling_args(i, scope) for i in items]
        case Int() | String() | IString() | Call() | Express() | UnaryPrefixOp():
            return [args], {}
        # case Call(): return [args], {}
        case Group(items):
            call_args, call_kwargs = [], {}
            for i in items:
                a, kw = collect_calling_args(i, scope)
                call_args.extend(a)
                call_kwargs.update(kw)
            return call_args, call_kwargs
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'collect_args not implemented yet for {args}')


    raise NotImplementedError(f'collect_args not implemented yet for {args}')



def attach_args_to_scope(signature: Group, args: list[AST], kwargs: dict[str, AST], scope: Scope):
    """Resolve calling arguments and attach each to the scope so they are available during function body evaluation"""
    dewy_args, dewy_kwargs = resolve_calling_args(signature, args, kwargs, scope)
    for name, value in (dewy_args | dewy_kwargs).items():
        scope.assign(name, value)


# TODO: resolve args should handle the full gamut of possible types of arguments in a function
#       position or keyword arguments (with or without defaults)
#       position only arguments (with or without defaults)
#       keyword only arguments (with or without defaults)
# Note: the function signature will stay the same since calling a function or pyaction just amounts to setting args and kwargs
def resolve_calling_args(signature: Group, args: list[AST], kwargs: dict[str, AST], scope: Scope) -> tuple[dict[str, AST], dict[str, AST]]:
    """
    Resolve the final list of arguments the function actually receives
    Properly handles when the signature includes defaults, keyword args, positional args, partial evaluation, etc.

    e.g. if we have:

    ```dewy
    let fn = (a, b, c) => a + b + c
    fn = @fn(c=3)
    fn(1, a=2)
    ```

    then we would resolve to args={b: 1} kwargs={a: 2, c: 3}
    """
    # for now, just assume all args are position or keyword args
    # partial eval converts that particular arg to keyword only
    sig_list = [*signature.items]
    dewy_args, dewy_kwargs = {}, {}

    # first pull out the calling keyword arguments
    for name, arg in kwargs.items():
        #remove this parameter from the sig list
        pdb.set_trace()
        remove_from_sig_list(sig_list, name)
        dewy_kwargs[name] = arg

    if len(sig_list) < len(args):
        raise ValueError(f'Too many arguments for function. {signature=}, {args=}, {kwargs=}')

    # split off the positional arguments from any remaining args in the signature
    sig_list, remaining = sig_list[:len(args)], sig_list[len(args):]
    assert all(isinstance(arg, Assign) for arg in remaining), f'Non-Assign arguments remaining unpaired in signature. {signature=}, {args=}, {kwargs=}, {remaining=}'
    for spec, arg in zip(sig_list, args):
        match spec:
            case Identifier(name):
                dewy_args[name] = arg
            case TypedIdentifier(id=Identifier(name), type=type): #TODO: could do type checking here? probably leave for type checker
                dewy_args[name] = arg
            case Assign(left=Identifier(name), right=right):
                dewy_args[name] = arg
            case Assign(left=TypedIdentifier(id=Identifier(name), type=type), right=right):
                dewy_args[name] = arg
            case _:
                raise NotImplementedError(f'Assign positional arg not implemented yet for {spec=}\n{signature=}, {args=}, {kwargs=}, {remaining=}')

    # all remaining arguments must have a value provided by the signature
    for arg in remaining:
        match arg:
            case Assign(left=Identifier(name), right=right):
                dewy_kwargs[name] = right
            case Assign(left=TypedIdentifier(id=Identifier(name), type=type), right=right):
                dewy_kwargs[name] = right
            case _:
                raise NotImplementedError(f'Assign keyword arg not implemented yet for {arg=}\n{signature=}, {args=}, {kwargs=}, {remaining=}')

    return dewy_args, dewy_kwargs    


def apply_partial_eval(f: AST, args: list[AST], scope: Scope) -> AST:
    match f:
        case FunctionLiteral(args, body):
            pdb.set_trace()
            ...
        case Identifier(name):
            f = scope.get(name).value
            return apply_partial_eval(f, args, scope)
        case _:
            raise NotImplementedError(f'Partial evaluation not implemented yet for {f=}')


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
    def step_iter_in(iter_props: tuple[TypingCallable, Iter], scope: Scope) -> AST:
        binder, iterable = iter_props
        cond, val = iter_next(iterable).items
        binder(val)
        return cond

    # if the iterator properties are already in the scope, use them
    if (res := scope.meta[ast].props) is not None:
        return step_iter_in(cast(tuple[TypingCallable, Iter], res), scope)

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



def evaluate_function_literal(ast: FunctionLiteral, scope: Scope):
    return Closure(fn=ast, scope=scope)

def evaluate_closure(ast: Closure, scope: Scope):
    fn_scope = Scope(ast.scope)
    args, kwargs = scope.meta[ast].call_args or ([], {})
    signature = ast.fn.args
    attach_args_to_scope(signature, args, kwargs, fn_scope)
    return evaluate(ast.fn.body, fn_scope)

    #grab arguments from scope and put them in fn_scope
    pdb.set_trace()
    ast.fn.args
    raise NotImplementedError('Closure not implemented yet')

def evaluate_pyaction(ast: PyAction, scope: Scope):
    fn_scope = Scope(scope)
    call_args, call_kwargs = scope.meta[ast].call_args or ([], {})
    dewy_args, dewy_kwargs = resolve_calling_args(ast.signature, call_args, call_kwargs, fn_scope)
    py_args, py_kwargs = ast.preprocessor([*dewy_args.values()], dewy_kwargs, fn_scope)
    return ast.action(*py_args, **py_kwargs)


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

def evaluate_default(ast: Default, scope: Scope, save_child_scope:TypingCallable[[Scope], None]=lambda _: None):
    scope = Scope(scope)
    save_child_scope(scope)
    scope.meta[ast].was_entered = True
    return evaluate(ast.body, scope)

#TODO: this needs improvements!
#Issue URL: https://github.com/david-andrew/dewy-lang/issues/2
def evaluate_if(ast: If, scope: Scope, save_child_scope:TypingCallable[[Scope], None]=lambda _: None):
    scope = Scope(scope)
    save_child_scope(scope)
    scope.meta[ast].was_entered = False
    if cast(Bool, evaluate(ast.condition, scope)).val:
        scope.meta[ast].was_entered = True
        return evaluate(ast.body, scope)

    # is this correct if the If isn't entered?
    return void

#TODO: this needs improvements!
def evaluate_loop(ast: Loop, scope: Scope, save_child_scope:TypingCallable[[Scope], None]=lambda _: None):
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

def evaluate_comparison_op(op: TypingCallable[[Comparable, Comparable], bool], ast: AST, scope: Scope):
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
def evaluate_logical_op(logical_op: TypingCallable[[bool, bool], bool], bitwise_op: TypingCallable[[int, int], int], ast: AST, scope: Scope):
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

def evaluate_unary_neg(ast: UnaryNeg, scope: Scope):
    val = evaluate(ast.operand, scope)
    match val:
        case Int(val=v): return Int(-v)
        case _:
            raise NotImplementedError(f'Negation not implemented for {val=}')

#TODO: long term, probably convert this into a matrix for all the input types and ops, where pairs can register to it
# def evaluate_arithmetic_op[T](op: TypingCallable[[T, T], T], ast: AST, scope: Scope):
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


def evaluate_at_handle(ast: AtHandle, scope: Scope):
    match ast.operand:
        case Identifier(name):
            return scope.get(name).value
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'AtHandle not implemented for {ast.operand=}')

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
        case Closure(fn): return f'{fn}'
        case FunctionLiteral() as fn: return f'{fn}'

        # can use the built-in __str__ method for these types
        case Int() | Bool() | Undefined(): return str(ast)

        # TBD what other types need to be handled
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'stringify not implemented for {type(ast)}')
    pdb.set_trace()


    raise NotImplementedError('stringify not implemented yet')

def preprocess_py_print_args(args: list[AST], kwargs: dict[str, AST], scope: Scope) -> tuple[list[Any], dict[str, Any]]:
    py_args = [py_stringify(i, scope) for i in args]
    py_kwargs = {k: py_stringify(v, scope) for k, v in kwargs.items()}
    return py_args, py_kwargs

def py_printl(s:str) -> Void:
    BuiltinFuncs.printl(s)
    return void

def py_print(s:str) -> Void:
    BuiltinFuncs.print(s)
    return void

def py_readl() -> String:
    return String(BuiltinFuncs.readl())

def insert_pyactions(scope: Scope):
    """replace pyaction stubs with actual implementations"""
    if 'printl' in scope.vars:
        assert isinstance((proto:=scope.vars['printl'].value), PrototypePyAction)
        scope.vars['printl'].value = PyAction(proto.args, preprocess_py_print_args, py_printl, proto.return_type)
    if 'print' in scope.vars:
        assert isinstance((proto:=scope.vars['print'].value), PrototypePyAction)
        scope.vars['print'].value = PyAction(proto.args, preprocess_py_print_args, py_print, proto.return_type)
    if 'readl' in scope.vars:
        assert isinstance((proto:=scope.vars['readl'].value), PrototypePyAction)
        scope.vars['readl'].value = PyAction(proto.args, lambda *a: ([],{}), py_readl, proto.return_type)
