# Dewy language reference

This reference records the behavior of the current Dewy compiler. It is
intentionally concise and organized by language construct rather than by a
learning sequence.

> **Development reference:** Dewy is version `0.0.0-dev.0`. Syntax and
> semantics may change. A feature described as **implemented** is expected to
> pass parsing, semantic analysis, µDewy lowering, and emission. Anything else
> is explicitly marked **planned**.

For tutorials and motivation, read [Learning Dewy](../learn/). For the most
detailed implementation checklist, see
[`dewy/status.md`](https://github.com/david-andrew/dewy-lang/blob/master/dewy/status.md).

## Conventions

- Dewy source normally uses the `.dewy` suffix.
- µDewy source normally uses `.udewy`, although suffixes do not alter Dewy's
  semantic analysis.
- Examples in this reference target current Dewy unless labelled µDewy.
- `T | undefined` denotes an optional value.
- Fixed-width integer examples use `int8` through `int64` and `uint8` through
  `uint64`.
