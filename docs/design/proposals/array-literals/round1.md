# Array literals — round 1

**BLUF.** Separator levels, as already decided, are the whole rank rule for a grid of scalars, and a one-level list stays 1-D. A comprehension does not read those levels: it splices the values it already expresses, flat, and a matrix comprehension is the one Dewy already writes, `[loop y in rows [loop x in cols f(x y)]]`. Rectangular nests and `[xs ys]` / `[xs ; ys]` are that same n-D array, stacked on a new leading axis; ragged nests are a compile error unless the expected type is `array<array<T>>`. `[[1 2 3]]` is 1×3 and `[[1] [2] [3]]` is 3×1. The parser change is a linear gap scan inside the array-literal reader; collapse is a linear check after that, with no backtracking.

## Normative rule

1. **Where `;` means what.** Directly in the element list of an array literal `[…]`, `;` is a separator. In a record literal, a dict literal, a `{…}` block, a `(…)` group, and every statement list, `;` discards the value before it. Attached and unattached spacing do not differ. Index brackets, slice brackets, and type arguments are not array context: a `;` there is an error (`xs[1; 2]` does not discard and does not index). A `[…]` is a record if it has a `name=` field, a dict if it has a `->` entry, otherwise an array.

2. **Discarding inside an array.** Discard in a group or a block, which are not array context. The group or block contributes the values it still expresses. One that expresses nothing contributes no element. `[1 (2;) 3]` is `[1 3]`. `[1 2 (f();) ; 3 4]` is the 2×2 grid of `1 2` and `3 4`. A discarded dict entry or record field is not stored: `["a" -> 1; "b" -> 2]` is the dict `"b" -> 2`.

3. **One gap, one level.** A gap is the whitespace, comments, and `;` tokens between two elements of the same element list. Spaces are level 0. A run of *k* `;` is level *k*. A run of *n* line breaks, after the removals in rule 5, is level *n*. A gap that contains several of these takes the highest level. Consecutive `;` are one gap, not empty rows: `[1 ;; 2]` is a single level-2 gap. A separator with no element on either side is an error (`[;]`, `[; 1]`, `[1 ; ; 2]` is not this — that is one level-2 gap).

4. **Which level is dimension 0.** Let *m* be the lowest level among the gaps that sit between elements. Subtract *m* from every between-element gap. Dimension 0 is that lowest level; each higher renormalized level is the next dimension. A list that uses only one level is 1-D, whatever that level was. `[10⏎20⏎30]`, `[1; 2; 3]`, and `[1 ;; 2]` are all 1-D. `[1 2⏎3 4]` and `[1 2 ; 3 4]` are `length=[2 2]`. After renormalization the levels present must be `0 .. max` with none missing. `[1 2 ;; 3 4]` (levels 0 and 2) is an error. A hole is judged only after renormalization: `[1 ; 2 ;; 3]` is levels `{1, 2}`, which renormalize to `{0, 1}` and then fail as ragged, not as a skipped level.

5. **What is not a gap.** The break after `[` and the break before `]` are not gaps (`[⏎1 2⏎]` is `[1 2]`). A comment-only line (`# …` or a `#{ … }#` line with no element) is deleted before breaks are counted, so it neither separates nor makes a blank line. A break inside a nested `[]`, `()`, or `{}` belongs to that nest, not to the outer list. A break that the expression parser already consumes as part of one element is not a gap, including a break before or after a binary operator (`1 +⏎2` is one element). A `\` at the end of a line cancels that break everywhere, including in an array, so a wrapped vector stays 1-D. The formatter preserves blank lines inside `[…]`; they are significant.

6. **Trailing separator.** A trailing separator is a gap after the last element, with nothing after it. It does not renormalize with the between-element gaps. If its level is exactly one higher than the highest between-element level (or exactly 1 when there is a single element and no between-element gap), it adds one leading axis of length 1. If it is higher than that, a level was skipped and the literal is an error. If it is not higher, it only closes the last group. `[1 2 3 ;]` is `length=[1 3]`. `[1 ; 2 ; 3 ;]` is 1-D (the trailing `;` is the same level as the gaps). `[1 ;;]` is an error. `[1 ;]` is `length=[1 1]`.

7. **Shape.** Axes are outermost first. `length=[2 3]` is 2 rows of 3. Storage order is row-major. For rank ≥ 2, `.length` is that shape. A true 1-D array is not rank-1 n-D: its `.length` is the element count, a number. A literal becomes 1-D exactly when rule 4 says so. It becomes n-D when the renormalized grid has rank ≥ 2, when rule 6 adds an axis, when a shape ascription says so (rule 10), or when rule 9 collapses rows. Equal-length rows are required at every axis. The wording already in the reader stands, with a real plural: "the rows of an array literal must have the same size: this one has 1 element, the first has 2." Blocks above rows use "blocks" and "rows"; higher axes use "parts". A missing level reads "skipped separator level: levels 0 and 2 appear, and level 1 does not." A trailing separator that skips a level reads "skipped separator level: the trailing separator is level 2, and a single element has no level 1 under it."

8. **Comprehensions splice flat.** A `loop`, `if`, or `match` written as an element of `[…]` contributes the values its body expresses, in order, as a contiguous run of cells. Spacing, blank lines, and `;` inside that body are not dimensions. A brace-less body is one statement, as elsewhere. A braced body is a block: `;` inside it discards, and the values the block expresses are the run. `[loop x in xs x]` is 1-D. `[loop x in xs {1.0 x x^2}]` is 1-D with three values per input, on one line or many. A filtered iteration contributes nothing: no cell and no gap. Nested loops in one body append in index order into that same flat run. An inner `[…]` is one value, not a splice of its contents.

   The gap before the comprehension applies before its first cell. The gap after it applies after its last cell. Cells inside the run are separated at level 0. The comprehension invents no axis. `[0 loop i in [1..3) i]` is `[0 1 2]`. `[1 2 ; loop i in [0..2) i]` is `length=[2 2]` when the run has length 2, and a ragged-row error when it does not. `[loop i in [0..3) i ;]` is the trailing-separator form of that run: `length=[1 3]`.

   A matrix comprehension yields a row per iteration, the idiom already in the language:

   `[loop y in [0..h) [loop x in [0..w) f(x y)]]`

   Each iteration contributes one array. Rule 9 makes the rectangular result `length=[h w]`. A brace block that yields several scalars does **not** become a row; `[i 0]` does, `{i 0}` does not.

9. **Nested brackets and array-valued cells are one n-D array when they are rectangular.** Parsed structure stays nested. The checker then collapses. If every cell of a literal is an array and those arrays have one common shape, the literal is an n-D array whose leading axes are the outer grid and whose remaining axes are that common shape. This is a stack on new leading axes, not an element-wise concatenation (`[xs... ys...]` stays that). It does not matter whether the outer grid used spaces, line breaks, or `;`: one level renormalizes to a leading axis of that length, so `[xs ys]`, `[xs ; ys]`, and a one-per-line list of equal rows are the same stack. `[[1 2] [3 4]]`, `[1 2 ; 3 4]`, and the two-line layout are all `length=[2 2]`. `[[1 2 3]]` is `length=[1 3]`. `[[1] [2] [3]]` is `length=[3 1]`. `[[[1 2] [3 4]] [[5 6] [7 8]]]` is `length=[2 2 2]`.

   Cells must agree. A scalar mixed with an array is an error ("an array literal mixes an array with a scalar; spread the array (`xs...`) or wrap the scalar"). Different shapes are an error ("these rows have different lengths ({a} and {b}); make them equal, or give this the nested type `array<array<…>>`"). They do not silently become a nested array.

   Collapse does not apply when the expected type is a nested array (`array<array<T>>`, any depth). Then the literal stays nested, raggedness included, and `.length` is the outer count. A bare literal with no expected array type collapses when rule 9's shape test passes. A spread splices elements at level 0 and is an error in a literal that also has a higher separator level, because its length is not a static row width. `xs...` of an n-D array splices along the outermost axis.

10. **Shape ascription and `new`.** An expected `array<T length=…>` whose element count equals the literal's cell count accepts the literal. `let c:array<int64 length=[3 1]> = [1 2 3]` is the column. The bare literal `[1 2 3]` stays 1-D. `new` on an n-D array, including the result of rule 9, inserts one axis of length 1 at that position (`m[new]` leading, `m[.. new]` trailing). `new` on a true 1-D array or a nested array keeps today's meaning: `xs[new]` is `[xs]`, `xs[.. new]` wraps each element. Those results are nested, not n-D, until something collapses them.

11. **Dewy keeps true 1-D arrays.** Nothing in rules 4–9 turns `[1 2 3]`, `[1 ; 2 ; 3]`, or a one-per-line list of scalars into 1×N or N×1. The explicit rank-2 forms are rule 6 (`[1 2 3 ;]`), rule 9 (`[[1 2 3]]`, `[[1] [2] [3]]`), and rule 10.

## Answers

### 1. Comprehensions

Loop capture ignores separator levels and is a flat splice. That is not a special case bolted on beside the separator rule. The element list is the only place levels exist, and a loop body is not an element list: a brace-less body is one statement, a braced body is a `{…}` block, and the decision already makes `{…}` discard context. Reading spaces inside the body as columns would invent a second grammar and would make a newline inside `{1.0 x x^2}` change the rank of a form the language already defines as flat.

The two compose. Scalar capture fills cells of the surrounding grid (rule 8). A comprehension that yields row arrays builds the matrix through collapse (rule 9), which is the grid idiom already documented. Filters drop iterations. Several comprehensions are several runs in one cell stream. A comprehension never adds an axis by itself; a trailing `;` after it is rule 6 applied to the finished run.

Rejected: making the body a miniature literal (`[loop i in 0..n i i*2 ;]` as n×2). It fights the one-statement body, it needs a new rule for which `;` belongs to the body, and braces already have a meaning. Also rejected: Julia's `for i in rows, j in cols` as new syntax. Nested `[loop y [loop x …]]` already reads as rows, and `and` is lockstep.

### 2. Nested literals and n-D

They are one value whenever the nest is rectangular, and two types when the programmer asks for a real array of arrays.

Keeping every nest nested, and stacking only `[xs ; ys]`, does not survive the decided rule that a line break and a `;` are the same level. After renormalization `[xs ys]`, `[xs ; ys]`, and a one-per-line list are the same one-level list. They have to agree. The useful agreement is the stack Dewy already computes for `[xs ; ys]` (`__array2_rows` / `__array_stack`), extended to every rectangular nest, which is also what NumPy does with `array([[1,2],[3,4]])` and what the existing grid comprehension should have produced for linear algebra.

The unsafe version of that agreement is "rectangular becomes n-D, ragged quietly becomes nested." Adding one element would change the type. Ragged is an error with a fix-it that writes `array<array<T>>`. The annotation is the straightforward adjustment, and it is how a rectangular list of vectors keeps independent rows (`push`, ragged-later, `.length` as a count).

`[[1 2 3]]` and `[[1] [2] [3]]` are the explicit 1×N and N×1 literals. Extra brackets add a leading axis only because rule 9 stacks one row, or stacks length-1 rows. They are not a second mechanism. `[1 2 3]` does not gain an axis. Element-wise join stays `[xs... ys...]`. `+` still does not join arrays.

### 3. Parsing

Tokenization today (`compiler/dewy_lexer.jo`, `dx_lex`) folds a whole whitespace run into two bits on the next lexeme, `space` and `newline` (`DewyLexeme` in `compiler/dewy_tokens.jo`). A blank line is not distinct from a single break. `\` newline is consumed in that skip and sets `space` without `newline`. Comments are skipped there too: a line comment does not consume the newline, a block comment sets `newline` if it contains one. No newline token exists. Elsewhere the parser treats `newline` as "this token starts a line," and an operator with precedence continues an expression across that line (`dewy_reader_seed.jo`, the `token.newline and dn_power(op) == 0` test). So `1 +⏎2` is already one element before any array rule runs.

The array reader is `rt_dc_array_literal`. It walks elements at bracket depth, counts each `;` into `breaks`, and `rt_dc_rows` turns a break count into a matrix or a `reshape`. A `;` with `space` and `newline` both false is a discard; any other `;` is a row break. Newlines do not affect `breaks`. A `loop` / `if` / `{` is one item (`rt_dc_flow` / the collector). Flows and row-breaks reject each other today. Nested brackets are consumed by `rt_dc_expr` and never appear as outer gaps. `(…)` groups (`rt_dc_group`) do not accept `;` yet, so `(2;)` does not parse.

**Changes, all local:**

- In `rt_dc_array_literal` only, measure each gap when the next element starts. If the next token has `newline == false` and the gap has no `;`, the level is 0 and nothing is scanned. Otherwise scan `src[prev.stop .. next.start)` once: copy the lexer's `\` rule, drop comment-only lines, count the remaining newlines, count `;` tokens consumed as part of the same gap, level = max of those. One forward pass over those bytes. Summed over the file it is O(n).
- Feed the level sequence to a generalization of `rt_dc_rows`: renormalize, reject a missing level, apply a trailing separator, reject ragged groups. Same O(elements) walk the compiler already does. No search, no backtrack.
- A comprehension stays one flow item. Its expressed values enter the cell list as a level-0 run between the surrounding gaps. Delete the "flows cannot have rows" rejection. Still one left-to-right walk.
- `rt_dc_group` accepts `;` as discard, so `(2;)` is a group that expresses nothing. The array reader skips an empty contribution. O(group size).
- Collapse (rule 9) is a checker step beside `check_matrix` in `compiler/expr.jo`, which already chooses `__array2`, `__array2_rows`, or `__array_stack` from the first element's type. Compare shapes, or honor an expected nested type. O(cells). Not a parse.

Do not widen `DewyLexeme.newline` into a count. Every other construct reads that bool; blank lines are meaningless outside arrays. The scan is the array reader's business.

The formatter change is separate and local: when reprinting an array element list, preserve blank lines and `\` continuations. That is a print rule, not a parse.

## Alternatives

### Comprehensions

| Option | What it does | Why it lost or won |
|---|---|---|
| Flat splice, rank from row values (recommended) | Body spacing is irrelevant. `[loop y [loop x f]]` collapses to a matrix. | Matches the one-statement body, the `{…}` discard rule, and the grid idiom. No new grammar. |
| Owner's "always 1-D" taken alone | Even row-yielding loops stay `array<array<T>>`. | Simple, and it is what the splice does. Incomplete: the documented grid comprehension would still not be the n-D array matrix math uses. Kept as the splice half, not the whole answer. |
| Body is a tiny literal; spaces are columns, `;` ends a row | `[loop i in 0..n i i*2 ;]` is n×2. | Julia-like and concise. It is a second separator grammar inside a statement, and it makes `{1.0⏎x⏎x^2}` ambiguous with the flat collector. |
| Ignore spaces, honor `;` inside the body | Newlines format, semicolons shape. | Breaks the decided equivalence of a line break and a `;`. |
| Cartesian `loop y in rows, x in cols` | One clause, rank from the clause count. | New syntax. `and` is already lockstep. The nested form is enough. |

### Nested literals and array-valued cells

| Option | What it does | Why it lost or won |
|---|---|---|
| Collapse when rectangular; annotation keeps nested; ragged is an error (recommended) | `[[1 2] [3 4]]` and `[xs ; ys]` are n-D. `array<array<T>>` opts out. | One rule for space, newline, and `;`. Keeps 1-D. Makes 1×N and N×1 out of brackets the owner already suggested. A one-element edit cannot change the type quietly. |
| Always nest; no stack | `[xs ; ys]` becomes a 1-D array of arrays. Stack needs a new function. | Pure, and it matches renormalization. It deletes the working row-stack and makes the grid comprehension the wrong type for `*`. A new name (`stack`) is not justified while the literal can say it. |
| Stack only on `;`, nest on space and newline | Restores today's `[xs ; ys]` and keeps one-per-line lists nested. | Newline and `;` would mean different things. The decision forbids that. |
| Always collapse, ragged becomes nested | NumPy's other habit. | A length tweak silently changes n-D into nested. Fails safe by default. |
| Julia fixed roles: space is columns, `;` is rows, `[1 2 3]` is 1×3 | No renormalization. | Rejected in Batch 6. It destroys true 1-D. |

### Parsing

| Option | What it does | Why it lost or won |
|---|---|---|
| Source scan in the array reader (recommended) | Count breaks only while reading a literal. | O(n), no lexer-ABI change, invisible outside `[…]`. |
| Store a newline count on every token | The lexer records what the array reader needs. | Also O(n), but every `.newline` reader and both token structs change for a fact only arrays use. |
| Newline tokens in the token stream | The parser sees breaks as tokens. | Rewrites "newline ends a statement" everywhere. Not local. |
| Backtracking so a body can be either a statement or a row picture | Try both parses of `[loop i in xs i i*2]`. | The cost bound forbids it, and the grammar does not need it. |

## What else does not hang together

- **Old attached `;` is gone, including the warning.** `[1 2; 3 4]` is a matrix now. The warning that said it meant `[1 3 4]` has to die in the same change, or it contradicts rule 1. Discard spelling is `(1 2;)` or a block.
- **LANGUAGE.md's `[xs ; ys]` stack is the collapse rule, not a special case of `;`.** After this, `[xs ys]` stacks too. Same shapes, same result. The sentence that only a standalone `;` stacks should not survive.
- **LANGUAGE.md's `[1 2 3 ;]` as `length=[1 3]` stays**, via rule 6. **LANGUAGE.md's implication that `[1 ; 2 ; 3]` is three rows does not.** Batch 6 makes it 1-D. The implementation's `rt_dc_rows` currently treats a semicolon break as an absolute axis and would build 3×1. Renormalization is the part that is not implemented.
- **A wrapped 1-D list that is broken into equal-width lines without `\` is a matrix.** That is the same syntax as an intentional matrix, visible in the source. The formatter must not insert those breaks on its own.
- **`[loop i in xs i i*2]` is not two values per iteration.** The body is `i`. The following `i*2` is the next element and `i` is out of scope. Two scalars per step are `{i i*2}`. A row per step is `[i i*2]`.
- **Dict and record brackets do not gain dimensions.** Newlines there are ordinary whitespace. `;` discards the entry. Nobody should write `[a=1; b=2]` and expect two fields.
- **`new` means two things on two types**, on purpose. On a true 1-D or nested array it wraps. On n-D it inserts a shape axis. Collapsing a literal changes which `new` you get. The split matches "true 1-D stays 1-D."

## Dogfood

Thirteen programs in `programs/`. Each is graded 1–5 on obvious, discoverable, concise, safe by default, and complete, against NumPy, Julia, MATLAB, Rust ndarray, and Go.

| Program | obvious | discoverable | concise | safe | complete | Floor |
|---|---|---|---|---|---|---|
| `sobel.dewy` | 5 | 5 | 5 | 5 | 5 | 5 |
| `voxel.dewy` | 5 | 5 | 5 | 5 | 5 | 5 |
| `orders.dewy` | 5 | 5 | 5 | 5 | 5 | 5 |
| `samples.dewy` | 5 | 5 | 4 | 5 | 5 | 4 |
| `series.dewy` | 5 | 5 | 5 | 5 | 5 | 5 |
| `grid.dewy` | 5 | 5 | 4 | 5 | 5 | 4 |
| `fill_row.dewy` | 5 | 5 | 5 | 5 | 5 | 5 |
| `vectors.dewy` | 5 | 5 | 4 | 5 | 5 | 4 |
| `discards.dewy` | 5 | 4 | 5 | 5 | 5 | 4 |
| `polylines.dewy` | 5 | 5 | 5 | 5 | 5 | 5 |
| `peaks.dewy` | 5 | 5 | 5 | 5 | 5 | 5 |
| `blend.dewy` | 5 | 5 | 5 | 5 | 5 | 5 |
| `quotes.dewy` | 5 | 5 | 5 | 5 | 5 | 5 |

Floor across the set: **4**.

The 4s are the same three comparisons, and each was iterated:

- `samples.dewy` is a wrapped 1-D list. Forgetting `\` on equal widths becomes a matrix. MATLAB and Julia do that too. An invisible fix (ignore newlines once a `\` appears anywhere) would make blank lines and wraps share a letter. Left as rule 5.
- `grid.dewy` is the nested comprehension. Julia's `[f(x,y) for y in 1:h, x in 1:w]` is shorter. Adding that clause is new syntax and collides with lockstep `and`. The nested form is the one the language already teaches, and collapse makes it the right type. Left as rule 8–9.
- `vectors.dewy` writes N×1 as `[[1] [2] [3]]`. MATLAB's `[1;2;3]` is a column only because MATLAB has no 1-D vector. Making Dewy's `[1; 2; 3]` a column was rejected in Batch 6. The NumPy spelling is the one that keeps true 1-D.
- `discards.dewy` loses a point on discoverable: `(f();)` is the discard, where Python would write nothing. The decision requires it, because a bare `;` inside `[…]` is a dimension. No iteration removes that without breaking rule 1.
