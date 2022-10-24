#implementation of the functional GLL parsing process from https://pure.royalholloway.ac.uk/portal/files/35434658/Accepted_Manuscript.pdf
#TODO: maybe look into the parsing combinators that they also discuss in the paper-->future work

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





#DEBUG make some test sentences and print
G = Grammar()
G.add_rule(NonTerminal("S"), Sentence([NonTerminal("A"), Terminal("a")]))
G.add_rule(NonTerminal("S"), Sentence([NonTerminal("B"), Terminal("b")]))
G.add_rule(NonTerminal("A"), Sentence([Terminal("a")]))
G.add_rule(NonTerminal("B"), Sentence([Terminal("b")]))
G.add_rule(NonTerminal("B"), Sentence([Terminal("b"), Terminal("b")]))
print(G)
pdb.set_trace()



class Slot: ...
class BSR: ...

class MAST(ABC): ... #perhaps this should just be grammar? or something
class EBNF(ABC): ... #this is the higher level grammar with extra notation




def fungll(Gamma, tau:str, X): ...
def descend(Gamma, X, l): ...
def loop(Gamma, tau:str, R, U, G, P, Y:set[BSR]): ...
def process(Gamma, tau:str, slot, G, P): ...
def process_eps(slot, G, P): ...
def process_sym(Gamma, tau:str, slot, G, P): ...
def match(tstr, slot): ... #TBD if tstr is just tau:str
def skip(k, c, R): ...
def ascend(k, K, r): ...
def nmatch(k, K, R): ...

def complete_parser_for(Gamma, X):
    def inner(tau:str): ...
    return inner