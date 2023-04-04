from grammar import Slot, Grammar, Sentence, NonTerminal, Terminal, Symbol

import pdb



############################### Binary Subtree Representation ###############################

BSR = tuple[Slot, int, int, int]            #(g:Slot, l:int, k:int, r:int)


def find_roots(start:NonTerminal, Y:set[BSR], length:int) -> set[BSR]:
    """Find all BSRs in Y that are roots of the parse tree
    
    Args:
        start (NonTerminal): The start symbol of the grammar
        Y (set[BSR]): The BSR set
        length (int): The length of the input string

    Returns:
        set[BSR]: The set of BSRs that are roots of the parse tree
    """

    result = set()
    for y in Y:
        g, l, k, r = y
        if g.X == start and l == 0 and r == length and len(g.beta) == 0:
            result.add(y)

    return result

#TODO: broken
def find_children(Y: set[BSR], y0: BSR) -> list[BSR]:
        g0, l0, k0, r0 = y0
        lefts, rights = [], []
        for y in Y:
            g, l, k, r = y
            if l == l0 and r == k0: #TODO: other checks...
                lefts.append(y)
            elif l == k0 and r == r0: #TODO: other checks...
                rights.append(y)

        if r0 - k0 == 1:
            #tau[k0:r0]
            assert isinstance(g0.alpha[-1], Terminal)
            rights.append(g0.alpha[-1])
        
        pdb.set_trace()
        # return children


def build_tree(Y: set[BSR], node: BSR) -> list[tuple[BSR, list]]:
    children = find_children(Y, node)
    tree = []
    for child in children:
        subtree = build_tree(Y, child)
        tree.append((child, subtree))
    return tree

def bsr_tree_str(X:NonTerminal, Y:set[BSR], length:int) -> str:
    roots = find_roots(X, Y, length)
    if len(roots) == 0:
        return "No roots found in the BSR set."

    trees = [build_tree(Y, root) for root in roots]
    pdb.set_trace()
    # return tree_to_string(tree)






############################### Shared Packed Parse Forest ################################

class SPPF:
    def __init__(self):
        self.nodes: set[SPPFNode] = set()
        self.edges: dict[SPPFNode, list[SPPFNode]] = {}
    # add node labelled (S, 0, n)
    # add node labelled (X ::= α·δ, k)
    # check if there are any extendable leaf nodes
    # (μ, i, j) is an extendable leaf node
    # node labelled (Ω, i, j)
    # add an edge from y to the node (Ω, i, j) 

class SPPFNode:...

def extractSPPF(*args, **kwargs):
    raise NotImplementedError

def sppf_tree_str(*args, **kwargs):
    raise NotImplementedError

"""
extractSPPF (Υ, Γ)
{
    G := empty graph
    let S be the start symbol of Γ
    let n be the extent of Υ
    if Υ has an element of the form (S ::= α, 0, k, n)
    {
        create a node labelled (S, 0, n) in G
        while G has an extendable leaf node
        {
            let w = (μ, i, j) be an extendable leaf node of G
            if (μ is a nonterminal X in Γ)
            {
                for each (X ::= γ, i, k, j) ∈ Υ 
                { 
                    mkPN(X ::= γ·, i, k, j, G) 
                } 
            }
            else
            {
                suppose μ is X ::= α·δ
                if (|α| = 1)
                {
                    mkPN(X ::= α·δ, i, i, j, G)
                }
                else for each (α, i, k, j) ∈ Υ 
                { 
                    mkPN(X ::= α·δ, i, k, j, G) 
                } 
            } 
        } 
    }
    return G
}

mkPN(X ::= α·δ, i, k, j, G)
{
    make a node y in G labelled (X ::= α·δ, k)
    if (α = ϵ)
    {
        mkN(ϵ, i, i, y, G)
    }
    if (α = βx, where |x| = 1)
    {
        mkN(x, k, j, y, G)
        if (|β| = 1)
        {
            mkN(β, i, k, y, G)
        }
        if (|β| > 1)
        {
            mkN(X ::= β·xδ, i, k, y, G) 
        }
    }
}

mkN (Ω, i, j, y, G)
{
    if there is not a node labelled (Ω, i, j) in G make one
    add an edge from y to the node (Ω, i, j) 
}
"""
