from abc import ABC
from dataclasses import dataclass


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
    def base_str(self): return " ".join(map(str, self.symbols))
    def __str__(self): return self.base_str() if len(self.symbols) > 0 else "ϵ"
    def __len__(self): return len(self.symbols)
    def __getitem__(self, i: int|slice):
        if isinstance(i, slice): return Sentence(self.symbols[i])
        return self.symbols[i]

class Grammar:
    def __init__(self, rules:dict[NonTerminal, list[Sentence]]=None, start:NonTerminal=None):
        self.rules = rules if rules else {}

    def add_rule(self, X:NonTerminal, sentence:Sentence):
        if X not in self.rules:
            self.rules[X] = []
        self.rules[X].append(sentence)

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
    def __str__(self): return f'{self.X} ::= {self.alpha.base_str()}•{self.beta.base_str()}'
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
    