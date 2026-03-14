"""
Tokenizer for udewy
designed to be straightforward to translate to assembly or etc. low level code
"""
from enum import Enum, auto
from dataclasses import dataclass


# some basic type aliases
char = str  # length=1
Value = int
Location = int


class Kind(Enum):
    TK_IDENT         = auto()    # (length, start, TK_IDENT)        # basic identifier. used for all identifiers except for function calls and indexes
    TK_IDENT_CALL    = auto()    # (length, start, TK_IDENT_CALL)   # an identifier followed by a paren. e.g. `some_fn(`
    TK_STRING        = auto()    # (length, start, TK_STRING)
    TK_TYPE_PARAM    = auto()    # (length, start, TK_TYPE_PARAM)  # a type parameter. e.g. `<T>` or `<int|string|undefined>`
    TK_VOID          = auto()
    TK_NUMBER        = auto()
    TK_LET           = auto()
    TK_IF            = auto()
    TK_LOOP          = auto()
    TK_ELSE          = auto()
    TK_RETURN        = auto()
    TK_BREAK         = auto()
    TK_CONTINUE      = auto()

    # # operators that can be in place operators 
    # _START_CAN_BE_IN_PLACE_ASSIGNMENT_OP:int = auto()  # not a TokenKind, just an index marker
    TK_PLUS          = auto()
    TK_MINUS         = auto()
    TK_MUL           = auto()
    TK_IDIV          = auto()
    TK_MOD           = auto()
    TK_EQ            = auto()
    TK_NOT_EQ        = auto()
    TK_GT            = auto()
    TK_GT_EQ         = auto()
    TK_LT            = auto()
    TK_LT_EQ         = auto()
    TK_AND           = auto()
    TK_OR            = auto()
    TK_XOR           = auto()
    TK_NOT           = auto()
    TK_LEFT_SHIFT    = auto()
    TK_RIGHT_SHIFT   = auto()
    # _END_CAN_BE_IN_PLACE_ASSIGNMENT_OP:int = auto()  # not a TokenKind, just an index marker

    TK_ASSIGN        = auto()    # (NO_VALUE, start, TK_ASSIGN)
    TK_UPDATE_ASSIGN = auto()    # (kind, start, TK_UPDATE_ASSIGN) # an equals sign after an operator token, i.e. `+=`, `-=`, `*=`, `//=`, `%=`
    TK_EXPR_CALL     = auto()    # closing paren followed by opening paren i.e. `)(...)`. means do a function call on the result of the left expression in parens
    TK_LEFT_PAREN    = auto()
    TK_RIGHT_PAREN   = auto()
    TK_LEFT_BRACE    = auto()
    TK_RIGHT_BRACE   = auto()
    TK_LEFT_BRACKET  = auto()
    TK_RIGHT_BRACKET = auto()
    _TK_COLON        = auto()    # should not appear in the final output 
    _TK_FN_COLON     = auto()    # should not appear in the final output 
    TK_TYPE          = auto()
    TK_FN_TYPE       = auto()    # `:>` e.g. `let foo = ():>bar => { ... }`
    TK_FN_ARROW      = auto()    # `=>`
    TK_PIPE          = auto()    # `|>` e.g. `x |> f1 |> f2 |> f3`
    TK_TRANSMUTE     = auto()    # `transmute` i.e. `<expr> transmute <(ident typeparam?)|typeparam>` e.g. `true transmute uint64`, `[1 2 3 4] transmute array<string>`, `foo transmute <int | string | bool>`, etc.

POSSIBLE_IN_PLACE_OPS: set[Kind] = {
    Kind.TK_PLUS,
    Kind.TK_MINUS,
    Kind.TK_MUL,
    Kind.TK_IDIV,
    Kind.TK_MOD,
    Kind.TK_EQ,
    Kind.TK_NOT_EQ,
    Kind.TK_GT,
    Kind.TK_GT_EQ,
    Kind.TK_LT,
    Kind.TK_LT_EQ,
    Kind.TK_AND,
    Kind.TK_OR,
    Kind.TK_XOR,
    Kind.TK_NOT,
    Kind.TK_LEFT_SHIFT,
    Kind.TK_RIGHT_SHIFT,
}

# placehold for tokens that don't have a value
TRUE_VALUE: Value = 0xFFFF_FFFF_FFFF_FFFF
FALSE_VALUE: Value = 0x0000_0000_0000_0000
NO_VALUE: Value = 0 # i.e. placeholder for tokens that don't have a value

KEYWORD_TOKENS: dict[str, tuple[Value, Kind]] = {
    "let":        (NO_VALUE,    Kind.TK_LET),
    "const":      (NO_VALUE,    Kind.TK_LET),
    "and":        (NO_VALUE,    Kind.TK_AND),
    "or":         (NO_VALUE,    Kind.TK_OR),
    "xor":        (NO_VALUE,    Kind.TK_XOR),
    "not":        (NO_VALUE,    Kind.TK_NOT),
    "true":       (TRUE_VALUE,  Kind.TK_NUMBER),
    "false":      (FALSE_VALUE, Kind.TK_NUMBER),
    "if":         (NO_VALUE,    Kind.TK_IF),
    "loop":       (NO_VALUE,    Kind.TK_LOOP),
    "else":       (NO_VALUE,    Kind.TK_ELSE),
    "return":     (NO_VALUE,    Kind.TK_RETURN),
    "break":      (NO_VALUE,    Kind.TK_BREAK),
    "continue":   (NO_VALUE,    Kind.TK_CONTINUE),
    "transmute":  (NO_VALUE,    Kind.TK_TRANSMUTE),
}

# sorted by length so that we take longest match
SYMBOL_TOKENS: list[tuple[str, Kind]] = [
    # MULTI_CHAR_TOKENS
    (">=?", Kind.TK_GT_EQ),
    ("<=?", Kind.TK_LT_EQ),
    ("//",  Kind.TK_IDIV),
    ("=?",  Kind.TK_EQ),
    (">?",  Kind.TK_GT),
    ("<?",  Kind.TK_LT),
    (":>",  Kind._TK_FN_COLON),
    ("=>",  Kind.TK_FN_ARROW),
    ("|>",  Kind.TK_PIPE),
    ("<<",  Kind.TK_LEFT_SHIFT),
    (">>",  Kind.TK_RIGHT_SHIFT),

    # SINGLE_CHAR_TOKENS
    ("+", Kind.TK_PLUS),
    ("-", Kind.TK_MINUS),
    ("*", Kind.TK_MUL),
    ("%", Kind.TK_MOD),
    ("(", Kind.TK_LEFT_PAREN),
    (")", Kind.TK_RIGHT_PAREN),
    ("{", Kind.TK_LEFT_BRACE),
    ("}", Kind.TK_RIGHT_BRACE),
    ("[", Kind.TK_LEFT_BRACKET),
    ("]", Kind.TK_RIGHT_BRACKET),
    (":", Kind._TK_COLON),
    ("=", Kind.TK_ASSIGN),

]


@dataclass
class Token:
    value: Value
    location: Location
    kind: Kind

whitespace: set[char] = {' ', '\t', '\n', '\r'}

def is_alpha(c:char)->bool:
    return ('A' <= c <= 'Z') or ('a' <= c <= 'z') or (c == "_")

def is_digit(c:char)->bool:
    return '0' <= c <= '9'

def is_hex(c:char)->bool:
    return is_digit(c) or ('A' <= c <= 'F') or ('a' <= c <= 'f')


def hex_value(c: char) -> int:
    if '0' <= c <= '9':
        return ord(c) - ord('0')
    if 'A' <= c <= 'F':
        return ord(c) - ord('A') + 10
    if 'a' <= c <= 'f':
        return ord(c) - ord('a') + 10
    
    raise ValueError(f"invalid hex digit: {c}")



def tokenize(src:str)->list[Token]:
    n = len(src)
    i = 0
    toks: list[Token] = []  # this would be a stack in the assembly impl

    while i < n:
        # running sanity check(s) for prototype tokens that shouldn't be in the final output
        # check here so that we can maintain a single pass tokenizer
        if len(toks) > 1 and toks[-2].kind in (Kind._TK_COLON, Kind._TK_FN_COLON):
            raise SyntaxError(f"colon must be followed by a type annotation at {i}: {src[i]!r}")
        
        # whitespace
        if src[i] in whitespace: #c == " " or c == "\t" or c == "\r" or c == "\n":
            i += 1
            continue

        # line comment: # ...
        if src[i] == "#":
            i += 1
            while i < n and src[i] != "\n":
                i += 1
            continue

        # identifier or keyword
        if is_alpha(src[i]):
            start = i
            i += 1
            while i < n and (is_alpha(src[i]) or is_digit(src[i])):
                i += 1
            text = src[start:i]

            keyword = KEYWORD_TOKENS.get(text)
            if keyword is not None:
                value, kind = keyword
                toks.append(Token(value, start, kind))
            elif text == "import":
                raise SyntaxError(f"`import` is a preprocessing directive and may only appear in the leading import prelude at {start}")
            elif i < n and src[i] == '(':
                toks.append(Token(i - start, start, Kind.TK_IDENT_CALL))
                i += 1  # consume the '('
            elif toks and toks[-1].kind == Kind._TK_COLON:
                toks.pop()
                toks.append(Token(i - start, start, Kind.TK_TYPE))
            elif toks and toks[-1].kind == Kind._TK_FN_COLON:
                toks.pop()
                toks.append(Token(i - start, start, Kind.TK_FN_TYPE))
            elif text == "void":
                # `:void` should become a type token, not a bare void keyword.
                toks.append(Token(NO_VALUE, start, Kind.TK_VOID))
            else:
                toks.append(Token(i - start, start, Kind.TK_IDENT))
            continue

        # hex number
        if src[i:].startswith('0x'):
            start = i
            i += 2
            val = 0
            while i < n and (is_hex(src[i]) or src[i] == '_'):
                if src[i] != '_':
                    val = val << 4 | hex_value(src[i])
                i += 1
            toks.append(Token(val, start, Kind.TK_NUMBER))
            continue
        
        # binary number
        if src[i:].startswith('0b'):
            start = i
            i += 2
            val = 0
            while i < n and src[i] in '01_':
                if src[i] != '_':
                    val = val << 1 | (ord(src[i]) - ord('0'))
                i += 1
            toks.append(Token(val, start, Kind.TK_NUMBER))
            continue

        # number (decimal int)
        if is_digit(src[i]):
            start = i
            val = 0
            while i < n and (is_digit(src[i]) or src[i] == '_'):
                if src[i] != '_':
                    val = val * 10 + (ord(src[i]) - ord('0'))
                i += 1
            toks.append(Token(val, start, Kind.TK_NUMBER))
            continue
        
        # string
        if src[i] == '"':
            start = i
            i += 1
            while i < n and src[i] != '"':
                if src[i] == '{' or src[i] == '}': raise SyntaxError(f"interpolation not supported in udewy strings at {i}: {src[start:i]!r}")
                if src[i] == '\\':
                    i += 1
                    if i >= n:
                        raise SyntaxError(f"unterminated string at {i}: {src[start:i]!r}")
                i += 1
            if i >= n or src[i] != '"':
                raise SyntaxError(f"unterminated string at {i}: {src[start:i]!r}")
            i += 1
            # store the string text location + length
            toks.append(Token(i - start, start, Kind.TK_STRING))
            continue
        
        # multi-character tokens
        if src.startswith(")(", i):
            toks.append(Token(NO_VALUE, i, Kind.TK_RIGHT_PAREN))
            toks.append(Token(NO_VALUE, i, Kind.TK_EXPR_CALL))
            i += 2
            continue

        # special case of "not" followed by "=?" -> "not=?"
        if src.startswith("=?", i) and toks and toks[-1].kind == Kind.TK_NOT:
            toks.pop()
            toks.append(Token(NO_VALUE, i, Kind.TK_NOT_EQ))
            i += 2
            continue
    
        # special case of in place assignment operator
        if src[i] == '=' and toks and toks[-1].kind in POSSIBLE_IN_PLACE_OPS:
            toks.pop()
            toks.append(Token(NO_VALUE, i, Kind.TK_UPDATE_ASSIGN))
            i += 1
            continue

        # general case of matching a symbol token
        matched_symbol = False
        for text, kind in SYMBOL_TOKENS:
            if src.startswith(text, i):
                toks.append(Token(NO_VALUE, i, kind))
                i += len(text)
                matched_symbol = True
                break
        if matched_symbol:
            continue
    
        # type parameter
        if src[i] == '<':
            stack = 1
            start = i
            i += 1
            while i < n and stack > 0:
                if src[i] == '#':
                    raise SyntaxError(f"udewy doesn't support comments inside type parameters at {i}: {src[start:i]!r}")
                if src[i] == '<':
                    stack += 1
                if src[i] == '>':
                    stack -= 1
                i += 1
            if stack != 0:
                raise SyntaxError(f"unterminated type parameter at {start}: {src[start:i]!r}")
            toks.append(Token(i - start, start, Kind.TK_TYPE_PARAM))
            continue

        # unknown character
        raise SyntaxError(f"Unrecognized token at {i}: {src[i]!r}\nTokens so far\n{toks}")

    return toks




def dump_token(token:Token, src:str):
    value = token.value
    location = token.location
    kind = token.kind

    if kind == Kind.TK_IDENT:         value = src[location:location+value]
    elif kind == Kind.TK_IDENT_CALL:  value = src[location:location+value] + "("
    elif kind == Kind.TK_TYPE:        value = ':' +src[location:location+value]
    elif kind == Kind.TK_FN_TYPE:     value = ':>' + src[location:location+value]
    elif kind == Kind.TK_TYPE_PARAM:  value = src[location:location+value]  # <> already included in range
    elif kind == Kind.TK_STRING:      value = src[location:location+value]
    elif kind == Kind.TK_NUMBER:      value = value
    else:                        value = None
    
    if value is not None:
        return f"({kind.name} {value})"
    return f'({kind.name})'



if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python t0.py <file>")
        sys.exit(1)
    with open(sys.argv[1], "r") as f:
        src = f.read()
    toks = tokenize(src)
    for tok in toks:
        print(dump_token(tok, src))