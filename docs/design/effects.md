# Milestone 23: effect rows

Accepted design, 2026-10-20. Slices 1, 2 and 4 are implemented.

## Authority and starting point

`docs/GOALS.md` governs ordinary versus strict behavior: ordinary code retains safe runtime checks and COW; strict code rejects unproved prohibited costs. The broader no-traps claims in `safety_and_concurrency.md` do not supersede that distinction. `semantic_contracts.md` requires representation choices to preserve mathematical semantics. `user_managed_storage.md` requires observable lifecycle effects and cleanup on every exit.

**Observed by source inspection:** `isolation.jo` already supplies demanded per-instance Tarjan solving after checking/helper discovery. It proves only ambient isolation, permits private allocation, and excludes captures/opaque calls. `lower.jo` separately traverses calls for `fn_writes`, resizing, races and determinism. `copies.jo` is dormant without `$explicit_copies`; its source copy policy is independent of backend placement. `FnSig` lacks contracts; `fn_.st` already stores labels, and `callable_fits` lacks contract compatibility. These are current observations, not benchmark results.

The archived reference supplies specified semantics, not evidence of implementation. Tier-3 10/11 previously failed unsupported effect syntax; 12 failed before its required semantic rejection. Preserve their distinction between executable core projections and acceptance. Programs 29/30 motivate precise service/database mutations, snapshot costs, formatting and sort callbacks; effects do not complete their refinement/API requirements.

## 1. Vocabulary and contract meaning

Start with this internal inventory:

- `Read(region)` and `Write(region)` map to `reads<p>` and `mutates<p>`. Regions distinguish formal places, globals, shared captures and nominal resource identities such as `Filesystem`. Private value parameters/local mutation export no external place effect; handle-payload effects still name their resource. Proven immutable startup constants need no external read.
- `Alloc` maps to bare `allocates`, never `allocates<Resource>`. Count logical storage work remaining after established move, borrow or static/frame placement. COW postponement alone cannot discharge it.
- `Detach`, `CostlyCopy`, `Panic/Terminate`, `IO(resource)`, `Block`, `Spawn` and `Escape(source,destination)` are internal categories immediately. Do not invent surface spellings. Read/write authority on nominal resources remains distinct from internal I/O/blocking flags. Unmodelled operations are `Opaque`, conservatively top across categories and reachable regions.

Track `Replace`, `Resize`, `StorageChange`, `Share/Expose` as write/ownership facets for invalidation. `reserve` can change storage without length; element writes need not resize. Escape describes flow into results, ambient storage or retained callbacks, not automatically an illegal operation; legal handles may escape, borrowed places may not. `Send`/`Sync` remain type properties. Error return alternatives and `noreturn` remain outside may-effects.

A positive row is a closed upper bound; execution need not perform every permitted effect. `no_effects` is the closed empty row across modeled categories, including reserved internal ones; it cannot hide panic or blocking merely because their individual spellings remain open. Negative-only rows remain open with exclusions: `no reads<Filesystem>` proves that absence, not purity. Unspecified behavior is inferred, never assumed absent. Exclusions subtract overlapping regions; excluding `box.field` still permits disjoint sibling mutation but rejects whole-box replacement. Contradictory permissions/exclusions are diagnosed. All declared bounds use both semantic effects and residual implementation costs; allocation promises cannot be certified at source-call scanning alone. A certified empty row needs the cost inventory below. Do not advertise syntax acceptance alone as the still-open full strict profile; that profile also selects proof and source-copy policies.

Represent the strict lane only as an internal `EffectPolicy` prohibition mask plus `RequireStatic` obligations, passed from checking configuration into planning; tests set it internally. David owns opt-in syntax, panic/detach names, allocation-failure policy and task authority. Until failure policy settles, allocation permission never certifies failure-free execution; unknown failure paths cannot pass strict verification. No whole-machine stack/resource-exhaustion guarantee is claimed.

## 2. Representation and callable identity

Extend `FnSig` by `ContractId` (zero means no declaration). Intern immutable contracts containing refinement pre/postconditions, effect bounds/exclusions and row binders. `FnSummary` is separate, per concrete instance: inferred effects, guarded implementation costs, callback applications, witnesses and generation. Never overwrite declarations with inference.

An `EffectRowId` interns sorted/deduplicated atoms, exclusions and rigid row variables. Normalize binders by owner/depth/ordinal, preserving nominal resource identity and nested scope. Kind-check `Effect` arguments separately from value types; substitute through imported aliases and mixed type/row binders. Inference cells remain transient and noncanonical until zonking; explicit rigid row variables may occur in canonical generic contracts. Source spans and runtime versions never affect interning.

Use one contract-bearing callable wrapper (`elem=base callable TypeId`, `st=ContractId`) shared with milestone 22's callable-contract plan; preserve the underlying callable's label field. Scalar refinement wrappers remain separate. Representation/layout unwraps this qualifier; compatibility must inspect it. Hash/equality include the contract; substitution, zonking, nested containers, returns, captures and partial application preserve it. Unresolved row cells mark types inference-bearing. Do not mutate an interned callable when summaries settle: queue compatibility obligations, then publish its canonical qualified type.

Keep ordinary shape-only callables unchanged and unconstrained indirect behavior top. Demand inferred rows when a handle reaches a constrained use, preserving assignment/branch sources until that obligation resolves; unsupported flows stay top. Thus omitted source rows are inferred without eagerly allocating rows for every ordinary function/type. Reassignment joins possible rows, never retains only the initializer's guarantee. Keep delayed obligations keyed by instance/use; demand a bounded backward source-flow walk only for constrained handles. A lost source or exhausted flow budget yields top, not a guessed empty row.

Conversion requires source effects within destination bounds, including exclusions; destination preconditions must imply source requirements, and source postconditions must imply destination guarantees. Check callback parameters contravariantly and results covariantly, recursively; retain today's ordinary value-shape restrictions. Unknown compatibility rejects. A weaker callable may forget guarantees, but recovering them requires another checked conversion. Partial application substitutes bound arguments and captures; creation costs are distinct from invocation effects.

## 3. Collection, substitution and solving

Reuse isolation's demanded graph, kind-aware child switch and generation boundary. During migration collect its conservative blocker bit alongside new events, avoiding two scans. Extend collection once with operation events and `CallEdge(callee, substitution, origin, callback-binding)`; nested closure bodies belong to their own instances. The existing isolation scanner stops at its first blocker: full collection must continue, recording all direct sources once. Unknown node/intrinsic kinds fail closed. Preserve `.for_.c/d` local IDs and `.partial.d` instance interpretation.

Share milestone 22's alias-normalized `PlaceId`: declaration root plus field/constant index/stable selector/unknown projection. Summary roots are owner-qualified formal ordinals, global declarations, capture slots or nominal resources. No compiler local number crosses a call edge untranslated. Runtime `ValueId`, length/storage/sharing epochs stay in facts, not rows.

Evaluate actuals in specified order, including `call_eval_order`, receivers, selectors and defaults; freeze by-value snapshots and normalize place actuals. On **every** edge, including SCC backedges, compose the callee region with the actual route: `p.field` called on `@pair.left` becomes `pair.left.field`. Swapping arguments uses slot mapping, never names. Evaluate selectors/defaults for their own effects; taking a dictionary entry place includes lookup/hash reads. Unsupported provenance becomes `AnyReachable`, not an invented root.

Solve monotone may-unions over demanded SCCs, with edge substitution before union. Recursive bodies do not become pure merely because checking is in progress. Bound each region set to 32 entries, projection depth to eight and symbolic callback applications to 16; widen excess to the corresponding reachable/global/resource top. Keep resource exclusions as explicit constraints; widening that overlaps them fails verification. These are judged initial caps, subject to profiling. Publish only settled components and checked declaration obligations.

For callbacks retain symbolic `Apply(callback-slot, actual-place-map)` terms until instantiation. `<E:Effect>` carries the **nonlocal remainder**: callback formal-place permissions stay explicit and remap at each invocation. In 11, `mutates<x>` becomes `mutates<y>`; it cannot leak into `E` with a foreign ordinal. Callback-local exclusions remain checked at that boundary. Unconstrained indirect/foreign/unknown calls are top; a verified callable contract supplies an upper bound without discovering its runtime target. Checked extern bodies are impossible: only narrowly reviewed intrinsic/FFI contracts can supply trust, selected by resolved declaration identity, never pathnames or ordinary unchecked annotations.

Collect implicit format, equality/hash, lifecycle, defaults, conversions, closure construction/copy and defer/cleanup edges. `value_helper_calls` and formatter `.pair` are starting seams, not complete coverage. Defaults count only where evaluated; creation and invocation of closures differ. Potential lifecycle hook effects remain checked even if optimization elides an invocation, as required by storage design. Cleanup covers returns, breaks, forwarding and partial construction.

## 4. Facts, costs and consolidation

Semantic reads/writes settle before fact invalidation. Apply substituted write/resize/expose facets before installing verified postconditions. Preserve captured scalar snapshots; invalidate current places by overlap. Equal selector values may alias; parent replacement kills descendants; content, length, storage and sharing invalidate independently. Unknown calls affect every potentially exposed region. This is exactly milestone 22's transfer contract, not a second facts engine.

Costs need a conditional implementation summary: e.g. mutating a buffer may detach unless unique, and pushing may allocate unless sufficient capacity and unique. Conditions name formal entry states, not mutable compiler flags. Caller facts discharge them at the actual invocation point. Retained snapshots invalidate uniqueness. Unknown conditions retain costs. Cap guarded alternatives at eight, widening excess to unconditional cost. Recursive implementation summaries solve conservatively over the same graph; no cyclic purity/uniqueness assumption discharges itself.

Record obligations for allocation, COW detach, costly duplication, closure environments, recursive boxes, bigint/adapters, checks/failure branches and cleanup. Share actual placement decisions with lowering; default/release and native/wasm may select different plans. Hook authority effects cannot disappear solely through cost elision. `$explicit_copies` retains its source policy: explicit copy may satisfy it while still violating strict allocation/copy limits. Reuse its move/view evidence, never treat successful copy-policy checking as no-allocation proof.

After checking/helper discovery, solve semantic summaries and bounded facts, select implementations, close helper/callee cost dependencies, then validate strict roots. Lowering sites must report costs through the same inventory; verify closure after late helper/initializer discovery before emission. An unclassified introduced operation rejects strict compilation. Subsequent transformations must preserve that inventory or register/revalidate additions. `check` runs the same plan verifier without emission; it cannot grant guarantees based on hoped-for optimization.

Make `ambient_length/storage/sharing_stable`, `fn_writes`, resize and race queries adapters over this summary. Preserve the isolation consumers' extra alias/actual exclusions until equivalent facets replace them. Race checking still proves worker disjointness and distinguishes private snapshots from shared captures; a row is insufficient alone. Retain existing diagnostics, replace library-directory exemptions with reviewed primitive contracts as consumers migrate. Keep liveness, cleanup ordering, fact transfer and disjointness analyses; remove duplicate effect collectors/transitive walks, not those distinct jobs. Fine-grained incremental invalidation is deferred: reset compilation generations, including watch/repl, and never publish mutable init bodies prematurely.

## 5. Diagnostics and compile budget

Retain one deterministic witness per category/region: direct source or predecessor edge plus substitution. Render a bounded call chain, collapse recursive cycles and offer expansion, rather than copying paths into every row. Example: “`f` may allocate because it calls `g`, which pushes onto `xs` (line N)”; also point to `no allocates`, the actual argument and unresolved uniqueness/capacity condition. For 12 show `forbidden → mutator → shared += x`. Distinguish observed may-effect, opaque contract, widening and unavailable proof. Always include implicit-hook origins and generic instantiation notes; no unsupported-syntax error earns a negative-test pass.

**Inherited measurements, not remeasured here:** Astra recorded median 1,347,611,586 user instructions for 22,005 root lines plus 36,744 implementation lines, default native compilation, one emission worker, i7-6700; counters were unmultiplexed. Refinement design later recorded one 1,339,685,858-instruction sample with changed sources. Neither is this HEAD's measured baseline. ROADMAP's approximately 1.36 G to 400 M target requires roughly 3.4× work reduction.

**Judgment:** dormant incremental budget 0.5–2 M instructions: about 0.04–0.15% at 1.35 G, 0.13–0.5% at 400 M. Achieving this requires lazy row arenas, zero-contract fast paths, no added whole-tree pass, and replacing existing demanded scans. A dense instance index is acceptable; per-node maps/rows are not. After migration ordinary optimization consumers demand only relevant facets. Active effects with 25k events and 5k substituted edges initially budget 10–25 M instructions; this estimate is not measured and excludes full relational facts. Saturation workloads need separate reporting. Do not book scan-removal savings beforehand.

Implementers establish a fresh matching baseline, then seven alternating single-worker baseline/candidate samples after warmup, default/release, identical source counts and unmultiplexed counters. Gate cumulative dormant growth at 1% against the fixed reference, not 1% per slice; profile toward the 2 M estimate. Measure chain/diamond/SCC graphs and callback-heavy programs separately. No new perf run or compiler tests were performed in this read-only design round.

## 6. Six delivery slices

1. **Direct-place pilot.** Own new `effects.jo`/`places.jo`, isolation adapter, parser/signature/callable hooks and dedicated tests. Support scalar place reads/writes, field projections, direct calls, positive rows and `no_effects`; no row variables, `allocates` spelling or general storage proofs yet. Certify the empty cost inventory only for wrapping fixed-width scalar operations, scalar frame places and their supported direct callees, matching both lowerers; everything else is top. This small inventory makes `quiet` honest without anticipating slice 4. Parse/retain contracts through `FnSig` and callable identity; constrained indirect calls may conservatively reject. Finalize declared checked bodies, including unreachable ones, after helper fixed point in check/build. Existing isolation remains conservative for legacy consumers. Acceptance: full 10 unchanged and semantic rejection of 12, with expected stdout/marked diagnostic. Soundness: swapped formals, sibling versus parent writes, mutual recursion with late global mutation, hidden formatter, unknown extern, aliasing actuals, unreachable bad declaration, misleading library path. Compare default/release behavior. Judged budget: 1–2 weeks, 1–2k compiler lines; stop/review above dormant gate. No claim to complete milestone 23.

2. **Callback contracts and rows.** Own contract interning, substitution, callable conversion and parser alias/binder support; 1–2 weeks judged. Acceptance: full 11, including allocation-free bare handles, read-only parameter borrowing and array iteration; unsupported environment copies remain top. Reject forbidden callbacks hidden through locals, reassignment, records/arrays, returns, nested callbacks, partial applications and imported aliases. Test positive equivalents, resource exclusions, binder shadowing, kind errors and callback-place leakage into `E`.

3. **Shared invalidation and consumers.** Own effects/place facets, isolation/write/resize/race adapters and milestone-22 fact interface; 1–2 weeks judged. Ship precise 29/30 service/database mutation extractions and retained-snapshot regressions; preserve 22's stale-length negatives. Test equal selectors, reserve versus resize, raw exposure, shared captures, dictionary lookup hooks and recursive projection widening. Remove replaced scans only after consumer equivalence; retain race/disjointness guarantees.

4. **Allocation and implicit operations.** Own intrinsic cost registry, lifecycle/default/defer edges and implementation planning hooks; 2–3 weeks judged. Acceptance: 02 rejects transitive dynamic growth for allocation, while read-only inspection passes. Cover formatting/hash/equality allocation, eager defaults, early-return drop/defer, closure capture/copy, recursive boxes and sort key invocation from 30. Exercise hooks on partial construction and target-specific adapters. Unsupported pending lifecycle facilities stay explicit blockers, not invented successful tests.

5. **Strict fixed-buffer kernel.** Own internal policy harness, conditional costs and final inventory verification; 1–2 weeks judged, depending on refinement proofs. Acceptance: 01's kernel under internal strict policy, with fixed frame placement, proven bounds and no remaining allocate/detach/copy/panic operations. Negative variants: retained shared buffer, escaping closure, unknown callback, failed capacity proof, divide/check failure, cleanup cost and late helper insertion. Test default/release and native/wasm where supported; ordinary counterparts retain safe behavior.

6. **Milestone closure and cost gates.** Own dedicated diagnostics/integration tests; 3–5 days judged. Complete 10/11/12 together, strengthen 29/30 callback/snapshot extractions, stabilize witness goldens, and run compile gates. Focused plus quick per compiler commit; full suite, independent bootstrap and fixed point per batch. Milestone 23 requires semantic checks, not merely syntax acceptance; strict public opt-in remains separately OPEN.

Dependency order: refinement slice 1's evaluation/capture interface and this design's slice 1 place identities come first; coordinate that small shared extraction. Then effects slices 2–3 feed refinement slice 4's precise call invalidation. Refinement slices 2–4's boundary/bounds proofs precede effects slice 5; they do not block direct rows. Share callable contracts when either slice first needs them. Neither design requires the architecture's full inference/layout/parallel refactor.

Sources inspected: archived `site/reference/src/refinements-and-effects.md` effects section; the three named design notes and GOALS; scratch `sol-ladder3` programs 01/02/10/11/12/29/30 and their acceptance notes; `sol-refine/DESIGN.md`; `astra-design/DESIGN.md` §2 and measurements; `sol-review/REVIEW.md` §2–5; current `isolation.jo`, `copies.jo`, `types.jo`, `check.jo`, `expr.jo`, `lower.jo` and `main.jo`. No repository artifacts or evidence files were written.

## Decided rules

Moved here from the decisions ledger ([decisions.md](decisions.md)), which keeps
a pointer to each rule. The wording is David's.

### The `panics` effect (2026-10-23)

*Later than this document's "ordinary code retains safe runtime checks" and "do
not invent surface spellings" for `Panic/Terminate` (no traps by default,
2026-10-21; see [no_traps.md](no_traps.md)): `panics` is an inferred effect
visible in rows.*

- `panics` effect: "may fail a runtime check" (and any other possible panic)
  is an inferred effect visible in rows. A no-traps scope cannot call code
  that `panics` unless it opts in with `$runtime_checks`; `& no panics`
  forbids it outright; `$no_hidden_costs` includes `no panics`. A dependency
  built with `$runtime_checks` cannot crash inside a caller that did not opt
  in.
- `$runtime_assert` makes its function `panics` for callers in other modules,
  not within its own module.
