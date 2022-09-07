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

    def get(self, name:str) -> AST:
        if name in self.vars:
            return self.vars[name]
        for p in self.parents: #TODO: may need to iterate in reverse to get same behavior as merging parent scopes
            if name in p.vars:
                return p.vars[name]
        raise NameError(name)

    def set(self, name:str, val:AST):
        self.vars[name] = val

    def __repr__(self):
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

root = Scope() #highest level of scope, mainly for builtins


def merge_scopes(*scopes:List[Scope], onto:Scope=None):
    #TODO... this probably could actually be a scope union class that inherits from Scope
    #            that way we don't have to copy the scopes
    pdb.set_trace()



class Function(AST):
    def __init__(self, name:str, args:List[Arg], bargs:List[BArg], body:AST, scope:Scope=None):
        self.name = name
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
        s = tab * indent + f'Function({self.name})\n'
        s += tab * (indent + 1) + f'args: {self.args}\n'
        s += tab * (indent + 1) + f'bargs: {self.bargs}\n'
        s += self.body.__str__(indent + 1)
        return s

builtins = {
    'print': partial(print, end=''),
    'printl': print,
    'readl': input
}
class Builtin(AST):
    def __init__(self, name:str, args:List[Arg], bargs:List[BArg], scope:Scope=None):
        self.name = name
        self.args = args
        self.bargs = bargs
        self.scope = scope
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

root.set('print', Builtin('print', ['text'], [], root))
root.set('printl', Builtin('printl', ['text'], [], root))
root.set('readl', Builtin('readl', [], [], root))


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
            try:
                return scope.get(self.name).eval(scope)
            except:
                pdb.set_trace()
        else:
            raise Exception(f'no scope provided for `{self.name}`')

    def __str__(self, indent=0):
        s = tab * indent + 'Call: ' + self.name + '\n'
        for arg in self.args:
            s += arg.__str__(indent + 1) + '\n'
        return s

    def __repr__(self):
        return f'Call({self.name}, {repr(self.args)})'

class Text(AST):
    def __init__(self, val:str):
        self.val = val
    def eval(self, scope:Scope=None):
        return self.val
    def __str__(self, indent=0):
        return f'{tab * indent}String: `{self.val}`'
    def __repr__(self):
        return f'Text({repr(self.val)})'

class String(AST):
    def __init__(self, parts:List[AST]):
        #convenience convert any str to Text
        self.parts = [Text(part) if isinstance(part, str) else part for part in parts]

    def eval(self, scope:Scope=None):
        return ''.join(part.eval(scope) for part in self.parts)

    def __str__(self, indent=0):
        s = tab * indent + 'String\n'
        for part in self.parts:
            s += part.__str__(indent + 1) + '\n'
        return s

    def __repr__(self):
        return f'String({repr(self.parts)})'

class Bind(AST):
    def __init__(self, name:str, value:AST):
        self.name = name
        self.value = value
    def eval(self, scope:Scope=None):
        scope.set(self.name, self.value)

    def __str__(self, indent=0):
        return f'{tab * indent}Bind: {self.name}\n{self.value.__str__(indent + 1)}'

    def __repr__(self):
        return f'Bind({self.name}, {repr(self.value)})'

def main():
    prog0 = Block([
        Call('printl', [Text('Hello, World!')]),
    ])
    print(prog0)
    prog0.eval(root)

    scope1 = Scope(root)
    prog1 = Block([
        Call('print', [Text("What's your name? ")]),
        Bind('name', Call('readl')),
        Call('printl', [String(['Hello ', Call('name'), '!'])]),
    ])
    print(prog1)
    prog1.eval(scope1)

if __name__ == '__main__':
    main()