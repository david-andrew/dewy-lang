# Variadic C functions (D51): round 1

Dewy has no way to declare a C function that ends in `...` (`printf`, `snprintf`, `open`,
`ioctl`, `fcntl`). LANGUAGE.md mentions "an argument to a variadic C function" but gives no
spelling; `$extern` takes only `name=` and `lib=`. The implementation language has one
(`@variadic(n)`, the count of fixed parameters), and the backends already pass C's variadic
arguments correctly: System V's vector-register count in `al`, float promotion to `double`,
Apple arm64's stack placement (tests/fixtures/core_ffi/variadic.c). Declaring a variadic
function as if it were fixed is undefined in C and breaks on Apple arm64, where variadic
arguments go on the stack.

No spelling exists in docs/design, resources/discussion_points.md or the archived reference
(site/reference/src/interoperability.md, functions-and-calls.md). The archive's direction for
Dewy's own functions is `...rest` capturing the arguments no earlier parameter claims
(functions-and-calls.md); a bare `...` already ends the positional run there, so parameters
after it need names.

## Candidates

| | Spelling | Notes |
|---|---|---|
| A | `printf = (format:string ...args):>int32` | a rest parameter, as Dewy's own `...rest`; visible in the list |
| B | `$extern(variadic=true)` before `printf = (format:string):>int32` | a third keyword beside `name=` and `lib=`; the list shows only the fixed part |
| C | `printf = (format:string ...):>int32` | C's spelling, but `...` already means "named parameters follow" |
| D | `printf = (format:string ...args:c_args):>int32` | A with a type naming what crosses |

## Semantics taken with any spelling

Each extra argument crosses as a fixed one would: fixed-width numbers, `bool`, `ptr<T>`,
`ptr<T>?` and strings (a `char *`); `int` and records by value are errors, as they are for
fixed parameters. C's default promotions apply: `float32` goes as `double`, narrower integers
as `int32`. Calls are `$unsafe`, as every C call is: nothing checks the extras against a
format string.

## Cold read (round 35 of ~/dev/tmp/naming-1107: a Sonnet, b Haiku, c Fable)

Seven lines, shuffled, each a declaration and a call. Every reader read every spelling
correctly (number and types of the arguments passed) and called each less safe than declaring
every parameter.

| Spelling | a | b | c | Notes |
|---|---|---|---|---|
| A `...args` | 4 | 2-3 | 4 | c: "suggests a Dewy-style collected rest" |
| B `variadic=true` | 3-4 | 3 | 3-4 | c: "the declaration looks like a two-parameter function while the call has three, which is surprising" |
| C bare `...` | 4 | 3 | 4 | "reads exactly like the C prototype" |
| D `...args:c_args` | 3 | 2 | 3 | b and a unsure it compiles |

Recommendation: A. It reads as well as C's spelling, keeps the extras visible in the parameter
list (B hides them), agrees with the direction for Dewy's own rest parameters, and does not
reuse the bare `...` that already means something else (C). Not dogfooded yet.
