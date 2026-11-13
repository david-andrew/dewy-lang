# Round 2: make the boundaries executable in principle

This amends round 1. The first paper pass found five fixable holes: no concrete staging operation, insufficient capture authority, a hook that could bypass its reference recipe, vague work budgets, and fallible iteration elided in the database comprehension. No compiler was run.

## 1. Staging is explicit on the library side

`code.Function<F>` is an intrinsic-backed **two-phase value**. Its descriptor is static information associated with the concrete wrapper, not runtime heap AST data. Its executable closure and captures are runtime values. `F` is the public type; a hidden static provenance component is retained by generic specialization, as callable identity is today. A heterogeneous collection of wrappers carries a finite descriptor family or an opaque case; it never creates runtime compiler objects.

Add `f.prepare(@planner)` to this type's interface. At compilation the evaluator invokes the ordinary pure planner on `f.body`; at runtime this expression is the planner's serializable result P. No planner execution depends on runtime captures. P may contain data and statically resolved function handles; it may not contain a descriptor, compiler pointer, type value in a runtime slot, or a handle to a compile-time local. This is an extension to current evaluator support for indirect/capturing calls and constant materialization, not syntax that already works.

The planner receives a reasoned opaque body when provenance is erased, body disclosure is unavailable, or representation is over budget. It can return a residual plan. A generic wrapper preserving Function<F> retains this option; a plain F boundary deliberately loses it. Direct `f.body` reads are legal only in demanded compile-time contexts, never at runtime. Merely assigning `const plan = ...` is not a phase annotation.

Conceptual library flow (API pseudocode; the domain engine helpers are library implementation work):

```text
where(source, predicate: Function<(T -> bool)>):
    require the existing database purity/totality contract for predicate.call
    static_template = predicate.prepare(plan_predicate)
    environment = bind referenced capture slots once from predicate
    return Query(source, static_template, environment, predicate.call)

plan_predicate(body):
    recognize resolved field(balance), exact-less-than, runtime-slot(0)
    otherwise return Residual(reason, original-call)
```

For `(a:Account) => a.balance <? threshold`, the representation is:

```text
parameters: p0 : Account
captures: c0 : int, read-only snapshot, runtime, disclosed scalar
n0 = Parameter(p0)
n1 = FieldRead(n0, Account.balance) : int
n2 = Capture(c0) : int
n3 = Compare(exact_integer_less, n1, n2) : bool
return n3
```

Planner output is data such as `Range(field_id=balance, relation=less, value_slot=c0)` plus ordinary fallback. The threshold's value is neither known nor needed while compiling. Binding uses the closure's captured snapshot, not a second read from the outer variable. The original callback remains the reference for residual execution.

A library builds its own validated plan nodes with ordinary constructors. Describing a Call supplies its **resolved identity**; asking for a callee body does not automatically inline it. A memoized worklist may request an allowed description once per specialization. Recursion back-edges remain edges; no recursive AST expansion.

## 2. Privacy is a disclosure boundary, not a closure dump

Wrapping a **literal lambda** intentionally supplies its written body as data to the Function parameter. Hover/signatures must say “inspects body and referenced ordinary captures.” That boundary grants the consumer the body operations and **referenced, nonsecret, accessible immutable values** needed to evaluate/translate them. It does not grant the enclosing frame, unused locals, whole capture objects when only a projection is authorized, or mutable environment storage.

This is a real difference from passing an opaque function value. It must not be hidden in an unannotated library implementation. Call-site syntax remains ordinary because the parameter's explicit Function type provides the disclosure contract, analogous to expression-tree parameters. Supplying an already-erased F cannot silently reopen its closure.

A named function/closure is opaque outside its definition's disclosure domain by default, even if its handle is callable there. Its author may return/store it explicitly as Function<F> to publish a description. No new public/private keyword or publication metatag is invented. Definition-domain access means lexical access to the original declaration/captures, not unrestricted access to every file in the compilation. Existing inferred aliases preserve provenance within that domain; returning an unannotated plain function from a factory does not export private captures.

A wrapper has no `.environment`, arbitrary `get_capture`, string name lookup or source-file API. A capture descriptor contains an unforgeable typed binding token. A checked plan constructor can request a runtime value binding only for an authorized slot of exactly that type, to a typed ordinary executor parameter. It can read that authorized scalar; this is intentional disclosure, not protection against all information a consumer could infer. Passing a literal comparison on a regular captured threshold authorizes its value as a query parameter. Capture projections must preserve ordinary evaluation timing; a getter/call cannot be reclassified as an inert field read.

Secret-typed values, secret-producing operations and inaccessible captures stay sealed. Do not expose a literal or constant-folded payload under a secret subtree. Diagnostics use sanitized spans/labels and redact values; they cannot print raw source containing a secret literal. A secret comparison can execute in the original closure, but the default query translator cannot extract its operand for SQL. Explicit `.reveal` in caller code is the established way to disclose a secret; this proposal adds no alternate escape hatch.

A plan can retain opaque operation capabilities only to invoke the original authorized operation with its ordinary arguments; capabilities neither open a closure nor reveal private fields. Unsupported/private subtrees remain local or cause the consumer's explicit unsupported-operation error. A default test assertion must not recursively call a formatter defined by user code to obtain operand text; use known primitive formatting, secret redaction, and type-only placeholders for other values.

These checks protect representation and lexical authority. They are **not a sandbox for a malicious library given ordinary data**: any library can print a public parameter, return an incorrect bool, or misuse an explicitly revealed value. No read-only AST can prove otherwise. Safe memory/visibility is enforced by the language; functional correctness of a translator is a separate library obligation.

## 3. The equivalence claim has a precise scope

The required contract is observational equivalence on the same valid logical input, snapshot, language version and semantic settings: values/types, row multiplicity/order, ordinary effects, short circuit, specified failures, cleanup and termination. Timing and incidental allocation are not exact trace equivalence, but declared allocation/resource constraints remain obligations. Invalid storage can fail differently when a plan never visits corrupted bytes; it may never manufacture valid data from corruption. Backend outages/resource exhaustion are reported honestly, not mapped to an empty result.

A typed description guarantees that the library sees the original meaning; it does **not** prove arbitrary target code implements it. For the first translator, use a closed algebra of reviewed primitive mappings and a separately implemented plan validator. It checks field/type identity, slot authority, comparator/codec compatibility, residual placement, stable order, snapshot identity and needed preconditions. Unknown mappings are rejected. No `assume_equivalent=true` escape hatch is offered to ordinary callers.

The validator's semantic primitives and target runtime remain trusted library implementation, exactly as an ordinary sorter or integer library is trusted to implement its advertised result. A third-party translator returning arbitrary SQL/SPIR-V is not magically certified. Calling a plan `Verified` without checking it would add no guarantee. Current `$proof` (LANGUAGE.md:1409–1425) proves a small fact language, not universal equivalence of SQL engines, GPU kernels, or terminating programs. This proposal does not claim otherwise.

Required conformance gates compare the optimized executor with the reference evaluator on adversarial inputs and validate algebraic primitive laws. Tests are evidence, not a universal proof. Approval of a fully compiler-enforced “even a buggy library cannot change results” promise would require another proof/translation-validation design; it is not delivered here.

When a backend cannot match exact int, optional equality, text/grapheme semantics, float signed zero/NaN/subnormals, failure order or stable sorting, decline that mapping. Guarded specialization is permitted only when the guard uses already-evaluated inert data and the wrong branch cannot run. Unknown totality is distinct from known divergence. Reordering or skipping a potentially diverging predicate is forbidden even if its effect row is empty.

## 4. Make the comprehension hook a planning protocol

`$__collect__ = (recipe) => ...` is an ordinary pure function assigned on the source type and invoked only during optional compilation planning. It receives no runtime store handle. `recipe` describes source type/slot, iterator/reference semantics, ordered filter/projection bodies, output cardinality/type, failure/exit edges and snapshot/order requirements. It returns either Decline(reason) or an Execution value: a static plan template plus a statically resolved ordinary executor handle. At runtime the compiler supplies the already-evaluated source and typed capture bindings to that executor.

The compiler first checks the ordinary comprehension. Output type, error effects, exit targets, captures, source evaluation and lifetime follow this baseline, regardless of whether a hook exists. The hook cannot add a callback expectation that changes `a` to a proxy or changes integer/float inference. The result must conform to the baseline output contract. Changing a source's hook must not make a previously legal lambda mean a different operation.

The hook cannot emit code or alter arbitrary caller nodes. The source library's closed execution-plan constructors and validator enforce the constraints in section 3. The compiler does not trust an untyped “replacement expression.” Ordinary-source iteration remains available to the executor and fallback without recursively invoking the same collection hook.

The initial eligible shape is one by-value source, zero or one pure total bool filter, and an identity or pure total single-valued projection. A header's `or_throw` on iterator errors can be retained as an explicit failure edge; it does not turn a source failure into a filter value. Source evaluation, source iterator acquisition, snapshot pinning and cleanup occur at the same boundaries as baseline execution. Empty input still evaluates the source once but does not evaluate a row predicate or projection. Captures lifted from a comprehension are limited to inert reads whose snapshot at entry is equivalent to their per-row read; live/shared reads, getters, state changes and resource-sensitive copies decline.

Reference DB order is primary-key order; an index produces candidates which may need sorting back into that order. Execute the original residual after candidate selection and before paging. If reordering source acquisition/decoding/failure would be observable under the source's specified contract, decline. A side-effecting ordinary iterator cannot acquire the privilege to skip `next` effects merely by adding a hook.

The DB dependency needs one correction: the literal core `[loop a in db.accounts if a.balance <? 0 a]` does not specify how a fallible source reports storage errors. Adopt the already accepted header form in actual database programs:

```dewy
report = <S>(db:S) => {
    let rows = [loop a in db.accounts or_throw if a.balance <? 0 a]
    loop a in rows { printl(a.id) }
}
```

The exact unadorned core is eligible on an infallible source. If the database design demands that exact spelling on a fallible source, a separate fallible-iterator/collector rule must settle its result; this proposal does not silently introduce one. The hook is not permitted to erase errors, insert unasked propagation or make `[]` a lazy query. Generalizing channel-style `or_throw` to the database's iterator is a documented protocol dependency, not evidence of compiler acceptance today.

For nonlocal `return`, `break`, `continue`, multi-yields, nested/combined sources and effectful bodies, keep the original comprehension and warn about missed planning where useful. This is an optimization eligibility limit, not a smaller source language. No lifting of those exits into a closure occurs.

## 5. Cost is bounded in deterministic units

`prepare` and the collection hook use one compiler-owned planning transaction per request. Proposed pilot defaults: 65,536 exposed nodes+edges, 1,000,000 evaluator steps, 16 MiB evaluator allocations, depth 256, at most 32 callable alternatives. These are provisional budgets to measure, not performance measurements. Exceeding a limit yields a typed BudgetExceeded outcome with counts and origin; it does not kill the compiler or use a wall-clock threshold.

Every nested planning call is charged to its parent's remaining budget. A library cannot reset or enlarge it. A compilation has a further 10,000,000-step optional-planning pool; sites receive work in stable source/dependency order. Repeated identical requests share a result and its charged work, so 10,000 runtime thresholds do not mean 10,000 compilations. No persistent cache is required. Memo keys include body identity, concrete type arguments, descriptor version, semantic settings, target capability profile, planner version and visibility domain; never runtime values. Source locations are kept separately for each requesting site's diagnostic.

Optional query/kernel optimization chooses original execution after budget exhaustion, with one diagnostic per site and reason. A semantic operation with no correct fallback, such as differentiating unsupported code, emits a compile error. Planner programming errors (invalid indexing, invalid returned plan, forbidden effects) are errors naming both library and call site, not silently treated as “unknown code.” Mandatory type-checking and unrelated const evaluation retain their existing policy; this is not a universal comptime quota change.

A warning threshold at half the budget gives early evidence of costly planning. Large output artifacts/code are separately charged to allocated bytes; a byte emitter cannot evade the step budget by one giant allocation. The initial graph path is O(N+E); a planner traverses with visited-node tables and no nested full scans. The finite plan validator is linear in plan nodes plus referenced graph edges. Demand-driven bodies and an interned graph avoid walking the complete program.

Before implementation lands: measure instruction-count overhead on the uninspected flagship panel (target no statistically meaningful added graph work), then inspected micro-workloads with 1/10/100 distinct functions and 10,000 runtime thresholds. Confirm structural linearity, stable budget fallback and code-size limits; follow the existing full/bootstrap/fixed-point gates for a batch. No wall-clock benchmarks on this desktop and no fabricated throughput claims.

## First-pass dogfood corrections

- Ordinary closures with captured thresholds need explicit staging and slots: sections 1–2 fix the missing bridge from compile-time plan to runtime binding.
- A callable returned from a credential factory must remain opaque: section 2 prevents private environment extraction and source-text leakage.
- `pure` is not `total`: section 3 prohibits skipping a diverging callback.
- Eager DB comprehensions need failure edges: section 4 retains `or_throw` and records the exact-spelling dependency.
- “Run the planner with a budget” was not implementable from today's unlimited evaluator: section 5 makes the new evaluator service and accounting explicit.

The next pass reviews all programs against these concrete rules, especially observable fallback, AD domains and the difference between mathematical derivatives and float-program derivatives.
