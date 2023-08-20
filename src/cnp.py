
#quick and dirty attempt to implement a scannerless GLL parser, which will inform developing the C implementation

from dataclasses import dataclass
from typing import List, Mapping, Tuple, Dict, Set, Optional, Union
import sys
from io import StringIO

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
        s = self.symbols[index]
        return Sentence(s) if isinstance(s, List) else s

    def __str__(self):
        return ''.join(str(x) for x in self.symbols)

    def __repr__(self):
        return str(self)

    def __len__(self):
        return len(self.symbols)

    def __iter__(self):
        return iter(self.symbols)


@dataclass
class Rule:
    head: NonTerminal
    bodies: List[Sentence]

    def __str__(self):
        return f'{self.head} ::= {" | ".join([str(b) for b in self.bodies])}'

    def __repr__(self):
        return str(self)

    def __getitem__(self, index):
        return self.bodies[index]


@dataclass
class Item:
    body: Sentence
    dot: int

    def __getitem__(self, index):
        return self.body[index]

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
    
    #check if at the end of the item
    def at_end(self):
        return self.dot == len(self.body)

    #iterate over the item by advancing the dot until at the end (return a new item at each step)
    # def __iter__(self):
    #     return Slot(self.body, self.dot)

    # def __next__(self):
    #     if self.at_end():
    #         raise StopIteration
    #     self.advance()
    #     return self


@dataclass
class SubTerm:
    head: NonTerminal | None
    body: Sentence

    def __str__(self):
        return f'{self.head} ::= {self.body}' if self.head else str(self.body)

    def __repr__(self):
        return str(self)

@dataclass
class Slot:
    head: NonTerminal
    item: Item

    def __getitem__(self, index):
        return self.item[index]

    def __str__(self):
        return f'{self.head} ::= {self.item}'
    
    def __repr__(self):
        return str(self)


CRFNode = Tuple[NonTerminal | Slot, int]
class CRF:
    """a digraph whose nodes are labelled (L, j) where L is either a nonterminal or a slot"""
    def __init__(self):
        self.nodeMap: Mapping[CRFNode, List[CRFNode]] = {}

    def add_node(self, node: CRFNode):
        if node not in self.nodeMap:
            self.nodeMap[node] = []

    def add_edge(self, from_node: CRFNode, to_node: CRFNode):
        if from_node not in self.nodeMap:
            self.nodeMap[from_node] = []
        self.nodeMap[from_node].append(to_node)




def PrintCode(slot: Slot):
    #determine which type of slot
    
    #slot with empty body, `code(X ::= •)` prints: 
    #    Υ := Υ ∪ {(X ::= ϵ, cI , cI , cI )}
    
    #slot with dot after a terminal, `code(X ::= α a• β)` prints:
    #    bsrAdd(X ::= α a• β, cU, cI, cI + 1)
    #    goto L0

    #slot with dot after a nonterminal, `code(X ::= α Y• β)` prints:
    #    call(X ::= α Y• β, cU, cI)
    #    goto L0
    #X ::= α Y• β:

    if (len(slot.item.body) == 0):
        print(f'        Υ := Υ ∪ {{({slot.head} ::= {eps}, cI, cI, cI)}}')
    elif isinstance(slot.item[slot.item.dot - 1], Terminal):
        print(f'        bsrAdd({slot}, cU, cI, cI + 1)')
        print(f'        cI += 1')
    else:
        assert(isinstance(slot.item[slot.item.dot - 1], NonTerminal))
        print(f'        call({slot}, cU, cI)')
        print(f'        goto L0')
        print(f'    {slot.head} ::= {slot.item}:')


def printLabelBody(label: Slot):
    #copy the slot so we don't modify the original
    originalLabel = label
    label = Slot(label.head, Item(label.item.body, label.item.dot))
    if label.item.dot == 0 and len(label.item.body) == 0:
        print(f'        Υ := Υ ∪ {{({label.head} ::= {eps}, cI, cI, cI)}}')
    else:
        while not label.item.at_end() and isinstance(label.item[label.item.dot], Terminal):
            if label.item.dot != 0:
                print(f'        if not testSelect(I[cI], {label.head}, {label.item.body[label.item.dot:]}):')
                print(f'            goto L0')
            label.item.advance()
            print(f'        bsrAdd({label}, cU, cI, cI + 1)')
            print(f'        cI += 1')

        if not label.item.at_end():
            if label.item.dot != 0:
                print(f'        if not testSelect(I[cI], {label.head}, {label.item.body[label.item.dot:]}):')
                print(f'            goto L0')
            label.item.advance()
            print(f'        call({label}, cU, cI)')

    if originalLabel.item.at_end() or label.item.at_end() and isinstance(label.item[label.item.dot - 1], Terminal):
       print(f'        if I[cI] ∈ follow({label.head}):')
       print(f'            rtn({label.head}, cU, cI)')
    
    print(f'        goto L0')


#global sets
P: Set[Tuple[NonTerminal, int, int]] = set()
Y: Set[Tuple[SubTerm, int, int, int]] = set()
Descriptor = Tuple[Slot, int, int]
R: Set[Descriptor] = set()
U: Set[Descriptor] = set()
input_string = 'abaa'
m: int = len(input_string)
I: List[str | int] = [c for c in input_string] + [0]
cI: int = -1
cU: int = -1
crf: CRF = CRF()

#first/follow set. ϵ is represented by ''
first: Dict[NonTerminal, Set[Terminal]] = {}
follow: Dict[NonTerminal, Set[Terminal]] = {}

#get the list of labels to be used in the CNP algorithm
def getLabels(rules: List[Rule]):
    labels = []
    for rule in rules:
        head = rule.head
        for body in rule.bodies:
            slot = Slot(head, Item(body, 0))
            labels.append(Slot(head, Item(body, 0)))

            #iterate over the slot, and insert a label for slots where the dot is after a NonTerminal
            while not slot.item.at_end():
                slot.item.advance()
                if isinstance(slot.item[slot.item.dot - 1], NonTerminal):
                    labels.append(Slot(head, Item(body, slot.item.dot)))
    return labels

def testSelect(c: str | int, head: NonTerminal, string: Sentence):
    raise NotImplementedError

def bsrAdd(slot: Slot, i: int, k: int, j: int):
    raise NotImplementedError

def call(slot: Slot, i: int, j: int):
    raise NotImplementedError

def rtn(head: NonTerminal, k: int, j: int):
    raise NotImplementedError


def handleLabel(label: Slot):
    global Y, U, R, I, cI, cU, crf

    originalLabel = label
    label = Slot(label.head, Item(label.item.body, label.item.dot))

    if label.item.dot == 0 and len(label.item.body) == 0:
        Y.add((SubTerm(label.head, Sentence([])), cI, cI, cI))
    else:
        while not label.item.at_end() and isinstance(label.item[label.item.dot], Terminal):
            if label.item.dot != 0:
                if not testSelect(I[cI], label.head, label.item.body[label.item.dot:]):
                    return
            label.item.advance()
            bsrAdd(label, cU, cI, cI + 1)
            cI += 1

        if not label.item.at_end():
            if label.item.dot != 0:
                if not testSelect(I[cI], label.head, label.item.body[label.item.dot:]):
                    return
            label.item.advance()
            call(label, cU, cI)

    if originalLabel.item.at_end() or label.item.at_end() and isinstance(label.item[label.item.dot - 1], Terminal):
        if I[cI] in follow[label.head]:
            rtn(label.head, cU, cI)
    


if __name__ == '__main__':
    #create a simple example grammar
    #S ::= ACaB | ABaa
    #A ::= aA | a
    #B ::= bB | b
    #C ::= bC | b

    #create the non-terminals
    S = NonTerminal('S')
    A = NonTerminal('A')
    B = NonTerminal('B')
    C = NonTerminal('C')
    D = NonTerminal('D')

    ACaB = Sentence([A, C, 'a', B])
    ABaa = Sentence([A, B, 'a', 'a'])
    aA = Sentence(['a', A])
    a = Sentence(['a'])
    bB = Sentence(['b', B])
    b = Sentence(['b'])
    bC = Sentence(['b', C])
    ABCDAaA = Sentence([A, B, C, D, 'a', A])
    empty = Sentence([])

    #create the rules
    rules = [
        Rule(S, [ACaB, ABaa, ABCDAaA, ]),
        Rule(A, [aA, a]),
        Rule(B, [bB, b]),
        Rule(C, [bC, b]),
        Rule(D, [empty])
    ]



    # fill out the CNP template according to the description in the paper
    #redirect stdout to a buffer so that it can be easily saved to a file
    buf = StringIO()
    sys.stdout = buf

    print(f'''m = len(input)
I = [c for c in input] + [$]
u0 = CRF_Node(S, 0)
U = ∅
R = ∅
P = ∅
Υ = ∅
ntAdd(S, 0)
while len(R) > 0:
    L, cU, cI = R.pop() #remove a descriptor (L, k, j) from R
    goto L
    ''')
    for rule in rules:
        head = rule.head
        for body in rule.bodies:
            slot = Slot(head, Item(body, 0))
            print(f'    {slot}:') #print the first label
            if slot.item.at_end():
                PrintCode(slot)
            else:
                slot.item.advance()
                while True: #while not at end of item
                    PrintCode(slot)
                    if slot.item.at_end():
                        break
                    print(f'        if not testSelect(I[cI], {head}, {body[slot.item.dot:]}):')
                    print(f'            goto L0')
                    slot.item.advance()
            print(f'        if I[cI] ∈ follow({head}):')
            print(f'            rtn({head}, cU, cI)')
            print(f'        goto L0')
    print(f'''
if (for some α and l, (S ::= α, 0, l, m) ∈ Υ):
    report success
else:
    report failure
    ''')


    #write the current contents of the buffer to the terminal and a file
    out1 = buf.getvalue()

    #reset the buffer
    buf.seek(0)
    buf.truncate()



    #now we are going to adjust/rewrite the above process so that it can be computed on a per-slot basis
    #create the list of labels to be used by the CNP template
    labels = getLabels(rules)

    #print out the CNP template for each rule, generating the rule body according to the label slot
    print(f'''m = len(input)
I = [c for c in input] + [$]
u0 = CRF_Node(S, 0)
U = ∅
R = ∅
P = ∅
Υ = ∅
ntAdd(S, 0)
while len(R) > 0:
    L, cU, cI = R.pop() #remove a descriptor (L, k, j) from R
    goto L
    ''')
    for label in labels:
        print(f'    {label}:')
        printLabelBody(label)
    print(f'''
if (for some α and l, (S ::= α, 0, l, m) ∈ Υ):
    report success
else:
    report failure
    ''')

    #write the current contents of the buffer to the terminal and a file
    out2 = buf.getvalue()
    
    sys.stdout = sys.__stdout__

    #check if the strings produced the same output
    if out1 != out2:
        print('different strings produced by two approaches')

    with open('CNP1.txt', 'w') as f:
        f.write(out1)
    with open('CNP2.txt', 'w') as f:
        f.write(out2)
    # print(out1)
    # print(out2)


    # pdb.set_trace()