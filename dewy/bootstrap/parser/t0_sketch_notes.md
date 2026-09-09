# t0 sketch: next implementation slice

The sketch now includes immutable base specifications, metatags, shift symbols, ordinary/type/based block openers and closers, a nonempty context stack, delimiter-pair indices, mismatched-delimiter reports, and EOF validation. The next slice adds ordinary/raw/template quoted strings, simple and Unicode escapes, interpolation, and exponent markers. Based strings, heredocs, and rest-of-file strings remain ahead.

## Compiler review (c1f82c51 and 7113df93)

The overall approach fits the agreed design: immutability participates in the
record type, writes are checked along access paths, defaults and explicit fields
produce proof obligations, and sibling relations feed the existing bounds
analysis. The immutable-record and constructor test modules pass (18 tests).
Two composition holes remain; neither requires changing the representation.

1. **Immutable nominal descendants can escape through writable ancestors.**
   `TypeSystem.is_subtype` in `dewy/semantic/ty.py` permits nominal descent without
   checking the immutable qualifier. This allows a mutable-place call to change
   the original immutable value. The following compiled and returned **99**:

   ```dewy
   P = type of any & [n:int64]
   C = type of P & const []
   let bump = (@p:P) => { p.n = 99 }
   let main = ():>int64 => { let c = C[1] bump(@c) return c.n }
   ```

   Check mutability compatibility before accepting nominal descent/carrying,
   including mutable-place parameter compatibility. This call must be rejected.

2. **Structural intersection drops the immutable qualifier.**
   `_intersect_object_types` in `dewy/semantic/check.py` rebuilds an `ObjectType`
   without `immutable`, so this mutation is accepted:

   ```dewy
   A:type = const [n:int64]
   B:type = A & [extra:int64]
   let main = ():>int64 => { let b:B = [1 2] b.n = 99 return b.n }
   ```

   Preserve the immutable contract through intersection, or reject incompatible
   writable requirements; never silently erase it. This matters especially when
   the inherited fields carry sibling invariants.

The compiler implementation is deliberately left unchanged by this sketch task.
Both reproductions should become compiler regression tests when those fixes land.

### Additional issues exposed by the next slice

- **Sequential subtype tests can use the wrong runtime representation.** This
  small native reproduction segfaults (exit `-11`) instead of returning 42:

  ```dewy
  T = $abstract type of any & [n:int64]
  A = type of T
  B = type of T & [a:A]
  let inspect = (x:T):>int64 => {
      if x is? A { printl"A" }
      if x is? B return 42
      return 0
  }
  let main = ():>int64 => inspect(B[1 A[2]])
  ```

  In the token-dumping test, the Number check loads the brand from an object
  pointer, but the subsequent ExponentMarker check treats that same pointer as
  a union cell. Preserve the physical representation across narrowing, rather
  than inferring a different layout from a narrowed view. The test dumper uses
  an independent function for the exponent check. Exponent probing itself takes
  only a boolean observation about the previous token, so it does not need an
  optional nominal-family value.
- **Named nonempty-string refinements are not recovered on nested field reads.**
  `QuoteEnd.text` is declared `nonemptystring`, but
  `ctx.ending.text.length` is treated as possibly zero. The sketch asserts the
  promised invariant explicitly before building a closing candidate. This check
  can go away once those field facts survive reads. A related slice bound is
  made explicit at quote-opener construction.
- **Union-valued match bindings with extracted conditions remain limited.** A
  local `frame:NestedContext = match o.mode { ... }` failed with `union flow
  condition requiring extracted statements`. The sketch instead constructs each
  token and its corresponding frame together in a returning match arm, which
  also makes their relationship clearer.
- **`Report.warn` leaves printing routed to stderr.** `Report.render` calls
  `_set_output_stderr(true)` without restoring the previous destination.
  After a lone-CR warning, even a subsequent ordinary `printl` goes to stderr.
  Restore the previous output destination around nonfatal rendering. The lexical
  warning test checks the records on either stream and explicitly notes this
  existing library issue; it does not claim output routing is fixed.

## Compiler support status

- [x] Immutable record expressions, nominal composition, and nested write checks
  for the direct forms used here (subject to the composition holes above).
- [x] Construction-time sibling-field proofs, including positional defaults,
  explicit radix overrides, and relations known on field reads.
- [x] Alphabet bounds propagated into the radix default.
- [x] Local object-valued matches and distinct bindings for repeated local names.

The expanded sketch compiles with the explicit nonempty-delimiter assertion and
returning string-construction arms described above. Its compiler and library
dependencies still have the independently reproduced issues listed here.

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
- Specialized no-match diagnostics (including the hosted shift-in-type history heuristic and illegal control characters) remain ahead. This slice reports a generic no-match error instead.

## Added string/exponent behavior

- `QuoteEnd` stores the exact nonempty delimiter, normalized during recognition.
  Even quote runs split in half for empty strings, matching hosted t0.
- The ordinary/raw/template frames share delimiter recognition but keep their
  lexical eligibility separate. Raw text includes backslashes and braces;
  ordinary strings interpolate `{...}`, templates interpolate `${...}`.
- Escapes recognize source spans only; decoding belongs to t1. Both `u` and `U`
  require four hexadecimal digits unless followed by a braced expression.
  Byte escapes `x`/`X` and incomplete escapes produce absolute-span errors.
- Parametric Unicode escapes push a curly block defaulting to hex. Closing it
  restores the enclosing string frame; nested ordinary blocks reset to decimal.
- Quote closers reuse the existing pair/action mechanism. EOF reports include
  unclosed strings as well as any interpolation or ordinary block still open.
- `ExponentMatch` retains a nested `NumberMatch` and resolves its base once.
  Eligibility uses the immediate previous output token, not context-owned
  history. Whitespace breaks eligibility, matching the hosted implementation.
  Number/ExponentMarker/Symbol still beat Identifier on equal-length ties.

## Validation scenarios

`tests/python_misc/test_bootstrap_t0_sketch.py` compiles the actual sketch with
a small token-dumping entry point and passes **29 tests**: hosted token/span/base/
exponent/pair comparisons, malformed inputs, grapheme/CRLF spans, and lone-CR
warnings. The original sketch CLI also compiled and ran a template string with
an interpolated exponent expression successfully. The existing immutable-record
and constructor modules passed **18 tests** separately. These results do not
cover the deferred string forms or repair the compiler review findings above.

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


Additional cases for this slice: empty and multi-quote strings; raw backslashes
and braces; template interpolation versus literal braces; nested quoted strings
inside interpolation; escaped delimiters; fixed and braced Unicode escapes;
resuming string text after a block; malformed/unfinished escapes; unclosed strings
with unclosed interpolation; `1e10`, `1 e10`, `1e+10`, and a prefixed exponent.
