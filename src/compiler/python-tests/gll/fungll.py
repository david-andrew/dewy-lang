from grammar import NonTerminal, Terminal, Sentence, Slot, Grammar
from trees import BSR, extractSPPF



#implementation of the functional GLL parsing process from https://pure.royalholloway.ac.uk/portal/files/35434658/Accepted_Manuscript.pdf
#TODO: maybe look into the parsing combinators that they also discuss in the paper-->future work

#TODO: replace tau:str with tau:Sequence[T] where T could be strings, or any other token type


import pdb

#TODO: quality of life EBNF/notation for specifying grammar rules. probably put in a different file
# class MAST(ABC): ... #perhaps this should just be grammar? or something
# class EBNF(ABC): ... #this is the higher level grammar with extra notation


Commencement = tuple[NonTerminal, int]      #(X:NonTerminal, l:int)
Continuation = tuple[Slot, int]             #(g:Slot, l:int)
Descriptor = tuple[Slot, int, int]          #(g:Slot, l:int, k:int)


"""
Definitions:
  W:list[Descriptor]                        - worklist of descriptors. paper uses 𝓡, but replaced with W to avoid confusion with R for the set of right extents. TODO: replace with unicode R that doesn't decompose to U+0052
  R:set[int]                                - set of right extents
  U:set[Descriptor]                         - set that stores all the descriptors that have been added to the worklist previously. ensures no descriptor is added to worklist twice
  P:set[tuple[Commencement, int]]           - set of relations that records for all nonterminals the left and right extents that have been discovered so far
  G:set[tuple[Commencement, Continuation]]  - set of relations between commencements and continuations
  Y:set[BSR]                                - set of all BSRs that have been discovered so far. Records the parse forest for the sentence
"""


def fungll(Gamma:Grammar, tau:str, X:NonTerminal) -> tuple[set[Descriptor], set[BSR]]: 
    return loop(Gamma, tau, descend(Gamma, X, 0), set(), set(), set(), set())


def descend(Gamma:Grammar, X:NonTerminal, l:int) -> list[Descriptor]:
    return [(Slot(X, rule, 0), l, l) for rule in Gamma.rules[X]]


def loop(Gamma:Grammar, tau:str, W:list[Descriptor], U:set[Descriptor], G:set[tuple[Commencement,Continuation]], P:set[tuple[Commencement, int]], Y:set[BSR]) -> tuple[set[Descriptor], set[BSR]]: 
    if not W: return U, Y
    d = W[0]
    (Wp,Yp), Gp, Pp = process(Gamma, tau, d, G, P)
    Wpp = [r for r in W + Wp  if r not in U|{d}]
    return loop(Gamma, tau, Wpp, U|{d}, G|Gp, P|Pp, Y|Yp)


def process(Gamma:Grammar, tau:str, d:Descriptor, G:set[tuple[Commencement,Continuation]], P:set[tuple[Commencement, int]]) -> tuple[tuple[list[Descriptor], set[BSR]], set[tuple[Commencement, Continuation]], set[tuple[Commencement, int]]]:
    g, l, k = d
    if len(g.beta) == 0:
        return process_eps(d, G, P)

    return process_sym(Gamma, tau, d, G, P)


def process_eps(d:Descriptor, G:set[tuple[Commencement, Continuation]], P:set[tuple[Commencement, int]]) -> tuple[tuple[list[Descriptor], set[BSR]], set[tuple[Commencement, Continuation]], set[tuple[Commencement, int]]]: 
    g, l, k = d
    K:set[Continuation] = {c for (_,c) in G}
    W, Y = ascend(l, K, k)
    Yp = {(g, l, l, l)}
    return (W, Y|Yp), set(), {((g.X, l), k)}


def process_sym(Gamma:Grammar, tau:str, d:Descriptor, G:set[tuple[Commencement,Continuation]], P:set[tuple[Commencement, int]]) -> tuple[tuple[list[Descriptor], set[BSR]], set[tuple[Commencement, Continuation]], set[tuple[Commencement, int]]]:
    g, l, k = d
    s = g.s
    if isinstance(s, Terminal):
        return (match(tau, d), set(), set())
    
    assert isinstance(s, NonTerminal), f'Expected NonTerminal, got {s}'
    Gp = {((s,k),(g.next(), l))}
    R = {r for ((_s,_k),r) in P if _k==k and _s==s}
    
    if len(R) == 0:
        return ((descend(Gamma, s, k),set()), Gp, set())
    
    return (skip(k, (g.next(), l), R), Gp, set())


def match(tau:str, d:Descriptor) -> tuple[list[Descriptor], set[BSR]]:
    g, l, k = d
    assert isinstance(g.s, Terminal), f'Cannot match because {g.s} is not a terminal.'
    if k < len(tau) and tau[k] == g.s.t:
        new_g = g.next()
        return ([(new_g,l,k+1)], {(new_g,l,k,k+1)})
    else:
        return ([], set())


def skip(k:int, c:Continuation, R:set[int]) -> tuple[list[Descriptor], set[BSR]]:
    return nmatch(k, {c}, R)


def ascend(k:int, K:set[Continuation], r:int) -> tuple[list[Descriptor], set[BSR]]:
    return nmatch(k, K, {r})


def nmatch(k:int, K:set[Continuation], R:set[int]) -> tuple[list[Descriptor], set[BSR]]:
    W: list[Descriptor] = []
    Y: set[BSR] = set()
    for c in K:
        g, l = c
        for r in R:
            W.append((g, l, r))
            Y.add((g, l, k, r))
    return W, Y


def complete_parser_for(Gamma:Grammar, X:NonTerminal):
    def parse(tau:str):
        U, Y = fungll(Gamma, tau, X)
        return Y
    return parse



#tasks
# check if a parse was a success by finding the top level BSR node
# nice printing of BSR
# seq[T] instead of str for tau


def parse_str(Y:set[BSR]):
    s = [f'({g}, {l}, {k}, {r})\n' for g, l, k, r in Y] 
    return '{\n' + ''.join(s) + '}'

def parse_roots(X:NonTerminal, Y:set[BSR], tau:str) -> set[BSR]:
    result = set()
    for y in Y:
        g, l, k, r = y
        if g.X == X and l == 0 and r == len(tau) and len(g.beta) == 0:
            result.add(y)

    return result


if __name__ == '__main__':

    # super simple test grammar S ::= 'h' 'e' 'l' 'l' 'o'
    S = NonTerminal('S')
    G = Grammar()
    G.add_rule(S, Sentence((Terminal('h'), Terminal('e'), Terminal('l'), Terminal('l'), Terminal('o'))))

    parse = complete_parser_for(G, S)
    print('------------------------------------------------------------')
    print(G)
    input = 'hello'
    print(f'input: {input}')
    result = parse(input)
    print(parse_str(result))
    roots = parse_roots(S, result, input)
    print(f'roots: {parse_str(roots)}')
    sppf = extractSPPF(result, G)
    print(f'sppf: {sppf}')

    # pdb.set_trace()


    # test with example from the paper
    # Tuple ::= '(' As ')'
    # As ::= ϵ | a' More
    # More ::= ϵ | ',' 'a' More
    Tuple = NonTerminal('Tuple')
    As = NonTerminal('As')
    More = NonTerminal('More')
    G = Grammar()
    G.add_rule(Tuple, Sentence((Terminal('('), As, Terminal(')'))))
    G.add_rule(As, Sentence((Terminal('a'), More)))
    G.add_rule(As, Sentence())
    G.add_rule(More, Sentence((Terminal(','), Terminal('a'), More)))
    G.add_rule(More, Sentence())

    parse = complete_parser_for(G, Tuple)
    print('------------------------------------------------------------')
    print(G)
    input = '(a,a)'
    print(f'input: {input}')
    result = parse(input)
    print(parse_str(result))
    roots = parse_roots(Tuple, result, input)
    print(f'roots: {parse_str(roots)}')
    sppf = extractSPPF(result, G)
    print(f'sppf: {sppf}')



    # test with example from paper: E ::= E E E | "1" | eps
    E = NonTerminal('E')
    G = Grammar()
    G.add_rule(E, Sentence((E,E,E)))
    G.add_rule(E, Sentence((Terminal('1'),)))
    G.add_rule(E, Sentence())

    parser = complete_parser_for(G, E)
    print('------------------------------------------------------------')
    print(G)
    input = '1'
    print(f'input: {input}')
    result = parser(input)
    print(parse_str(result))
    roots = parse_roots(E, result, input)
    print(f'roots: {parse_str(roots)}')
    sppf = extractSPPF(result, G)
    print(f'sppf: {sppf}')


    # custom test example
    #S = 'a' | 'b' #B #S #S | ϵ;
    #B = ϵ;
    S = NonTerminal('S')
    B = NonTerminal('B')
    G = Grammar()
    G.add_rule(S, Sentence((Terminal('a'),)))
    G.add_rule(S, Sentence((Terminal('b'), B, S, S,)))
    G.add_rule(S, Sentence())
    G.add_rule(B, Sentence())

    parser = complete_parser_for(G, S)
    print('------------------------------------------------------------')
    print(G)
    input = 'bb'
    print(f'input: {input}')
    result = parser(input)
    print(parse_str(result))
    roots = parse_roots(S, result, input)
    print(f'roots: {parse_str(roots)}')
    sppf = extractSPPF(result, G)
    print(f'sppf: {sppf}')


    #simple arithmetic grammar
    #E ::= E + E | E * E | (E) | 1
    E = NonTerminal('E')
    G = Grammar()
    G.add_rule(E, Sentence((E, Terminal('+'), E)))
    G.add_rule(E, Sentence((E, Terminal('*'), E)))
    G.add_rule(E, Sentence((Terminal('('), E, Terminal(')'))))
    G.add_rule(E, Sentence((Terminal('1'),)))

    parser = complete_parser_for(G, E)
    print('------------------------------------------------------------')
    print(G)
    input = '1+1'
    print(f'input: {input}')
    result = parser(input)
    print(parse_str(result))
    roots = parse_roots(E, result, input)
    print(f'roots: {parse_str(roots)}')
    sppf = extractSPPF(result, G)
    print(f'sppf: {sppf}')



