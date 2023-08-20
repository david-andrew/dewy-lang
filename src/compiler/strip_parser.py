"""
a practical parser while we figure out how to do FUN-GLL/BSR parsing
"""




#0. convert input str to a list of tokens (or could be handed an existing token string). actually though, these will probably be nodes in the AST
#1. functions to remove comments and insert <jux> between adjacent tokens
#
# ...
# everything is either a sequence or an operation. strip outside (lowest precedence) of tokens until we get to the middle


from typing import Callable, Any
from enum import Enum, auto


import pdb

class node_type(Enum):
    char = auto()
    jux = auto()
    #TODO: ...
    

class Node:
    def __init__(self, type:node_type, body:str|list['Node']|None=None):
        self.type = type
        self.body = body

    def __repr__(self):
        # return f'Node({self.type}, {self.body})'
        return str(self)
    
    def __str__(self):
        if self.body is None:
            return f'<{self.type.name}>'
        
        #if type is char, escape it
        if self.type == node_type.char:
            return f'<{self.type.name} {self.body!r}>'
        return f'<{self.type.name} {self.body}>'



def str_to_nodes(s:str) -> list[Node]:
    return [Node(node_type.char, c) for c in s]


def pattern_match(targets:list[tuple[node_type, str|list[Node]]], nodes:list[Node]) -> bool:
    """
    check if the first len(targets) nodes match the targets
    
    targets is a list of (type, body) tuples
    """
    if len(targets) > len(nodes):
        return False
    for (ttype, tbody), node in zip(targets, nodes):
        if ttype != node.type:
            return False
        if tbody is not None and tbody != node.body:
            return False
    return True


def interleave(A:list, v:Any) -> list:
    """
    interleave v between every element of A
    """
    out = []
    for i in range(len(A)-1):
        out.append(A[i])
        out.append(v)
    if len(A) > 0:
        out.append(A[-1])
    return out
        
                
def find_next_comment_or_whitespace(nodes:list[Node]) -> tuple[int, int]|None:
    """
    find the next block or line comment, or whitespace
    return its start and end index, or None if no comments or whitespace detected
    
    line comments start with a // and end with a newline
    block comments start with a /{ and end with a }/. they can be nested
    """
    for i in range(len(nodes)-1):

        ##CANNOT STRIP WHITESPACE. there could be strings with whitespace in them...
        # #whitespace
        # if pattern_match([(node_type.char, ' ')], nodes[i:i+1]):
        #     return i, i+1
        # if pattern_match([(node_type.char, '\t')], nodes[i:i+1]):
        #     return i, i+1
        # if pattern_match([(node_type.char, '\n')], nodes[i:i+1]):
        #     return i, i+1
        

        #line comment
        if pattern_match([(node_type.char, '/'), (node_type.char, '/')], nodes[i:i+2]):
            for j in range(i+2, len(nodes)):
                if pattern_match([(node_type.char, '\n')], nodes[j:j+1]):
                    return i, j+1
        
        #block comment
        if pattern_match([(node_type.char, '/'), (node_type.char, '{')], nodes[i:i+2]):
            depth = 1
            for j in range(i+2, len(nodes)-1):
                if pattern_match([(node_type.char, '/'), (node_type.char, '{')], nodes[j:j+2]):
                    depth += 1
                elif pattern_match([(node_type.char, '}'), (node_type.char, '/')], nodes[j:j+2]):
                    depth -= 1
                    if depth == 0:
                        return i, j+2


def strip_nodes(nodes:list[Node], find_next:Callable[[list[Node]], tuple[int, int]|None], add_jux:bool=False) -> list[Node]:
    """
    strip comments from input list, and optionally insert <jux> between adjacent tokens
    """
    out = []
    i = 0
    while i < len(nodes):
        res = find_next(nodes[i:])
        if res is None:
            for node in nodes[i:-1]:
                out.append(node)
                if add_jux:
                    out.append(Node(node_type.jux))
            out.append(nodes[-1])
            break

        start, end = res        
        out.extend(interleave(nodes[i:i+start], Node(node_type.jux)) if add_jux else nodes[i:i+start])
        i += end


    return out






def test():
    """simple test dewy program"""

    prog = """
// proof that dewy is turing complete
// rule 110 would grow the vector from the front, so instead we reverse everything for efficiency
// for now use parenthesis where precedence filter needed. eventually should be able to remove with precedence filter

/{ this is a block comment with a /{nested}/ comment inside }/

progress = world:vector<bit> => {
    update:bit = 0
    loop i in 0..world.length
    {
        if i >? 0 world[i-1] = update //TODO: #notfirst or #iters[1..]
        update = (0b01110110 << (((world[i-1] ?? 0) << 2) or ((world[i] ?? 0) << 1) or (world[i+1] ?? 0)))
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

    nodes = str_to_nodes(prog)
    nodes = strip_nodes(nodes, find_next_comment_or_whitespace, add_jux=True)
    pdb.set_trace()

    for node in nodes:
        print(node.type, node.body)

if __name__ == '__main__':
    test()