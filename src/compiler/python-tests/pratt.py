class Token:
    def __init__(self, type, value):
        self.type = type
        self.value = value

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.current = next(self.tokens)

    def eat(self, token_type):
        if self.current.type == token_type:
            self.current = next(self.tokens, None)
        else:
            raise ValueError(f"Unexpected token type: {self.current.type}")

    def parse(self):
        return self.expression()

    def expression(self, precedence=0):
        token = self.current

        if token.type in {"+", "-", "*", "/", "^"}:
            self.eat(token.type)
            left = UnaryOpNode(token.type, self.expression(10))
        else:
            self.eat("INT")
            left = IntNode(token.value)

        while self.current is not None and self.current.type in OPERATORS and OPERATORS[self.current.type] > precedence:
            op = self.current.type
            self.eat(op)
            right = self.expression(10 if self.current.type in {"*", "/"} else OPERATORS[op])
            left = BinOpNode(left, op, right)

        return left

class Node:
    pass

class IntNode(Node):
    def __init__(self, value):
        self.value = value

class UnaryOpNode(Node):
    def __init__(self, operator, operand):
        self.operator = operator
        self.operand = operand

class BinOpNode(Node):
    def __init__(self, left, operator, right):
        self.left = left
        self.operator = operator
        self.right = right

OPERATORS = {
    "+": 1, "-": 1,
    "*": 2, "/": 2, "%": 2,
    "^": 3
}

def tokenize(expression):
    for char in expression:
        if char.isdigit():
            yield Token("INT", int(char))
        elif char in OPERATORS or char in {"+", "-"}:
            yield Token(char, char)
    yield None  # End-of-input marker

def parse_expression(expression):
    tokens = tokenize(expression)
    parser = Parser(tokens)
    return parser.parse()

ast = parse_expression("2+3*5")
ast2 = parse_expression("10^/-3")
# This will create an abstract syntax tree (AST) representing the expression.
import pdb; pdb.set_trace()
...