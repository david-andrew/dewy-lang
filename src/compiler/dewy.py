"""
[redo of dewy runtime]
remove all reliance on .topy(). .eval() needs to be better fleshed out
--> .eval() means if atom type, return self, otherwise operate/evaluate until there is an atomic type
    --> eval(4) -> 4.  eval(1 + 2) -> 3. eval(() => {5}) -> 5 (or function handle?)  
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


from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import EllipsisType

import pdb


class AST(ABC):
    @abstractmethod
    def eval(self, scope: 'Scope') -> 'AST':
        """Evaluate the AST in the given scope, and return the result (as a dewy obj) if any"""
    # @abstractmethod
    # def comp(self, scope: 'Scope') -> str:
    #     """TODO: future handle compiling an AST to LLVM IR"""
    @abstractmethod
    def typeof(self, scope: 'Scope') -> 'Type':
        """Return the type of the object that would be returned by eval"""
    @abstractmethod
    def treestr(self, prefix='') -> str:
        """Return a string representation of the AST tree"""
    @abstractmethod
    def __str__(self) -> str:
        """Return a string representation of the AST as dewy code"""
    @abstractmethod
    def __repr__(self) -> str:
        """Return a string representation of the python objects making up the AST"""
    @abstractmethod
    def to_string(self, scope: 'Scope') -> 'String':
        """Return a string representation of the AST. Used when automatically converting to string, e.g. in `printl`"""


class Type(AST):
    def __init__(self, name: str, parameters: list = None):
        self.name = name
        self.parameters = parameters or []

    def eval(self, scope: 'Scope') -> 'Type':
        return self

    def typeof(self, scope: 'Scope') -> 'Type':
        return Type('type')

    def treestr(self, prefix='') -> str:
        pdb.set_trace()
        # return prefix + f'Type({self.name})'

    def to_string(self, scope: 'Scope') -> 'String':
        return String(self.__str__())

    def __str__(self) -> str:
        if self.parameters:
            return f'{self.name}<{", ".join(map(str, self.parameters))}>'
        return self.name

    def __repr__(self) -> str:
        return f'Type({self.name}, {self.parameters})'

    def __eq__(self, other):
        pdb.set_trace()

    @staticmethod
    def is_subtype(candidate: 'Type', type: 'Type') -> bool:
        pdb.set_trace()

    @staticmethod
    def is_instance(scope: 'Scope', val: AST, type: 'Type') -> bool:
        pdb.set_trace()


class Undefined(AST):
    """undefined singleton"""

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Undefined, cls).__new__(cls)
        return cls.instance

    def eval(self, scope: 'Scope'):
        return self

    def typeof(self, scope: 'Scope'):
        return Type('undefined')

    def treestr(self, prefix='') -> str:
        return prefix + 'Undefined'

    def to_string(self, scope: 'Scope') -> 'String':
        return String('undefined')

    def __str__(self):
        return 'undefined'

    def __repr__(self):
        return 'Undefined()'


# undefined shorthand, for convenience
undefined = Undefined()


class Void(AST):
    """void singleton"""

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Void, cls).__new__(cls)
        return cls.instance

    def eval(self, scope: 'Scope'):
        return self

    def typeof(self, scope: 'Scope'):
        return Type('void')

    def treestr(self, prefix=''):
        return prefix + 'Void'

    def to_string(self, scope: 'Scope'):
        return String('void')

    def __str__(self):
        return 'void'

    def __repr__(self):
        return 'Void()'


# void shorthand, for convenience
void = Void()


class Scope():

    @dataclass
    class _var():
        # name:str #name is stored in the dict key
        type: AST
        value: AST
        const: bool

    def __init__(self, parent: 'Scope|None' = None):
        self.parent = parent
        self.vars: dict[str, Scope._var] = {}

        # used for function calls
        # TODO: from now on, we just make a new scope for holding args
        # self.args: Array | None = None

    @property
    def root(self) -> 'Scope':
        """Return the root scope"""
        return [*self][-1]

    def let(self, name: str, type: 'Type|Undefined', value: AST, const: bool):
        # overwrite anything that might have previously been there
        self.vars[name] = Scope._var(type, value, const)

    def get(self, name: str, default: AST = None) -> AST:
        # get a variable from this scope or any of its parents
        for s in self:
            if name in s.vars:
                return s.vars[name].value
        if default is not None:
            return default
        raise NameError(f'{name} not found in scope {self}')

    def bind(self, name: str, value: AST):

        # update an existing variable in this scope or  any of the parent scopes
        for s in self:
            if name in s.vars:
                var = s.vars[name]
                assert not var.const, f'cannot assign to const {name}'
                assert Type.is_instance(value.typeof(), var.type), f'cannot assign {
                    value}:{value.typeof()} to {name}:{var.type}'
                var.value = value
                return

        # otherwise just create a new instance of the variable
        self.vars[name] = Scope._var(undefined, value, False)

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

    def copy(self):
        s = Scope(self.parent)
        s.vars = self.vars.copy()
        return s

    @staticmethod
    def default():
        """return a scope with the standard library (of builtins) included"""
        root = Scope()
        # root.bind('print', Builtin('print', [Arg('text')], None, Type('callable', [Array([String.type]), Undefined.type])))
        # root.bind('printl', Builtin('printl', [Arg('text')], None, Type('callable', [Array([String.type]), Undefined.type])))
        # root.bind('readl', Builtin('readl', [], String, Type('callable', [Array([]), String.type])))
        # TODO: eventually add more builtins

        return root


class Orderable(AST):
    """An object that can be sorted relative to other objects of the same type"""
    @abstractmethod
    def compare(self, other: 'Orderable', scope: 'Scope') -> 'Number':
        """Return a value indicating the relationship between this value and another value"""
    # @staticmethod
    # @abstractmethod
    # def max() -> 'Rangeable':
    #     """Return the maximum element from the set of all elements of this type"""
    # @staticmethod
    # @abstractmethod
    # def min() -> 'Rangeable':
    #     """Return the minimum element from the set of all elements of this type"""

# TODO: come up with a better name for this class... successor and predecessor are only used for range iterators, not ranges themselves
#        e.g. Incrementable, Decrementable, etc.


class Rangeable(Orderable):
    """An object that can be used to specify bounds of a range"""
    @abstractmethod
    def successor(self, step: 'Number', scope: 'Scope') -> 'Rangeable':
        """Return the next value in the range"""
    @abstractmethod
    def predecessor(self, step: 'Number', scope: 'Scope') -> 'Rangeable':
        """Return the previous value in the range"""


class Unpackable(AST):
    @abstractmethod
    def len(self, scope: 'Scope') -> int:
        """Return the length of the unpackable"""
    @abstractmethod
    def get(self, key: int | EllipsisType | slice | tuple[int | EllipsisType | slice], scope: 'Scope') -> AST:
        """Return the item at the given index"""
# TODO: make a type annotation for Unpackable[N] where N is the number of items in the unpackable?
#        would maybe replace the len property?


class Iter(AST):
    @abstractmethod
    def next(self, scope: 'Scope') -> Unpackable:  # TODO: TBD on the return type. need dewy tuple type...
        """Get the next item from the iterator"""


class Iterable(AST):
    # TODO: maybe don't need scope for this method...
    @abstractmethod
    def iter(self, scope: 'Scope') -> Iter:
        """Return an iterator over the iterable"""


class Flowable(AST):
    @abstractmethod
    def was_entered(self) -> bool:
        """Determine if the flowable branch was entered. Should reset before performing calls to flow and checking this."""
    @abstractmethod
    def reset_was_entered(self) -> None:
        """reset the state of was_entered, in preparation for executing branches in a flow"""


class Identifier(AST):
    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return f'{self.name}'

    def __repr__(self) -> str:
        return f'Identifier({self.name})'

    def eval(self, scope: Scope) -> AST:
        return scope.get(self.name)

    def typeof(self, scope: Scope) -> Type:
        pdb.set_trace()

    def treestr(self, prefix='') -> str:
        return prefix + f'Identifier: {self.name}'

    def to_string(self, scope: Scope) -> 'String':
        return String(self.name)


class Array(Iterable, Unpackable):
    def __init__(self, vals: list[AST]):
        self.vals = vals

    def eval(self, scope: Scope):
        return self

    def typeof(self, scope: Scope):
        pdb.set_trace()
        # TODO: this should include the type of the data inside the vector...
        return Type('Array')

    # unpackable interface
    def len(self, scope: Scope):
        return len(self.vals)

    def get(self, key: int | EllipsisType | slice | tuple[int | EllipsisType | slice], scope: Scope):
        if isinstance(key, int):
            return self.vals[key]
        elif isinstance(key, EllipsisType):
            return self
        elif isinstance(key, slice):
            return Array(self.vals[key])
        elif isinstance(key, tuple):
            # probably only valid for N-dimensional/non-jagged vectors
            raise NotImplementedError('TODO: implement tuple indexing for Array')
        else:
            raise TypeError(f'invalid type for Array.get: `{key}` of type `{type(key)}`')

    def iter(self, scope: Scope) -> Iter:
        return ArrayIter(self)

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

    def eval(self, scope: Scope):
        return self

    def next(self, scope: Scope = None) -> Unpackable:
        if self.array is None:
            self.array = self.ast.eval(scope)
            assert isinstance(self.array, Array), f'ArrayIter must be initialized with an AST that evaluates to an Array, not {
                type(self.array)}'
            self.i = 0

        if self.i < len(self.array.vals):
            ret = self.array.vals[self.i]
            self.i += 1
            return Array([Bool(True), ret])

        return Array([Bool(False), undefined])

    def typeof(self):
        return Type('ArrayIter')

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

    def eval(self, scope: Scope):
        return self

    def typeof(self, scope: Scope):
        return self.type
    # TODO: implement rangable methods

    def treestr(self, indent=0):
        return f'{tab * indent}String: `{self.val}`'

    def to_string(self, scope: Scope):
        return self

    def compare(self, other: 'String', scope: 'Scope') -> 'Number':
        pdb.set_trace()

    def successor(self, step: 'Number', scope: 'Scope') -> 'String':
        pdb.set_trace()

    def predecessor(self, step: 'Number', scope: 'Scope') -> 'String':
        pdb.set_trace()

    def __str__(self):
        return f'"{self.val}"'

    def __repr__(self):
        return f'String({repr(self.val)})'


class IString(AST):
    def __init__(self, parts: list[AST]):
        self.parts = parts

    def eval(self, scope: Scope = None):
        # convert self into a String()
        return String(self.topy(scope))

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


class Function(AST):
    ...


class AtHandle(AST):
    ...
