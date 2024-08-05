from syntax import AST

"""after the main parsing, post parse to handle any remaining prototype asts within the main ast"""
import pdb


def post_parse(ast: AST) -> AST:
    pdb.set_trace()
    # at the end of the post parse process
    assert ast.settled(), f'AST not settled: {ast}'
