# t0 sketch: next implementation slice

The sketch now includes immutable base specifications, metatags, shift symbols, ordinary/type/based block openers and closers, a nonempty context stack, delimiter-pair indices, mismatched-delimiter reports, and EOF validation. Strings and exponent markers remain unimplemented.

## Compiler support to implement

- **Immutable record type expressions:** resolve `const [...]` in type positions, including structural aliases and `type of any & const [...]`. It denotes runtime values with immutable contents, not compile-time evaluation. Preserve the qualifier through construction, copies, nominal composition, unions, fields, function boundaries, and containers. Reject conflicting writable contracts.
- **Transitive mutation checking:** reject direct/nested field writes, dictionary updates and mutating methods, and mutable-place projections through an immutable record. Independently copied container contents may be mutable; replacing a mutable binding with a complete valid record remains legal. Existing per-field const machinery is a starting point, not proof that all these paths work.
- **Construction-time sibling-field invariants:** bind earlier fields while checking later defaults and refinements. Prove `radix =? alphabet.length` for both omitted and explicitly supplied radix arguments, including positional records inside the total dictionary. Retain the relation when the record is read. Initially restrict these invariants to immutable records.
- **Bounds in field-default checking:** carry the alphabet's declared length bound into `alphabet.length`, so the default proves that it fits `uint8`. This is distinct from supporting defaults syntactically, which already exists.
- **Bound union-valued flow results:** lower `token:Token = match ...` inside `finish`, including branches constructing different concrete token types. The existing support for distributing flow results through returns does not yet handle this local binding (`no udewy flow temporary representation for Token`).

The full source parses on the current hosted parser. Semantic checking first stops at `BaseInfo:type = const [...]` with `KeywordExpr in type position is not yet handled`. This is intentionally a feature-targeting sketch, not a currently compilable replacement. An in-memory compatibility projection, removing the new const qualifiers and changing the dependent radix to an `int64` default, passed semantic checking and reached the bound-flow lowering failure above. That experiment does not validate the new immutable semantics or runtime behavior. Additional downstream implementation gaps may surface later.

## Representation and behavior

- `BaseInfo` stores the ordered canonical alphabet. Radix is derived and checked; aliases and padding do not increase it. `case_sensitive` has the opposite polarity from the old field; all table rows have been adjusted.
- `NumberMatch` retains the base used for scanning. The already-validated first digit is consumed before the remaining-digit loop, making progress explicit.
- Opening candidates describe a block kind and its base. Ordinary blocks and type bodies reset to decimal; based blocks set their own base.
- Closer candidates retain the narrowed, immutable opening frame. `finish` validates the winning closer and returns a token plus `Keep`, `Push`, or `Close`. It never receives a broad current context or mutates the stack.
- All diagnostic spans are absolute, including comment errors, number errors, selection errors, earlier opening locations, and EOF pointers. The driver does not shift reports. Whitespace candidates retain local offsets until the winning candidate's warning reports are constructed.
- `tokenize` returns `[tokens pairs]`. Pairs are append-only records of opening and closing token indices, in closing order. t1 will need to use these indices (or a lookup built from them) instead of Python's mutual token references. Tokens keep the sketch's full-source-plus-span convention.
- Square and round delimiters can mix for ranges; curly braces must match. Based blocks require `]`. This gives a diagnostic for `0x[1)` where hosted `RightParenthesis.action_on_eat` currently falls into an internal error.
- High-base blocks accept unprefixed numbers, matching hosted t0. Explicitly prefixed number literals above base 16 are errors. Number wins an equal-length tie against Identifier, following the current hosted precedence policy.
- Shift tokens compete with angle delimiters in root/block contexts. They are not probed directly in a type body. A symbol such as `>?` can beat a type closer; its losing candidate must never pop the stack.
- Specialized no-match diagnostics (including the hosted shift-in-type history heuristic and illegal control characters) remain ahead, along with strings and exponent markers. This slice reports a generic no-match error instead.

## Validation scenarios once compilation is available

Compare kinds, token text, resolved bases, and pair indices against hosted t0; normalize Python code-point offsets against Dewy grapheme offsets for Unicode.

| Source | Expected property |
| --- | --- |
| `[1..3)` and `(1..3]` | Mixed square/round delimiters produce a pair. |
| `{[1](2)}` | Three pairs in closing order; root remains at EOF. |
| `0x[ff (10) ff]` | Number bases are hex, decimal, hex after nested context restoration. |
| `0r[z]` | Unprefixed high-base number accepted in its based block. |
| `0r123` | Explicit high-base number error. |
| `0zXE 0zxe 0xAf 0tT` | Case aliases and balanced ternary recognized. |
| `$name $` | Metatag followed by standalone symbol. |
| `a << b` | ShiftSymbol wins over the one-character type opener. |
| `<a >? b>` | `>?` does not pop the type frame; final `>` does. |
| `<(a >> b)>` | Nested ordinary block admits shifts inside a type body. |
| `[}` and `{]` | Mismatch reports point to both opener and closer. |
| `0x[1)` | Expected `]`, not an internal error. |
| `prefix { [` | EOF report points to both unclosed openers and EOF. |
| `prefix #{ nested #{ comment }#` | Remaining comment opener has an absolute span. |
| Whitespace with lone CR and CRLF | Only lone CR warns, after winner selection. |

Immutable-record checks should also reject an inconsistent explicit radix, oversized/too-short alphabets, radix/alphabet assignments, nested dictionary mutation, and mutable-place access through `BaseInfo`, including copies and function/container boundaries. A runtime alphabet satisfying the bounds and whole-value replacement of a mutable `BaseInfo` binding should be accepted.
