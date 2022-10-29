#implementation of the functional GLL parsing process from https://pure.royalholloway.ac.uk/portal/files/35434658/Accepted_Manuscript.pdf
#TODO: maybe look into the parsing combinators that they also discuss in the paper-->future work

#TODO: replace tau:str with tau:Sequence[T] where T could be strings, or any other token type

from abc import ABC
from dataclasses import dataclass

import pdb

#TODO: quality of life EBNF/notation for specifying grammar rules. probably put in a different file
# class MAST(ABC): ... #perhaps this should just be grammar? or something
# class EBNF(ABC): ... #this is the higher level grammar with extra notation


class Symbol(ABC): ...

@dataclass(slots=True, frozen=True, eq=True)
class Terminal(Symbol):
    t: str
    def __str__(self): return self.t

@dataclass(slots=True, frozen=True, eq=True)
class NonTerminal(Symbol):
    X: str
    def __str__(self): return self.X

@dataclass(slots=True, frozen=True, eq=True)
class Sentence:
    symbols: tuple[Symbol, ...] = ()
    def __str__(self): return " ".join(map(str, self.symbols)) if len(self.symbols) > 0 else "ϵ"
    def __len__(self): return len(self.symbols)
    def __getitem__(self, i: int|slice):
        if isinstance(i, slice): return Sentence(self.symbols[i])
        return self.symbols[i]

class Grammar:
    def __init__(self, rules:dict[NonTerminal, list[Sentence]]=None, start:NonTerminal=None):
        self.rules = rules if rules else {}
        self.start = start

    def add_rule(self, X:NonTerminal, sentence:Sentence):
        if X not in self.rules:
            self.rules[X] = []
        self.rules[X].append(sentence)

    def set_start(self, X:NonTerminal):
        self.start = X

    def __repr__(self):
        return f'Grammar(start={self.start}, rules={self.rules})'

    def __str__(self):
        lines = []
        for X in self.rules:
            lines.append(f'{X} -> {" | ".join(map(str, self.rules[X]))}')

        return '\n'.join(lines)


@dataclass(slots=True, frozen=True, eq=True)
class Slot:
    X: NonTerminal
    rule: Sentence
    i: int
    def __str__(self): return f'{self.X} ::= {self.alpha}•{self.beta}'
    def __repr__(self): return f'Slot(X={self.X}, rule={self.rule}, i={self.i})'
    @property
    def alpha(self) -> Sentence: return self.rule[:self.i]
    @property 
    def beta(self) -> Sentence: return self.rule[self.i:]
    @property
    def betap(self) -> Sentence: return self.rule[self.i+1:]
    @property
    def s(self) -> Symbol: return self.rule[self.i]
    def next(self) -> 'Slot': 
        assert self.i < len(self.rule), f'Cannot get next slot for {self}. Slot is already at end of rule.'
        return Slot(self.X, self.rule, self.i+1) 
    

Commencement = tuple[NonTerminal, int]      #(X:NonTerminal, l:int)
Continuation = tuple[Slot, int]             #(g:Slot, l:int)
Descriptor = tuple[Slot, int, int]          #(g:Slot, l:int, k:int)
BSR = tuple[Slot, int, int, int]            #(g:Slot, l:int, k:int, r:int)


"""
Definitions:
  W:list[Descriptor]                        - worklist of descriptors. paper uses 𝓡, but replaced with W to avoid confusion with R for the set of right extents. TODO: replace with unicode R that doesn't decompose to U+0052
  R:set[int]                                - set of right extents
  U:set[Descriptor]                         - set that stores all the descriptors that have been added to the worklist previously. ensures no descriptor is added to worklist twice
  P:set[tuple[Commencement, int]]           - set of relations that records for all nonterminals the left and right extents that have been discovered so far
  G:set[tuple[Commencement, Continuation]]  - set of relations between commencements and continuations
  Y:set[BSR]                                - set of all BSRs that have been discovered so far. Records the parse forest for the sentence
"""


def fungll(Gamma:Grammar, tau:str, X:NonTerminal): 
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



if __name__ == '__main__':

    # test with example from paper: E ::= E E E | "1" | eps
    E = NonTerminal('E')
    G = Grammar()
    G.add_rule(E, Sentence((E,E,E)))
    G.add_rule(E, Sentence((Terminal('1'),)))
    G.add_rule(E, Sentence())

    parser = complete_parser_for(G, E)
    print(G)
    print('1')
    print(parser('1'))


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
    print(G)
    print('bb')
    print(parser('bb'))


    #simple arithmetic grammar
    #E ::= E + E | E * E | (E) | 1
    E = NonTerminal('E')
    G = Grammar()
    G.add_rule(E, Sentence((E, Terminal('+'), E)))
    G.add_rule(E, Sentence((E, Terminal('*'), E)))
    G.add_rule(E, Sentence((Terminal('('), E, Terminal(')'))))
    G.add_rule(E, Sentence((Terminal('1'),)))

    parser = complete_parser_for(G, E)
    print(G)
    print('1+1')
    print(parser('1+1'))




