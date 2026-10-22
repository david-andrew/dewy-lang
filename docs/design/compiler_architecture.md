# Lean compiler architecture (Track B1)

Round 3, 2026-10-22, revises `b8690d021` against both Sol audits, B0 and
`97f57afad`'s evidence. Scope/ownership: this document only. Acceptance: preserve
round-2 correctness and specify a converging, falsifiable migration. Budget:
60 minutes; no implementation, surface changes, persistent cache or rewrite.
B2 approval still requires replacement-cost evidence, not this arithmetic alone.

## Contract and accounting

[GOALS](../GOALS.md) and [decisions](decisions.md) require fresh, single-threaded,
default builds at **200–250k lines/s on every tier-4 flagship**, dunes and 101
included. Count user lines, reached library lines after lazy pruning, and generic
instance work attributed to its originating source. Report library fan-out
(reached library lines and instantiated bodies/program) and **hello ≤20 ms**.
No subtraction of hello, per-machine library index, precomputed summaries/images,
or explicit game-prelude import. The prelude stays implicit.
[compile_throughput](compile_throughput.md)'s image/parallel-primary framing is
superseded; executable emission below is ordinary output writing.

Use one source-provenance ledger for lines L and nodes N: user validation roots,
reached library declarations/bodies, and each distinct semantic instance's source
spans, attributed to the requesting call. Count each such span/node once per
instance; never count retries, cloned syntax or generated helpers as extra source.
Representation sharing does not invent additional instances. Index-only bytes do
not become reached library lines. Their entire cost still counts in instructions I.
Report raw scan bytes, parsed nodes P, lowered/optimized/emitted IR operations,
and semantic versus representation-instance counts separately.

| Phase | Working ceiling, instructions/N |
|---|---:|
| Fresh index, lexing, parsing, projection | 150 |
| Resolve/check, including instances | 350 |
| Facts, effects, ownership | 200 |
| Lowering and helper expansion | 250 |
| Default optimizer | 140 |
| Analyze, allocate, machine-code generation | 300 |
| Scheduling, interning, adapters, executable output | 60 |
| **Total** | **1,450** |

The envelope is **~1.2–1.5k instructions per all-processed source node**, not
per root node. Frontend aims at ~150/parsed node including amortized indexing;
P/N and index bytes/N must fit its allocation. Lowering and codegen each target
**100–150 instructions per reference IR operation**: initial semantic IR before
helper expansion for lowering, input IR for optimization/codegen. Charge internal
expansion and rescans to those fixed denominators. Optimizer targets at most ~150/op **and ≤10% of
actual total I**, including every pass. Both constraints apply: with IR/N=2,
140/N requires ≤70/op, not 150. That stricter case needs a measured pilot.
Lower/codegen must likewise satisfy cost/op × their respective IR/N ceilings;
150/op alone fits 250/N only when lowering IR/N ≤1.67. Phase savings toward
1,200/N must reduce optimizer cost proportionately to retain its 10% limit.

At a reference 6.3G instructions/s, require I/L ≤31,500 (200k), aiming at
25,200 (250k). At 1,450/N, N/L must be ≤21.7/17.4 respectively. Measure density
per entry; B0's ~10 root nodes/line is not a universal density. High expansion
cannot enlarge the denominator to pass. This is a flagship envelope, not a
universal bound on arbitrary comptime, exact sets or rational arithmetic.

## Residuals and the early gate

B0/evidence measure **50,160 instructions/root node**, including check 15,530,
analysis 8,971, lower 6,510, optimizer 6,712 and codegen 7,165; load is 5,272.
Those are historical root-normalized costs, not measurements under the new metric.
The ~5k of the earlier compact compiler is a comparison, not evidence for Dewy's replacement costs.

Let m=N/root-nodes on a fixed, matched closure. The table retains untouched
historical costs explicitly; m=2.5 illustrates arithmetic, not a newly measured
flagship. Do not average m across entries. Rebase after the diet and queued
landings; never claim their savings twice. Diet receives **zero assumed credit**.

| After cut, in execution order | Predicted instructions/N | Illustration, m=2.5 |
|---|---:|---:|
| 0: matched baseline | 50,160/m | 20,064 |
| A: closure diet | remeasure I/N; no assumed reduction | — |
| C: check | 34,630/m + 350 | 14,202 |
| 6 + G: lower and codegen | 20,955/m + 900 | 9,282 |
| 8: optimizer | 14,243/m + 1,040 | 6,737 |
| 2: call footprints and facts | 9,272/m + 1,040 | 4,749 |
| 4 + 9: index and frontend | 4,000/m + 1,190 | 2,790 |
| 3: remaining analyses | 1,390 | 1,390 |
| 5 + 7: closure integration, reserve | **1,450** | **1,450** |

Interim rows exclude the final 60/N integration reserve; adapters must fit it.
These are conditional residuals, not measured speedups. Unlike round 2's ~27k
plateau, no expensive phase survives unchanged. The fixed-cohort algebra is
independent of closure savings; after removing bodies, recompute both numerator
and denominator. Diet improves fan-out/latency, not automatically I/N.

**Step 0 (one day):** use exclusive counters on hello, dunes, 95–100 `design.dewy`
and 101 `core.dewy`; keep tensor `design.dewy` as a separate held capability.
Freeze source-line counting, instance provenance, diagnostics and phase ownership.
Measure P/N, each IR/N, bytes/N, candidate trials/call, instance hits/misses,
event/set cardinality, substitution, retained bytes and global-component size.
Record all adapters, fallbacks and inline queries exactly once. Existing
`require-static` failures remain visible; passing today's default is not evidence
for the decided no-traps workload.

Pilot every phase floor before authorizing its full replacement. For each entry,
replace every historical coefficient and m with that entry's counters, then apply
measured replacement unit costs and the I/L formula. Re-rank cuts on the refreshed
profile; ceilings never authorize regressions where current costs are lower.
A ≥3% saving alone does not establish convergence. Scan hello's
runtime closure first. The old 4.9 instructions/byte C index (13.3 in Jo) costs
7.7–21M/build: it is **not** the near-free solution. The old root-only allowance
failures motivate the diet, but are not failures against the newly decided metric.

## Records, discovery and ownership

Step 1 adapters arrive only with consumers. Retain indexed `Node[]`, list arenas
and `Ins[]`; use checked IDs, spans, interned names/types/rows, indexed scope heads
and undo stacks. Share immutable generic syntax with typed overlays. Compilation
owns source buffers, `DeclIndex`, descriptors and `SummaryStore`. Each
`FunctionUnit(InstanceKey, revision)` owns events, recipes, dependency generations
and diagnostics. Cells are `Pending`, `Solving`, `Settled`, `Error`; absence never
means purity. Reverse edges invalidate consumers. Suspensions retain records,
not checker stacks. Plans own representation, copies, cleanup and helper inventory;
fragments own bytes/relocations. Scratch pointers never escape; publication permits
arena reclamation. Future workers use coordinator-owned identities.

Index imported sources and implicit-prelude scopes in legacy order. Complete
visible overload families, imports and nominal ancestry/descendants before selection
or `prepare_nominals`-equivalent queries. Comptime discovery is a charged job.
Initialization, exports, reflection and library-validation projects supply roots.
Keep all existing user validation roots, including uncalled nongeneric functions,
without inventing generic instances.

Replace method-triggered `dc_force_all()` only after demanded receiver-mutability
and receiver-read/static facets cover bodies/defaults. Initially reuse
`dewy_changes/dewy_reads`: scope-aware member reads/writes, place uses, nested-capture
violations and candidate edges. Resolve inherited members and visible receiver-name
overloads under today's conservative rules. Solve mutability's Boolean least fixed
point, then read/static; hooks count as reads. Uncalled candidates may demand
signature-only bodies. Retain their events before freeing ASTs; a compact scanner
must reproduce facets before replacing parsing.

## Closure certificate and replacement

Keep legacy checking order and the **whole-program closure barrier** initially.
Tentative unit plans publish only when all five conditions hold:

1. Imports, overloads, nominals and validation jobs are drained. Every checked
   initializer/body, including unreachable user declarations, registers global/
   capture writes, aliases, callbacks and instances. Each binding has a complete
   writer set; call reachability cannot establish uniqueness or literal domains.
2. Dependency SCCs include instances, global/capture, receiver, return, inferred-error,
   representation and helper cells; external dependencies are settled. Preserve
   recursive inference/errors. Exact unions grow by indexed deltas; existing
   region/projection caps reach top, never an invented proof.
3. Settle writes/types, later literal writes and exact-decimal contexts. Error
   cells retain annotated order, otherwise `main_kind_order` declaration order.
   Perform `infer_finish` return-coercion replacement before freezing exit codes
   or main's wrapper.
4. Establish exact uniqueness over all relevant checked bodies; settle write
   footprints, probe bounds, then recompute cost rows. Preserve actual/formal
   substitution, callbacks, positive contracts, forbid-only inferred rows and
   witnesses. Proof/cost cycles cannot discharge their own assumptions; unsupported
   pending/cyclic evidence remains unproved.
5. Plan ownership, failed-construction cleanup, bigint promotion, coercions and
   hooks for emission and existing lower-only validation roots. Discover helpers/
   initializers before emission. New requests reopen discovery and invalidate
   certificates. Publish only with empty queues, matching generations and a complete
   planning sweep adding no writers, instances, helpers or obligations.

Sealed revisions reject new requests as scheduling errors. Earlier component
publication requires proof that remaining jobs cannot add writers/instances.
Suspension does not skip later statements/defaults: collect recipes and pending
write-target edges through every required subtree. Unresolved targets prevent
sealing; new edges recompute affected SCCs.

Recipes are transactions keyed by source operation/input generations. Replace
obsolete overloads, coercions, helpers, diagnostics and effects; detach reverse
edges and reference-counted helper requests, rebuilding affected aggregates.
Delay overload commitment until inputs close. Within an epoch, only strict
monotone changes enqueue work. Finite discovery and existing caps terminate ordinary
components. Repeated recipe/input states trigger one legacy serial restart before
lowering, with scheduler re-entry disabled. Charge and retain this fallback until
differential coverage permits removal. Preserve comptime/instantiation resource
limits; do not repeatedly lower the whole program.

## Analysis, diagnostics and editor identity

Partial operations create obligations; immediate constant/range answers precede
demanded relational events. Index `PlaceId→ValueId`, bounds and incident rows;
avoid all-pairs joins. Separate content/length/storage/sharing epochs. Preserve
captured actuals, alias invalidation, post-cleanup results, widening and final loop
validation. Unknown rejects unless existing runtime-check/prototype policy permits
checks. Strict-cost acceptance and finite literal precision remain unchanged.

For active events A, edges E and queries Q, target O(K(A+E+Q)) work/state.
Measure K: lattice height, row/set cardinality, projection, substitution and loop/
query work. Charge bit-size-sensitive rational arithmetic. Ownership tables activate
only for participating values, preserving COW snapshots, explicit copies, moves,
hooks and partition disjointness. Expand bigint semantic IR once before allocation,
retaining ABI/promotion costs; cache union remaps without changing logical types.

Diagnostic compatibility means existing single-worker eager/replay traversal, not
declaration sorting. Retain replay until ordered diagnostics, warnings, first-error
suppression, recovery, generic call trails and fix-its match. Preserve allocation-
before-opaque witness ranking. Identity includes span, canonical instance/expansion,
kind/arguments, witness and call trail; revision is publication metadata. Assign
request ordinals in legacy phase/module/nested order; hold later diagnostics until
earlier requests finish or suppress them. Retain replay where this trace is unavailable.
No wholesale golden regeneration; explain individual compatibility corrections.

LSP fast checks stay provisional. Completed revisions run CLI proofs/plan verification
without emission, matching types/errors/fix-its. Completion indexes visible declarations;
hover/references demand bodies, and project references include dormant bodies.
Edits invalidate reverse dependencies and reject stale responses. Integrate decimal
restart removal with dedicated correction goldens: old IDE/REPL/watch/errors-only
exclusions are not the parity oracle.

## Migration cuts and falsification

Retain historical labels; execution follows the residual table. Implementation
order follows removable instructions: checking (~15.5k/root), paired backend
(~13.7k), optimizer (~6.7k), call/fact work (~5k), frontend, remaining analyses.
The diet and all floor pilots run early because they determine the workload.
Each pilot is bounded to two days, after measuring its upper bound; no unbounded
rewrite follows a failed assumption. Owned files below describe future cuts.

**A — Closure diet.** Own reached runtime/library modules, generic-instance planning
and game discovery. Split formatting/bigint and crash/backtrace dependencies from
plain text output, retaining demanded errors and initialization effects. Evidence
attributes 60%/20% of hello's lowered library IR to these pieces; first replay the
reachability graph to test the proposed ~5× reduction in demanded runtime work.
Share machine bodies by representation only when ABI, operations, constants, hooks,
effects and cleanup agree; retain distinct semantic checks, logical types and
diagnostics. Hash equivalent closed plans to measure the actual sharing ceiling.
Scan game declarations within imported scopes and implicit-prelude demand, preserving
all visible names/collisions; never require an explicit import. Report reached lines,
semantic/representation instances, lowered bodies and hello latency before/after.

**C — Check unit cost (new).** Own `expr.jo`, `check.jo`, signature/instance tables.
KV's `resolve_fn_call`/`get_fn_inst` cost 63M; removing that alone cannot establish
350/N. Index complete overload families by name, arity, parameter names and safe
type discriminants; preserve ranking, contextual arguments and diagnostic fallbacks.
Concrete instance keys are already hashed: do not credit that existing fast path.
Canonicalize remaining inferred keys with dependency generations, cache signature/
default metadata and use typed overlays instead of cloning/rechecking syntax.
Measure `fn_sig`/`ensure_ret`, coercion and overlay costs separately. Target
O(nodes + candidate trials + new-instance work), with expected constant-time indexed lookup. First
count hits, trials, copies and uncached semantic visits; replay representative calls
including rejected candidates. Bracket the remaining checker too: 350/N requires
cheap ordinary visits and bounded demand, not just faster lookup.

**6 + G — Lower/codegen unit cost (G new).** Own `lower.jo`, `x64.jo` and plan/IR
records. Extract plans with identical IR, then lower once into indexed operands,
use lists, block summaries and helper inventories. Replace repeated `analyze`/
`allocate`/`x64_function` scans and temporary lists with shared use/liveness data,
bounded register-class state and direct encoding. Target linear scans plus measured
liveness propagation/spill work; count block revisits and pressure, never assume
allocation is constant-cost. Pilot complete low/high-pressure functions including
collection, bigint expansion, spills and relocation: current ~1,260 lower and
~1,390 codegen instructions/op must approach 100–150, within 250/300 per N.
Review code-shape differences and runtime before replacing extraction adapters.

**8 — Optimizer unit cost.** Own `opt.jo` and its use/CFG indexes. Keep forward
sweep, leaf inline, SRA and short vectorization in default builds: evidence shows
every pass earns its slot; wholesale deletion saves <10% and damages runtime.
Build indexes once; trigger expensive passes only on eligible operations, update
def-use incrementally and bound revisits. Include discovery, inlining growth and
all passes in the ~150/op and ≤10% limits. Cheap replay measures mandatory sweep
cost plus candidate densities; high IR/N must satisfy the stricter quotient above.
No pass-removal assumption finances this row. Require semantic goldens and ≤3%
runtime regression on named default/release kernels, including 101.

**2 — `fact_call_effects` → effect footprints.** Own `facts.jo:587`'s call kill
and `effects.jo`'s footprint export only. Build on Opus's `wt/effectsfast`
effects-bitset summaries and Astra's queued `e27a24739` demand-driven facts;
reprofile their combined landing
before claiming incremental savings. Export one generation-tagged, settled footprint
per instance: interned place bases, content/length/storage/sharing epochs and opaque
state (including conservative escape handling). Substitute actuals/callbacks;
facts kill indexed per-base chains without
`effects_demand`/`effect_visit` re-walks. Pending remains conservative. Construction
is proportional to summary entries; application visits substituted writes/affected
chains. The historical KV 94M call-kill and RTOS 43M locate the opportunity;
KV facts+effects 181→~95M is a pre-landing hypothesis, not additive savings.
Replay collection, invalidation and adapters; require unchanged proofs, witnesses,
bytes and ordered diagnostics. The residual row's analysis 8,971→4,000/root also
requires measured join savings from the queued facts work.

**4 + 9 — Fresh index/frontend.** Own lazy discovery, lexer/parser and projection.
Use memchr-class delimiter searches with small string/comment/nesting state;
record declaration/name/body spans, then tokenize/parse only demanded headers/bodies.
No token stream for unreached code. Preserve discovery/facets above. Target
O(scanned bytes + delimiter candidates + demanded syntax), with bulk skipping.
First measure bulk-search cost and delimiter density on the actual library; the
scan ceiling is (150N minus demanded frontend instructions)/scanned bytes.
Benchmark actual source bytes and demanded parsing together; require index cost to fit the
150/N frontend remainder after parsing (~150/P). The existing 4.9/byte scanner
fails this premise. Direct compact AST construction removes projection; postpone
it only if measured retained projection fits. Import-scoped game discovery shares
A's index, avoiding a second digest. Oracle: grammar, positions, signatures, roots,
initialization, diagnostics and bytes.

**3 — Remaining summaries/ownership.** Own effects, ownership and demand stores.
Intern rows, propagate changed entries once per dependent edge and activate ownership
only for relevant values. Preserve write→bounds→cost order. Replay actual K and
retention, including callbacks and exact sets; all analysis must reach 200/N.
**5 — Inference** owns checker/string-domain/error/decimal cells and integrates the
decimal correction; no savings assumed. **7 — Scheduling** owns driver/unit queues
and drives closed units
through check/proofs/plans/lower/opt/emit; retain the global barrier. No worker
speedup pays the single-thread budget. Combined adapters/scheduling/output fit 60/N;
measure queue operations, retained SCC state and replay frequency before integration.
Use expected O(1) enqueue/intern operations and charge dependency invalidations.

Adversarial later writers, recursive callbacks/errors, helper cleanup and mutable/
static/inherited methods precede migration. Byte/ordered-diagnostic equivalence is
the default oracle; reviewed optimizer/representation and decimal corrections get
targeted tests. Compiler commits run focused/quick gates; batches run full,
independent bootstrap and fixed point. Check supported backends, CLI/LSP,
default/release and 1/2/4-worker determinism; no per-entry instruction regression
beyond noise. Final acceptance includes quiet pinned/CI throughput and hello latency.
Failed optional pilots end their idea family; decided capabilities require diagnosed
redesign, not weaker semantics. B3 uses Dewy import-cycle leaves with seed-compatible
Jo twins and exact/transitive `FROZEN_TWINS`, per [self_hosting](self_hosting.md).

## Audit response

Round 2 accepted closure, transactional replacement, lazy signature facets,
diagnostic replay and completed-revision editor parity; all remain requirements.
Its unresolved budget objection is addressed with a consistent processed-source
denominator, explicit check/codegen cuts, charged optimizer work and an early
per-entry falsification gate. Evidence amendments add the closure diet and name
step 2 relative to concurrent work. Pass deletion, root-only ceilings and persistent
index/explicit-game-import remedies are superseded. Conditional convergence now
reaches 1,450/N; budget plausibility remains contingent on measured unit costs,
densities and the fresh scanner, not asserted by the residual table.
