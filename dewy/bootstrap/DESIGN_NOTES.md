# Hosted parser design notes

This inventory preserves documentation and pending decisions from the hosted parser while the bootstrap is developed. These are reference notes, not additional language features. See README.md for implementation status.

## t0

### dewy/parser/t0.py:1

```text
Tokenizer framework

This module implements a small declarative framework for tokenizing Dewy source.

Each concrete token is a subclass of `Token[T]`, where `T` is one or more
`Context` types indicating where that token is valid (e.g. `Root`, `StringBody`, `BlockBody`, etc.).
`Token.__init_subclass__` introspects the type parameter and builds a `valid_contexts` set for each token class.

During `tokenize`, we never hard-code a list of token types.
Instead, we dynamically (with caching) determine which tokens are allowed in a given context:
- look up all subclasses of `Token` via `descendants(Token)`,
- filter them by whether the current context type appears in their `valid_contexts`,
- then call `eat(src[i:], ctx)` on each allowed token class remaining.

Any token whose `eat` method returns a non-`None` length is considered a match.
We keep only the longest matches, then resolve any remaining ambiguities via `token_precedence`.

Each token class can also return a `Push` or `Pop` action from `action_on_eat`,
which updates a stack of `Context` objects (for example when entering or
leaving a block or string). This context stack controls which tokens are
eligible to match at each position, and lets the tokenizer enforce context-
sensitive rules (e.g. different tokens allowed inside strings vs. at the top
level) in a purely declarative way.
```

### dewy/parser/t0.py:109

```text
determine if a digit is valid in a given base
```

### dewy/parser/t0.py:114

```text
Parse an integer from a string, handling base prefixes and underscores
```

### dewy/parser/t0.py:228

```text
Base class for all tokens.

    Each concrete token is a `Token[T]` where `T` is one or more `Context`
    types (e.g. `Root`, `StringBody`, `BlockBody`). Subclasses declare where
    they are valid by choosing appropriate type parameters; `__init_subclass__`
    inspects those parameters and populates `valid_contexts` for the class.
    
    Example:
        ```
        class MyToken(Token[StringBody]): ...
        ``` 
        will only be considered when the current context is `StringBody`, while
        ```
        class AnotherToken(Token[GeneralBodyContexts]): ...
        ``` 
        will be considered in any of `Root`, `BlockBody`, or `TypeBody` contexts.

    The main `tokenize` loop discovers token classes dynamically via
    `descendants(Token)` and caches, for each `Context` type, the list of token
    classes whose `valid_contexts` contains that context type. For each token
    class allowed in the current context, it calls its `eat(src[i:], ctx)` method;
    eat methods return an integer length
    to indicate a match (and how many characters it is) or `None` if no match. 
    The tokenizer uses the longest match strategy to break ties, and may further
    break ties using `token_precedence` if multiple longest matches have the same length.

    After a token is instantiated, its `action_on_eat` result (`Push`, `Pop`,
    or `None`) updates the context stack (if needed). This design lets token
    classes declare both where they are legal and how they affect nesting
    structure, without having to be manually registered in the tokenizer.
```

### dewy/parser/t0.py:1377

```text
For a given context type, return all token types that are allowed in that context. Cached for performance
    WARNING: because this is cached, creating new Token classes after this is called may not be reflected in the cached result
```

### dewy/parser/t0.py:1498

```text
Convert a list of tokens to a report of the tokens consumed so far.
```

### dewy/parser/t0.py:169

```text
Return the current position in the source string that the tokenizer is at
```

### dewy/parser/t0.py:271

```text
Try to match a token
        
        Args:
            src (str): the source string to match against, starting at the current position
            ctx (Context): the current context mode the tokenizer is in
        
        Returns: 
            int | None: The number of characters eaten if successful, or `None` if no match.
```

### dewy/parser/t0.py:283

```text
If overridden, indicates actions to perform on the context stack when a token is eaten.

        Args:
            ctx (Context): the current context mode the tokenizer is in

        Returns:
            ContextAction: a `Push`, `Pop`, or `None` action to perform on the context stack.
```

### dewy/parser/t0.py:295

```text
verify that subclasses parameterize Token with a context argument and set the valid_contexts class variable
```

### dewy/parser/t0.py:301

```text
get the type parameters of the child class (e.g. class Identifier(Token[GeneralBodyContexts])) -> [*GeneralBodyContexts]
```

### dewy/parser/t0.py:327

```text
white space is any sequence of whitespace characters
```

### dewy/parser/t0.py:349

```text
line comments are any sequence of characters after a # until the end of the line
```

### dewy/parser/t0.py:367

```text
Block comments are of the form #{ ... }# and can be nested.
```

### dewy/parser/t0.py:413

```text
Identifiers:
        - may not start with a number
        - may not be an operator (handled by longest match + token precedence)
        - may contain decorator characters (superscripts/subscripts) anywhere (but must include at least one start character)
```

### dewy/parser/t0.py:442

```text
symbolic operators are any sequence of characters in the symbolic_operators set
```

### dewy/parser/t0.py:453

```text
shift operators are any sequence of characters in the shift_operators set
```

### dewy/parser/t0.py:463

```text
metatags are just special identifiers that start with $
```

### dewy/parser/t0.py:674

```text
string quotes are any odd-length sequence of either all single or all double quotes
```

### dewy/parser/t0.py:700

```text
a string quote closer is a matching opening quote
```

### dewy/parser/t0.py:722

```text
regular characters are anything except for the delimiter, an escape sequence, or a block opening
```

### dewy/parser/t0.py:753

```text
Eat an escape sequence, return the number of characters eaten
        
        Predefined escape sequences:
        - \n newline
        - \\n (i.e. \<newline>) a special case that basically ignores the newline and continues the string. Useful for ignoring newlines in multiline strings.
        - \r carriage return
        - \t tab
        - \b backspace
        - \f form feed
        - \v vertical tab
        - \a alert
        - \0 null
        - \u#### or \U#### for a unicode codepoints. Must be four hex digits [0-9a-fA-F]
        - \x or \X hex byte escapes are not supported (error)

        Catch-all case:
        - \ followed by any character not mentioned above converts to just the literal character itself without the backslash
        This is how to insert characters that have special meaning in the string, e.g.
        - \' converts to just a single quote '
        - \{ converts to just a single open brace {
        - \\ converts to just a single backslash \
        - \m converts to just a single character m
        - \<space> converts to just a single <space> character
        - etc.
```

### dewy/parser/t0.py:820

```text
Helper for when a string escape is incomplete
```

### dewy/parser/t0.py:833

```text
Helper for when a hex or unicode escape doesn't have enough digits
```

### dewy/parser/t0.py:862

```text
\u{##..##} or \U{##..##} for an arbitrary unicode character. Inside the braces defaults to hex, and users can get decimal by using the 0d prefix
        
        The block can also be an arbitrary expression, so long as it evaluates to an integer
```

### dewy/parser/t0.py:878

```text
raw string quotes are r followed by any odd-length sequence of either all single or all double quotes
```

### dewy/parser/t0.py:891

```text
regular characters are anything except for the delimiter
```

### dewy/parser/t0.py:907

```text
dollar string quotes are t followed by any odd-length sequence of either all single or all double quotes
```

### dewy/parser/t0.py:920

```text
a string that has an opening delimiter but no closing delimiter (consumes until EOF)
        Opening delimiters $""" $'''
```

### dewy/parser/t0.py:932

```text
a raw string that has an opening delimiter but no closing delimiter (consumes until EOF)
        Opening delimiters $r""" $r'''
```

### dewy/parser/t0.py:945

```text
a template string that has an opening delimiter but no closing delimiter (consumes until EOF)
        Opening delimiters t""" t'''
```

### dewy/parser/t0.py:960

```text
heredoc string opening and closing quotes are `$"<delim>"` and `<delim>` respectively
        <delim> is an arbitrary user-defined delimiter. May use any identifier or symbol characters in the language except for quotes `"`, `'`
```

### dewy/parser/t0.py:986

```text
get the delimiter from the string quote
```

### dewy/parser/t0.py:991

```text
Helper for when a heredoc delimiter is incomplete
```

### dewy/parser/t0.py:1014

```text
Helper to check if a heredoc delimiter starts or ends with space
```

### dewy/parser/t0.py:1052

```text
a heredoc string closer is a matching opening quote
```

### dewy/parser/t0.py:1071

```text
raw heredoc string opening and closing quotes are `$r"<delim>"` and `<delim>` respectively
        <delim> is an arbitrary user-defined delimiter. May use any identifier or symbol characters in the language except for quotes `"`, `'`
```

### dewy/parser/t0.py:1084

```text
get the delimiter from the string quote
```

### dewy/parser/t0.py:1093

```text
template heredoc string opening and closing quotes are `$t"<delim>"` and `<delim>` respectively
        <delim> is an arbitrary user-defined delimiter. May use any identifier or symbol characters in the language except for quotes `"`, `'`
```

### dewy/parser/t0.py:1106

```text
get the delimiter from the string quote
```

### dewy/parser/t0.py:1150

```text
a based number is a sequence of 1 or more digits, optionally preceded by a (lowercase) base prefix (up to base-16)
```

### dewy/parser/t0.py:1212

```text
an exponent marker is a single character `eE` or `pP` with a number before and a number after
        This is specifically to disambiguate for floats where the exponent part is read as an identifier
        e.g. 1e10 looks like <number 1><identifier e10>
```

### Pending implementation and design markers

```text
46: # TODO: The specific set of digits is open for debate. The following are proposed:
50: # Also `ϕϖϗϰϱϴ`, perhaps just `ϕϴ` which would normalize to the greek versions
134: '\\', # left divide e.g. given Ax=b, x=A\b, where A\B ≡ solve(A B) (note this is not the same as x=A⁻¹B) (TODO: move description to docs)
137: '=', '::', ':=', # not a walrus operator. `x:=y` is sugar for `let x=y` (TODO: move this description to where ever we describe all operators, e.g. docs)
206: # TODO: consider making it each context defines what tokens are valid for it, rather than tokens select from valid contexts
323: # TODO: want a warning if there is a lone \r not followed by \n
1161: # TODO: have error here if not a based string literal or based array literal
1235: # TBD if we want a more global list, or what, but this should be good for now
1241: # TODO: other cases...
1265: hint="Shift operations may not be used directly within a type parameter.\nPerhaps you meant to wrap the expression in parentheses\ne.g. `something<(a >> b)>` instead of `something<a >> b>`"
1308: # TODO: other known error cases
1365: pdb.set_trace()
1367: raise NotImplementedError(f"INTERNAL ERROR: unhandled context: {ctx=}")
1446: # TODO: probably a better way to handle would be for checking if any upper contexts support the next token
1448: # TBD: what about the other way around, e.g. if the user didn't open a context they are trying to close?
```

## t1

### dewy/parser/t1.py:1

```text
Second phase of tokenization. Mainly building up a few types of compound tokens out of constituent parts. Namely:
- strings
- floats
- blocks
- opchains

Additionally symbols are separated into operators and identifiers. And identifiers from the previous step have keywords and keyword operators split off
```

### dewy/parser/t1.py:72

```text
For Token2's that are not constructed via the normal .eat() method. instead other tokens may construct them directly
```

### dewy/parser/t1.py:89

```text
Patterns:
    <number><eEpP><number>
    <number><eEpP><+-><number>
    <number><dot><number>
    <number><dot><number><eEpP><number>
    <number><dot><number><eEpP><+-><number>

    
    Examples:
    3.14
    1.0
    1.23e4
    1.23E+4
    1.23e-4
    0x1.0x8p10  % note `p` instead of `e` for exponent. 0x1.8p10 = 1.5 × 2¹⁰
    % 0x1.fp-2  % note this won't parse as a float because no prefix was used for the number after the dot. <int 0x1><dot><identifier fp><operator -><int 2>
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
    b:int = inf      % convert to symbolic InfinityType that can interact with ints as a singleton type
    ```

    suggested to have some set of string input functions for C/IEEE-754 notation
    ieee754<float64>'0x1.8p10'
```

### dewy/parser/t1.py:188

```text
any strings that contain only chars and or non-parametric escapes (i.e. the entire string is known and can be rendered without evaluating any interpolations or parametric escape expressions)


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
```

### dewy/parser/t1.py:293

```text
Any string that contains an expression or interpolation (includes parametric unicode+hex escapes)
```

### dewy/parser/t1.py:301

```text
<opener><inner_tokens><matching closer>
```

### dewy/parser/t1.py:449

```text
Public API for second tokenization stage
```

### dewy/parser/t1.py:494

```text
Mostly for error reporting purposes. Try to get the next token2. Otherwise try to get the next token1. Otherwise return None
```

### Pending implementation and design markers

```text
24: # 'extern', 'intrinsic', 'none', 'void', 'untyped', 'end', 'new' #TBD if these are keywords or just special identifiers
75: raise NotImplementedError(f'{cls.__name__} should not be constructed via .eat(). Instead some other token should construct it directly via {cls.__name__}(...)')
201: perhaps consider two separate string tokens:
205: (perhaps later in type checking, some interpolated strings could be converted to chars only if their expression is compiletime const)
461: # TODO: more specific error reporting based on the case
468: hint='TODO: better error analysis'
476: # TODO: more specific error reporting based on the case
483: hint=f'The following tokens matched: {matches}\nTODO: provide better explanation for how to disambiguate'
```

## t2

### dewy/parser/t2.py:1

```text
Post processing steps on tokens to prepare them for expression parsing
```

### dewy/parser/t2.py:134

```text
keywords:
'loop', 'if', 'else', 'match', 'return', 'yield', 'break', 'continue',
'import', 'from', 'let', 'const', 'local_const', 'overload_only',

patterns:
flows # note that if-else-if/if-else-loop/etc. should all be bundled up into one higher level token
  <loop><expr><expr>
  <if><expr><expr>
<match><expr><expr>
<return>
<return><expr>
<yield>
<yield><expr>
<break>
<break><hashtag>
<continue>
<continue><hashtag>
<import><expr>
<import><expr><from><expr>
<from><expr><import><expr>
<let><expr>
<const><expr>
<local_const><expr>
<overload_only><expr>
```

### dewy/parser/t2.py:286

```text
non-exhaustive blacklist of some expressions involving juxtapose that are easy to catch and are not valid
This is mainly just a convenience to prevent enormous exponential blowup when dealing with certain ambiguous parses

If for some ungodly reason, a user wanted to overload a type to support these operations, parsing would still filter them out,
so the user would have to use more explicit syntax to get the effect, e.g. 
```dewy
# explicit multiplication
'some string' * 2  
# explicit call
$call('some string' (other arguments to call with))
# explicit indexing
$index((+) [2..10])
```
```

### dewy/parser/t2.py:17

```text
abstract base class for all juxtapose operators
```

### dewy/parser/t2.py:66

```text
`$` used for constructing predicate functions, e.g. `x => x >? 10` can be constructed as `$ >? 10`
```

### dewy/parser/t2.py:71

```text
Quantum Juxtapose: represents operator ambiguity at a given point. Mainly for vanilla juxtapose.
    E.g. without type information, a plain juxtapose could be a call, index, or multiply
    ```
    x = 1
    y = 2
    z = [3]
    
    sin(x)   # call
    x(y)     # multiply
    x[y]     # index
    (x)z     # index
    # etc.
    ```
```

### dewy/parser/t2.py:114

```text
checks if two operators are the same kind (ignoring span/position)
```

### dewy/parser/t2.py:188

```text
`$assert cond`, `$runtime_assert cond, message`, `$expect cond, message`, `$fail [message]`, `$breakpoint`.
```

### dewy/parser/t2.py:344

```text
For certain tokens, we alredy know which juxtapose (precedence level) they should have
    
    General Juxtapose Rules:
    - can always juxtapose atoms

    Range/Ellipsis Jux Rules:
    - can juxtapose any operator that is prefix or postfix
    - cannot juxtapose binary (only) operators (As well as flat and fail)
    
    Type-param Jux Rules:
    - does not occur next to operators
    - may only juxtapose on one side. prefer left side over right side

    Call/Mul Jux Rules:
    - does not occur next to operators

    Semicolon Jux Rules:
    - jux anything to it's left
    - cannot jux to right
```

### dewy/parser/t2.py:458

```text
Helper to recursively apply a function to the inner tokens of a token (if it has any)
    It is expected that `func` will call `recurse_into` with itself as the callable.
```

### dewy/parser/t2.py:492

```text
Remove whitespace tokens from the tokens list (recursively)
```

### dewy/parser/t2.py:499

```text
Insert juxtapose tokens between adjacent (atom) tokens if their spans touch (which indicates there was no whitespace between them)
    TODO: this is vaguely inefficient with all the insertions. If this is a performance bottleneck, consider some type of e.g. heap or rope or etc. data structure
          alternatively, just do 1 pass to find where juxtaposes go, and then insert them all at once.

    Note: this function is idempotent, so it can be called multiple times, e.g. before andafter grouping up tokens to the token list
```

### dewy/parser/t2.py:523

```text
Insert void tokens between any instances of `,,` or comma at the beginning or end of a context
```

### dewy/parser/t2.py:546

```text
`type` followed by `of` becomes the prefix operator `type of`: minting
    binds tighter than `&`/`|` (`type of Token & [text:string]` is
    `(type of Token) & [...]`), while the infix `of` of a generic bound
    (`<T of A & B>`) keeps its loose level.
```

### dewy/parser/t2.py:562

```text
`not` followed by a comparison operator becomes an inverted comparison operator
```

### dewy/parser/t2.py:576

```text
Convert any . operator next to a unary or binary operator into a broadcast operator
```

### dewy/parser/t2.py:589

```text
Convert any combined assignment operators into a single token
```

### dewy/parser/t2.py:610

```text
`(op operand)` becomes the lambda `(_ => _ op operand)`, spelled out in tokens.
```

### dewy/parser/t2.py:625

```text
convert (op) into an identifier token for that operator
```

### dewy/parser/t2.py:641

```text
convert any `$` identifiers into placeholder tokens
```

### dewy/parser/t2.py:651

```text
Whether a newline separates two tokens: a `return`'s (or `yield`'s) value
    must start on the keyword's line — the one place a line boundary is
    structural, so `if done return` followed by a statement on the next line
    does not return that statement's value.
```

### dewy/parser/t2.py:659

```text
Return True if `token` is a keyword whose name is in `stop`.

    `stop` is a set of keyword names that act as delimiters for `collect_expr`/`collect_chunk`:
    when collecting an expression slice, we stop *before* these keywords so the caller can
    interpret them structurally (e.g. `else`, `from`, `import`, `loop`).
```

### dewy/parser/t2.py:728

```text
`collect_chunk` returned no tokens when `collect_expr` expected one.
    This mostly happens when a delimited construct (flow keyword, block, file, etc.)
    ends before the next expression is present.
```

### dewy/parser/t2.py:797

```text
Collect a single expression chunk starting at `start`. A chunk is basically an atom surrounded by prefix and postfix operators.

    Chunk grammar (informal):
      chunk := prefix_like* atom postfix_like*

    Returns:
      (chunk_tokens, next_index)
```

### dewy/parser/t2.py:841

```text
Collect `$assert expr [, expr]` (and `$runtime_assert`, `$expect`) into one atom.

    The argument is collected like any expression, then split at its top-level
    comma: the directive form owns that comma (see `Directive`).
```

### dewy/parser/t2.py:914

```text
The `void` `insert_comma_voids` puts after a trailing comma.
```

### dewy/parser/t2.py:919

```text
Collect a single expression chain starting at `start`.

    This does not parse precedence; it only groups tokens into a contiguous chain that
    is directly consumable by a later expression parser (Pratt, etc.).

    Chain grammar (informal):
      expr := chunk (infix_op chunk)*

    Stops before:
    - any keyword in `stop_keywords`
    - a semicolon token

    Returns:
      (expr_tokens, next_index)
```

### dewy/parser/t2.py:968

```text
Collect a single flow arm (if/loop/match) into a `FlowArm`.

    The result is a mostly-unstructured "syntax skeleton":
      FlowArm.parts := [Keyword, expr, Keyword, expr, ...]

    Notes:
    - This function consumes the arm's starting keyword at `tokens[start]`.
    - It does not include `else` (that delimiter is handled by `collect_flow`).
    - Each `expr` entry is a `list[t1.Token]` produced by `collect_expr`.
```

### dewy/parser/t2.py:994

```text
Collect an entire flow expression (if/loop/match with optional else chains).

    Structure:
    - `Flow.arms` is a list of `KeywordExpr` tokens (each arm retains its own keywords).
    - `Flow.default` is either None or a Chain for the final default expression.

    `else` is treated as structural and is consumed but not stored.
```

### dewy/parser/t2.py:1029

```text
Collect a keyword-driven expression into a single atom token.

    Returns:
      (atom_token, next_index)

    The returned atom token is either:
    - `Flow` for flow keywords (`if`, `loop`, `match`)
    - `KeywordExpr` for other keywords

    `KeywordExpr.parts` is a "syntax skeleton" alternating between structural keywords
    and collected expression token lists, e.g.:
      - `return <expr>`              -> [return_kw, expr]
      - `from <expr> import <expr>`  -> [from_kw, expr, import_kw, expr]
```

### dewy/parser/t2.py:1107

```text
Walk `tokens` and replace any keyword-started expression with a single atom token.

    This is a post-tokenization bundling pass. It is recursive: blocks and interpolated
    strings are traversed, so keyword expressions are bundled at all nesting levels.

    `else` is not bundled as a standalone atom; it is only consumed structurally by
    `collect_flow`.
```

### dewy/parser/t2.py:1138

```text
convert list[Token] into list[Chain] in place
```

### dewy/parser/t2.py:1156

```text
apply postprocessing steps to the tokens
```

### dewy/parser/t2.py:1164

```text
apply postprocessing steps to the tokens. Converts list[Token] into list[Chain] in place
```

### Pending implementation and design markers

```text
125: # TODO: not sure how op equals should behave for QOperators. maybe just always return False? or check if inners are all equal modulo ordering
126: pdb.set_trace()
314: (MultiplyJuxtapose, t1.Integer),  # TBD if keep these two cases or not. right-side jux-mul for numbers is rare and not really great style
488: # else no inner tokens. TODO: would be nice if we could error if there were any unhandled cases with inner tokens...
501: TODO: this is vaguely inefficient with all the insertions. If this is a performance bottleneck, consider some type of e.g. heap or rope or etc. data structure
```

## p0

### dewy/parser/p0.py:1

```text
Initial parsing pass. A simple pratt-style parser
```

### dewy/parser/p0.py:106

```text
expressions that need to make sense given precedence table/rules:

-x-y      => (-x) - y
/x-y      => 1/x - y
/x/y      => (1/x)/y
-x/y      => 0 - x/y
-x^2      => -(x^2)
~A|B?     => (~A)|(B?)
-sin(x)^2 => -((sin(x))^2)
-a(x)^2   => -(a*(x^2))
```

### dewy/parser/p0.py:23

```text
quantum int for dealing with precedences that are multiple values at the same time
    qint's can only be strictly greater or strictly less than other values. Otherwise it's ambiguous
    In the case of ambiguous precedences, the symbol table is needed for helping resolve the ambiguity

    Optionally, qints may store some payload or metadata per each value by passing in a dict[int, T] rather than a set[int]
```

### dewy/parser/p0.py:243

```text
either a binary node, a prefix node, or a postfix node
```

### dewy/parser/p0.py:261

```text
node for flat operators that all combine to a single operation rather than a tree (e.g. comma separated expressions)
```

### dewy/parser/p0.py:297

```text
all non-container Tokens just get wrapped up into an Atom AST
```

### dewy/parser/p0.py:302

```text
A directive form: `$assert cond`, `$runtime_assert cond, message`, `$expect cond, message`,
    `$fail [message]`, `$abstract <type of …>` (its mint as the condition; see `t2.Directive`),
    and `$breakpoint` (no condition: stop here and show the live bindings).
```

### dewy/parser/p0.py:312

```text
transformation of t2.Chain that can be used at this phase. Comprises a single expression
```

### dewy/parser/p0.py:411

```text
simple bottom up iterative shunting-esque algorithm driven by pratt-style binding powers
    
    Steps:
    1. collect all AST nodes
    2. identify if node shifts left, right, none based on binding power of adjacent operators
    3. apply reductions to "fulfilled" operators:
        TODO: note adjust the conditions mentioned here now that we are operating on Chains, not list[Token]
        - binary operators that receive both left and right
        - unary prefix operators that receive right (if the thing to the left cannot end an expression (i.e. it is an operator, but not possibly a postfix operator))
        - unary postfix operators that receive left (simpler since no postfix operators are also binary operators)
        - flat operators that are a full alternating sequence of (arg, op, arg, op, ... op, arg) with no connecting operators on either side (if leftmost and rightmost operators shifted inward, there shouldn't be any connecting operators)
        - for fail associativity operators, treat like regular binary, but if a child AST would have the same operator as the parent node, error out
    4. repeat until no new reductions constructed


    tricky examples
    10*-5   [<int 10>, <op *>, Node(-, None, 5)]
    10?-5   [<int 10>, <op ?>, Node(-, None, 5)] -> [Node(?, 10, None), Node(-, None, 5)]

    --x vs y--x
    <op -><op -><id x>
    <id y><op -><op -><id x>

    10? >? -x + /y  [<int 10><op ?><op >?><op -><>]
```

### dewy/parser/p0.py:522

```text
repeatedly apply shunting reductions until no more occur. modifies `tokens` in place
    
    Each chain in the list is an ambiguous alternative parse (initially there should only be one, but the list can grow if ambiguous operators are present)
    If multiple chains are present at the end, an Ambiguous node is returned containing all the candidates
    Otherwise the parsed AST is returned
```

### dewy/parser/p0.py:604

```text
apply a shunting reduction. modifies `chains` in place (potentially adding new lists in the case of ambiguities)
```

### dewy/parser/p0.py:863

```text
determine if the operator (which is both prefix and binary according to the precedence table) could actually be a binary operator in its current position
    To be a binary operator, there would need to be a left operand that it connects to.
    The parsing rule is that when an operator could be prefix or binary, it always picks binary.

    example cases
    (looking at `/` next to `y`)
    x/y      -> True.  `/` could take `x` as a left operand
    x-/y     -> False. `-` is binary, thus making `/` a prefix
    x?/y     -> True. `?` is postfix only, therefore `/` could be binary
    /y       -> False. `/` has nothing to the left to connect to
    x+`/y    -> False. backtick (`) cannot connect to left `+` so backtick must be prefix, and therefore `/` cannot be binary
    x+``/y   -> False. backtick (`) cannot connect to left `+` so backtick must be prefix, and therefore `/` cannot be binary
    x`-/y    -> False. binary `-` means the `/` must be a prefix
    x`~/y    -> False. `~` left of `/` is prefix only, therefore `/` must also be prefix
    x`?/y    -> True. backtick (`) is postfix to `x`, and `?` is postfix only. Therefore `/` could be binary
    x`````/y -> True. all backticks (`) are postfix to `x`
    x``+``/y -> False. `+` in middle blocks right backticks (`) from connecting to `x`, so they must be prefixes on `y`
```

### dewy/parser/p0.py:920

```text
same idea as could_be_binop, but for postfix operators
```

### Pending implementation and design markers

```text
48: if not isinstance(other, int): return NotImplemented
52: if not isinstance(other, int): return NotImplemented
55: if not isinstance(other, int): return NotImplemented
58: if not isinstance(other, int): return NotImplemented
59: if other == 0: raise RuntimeError(f'Currently, multiplying by 0 is not allowed. got {self}*{other}. TBD if this was reasonable (would return int(0) instead of qint)')
63: if not isinstance(other, int): return NotImplemented
66: if not isinstance(other, int): return NotImplemented
127: (Associativity.postfix, ['`']), #TODO/Note: at the moment, prefix vs postfix precedence of (`) is backed into the algorithm, and wouldn't listen to the ordering in the table...
170: # TODO: adjust so operators have left and right precedence levels to support pratt parsing
266: # TBD how to set this up since don't have a whole AST when we see ambiguity, just reductions in a list
267: # perhaps instead keep the reductions + AST/tokens they tend over
319: # TODO: this error message is suboptimal. e.g. `1..,2,..3` gives a wacky error message that doesn't really make sense
333: # TODO: this hint isn't very helpful.
367: # TODO (long term): probably would be better to somehow point to the docs...
407: # TODO: make this return a single block AST instead of a list of ASTs...
418: TODO: note adjust the conditions mentioned here now that we are operating on Chains, not list[Token]
443: # TODO: consider making AST container types for each of the items that recursed into so we aren't shoving ASTs where tokens are expected...
543: # TODO: this could be a user error, e.g. `A&;b&c`. Do full error reporting
544: # perhaps do: for each item in list, if is op, determine what kinds of reductions it could participate in and show error listing them vs what was present
848: pdb.set_trace()
857: # TODO: a possibly cleaner approach than doing all this left checking of operators:
916: # TODO: note that currently same symbol prefix and postfix operators always prefer the postfix one (regardless of ordering in the precedence table)
```
