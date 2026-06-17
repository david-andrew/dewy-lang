# dewy compiler rewrite
This is an in-progress rewrite from the ground up of the dewy compiler. When finished, this will completely replace the existing dewy compiler code located under dewy-lang/src

## Major changes
- target udewy as primary backend. udewy can then target specific backends
    - special backends like universal shell, etc. can still be directly targeted by dewy
- brand new lexer/parser designed to keep things cleaner
    - t0 is still perhaps a bit complicated given how many constructs it supports. may consider removing the whole inherit from `Token[Context]`, and just replace it with simple lists of which states can read which tokens
    - uses a bottom up precedence parser. very directly related to the precedence table. similar to pratt parsing with binding power, but bottom up instead of top down.
- much improved type checking process (work in progress). TBD the exact shape/semantics, but the whole mul vs call vs index jux ambiguity is tucked neatly in straightforward ambiguous nodes
