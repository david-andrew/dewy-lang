# Design round: combining failures, David's design

You are designing one piece of the Dewy language. Read-only everywhere except `~/dev/tmp/par12/errors/`. The checkout is `~/dev/dewy-lang`.

## David's design (binding direction, decisions.md batch 10, 2026-11-13)

- `e1 & e2` combines two failures; its type is `E1 & E2` and a match arm can name it (`<E1 & E2> => …`). It is an **unordered set**. `&` and `and` are the same operator (only precedence and idiom differ).
- `v as T` takes one part out of a combined value (`result as E1`), for any combined value, not only errors (e.g. take a subset of a combined object). A field present in several parts is reached through `as`; reaching it directly is ambiguous.
- Two failures of the same type (`e1a & e1b`) are a compile error pointing to the **error stack**: `type of error & array`, ordered, whose `__and__` pushes and returns the stack (so `stack & e` and `stack &= e` append).
- Errors carry metatag members (where they occurred, stack traces) produced **on demand**: demand-driven at compile time, not stored when nothing reads them.
- `or_throw` unchanged for now; `or_throw(& previous)` (an operator section, an existing feature) is the shape if combining on forward is wanted later.

His sketch:

```dewy
let E1:type = type of error
let E2:type = type of error
let f1 = ():> int|E1 => ...
let f2 = ():> int|E2 => ...
combined_fn = () => {
    r1 = f1()
    r2 = f2()
    if r1 is? error and r2 is? error
        return r1 & r2
    else if r1 is? error
        return r1
    else if r2 is? error
        return r2
    return r1 + r2
}
log_error = (e:E1) => ...
main = () => {
    match combined_fn() as result {
        <E1 & E2> => printl'Both errors: {result}'
        <E1> => printl'just E1: {result}'
        <E2> => printl'just E2: {result}'
        <int> => printl'no errors: {result}'
    }
    result = combined_fn()
    if result is? E1 log_error(result)   # works if E1 or E1 & E2 was returned
    if result is? E1 & E2
        e1, e2 = result as E1, result as E2
}
```

## Open points to settle (David asked for these)

1. **Handlers must not silently swallow parts.** If `E1 & E2` is accepted where `E1` is, `combined_fn() ??<E1> 0` would discard the `E2`, and a function declared `:> int | E1` could return `E1 & E2` with the caller unaware. Candidate rules: (a) `??<E>`/`or_throw<E>` match only an exact type; (b) a handler consumes a combination only when every part is covered (`??<E1 | E2>` consumes `E1 & E2`, `??<E1>` passes it through); (c) others. Using a part (`as E1`, an `E1` parameter, `is? E1`) stays allowed. Pick one with examples, and say what plain `??` (no type) does.
2. **Cancellation.** Batch 4 (D4 Q1) decided `Canceled` passes through `??`; David now has "a bad feeling" about exceptions bypassing `??` and asked to see the reasoning again. Find the original example and reasoning (`docs/design/decisions.md` batch 4, `docs/design/proposals/concurrency/unified/` v4/v5: cancellation is level-triggered, so `let job = jobs.receive ?? continue` would spin forever after Ctrl-C, and `?? 0` would turn Ctrl-C into a value and exit 0). Then weigh honestly: keep the rule; or let `??` catch `Canceled` with a compile-time warning/error at each `??` that can see it (`$explicit_cancellation` already does this under `$bulletproof`); or another option. How does whichever rule apply to `Canceled & E1`? Present the trade-off with minimal examples, each in its enclosing function, so David can decide.
3. **Distinct error types per operation.** David asks whether libraries should give specific error types (`FileWriteFailed`, `FileCloseFailed`) so automatic cleanup combines naturally with `&`, using the stack only for genuine repeats (two files both failing to close). Design the standard library error vocabulary for files, sockets, processes and transactions this way, and say exactly what automatic cleanup produces: `body & cleanup` when the types differ; a stack when the same type can occur more than once (several owners of one type); what generic code does when `T & U` turns out to have `T == U` at instantiation.
4. **`as` on combined values in general:** projection semantics, a proven vs unproven `as` (today `x as T` must be proven), records combined with `&` whose fields conflict, and how `is?` relates.
5. **The error stack:** its type spelling, iteration order, `is? E1` on a stack (true if any element is? or never?), matching, reporting, and accumulating in a loop.
6. **Origins and traces:** the metatag member names (check `resources/discussion_points.md` with `/usr/bin/grep` first), what "demand-driven at compile time" means precisely (a static site id that is always available vs a trace captured at creation only if some code reads `$trace`), and their cost.

Also read, for comparison only: `docs/design/proposals/errors/round4.md` (the earlier `ErrorGroup` proposal) and `review-round3.md`. Compare honestly at the end: where David's design is better, and any case where it is worse.

## Deliverables (under `~/dev/tmp/par12/errors/`)

1. `round1.md`: lead with minimal examples, each in its enclosing function: combine two, take one out with `as`, match all four cases, a handler that must not swallow, cancellation, a stack accumulating in a loop, cleanup with distinct error types, where an error came from. Then the rules for points 1–6, then the comparison.
2. `programs/`: at least 12 realistic programs (form validation with a stack, batch file processing, cleanup of a written file, two output files both failing to close, a parallel block with several failing items, a library adding context, a CLI printing locations, retry, cancellation during cleanup, generic code combining `T & U`, combined non-error records with `as`).
3. `dogfood.md`: grade each program 1–5 on obvious, discoverable, concise, safe by default and complete against Python, Go, Rust, TypeScript and Swift, citing lines for every score under 5. Honest grades; an independent reviewer will check. Iterate (round2.md, round3.md) while anything under 5 is fixable.
4. `names.txt`: new names as usage lines for a cold read.
5. `summary.md`.

Dewy conventions: space-separated arguments, `=?` equality, `@f` handle, `$name` metatag, `or_throw`, `??`, `??<E>`, value-returning zero-arg calls drop `()` and void ones keep it, strings formatted only with `fmt`, `.dewy` imports, dunder metatags are assigned functions (`$__drop__ = () => …`), `()` unscoped and `{}` scoped blocks. No model names in files. Budget about three hours.
