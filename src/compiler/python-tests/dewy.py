from abc import ABC
from dataclasses import dataclass
from types import EllipsisType
from typing import Any, Callable as PyCallable, Union, Optional
from functools import partial

import pdb

#Written in python3.10

#dumb look at interpreting/compiling dewy
#for now, construct the AST directly, skipping the parsing step


# [Tasks]
# - instead of If with a block of multiple conditional checks: ConditionalChain, which can have any conditonals, e.g. if, loop, etc, and the first one that gets entered stops the chain
# - write function for crawling AST, and replacing 
# loop <var> in <expr> 
#   <body> 
# with 
# <_itr> = <expr>.iter()
# <var> = <itr>.next()
# loop <var>
#   <body>
#   <var> = <itr>.next()
#
# - make all type checking happen at compile time, and be based on calls to expr.type
#   -> need to be able to handle type graph with child types matching where parent types are expected, etc. e.g. int is a number, etc.
# also make the current functionality not worker (where it checks if the variable exists). should throw an error about how it's syntax sugar

#convenient for inside lambdas
def notimplemented():
    raise NotImplementedError()

tab = '    ' #for printing ASTs
newline = '\n' # or ' ' to make it all one line
# tabin = '|>>>>|'
# tabout = '|<<<<|'


def insert_tabs_inner(s):
    """given the output of __str__ from an AST, insert tabs at \n based on how many {} were encountered so far"""
    #TODO: this runs into problems b/c {} is also used in string interpolation syntax...
    level = 0
    out = []
    for c in s:
        if c == '{':
            level += 1
        elif c == '}':
            level -= 1
            if out[-1].isspace():
                out[-1] = out[-1][:-4] #remove 1 tab
        out.append(c)

        if c == '\n':
            out.append(tab*level)
            continue

    return ''.join(out)

inserting_tabs = False #so that only the top level inserts the tabs
def insert_tabs(func):
    def wrapper(*args, **kwargs):
        global inserting_tabs
        if inserting_tabs:
            out = func(*args, **kwargs)
        else:
            inserting_tabs = True
            out = insert_tabs_inner(func(*args, **kwargs))
            inserting_tabs = False
        return out

    return wrapper


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

class Undefined(AST):
    """undefined singleton"""
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Undefined, cls).__new__(cls)
        return cls.instance
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

#undefined shorthand, for convenience
undefined = Undefined()



class Callable(AST):
    def call(self, scope:'Scope'=None):
        """Call the callable in the given scope"""
        raise NotImplementedError(f'{self.__class__.__name__}.call')

class Orderable(AST):
    """An object that can be sorted relative to other objects of the same type"""
    def compare(self, other:'Orderable', scope:'Scope'=None) -> 'Number':
        """Return a value indicating the relationship between this value and another value"""
        raise NotImplementedError(f'{self.__class__.__name__}.compare')
    @staticmethod
    def max(self) -> 'Rangeable':
        """Return the maximum element from the set of all elements of this type"""
        raise NotImplementedError(f'{self.__class__.__name__}.max')
    @staticmethod
    def min(self) -> 'Rangeable':
        """Return the minimum element from the set of all elements of this type"""
        raise NotImplementedError(f'{self.__class__.__name__}.min')
    
#TODO: come up with a better name for this class... successor and predecessor are only used for range iterators, not ranges themselves
#        e.g. Incrementable, Decrementable, etc.
class Rangeable(Orderable):
    """An object that can be used to specify bounds of a range"""
    def successor(self, step=undefined, scope:'Scope'=None) -> 'Rangeable':
        """Return the next value in the range"""
        raise NotImplementedError(f'{self.__class__.__name__}.successor')
    def predecessor(self, step=undefined, scope:'Scope'=None) -> 'Rangeable':
        """Return the previous value in the range"""
        raise NotImplementedError(f'{self.__class__.__name__}.predecessor')

class Unpackable(AST):
    def len(self, scope:'Scope'=None) -> int:
        """Return the length of the unpackable"""
        raise NotImplementedError(f'{self.__class__.__name__}.len')
    def get(self, key:int|EllipsisType|slice|tuple[int|EllipsisType|slice], scope:'Scope'=None) -> AST:
        """Return the item at the given index"""
        raise NotImplementedError(f'{self.__class__.__name__}.get')
#TODO: make a type annotation for Unpackable[N] where N is the number of items in the unpackable?
#        would maybe replace the len property?

class Iter(AST):
    def next(self, scope:'Scope'=None) -> Unpackable: #TODO: TBD on the return type. need dewy tuple type...
        """Get the next item from the iterator"""
        raise NotImplementedError(f'{self.__class__.__name__}.next')

class Iterable(AST):
    #TODO: maybe don't need scope for this method...
    def iter(self, scope:'Scope'=None) -> Iter:
        """Return an iterator over the iterable"""
        raise NotImplementedError(f'{self.__class__.__name__}.iter')






BArg = tuple[str, AST]   #bound argument + current value for when making function calls

class Scope():
    
    @dataclass
    class _var():
        # name:str #name is stored in the dict key
        type:AST
        value:AST
        const:bool
    
    def __init__(self, parent:Optional['Scope']=None):
        self.parent = parent
        self.vars:dict[str, Scope._var] = {}
        
        #used for function calls
        self.args:list[AST] = []
        self.bargs:list[BArg] = []

    @property
    def root(self) -> 'Scope':
        """Return the root scope"""
        return [*self][-1]

    def let(self, name:str, type:Union['Type',Undefined]=undefined, value:AST=undefined, const=False):
        #overwrite anything that might have previously been there
        self.vars[name] = Scope._var(type, value, const)

    def get(self, name:str, default:AST=None) -> AST:
        #get a variable from this scope or any of its parents
        for s in self:
            if name in s.vars:
                return s.vars[name].value
        if default is not None:
            return default
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

    def attach_args(self, args:list[AST], bargs:list[BArg]):
        self.args = args
        self.bargs = bargs

    @staticmethod
    def default():
        """return a scope with the standard library (of builtins) included"""
        root = Scope()
        root.bind('print', Builtin('print', [Arg('text')]))
        root.bind('printl', Builtin('printl', [Arg('text')]))
        root.bind('readl', Builtin('readl', [], String))
        #TODO: eventually add more builtins

        return root


#probably won't use this, except possibly for when calling functions and providing enums from the function's scope
# def merge_scopes(*scopes:list[Scope], onto:Scope=None):
#     #TODO... this probably could actually be a scope union class that inherits from Scope
#     #            that way we don't have to copy the scopes
#     pdb.set_trace()


class Type(AST):
    def __init__(self, name:str, params:list[AST]=None):
        self.name = name
        self.params = params
    def eval(self, scope:Scope=None):
        return self

    def treestr(self, indent=0):
        s = tab * indent + f'Type: {self.name}\n'
        for p in self.params:
            s += p.treestr(indent + 1) + '\n'
        return s

    @insert_tabs
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
    # @insert_tabs
    def __str__(self):
        s = f'{self.name}'
        if self.type is not None:
            s += f':{self.type}'
        if self.val is not None:
            s += f' = {self.val}'
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
    def __init__(self, args:list[Arg], body:AST, scope:Scope=None):
        self.args = args
        self.body = body
        self.scope = scope #scope where the function was defined, which may be different from the scope where it is called
    
    def eval(self, scope:Scope=None):
        #TODO: maybe this should do self.scope=scope since this is the scope where the function is defined
        #        just probably problems when expressing the function without calling it, e.g. with handles
        #        f = {() => {...}} @f // the @f would set the scope to be the outer scope...
        return self
    
    def call(self, scope:Scope=None):
        #collect args from calling scope, and merge into function scope
        fscope = Scope(self.scope)

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

    @insert_tabs
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
    def __init__(self, name:str, args:list[Arg], cls:PyCallable=None):
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

    # @insert_tabs
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

    @insert_tabs
    def __str__(self):
        return f'{"const" if self.const else "let"} {self.name}:{self.type} = {self.value}'

    def __repr__(self):
        return f'{"Const" if self.const else "Let"}({self.name}, {self.type}, {self.value})'


class Bind(AST):
    #TODO: allow bind to take in an unpack structure
    def __init__(self, name:str, value:AST):
        self.name = name
        self.value = value
    def eval(self, scope:Scope=None):
        scope.bind(self.name, self.value.eval(scope))

    def treestr(self, indent=0):
        return f'{tab * indent}Bind: {self.name}\n{self.value.treestr(indent + 1)}'

    @insert_tabs
    def __str__(self):
        return f'{self.name} = {self.value}'

    def __repr__(self):
        return f'Bind({self.name}, {repr(self.value)})'


class PackStruct(list[Union[str,'PackStruct']]):
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
        assert sum(1 for s in struct if isinstance(s, str) and s.startswith('...')) <= 1, 'only one ellipsis is allowed per level of the structure'
        self.struct = struct
        self.value = value

    def eval(self, scope:Scope=None):
        value = self.value.eval(scope)
        assert isinstance(value, Unpackable), f'{value} is not unpackable'
        value_len = value.len(scope)
        
        #check that the structure has a matching number of elements to the value
        #TODO: actually maybe allow this, and any extra elements are just undefined. complicated to handle if the number of elements is wrong though
        has_ellipsis = any(isinstance(s, str) and s.startswith('...') for s in self.struct)
        if has_ellipsis:
            assert value_len >= len(self.struct) - 1, f'cannot unpack {value} into {Unpack.str_helper(self.struct)}, expected more values to unpack'
        else:
            assert value_len == len(self.struct), f'cannot unpack {value} into {Unpack.str_helper(self.struct)}, ' + ('expected more' if value_len < len(self.struct) else 'expected less') + ' values to unpack'

        offset = 0 #offset for handling if an ellipsis was encountered during the unpack
        for i, s in enumerate(self.struct):
            if isinstance(s, str):
                if s.startswith('...'):
                    name = s[3:]
                    n = value_len - len(self.struct) + 1 #number of elements to fill the ellipsis with
                    scope.bind(name, value.get(slice(i,i+n), scope))
                    offset += n - 1
                else:
                    scope.bind(s, value.get(i+offset, scope))
            elif isinstance(s, list) or isinstance(s, tuple):
                Unpack(s, value.get(i+offset, scope)).eval(scope)
            else:
                raise TypeError(f'invalid type in unpack structure: `{s}` of type `{type(s)}`')

    def treestr(self, indent=0):
        return f'{tab * indent}Unpack: {self.struct}\n{self.value.treestr(indent + 1)}'

    @insert_tabs
    def __str__(self):
        return f'{Unpack.str_helper(self.struct)} = {self.value}'

    @staticmethod
    def str_helper(val):
        if isinstance(val, str):
            return val
        else:
            s = '['
            for i, v in enumerate(val):
                if isinstance(v, str):
                    s += v
                else:
                    s += Unpack.str_helper(v)
                if i != len(val) - 1:
                    s += ', '
            s += ']'
            return s

    def __repr__(self):
        return f'Unpack({self.struct}, {self.value})'

class Tuple(AST):
    """
    A comma separated list of expressions (not wrapped in parentheses) e.g. 1, 2, 3
    There is no special in-memory representation of a tuple, it is literally just a const list
    """
    def __init__(self, exprs:list[AST]):
        self.exprs = exprs

    def eval(self, scope:Scope=None):
        pdb.set_trace()
    

class Block(AST):
    def __init__(self, exprs:list[AST], newscope:bool=True):
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

    @insert_tabs
    def __str__(self):
        return f'{{{newline}{newline.join(map(str, self.exprs))}{newline}}}'

    def __repr__(self):
        return f'Block({repr(self.exprs)})'


class Call(AST):
    def __init__(self, expr:str|AST, args:list[AST]=[], bargs:list[BArg]=[]):
        assert isinstance(expr, str|AST), f'invalid type for call expression: `{self.expr}` of type `{type(self.expr)}`'
        self.expr = expr
        self.args = args
        self.bargs = bargs

    def eval(self, scope:Scope):
        scope.attach_args(self.args, self.bargs)

        #check if we need to resolve the name, or if it was an anonymous expression
        if isinstance(self.expr, AST):
            expr = self.expr.eval(scope)
        else:
            expr = scope.get(self.expr)
        
        #functions get called with args, while everything else just gets evaluated/returned
        if isinstance(expr, Callable):
            return expr.call(scope)
        else:
            return expr

    def treestr(self, indent=0):
        s = tab * indent + 'Call: '
        if isinstance(self.expr, AST):
            s += self.expr.treestr(indent + 1)
        else:
            s += self.expr
        if len(self.args) > 0 or len(self.bargs) > 0:
            s += '\n'
            for arg in self.args:
                s += arg.treestr(indent + 1) + '\n'
            for a, v in self.bargs:
                s += tab * (indent + 1) + f'{a}={v}\n'
        return s

    @insert_tabs
    def __str__(self):
        arglist = ', '.join(map(str, self.args))
        barglist = ', '.join(f'{a}={v}' for a, v in self.bargs)
        args = arglist + (', ' if arglist and barglist else '') + barglist
        #TODO: not sure if Function captures all objects that should get () even if they don't have args
        return f'{self.expr}' + (f'({args})' if args or isinstance(self.expr, Function) else f'')

    def __repr__(self):
        return f'Call({self.expr}, {repr(self.args)}, {repr(self.bargs)})'

class String(Rangeable):
    def __init__(self, val:str):
        self.val = val
    def eval(self, scope:Scope=None):
        return self
    def type(self, scope:Scope=None):
        return Type('string')
    #TODO: implement rangable methods
    def topy(self, scope:Scope=None) -> str:
        return self.val
    def treestr(self, indent=0):
        return f'{tab * indent}String: `{self.val}`'
    # @insert_tabs
    def __str__(self):
        return f'"{self.val}"'
    def __repr__(self):
        return f'String({repr(self.val)})'

class IString(AST):
    def __init__(self, parts:list[AST]):
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

    @insert_tabs
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
    @insert_tabs
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

class Mul(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, lambda l, r: Number(l * r), 'Mul', '*')

class Div(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, lambda l, r: Number(l / r), 'Div', '/')

class IDiv(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, lambda l, r: Number(l // r), 'IDiv', '//')

class Mod(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, lambda l, r: Number(l % r), 'Mod', '%')

class Pow(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, lambda l, r: Number(l ** r), 'Pow', '**')


##################### Unary operators #####################
class UnaryOp(AST):
    def __init__(self, child:AST, op:PyCallable[[AST],AST], opname:str, opsymbol:str):
        self.child = child
        self.op = op
        self.opname = opname
        self.opsymbol = opsymbol

    def eval(self, scope:Scope=None):
        return self.op(self.child.eval(scope).topy())
    def treestr(self, indent=0):
        return f'{tab * indent}{self.opname}\n{self.child.treestr(indent + 1)}'
    @insert_tabs
    def __str__(self):
        return f'{self.opsymbol}{self.child}'
    def __repr__(self):
        return f'{self.opname}({repr(self.child)})'

class Neg(UnaryOp):
    def __init__(self, child:AST):
        super().__init__(child, lambda c: Number(-c), 'Neg', '-')

class Inv(UnaryOp):
    def __init__(self, child:AST):
        super().__init__(child, lambda c: Number(1/c), 'Inv', '/')


class Bool(AST):
    def __init__(self, val:bool):
        self.val = val
    def eval(self, scope:Scope=None):
        return self
    def topy(self, scope:Scope=None):
        return self.val
    def type(self, scope:Scope=None):
        return Type('bool')
    def treestr(self, indent=0):
        return f'{tab * indent}Bool: {self.val}'
    # @insert_tabs
    def __str__(self):
        return f'{self.val}'
    def __repr__(self):
        return f'Bool({repr(self.val)})'

class If(AST):
    def __init__(self, clauses:list[tuple[AST, AST]]):
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

    @insert_tabs
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

    @insert_tabs
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
    def __init__(self, name:str|PackStruct, iterable:Iterable):#, init:AST, body:AST):
        self._id = f'.it_{id(self)}'
        self.name = name
        self.iterable = iterable

    def eval(self, scope:Scope=None) -> Bool:
        #idempotent initialization
        try:
            it = scope.get(self._id)
        except NameError:
            it = self.iterable.iter(scope)
            scope.let(self._id, value=it, const=True)

        # body gets the binds element and returns the resulting condition
        Unpack(['_', self.name], Next(Call(self._id))).eval(scope)
        cond = Call('_').eval(scope)
        assert isinstance(cond, Bool), f'loop condition must be a Bool, not {cond} of type {type(cond)}'
        return cond

    def treestr(self, indent=0):
        return f'{tab * indent}In: {self.name}\n{self.iterable.treestr(indent + 1)}'

    @insert_tabs
    def __str__(self):
        return f'{self.name} in {self.iterable}'

    def __repr__(self):
        return f'In({repr(self.name)}, {repr(self.iterable)})'

class Next(AST):
    """handle getting the next element in the iteration"""
    def __init__(self, iterable:AST):
        self.iterable = iterable

    def eval(self, scope:Scope=None) -> AST:
        it = self.iterable.eval(scope)
        assert isinstance(it, Iter), f'cannot call next on {it}, not an iterator'
        return it.next(scope)

    def __repr__(self):
        return f'Next({repr(self.iterable)})'

    @insert_tabs
    def __str__(self):
        return f'next({self.iterable})'

class Number(Rangeable):
    def __init__(self, val:int|float):
        self.val = val
    def eval(self, scope:Scope=None):
        return self
    def type(self):
        return Type('Number')
    
    #Rangeable methods
    def compare(self, other:'Number', scope:Scope=None) -> 'Number':
        return Number(self.val - other.val)
    def successor(self, step:'Number'=undefined, scope:'Scope'=None) -> 'Number':
        if step is undefined:
            return Number(self.val + 1)
        else:
            return Number(self.val + step.val)
    def predecessor(self, step:'Number'=undefined, scope:'Scope'=None) -> 'Number':
        if step is undefined:
            return Number(self.val - 1)
        else:
            return Number(self.val - step.val)
    @staticmethod
    def max(self) -> 'Number':
        return Number(float('inf'))
    @staticmethod
    def min(self) -> 'Number':
        return Number(float('-inf'))
    
    def topy(self, scope:Scope=None):
        return self.val
    def treestr(self, indent=0):
        return f'{tab * indent}Number: {self.val}'
    # @insert_tabs
    def __str__(self):
        return f'{self.val}'
    def __repr__(self):
        return f'Number({repr(self.val)})'


#TODO: handling of different types of ranges (e.g. character ranges, vs number ranges). 
#   how to handle +inf/-inf in non-numeric case? implies some sort of max/min element for the range value...
#   i.e. class Rangeable(AST): where class Number(Rangable), Char(Rangeable), etc.
#   Rangable types should implement successor(step=1) and predecessor(step=1) methods
class Range(Iterable,Unpackable):
    """
    Inspired by Haskell syntax for ranges:
    [first..]               // first to inf
    [first,second..]        // step size is second-first
    [first..last]           // first to last
    [first,second..last]    // first to last, step size is second-first
    //[first..2ndlast,last] // this is explicitly NOT ALLOWED, as it is covered by the previous case, and can have unintuitive behavior
    [..2ndlast,last]        // -inf to last, step size is last-penultimate
    [..last]                // -inf to last
    [..]                    // -inf to inf

    open/closed ranges:
    [first..last]           // first to last including first and last
    [first..last)           // first to last including first, excluding last
    (first..last]           // first to last excluding first, including last
    (first..last)           // first to last excluding first and last
    first..last             // same as [first..last]. Note that parentheses are required if `second` is included in the expression
    """
    def __init__(self, first:Rangeable=undefined, second:Rangeable=undefined, last:Rangeable=undefined, include_first:bool=True, include_last:bool=True):
        range_type = type(first) if first is not undefined else type(second) if second is not undefined else type(last)
        if range_type is undefined:
            range_type = Number
        assert issubclass(range_type, Rangeable), f'Range type must be of type Rangeable, not {range_type}'
        #TODO: type checking to confirm that first, second, and last are all compatible types

        self.range_type = range_type
        self.first = first if first is not undefined else range_type.min()
        self.second = second
        self.last = last if last is not undefined else range_type.max()
        self.include_first = include_first
        self.include_last = include_last
        

    def eval(self, scope:Scope=None):
        return self
    
    def iter(self, scope:'Scope'=None) -> Iter:
        return RangeIter(self)

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

    @insert_tabs
    def __str__(self):
        s = ''
        s += '[' if self.include_first else '('
        if self.first is not undefined:
            s += str(self.first)
        if self.second is not undefined:
            s += ','
            s += str(self.second)
        s += '..'
        if self.last is not undefined:
            s += str(self.last)
        s += ']' if self.include_last else ')'
        return s

    def __repr__(self):
        interval = f'{"[" if self.include_first else "("}{"]" if self.include_last else ")"}'
        return f'Range({repr(self.first)},{repr(self.second)},{repr(self.last)},interval={interval})'


class RangeIter(Iter):
    def __init__(self, ast:AST):#range:Range): #TODO: want AST[Range] typing which means it evals to a range...
        # self._id = f'.iter_{id(self)}'
        self.ast = ast
    #     self.reset()

    # def reset(self):
        self.range = None
        self.i = None
        self.step = None

    def eval(self, scope:Scope=None):
        return self

    def next(self, scope:Scope=None) -> Unpackable:
        if self.range is None:
            self.range = self.ast.eval(scope)
            assert isinstance(self.range, Range), f'RangeIter must be initialized with an AST that evaluates to a Range, not {type(self.range)}' 
            self.i = self.range.first
            #set the stepsize (needed access to the scope)
            if self.range.second is not undefined:
                self.step = self.range.second.compare(self.range.first, scope)
            else:
                self.step = undefined
            
            #skip the first element if it's not included (closed interval)
            if not self.range.include_first:
                self.i = self.i.successor(self.step, scope)

        #check the stop condition and return the next element
        if (c:=self.i.compare(self.range.last).val) < 0 or (c==0 and self.range.include_last):
            ret = self.i
            self.i = self.i.successor(self.step, scope)
            return Vector([Bool(True), ret])
        else:
            return Vector([Bool(False), undefined])

    def type(self):
        return Type('RangeIter')

    def topy(self, scope:Scope=None):
        raise NotImplementedError

    def treestr(self, indent=0):
        return f'{tab * indent}RangeIter:\n{self.ast.treestr(indent + 1)}'
        
    @insert_tabs
    def __str__(self):
        return f'RangeIter({self.ast})'

    def __repr__(self):
        return f'RangeIter({repr(self.ast)})'


class Vector(Iterable, Unpackable):
    def __init__(self, vals:list[AST]):
        self.vals = vals
    def eval(self, scope:Scope=None):
        return self
    def type(self, scope:Scope=None):
        #TODO: this should include the type of the data inside the vector...
        return Type('Vector')
    
    #unpackable interface
    def len(self, scope:Scope=None):
        return len(self.vals)
    def get(self, key:int|EllipsisType|slice|tuple[int|EllipsisType|slice], scope:Scope=None):
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
    @insert_tabs
    def __str__(self):
        return f'[{" ".join(map(str, self.vals))}]'
    def __repr__(self):
        return f'Vector({repr(self.vals)})'



def hello(root:Scope) -> AST:
    """printl('Hello, World!')"""
    return Call('printl', [String('Hello, World!')])


def hello_func(root:Scope) -> AST:
    """
    {
        main = () => {printl('Hello, World!')}
        main
    }
    """
    return Block([
        Bind(
            'main',
            Function(
                [],
                Call('printl', [String('Hello, World!')]),
                root
            )
        ),
        Call('main'),
    ])
   

def anonymous_func(root:Scope) -> AST:
    """
    {
        (() => printl('Hello, World!'))()
    }
    """
    return Block([
        Call(
            Function(
                [],
                Call('printl', [String('Hello, World!')]),
                root
            )
        ),
    ])

def hello_name(root:Scope) -> AST:
    """
    {
        print("What's your name? ")
        name = readl()
        printl('Hello {name}!')
    }
    """
    return Block([
        Call('print', [String("What's your name? ")]),
        Bind('name', Call('readl')),
        Call('printl', [IString([String('Hello '), Call('name'), String('!')])]),
    ])


def if_else(root:Scope) -> AST:
    """
    {
        print("What's your name? ")
        name = readl()
        if name =? 'Alice' printl('Hello Alice!')
        else printl('Hello stranger!')
    }
    """
    return Block([
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


def if_else_if(root:Scope) -> AST:
    """
    {
        print("What's your name? ")
        name = readl()
        if name =? 'Alice' printl('Hello Alice!')
        else if name =? 'Bob' printl('Hello Bob!')
        else printl('Hello stranger!')
    }
    """
    return Block([
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


def hello_loop(root:Scope) -> AST:
    """
    {
        print("What's your name? ")
        name = readl()
        i = 0
        loop i <? 10 {
            printl('Hello {name}!')
            i = i + 1
        }
    }
    """
    return Block([
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


def unpack_test(root:Scope) -> AST:
    """
    {
        s = ['Hello' ['World' '!'] 5 10]
        printl('s={s}')
        a, b, c, d = s
        printl('a={a} b={b} c={c} d={d}')
        a, ...b = s
        printl('a={a} b={b}')
        ...a, b = s
        printl('a={a} b={b}')
        a, [b, c], ...d = s
        printl('a={a} b={b} c={c} d={d}')

        //error tests
        //a, b, c, d, e = s         //error: not enough values to unpack
        //a, b = s                  //error: too many values to unpack
        //a, ...b, c, d, e, f = s   //error: too many values to unpack

        //TBD how unpack would handle `a, ...b, c, d, e = s`. Probably b would be empty?
    }
    """

    return Block([
        Bind('s', Vector([String('Hello'), Vector([String('World'), String('!')]), Number(5), Number(10)])),
        Call('printl', [IString([String('s='), Call('s')])]),
        Unpack(['a', 'b', 'c', 'd'], Call('s')),
        Call('printl', [IString([String('a='), Call('a'), String(' b='), Call('b'), String(' c='), Call('c'), String(' d='), Call('d')])]),
        Unpack(['a', '...b'], Call('s')),
        Call('printl', [IString([String('a='), Call('a'), String(' b='), Call('b')])]),
        Unpack(['...a', 'b'], Call('s')),
        Call('printl', [IString([String('a='), Call('a'), String(' b='), Call('b')])]),
        Unpack(['a', ['b', 'c'], '...d'], Call('s')),
        Call('printl', [IString([String('a='), Call('a'), String(' b='), Call('b'), String(' c='), Call('c'), String(' d='), Call('d')])]),

        # Test unpacking too few/many values
        # Unpack(['a', 'b', 'c', 'd', 'e'], Call('s')),         # error: not enough values to unpack
        # Unpack(['a', 'b'], Call('s')),                        # error: too many values to unpack
        # Unpack(['a', '...b', 'c', 'd', 'e', 'f'], Call('s')), # error: too many values to unpack
    ])


def range_iter_test(root:Scope) -> AST:
    """
    {
        r = [0,2..20]
        it = iter(r)
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it))
        printl(next(it)) //last iteration. should return [true, 20]
        printl(next(it)) //should return [false, undefined]
        printl(next(it))
        printl(next(it))
    }
    """
    return Block([
        Bind('r', Range(Number(0), Number(2), Number(20))),
        Bind('it', RangeIter(Call('r'))),
        Call('printl', [Next(Call('it'))]),
        Call('printl', [Next(Call('it'))]),
        Call('printl', [Next(Call('it'))]),
        Call('printl', [Next(Call('it'))]),
        Call('printl', [Next(Call('it'))]),
        Call('printl', [Next(Call('it'))]),
        Call('printl', [Next(Call('it'))]),
        Call('printl', [Next(Call('it'))]),
        Call('printl', [Next(Call('it'))]),
        Call('printl', [Next(Call('it'))]),
        Call('printl', [Next(Call('it'))]),
        Call('printl', [Next(Call('it'))]), #should print [False, None] since the iterator is exhausted
        Call('printl', [Next(Call('it'))]),
        Call('printl', [Next(Call('it'))]),
    ])


def loop_iter_manual(root:Scope) -> AST:
    """
    {
        it = iter([0,2..10])
        [cond, i] = next(it)
        loop cond {
            printl(i)
            [cond, i] = next(it)
        }
    }
    """
    return Block([
        Bind('it', RangeIter(Range(Number(0), Number(2), Number(10)))),
        Unpack(['cond', 'i'], Next(Call('it'))),

        Loop(
            Call('cond'),
            Block([
                Call('printl', [Call('i')]),
                Unpack(['cond', 'i'], Next(Call('it'))),
            ])
        )
    ])



def loop_in_iter(root:Scope) -> AST:
    """
    {
        loop i in [0,2..10] printl(i)
    }
    """
    return Loop(
        In('i', Range(Number(0), Number(2), Number(10))),
        Call('printl', [Call('i')]),
    )
   

def nested_loop(root:Scope) -> AST:
    """    
    loop i in [0,2..10]
        loop j in [0,2..10]
            printl('{i},{j}')
    """
    return Loop(
        In('i', Range(Number(0), Number(2), Number(10))),
        Loop(
            In('j', Range(Number(0), Number(2), Number(10))),
            Call('printl', [IString([Call('i'), String(','), Call('j')])]),
        )
    )



def block_printing(root:Scope) -> AST:
    """
    {
        loop i in [0,2..5] {
            loop j in [0,2..5] {
                loop k in [0,2..5] {
                    loop l in [0,2..5] {
                        loop m in [0,2..5] {
                            printl('{i},{j},{k},{l},{m}')
                        }
                    }
                }
            }
        }
    }
    """
    return Block([
        Loop(
            In('i', Range(Number(0), Number(2), Number(5))),
            Block([
                Loop(
                    In('j', Range(Number(0), Number(2), Number(5))),
                    Block([
                        Loop(
                            In('k', Range(Number(0), Number(2), Number(5))),
                            Block([
                                Loop(
                                    In('l', Range(Number(0), Number(2), Number(5))),
                                    Block([
                                        Loop(
                                            In('m', Range(Number(0), Number(2), Number(5))),
                                            Block([
                                                Call('printl', [IString([Call('i'), String(','), Call('j'), String(','), Call('k'), String(','), Call('l'), String(','), Call('m')])]),
                                            ])
                                        )
                                    ])
                                )
                            ])
                        )
                    ])
                )
            ])
        )
    ])

def rule110(root:Scope) -> AST:
    """
    progress = world:vector<bit> => {
        update:bit = 0
        loop i in 0..world.length
        {
            if i >? 0 world[i-1] = update //TODO: #notfirst handled by compiler unrolling the loop into prelude, interludes, and postlude
            update = 0b01110110 << (world[i-1..i+1] .?? 0 .<< [2 1 0])
        }
        world.push(update)
    }

    world: vector<bit> = [1]
    loop true
    {
        printl(world)
        progress(world)
    }
    """

    #rule 110
    #TODO: handle type annotations in AST
    return Block([
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




if __name__ == '__main__':
    show = True
    show_verbose = True
    run = True

    progs = [
        hello,
        hello_func,
        anonymous_func,
        hello_name,
        if_else,
        if_else_if,
        hello_loop,
        unpack_test,
        range_iter_test,
        loop_iter_manual,
        loop_in_iter,
        nested_loop,
        block_printing,
        # rule110,
    ]

    for prog in progs:
        #set up root scope with some functions
        root = Scope.default()

        # get the program AST
        ast = prog(root)

        # display and or run the program
        if show:
            print(ast)
        if show_verbose:
            print(repr(ast))
        if run:
            ast.eval(root)

        print('----------------------------------------')