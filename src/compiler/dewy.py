from abc import ABC
from dataclasses import dataclass
from types import EllipsisType
from typing import Any, Callable as PyCallable, Type as PyType, Union, Optional
from functools import partial
import operator

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
    
    #TODO: make accessing this raise better error if not overwritten by child class
    #      for now, just rely on exception for missing property
    # type:'Type' = None

    def eval(self, scope:'Scope'=None) -> 'AST':
        """Evaluate the AST in the given scope, and return the result (as a dewy obj) if any"""
        raise NotImplementedError(f'{self.__class__.__name__}.eval')
    def topy(self, scope:'Scope'=None) -> Any:
        """Convert the AST to a python equivalent object (usually unboxing the dewy object)"""
        raise NotImplementedError(f'{self.__class__.__name__}.topy')
    def comp(self, scope:'Scope'=None) -> str:
        """TODO: future handle compiling an AST to LLVM IR"""
        raise NotImplementedError(f'{self.__class__.__name__}.comp')
    # @abstractclassmethod
    # def type(cls, scope:'Scope'=None) -> 'Type':
    #     """Return the type of the object that would be returned by eval"""
    #     raise NotImplementedError(f'{cls.__name__}.type')
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

class PrototypeAST(AST):
    def eval(self, scope:'Scope'=None) -> AST:
        raise ValueError(f'Prototype ASTs may not define eval. Attempted to call eval on prototype {self}, of type ({type(self)})')

class Undefined(AST):
    """undefined singleton"""

    #type value is set in __new__, since class Type isn't declared yet
    type:'Type'

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Undefined, cls).__new__(cls)
        return cls.instance
    def eval(self, scope:'Scope'=None):
        return self
    def topy(self, scope:'Scope'=None):
        return None
    def typeof(self, scope:'Scope'=None):
        return Type('undefined')
    def treesr(self, indent=0):
        return tab * indent + 'Undefined'
    def __str__(self):
        return 'undefined'
    def __repr__(self):
        return 'Undefined()'

#undefined shorthand, for convenience
undefined = Undefined()




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
        self.args:Array|None = None

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
                assert Type.is_instance(value.typeof(), var.type), f'cannot assign {value}:{value.typeof()} to {name}:{var.type}'
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

    def attach_args(self, args:Union['Array', None]):
        self.args = args

    @staticmethod
    def default():
        """return a scope with the standard library (of builtins) included"""
        root = Scope()
        root.bind('print', Builtin('print', [Arg('text')], None, Type('callable', [Array([String.type]), Undefined.type])))
        root.bind('printl', Builtin('printl', [Arg('text')], None, Type('callable', [Array([String.type]), Undefined.type])))
        root.bind('readl', Builtin('readl', [], String, Type('callable', [Array([]), String.type])))
        #TODO: eventually add more builtins

        return root


#probably won't use this, except possibly for when calling functions and providing enums from the function's scope
# def merge_scopes(*scopes:list[Scope], onto:Scope=None):
#     #TODO... this probably could actually be a scope union class that inherits from Scope
#     #            that way we don't have to copy the scopes
#     pdb.set_trace()


class Type(AST):

    type:'Type'

    #map by name from simple types to their parent type in the type graph
    graph: dict[str, str|None] = {
        'callable': None,
        'function': 'callable',
        'builtin': 'callable'
    }

    def __init__(self, name:str|AST, params:list[AST]=None, parent:str=None):
        self.name = name
        self.params = params or []
        
        # register type in the type graph
        if isinstance(name, str) and name not in Type.graph:
            Type.graph[name] = parent
        
    def eval(self, scope:Scope=None):
        return self

    def typeof(self, scope:Scope=None):
        return Type('type')
    

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
    
    def __and__(self, other:AST):
        return And(self, other, Type)
    
    def __rand__(self, other:AST):
        return And(other, self, Type)
    
    def __or__(self, other:AST):
        return Or(self, other, Type)
    
    def __ror__(self, other:AST):
        return Or(other, self, Type)

    def __eq__(self, other):
        raise NotImplementedError('Type comparisons should be performed with `Type.is_instance()`')
    
    #TODO: come up with better names for the method arguments
    @staticmethod
    def is_instance(obj_t:Union['Type',Undefined], target_t:Union['Type',Undefined]) -> bool:
        """
        Check if the object is an instance (or descendent) of the specified type

        if target_t is undefined, short circuit results to True.
        Parameters are only checked based on those present in target_t, 
            e.g. if obj_t=array<int> and target_t=array, then no params would be checked (and is_instance would be true)

        Args:
            obj_t (Type|Undefined): The type of the object to be checked (i.e. for some dewy obj, obj_t = obj.typeof())
            target_t: (Type|Undefined): The target type for determining if obj_t is an instance or not

        Returns:
            (bool): whether or not obj_t is an instance (or descendent) of target_t
        """
        assert isinstance(target_t, (Type, Undefined)), f't must be a Type or undefined, not {target_t}'
        assert isinstance(obj_t, (Type, Undefined)), f'obj_t must be a Type or undefined, not {obj_t}'
        
        # undefined target always returns true
        if isinstance(target_t, Undefined):
            return True
        
        # since target is not undefined, undefined obj_t necessarily doesn't match
        if isinstance(obj_t, Undefined):
            return False
        
        
        #DEBUG/TODO
        if isinstance(target_t.name, AST) and isinstance(obj_t.name, AST):
            #TODO: need to make AST equality work properly (namely for binops and/or)
            #      will remove this if check, and let target.name == obj_t.name handle it
            pdb.set_trace()
        
        # check the type by name, and params
        if target_t.name == obj_t.name:
            if len(obj_t.params) < len(target_t.params):
                return False
            
            # check if any object parameters don't match the present target parameters
            # note: obj_t may have more params than target_t
            if any(obj_param != target_param for obj_param, target_param in zip(target_t.params, obj_t.params)):
                return False
                
            # names match, and obj_t has all params target_t has
            return True
        

        # for non-matching name, if atomic type, recursively check parent type in graph for compatibility
        if isinstance(obj_t.name, str):
            parent = Type.graph[obj_t.name]
            if parent is not None:
                #TODO: this is a poor way to check for parent types. Assumes parent parameters are same shape as child type...
                return Type.is_instance(Type(parent, obj_t.params), target_t)

        return False

# set the type class property for Type, and Undefined since class Type() exists now
Type.type = Type('type')
Undefined.type = Type('undefined')

class Identifier(PrototypeAST):
    # intermediate node, expected to be replaced with call or etc. during AST construction

    def __init__(self, name:str) -> None:
        self.name = name
    
    def __str__(self) -> str:
        return f'{self.name}'
    
    def __repr__(self) -> str:
        return f'Identifier({self.name})'


class Callable(AST):

    type:Type = Type('callable')

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




class Arg:
    def __init__(self, name:str, type:Type=None, val:AST|None=None):
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
    
    type:Type = Type('function')

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

        # grab the args being passed in
        caller_args:list[AST] = []
        caller_kwargs:dict[str,AST] = {}
        if scope is not None and scope.args is not None:
            for arg in scope.args.vals:
                if not isinstance(arg, Bind):
                    caller_args.append(arg)
                else:
                    caller_kwargs[arg.name] = arg.value
        
        # grab the args and any default args from the function definition
        fn_args = [arg for arg in self.args if arg.val is None and arg.name not in caller_kwargs]
        fn_kwargs = [arg for arg in self.args if arg.val is not None and arg.name not in caller_kwargs]
        fn_arg_names = {arg.name for arg in self.args}

        # bind the positional arguments to the function scope
        assert len(fn_args) == len(caller_args), f'encountered different number of positional arguments than expected. Function is defined with {[a for a in self.args if a.val is None]}. Tried to call with {caller_args}'
        for fn_arg, caller_arg in zip(fn_args, caller_args):
            fscope.let(fn_arg.name, caller_arg)

        # bind keyward arguments to the function scope, first from default args, then from caller
        for fn_kwarg in fn_kwargs:
            fscope.let(fn_kwarg.name, fn_kwarg.val)
        for caller_kwarg_name, caller_kwarg_value in caller_kwargs.items():
            assert caller_kwarg_name in fn_arg_names, f"tried to bind unrecognized keyword argument '{caller_kwarg_name}' to function {self}"
            fscope.let(caller_kwarg_name, caller_kwarg_value)

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

    type:Type = Type('builtin')

    def __init__(self, name:str, args:list[Arg], cls:PyCallable, type:Type):
        self.name = name
        self.args = args
        self.cls = cls
        self.type = type
    
    def eval(self, scope:Scope=None):
        return self
    
    def call(self, scope:Scope=None):
        if self.name in Builtin.funcs:
            f = Builtin.funcs[self.name]
            #TODO: this doesn't handle differences in named vs unnamed args between the function definition and the call

            args = []
            kwargs = {}

            # insert positional and keyward args from the call
            if scope.args is not None:
                for ast in scope.args.vals:
                    if not isinstance(ast, Bind):
                        args.append(ast.eval(scope).topy(scope))
                    else:
                        kwargs[ast.name] = ast.value.eval(scope).topy(scope)

            # insert any default/named args (not already inserted by the call)
            for arg in self.args:
                if arg.val is not None and arg.name not in kwargs:
                    kwargs[arg.name] = arg.val.eval(scope).topy(scope)

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

class Tuple(PrototypeAST):
    """
    A comma separated list of expressions (not wrapped in parentheses) e.g. 1, 2, 3
    There is no special in-memory representation of a tuple, it is literally just a const list
    """
    def __init__(self, exprs:list[AST]):
        self.exprs = exprs
    def __repr__(self):
        return f'Tuple({repr(self.exprs)})'
    

class Block(AST):
    def __init__(self, exprs:list[AST], newscope:bool=True):
        self.exprs = exprs
        self.newscope = newscope
    def eval(self, scope:Scope=None):
        #TODO: handle flow control from a block, e.g. return, break, continue, express, etc.
        if self.newscope:
            scope = Scope(scope)
        expressed = []
        for expr in self.exprs:
            res = expr.eval(scope)
            if res is not None and res is not void:
                expressed.append(res)
        if len(expressed) == 0:
            return void
        if len(expressed) == 1:
            return expressed[0]
        raise NotImplementedError('block with multiple expressions not yet supported')
        #TODO: this is actually a lot like `yield`! maybe `yield` should be instead of `express` or they are synonymous
        return Array(expressed)

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
    def __init__(self, expr:str|Callable, args:Union['Array',None]=None):
        assert isinstance(expr, str|Callable), f'invalid type for call expression: `{self.expr}` of type `{type(self.expr)}`'
        self.expr = expr
        self.args = args


    def eval(self, scope:Scope):
        scope.attach_args(self.args)

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
        if self.args is not None:
            s += '\n'
            s += self.args.treestr(indent+1)
        return s

    @insert_tabs
    def __str__(self):
        #TODO: not sure if expr of type Function should get () even if they don't have args
        argsstr = '' if self.args is None else f'({str(self.args)[1:-1]})' #strip off [] and replace with ()
        return f'{self.expr}' + (f'{self.args}' if self.args else '')

    def __repr__(self):
        return f'Call({repr(self.expr)}, {repr(self.args)})'

class String(Rangeable):
    type:Type=Type('string')
    
    def __init__(self, val:str):
        self.val = val
    def eval(self, scope:Scope=None):
        return self
    def typeof(self, scope:Scope=None):
        return self.type
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
    def __init__(self, left:AST, right:AST, op:PyCallable[[Any, Any],Any], outtype:PyType[AST]|None, opname:str, opsymbol:str):
        self.left = left
        self.right = right
        self.op = op
        self.outtype = outtype
        self.opname = opname
        self.opsymbol = opsymbol

    def eval(self, scope:Scope=None):
        left = self.left.eval(scope)
        right = self.right.eval(scope)
        outtype = self.outtype

        if outtype is None:
            #TODO: remove support for this later. type should be determined after parsing during type checking!
            # determine the outtype from the input types
            assert type(left) == type(right), f"For unspecified output type, both left and right must have the same type. Found {type(left)=}, {type(right)=}"
            outtype = type(left)

        return outtype(self.op(left.topy(), right.topy()))
    

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
        super().__init__(left, right, operator.eq, Bool, 'Equal', '=?')

class NotEqual(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, operator.ne, Bool, 'NotEqual', 'not=?')

class Less(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, operator.lt, Bool, 'Less', '<?')

class LessEqual(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, operator.le, Bool, 'LessEqual', '<=?')

class Greater(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, operator.gt, Bool, 'Greater', '>?')

class GreaterEqual(BinOp):
    def __init__(self, left:AST, right:AST):
        super().__init__(left, right, operator.ge, Bool, 'GreaterEqual', '>=?')

class Add(BinOp):
    def __init__(self, left:AST, right:AST, outtype:PyType[AST]):
        super().__init__(left, right, operator.add, outtype, 'Add', '+')

class Sub(BinOp):
    def __init__(self, left:AST, right:AST, outtype:PyType[AST]):
        super().__init__(left, right, operator.sub, outtype, 'Sub', '-')

class Mul(BinOp):
    def __init__(self, left:AST, right:AST, outtype:PyType[AST]):
        super().__init__(left, right, operator.mul, outtype, 'Mul', '*')

class Div(BinOp):
    def __init__(self, left:AST, right:AST, outtype:PyType[AST]):
        super().__init__(left, right, operator.truediv, outtype, 'Div', '/')

class IDiv(BinOp):
    def __init__(self, left:AST, right:AST, outtype:PyType[AST]):
        super().__init__(left, right, operator.floordiv, outtype, 'IDiv', '//')

class Mod(BinOp):
    def __init__(self, left:AST, right:AST, outtype:PyType[AST]):
        super().__init__(left, right, operator.mod, outtype, 'Mod', '%')

class Pow(BinOp):
    def __init__(self, left:AST, right:AST, outtype:PyType[AST]):
        super().__init__(left, right, operator.pow, outtype, 'Pow', '**')

class And(BinOp):
    def __init__(self, left:AST, right:AST, outtype:PyType[AST]):
        super().__init__(left, right, operator.and_, outtype, 'And', 'and')

class Or(BinOp):
    def __init__(self, left:AST, right:AST, outtype:PyType[AST]):
        super().__init__(left, right, operator.or_, outtype, 'Or', 'or')

class Xor(BinOp):
    def __init__(self, left:AST, right:AST, outtype:PyType[AST]):
        super().__init__(left, right, operator.xor, outtype, 'Xor', 'xor')

class Nand(BinOp):
    def __init__(self, left:AST, right:AST, outtype:PyType[AST]):
        super().__init__(left, right, lambda l, r: not (l and r), outtype, 'Nand', 'nand')

class Nor(BinOp):
    def __init__(self, left:AST, right:AST, outtype:PyType[AST]):
        super().__init__(left, right, lambda l, r: not (l or r), outtype, 'Nor', 'nor')

class Xnor(BinOp):
    def __init__(self, left:AST, right:AST, outtype:PyType[AST]):
        super().__init__(left, right, lambda l, r: l == r, outtype, 'Xnor', 'xnor')



##################### Unary operators #####################
class UnaryOp(AST):
    def __init__(self, child:AST, op:PyCallable[[Any, Any],Any], outtype:PyType[AST]|None, opname:str, opsymbol:str):
        self.child = child
        self.op = op
        self.outtype = outtype
        self.opname = opname
        self.opsymbol = opsymbol

    def eval(self, scope:Scope=None):
        child = self.child.eval(scope)
        outtype = self.outtype

        if outtype is None:
            #TODO: remove support for this later. type should be determined after parsing during type checking!
            # determine the outtype from the input type
            outtype = type(child)

        return outtype(self.op(child.topy()))

    def treestr(self, indent=0):
        return f'{tab * indent}{self.opname}\n{self.child.treestr(indent + 1)}'
    @insert_tabs
    def __str__(self):
        return f'{self.opsymbol}{self.child}'
    def __repr__(self):
        return f'{self.opname}({repr(self.child)})'

class Neg(UnaryOp):
    def __init__(self, child:AST, outtype:PyType[AST]):
        super().__init__(child, operator.neg, outtype, 'Neg', '-')

class Inv(UnaryOp):
    def __init__(self, child:AST, outtype:PyType[AST]):
        super().__init__(child, lambda x: 1/x, outtype, 'Inv', '/')

class Not(UnaryOp):
    def __init__(self, child:AST, outtype:PyType[AST]):
        super().__init__(child, operator.not_, outtype, 'Not', 'not')

class Bool(AST):
    def __init__(self, val:bool):
        self.val = val
    def eval(self, scope:Scope=None):
        return self
    def topy(self, scope:Scope=None):
        return self.val
    def typeof(self, scope:Scope=None):
        return Type('bool')
    def treestr(self, indent=0):
        return f'{tab * indent}Bool: {self.val}'
    # @insert_tabs
    def __str__(self):
        return f'{self.val}'
    def __repr__(self):
        return f'Bool({repr(self.val)})'

class Flowable(AST):
    def was_entered(self) -> bool:
        """Determine if the flowable branch was entered. Should reset before performing calls to flow and checking this."""
        raise NotImplementedError(f'flowables must implement `was_entered()`. No implementation found for {self.__class__}')

    def reset_was_entered(self) -> None:
        """reset the state of was_entered, in preparation for executing branches in a flow"""
        raise NotImplementedError(f'flowables must implement `reset_was_entered()`. No implementation found for {self.__class__}')

class If(Flowable):
    def __init__(self, cond:AST, body:AST):
        self.cond = cond
        self.body = body
        self._was_entered: bool = False
    
    def was_entered(self) -> bool:
        return self._was_entered
    
    def reset_was_entered(self) -> None:
        self._was_entered = False
    
    def eval(self, scope:Scope=None):
        child = Scope(scope) #if clause gets an anonymous scope
        if self.cond.eval(child).topy(child):
            self._was_entered = True
            return self.body.eval(child)

    def treestr(self, indent=0):
        s = tab * indent + 'If\n'
        s += self.cond.treestr(indent + 1) + '\n'
        s += self.body.treestr(indent + 1) + '\n'
        return s

    @insert_tabs
    def __str__(self):
        return f'if {self.cond} {self.body}'
        
    def __repr__(self):
        return f'If({repr(self.cond)}, {repr(self.body)})'

#TODO: maybe loop can work the say way as If, taking in a list of clauses?
class Loop(Flowable):
    def __init__(self, cond:AST, body:AST):
        self.cond = cond
        self.body = body
        self._was_entered: bool = False
    
    def was_entered(self) -> bool:
        return self._was_entered
    
    def reset_was_entered(self) -> None:
        self._was_entered = False

    def eval(self, scope:Scope=None):
        child = Scope(scope)
        while self.cond.eval(child).topy(child):
            self._was_entered = True
            self.body.eval(child)
        #TODO: handle capturing values from a loop
        #TODO: handle break and continue
        #TODO: also eventually handle return (problem for other ASTs as well)

        #for now just don't let loops return anything
        return void

    def treestr(self, indent=0):
        return f'{tab * indent}Loop\n{self.cond.treestr(indent + 1)}\n{self.body.treestr(indent + 1)}'

    @insert_tabs
    def __str__(self):
        return f'loop {self.cond} {self.body}'

    def __repr__(self):
        return f'Loop({repr(self.cond)}, {repr(self.body)})'

class Flow(AST):
    def __init__(self, branches:list[Flowable|AST]):
        
        #separate out the possible last branch which need not be a Flowable()
        if not isinstance(branches[-1], Flowable):
            branches, default = branches[:-1], branches[-1]
        else:
            branches, default = branches, None
        
        #verify all branches (not necessarily including last) are Flowable
        assert all(isinstance(branch, Flowable) for branch in branches), f'All branches in a flow (excluding the last one) must inherit `Flowable()`. Got {branches=}'
        
        self.branches: list[Flowable] = branches
        self.default: AST|None = default
        
    
    def eval(self, scope:Scope=None):
        shared = Scope(scope) #for now, all clauses share a common anonymous scope

        #reset was entered for this execution of the flow
        for expr in self.branches:
            expr.reset_was_entered()

        #execute branches in the flow until one is entered
        for expr in self.branches:
            res = expr.eval(shared)
            if expr.was_entered():
                return res
            
        #execute any default branch if it exists
        if self.default is not None:
            return self.default.eval(shared)
        
        return undefined

    def treestr(self, indent=0):
        s = tab * indent + 'Flow\n'
        for expr in self.branches:
            s += expr.treestr(indent + 1) + '\n'
        if self.default is not None:
            s += self.default.treestr(indent + 1) + '\n'
        return s

    @insert_tabs
    def __str__(self):
        s = ''
        for i, expr in enumerate(self.branches):
            if i == 0:
                s += f'{expr}'
            else:
                s += f' else {expr}'
        if self.default is not None:
            s += f' else {self.default}'
        return s

    def __repr__(self):
        return f'Flow({repr(self.branches)})'


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
#class iter is the manager for things that can iterate, e.g. Range.iter()->RangeIter, Array.iter()->ArrayIter, etc.
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
    type:Type = Type('number')

    def __init__(self, val:int|float):
        self.val = val
    def eval(self, scope:Scope=None):
        return self
    def typeof(self):
        return Type('number')
    
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
    def max() -> 'Number':
        return Number(float('inf'))
    @staticmethod
    def min() -> 'Number':
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
        
        # DEBUG: for now, require that ranges were wrapped in [], [), (], or () to avoid ambiguity
        # this means at parse time, when the range is first made, was_wrapped will be false
        # and then when the enclosing block is parsed, was_wrapped can be set to true
        self.was_wrapped = False

    def eval(self, scope:Scope=None):
        return self
    
    def iter(self, scope:'Scope'=None) -> Iter:
        return RangeIter(self)

    # def typeof(self):
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
            return Array([Bool(True), ret])
        else:
            return Array([Bool(False), undefined])

    def typeof(self):
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


class Array(Iterable, Unpackable):
    def __init__(self, vals:list[AST]):
        self.vals = vals
    def eval(self, scope:Scope=None):
        return self
    def typeof(self, scope:Scope=None):
        #TODO: this should include the type of the data inside the vector...
        return Type('Array')
    
    #unpackable interface
    def len(self, scope:Scope=None):
        return len(self.vals)
    def get(self, key:int|EllipsisType|slice|tuple[int|EllipsisType|slice], scope:Scope=None):
        if isinstance(key, int):
            return self.vals[key]
        elif isinstance(key, EllipsisType):
            return self
        elif isinstance(key, slice):
            return Array(self.vals[key])
        elif isinstance(key, tuple):
            #probably only valid for N-dimensional/non-jagged vectors
            raise NotImplementedError('TODO: implement tuple indexing for Array')
        else:
            raise TypeError(f'invalid type for Array.get: `{key}` of type `{type(key)}`')


    #iterable interface
    #TODO...

    def topy(self, scope:Scope=None):
        return [v.eval(scope).topy(scope) for v in self.vals]
    def treestr(self, indent=0):
        s = tab * indent + 'Array\n'
        for v in self.vals:
            s += v.treestr(indent + 1) + '\n'
        return s
    @insert_tabs
    def __str__(self):
        return f'[{" ".join(map(str, self.vals))}]'
    def __repr__(self):
        return f'Array({repr(self.vals)})'



class Void(AST):
    """void singleton"""

    type:Type=Type('void')

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Void, cls).__new__(cls)
        return cls.instance
    def eval(self, scope:Scope=None):
        return self
    def topy(self, scope:Scope=None):
        return None
    def typeof(self, scope:Scope=None):
        return Type('void')
    def treesr(self, indent=0):
        return tab * indent + 'Void'
    def __str__(self):
        return 'void'
    def __repr__(self):
        return 'Void()'

#void shorthand, for convenience
void = Void()





############################################## EXAMPLE PROGRAMS #############################################

def hello(root:Scope) -> AST:
    """printl('Hello, World!')"""
    return Call('printl', Array([String('Hello, World!')]))


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
                Call('printl', Array([String('Hello, World!')])),
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
                Call('printl', Array([String('Hello, World!')])),
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
        Call('print', Array([String("What's your name? ")])),
        Bind('name', Call('readl')),
        Call('printl', Array([IString([String('Hello '), Call('name'), String('!')])])),
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
        Call('print', Array([String("What's your name? ")])),
        Bind('name', Call('readl')),
        Flow([
            If(
                Equal(Call('name'), String('Alice')),
                Call('printl', Array([String('Hello Alice!')]))
            ),
            Call('printl', Array([String('Hello Stranger!')])),
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
        Call('print', Array([String("What's your name? ")])),
        Bind('name', Call('readl')),
        Flow([
            If(
                Equal(Call('name'), String('Alice')),
                Call('printl', Array([String('Hello Alice!')]))
            ),
            If(
                Equal(Call('name'), String('Bob')),
                Call('printl', Array([String('Hello Bob!')]))
            ),
            Call('printl', Array([String('Hello Stranger!')])),
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
        Call('print', Array([String("What's your name? ")])),
        Bind('name', Call('readl')),
        Bind('i', Number(0)),
        Loop(
            Less(Call('i'), Number(10)),
            Block([
                Call('printl', Array([IString([String('Hello '), Call('name'), String('!')])])),
                Bind('i', Add(Call('i'), Number(1), Number)),
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
        Bind('s', Array([String('Hello'), Array([String('World'), String('!')]), Number(5), Number(10)])),
        Call('printl', Array([IString([String('s='), Call('s')])])),
        Unpack(['a', 'b', 'c', 'd'], Call('s')),
        Call('printl', Array([IString([String('a='), Call('a'), String(' b='), Call('b'), String(' c='), Call('c'), String(' d='), Call('d')])])),
        Unpack(['a', '...b'], Call('s')),
        Call('printl', Array([IString([String('a='), Call('a'), String(' b='), Call('b')])])),
        Unpack(['...a', 'b'], Call('s')),
        Call('printl', Array([IString([String('a='), Call('a'), String(' b='), Call('b')])])),
        Unpack(['a', ['b', 'c'], '...d'], Call('s')),
        Call('printl', Array([IString([String('a='), Call('a'), String(' b='), Call('b'), String(' c='), Call('c'), String(' d='), Call('d')])])),

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
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])), #should print [False, None] since the iterator is exhausted
        Call('printl', Array([Next(Call('it'))])),
        Call('printl', Array([Next(Call('it'))])),
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
                Call('printl', Array([Call('i')])),
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
        Call('printl', Array([Call('i')])),
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
            Call('printl', Array([IString([Call('i'), String(','), Call('j')])])),
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
                                                Call('printl', Array([IString([Call('i'), String(','), Call('j'), String(','), Call('k'), String(','), Call('l'), String(','), Call('m')])])),
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
            Array([Number(1)]),
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