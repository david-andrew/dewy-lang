from abc import ABC
from collections import defaultdict, namedtuple
from dataclasses import dataclass
from typing import Any, List, Tuple, Callable as PyCallable, Union
from functools import partial

import pdb

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
    def comp(self, scope:'Scope'=None):
        """TODO: future handle compiling an AST to LLVM IR"""
        raise NotImplementedError(f'{self.__class__.__name__}.comp')
    def type(self, scope:'Scope'=None):
        """Return the type of the object that would be returned by eval"""
        raise NotImplementedError(f'{self.__class__.__name__}.type')
    #TODO: other methods, e.g. semantic analysis
    def treestr(self, indent=0) -> str:
        """Return a string representation of the AST tree"""
        raise NotImplementedError(f'{self.__class__.__name__}.treestr')
    def __str__(self) -> str:
        """Return a string representation of the AST as dewy code"""
        raise NotImplementedError(f'{self.__class__.__name__}.__str__')
    def __repr__(self):
        """Return a string representation of the python objects making up the AST"""
        raise NotImplementedError(f'{self.__class__.__name__}.__repr__')

class Callable(AST):
    def call(self, scope:'Scope'=None):
        """Call the callable in the given scope"""
        raise NotImplementedError(f'{self.__class__.__name__}.call')

class Undefined(AST):
    def __init__(self):
        pass
    def eval(self, scope:'Scope'=None):
        return self
    def topy(self, scope:'Scope'=None):
        return None
    def treesr(self, indent=0):
        return tab * indent + 'Undefined'
    def __str__(self):
        return 'undefined'
    def __repr__(self):
        return 'Undefined()'

undefined = Undefined() #singleton instance of undefined

tab = '    ' #for printing ASTs
BArg = Tuple[str, AST]   #bound argument + current value for when making function calls

class Scope():
    
    @dataclass
    class _var():
        # name:str #name is stored in the dict key
        type:AST
        value:AST
        const:bool
    
    def __init__(self, parents:'Scope'|List['Scope']=[]):
        if isinstance(parents, Scope):
            parents = [parents]
        self.parents = parents
        self.vars = {} #defaultdict(lambda: Scope._var(undefined, undefined, False)) #default dict would cause more bugs, e.g. from mispelling a variable name

    def let(self, name:str, type:'Type'=undefined, value:AST=undefined, const=False):
        #overwrite anything that might have previously been there
        self.vars[name] = Scope._var(type, value, const)


    def get(self, name:str) -> AST:
        if name in self.vars:
            return self.vars[name].value
        for p in self.parents: #TODO: may need to iterate in reverse to get same behavior as merging parent scopes
            if name in p.vars:
                return p.vars[name].value
        raise NameError(f'{name} not found in scope {self}')

    def bind(self, name:str, value:AST):

        #update an existing variable in this scope
        if name in self.vars:
            var = self.vars[name]
            assert not var.const, f'cannot assign to const {name}'
            assert Type.compatible(var.type, value.type()), f'cannot assign {value}:{value.type()} to {name}:{var.type}'
            self.vars[name].value = value
            return
        
        #update an existing variable in any of the parent scopes
        for p in self.parents:
            if name in p.vars:
                assert not self.vars[name].const, f'cannot assign to const {name}'
                assert Type.compatible(var.type, value.type()), f'cannot assign {value}:{value.type()} to {name}:{var.type}'
                p.vars[name].value = value
                return

        #otherwise just create a new instance of the variable
        self.vars[name] = Scope._var(undefined, value, False)

    def __repr__(self):
        if len(self.parents) > 0:
            return f'Scope({self.vars}, {self.parents})'
        return f'Scope({self.vars})'

    def copy(self):
        s = Scope(self.parents)
        s.vars = self.vars.copy()
        return s

    #TODO:consider having a custom space in a scope for storing current call arguments...
    def attach_args(self, args:List[AST], bargs:List[BArg]): 
        #TODO: args should have a separate parameter in the scope, e.g. self.args/self.bargs
        #      that way we can't have a name collision, e.g. if a function and barg have the same name
        for i, a in enumerate(args):
            self.bind(f'.{i}', a)
        for a, v in bargs:
            self.bind(a, v)

def merge_scopes(*scopes:List[Scope], onto:Scope=None):
    #TODO... this probably could actually be a scope union class that inherits from Scope
    #            that way we don't have to copy the scopes
    pdb.set_trace()


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
        if rule == undefined:
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
        for i, a in enumerate(self.args):
            fscope.bind(a, scope.get(f'.{i}'))
        for a, v in self.bargs:
            fscope.bind(a, v)
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

builtins = {
    'print': partial(print, end=''),
    'printl': print,
    'readl': input
}
class Builtin(Callable):
    def __init__(self, name:str, args:List[Arg], cls:PyCallable=None):
        self.name = name
        self.args = args
        self.cls = cls
    
    def eval(self, scope:Scope=None):
        return self
    
    def call(self, scope:Scope=None):
        if self.name in builtins:
            f = builtins[self.name]
            args = [scope.get(f'.{i}').eval(scope).topy(scope) for i, a in enumerate(self.args) if a.val is None]
            kwargs = {a: a.val.eval(scope).topy(scope) for a in self.args if a.val is not None}
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
    def __init__(self, name:str, value:AST):
        self.name = name
        self.value = value
    def eval(self, scope:Scope=None):
        #TODO: 
        # 1. check if name was already typed/new type is compatible
        # 2. check if value is compatible with type
        #if name doesn't exist in scope (or parents scope)
        #  use given type
        #else if given type is none, 
        #  use existing type
        #else
        #  overwrite existing type with new type? alternatively this is an error...
        #  also need to figure out let/const bindings.../ how they play with simple bindings
        scope.bind(self.name, self.value.eval(scope))

    def treestr(self, indent=0):
        return f'{tab * indent}Bind: {self.name}\n{self.value.treestr(indent + 1)}'

    def __str__(self):
        return f'{self.name} = {self.value}'

    def __repr__(self):
        return f'Bind({self.name}, {repr(self.value)})'


class Block(AST):
    def __init__(self, exprs:List[AST]):
        self.exprs = exprs
    def eval(self, scope:Scope=None):
        #TODO: handle flow control from a block, e.g. return, break, continue, express, etc.
        for expr in self.exprs:
            # print(scope)
            # if isinstance(expr, Call):
            #     pdb.set_trace()
            expr.eval(scope)
        #TODO: return Undefined if nothing is returned

    def treestr(self, indent=0):
        """print each expr on its own line, indented"""
        s = tab * indent + 'Block\n'
        for expr in self.exprs:
            s += expr.__str__(indent + 1)
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
        #TODO: maybe we could replace this with a view of the merged scopes. e.g. some sort of Scope union class...
        # if scope is None:
            # scope = Scope() #TODO: also, does this even make sense? can you ever call something if there was no scope which would contain it?
        # else:
        scope = scope.copy()
        scope.attach_args(self.args, self.bargs)

        #TODO: depending on the type, do different things
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
        #convenience convert any str to Text
        # self.parts = [String(part) if isinstance(part, str) else part for part in parts]
        self.parts = parts

    def eval(self, scope:Scope=None):
        return self

    def topy(self, scope:Scope=None):
        return ''.join(part.eval(scope).topy(scope) for part in self.parts)

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

class Equal(AST):
    def __init__(self, left:AST, right:AST):
        self.left = left
        self.right = right
    def eval(self, scope:Scope=None):
        return Bool(self.left.eval(scope).topy() == self.right.eval(scope).topy())
    def treestr(self, indent=0):
        return f'{tab * indent}Equal\n{self.left.treestr(indent + 1)}\n{self.right.treestr(indent + 1)}'
    def __str__(self):
        return f'{self.left} =? {self.right}'
    def __repr__(self):
        return f'Equal({repr(self.left)}, {repr(self.right)})'

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
    def __init__(self, clauses:List[Tuple[AST, AST]]):
        self.clauses = clauses
    
    def eval(self, scope:Scope=None):
        for cond, expr in self.clauses:
            if cond.eval(scope).topy(scope):
                return expr.eval(scope)

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


class Number(AST):
    def __init__(self, val):
        self.val = val
    def eval(self, scope:Scope=None):
        return self
    def topy(self, scope:Scope=None):
        return self.val
    def treestr(self, indent=0):
        return f'{tab * indent}Number: {self.val}'
    def __str__(self):
        return f'{self.val}'
    def __repr__(self):
        return f'Number({repr(self.val)})'

class Vector(AST):
    def __init__(self, vals:List[AST]):
        self.vals = vals
    def eval(self, scope:Scope=None):
        return self
    def topy(self, scope:Scope=None):
        return [v.eval(scope) for v in self.vals]
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



def hello_name():

    #set up root scope with some functions
    root = Scope() #highest level of scope, mainly for builtins
    root.bind('print', Builtin('print', [Arg('text')]))
    root.bind('printl', Builtin('printl', [Arg('text')]))
    root.bind('readl', Builtin('readl', [], String))

    #Hello <name>!
    prog1 = Block([
        Call('print', [String("What's your name? ")]),
        Bind('name', Call('readl')),
        Call('printl', [IString([String('Hello '), Call('name'), String('!')])]),
    ])
    # print(prog1)
    prog1.eval(root)



def if_else():

    #set up root scope with some functions
    root = Scope() #highest level of scope, mainly for builtins
    root.bind('print', Builtin('print', [Arg('text')]))
    root.bind('printl', Builtin('printl', [Arg('text')]))
    root.bind('readl', Builtin('readl', [], String))

    #if name =? 'Alice' then print 'Hello Alice!' else print 'Hello stranger!'
    prog2 = Block([
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
    # print(prog2)
    prog2.eval(root)


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
    prog3 = Block([
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
    # print(prog3)
    prog3.eval(root)



def rule110():

    #set up root scope with some functions
    root = Scope() #highest level of scope, mainly for builtins
    root.bind('print', Builtin('print', [Arg('text')]))
    root.bind('printl', Builtin('printl', [Arg('text')]))
    root.bind('readl', Builtin('readl', [], String))

    #rule 110
    #TODO: handle type annotations in AST
    prog2 = Block([
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
    # print(prog2)
    prog2.eval(root)




if __name__ == '__main__':
    # hello()
    # hello_name()
    # if_else()
    if_else_if()
    # rule110()