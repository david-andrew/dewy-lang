# Assumptions and their opt-outs

The bulletproof principle (decisions.md, 2026-10-23): every convenience axiom or
assumption the compiler makes has a metatag that turns it off and demands the
proof instead. This is the one list; the strictest configuration is a library
bundle that turns every entry off. Spellings marked *pending* await David.

| Assumption (default on) | Where | Opt-out metatag |
|---|---|---|
| A 64-bit counter or accumulator growing by a bounded amount per iteration or allocation cannot overflow | facts (fixed-width stores) | `$no_assumed_bounds` |
| An array's length fits in 2^56 bytes (the largest address space of any target) | facts (integer counters) | `$no_assumed_bounds` |
| Library-internal `assert`/`unreachable` are trusted invariants, not `panics` | effects (`panics`) | *pending* |
| Running out of memory and the runtime core (lib/core/rt.jo) are environmental, not `panics` | effects (`panics`) | *pending* (`$explicit_allocation_failure` covers allocation) |
| Library code's own obligations stay runtime checks under a static user policy | facts policy | *pending* |
| The library's raw-memory code is trusted by the arena escape check | ownership (arenas) | *pending* |
| `$runtime_assert` within one module does not make that module's own callers `panics` | effects (`panics`) | *pending* |
| Paths from command-line arguments or the environment do not warn at filesystem sinks | untrusted-input brand | *pending* |
| `$no_deadlocks`: the scheduler is fair, local computation terminates, external peers cooperate | deadlock certificates | stated assumptions of the theorem |

When a new assumption is added anywhere in the compiler or library, it gets a
row here in the same change.

`$bulletproof` (library bundle) turns every row off together with
`$no_hidden_costs`, `$explicit_allocation_failure`, `$finite_floats` and
`$no_deadlocks`.
