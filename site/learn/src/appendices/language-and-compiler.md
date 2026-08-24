# Language Design and Compiler Support

The main chapters describe the intended Dewy language. This appendix explains how to interpret features whose design or implementation is still moving.

## Two Separate Questions

A feature can have settled language semantics before the compiler implements it. Conversely, an experimental implementation can exist while some edge cases remain open. Documentation therefore tracks two independent kinds of maturity:

- **Design maturity:** settled, provisional, or open.
- **Implementation maturity:** implemented, partial, or not yet implemented.

Settled design remains part of the normal Learn and Reference prose. Provisional sections state the boundary of what has been decided. Open questions live here or in the project's design notes rather than being presented as established syntax.

## Current Compiler Snapshot

The hosted compiler currently covers a substantial core: bindings and scope, fixed-width integer and Boolean operations, functions and calls, defaults and keyword arguments, static overload selection, conditionals and loops, compile-time-anchored range values, streamed and materialized string interpolation, grapheme operations, homogeneous arrays, structural objects, optional values and narrowing, initial dictionary literal iteration, explicit nonescaping places, source modules and imports, and the initial `Time`/`Duration` facilities.

Important partial areas include arbitrary-precision `int` representation, arrays whose storage requirements escape their current scope, interpolation through user-defined conversions, ranges with runtime anchors or runtime storage, general physical dimensions, function handles and closures, runtime dictionary operations, and broader host support.

Major design or implementation frontiers include floating-point and exact real arithmetic, general user-written generics and unannotated generic inference, growable dictionaries and sets, complete refinements and effects, exception-value forwarding and recovery, broadcasting and multidimensional array operations, pattern matching and general unions, generators as stored values, automatic-call behavior inside function-valued member routes, and general compile-time evaluation.

This summary is intentionally broad. The repository's [implementation status](https://github.com/david-andrew/dewy-lang/blob/master/dewy/status.md) is the authoritative detailed checklist.

## Platform Notes

The quick installer and the full hosted execution path currently target x86-64 Linux. The µDewy bootstrap compiler and browser playground cover additional backend and WebAssembly scenarios, but the browser playground runs µDewy rather than the complete Dewy language.

Platform availability is an implementation property, not a restriction in the language design.

## Reading Examples

Unless a chapter says that a design is provisional, its examples illustrate intended Dewy. Some examples may be ahead of the current compiler. Examples that are part of compiler tests are checked continuously; future documentation tooling will make this classification explicit in source metadata while keeping the reading experience uncluttered.

For exact present-day behavior, use the implementation status and executable tests. For exact intended language rules, use the [Dewy Language Reference](../../reference/).
