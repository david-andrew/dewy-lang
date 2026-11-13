# Independent regrade: callable inspection, round 3

The scores and program deductions below were fixed before opening `dogfood.md`. The author comparison is appended separately; those scores do not change mine. This is a paper review of the final rules, not a compiler run, backend conformance result, usability study or performance measurement. Proposed missing modules do not by themselves cost points.

## Rubric and comparison basis

Columns are **O** obvious, **D** discoverable, **C** concise, **S** safe by default, **F** complete for the demonstrated task. 5 means a clear, economical, fully specified path competitive with the best applicable peer workflow; 4 is a small teaching/coverage cost, 3 a material protocol or coverage gap, 2 a common requested operation unavailable, and 1 no useful path. Safety assesses the specified default contract with a correctly implemented library; it does not certify an implementation or a malicious translator. A deliberate compile rejection or domain-error value is safe, but can still score poorly on completeness. A 5 in concision does not assert superiority over every peer's character count.

I compare every row against the six workflows below. These are design judgments, not six executed ports or claims that all six languages have a built-in database/GPU/AD system.

| Peer | Database/filter and collection baseline | Assertions baseline | Numeric/AD and forwarding baseline |
|---|---|---|---|
| C# | Expected expression-tree parameters accept suitable ordinary expression lambdas; ordinary enumeration is a distinct execution path. Closure behavior must not be assumed to be Dewy's snapshot capture. | Ordinary delegates execute the callback; rich operands require a tree-aware library or other instrumentation. | Expression trees expose supported expression structure, while erasing to a delegate loses that tree interface. A GPU/AD implementation remains library work. |
| Scala | Typed quotes and macros provide explicit staged inspection, with a visible macro-author phase boundary. | Macro instrumentation can inspect a quoted expression and preserve evaluation through generated bindings. | Typed quotation is more general than this finite scalar AD subset, at a higher authoring/staging cost; an ordinary function is not automatically a quote. |
| Julia | Ordinary functions/collections are direct; macros can consume syntax, and generated functions have restrictions distinct from arbitrary function-body access. | A macro can receive assertion syntax instead of an already-erased callable. | Numeric generic code and explicit symbolic/dual types are relevant alternatives; general metaprogramming is broader than the proposed closed descriptor. |
| Zig | Ordinary iteration, typed data and comptime computations support explicit query descriptors; comptime evaluation alone is not a function-body API. | An ordinary checked assertion is simple; structured operand reporting needs deliberate data/instrumentation. | Generic numeric algorithms can accept deliberate alternate scalar types. Comptime does not itself solve arbitrary typed-callback inspection. |
| Rust | Ordinary iterator closures are direct; explicit typed query builders are a fair alternative. Procedural macros consume tokens rather than this resolved typed descriptor. | Macro syntax offers an explicit instrumentation boundary; arbitrary callback internals are a separate problem. | Generic numeric/dual types and explicit syntax macros are the relevant alternatives; callable erasure does not preserve a typed expression tree. |
| Python | Ordinary comprehensions are easy to read; AST/source recovery is a distinct, weaker inspection route than a compile-time typed contract. | Ordinary assertion evaluation is direct; AST/source instrumentation is additional machinery. | Generic numeric functions can use alternate scalar objects; runtime source inspection has availability limits and is not an exact typed-body contract. |

Primary sources checked for those mechanism distinctions: [C# expression trees](https://learn.microsoft.com/en-us/dotnet/csharp/advanced-topics/expression-trees/), [Scala typed quotes](https://docs.scala-lang.org/scala3/guides/macros/quotes.html), [Julia metaprogramming](https://docs.julialang.org/en/v1/manual/metaprogramming/), [Zig comptime](https://ziglang.org/documentation/master/#comptime), [Rust procedural macros](https://doc.rust-lang.org/reference/procedural-macros.html), [Python AST](https://docs.python.org/3/library/ast.html) and [Python source inspection](https://docs.python.org/3/library/inspect.html#inspect.getsource). These sources establish capabilities and boundaries; the grades are my inference from the Dewy programs and final proposal.

## Fixed scores

| Program | O | D | C | S | F |
|---|---:|---:|---:|---:|---:|
| 01 captured balance | 4 | 4 | 5 | 5 | 4 |
| 02 eager comprehension | 4 | 3 | 4 | 5 | 3 |
| 03 residual page | 4 | 3 | 4 | 5 | 3 |
| 04 optional limit | 5 | 4 | 5 | 5 | 4 |
| 05 effectful collection | 5 | 4 | 4 | 5 | 4 |
| 06 wrapping pixel kernel | 4 | 3 | 5 | 5 | 3 |
| 07 strict float fallback | 4 | 4 | 5 | 5 | 4 |
| 08 assert invoice | 5 | 4 | 5 | 5 | 4 |
| 09 assert short circuit | 5 | 4 | 5 | 5 | 4 |
| 10 assert once | 4 | 3 | 4 | 5 | 4 |
| 11 derivative calibration | 4 | 3 | 5 | 5 | 3 |
| 12 derivative loss | 4 | 3 | 5 | 5 | 3 |
| 13 derivative nonsmooth | 3 | 3 | 4 | 5 | 2 |
| 14 derivative domain | 4 | 4 | 5 | 5 | 4 |
| 15 private callback | 4 | 3 | 4 | 5 | 4 |
| 16 forwarded inspection | 4 | 3 | 4 | 5 | 4 |
| 17 effectful predicate rejected | 4 | 4 | 4 | 5 | 4 |
| 18 exact integer fallback | 5 | 4 | 5 | 5 | 4 |
| 19 runtime thresholds | 5 | 4 | 5 | 5 | 4 |
| 20 opaque derivative rejected | 3 | 2 | 3 | 5 | 2 |
| fixtures (shared setup) | 4 | 4 | 4 | 5 | 4 |

Floor: **2**, completeness of **13 and 20**, and discoverability of **20**. The fixture is included because the review brief asks for each program in the directory; the author labels it setup, not a twenty-first scenario.

## Line evidence and peer-relative reasons

All program paths below are relative to `programs/`. Every non-5 score has a reason here. The table above supplies the six comparison baselines throughout; the following paragraphs identify where each program falls short of that bar.

**01 — `01_captured_balance.dewy:5–12`. O4/D4: the two superficially similar predicates use different snapshots, and whether `@owing` is inspectable depends on inferred provenance and lexical disclosure (`round1.md:77`, `round2.md:49`). Dewy's snapshot rule is coherent, but a reader bringing C#/Python capture expectations needs teaching. F4: correct filtered rows are specified, but indexing depends on the not-yet-concrete plan/binding interface (`round3.md:97`); ordinary typed query builders across the peers make that representation explicit. C5/S5: short native code, original snapshot and exact fallback retained.

**02 — `02_eager_comprehension.dewy:5–8,11–13`. O4/D3: the `item or_throw` prefix is an explicit per-row failure edge whose optimizer eligibility is a special recipe shape (`round3.md:21`), rather than a discoverable consequence of a function parameter. C4: four lines replace the requested one-line filter. F3: the exact fallible one-liner remains unavailable (`round3.md:23`) and no hook authoring example closes the executor contract. Ordinary comprehensions/iterators in all six peers provide the fallback baseline; C#/Scala inspection mechanisms do not automatically solve arbitrary fallible comprehension pushdown either. S5: failures and the enclosing exit target are preserved.

**03 — `03_residual_page.dewy:3–7,12`. O4/D3: a plain bool callback parameter carries an inferred totality obligation not expressed by its return type; the source comment is not the checked summary (`round3.md:95`). C4: caller must learn separate query, page, scan budget and continuation contracts for a small filter. F3: runtime-selected opaque callbacks work only if checked totality survives selection; general recursion/unknown summaries do not. C# delegates, Scala functions, Julia/Zig/Rust/Python ordinary callbacks provide a simpler executable fallback; explicit builders in those workflows make supported query operations more visible. S5: rejecting an unknown guarantee is safer than assuming termination.

**04 — `04_optional_limit.dewy:5–9`. D4: translating `none`, `??` and unary negation requires knowing the backend subset and warning rather than just the source expression. F4: optional/default nodes may execute locally, so portable indexed execution of this complete task is not specified. C#/Scala option/null distinctions and Julia/Zig/Rust/Python ordinary optional-value handling provide comparison points; none justify importing SQL NULL semantics. O5/C5/S5: the Dewy expression and exact local behavior are clear.

**05 — `05_effectful_collection.dewy:5–10`. D4: readers must discover why an otherwise similar comprehension cannot use the collection hook. C4: explicit row-error handling adds ceremony compared with an ordinary in-memory comprehension. F4: the effectful traversal is complete as ordinary code, but the common optimization-transparent promise has a deliberately narrow eligibility envelope. Across C#/Scala/Julia/Zig/Rust/Python, ordinary sequential traversal is the appropriate comparison, not a provider pretending to preserve skipped prints. O5/S5: visitation of a, b, c is explicit and correctly retained.

**06 — `06_wrapping_pixel_kernel.dewy:3,7–9`. O4: `compute.map` hides a device/CPU choice with material error and cost consequences. D3: exact wrapping compatibility, dispatch failure and fallback rules must be learned outside the call. F3: this is a narrow scalar-word pilot, not a generally usable GPU callback facility (`round3.md:53–57,89`); the CPU-shaped assertion does not establish device execution. C#/Scala expression/macro libraries, Julia/Python alternate numeric workflows, and Zig/Rust explicit typed kernels are all relevant alternatives, with their own backend work. C5/S5: concise and correct fallback is specified.

**07 — `07_strict_float_fallback.dewy:4–7`. O4/D4: the same map spelling may dispatch to a device or sequential CPU execution, learned through capability diagnostics. F4: exact CPU output is specified; compatible device acceleration is not demonstrated and cannot be assumed. This earns credit for being safer than a precision-changing backend in any of the six peer workflows, without claiming those peers universally demote floats. C5/S5: no extra caller spelling is required to preserve the chosen precision.

**08 — `08_assert_invoice.dewy:5,8–9`. D4: rich operand detail depends on the finite pure scalar instrumentation subset and allocation policy (`round3.md:59`), not simply on calling `check.that`. F4: the report is expected prose, with no concrete report API or closed scalar coverage list; unknown expressions lose detail. Compared with C#/Scala tree/macro assertions, Julia/Rust syntax macros, Zig explicit assertion data and Python source instrumentation, the call is excellent but its library contract is still less complete. O5/C5/S5: no repeated execution and error-as-value behavior are clear.

**09 — `09_assert_short_circuit.dewy:4,7–9`. D4/F4: the requested skipped-node report depends on supporting the short-circuit graph and guarded rational division; the assertion evaluator's exact scalar vocabulary is not enumerated (`round3.md:41,43,59`). Whole-thunk fallback is correct but cannot promise the illustrated operand report. Across the six peers, preserving a skipped division is basic correctness; syntax/tree instrumentation must additionally preserve that guard. O5/C5/S5: the source guard and nonexecution requirement are explicit.

**10 — `10_assert_once.dewy:4–8`. O4/D3: an inferred, inspectable named closure can nevertheless be uninstrumentable because it mutates shared state; distinguishing provenance from purity is a substantial teaching point. C4: a separately named callback and `$capture` are necessary for this effectful demonstration. F4: the only supported diagnostic is site/bool, losing the rich-expression purpose. Ordinary callbacks in C#/Scala/Julia/Zig/Rust/Python can execute once; macros or tracing do not deserve credit for rerunning them. S5: whole-thunk execution once is the correct fallback.

**11 — `11_derivative_calibration.dewy:5–8`. O4/D3: `derivative` means real-interpretation forward AD with runtime float rounding and snapshot-constant captures, rather than arbitrary float-function differentiation. F3: only one scalar input/output and a short primitive list are supported (`round3.md:63–69`). The six peers' explicit symbolic/dual numeric designs remain viable alternatives; C#/Scala code-data mechanisms can instead support a library translator, at a staging cost. C5/S5: concise and explicit error propagation.

**12 — `12_derivative_loss.dewy:6–13`. O4/D3: local bindings look completely general but only a finite recognized scalar graph is admitted, and the derivative has the same nontrivial numeric contract as 11. F3: a hand-unrolled two-point loss succeeds, while an ordinary data loop/array model is outside the initial subset (`round3.md:41,65,69`). The fixed small example should not stand in for general model training available through broader numeric libraries; no claim is made that any peer language includes AD intrinsically. C5/S5: the shown loss is concise and its derivative oracle is correct.

**13 — `13_derivative_nonsmooth.dewy:4–10`. O3/D3: expressing abs as an ordinary conditional changes a supported primitive into a compile rejection; recognizing this boundary requires library-subset knowledge. C4: a concise normal function must be rewritten to the canonical primitive. F2: it cannot differentiate the piecewise function even at a nonzero input, although the shown zero input also has a genuine mathematical domain problem. Across all six peer workflows, an explicit symbolic/dual implementation could handle a chosen abs primitive; more general source/macro mechanisms can support richer control rules but do not prove smoothness automatically. S5: refusing an unsupported derivative is sound.

**14 — `14_derivative_domain.dewy:4–6`. O4/D4: readers must learn that a valid primal float operation can yield a derivative-domain error, and how that differs from 13's compile rejection. F4: the program has no recovery/matching example and exercises only abs(0), while the defined domain also excludes nonfinite intermediates and zero division (`round3.md:67`). The six peer workflows need an explicit convention at nondifferentiable points too; returning an arbitrary subgradient is a different contract. C5/S5: the error is concise and explicit.

**15 — `15_private_callback.dewy:3–10`. O4/D3: an explicit plain function annotation both states a callable type and erases inspection authority, unlike an inferred handle within the defining domain. C4: the factory and annotation are ceremony needed to demonstrate that distinction. F4: secure site/bool fallback works but rich diagnostics are unavailable; cross-module publication/erasure cases are absent. C#/Scala tree-versus-function distinctions offer useful precedent; Julia/Zig/Rust/Python mechanisms do not supply Dewy's proposed lexical secrecy contract for free. S5: the existing secret equality deliberately reveals only its bool; the captured string stays sealed.

**16 — `16_forwarded_inspection.dewy:4–9`. O4/D3: helpers must learn the special two-phase wrapper rather than simply the ordinary function type; most caller examples never mention it. C4: the long wrapper type is visible API ceremony. F4: the easy forwarding case is shown, but heterogeneous storage, dynamic choice and budget outcomes are only rules, not concrete API examples. C# tree types and Scala staged expressions have comparable preservation requirements; Julia/Zig/Rust/Python explicit descriptors can also preserve their own data without arbitrary callback reification. S5: explicit forwarding preserves rather than recreates authority.

**17 — `17_effectful_predicate_rejected.dewy:6–13`. O4/D4: two ordinary-looking filtering paths differ because `where` imposes purity/totality while a collection body may print; readers need that contract. C4/F4: the common request to count visited records needs materialization and an ordinary loop, losing query pushdown and adding code. All six peers can express that ordinary sequential loop, while provider/macro libraries must document different execution contracts. S5: rejecting shared mutation avoids changed invocation counts.

**18 — `18_exact_integer_fallback.dewy:5–8`. D4: the fallback boundary depends on resolved arithmetic and codec capability, not a visible fixed-width type. F4: correctness is specified, but indexed/remote execution for the exact operation remains unavailable on incompatible adapters; large value storage is itself a database capability dependency. C#/Scala/Julia/Zig/Rust/Python workflows need explicit exact-number support or a correct local path too; ordinary Python big ints are a particularly natural semantic comparison. O5/C5/S5: the requested value and no-approximation rule are clear.

**19 — `19_runtime_thresholds.dewy:5–10`. D4: the one-template property relies on hidden static provenance and runtime binding keys, knowledge absent from the call. F4: the comment asserts bounded specialization but there is no inspectable plan-count/build-size gate or concrete binding implementation (`round2.md:100–106`, `round3.md:97`). C#/Scala parameterized code-data plans, explicit descriptors in Zig/Rust, and generic/runtime numeric data in Julia/Python are relevant baselines; none require a compiler instance per threshold value. O5/C5/S5: clear ordinary loop and runtime data.

**20 — `20_opaque_derivative_rejected.dewy:3–10`. O3/D2: adding an ordinary function annotation/helper boundary makes a simple square unavailable for differentiation, despite a literal at the caller; the remedy requires discovering an intrinsic-backed wrapper. C3: a common abstraction needs a different public parameter type and provenance knowledge. F2: the displayed task has no derivative at all; it must change the API or use another numeric mechanism. C# delegates versus expression trees and Scala functions versus quotes have a comparable tradeoff; explicit generic/dual APIs in Julia/Zig/Rust/Python avoid body recovery for suitable generic functions but also require a deliberate interface. S5: there is no deceptive f(x), zero or finite-difference fallback.

**Shared fixture — `fixtures.dewy:3–10`. O4/D4: a type-derived schema and index selector are proposed library contracts whose inspected/pure status is implicit at these calls. C4: schema, index and three explicit insert/error-discard statements are setup overhead for tiny cases. F4: only a small exact-int/optional schema and success path are supplied; no opening/storage-failure setup tests the iterator failure recipe. All six peer workflows need database setup too; the deduction concerns this design's unclosed selector/codec contract rather than penalizing setup uniquely. S5: insert failures remain explicit and no source repository was modified.

## Author comparison (added after fixing the scores)

Read `dogfood.md` only after writing the fixed scores and line deductions above. Compared all **100 matched scores** (20 programs × five axes); **60 agree exactly**, **40 differ by one**, and **0 differ by two or more**. There is no author fixture vector to compare.

**Differences of two or more: none.** My floor is 2 at 13/20 completeness and 20 discoverability; the author's floor additionally includes 02 completeness, which I score 3 because the explicit fallible comprehension is a usable, longer path even though the exact requested spelling is unmet.

Most safety differences are rubric differences: the author deducts for unimplemented enforcement; I grade the specified safe-default contract and explicitly withhold implementation certification. I am more optimistic by one point about several correct fallback paths' completeness, and stricter by one on discoverability/obviousness of some hidden capability and provenance boundaries. This does not eliminate any design finding in `review-round3.md`.
