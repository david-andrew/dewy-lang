# Tensors and broadcasting (adopted direction, 2026-10-21)

David's decision on open question 7. It replaces the earlier provisional tensor
notes. Not built yet: it is queued after concurrency stage 1. Keep it
device-agnostic. A GPU is placement context (`x.to(dev)`), not a type change, and
mixing devices is a compile error ([decisions](decisions.md)).

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
