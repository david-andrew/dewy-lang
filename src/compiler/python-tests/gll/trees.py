from grammar import Slot, Grammar, Sentence, NonTerminal, Terminal, Symbol

BSR = tuple[Slot, int, int, int]            #(g:Slot, l:int, k:int, r:int)



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


from collections import defaultdict

class SPPFNode:
    def __init__(self, label: Symbol|None, i:int, j:int):
        self.label = label
        self.i = i
        self.j = j
        self.children = []

    def __eq__(self, other):
        if not isinstance(other, SPPFNode):
            return False
        return self.label == other.label and self.i == other.i and self.j == other.j

    def __hash__(self):
        return hash((self.label, self.i, self.j))

    def __repr__(self):
        return f'SPPFNode({self.label}, {self.i}, {self.j})'

    def add_child(self, child):
        self.children.append(child)

    def is_terminal(self) -> bool:
        return isinstance(self.label, Terminal)

    def is_ambiguous(self) -> bool:
        return len(self.children) > 1

class SPPF:
    def __init__(self):
        self.nodes = defaultdict(set)

    def get_node(self, label:Symbol|None, i:int, j:int):
        node = SPPFNode(label, i, j)
        if node not in self.nodes[(label, i, j)]:
            self.nodes[(label, i, j)].add(node)
        else:
            node = next(filter(lambda n: n == node, self.nodes[(label, i, j)]))
        return node

    def add_edge(self, parent:SPPFNode, child:SPPFNode):
        parent.add_child(child)

    def __repr__(self):
        result = "SPPF(\n"
        for nodes_set in self.nodes.values():
            for node in nodes_set:
                result += f"  {node}: {[str(child) for child in node.children]}\n"
        result += ")"
        return result
    
    # def __str__(self) -> str:
    #     return self._str_helper(self.get_node(self.G.start, 0, self.max_j))

    # def _str_helper(self, node: SPPFNode|None, indent: str = "") -> str:
    #     output = []

    #     if node is None:
    #         return ""

    #     children = self.get_children(node)
    #     is_ambiguous = len(children) > 1

    #     label = f"!{node.X}" if is_ambiguous else str(node.X)
    #     output.append(f"{indent}{label}:{node.i}-{node.j}")

    #     indent += "│   " if is_ambiguous else "    "

    #     for idx, child_list in enumerate(children):
    #         if idx > 0:
    #             output.append(f"{indent[:-4]}├── !alternate")
    #         for i, child in enumerate(child_list):
    #             if i < len(child_list) - 1:
    #                 output.append(f"{indent}├── " + self._str_helper(child, indent + "│   "))
    #             else:
    #                 output.append(f"{indent}└── " + self._str_helper(child, indent + "    "))

    #     return "\n".join(output)


    # def print_sppf(sppf: 'SPPF', node: SPPFNode|None = None, indent: str = "") -> None:
    #     if node is None:
    #         node = sppf.get_node(sppf.start, 0, sppf.max_j)

    #     children = sppf.get_children(node)
    #     is_ambiguous = len(children) > 1

    #     label = f"!{node.X}" if is_ambiguous else str(node.X)
    #     print(f"{indent}{label}:{node.i}-{node.j}")

    #     indent += "│   " if is_ambiguous else "    "

    #     for idx, child_list in enumerate(children):
    #         if idx > 0:
    #             print(f"{indent[:-4]}├── !alternate")
    #         for i, child in enumerate(child_list):
    #             if i < len(child_list) - 1:
    #                 print(f"{indent}├── ", end="")
    #                 print_sppf(sppf, child, indent + "│   ")
    #             else:
    #                 print(f"{indent}└── ", end="")
    #                 print_sppf(sppf, child, indent + "    ")




def extractSPPF(Y: set[BSR], G: Grammar) -> SPPF:
    sppf = SPPF()
    n = max(r for _, _, _, r in Y)

    if any(slot.X == G.start and slot.i == len(slot.rule) and r == n for slot, _, _, r in Y):
        sppf.get_node(G.start, 0, n)
        extendable_nodes = [sppf.get_node(G.start, 0, n)]
        while extendable_nodes:
            w = extendable_nodes.pop()
            X = w.label
            if isinstance(X, NonTerminal):
                for slot, i, k, j in Y:
                    if slot.X == X and w.i == i and w.j == j:
                        mkPN(slot, i, k, j, sppf)
    else:
        print("No matching start symbol found in Y")

    return sppf

def mkPN(slot: Slot, i: int, k: int, j: int, sppf: SPPF) -> None:
    y = sppf.get_node(slot, k, j)

    if slot.i < len(slot.rule):  # Check if i is within bounds
        mkN(slot.s, i, k, y, sppf)

        if len(slot.alpha) == 1:
            mkN(slot.alpha, i, k, y, sppf)
        elif len(slot.alpha) > 1:
            try:
                next_slot = slot.next()
                mkN(next_slot, i, k, y, sppf)
            except AssertionError:
                print(f"Cannot get next slot for {slot}. Slot is already at the end of the rule.")

def mkN(omega: Symbol, i: int, j: int, y: SPPFNode, sppf: SPPF) -> None:
    node = sppf.get_node(omega, i, j)
    sppf.add_edge(y, node)







def sppf_tree_str(sppf: SPPF, grammar: Grammar, input_str: str) -> str:
    def _str_helper(node: SPPFNode|None, indent: str = "") -> str:
        if node is None:
            return ""

        if node.is_terminal():
            label = repr(node.label)
        else:
            label = str(node.label)

        if node.is_ambiguous():
            label += " [ambiguous]"

        result = f"{indent}{label}\n"


        for i, child in enumerate(node.children):
            if i < len(node.children) - 1:
                child_indent = indent + "├── "
                next_indent = indent + "│   "
            else:
                child_indent = indent + "└── "
                next_indent = indent + "    "
            result += _str_helper(child, child_indent + next_indent)

        return result

    start_node = sppf.get_node(grammar.start, 0, len(input_str))
    tree_str = _str_helper(start_node)
    return tree_str