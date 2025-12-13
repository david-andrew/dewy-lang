"""
t2
build chains + flowables
pratt/shunt parse


t2 tasks:
- build strings
- build floats
- collect blocks as token with sub members
- combine opchains

t3 tasks:
- insert juxtapose

then parsing, typechecking, codegen, etc.
"""


class Token2:
    ...

class Float(Token2):
    """
    Patterns:
    3.14
    1.0
    1.23e4
    1.23E+4
    1.23e-4
    0x1.8p10    % note `p` instead of `e` for exponent. 0x1.8p10 = 1.5 × 2¹⁰
    0x1.fp-2    % bug: if number after dot is different base, tokenizer doesn't recognize it without a prefix.. perhaps make that the case (i.e. require user to specify prefix every time, warn if bases don't match in float)
    1e10
    2E-23

    10.25p3  % all base 10. suggested to either warn or error (leaning warn b/c simpler to parse, just look for src[i] in 'eEpP')

    0x1.0x8p10   % special case <hex>.<hex>p<dec> gets no warning, even though base mismatch
    0x1.0x8p0xA  % no warning, though programmer being extra explicit
    0x1.0b1p10   % warn, mantissa halves have different bases
    0x1.8p10     % warn, different bases
    
    p/P is only allowed for bases that are powers of 2, and means 2^exponent (instead of 10^exponent for e/E)

    literals? probably not parsed here, but as identifiers
      nan
      inf
    literals are treated as singleton types, and receive their bit pattern when used in a typed context
    ```dewy
    a:float64 = inf  % convert to ieee754 compatible float inf
    b:int = inf`     % convert to symbolic InfinityType that can interact with ints as a singleton type
    ```

    suggested to have some set of string input functions for C/IEEE-754 notation
    ieee754<float64>'0x1.8p10'
    """
    ...

class String(Token2):
    """
    <string_inner> = (chars|escape|block)*

    string = 
      | <quote><string_inner><quote>
      | <raw_quote><chars>*<quote>
      | <heredoc_start><string_inner><heredoc_end>
      | <raw_heredoc_start><chars>*<heredoc_end>
      | <rof_start><chars>*
    
    perhaps consider two separate string tokens:
    - interpolated
    - chars only
    we would select the appropriate one based on if there are any blocks present in the string
    (perhaps later in type checking, some interpolated strings could be converted to chars only if their expression is compiletime const)
    """
    ...

class Block(Token2):
    """
    <opener><inner_tokens><matching closer>
    """
    ...

class OpChain(Token2):
    ...


# class Symbol(Token2): ...  # tbd if all the symbols here would just go under identifier, e.g. '∞', '∅'
# class InfixOperator(Token2): ...
# class PrefixOperator(Token2): ...
# class PostfixOperator(Token2): ...
class Operator(Token2): ...
class Keyword(Token2): ... # e.g. if, loop, import, let, etc. any keyword that behaves differently syntactically e.g. `<keyword> <expr>`. Ignore keywords that can go in identifiers, e.g. `void`, `intrinsic`/`extern`, etc.
class Identifier(Token2): ...
class Hashtag(Token2): ...   
class Integer(Token2): ...
class Whitespace(Token2): ... # so we can invert later for juxtapose