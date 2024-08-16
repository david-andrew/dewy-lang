from .syntax import (
    AST,
    Call,
    Group,
    PrototypeIdentifier, Identifier
)

"""after the main parsing, post parse to handle any remaining prototype asts within the main ast"""
import pdb


def post_parse(ast: AST) -> AST:

    ast = convert_prototype_identifiers(ast)

    # at the end of the post parse process
    if not ast.is_settled():
        raise ValueError(f'INTERNAL ERROR: Parse was incomplete. AST still has prototypes\n{ast!r}')

    return ast

#TODO: this is pretty inefficient memory-wise. more ideal would be in place conversions
def convert_prototype_identifiers(ast: AST) -> AST:
    match ast:
        case Call(f=PrototypeIdentifier(name=name), args=args):
            return Call(Identifier(name=name), args)
        case Group(items=items):
            return Group([convert_prototype_identifiers(i) for i in items])
        case PrototypeIdentifier(name=name):
            return Call(Identifier(name=name))
        case _:
            raise NotImplementedError(f'conversion not handled for {type(ast)}')
    for i in ast:
        print(repr(i))

    pdb.set_trace()

    return ast
