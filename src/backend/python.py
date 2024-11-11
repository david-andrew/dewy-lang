from ..tokenizer import tokenize
from ..postok import post_process
from ..dtypes import (
    Scope as DTypesScope,
    typecheck_call, typecheck_index, typecheck_multiply,
    register_typeof, short_circuit,
    CallableBase, IndexableBase, IndexerBase, MultipliableBase, ObjectBase,
)
from ..parser import top_level_parse, QJux
from ..syntax import (
    AST,
    Type, TypeParam,
    PointsTo, BidirPointsTo,
    ListOfASTs, PrototypeTuple, Block, Array, Group, Range, ObjectLiteral, Dict, BidirDict, UnpackTarget,
    TypedIdentifier,
    Void, void, Undefined, undefined, untyped,
    String, IString,
    Flowable, Flow, If, Loop, Default,
    Identifier, Express, Declare,
    PrototypeBuiltin, Call, Access, Index,
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

from ..postparse import post_parse, FunctionLiteral, Signature, normalize_function_args
from ..utils import Options

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast, Callable as TypingCallable, Any, Generic
from functools import cache
from collections import defaultdict
from types import SimpleNamespace


import pdb



def python_interpreter(path: Path, args:list[str], options: Options) -> None:
    # get the source code and tokenize
    src = path.read_text()
    tokens = tokenize(src)
    post_process(tokens)

    # parse tokens into AST
    ast = top_level_parse(tokens)
    ast = post_parse(ast)

    # debug printing
    if options.verbose:
        print_ast(ast)
        print(repr(ast))

    # run the program
    res = top_level_evaluate(ast)
    if res is not void:
        print(res)

def python_repl(args: list[str], options: Options):
    try:
        from easyrepl import REPL
    except ImportError:
        print('easyrepl is required for REPL mode. Install with `pip install easyrepl`')
        return

    # Set up scope to share between REPL calls
    scope = Scope.default()
    insert_pyactions(scope)

    # get the source code and tokenize
    for src in REPL(history_file='~/.dewy/repl_history'):
        # Check for custom commands
        match src:
            case 'exit' | 'quit':
                return
            case 'help':
                print('Commands:')
                print('  exit|quit: exit the REPL')
                print('  help: display this help message')
                continue

        try:
            tokens = tokenize(src)
            post_process(tokens)
            if options.tokens:
                print(tokens)

            # parse tokens into AST
            ast = top_level_parse(tokens)
            ast = post_parse(ast)

            # debug printing
            if options.verbose:
                print_ast(ast)
                print(repr(ast))

            # run the program (sharing the same scope)
            res = evaluate(ast, scope)
            if res is not void:
                print(res)
        except Exception as e:
            print(f'Error: {e}')

    print() # newline after exiting REPL with ctrl+d

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
class Scope(DTypesScope):
    """An extension of the Scope used during parsing to support runtime"""
    meta: dict[AST, MetaNamespace] = field(default_factory=MetaNamespaceDict)

    def __repr__(self):
        return f'<Scope@{hex(id(self))}>'


class Iter(AST):
    item: AST
    i: int

    def __str__(self):
        return f'Iter({self.item}, i={self.i})'

class BuiltinArgsPreprocessor(Protocol):
    def __call__(self, args: list[AST], kwargs: dict[str, AST], scope: Scope) -> tuple[list[Any], dict[str, Any]]: ...

class Builtin(CallableBase):
    signature: Signature
    preprocessor: BuiltinArgsPreprocessor
    action: TypingCallable[..., AST]
    return_type: AST

    def __str__(self):
        return f'{self.signature}: {self.return_type} => {self.action}'

    def from_prototype(proto: PrototypeBuiltin, preprocessor: BuiltinArgsPreprocessor, action: TypingCallable[..., AST]) -> 'Builtin':
        return Builtin(
            signature=normalize_function_args(proto.args),
            preprocessor=preprocessor,
            action=action,
            return_type=proto.return_type,
        )

# hacky for now. longer term, want full signature type checking for functions!
register_typeof(Builtin, short_circuit(Builtin))

class Closure(CallableBase):
    fn: FunctionLiteral
    scope: Scope

    def __str__(self):
        return f'{self.fn} with <Scope@{hex(id(self.scope))}>'
        # scope_lines = []
        # for name, var in self.scope.vars.items():
        #     line = f'{var.decltype.name.lower()} {name}'
        #     if var.type is not untyped:
        #         line += f': {var.type}'
        #     if var.value is self:
        #         line += ' = <self>'
        #     elif var.value is not void:
        #         line += f' = {var.value}'
        #     scope_lines.append(line)
        # scope_contents = ', '.join(scope_lines)
        # return f'{self.fn} with scope=[{scope_contents}]'

# register_callable(Builtin)
# register_callable(Closure)

register_typeof(Closure, short_circuit(Closure))

class Object(ObjectBase):
    scope: Scope

    def __str__(self):
        chunks = []
        for name, var in self.scope.vars.items():
            chunk = f'{var.decltype.name.lower()} {name}'
            if var.type is not untyped:
                chunk += f': {var.type}'
            #TODO: need to handle any recursion loops...
            elif var.value is not void:
                chunk += f' = {var.value}'
            chunks.append(chunk)
        if len(chunks) < 5:
            return f'[{" ".join(chunks)}]'
        newline = '\n'
        #TODO: py3.12 remove {newline} and replace with direct \n
        return f'[{newline}    {f"{newline}    ".join(chunks)}{newline}]'


def typeof_object(obj: Object, scope: Scope, params:bool=False) -> Type:
    return Type(Object, TypeParam([obj.scope]))
register_typeof(Object, typeof_object)

class Float(MultipliableBase):
    val: float

    def __str__(self):
        return f'{self.val}'

############################ Evaluation functions ############################

#DEBUG supporting py3.11
from typing import TypeVar
T = TypeVar('T', bound=AST)
U = TypeVar('U', bound=AST)
class EvalFunc(Protocol):
    def __call__(self, ast: T, scope: Scope) -> AST: ...

def no_op(ast: T, scope: Scope) -> T:
    """For ASTs that just return themselves when evaluated"""
    return ast

# #py3.12 version
# class EvalFunc[T](Protocol):
#     def __call__(self, ast: T, scope: Scope) -> AST: ...
#
# def no_op[T](ast: T, scope: Scope) -> T:
#     """For ASTs that just return themselves when evaluated"""
#     return ast

def cannot_evaluate(ast: AST, scope: Scope) -> AST:
    raise ValueError(f'INTERNAL ERROR: evaluation of type {type(ast)} is not possible')


@cache
def get_eval_fn_map() -> dict[type[AST], EvalFunc]:
    return {
        Declare: evaluate_declare,
        QJux: evaluate_qjux,
        Call: evaluate_call,
        Block: evaluate_block,
        Group: evaluate_group,
        Array: evaluate_array,
        Dict: evaluate_dict,
        PointsTo: evaluate_points_to,
        BidirDict: evaluate_bidir_dict,
        BidirPointsTo: evaluate_bidir_points_to,
        ObjectLiteral: evaluate_object_literal,
        Object: no_op,
        Access: evaluate_access,
        Index: evaluate_index,
        Assign: evaluate_assign,
        IterIn: evaluate_iter_in,
        FunctionLiteral: evaluate_function_literal,
        Closure: evaluate_closure,
        Builtin: evaluate_pyaction,
        String: no_op,
        IString: evaluate_istring,
        Identifier: cannot_evaluate,
        Express: evaluate_express,
        Int: no_op,
        Float: no_op,
        Bool: no_op,
        Range: no_op,
        Flow: evaluate_flow,
        Default: evaluate_default,
        If: evaluate_if,
        Loop: evaluate_loop,
        UnaryPos: evaluate_unary_dispatch,
        UnaryNeg: evaluate_unary_dispatch,
        UnaryMul: evaluate_unary_dispatch,
        UnaryDiv: evaluate_unary_dispatch,
        Not: evaluate_unary_dispatch,
        Greater: evaluate_binary_dispatch,
        GreaterEqual: evaluate_binary_dispatch,
        Less: evaluate_binary_dispatch,
        LessEqual: evaluate_binary_dispatch,
        Equal: evaluate_binary_dispatch,
        And: evaluate_binary_dispatch,
        Or: evaluate_binary_dispatch,
        Xor: evaluate_binary_dispatch,
        Nand: evaluate_binary_dispatch,
        Nor: evaluate_binary_dispatch,
        Xnor: evaluate_binary_dispatch,
        Add: evaluate_binary_dispatch,
        Sub: evaluate_binary_dispatch,
        Mul: evaluate_binary_dispatch,
        Div: evaluate_binary_dispatch,
        Mod: evaluate_binary_dispatch,
        Pow: evaluate_binary_dispatch,
        LeftShift: evaluate_binary_dispatch,
        RightShift: evaluate_binary_dispatch,
        LeftRotate: evaluate_binary_dispatch,
        RightRotate: evaluate_binary_dispatch,
        LeftRotateCarry: evaluate_binary_dispatch,
        RightRotateCarry: evaluate_binary_dispatch,
        CycleLeft: evaluate_binary_dispatch,
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


def suspend(ast:AST, scope:Scope) -> Closure:
    """Wrap an AST in a Closure to be evaluated later"""
    return Closure(fn=FunctionLiteral(args=Signature(), body=ast), scope=scope)


def evaluate_declare(ast: Declare, scope: Scope):
    match ast.target:
        case Identifier(name):
            value = void
            type = untyped
        case TypedIdentifier(id=Identifier(name), type=type):
            value = void
        case Assign(left=Identifier(name), right=right):
            value = evaluate(right, scope)
            type = untyped
        case Assign(left=TypedIdentifier(id=Identifier(name), type=type), right=right):
            value = evaluate(right, scope)
        case Assign(left=UnpackTarget() as target, right=right):
            right = evaluate(right, scope)
            #TODO: need to declare each value being unpacked. something with this effect (but also makes new declarations for each):
            # unpack_assign(target, right, scope)
            pdb.set_trace()
            ...

        case _:
            raise NotImplementedError(f'Declare not implemented yet for {ast.target=}')

    scope.declare(name, value, type, ast.decltype)
    return void

def evaluate_qjux(ast: QJux, scope: Scope) -> AST:
    if ast.call is not None and typecheck_call(ast.call, scope):
        return evaluate_call(ast.call, scope)
    if ast.index is not None and typecheck_index(ast.index, scope):
        return evaluate_index(ast.index, scope)
    if typecheck_multiply(ast.mul, scope):
        return evaluate_binary_dispatch(ast.mul, scope)

    raise ValueError(f'Typechecking failed to match a valid evaluation for QJux. {ast=}')

# def evaluate_qast(ast: QAST, scope: Scope):
#     # use type checking to determine which branch of the QAST to evaluate
#     candidates: list[AST] = [a for a in ast.asts if typecheck(a, scope)]
#     if len(candidates) == 0:
#         raise ValueError(f'No valid candidates for QAST. {ast=}')
#     if len(candidates) > 1:
#         raise ValueError(f'Multiple valid candidates for QAST. {ast=}, {candidates=}')
#     selected, = candidates
#     return evaluate(selected, scope)


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
    assert isinstance(f, (Builtin, Closure)), f'expected Function or Builtin, got {f}'

    # save the args of the call as metadata for the function AST
    call_args, call_kwargs = collect_calling_args(call.args, scope)
    scope.meta[f].call_args = call_args, call_kwargs

    # run the function and return the result
    if isinstance(f, Builtin):
        return evaluate_pyaction(f, scope)
    if isinstance(f, Closure):
        return evaluate_closure(f, scope)

    pdb.set_trace()
    raise NotImplementedError(f'Function evaluation not implemented yet')

#TODO: longer term this might also return a list/dict of spread args passed into the function
def collect_calling_args(args: AST | None, scope: Scope) -> tuple[list[AST], dict[str, AST]]:
    """
    Collect the arguments that a function is being called with
    e.g. `let fn = (a b c) => a + b + c; fn(1 c=2 3)`
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
        case Assign(left=Identifier(name)|TypedIdentifier(id=Identifier(name)), right=right): return [], {name: right}
        # case Assign(left=UnpackTarget() as target, right=right): raise NotImplementedError('UnpackTarget not implemented yet')
        case Assign(): raise NotImplementedError('Assign not implemented yet') #called recursively if a calling arg was an keyword arg rather than positional
        case CollectInto(right=right):
            pdb.set_trace()
            ... #right should be iterable, so extend with the values it expresses
                #whether to add to args or kwargs depends on each type from right
            val = evaluate(right, scope)
            match val:
                case Array(items): ... #return [collect_calling_args(i, scope) for i in items]
        case Group(items):
            call_args, call_kwargs = [], {}
            for i in items:
                a, kw = collect_calling_args(i, scope)
                call_args.extend(a)
                call_kwargs.update(kw)
            return call_args, call_kwargs

        #TODO: eventually it should just be anything that is left over is positional args rather than specifying them all out
        case Int() | String() | IString() | Range() | Call() | Access() | Index() | Express() | QJux() | UnaryPrefixOp() | UnaryPostfixOp() | BinOp() | BroadcastOp():
            return [args], {}
        # case Call(): return [args], {}
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'collect_args not implemented yet for {args}')


    raise NotImplementedError(f'collect_args not implemented yet for {args}')


def get_arg_name(arg: AST) -> str:
    """little helper function to get the name of an argument"""
    match arg:
        case Identifier(name): return name
        case TypedIdentifier(id=Identifier(name)): return name
        case Assign(left=Identifier(name)): return name
        case Assign(left=TypedIdentifier(id=Identifier(name))): return name
        case _:
            raise NotImplementedError(f'get_arg_name not implemented for {arg=}')

# TODO: this should maybe take in 2 scopes, one for the closure scope, and one for the callings scope... or closure scope args should already be evaluated...
# TODO: resolve args should handle the full gamut of possible types of arguments in a function
#       position or keyword arguments (with or without defaults)
#       position only arguments (with or without defaults)
#       keyword only arguments (with or without defaults)
# Note: the function signature will stay the same since calling a function or pyaction just amounts to setting args and kwargs
# TODO: probably expand to include a container for unpack targets
def resolve_calling_args(signature: Signature, args: list[AST], kwargs: dict[str, AST], caller_scope: Scope, closure_scope: Scope = Scope()) -> tuple[dict[str, AST], dict[str, AST]]:
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

    This is mainly for interfacing with python functions which want *args, **kwargs
    """
    # for now, just assume all args are position or keyword args
    # partial eval converts that particular arg to keyword only
    sig_pkwargs, sig_pargs, sig_kwargs = signature.pkwargs, signature.pargs, signature.kwargs
    dewy_args, dewy_kwargs = {}, {}

    # evaluate all the args and kwargs
    args = [evaluate(arg, caller_scope) for arg in args]
    kwargs = {name: evaluate(arg, caller_scope) for name, arg in kwargs.items()}


    # first pull out the calling keyword arguments
    dewy_kwargs.update(kwargs)
    sig_pkwargs = [*filter(lambda item: get_arg_name(item) not in kwargs, sig_pkwargs)]
    sig_kwargs = [*filter(lambda item: get_arg_name(item) not in kwargs, sig_kwargs)]

    #remaining kwargs are added to the dewy_kwargs
    for arg in sig_kwargs:
        assert isinstance(arg, Assign), f'INTERNAL ERROR: {arg=} is not an Assign'
        name = get_arg_name(arg)
        dewy_kwargs[name] = evaluate(arg.right, closure_scope)

    if len(sig_pargs) + len(sig_pkwargs) < len(args):
        raise ValueError(f'Too many positional arguments for function. {signature=}, {args=}, {kwargs=}')

    # next, pair up the positional arguments
    for spec, arg in zip(sig_pargs + sig_pkwargs, args):
        name = get_arg_name(spec)
        dewy_args[name] = arg

    # all remaining arguments must have a value provided by the signature
    for arg in (sig_pargs + sig_pkwargs)[len(args):]:
        #TODO: handle unpacking/spread
        name = get_arg_name(arg)
        if not isinstance(arg, Assign):
            pdb.set_trace()
            raise ValueError(f'Non-Assign arguments remaining unpaired in signature. {signature=}, {args=}, {kwargs=}')
        dewy_kwargs[name] = evaluate(arg.right, closure_scope)

    return dewy_args, dewy_kwargs



def update_signature(signature: Signature, args: list[AST], scope: Scope) -> Signature:
    """Given values to partially apply to a function, update the call signature to reflect the new values"""
    call_args, call_kwargs = collect_calling_args(args, scope)
    sig_pkwargs, sig_pargs, sig_kwargs = signature.pkwargs.copy(), signature.pargs.copy(), signature.kwargs.copy()
    for item in sig_kwargs:
        name = get_arg_name(item)
        if name in call_kwargs:
            sig_kwargs = [*filter(lambda i: get_arg_name(i) != name, sig_kwargs)]
            right = suspend(call_kwargs[name], scope) #((lambda ast, scope: lambda: evaluate(ast, scope))(call_kwargs[name], scope))
            sig_kwargs.append(Assign(left=Identifier(name), right=right))
    for item in sig_pkwargs:
        name = get_arg_name(item)
        if name in call_kwargs:
            sig_pkwargs = [*filter(lambda i: get_arg_name(i) != name, sig_pkwargs)]
            right = suspend(call_kwargs[name], scope) #Suspense((lambda ast, scope: lambda: evaluate(ast, scope))(call_kwargs[name], scope))
            # any pkwargs become kwargs when a value is given by keyword or position
            sig_kwargs.append(Assign(left=Identifier(name), right=right))

    # update the positional arguments
    for item in call_args:
        if len(sig_pargs) > 0:
            parg, sig_pargs = sig_pargs[0], sig_pargs[1:]
            name = get_arg_name(parg)
        elif len(sig_pkwargs) > 0:
            parg, sig_pkwargs = sig_pkwargs[0], sig_pkwargs[1:]
            name = get_arg_name(parg)
        else:
            raise ValueError(f'Too many positional arguments for function. {signature=}, {args=}')
        right = suspend(item, scope) #Suspense((lambda ast, scope: lambda: evaluate(ast, scope))(item, scope))
        sig_kwargs.append(Assign(left=Identifier(name), right=right))

    return Signature(pkwargs=sig_pkwargs, pargs=sig_pargs, kwargs=sig_kwargs)

def apply_partial_eval(f: AST, args: list[AST], scope: Scope) -> AST:
    match f:
        # # this case shouldn't really be possible since you have to wrap a function literal in parenthesis to @ it, turning it into a Closure
        # case FunctionLiteral(args=signature, body=body):
        #     new_signature = update_signature(signature, args, scope)
        #     return FunctionLiteral(args=new_signature, body=body)

        case Closure(fn=FunctionLiteral(args=signature, body=body), scope=closure_scope):
            new_signature = update_signature(signature, args, scope)
            return Closure(fn=FunctionLiteral(args=new_signature, body=body), scope=closure_scope)

        case Builtin(signature=signature, preprocessor=preprocessor, action=action, return_type=return_type):
            new_signature = update_signature(signature, args, scope)
            return Builtin(signature=new_signature, preprocessor=preprocessor, action=action, return_type=return_type)

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

def evaluate_object_literal(ast: ObjectLiteral, scope: Scope) -> Object:
    obj_scope = Scope(scope)
    evaluate(Group(ast.items), obj_scope)
    return Object(scope=obj_scope)

def evaluate_access(ast: Access, scope: Scope) -> AST:
    left = evaluate(ast.left, scope)
    right = ast.right
    match right:
        case Identifier():
            return evaluate_id_access(left, right, scope, evaluate_right=True)
        case AtHandle(operand=Identifier() as id):
            return evaluate_id_access(left, id, scope, evaluate_right=False)
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'evaluate_access not implemented yet for {right=}. {left=}')

def evaluate_index(ast: Index, scope: Scope) -> AST:
    left = evaluate(ast.left, scope)
    right = evaluate(ast.right, scope)
    match left, right:
        case Array(items), Array(items=[Int(i)]):
            return items[i]
        case _:
            pdb.set_trace()
    pdb.set_trace()
    ...

def evaluate_id_access(left: AST, right: Identifier, scope: Scope, evaluate_right=True) -> AST:
    match left:
        case Object(scope):
            access = scope.get(right.name, search_parents=False).value
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'evaluate_id_access not implemented yet for {left=}, {right=}')
        
    if evaluate_right:
        return evaluate(access, scope)
    return access

# def evaluate_at_handle_access(left: AST, right: AtHandle, scope: Scope) -> AST:
#     pdb.set_trace()
#     raise NotImplementedError(f'evaluate_at_handle_access not implemented yet for {left=}, {right=}')

#TODO: other access types (which are probably more like vectorized ops)
#      vectorized_call. perhaps this is just the catch all case for anything not an identifier? to use an identifier as an arg, just wrap in parens
#      vectorized_index? is that a coherent concept? honestly probably just let regular multidimensional indexing handle that case

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
    num_spread = sum(isinstance(t, CollectInto) for t in target.target)
    if num_spread > 1: raise RuntimeError(f'Only one collect-into is allowed in unpacking. {target=}, {value=}')

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
            case CollectInto(right=Identifier(name)):
                scope.assign(name, Array([next(gen) for _ in range(spread_size)]))
            case CollectInto(right=UnpackTarget() as left):
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
    closure_scope = Scope(ast.scope)
    caller_scope = Scope(scope)
    args, kwargs = scope.meta[ast].call_args or ([], {})
    signature = ast.fn.args

    # attach all the args to scope so body can access them
    dewy_args, dewy_kwargs = resolve_calling_args(signature, args, kwargs, caller_scope, closure_scope)
    for name, value in (dewy_args | dewy_kwargs).items():
        closure_scope.assign(name, value)

    return evaluate(ast.fn.body, closure_scope)


def evaluate_pyaction(ast: Builtin, scope: Scope):
    caller_scope = Scope(scope)
    call_args, call_kwargs = scope.meta[ast].call_args or ([], {})
    dewy_args, dewy_kwargs = resolve_calling_args(ast.signature, call_args, call_kwargs, caller_scope)
    py_args, py_kwargs = ast.preprocessor([*dewy_args.values()], dewy_kwargs, caller_scope)
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



def int_int_div(l: int, r: int) -> Int | Float | Undefined:
    if r == 0:
        return undefined
    res = l / r
    if res.is_integer():
        return Int(int(res))
    else:
        return Float(res)

def float_float_div(l: int|float, r: int|float) -> Float | Undefined:
    if r == 0:
        return undefined
    return Float(l / r)

class SimpleValue(Protocol, Generic[T]):
    val: T


# @dataclass
# class Dispatch:
#     fn_table: dict[tuple[Any, ...], TypingCallable[..., AST]]
#     type_symmetric: bool = True
#     # etc.
# DispatchTable = dict[type[UnaryPrefixOp|UnaryPostfixOp|BinOp], Dispatch]
# PromotionTable = dict[tuple[type[T], type[U]], TypingCallable[[T|U], T|U]]
# promote_rule(Int, Float64) == Float64
# promote_type(Int, Float64)  # Float64

UnaryDispatchKey =  tuple[type[UnaryPrefixOp]|type[UnaryPostfixOp], type[SimpleValue[T]]]
unary_dispatch_table: dict[UnaryDispatchKey[T], TypingCallable[[T], AST]] = {
    (Not, Int): lambda l: Int(~l),
    (Not, Bool): lambda l: Bool(not l),
    (UnaryPos, Int): lambda l: Int(l),
    (UnaryNeg, Int): lambda l: Int(-l),
    (UnaryMul, Int): lambda l: Int(l),
    (UnaryDiv, Int): lambda l: Int(1/l),
}

BinaryDispatchKey = tuple[type[BinOp], type[SimpleValue[T]], type[SimpleValue[U]]]
# These are all symmetric meaning you can swap the operand types and the same function will be used (but the arguments should not be swapped)
binary_dispatch_table: dict[BinaryDispatchKey[T, U], TypingCallable[[T, U], AST]|TypingCallable[[U, T], AST]] = {
    (And, Int, Int): lambda l, r: Int(l & r),
    (And, Bool, Bool): lambda l, r: Bool(l and r),
    (Or, Int, Int): lambda l, r: Int(l | r),
    (Or, Bool, Bool): lambda l, r: Bool(l or r),
    (Xor, Int, Int): lambda l, r: Int(l ^ r),
    (Xor, Bool, Bool): lambda l, r: Bool(l != r),
    (Nand, Int, Int): lambda l, r: Int(~(l & r)),
    (Nand, Bool, Bool): lambda l, r: Bool(not (l and r)),
    (Nor, Int, Int): lambda l, r: Int(~(l | r)),
    (Nor, Bool, Bool): lambda l, r: Bool(not (l or r)),
    (Add, Int, Int): lambda l, r: Int(l + r),
    (Add, Int, Float): lambda l, r: Float(l + r),
    (Add, Float, Float): lambda l, r: Float(l + r),
    (Sub, Int, Int): lambda l, r: Int(l - r),
    (Sub, Int, Float): lambda l, r: Float(l - r),
    (Sub, Float, Float): lambda l, r: Float(l - r),
    (Mul, Int, Int): lambda l, r: Int(l * r),
    (Mul, Int, Float): lambda l, r: Float(l * r),
    (Mul, Float, Float): lambda l, r: Float(l * r),
    (Div, Int, Int): int_int_div,
    (Div, Int, Float): float_float_div,
    (Div, Float, Float): float_float_div,
    (Mod, Int, Int): lambda l, r: Int(l % r),
    (Mod, Int, Float): lambda l, r: Float(l % r),
    (Mod, Float, Float): lambda l, r: Float(l % r),
    (Pow, Int, Int): lambda l, r: Int(l ** r),
    (Pow, Int, Float): lambda l, r: Float(l ** r),
    (Pow, Float, Float): lambda l, r: Float(l ** r),
    (Less, Int, Int): lambda l, r: Bool(l < r),
    (Less, Int, Float): lambda l, r: Bool(l < r),
    (Less, Float, Float): lambda l, r: Bool(l < r),
    (LessEqual, Int, Int): lambda l, r: Bool(l <= r),
    (LessEqual, Int, Float): lambda l, r: Bool(l <= r),
    (LessEqual, Float, Float): lambda l, r: Bool(l <= r),
    (Greater, Int, Int): lambda l, r: Bool(l > r),
    (Greater, Int, Float): lambda l, r: Bool(l > r),
    (Greater, Float, Float): lambda l, r: Bool(l > r),
    (GreaterEqual, Int, Int): lambda l, r: Bool(l >= r),
    (GreaterEqual, Int, Float): lambda l, r: Bool(l >= r),
    (GreaterEqual, Float, Float): lambda l, r: Bool(l >= r),
    (Equal, Int, Int): lambda l, r: Bool(l == r),
    (Equal, Float, Float): lambda l, r: Bool(l == r),
    (Equal, Bool, Bool): lambda l, r: Bool(l == r),
    (Equal, String, String): lambda l, r: Bool(l == r),
    # (NotEqual, Int, Int): lambda l, r: Bool(l != r),
    (LeftShift, Int, Int): lambda l, r: Int(l << r),
    (RightShift, Int, Int): lambda l, r: Int(l >> r),

}

unsymmetric_binary_dispatch_table: dict[BinaryDispatchKey[T, U], ] = {
    #e.g. (Mul, String, Int): lambda l, r: String(l * r), # if we follow python's behavior
}

# dispatch table for more complicated values that can't be automatically unpacked by the dispatch table
# TODO: actually ideally just have a single table
CustomBinaryDispatchKey = tuple[type[BinOp], type[T], type[U]]
custom_binary_dispatch_table: dict[CustomBinaryDispatchKey[T, U], TypingCallable[[T, U], AST]] = {
    (Add, Array, Array): lambda l, r: Array(l.items + r.items), #TODO: this will be removed in favor of spread. array add will probably be vector add
    # (BroadcastOp, Array, Array): broadcast_array_op,
    # (BroadcastOp, NpArray, NpArray): broadcast_array_op,
    # (BroadcastOp, Int, Array): broadcast_array_op,
    # (BroadcastOp, Float, Array): broadcast_array_op,

}

#TODO: handling short circuiting for logical operators. perhaps have them in a separate dispatch table

def evaluate_binary_dispatch(op: BinOp, scope: Scope):
    # evaluate the operands
    left = evaluate(op.left, scope)
    right = evaluate(op.right, scope)
    
    # if either operand is undefined, the result is undefined
    if isinstance(left, Undefined) or isinstance(right, Undefined):
        return undefined
    
    # dispatch to the appropriate function
    key = (type(op), type(left), type(right))
    if key in binary_dispatch_table:
        left, right = cast(SimpleValue[T], left), cast(SimpleValue[U], right)
        return binary_dispatch_table[key](left.val, right.val)
    if key in custom_binary_dispatch_table:
        return custom_binary_dispatch_table[key](left, right)

    # if the key wasn't found, try the reverse key (by swapping the types of the operands)
    reverse_key = (type(op), type(right), type(left))
    if reverse_key in binary_dispatch_table:
        left, right = cast(SimpleValue[U], left), cast(SimpleValue[T], right)
        return binary_dispatch_table[reverse_key](left.val, right.val)
    if reverse_key in custom_binary_dispatch_table:
        return custom_binary_dispatch_table[reverse_key](right, left)

    raise NotImplementedError(f'Binary dispatch not implemented for {key=}')

def evaluate_unary_dispatch(op: UnaryPrefixOp|UnaryPostfixOp, scope: Scope):
    # evaluate the operand
    operand = evaluate(op.operand, scope)

    # if the operand is undefined, the result is undefined
    if isinstance(operand, Undefined):
        return undefined
    
    # dispatch to the appropriate function
    key = (type(op), type(operand))
    if key in unary_dispatch_table:
        operand = cast(SimpleValue[T], operand)
        return unary_dispatch_table[key](operand.val)
    
    raise NotImplementedError(f'Unary dispatch not implemented for {key=}')


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
def py_stringify(ast: AST, scope: Scope, top_level:bool=False) -> str:    
    # don't evaluate. already evaluated by resolve_calling_args
    ast = evaluate(ast, scope) if not isinstance(ast, (Builtin, Closure)) else ast
    match ast:
        # types that require special handling (i.e. because they have children that need to be stringified)
        case String(val): return val# if top_level else f'"{val}"'
        case Array(items): return f"[{' '.join(py_stringify(i, scope) for i in items)}]"
        case Dict(items): return f"[{' '.join(py_stringify(kv, scope) for kv in items)}]"
        case PointsTo(left, right): return f'{py_stringify(left, scope)}->{py_stringify(right, scope)}'
        case BidirDict(items): return f"[{' '.join(py_stringify(kv, scope) for kv in items)}]"
        case BidirPointsTo(left, right): return f'{py_stringify(left, scope)}<->{py_stringify(right, scope)}'
        case Range(left, right, brackets): return f'{brackets[0]}{py_stringify_range_operands(left, scope)}..{py_stringify_range_operands(right, scope)}{brackets[1]}'
        case Closure(fn): return f'{fn}'
        case FunctionLiteral() as fn: return f'{fn}'
        case Builtin() as fn: return f'{fn}'
        case Object() as obj: return f'{obj}'
        # case AtHandle() as at: return py_stringify(evaluate(at, scope), scope)

        # can use the built-in __str__ method for these types
        case Int() | Float() | Bool() | Undefined(): return str(ast)

        # TBD what other types need to be handled
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'stringify not implemented for {type(ast)}')
    pdb.set_trace()


    raise NotImplementedError('stringify not implemented yet')

def py_stringify_range_operands(ast: AST, scope: Scope) -> str:
    """helper function to stringify range operands which may be a single value or a tuple (represented as an array)"""
    if isinstance(ast, Array):
        return f"{','.join(py_stringify(i, scope) for i in ast.items)}"
    return py_stringify(ast, scope)

def preprocess_py_print_args(args: list[AST], kwargs: dict[str, AST], scope: Scope) -> tuple[list[Any], dict[str, Any]]:
    py_args = [py_stringify(i, scope, top_level=True) for i in args]
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
        assert isinstance((proto:=scope.vars['printl'].value), PrototypeBuiltin)
        scope.vars['printl'].value = Builtin.from_prototype(proto, preprocess_py_print_args, py_printl)
    if 'print' in scope.vars:
        assert isinstance((proto:=scope.vars['print'].value), PrototypeBuiltin)
        scope.vars['print'].value = Builtin.from_prototype(proto, preprocess_py_print_args, py_print)
    if 'readl' in scope.vars:
        assert isinstance((proto:=scope.vars['readl'].value), PrototypeBuiltin)
        scope.vars['readl'].value = Builtin.from_prototype(proto, lambda *a: ([],{}), py_readl)
