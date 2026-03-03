"""
goal: minimal parser + tokenizer, 
output 
- C
- x86_64?
- qbe?

"""

from itertools import count

import pdb


# some basic type aliases
type char = str # length=1
type TokenKind = int
type TokenValue = int
type Location = int
type Token = tuple[TokenKind, TokenValue, Location]
type PackedToken = int

# ----- Token kinds -----
_counter = count(0)
def auto(): return next(_counter)

# TK_EOF:          TokenKind = auto()
TK_IDENT:        TokenKind = auto()    # (TK_IDENT, length, start)        # basic identifier. used for all identifiers except for function calls and indexes
TK_IDENT_CALL:   TokenKind = auto()    # (TK_CALL_IDENT, length, start)   # an identifier followed by a paren. e.g. `some_fn(`
TK_IDENT_INDEX:  TokenKind = auto()    # (TK_IDENT_INDEX, length, start)  # an identifier followed by a bracket. e.g. `some_arr[`
TK_IDENT_DOT:    TokenKind = auto()    # (TK_IDENT_DOT, length, start)    # an identifier followed by a dot. e.g. `some_obj.`
TK_STRING:       TokenKind = auto()    # (TK_STRING, length, start)
TK_NUMBER:       TokenKind = auto()
TK_LET:          TokenKind = auto()
TK_IF:           TokenKind = auto()
TK_LOOP:         TokenKind = auto()
TK_ELSE:         TokenKind = auto()
TK_RETURN:       TokenKind = auto()
TK_BREAK:        TokenKind = auto()
TK_CONTINUE:     TokenKind = auto()
TK_PLUS:         TokenKind = auto()
TK_MINUS:        TokenKind = auto()
TK_MUL:          TokenKind = auto()
TK_IDIV:         TokenKind = auto()
TK_MOD:          TokenKind = auto()
TK_LEFT_PAREN:   TokenKind = auto()
TK_RIGHT_PAREN:  TokenKind = auto()
TK_LEFT_BRACE:   TokenKind = auto()
TK_RIGHT_BRACE:  TokenKind = auto()
TK_LEFT_BRACKET: TokenKind = auto()
TK_RIGHT_BRACKET:TokenKind = auto()
TK_ASSIGN:       TokenKind = auto()
TK_EQ:           TokenKind = auto()
TK_NOT_EQ:       TokenKind = auto()
TK_GT:           TokenKind = auto()
TK_GT_EQ:        TokenKind = auto()
TK_LT:           TokenKind = auto()
TK_LT_EQ:        TokenKind = auto()
TK_AND:          TokenKind = auto()
TK_OR:           TokenKind = auto()
TK_BIT_NOT:      TokenKind = auto()
TK_LEFT_SHIFT:   TokenKind = auto()
TK_RIGHT_SHIFT:  TokenKind = auto()
TK_NOT:          TokenKind = auto()
_TK_COLON:       TokenKind = auto()  # should not appear in the final output 
_TK_FN_COLON:    TokenKind = auto()  # should not appear in the final output 
TK_TYPE:         TokenKind = auto()
TK_FN_TYPE:      TokenKind = auto()
TK_FN_ARROW:     TokenKind = auto()
TK_PIPE:         TokenKind = auto() # TBD if included or not. single arg piping

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
        if len(toks) > 1 and (unpack_token(toks[-2])[0] == _TK_COLON or unpack_token(toks[-2])[0] == _TK_FN_COLON):
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

            if str_left_eq("let", text) or str_left_eq("const", text):
                toks.append(pack_token(TK_LET, NO_VALUE, start))
            elif str_left_eq("and", text):
                toks.append(pack_token(TK_AND, NO_VALUE, start))
            elif str_left_eq("or", text):
                toks.append(pack_token(TK_OR, NO_VALUE, start))
            elif str_left_eq("not", text):# and (i >= n or src[i] != '='):  # one special case since `not=?` is checked after
                toks.append(pack_token(TK_NOT, NO_VALUE, start))
            elif str_left_eq("true", text):
                toks.append(pack_token(TK_NUMBER, TRUE_VALUE, start))
            elif str_left_eq("false", text):
                toks.append(pack_token(TK_NUMBER, FALSE_VALUE, start))
            elif str_left_eq("if", text):
                toks.append(pack_token(TK_IF, NO_VALUE, start))
            elif str_left_eq("loop", text):
                toks.append(pack_token(TK_LOOP, NO_VALUE, start))
            elif str_left_eq("else", text):
                toks.append(pack_token(TK_ELSE, NO_VALUE, start))
            elif str_left_eq("return", text):
                toks.append(pack_token(TK_RETURN, NO_VALUE, start))
            elif str_left_eq("break", text):
                toks.append(pack_token(TK_BREAK, NO_VALUE, start))
            elif str_left_eq("continue", text):
                toks.append(pack_token(TK_CONTINUE, NO_VALUE, start))
            elif i < n and src[i] == '(':
                toks.append(pack_token(TK_IDENT_CALL, len(text), start))
                i += 1 # consume the '('
            elif i < n and src[i] == '[':
                toks.append(pack_token(TK_IDENT_INDEX, len(text), start))
                i += 1 # consume the '['
            elif i < n and src[i] == '.':
                toks.append(pack_token(TK_IDENT_DOT, len(text), start))
                i += 1 # consume the '.'
            elif unpack_token(toks[-1])[0] == _TK_COLON:
                toks.pop()
                toks.append(pack_token(TK_TYPE, len(text), start))
                continue
            elif unpack_token(toks[-1])[0] == _TK_FN_COLON:
                toks.pop()
                toks.append(pack_token(TK_FN_TYPE, len(text), start))
                continue
            else:
                # regular identifier
                toks.append(pack_token(TK_IDENT, len(text), start))
            continue

        # hex number
        if i+2 < n and src[i] == '0' and src[i+1] == 'x':
            start = i
            i += 2
            val = 0
            while i < n and is_hex(src[i]):
                digit_val = ord(src[i]) - 48 if 48 <= ord(src[i]) <= 57 else ord(src[i]) - 55
                val = val * 16 + digit_val
                i += 1
            toks.append(pack_token(TK_NUMBER, val, start))
            continue
        
        # binary number
        if i+2 < n and src[i] == '0' and src[i+1] == 'b':
            start = i
            i += 2
            val = 0
            while i < n and (src[i] == '0' or src[i] == '1'):
                val = val * 2 + (ord(src[i]) - 48)
                i += 1
            toks.append(pack_token(TK_NUMBER, val, start))
            continue

        # number (decimal int)
        if is_digit(c):
            start = i
            val = 0
            while i < n and is_digit(src[i]):
                val = val * 10 + (ord(src[i]) - 48)
                i += 1
            toks.append(pack_token(TK_NUMBER, val, start))
            continue
        
        # string
        if c == '"':
            start = i
            i += 1
            while i < n and src[i] != '"':
                if src[i] == '{' or src[i] == '}':
                    raise SyntaxError(f"interpolation not supported in udewy strings at {i}: {src[start:i]!r}")
                if src[i] == '\\': i += 1 # skip escape characters, properly handles escaping quotes
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
            if toks[-1] == TK_NOT:
                toks.pop()
                toks.append(pack_token(TK_NOT_EQ, NO_VALUE, i))
            else:
                toks.append(pack_token(TK_EQ, NO_VALUE, i))
            i += 2
            continue
        # if str_left_eq("not=?", src[i:]):
        #     toks.append(pack_token(TK_NOT_EQ, NO_VALUE, i))
        #     i += 5
        #     continue
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
            toks.append(pack_token(_TK_FN_COLON, NO_VALUE, i))
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
        if str_left_eq("<<", src[i:]):
            toks.append(pack_token(TK_LEFT_SHIFT, NO_VALUE, i))
            i += 2
            continue
        if str_left_eq(">>", src[i:]):
            toks.append(pack_token(TK_RIGHT_SHIFT, NO_VALUE, i))
            i += 2
            continue
        

        # single-character tokens
        i += 1
        if c == "+": toks.append(pack_token(TK_PLUS, NO_VALUE, i));          continue
        if c == "-": toks.append(pack_token(TK_MINUS, NO_VALUE, i));         continue
        if c == "*": toks.append(pack_token(TK_MUL, NO_VALUE, i));           continue
        if c == "%": toks.append(pack_token(TK_MOD, NO_VALUE, i));           continue
        if c == "~": toks.append(pack_token(TK_BIT_NOT, NO_VALUE, i));       continue
        if c == "(": toks.append(pack_token(TK_LEFT_PAREN, NO_VALUE, i));    continue
        if c == ")": toks.append(pack_token(TK_RIGHT_PAREN, NO_VALUE, i));   continue
        if c == "{": toks.append(pack_token(TK_LEFT_BRACE, NO_VALUE, i));    continue
        if c == "}": toks.append(pack_token(TK_RIGHT_BRACE, NO_VALUE, i));   continue
        if c == "[": toks.append(pack_token(TK_LEFT_BRACKET, NO_VALUE, i));  continue
        if c == "]": toks.append(pack_token(TK_RIGHT_BRACKET, NO_VALUE, i)); continue
        if c == "=": toks.append(pack_token(TK_ASSIGN, NO_VALUE, i));        continue
        if c == ":": toks.append(pack_token(_TK_COLON, NO_VALUE, i));        continue
        i -= 1  # undo the increment above


        # unknown character
        pdb.set_trace()
        raise SyntaxError(f"bad character at {i}: {c!r}")

    # toks.append(pack_token(TK_EOF, NO_VALUE, n))
    return toks



# Some convenient debug helpers (not written in assembly-ish style)
def kind_to_str(kind:TokenKind)->str:
    for name, value in globals().items():
        if not name.startswith("TK_"): continue
        if value == kind:
            return name
    raise ValueError(f"unknown token kind: {kind}")

def dump_token(token:PackedToken, src:str):
    kind, value, location = unpack_token(token)
    kind_str = kind_to_str(kind)

    if kind == TK_IDENT:
        length, start = value, location
        value = src[start:start+length]
    elif kind == TK_IDENT_CALL:
        length, start = value, location
        value = src[start:start+length] + "("
    elif kind == TK_IDENT_INDEX:
        length, start = value, location
        value = src[start:start+length] + "["
    elif kind == TK_IDENT_DOT:
        length, start = value, location
        value = src[start:start+length] + "."
    elif kind == TK_TYPE:
        length, start = value, location
        value = ':' +src[start:start+length]
    elif kind == TK_FN_TYPE:
        length, start = value, location
        value = ':>' + src[start:start+length]
    elif kind == TK_STRING:
        length, start = value, location
        value = src[start:start+length]
    elif kind == TK_NUMBER:
        value = value
    else:
        value = None
    
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