"""
goal: minimal parser + tokenizer, 
output 
- C
- x86_64?
- qbe?

"""

from typing import TypeAlias
from itertools import count

import pdb


# some basic type aliases
char: TypeAlias = str # length=1
TokenKind: TypeAlias = int
TokenValue: TypeAlias = int
Location: TypeAlias = int
Token: TypeAlias = tuple[TokenKind, TokenValue, Location]
PackedToken: TypeAlias = int

# ----- Token kinds -----
_counter = count(0)
def auto(): return next(_counter)

TK_EOF:     TokenKind = auto()
TK_IDENT:   TokenKind = auto()    # (TK_IDENT, length, start)
TK_NUM:     TokenKind = auto()
TK_STRING:  TokenKind = auto()    # (TK_STRING, length, start)
TK_LET:     TokenKind = auto()
TK_PLUS:    TokenKind = auto()
TK_MINUS:   TokenKind = auto()
TK_MUL:     TokenKind = auto()
TK_IDIV:    TokenKind = auto()
TK_LPAREN:  TokenKind = auto()
TK_RPAREN:  TokenKind = auto()
TK_LBRACE:  TokenKind = auto()
TK_RBRACE:  TokenKind = auto()
TK_LBRACKET:TokenKind = auto()
TK_RBRACKET:TokenKind = auto()
TK_ASSIGN:  TokenKind = auto()
TK_EQ:      TokenKind = auto()
TK_NOT_EQ:  TokenKind = auto()
TK_GT:      TokenKind = auto()
TK_GT_EQ:   TokenKind = auto()
TK_LT:      TokenKind = auto()
TK_LT_EQ:   TokenKind = auto()
TK_AND:     TokenKind = auto()
TK_OR:      TokenKind = auto()
TK_NOT:     TokenKind = auto()
TK_COLON:   TokenKind = auto()
TK_COMMA:   TokenKind = auto()
TK_DOT:     TokenKind = auto()
TK_FN_COLON:TokenKind = auto()
TK_FN_ARROW:TokenKind = auto()
TK_PIPE:    TokenKind = auto()
TK_SEMI:    TokenKind = auto()

# placehold for tokens that don't have a value
TRUE_VALUE: TokenValue = 1
FALSE_VALUE: TokenValue = 0
NO_VALUE: TokenValue = 0 # i.e. placeholder for tokens that don't have a value


def pack_token(kind:TokenKind, value:TokenValue, location:Location)->PackedToken:
    """Pack a token into a single 64-bit integer"""
    return (kind << 32) | (value << 16) | location

def unpack_token(packed:PackedToken)->Token:
    """Unpack a token from a single 64-bit integer"""
    return (packed >> 32, (packed >> 16) & 0xFFFF, packed & 0xFFFF)

def str_left_eq(prefix:str, s:str)->bool:
    """Check if the prefix is a left substring of the string"""
    if len(prefix) > len(s):
        return False
    i = 0
    end = len(prefix)
    while i < end:
        if prefix[i] != s[i]:
            return False
        i += 1
    return True

def str_eq(s1:str, s2:str)->bool:
    """Check if the two strings are equal"""
    if len(s1) != len(s2):
        return False
    i = 0
    end = len(s1)
    while i < end:
        if s1[i] != s2[i]:
            return False
        i += 1
    return True

def is_alpha(c:char)->bool:
    o = ord(c)
    return (65 <= o <= 90) or (97 <= o <= 122) or (c == "_")

def is_digit(c:char)->bool:
    o = ord(c)
    return 48 <= o <= 57


def tokenize(src:str)->list[PackedToken]:
    n = len(src)
    i = 0
    toks: list[PackedToken] = []  # this would be a stack in the assembly impl

    while i < n:
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

            if str_left_eq("let", text) or str_left_eq("const", text):
                toks.append(pack_token(TK_LET, NO_VALUE, start))
            elif str_left_eq("and", text):
                toks.append(pack_token(TK_AND, NO_VALUE, start))
            elif str_left_eq("or", text):
                toks.append(pack_token(TK_OR, NO_VALUE, start))
            elif str_left_eq("not", text):
                toks.append(pack_token(TK_NOT, NO_VALUE, start))
            elif str_left_eq("true", text):
                toks.append(pack_token(TK_NUM, TRUE_VALUE, start))
            elif str_left_eq("false", text):
                toks.append(pack_token(TK_NUM, FALSE_VALUE, start))
            else:
                # store the identifier text location + length
                toks.append(pack_token(TK_IDENT, len(text), start))
            continue

        # number (decimal int)
        if is_digit(c):
            start = i
            val = 0
            while i < n and is_digit(src[i]):
                val = val * 10 + (ord(src[i]) - 48)
                i += 1
            toks.append(pack_token(TK_NUM, val, start))
            continue
        
        # string
        if c == '"':
            start = i
            i += 1
            while i < n and (src[i] != '"' or src[i-1] == '\\'):
                print(f"i: {i}, src[i]: {src[i]}")
                if src[i] == '{' or src[i] == '}':
                    pdb.set_trace()
                    raise SyntaxError(f"interpolation not supported in udewy strings at {i}: {src[start:i]!r}")
                if src[i] == '\\': i += 1 # skip escape characters, so checking `\"` is aligned properly and we wouldn't accidentally match e.g. `\\"` as not the end of the string
                i += 1
            if src[i] != '"':
                raise SyntaxError(f"unterminated string at {i}: {src[start:i]!r}")
            i += 1
            # store the string text location + length
            toks.append(pack_token(TK_STRING, i - start, start))
            continue


        # multi-character tokens
        if str_left_eq("//", src[i:]):
            toks.append(pack_token(TK_IDIV, NO_VALUE, i))
            i += 2
            continue
        if str_left_eq("=?", src[i:]):
            toks.append(pack_token(TK_EQ, NO_VALUE, i))
            i += 2
            continue
        if str_left_eq("!=?", src[i:]):
            toks.append(pack_token(TK_NOT_EQ, NO_VALUE, i))
            i += 3
            continue
        if str_left_eq(">=?", src[i:]):
            toks.append(pack_token(TK_GT_EQ, NO_VALUE, i))
            i += 3
            continue
        if str_left_eq("<=?", src[i:]):
            toks.append(pack_token(TK_LT_EQ, NO_VALUE, i))
            i += 3
            continue
        if str_left_eq(">?", src[i:]):
            toks.append(pack_token(TK_GT, NO_VALUE, i))
            i += 2
            continue
        if str_left_eq("<?", src[i:]):
            toks.append(pack_token(TK_LT, NO_VALUE, i))
            i += 2
            continue
        if str_left_eq(":>", src[i:]):
            toks.append(pack_token(TK_FN_COLON, NO_VALUE, i))
            i += 2
            continue
        if str_left_eq("=>", src[i:]):
            toks.append(pack_token(TK_FN_ARROW, NO_VALUE, i))
            i += 2
            continue
        if str_left_eq("|>", src[i:]):
            toks.append(pack_token(TK_PIPE, NO_VALUE, i))
            i += 2
            continue

        # single-character tokens
        i += 1
        if c == "+": toks.append(pack_token(TK_PLUS, NO_VALUE, i)); continue
        if c == "-": toks.append(pack_token(TK_MINUS, NO_VALUE, i)); continue
        if c == "*": toks.append(pack_token(TK_MUL, NO_VALUE, i)); continue
        if c == "(": toks.append(pack_token(TK_LPAREN, NO_VALUE, i)); continue
        if c == ")": toks.append(pack_token(TK_RPAREN, NO_VALUE, i)); continue
        if c == "{": toks.append(pack_token(TK_LBRACE, NO_VALUE, i)); continue
        if c == "}": toks.append(pack_token(TK_RBRACE, NO_VALUE, i)); continue
        if c == "[": toks.append(pack_token(TK_LBRACKET, NO_VALUE, i)); continue
        if c == "]": toks.append(pack_token(TK_RBRACKET, NO_VALUE, i)); continue
        if c == "=": toks.append(pack_token(TK_ASSIGN, NO_VALUE, i)); continue
        if c == ";": toks.append(pack_token(TK_SEMI, NO_VALUE, i)); continue
        if c == ":": toks.append(pack_token(TK_COLON, NO_VALUE, i)); continue
        if c == ",": toks.append(pack_token(TK_COMMA, NO_VALUE, i)); continue
        if c == ".": toks.append(pack_token(TK_DOT, NO_VALUE, i)); continue
        i -= 1  # undo the increment above


        # unknown character
        pdb.set_trace()
        raise SyntaxError(f"bad character at {i}: {c!r}")

    toks.append(pack_token(TK_EOF, NO_VALUE, n))
    return toks



# TODO: little globals() helper for printing out tokens



if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python t0.py <file>")
        sys.exit(1)
    with open(sys.argv[1], "r") as f:
        src = f.read()
    toks = tokenize(src)
    for tok in toks:
        print(unpack_token(tok))