"""
[redo of dewy runtime]
remove all reliance on .topy(). .eval() needs to be better fleshed out
--> .eval() means if atom type, return self, otherwise operate/evaluate until there is an atomic type
    --> eval(4) -> 4.  eval(1 + 2) -> 3. eval(() => {5}) -> () => {5}. eval(eval(() => {5})) -> 5. eval(eval(4)) -> 4
FunctionHandle(AST)
--> .eval returns a Function (perhaps different name...)
--> Function.eval() evaluates the function


On each new binop AST, add an entry to the type table
--> any types that want to use that binop must register in the table first.
    registration is basically just how to get the result given the input types
    e.g. __add__ binop, need to register left:int, right:int => left + right
--> All of the binop outtype should be handled by looking up in the table
    ```
    def eval(self, scope):
        left = self.left.eval(scope)
        right = self.right.eval(scope)

        #lookup outtype based on the table
        outtype = types_table[self.__class__][left.typeof(), right.typeof()]

        return outtype(self.op(left.topy(), right.topy()))
    ```



implement .typeof() more extensively
--> .typeof() is basically saying, if you call .eval() on this, what type will the result be

nand, nor, xnor currently won't work work on integers, only booleans...

dealing with scopes, especially during parsing... handling function declarations, partial evaluation, etc.

handling case insensitive identifiers (e.g. for units)
"""


from dataclasses import dataclass
from .ast import Type, Undefined, Void, AST, DeclarationType

# from abc import ABC, abstractmethod
# from dataclasses import dataclass, field
# from types import EllipsisType
# from typing import Callable as PyCallable


# import pdb



# TODO: turn into a singleton...
# untyped type for when a declaration doesn't specify a type
untyped = Type('untyped')

# undefined shorthand, for convenience
undefined = Undefined()

# void shorthand, for convenience
void = Void()




class Scope():
    _empty = None

    @dataclass
    class _var():
        # name:str #name is stored in the dict key
        decltype: DeclarationType
        type: AST
        value: AST

    def __init__(self, parent: 'Scope|None' = None, readonly=False):
        self.parent = parent
        self.vars: dict[str, Scope._var] = {}
        # self.combos: dict[tuple[list[str], ...], Function] = {} #TODO: mainly for handling unit combo identifiers such, e.g. <kilo><gram>
        self.readonly = readonly

    @property
    def root(self) -> 'Scope':
        """Return the root scope"""
        return [*self][-1]

    def declare(self, decltype: DeclarationType, name: str, type: Type, value: AST = undefined):
        if self.readonly:
            raise ValueError(f'cannot declare in a readonly scope')
        if name in self.vars:
            pdb.set_trace()  # TODO: are there circumstances overwriting an existing variable is allowed? e.g. if it was LET?
            raise NameError(f'Cannot redeclare "{name}". already exists in scope {self} with value {self.vars[name]}')
        self.vars[name] = Scope._var(decltype, type, value)

    # def combo(self, *names: dict[str, AST], postprocess: PyCallable[[list[AST]], AST]):
    #     pdb.set_trace()
    #     ...

    def get(self, name: str, default: AST = None) -> AST:
        # pdb.set_trace()
        # get a variable from this scope or any of its parents
        for s in self:
            if name in s.vars:
                return s.vars[name].value
        if default is not None:
            return default
        raise NameError(f'{name} not found in scope {self}')

    def bind(self, name: str, value: AST):
        if self.readonly:
            raise ValueError(f'cannot bind in a readonly scope')
        pdb.set_trace()  # dealing with local, alias, etc. other cases
        # update an existing variable in this scope or  any of the parent scopes
        for s in self:
            if name in s.vars:
                var = s.vars[name]
                assert not var.const, f'cannot assign to const {name}'
                assert Type.is_instance(value.typeof(), var.type), f'cannot assign {
                    value}:{value.typeof()} to {name}:{var.type}'
                var.value = value
                return

        # TODO: consider what the declaration type default should be. Or maybe we just disallow binding to undeclared variables
        # otherwise just create a new instance of the variable
        self.vars[name] = Scope._var(DeclarationType.DEFAULT, untyped, value)

    def __iter__(self):
        """return an iterator that walks up each successive parent scope. Starts with self"""
        s = self
        while s is not None:
            yield s
            s = s.parent

    def __repr__(self):
        if self.parent is not None:
            return f'Scope({self.vars}, {repr(self.parent)})'
        return f'Scope({self.vars})'

    # def copy(self):
    #     s = Scope(self.parent)
    #     s.vars = self.vars.copy()
    #     return s

    # TODO: would be nice if this was read-only, i.e. no declaring or binding allowed
    @staticmethod
    def empty():
        if Scope._empty is None:
            Scope._empty = Scope(readonly=True)
        return Scope._empty

    @staticmethod
    def default():
        """return a scope with the standard library (of builtins) included"""
        root = Scope()

        def pyprint(scope: Scope):
            print(scope.get('text').to_string(scope).val, end='')
            return void
        pyprint_ast = Function(
            [Declare(DeclarationType.DEFAULT, 'text', Type('string'))],
            [],
            PyAction(pyprint, Type('void')),
            Scope.empty()
        )
        root.declare(DeclarationType.LOCAL_CONST, 'print', pyprint_ast.typeof(root), pyprint_ast)

        def pyprintl(scope: Scope):
            print(scope.get('text').to_string(scope).val)
            return void
        pyprintl_ast = Function(
            [Declare(DeclarationType.DEFAULT, 'text', Type('string'))],
            [],
            PyAction(pyprintl, Type('void')),
            Scope.empty()
        )
        root.declare(DeclarationType.LOCAL_CONST, 'printl', pyprintl_ast.typeof(root), pyprintl_ast)

        def pyreadl(scope: Scope):
            return String(input())
        pyreadl_ast = Function([], [], PyAction(pyreadl, Type('string')), Scope.empty())
        root.declare(DeclarationType.LOCAL_CONST, 'readl', pyreadl_ast.typeof(root), pyreadl_ast)

        # TODO: eventually add more builtins

        return root



# class Orderable(AST):
#     """An object that can be sorted relative to other objects of the same type"""
#     @abstractmethod
#     def compare(self, other: 'Orderable', scope: 'Scope') -> 'Number':
#         """Return a value indicating the relationship between this value and another value"""


# class Boundable(AST):
#     @staticmethod
#     @abstractmethod
#     def max() -> 'Rangeable':
#         """Return the maximum element from the set of all elements of this type"""
#     @staticmethod
#     @abstractmethod
#     def min() -> 'Rangeable':
#         """Return the minimum element from the set of all elements of this type"""


# class Rangeable(Orderable):
#     # TODO: come up with a better name for this class... successor and predecessor are only used for range iterators, not ranges themselves
#     #        e.g. Incrementable, Decrementable, etc.
#     """An object that can be used to specify bounds of a range"""
#     @abstractmethod
#     def successor(self, step: 'Number', scope: 'Scope') -> 'Rangeable':
#         """Return the next value in the range"""
#     @abstractmethod
#     def predecessor(self, step: 'Number', scope: 'Scope') -> 'Rangeable':
#         """Return the previous value in the range"""


# class Unpackable(AST):
#     # TODO: need to handle unpacking of objects + unpacking dicts
#     @abstractmethod
#     def len(self, scope: 'Scope') -> int:
#         """Return the length of the unpackable"""
#     @abstractmethod
#     def get(self, key: int | EllipsisType | slice | tuple[int | EllipsisType | slice], scope: 'Scope') -> AST:
#         """Return the item at the given index"""
# # TODO: make a type annotation for Unpackable[N] where N is the number of items in the unpackable?
# #        would maybe replace the len property?


# class Iter(AST):
#     @abstractmethod
#     def next(self, scope: 'Scope') -> Unpackable:  # TODO: TBD on the return type, e.g. Tuple[Bool, AST]
#         """Get the next item from the iterator"""


# class Iterable(AST):
#     # TODO: maybe don't need scope for this method...
#     @abstractmethod
#     def iter(self, scope: 'Scope') -> Iter:
#         """Return an iterator over the iterable"""


# class Flowable(AST):
#     @abstractmethod
#     def was_entered(self) -> bool:
#         """Determine if the flowable branch was entered. Should reset before performing calls to flow and checking this."""
#     @abstractmethod
#     def reset_was_entered(self) -> None:
#         """reset the state of was_entered, in preparation for executing branches in a flow"""


class PyAction(AST):
    def __init__(self, action: PyCallable[[Scope], AST], return_type: Type):
        self.action = action
        self.return_type = return_type

    # def eval(self, scope: Scope):
    #     return self.action(scope)

    # def typeof(self, scope: Scope):
    #     return self.return_type

    def treestr(self, prefix=''):
        return prefix + f'PyAction: {self.action}'

    # def to_string(self, scope: Scope):
    #     return String(f'<PyAction: {self.action}>')

    def __str__(self):
        return f'PyAction({self.action})'

    def __repr__(self):
        return f'PyAction({self.action}, {self.return_type})'


class Array(Iterable, Unpackable):
    def __init__(self, vals: list[AST]):
        self.vals = vals

    # def eval(self, scope: Scope):
    #     return self

    # def typeof(self, scope: Scope):
    #     pdb.set_trace()
    #     # TODO: this should include the type of the data inside the vector...
    #     return Type('Array')

    # # unpackable interface
    # def len(self, scope: Scope):
    #     return len(self.vals)

    # def get(self, key: int | EllipsisType | slice | tuple[int | EllipsisType | slice], scope: Scope):
    #     if isinstance(key, int):
    #         return self.vals[key]
    #     elif isinstance(key, EllipsisType):
    #         return self
    #     elif isinstance(key, slice):
    #         return Array(self.vals[key])
    #     elif isinstance(key, tuple):
    #         # probably only valid for N-dimensional/non-jagged vectors
    #         raise NotImplementedError('TODO: implement tuple indexing for Array')
    #     else:
    #         raise TypeError(f'invalid type for Array.get: `{key}` of type `{type(key)}`')

    # def iter(self, scope: Scope) -> Iter:
    #     return ArrayIter(self)

    def treestr(self, prefix=''):
        s = prefix + 'Array\n'
        for v in self.vals:
            s += v.treestr(indent + 1) + '\n'
        return s

    def __str__(self):
        return f'[{" ".join(map(str, self.vals))}]'

    def __repr__(self):
        return f'Array({repr(self.vals)})'


class ArrayIter(Iter):
    def __init__(self, ast: AST):
        self.ast = ast

        self.array = None
        self.i = None

    # def eval(self, scope: Scope):
    #     return self

    # def next(self, scope: Scope = None) -> Unpackable:
    #     if self.array is None:
    #         self.array = self.ast.eval(scope)
    #         assert isinstance(self.array, Array), f'ArrayIter must be initialized with an AST that evaluates to an Array, not {
    #             type(self.array)}'
    #         self.i = 0

    #     if self.i < len(self.array.vals):
    #         ret = self.array.vals[self.i]
    #         self.i += 1
    #         return Array([Bool(True), ret])

    #     return Array([Bool(False), undefined])

    # def typeof(self):
    #     return Type('ArrayIter')

    def treestr(self, prefix=''):
        return f'{prefix}ArrayIter:\n{self.ast.treestr(indent + 1)}'

    def __str__(self):
        return f'ArrayIter({self.ast})'

    def __repr__(self):
        return f'ArrayIter({repr(self.ast)})'


class String(Rangeable):
    type: Type = Type('string')

    def __init__(self, val: str):
        self.val = val

    # def eval(self, scope: Scope):
    #     return self

    # def typeof(self, scope: Scope):
    #     return self.type
    # # TODO: implement rangable methods

    def treestr(self, indent=0):
        return f'{tab * indent}String: `{self.val}`'

    # def to_string(self, scope: Scope):
    #     return self

    # def compare(self, other: 'String', scope: 'Scope') -> 'Number':
    #     pdb.set_trace()

    # def successor(self, step: 'Number', scope: 'Scope') -> 'String':
    #     pdb.set_trace()

    # def predecessor(self, step: 'Number', scope: 'Scope') -> 'String':
    #     pdb.set_trace()

    def __str__(self):
        return f'"{self.val}"'

    def __repr__(self):
        return f'String({repr(self.val)})'


class IString(AST):
    def __init__(self, parts: list[AST]):
        self.parts = parts

    # def eval(self, scope: Scope = None):
    #     # convert self into a String()
    #     return String(self.topy(scope))

    def treestr(self, indent=0):
        s = tab * indent + 'IString\n'
        for part in self.parts:
            s += part.treestr(indent + 1) + '\n'
        return s

    def __str__(self):
        s = ''
        for part in self.parts:
            if isinstance(part, String):
                s += part.val
            else:
                s += f'{{{part}}}'
        return f'"{s}"'

    def __repr__(self):
        return f'IString({repr(self.parts)})'


# class FunctionLiteral(AST):
#     def __init__(self, args: list[Declare], kwargs: list[Bind], body: AST):
#         self.args = args
#         self.kwargs = kwargs
#         self.body = body

#     def eval(self, scope: Scope) -> 'Function':
#         return Function(self.args, self.kwargs, self.body, scope)


class Function(AST):
    def __init__(self, args: list[Declare], kwargs: list[Bind], body: AST, decl_scope: Scope):

        # ensure no duplicate names
        arg_names = {arg.name for arg in args}
        kwarg_names = {kwarg.target.name for kwarg in kwargs}
        assert arg_names.isdisjoint(kwarg_names), f'args and kwargs cannot share any names. Names found in both: {
            arg_names & kwarg_names}'

        self.args = args
        self.kwargs = kwargs
        self.body = body

        # as positional args are bound, they are transferred into the kwargs list

    # def partial_eval(self, update: list[Bind]):
    #     # update the args/kwargs with the new values
    #     assert all(u.value is not void for u in update), f'cannot partially evaluate with void values. Update: {update}'
    #     assert all(isinstance(u.target, Identifier)
    #                for u in update), f'can only partially evaluate with identifiers, not declarations. Update: {update}'
    #     for u in update:
    #         try:
    #             arg_names = [arg.name for arg in self.args]
    #             i = arg_names.index(u.target.name)  # raises ValueError if not found
    #             decl = self.args.pop(i)
    #             self.kwargs.append(Bind(decl, u.value))
    #         except ValueError:
    #             kwarg_names = [kwarg.target.name for kwarg in self.kwargs]
    #             i = kwarg_names.index(u.target.name)
    #             self.kwargs[i].value = u.value

    # def eval(self, scope: Scope) -> AST:
    #     # this is the scope that passed in arguments come from
    #     # decl_scope is where any closure captured variables come from
    #     # execution of functions happens in a child of the decl_scope
    #     pdb.set_trace()

    # def typeof(self, scope: Scope):
    #     # TODO: make this include arg types and return type
    #     return Type('callable')
    #     # argtypes = [arg.typeof(scope) for arg in self.args]
    #     # kwargtypes = [kwarg.typeof(scope) for kwarg in self.kwargs]
    #     # something to do with body.typeof(), but need to allow any argument types to also come into play
    #     # honestly gets complicated especially with parametric types, etc.

    def treestr(self, indent=0):
        s = tab * indent + 'Function\n'
        for arg in self.args:
            s += arg.treestr(indent + 1) + '\n'
        s += self.body.treestr(indent + 1)
        return s

    # def to_string(self, scope: Scope):
    #     return String(self.__str__())

    def __str__(self):
        return f'({", ".join(map(str, self.args))}) => {self.body}'

    def __repr__(self):
        return f'Function({repr(self.args)}, {repr(self.body)})'

# TODO: behavior might change depending on precedence of @ and juxtaposition


class AtHandle(AST):
    def __init__(self, id: Identifier):
        # TODO: identifier must be a function or other callable...
        self.id = id

    # def eval(self, scope: Scope) -> Identifier:
    #     pdb.set_trace()
    #     return self.id


class CallWithArgs(AST):
    def __init__(self, fn: AST, args: list[Declare], kwargs: list[Bind]):
        self.fn = fn
        self.args = args

    # def eval(self, scope: Scope):
    #     pdb.set_trace()
