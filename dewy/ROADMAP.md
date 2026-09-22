# Dewy roadmap after the native bootstrap

This is the high-level roadmap for taking the language from "a native
compiler pair exists" to a practical compiler and the language as it was
intended. It records the order in which the remaining pieces should land,
why that order, and the strategy for the pieces where the project has
previously bogged down.

How this relates to the other documents:

- [`status.md`](status.md) is the feature-by-feature implementation tracker
  and the home of the detailed design essays (liquid refinements, ownership
  tiers, nominal/structural construction). This document orders that work.
- [`bootstrap/IMPLEMENTATION.md`](bootstrap/IMPLEMENTATION.md) records the
  verified, published, installable native pair reached on 2026-09-14 and
  the remaining hosted-parity gaps. The C-accelerated fixed point is complete;
  full language parity and practical compile-time performance remain Phase 0
  work. The direct x86-64 route reached a verified fixed point on 2026-09-18;
  that checkpoint is not a certification of subsequent source changes.
- [`semantic/*.md`](semantic/) are the design notes for individual areas.
  Where this document says a design is open, the note is where the options
  live.
- [`../site/reference/src/design-status.md`](../site/reference/src/design-status.md)
  is the user-facing maturity ledger. It should move items from provisional
  to settled as the phases below complete.

Recorded 2026-09-13. The ordering and the phase 1.1 strategy were reviewed
and accepted by David for phases 1.1 through 1.3; later phases are a
preliminary proposal and will be revised as earlier phases land.
The immediate parity and performance sequence below was reviewed and
accepted on 2026-09-14 after the native fixed point completed.

## Organizing principle

Dewy's identity rests on three commitments, and nearly every unfinished
feature either depends on one of them or is blocked by one being half-built:

1. value semantics whose cost is never hidden;
2. compile-time proof instead of runtime checks, with no runtime traps;
3. one language for runtime and compile time (compile-time evaluation, not
   macros).

Work is therefore ordered by "which foundation does this need", not by user
visibility. The pieces users notice most (floats, matrices, closures, GUI
examples) come after the pieces that make them cheap to build once.

One structural cost shapes everything: while the hosted Python compiler and
the bootstrap compiler stay in parity, every feature costs twice. That cost
is accepted on purpose for now; see "The hosted compiler's role" below for
what it buys and when it stops being worth paying.

## The hosted compiler's role

The Python compiler is not only the bootstrap seed. It has independently
implemented parsing, checking, and lowering, in a different language from
the native compiler, which makes it:

- an independent oracle for miscompilation. A self-hosting compiler can
  miscompile itself consistently and still reach a byte-identical fixed
  point; the differential `test_bootstrap_*` comparisons catch what a
  fixed-point check cannot, and matter most while lowering and ownership
  are being rewritten (Phase 1);
- a from-source bootstrap path with no trusted binary seed;
- a convenient development loop for prototyping and inspecting analyses in
  Python before porting them. The 2026-09-15 complete direct-output build
  checkpoints for the larger, cache-enabled compiler were about 76 seconds
  hosted and 40 seconds native, the latter using a C-built seed pair and
  direct x86-64 output. The dedicated campaign (2026-09-15/16) brought the
  native cold self-build to 18.2-18.5 seconds, under the 30-second target
  but above the 10-second stretch goal; it was paused there by decision.
  The fully direct bootstrap (both compilers, two byte-identical
  generations, no C after the seeds) was verified on 2026-09-18 in 137 s.
  The timings above are single-generation measurements, not fixed-point
  certifications.
  Recorded inputs, seeds and phase timings live in
  [`bootstrap/PHASE0_MEASUREMENTS.md`](bootstrap/PHASE0_MEASUREMENTS.md);
- the way around staged seeds when the language changes: the compiler's
  own source will use each new feature, and a hosted compiler that already
  supports it avoids a two-generation staging dance for every change.

The hosted compiler must remain dependency-free beyond Python and the existing
system build tools. Do not introduce Cython or another required Python package
as a performance strategy. Native performance takes priority; keep measuring
and improving the hosted path, but it may lag behind the native time target.

That independence has limits: the compilers share the µDewy execution layer
and runtime library. Keep explicit expected-result tests alongside
differential comparisons, so agreement between implementations cannot hide
a shared bug.

Its role changes in three steps, decided 2026-09-14:

1. **Full parity (now, and through the period of frequent language
   change).** Features and semantic fixes land in both compilers. Parity
   includes agreement on acceptance and rejection of programs under the
   settled language rules, and identical behavior for accepted programs.
   Exact diagnostic wording need not match. Work is bidirectional: port
   native-only semantic fixes back to Python, and close native gaps in
   features the hosted compiler already supports. Most currently recorded
   language-coverage gaps are in the latter direction. Parity is not parity
   in cost; the native lowering already reclaims storage the hosted lowering
   does not, and the hosted side is not required to match that.
2. **Pinned reference.** When the language changes slowly enough that
   staging is cheap, the hosted compiler is pinned at a language version N
   and stops taking features. Native N+1 is built by native N, which was
   built by hosted N. The execution-parity oracle keeps working across
   versions for programs both accept.
3. **Retirement.** When native compile time is competitive, a
   reproducibly built native seed is published, and the language has
   stabilized. Expected around the end of Phase 2, not Phase 0.

## Phase 0: workable native compiler (in progress, mandated)

Exit criteria that the later phases depend on:

- verified fixed point: two native generations of both compilers, byte
  identical, built without Python (`tools/bootstrap_native.sh`); achieved
  with C acceleration on 2026-09-14 and through the direct x86-64 backend
  alone on 2026-09-18;
- the native pair passes the full end-to-end corpus, the differential
  `test_bootstrap_*` groups, and the `$test` runner;
- installer and release wired to the verified package (achieved); CI green
  remains a separate gate;
- the Python compiler remains the behavioral reference and stays in
  parity (see "The hosted compiler's role"); its retirement is not a Phase
  0 exit criterion;
- compile-time performance adequate for dogfooding, measured against explicit
  time and memory budgets. The dedicated campaign below targets a complete
  native compiler build in under 30 seconds, with under 10 seconds as the
  stretch goal. Hosted performance is secondary and may lag behind. Record
  cold and warm compilation separately for a small program, a representative compiler
  module, and the full compiler.
  Record checking, lowering, emission, and backend timings; peak memory;
  generated µDewy size; and copied bytes, shared snapshots, and detachments.
  Establish the baselines and workload budgets before accepting optimization
  batches, rather than treating a successful self-build as sufficient.

### Immediate work order

**Review checkpoint (2026-09-20):** keep the order below, with a short
correctness/parity closure pass before expanding Phase 1.1. Recent borrow
elision crossed value boundaries through aliased places and raw-exposed
records; regression fixes and the review are recorded in
[`bootstrap/REVIEW_2026_09_20.md`](bootstrap/REVIEW_2026_09_20.md).
Finish the corpus expectation for `nat_types`, use explicit fixture outcomes
(including arguments and expected failures), and verify ownership changes
with a second-generation compiler as well as hosted/native comparisons.
Do not mistake agreement between implementations or a fixed point for an
independent correctness oracle.

Complete copy-report coverage and module attribution before enforcing
`$explicit_copies` across the compiler. Its approved explicit remedies must
work before diagnostics prescribe them. Strict-mode acceptance must agree
between compilers even when their optimization choices differ. Continue
targeted alias/effect and move work in this checkpoint; broader lifecycle
and proof-engine work follows the Phase 0 gates rather than replacing them.

1. Establish a bidirectional semantic parity inventory and isolated
   regressions for acceptance, rejection, and execution. A first unsupported
   construct must not conceal the rest of a corpus bundle. Use
   `bootstrap/IMPLEMENTATION.md` as the starting inventory, not an exhaustive
   list of gaps. Establish reproducible performance baselines alongside it.
2. Run the dedicated performance campaign once the compiler's own source and
   the optimization regression cases work reliably on both implementations.
   Unrelated parity gaps can remain while this campaign runs.
3. Finish the remaining Phase 0 parity, corpus, and release/CI gates with the
   faster development loop.
4. Proceed into the broader ownership, proof, and effects work. Targeted
   ownership improvements, and the proofs or effects needed to justify them,
   can be pulled into the performance campaign where measurements warrant it.
   Ownership does not wait for the complete solver.

### Dedicated performance campaign

Plan a sustained optimization effort early in Phase 0, potentially about a
week when started. The duration is an investment in reaching the target,
not a guarantee that the target will be achieved within a week. This
milestone consolidates the performance work below and selected parts of
Phase 1.1, rather than spreading it across ordinary feature development.

**Status (reviewed 2026-09-20):** the campaign paused at 18.2-18.5 s cold
using a C-built executing compiler and direct output; later source grew this
to about 20 s. The direct-built executing compiler remains around 44.6-44.7 s
for the same kind of full build. The accelerated route meets 30 s; the
no-C route does not yet. Track these as separate benchmark rows, with an
explicit seed provenance, and retain the under-10-second stretch goal.
Slices, numbers and the remaining levers are recorded in
`bootstrap/PHASE0_MEASUREMENTS.md`. Resume measured batches that remove
repeated work or improve generated code, including Phase 1.1 where justified.
Static copy-site counts supplement elapsed time and runtime allocation/copy
counters; a lower site count alone is not evidence of a faster compiler.

**Acceptance target (revised 2026-09-15):** the native compiler builds the
Dewy compiler from source into an executable in **under 30 seconds** on a
recorded benchmark machine; **under 10 seconds** is the stretch goal. Keep
the dependency-free Python-hosted compiler usable and measured, but it need
not reach the native target before the campaign can succeed. Time the complete
invocation, including checking,
lowering, emission, µDewy compilation, and linking; include C compilation
when that route uses it. Measure one compiler generation separately from
the two-generation bootstrap verification and its execution checks.

Record cold full builds, warm full builds, and incremental builds separately,
with the machine, toolchain, backend, options, and cache state. A cached
executable or an incremental result cannot establish the full-build target.
Retain semantic and expected-result tests, deterministic bootstrap checks,
and bounded memory budgets throughout the campaign.

Use the machine's compute and memory throughput to challenge the amount of
work performed: record source and output bytes, node counts, allocation and
copy volume, and repeated visits alongside elapsed time. Distinguish an
idealized bandwidth/cycle budget from an achievable compiler time; parsing,
proofs, pointer chasing and toolchain startup cannot be priced as a single
streaming copy. Prioritize eliminating redundant representations and passes
when costs exceed those justified by the workload, rather than chasing small
speedups in already cheap operations.

The campaign covers the whole compilation path:

- Eliminate repeated type queries, expensive cache keys, redundant tree
  transformations, and unnecessary intermediate representation construction.
  Keep hosted and native profiles separate and prioritize measured costs.
- Implement native checked-prelude caching. This should particularly improve
  ordinary edit/run cycles; measure its effect on full self-builds separately.
  Restore binding and type identities correctly, and invalidate cached state
  when compiler/cache format, library inputs, target, or relevant options
  change. Cached and uncached compilation must agree semantically.
- Reduce generated-code expansion through helper reuse, static data, and
  cheaper emission, and reduce text-processing overhead between stages.
  The verified self-build emitted roughly 97 MB of µDewy. Its downstream
  compilation takes minutes, so faster analysis alone cannot meet the target.
- Improve the µDewy and C compilation paths as measured bottlenecks warrant.
  Keep the direct backend as a measured route throughout, preserving the
  goal of a reasonably performant full bootstrap without C acceleration.
- Pull forward targeted ownership and allocation improvements from Phase 1.1
  where copying or reclamation dominates, together with the specific proof
  and effect improvements needed to make them sound.

Work in coherent optimization batches against bounded representative
benchmarks. Run full compiler builds and bootstrap comparisons at meaningful
integration checkpoints, rather than after every small edit. Reaching the
target is likely to require eliminating whole categories of repeated work;
small local speedups alone are unlikely to be sufficient.

### Performance measurements and candidates

The measurements below describe the hosted Python route. They identify
candidate work, not the native compiler's current profile. Native lowering
already caches record layouts, shares copy/release helpers, and emits static
string descriptors. Measure the remaining costs of those mechanisms before
porting an optimization or expanding it further. Cache pure queries only
within the compilation state where their inputs and dependencies are stable;
frozen type objects alone do not justify caching queries that depend on
changing registries or facts.

- Generated µDewy size and the time spent generating it
  (hosted measurement, 2026-09-14, `bootstrap/parser/t0.dewy`, 873 lines: 5.7 MB /
  79k lines of µDewy; 17.9 s to check, lower, and emit against 4.6 s for the
  µDewy stage to parse, assemble, and link). The text is large, but the time
  is mostly in *building* it — lowering is about three quarters, checking a
  seventh, emission a ninth (a third of that the source-position markers).
  In order of payoff per risk:

  1. cache the pure type functions the lowering recomputes per site
     (`_object_layout` ran 24k times, the union-member computation 18k, for
     that one program; ninety union result writes cost 9 s between them) —
     output-neutral, plausibly a third to a half of the lowering time;
  2. outline what a person writing µDewy would call a helper for: the
     scope-exit release sequence (3,274 inline blocks of ~6 lines, about a
     fifth of the file) as one prelude call; a per-type copy function for
     object copies and union writes instead of inline field-by-field stores;
  3. hoist string literals (595 sites, each rebuilding its descriptor and
     boundary table with a dozen stores every time the site runs) into
     module init or static data, and build the module-level constant tables
     (the 15k-line top-level function: symbol lists, character sets) as data
     rather than store by store;
  4. emit source-position markers (12.7k lines) only for debug builds, or
     thin them to statement starts.

  The original estimate of about half the text and a further slice off
  lowering is a hypothesis from this hosted profile, not an established
  speedup or a native target. Measure after each batch, since the profile
  shifts. The checker's share is analysis proportional to the program, not
  the output, and is a separate problem (the proof engine's bounded
  traversals, 1.2).
- Further candidates from that hosted self-time profile, intended to preserve
  output (recorded 2026-09-14):
  - `repr` of whole types as sort and cache keys: `runtime_union_members`
    and `enum_members` sort members by `repr(member)` (`semantic/ty.py`),
    and `_member_tag` keys its cache by `repr(plain)`
    (`backend/udewy/lowering_optionals.py`). A record's repr is its whole
    nested dataclass text, guarded by `reprlib` — 3.6 million repr calls and
    7.5 million set operations for one program, the single largest self-time
    item. Memoize by retained type-object identity within a stable lowering
    scope, or key by a cheap structural hash where safe. Some type objects
    contain mutable unions or unresolved aliases; global memoization is
    unsafe. The first scoped-cache batch and measurements are recorded in
    [`bootstrap/PHASE0_MEASUREMENTS.md`](bootstrap/PHASE0_MEASUREMENTS.md);
  - `location_marker` resolves the source path (`Path(...).resolve()`) for
    every marker — 52k `realpath` and 181k `lstat` calls, about 1.9 s.
    Resolve once per source file;
  - `is_subtype` normalizes both operands on every query (`to_nnf` 276k
    calls, 3.3 s) and `user_brand_carries` runs 474k times (1.7 s). Memoize
    `normalize`, or `is_subtype` itself for hashable operands;
  - the tree rewrites (`ModuleCompiler._rename`, `_uniquify_module_locals`,
    the analysis walkers) call `dataclasses.fields` per node and `replace`
    on every node: 331k and 280k calls, about 3.7 s. Cache `fields` per
    class, and rebuild only changed subtrees — the whole prelude tree is
    renamed on every compile though its renaming never changes;
  - the µDewy stage is its own front end: of its 4.6 s, tokenizing and
    parsing the text are about nine tenths (a character loop with 4.6
    million `startswith` calls, then a recursive-descent parse); assembling
    and linking are about a second. A regex-driven tokenizer helps; better,
    when the hosted compiler drives the µDewy compiler in-process it can hand
    over its statements or tokens and skip the text round trip entirely.

## Phase 1: foundations to their intended designs

### 1.1 Memory and ownership model

The intended design is recorded in `status.md` ("Ownership and storage
model") and `semantic/value_semantics.md`: one owner per value, moves by
last-use liveness, borrows where proven read-only, deterministic release,
placement (stack, static, scoped arena) as a proof-gated optimization.
Copy-on-write is a provisional bootstrap accelerator
(`bootstrap/PERFORMANCE.md`), not the long-term mechanism.

**What went wrong last time.** The model was not the problem. The analysis
could not justify enough borrows and moves, so lowering fell back to "copy to
be safe", and the compiler's own code shape hit the worst case for that
fallback. Profiles taken during the September 2026 paired self-build
attempts (summarized in `bootstrap/PERFORMANCE.md`) showed every sample
inside string cloning, called from record copying, called from reading a
node out of the type arena: a read-only arena lookup paid a full deep copy
each time, for a cumulative 324 GB allocated against 9 GB live. Copy-on-write
made snapshots cheap until a write; together with string ownership and
temporary reclamation, it unblocked the bootstrap. The completed run no
longer has that memory blocker, but compile latency and allocation overhead
still make ordinary native development too expensive.

**Strategy.** Make it structurally impossible to re-enter that state
silently.

1. **Every copy visible and budgeted.** Extend the existing kernel gates
   (`tests/python_misc/test_array_sharing.py` and its byte/allocation
   counters). `dewy analyze` reports aggregate copy sites with the reason
   the analysis could not borrow or move them (landed 2026-09-20 in both
   compilers, with `tools/copy_report.py`; the initial native baseline was
   7,910 sites, see `bootstrap/PHASE0_MEASUREMENTS.md`). Report completeness
   and hosted/native coverage still need verification. These are static
   sites, not execution counts or bytes; a hot loop and a cold branch each
   contribute one site. Treat
   "unexplained copies on the compiler's own sources" as a CI metric with a
   fixed budget per kernel and per thousand lines. The native command test now
   gates the bootstrap inventory at 4,500 static sites and 100 sites/KLOC;
   the measured arithmetic-proof checkpoint is 4,497 sites and 92.481/KLOC. Concise reporting
   retains every entry while avoiding repeated source rendering. Regressions
   surface in a pull request, not at 25 GB in a self-build.
2. **Mechanisms in order of where the bytes went.** First: read-only
   element and field reads that do not escape their expression or scope
   lower as views, justified by the effect analysis proving the root is not
   mutated during the borrow. This alone removes the arena-lookup case.
   Second: moves at last use for records, strings, and unions (arrays
   already have this). Third: scoped arenas for the checker's per-branch
   temporaries. Each step is measured against the gates before the next.
3. **Ratchet copy-on-write down, do not rip it out.** Keep it behind the
   same descriptor interface as the fallback. Count detachments and shared
   snapshots per kernel. Remove it from a shape only when the static path
   drives that shape's count to zero on the compiler's sources. What remains
   becomes the opt-in strategy the design wants for types that choose it.
4. **A fast path that never waits on inference.** The compiler makes the
   `addr`-handle-into-arena idiom the bootstrap already uses cheap first.
   Implement the approved `const node = @arena[id]` escape hatch below,
   with a conflicting write diagnosed at that write. It must use the same
   alias/lifetime rules as inferred views, not bypass a failed proof.
5. **Explicit fallback policy (decided 2026-09-13).** When a borrow or move
   cannot be proven, the default is a copy accompanied by an analysis note,
   never a silent copy. A module-level opt-in directive turns any unproven
   copy of a runtime-length aggregate into a compile error. The compiler's
   own sources are intended to compile under that directive once reporting,
   explicit remedies and acceptance parity are complete. Its approved
   spelling is `$explicit_copies` (see the decisions below). Both lowerers now
   enforce the per-module policy on recorded runtime-sized copies, including
   nested storage, without a CLI-only scan. Reporting coverage and ownership
   proof parity remain in progress.

The difference from the earlier attempt is the order and the gate: each
mechanism lands against a measured kernel and the compiler's own sources,
with copy-on-write as a measured floor rather than a cliff. The hosted and
native compilers stay in behavioral parity throughout: each mechanism lands
in both lowerings and the parity tool is the gate.

**Decisions of 2026-09-19 (David):**

- *Unproven copies.* The module-level directive is `$explicit_copies`; under
  it an aggregate copy the analysis cannot justify is an error whose
  diagnostic names the reason and the explicit forms: `.copy()` to keep the
  copy, or a read-only view. Without the directive the copy lands with an
  analysis note.
- *Read-only views.* A `const` binding of a place (`const node = arena[id]`)
  is a view whenever the analysis proves the source is not written while the
  binding lives; otherwise it copies (with a note, or an error under the
  directive). The explicit form `const node = @arena[id]` demands the view,
  so a conflicting write is reported at the write instead of the binding
  copying; `let cursor = @xs[i]` is a mutable place, as `@` already means
  for arguments. The `@` forms are a stop-gap that should be needed less as
  the analysis improves, and the documentation must say so.
- *Lifecycle hooks.* Metatagged members of the mint: `$__drop__`,
  `$__copy__`, `$__move__`. A type opts in by declaring them. Declaring
  `$__drop__` without `$__copy__` makes the type move-only: no synthesized
  copy. `b = a` on such a type is a move at a last use, a view when the two
  names never both write (the compiler decides this from the effect
  summaries, with no annotation), and an error only when the program needs
  two independent resources, reported at the second write with `$__copy__`
  as the fix. Types declaring no hooks keep the synthesized memberwise
  copy, move and release. Hooks are invoked with internal nonescaping
  places, never by passing the value by copy. The intent throughout: the
  compiler infers sharing; the programmer is not asked to fight for it.
  Follow-up approval (2026-09-20): zero-argument compiler-only members;
  copy/move return the same nominal type, drop returns void before automatic
  field cleanup. Observable hook effects are allowed under ordinary effect
  contracts, with no guaranteed invocation count for elidable operations.
  The [approved call protocol](PHASE1_DESIGN_PROPOSALS.md#lifecycle-call-protocol--approved-implementation-in-progress)
  records the details. Both checkers now validate their declarations and
  read-only copy receivers, and compose inherited hooks with the child's
  added fields through checked constructors. Explicit custom copies expose
  hook effects and result facts. Runtime drop now works for fresh local
  owners whose fields use ordinary synthesized cleanup, including inherited
  drops, reverse scope cleanup, scalar implicit results and early returns/loop exits. Its calls participate in fact/effect checking.
  Nested resource records also drop in reverse field order, even when the
  wrapper has no hook. Fresh arrays of resources, including nested arrays
  and array fields, run element hooks in reverse order before releasing their
  storage. Per-shape cleanup helpers retain ordinary bounds/effect checking;
  `push`/`insert` accept fresh or copied owners, `pop` transfers the removed
  owner, and `reserve` preserves element lifetimes. Discarded results drop
  once. `clear` drops elements in reverse order, retaining its checked
  zero-length result fact even through an indexed receiver. `truncate` drops
  only the removed suffix and preserves the builtin's minimum-length facts;
  selectors and counts are evaluated once, with receiver stability checked.
  Dictionary `clear` also drops values in reverse order before resetting
  storage, including indexed receivers selected once. Dictionary/set live
  length facts become zero after clear and are invalidated by later mutations.
  Proven entry reads and `.get` now perform logical component copies; unused
  eager defaults drop on a hit. Stores transfer fresh/last-use owners and drop
  replaced values after evaluating the replacement. Optional and array values
  retain their storage layout. Resource pop transfers
  ownership, including eager default cleanup. Logical copy/drop first compacts
  tombstones, without adding linear work to each pop. Cached resource-entry
  positions are reprobed because synthesized copies can compact the receiver.
  Dictionary values snapshots copy live components through their hooks; keys
  keep ordinary value semantics.
  Resource iterator sources now use ordinary lexical owners: stable sources
  borrow, last uses move, and independent snapshots invoke checked copies.
  Read-only element loans end with each iteration; source cleanup covers
  early returns and loop exits. Mutable local entry places now retain their
  dictionary through the last alias use, capture keys once, and reprobe after
  representation changes. Resource replacement drops the previous owner once.
  Field and element overwrite now capture selectors and replacement values
  once, then drop the previous owner before installing the new one. This
  includes optional fields, nested arrays and borrowed receivers; side effects
  that change the selected receiver during evaluation are rejected. Transfers
  from existing local owners now also supply owning calls, constructors,
  array literals/insertion and replacement at a proven same-block last use.
  Dependent read-only aliases extend the original owner’s lifetime. Resource unions
  and optional owners now select cleanup by the active alternative, including
  array elements; custom union moves consume only that alternative's resources. Explicit custom copies can construct fresh results,
  including nested hook calls. When a surviving source needs an independent
  owner, its declared copy hook now supplies local bindings, projected values
  and owning arguments; its effects and implicit-copy cost remain checked.
  Synthesized record and union copies now call the active components' copy
  hooks, including nested wrappers and temporary receivers. Synthesized array
  copies now run component hooks and prove their returned length; nested arrays
  and optional elements use the same construction. Recursive optional-link records now use checked cleanup helpers, including
  arrays containing those records and recursive factory results. Recursive copy
  hooks and synthesized recursive wrapper copies now preserve independent
  owners. Fresh conditional/block initializers capture their value before
  local cleanup, and branch-local move-only results transfer at proven last
  use, including values followed by unrelated trailing statements. Recursive `array<Self>` and nested array edges now have checked ownership,
  component copying, growth/pop transfer and deterministic cleanup. Empty
  arrays provide a finite base case; nonempty required recursive storage
  still needs a terminating alternative. The remaining dictionary removal and entry-lifetime
  operations are tracked above. Fresh record results now transfer from factories
  (including callbacks) to caller-owned bindings. Results are evaluated before
  cleanup, including aggregate field snapshots and copy hooks with scratch
  owners. Ordinary `@` parameters borrow resource records, including nested
  fields and forwarding through callbacks; callees do not drop borrowed owners.
  Explicit and implicit results transfer existing local owners on the exiting
  path, including conditional results and nested scopes; other owners drop in
  reverse order. A result before trailing statements is saved at its evaluation
  point, and those statements still run before return. Same-scope local bindings
  transfer resources at a proven last use, including inside branches and loops;
  captures and later uses prevent that proof. Read-only same-scope aliases can
  now share one resource owner, including derived aliases and explicit const
  views; source or alias writes still require further lifetime analysis.
  Custom move hooks now run at these transfers. The consumed owner's own drop
  is skipped, while its remaining nested resources and backing storage are
  cleaned up; hook effects are checked through callers. Inherited moves compose
  parent results with added fields, including move-only resource fields and
  arrays. Only the original hook’s parent portion needs leftover field cleanup.
  Inherited copies consume their intermediate parent results, including nested
  resources and multiple inheritance levels. Conditional transfers of outer
  owners now join branch liveness and guard cleanup on the executed path.
  Loop exits now retain their selected continuation: a last use before
  `break`, including a labeled exit, can consume an outer owner when no later
  read or alias needs it. Returning a field or array element from an exiting local or by-value owner
  now transfers it through synthesized wrappers and drops the remaining
  components. Nested selectors evaluate once and retain checked bounds. Custom wrapper
  hooks still require a complete receiver. Last-use component transfers now also
  supply owning bindings, calls and constructors, retaining the wrapper’s lexical
  cleanup. Direct same-block field/ancestor replacement restores partial record ownership,
  preserving cleanup of remaining old components and the new value.
  Whole-owner replacements re-establish ownership across loop backedges;
  every advancing path must provide a fresh value before another consuming use.
  Broader partial transfers and remaining resource-container mutations still
  require further lifetime analysis. Same-block owning input
  transfers now include owning parameters, custom move hooks and union owners;
  first if conditions are unconditional input sites, while loop conditions
  and later arms still need the more general lifetime join. Fresh arguments, factory results and explicit copies
  can supply ordinary by-value parameters, which own and clean up the value.
  This includes callbacks and defaults; returning a parameter transfers it.
  Replacing a local owner or owning parameter now evaluates the new value
  before dropping the old one, including optional owners currently absent.
  The current stored value remains owned across branches and until scope exit.
- *Explicit moves.* No `move` operator or keyword for now; moves are inferred
  at last use and reported by `dewy analyze`. If explicit assertion of a
  last use turns out to be needed it should be a meta-level form (a
  directive), not an operator; to be revisited.
- *Allocation failure.* Tentative: a process-level failure report by default
  on the same channel as `$prototype` panics (its own exit code), and a
  module-level `$fallible_allocation` under which allocating operations
  carry `OutOfMemory` in their result type. Needs more thought before
  landing: the balance of safety and ergonomics, without blind spots or
  sharp edges (`semantic/resource_exhaustion.md`).

Progress on 2026-09-20: explicit `const name = @route` demands are implemented
for stored local values, including scalars and containers, in both compilers. They use the existing stable
storage proof, retain owner liveness through dependent views, and report
conflicting writes instead of copying. Inference first checks stability
throughout the function; required views and inferred const projection views
can also use a containing lexical block or a statement interval ending at the last use of all derived aliases
when the owner is private, uncaptured and unexposed. The live interval now distinguishes return edges inside control flow, so
cleanup after saving a result does not invalidate an earlier view. Loop
backedges retain repeated reads, and outward/captured/exposed aliases retain
the lexical lifetime. Known nonescaping place calls outside the interval no
longer exclude the owner for its entire function. Mutable local places now use rooted bindings, fields and array selections,
capturing selectors once and retaining checked storage/fact/effect contracts.
Their private, uncaptured owners must remain stable through the last use of
all dependent aliases. Proven dictionary entries now use the same lifetime demand, including nested
receivers and dependent aliases. Value writes retain ancestor membership,
while mutable entry routes detach shared dictionary/payload storage and
publish replacement handles back to their slots. Other entry writes remain
conservative; lifetimes for captured or exposed owners remain pending.

### 1.2 The proof engine

Today the refinement system is an interval analysis plus a growing set of
fact-transfer rules, and the bootstrap keeps finding sound-but-missing rules
one at a time. The intended design is the liquid refinement system in
`status.md`: a proposition grammar with a finite qualifier vocabulary,
symbolic state across mutation, effect and alias tracking so proofs survive
calls, a solver that answers unknown rather than false, checked lemmas, and
an `unsafe` boundary that is a real audit obligation. Building that properly
turns the rule-by-rule work into a system. It is also the feature that
distinguishes Dewy from every other systems language, and the standing rule
applies throughout: proofs come from facts the analysis carries, not from
restructuring code into a shape the analysis happens to understand.

Two concrete gaps probed on 2026-09-16 and recorded in `status.md` are the
first tests for that system, because both are loop invariants the interval
rules cannot express one rule at a time. Array length is exact through
straight-line pushes but is dropped at every loop head, so build-then-read
and parallel-array loops need a guard after the loop that restates what the
loop already established (`array_sort.dewy` carries one). And a counter
bounded by an enclosing range iterator (`loop j in [0..i)` inside
`loop i in [0..xs.length)`) is rejected as unbounded although the same loop
written with an explicit `int64` counter proves. The symbolic state across
mutation described above should carry "length grows by one per iteration"
and "an iterator's interval is a fact inside nested loops" as consequences
of the design rather than as two more transfer rules.

Progress on 2026-09-20: shared array-length equality invariants and nested
range-counter fixtures now pass in both compilers. Counter storage uses an
inductive word-range candidate, checked on every advancing edge; failed
candidates are discarded before ordinary body validation. Bounded constant-difference
qualifiers now connect entry intervals as well as exact values; every
backedge must preserve them. A bounded vocabulary also selects term pairs
mentioned in loop predicates/arithmetic, so an unrelated counter need not
displace a useful relation. A source assertion selects a candidate but never
establishes it: the incoming intervals and each advancing edge supply proof. Word updates keep affine facts only when
neither the arithmetic nor its destination can wrap. Stable literal/const-selected array and dictionary reads also consume
branch type alternatives and predicate-result facts, while writes retain their
storage contracts. Mutation prefixes invalidate possibly aliased descendants
without discarding ancestor type facts. Established ordering facts now form a finite
worklist graph, so proof search has no fixed two-step chain cutoff. Hosted fact
keys are structural, and both registries keep declaration/route identities
disjoint beyond the old packing boundaries. Arithmetic differences and slice
lengths consume the same graph, retaining address-cap provenance through
transfers and widening. The general liquid qualifier/invariant
work remains broader than these completed fixtures.

### 1.3 Effects as a real vocabulary

The transitive parameter effect analysis exists
(`semantic/analyze/effects.py`). Initial source contracts now keep the public
row separate from those access summaries: both compilers check `no_effects`
(and `Effect<>`), nominal `reads<Resource>` / `mutates<Resource>` permissions,
place-parameter routes, and `no reads<Resource>` / `no reads` exclusions.
Direct calls, including imported helpers, infer effects across the checked
module graph and translate place subjects; constrained callbacks retain open
negative guarantees. Unknown operations cannot satisfy an empty row or an
unproved exclusion. Separately kind-checked `<E:Effect>` parameters now infer
and substitute callback rows in both compilers, including mixed type/row
signatures and distinct cached instances. Omitted literal rows now travel through ordinary callable values and generic
calls, including recursion, conditional joins and independently reassigned
handles. Selected value boundaries are checked after solving and again after
lifecycle lowering; an unknown callback parameter stays unknown. Inferred wrappers now retain open negative guarantees using a separate finite
exclusion fixed point: every body and incoming assignment must establish each
surviving exclusion. Generic row substitutions now retain shared negative
guarantees as well, including their cache identity and restored bindings.
Inferred call rows now retain their subject environment until the source row
is resolved, including reordered parameters, field routes and reassigned
callbacks. Body equations and callable boundaries share the same solver.
Inverse mappings propagate demanded exclusions through a finite vocabulary of
route suffixes without strengthening their scope. User-written polymorphic
place rows remain in progress. Bare
`allocates` / `no allocates` now classify logical copies and aggregate
construction; fixed scalar local arrays and scalar record literals now share
a bounded nonescaping frame-placement proof with lowering. Native record
storage is allocated once per function frame and reused across loop iterations.
Fixed local arrays and scalar records may lend field/element addresses through
known nonescaping helpers, including forwarding and recursion, without losing
frame placement. Whole-owner loans now include read-only scalar arrays and
field-mutating scalar records when every known callee preserves their backing
storage. Fresh local arrays and records can also lend ordinary by-value
arguments to proven read-only callees while retaining frame placement. Unknown
callbacks, whole-owner replacement/resizing and unproved owning uses remain
conservative. Conditional choices among known
callees keep the guarantees common to every branch, with selector effects
checked separately and shared choices visited once.
Projected writes and mutating place calls share their allocation obligations;
an untouched sibling projection can still borrow its own storage.
Read-only aggregate forwarding now shares its storage
proof with allocation contracts, including records, strings, tagged unions and field/element
projections of stable by-value parameters. Read-only optional and general-union
default parameters borrow supplied cells and own omitted defaults. Absent
union values use static/frame storage; mutable container slots retain private
tag cells. Lifecycle operations, unknown
callbacks, raw exposure and conflicting argument evaluation retain their
ordinary obligations. The placement proof is exercised by a zero-allocation loop kernel
on both compilers/backends. Broader placement/move proofs and further storage
operations and failure remain in progress. The reviewed rules are in `PHASE1_DESIGN_PROPOSALS.md`.
Effect polymorphism, allocation and failure as effects, and the
`noreturn`/escape set are prerequisites for compile-time purity (Phase 2),
the resource-exhaustion policy (`semantic/resource_exhaustion.md`), and the
concurrency model (Phase 4). Effects remain separate from errors: errors are
union alternatives, effects describe evaluation behavior.

### 1.4 Design-decision sprint

A short pass over small surface questions that get more expensive every
month and block documentation and library code. None needs a large
implementation; the value is in closing them. Each case below states the
question with a minimal example, then the decision (or that it stays open).
Decisions were made by David on 2026-09-13.

1. **Juxtaposition with union-typed operands (decided).** Writing two
   expressions next to each other is an operation chosen by the operand
   types: a callable on the left means call, a number means multiply.
   The two forms have different precedences on purpose, so that
   `sin(x)^2` is `(sin(x))^2` while `2x^2` is `2 * (x^2)`. The question
   is what happens when the left operand's static type is a union of a
   callable and a number, since the parser cannot pick a precedence:

   ```dewy
   let f:((int):>int) | int = ...
   f(x)^2        # call or multiply?
   ```

   Decision: such union types are allowed by the type system, but a value
   of one reaching a juxtaposition is a compile error as ambiguous. The
   diagnostic must show the explicit forms: `A |> B` or `B <| A` for a
   call, `A * B` for a multiplication. Parenthesizing is not offered as a
   fix, since the parentheses are gone by the time the operation is chosen.
   Both precedences stay. A bare number written directly after an
   expression (no whitespace) is an ordinary juxtaposition, and the left
   operand's type chooses the operation exactly as it does for any other
   right operand: a number on the left multiplies, a callable calls, and
   the callable-or-number union above is the ambiguity error. Whitespace
   separates expressions, so `x 2` and `(x+1) 5` are two expressions.
   Intended results (confirmed by David 2026-09-21):

   ```dewy
   2x            # multiply
   2 x           # two expressions
   (x+1)5        # multiply (a number on the left)
   (y)3.14159    # multiply
   (f)2          # call if `f` is callable, multiply if `f` is a number
   g(1)2         # the call result decides: multiply for a numeric result
   printl"hi"    # call
   ```

   **Correction (2026-09-21):** the earlier record here said a number on
   the right starts a separate expression; that was a misreading of a
   tentative note in the hosted `t2` stage, not a decision. Both parsers now
   leave tight right-hand numeric adjacency as undecided call-or-multiply;
   whitespace still separates expressions. The four erroneous blacklist
   entries were removed, and hosted grouping now preserves a callable's
   call-target context through single parentheses, matching native behavior.
   The precedence fixture checks `(x+1)5`, `(f)2`, `g(1)2` and exponentiation
   on both routes. Callable-or-number union ambiguity remains an error.
2. **Based byte literals (open, low priority).** Strings carry no `\x`
   escape because a string is a sequence of scalars, not bytes, so byte
   arrays need their own literal. The compiler already implements the
   based-string family for power-of-two bases, e.g.
   `a:array<uint8> = 0x"00 ff ab 12"`, with digits in big-endian order.
   Still undecided: whether the reserved non-power-of-two bases
   (`0t 0s 0d 0z 0r`) pack or are rejected, which separators are allowed,
   and the exact rule relating digit order to a numeric literal reinterpreted
   with `transmute`. See `../resources/discussion_points.md` ("How to input
   byte-arrays").
3. **Keywords (decided).** The hosted `t1` stage carried a note asking
   whether `extern`, `intrinsic`, `none`, `void`, `untyped`, `end`, and
   `new` are keywords (cannot be shadowed, may change parsing) or ordinary
   identifiers the prelude provides (`let none = 5` would be legal).
   Decision: `extern`, `intrinsic`, `none`, `void`, `end`, and `new` are
   all reserved. `end` is the last-index name inside an index expression
   (`xs[end]`). `new` is the NumPy `newaxis` idiom: `myarray[new]` yields
   an array (or view) with an extra singleton dimension at the front,
   `myarray[... new]` at the end, following NumPy exactly. `untyped` was
   only an internal inference marker (`ty.INFERRED_TYPE` still uses the
   string internally) and is not reserved as surface syntax.
   Implemented 2026-09-20: both compilers reject the six reserved names in
   source bindings, including parameters, fields, methods and import aliases.
   Existing value/type/index roles remain valid; `new` axis insertion is
   still separate implementation work.
4. **Brackets for parametric types (decided).** Whether `array<int>`
   should become `array[int]` or `array(int)`. Dewy's comparison operators
   are `<?` and `>?`, so the usual less-than ambiguity does not arise; the
   one wart is a shift inside a type parameter needing parentheses
   (`something<(a >> b)>`). Both alternatives collide with indexing or
   calls under juxtaposition. Decision: `T<>` stays.
5. **Export control (decided).** Every top-level binding in a module is
   importable today; the question was whether an `export` keyword or a
   privacy modifier is needed. Decision: Python's convention. Everything
   is public, a leading underscore marks a binding as private by
   convention, nothing is enforced. Left alone until people demand more.
6. **Unicode identifiers (partly decided, low priority).** Which non-ASCII
   characters may appear in identifiers (the hosted `t0` stage lists
   candidate additions), and which visually or semantically equivalent
   spellings name the same binding. Direction (2026-09-19, open to
   adjustment): an underscore followed by a run of digits spells those
   digits as subscripts, and the overline `‾` (U+203E) followed by a run
   of digits spells superscripts; digits only, never letters, and
   adjacent runs combine:

   ```
   x_12       == x_1_2 == x₁₂
   foo_bar    stays foo_bar
   foo_2      == foo₂
   foo_2_bar  == foo₂_bar
   x‾12       == x¹²
   ```

   So `x₁` and `x1` are different names, `x₁` and `x_1` the same, and
   `x_12` and `x_1_2` normalize to the same identifier (accepted with some
   apprehension, since it merges names other languages keep distinct; the
   display form is indistinguishable, which is the point). Letter
   subscripts and superscripts (`xᵢ`, `xₙ`, `xᵀ`, `λ̂`) are written as the
   Unicode characters directly. A doubled `__`/`‾‾` as an escape from the
   rule is a possibility with trade-offs against dunder names; open.
   Domain notations put superscripts in the power position legitimately
   (the robotics twist `₂V₃¹`, spelled `_2V_3‾1`); the style guide should
   say a superscript in an identifier is a label, not an exponent, rather
   than discourage the form.
   Look-alikes normalize to one character (the micro sign and Greek mu are
   the same name), except between ASCII and Greek letters, which stay
   distinct (`A` and `Α` differ). The full repertoire is still open.
   Implemented 2026-09-20: digit-label normalization and the micro-sign alias
   in both t1 parsers, preserving raw source spans and ordinary letter names.
   Emission encodes non-ASCII symbols for µDewy rather than expanding its
   identifier grammar. The open repertoire and doubled-marker escape remain
   separate design questions.
7. **Unit-like nominal types (decided).** A minted nominal type with no
   fields, such as an error type declared as `Overflow = type of error`,
   is spelled the same way whether used as a type or as its single value:

   ```dewy
   let r:int64 | Overflow = ...
   if r is? Overflow ...     # the type
   return Overflow           # the value
   ```

   Decision: the shared spelling is the language rule and the name is
   usable in both roles. Whether the implementation represents the type
   and its inhabitant as one object or two is internal.
   Verified 2026-09-20: both compilers execute ordinary and error sentinels
   in unions, preserve identity through namespace/selective imports and type
   aliases, and distinguish independent empty mints with the same spelling.
8. **Container method names (decided).** Dewy collapses names that mean
   the same thing across container types (`length`, `pop`); the open item
   was whether sets should keep `add` or use `push` like arrays. Decision:
   `push` is the uniform name for adding to any container, sets included
   (their insertion order is guaranteed, so "push" is meaningful); `pop`
   is the uniform name for removing. Uniform names may take
   container-specific parameters, but the name and the broad signature are
   the same everywhere. `length` is the uniform accessor for both length
   and shape: on a multidimensional array `myarr.length` returns an array
   of dimensions. There is no `size` or `shape`.

Not decisions: the precedence adjustments once listed as open in the
reference's design-status appendix (word `not` below comparisons,
one-direction comparison chains, postfix `or_throw` below `as`, prefix
`type of`) landed on 2026-08-31; see `semantic/precedence.md` and the
2026-08-31 entry in `status.md`. Multidimensional shape syntax is a real
design but belongs to Phase 3.

## Phase 2: expressiveness on top of the foundations

- **Parameterized types**, explicit type arguments, monomorphization. This
  unlocks the stated long-term goal of moving arrays, dictionaries, sets, and
  strings out of the compiler into Dewy libraries, which shrinks the
  compiler and makes the ownership model testable in library code.
- **Closures as environment records**, using the ownership model for
  captures (today: lambda-lifted non-escaping local functions only).
- **Compile-time evaluation, first slice:** the reflection primitives in
  `semantic/argparse_and_reflection.md` (`fields`, `members`, `$field`,
  unrolled literals). Then general compile-time execution under the purity
  and termination rules. This replaces pressure for compiler builtins; the
  rule stands that library features are built on reusable primitives, never
  on the checker recognizing a library call. Note: compile-time execution
  does not make the compiler faster; it makes it smaller and more uniform.
- **Error propagation completeness:** transformed propagation, pipe
  forwarding, the `exception` family finished.

## Phase 3: the engineering numerics story

The front-page promise, nearly untouched: IEEE floats and promotion,
multidimensional arrays with shapes and broadcasting, vectorized calls,
matrix and linear-algebra overloads, the rest of the units library
(conversions, offset scales, display units), a math standard library. After
Phase 2 because it needs generic types, compile-time shapes, and the
juxtaposition decision. `semantic/numerical_stress_test.md` is the
evaluation plan.

## Phase 4: reach

- A stable foreign-function interface; target triples with structured
  `$target` gating (`status.md`, "Proper compilation target list"); full
  prelude on wasm32; at least one non-Linux host.
- The concurrency model (`semantic/safety_and_concurrency.md`):
  partition-first fork-join, `Send`/`Sync` as structural properties, then
  the resource-exhaustion policy. Deliberately last among language
  features: its design has a dozen open questions and needs ownership and
  effects settled first.

## Phase 5: ecosystem

Language server on the native parser and checker (replacing the lexical
TextMate grammar and any tree-sitter path), formatter, installed-package
imports, the documentation projects and case studies in
`../site/DOCUMENTATION_PROJECTS.md`, and the trusted-computing-base and
DewyOS explorations. These make the language real to other people, but
should not be built twice, so they wait for the native compiler and a
stable surface.

## Deprioritized

- Additional µDewy backends, the browser playground, and the hypothetical
  ndewy rung (a TBD section in `../udewy/trusted_computing_concept.md`; no
  code exists). Finished enough, or not started, and correctly so for now.
- Matching the native compiler's storage cost in the hosted lowering.
  Parity is semantic; the hosted compiler is the reference and the seed,
  not the performance target.
- Any new user-visible spelling before the Phase 1.4 decisions; surface
  changes need David's approval first.

## Ordering decisions and open questions

- Keep ownership (1.1) before the full proof engine (1.2), while landing the
  targeted proof and effect improvements needed to justify borrows alongside
  it. The bootstrap memory blocker is resolved; the purpose now is predictable
  costs and practical native development, without making either project wait
  for the other to be complete.
- Whether compile-time reflection deserves to move into Phase 1 so more of
  the standard library can be written in Dewy earlier. Current lean: no; it
  does not help compiler performance and its purity rules want effects
  (1.3) first.
