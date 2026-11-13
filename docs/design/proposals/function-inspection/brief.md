# Design round: inspecting a function as data at compile time

You are designing one piece of the Dewy language. Read-only everywhere except `~/dev/tmp/par10/inspect/`. The checkout is `~/dev/dewy-lang`.

## Why

A Dewy-native database (`~/dev/tmp/par10/db/`, rounds 1–3, review-round3.md) wants ordinary Dewy filters to become indexed queries: `db.accounts.where((a) => a.balance <? 0)` or `[loop a in db.accounts if a.balance <? 0 a]`. The library can only do that if it can see the lambda's body (or the comprehension's filter) as data while compiling, the way C#'s LINQ uses expression trees. The same mechanism would serve other libraries: GPU kernels from ordinary functions, automatic differentiation, SQL generation, query planning, serializers, test assertions that print the failing subexpression, physics/units symbolic rewrites. Dewy has comptime and field reflection today but no way to inspect code.

David's principles (binding): no compiler magic; comptime library mechanisms that userspace could replicate are preferred; metatags are any meta functionality, preferably comptime-backed; remove friction even if the compiler works harder, and warn on performance cost; start from existing constructs before inventing syntax; unsafety opt-in; no context sensitivity without good reason.

## Read first

- `docs/LANGUAGE.md`: search for comptime, `const`, metatags/directives, reflection, generics, functions and lambdas, `@` handles.
- `docs/design/decisions.md` (all batches), especially comptime and metatag decisions; `docs/design/` for any comptime/reflection design.
- `~/dev/tmp/par10/db/review-round3.md` and `round3.md` (the dependency as stated).
- `resources/discussion_points.md` with `/usr/bin/grep` for comptime, macro, quote, reflect, expression, symbolic, autodiff (David's notes; he has thought about autodiff and symbolic expressions).

## Settle

- **What a library receives:** a typed, read-only description of a function's body (or a comprehension's parts) at compile time, and what it may do with it: inspect, translate to another form (a query plan, SQL, a GPU kernel), or fall back to running the ordinary function. Which parameters opt into this (a parameter type, a metatag on the parameter, or something else), so a caller writes an ordinary lambda.
- **What it may see:** operators, field reads, calls, constants, captured values (by value? as parameters?), and what happens with code it doesn't understand (fallback with a warning, an error, or a partial translation). Guarantee: translation never changes results.
- **Safety and hygiene:** the library can't change the caller's meaning or see private data it shouldn't; inspection is pure and deterministic; compile-time cost bounds and warnings.
- **Comprehensions:** how `[loop a in db.accounts if a.balance <? 0 a]` reaches the source's planner (the iterator can't see its caller's filter today).
- **Prior art**: C# expression trees and LINQ, Scala macros/quotes, Julia macros and generated functions, Zig comptime, Rust proc macros, Lisp quote, Python AST/inspect (Pony ORM), Kotlin compiler plugins, Swift result builders and macros, JAX tracing, Template Haskell. What each gets right and wrong for Dewy.
- **Alternatives without inspection**: typed field selectors/predicate objects (the database's v1 path), tracing by running the lambda on symbolic values (JAX/PyTorch style, possible with operator overloading), and when they are enough.

## Deliverables (under `~/dev/tmp/par10/inspect/`)

1. `round1.md`: lead with minimal examples, each in its enclosing function: a database filter, a GPU kernel, a test assertion that shows the failing subexpression, autodiff of a small function. Then the rules, then prior art and alternatives, then what is new (ideally a library type plus at most one metatag) with the existing-construct comparison.
2. `programs/`: at least 10 realistic programs across those uses, including fallback cases and code the library can't translate.
3. `dogfood.md`: grade 1–5 on obvious, discoverable, concise, safe by default and complete against C#, Scala, Julia, Zig, Rust, Python, citing lines for every score under 5. Iterate (round2.md, round3.md) while anything under 5 is fixable.
4. `names.txt`: new names as usage lines for a cold read.
5. `summary.md`.

Dewy conventions: space-separated arguments, `=?` equality, `@f` handle, `$name` metatag (scope settings at the top of their scope; tags on a single construct prefix it), `or_throw`, `??`, value-returning zero-arg calls drop `()` and void ones keep it, `fmt` for formatting, `.dewy` imports, dunder metatags are assigned functions (`$__drop__ = () => …`), `()` unscoped and `{}` scoped blocks. No model names in files. Budget about three hours.
