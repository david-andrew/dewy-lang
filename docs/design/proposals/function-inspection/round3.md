# Round 3: final contract and remaining limits

This is the final amendment to rounds 1–2. It follows a line-by-line review of the 20 programs and the iterator, effects, float, proof and secret rules. Programs are proposed design specimens; no compiler, database, GPU or user study ran. The recommendations below are provisional, and no name is cold-tested.

## 1. Correct the fallible-comprehension example

Round 2's header example is **withdrawn**. LANGUAGE.md:3894–3904 gives `loop item in inbox or_throw` special per-item forwarding for a merged inbox; after an ordinary iterable it forwards only failure of the iterable expression before starting. It does not currently forward arbitrary iterator elements. A stored database collection cannot inherit that special case by analogy.

Set the proposed database iterator contract explicitly: `next` yields Account, a storage failure, or none; on failure it yields that failure once and then exhausts, retaining snapshot cleanup. Ordinary Dewy can handle it without new propagation syntax:

```dewy
report = <S>(db:S) => {
    let rows = [loop item in db.accounts {
        let a = item or_throw
        if a.balance <? 0 a
    }]
    loop a in rows { printl(a.id) }
}
```

This is the final program 02. `or_throw` keeps its enclosing-function target. `$__collect__` eligibility may recognize this explicit error-demultiplexing prefix as well as the infallible one-source shape; the recipe retains the error edge, and the compiler preserves the target instead of hiding the prefix inside a new lambda. A returned executor error takes that original edge, with the baseline cleanup. Other nonlocal control flow still declines.

The exact requested `[loop a in db.accounts if a.balance <? 0 a]` can reach the source planner on an **infallible** source whose element is Account. On this fallible database source its element includes an error, so `a.balance` is ill-typed. No amount of inspection fixes that. Recommendation: keep errors explicit and use the ordinary form above or `.where(...).all or_throw`. If the literal one-line comprehension is nonnegotiable on fallible storage, settle a general fallible-iteration contract separately; do not disguise that language decision inside the code-inspection type. This is an unmet part of the exact-spelling target, not a completed all-5 feature.

This distinction also resolves effectful program 05: handle each source error, then print each visited account in primary-key order. The planner declines because printing is observable. It must not prefilter with an index and suppress the print for Ben.

## 2. A finite initial representation

The design permits descriptions of general code, but the initial implementation need not model every construct to benefit callers. Keep a complete opaque fallback and start with this stable data contract:

| Description component | Required information | Must not expose |
|---|---|---|
| Body | descriptor version, F, root, indexed nodes, capture schema, source origin | runtime environment, host pointers, arbitrary source-file reads |
| Node | local ID, kind, result type/arity, ordered child/control edges, effect/cost summary, source origin | mutable AST handles, synthetic name lookup |
| Scalar operation | exact resolved semantic operation, operand/result types, relevant settings | an unqualified token such as `+` as its entire meaning |
| Field | declaring type/field identity and accessible projection | inaccessible owner storage |
| Capture | slot identity, type, snapshot/shared classification, disclosure status | runtime value at compile time, unrelated captures |
| Call | selected callable signature/identity, call edges, optional authorized body | recursive arbitrary callee/source access |
| Opaque | type/arity, conservative effects, call capability when applicable, reason, safe source origin | invented summaries or “unknown means pure” |

Descriptor kinds initially include Parameter, Constant, Capture, Field, Binding, ScalarOperation, ShortCircuit, Conditional, Call, Return and Opaque. General loops, unsafe regions, cleanup and complex mutation can initially be Opaque **with their complete conservative effect/control summary**. Unsupported graph structure does not make the executable callback invalid. The broad list in round 1 described the eventual schema, not a prerequisite to ship every form.

Nodes referring to type values are compile-time data. A runtime interpreter such as the assertion/AD library must lower to its own closed tagged scalar/value representation, checked for every node. There is no cast from arbitrary NodeId into a runtime T. Capture binding tokens lower only to typed authorized accessor stubs, not a closure-memory pointer; the wrapper's original lifetime and move rules apply.

New descriptor versions preserve identity of existing semantic operations. An unknown version/kind yields opacity and fallback, or a precise consumer error when there is no semantic fallback. Index checks never match by field text. A local function shadowing `abs`, `sin` or `=?` does not inherit a recognized primitive's semantics; an alias retaining the very same resolved intrinsic identity does. Version/settings/capability keys are part of every cached plan.

## 3. Fallback is consumer-specific

| Consumer | Unsupported operation | Missing purity/other precondition | Runtime failure |
|---|---|---|---|
| Database `where` | Keep original total predicate as local residual; warn at source, explain work | Reject query callback; materialize then use an ordinary loop | Storage/query-budget errors; no incomplete page labeled complete |
| Collection hook | Decline to exact ordinary comprehension | Decline optimization; preserve legal effects/control | Original failure edge and cleanup |
| `compute.map` | Ordinary sequential CPU callback over same input values; warn | Reject a callback whose effects conflict with map's documented independent-element contract | Device errors before observable dispatch may permit CPU choice; after uncertain execution do not replay; report error |
| `check.that` | Invoke original thunk exactly once; report site/bool, warn about missing operand detail | Effectful thunks are legal only on this uninstrumented path | Original failure propagates; false returns AssertionFailed |
| `diff.derivative` | Compile error for unavailable body/rule; no ordinary-function “fallback” | Compile error for effects/state/control outside supported AD subset | NotDifferentiable for supported but invalid domain values |

Map accepts pure independent scalar callbacks in this proposal, not arbitrary IO. CPU fallback is a normal library loop; it is not today's float-demoting `gpu` upload path. Device capability checks happen before execution. A driver failure after possible execution is not permission to repeat external effects (none are accepted), or to conceal a device error by promising a completed result. Memory/resource failures use ordinary policy; the final examples do not claim `$bulletproof` support.

Assertions instrument only the finite pure scalar subset with equivalent evaluation and inert primitive operand formatting. A potentially allocating exact-int expression must obey the active allocation policy; under explicit failure it either has an equivalent error-aware evaluator or takes whole-thunk fallback. Capturing values and report allocation cannot invalidate a strict no-allocation contract: that mode rejects the rich report or uses an already specified allocation-free reporter. It is not silently exempted from effects. A branch skipped by `and` or `??` is recorded as “not evaluated”; it is never called for its value.

## 4. State the AD semantics honestly

`diff.derivative` differentiates the **real-arithmetic interpretation of recognized numeric operations**, with runtime primal/derivative arithmetic carried out in the function's declared scalar precision. It is not the mathematical derivative of the bit-pattern-to-bit-pattern IEEE rounding function. That distinction is necessary even for `x*x`: rounding gives a step function, while the useful AD derivative follows the algebraic operations.

The first subset supports one float scalar input/output, immutable scalar captures, local scalar bindings, `+`, `-`, `*`, supported nonzero division, and canonical `abs`. It constructs a library graph for forward primal/tangent evaluation. Operands evaluate in source order. The primitive rule for multiplication is `dx*y + x*dy`, with that order and no reassociation/FMA unless the original permitted settings explicitly allow it. The returned derivative closure owns the same captured snapshots. Runtime captures are constants with respect to the selected input. Multiple-parameter Jacobians, reverse mode, arrays and units are future library work, not necessary compiler features.

At abs(0), a zero denominator, nonfinite input or a nonfinite intermediate in this initial mathematical domain, return NotDifferentiable with a safe node location. Positive/negative finite abs inputs have derivatives +1/-1. This error denotes the library's supported derivative domain, not a claim that an underlying ordinary float operation is ill-typed. Program 14 exercises abs(0). Program 13's arbitrary conditional is rejected statically: branch-sensitive derivatives and boundary proofs are outside this initial library. The diagnostic suggests canonical `abs` for that exact pattern; it must not automatically change arbitrary piecewise functions.

An opaque derivative callback (program 20) has no sound automatic derivative. Accepting it and returning f(x), zero or a numerical estimate would change the requested operation. The remedy is to preserve Function<F> through the helper or use an explicit symbolic/dual-number library. The inability to differentiate arbitrary ordinary code is a real completeness limit compared with mature AD libraries.

The strict “translation preserves the original function” promise applies to primal evaluation, database predicates and kernels. AD is a separately requested mathematical operation. Presenting its different numeric result as a violation of equivalence would confuse two contracts; claiming it is the exact derivative of all IEEE behavior would be false.

## 5. Compiler and library responsibilities, without hidden magic

Compiler responsibilities are: retain authorized body provenance; type-check lambda against ordinary F before wrapping; produce the sealed descriptor and typed binding stubs; run `prepare` with pure bounded evaluation; preserve phase separation; and lower eligible collections through the new hook while fixing reference types, exits, lifetimes and resource/effect obligations. These are substantive implementation work. One type name and one metatag do not imply one small patch.

Library responsibilities are: classify supported operations, validate closed plan algebra, bind authorized captures, interpret or execute plans, implement target primitive semantics, maintain database snapshot/order/error contracts, build AD rules, format safe diagnostics and publish cost reports. Userspace can replicate these parts. Userspace cannot reconstruct body provenance from today's opaque function value, so the base type is not fully library-definable.

In particular, the compiler can type-check an executor's signature but cannot infer semantic equivalence from that signature. A library returning a wrong plan is a library bug. This proposal deliberately does not add a general proof checker or unchecked “equivalent” assertion. The strongest hostile-library guarantee remains unsolved; the stated contract assumes correct primitive adapters, as ordinary arithmetic/collection libraries do.

Runtime settings cannot disappear into a static plan. Preserve settings dependencies as runtime inputs when permitted; clone bounded plan variants only for semantically distinct known policies, with their effects in the public result. If a setting would change an operation's meaning and no equivalent dynamic executor exists, take original execution. Do not key specializations on every runtime setting value. Compile-time-fixed settings participate in semantic identity.

## 6. Residual risks and the smallest next experiment

There is no measured compilation or runtime gain in this paper. Inspection pays for itself only if a demanded plan avoids real work; do not build whole-program reification first. The DB pilot's plausible gain is eliminating N row decodes in favor of K candidates, but source-order restoration may cost O(K log K), and a no-match scan may still examine everything. Measure selectivity, decode cost, ordering and compiler instruction counts before making a performance claim.

Recommended first implementation experiment, separately authorized: one Account comparison over an immutable captured exact int, one opaque callback fallback, one privacy rejection, and a minimal eager collection recipe. Compare against typed explicit field descriptors on the same valid snapshot. Include negative/huge ints, changed outer captures, an empty source, source failure, stable order and plan budget exhaustion. Acceptance is identical values/error contracts and bounded planning, plus a useful measured avoided-work bound. Stop the optional optimization pilot if the bound is under the project's bar; the explicit predicate alternative remains useful.

The general exact one-line **fallible** comprehension, mature AD coverage, exact floating GPU support, public stable descriptor schema, totality inference, privacy implementation, compile-budget tuning and independent naming/usability tests are still work. A fully compiler-enforced guarantee against buggy target translators is a larger undecided problem. These limitations are retained in dogfood scores instead of papered over by new names.

No new decision was added to the repository. Names.txt is a candidate inventory in usage context, **not** the required shuffled, names-only three-reader test. This sub-agent did not spawn other readers. The coordinator should not mark these names “tested” or the proposal ready for open_decisions.md on this evidence alone.

## 7. Two library-author obligations made explicit

**Totality is not an effect row.** The initial checker can establish termination for the finite acyclic scalar subset and calls carrying a checked totality summary; it must leave general recursion/loops unknown. Exact integer/string primitives have their standard finite-input contracts and active resource policy. An opaque callback may retain a checked summary even when its body is undisclosed. Program 03 needs inferred “pure and total callback” requirements propagated to callers, analogous to existing callback safety obligations but with this additional totality property. This is new checking work, not supplied by writing `:>bool` or `& no_effects`. If a dynamically loaded callback has only that return type and no checked summary, the query call is rejected. No totality-by-trust metatag is introduced here; an ordinary materialized loop remains available.

**Planning outcomes must be handled.** Conceptually `prepare` yields a compile-time outcome containing P and diagnostics, or BudgetExceeded; the consuming library must choose its residual recipe or a compile-time error in the latter arm. It cannot invoke an arbitrary library planner after the budget is exhausted just to ask for fallback: the generic residual recipe is constructed outside that optional transaction, with fixed work. The public interface must provide typed outcomes; the round-2 pseudocode abbreviates this mandatory match. Planner diagnostics are immutable data `(severity, authorized node origin, reason, cost)` returned to the intrinsic, not arbitrary output/host I/O. The compiler emits them deterministically and validates that a source origin belongs to the supplied descriptor. Runtime explain records are ordinary library data. The precise convenience member names and heterogeneous P encoding belong in the implementation prototype; their absence is a remaining library-author completeness issue, not a claim that the simple pseudocode is ready to compile.
