# Numerical stress test proposal

Recorded 2026-09-05. This is a proposed application and evaluation plan, not an implemented benchmark or a claim that every required feature works today. It complements the bootstrap compiler as a source of real program requirements.

## Design intent

David's clarification: Dewy will support IEEE floats as first-class numeric types, including arithmetic. The eventual scope includes the kinds of numerical capabilities available in NumPy and PyTorch. The initial priority is making the numeric types that people without specialist mathematical or engineering knowledge reach for work well and intuitively. Standard scientific numeric capabilities follow; float support is tentatively expected alongside the full matrix math system.

The evaluation should therefore ask whether the defaults are useful and predictable, and whether programs can deliberately choose other representations when needed. It should test the path from exact calculations to approximate ones as well as each domain in isolation. Float formats, promotion rules, exceptional-value behavior, and matrix APIs remain separate design decisions.

## First application: a household energy report

Build a small command-line program that reads timestamped power readings and tariff changes, then reports energy consumed, time-weighted average power, peak power, and cost per day and for the whole input. This combines quantities and everyday decimal arithmetic without requiring an advanced numerical method.

Start with deterministic data constructed at runtime. Add file input and formatting after the arithmetic works, so an I/O gap cannot conceal a numeric gap. Treat timestamps as elapsed time from a chosen origin; calendar and timezone semantics are outside this experiment.

Specify the data model before writing the implementation:

- A reading gives constant power until the next timestamp. The final timestamp closes the last interval. Split intervals at tariff and report boundaries.
- Compute energy as power times elapsed time. A tariff is an exact decimal amount per kWh. Money can initially be a rational amount in one declared currency; a new currency type is not a prerequisite.
- Keep internal totals exact. Apply an explicit rounding policy only when presenting a bill, stating whether rounding is per line or on the final total.
- Compute mean power from total energy divided by total elapsed time, so irregular sampling cannot silently turn it into an unweighted sample mean.
- Empty input, duplicate or decreasing timestamps, and zero total duration receive deliberate outcomes. Return input failures to the application; proof obligations must not become hidden library exits.

Begin with a hand-checkable fixture: 1.5 kW for 20 minutes, followed by 0.5 kW for 40 minutes, at 0.24 currency units per kWh. The exact totals are 5/6 kWh, 5/6 kW average power, and 0.20 currency units. Also report it using watts and seconds; changing the units must preserve the physical result.

Extend the dataset with irregular intervals, fractional tariffs, tariff changes inside a reading interval, zeros, large accumulated totals, and positive and negative adjustments under a stated policy. Feed values through function parameters and containers so the compiler cannot fold the entire workload.

## Focused cases around the application

| Case | What to establish |
| --- | --- |
| Decimal accumulation | Repeated additions of exact decimal amounts produce the exact expected total; formatting applies only the chosen rounding policy. |
| Word boundaries | Abstract integers and rationals preserve their values beyond machine-word-sized intermediates. Record current restrictions at function and container boundaries. |
| Reduction and cancellation | Fractions normalize correctly, including zero and negative values; large intermediate parts and coprime denominators expose representation cost. |
| Explicit numeric types | Fixed-width integers follow their documented rollover rules; checked rational/fixed operations follow their own error contracts. Test narrowing separately from arithmetic. |
| Approximation boundaries | Exercise positive and negative fixed-point conversion, halfway rounding, the smallest step, representable endpoints, and values just outside the range. |
| Units | Equivalent scales agree; incompatible dimensions are rejected with a useful diagnostic. Exercise dimensions through functions and arrays. |
| Proofs | Ordinary guards prove valid division and indexing; missing or invalidated facts produce actionable diagnostics. Include mutation and function calls. |
| Value semantics | Copying and editing stored readings or computed results preserves the originals; repeated temporaries are released. |

Use exact identities as additional checks: splitting an interval into equal-power pieces preserves energy; regrouping exact subtotals preserves the final total; converting units and converting back preserves exact quantities. Do not require these identities to hold bit-for-bit for approximate arithmetic.

## Second application: a repeated simulation

Add a driven, damped spring simulation with position, velocity, mass, stiffness, damping, force, and timestep carrying their physical dimensions. Begin with a scalar loop and a constant or piecewise-constant force; trigonometry and matrices are not prerequisites. Choose and document one integration method, such as semi-implicit Euler, and use that same recurrence for every representation.

Run a short exact-rational version as a reference for the discrete recurrence, then a fixed-point version with an explicit conversion boundary. Use rational coefficients that cause denominator growth as well as simple cases that cancel. Measure numerator/denominator sizes, allocation, elapsed time, and deviation from the exact recurrence as the number of steps grows.

Distinguish three sources of error: the integration method's approximation of the physical system, the representation's rounding of the recurrence, and a compiler/library defect. The exact recurrence is not an exact physical solution. Use an equilibrium case and a constant-velocity case as simple controls; use timestep refinement as a separate investigation of integration error. Set a resource limit for exact runs and report reaching it rather than silently changing the numeric representation to an approximate one.

The usability question is whether the program can start with intuitive defaults, reveal an expensive exact computation, and move deliberately to an approximate representation without rewriting its physical model or losing dimensional checks. Record casts, annotations, guards, and algorithm changes needed to make that move.

## Later phase: IEEE floats and matrix math

When those capabilities arrive, repeat the simulation with each supported float format and then with a batch of independent systems expressed through matrix or array operations. Compare the batch result against the corresponding scalar computation under a stated error budget.

Add small dot products, reductions, matrix multiplication, and a linear solve with independently known answers. Include cancellation, large dynamic range, well-conditioned and ill-conditioned inputs, and singular systems. A small matrix-based regression workload can exercise a more complete user workflow; full NumPy/PyTorch parity is an eventual scope direction, not this benchmark's acceptance criterion.

Cover shape checking, broadcasting, layout, scalar/array promotion, and typed external calls as those contracts are designed. Add signed zero, subnormal values, infinities, NaNs, overflow, and underflow according to the chosen IEEE contracts. Explicitly settle their relationship to the no-traps policy before asserting expected behavior. Document reduction order, fused operations, and any relaxed optimization policy; cross-target bitwise equality is required only where the language promises it.

## Independent answers and measurements

Use a separate oracle based on Python integers and `fractions.Fraction` for exact calculations, constructed from decimal strings or integer ratios rather than binary floats. Model fixed-point rounding with explicit integer arithmetic according to the documented operation, without translating the Dewy library's implementation. Preserve the small hand-calculated cases as checks on the oracle. For future floating-point tests, use a higher-precision reference and state absolute/relative tolerances, including an absolute bound near zero. A matching result from another compiler backend alone is not an independent oracle.

For each workload, retain the input or generator seed, expected result, source revision, target, toolchain, optimization settings, numeric types, and resource limits. Measure compilation separately from execution, excluding printing and input parsing from kernel timings. Report repeated-run timing distributions, peak memory, retained memory over repeated batches, and the representation choices reported by `dewy analyze`. Separate necessary growth of exact values from storage retained after values die.

Suggested sizes are 10, 1,000, and 100,000 energy intervals, and 10, 100, 1,000, then 10,000 simulation steps where resource limits allow. These are starting points for a sweep, not performance promises. Compare like-for-like algorithms and numeric semantics; later include conventional approximate implementations with their precision and error budgets reported alongside their runtime.

## Completion criteria and artifacts

The first milestone is a readable energy-report program with independently verified totals, explicit rounding, useful invalid-input handling, and measured scaling. The second adds simulation results that explain where exact and approximate representations are practical. The float/matrix phase waits for those capabilities instead of blocking the first two milestones.

For each implemented phase, keep:

- The runnable application, deterministic inputs, oracle, and invocation commands.
- Small regression tests for discovered failures, including expected diagnostics.
- A result table with correctness, numerical error where applicable, runtime, memory, and current limitations for each representation and target tested.
- A short account of programmer friction: necessary annotations, unexpected promotions, proof workarounds, confusing diagnostics, and missing operations.

A phase succeeds when its results meet predeclared correctness/error criteria, invalid cases behave according to their contracts, and resource use is explained. Set practical runtime and memory budgets before measuring each intended use case; do not invent a universal speed threshold. A feature gap is a recorded outcome and a candidate requirement, not a reason to quietly weaken the test.

Related contracts: [numeric types](../../site/reference/src/numeric-types.md), [physical quantities](../../site/reference/src/physical-quantities.md), [refinements and effects](../../site/reference/src/refinements-and-effects.md), and [value semantics](value_semantics.md).
