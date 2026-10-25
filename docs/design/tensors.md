# Tensors and broadcasting (adopted direction, 2026-10-21)

David's decision on open question 7. It replaces the earlier provisional tensor
notes. Largely built: shaped arrays and shape-typed parameters, dotted
broadcasting and `f.(xs)`, matrix literals, `end`/`new` indexing, `value.to(device)`
(one device, `'cpu'`, so far) and `gpu(...)` arrays work as docs/LANGUAGE.md
("Numeric arrays and matrices", "GPU arrays") describes. Keep it
device-agnostic.
 A GPU is placement context (`x.to(dev)`), not a type change, and
mixing devices is a compile error (see "Decided rules" below).

## One array type, shape in the type

There is one `array` type. Its shape lives in the type as
`array<T length=[d1 d2 ...]>`. Dimensions may be symbolic, and the fact engine
checks them:

```
matmul = (a:array<float64 length=[m n]> b:array<float64 length=[n p]>):>array<float64 length=[m p]>
```

There is no `.shape` member. `.length` is the single source of truth: an int for
a 1-D array, a sequence for an N-d one.

## Broadcasting

- **Dot operators** (Julia-style, with cues from MATLAB) broadcast: `a .* b`,
  `m .+ row`, and `f.(xs)` vectorizes any function.
- **Plain operators** work where the meaning without broadcasting is obvious:
  `a + b` on same-shape arrays is elementwise, and `A * B` is matrix multiply.
  Shapes are checked at compile time.
- **Rules** are NumPy's: align trailing axes, and stretch size-1 axes.
- **Axes:** `new` inserts an axis, and `end` is the last index (both decided).
- **1-D arrays** have no orientation. Each acts as a singleton-dimension row or
  column, whichever a matrix multiply needs on that side. Only a genuinely 2-D
  array with a singleton dimension complains when shapes don't line up.

## Literals

Literals lean contiguous N-d unless explicitly jagged, either by the literal's
own shape or by the receiving type.

- Rows separated by newlines build a 2-D array.
- A `\` at the end of a line cancels that newline (decided 2026-10-23), so
  `[2 3 5 \` + newline + `7 11]` is one row. A 2-D literal given to a 1-D type
  is an error suggesting `\` (this replaces "a 1-D receiving type flattens rows").
- 2-D blocks separated by blank lines build a 3-D array.
- A standalone `;` (not attached to an expression) stands in for a newline, so
  higher dimensions fit on one line, Julia-style.
- Explicit inner brackets, `[[1 2 3] [4 5 6] [7 8 9]]`, are 2-D unless the
  target type is jagged.

Loop capture can produce shaped N-d arrays; simple loop captures are 1-D.

## Indexing and safety

Indexing is `m[i j]`, with one space-separated index per dimension
(resources/discussion_points.md). Shape mismatches follow no-traps: a compile
error unless proven, or checked under `$runtime_checks`.

## Decided rules

Moved here from the decisions ledger ([decisions.md](decisions.md)), which keeps
a pointer to each rule. The wording is David's.

### GPU placement

- GPU: computation follows data with explicit placement (`x.to(dev)`,
  `.to('best')` or a pushed device context); mixing devices is a compile error,
  tracked as a device-equality fact. A `parallel` body with no blocks, allocates
  or syscalls over arrays and scalars is GPU-eligible. Designs stay
  device-agnostic; nothing to build yet.

### `end` and `new`

- `end` and `new` are reserved: `end` is the last index inside an index; `new`
  inserts a singleton axis (NumPy `newaxis`): `xs[new ..]`, `xs[.. new]`.

### Line continuation (2026-10-23)

- Line continuation: a `\` at the end of a line cancels that newline
  everywhere: in array and matrix literals (`[2 3 5 \` + newline + `7 11]` is
  one row), in strings (removes the newline) and in ordinary code. This
  replaces the provisional "1-D receiving type flattens rows" rule; a 2-D
  literal assigned to a 1-D type is an error suggesting `\`.
