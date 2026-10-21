# Milestone 24: ownership, scoped storage and cleanup

Accepted design, 2026-10-20. Slices 1–3 are implemented; arena slices 4–5 wait on open question 4.

## Authority and starting point

The approved hook protocol and scoped byte loans are requirements. Ordinary
arrays/strings retain COW; placement preference is static sizing, then arenas,
then heap. Archived storage descriptions predating GOALS cannot replace that
default. Arena scope results must survive reset; move inference is already
specified. REPORT questions 3–6 remain separate: prototype scope belongs to
refinement policy; general payload places, allocation refusal and explicit moves
stay open. Represent those choices internally without adding surface syntax.

Observed by source inspection, not execution: `lower.jo` has `copy_ref`, recursive
`helper_drop`, `emit_scope_exit`, `BuildItem` partial cleanup and environment
copy/drop helpers. Ordinary copies currently retain COW buffers; callable-bearing
arrays already take a special eager path. Existing helper field/fixed-array loops
run forward, so reverse resource cleanup needs deliberate changes. `copies.jo`
runs only under `$explicit_copies`; its last-use proof conservatively blocks
parameters, captures, exposure, loops and defers. It is reusable evidence, not a
complete resource lifetime checker. `rt.jo` combines per-thread bump allocation,
size-class reuse and large blocks; array/string payload headers are rc/length/cap.
`__panic` ultimately exits or performs REPL/watch handling without lexical unwind.

Inherited ladder observations: 14/15 fail before lifecycle semantics, 16/17 at
unsupported `$lend`; 13's passing projection removes allocator behavior. No new
throughput/runtime measurements were taken.

## Shared representation and lifecycle protocol

Cache `LifecycleInfo` per concrete TypeId: hook instance IDs, needs-cleanup,
copyable, relocation strategy and component plans. Keep nominal hook identities
outside structural field equality; recursive properties settle monotonically,
without expanding recursive layouts. Validate one compiler-only zero-argument
member per role, borrowed receiver, readonly copy receiver, same-nominal copy/move
result and void drop. Preserve the archived inherited-parent composition: parent
hook once, added fields normally, complete child identity and contracts checked.
An overriding role replaces that role, not recursive field cleanup.

Use milestone 22/23's `PointId`, alias-normalized `PlaceId`, captured `ValueId`,
`FnSummary` and cost inventory. Add sparse `OwnerId`, initialization state and
residency to the per-instance plan, never type identity. Ownership states are
uninitialized, live, consumed and path-dependent; partial aggregates carry live
field bits, arrays an initialized prefix, unions their active tag. Runtime bits
exist only where control flow prevents static resolution. Zero bytes alone are
not an initialization proof: a valid resource may contain zeros.

Every owning boundary selects `Borrow`, `CopyInit`, `MoveInit` or fresh-result
adoption. Borrow requires a checked nonescaping read/stability proof. Copy calls
the hook, otherwise recursively copies components; drop-only nominal types are
move-only even with plain fields. Move calls its hook or synthesizes ownership
transfer. Hook results initialize fresh storage directly, avoiding self-recursion.
A declared copy hook owns its result construction; absent one, copyability is
structural through fields, arrays, alternatives and captures. Generics instantiate
this property once per concrete instance; an unsupported copy diagnoses the
instantiation and template use, without a new trait spelling.

Move success consumes the receiver, skips its outer drop and cleans remaining
fields. Initially require a proved no-failure summary for custom move hooks:
blindly skipping the outer drop after a failing hook can leak an opaque scalar
resource; running it can double-release a partially transferred one. Failing
custom moves remain an explicit unsupported implementation shape pending a checked
consuming-failure protocol, not a new approved language rule. Ordinary partial
field transfers remain conservative where an outer drop could read the missing
field; move-hook receivers have their own checked field states. The archived abstract-value-preservation
question remains unresolved: do not assume arbitrary hooks are identity functions
for facts, CSE or relocation. Apply verified result contracts only; keep mechanical
buffer relocation distinct from semantic moves. This reports an existing question,
not a proposed new surface rule.

## Cleanup and inferred moves

Compile one cleanup plan used by `emit_scope_exit`, temporary cleanup, partial
construction and panic unwinding. Preserve defer-before-local ordering, reverse
local/field/array order, hook-before-remaining-fields and active-alternative-only
cleanup. A failed constructor drops initialized children, never the incomplete
outer value's hook. Advance an array's initialized prefix only after element
construction succeeds; `__arr_filled` must not publish a final length prematurely.
Replace by evaluating and owning the replacement first,
then dropping the old destination, then publishing the new owner. Self-assignment
and aliasing RHS use captured values, not re-read storage.

Save return/forwarded values before cleanup; keep pending results registered until
successful handoff. Break/continue clean precisely crossed scopes, including
labeled exits. Drop hooks cannot forward errors, panic or terminate: verify their
transitive summaries and residual failure costs, rejecting unknowns. Observable
I/O/mutation is allowed and participates in fact invalidation. Copy hooks may
fail and use ordinary partial cleanup; move hooks use the restriction above. Potential hook effects remain checked even
when an optional invocation is elided; actual owners still clean up exactly once.

For panic across calls, add a per-thread intrusive chain only for frames with
cleanup obligations. Each stack record points to live slots/state and a generated
cleanup dispatcher. Before any possibly panicking operation publish the exact
initialization state. Remove/advance each action before executing it; interrupted
defers must not repeat. `__panic` drains the chain before existing termination,
REPL or watch transfer; normal exits unlink it. Reviewed termination/OOM paths
must also dispatch cleanup under the selected internal failure policy. A pending caller-owned result has
one cleanup authority until handoff, including sret. Unexpected failure inside a
verified drop is an invariant violation, not a second unwind. No heap allocation
is needed to register/unwind. Foreign faults, process kill and unmodelled foreign
longjmp are outside compiler-controlled panic; do not claim those are covered.

Extract `copies.jo`'s move evidence from its source-policy gate. Demand ownership
checking whenever resources occur, even without `$explicit_copies`; retain that
directive's independent costly-copy policy. Compute backwards liveness over
structured edges with forward initialization joins. Include aliases, whole-root
reads, default/hook/defer uses, argument evaluation order and cleanup reads.
A backedge needs the next iteration's owner; a break edge may consume it. Mutually
exclusive branches may each transfer; joined cleanup uses executed-path bits.
Budget exhaustion retains a copy for copyable values and rejects an unproved
move-only transfer. Cap exploratory alias/branch work at 4,096 edges per owner;
widen excess residency sets to unknown. No heuristic may manufacture ownership. Internal
`TransferIntent=Infer/Require` supports future explicit moves; expose only Infer.

Ordinary data retains existing COW. Resource-bearing records use semantic
component initialization, not memcpy-plus-retain. For arrays containing hooks,
start with eager independent element copies; arrays of move-only elements are
move-only, but can be iterated by readonly loans. This deliberately uses the
existing callable-array eager seam; it does not remove ordinary COW. Buffer growth
and sorting can mechanically relocate complete owners without invoking semantic
move hooks, provided no live loan exists. Pop transfers; clear/truncate/replacement
drop removed owners; dictionaries visit live entries only. Shared plain-data
buffers release elements only on their last reference.

Closure capture is another boundary: snapshot capture copies or last-use moves;
copying an environment recursively copies captures. A move-only capture makes
that closure move-only, so immutable-environment retain shortcuts cannot silently
permit duplication. Retain an internal copyability capability in the shared
contract-bearing callable qualifier, including conversions and generic/container
substitution; an erased callable boundary cannot forget it and enable copies.
Explicit shared captures remain borrowed places and cannot
escape their owners. Unknown callback behavior is top; it cannot justify a borrow,
a consumed capture, or stable storage.

## Scoped raw loans

Implement the approved byte-array subset, not general returned payload places.
`LoanId` identifies owner, mode, entry length, reservation and storage epoch.
Resolve aliases to the owner; require stable named storage and no conflicting
live view. Evaluate writable reservation once; prove nonnegative and checked
entry-length addition. Detach snapshots and reserve **additional** bytes before
obtaining any address. Keep the owner alive through every body exit.

Within the block allow the specified raw byte operations, scalar work and length
reads. The only owner mutation is `x.set_length(n)` on the active writable owner.
Reject growth, replacement, independent owner reads/copies, new aliases, nested
conflicting loans, owner moves/drops/reset, or calls whose transitive footprints
could do those things. Readonly loans reject raw writes. Existing synchronous
read/write intrinsics receive narrowly reviewed no-retain contracts by resolved
identity; a raw numeric argument to an arbitrary function is not automatically
safe. Initially reject other address-taking calls rather than trusting annotations.

Propagate address origins through assignments, arithmetic, casts, aggregates,
control joins and backedges. Derived integers retain taint, including narrowing
and encoding. Comparisons retain origins, as do assignments/results controlled
by address-derived conditions, preventing reconstruction one bit at a time. Reject tainted results,
outer/global stores, captures, aggregate publication, raw stores of addresses and
unmodelled calls. Iterate origin unions to convergence; cap sets at eight loans
then widen to any-active-loan, which remains nonescapable. Unsupported transforms
fail closed. A body producing a raw byte load or syscall count can return that
scalar; returning the address cannot. This conservative analysis prevents laundering
through loops or closures without introducing lifetime-bearing types.

Each `set_length` must statically prove `0 <= n <= entry_length + reservation`,
not merely fit whatever extra capacity geometric growth happened to obtain.
Reuse milestone 22 obligations/overflow rules, including its difference/affine
facts for read counts; no implicit commit check. Commit changes length facts but
not storage epoch; raw writes invalidate element facts. Reservation cannot prove
that every committed byte was initialized: the approved raw subset retains that
low-level obligation. Empty loans must handle null data without dereferencing it.
Unscoped exposure keeps its existing pinning behavior.

## Arena placement, escape and runtime

Give each reset interval `RegionId=(arena identity,generation)`; residency follows
owned storage recursively through values, COW buffers and environments. `$allocator`
borrows the arena exclusively for the expression: neither reset, copying its
control handle nor reentrant use through aliases/callbacks is allowed. Separate
arenas may nest; nesting the same active arena is rejected. Exiting the expression
ends the borrow, not the arena's reset interval.

At every outward boundary—result, return, outer assignment, place write,
container store or retained callback—plan `Promote(value,destination region)`
before publication. Nested scope results promote into the enclosing allocator;
outer results promote into their destination. Recursively rebuild arena-backed
buffers/strings/records and closure captures there, retaining only components
already proven longer-lived. Promotion cannot be an rc increment, nor may last-use
movement carry resettable bytes outward. Destination plans determine allocation
for outer-place writes even during an inner allocator scope. Subsequent COW
writes allocate under the destination's lifetime contract.

A custom hook retaining an opaque arena pointer cannot certify promotion merely
by returning the same nominal type. Require verified storage provenance from its
body; unknown opaque handles are allocated in an enclosing safe region, reported
as fallback, or rejected when a required escape cannot be proved safe. Copyable
structural values promote; noncopyable arena-dependent owners reject unless a
checked move constructs destination-independent storage. Heap-owned external
handles can transfer unchanged. Unknown callbacks receive promoted owning
snapshots; borrowed inner captures cannot be retained. A call without a checked
escape/allocator summary uses enclosing placement, never guessed arena allocation.

Copies leaving an allocator scope enter the shared copy inventory, including
immutable strings, and obey `$explicit_copies`. Reusing truly static bytes is free;
sharing resettable bytes is not. Retained COW snapshots stay within their source
region or each receives safe promotion. Reset is legal only with no active loans,
arena borrows or surviving region-dependent owners. Usually lexical cleanup and
promotion discharge this; unsupported ambient/shared escape rejects. Unknown
residency widens conservatively, never to heap-safe.

In `rt.jo`, keep payload rc/length/cap layouts. Add an arena control block with
chunk chain, cursor/end, generation, live-block and active-borrow counts. Arena chunks use the
existing heap/page allocator; arena allocations bump within them. Reuse the two
allocation-prefix words as rounded size plus tagged arena-control pointer; heap
small/large markers remain distinct, and allocation-size queries retain their answer. Update free/size/grow and small-box header
reuse to dispatch correctly: arena logical frees do not enter heap free lists,
but last-owner element/hook cleanup still executes. Reset requires zero live
region obligations, resets/releases chunks and increments generation; it never
substitutes for destructors. Debug builds poison reset storage/check generations.

Pass an internal allocator-context operand through demanded direct helpers and
allocator-aware callable adapters; ordinary call ABIs/heap helpers stay unchanged.
Unmodelled indirect calls use enclosing-placement fallback. A closure does not
implicitly capture a temporary allocator context for later invocation. Cleanup
records restore any active scope state on panic. Keep allocation failure behind
`FailurePolicy=Unsettled/Return/Terminate`; unsettled costs cannot certify no-panic
or recovery. Current fatal OOM is an observation, not approval of the final policy.
General returned-place support is similarly an internal disabled capability.

## Witnesses and compile cost

Record bounded predecessor witnesses, not copied execution histories. For 15,
point to `duplicate=owner`, the missing copy hook, and `consume(owner)` keeping
another owner live; `.copy()` cannot repair a move-only type. For use-after-move,
show the consuming edge and later read/backedge. For 17, trace address extraction
to block result. Stability failures name the conflicting call/alias and summary
edge. Commit errors show proposed length, entry length, reservation and missing
bound; promotion errors show capture/store path and reset generation. Distinguish
possible conflict, proved violation, opaque summary and analysis-budget exhaustion.
No unsupported-syntax error satisfies the ladder's marked negatives.

**Inherited measurements:** refinement's earlier HEAD used 1,339,685,858 user
instructions on 22,005 synthetic root lines plus 37,268 implementation lines;
effects reports separate earlier samples. None measures this proposal. ROADMAP
records 1,322 M to 400 M, approximately 3.4× reduction; new work must preserve that
trajectory.

**Judgment:** target dormant ownership overhead 0.5–2 M instructions (0.04–0.15%
of 1.34 G, 0.13–0.5% of 400 M). Set demand/type bits during existing checking;
allocate no owner/loan/region maps for ordinary resource-free functions. Cache
component plans and reuse COW cleanup; add no independent universal AST scan.
Active pilot budget: 20k ownership events × 300–600 instructions plus 2k promotion/
loan queries × 1–3k, roughly 8–18 M before shared facts/effects costs. These are
engineering budgets, not benchmark predictions; panic-frame registration also
needs runtime measurement. Reuse existing liveness where valid, replacing walks
rather than accumulating them.

Gate all three designs cumulatively at ≤1% dormant growth against one fixed,
fresh matching baseline, not 1% per slice/design. Use seven alternating
single-worker samples after warmup, unmultiplexed counters, identical sources and
default/release modes; kernels stay within +3% instructions. Separately measure
hook-heavy containers, callbacks, nesting and saturated analysis. Ownership
uncertainty must reject or retain work, never turn into a cheap unsound proof.

## Six delivery slices and cross-design order

1. **Scalar owner pilot (judged 1–2 weeks).** Own new `ownership.jo`, nominal-hook
metadata/parser/checker seams, `copies.jo` proof extraction, `lower.jo` cleanup
adapter, minimal panic-chain runtime and dedicated tests. Support drop-only scalar
nominal records, fresh construction, whole-local inferred moves, direct owning
parameters/returns, branches and loop exits; no resource containers, custom copy/
move bodies, loans or arenas yet. Parameter ownership must be explicit in the
internal call plan, independent of source-copy policy. Validate hook declarations,
register owners after initialization, consume source bits on transfer, and check
hook failure summaries before emission. Replace `scope_add_local`'s blanket
parameter exclusion with the plan's incoming-owner versus borrow distinction. First acceptance is **full 14** (`72 61`)
and marked semantic rejection of **15**, including checking unreachable bad bodies.
Soundness tests distinguish zero-valued live owners, branch-only transfers,
continue-versus-break, later reads/internal forced-consume checks, defer/alias
blockers, reassignment, unused
results, nested-callee panic and partial construction. Panic goldens observe drop
output/order before exit 101; every actual owner drops once. Unknown hook calls
reject rather than bypass no-failure validation. No general effect-row parser is
required: reuse the shared summary engine's conservative subset. Stop/review above
the cost gate; this slice alone does not complete 24.

2. **Hook composition and aggregates (2–3 weeks).** Own lifecycle planners,
checked hook-call insertion and container/environment helpers. Ship copy/move,
inheritance, recursive/optional owners, resource arrays/dictionaries and closure
copyability. Test nested reverse cleanup, injected failure at every construction
prefix, moved fields, hook effects invalidating facts, closure double drop,
move-only generic instantiation and borrowed iteration. Cover eager copies versus
ordinary COW snapshots, pop/clear/replace and mechanical growth relocation.

3. **Scoped bytes (1–2 weeks).** Own loan checking, intrinsic contracts and
capacity obligations. Ship full 16 (`1680 39`) and semantic 17 rejection. Test
address escape via casts, loops, aggregate/closure/global/raw stores and unknown
calls; hidden alias resize/reset, negative/overflowing reservation, excessive
commit and retained snapshots. Compare default/release and supported backends.

4. **Allocator runtime and bounded placement (1–2 weeks).** Own arena control/
prefix dispatch, allocator-aware helper variants and placement reports. Ship
non-escaping scoped allocations and reset reuse, preserving existing heap paths.
Test alignment, size-class/large blocks, boxes, growth, zero sizes, repeated reset,
destructors before reset and panic within nested allocator scopes. Inject failure
internally under each policy without claiming a public refusal API.

5. **Escape promotion (2–3 weeks).** Own recursive residency/promotion and
callback/environment escape plans. Ship full 13 (`5440 30 16`). Test nested arenas,
shared snapshots, outer-place stores, returned closures, callbacks retaining
snapshots, rejected shared inner captures, opaque handle fallback and move-only
arena-dependent rejection. Poison/reset immediately before exercising escaped
values; neither ordinary output alone nor heap fallback alone proves placement.

6. **Integration and budgets (3–5 days).** Own dedicated witness goldens and
ladder integration. Complete 13–17 together, strict cost/cleanup tests and
check/build equivalence. Focused plus quick tests per compiler commit; full suite,
independent bootstrap and fixed point per batch. Test panic cleanup on every
supported backend and explicit blockers on unsupported ownership paths.

Build order across designs: extract shared places/evaluation capture with
refinement slice 1 and effects slice 1; settle direct summary publication before
ownership slice 1's drop verification. Effects slices 2–3 supply callback/alias
precision; refinement slices 3–4 supply length/affine commit proofs for ownership
slice 3. Ownership slices 1–2 register lifecycle edges in effects slice 4's cost
inventory, which must close before strict certification (effects slice 5).
Ownership slice 4 can follow slice 2 independently of loans; slice 5 needs both
region planning and settled escape summaries. Share post-cleanup result checking
with refinement slice 2. No design waits for a wholesale inference/layout rewrite.

HEAD advanced externally to `82263830`; inspected ownership machinery is unchanged.
Its new benchmark instruction gate can implement the budget checks.

Sources: current GOALS, ROADMAP, user-managed-storage/value-semantics notes;
archived `values.md`, `objects.md`, `arrays-and-containers.md` and approved
`dewy/PHASE1_DESIGN_PROPOSALS.md` protocol; ladder REPORT questions 3–6 and 13–17;
prior refinement/effects designs; current lower/copies/check/expr/types and rt.

