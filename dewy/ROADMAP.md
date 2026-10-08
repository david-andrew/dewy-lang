# Dewy roadmap after the native bootstrap

This is the high-level roadmap for taking the language from "a native
compiler pair exists" to a practical compiler and the language as it was
intended. It records the order in which the remaining pieces should land,
why that order, and the strategy for the pieces where the project has
previously bogged down.

The [September 29 audit](AUDIT_2026_09_29.md) records fresh direct-native
measurements, capability/validation gaps and proposed sequencing adjustments.
Its sequencing recommendations were accepted on September 29 and are reflected
below: bound the remaining Phase 1 closure work, improve the feedback path,
and resume the throughput campaign within Phase 1. The same review makes
generated-program performance and efficient CPU/GPU array execution explicit
project goals. The audit remains a record of that revision's measurements,
not certification of later changes.

The [September 30 follow-up](AUDIT_2026_09_29.md#follow-up-2026-09-30)
adds semantic-composition and library-boundary counterexamples, local
representation/call specialization, and lifecycle value-preservation questions.
David accepted the local-specialization direction and clarified fresh builds
without persistent caches and programmer-trusted general compile-time execution.
Library-defined validation is the provisional default: prefer checked guarantees,
allow a narrow documented trust boundary where needed, and revisit it with
library experience. The exact validator/proof interface remains open.

The [focused September 30 audit](AUDIT_2026_09_30.md) adds bounded inference,
type-algebra, specialization and leaf-code evidence, a source-inspected string
capacity hazard, and an append-stability dependency for future dense arrays.
Its [follow-through](#focused-audit-follow-through-2026-09-30) records targeted
work within the current phases. Largest-descendant layout, dense storage and
variant reuse remain attributed to the earlier review; temporary-cache work
does not become a permanent architecture priority.

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
The current immediate work order and performance goals were updated with
David's review on 2026-09-29. Later feature designs still need review where
their semantics are unsettled.

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

## Performance goals across the roadmap (accepted 2026-09-29)

**Compiler speed:** the final target is compilation on the order of Jai's
compiler, allowing Dewy to be somewhat slower for its richer semantics, but
not by a large factor. Under 30 seconds for a full native compiler build is
the nearer minimum milestone; under 10 seconds is the next milestone, not
the destination. Use recorded machines and comparable workloads when making
external comparisons; source lines alone do not normalize proof work or
language differences. The final target is a fresh whole-program build without
incremental state or persistent compiler caches, including the checked prelude
(clarified 2026-09-30). Existing prelude caching is a transitional implementation
aid, not a permanent exception. Reusing analysis within one invocation is compatible
with this goal; record cached and uncached measurements separately during transition.

**Program speed (clarified with David, 2026-10-03):** straightforward,
idiomatic Dewy should approach the performance of equivalent, idiomatic C/Rust
and be comfortable for games and other demanding applications. Common
abstractions should compile efficiently without pervasive performance
annotations. The default compiler should provide useful application performance
with very fast compilation; further optimization may trade compilation time
for execution speed. Matching C/Rust is the ambition, not a claim of current
measured parity.

This clarification replaces the earlier approximate 80% default/optimized
throughput target with workload-specific evaluation. No universal percentage
is selected: the cost of language semantics, the quality of ordinary source
and representations, and the gap between fast and optimizing code generation
are separate questions. Establish numeric budgets for named workloads from
comparable measurements and application needs. Report important regressions
individually rather than allowing an aggregate average to conceal them.

The fast development backend must therefore produce useful machine code,
not merely compile quickly. Measure compile latency and output execution
separately, including the native compiler as an output program. Track CPU
time, peak memory, allocation/copy volume, and latency spikes where relevant.
Use small kernels plus complete workloads: compiler data structures, numeric
arrays, and eventually a game-like update/render workload. Record default
versus optimizing code generation and idiomatic versus manually tuned source
as separate comparisons, plus equivalent systems-language baselines where
available. Keep benchmark source, options and hardware with the results.

Simple value-oriented code should benefit from inferred borrows, moves,
placement, efficient containers and good generated code. Requiring pervasive
explicit views, manual `.copy()` annotations or raw handles to obtain ordinary
performance would miss this goal. Preserve value semantics, facts and effect
contracts while removing their avoidable implementation costs. Copy-on-write
remains provisional: its deferred copies and latency spikes leave predictable,
near-zero-cost storage behavior an open long-term design question.

**Local representation and private call specialization (accepted 2026-09-30):**
choose physical forms from proven uses, with explicit conversion where broader
behavior is required. A semantic type describes permitted values; a local value
need not carry every descendant, union alternative, ownership mode or calling
convention that some other use of that type/function needs. Preserve exact
constructor information, reachable alternatives, consumer field/result demand,
ownership and stable-address requirements through lowering.

Extend existing projected/borrowed getters, direct ownership inputs and local
array placement into shared representation decisions consumed by allocation
contracts, copy policy, cleanup and calls. Distinguish logical narrowing from the
physical layout already stored; transitions must explicitly materialize or convert
values, preserving effects, aliases, value independence and lifecycle obligations.
The first focused batches should:

- retain a private direct-call entry when the function also needs a general
  function-value entry or adapter;
- keep proven exact records compact and generalize only at actual joins, writes
  or escape boundaries; review largest-descendant layout as a general boundary
  representation rather than the inevitable form of every local;
- extend demanded-field results and plan dense aggregate arrays with explicit
  stride, lifetime, mutation and borrowing rules. Separate preservation of
  existing element values during append from physical address stability:
  today's boxed-record guarantee must not authorize dense-storage borrows
  across backing-store growth without representation-specific evidence;
- reuse variants with the same representation, ownership protocol and result
  demand. Measure generic body checks separately from emitted variants and
  code size; emission-only deduplication leaves repeated checking intact.
  Unlimited per-call cloning is not the objective.

Acceptance kernels should establish that an unused subtype does not enlarge a
proven exact local, taking a function's address does not degrade an unchanged
direct call, a field-only consumer avoids a whole-record copy, and a homogeneous
aggregate array has its intended dense layout. Include negative cases where
heterogeneous values, unknown calls, mutation or exposed addresses require a
general form. These are staged implementation targets, not claims of present
support or a new requirement to finish every representation before Phase 1 closes.
Include the same getter/read-across-growth kernel for boxed and future dense
arrays, plus replacement and exposed-address cases. A selected layout must
preserve meaning with an honest borrow/address strategy.

**CPU/GPU execution:** compatible array problems should run efficiently on
the GPU, and applications using both processors should avoid unnecessary
transfers, allocations and synchronization. Phase 3 develops the array
execution model; Phase 4 supplies the broader interop/platform integration.
Establish an efficient CPU baseline first and measure end-to-end GPU workloads,
including transfer and synchronization costs. This direction does not settle
device selection, buffer residency, numeric equivalence or synchronization
syntax; those designs need review before implementation.

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
- installer and release wired to the verified package (achieved); publication
  must be gated by full test and differential certification for the same
  source revision as the packaged fixed point. Historical green checkpoints
  do not certify a newer package;
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

### Immediate work order (accepted 2026-09-29)

The [September 20 review](bootstrap/REVIEW_2026_09_20.md) established the
correctness requirements: value boundaries must survive aliasing and raw
exposure; test fixtures need independent expected outcomes; ownership changes
need second-generation execution as well as hosted/native comparison. Those
requirements remain. The September 29 audit updates the execution order:

1. **Freeze the remaining Phase 1 closure matrix.** Use
   [`PHASE1_PROGRESS.md`](PHASE1_PROGRESS.md) to enumerate supported ownership
   operations, shared storage decisions across checking/effects/lowering,
   actual unsafe-assumption provenance, strict-source adoption and report
   parity, and final integration. Give each row acceptance/rejection examples,
   implementation status and completion evidence. Keep conservative unsupported
   cases visible. Closure-dependent captures stay in Phase 2; genuinely open
   resource/failure designs stay in their design track. This bounds the work
   without declaring unfinished support complete or reducing approved scope.
2. **Improve feedback and revision-specific certification alongside closure.**
   Reuse test-driver builds identified by source/library revision, target and
   relevant options. Separate fast local semantic/allocation gates, frozen
   integration checkpoints, and complete scheduled/release certification.
   Publication must require full pytest, the complete paired manifest and
   native fixed-point evidence for the exact packaged revision. Keep explicit
   expected-result tests and the independent hosted recovery route.
   Add the follow-up's spelling/binding/effect-order regressions and small
   independent library boundary cases to the relevant gates. Compiler agreement
   alone cannot validate a shared arithmetic or OS-library algorithm.
3. **Resume the sustained throughput campaign within Phase 1.** Do not wait
   for every compiler module to adopt strict mode. Prioritize allocation
   elimination, redundant graph/state analysis, and the performance of direct
   generated code. Land coherent batches with bounded kernel checks, then
   full self-builds at integration checkpoints. Strict-copy reporting must
   remain complete; annotating unwanted copies or suppressing bounded stores
   is not a performance improvement.
   Include the local-specialization batches above. Settle the scope of general
   record storage and the value-preservation obligations of elidable lifecycle
   hooks before broad optimizations depend on an assumed answer.
   Start the small cross-language application benchmarks below alongside the
   current optimizer/emitter work. Use supported language features first;
   extend the workloads through Phase 2 and Phase 3 as their prerequisites land.
4. **Close Phase 1 with fresh integration evidence.** Complete the agreed
   matrix and source adoption, then certify the full paired corpus and native
   loop at the same revision. Record remaining conservative boundaries and
   performance measurements explicitly. Maintain one concise current
   capability/certification table with fixture links; historical checkpoint
   prose must not be the only way to discover current support.
5. **Start a focused Phase 2 library customer.** After Phase 1 closure, use a
   small generic/reflection slice to move one real abstraction out of checker
   special cases. Expand from demonstrated contracts and performance, then
   continue closures/error completeness, numerics, reach and ecosystem work.
   Include one invariant-bearing library type with mandatory validation at its
   relevant construction/mutation boundaries and an explicit account of checked
   versus trusted facts; see [idiomatic facts](semantic/idiomatic_facts.md#library-validation-default-2026-09-30).

### Dedicated performance campaign

Resume a sustained optimization effort during the remaining Phase 1 work,
potentially about a week of concentrated work when started. The duration is
an investment, not a guarantee of reaching the target within a week. This
consolidates measured compiler, ownership and generated-code work instead of
making each small edit wait for another expensive bootstrap.

**Current baseline (audited 2026-09-29, source `a202b734`):** an independently
hosted-seeded, direct-built executing compiler took **97.33 s** for a cold
single-generation direct x86-64 self-build, without C acceleration, and used
**4.39 GiB peak process RSS**. The benchmark machine was an i7-6700 at 3.4 GHz
(4 cores / 8 threads); the process and artifact directory were fresh, but OS
page caches were uncontrolled. This is one observation, not a repeated
performance certification. Disjoint root phases requested **57.04 GB** of
storage and reported **1.40 GB** of payload copies. Frontend, validation and
lowering dominated; emission and backend together took about six seconds.
The seed's zero live/peak allocation gauges were invalid because of an imported
scalar-contract bug, since fixed; RSS remains usable. Rebuild the corrected
seed before drawing conclusions from those gauges. Details and artifacts are
in the [audit](AUDIT_2026_09_29.md).

**Historical milestones:** the September 15/16 campaign reached 18.2–18.5 s
using a C-built executing compiler and direct output; later September
checkpoints measured roughly 20 s on that route and 45 s direct. These are
older, different inputs and seeds, not a matched regression comparison or
current target certification. Keep C-built and direct-built executing
compilers in separate rows with seed provenance. The last full paired
certification covered 668 cases at `9df1d08f`; the post-audit manifest has
698 cases and requires a fresh complete run. Focused checks do not replace it.

**Near-term acceptance:** build the Dewy compiler from source into an
executable in **under 30 seconds**, then **under 10 seconds**, on the recorded
benchmark machine. The direct-built executing compiler and no-C output route
must meet the minimum; a C-accelerated result is a separate useful measurement.
These are waypoints toward the Jai-class goal above. Keep dependency-free
hosted Python usable and measured, though it may lag behind the native target.
Time the complete invocation, including parsing/checking, validation, lowering,
emission, µDewy compilation and linking; include C compilation when used.
Measure one generation separately from complete bootstrap verification.

Record cold and warm full builds, with machine, toolchain, target, options,
executing-compiler provenance and fixed-prelude cache state. Warm means another
whole-program compilation, not reuse of user-program analysis or artifacts.
Cached executables and incremental results cannot establish this target.
During the prelude-cache transition, report both prelude-cached and fully
uncached rows. Only the fully uncached row establishes the final fresh-build goal.
Retain expected-result tests, semantic parity, deterministic bootstrap checks
and bounded memory budgets throughout the campaign.

Use the machine's compute and memory throughput to challenge the amount of
work performed: record source/output bytes, node counts, allocation and copy
volume, detachments and repeated visits alongside elapsed time. Distinguish an
idealized bandwidth/cycle budget from achievable compiler time; parsing,
proofs, pointer chasing and startup are not a streaming copy. Prioritize
eliminating categories of waste over local improvements to cheap operations.

The next batches should address:

- **Storage operations remaining after copy elimination.** Remove repeated
  empty-container descriptors, use static immutable literals with correct
  ownership on mutation, and prove inline/frame placement for small
  non-escaping growable containers. Build analysis state directly in its
  destination rather than repeatedly materializing owning snapshots.
- **Repeated analysis and representation work.** Reuse immutable lookup tables
  and revision/mode-bound analysis context, propagate changes through
  dependency worklists, and compact hot state/identity representations where
  measured. Do not memoize mutable proof state without dependency invalidation
  or duplicate the same wasted work across threads.
- **The compiler as a generated program.** Profile native execution, calls,
  spills, retain/release traffic and hot loops. Improve existing code generation
  where it holds back both compiler throughput and ordinary Dewy programs.
  Register allocation already exists; assess its output rather than treating
  its introduction as future work.
- **Remaining stage overhead where justified.** Bytecode/object output and
  checked-prelude caching have landed. While caches remain, preserve input
  identity and cached/uncached agreement and remove or disable executable
  project-relative pickle loading; filename hashes establish freshness, not
  producer trust. Retire persistent caches as fresh-build throughput permits.
  Internal token and assembly representations still
  incur work, but the current downstream six-second cost is not the dominant
  part of a 97-second build. Keep all routes measured and prioritize accordingly.

Use bounded, representative semantic/allocation/scaling kernels for the inner
loop. Run full self-builds, paired comparisons and fixed-point checks at
meaningful integration points and before publication. Do not skip required
checks because they are slow; make setup reusable and scope explicit. Static
copy-site counts are one metric alongside execution time, memory, allocation
volume and work counts, not a proxy for all performance.

### Small cross-language application benchmarks (accepted 2026-10-03)

Start this suite during the current Phase 1 throughput campaign, alongside
the optimizing tier in [`bootstrap/OPTIMIZER.md`](bootstrap/OPTIMIZER.md).
It supplies application evidence in addition to the compiler self-build and
mechanism kernels. Establish a baseline before using it to assess the new
emitters; compare subsequent optimization batches at integration checkpoints.
This is measurement work within the existing campaign, not an additional
Phase 1 closure criterion or a prerequisite that pauses emitter development.

Begin with a few small, deterministic application workloads using currently
supported features: helper-heavy scalar and flat integer-array loops,
dictionary/graph traversal, text scanning or parsing, and loops over arrays
of small records. Give each an independently checked result and runtime inputs
that prevent the entire computation from folding away. Keep setup and output
separate from kernel timing, and measure complete application execution too.
Include small and larger input sizes to expose startup, scaling, working-set
and layout costs. Start with a C or Rust counterpart for each workload; add
the other where it provides useful independent evidence.

Compare the same task and algorithm with matching numerical, text and value
semantics. An exact-rational calculation is not a floating-point baseline,
and grapheme processing is not byte processing. Record required safety/error
behavior, libraries, and any differences in data layout. Distinguish necessary
semantic work from avoidable allocation, copying, indirection and instructions.

Keep ordinary Dewy source as the primary customer. Compare its default and
optimizing compilation paths on the same source where both are available;
record manually tuned Dewy separately. Record each C/Rust toolchain's build
options. Measure fresh compile latency including the prelude, runtime
distributions, peak memory and allocation/copy traffic where available. Retain
source revisions, inputs, hardware, results and required annotations, explicit
views, casts or proof workarounds. Report ordinary-versus-tuned Dewy and
Dewy-versus-C/Rust separately; neither comparison substitutes for the other.

Extend the suite through the Phase 2 library customer to test abstraction and
refactoring costs. Phase 3 adds IEEE arithmetic, shapes, broadcasting, dense
aggregate/optional arrays and the numerical stress-test applications as those
capabilities land; their absence does not block the initial supported workloads.
Use measured application needs to set per-workload budgets, preserving explicit
coverage of weak workloads rather than selecting one language-wide percentage.

### Compile-time throughput as a design constraint

David's September 23 direction, reaffirmed September 29: large programs,
including the compiler, should recompile at scripting-language speed through
whole-program batch compilation. The final comparison is Jai-class compiler
throughput, somewhat slower if necessary for Dewy's semantics, but close.
The final model has no incremental builds, resident compiler requirement or
persistent compiler cache; every invocation builds from source and rechecks the
program and its proofs. The former checked-prelude exception is transitional,
superseded as a long-term policy by David's September 30 clarification.
Within-invocation memoization and identified test-driver reuse are distinct from
retaining user-build analysis between invocations.

The audited native source contains about 56k lines in 137 compiler modules.
A 97-second direct build is far from the goal. Cross-language lines per second
help motivate investigating wasted work, but cannot establish achievable
Dewy time by themselves. Use phase profiles, allocation volume, generated-code
performance and increasing-input scaling tests to choose changes.

The architectural levers are:

1. **Reduce intermediate serialization.** Binary µDewy input and native object
   output landed September 25. Further simplification of internal tokens and
   assembly should follow measured cost, while retaining diagnostic/text paths.
2. **A fast development backend with good output.** Keep direct compilation
   fast without making its output an inefficient interpreter of the source.
   Measure frontend/backend latency and generated-program execution separately.
   Distinguish a C-built executing compiler from one emitting C; an eventual
   optimizing path must not be the only way to get useful runtime performance.
3. **Ownership and lifetime-directed storage.** Borrows, moves, inline/static
   placement and scoped arenas remove different costs. An arena does not prove
   independent mutable values can share storage. Measure working set and
   reclamation as well as time: a module-sized bounds-checker arena already
   increased memory without improving time. Avoid universal arenas.
4. **Dependency-driven work.** Use bounded worklists instead of revisiting
   unrelated declarations or rebuilding graph summaries. The targeted analyses
   can improve now; general compile-time execution joins this model in Phase 2.
5. **Parallel work after ownership/dependencies are explicit.** Available CPU
   parallelism is mostly unused. Independent procedure analysis/code generation
   may eventually help, but first avoid replication of mutable graph state and
   redundant analysis. Parallelism must preserve deterministic output and proof
   boundaries, not mask single-thread inefficiency.
6. **Bounded proof effort.** Limit qualifier generation, propagate dependency
   changes and give expensive searches explicit budgets. Exhaustion means
   unknown or a diagnostic, never an assumed proof. Track bounds/effects/borrow/
   move work and memory as inputs grow; there is no blanket linearity promise
   for the intended proof language.

Those solver and optimizer budgets do not impose mandatory execution limits or
termination proofs on programmer-written general compile-time code. The latter
trusts the programmer and may run indefinitely; cancellation, progress and useful
instantiation diagnostics are tooling goals. Preserve the stricter contracts of
checked proof constructs, where incomplete search must never supply evidence.

**Juxtaposition narrowing (decided against, 2026-09-27):** David keeps
`a(x)^2` (a number `a`) and `(x+1)5^2` as multiplications. Measured ambiguity
was about 2% of a self-build, so the surface stays as decided in 1.4 item 1.
A broad parser rewrite is not the first throughput response.

Allocation and repeated-analysis reductions join generated-code improvements
in the next batch inside Phase 1. Scoped storage follows demonstrated lifetime
boundaries; general evaluation remains Phase 2; parallel checking follows
explicit graph dependencies. Record wall time and allocation volume of the
**disjoint root phases**: frontend, validation, initialization/reachability,
lowering, emission and backend. Prelude and per-module/sub-phase counters
are nested, and must not be summed with their parents; see
[`bootstrap/PERFORMANCE.md`](bootstrap/PERFORMANCE.md).

### Focused audit follow-through (2026-09-30)

The [audit](AUDIT_2026_09_30.md) and [probe record](audits/2026-09-30/README.md)
distinguish new findings from corroboration of existing plans. The observations
are revision-specific and do not certify the current compiler. These tasks fit
the existing correctness, throughput and early-library work; they do not expand
the frozen Phase 1 closure matrix or settle new language syntax.

| Task | Placement and completion evidence |
| --- | --- |
| Preserve known context at generic calls | Early Phase 2 generic-library slice. A type parameter unrelated to an explicitly typed argument must not discard that argument's known context. Cover nested calls and expected results containing `T` under records, optionals and arrays, with deliberate ambiguity diagnostics. |
| Reduce repeated specialization work | Current throughput campaign and generic-library slice. Track body checks, instance-lookup visits, emitted variants and code size separately; reduce checking for distinctions the body does not use. Retain semantic contracts and behavior identities. |
| Contain automatic Boolean type expansion | Current throughput/scaling campaign. Measure normalization clauses and visits independently of numeric-proof budgets. Avoid eagerly materializing exponential DNF for simple queries; exhausted automatic search yields unknown or a complexity diagnostic. |
| Make small helpers cheap | Current development-backend campaign. Investigate used-register saves, leaf frames and register use across calls, with stack/ABI correctness and helper-heavy runtime kernels. Measure output instruction traffic and compile cost. |
| Repair lazy-string metadata capacity | Targeted correctness work. Confirm and remove the inspected `write_boundaries -> none -> count zero` fallback when uint32 offsets cannot represent the input. Establish a capacity contract, wider/chunked representation or explicit failure before caching metadata. |
| Measure deferred text costs | Current runtime campaign, then text-library slice. Record first length/segmentation cost, metadata bytes and backing bytes retained by small slices, alongside copies and allocations. Determine whether explicit preparation/compaction is needed from workloads. |
| Expose semantic feedback and annotation burden | Early Phase 2, alongside the first generic-library customer. Start with batch inspection of types/effects, specialization and failed obligations; use ordinary application/refactoring kernels before committing to the full Phase 5 language server. |

**Inference acceptance:** the recorded hosted matrix has 11 accepted and seven
rejected forms. Both checkers reject an inner common-array call when an otherwise
monomorphic consumer gains only an unrelated generic tag; its array parameter
remains completely known. Propagate independently known parameter constraints
before all generic variables are solved. Also test typed locals, declared returns,
record fields, imported/forwarded generics, helper extraction and nested/wrapped
results. Establish a deterministic local bidirectional policy and explicit
ambiguity boundary, rather than unrestricted whole-program inference. Count
annotations and their placement: moving the same contract through an ordinary
refactoring should not unexpectedly make it unusable. Some forms already work;
retain those positive cases.

**Specialization acceptance:** the two-parameter constant-result kernel causes
9/25/49 hosted body checks and emitted functions for 9/25/49 explicit calls;
native decoded operation groups confirm 9/49 duplicate bodies. This is not
exponential growth relative to source size. Use reusable body requirements and
dependency summaries to distinguish necessary fresh checking from unused
call-site facts. Index native instances per generic instead of scanning unrelated
instances; replace hosted whole-type textual keys with compact retained identities
where valid. A 21-node shared type graph rendered 462,554 bytes in the original
probe. Within-invocation reuse must retain selected operations, effects, defaults,
lifecycle obligations and invariant storage contracts; layout equality alone
does not authorize sharing. These are implementation targets within the already
accepted variant-reuse direction.

**Scaling acceptance:** the bounded normalization kernel expands 14 binary choices
to 16,384 clauses and 229,376 literal entries; accepted source reaches the same
distribution path at smaller sizes even for an uncalled function. Track formula
size/nesting, overload counts, instance counts, effect vocabulary and control-flow
joins as separate axes. Prune or answer cheap subtype/disjointness questions
before distribution; compact Boolean expressions or lazy clause exploration are
candidate implementations. These automatic solver/optimizer limits do not add
mandatory execution budgets to programmer-written compile-time code. Growing
generic expansion remains existing diagnostics/cancellation work.

**Text correctness and cost:** test offset-range boundaries through a bounded
helper/model or controlled failure injection; do not require a multi-gigabyte
allocation in routine tests. This inspected representation-capacity hazard is
distinct from out-of-memory behavior. Preserve grapheme semantics and honest
effects while measuring first-touch scans, metadata allocation and owner retention.
The capacity representation/failure policy remains a design choice, not a claim
that the current code already handles the boundary.

**Decided 2026-10-02 (David):**
- *Bigints are immutable values.* The library already builds every result
  rather than editing an existing value, so `BigInt` is `0 | const [sign
  limbs]`: component writes are refused, and copying a bigint is a bounded
  share under `$explicit_copies`. Direction: when an operation consumes a
  bigint that dies there and produces one with mostly the same parts, reuse
  the dying value's storage (for example a `push` on its limbs) instead of
  allocating a fresh value. This is ownership-driven reuse, never in-place
  mutation of a value someone can still observe.
- *Strings use tiered internal representations* with identical semantics:
  - tiny strings packed in one word;
  - small strings (under about 1 KiB) in frame storage where placement
    allows;
  - larger strings with 32-bit grapheme offsets up to 4 GiB;
  - 64-bit offsets beyond 4 GiB. Offsets beyond 64 bits are moot on current
    machines.

  The 64-bit tier is the repair for the metadata-capacity hazard above: it
  replaces the fallback that caches a grapheme count of zero.

**Temporary caches:** the hosted executable shortcut can choose the same artifact
for different requested targets. Bypass/remove it wherever it obstructs target
checks, certification, dogfooding or measurements; a small guard is sufficient
if current tooling still needs it. Do not build permanent read-set/cache machinery
for this finding. Persistent caches, including the prelude, remain transitional.

### Direct binary fast path (2026-09-24)

**Status (2026-09-25): initial implementation complete.** All seven steps
landed in both compilers. The September 27 follow-up records target/ABI
identity in `UBC2` and rejects incompatible streams; internal token and
assembly representations remain candidates for measured simplification.
Both Dewy compilers write µDewy bytecode, and the native µDewy writes x86-64,
AArch64, RISC-V and wasm32 objects itself by default. The details and
verification are in `PHASE1_PROGRESS.md`.

Accepted direction for lever 1. Two binary cuts around the µDewy backends,
both fast paths beside the text pipeline. Source text, assembly text, and
`cc` stay. The linker stays too: imported artifacts are already object files
and shared libraries.

**Bytecode in, straight to code generation.** µDewy has no intermediate
representation. `p0.parse` is the parser and the code generator: every
expression calls a method on `Backend`, and `finish_module` is what produces
assembly or WAT. `entry_point` already accepts a `generate` callback that
drives a backend without parsing, and nothing uses it. The binary format is
a recording of that call stream, about forty operations, one per method the
parser actually calls. A player decodes an opcode and calls the live
backend. Methods that return an id (`declare_function`, `alloc_local`,
`intern_string`, `cond_and_split`) go through a side table from the recorded
id to whatever that backend just returned, so the backends do not change.
Tokens are the wrong cut (the lexer is the cheap part). Dewy's
`LoweredProgram` is also the wrong cut: it is still Dewy HIR, and µDewy has
no walker for it.

The player does not redo the parser's other work, so the producer must
already have done name resolution, scope and forward-reference checks, const
folding, global-initializer synthesis, and the reachability set. Builtin
constants such as syscall numbers are folded to integers, which makes a blob
per target; that matches `$supported_targets` and `if`-target, which already
split the program before parsing. Link artifacts and imported paths come from
`t0`, not from the parse, so they belong in the blob header. Debug metadata
is more operations in the same stream. Strings and `$include_bytes` go in a
byte pool.

Inside µDewy this is a recorder backend plus a player wired through
`generate`, tested by round-tripping to the same assembly. That only speeds
a program that has already been compiled once. The compile-time win is Dewy
writing the stream instead of µDewy source. That is a second emitter of about
the size of today's text emitter, not a serialization of `LoweredProgram`.

**Code generation straight to object bytes.** Skipping the assembler is
realistic for every backend except C, and the three ELF targets share one
object-file writer (section headers, symbol and string tables, relocations,
weak and hidden symbols, the GNU-stack note, the per-symbol sections
`--gc-sections` already depends on). Each backend already emits a closed
instruction set, so the encoder covers that set only. Local branches resolve
inside the object file. Cross-section symbols and every `extern` become
relocations. `ld` still links.

- **wasm32** is the small one. The WAT from `finish_module` is already a
  structured module, and the binary format is that structure with LEB128
  sizes and opcode bytes. No relocations. This removes `wat2wasm`.
- **AArch64** is the easiest ELF target. Instructions are fixed 32-bit
  words, and there is no DWARF to preserve. Replace the `ldr x0, =imm`
  literal-pool pseudo with `movz`/`movk`. `adrp`, `:lo12:`, and `bl` become
  a handful of relocation kinds.
- **x86-64** is a step harder. Always emitting near jumps avoids the
  short-jump relaxation the assembler does. RIP-relative `leaq` and `call`
  are `R_X86_64_PC32` or `R_X86_64_PLT32`; the PLT form is required for the
  existing shared-library link. `.debug_info` and `.debug_aranges` are
  already spelled as assembler bytes plus label differences.
  `.loc` is not: the assembler builds `.debug_line` from it. Keeping line
  numbers means writing that state machine; codegen without them is
  comparable to AArch64.
- **RISC-V** is hard only because the text is not the instructions. `li`,
  `la`, and `call` are macros, and `la`/`call` also carry linker relaxation.
  `_start` depends on relaxation being off for `la gp, __global_pointer$`.
  The tractable path is to expand the macros and emit the long form with
  `R_RISCV_PCREL_*` and `R_RISCV_CALL` / `R_RISCV_CALL_PLT`, and no
  `R_RISCV_RELAX` anywhere. Linking still works; code gets a little larger.
  Full relaxation is an assembler project and is out of scope.
- **C** has nothing to skip. `cc` compiles, assembles, and links in one
  process. Emitting an object from this backend would mean abandoning C.

The two paths compose. A bytecode blob replayed into an object-emitting
backend avoids external µDewy text and assembler round trips. The current
object writers still parse assembly strings internally; native Dewy
emission still passes through µDewy tokens and a parser port. Either path is useful
alone: bytecode into today's assemblers, or assembly text into a direct
object writer. Dewy emitting bytecode is the step that removes the text
round trip from a cold compile.

**Order and parity (agreed 2026-09-24).** Build each step in the native
µDewy (`udewy/bootstrap`) first, where the self-build spends its time, then
mirror it in the Python µDewy. Hosted/native parity holds as elsewhere: the
Python side lands before a step counts as done. x86-64 comes first among
object writers because it is the host target: ordinary builds already pass
`--no-debug-info`, so an x86-64 writer without DWARF covers them, and
`debug` builds keep the assembler until `.debug_line` exists.

1. Measure how the backend's time splits between µDewy parsing, code
   generation, `as`, and `ld`.
2. The native recorder and player, checked by byte-identical assembly
   against the parse path on every fixture and on the compiler itself.
3. The shared ELF writer with x86-64, without DWARF.
4. Dewy emitting the stream directly.
5. wasm32 and AArch64 on the shared writer.
6. x86-64 `.debug_line`.
7. RISC-V in the long form.

**Build settings belong to the language (David, 2026-09-25).** The knobs
this work added are environment variables for now: `UDEWY_OBJECT=as` (the
native µDewy writes objects directly by default; Python keeps `as`),
`UDEWY_JOBS`, `UDEWY_RECORD`, and `DEWY_EMIT=udewy` (both Dewy compilers
keep µDewy bytecode by default; this keeps the text). Compilation settings should move into the
language instead: small ones as source meta tags in the style of
`$supported_targets` and `if $target =? ...`, and generally a Jai-style
build configuration file written in Dewy that sets the compiler's options,
so the language knows how to compile itself without an external build
system. That needs a design (it builds on comptime) before the variables
are retired.

**Acceptance checks for direct objects.** Byte identity with `as` output
is not a goal. Semantic equality per symbol is.

- Run the existing native suites on the assembler path and the
  direct-object path. Require the same exit codes and the same stdout and
  stderr.
- Link one fixture against an extern `.o` and one against a shared library,
  and run both. This proves `R_X86_64_PLT32` and the other extern
  relocations are real. A plain `call sym` must use `R_X86_64_PLT32`, as
  gas does, even though the backend never writes `@PLT`.
- An undefined external symbol produces the same `ld` error on both paths,
  so the writer never drops or silently resolves a relocation.
- Link with `--gc-sections` and confirm an unreferenced per-symbol section is
  absent from the executable.
- Keep the bootstrap fixed point: generations 2 and 3 byte-identical, both
  built through the direct path. This checks stability only.
- The same input yields byte-identical objects across two runs.
- Compare each object against `as` per symbol, by instruction sequence,
  not by address. For every function, match mnemonic, operands, the branch
  target as the index of the instruction it lands on, and relocation type,
  symbol, and addend. `objdump -dr --no-show-raw-insn` hides encoding
  choices such as `imm8` versus `imm32`.
- Treat these as the same instruction: an x86 rel8 branch and a rel32
  branch to the same label; an AArch64 `ldr =imm` and the `movz`/`movk`
  sequence for that immediate.
- Compare RISC-V after `ld`, or against the long `auipc` form with no
  `R_RISCV_RELAX`. Do not compare to gas's pre-link relaxed dump.
- Compare initialized data bytes, and compare data relocations with symbol
  and addend. Compare BSS by section size and type `NOBITS`, not by bytes.
- Check section flags and alignment with `readelf -S`: text executable,
  data writable, BSS `NOBITS`, and `sh_addralign` matching the assembler's.
- Check the symbol table: `.globl` symbols are global, local labels are
  not, `.L` labels are absent, `__dso_handle` is weak and hidden, `_start`
  is the entry symbol, and symbol types (`STT_FUNC`/`STT_OBJECT`) and sizes
  match.
- Require a `.note.GNU-stack` note, and require that the stack is not
  marked executable.
- One encoder edge-case fixture, compared per symbol against gas: x86
  displacements 0 and ±128, an `rbp`/`r13` base (explicit displacement), an
  `rsp`/`r12` base (SIB byte), immediates at the `imm8` and `imm32` edges,
  `movabs` constants, and REX with the high registers.
- The comparator itself is tested: flipping one byte in a known-good
  object must make the per-symbol check fail.
- For wasm32, compare `wasm-objdump` against `wat2wasm` on types, imports,
  functions, table, elements, data, and exports, and run `wasm-validate`.
- If line numbers stay, compare `.debug_line` as decoded rows
  (`readelf --debug-dump=decodedline`), not bytes, and stop once in a
  debugger on a source line. Behavior tests will not notice its absence.

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
    and linking are about a second. The replacement for that round trip is
    the bytecode-in / object-out fast path recorded above, not a handoff of
    tokens or statements.

## Phase 1: foundations to their intended designs

### Closure and performance work

Phase 1 remains in progress. Freeze a finite closure matrix in
[`PHASE1_PROGRESS.md`](PHASE1_PROGRESS.md), preserving the approved scope:

| Area | Required closure evidence |
| --- | --- |
| Ownership and placement | Supported borrow/move/lifecycle/owner-promotion operations compose correctly across aliases, selectors, calls, imports and joins; conservative unsupported cases are explicit. |
| Shared storage decisions | Copy policy, allocation effects, borrow legality and lowering consume compatible proof decisions for supported shapes. Logical hook effects survive physical elision. |
| Semantic composition and library boundaries | Parsed directives and resolved bindings determine behavior; transformations preserve evaluation/effect order. Small independent numeric and OS-boundary expectations supplement paired agreement. |
| Proof and unsafe boundary | Checked facts survive transfer/invalidation correctly; unsafe audit records actual obligation dependencies, not just candidate checks in an assumption-bearing scope. Budget exhaustion remains unknown. |
| Compiler source and inventory | Strict-source adoption is completed for the agreed compiler scope; hosted/native acceptance and report coverage agree, with bounded stores retained in the inventory. |
| Integration | Independently hosted-seeded native fixed point, complete paired manifest, surrounding tests and performance evidence identify the same source revision. |

Each row needs executable examples and implementation/parity status, not only
a design note. Instrument unknown proof reasons (unsupported fragment,
invalidated identity, missing contract, exhausted budget) and scaling before
adding broader entailment rules. Finishing the full ideal solver, every lifetime
shape or unsettled resource-exhaustion policy is not an implicit exit criterion.
Keep these continuing goals recorded; environment ownership for escaping or
writable captures remains the explicit Phase 2 closure work.

The throughput campaign runs alongside these rows. Allocation and generated-code
improvements should make ordinary value-oriented programs faster as well as the
compiler. A lower static copy count or broader strict-mode adoption alone does
not establish either performance goal.

#### Validation turnaround first (accepted 2026-10-07)

Before the throughput campaign's compiler work, the validation loop itself
gets faster. Every verified slice waited about 1.5 h for the local gate and
about 40 min for verification; the integration certification takes about
3 h (2 h of it the full pytest suite) and GitHub's runners about 2.5 h. Almost
all of that is the hosted Python compiler: driver builds from the compiler's
own sources, the hosted half of the paired manifest, and in-process hosted
compiles whose memory grows through a long-lived xdist worker. In order:

1. **Measure.** One suite run with per-test durations and per-worker memory,
   grouped by file family, names where the time and the late memory growth go.
2. **Native-built test drivers.** Drivers and other compiler-source programs
   the tests run are built by the verified native compiler (seconds) instead
   of the hosted one (minutes), keeping hosted coverage where a test is about
   the hosted compiler itself. This should shorten the gate, certification and
   CI together and remove most of the late memory growth.
3. **Split the gate.** Per slice: focused fast tests plus the paired manifest;
   the full suite before each push and in certification.

Targets are set from the measurement (step 1); the turnaround is tracked in
[`PHASE1_PROGRESS.md`](PHASE1_PROGRESS.md) alongside the throughput figures.

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
   gates the bootstrap inventory at 4,500 static sites and 85 sites/KLOC.
   The corrected inventory at `f899b2b5` measured 4,301 sites and
   80.762/KLOC across 53,255 source lines. The latest fully certified
   `9df1d08f` checkpoint measures 4,220 sites and 75.272/KLOC across 56,063
   inventory lines. This is checkpoint evidence, not coverage certification
   of subsequent source changes.
   Earlier 3,000/60 gates were based on incomplete reporting: retained inline
   record-field snapshots were omitted, including 1,336 two-word Span stores.
   Rebaselining retains all entries, including bounded copies; it changes no
   allocation-counter gate or strict-copy acceptance rule. Concise reporting
   retains every entry while avoiding repeated source rendering. Regressions
   surface in a pull request, not at 25 GB in a self-build.
2. **Mechanisms in order of where the bytes went.** First: read-only
   element and field reads that do not escape their expression or scope
   lower as views, justified by the effect analysis proving the root is not
   mutated during the borrow. This alone removes the arena-lookup case.
   Second: moves at last use for records, strings, and unions (arrays
   already have this). Third: frame placement for small aggregates that
   the same escape facts prove never leave their function. Fourth: scoped
   arenas for the checker's per-branch temporaries. Each step is measured
   against the gates before the next.
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

**Allocation profile (updated 2026-09-29).** The September 28 per-site profile
at `86a86d8a` attributed about 32 GB to 402 million arena allocations, with
2.6 GB peak live storage; see `bootstrap/PERFORMANCE.md`. This is historical
attribution. The fresh audit reports 57.04 GB of disjoint root-phase requests
on a different revision/seed. Refresh per-site counts after recent changes
before claiming which old category still dominates.

`fact_state.join` reservation and completed per-type
`lifecycle_runtime.resource` caching already exist. Narrowed-node borrowing
has also received substantial repairs. Measure their remaining costs instead
of scheduling their initial implementation again. Priorities now are:

- **Empty descriptors and constant arrays.** Empty arrays avoid a data buffer
  but still allocate a private descriptor. Introduce a shared immutable empty
  representation and static constant literals, materializing a private owner
  on mutation. Check places, reserve, nested fields, allocator lifetime and
  cleanup; sharing must never make the static descriptor writable.
- **Small non-escaping scratch lists.** Extend existing bounded scalar frame
  placement to proven growable scratch owners with inline storage and a spill
  path. Parser candidates, child worklists and effect paths are customers.
  Cover the supported lifetime shapes now; do not wait for every lifetime case.
  Caller-local aggregate results can follow through the destination-result
  protocol in `status.md`, with an allocating fallback when placement is unknown.
- **Owning analysis-state construction.** Borrow immutable inputs, build mutable
  results with one owner, and transfer completed state. Compact IDs/entries can
  remove nested ownership trees. COW detachments and repeated snapshots need
  measurement even when reported payload copying is small.
- **Repeated graph discovery.** Share revision/mode-bound route and analysis
  context where semantics match; drive summary updates by dependencies. Keep
  distinct raw-exposure/escape modes and invalidation rules explicit.
- **Scoped storage for large tables.** HIR nodes, tokens and cache bytes are
  candidates at proven lifetime boundaries. Arenas can reduce reclamation;
  they do not remove table construction or growth. Accept them only with
  measured time and working-set improvements.

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
  analysis note. Only copies that cost something count (David, 2026-09-27):
  sharing an immutable string is not a copy, while a string leaving an
  `$allocator` block still is. A backend's own placement copy (hosted
  frame-region strings) is reported by `dewy analyze` but never enforced, so
  acceptance cannot depend on placement. The same exemption applies
  recursively to shared immutable strings in fixed aggregates; mutable
  runtime-length containers keep their independent-storage obligation.
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
  drop hooks still require a complete receiver; copy/move hooks alone do not
  prevent partial field ownership. Last-use component transfers now also
  supply owning bindings, calls and constructors, retaining the wrapper’s lexical
  cleanup. Direct same-block field/ancestor replacement restores partial record ownership,
  preserving cleanup of remaining old components and the new value.
  Whole-owner replacements re-establish ownership across loop backedges;
  every advancing path must provide a fresh value before another consuming use.
  A component can also leave its owner on some paths only (a branch, some
  loop iterations): liveness is kept per field route, a field assignment
  ends only the replaced component's lifetime, and the owner keeps one flag
  per such component that its cleanup and replacements consult.
  Conditional field transfers now include custom moves, arrays and resource
  unions. A custom move cleans its leftover nested resources on the consuming
  edge before marking the field absent; replacements restore that field.
  Proven constant array-element routes now participate in the same branch liveness
  and cleanup flags, including nested arrays, field projections, replacement
  and custom moves. Named constants and checked constant-result selectors use
  the same slot identity as literals; selector effects and dependencies still
  run once on the selected path. Length reads keep the container alive without demanding
  its consumed elements. Possibly overlapping dynamic index routes and remaining resource-container
  mutations still require
  further lifetime analysis. Same-block owning input
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
Their owners must remain stable through the last use of
all dependent aliases. Nonescaping read-only local functions may capture the
owner or the place; capturing a place retains its loan through the enclosing
scope, including dependent aliases and default arguments. The enclosing
function keeps ownership and cleanup; the callee borrows the captured storage.
Writes through captures and escaping function values remain unsupported.
Proven dictionary entries now use the same lifetime demand, including nested
receivers and dependent aliases. Value writes retain ancestor membership,
while mutable entry routes detach shared dictionary/payload storage and
publish replacement handles back to their slots. Other entry writes remain
conservative; raw-exposed owners require further lifetime evidence.

Read-only `$lend(bytes) { ... }` now checks scoped raw access to named byte
arrays in both compilers. It permits address extraction, scalar local work,
raw reads and modeled synchronous writes without permanently pinning the
owner. Address escape, owner mutation and unknown callees remain rejected.
The repeated-read kernel and native three-generation fixed point pass.
Stdout, stderr and file writes now use these loans on x86-64/C, with a
zero-retained-bytes output kernel. Writable `$lend(@bytes reserve=n)` now
checks reservation-bounded `.set_length(n)` commits, and file reads use this
bulk path on x86-64/C. The paired bulk-read kernels and native fixed point
pass; other targets retain their previous I/O route.

Required-view and strict-copy obligations now survive unused-function/import
pruning in both compilers. The native proof graph retains the needed view functions separately
from runtime emission, and both routes reuse their lowering proof and report.
Focused paired checks cover conflicts, derived aliases and writes after last
use. Full integration evidence is tracked in `PHASE1_PROGRESS.md`.

Ownership follow-up (2026-09-28): runtime-selected transfers now preserve
unrelated sibling fields, and disjoint containing arrays can transfer on the
same path. Cleanup propagates independent presence conditions and saved selectors
through nested arrays. Liveness now also retains field suffixes below unknown
indices: `rows[i].left` and `rows[j].right` are disjoint for every selection.
Same-field selections still conflict when their indices may overlap, and selected
slot replacement cannot silently renew an unknown hole. Replacing a statically selected containing array or ancestor after a dynamic
element transfer now cleans only the old remainder and restores the new value
across backedges. Possibly overlapping dynamic routes remain conservative;
this is a remaining lifetime-proof case, not implicit permission to copy a
resource. A component may now transfer through an enclosing drop hook when
its transitive may-access summary proves that hook does not read, mutate,
replace or expose the missing route. Drops still run before ordinary remaining-
field cleanup. Unknown calls and overlapping accesses keep the owner complete.

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
work remains broader than these completed fixtures. The 2026-09-27 convergence
audit found and fixed an unsound eight-transfer cutoff: budget exhaustion now
discards unstable facts rather than treating them as inductive. Both compilers
include condition writes in each while-loop transfer. Delayed-dependency
regressions cover while loops and single/multiple iterators.
Candidate discovery now includes the loop guard as well as its body, under
one deduplicated pair budget. Guard-selected facts still require entry and
backedge evidence; zero-trip, condition-write and candidate-budget cases
are covered in both compilers.
Numeric route facts now also follow named mutable selectors, including
parameters and nested range iterators. A guard on `rows[row].length` can
justify `rows[row][column]`; assignments, place writes and loop advancement
invalidate facts that depend on the changed selector. This is numeric
evidence for the current selection, not persistent source-level type narrowing.

The implemented vocabulary and its inference limits are recorded in
[`semantic/finite_facts.md`](semantic/finite_facts.md). This inventory separates
candidate discovery from proof and keeps the remaining closure work explicit.

The finite fact vocabulary also retains symmetric disequalities between current
scalar/length routes. Equality exclusions survive joins only with evidence on
each path, sharpen an established non-strict order, and invalidate with their
subjects. Dependent disequality contracts now use the same evidence for
parameters, results, predicate arms and checked proof calls; copied scalar
values retain their own facts after the source changes. Bounded linear queries now combine established difference paths with constant
coefficients, checking every intermediate for wrapping. They preserve unknown
for nonlinear, opaque, invalidated or over-budget queries. Bounded linear source syntax now selects difference and weighted-sum candidates,
validated from entry facts and every advancing edge. Weighted rows preserve
uneven counter updates such as `2*i<=j`, scalar snapshots, field routes and
array-length growth. Candidate and derived-row budgets retain unknown on
exhaustion. Broader shared proof coverage, final scaling and the unsafe-audit
consumer provenance remain closure work.

#### Native compiler as a fact-system ergonomics benchmark (2026-10-03)

Use the compiler's own `$runtime_assert` sites as a focused evaluation of
ordinary proof ergonomics. Sample shared arena getters, numeric operations,
and SSA structures; classify each selected check as missing inference,
evidence discarded at an interface, a mutable representation invariant, or
intentional runtime validation. Follow representative cases through callers,
record storage, helper extraction and mutation. A refined getter compiling
locally is not enough: measure the source and annotation effort needed to
establish and preserve its callers' evidence, alongside compilation/runtime
cost. Retain intentional checks and identify which obligations are actually
checked versus trusted. This is a bounded audit, not a new Phase 1 gate or a
requirement to prove every internal compiler invariant before other work.

The [October 3 probe record](audits/2026-10-03/README.md) supplies two concrete
arithmetic acceptance cases: `uint64 and 15` should establish the bound needed
for hexadecimal indexing, and rejecting a nonpositive `bigint` should establish
nonzero for division. Both currently need additional evidence, while the
corresponding remainder bound and word-integer guard pass. Straightforward
inference fixes and inexpensive contract improvements can proceed alongside
current compiler work, with parity checks in both implementations. Persistent
evidence for stored arena IDs, correlated mutable arrays and validated compiler
stages belongs with the broader mutation-aware proof-engine work. The record
distinguishes observed checker gaps from representation/design questions;
[`semantic/idiomatic_facts.md`](semantic/idiomatic_facts.md) retains the durable
requirements rather than accumulating transient failures.

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
route suffixes without strengthening their scope. Generic row parameters carry nonlocal effects; place permissions stay
explicit in callback and wrapper signatures. This Phase 1 boundary was
approved on 2026-09-27. Rows carrying/remapping callback-local places await
a separate design review. Bare
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
   (y)3.14159    # call if `y` is callable, multiply if `y` is a number
   (f)2          # call if `f` is callable, multiply if `f` is a number
   g(1)2         # by the type of `g`: a number makes both multiplications;
                 # a callable makes `g(1)` a call, and then its result's
                 # type decides whether `2` is called with or multiplied
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
   is the uniform name for removing. There are no compatibility aliases:
   `s.add(x)` is an error that points to `push` (removed 2026-09-26, with
   every source use rewritten). Uniform names may take
   container-specific parameters, but the name and the broad signature are
   the same everywhere. `length` is the uniform accessor for both length
   and shape: on a multidimensional array `myarr.length` returns an array
   of dimensions. There is no `size` or `shape`.

9. **Equality of arrays and records (decided 2026-09-27).** `=?` is
   always a value comparison: element-wise for arrays (a different length
   is unequal, including a different static length) and field-wise for
   records, recursively; never a comparison of handles. Implemented in both
   compilers with one generated helper per compared layout. Dictionary and
   set equality stay open.

Not decisions: the precedence adjustments once listed as open in the
reference's design-status appendix (word `not` below comparisons,
one-direction comparison chains, postfix `or_throw` below `as`, prefix
`type of`) landed on 2026-08-31; see `semantic/precedence.md` and the
2026-08-31 entry in `status.md`. Multidimensional shape syntax is a real
design but belongs to Phase 3.

## Phase 2: expressiveness on top of the foundations

**First customer after Phase 1 closure:** a narrow generic/reflection/library
slice that removes one real checker special case. Named generic functions
already instantiate; explicit generic function arguments and user generic
object/container types remain incomplete. Choose one useful abstraction,
establish its ordinary contracts in both compilers, and measure its default
runtime performance before migrating whole container families. Reusable
primitives should let library code be as efficient as a compiler builtin;
the checker must not recognize a library name to make it work. This is the
first slice below, not a requirement to finish all reflection ahead of closures.

- **Parameterized types**, explicit type arguments, monomorphization. This
  unlocks the stated long-term goal of moving arrays, dictionaries, sets, and
  strings out of the compiler into Dewy libraries, which shrinks the
  compiler and makes the ownership model testable in library code.
- **Inference and semantic inspection, alongside the first library slice:**
  implement the [focused inference gates](#focused-audit-follow-through-2026-09-30)
  and expose source-linked batch diagnostics, inferred types/effects and
  explanations for specialization, missing proofs and borrow/copy decisions.
  Start with small checker/query interfaces and incomplete-input recovery;
  this does not require an incremental compiler or resident process. Repeated
  customers should include a text/file utility, validated data transform,
  record-array update loop and generic helper library. Count explicit types,
  casts, repeated guards, copies and unsafe assumptions before and after normal
  API composition. This is an early usability milestone; full editor/package
  integration remains Phase 5.
- **Closures as environment records**, using the ownership model for
  captures (today: lambda-lifted non-escaping local functions only).
- **Compile-time evaluation, first slice:** the reflection primitives in
  `semantic/argparse_and_reflection.md` (`fields`, `members`, `$field`,
  unrolled literals). Then general compile-time execution that trusts the
  programmer; no mandatory termination proof or user-code execution budget is
  selected. Effect/capability and reproducibility contracts still need design,
  and checked proof constructs retain their own soundness requirements.
  This replaces pressure for compiler builtins; library features remain built on
  reusable primitives, never
  on the checker recognizing a library call. Compile-time execution is not
  itself a throughput optimization: reducing special cases may simplify the
  compiler, while evaluation adds work to measure and make diagnosable/cancellable.
- **Library-defined validation:** make one invariant-bearing type a complete
  customer. Validate known values at compile time; for runtime values use checked
  construction/preservation, an explicit fallible validator or the documented
  trusted boundary. Success may carry predicate facts; further consequences need
  checked implications or a narrow documented trusted library contract.
  Prefer eventual language/type-system
  guarantees, but do not require a general proof framework before this first
  slice. Cover constructor, conversion, mutation, copy and supported reflection
  routes. The exact trust mechanism is provisional and should be reevaluated
  from use, as recorded in [idiomatic facts](semantic/idiomatic_facts.md#library-validation-default-2026-09-30).
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

Pull its small independent integer/Fraction and fixed-point boundary checks into
the current correctness gates; they do not depend on the larger Phase 3 workload.
The audit's representable fixed-point minimum divided by itself must yield one.
Canonical numeric representations and explicit rounding boundaries need expected
answers independent of the shared Dewy libraries.

Runtime performance is part of this phase's acceptance, rather than a later
optimization pass. Start with contiguous CPU arrays and ordinary numeric
loops, then measure compatible fused operations, vectorization, broadcasting
and linear algebra. Preserve facts and effect order while avoiding temporary
arrays, unnecessary bounds work and per-element allocation. Keep default and
optimized Dewy comparisons plus equivalent CPU baselines for representative
sizes; small arrays and large streaming workloads need different cost choices.
Specify dense aggregate and optional-element layouts alongside scalar arrays,
including the boundary to heterogeneous/polymorphic storage. Use particle,
complex-number and optional-number workloads to check stride, indirection,
allocation, borrowing stability and eventual foreign/device buffer compatibility.

**GPU array execution and CPU/GPU interop:** compatible array computations
should have a GPU execution path that preserves the intended problem model
without requiring a wholesale rewrite. Develop this after the CPU array and
shape contracts are usable, with Phase 4 platform/FFI support as needed:

- Identify eligible array operations and composed kernels; measure fusion,
  launch overhead and the size at which GPU execution helps. Keep an efficient
  CPU path for small or incompatible work.
- Establish buffer layout, residency and lifetime contracts so data can stay
  on the GPU across operations. Support applications that alternate CPU and
  GPU work without repeated full-buffer copies or hidden synchronization.
- Measure total application latency/throughput, transfers, temporary storage
  and synchronization, not only kernel time. Use numeric workloads and a
  game-like CPU update/GPU workload as concrete customers.
- Review device selection, synchronization/effects, capacity/failure behavior,
  and floating-point/reduction ordering before committing their semantics.
  Preserve observable effects and explicit numeric policies across execution
  paths; compatible shape alone is not proof an operation can move to a GPU.

This records an execution direction, not new GPU syntax or a decision that
all arrays automatically move between devices. Start with a small end-to-end
CPU/GPU example on a recorded device before generalizing APIs or backends.

## Phase 4: reach

- A stable foreign-function interface; target triples with structured
  `$target` gating (`status.md`, "Proper compilation target list"); full
  prelude on wasm32; at least one non-Linux host.
- CPU/GPU platform and graphics interop supporting Phase 3's array execution:
  device buffers and host APIs must use coherent resource identity, lifetime
  and effect contracts. Evaluate integration with game-like workloads. Share
  the language's storage rules rather than creating an unchecked parallel
  ownership system. This can proceed as a focused dependency of Phase 3;
  it need not wait for unrelated portability or general concurrency work.
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

The narrow batch semantic-feedback path and ordinary-program ergonomics gates
start in early Phase 2 as recorded above; they should inform these later tools.

Small library examples and performance workloads belong alongside the earlier
phases now; a complete game engine or ecosystem is not required to test runtime
quality. Carry those examples into documentation as their contracts stabilize.

## Deprioritized

- Additional general-purpose µDewy backends without a measured workload need,
  the browser playground, and the hypothetical
  ndewy rung (a TBD section in `../udewy/trusted_computing_concept.md`; no
  code exists). Finished enough, or not started, and correctly so for now.
  The planned GPU array execution path is a Phase 3 goal, not part of this
  general backend deferral.
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
- Keep general reflection/evaluation in Phase 2, after its Phase 1 proof/effect
  prerequisites. Its first focused library customer may reduce compiler
  special cases; that does not make broad reflection an immediate performance
  prerequisite.
- Improve compile latency and generated-program performance together without
  conflating their budgets. Jai-class compilation and near-systems-language
  runtime are final goals; the 30/10-second self-build milestones and the small
  cross-language application suite's per-workload measurements provide nearer evidence.
- CPU/GPU placement, synchronization and numeric policies remain design work.
  The direction is approved; fundamentally new semantics still need review.
