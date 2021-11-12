#quick and dirty attempt to implement a scannerless GLL parser, which will inform developing the C implementation

from dataclasses import dataclass
from typing import List, Tuple, Dict, Set, Optional, Union

import pdb

Terminal = str

@dataclass
class NonTerminal:
    name: str

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

eps = 'ϵ'

@dataclass
class Sentence:
    symbols: List[Terminal | NonTerminal]

    #make slicing a sentence return a new sentence
    def __getitem__(self, index):
        return Sentence(self.symbols[index])

    def __str__(self):
        return ' '.join(str(x) for x in self.symbols)

    def __repr__(self):
        return str(self)

    def __len__(self):
        return len(self.symbols)


@dataclass
class Rule:
    head: NonTerminal
    body: List[Sentence]

    def __str__(self):
        return f'{self.head} ::= {" | ".join([str(b) for b in self.body])}'

    def __repr__(self):
        return str(self)

    def __getitem__(self, index):
        return self.body[index]


@dataclass
class Item:
    body: Sentence
    dot: int

    #print the item with the unicode dot in the correct position in the sentence
    def __str__(self):
        return str(self.body[:self.dot]) + '•' + str(self.body[self.dot:])

    def __repr__(self):
        return str(self)

    #function for progressing the dot in the item
    def advance(self):
        if (len(self.body) <= self.dot):
            raise Exception(f'Cannot advance item ({self}), already at max position')
        self.dot += 1


if __name__ == '__main__':
    #create a simple example grammar
    #A ::= aAb | aAc | a

    #create a nonterminal for A
    A = NonTerminal('A')
    
    #create sentences for A
    aAb = Sentence(['a', A, 'b'])
    aAc = Sentence(['a', A, 'c'])
    a = Sentence(['a'])

    #create a rule for A
    rule = Rule(A, [aAb, aAc, a])

    #create the first items for each rule in A
    items0 = [Item(b, 0) for b in rule.body]

    pdb.set_trace()