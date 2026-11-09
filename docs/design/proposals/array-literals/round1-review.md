# Review of array literals, round 1

Verdict: the separator rules are sound, apart from the small gaps in section 2. Collapse as written fails David's first test (the common path is easy) for general code. I recommend a narrower rule, below.

## 1. Collapse

What I checked: the repo's own code, `compiler/expr.jo` (`check_matrix`), `lib/std/nd.jo` (`__array2_rows`, `__array_stack`), and `[loop … [loop …]]` usage.

**The common path for nested brackets is real nesting, not matrices.**
- The repo has 57 `[loop … [loop …]]` sites and about 279 `][` index sites.
- `tests/cases/dogfood/98_maze_carver.dewy` has `let seen = [loop _ in [0..H) [loop _ in [0..W) false]]` and then `seen[y][x] = true`.
- `74_image_regions.dewy` and `grid_row_push_in_loop.dewy` use `seen[i].push(true)`.
- Under collapse, `seen` is a bool matrix. `seen[y][x]` breaks: LANGUAGE.md says scalar indexing needs rank equal to the index count. `seen[i].push` breaks too.
- The user must add `:array<array<bool>>` to every visited-grid, DP-table and board. That is the 80% path needing an annotation, not the rare case.
- The proposal never says what `m[i]`, `loop row in m` or `push` mean on a collapsed value. Those are the operations the common path uses.

**Runtime lengths are the weak point.** Rank is static, but the equal-length check is not.
- `[read_row() read_row()]`, `[loop line in lines line.split(",")]` and `[loop row in image [loop _ in row false]]` have unknown row lengths.
- "Ragged is a compile error" cannot fire for them. Today `__array2_rows` panics at run time.
- A panic needs a proof or `$runtime_checks`, per the "exceptions become proofs" rule. The user meets "cannot prove these rows are equal length", and the offered fix says "make them equal", which they cannot do.
- The only way out is the annotation, which gives nested. So collapse works only where lengths are statically visible (literals, `[0..h)` loops).
- There is no fallible builder for run-time rows (an `array<T length=[r c]>?` or a result). For CSV or batches, collapse does nothing and the annotation is mandatory.
- Realistic code that needs `array<array<T>>`: CSV rows, adjacency lists, words per line, polylines, jagged buckets, visited grids, sudoku and board state, `Vec<Vec<T>>` ports. Matrix math is the minority.

**Generic code flips type.**
- In `f = (x:T y:T) => [x y]`, the bare literal collapses when `T` is an array and stays 1-D when it is not.
- Rule 9 is silent for expected type `array<T>` with `T` unbound. `plain([[42]])[0]` in `tests/cases/argument/array_generic_context.dewy` shows this case exists.
- Overloads on `array<array<int>>` versus `array<int length=[…]>` are unspecified.

**Smaller costs.**
- `[xs ys]` copies both arrays into one flat store. The ownership rule is that copies must be explicit and costly. Nested literals share immutable rows.
- `.length` changes from a count to a shape array. Most misuse is a type error, but it prints `[2 3]` silently.
- `[loop y in [0..0) [loop x in [0..4) f]]` collapses to `[0 0]`, losing the width. `__array_stack` already drops rank on empty input (`NDArray([] , [0])`).
- Collapse recurses, so deep nests copy `n × depth` times. Minor.
- The existing nested-comprehension length proofs in LANGUAGE.md would have to be rewritten as shape facts.

**Other languages.**
- NumPy collapses, but only inside an explicit `np.array(...)` or `np.stack`, and ragged is an error or an object array. Its a[y][x] still works because `a[y]` is a view.
- Julia keeps a vector of vectors nested and stacks with `stack`, `hcat` or `reduce(vcat, …)`. The bracket stays a list constructor.
- Rust, Go and ndarray keep `Vec<Vec<T>>` nested. A matrix is a separate constructor.
- Dewy would be the only one to make its universal list bracket type-directed.

**Recommendation: none of the three as stated. Keep nesting, and let the expected type ask for n-D.**
- A bare nest stays `array<array<T>>`, ragged allowed. `[xs ys]`, `[xs ; ys]`, `[[1 2] [3 4]]` and the grid comprehension are real nests.
- A nest becomes n-D only when the expected type says so: `let m:array<float64 length=[2 2]> = [[1 2] [3 4]]`, or a shaped parameter or field. That is rule 10's mechanism, applied to nests.
- A shape mismatch is a compile error when the lengths are provable and an obligation otherwise.
- The scalar grid `[1 2 ; 3 4]` is already n-D by Batch 6, so the matrix literal needs no nesting.
- `[xs ; ys]` becomes a nest. That follows from the decided line-break and `;` equivalence, and the no-legacy rule covers it.
- Stacking run-time rows needs a function. `stack(rows)` is a new name, so it goes to open_decisions after the cold test. Until then, `reshape` and shaped ascription cover it.
- "Collapse only for literal-written nests" is the worst option. `[[1 2] [3 4]]` would be n-D while `a=[1 2]; [a b]` is nested, so extracting a variable changes the type.
- If David still wants bare collapse, require provable equal shapes. An unprovable case must not silently choose either type. It needs the annotation, with an error message that says so.
- Both parsers still build the nest first, so this is easy to adopt later. Reversibility holds either way, but the type change is observable.

## 2. Soundness of the rule text

- **Fixture 28** says "this one has 1 rows". Rule 7 promises a real plural. Fix the wording ("1 row").
- **`xs[new]` is no longer `[xs]`.** LANGUAGE.md says `xs[new]` is `[xs]`. Under rule 9, `[xs]` is a 1×N n-D value, but rule 10 keeps `xs[new]` nested. The same value now has two types. NumPy's `xs[None]` is 1×N. Fix: on a true 1-D array `new` yields n-D, and `xs[.. new]` yields N×1. That removes the "new means two things" paragraph.
- **Variable-width runs are treated inconsistently.** Fixture 80 forbids a spread beside a higher level, because "its length is not a static row width". Fixtures 87 and 88 allow a comprehension run in a row, whose width is also dynamic. Treat both the same: a run is level-0 cells, and the row-width check is a proof or an obligation.
- **Comprehension rank is ambiguous.** `[loop i in xs i ; loop j in ys j]` has one written gap, level 1, so rule 4 makes it 1-D. `[1 2 ; loop i in xs i]` is 2-D. A comprehension alone is "a row" in one and "cells" in the other. State that rank comes from written gaps only.
- **Gaps across an empty group.** Rule 3 says a gap is between two elements. Fixture 54 puts `(f();)` in the middle, so the gap spans an element that vanishes. Say that empty contributions are deleted and their neighbouring gaps merge, and say how: max, or sum. `[1 2⏎(f();)⏎3 4]` is level 1 under max and level 2 under sum.
- **Rule 6 has three spellings and an asymmetry.**
  - `[1 2 3 ;]`, `[[1 2 3]]` and an ascription all give 1×N.
  - `[1 2 3 ;]` is 1×3, but `[1 2 ; 3 4 ;]` is 2×2 and `[1 ; 2 ;]` is 1-D.
  - `[1 ; 2 ;;]` is 1×2, while `[1 ;;]` is an error.
  - A trailing `;` adds an axis but a trailing line break does not.
  - Under right-design-not-legacy, drop rule 6. `[[1 2 3]]` or `m[new]` covers it, and trailing `;` becomes a plain error or is ignored.
- **A one-gap list absorbs the old discard.** `[f(); 7]` was a discard. It is now `[f() 7]`, so a stray `;` no longer errors. That is fine, but say it in the "what else" list.
- **Expected 1-D with a matrix-shaped literal.** `samples.dewy` annotates `array<float64>` and relies on `\`. The text does not say that an annotated 1-D target rejects a shape-[2 3] literal. It should: "this looks 2×3, you asked for 1-D; add `\`". That closes the main silent hazard (an equal-width wrapped list).
- **Rank-1 `length=[n]` versus count.** LANGUAGE.md calls `array<float64 length=[n]>` "a 1-D one". Rule 7 says a true 1-D array is not rank-1 n-D. State which type `length=[3]` accepts and what `.length` returns.
- **Blank lines.** Say what a whitespace-only line, CRLF, and a blank line inside a trailing comment count as. State whether a trailing-whitespace strip is safe in the formatter.
- **Collapse edge cases still open:** cells of `array<int>` and `array<float64>`; cells that are `array<array<T>>`; optional-array cells; and `loop row in m` or `m[i]` on n-D.

## 3. Parser plan

The plan is linear and has no backtracking, but "all local" is optimistic.
- **There are two readers.** `compiler/dewy_reader_seed.jo` (`rt_dc_array_literal`) and `compiler/dewy_reader.dewy` (`dw_rows_literal`, `dw_collector`) both parse arrays. The plan names only the Jo one.
- **The source scan must be comment-aware.** `src[prev.stop .. next.start)` can hold `# a; b` and `#{ x⏎y }#`. A raw byte count of `;` or newlines is wrong there. Count `;` from tokens, and newlines from bytes outside comments. The lexer already skips comments, so duplicating its `\` and comment rules invites drift.
- **The collector is not a parser step.** `rt_dc_collector` desugars to an accumulator with `push` and `extend`, which keeps no row structure. A comprehension row needs a run-time reshape plus a check. Deleting the "flows cannot have rows" rejection means building that, and the check needs an obligation.
- **`rt_dc_rows` and `check_matrix` need a rewrite, not a tweak.** Today they take absolute axes. Renormalization, holes and trailing rules are new.

## 4. Grades (strict)

Order: obvious, discoverable, concise, safe, complete. Compared with NumPy, Julia, MATLAB, ndarray and Go.

| Program | o | d | c | s | k | Floor | Why |
|---|---|---|---|---|---|---|---|
| sobel | 5 | 4 | 5 | 4 | 5 | 4 | A line break is a row, like MATLAB. A mis-wrapped equal-width list is silently 2-D. |
| voxel | 4 | 3 | 5 | 4 | 4 | 3 | A blank line is the third axis. Invisible, and editors strip it. |
| orders | 5 | 5 | 5 | 5 | 5 | 5 | Records stay a list. |
| samples | 3 | 3 | 4 | 3 | 4 | 3 | `\` on every line; forgetting it is silent unless annotated. |
| series | 5 | 5 | 5 | 5 | 5 | 5 | |
| grid | 4 | 3 | 4 | 4 | 3 | 3 | Nothing says a nest is a matrix. `field[y][x]` fails. The `h=0` shape is lost. |
| fill_row | 3 | 3 | 5 | 3 | 3 | 3 | A run-time-width row with an unspecified width check. |
| vectors | 3 | 4 | 3 | 5 | 4 | 3 | Three spellings of 1×N. `[[1.0] [2.0] [3.0]]` is a clumsy column. |
| discards | 3 | 2 | 3 | 4 | 4 | 2 | `(note("left");)` is new and odd. Python writes nothing. |
| polylines | 4 | 4 | 4 | 5 | 5 | 4 | Ragged data needs an annotation. |
| peaks | 3 | 3 | 4 | 4 | 4 | 3 | `[i i*i]` is a row and `{i i*i}` is flat. Easy to mix up. |
| blend | 4 | 3 | 5 | 4 | 4 | 3 | `[top bottom]` stacks with a hidden copy. NumPy needs `np.stack`. |
| quotes | 5 | 4 | 5 | 5 | 5 | 4 | The annotation checks the table shape. |

Floor across the set: **2** (`discards`), and mostly 3. Round 1 claimed 4.

## 5. Top 5 issues and fixes

1. **Collapse of bare nests breaks the main grid idiom and cannot be checked at run time.**
   - Evidence: 57 nested-comprehension sites, `seen[y][x]`, `rows.push`.
   - Fix: n-D only from an n-D expected type. Bare nests stay nested. Add a fallible `stack` later, after the cold name test.
2. **`xs[new]` versus `[xs]`.** Make `new` on a true 1-D array give n-D, so one value has one type.
3. **Variable-width runs.** Apply one rule to spreads (fixture 80) and comprehensions (87, 88). Rank comes from written gaps only. Specify the row-width proof or obligation.
4. **Gap definition holes.**
   - Empty groups (fixture 54): how neighbouring gaps merge.
   - Trailing separators (rule 6): drop the rule.
   - Fix the "1 rows" wording (fixture 28).
   - An annotated 1-D target must reject a matrix-shaped literal.
5. **Parser plan scope.**
   - Cover both readers (`dewy_reader_seed.jo` and `dewy_reader.dewy`).
   - Make the gap scan comment-aware.
   - Plan the collector's run-time reshape and check. Rewrite the nested-length proofs as shape facts.
