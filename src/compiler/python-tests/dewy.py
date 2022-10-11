from abc import ABC
from collections import defaultdict, namedtuple
from dataclasses import dataclass
from types import NoneType, EllipsisType
from typing import Any, List, Tuple as PyTuple, Callable as PyCallable, Union
from functools import partial

import pdb
import typing

#Written in python3.10

#dumb look at interpreting/compiling dewy
#for now, construct the AST directly, skipping the parsing step


#convenient for inside lambdas
def notimplemented():
    raise NotImplementedError()

class AST(ABC):
    def eval(self, scope:'Scope'=None) -> 'AST':
        """Evaluate the AST in the given scope, and return the result (as a dewy obj) if any"""
        raise NotImplementedError(f'{self.__class__.__name__}.eval')
    def topy(self, scope:'Scope'=None) -> Any:
        """Convert the AST to a python equivalent object (usually unboxing the dewy object)"""
        raise NotImplementedError(f'{self.__class__.__name__}.topy')
    def comp(self, scope:'Scope'=None) -> str:
        """TODO: future handle compiling an AST to LLVM IR"""
        raise NotImplementedError(f'{self.__class__.__name__}.comp')
    def type(self, scope:'Scope'=None) -> 'Type':
        """Return the type of the object that would be returned by eval"""
        raise NotImplementedError(f'{self.__class__.__name__}.type')
    #TODO: other methods, e.g. semantic analysis
    def treestr(self, indent=0) -> str:
        """Return a string representation of the AST tree"""
        raise NotImplementedError(f'{self.__class__.__name__}.treestr')
    def __str__(self) -> str:
        """Return a string representation of the AST as dewy code"""
        raise NotImplementedError(f'{self.__class__.__name__}.__str__')
    def __repr__(self) -> str:
        """Return a string representation of the python objects making up the AST"""
        raise NotImplementedError(f'{self.__class__.__name__}.__repr__')

class Callable(AST):
    def call(self, scope:'Scope'=None):
        """Call the callable in the given scope"""
        raise NotImplementedError(f'{self.__class__.__name__}.call')

class Iterable(AST):
    def iter(self, scope:'Scope'=None) -> 'Iter':
        """Return an iterator over the iterable"""
        raise NotImplementedError(f'{self.__class__.__name__}.iter')

class Iter(AST):
    def next(self, scope:'Scope'=None):# -> Tuple[AST,AST]: #TODO: TBD on the return type. need dewy tuple type...
        """Get the next item from the iterator"""
        raise NotImplementedError(f'{self.__class__.__name__}.next')

class Unpackable(AST):
    def len(self, scope:'Scope'=None) -> int:
        """Return the length of the unpackable"""
        raise NotImplementedError(f'{self.__class__.__name__}.len')
    def get(self, key:int|EllipsisType|slice|PyTuple[int|EllipsisType|slice], scope:'Scope'=None) -> AST:
        """Return the item at the given index"""
        raise NotImplementedError(f'{self.__class__.__name__}.get')
#TODO: make a type annotation for Unpackable[N] where N is the number of items in the unpackable?
#        would maybe replace the len property?


class Undefined(AST):
    def __init__(self):
        pass
    def eval(self, scope:'Scope'=None):
        return self
    def topy(self, scope:'Scope'=None):
        return None
    def type(self, scope:'Scope'=None):
        return Type('undefined')
    def treesr(self, indent=0):
        return tab * indent + 'Undefined'
    def __str__(self):
        return 'undefined'
    def __repr__(self):
        return 'Undefined()'

#make any further calls to Undefined() return the same singleton instance
undefined = Undefined()
Undefined.__new__ = lambda cls: undefined


tab = '    ' #for printing ASTs
BArg = PyTuple[str, AST]   #bound argument + current value for when making function calls

class Scope():
    
    @dataclass
    class _var():
        # name:str #name is stored in the dict key
        type:AST
        value:AST
        const:bool
    
    def __init__(self, parent:Union['Scope',NoneType]=None):
        self.parent = parent
        self.vars = {}
        
        #used for function calls
        self.args:List[AST] = [] 
        self.bargs:List[BArg] = []

    def let(self, name:str, type:'Type'=undefined, value:AST=undefined, const=False):
        #overwrite anything that might have previously been there
        self.vars[name] = Scope._var(type, value, const)


    def get(self, name:str) -> AST:
        #get a variable from this scope or any of its parents
        for s in self:
            if name in s.vars:
                return s.vars[name].value
        raise NameError(f'{name} not found in scope {self}')

    def bind(self, name:str, value:AST):

        #update an existing variable in this scope or  any of the parent scopes
        for s in self:
            if name in s.vars:
                var = s.vars[name]
                assert not var.const, f'cannot assign to const {name}'
                assert Type.compatible(var.type, value.type()), f'cannot assign {value}:{value.type()} to {name}:{var.type}'
                var.value = value
                return

        #otherwise just create a new instance of the variable
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

    def attach_args(self, args:List[AST], bargs:List[BArg]): 
        self.args = args
        self.bargs = bargs


#probably won't use this, except possibly for when calling functions and providing enums from the function's scope
# def merge_scopes(*scopes:List[Scope], onto:Scope=None):
#     #TODO... this probably could actually be a scope union class that inherits from Scope
#     #            that way we don't have to copy the scopes
#     pdb.set_trace()


class Type(AST):
    def __init__(self, name:str, params:List[AST]=None):
        self.name = name
        self.params = params
    def eval(self, scope:Scope=None):
        return self

    def treestr(self, indent=0):
        s = tab * indent + f'Type: {self.name}\n'
        for p in self.params:
            s += p.__str__(indent + 1) + '\n'
        return s

    def __str__(self):
        if self.params is not None and len(self.params) > 0:
            return f'{self.name}<{", ".join(map(str, self.params))}>'
        return self.name

    def __repr__(self):
        return f'Type({self.name}, {self.params})'

    def __eq__(self, other):
        if isinstance(other, Type):
            return self.name == other.name and self.params == other.params
        return False
    
    @staticmethod
    def compatible(rule:AST, candidate:AST) -> bool:
        assert isinstance(rule, Type) or rule is undefined, f'rule must be a Type or undefined, not {rule}'
        assert isinstance(candidate, Type) or candidate is undefined, f'candidate must be a Type or undefined, not {candidate}'
        if rule is undefined:
            return True
        if rule == candidate:
            return True
        
        #TODO: check type graph for compatibility
        # pdb.set_trace()

        return False

class Arg:
    def __init__(self, name:str, type:Type=None, val:AST=None):
        self.name = name
        self.val = val
        self.type = type
    def __str__(self):
        s = f'{self.name}'
        if self.type is not None:
            s += f':{repr(self.type)}'
        if self.val is not None:
            s += f' = {repr(self.val)}'
        return s
    def __repr__(self):
        s = f'Arg({self.name}'
        if self.type is not None:
            s += f', {repr(self.type)}'
        if self.val is not None:
            s += f', {repr(self.val)}'
        s += ')'
        return s


class Function(Callable):
    def __init__(self, args:List[Arg], body:AST, scope:Scope=None):
        self.args = args
        self.body = body
        self.scope = scope #scope where the function was defined, which may be different from the scope where it is called
    
    def eval(self, scope:Scope=None):
        return self
    
    def call(self, scope:Scope=None):
        #collect args from calling scope, and merge into function scope
        fscope = self.scope.copy()
        
        #TODO: this probably doesn't handle when the named vs unnamed call arguments are not exactly the same as defined
        for arg in self.args:
            if arg.val is None:
                fscope.bind(arg.name, scope.args.pop(0))
            else:
                fscope.bind(arg.name, arg.val)
        assert len(scope.args) == 0, f'not all arguments were used in function call {self}'
        for name, val in scope.bargs:
            assert name in [a.name for a in self.args], f'unknown argument {name} in function call {self}'
            fscope.bind(name, val)
        scope.bargs = []

        #check that all unnamed args have values in the scope
        #TODO: make this check more robust + better error messages
        # for name in self.args[len(scope.args):]:
        #     if name not in fscope.vars:
        #         raise TypeError(f'function {self} missing argument {name}')

        return self.body.eval(fscope)

    def treestr(self, indent=0):
        s = tab * indent + f'Function()\n'
        for arg in self.args:
            s += tab * (indent + 1) + f'Arg: {arg.name}\n'
            if arg.type is not None:
                s += arg.type.treestr(indent + 2) + '\n'
            if arg.val is not None:
                s += arg.val.treestr(indent + 2) + '\n'
        s += tab*(indent+1) + 'Body:\n' + self.body.treestr(indent + 2)
        return s

    def __str__(self):
        s = ''
        if len(self.args) == 1:
            s += f'{self.args[0]}'
        else:
            s += f'({", ".join(map(str, self.args))})'
        s += f' => {self.body}'
        return s

    def __repr__(self):
        return f'Function(args:{self.args}, body:{self.body}, scope:{self.scope})'

class Builtin(Callable):
    funcs = {
        'print': partial(print, end=''),
        'printl': print,
        'readl': input
    }
    def __init__(self, name:str, args:List[Arg], cls:PyCallable=None):
        self.name = name
        self.args = args
        self.cls = cls
    
    def eval(self, scope:Scope=None):
        return self
    
    def call(self, scope:Scope=None):
        if self.name in Builtin.funcs:
            f = Builtin.funcs[self.name]
            #TODO: this doesn't handle differences in named vs unnamed args between the function definition and the call
            args = [scope.args[i].eval(scope).topy(scope) for i, a in enumerate(self.args) if a.val is None]
            kwargs = {a: a.val.eval(scope).topy(scope) for a in self.args if a.val is not None}
            for name, val in scope.bargs:
                kwargs[name] = val.eval(scope).topy(scope)
            result = f(*args, **kwargs)
            if self.cls is not None:
                return self.cls(result)
        else:
            raise NameError(self.name, 'is not a builtin')

    def treestr(self, indent=0):
        s = tab * indent + f'Builtin({self.name})\n'
        for arg in self.args:
            s += tab * (indent + 1) + f'Arg: {arg.name}\n'
            if arg.type is not None:
                s += arg.type.treestr(indent + 2) + '\n'
            if arg.val is not None:
                s += arg.val.treestr(indent + 2) + '\n'
        return s

    def __str__(self):
        return f'{self.name}({", ".join(map(str, self.args))})'

    def __repr__(self):
        return f'Builtin({self.name}, {self.args})'


class Let(AST):
    def __init__(self, name:str, type:Type, value:AST=undefined, const=False):
        self.name = name
        self.type = type
        self.value = value
        self.const = const

    def eval(self, scope:Scope=None):
        scope.let(self.name, self.type, self.value, self.const)

    def treestr(self, indent=0):
        return f'{tab * indent}{"Const" if self.const else "Let"}: {self.name}\n{self.type.treestr(indent + 1)}'

    def __str__(self):
        return f'{"const" if self.const else "let"} {self.name}:{self.type}'

    def __repr__(self):
        return f'{"Const" if self.const else "Let"}({self.name}, {self.type})'


class Bind(AST):
    #TODO: allow bind to take in an unpack structure
    def __init__(self, name:str, value:AST):
        self.name = name
        self.value = value
    def eval(self, scope:Scope=None):
        scope.bind(self.name, self.value.eval(scope))

    def treestr(self, indent=0):
        return f'{tab * indent}Bind: {self.name}\n{self.value.treestr(indent + 1)}'

    def __str__(self):
        return f'{self.name} = {self.value}'

    def __repr__(self):
        return f'Bind({self.name}, {repr(self.value)})'


class PackStruct(List[Union[str,'PackStruct']]):
    """
    represents the type for left hand side of an unpack operation

    unpacking operations in dewy look like this:
    [a, b, c] = [1 2 3]                                         //a=1, b=2, c=3
    [a, [b, c]] = [1 [2 3]]                                     //a=1, b=2, c=3
    [a, [b, c], d] = [1 [2 3] 4]                                //a=1, b=2, c=3, d=4
    [a, ...b] = [1 2 3 4]                                       //a=1, b=[2 3 4]
    [a, ...b, c] = [1 2 3 4 5]                                  //a=1, b=[2 3 4], c=5
    [a, ...b, [c, [...d, e, f]]] = [1 2 3 4 [5 [6 7 8 9 10]]]   //a=1, b=[2 3 4], c=5, d=[6 7 8], e=9, f=10

    note that there may only be one ellipsis in a given level of the structure
    """
    ...



class Unpack(AST):
    def __init__(self, struct:PackStruct, value:Unpackable):
        #check that there is only one ellipsis in the top level of the structure (lower levels are checked recursively)
        #TODO: problem with checking lower levels recursively is that it is no longer a compile time check
        assert sum(1 for s in struct if s.startswith('...')) <= 1, 'only one ellipsis is allowed per level of the structure'
        self.struct = struct
        self.value = value

    def eval(self, scope:Scope=None):
        value = self.value.eval(scope)
        assert isinstance(value, Unpackable), f'{value} is not unpackable'
        for i, s in enumerate(self.struct):
            if isinstance(s, str):
                if s.startswith('...'):
                    n = len(self.struct) - i - 1 #number of elements after the ellipsis
                    name = s[3:]
                    scope.bind(name, value.get(slice(i,-n), scope))
                else:
                    scope.bind(s, value.get(i, scope))
            elif isinstance(s, list):
                Unpack(s, value.get(i, scope)).eval(scope)
            else:
                raise TypeError(f'invalid type in unpack structure: `{s}` of type `{type(s)}`')

    def treestr(self, indent=0):
        return f'{tab * indent}Unpack: {self.struct}\n{self.value.treestr(indent + 1)}'

    def __str__(self):
        return f'{self.struct} = {self.value}'

    def __repr__(self):
        return f'Unpack({self.struct}, {self.value})'



class Block(AST):
    def __init__(self, exprs:List[AST], newscope:bool=True):
        self.exprs = exprs
        self.newscope = newscope
    def eval(self, scope:Scope=None):
        #TODO: handle flow control from a block, e.g. return, break, continue, express, etc.
        if self.newscope:
            scope = Scope(scope)
        ret = undefined
        for expr in self.exprs:
            ret = expr.eval(scope)
        return ret

    def treestr(self, indent=0):
        """print each expr on its own line, indented"""
        s = tab * indent + 'Block\n'
        for expr in self.exprs:
            s += expr.treestr(indent + 1)
        return s

    def __str__(self):
        return f'{{{" ".join(map(str, self.exprs))}}}'

    def __repr__(self):
        return f'Block({repr(self.exprs)})'


class Call(AST):
    def __init__(self, name:str, args:List[AST]=[], bargs:List[BArg]=[]):
        self.name = name
        self.args = args
        self.bargs = bargs

    def eval(self, scope:Scope):
        #make a fresh scope we can modify, and attach the calling args to it
        scope = scope.copy()
        scope.attach_args(self.args, self.bargs)

        #functions get called with args, while everything else just gets evaluated/returned
        if isinstance(scope.get(self.name), Callable):
            return scope.get(self.name).call(scope)
        else:
            return scope.get(self.name)

    def treestr(self, indent=0):
        s = tab * indent + 'Call: ' + self.name
        if len(self.args) > 0 or len(self.bargs) > 0:
            s += '\n'
            for arg in self.args:
                s += arg.treestr(indent + 1) + '\n'
            for a, v in self.bargs:
                s += tab * (indent + 1) + f'{a}={v}\n'
        return s

    def __str__(self):
        arglist = ', '.join(map(str, self.args))
        barglist = ', '.join(f'{a}={v}' for a, v in self.bargs)
        args = arglist + (', ' if arglist and barglist else '') + barglist
        return f'{self.name}({args})'

    def __repr__(self):
        return f'Call({self.name}, {repr(self.args)}, {repr(self.bargs)})'

class String(AST):
    def __init__(self, val:str):
        self.val = val
    def eval(self, scope:Scope=None):
        return self
    def topy(self, scope:Scope=None) -> str:
        return self.val
    def treestr(self, indent=0):
        return f'{tab * indent}String: `{self.val}`'
    def __str__(self):
        return f'"{self.val}"'
    def __repr__(self):
        return f'String({repr(self.val)})'

class IString(AST):
    def __init__(self, parts:List[AST]):
        self.parts = parts

    def eval(self, scope:Scope=None):
        #convert self into a String()
        return String(self.topy(scope))

    def topy(self, scope:Scope=None):
        return ''.join(str(part.eval(scope).topy(scope)) for part in self.parts)

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

class BinOp(AST):
    def __init__(self, left:AST, right:AST, op:PyCallable[[AST, AST],AST], opname:str, opsymbol:str):
        self.left = left
        self.right = right
        self.op = op
        self.opname = opname
        self.opsymbol = opsymbol

    def eval(self, scope:Scope=None):
        return self.op(self.left.eval(scope).topy(), self.right.eval(scope).topy())
    def treestr(self, indent=0):
        return f'{tab * indent}{self.opname}\n{self.left.treestr(indent + 1)}\n{self.right.treestr(indent + 1)}'
    def __str__(self):
        return f'{self.left} {self.opsymbol} {self.right}'
    def __repr__(self):
        return f'{self.opname}({repr(self.left)}, {repr(self.right)})'

##################### Binary operators #####################
class Equal(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, lambda l, r: Bool(l == r), 'Equal', '=?')

class NotEqual(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, lambda l, r: Bool(l != r), 'NotEqual', 'not=?')

class Less(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, lambda l, r: Bool(l < r), 'Less', '<?')

class LessEqual(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, lambda l, r: Bool(l <= r), 'LessEqual', '<=?')

class Greater(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, lambda l, r: Bool(l > r), 'Greater', '>?')

class GreaterEqual(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, lambda l, r: Bool(l >= r), 'GreaterEqual', '>=?')

#TODO: type of output should be based on types of the inputs
class Add(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, lambda l, r: Number(l + r), 'Add', '+')

class Sub(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, lambda l, r: Number(l - r), 'Sub', '-')

# class Mul(BinOp):
#     def __init__(self, left:AST, right:AST):
#         super().__init__(left, right, lambda l, r: Number(l * r), 'Mul', '*')

# class Div(BinOp):
#     def __init__(self, left:AST, right:AST):
#         super().__init__(left, right, lambda l, r: Number(l / r), 'Div', '/')



class Bool(AST):
    def __init__(self, val:bool):
        self.val = val
    def eval(self, scope:Scope=None):
        return self
    def topy(self, scope:Scope=None):
        return self.val
    def treestr(self, indent=0):
        return f'{tab * indent}Bool: {self.val}'
    def __str__(self):
        return f'{self.val}'
    def __repr__(self):
        return f'Bool({repr(self.val)})'

class If(AST):
    def __init__(self, clauses:List[PyTuple[AST, AST]]):
        self.clauses = clauses
    
    def eval(self, scope:Scope=None):
        # TODO: determine if scope should be shared, or a new scope should be created per clause
        child = Scope(scope) #all clauses share a common anonymous scope
        for cond, expr in self.clauses:
            # child = Scope(scope) #each clause gets its own anonymous scope
            if cond.eval(child).topy(child):
                return expr.eval(child)

    def treestr(self, indent=0):
        s = tab * indent + 'If\n'
        for cond, expr in self.clauses:
            s += tab * (indent + 1) + 'Clause\n'
            s += cond.treestr(indent + 2) + '\n'
            s += expr.treestr(indent + 2) + '\n'
        return s

    def __str__(self):
        s = ''
        for i, (cond, expr) in enumerate(self.clauses):
            if i == 0:
                s += f'if {cond} {expr}'
            else:
                s += f' else if {cond} {expr}'
        return s

    def __repr__(self):
        return f'If({repr(self.clauses)})'

#TODO: maybe loop can work the say way as If, taking in a list of clauses?
class Loop(AST):
    def __init__(self, cond:AST, body:AST):
        self.cond = cond
        self.body = body

    def eval(self, scope:Scope=None):
        child = Scope(scope)
        while self.cond.eval(child).topy(child):
            self.body.eval(child)
        #TODO: handle capturing values from a loop
        #TODO: handle break and continue
        #TODO: also eventually handle return (problem for other ASTs as well)

    def treestr(self, indent=0):
        return f'{tab * indent}Loop\n{self.cond.treestr(indent + 1)}\n{self.body.treestr(indent + 1)}'

    def __str__(self):
        return f'loop {self.cond} {self.body}'

    def __repr__(self):
        return f'Loop({repr(self.cond)}, {repr(self.body)})'

#DEBUG example
"""
loop i in [0..10)
    printl(i)

//expanded version of above
iter = [0..10).iter()
let i
loop {(cond, i) = iter.next(); cond} 
    printl(i)

//but ideally the entire iterator could be contained in the condition expression of the loop
{
    loop
    (
        // idempotent initialization here
        #ifnotexists(iter) iter = [0..10).iter()
        (cond, i) = iter.next()
        cond
    )
    (
        // condition and body share the same scope
        printl(i)
    )
}
"""
#TODO: convert to class In()
#  in basically does this, but has the extra stuff with the var being set, and so forth
#class iter is the manager for things that can iterate, e.g. Range.iter()->RangeIter, Vector.iter()->VectorIter, etc.
class In(AST):
    #TODO: allow name to be an unpack structure as well
    def __init__(self, name:str, iterable:Iterable):#, init:AST, body:AST):
        self._id = f'.iter_{id(self)}'
        # self.init = init
        # self.body = body

    def eval(self, scope:Scope=None) -> Bool:
        #idempotent initialization
        try:
            it = scope.get(self._id)
        except NameError:
            it = self.init.eval(scope)
            scope.let(self._id, value=it, const=True)

        # body gets the binds element and returns the resulting condition
        return self.body.eval(scope)



class Number(AST):
    def __init__(self, val):
        self.val = val
    def eval(self, scope:Scope=None):
        return self
    def type(self):
        return Type('Number')
    def topy(self, scope:Scope=None):
        return self.val
    def treestr(self, indent=0):
        return f'{tab * indent}Number: {self.val}'
    def __str__(self):
        return f'{self.val}'
    def __repr__(self):
        return f'Number({repr(self.val)})'


#TODO: this needs something inbetween for handling `i in 1..10`, i.e. the part that does the binding is not part of the range
class Range(Iterable,Unpackable):
    """
    Inspired by Haskell syntax for ranges:
    [first..]               // first to inf
    [first,second..]        // step size is second-first
    [first..last]           // first to last
    [first,second..last]    // first to last, step size is second-first
    [..last]                // -inf to last
    [..]                    // -inf to inf

    open/closed ranges:
    [first..last]           // first to last including first and last
    [first..last)           // first to last including first, excluding last
    (first..last]           // first to last excluding first, including last
    (first..last)           // first to last excluding first and last
    first..last             // same as [first..last]. Note that parentheses are required if `second` is included in the expression
    """
    def __init__(self, first:AST|Undefined=undefined, second:AST|Undefined=undefined, last:AST|Undefined=undefined, include_first:bool=True, include_last:bool=True):
        self.first = first if first is not undefined else Number(float('-inf'))
        self.second = second
        self.last = last if last is not undefined else Number(float('inf'))
        self.include_first = include_first
        self.include_last = include_last
        

    def eval(self, scope:Scope=None):
        return self
    
    def iter(self, scope:'Scope'=None) -> Iter:
        #todo: write later
        pdb.set_trace()

    # def type(self):
    #     return Type('Range') #TODO: this should maybe care about the type of data in it?

    def topy(self, scope:Scope=None):
        step_size = self.second.topy() - self.first.topy() if self.second is not undefined else 1
        return range(self.first.topy(scope), self.last.topy(scope), step_size)

    def treestr(self, indent=0):
        s = f'{tab * indent}Range\n'
        s += f'{tab * (indent + 1)}first:\n{self.first.treestr(indent + 2)}\n'
        s += f'{tab * (indent + 1)}second:\n{self.second.treestr(indent + 2)}\n'
        s += f'{tab * (indent + 1)}last:\n{self.last.treestr(indent + 2)}\n'
        return s


class RangeIter(Iter):
    def __init__(self, range:Range):
        self.range = range
        self.i = self.range.first
        self.step_size = Sub(self.range.second, self.range.first) if self.range.second is not undefined else Number(1)

    # def next(self, scope:Scope=None) -> Tuple[Bool, AST]:
    #     pdb.set_trace()
    #     if self.i < self.range.last:
    #         ret = self.i
    #         self.i += self.step_size
    #         return (Bool(True), ret)
    #     else:
    #         return (Bool(False), undefined)


class Vector(Iterable, Unpackable):
    def __init__(self, vals:List[AST]):
        self.vals = vals
    def eval(self, scope:Scope=None):
        return self
    
    #unpackable interface
    def len(self, scope:Scope=None):
        return len(self.vals)
    def get(self, key:int|EllipsisType|slice|PyTuple[int|EllipsisType|slice], scope:Scope=None):
        if isinstance(key, int):
            return self.vals[key]
        elif isinstance(key, EllipsisType):
            return self
        elif isinstance(key, slice):
            return Vector(self.vals[key])
        elif isinstance(key, tuple):
            #probably only valid for N-dimensional/non-jagged vectors
            raise NotImplementedError('TODO: implement tuple indexing for Vector')
        else:
            raise TypeError(f'invalid type for Vector.get: `{key}` of type `{type(key)}`')


    #iterable interface
    #TODO...

    def topy(self, scope:Scope=None):
        return [v.eval(scope).topy(scope) for v in self.vals]
    def treestr(self, indent=0):
        s = tab * indent + 'Vector\n'
        for v in self.vals:
            s += v.treestr(indent + 1) + '\n'
        return s
    def __str__(self):
        return f'[{" ".join(map(str, self.vals))}]'
    def __repr__(self):
        return f'Vector({repr(self.vals)})'



def hello():

    #set up root scope with some functions
    root = Scope() #highest level of scope, mainly for builtins
    root.bind('printl', Builtin('printl', [Arg('text')]))

    #Hello, World!
    prog0 = Block([
        Call('printl', [String('Hello, World!')]),
    ])
    # print(prog0)
    prog0.eval(root)


def hello_func():

    #set up root scope with some functions
    root = Scope() #highest level of scope, mainly for builtins
    root.bind('printl', Builtin('printl', [Arg('text')]))

    #Hello, World!
    prog = Block([
        Bind(
            'main',
            Function(
                [],
                Block([
                    Call('printl', [String('Hello, World!')]),
                ]),
                root
            )
        ),
        Call('main'),
    ])
    # print(prog)
    prog.eval(root)


def hello_name():

    #set up root scope with some functions
    root = Scope() #highest level of scope, mainly for builtins
    root.bind('print', Builtin('print', [Arg('text')]))
    root.bind('printl', Builtin('printl', [Arg('text')]))
    root.bind('readl', Builtin('readl', [], String))

    #Hello <name>!
    prog = Block([
        Call('print', [String("What's your name? ")]),
        Bind('name', Call('readl')),
        Call('printl', [IString([String('Hello '), Call('name'), String('!')])]),
    ])
    # print(prog)
    prog.eval(root)



def if_else():

    #set up root scope with some functions
    root = Scope() #highest level of scope, mainly for builtins
    root.bind('print', Builtin('print', [Arg('text')]))
    root.bind('printl', Builtin('printl', [Arg('text')]))
    root.bind('readl', Builtin('readl', [], String))

    #if name =? 'Alice' then print 'Hello Alice!' else print 'Hello stranger!'
    prog = Block([
        Call('print', [String("What's your name? ")]),
        Bind('name', Call('readl')),
        If([
            (
                Equal(Call('name'), String('Alice')),
                Call('printl', [String('Hello Alice!')])
            ),
            (
                Bool(True),
                Call('printl', [String('Hello Stranger!')]),
            )
        ])
    ])
    # print(prog)
    prog.eval(root)


def if_else_if():

    #set up root scope with some functions
    root = Scope() #highest level of scope, mainly for builtins
    root.bind('print', Builtin('print', [Arg('text')]))
    root.bind('printl', Builtin('printl', [Arg('text')]))
    root.bind('readl', Builtin('readl', [], String))


    #name = readl()
    #if name =? 'Alice' 
    #   printl('Hello Alice!') 
    #else if name =? 'Bob' 
    #   printl('Hello Bob!')
    #else
    #   print('Hello stranger!')
    prog = Block([
        Call('print', [String("What's your name? ")]),
        Bind('name', Call('readl')),
        If([
            (
                Equal(Call('name'), String('Alice')),
                Call('printl', [String('Hello Alice!')])
            ),
            (
                Equal(Call('name'), String('Bob')),
                Call('printl', [String('Hello Bob!')])
            ),
            (
                Bool(True),
                Call('printl', [String('Hello Stranger!')]),
            )
        ])
    ])
    # print(prog)
    prog.eval(root)


def hello_loop():
    
        #set up root scope with some functions
        root = Scope() #highest level of scope, mainly for builtins
        root.bind('print', Builtin('print', [Arg('text')]))
        root.bind('printl', Builtin('printl', [Arg('text')]))
        root.bind('readl', Builtin('readl', [], String))

        #print 'Hello <name>!' 10 times
        prog = Block([
            Call('print', [String("What's your name? ")]),
            Bind('name', Call('readl')),
            Bind('i', Number(0)),
            Loop(
                Less(Call('i'), Number(10)),
                Block([
                    Call('printl', [IString([String('Hello '), Call('name'), String('!')])]),
                    Bind('i', Add(Call('i'), Number(1))),
                ])
            )
        ])
        # print(prog)
        prog.eval(root)


def unpack_test():

    #set up root scope with some functions
    root = Scope()
    root.bind('printl', Builtin('printl', [Arg('text')]))

    #unpack several variables from a vector and print them
    prog = Block([
        Bind('s', Vector([String('Hello'), Vector([String('World'), String('!')]), Number(5), Number(10)])),
        Unpack(['a', 'b', 'c', 'd'], Call('s')),
        Call('printl', [IString([String('a='), Call('a'), String(' b='), Call('b'), String(' c='), Call('c'), String(' d='), Call('d')])]),
    ])
    # print(prog)
    prog.eval(root)


def rule110():

    #set up root scope with some functions
    root = Scope() #highest level of scope, mainly for builtins
    root.bind('print', Builtin('print', [Arg('text')]))
    root.bind('printl', Builtin('printl', [Arg('text')]))
    root.bind('readl', Builtin('readl', [], String))

    #rule 110
    #TODO: handle type annotations in AST
    prog = Block([
        Bind(
            'progress', 
            Function(
                [Arg('world', Type('vector', [Type('bit')]))], 
                Block([
                    Bind('cell_update', Number(0)),
                    # loop i in 0..world.length
                    #     if i >? 0 world[i-1] = cell_update
                    #     update = (0b01110110 << (((world[i-1] ?? 0) << 2) or ((world[i] ?? 0) << 1) or (world[i+1] ?? 0)))
                    # world.push(update)
                    #etc....
                ]), 
                root
            ),
            # Type('function', [Type('vector', [Type('bit')]), Type('vector', [Type('bit')])]),
        ),
        Let('world', Type('vector', [Type('bit')])),
        Bind(
            'world',
            Vector([Number(1)]),
        ),
        # loop true
        #     printl(world)
        #     update(world)
    ])
    # print(prog)
    prog.eval(root)




if __name__ == '__main__':
    # hello()
    # hello_func()
    # hello_name()
    # if_else()
    # if_else_if()
    # hello_loop()
    unpack_test()
    # rule110()