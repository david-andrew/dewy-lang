from dataclasses import dataclass

from ..tokenizer import tokenize
from ..postok import post_process
from ..parser import top_level_parse, Scope
from ..syntax import AST, Type, undefined, untyped, void, DeclarationType


import pdb

def python_interpreter(path: str, args: list[str]):

    with open(path) as f:
        src = f.read()

    tokens = tokenize(src)
    post_process(tokens)

    ast = top_level_parse(tokens)
    print(f'parsed AST: {ast}\n{repr(ast)}')
    exit(1)
    raise NotImplementedError("evaluation hasn't been implemented yet")

    res = top_level_evaluate(ast)
    if res and res is not void:
        print(res)



# # For now, scope lives here, but perhaps we will move it to a higher level if it can be shared between backends

# class Scope():
#     @dataclass
#     class _var():
#         # name:str #name is stored in the dict key
#         decltype: DeclarationType
#         type: AST
#         value: AST

#     def __init__(self, parent: 'Scope | None' = None):
#         self.parent = parent
#         self.vars: dict[str, Scope._var] = {}

#     @property
#     def root(self) -> 'Scope':
#         """Return the root scope"""
#         return [*self][-1]

#     def declare(self, decltype: DeclarationType, name: str, type: Type, value: AST = undefined):
#         pdb.set_trace()  # TODO: are there circumstances overwriting an existing variable is allowed? e.g. if it was LET?
#         if name in self.vars:
#             raise NameError(f'Cannot redeclare "{name}". already exists in scope {self} with value {self.vars[name]}')
#         self.vars[name] = Scope._var(decltype, type, value)

#     def get(self, name: str, default: AST = None) -> AST:
#         pdb.set_trace()
#         # get a variable from this scope or any of its parents
#         for s in self:
#             if name in s.vars:
#                 return s.vars[name].value
#         if default is not None:
#             return default
#         raise NameError(f'{name} not found in scope {self}')

#     def bind(self, name: str, value: AST):
#         pdb.set_trace()  # dealing with local, alias, etc. other cases
#         # update an existing variable in this scope or  any of the parent scopes
#         for s in self:
#             if name in s.vars:
#                 var = s.vars[name]
#                 assert not var.const, f'cannot assign to const {name}'
#                 assert Type.is_instance(value.typeof(), var.type), f'cannot assign {
#                     value}:{value.typeof()} to {name}:{var.type}'
#                 var.value = value
#                 return

#         # TODO: consider what the declaration type default should be. Or maybe we just disallow binding to undeclared variables
#         # otherwise just create a new instance of the variable
#         self.vars[name] = Scope._var(DeclarationType.DEFAULT, untyped, value)

#     def __iter__(self):
#         """return an iterator that walks up each successive parent scope. Starts with self"""
#         s = self
#         while s is not None:
#             yield s
#             s = s.parent

#     def __repr__(self):
#         if self.parent is not None:
#             return f'Scope({self.vars}, {repr(self.parent)})'
#         return f'Scope({self.vars})'

#     def copy(self):
#         s = Scope(self.parent)
#         s.vars = self.vars.copy()
#         return s

#     @staticmethod
#     def default():
#         """return a scope with the standard library (of builtins) included"""
#         root = Scope()

#         raise NotImplementedError('default scope is not implemented yet.')

#         # def pyprint(scope: Scope):
#         #     print(scope.get('text').to_string(scope).val, end='')
#         #     return void
#         # pyprint_ast = Function(
#         #     [Declare(DeclarationType.DEFAULT, 'text', Type('string'))],
#         #     [],
#         #     PyAction(pyprint, Type('void')),
#         #     Scope.empty()
#         # )
#         # root.declare(DeclarationType.LOCAL_CONST, 'print', pyprint_ast.typeof(root), pyprint_ast)

#         # def pyprintl(scope: Scope):
#         #     print(scope.get('text').to_string(scope).val)
#         #     return void
#         # pyprintl_ast = Function(
#         #     [Declare(DeclarationType.DEFAULT, 'text', Type('string'))],
#         #     [],
#         #     PyAction(pyprintl, Type('void')),
#         #     Scope.empty()
#         # )
#         # root.declare(DeclarationType.LOCAL_CONST, 'printl', pyprintl_ast.typeof(root), pyprintl_ast)

#         # def pyreadl(scope: Scope):
#         #     return String(input())
#         # pyreadl_ast = Function([], [], PyAction(pyreadl, Type('string')), Scope.empty())
#         # root.declare(DeclarationType.LOCAL_CONST, 'readl', pyreadl_ast.typeof(root), pyreadl_ast)

#         # # TODO: eventually add more builtins

#         # return root



def top_level_evaluate(ast:AST) -> AST|None:
    pdb.set_trace()
    scope = Scope.default()
    return evaluate(ast, scope)

def evaluate(ast:AST, scope:Scope) -> AST|None:
    pdb.set_trace()
