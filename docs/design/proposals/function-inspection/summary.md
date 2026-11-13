# Callable inspection design: handoff

**Recommendation:** prototype an intrinsic-backed `code.Function<F>` that carries a read-only typed body description at compile time and the original executable closure at runtime. Use one new assigned dunder hook, `$__collect__`, for eligible eager comprehensions. Keep translators, query plans, AD graphs, assertion evaluators and backend emitters in ordinary Dewy libraries. Do not present the compiler primitive itself as reproducible from today's opaque callable ABI.

Read [round3.md](round3.md) first for the final corrections, then [round2.md](round2.md) for staging/privacy/equivalence/budgets and [round1.md](round1.md) for minimal contextual examples, prior art and alternatives. Later rounds supersede earlier rules explicitly; round 2's generic header `or_throw` example is withdrawn.

## Deliverables

- [round1.md](round1.md): database, GPU, assertion and autodiff examples in enclosing functions; initial rules; twelve prior-art comparisons with primary sources; explicit field-descriptor/symbolic alternatives; compiler-versus-library inventory.
- [round2.md](round2.md): static body/runtime capture staging, disclosure, target equivalence boundary, collection protocol, deterministic planner budgets.
- [round3.md](round3.md): corrected fallible collection, finite descriptor schema, consumer-specific fallback, real-interpretation AD semantics, totality and planner-outcome obligations.
- [programs/](programs/): 20 scenarios plus shared database fixture. Covers successful indexed lambdas, explicit eager collection, residual paging, optional and huge integers, effects, wrapping GPU words, strict-float CPU fallback, assertion detail/short circuit/single execution, scalar AD/domain failures, private closures, helper forwarding, and expected rejection cases.
- [dogfood.md](dogfood.md): all 20 graded on obvious/discoverable/concise/safe/complete against C#, Scala, Julia, Zig, Rust and Python workflows. Every deduction and positive score has source-line evidence. **Floor 2; no all-5 or gold-standard claim.**
- [names.txt](names.txt): candidate usage lines for later cold reads; no name is represented as approved or cold-tested.

## Settled in this proposal

An expected Function<F> parameter asks for inspection **after** ordinary lambda type checking. It does not substitute a symbolic Account for the real type. Capture values remain runtime snapshot bindings, and never enter specialization keys. Opaque ordinary functions remain executable; preserving an explicit Function<F> through a helper preserves inspection provenance.

Immutable node identities, lexical disclosure, sealed captures, secret-safe diagnostics and no syntax splicing prevent access to unrelated caller state or mutation of its AST. A literal callback intentionally discloses its referenced accessible ordinary values to the inspecting API; that is part of the parameter's visible contract. An erased function from a factory does not expose its environment.

A pure compile-time planner builds ordinary domain data; the original callback is the fallback. Query/kernel optimization can decline; an assertion can lose operand detail while calling once; AD must reject an unavailable derivative instead of pretending the original function or a numerical approximation is its derivative. Purity alone does not justify dropping a possibly diverging callback.

Comprehensions are typed against their ordinary iterator first. The hook can see their filter/projection and produce a source-specific plan without changing eager execution, type inference, source order, snapshot boundaries or exit targets. Effectful bodies and unhandled control forms keep the original loop.

## Material limits for the coordinator

1. **The exact fallible database one-liner is not settled by inspection.** Under the proposed ordinary iterator, a row can be a storage error. Current generic loop-header or_throw does not forward arbitrary per-item errors. The valid specimen handles `item or_throw` in the body, and the hook preserves that edge. A general fallible-iteration design would be needed to promise the literal unadorned form. [round3.md:7–23](round3.md)
2. **Read-only typed data cannot prove arbitrary target equivalence.** The contract uses validated closed plan algebra and correct backend primitives, just as ordinary libraries rely on correct implementations. It does not protect against a buggy translator that returns wrong results. Current `$proof` is not a universal SQL/GPU equivalence checker. [round2.md:59–69](round2.md)
3. **Strict GPU equivalence is narrower than today's GPU path.** Wrapping words are the first pilot; incompatible float semantics choose the ordinary CPU callback. No device was tested. [round3.md:53–59](round3.md)
4. **AD coverage is intentionally limited.** Scalar mathematical forward differentiation is defined; arbitrary piecewise functions, reverse mode, arrays and opaque functions are not delivered. This is not the derivative of all IEEE bit-level behavior. [round3.md:61–71](round3.md)
5. **Substantial compiler work remains.** Provenance, phase separation, typed capture binding, totality summaries, bounded optional evaluation, stable descriptor format, collection lowering and diagnostics require implementation. The library-author heterogeneous planning outcome API still needs a concrete prototype. [round3.md:73–97](round3.md)
6. **No naming/usability evidence was fabricated.** This sub-agent launched no other agents. The required separate cold-read process remains a coordinator task before advancing new names as tested decisions.

The smaller alternative remains viable: typed field descriptors own both predicate evaluation and planning without arbitrary code inspection. They cover common indexed filters but cannot honestly claim the ordinary Account lambda/comprehension spelling. The next bounded experiment should compare both paths on one captured comparison and an opaque fallback, with exact integer/optional/order/privacy/error tests and compiler instruction counts. No whole-program reification project is justified by this paper alone.

## Validation and scope

Read the requested language/design decisions and discussion notes, the database round/review, and primary prior-art documentation. Reviewed all specimens and checked their simple numeric oracles independently. A structural audit checks file/line links and per-program score coverage; this is documentation validation, not semantic execution.

No compiler suite, backend, GPU, benchmark, cold-reader study or independent reviewer ran. Proposed modules do not exist, so running today's compiler would only test missing imports. Repository paths were read only. All authored files are under `~/dev/tmp/par10/inspect/`; no commits, pushes or worktrees were created. The work stayed within the three-hour brief.
