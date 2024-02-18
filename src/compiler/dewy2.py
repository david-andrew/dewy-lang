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
        outtype = self.outtype
        if outtype is None:
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
    def is_instance(val: AST, type: 'Type') -> bool:
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
