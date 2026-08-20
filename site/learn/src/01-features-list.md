# Features

A map of the language, in roughly the order this book teaches it. Items
marked **not yet determined** belong here, but the syntax or detailed
rules are still open.

## Syntax and Structure

- [Expressions, Statements, and Blocks](ch03/expressions-statements-blocks.md)
- [Bindings and Scope](ch03/bindings-and-scope.md)
- [Whitespace Lists](ch03/container-types.md) instead of comma separators
- Blocks, objects, functions, and generators share one grammar
- [Imports](ch03/imports.md) and the source prelude
- `export` and installed package lookup. Not yet determined
- Meta-programming and a language-defined grammar. Not yet determined

## Types and Values

- [Basic Data Types](ch03/basic-data-types.md). `int`, fixed widths,
  `real`, `rational`, `bool`, `void`, `undefined`, complex, quaternion
- [Number Bases](ch03/number-bases.md) and packed based strings
- [Optional Types](ch03/optional-types.md). `T | undefined`, `is?` / `isnt?`
- [String Types](ch03/string-types.md). Graphemes, interpolation, views
- [Ranges](ch03/range-types.md) with inclusive or exclusive bounds
- [Containers](ch03/container-types.md). Arrays, dictionaries, bidicts, sets
- [Objects](ch03/object-types.md) without a class keyword
- [Refinements](ch03/refinements.md). `T<conditions>`, `unsafe`
- Types you omit are filled in, and type aliases
- Fixed-point literals. Not yet determined
- Custom-ranged integer overflow. Not yet determined
- String collation and normalization. Not yet determined

## Operators and Math

- [Operators](ch03/operators.md). `=?`, English booleans, juxtaposition,
  pipes, `as` / `transmute`
- Composite arithmetic such as `n^/2`
- [Basic Math](ch03/basic-math.md) and [Linear Algebra](ch03/linear-algebra.md)
- [Physical Units](ch03/units.md)

## Functions and Flow

- [Function Types](ch03/function-types.md). Literals, defaults, named and
  keyword-only arguments, overloads with `&`
- `@` to freeze some arguments
- [Functional Programming](ch03/functional-programming.md)
- [Flow Control](ch03/flow-control.md)
- [One Loop to Rule Them All](ch03/loops.md). `in`, several iterators,
  labeled exits, generators
- Rest capture, spreading, and positional-only parameters. Not yet determined
- `match` and `finally`. Not yet determined

## Standard Library and Model

- [Standard Library](ch04/00-stdlib.md), including [Time](ch04/xx-time.md)
- Timezones and calendars. Not yet determined
- [Sandboxes and Harnesses](ch05/xx-sandboxes-harnesses.md)
