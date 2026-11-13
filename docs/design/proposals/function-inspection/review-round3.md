# Independent review: callable inspection, rounds 1–3

**Revise before adopting the general multi-consumer design. One must-fix finding: optional query planning must not consume the budget needed to construct a supported derivative.** A database-only prototype is reasonable, after making the library-author boundary concrete. `code.Function<F>` is the clearest of the proposed inspection boundaries when ordinary, normally typed Account lambdas are a requirement; it is not the smallest way to build useful database filters.

Scope: read the brief, rounds 1–3, summary, names, all twenty scenarios and shared fixture; all decision batches in `docs/design/decisions.md`; the relevant function, capture, generic, effect, integer, secret, iteration and comptime rules in `docs/LANGUAGE.md`; the reflection design and symbolic/snippet discussion notes; and the database round-3 dependency/review. Later amendments supersede earlier examples. Independent scores were written to `regrade-round3.md` before opening `dogfood.md`; author comparison followed. This is a design review, not implementation, execution, measurement, a naming study or an equivalence proof. Only the two requested output files were written; the checkout was read only and no commit was made.

## Must-fix

### M1 — Optional optimizer work can make an unrelated supported semantic operation fail to compile

**Severity:** must-fix for the proposed multi-consumer contract. **Rules:** `round2.md:98–104` (one transaction budget, nested charging and the compilation-wide optional pool); `round3.md:55,97` (AD has no original-function fallback and an exhausted outcome must become a diagnostic). **Affected examples:** `programs/11_derivative_calibration.dewy:7`, `12_derivative_loss.dewy:11`, `14_derivative_domain.dewy:4`.

**Concrete scenario:** enough distinct, legal database-filter planning requests occur earlier in the stable source/dependency order to consume the 10,000,000-step optional pool. Each request respects its own per-site cap and can correctly use residual execution. A later tiny derivative of `x*x`, otherwise within the supported AD subset and its own site cap, now receives BudgetExceeded. AD cannot execute the original square as its derivative, so the build fails. Moving that derivative before the queries, or changing the cost of an unrelated query optimizer, makes the same supported derivative constructible. The same issue affects any future semantic consumer with no valid fallback.

**Why it blocks:** source-order determinism is useful for optional optimization choices, but is not an adequate reason for optional optimization to determine availability of a requested semantic operation. This conflicts with the standing orthogonality/context preference (`docs/design/decisions.md:483–485`) and with the proposal's own separation of optional planning from mandatory evaluation (`round2.md:102`). This is a budget-policy defect, not a demand to infer termination or allow unlimited compilation.

**Suggested fix:** distinguish optimization transactions, which consume a compilation-wide optional pool and always have a prebuilt fallback, from demanded transformations such as AD. Give demanded operations their own explicit deterministic resource contract, independent of prior optional work; alternatively defer such consumers from this first version. Shared implementation, graph interning and memoization can remain. Charge nested requests to their correct parent and specify whether a semantic consumer may contain an optional suboptimization. Do not merely raise the shared limit.

**Acceptance:** a supported small derivative has the same success/rejection result before and after adding unrelated budget-exhausting query optimizations. The queries warn and fall back; an AD operation exceeding its own demanded limit diagnoses its own site. Memoization and source reordering cannot turn optional work into a semantic build dependency.

## Should-fix

### S1 — Close the library-author interface before calling the mechanism settled

**Severity:** should-fix before a compiler prototype. **Rules:** `round2.md:7–24,73`; `round3.md:43,75,97`; usage inventory `names.txt:4–11`. **Programs:** `03_residual_page.dewy:3–6`, `16_forwarded_inspection.dewy:4–5`.

**Scenario:** a library author tries to write the proposed `where`. `prepare` is first described as returning serializable P directly and later as returning a typed compile-time outcome. Runtime capture binding is pseudocode, and the authoritative final round explicitly leaves P encoding and convenience signatures unsettled. An executor needs statically checked runtime slot types, while opaque and budget-exhausted cases need an original callback without manufacturing a runtime compiler object. Those are precisely the phase/type boundaries this proposal exists to specify.

**Suggested fix:** supply one complete, language-shaped author example for a single comparison, with the actual outcome match, declared ordinary plan type, authorized capture-binding operation, original callable storage and execution. Show both body-available and body-opaque cases through the same public signature, and state whether P is fixed by the planner's result type. If a descriptor family needs heterogeneous P, show its finite union or deliberate erasure. An opaque callback carrying a checked totality summary needs a concrete checked-boundary example as well. No need to design all AST variants or every convenience method first; do not introduce unlisted public members as implementation accidents.

### S2 — Step limits are not yet a complete compile-time or binary-size bound

**Severity:** should-fix. **Rules:** `round1.md:133`; `round2.md:98–106`; `round3.md:75,85–89`. **Program:** `19_runtime_thresholds.dewy:5–10`.

**Scenario:** many distinct inspected bodies each retain a near-limit plan/artifact, or hidden provenance forces multiple ordinary generic/executor specializations before `prepare` runs. The global step pool does not itself state a global retained-byte/output-code budget. Per-transaction evaluator allocation accounting does not obviously charge compiler graph retention, type/provenance analysis, generated backend compilation or emitted specialized machine code. A cap of 32 callable alternatives within a request does not by itself bound the number of requests or every family forwarded through ordinary generic code. The comment “one body template” is credible for 19's runtime thresholds, but does not establish a general code-size guarantee.

**Suggested fix:** define the accounting boundary for graph extraction, planner execution, validation, retained plans, emitted byte artifacts and provenance-driven specialization. Add an aggregate retained/output-byte policy and a bounded specialization policy, or explicitly narrow the claim to work performed by the evaluator. Warnings need actual counts for retained/emitted growth as well as steps, site, fallback and reason. Do not charge runtime threshold values to a static specialization key.

The existing warnings are useful: half-budget warning, once-per-site exhaustion warning, unsupported operation/cost reason, plus runtime explain. Keep those. The proposed default numbers are unmeasured policy candidates, not evidence of acceptable overhead. Test 1/10/100 distinct functions, many runtime thresholds and nested descriptor families; gate compiler instruction counts on the flagship panel, include reached library/instance work, and report executable/backend artifact sizes. No desktop wall-clock claims are warranted.

### S3 — The privacy specimens exercise erasure and secrets, but not lexical disclosure itself

**Severity:** should-fix. **Rules:** `round2.md:45–55`; `round3.md:33–45`. **Program:** `15_private_callback.dewy:3–10`.

**Scenario:** the current negative disclosure specimen has both an explicit plain-function boundary and a secret-typed capture. Either can prevent extraction, so it cannot isolate whether lexical privacy works for a nonsecret private capture. A separate case must distinguish same-domain inferred alias, erased alias, explicitly published Function, and a callback obtained from another module. Another library could also attempt to copy a capture token from one descriptor into an otherwise type-compatible plan for another.

**Suggested fix:** next round add isolated two-module specimens with an ordinary private scalar, an unused captured field, a permitted public field projection, a secret literal beneath an operation, and descriptor-token mixing. Expect opaque execution where publication is absent, authorized referenced-scalar access where explicitly disclosed, no whole-object/environment access, and sanitized diagnostics. Show named-function and literal-lambda disclosure separately. These are adversarial acceptance cases for the proposed rules, not a demonstrated leak in the final text. No need to expose private values in a review report.

### S4 — Publish the exact initial consumer subsets and keep the first implementation to database filters

**Severity:** should-fix. **Rules:** `round3.md:41–43,49–69,87–97`. **Programs:** `08_assert_invoice.dewy:5`, `09_assert_short_circuit.dewy:4`, `13_derivative_nonsmooth.dewy:5–9`, `20_opaque_derivative_rejected.dewy:3–10`.

**Scenario:** program 09 requests a rich short-circuit report for guarded integer division. The final schema includes ShortCircuit and ScalarOperation, but the assertion evaluator's closed scalar vocabulary is not enumerated; it is unclear whether rational intermediates are in the first instrumented subset or the whole thunk falls back. Similarly, general Conditional exists in descriptors but is deliberately unsupported in first-version AD. “Representable”, “accepted as an ordinary callback”, and “translated by this consumer” are different promises.

**Suggested fix:** publish a per-consumer support matrix with exact primitive identities/types, allocation/error handling and opacity outcome. State program 09's expected rich-report eligibility, rather than relying on its comment. First implement one captured Account comparison, a checked opaque residual, privacy rejection and bounded planning through `.where`. Keep GPU, assertions and AD as design stress cases, with no claim they ship together. Add the collection hook after the iterator/error recipe has a concrete authoring contract. This reduces implementation scope without pretending the exact comprehension target has already been delivered.

### S5 — The call-site disclosure and erasure rules need visible tooling and a cross-module story

**Severity:** should-fix. **Rules:** `round1.md:75–77`; `round2.md:45–49`. **Programs:** `01_captured_balance.dewy:6–8`, `15_private_callback.dewy:7–8`, `16_forwarded_inspection.dewy:4–9`, `20_opaque_derivative_rejected.dewy:3–10`.

**Scenario:** an inferred local handle can retain authorized body provenance, whereas an explicitly written F boundary erases it. A helper refactor can therefore preserve executable results yet turn indexing into residual work or AD into rejection. A literal lambda also intentionally discloses referenced ordinary scalar captures to a consumer that would not receive those scalars through an ordinary opaque callback interface.

**Suggested fix:** signatures, hover and generated docs must show both the inspection/disclosure contract and inferred callback requirements. Lost-inspection diagnostics should identify the exact boundary, not just the final consumer. State the behavior for an imported generic helper, separate compilation and finite runtime selection. Keep the explicit Function parameter type; do not hide inspection solely in a library implementation. This is an ergonomic cost of the chosen model, not evidence that every implicit lambda conversion is unsafe.

## Notes and checks that passed

### N1 — Capture privacy and hygiene are coherently specified, within the stated trust boundary

**Severity:** note. **Rules:** `round1.md:81–97`; `round2.md:43–57`; `round3.md:31–45`.

No concrete private-capture extraction follows from the final rules. A literal callback intentionally publishes only its accessible referenced ordinary values/projections; it does not publish the frame, unused fields or arbitrary private closure storage. Definition-domain access is lexical, erased factory results stay opaque, secrets remain sealed, tokens are unforgeable and typed, and diagnostic source text must be sanitized. Source spelling cannot substitute for resolved field/operator identity, and no syntax splicing or rebinding is offered. Copy/move/lifetime rules belong to the original closure rather than an extra environment copy. These are substantive compiler obligations requiring S1/S3 implementation tests.

The consumer **can** learn an ordinary captured threshold when the callback deliberately grants it. That is an intentional disclosure boundary, not a guarantee that the library learns nothing beyond calling a bool function. This needs the visibility in S5. Likewise a public callable's signature does not authorize recursively opening its callees.

### N2 — Fallback is the original executable callable where such a fallback exists

**Severity:** note. **Rules:** `round1.md:107`; `round3.md:49–59,69`.

Database residuals and CPU kernels use original execution, not an approximate AST interpreter. A collection decline retains the original loop. An effectful assertion runs the original thunk once and loses detail, rather than executing an instrumented partial attempt and replaying it. Supported pure assertion graphs still require the equivalent checked evaluator promised in the text. AD is a requested different mathematical operation and correctly rejects opacity; returning the original function, zero or numerical differencing would be false fallback. Device failure after uncertain execution is not permission for a concealed replay. These are the right distinctions.

### N3 — A read-only descriptor cannot enforce arbitrary translator correctness

**Severity:** note with a material acceptance limitation. **Rules:** `round2.md:61–69`; `round3.md:77–79`; original brief's “translation never changes results” requirement.

A buggy library can return an incorrectly planned query or GPU program while obeying memory safety and every descriptor-access rule. The final proposal explicitly acknowledges this. Read-only typed data guarantees what the library sees and can access, not that its output implements the advertised meaning. Closed primitive mappings, independent plan validation and conformance tests are reasonable ordinary-library correctness measures; signatures alone are not an equivalence proof.

I would accept “correct translators must preserve the reference evaluator; unknown cases decline” as the first-version contract, with the backend/validator included in the trusted implementation. I would not sign off a stronger compiler-enforced guarantee against faulty arbitrary translators. If the original brief intends that stronger promise, it remains an unmet acceptance condition; this review neither assumes a universal proof checker nor quietly treats tests as proof. There is no new `$unsafe` requirement merely because an ordinary library can have a functional bug.

### N4 — `$__collect__` can preserve eager semantics, but it is an additional protocol

**Severity:** note. **Rules:** `round2.md:73–94`; `round3.md:7–25`.

The final contract first type-checks the ordinary comprehension, evaluates its source once, retains its reference type/cardinality, iterator/snapshot acquisition, source order, failure edges, cleanup and enclosing exit targets. It forbids silently making `[]` lazy. Only inert, equivalent capture lifting is allowed; empty sources do not evaluate row bodies. Live/shared reads, effectful iterators, effectful bodies, nested/combined sources, multi-yields and unsupported control flow decline. In program 05, Ben's print cannot be skipped. A fallible item is explicitly demultiplexed in program 02 and the hook retains the original `or_throw` target.

These are sound obligations assuming a correct source executor and validator; I found no final rule authorizing changed evaluation order, laziness or errors. They are stronger than today's iterator interface and require new compiler lowering. A source's hook cannot gain extra privileges to skip observable `next` work. The exact `[loop a in db.accounts if a.balance <? 0 a]` is still ill-typed for the proposed fallible item union; the final round accurately records that unmet target. A new fallible-iteration decision should be evaluated on its merits, rather than inserted as hidden optimizer behavior or rejected merely because the compiler lacks it today.

### N5 — Totality, exact arithmetic and AD's numeric meaning are not hand-waved away

**Severity:** note. **Rules:** `round2.md:69`; `round3.md:63–71,95`; `docs/LANGUAGE.md:688–717,924–943,4268–4322`.

Purity does not establish termination; unknown callback totality cannot be assumed in a query that skips rows. Program 03 therefore depends on genuinely new checked-summary propagation, not a comment or bool result type. The text acknowledges that work. Exact ints, optional values, resolved overloads, strict floats and settings must remain distinct; strict-incompatible float devices choose CPU execution. The arithmetic examples' expected values are consistent: the captured threshold selects a/c, optional limits produce no uncovered rows, wrapped max-word arithmetic gives 4294967294, and the two-sample loss has slope 10w−26, hence −6 at w=2.

AD explicitly differentiates the real interpretation of recognized operations, with runtime scalar rounding and a documented derivative domain. It is not differentiating the IEEE bit-pattern function. Unsupported control and opaque functions diagnose; abs(0) returns a domain error. That is a defensible limited library operation, though substantially less complete than the broad use-case list suggests. Program 15's secret equality is permitted by the existing rule that equality intentionally returns one plain bool bit; no implicit reveal of the string is required.

## Which mechanism I would pick

| Mechanism | What it buys | What it loses / new obligation | Choice |
|---|---|---|---|
| Typed field selectors / predicate objects | Ordinary typed data can own both evaluation and a query plan; supports indexed comparisons, conjunctions, optional cases and dynamic filters without arbitrary body reification. Smallest useful database mechanism. | Does not preserve the ordinary Account lambda or comprehension. `<?` currently returns bool, so pretending a selector comparison returns a predicate is itself a language change; use ordinary named constructors/methods. Does not recover arbitrary assertions, concrete-float kernels or AD bodies. | The baseline and fallback product path; measure it first. |
| Symbolic / dual values via operator overloading | Useful straight-line generic numeric code and AD can be library mechanisms; matches David's explicit symbolic-type notes (`resources/discussion_points.md:1158–1191`). | A concrete `float64` or Account callback cannot silently receive a proxy. A real bool branch or lazy boolean cannot be captured by sampling one execution. Unknown code must not run just to discover a graph. Requires deliberate generic/symbolic APIs and a restricted domain. | Keep as a complementary numeric library; not a transparent substitute for this brief. |
| Metatag on a parameter | Naturally advertises meta functionality and could reuse a comptime-backed inspection service. No necessary new quote syntax. | It needs the same compiler provenance, phase, privacy and budgeting machinery. It must also explain what value/type the function body receives and how inspection survives forwarding/storage. If it merely elaborates F to the same wrapper, it adds spelling without reducing mechanism. | Viable if a concrete design provides a simpler phase contract; not dismissed just because it is an annotation. No such reduction is shown here. |
| `code.Function<F>` parameter | A first-class type can expose static body/prepare separately from original runtime call; survives explicit forwarding; preserves ordinary lambda typing before conversion. One reusable code-data boundary, not a macro expansion language. | Intrinsic-backed two-phase values, hidden provenance, typed capture binding, lifetime/effect/totality checking and budgets are substantial compiler work. Explicit plain F can erase inspection. Does not alone expose comprehension filters. | Preferred inspection boundary if ordinary typed lambdas are the requirement; first use database filters only. |

The comparison is about mechanisms, not counting new tokens. `code.Function<F>` plus `$__collect__` is not the smallest database design; it is a candidate for both ordinary-lambda and ordinary-comprehension demands. A metatag would not make reification library-definable, and an intrinsic-backed type does not contradict the preference for ordinary comptime libraries when it honestly exposes the missing primitive. Resolved body access is a new decision alongside existing field reflection; the old AST/source-generation exclusion is preserved because no general replacement-code compiler is added (`docs/design/argparse_and_reflection.md:98–108`).

## Recommended first version and decision readiness

Use a **database-only `code.Function<F>` pilot through `.where`**, compared against an ordinary typed-field predicate implementation over the same snapshot. Choose one immutable captured exact-int comparison, checked opaque residual, a lexical privacy rejection and exhausted-planner fallback. Establish the avoided-decode bound before optimization work; measure compiler instructions and output size, then run the required focused/quick and batch full/bootstrap/fixed-point gates when compiler code actually changes. If the gain cannot meet the project's bar, retain the useful explicit-predicate path and report the failed optimization experiment. No backend or benchmark was run for this review.

Assertions would offer a smaller backend experiment, but would not resolve the database motivation, and `check.that` introduces another assertion interface alongside fact-producing `$assert`/`$runtime_assert`. GPU and AD introduce their own numeric and failure domains. Keeping them as stress tests is valuable; bundling four implementations and the collection protocol into a first version is unnecessary. Defer `$__collect__` until the explicit query path proves its staging and error contract. This is a scope recommendation, not a claim to have fulfilled the exact comprehension requirement.

The proposal declares the intrinsic-backed type, wrapper members and one assigned dunder hook as new. The later rounds additionally acknowledge new checked totality propagation, bounded planning and typed capture stubs; these must appear in the decision inventory, not be characterized as existing comptime. The proposed spelling uses existing type/tag syntax and the accepted assigned-dunder convention. I found no surviving direct contradiction to the decided capture, no-traps, secrecy, strict-float or scope-setting rules. The runtime-settings amendment correctly prevents fixed planning from erasing runtime semantic choices (`round3.md:81`).

Names are untested candidates. `names.txt` is usage context, not shuffled names-only evidence from three independent readers. Neither this review nor the author's paper grades complete that required process. No public name should advance as tested, and no sub-5 should be relabeled all-5 on the strength of this review. The independent floor and author comparison are in `regrade-round3.md`: floor 2 at 13/20 completeness and 20 discoverability; no matched score differs from the author by two or more.

**Recommendation in two sentences:** use `code.Function<F>` for a database-only pilot, measured against typed field descriptors, when ordinary typed lambdas are the intended surface. Defer `$__collect__`, GPU and AD until the explicit filter path closes the authoring, privacy and cost contracts; separate demanded-transformation budgets before adding AD.
