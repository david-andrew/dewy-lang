#implementation of the functional GLL parsing process from https://pure.royalholloway.ac.uk/portal/files/35434658/Accepted_Manuscript.pdf
#TODO: maybe look into the parsing combinators that they also discuss in the paper-->future work

#TODO: replace tau:str with tau:Sequence[T] where T could be strings, or any other token type

from abc import ABC
from dataclasses import dataclass

import pdb


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
    symbols: list[Symbol]
    def __str__(self): return " ".join(map(str, self.symbols))
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

@dataclass(slots=True, frozen=True, eq=True)
class Commencement:
    X: NonTerminal
    l: int
    def __str__(self): return f'〈{self.X}, {self.l}〉'
    def __repr__(self): return f'Commencement(X={self.X}, l={self.l})'

@dataclass(slots=True, frozen=True, eq=True)
class Continuation:
    g: Slot
    l: int
    def __str__(self): return f'〈{self.g}, {self.l}〉'
    def __repr__(self): return f'Continuation(g={self.g}, l={self.l})'

@dataclass(slots=True, frozen=True, eq=True)
class Descriptor:
    slot: Slot
    l: int; k: int
    def __str__(self): return f'〈{self.g}, {self.l}, {self.k}〉'
    def __repr__(self): return f'Descriptor(slot={self.slot}, l={self.l}, k={self.k})'
    
@dataclass(slots=True, frozen=True, eq=True)
class BSR:
    g: Slot
    l: int; k: int; r: int
    def __str__(self): return f'〈{self.g}, {self.l}, {self.k}, {self.r}〉'
    def __repr__(self): return f'BSR(slot={self.g}, l={self.l}, k={self.k}, r={self.r})'



"""
Definitions:
  R:list[Descriptor]                        - worklist of descriptors
  U:set[Descriptor]                         - set that stores all the descriptors that have been added to the worklist previously. ensures no descriptor is added to worklist twice
  P:set[tuple[Commencement, int]]           - set of relations that records for all nonterminals the left and right extents that have been discovered so far
  G:set[tuple[Commencement, Continuation]]  - set of relations between commencements and continuations
  Y:set[BSR]                                - set of all BSRs that have been discovered so far. Records the parse forest for the sentence
"""


def fungll(Gamma:Grammar, tau:str, X:NonTerminal): 
    return loop(Gamma, tau, descend(Gamma,X, 0), set(), set(), set(), set())


def descend(Gamma:Grammar, X:NonTerminal, l:int) -> list[Descriptor]:
    return [Descriptor(Slot(X, rule, 0), l, l) for rule in Gamma.rules[X]]


def loop(Gamma:Grammar, tau:str, R:list[Descriptor], U:set[Descriptor], G:set[tuple[Commencement,Continuation]], P:set[tuple[Commencement, int]], Y:set[BSR]) -> tuple[set[Descriptor], set[BSR]]: 
    if not R: return U, Y
    d = R.pop()
    (Rp,Yp), Gp, Pp = process(Gamma, tau, d, G, P)
    Rpp = [r for r in R + Rp  if r not in U] #and r != d (already popped)
    return loop(Gamma, tau, Rpp, U|{d}, G|Gp, P|Pp, Y|Yp)


def process(Gamma:Grammar, tau:str, d:Descriptor, G:set[tuple[Commencement,Continuation]], P:set[tuple[Commencement, int]]): 
    ...


def process_eps(d:Descriptor, G:set[tuple[Commencement, Continuation]], P:set[tuple[Commencement, int]]): 
    ...


def process_sym(Gamma:Grammar, tau:str, d:Descriptor, G:set[tuple[Commencement,Continuation]], P:set[tuple[Commencement, int]]):
    ...


def match(tau:str, d:Descriptor):
    ...


def skip(k:int, c:Continuation, R:list[Descriptor]):
    ...


def ascend(k:int, K:set[Continuation], r:int) -> tuple[list[Descriptor], set[BSR]]:
    ...


def nmatch(k:int, K:set[Continuation], R:list[Descriptor]):
    ...


def complete_parser_for(Gamma:Grammar, X:NonTerminal):
    def parse(tau:str): ...
    return parse





# #DEBUG make some test sentences and print
# G = Grammar()
# G.add_rule(NonTerminal("S"), Sentence([NonTerminal("A"), Terminal("a")]))
# G.add_rule(NonTerminal("S"), Sentence([NonTerminal("B"), Terminal("b")]))
# G.add_rule(NonTerminal("A"), Sentence([Terminal("a")]))
# G.add_rule(NonTerminal("B"), Sentence([Terminal("b")]))
# G.add_rule(NonTerminal("B"), Sentence([Terminal("b"), Terminal("b")]))
# print(G)
# pdb.set_trace()


#TODO: quality of life EBNF/notation for specifying grammar rules
# class MAST(ABC): ... #perhaps this should just be grammar? or something
# class EBNF(ABC): ... #this is the higher level grammar with extra notation
