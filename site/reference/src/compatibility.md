# Implementation Compatibility

This appendix describes implementation coverage. It does not define the language.

## Hosted Dewy Compiler

The hosted compiler parses and statically checks Dewy, lowers supported programs to µDewy, and uses a µDewy backend to produce executable output.

Its implemented core includes bindings, fixed-width integers and Booleans, functions and calls, defaults and keyword arguments, static overloads, structured control flow, compile-time-anchored range values and multiiterators, strings, graphemes, streamed and bounded materialized interpolation, homogeneous arrays, structural objects, optional values, initial dictionary literal iteration, nonescaping explicit places, source imports, and initial time quantities.

Several normative areas are only partial. Notable examples include arbitrary-precision runtime integers, escaping and runtime-sized aggregate storage, user-defined interpolation conversions and unbounded result capacities, runtime range storage, function handles and closures, runtime dictionaries, general physical quantities, user-written generics, refinements, effects, and heterogeneous unions.

The hosted type system records `exception` as the parent of `error` and `undefined`. Automatic exception forwarding and `or_return` are not yet implemented, so those rules describe the intended language rather than current compiler behavior.

Generative `type of Parent`, hybrid `Type[field=value ...]` construction, and general structural-object intersection merging are also not yet implemented.

The detailed and continuously maintained checklist is [`dewy/status.md`](https://github.com/david-andrew/dewy-lang/blob/master/dewy/status.md).

## Platform Coverage

The quick installer and the complete hosted execution path currently focus on x86-64 Linux. µDewy has x86-64 Linux, WebAssembly, RISC-V, AArch64, and C backends, but Dewy's implicit libraries and host facilities are not yet equally available on every target.

The browser playground executes µDewy rather than the complete Dewy language.

## µDewy Compatibility

The defining compatibility goal is:

> Every well-formed µDewy program should compile and exhibit the same visible behavior under both the µDewy compiler and the full Dewy compiler.

That parity remains in progress and is checked by executable fixtures. Dewy's type checker does not select a weaker semantic mode merely because a file ends in `.udewy`; the suffix is conventional. µDewy's own compiler accepts only the strict subset defined by its specification.

See the [µDewy specification](/udewy/reference/) for the subset language and backend contracts.
