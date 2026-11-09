# Array literals — round 2

**BLUF.** Option B. Separators give a scalar grid its rank; brackets build `array<array<T>>`. A nest becomes n-D only when a shaped type asks. Bare collapse (option A) fails the common path: the repo's grids are `seen[y][x]` and `seen[i].push`, and row lengths that arrive at run time cannot be proved. The corpus floor is 2 for both options, from the decided discard spelling `(f();)`. On the programs where the options differ, A floors at 2 and B at 4.

A is specified tightly enough to adopt later. The parser still builds the nest either way.

## Where they differ

| | A. Collapse a bare rectangular nest | B. Brackets nest; a shaped type asks for n-D |
|---|---|---|
| `[1 2 ; 3 4]` and the blank-line cube | n-D, from the separator rule. Same in both. | Same. |
| `[[1 2] [3 4]]`, `[xs ys]`, `[xs ; ys]`, one row per line | n-D when the shapes match | `array<array<T>>`, ragged allowed |
| `[[1 2 3]]` | `length=[1 3]` | nested, length 1, element `[1 2 3]` |
| `[[1] [2] [3]]` | `length=[3 1]` | nested, three length-1 arrays |
| 1×N / N×1 without a new bracket meaning | `[1 2 3 ;]`, ascription, and (wrongly, under A) an extra bracket | `[1 2 3 ;]`, `array<T length=[1 n]>`, `array<T length=[n 1]>`, `v[new]`, `v[.. new]` |
| `[loop y in [0..h) [loop x in [0..w) false]]` then `seen[y][x] = true` | the value is n-D; `seen[y][x]` and `.push` do not typecheck | the value is nested; both work, including when a later `push` makes a row longer |
| `[loop line in lines line.split(",")]` | lengths are not provable, so this is an error until you write `array<array<string>>` | nested, no proof |
| `[loop _ in [0..n) []]` then `lists[i].push(j)` | every row has length 0, which *is* provable, so this collapses and `.push` fails | nested, `.push` works |
| `[top bottom]` of two equal matrices | one n-D batch, and a copy into a flat buffer | a list of two matrices. A batch is a shaped ascription, or the fallible function in questions |
| `f = (x:T y:T) => [x y]` | the result flips when `T` is an array | always `array<T>` |
| Empty `[loop y in [0..0) [loop x in [0..4) 0]]` | a collapsed empty drops the width 4 | nested, length 0. `length=[0 4]` only if a shaped type asks and the width is proved |
| Copies | the nest is built, then packed into one buffer | the nest is the value. A shaped ascription is the copy, and it is written at the type |

Today's `[xs ; ys]` row stack does not survive B. A line break and a `;` are the same level, so `[xs ; ys]`, `[xs ys]`, and a one-per-line pair are one form. That form is a nest. Stacking moves to an explicit function. Keeping "`;` stacks when the cells are arrays" would make the separator mean a different thing for arrays than for scalars, which is the context sensitivity Batch 4 rejects, and it would make `[xs⏎ys]` disagree with `[xs ; ys]` or else stack on an ordinary line break too.

## Option A, in full

A bare literal whose cells are arrays of one provable common shape is n-D. The leading axes are the outer grid after renormalization; the rest are that shape. `[xs ; ys]` stacks. `[[1 2 3]]` is 1×3.

Three cases, and the middle one must not guess:

- Provably equal: collapse.
- Provably unequal: error, "these rows have different lengths (2 and 1); make them equal, or give this the nested type `array<array<…>>`".
- Not provable: error, not a nested array and not an n-D array. "cannot prove these rows have the same length; give this the nested type `array<array<…>>`, or check it at run time with `$runtime_checks`". Under that flag the check is an obligation and a mismatch panics. There is still no failure value.

That last rule is what keeps A from inventing a type. It does not make the CSV case easy: the annotation is mandatory, and the message that says "make them equal" is a lie when the lengths come from input. The all-empty adjacency list never hits this rule, because length 0 is proved, and the collapse is exactly what breaks `.push`.

`array<array<T>>` as the expected type opts out. An unbound `T` in `array<T>` does not collapse; the literal stays `array<T>` and an array-valued `T` is then nested inside it. Overload resolution sees the type after that choice, not before.

A is reversible in the parser. It is not reversible in the program: `seen[y][x]` either typechecks or it does not.

## Option B, the recommended rule

Rules 1–5 and 7 are the separator rules from round 1, with the fixes below. Rules 8–12 replace collapse.

1. **`;`.** In the element list of an array literal, `;` is a separator. In a record, a dict, a `{…}` block, a `(…)` group, and any statement, `;` discards the value before it. Attached and unattached spacing do not differ. Index brackets, slice brackets, and type arguments reject `;`. A `[…]` is a record if it has a `name=` field, a dict if it has a `->` entry, otherwise an array. A stray `[f(); 7]` is therefore the 1-D list of both values. The call is not discarded. The discard is `(f();)`.

2. **Discarding inside an array.** A group or a block contributes the values it still expresses. One that expresses nothing is deleted, not stored as a hole. `[1 (2;) 3]` is `[1 3]`.

3. **Gaps, including across a deleted element.** A gap is the whitespace, comments, and `;` tokens between two elements that survive. Spaces are level 0. *k* semicolons are level *k*. *n* line breaks, after rule 5, are level *n*. One gap takes the highest of those. Consecutive semicolons are one gap: `[1 ;; 2]` is a single level-2 gap, not an empty row. A separator with no element before it is an error (`[;]`, `[; 1]`). Deleting an empty contribution merges the gap before it with the gap after it by **max, not sum**. `[1 2⏎(f();)⏎3 4]` is one level-1 gap. `[1 2⏎⏎(f();)⏎3 4]` is level 2. A discarded expression cannot invent a blank line.

4. **Dimension 0.** Take every gap, **including a trailing separator**. Let *m* be the lowest level. Subtract *m*. The result must be exactly the set `0 .. max` with none missing. One level, whatever it was, is 1-D. `[1; 2; 3]`, `[1⏎2⏎3]`, `[1 ;; 2]`, and `[1 ;;]` are 1-D. `[1 2 ;; 3 4]` is an error: levels 0 and 2, no level 1. `[1 ; 2 ;; 3]` renormalizes to levels 0 and 1 and then fails as ragged, not as a skip.

5. **What is not a gap.** The break after `[` and the break before `]` are not gaps, so `[1 2 3⏎]` is 1-D and a trailing line break never plays the role of a trailing `;`. That is the Batch 6 rule, and it is why 1×N is written with `;` rather than with a newline. A comment-only line is deleted before breaks are counted. A break inside nested brackets, parens, or braces belongs to that nest. A break the expression parser consumes with a binary operator is not a gap. `\` cancels one break. A line that contains only spaces and tabs is a blank line, because the level is the newline count, not a search for non-space. `\r\n` is one break; a bare `\r` is ordinary whitespace. A blank line inside a comment is part of the comment and does not count. The formatter may strip trailing spaces and trailing `\r`. It must not remove a blank line inside `[…]`, and it must not insert one.

6. **Trailing `;` is an ordinary gap.** It is included in rule 4. There is no extra "add an axis" rule. `[1 2 3 ;]` has levels 0 and 1, so it is `length=[1 3]`. `[1 2 ; 3 4 ;]` closes the last row and is `length=[2 2]`. `[1 ; 2 ;]` is one level and is 1-D. `[1 ;]` is 1-D, not 1×1. `[1 ; 2 ;;]` renormalizes to a higher trailing gap and is `length=[1 2]`. `[1 ;;]` renormalizes to 1-D. Round 1's special case, and its error for `[1 ;;]`, are withdrawn. 1×N is this spelling or a shaped ascription. It is not an extra pair of brackets.

7. **Shape of a scalar grid.** Outermost axis first, row-major. Rank ≥ 2 is `array<T length=[…]>` and `.length` is that shape. A true 1-D literal is `array<T>` with no `length`, and `.length` is the count. `array<T length=[3]>` is a shaped rank-1 array: `.length` is `[3]`, not `3`, and one index still selects an element. Ascribing `length=[3]` to `[1 2 3]` is that conversion. Ascribing a 1-D `array<T>` to a rank ≥ 2 literal is an error: "this literal is 2×2, and `array<float64>` is 1-D; join the lines with `\` or ask for `array<float64 length=[2 2]>`". Plurals are real: "1 element", "2 elements", "1 row", "2 rows", "1 part", "2 parts".

8. **Runs.** A spread and a comprehension are runs of cells. Rank comes only from gaps written in the literal, not from a gap invented inside the run. The gap before a run stands before its first cell; the gap after it stands after its last cell; between its cells the level is the lowest written level, which is dimension 0 after rule 4. A run that is the whole literal has no written gap and is 1-D. `[loop i in xs i ; loop j in ys j]` has one written level, so it is 1-D: the semicolon renormalizes away and the cells append. `[1 2 ; loop i in xs i]` has levels 0 and 1, so the run is the next row and its length must be 2. The same rule covers `[1 xs... ; 2]`. A length proved wrong is the ragged error. A length not proved is an obligation: "cannot prove this row has 2 elements; the length is checked at run time under `$runtime_checks`". It is not a syntax error, and it is not a reason to change rank.

9. **Brackets nest.** A cell that is itself an array is an element of `array<array<…>>`. The outer separators still decide the outer shape, and a one-level list is 1-D, so `[xs ys]`, `[xs ; ys]`, `[[1 2] [3 4]]`, and a one-per-line list of rows are the same nested array. Ragged lengths are legal. `[[1 2 3]]` is nested, length 1. Nothing here copies the rows into a flat buffer, and `.length` stays a count. `loop row in m` yields a row. `m[i]` is a row. `m[i].push` and `m[y][x]` work.

10. **A shaped type asks for n-D.** `let m:array<int64 length=[2 2]> = [[1 2] [3 4]]` is the matrix. So is a shaped parameter or field. When every row length and the outer count are proved, a mismatch is a compile error and a match is free of a run-time check, including a proved empty: `length=[0 4]` accepts `[loop y in [0..0) [loop x in [0..4) 0]]`. When a length is not proved, the program does not compile unless `$runtime_checks` is on, and then the check is an obligation. The message names the missing proof and offers the nested type. It does not tell the programmer to make input rows equal. The ascription is the copy into the flat buffer.

11. **Comprehensions.** A brace-less body is one statement. A braced body is a block, so `;` inside it discards and its expressed values are scalars in a run. `[loop x in xs {1.0 x x^2}]` is 1-D. `[loop x in xs [x x^2]]` is a nested array of pairs. `[loop y in [0..h) [loop x in [0..w) f(x y)]]` is the grid, nested. A filter drops the iteration. Several comprehensions are several runs in one literal, ranked by rule 8.

12. **`new`.** On a rectangular array, true 1-D included, `new` inserts one axis of length 1 and the result is n-D. `xs[new]` is `length=[1 n]`. `xs[.. new]` is `length=[n 1]`. This is not `[xs]`. `[xs]` is the nested array of rule 9. On an n-D value, `new` inserts the axis at that position. On a nested `array<array<T>>`, `new` is an error: " `new` inserts an axis of a rectangular array; this value is nested. Write `[rows]` to wrap it, or `[loop x in xs [x]]` to wrap each element." Strings are unchanged.

The fallible stack of run-time rows is not given a name here. Its behavior, if the name passes a cold read: it takes the nested array, returns an n-D array with a new leading axis, and returns a failure when the input is empty or the shapes differ. No panic. Empty input fails because the width is not in the value. A shaped ascription remains the path that already has a name.

## Grades

Order: obvious, discoverable, concise, safe, complete. Against NumPy, Julia, MATLAB, Rust ndarray, and Go. The shared separator fixes (1-D target rejects a matrix, runs are obligations, trailing `;` is just a gap) are in force for both columns.

| Program | A | B |
|---|---|---|
| `sobel.dewy` | 5 4 5 4 5 → 4 | 5 4 5 4 5 → 4 |
| `voxel.dewy` | 4 3 5 4 4 → 3 | 4 3 5 4 4 → 3 |
| `orders.dewy` | 5 5 5 5 5 → 5 | 5 5 5 5 5 → 5 |
| `samples.dewy` | 4 4 3 5 5 → 3 | 4 4 3 5 5 → 3 |
| `series.dewy` | 5 5 5 5 5 → 5 | 5 5 5 5 5 → 5 |
| `grid.dewy` | 3 3 4 3 2 → 2 | 5 5 4 5 5 → 4 |
| `fill_row.dewy` | 4 4 5 5 4 → 4 | 4 4 5 5 4 → 4 |
| `vectors.dewy` | 3 3 3 5 4 → 3 | 4 4 4 5 5 → 4 |
| `discards.dewy` | 3 2 3 4 4 → 2 | 3 2 3 4 4 → 2 |
| `polylines.dewy` | 4 4 4 5 5 → 4 | 5 5 5 5 5 → 5 |
| `peaks.dewy` | 3 3 4 4 3 → 3 | 4 4 4 5 5 → 4 |
| `blend.dewy` | 3 3 5 3 3 → 3 | 5 5 5 5 5 → 5 |
| `quotes.dewy` | 5 4 5 5 5 → 4 | 5 4 5 5 5 → 4 |
| `csv.dewy` | 4 3 3 5 5 → 3 | 5 5 5 5 5 → 5 |
| `words.dewy` | 4 3 3 5 5 → 3 | 5 5 5 5 5 → 5 |
| `adjacency.dewy` | 3 2 4 2 2 → 2 | 5 5 5 5 5 → 5 |
| `batches.dewy` | 3 3 4 3 3 → 3 | 5 4 4 5 5 → 4 |

Corpus floor: **2** either way (`discards.dewy`). The spelling is required by Batch 6, because a bare `;` inside `[…]` is a dimension. Python writes nothing there; Dewy cannot, without a second meaning for `;`.

Floor of the choice itself, ignoring `discards` and the shared separator programs: **A is 2** (`grid.dewy`, `adjacency.dewy`), **B is 4** (`grid.dewy`, `vectors.dewy`, `batches.dewy`).

`voxel.dewy` stays 3 because a blank line is invisible and a trim deletes it. `;;` is the same cube and would score 4; the program shows both and the grade is the blank-line form. `samples.dewy` stays 3 on concise: a backslash per line is the decided wrap, and one item per line is the wrap you do not need.

## Parser

Both readers parse arrays today, and they disagree with this rule in the same places. `compiler/dewy_reader_seed.jo` has `rt_dc_array_literal`, `rt_dc_rows`, `rt_dc_collector`, and `rt_dc_group`. `compiler/dewy_reader.dewy` has `rd_dc_array_literal`, `rd_dc_rows`, and `rd_dc_collector`. `check_matrix` in `compiler/expr.jo` lowers a scalar grid. It must not collapse a nest. A shaped ascription of a nest is a separate checker path.

The lexer (`dx_lex` in `compiler/dewy_lexer.jo`, and the Dewy twin) folds whitespace into `space` and `newline` on the next lexeme. Block-comment spans are recorded in `dn_block_comments` as `[start, end)` pairs. The formatter reads that list as block comments (`df_blocks` in `compiler/dewy_fmt.jo`), so line comments must not be pushed onto it.

Gap level, one helper called from both readers:

- Semicolons come from `.semi` tokens the array reader consumes at this bracket depth. A `;` inside `# a; b` or `#{ a; b }#` is never a token, so it is never counted.
- Newlines come from bytes in `src[prev.stop .. next.start)`, skipping three things: spans in `dn_block_comments`, line comments, and a `\` break. Line comments and `\` use the lexer's own skip, extracted so the helper calls it instead of copying it. `\r\n` contributes the `\n` only.
- Level is the max of that newline count and the semicolon count. Empty contributions are removed first; their adjacent gaps combine by max.
- No token grows a newline count. Outside an array, a blank line is still insignificant.

Rank is a rewrite of `rt_dc_rows` and `rd_dc_rows`, not a tweak. They take absolute break counts today. The new walk renormalizes, rejects a missing level, treats a trailing semicolon as a gap, and checks row widths. One forward pass, no backtracking.

A run beside a higher level cannot be today's collector. `rt_dc_collector` and `rd_dc_collector` desugar to `push` and `extend` and then forget the rows. For a one-level literal that desugar stays. For a higher level, each reader records the run's length beside the cells it already lowers. The checker proves the length or emits the obligation. Deleting the "flows cannot have rows" rejection is not enough.

Cost is linear in the literal's source. The helper scans each gap once. The row walk is linear in the number of cells. Nothing searches.

## What round 1 had wrong

- Bare collapse as the default. Withdrawn.
- `xs[new]` and `[xs]` described as two meanings of one value. Under B they are different operations, and only `new` yields n-D.
- Fixture 80 banned a spread beside `;`, while fixtures 87 and 88 allowed a comprehension there. One run rule covers both.
- Empty `(f();)` left the gap rule unspoken. Merge by max.
- Trailing `;` was a special case, `[1 ;;]` was an error, and a trailing line break was not. Trailing `;` is a gap; the line break before `]` stays not a gap, by Batch 6.
- "1 rows". The plural is "1 row".
- The parser note named only the Jo reader, and a raw byte scan would have counted `;` and newlines inside comments.
- An annotated 1-D target did not reject a matrix literal, so a forgotten `\` was silent.
- `array<T length=[n]>` was called both "true 1-D" and a shape. `.length` is `[n]` when the `length` is written, and the count when it is not.
