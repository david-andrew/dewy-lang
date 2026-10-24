# Assumptions and their opt-outs

The bulletproof principle (decisions.md, 2026-10-23): every convenience axiom or
assumption the compiler makes has a metatag that turns it off and demands the
proof instead. This is the one list; the strictest configuration is a library
bundle that turns every entry off. Spellings marked *pending* await David.

| Assumption (default on) | Where | Opt-out metatag |
|---|---|---|
| A 64-bit counter or accumulator growing by a bounded amount per iteration or allocation cannot overflow | facts (fixed-width stores); a `parallel` range of 2^63 or more values runs as 2^63 - 1 (lib/std/thread.jo) | `$no_assumed_bounds` |
| An array's length fits in 2^56 bytes (the largest address space of any target) | facts (integer counters) | `$no_assumed_bounds` |
| Library-internal `assert`/`unreachable` are trusted invariants, not `panics` | effects (`panics`) | *pending* |
| Running out of memory (an array shape whose element count passes int64 included) and the runtime core (lib/core/rt.jo) are environmental, not `panics` | effects (`panics`) | *pending* (`$explicit_allocation_failure` covers allocation) |
| A failure of the environment inside the library (a graphics driver refusing a call, no pipes for the test runner, standard input ending before `input_int`/`input_float` get a number: `__environment_failure`) is environmental, not `panics` | effects (`panics`) | *pending* |
| Library code's own obligations stay runtime checks under a static user policy | facts policy | *pending* |
| The library's raw-memory code is trusted by the arena escape check | ownership (arenas) | *pending* |
| The library's own drop hooks (a lock guard releasing its word) cannot fail | ownership (hooks: compiler/ownership.jo) | *pending* |
| `$runtime_assert` within one module does not make that module's own callers `panics` (a scoping assumption, not an assumed bound: `$no_assumed_bounds` does not cover it) | effects (`panics`) | `$assume_local_asserts=false` (spelling provisional; `$bulletproof` should include it) |
| A path taken whole (from arguments, the environment, input or anywhere else) has no base to escape: the file-system operations' `$warn_if path isnt? SafePath` takes it as safe | contained paths (compiler/safe_paths.jo) | `$confine_external_paths` (spelling provisional; `$bulletproof` should include it) |
| `$no_inf` takes values entering its scope (parameters, fields, elements, call results) as finite; `$no_nan` no longer assumes them | floats (compiler/floats.jo) | *pending* |
| `$no_deadlocks`: the scheduler is fair, local computation terminates, external peers cooperate | deadlock certificates (compiler/deadlock.jo; safety_and_concurrency.md) | stated assumptions of the theorem |
| A foreign call or system call inside an audited adapter (`$audited_wait`, spelling provisional) waits only on the outside world, never on a task of the program | deadlock certificates (compiler/deadlock.jo) | none: the audit is a person's claim, like `$unsafe`; write `$audited_wait` only in each adapter (never for a module, never in a bundle) |
| The library's certified protocols (`serve`, `pipeline`: lib/prelude/protocols.dewy) wait only as documented | deadlock certificates | *pending* (a model-checking gate for the primitives, as planned for the expert lane) |

When a new assumption is added anywhere in the compiler or library, it gets a
row here in the same change.

`$bulletproof` (library bundle) turns every row off together with
`$no_hidden_costs`, `$explicit_allocation_failure`, `$finite_floats` and
`$no_deadlocks`.

## Decided rules

Moved here from the decisions ledger ([decisions.md](decisions.md)), which keeps
a pointer to each rule. The wording is David's.

### Safety configuration (2026-10-21)

- Safety configuration: orthogonal boolean metatags plus purpose-named,
  library-defined bundles. Docs present a loosest-to-strictest ladder:
  `$prototype`, `$runtime_checks`, the default (no traps), `$explicit_copies`,
  `$no_hidden_costs`, `$explicit_allocation_failure`. No numbered levels.
- Strict lane is `$no_hidden_costs`: a library-defined module bundle over
  function rows (`& no allocates`, …) plus `$explicit_copies` semantics; forbids
  hidden allocation, detach, implicit costly copies and `$runtime_checks`/
  `$prototype`; `$no_hidden_costs = false` opts a scope out. `$realtime` is
  reserved for a future stronger bundle (no blocks, bounded stack).

### Metatag names and the bundle (2026-10-23)

- Metatag names: `$no_assumed_bounds` disables the 64-bit counter progress
  axiom and any similar "can't happen in practice" bound, demanding real
  proofs. `$bulletproof` is the strictest-everything library bundle:
  `$no_hidden_costs`, `$explicit_allocation_failure`, `$finite_floats`,
  `$no_deadlocks`, `$no_assumed_bounds`, and every future opt-out listed in
  [assumptions.md](assumptions.md).

### Counter progress axiom and `$no_nan` (2026-10-23)

- Counter progress axiom: default on. A 64-bit counter or accumulator that
  grows by a bounded amount per iteration or allocation cannot overflow;
  32-bit and narrower counters get no axiom. An opt-out metatag (spelling
  pending David) disables it and requires a real proof.
- `$no_nan` does not assume incoming values: callers prove not-NaN, or it is
  checked under `$runtime_checks`.
