"""
Tokenizer for udewy
designed to be straightforward to translate to assembly or etc. low level code
"""

from itertools import count

# some basic type aliases
char = str  # length=1
TokenKind = int
TokenValue = int
Location = int
Token = tuple[TokenValue, Location, TokenKind]
PackedToken = int  # 128-bit integer: vvvv_vvvv_vvvv_vvvv llll_llll_llll_kkkk (v=value, l=location, k=kind)

# ----- Token kinds -----
_counter = count(0)
def auto(): return next(_counter)

TK_IDENT:        TokenKind = auto()    # (length, start, TK_IDENT)        # basic identifier. used for all identifiers except for function calls and indexes
TK_IDENT_CALL:   TokenKind = auto()    # (length, start, TK_IDENT_CALL)   # an identifier followed by a paren. e.g. `some_fn(`
TK_STRING:       TokenKind = auto()    # (length, start, TK_STRING)
TK_TYPE_PARAM:   TokenKind = auto()    # (length, start, TK_TYPE_PARAM)  # a type parameter. e.g. `<T>` or `<int|string|undefined>`
TK_VOID:         TokenKind = auto()
TK_NUMBER:       TokenKind = auto()
TK_LET:          TokenKind = auto()
TK_IF:           TokenKind = auto()
TK_LOOP:         TokenKind = auto()
TK_ELSE:         TokenKind = auto()
TK_RETURN:       TokenKind = auto()
TK_BREAK:        TokenKind = auto()
TK_CONTINUE:     TokenKind = auto()

# operators that can be in place operators 
_START_CAN_BE_IN_PLACE_ASSIGNMENT_OP:int = auto()  # not a TokenKind, just an index marker
TK_PLUS:         TokenKind = auto()
TK_MINUS:        TokenKind = auto()
TK_MUL:          TokenKind = auto()
TK_IDIV:         TokenKind = auto()
TK_MOD:          TokenKind = auto()
TK_EQ:           TokenKind = auto()
TK_NOT_EQ:       TokenKind = auto()
TK_GT:           TokenKind = auto()
TK_GT_EQ:        TokenKind = auto()
TK_LT:           TokenKind = auto()
TK_LT_EQ:        TokenKind = auto()
TK_AND:          TokenKind = auto()
TK_OR:           TokenKind = auto()
TK_XOR:          TokenKind = auto()
TK_NOT:          TokenKind = auto()
TK_LEFT_SHIFT:   TokenKind = auto()
TK_RIGHT_SHIFT:  TokenKind = auto()
_END_CAN_BE_IN_PLACE_ASSIGNMENT_OP:int = auto()  # not a TokenKind, just an index marker

TK_ASSIGN:       TokenKind = auto()    # (NO_VALUE, start, TK_ASSIGN)
TK_UPDATE_ASSIGN:TokenKind = auto()    # (kind, start, TK_UPDATE_ASSIGN) # an equals sign after an operator token, i.e. `+=`, `-=`, `*=`, `//=`, `%=`
TK_EXPR_CALL:    TokenKind = auto()    # closing paren followed by opening paren i.e. `)(...)`. means do a function call on the result of the left expression in parens
TK_LEFT_PAREN:   TokenKind = auto()
TK_RIGHT_PAREN:  TokenKind = auto()
TK_LEFT_BRACE:   TokenKind = auto()
TK_RIGHT_BRACE:  TokenKind = auto()
TK_LEFT_BRACKET: TokenKind = auto()
TK_RIGHT_BRACKET:TokenKind = auto()
_TK_COLON:       TokenKind = auto()    # should not appear in the final output 
_TK_FN_COLON:    TokenKind = auto()    # should not appear in the final output 
TK_TYPE:         TokenKind = auto()
TK_FN_TYPE:      TokenKind = auto()    # `:>` e.g. `let foo = ():>bar => { ... }`
TK_FN_ARROW:     TokenKind = auto()    # `=>`
TK_PIPE:         TokenKind = auto()    # `|>` e.g. `x |> f1 |> f2 |> f3`
TK_TRANSMUTE:    TokenKind = auto()    # `transmute` i.e. `<expr> transmute <(ident typeparam?)|typeparam>` e.g. `true transmute uint64`, `[1 2 3 4] transmute array<string>`, `foo transmute <int | string | bool>`, etc.

# placehold for tokens that don't have a value
TRUE_VALUE: TokenValue = 0xFFFF_FFFF_FFFF_FFFF
FALSE_VALUE: TokenValue = 0x0000_0000_0000_0000
NO_VALUE: TokenValue = 0 # i.e. placeholder for tokens that don't have a value

KEYWORD_TOKENS: dict[str, tuple[TokenValue, TokenKind]] = {
    "let": (NO_VALUE, TK_LET),
    "const": (NO_VALUE, TK_LET),
    "and": (NO_VALUE, TK_AND),
    "or": (NO_VALUE, TK_OR),
    "xor": (NO_VALUE, TK_XOR),
    "not": (NO_VALUE, TK_NOT),
    "true": (TRUE_VALUE, TK_NUMBER),
    "false": (FALSE_VALUE, TK_NUMBER),
    "if": (NO_VALUE, TK_IF),
    "loop": (NO_VALUE, TK_LOOP),
    "else": (NO_VALUE, TK_ELSE),
    "return": (NO_VALUE, TK_RETURN),
    "break": (NO_VALUE, TK_BREAK),
    "continue": (NO_VALUE, TK_CONTINUE),
    "transmute": (NO_VALUE, TK_TRANSMUTE),
}

MULTI_CHAR_TOKENS: tuple[tuple[str, TokenKind], ...] = (
    (">=?", TK_GT_EQ),
    ("<=?", TK_LT_EQ),
    ("//", TK_IDIV),
    ("=?", TK_EQ),
    (">?", TK_GT),
    ("<?", TK_LT),
    (":>", _TK_FN_COLON),
    ("=>", TK_FN_ARROW),
    ("|>", TK_PIPE),
    ("<<", TK_LEFT_SHIFT),
    (">>", TK_RIGHT_SHIFT),
)

SINGLE_CHAR_TOKENS: dict[str, TokenKind] = {
    "+": TK_PLUS,
    "-": TK_MINUS,
    "*": TK_MUL,
    "%": TK_MOD,
    "(": TK_LEFT_PAREN,
    ")": TK_RIGHT_PAREN,
    "{": TK_LEFT_BRACE,
    "}": TK_RIGHT_BRACE,
    "[": TK_LEFT_BRACKET,
    "]": TK_RIGHT_BRACKET,
    ":": _TK_COLON,
}


def pack(value:TokenValue, location:Location, kind:TokenKind)->PackedToken:
    """
    Pack a token into a single 128-bit integer
    vvvv_vvvv_vvvv_vvvv llll_llll_llll_kkkk (l=location, v=value, k=kind)
    """
    return (value << 64) | (location << 16) | kind

def unpack(packed:PackedToken)->Token:
    """
    Unpack a token from a single 128-bit integer
    
    Returns: (value, location, kind)
    """
    return (packed >> 64, (packed >> 16) & 0xFFFF_FFFF_FFFF, packed & 0xFFFF)

def kindof(packed:PackedToken)->TokenKind:
    return packed & 0xFFFF

def is_alpha(c:char)->bool:
    o = ord(c)
    return (65 <= o <= 90) or (97 <= o <= 122) or (c == "_")

def is_digit(c:char)->bool:
    o = ord(c)
    return 48 <= o <= 57

def is_hex(c:char)->bool:
    o = ord(c)
    return (48 <= o <= 57) or (65 <= o <= 70) or (97 <= o <= 102)


def tokenize(src:str)->list[PackedToken]:
    n = len(src)
    i = 0
    toks: list[PackedToken] = []  # this would be a stack in the assembly impl

    while i < n:
        # running sanity check(s) for prototype tokens that shouldn't be in the final output
        # check here so that we can maintain a single pass tokenizer
        if len(toks) > 1 and kindof(toks[-2]) in (_TK_COLON, _TK_FN_COLON):
            raise SyntaxError(f"colon must be followed by a type annotation at {i}: {src[i]!r}")
        
        # current character
        c = src[i]

        # whitespace
        if c == " " or c == "\t" or c == "\r" or c == "\n":
            i += 1
            continue

        # line comment: # ...
        if c == "#":
            i += 1
            while i < n and src[i] != "\n":
                i += 1
            continue

        # identifier or keyword
        if is_alpha(c):
            start = i
            i += 1
            while i < n and (is_alpha(src[i]) or is_digit(src[i])):
                i += 1
            text = src[start:i]

            keyword = KEYWORD_TOKENS.get(text)
            if keyword is not None:
                value, kind = keyword
                toks.append(pack(value, start, kind))
            elif text == "import":
                raise SyntaxError(f"`import` is a preprocessing directive and may only appear in the leading import prelude at {start}")
            elif i < n and src[i] == '(':
                toks.append(pack(i - start, start, TK_IDENT_CALL))
                i += 1  # consume the '('
            elif toks and kindof(toks[-1]) == _TK_COLON:
                toks.pop()
                toks.append(pack(i - start, start, TK_TYPE))
            elif toks and kindof(toks[-1]) == _TK_FN_COLON:
                toks.pop()
                toks.append(pack(i - start, start, TK_FN_TYPE))
            elif text == "void":
                # `:void` should become a type token, not a bare void keyword.
                toks.append(pack(NO_VALUE, start, TK_VOID))
            else:
                toks.append(pack(i - start, start, TK_IDENT))
            continue

        # hex number
        if i+2 < n and src[i] == '0' and src[i+1] == 'x':
            start = i
            i += 2
            val = 0
            while i < n and (is_hex(src[i]) or src[i] == '_'):
                if src[i] != '_':
                    digit_val = ord(src[i]) - 48 if 48 <= ord(src[i]) <= 57 else ord(src[i]) - 55
                    val = val << 4 | digit_val
                i += 1
            toks.append(pack(val, start, TK_NUMBER))
            continue
        
        # binary number
        if i+2 < n and src[i] == '0' and src[i+1] == 'b':
            start = i
            i += 2
            val = 0
            while i < n and (src[i] == '0' or src[i] == '1' or src[i] == '_'):
                if src[i] != '_':
                    val = val << 1 | (ord(src[i]) - 48)
                i += 1
            toks.append(pack(val, start, TK_NUMBER))
            continue

        # number (decimal int)
        if is_digit(c):
            start = i
            val = 0
            while i < n and (is_digit(src[i]) or src[i] == '_'):
                if src[i] != '_':
                    val = val * 10 + (ord(src[i]) - 48)
                i += 1
            toks.append(pack(val, start, TK_NUMBER))
            continue
        
        # string
        if c == '"':
            start = i
            i += 1
            while i < n and src[i] != '"':
                if src[i] == '{' or src[i] == '}': raise SyntaxError(f"interpolation not supported in udewy strings at {i}: {src[start:i]!r}")
                if src[i] == '\\': i += 1 # skip escape characters, properly handles escaping quotes
                i += 1
            if src[i] != '"':
                raise SyntaxError(f"unterminated string at {i}: {src[start:i]!r}")
            i += 1
            # store the string text location + length
            toks.append(pack(i - start, start, TK_STRING))
            continue
        
        # multi-character tokens
        if src.startswith(")(", i):
            toks.append(pack(NO_VALUE, i, TK_RIGHT_PAREN))
            toks.append(pack(NO_VALUE, i, TK_EXPR_CALL))
            i += 2
            continue

        if src.startswith("=?", i):
            if toks and kindof(toks[-1]) == TK_NOT:
                toks.pop()
                toks.append(pack(NO_VALUE, i, TK_NOT_EQ))
            else:
                toks.append(pack(NO_VALUE, i, TK_EQ))
            i += 2
            continue

        matched_multi = False
        for text, kind in MULTI_CHAR_TOKENS:
            if src.startswith(text, i):
                toks.append(pack(NO_VALUE, i, kind))
                i += len(text)
                matched_multi = True
                break
        if matched_multi:
            continue
    
        # type parameter
        if c == '<':
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
            toks.append(pack(i - start, start, TK_TYPE_PARAM))
            continue

        # single-character tokens
        token_kind = SINGLE_CHAR_TOKENS.get(c)
        if token_kind is not None:
            toks.append(pack(NO_VALUE, i, token_kind))
            i += 1
            continue
        if c == "=":
            if not toks:
                raise SyntaxError(f"unexpected equals sign at {i}: {src[i:]!r}")
            prior_kind = kindof(toks[-1])
            # if the prior token is an operator that can be an in place operator
            if prior_kind > _START_CAN_BE_IN_PLACE_ASSIGNMENT_OP and prior_kind < _END_CAN_BE_IN_PLACE_ASSIGNMENT_OP:
                toks.pop()
                toks.append(pack(prior_kind, i, TK_UPDATE_ASSIGN))
            else:
                toks.append(pack(NO_VALUE, i, TK_ASSIGN))
            i += 1
            continue

        # note if any checks are done after this, need to undo the increment of i

        # unknown character (-1 undoes the increment from above)
        raise SyntaxError(f"bad character at {i}: {c=}. {src[i-1:]=}")

    return toks



# Some convenient debug helpers (not written in assembly-ish style)
def kind_to_str(kind:TokenKind)->str:
    for name, value in globals().items():
        if not name.startswith("TK_"): continue
        if value == kind:
            return name
    raise ValueError(f"unknown token kind: {kind}")

def dump_token(token:PackedToken, src:str):
    value, location, kind = unpack(token)
    kind_str = kind_to_str(kind)

    if kind == TK_IDENT:         value = src[location:location+value]
    elif kind == TK_IDENT_CALL:  value = src[location:location+value] + "("
    elif kind == TK_TYPE:        value = ':' +src[location:location+value]
    elif kind == TK_FN_TYPE:     value = ':>' + src[location:location+value]
    elif kind == TK_TYPE_PARAM:  value = src[location:location+value]  # <> already included in range
    elif kind == TK_STRING:      value = src[location:location+value]
    elif kind == TK_NUMBER:      value = value
    else:                        value = None
    
    if value is not None:
        return f"({kind_str} {value})"
    return f'({kind_str})'



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