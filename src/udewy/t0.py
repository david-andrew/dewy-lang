"""
Tokenizer for udewy
designed to be straightforward to translate to assembly or etc. low level code
"""

from itertools import count

import pdb


# some basic type aliases
type char = str # length=1
type TokenKind = int
type TokenValue = int
type Location = int
type Token = tuple[TokenValue, Location, TokenKind]
type PackedToken = int  # 128-bit integer: vvvv_vvvv_vvvv_vvvv llll_llll_llll_kkkk (v=value, l=location, k=kind)

# ----- Token kinds -----
_counter = count(0)
def auto(): return next(_counter)

# TK_EOF:          TokenKind = auto()
TK_IDENT:        TokenKind = auto()    # (length, start, TK_IDENT)        # basic identifier. used for all identifiers except for function calls and indexes
TK_IDENT_CALL:   TokenKind = auto()    # (length, start, TK_IDENT_CALL)   # an identifier followed by a paren. e.g. `some_fn(`
TK_IDENT_INDEX:  TokenKind = auto()    # (length, start, TK_IDENT_INDEX)  # an identifier followed by a bracket. e.g. `some_arr[`
TK_STRING:       TokenKind = auto()    # (length, start, TK_STRING)
TK_TYPE_PARAM:   TokenKind = auto()    # (length, start, TK_TYPE_PARAM)  # a type parameter. e.g. `<T>` or `<int|string|undefined>`
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
TK_EXPR_CALL:    TokenKind = auto()    # closing paren followed by opening paren i.e. `)(...)`
TK_LEFT_PAREN:   TokenKind = auto()
TK_RIGHT_PAREN:  TokenKind = auto()
TK_LEFT_BRACE:   TokenKind = auto()
TK_RIGHT_BRACE:  TokenKind = auto()
TK_LEFT_BRACKET: TokenKind = auto()
TK_RIGHT_BRACKET:TokenKind = auto()
_TK_COLON:       TokenKind = auto()    # should not appear in the final output 
_TK_FN_COLON:    TokenKind = auto()    # should not appear in the final output 
TK_TYPE:         TokenKind = auto()
TK_FN_TYPE:      TokenKind = auto()
TK_FN_ARROW:     TokenKind = auto()
TK_PIPE:         TokenKind = auto()

# placehold for tokens that don't have a value
TRUE_VALUE: TokenValue = 0xFFFF_FFFF_FFFF_FFFF
FALSE_VALUE: TokenValue = 0x0000_0000_0000_0000
NO_VALUE: TokenValue = 0 # i.e. placeholder for tokens that don't have a value


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
        if len(toks) > 1 and (kindof(toks[-2]) == _TK_COLON or kindof(toks[-2]) == _TK_FN_COLON):
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
            
            # specific keywords
            if   str_left_eq("let", text):      toks.append(pack(NO_VALUE, start, TK_LET))
            elif str_left_eq("const", text):    toks.append(pack(NO_VALUE, start, TK_LET))
            elif str_left_eq("and", text):      toks.append(pack(NO_VALUE, start, TK_AND))
            elif str_left_eq("or", text):       toks.append(pack(NO_VALUE, start, TK_OR))
            elif str_left_eq("xor", text):      toks.append(pack(NO_VALUE, start, TK_XOR))
            elif str_left_eq("not", text):      toks.append(pack(NO_VALUE, start, TK_NOT))
            elif str_left_eq("true", text):     toks.append(pack(TRUE_VALUE, start, TK_NUMBER))
            elif str_left_eq("false", text):    toks.append(pack(FALSE_VALUE, start, TK_NUMBER))
            elif str_left_eq("void", text):     toks.append(pack(NO_VALUE, start, TK_NUMBER))
            elif str_left_eq("if", text):       toks.append(pack(NO_VALUE, start, TK_IF))
            elif str_left_eq("loop", text):     toks.append(pack(NO_VALUE, start, TK_LOOP))
            elif str_left_eq("else", text):     toks.append(pack(NO_VALUE, start, TK_ELSE))
            elif str_left_eq("return", text):   toks.append(pack(NO_VALUE, start, TK_RETURN))
            elif str_left_eq("break", text):    toks.append(pack(NO_VALUE, start, TK_BREAK))
            elif str_left_eq("continue", text): toks.append(pack(NO_VALUE, start, TK_CONTINUE))
            
            # special cases of identifiers preceded or followed by something
            elif i < n and src[i] == '(':
                toks.append(pack(i - start, start, TK_IDENT_CALL))
                i += 1 # consume the '('
            elif i < n and src[i] == '[':
                toks.append(pack(i - start, start, TK_IDENT_INDEX))
                i += 1 # consume the '['
            elif len(toks) > 0 and kindof(toks[-1]) == _TK_COLON:
                toks.pop()
                toks.append(pack(i - start, start, TK_TYPE))
            elif len(toks) > 0 and kindof(toks[-1]) == _TK_FN_COLON:
                toks.pop()
                toks.append(pack(i - start, start, TK_FN_TYPE))
            
            # regular identifier
            else: toks.append(pack(i - start, start, TK_IDENT))
            
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
            while i < n and is_digit(src[i]):
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
        if str_left_eq("//", src[i:]):
            toks.append(pack(NO_VALUE, i, TK_IDIV))
            i += 2
            continue
        if str_left_eq("=?", src[i:]):
            if kindof(toks[-1]) == TK_NOT:
                toks.pop()
                toks.append(pack(NO_VALUE, i, TK_NOT_EQ))
            else:
                toks.append(pack(NO_VALUE, i, TK_EQ))
            i += 2
            continue
        if str_left_eq(">=?", src[i:]):
            toks.append(pack(NO_VALUE, i, TK_GT_EQ))
            i += 3
            continue
        if str_left_eq("<=?", src[i:]):
            toks.append(pack(NO_VALUE, i, TK_LT_EQ))
            i += 3
            continue
        if str_left_eq(">?", src[i:]):
            toks.append(pack(NO_VALUE, i, TK_GT))
            i += 2
            continue
        if str_left_eq("<?", src[i:]):
            toks.append(pack(NO_VALUE, i, TK_LT))
            i += 2
            continue
        if str_left_eq(":>", src[i:]):
            toks.append(pack(NO_VALUE, i, _TK_FN_COLON))
            i += 2
            continue
        if str_left_eq("=>", src[i:]):
            toks.append(pack(NO_VALUE, i, TK_FN_ARROW))
            i += 2
            continue
        if str_left_eq("|>", src[i:]):
            toks.append(pack(NO_VALUE, i, TK_PIPE))
            i += 2
            continue
        if str_left_eq("<<", src[i:]):
            toks.append(pack(NO_VALUE, i, TK_LEFT_SHIFT))
            i += 2
            continue
        if str_left_eq(">>", src[i:]):
            toks.append(pack(NO_VALUE, i, TK_RIGHT_SHIFT))
            i += 2
            continue
        if str_left_eq(")(", src[i:]):
            toks.append(pack(NO_VALUE, i, TK_RIGHT_PAREN))
            toks.append(pack(NO_VALUE, i, TK_EXPR_CALL))
            i += 2
            continue
    
        # type parameter
        if c == '<':
            stack = 1
            start = i
            i += 1
            while i < n and stack > 0: #src[i] != '>':
                if src[i] == '#': raise SyntaxError(f"udewy doesn't support comments inside type parameters at {i}: {src[start:i]!r}")
                if src[i] == '<': stack += 1
                if src[i] == '>': stack -= 1
                i += 1
            toks.append(pack(i - start, start, TK_TYPE_PARAM))
            continue

        # single-character tokens
        i += 1
        if c == "+": toks.append(pack(NO_VALUE, i, TK_PLUS));          continue
        if c == "-": toks.append(pack(NO_VALUE, i, TK_MINUS));         continue
        if c == "*": toks.append(pack(NO_VALUE, i, TK_MUL));           continue
        if c == "%": toks.append(pack(NO_VALUE, i, TK_MOD));           continue
        if c == "(": toks.append(pack(NO_VALUE, i, TK_LEFT_PAREN));    continue
        if c == ")": toks.append(pack(NO_VALUE, i, TK_RIGHT_PAREN));   continue
        if c == "{": toks.append(pack(NO_VALUE, i, TK_LEFT_BRACE));    continue
        if c == "}": toks.append(pack(NO_VALUE, i, TK_RIGHT_BRACE));   continue
        if c == "[": toks.append(pack(NO_VALUE, i, TK_LEFT_BRACKET));  continue
        if c == "]": toks.append(pack(NO_VALUE, i, TK_RIGHT_BRACKET)); continue
        if c == ":": toks.append(pack(NO_VALUE, i, _TK_COLON));        continue
        if c == "=":
            if len(toks) == 0: raise SyntaxError(f"unexpected equals sign at {i}: {src[i:]!r}")
            prior_kind = kindof(toks[-1])
            # if the prior token is an operator that can be an in place operator
            if prior_kind > _START_CAN_BE_IN_PLACE_ASSIGNMENT_OP and prior_kind < _END_CAN_BE_IN_PLACE_ASSIGNMENT_OP:
                toks.pop()
                toks.append(pack(prior_kind, i, TK_UPDATE_ASSIGN))
            else:
                toks.append(pack(NO_VALUE, i, TK_ASSIGN))
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
    elif kind == TK_IDENT_INDEX: value = src[location:location+value] + "["
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