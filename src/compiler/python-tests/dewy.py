from abc import ABC
from collections import namedtuple
from typing import List, Tuple
from functools import partial

import pdb

#Written in python3.10

#dumb look at interpreting/compiling dewy
#for now, construct the AST directly, skipping the parsing step


#convenient for inside lambdas
def notimplemented():
    raise NotImplementedError()

class AST(ABC):
    def eval(self, scope:'Scope'=None):
        raise NotImplementedError(f'{self.__class__.__name__}.eval')
    def comp(self, scope:'Scope'=None):
        raise NotImplementedError(f'{self.__class__.__name__}.comp')
    def type(self, scope:'Scope'=None):
        raise NotImplementedError(f'{self.__class__.__name__}.type')
    #TODO: other methods, e.g. semantic analysis
    def __str__(self, indent=0) -> str:
        raise NotImplementedError(f'{self.__class__.__name__}.__str__')
    def __repr__(self):
        raise NotImplementedError(f'{self.__class__.__name__}.__repr__')


Arg = str                #name of an argument
BArg = Tuple[Arg, AST]   #bound argument + current value
tab = '    ' #for printing ASTs

class Scope():
    def __init__(self, parents:'Scope'|List['Scope']=[]):
        if isinstance(parents, Scope):
            parents = [parents]
        self.parents = parents
        self.vars = {}
        self.types = {}

    def let(self, name:str, type:'Type'=None, const=False):
        pdb.set_trace()
        #set the type for the name


    def get(self, name:str) -> AST:
        if name in self.vars:
            return self.vars[name]
        for p in self.parents: #TODO: may need to iterate in reverse to get same behavior as merging parent scopes
            if name in p.vars:
                return p.vars[name]
        raise NameError(f'{name} not found in scope {self}')

    def set(self, name:str, val:AST):
        #check to ensure that `name` already has some type? or we can allow this and just default to `any` type
        #type of val must match existing type on `name`
        #also check to ensure that `name` is not const
        self.vars[name] = val
        

    def __repr__(self):
        if len(self.parents) > 0:
            return f'Scope({self.vars}, {self.parents})'
        return f'Scope({self.vars})'

    def copy(self):
        s = Scope(self.parents)
        s.vars = self.vars.copy()
        return s

    def attach_args(self, args:List[Arg], bargs:List[BArg]):
        for i, a in enumerate(args):
            self.set(f'.{i}', a)
        for a, v in bargs:
            self.set(a, v)



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

    def __str__(self, indent=0):
        s = tab * indent + f'Type: {self.name}\n'
        for p in self.params:
            s += p.__str__(indent + 1) + '\n'
        return s

    def __repr__(self):
        if len(self.params) > 0:
            return f'{self.name}<{", ".join(map(str, self.params))}>'
        return self.name

    # def __repr__(self):
        # return f'Type({self.name}, {self.params})'



class Function(AST):
    def __init__(self, args:List[Arg], bargs:List[BArg], body:AST, scope:Scope=None):
        self.args = args
        self.bargs = bargs
        self.body = body
        self.scope = scope #scope where the function was defined, which may be different from the scope where it is called
    def eval(self, scope:Scope=None):
        #collect args from calling scope, and merge into function scope
        fscope = self.scope.copy()
        for i, a in enumerate(self.args):
            fscope.set(a, scope.get(f'.{i}'))
        for a, v in self.bargs:
            fscope.set(a, v)
        return self.body.eval(fscope)

    def __str__(self, indent=0):
        s = tab * indent + f'Function()\n'
        s += tab * (indent + 1) + f'args: {self.args}\n'
        s += tab * (indent + 1) + f'bargs: {self.bargs}\n'
        s += self.body.__str__(indent + 1)
        return s

    def __repr__(self):
        return f'Function(args:{self.args}, bargs:{self.bargs}, body:{self.body}, scope:{self.scope})'

builtins = {
    'print': partial(print, end=''),
    'printl': print,
    'readl': input
}
class Builtin(AST):
    def __init__(self, name:str, args:List[Arg], bargs:List[BArg]):
        self.name = name
        self.args = args
        self.bargs = bargs
    def eval(self, scope:Scope=None):
        if self.name in builtins:
            f = builtins[self.name]
            args = [scope.get(f'.{i}').eval(scope) for i, a in enumerate(self.args)]
            kwargs = {a: v.eval(scope) for a, v in self.bargs}
            return f(*args, **kwargs)
        else:
            raise NameError(self.name, 'is not a builtin')

    def __str__(self, indent=0):
        s = tab * indent + f'Builtin({self.name})\n'
        s += tab * (indent + 1) + f'args: {self.args}\n'
        s += tab * (indent + 1) + f'bargs: {self.bargs}\n'
        return s

    def __repr__(self):
        return f'Builtin({self.name}, {self.args}, {self.bargs})'


class Let(AST):
    def __init__(self, name:str, type:Type, const=False):
        self.name = name
        self.type = type
        self.const = const

    def eval(self, scope:Scope=None):
        scope.let(self.name, self.type, self.const)

    def __str__(self, indent=0):
        return f'{tab * indent}Let: {self.name}\n{self.type.__str__(indent + 1)}'

    def __repr__(self):
        return f'Let({self.name}, {self.type})'

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

        scope.set(self.name, self.value)

    def __str__(self, indent=0):
        return f'{tab * indent}Bind: {self.name}\n{self.value.__str__(indent + 1)}'

    def __repr__(self):
        return f'Bind({self.name}, {repr(self.value)})'


class Block(AST):
    def __init__(self, exprs:List[AST]):
        self.exprs = exprs
    def eval(self, scope:Scope=None):
        for expr in self.exprs:
            expr.eval(scope)

    def __str__(self, indent=0):
        """print each expr on its own line, indented"""
        s = tab * indent + 'Block\n'
        for expr in self.exprs:
            s += expr.__str__(indent + 1)
        return s

    def __repr__(self):
        return f'Block({repr(self.exprs)})'


class Call(AST):
    def __init__(self, name:str, args:List[AST]=[], bargs:List[BArg]=[]):
        self.name = name
        self.args = args
        self.bargs = bargs

    def eval(self, scope:Scope=None):
        #make a fresh scope we can modify, and attach the calling args to it
        #TODO: maybe we could replace this with a view of the merged scopes. e.g. some sort of Scope union class...
        if scope is None:
            scope = Scope()
        else:
            scope = scope.copy()
        scope.attach_args(self.args, self.bargs)

        if scope is not None:
            return scope.get(self.name).eval(scope)
        else:
            raise Exception(f'no scope provided for `{self.name}`')

    def __str__(self, indent=0):
        s = tab * indent + 'Call: ' + self.name
        if len(self.args) > 0 or len(self.bargs) > 0:
            s += '\n'
            for arg in self.args:
                s += arg.__str__(indent + 1) + '\n'
            for a, v in self.bargs:
                s += tab * (indent + 1) + f'{a}={v}\n'
        return s

    def __repr__(self):
        return f'Call({self.name}, {repr(self.args)}, {repr(self.bargs)})'

class String(AST):
    def __init__(self, val:str):
        self.val = val
    def eval(self, scope:Scope=None):
        return self.val
    def __str__(self, indent=0):
        return f'{tab * indent}String: `{self.val}`'
    def __repr__(self):
        return f'String({repr(self.val)})'

class IString(AST):
    def __init__(self, parts:List[AST]):
        #convenience convert any str to Text
        # self.parts = [String(part) if isinstance(part, str) else part for part in parts]
        self.parts = parts

    def eval(self, scope:Scope=None):
        return ''.join(part.eval(scope) for part in self.parts)

    def __str__(self, indent=0):
        s = tab * indent + 'IString\n'
        for part in self.parts:
            s += part.__str__(indent + 1) + '\n'
        return s

    def __repr__(self):
        return f'IString({repr(self.parts)})'

class Number(AST):
    def __init__(self, val):
        self.val = val
    def eval(self, scope:Scope=None):
        return self.val
    def __str__(self, indent=0):
        return f'{tab * indent}Number: {self.val}'
    def __repr__(self):
        return f'Number({repr(self.val)})'

class Vector(AST):
    def __init__(self, vals:List[AST]):
        self.vals = vals
    def eval(self, scope:Scope=None):
        return [v.eval(scope) for v in self.vals]
    def __str__(self, indent=0):
        s = tab * indent + 'Vector\n'
        for v in self.vals:
            s += v.__str__(indent + 1) + '\n'
        return s
    def __repr__(self):
        return f'Vector({repr(self.vals)})'

def main():

    #set up root scope with some functions
    root = Scope() #highest level of scope, mainly for builtins
    root.set('print', Builtin('print', ['text'], []))
    root.set('printl', Builtin('printl', ['text'], []))
    root.set('readl', Builtin('readl', [], []))


    #Hello, World!
    prog0 = Block([
        Call('printl', [String('Hello, World!')]),
    ])
    # print(prog0)
    prog0.eval(root)

    #Hello <name>!
    prog1 = Block([
        Call('print', [String("What's your name? ")]),
        Bind('name', Call('readl')),
        Call('printl', [IString([String('Hello '), Call('name'), String('!')])]),
    ])
    # print(prog1)
    prog1.eval(root)

    #rule 110
    #TODO: handle type annotations in AST
    prog2 = Block([
        Bind(
            'update_world', 
            Function(['world'], [], Block([ #'world' should be type: vector<bit>
                Bind('cell_update', Number(0)),
                # loop i in 0..world.length
                #     if i >? 0 world[i-1] = cell_update
                #     update = (0b01110110 << (((world[i-1] ?? 0) << 2) or ((world[i] ?? 0) << 1) or (world[i+1] ?? 0)))
                # world.push(update)
                #etc....
            ]), root),
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
    prog2.eval(root)

if __name__ == '__main__':
    main()