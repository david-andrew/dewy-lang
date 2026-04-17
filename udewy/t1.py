"""
Tokenizer for udewy
designed to be straightforward to translate to assembly or etc. low level code
"""
from dataclasses import dataclass
from enum import Enum, auto
from typing import cast
from . import t0
from .errors import error


# some basic type aliases
# char = str  # length=1
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
    TK_CONST         = auto()
    TK_IF            = auto()
    TK_LOOP          = auto()
    TK_ELSE          = auto()
    TK_RETURN        = auto()
    TK_BREAK         = auto()
    TK_CONTINUE      = auto()
    TK_EXTERN        = auto()
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
    TK_ASSIGN        = auto()    # (None, start, TK_ASSIGN)
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

# operators that can be in place operators 
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

# placeholder for tokens that don't have a value
TRUE_VALUE: Value = 0xFFFF_FFFF_FFFF_FFFF
FALSE_VALUE: Value = 0x0000_0000_0000_0000

KEYWORD_TOKENS: dict[str, tuple[Value | None, Kind]] = {
    "let":        (None,        Kind.TK_LET),
    "const":      (None,        Kind.TK_CONST),
    "and":        (None,        Kind.TK_AND),
    "or":         (None,        Kind.TK_OR),
    "xor":        (None,        Kind.TK_XOR),
    "not":        (None,        Kind.TK_NOT),
    "true":       (TRUE_VALUE,  Kind.TK_NUMBER),
    "false":      (FALSE_VALUE, Kind.TK_NUMBER),
    "if":         (None,        Kind.TK_IF),
    "loop":       (None,        Kind.TK_LOOP),
    "else":       (None,        Kind.TK_ELSE),
    "return":     (None,        Kind.TK_RETURN),
    "break":      (None,        Kind.TK_BREAK),
    "continue":   (None,        Kind.TK_CONTINUE),
    "extern":     (None,        Kind.TK_EXTERN),
    "transmute":  (None,        Kind.TK_TRANSMUTE),
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
    value: Value | Kind | None
    location: Location
    kind: Kind


def tokenize(src:str)->list[Token]:
    n = len(src)
    i = 0
    toks: list[Token] = []  # this would be a stack in the assembly impl

    while i < n:
        # running sanity check(s) for prototype tokens that shouldn't be in the final output
        # check here so that we can maintain a single pass tokenizer
        if len(toks) > 1 and toks[-2].kind in (Kind._TK_COLON, Kind._TK_FN_COLON):
            error(src, i, f"colon must be followed by a type annotation, got {src[i]!r}")
        
        # whitespace
        if src[i] in t0.whitespace: #c == " " or c == "\t" or c == "\r" or c == "\n":
            i += 1
            continue

        # line comment: # ...
        if src[i] == "#":
            i += 1
            while i < n and src[i] != "\n":
                i += 1
            continue

        # identifier or keyword
        if t0.is_ident_start(src[i]):
            start = i
            i += 1
            while i < n and t0.is_ident(src[i]):
                i += 1
            text = src[start:i]

            keyword = KEYWORD_TOKENS.get(text)
            if keyword is not None:
                value, kind = keyword
                toks.append(Token(value, start, kind))
            elif text == "import":
                error(src, start, "`import` is a preprocessing directive and may only appear in the leading import prelude")
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
                toks.append(Token(None, start, Kind.TK_VOID))
            else:
                toks.append(Token(i - start, start, Kind.TK_IDENT))
            continue

        # hex number
        if src[i:].startswith('0x'):
            start = i
            i += 2
            val = 0
            while i < n and (t0.is_hex(src[i]) or src[i] == '_'):
                if src[i] != '_':
                    val = val << 4 | t0.hex_value(src[i])
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
        if t0.is_digit(src[i]):
            start = i
            val = 0
            while i < n and (t0.is_digit(src[i]) or src[i] == '_'):
                if src[i] != '_':
                    val = val * 10 + (ord(src[i]) - ord('0'))
                i += 1
            toks.append(Token(val, start, Kind.TK_NUMBER))
            continue
        
        # string
        if src[i] == '"':
            start = i
            i = t0.string_end(src, start)
            toks.append(Token(i - start, start, Kind.TK_STRING))
            continue
        
        # multi-character tokens
        if src.startswith(")(", i):
            toks.append(Token(None, i, Kind.TK_RIGHT_PAREN))
            toks.append(Token(None, i, Kind.TK_EXPR_CALL))
            i += 2
            continue

        # special case of "not" followed by "=?" -> "not=?"
        if src.startswith("=?", i) and toks and toks[-1].kind == Kind.TK_NOT:
            toks.pop()
            toks.append(Token(None, i, Kind.TK_NOT_EQ))
            i += 2
            continue
    
        # special case of in place assignment operator
        if src[i] == '=' and toks and toks[-1].kind in POSSIBLE_IN_PLACE_OPS:
            op_kind = toks.pop().kind
            toks.append(Token(op_kind, i, Kind.TK_UPDATE_ASSIGN))
            i += 1
            continue

        # general case of matching a symbol token
        matched_symbol = False
        for text, kind in SYMBOL_TOKENS:
            if src.startswith(text, i):
                toks.append(Token(None, i, kind))
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
                    error(src, i, "udewy doesn't support comments inside type parameters")
                if src[i] == '<':
                    stack += 1
                if src[i] == '>':
                    stack -= 1
                i += 1
            if stack != 0:
                error(src, start, "unterminated type parameter")
            toks.append(Token(i - start, start, Kind.TK_TYPE_PARAM))
            continue

        error(src, i, f"Unrecognized token {src[i]!r}")

    return toks

def dump_token(token:Token, src:str):
    location = token.location

    value: str | int | None = None
    if   token.kind == Kind.TK_IDENT:       value =        src[location:location+cast(int, token.value)]
    elif token.kind == Kind.TK_IDENT_CALL:  value =        src[location:location+cast(int, token.value)] + "("
    elif token.kind == Kind.TK_TYPE:        value = ':' +  src[location:location+cast(int, token.value)]
    elif token.kind == Kind.TK_FN_TYPE:     value = ':>' + src[location:location+cast(int, token.value)]
    elif token.kind == Kind.TK_TYPE_PARAM:  value =        src[location:location+cast(int, token.value)]  # <> already included in range
    elif token.kind == Kind.TK_STRING:      value =        src[location:location+cast(int, token.value)]
    elif token.kind == Kind.TK_NUMBER:      value =        cast(int, token.value)
    
    if value is not None:
        return f"({token.kind.name} {value})"
    return f'({token.kind.name})'



if __name__ == "__main__":
    import sys
    from . import t0
    from pathlib import Path

    if len(sys.argv) != 2:
        print("Usage: python -m udewy.t1 <file.udewy>")
        sys.exit(1)

    source_path = Path(sys.argv[1])
    source = t0.load_program_source(source_path)
    toks = tokenize(source)
    for tok in toks:
        print(dump_token(tok, source))