"""
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
    
    literals?
      nan
      inf % tbd since we have our own separate `inf` that is not treated as a float..? or consider maybe it does map to float?.. tbd

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