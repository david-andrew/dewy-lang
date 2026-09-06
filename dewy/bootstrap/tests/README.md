# Bootstrap parser inputs

Dewy source files for building the bootstrap tokenizer and parser (`t0.dewy`,
then `t1`, `t2`, `p0`) up to parity with the Python pipeline in `dewy/parser/`.
Each file exercises one family of tokens, in roughly the order a tokenizer
grows; `09_kitchen_sink.dewy` mixes everything the way a real module does.
All of them (except `04b`) tokenize and parse through the Python `p0`, so the
same file is an input for every stage.

| file | exercises |
|---|---|
| `00_comments.dewy` | line comments, nested block comments, a comment at EOF without a newline, `#{` inside a line comment |
| `01_whitespace_and_identifiers.dewy` | spaces/tabs/newlines, identifier characters (ASCII, Greek, math letters, `_ ! °`), decorations anywhere (superscripts, subscripts, primes), case-insensitive booleans, names that look like keywords |
| `02_numbers.dewy` | integers with `_`, every numeric base prefix up to 16, reals, `e`/`p` exponents, units by juxtaposition, ranges incl. the stepped `1,3..10` and open bounds |
| `03_strings.dewy` | quotes of odd length, escapes, `{}` interpolation, raw `r"…"`, template `t"…${}"`, based strings (`0x"…"`, base 64), heredocs (plain, raw, template, symbolic delimiter) |
| `04_operators.dewy` | every operator spelling, inverted comparisons (`not =?`, `not in?`), shifts, combined assignment, broadcast `.+`, operator functions `(+)`, partial operators `(<? 10)`, the `$` placeholder, `;` |
| `04b_reserved_symbols.dewy` | symbols the tokenizer knows but the parser rejects (`<=>`, `??`): tokenizer-only |
| `05_blocks.dewy` | `() [] {} <>`, range blocks `[a..b)`, based blocks `0x[…]`, type blocks holding `>?`/`<?` operators, nesting, empty blocks, comments inside blocks |
| `06_keywords_and_metatags.dewy` | `let const local_const overload_only import from if else loop match return yield break continue`, the directives `$assert $runtime_assert $expect $fail $breakpoint $prototype $test $target $abstract`, an unknown metatag |
| `07_functions_and_types.dewy` | function literals (defaults, `...rest`, keyword-only `...`, position-only `<>`, generics, refined results, type facts, predicates), calls (keyword, juxtaposition, partial evaluation), type aliases, minted types, unions/intersections/negation, objects |
| `08_flow_and_data.dewy` | flows as statements and expressions, loop captures, unpacking, containers and their methods, slices, `match` with type arms, chained comparisons |
| `09_kitchen_sink.dewy` | a tokenizer module in the shape of `t0.dewy` itself: docstring, imports, minted token family, facts, `match`, `main` |
| `10`–`12` rest-of-file strings | `$"""`, `$r'''`, `$t"""` — an opener with no closer; the file ends inside the string |

## Reference output

`tools/token_stream.py` prints what the Python stages produce, one token per
line, so the bootstrap's output can be diffed against it:

```
python tools/token_stream.py dewy/bootstrap/tests/03_strings.dewy               # t0 tokens: class, span, source
python tools/token_stream.py dewy/bootstrap/tests/03_strings.dewy --stage t1    # post-tokens, blocks nested
python tools/token_stream.py dewy/bootstrap/tests/05_blocks.dewy --stage t2     # chains, keyword expressions, juxtaposition
python tools/token_stream.py dewy/bootstrap/tests/08_flow_and_data.dewy --stage p0   # the AST
```

`python -m dewy.parser.t0 FILE` (and `.t1`, `.t2`, `.p0`) draw the same stages
as source-annotated reports.

## Things to know while matching

- Longest match decides; `LineComment.eat` refuses `#{` so a block comment is
  the only candidate there (`dewy/parser/t0.py`).
- Numeric literals stop at base 16; bases 32/36/64 exist only as based strings.
- A rest-of-file string consumes to EOF, so files `10`–`12` end without closers.
- `(op)` alone is an operator function; `(op x)` is a partial operator; both
  are rewritten before parsing (`t2.make_op_functions`, `t2.make_partial_operators`).
- Whitespace tokens are kept through t1: juxtaposition (`f x`, `20N`, `xs[i]`)
  is decided from where whitespace is and is not.
