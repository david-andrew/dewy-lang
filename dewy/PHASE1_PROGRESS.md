# Phase 1 implementation checkpoints

Started 2026-09-20 from `be7d1b1a`. The scope is all of Phase 1 in
[ROADMAP.md](ROADMAP.md), with the correctness/parity closure checkpoint
first. This ledger records implementation and validation, not new language
decisions. Fundamental new directions still need review; obvious Dewy-aligned
extensions may proceed provisionally and are recorded here for David.

## Latest native/parity repair integration (2026-09-29)

**613/613** paired acceptance/execution cases pass against frozen source
`748129bb`. An independent hosted seed rebuilt the repaired native sources to
a byte-identical three-generation fixed point, including x86-64/C execution
and scaling checks. The complete inventory reports **4,250 sites / 55,823 lines
= 76.133/KLOC**, within the unchanged 4,500/85 gates. Generations 2/3 took
59/68 seconds under concurrent validation, not isolated performance timings.
Artifacts use `phase1-owner-closure-*` outside the checkout. The preceding
541-case `2850bc9a` checkpoint measured 4,278 sites / 55,629 lines. Subsequent
numeric/query changes have focused evidence below.

The non-slow pytest run against the preceding frozen repair source finished
with **6,092 passes, 4 failures and 13 skips** (95m49s). One failure is the
contextual-literal follow-up fixed in `2850bc9a`; three measurement tests require
Git metadata absent from the archive used for that run. All four pass focused
rechecks in the current Git checkout (`dewy-full-suite-final-rechecks.log`).
This accounts for every observed failure, but is not a claim that later source
changes have received a fresh green full-suite run. The previous `5d6a1baa`
run had 6,039 passes, 20 failures and 13 skips. The refreshed hosted strict-copy
inventory has 1,587 implicit runtime-sized bootstrap sites across 69 modules,
before the latest conversion/iterator work. Phase 1 remains open.

## Comparison worklists and explicit snapshot ownership (2026-09-29)

Comparison transfer records only matching sequence ids before inserting index
facts, avoiding a snapshot of every fact and bigint endpoint. It computes the
scalar index decision before transferring the order gap and constructs only
the selected narrowed interval. Branch states explicitly copy their incoming
state. Rewritten function contracts explicitly retain their promises and the
member-id worklist that survives type-arena updates.

Hosted record ownership now uses the same fresh-result classification as
record initialization. Explicit `.copy()` results, dictionary views and set
operations were initialized as owners but omitted from move discovery; the
shared classification removes that discrepancy. A copied owner can transfer
its fields or enter an optional result after its last use, while a still-live
snapshot remains independent.

Seventeen comparison/transfer checks and twenty-nine return/disequality contract
checks pass. The copied-record native group also passes on x86-64/C, including
repeated live-byte recovery and rejection of a still-live source. Comparison
and function-contract modules pass strict checking on both routes: 74 physical
modules certified. Five fixtures bring the manifest to 625. Logs use
`dewy-proof-query-*`, `dewy-comparison-*`, `dewy-function-contracts-*` and
`dewy-scoped-query-native-tests.log`. The ongoing frozen 613-case integration
predates these changes.

## Numeric queries and tagged replacement transfers (2026-09-29)

Index checking now compares borrowed length endpoints directly instead of
building optional interval/bigint snapshots. Exact result endpoints still copy
explicitly because the result retains them. Range normalization avoids an
absolute-step snapshot and transfers its computed count after the final read;
its mutable first endpoint explicitly owns a copy. Numeric HIR construction
reads alias identities without copying their aggregate alternatives, uses a
machine-word sign, and explicitly retains mathematical payloads.

This exposed a hosted last-use gap: tagged-cell assignment did not participate
in transfer discovery even though initialization and native assignment did.
Replacement now uses the existing ownership/layout checks. Seven hosted cases
cover same/widened unions, conditional transfers, record and bigint payloads,
live-source rejection and cleanup. Three paired x86-64/C groups pass, including
the surrounding field and injection tests (76.70 seconds). Fifty-four numeric,
index and range checks pass, plus an exact-normalization kernel spanning 192
combinations of large signed endpoints, step directions and open/closed bounds.

All three modules pass strict checking on both routes, reaching 72 physical
bootstrap modules. Seven fixtures bring the manifest to 620. Logs use
`dewy-numeric-query-*`, `dewy-union-replacement-*` and
`dewy-integer-range-normalization.log`. These changes postdate the ongoing
613-case frozen integration.

## Lasting ownership for global replacements (2026-09-29)

Hosted ordinary array/record assignment now uses the existing lasting-storage
replacement path for module owners, instead of blanket rejection. Global arrays
release their prior descriptor after RHS evaluation, including repeated module
initialization. Native globals now release previous owned values too: globals
were absent from lexical cleanup frames, so repeated replacement leaked them.
The native module-initialization path participates without pretending that a
global has function-local cleanup. Exposed storage retains its conservative
lifetime boundary; resource-bearing hosted global replacements remain outside
this slice.

Eight hosted cases pass, plus fifteen surrounding ownership checks and the
fresh paired native group on x86-64/C. Kernels cover records, arrays, fixed and
nested extents, retained snapshots, self-copy replacement, module startup,
dynamic strings and repeated live-byte recovery. The initial native probe
returned the leak failure (3); the repaired cases return 42. Eight fixtures
bring the manifest to 613. Logs use `dewy-global-aggregate-*` and
`dewy-global-owner-*`.

An independent hosted seed pair built successfully from the preceding frozen
snapshot: 191.49 seconds checking, 48.74 lowering, 4.83 emission and 24.20
backend. It predates the final module-startup release adjustment; fresh native
integration of the complete batch is still required.

## Parent-place validation adopts strict checking (2026-09-29)

Parent-place validation borrows a membership-guarded parameter summary instead
of constructing an owning optional result. Its consumed traversal worklist and
separate mutable effect-solver state explicitly request independence from the
roots/discovery data retained for subsequent queries.

The module passes strict checking on both routes, reaching 69 physical modules.
All eleven existing hosted cases and a new paired native group pass, covering
field updates through a parent and rejection of whole-child replacement through
direct, forwarded and nested helpers. Logs use `dewy-place-contracts-*` and
`dewy-global-owner-native-tests.log`; the corpus remains 605 cases.

## Element writes preserve containing array extents (2026-09-29)

Both fact engines retain known lengths of every array containing an element
store. Contents and descendant values still invalidate normally. Evidence is
saved after RHS evaluation, so resizing/replacing calls cannot resurrect a
pre-call length. Constant and named selectors, multiple nesting levels, row
replacement and RHS mutation are covered.

Thirty-eight focused/surrounding hosted checks pass, plus the paired native
group on x86-64/C. Five fixtures bring the manifest to 605. This closes the
nested extent gap exposed by the global replacement kernel below; it does not
preserve a replaced element's own old extent. Logs use
`dewy-element-store-lengths-host.log` and `dewy-global-owner-native-tests.log`.

## Read-only compiler analyses avoid intermediate snapshots (2026-09-29)

Callback analysis now keeps HIR ids rather than copied call records and reads
supplied/discovered function sets through the same resolver. Its extended
binding set and independently retained target arrays are explicit copies.
Runtime reporting builds each source index directly into its cache and borrows
that entry during materialization. Sort-lifetime checking asks membership
questions of the original sets instead of constructing optional/selected sets.

Sort option checks retain sparse nonmutating-call overrides instead of copying
the whole program effects dictionary per argument. Direct writes and argument
side effects still participate. The hosted route already uses a sparse ChainMap;
this removes the native full-table counterpart without changing the contract.

All three modules pass strict checking on both routes, reaching 68 physical
bootstrap modules. A freshly emitted native driver passes 26 callback, sort
lifetime and assertion/storage checks, including actual failure-report execution
and stderr checks on x86-64/C. Logs use `dewy-lifetime-*` and
`dewy-storage-lifetimes-*`; the corpus remains 600 cases.

## Returned field views take their local owner's storage (2026-09-29)

A stable aggregate view returned at function exit can now transfer its field
from an owned local on both routes. Static member paths use the existing
physical transfer rules: detach shared native roots, promote frame-backed
fields if needed, and clean the remaining owner normally. Incoming borrowed
roots, exposed/captured roots and lifecycle-bearing owners remain excluded.
Saved scalar values never re-read their old source at return; the surrounding
view tests caught and corrected that overly broad initial rule.

Ninety-nine focused/surrounding hosted checks pass, along with three native
groups and two additional paired cases. Coverage includes arrays, tagged
payloads, inline records, nested paths, explicit views, loop exits, a retained
caller snapshot and repeated live-byte recovery on x86-64/C. Nine new fixtures
bring the manifest to 600; two former borrowed-union return rejections now
expect successful execution. Logs use `dewy-returned-view-*` outside the tree.
This is the first owner-directed return slice, not general escape/capture
promotion; full integration remains the checkpoint above.

## Loop interval loans and bytecode source adoption (2026-09-29)

Array loops can borrow a place field after earlier writes have completed.
Both backends prove the interval separately: only disjoint fields and private
local owners may be written; unknown calls, exposed aliases and lifecycle
operations retain the snapshot. Multi-iterator source evaluation participates
in the proof, so a later source cannot invalidate an earlier iteration value.
Hosted array snapshots now produce the copy notes previously missing from
single/multiple iterator paths; strict checking sees those operations.

Ninety focused/surrounding hosted checks and two native groups pass. Seven
fixtures bring the paired manifest to 591. All sixteen bytecode execution and
text/stream equivalence tests pass with the new native drivers.

The bytecode module now passes strict checking on both routes (65 physical
modules). Its retained blob and diagnostic results explicitly request
independence; adjacency traversal reads a guarded dictionary slot directly.
The full hosted bootstrap prepared/emitted in 240.30/245.35 seconds with the
corrected reporting. Its inventory has 1615 implicit runtime-sized bootstrap
sites across 67 modules. This is focused evidence, not a new full
integration certification. Logs use `dewy-place-iterator-*`,
`dewy-bytecode-*` and `dewy-iterator-inventory.*` outside the checkout.

## Typed conversions preserve unrelated loans (2026-09-29)

Both shared storage proofs now keep a representation conversion's escape
restriction on its own source route rather than blocking the complete caller.
Typed value conversion does not expose an arbitrary outside owner. Source
escape summaries, raw boundaries, later argument writes and public allocation
permissions remain conservative. UTF-8/Unicode-scalar conversion and mutation
of a converted byte array retain value independence and reclaim temporary
storage after warming the runtime's reusable region.

Thirty-six focused/surrounding hosted checks and the paired x86-64/C group
pass. Five fixtures bring the corpus to 584. The numeric type-product module
now passes strict checking on both routes, reaching 64 physical modules.
The fresh driver was built with the preceding corrected native driver, since
the older full-checkpoint seed cannot check the new strict predicate module.
Logs use `dewy-conversion-loan-*` and `dewy-type-products-*`.

A refreshed hosted inventory after the preceding ownership/report fixes has
1,587 implicit runtime-sized bootstrap sites in 69 modules (down from 1,694
in 72); it predates this conversion change. Complete source adoption and the
other closure work below remain open. The frozen inventory source is
`phase1-storage-inventory-source`, with `dewy-storage-inventory.*` logs outside
the checkout.

## Predicate result ownership and numeric constants (2026-09-29)

`inferred_results.dewy` now passes `$explicit_copies` on both compiler routes:
compute a proposition's negation while the original remains readable, then
transfer both independent results into the refined type. This removes an
unnecessary early snapshot without changing evaluation effects. The complete
inferred-result acceptance/type comparison group passes. Strict adoption is
now 63 physical bootstrap modules.

Bigint's limb base, mask and unit magnitude are immutable startup values,
matching their existing constant role. Fourteen hosted bigint checks and
paired x86-64/C arithmetic execution pass. The numeric type-product helper
still has a separate storage-proof gap across representation conversions;
its strict directive is not enabled. Logs use `dewy-inferred-results-*`,
`dewy-immutable-bigint-*` and `dewy-constant-bigint-*`.

## Shared storage proof across runtime reports (2026-09-29)

The shared argument/literal storage proof now uses the same installed-report
boundary as direct lowering. Hosted traversal omits compiler-marked report
call edges; native traversal follows a RuntimeFailure's source message instead
of its expanded reporting body. User conditions/messages retain their own
calls and writes. Public effect contracts retain reporting effects: storage
isolation is not a purity guarantee.

Twenty-nine hosted storage/effect checks, the additional source-message
rejection, and both paired native report groups pass. Coverage includes
transitive checked helpers, borrowed record temporaries, zero-allocation happy
paths, side-effecting failure messages, user functions with helper-like names,
and rejection of `no_effects` on reporting code. Three fixtures bring the
manifest to 579. Logs use `dewy-report-loan-*`; the fresh native test driver is
in `phase1-shared-report-source` outside the checkout.

## Ordered guards preserve last-use transfers (2026-09-29)

Both move analyses now model an `else if` guard as running only for its own
arm or a later outcome. An earlier taken body and a later guard are disjoint;
reads after the conditional remain live on every incoming path. Persistent
paths store choice ranges, keeping long conditional chains shallow rather
than introducing one nested path per guard. Loop and capture restrictions
remain in force.

Three focused hosted cases, 38 surrounding move checks and the paired native
x86-64/C group pass, including nested arms, post-join rejection and repeated
cleanup. Three fixtures bring the corpus to 576. Logs use
`dewy-ordered-guard-*`. The compiler's predicate-result constructor now moves
its selected constant through the ordered conditional; retaining both a fact
and its negation is the next separate storage obligation.

## Isolated later arguments beside place projections (2026-09-29)

Hosted call-boundary borrowing no longer treats every known later call as a
possible write through an unknown place alias. A finite reverse call graph
proves functions whose writes remain in their local/by-value storage. External
writes, place parameters, raw access, unresolved calls and captures remain
conservative. Diagnostic support uses the existing compiler-report boundary;
user message expressions still contribute effects. This matches the already
supported native calculation of an index beside a place projection.

Twenty-three focused/surrounding hosted checks and the paired native group
pass. They include zero allocation over 1,000 calls, a disabled-proof control,
transitive helpers, place writes, ambient writes and raw exposure. Five fixtures
bring the corpus to 573. Logs use `dewy-nested-place-loan-*`. The bootstrap
`inferred_results.dewy` nested getter now borrows; its next remaining copy is
a last-use value in an ordered conditional whose later guards also mention it.

## Last-use tagged record fields (2026-09-29)

Both lowerers now transfer the active payload of an ordinary record's last-use
union field. The cell stays in the containing record for normal cleanup, with
its payload emptied; the receiving cell owns the transferred value. Native
lowering detaches shared enclosing roots before touching the field. Narrowed
payloads retain their actual layout, and fixed frame trees and family-layout
conversions keep the established copy path. Native field-sensitive liveness now
includes these cells, including replacement after a transfer.

Ten focused hosted checks (including a disabled-proof control), 60 surrounding
move/union checks and the paired native group pass. Coverage includes optional
owners, nested fields, narrowed array/record payloads, retained snapshots,
replacement and 1,000 iterations with no retained heap bytes. Escaping named
borrowed aliases still require separate owner-directed promotion; they are not
silently reclassified as owners. Ten fixtures bring the manifest to 568.
Artifacts use `dewy-union-field-*`. The `inferred_results.dewy` endpoint transfer
now proves; its next obligation is a nested read-only getter call.

## Computed immutable startup owners (2026-09-29)

The shared storage proof recognizes ordinary factory results and explicit
copies as independent startup owners, alongside literal construction. Only
immutable, owning module declarations qualify; local declarations are removed
before resolving ambient readers. Unknown/raw operations and mutable globals
keep their existing stability restrictions. Explicit copies also qualify as
fresh local origins under the same exposure and capture checks.

All eleven hosted checks and the paired native group pass, including a proof-
disabled control, mutation of the original after a startup snapshot, record
factory results, mutable globals and captured local storage. Six new fixtures
bring the corpus to 558. Logs use `dewy-computed-constant-*`. The compiler's
`type_products.dewy` remains non-strict: its call graph reaches reporting and
raw I/O, so the shared incoming-storage proof still cannot justify its call
root. No ambient mutation or allocation permission was relaxed to admit it.

## Explicit array assignment takes its result owner (2026-09-29)

Hosted assignment now takes the arena descriptor produced by an explicit copy
of existing storage, as it already does for a named function result. Previously
it copied the snapshot again and rejected that second operation under strict
policy. Copying a fresh literal still elides the redundant snapshot and promotes
the literal's storage across its scope; it never lends the dead frame buffer.
Native lowering already supports these transfers.

Five focused hosted cases and their paired native group pass, covering startup
globals, local and place replacement, self-copy and nested literal lifetimes.
Twelve surrounding explicit-copy tests also pass. Five manifest cases bring the
corpus to 552. Artifacts use `dewy-explicit-array-assignment-*`. The complete
inventory at the preceding repaired native checkpoint is 4,278 sites / 55,629
lines = 76.902/KLOC, within the unchanged 4,500/85 gates.

## Modeled array operations preserve unrelated storage loans (2026-09-29)

The shared storage proof now recognizes ordinary builtin array operations in
its ambient call graph, using the same classification for exposure and caller
stability. Their receiver/argument routes already belong to the effect summary;
an operation on one record field does not add an unknown ambient write to all
siblings. Lifecycle-bearing arrays and sort callbacks retain the conservative
call-graph boundary. No allocation permission changes: the builtin can still
need storage even when a sibling loan is proved.

Seven hosted checks and two paired native groups pass, including a disabled-
proof control, overlapping later-argument rejection, and zero allocated bytes
over 1,000 unique-owner calls. Thirteen surrounding hosted loan checks also
pass. Six fixtures bring the corpus to 547. Artifacts use
`dewy-sibling-array-method-*`. The compiler's `type_products.dewy` still has
unproved storage boundaries, so it has not been marked strict.

The preceding frozen repairs reached a byte-identical three-generation native
fixed point with both backend execution/scaling checks. Generations 2/3 took
92/83 seconds under concurrent tests, not isolated performance measurements.
The 541-case parity run and broader pytest run remain in progress; the latter
has found the contextual-literal follow-up described below.

## Full-suite repair: superseded expectations (2026-09-29)

The remaining expectation updates distinguish supported consuming returns from
unused bodies that really require snapshots. The copy-inventory fixture now
keeps its source live across retagging, so it still exercises a real copy rather
than a newly supported move. Stronger array-length evidence reports a proven
out-of-bounds access; the older tests expected only an unknown bound. The getter
projection fixture now passes its required type table. The borrowing fixture
accepts the already implemented proof that unrelated raw work cannot reach a
private, unexposed input. The CLI string inventory expects retained immutable
bytes to remain outside the logical-copy budget, as the approved policy states.

Validation: 24 diagnostic/getter checks, 22 hosted copy-policy checks and 27
paired strict-body/widening checks pass; the standalone borrowing fixture also
passes. The fresh full CLI test passes against frozen
`phase1-full-suite-repair-source`, including the unchanged compiler copy gates.
Its first attempt built the seed successfully and exposed a removed test-local
row helper; after restoring that helper the complete command test reused the
same independent hosted seed. A fresh non-slow suite and three-generation
native rebuild are now running. These targeted repairs do not yet certify a
green full suite or completion of Phase 1.

The fresh suite's live failure log caught a follow-up in contextual dictionary
literal unpacking: requiring array subtyping also compared the literal's
unconverted element type. The new check now applies only to union destinations;
ordinary array fields retain the established length-transfer rule after their
initializer has been checked. The unpacking fixture and all eleven hosted
array-field regressions pass. The frozen full run still uses the preceding
source, so this repair needs the later integration checkpoint.

## Full-suite repair: bounded union-array copies (2026-09-29)

Hosted source checking now retains a known array initializer's length through
a union annotation, matching native reads without narrowing the write contract.
Array-transfer copy reporting likewise uses a known source length instead of
the wider destination's growable contract. A bounded copy remains inventoried;
runtime-sized elements and unknown lengths retain their strict-copy obligation.
The original local-union failure now executes as a bounded-copy positive, while
the negative obtains its unknown-sized value from a function and is rejected.

All 46 local-widening/strict-policy/injection checks pass with the paired native
groups. Twelve field-read checks pass, including union field/binding replacement
on both compilers/backends. The source-checker union-array comparison also
passes against the frozen native checker. Four new manifest entries bring the
corpus to 541. Artifacts use `dewy-bounded-union-*` and `dewy-union-*`.

## Full-suite repair: shared family adoption helpers (2026-09-29)

Hosted last-use record adoption now shares one exact field-transfer helper per
concrete nominal layout. Previously each parent helper repeated all descendant
transfers, regressing the family-growth fixture to 870,995 generated bytes.
It now emits 295,602 bytes and passes the unchanged 700,000-byte gate. Families
with fixed-array fields keep their prepared/unprepared destination distinction;
borrowed fields also retain the original path. Native record transfers already
hand over their owned root and do not need this hosted representation repair.

All seven focused helper/nominal-payload checks pass, including x86-64/C
execution, prepared result fields, descendant-only storage, value independence
and repeated cleanup. Artifacts use `dewy-record-helper-*`. The complete pytest
checkpoint above still has other repairs pending.

## Full-suite repair: aliased selector lengths (2026-09-29)

Array length transitions invalidated descendants but missed peer routes that
could denote the receiver itself: clearing `xs[j]` could leave the old length
of `xs[i]` in the source checker's type facts. Both checkers now capture the
receiver's old length, invalidate all overlapping routes, then install its
postcondition. Sorting retains its length and invalidates only descendants.
This repairs an unsound acceptance; no new proof is assumed about selectors.

The complete selector module passes all 12 checks, including both compilers
and x86-64/C execution. Thirty-three surrounding hosted array/route checks
passed; one stronger out-of-bounds diagnostic required a separate expectation
update. Four rejected manifest cases cover const, mutable and literal peers,
including nested record fields, bringing the corpus to 537. The native driver
was built from frozen `phase1-regression-repair-source`; artifacts use
`dewy-selector-*`. Other full-suite failures are still being repaired.

## Full-suite repair: conditional frame-array expectation (2026-09-29)

The older representation test required both branches of a read-only array
selection to use owned descriptors. The current scoped-loan proof keeps their
data in the frame and adapts only the selected view. The regression now checks
that representation and executes both branches on x86-64/C. The targeted
range/array/string pass had 107 passes and this one stale expectation; all ten
representation checks pass after updating it. The nine existing record-element
checks also pass with the corrected move explanation. The frozen broader run
is still finishing and has additional failures to resolve.

## Effect syntax owns its retained snapshots (2026-09-29)

`effect_syntax.dewy` now enables `$explicit_copies`. Its application parameter
list and returned effect contract explicitly own independent snapshots. Rebuilding
an immutable `Source` copies the node list it modifies and retains only the source
metadata needed for replacement, instead of first snapshotting the whole source
record. These are intentional value boundaries, not a claimed speedup or copy
budget reduction; every copy stays in the inventory.

Both compiler/backend pairs pass source-replacement and registry-replacement
fixtures, and the hosted inventory contains only explicit runtime-sized copies
for this module. The initial three checks took 544.53 seconds, dominated by
compiler-sized C builds. Their inventory assertion now runs inside the existing
paired harness to avoid duplicating the hosted compilation and execution.
Two manifest entries bring the corpus to 533. Artifacts use
`dewy-effect-syntax-*` and `dewy-strict-effect-syntax-*`. The frozen full suite is
still completing with reported failures; this does not close Phase 1.

## Nominal child payloads at parent results (2026-09-29)

Hosted lowering now adopts the owned fields of a last-use nominal child into
the parent's complete family root. It preserves the dynamic brand and child-only
fields, and gives the destination the correct allocation size for its cleanup.
Copying the source cell's tag or handing over its differently sized root would
not suffice. The proof is limited to canonical nominal prefixes with unchanged
inherited field types; retained readers and representation changes keep their
ordinary obligations. Native lowering already supports this transfer.

This closes the `TokenError` to `Error` return in bootstrap `test_syntax.dewy`,
which now enables `$explicit_copies`. Four focused hosted checks and their
paired native group pass, including wider sibling layouts, child-only owned
fields, union/ordinary owners and repeated cleanup. The complete test-syntax
runner compiles under strict policy and executes on both backends through both
routes; its hosted inventory has no implicit runtime-sized copies. Five added
manifest cases bring the corpus to 531. Logs use `dewy-nominal-payload-*` and
`dewy-test-syntax-*`. The broader frozen pytest run remains in progress with
failures to resolve; Phase 1 is still open.

## Nested array descriptor transfers (2026-09-29)

Last-use nested arrays now transfer their descriptor from the selected slot.
Fields and elements share one descriptor-handoff helper in each lowerer. The
containing COW array detaches before its slot changes; arena descriptors move,
while frame descriptors promote with the operation retained in the copy report.
The hosted liveness inventory now also recognizes owned element handles in a
fixed frame buffer. Only the element transfers, never its enclosing frame data.

Validation: seven focused hosted checks, 16 surrounding hosted checks, the
existing paired record-field group, and the complete nine-check descriptor
module pass. A separate slot-replacement case passes on both compilers/backends.
The kernels check retained snapshots, const roots, returned elements, successive
owning transfers, slot renewal, bounded allocation and steady-state cleanup.
Disabling element moves fails the allocation control. Read-only borrowed-alias
promotion remains separate; these handoffs require an owning source or an owned
container slot. Eight manifest cases bring the corpus to 526. Artifacts use
`dewy-nested-array-*`; no strict-copy or allocation gate was weakened.

## Last-use record elements (2026-09-29)

Ordinary records can now transfer out of an owned array at their last use,
including disjoint constant slots and a runtime-selected final read. Both
lowerers detach the containing array before changing physical ownership, so
retained COW snapshots stay independent. Native elements hand over their headed
record root and clear the slot; hosted elements adopt owned fields into the
receiving root and leave the emptied old root for array cleanup. The same
field-sensitive liveness proof handles sibling reads, with live aliases,
exposed storage, lifecycle hooks and incompatible layouts kept conservative.

Validation: 29 surrounding hosted checks, 11 expanded hosted checks (including
a disabled-move allocation control), and three paired native groups pass. A
separate runtime-index case passes on both compilers/backends. The compound
assertion's reusable hosted scratch-header pool is warmed before its retained-
bytes measurement; repeated calls retain no additional storage. Eleven new
manifest cases bring the corpus to 518. Artifacts use `dewy-record-selection-*`.
The preceding frozen 507-case integration remains in progress; Phase 1 is open.

## Integration repair (2026-09-29): nested loop writes

The independent hosted seed at `a2919429` exposed a missing hosted loop
invalidation case: the syntax pre-scan found `items.push` but missed
`box.items.push` and deeper stores. Exact initializer lengths could therefore
survive mutation; the compiler's local-place inventory copied an empty array
instead of the collected node IDs. The pre-scan now shares the complete storage
route traversal used by iterator exclusion checks. No borrowing rule changed.

Validation: 27 focused hosted checks pass, plus paired native execution and
rejection cases for nested fields, indexed receivers, while/iterator loops,
and stale bounds. Seven new manifest cases retain this regression. The frozen
425-case integration run is still in progress; its failures are being reduced.
Phase 1 remains open pending corrected-seed integration and the checklist below.

## Integration repair (2026-09-29): conversion facts

Array-field fact seeding now crosses only subtype-widening casts in both
checkers. A real conversion produces a different value: in particular, decoding
bytes cannot refine an optional string back to the input's array type. The
existing decoded-string escape regression exposed this after array root facts
were generalized. Twenty-three hosted conversion/field-fact checks and two
paired native groups pass, including ownership and release of decoded payloads.

## Integration repair (2026-09-29): read facts versus write slots

Native assignments and place arguments now carry the destination's declared
storage type on their target leaf. A previous `none` value in a resource union
must not hide the slot from lifecycle replacement; an exact array read length
must not change a writable descriptor's representation. Compound assignments
keep their narrowed read expression separate. This matches the hosted checker's
storage contract rule and restores the existing resource-slot regression.

Five hosted checks and three paired native groups pass, covering optional
resource replacement, mutable optional scalar fields, array replacement/growth,
and retained field-read evidence. A new write-destination manifest case records
the nonresource paths as well. The independent seed with the preceding loop and
conversion repairs built successfully (233.57 seconds prepare, 238.88 emitted);
full source bootstrap validation follows with this write-target repair included.

## Nested record argument loans (2026-09-29)

The shared storage proof now permits stable inline record fields in a
call-scoped record root, including nested dictionaries. Both lowerers copy only
the bounded inline representation: its descriptors remain borrowed from the
source, with no retain, allocation or cleanup in the temporary root. Callee
read-only effects and caller-wide storage stability are still required; later
argument writes prevent the loan. The copy report includes each bounded
representation copy rather than hiding it under the source type's runtime size.

The frame bound includes possible nominal descendants and structural carriers,
counting repeated fields and conservatively summing family alternatives. Cycles,
unsupported layouts and the 4096-byte per-function budget retain the ordinary
ownership obligation. No new syntax or ownership policy is introduced.

Validation: 27 hosted checks and two paired native groups pass; an additional
nominal-descendant execution case passes on both backends for both compilers.
The kernels require zero allocated bytes across 1,000 calls. They cover nested
structural records, minted records, dictionaries, mutation conflicts and an
oversized descendant family. Eight fixtures bring the manifest to 441.

Independent integration of the preceding `da4a1aca` source reached a
byte-identical three-generation native fixed point, including x86-64/C execution
checks. Generations 2/3 took 61/65 seconds under concurrent checking, not isolated
performance measurements. Its full 433-case parity run remains in progress.

## Certified integration checkpoint: `da4a1aca` (2026-09-29)

All **433/433** paired acceptance/execution cases pass, including every failure
from the earlier 425-case run. The native pair reaches a byte-identical
three-generation fixed point and passes its x86-64/C execution checks. The
complete native inventory reports **4,270 sites / 55,206 lines = 77.347/KLOC**,
passing the unchanged 4,500/85 gates. This is the latest complete certification;
the nested-record-loan work above has focused evidence and a fresh independent
hosted seed, but postdates this full checkpoint.

The nested-loan hosted build prepared/emitted in 233.13/238.44 seconds. Its
remaining implicit runtime-sized inventory is 1,823 sites in 73 bootstrap
modules, unchanged from the preceding hosted inventory: the new proof enables
nested loans but does not yet cover the compiler's full context constructors.
Phase 1 remains open; these measurements are not a completion claim.

## Optional record field transfers (2026-09-29)

Last-use array-field transfer now includes owned optional/tagged record locals.
The source cell or nullable record handle remains available for cleanup of
untouched fields. Native lowering detaches any shared record before emptying the
selected slot; hosted lowering requires its registered aggregate-cell owner.
Exact member representation is required. Borrowed roots, exposed places, live
aliases and later owner reads retain their ordinary copy obligation.

Eight hosted checks pass, including a positive control that disables field
moves and observes allocation, plus 58 surrounding field/union move checks.
The final paired native group passes on x86-64/C (19.14 seconds), covering
optional and mixed unions, nested records, returned fields, shared snapshots,
repeated live-byte checks and rejected retained-reader cases. Seven fixtures
bring the manifest to 448. Full integration remains certified at `da4a1aca`.

## Scalar cell and place projection loans (2026-09-29)

Bounded call roots now admit scalar tag cells, including concrete member
initializers and existing optional scalar values. Hosted lowering preserves
`none` until tagging; native lowering packs members directly into the final
inline cell rather than allocating a temporary. Allocation effects use that
same construction proof. Cells with owned aggregate payloads retain their
ordinary storage obligation.

The shared proof also admits unwritten projections of a sole place parameter.
Sibling field writes are allowed; overlapping writes, escapes and unknown/raw
calls still prevent borrowing. Multiple place formals remain conservative
until cross-parameter alias relationships are proved.

Ten hosted checks and two paired native groups pass, including zero allocation
across 1,000 calls, optional defaults, existing scalar cells, sibling mutation,
later-argument mutation and owned-cell rejection. Ten new manifest cases bring
the total to 458. Full integration remains certified at `da4a1aca`; Phase 1 is
still open.

## Projection-only forwarding of call roots (2026-09-29)

The bounded call-root proof now follows whole-record arguments through known
read-only helpers. Every use must ultimately project a field or forward to
another such parameter. A complete-record ownership use rejects its parameter
and all upstream forwarders through a finite worklist; recursive forwarding
without an owning endpoint remains safe. This does not equate read-only effects
with a nonowning parameter ABI.

Twenty-four hosted checks and two paired native groups pass, covering multiple
helpers, keyword arguments, recursion, returned roots, owning locals and the
existing frame budget/stability cases. Five fixtures bring the manifest to 463.
Native reporting also retains the bounded two-word copies of existing scalar
cells in call roots. An independent hosted build of the forwarding proof is in
progress; full integration remains certified at `da4a1aca`.

## Immutable startup storage loans (2026-09-29)

Closed literal initializers of immutable startup bindings now supply shared
storage evidence to allocation effects and lowering. Function-local/captured
const declarations and required views are excluded from this startup proof;
mutable globals and initializers with calls or existing-storage reads remain
unknown. Reading a proved immutable startup value adds no external effect.
Borrowing still excludes raw/unknown call graphs.

A dynamic array's declared descriptor layout is preserved when its read type
carries an exact length. The call-root proof checks the startup declaration's
store contract before using that descriptor; fixed-array storage retains its
ordinary conversion obligation.

Five hosted checks, 150 surrounding hosted effect/borrow checks and paired
native x86-64/C cases pass. Repeated calls allocate zero bytes, preserve array
contents and reject mutable or unproved startup storage. Five fixtures bring
the manifest to 468. The preceding forwarding source's independent hosted
build prepared/emitted in 231.48/236.57 seconds and reduced implicit
runtime-sized bootstrap copies from 1,823 to 1,804 sites across 73 modules.
Full integration remains certified at `da4a1aca`; the new batch follows below
when its integration completes.

## Preserve siblings after an ordinary field transfer (2026-09-29)

Ordinary dynamic-array fields now reuse logical ownership's field-sensitive
backward liveness when a containing local remains live only for sibling fields.
Both lowerers retain their physical ownership/layout checks and empty only the
transferred slot. Existing borrowed dependents, captured or exposed roots and
later overlapping reads keep the conservative copy path. This extends the
ordinary-array proof using the existing branch/loop lifetime rules rather than
introducing a second field-path analysis.

Nine hosted checks pass, including a positive control that disables field moves
and observes the otherwise avoided allocation; 42 surrounding hosted checks and
two paired native groups also pass. Repeated kernels preserve optional, mixed
union and plain record siblings, sibling writes and owned sibling arrays with
zero allocation during transfer and no retained live bytes. Overlapping field
reads and explicit/inferred aliases remain rejected under strict copy policy.
Eight fixtures bring the manifest to 476. The preceding `db95f751` source has
reached a native fixed point and passed its 4,276-site / 77.204-per-KLOC copy
gate; its complete 468-case parity run is still in progress.

## Keep overload candidates in one owner (2026-09-29)

Ordered dispatch now retains a checked candidate index and an ambiguity count
instead of copying promotion plans into a second winners array. The selected
index carries `index <? apps.length`; after proving uniqueness, `pop` transfers
the winning record from the original array. The new field-liveness proof also
transfers `bound.pos` while preserving the later `bound.kw` read.

The focused compiler-import kernel passes hosted and native compilation and
x86-64/C execution, covering exact selection, named/positional binding,
numeric promotion, ambiguity and no match. Its hosted inventory has only the
separate mapping-argument obligation in `dispatch.dewy`; the former argument
array, winner insertion and result union copies are gone. One fixture brings
the manifest to 477. No dispatch ranking or ambiguity rule changed.

## Transfer inline record fields (2026-09-29)

The existing field liveness proof now also permits inline records and
nested dictionaries to leave an ordinary owned root. Hosted lowering adopts
their fields into destination storage; native lowering constructs a headed
root and dispatches the transfer across the actual nominal family. Array
handles transfer, frame-backed arrays promote, and moved string/union payload
slots are emptied without disturbing sibling cleanup. Taking a native field
detaches shared COW storage before changing it. Prepared fixed-array trees,
live aliases and later overlapping reads retain their existing obligations.

Twelve hosted checks, eighteen surrounding checks and two paired native groups
pass on x86-64/C. The kernels bound allocation independently of a 1,024-element
buffer and verify repeated live-byte recovery, dictionaries, nested fields,
nominals, optional payloads, frame promotion and retained snapshots. Disabling
field transfers makes the allocation control fail as expected. Eleven cases
bring the manifest to 488. Full certification remains at `db95f751`.

The preceding sibling-field/dispatch hosted build prepared/emitted in
228.28/233.32 seconds and reduced the implicit runtime-sized bootstrap
inventory from 1,805 to 1,765 obligations across the same 73 modules. Memoized
ownership queries retain this result; both focused native groups pass.

## Disjoint operands share an owner (2026-09-29)

Component liveness now checks the maximal storage routes of other operands.
`consume(pair.left pair.right)` can transfer both fields; a whole-owner or
overlapping argument still prevents the transfer. Aliases retain their
conservative whole-root footprint, and selectors still contribute their own
reads. Whole-root moves keep the unique-input requirement. This is shared by
ordinary storage and logical resource cleanup.

Forty-seven hosted argument/lifecycle checks and two paired native groups pass,
including drop counts and overlapping-argument rejection. Five cases bring the
manifest to 493. Enabling strict policy for the dispatch module additionally
exposed native snapshots for defaulted record parameters; that protocol is being
extended before adoption is committed. Full certification remains `db95f751`.

## Owning defaulted records and dispatch policy (2026-09-29)

Direct mutable record parameters now use the same owning protocol with or
without a default. Supplied arguments donate fresh/moved/explicitly copied
storage; omission constructs the default lazily. Both branches own their
cleanup. Read-only defaults and first-class callable values retain their
existing borrowed ABI. Hosted default joins distinguish direct storage from
copying without confusing that distinction with the cleanup presence bit.

Five focused hosted cases, twenty-seven surrounding cases and three paired
native groups pass. Allocation kernels cover supplied/named/omitted arguments,
lazy side effects, retained caller values and repeated live-byte recovery.
The dispatch module now enables `$explicit_copies`: overload selection takes
its winner, and generic instantiation transfers disjoint inference fields.
Its signature getter explicitly requests independence for escaping returns;
synchronous getter loans remain available. Five fixtures bring the manifest
to 498; full certification remains `db95f751`.

An independent hosted build of this snapshot prepared/emitted in
237.78/242.79 seconds. Its implicit runtime-sized bootstrap inventory is
**1,694 sites in 72 modules**, down from 1,805/73 at the certified checkpoint.
The resulting native seed built its driver and passed the groups above.

## Once-initialized local selector identities (2026-09-29)

Resource separation can now use stable `int64` locals as well as inputs. A
lexical availability pass records which declarations dominate each operation;
liveness may request a disequality only when its referenced selectors already
exist there. Nested branch/block locals are supported after initialization.
Loop-repeated declarations keep wildcard identities. Mutation, capture and
place-exposure exclusions remain in force; no selector expression is moved or
reevaluated to manufacture a proof.

Twenty-four hosted checks and two paired native groups pass on x86-64/C.
Positive cases include `let`/`const`, branch-local initialization and changes
to the original inputs after copying their values. Missing separation,
future declarations, rewritten selectors and loop-repeated declarations are
rejected. Eight fixtures bring the manifest to 506. Full certification remains
`db95f751`; the remaining checklist is unchanged in scope.

## Return an inline field through destination storage (2026-09-29)

Hosted record returns now consult the same adoption helper as declarations,
assignments and owning calls. A last-use inline field can therefore transfer
its owned buffers directly into the caller's result storage, retaining normal
cleanup of the source record. Native returns already use the general owned-value
path. Thirteen hosted field checks and the paired x86-64/C return regression
pass, including repeated live-byte recovery. The manifest now contains 507
cases; a fresh full integration checkpoint is next.

## Current completion checklist (2026-09-28)

Phase 1 is **not complete**. The entries below replace the original generic
work list; historical checkpoints below still describe their own dates.
Implemented means that the mechanism and focused regressions exist, not that
all source shapes or the complete integration matrix have been certified.

| Area | Implemented foundation | Remaining closure work |
| --- | --- | --- |
| 1.1 Copy policy | Both semantic/lowering entry points enforce `$explicit_copies`; `.copy()`, inferred/required views, last-use moves, recursive shared-string exemptions and placement-independent acceptance are present. | Complete compiler-source adoption and copy inventory/acceptance parity; reduce unexplained copies with shared proofs rather than explicit-copy annotations used to hide regressions. |
| 1.1 Resource lifetimes | Checked lifecycle hooks, inherited composition, owning/borrowed parameters, conditional ownership, partial record fields, array and dictionary ownership operations, conditional runtime-selected transfers with disjoint field footprints and drop-hook access proofs. | Broader stable-selector discovery beyond function inputs, remaining unsupported resource operations; escaping/writable captured storage lifetimes. |
| 1.1 Placement | Frame proofs shared with effects, native scoped arenas, escape checks/copy reports, fallback reasons and no-allocation body warnings. | owner-directed promotion instead of conservative outer-store fallbacks; hosted placement parity and measured allocator/copy kernels. |
| 1.2 Proofs | Finite relational facts, checked loop candidates, alias/effect invalidation, `$proof`, `$assert`, audited `$unsafe_assume` and rejection of known contradictions. | Audit candidate selection, convergence limits and shared proof coverage against the intended finite-qualifier design; keep unsupported obligations unknown; final paired integration/scaling checks. |
| 1.3 Effects | Public rows/exclusions, nominal resource identities, inferred rows, kind-checked row parameters, callback inference, place-subject translation, allocation contracts and lifecycle effects. | More precise storage/move proofs shared with lowering; clarify the remaining failure/escape vocabulary before implementing new forms. |
| 1.4 Settled surface decisions | Type-directed juxtaposition (including numeric RHS), reserved names, unit nominals, uniform `set.push`, digit-label normalization, array/record value equality. | Final integration checks and documentation consistency. Keep the expressly open decisions below separate. |

Integration exit: a fresh hosted-built native route, paired acceptance and
execution manifests, relevant ownership/allocation counters, and a native
two-generation fixed point. Record evidence per checkpoint; neither a fixed
point nor a passing subset of tests alone closes the phase. Native build
performance retains the 30-second minimum target and 10-second stretch target.

Explicitly open designs remain open: fallible allocation and failure policy,
resource-parameterized allocator rows/user allocator kinds, generic rows that
carry/remap callback-local place identities, non-power-of-two
base-string packing and Unicode repertoire/escape decisions. The provisional
COW implementation preserves value independence; predictable zero-cost
ownership remains the long-term design question. This checklist does not
approve new syntax or remove these items from the roadmap.

Checkpoint (2026-09-29): the independent-seed failure was a hosted value
cast lowering bug, exposed by the traversal cursor added in `50deaaca`.
Erasing a record value cast to `int64` before selecting an inferred local's
storage skipped its ownership boundary. Reassigning the cursor then overwrote
the borrowed input node, corrupting a checked block into its final flow node.
A hardware watchpoint identified that write in `borrowing.scan_reads`.

Hosted lowering now retains the logical record type until storage selection,
then erases its representation during expression extraction. No move/copy
permission is weakened. Cursor traversal, field mutation, dynamic fields and
strict-copy rejection have focused regressions; 38 hosted ownership/brand/
projection checks and the paired x86-64/C group pass (28.08 seconds). Four
fixtures bring the manifest to 425. A fresh independent hosted seed is building;
full integration certification remains pending.

Checkpoint (2026-09-29): current array-field length facts now refine hosted
reads without narrowing the declared mutation/growth contract. Both routes
reseed stable member routes after replacement; mutation and deferred captures
invalidate old evidence. Forty-four focused hosted checks and the paired
x86-64/C group pass (15.76 seconds). Nine fixtures bring the manifest to 421.
This closes the constructor-length precision gap recorded below.

Independent integration of `3823554c` exposed a return-move regression in a
hosted-built native seed. A minimal conditional optional-record return fails
when its guard compares strings; the corresponding native-built driver
accepts it. Disabling hosted array-field transfers does not remove the failure.
Investigation is ongoing; `73fd8f9c` remains the latest full certification.

Checkpoint (2026-09-28): final array-field reads can transfer from owned
record locals on both routes. The complete receiver participates in last-use
analysis, including derived readers, branch paths and loop backedges. Taking
a native field detaches a shared record first; a frame-backed descriptor uses
ordinary storage promotion rather than escaping its frame. Other fields retain
normal cleanup. Conditional promotion is reported with the existing placement
exemption, rather than hidden or treated as a source-requested copy.

Fifteen hosted field-transfer checks pass, including zero-allocation reserved
buffer growth, a positive control with transfer disabled, aggregate elements,
repeated live-byte checks, shared snapshots and const owners. The final paired
native group passes on x86-64/C (53.76 seconds). The earlier record-field suite
also passes on both routes; lifecycle/borrow regression checking passed 61 cases
and exposed two stale expectations about synchronous read-only captures. Those
expectations now check supported execution and rejection of writes; all eight
focused hosted checks and the two native execution cases pass. The test update
is separately committed as `13df1d66`.

Native move analysis no longer copies the program-wide donation map into each
function's mutable analysis state. Its candidate lists update their actual
slots, and membership-guarded readers avoid optional owning lookup results.
It passes strict checking on both routes: **59 physical bootstrap modules**.
Twelve field/capture fixtures bring the manifest to **412 cases**. The corrected
native driver also emitted the complete bootstrap (24,161,632 bytes) before
the final exact-length/reporting adjustment; a fresh independent full integration
checkpoint is still required. The latest completed full certification remains
`73fd8f9c` below.

One acceptance-precision gap remains recorded: native retains the exact length
of `Pack[[2]].values` across the local constructor, so a snapshot before a drop
hook is bounded; hosted currently keeps only the declared runtime length and
requires an explicit copy. With a runtime-sized input both reject the implicit
snapshot, and both preserve the hook's read. No hook is skipped or run after
its observed field has been emptied.

Checkpoint (2026-09-28): the frozen `73fd8f9c` integration passes
**391/391** paired acceptance/execution cases and a byte-identical
three-generation native fixed point. The last generations took 59/65 seconds
under concurrent validation; hosted preparation/emission took 223.40/228.41
seconds. Its complete native inventory is **4,171 sites / 54,993 lines =
75.846/KLOC**, passing the unchanged 4,500/85 gates. The hosted inventory
contains 1,906 implicit runtime-sized obligations in 78 bootstrap modules.
This is the latest complete integration certification.

The next ownership slice lets direct aggregate inputs become working local
owners after checked scalar query calls. Solved parameter effects must prove
those calls read-only and non-retaining. Local ownership demand propagates
backward through aliases from actual mutations or whole-value transfers;
read-only traversal cursors and alias cycles do not create demand. Compound
updates and their checked `x = operation(x)` form agree on both routes.
Proved nonreturning diagnostic branches do not keep readers alive on the
successful continuation. The ordinary owned-parameter cleanup protocol still
handles earlier returns and live borrowed readers.

Numeric literal/constant helpers, loop control and record intersections now
pass strict checking, bringing adoption to **58 physical bootstrap modules**.
Intentional copies retain independent arena constants, cached control-flow
results, and source fields in merged records. Record merging reads the old
field's scalar metadata before replacement instead of snapshotting the whole
field descriptor. Nine fixtures bring the manifest to **400 cases**.

Focused hosted ownership/protocol and numeric checks pass. The fresh native
alias group passes on x86-64/C, including a large-integer working local, a
read-only cursor, terminal diagnostics and rejected retained aliases. Five
numeric cases, two record execution cases and a record-intersection rejection
also pass on both routes. The fresh native driver emits the complete compiler
with all 58 strict directives enabled (24,197,087 bytes), and that output
compiles with native uDewy. These changes have not yet received their own
independent hosted seed/full-manifest/fixed-point certification.

The failing-guard case exits 101 on both native backends. Its native diagnostic
preserves the condition and source, but still lacks the hosted saved operand
value notes: the existing runtime-report placeholder remains explicit. The
parity fixture tests the shared diagnostic, while the hosted test also checks
its operand note; no guard expression is reevaluated for reporting.

Checkpoint (2026-09-28): direct aggregate inputs may transfer after scalar
observations, with normal owner cleanup on earlier exits. The final read must
remain unguarded and every earlier read must be a non-retaining observation;
first-class calls and exposed/captured inputs keep their ordinary fallback.
Native donated owners now use ordinary last-use analysis, including live-view
constraints. Hosted narrowed record transfers empty owned fields while leaving
the containing union cell responsible for its payload root's cleanup.

Common union-array field lengths now borrow only for the immediate measure,
with the same proof consumed by public effect inference. Fifty-nine hosted
ownership/field checks pass. Four native ownership groups passed (101.17 s);
the fresh observed-input/common-field groups also pass on x86-64/C (61.47 s),
including early-exit live-byte checks and zero-allocation length reads.

The tokenizer now passes strict checking on both routes: recognition consumes
candidate inputs after their length tests, selection tracks an index/count
instead of constructing an owning candidate array, and its operator tables
are constant literals ordered longest first. Its control-character table is
constructed in a function-local owner. Strict adoption reaches **54 physical
bootstrap modules**; six fixtures bring the manifest to 391. The tokenizer
parity suite passes 55 cases, including the additional operator-table cases.
The native test driver was staged with the newly added tokenizer directive
disabled in its isolated build tree; the actual directive-enabled tokenizer
was then checked independently. The latest full-program certification remains
`25236513`; this slice does not claim a new fixed point.

Two proof gaps encountered during this adoption remain explicit: dependent
bounds inside an optional local do not survive a loop join, and a generated
module-level comprehension accumulator cannot yet transfer to its final
binding. Neither gap is worked around by assuming an unproved fact or hiding
a copy report. The tokenizer uses an ordinary bounded index after excluding
empty input and a local table-construction function.

Checkpoint (2026-09-28): conditional array selections now compose with
common-field loans across record unions. The shared proof checks each leaf's
layout and owner stability; lowering dispatches only the selected arm. Public
effect inference consumes the same proof. Derived selected views are registered
against their underlying owners before last-use moves, so moving a record cannot
invalidate a still-live selected array, including through another selection.
Mutable readers and escaping uses retain the ordinary owning fallback.

Thirty-five hosted selection checks pass. Both native paired groups pass on
x86-64/C (33.92 seconds), including zero-allocation reads, independent mutation
snapshots and strict rejection of an owner move with live derived readers.
Propositions, effect-boundary construction and type rebinding pass standalone
strict checking on both routes, with comments on their intentional retained
constants/contracts. Strict adoption reaches **53 physical bootstrap modules**;
four selection fixtures bring the manifest to 385. The staged native seed was
built with these three new module directives disabled only in its isolated
build checkout, then checked the actual directive-enabled sources successfully.

The frozen `25236513` checkpoint has now passed **373/373** paired acceptance
and execution cases, alongside its recorded three-generation fixed point and
complete copy-inventory gate. This closes that integration checkpoint, including
the two regressions found at `99f2592e`; later source changes still need a fresh
whole-program integration checkpoint. Phase 1 remains open for the work in the
completion checklist above.

Checkpoint (2026-09-28): stable common array fields across record unions
now lend their descriptors to read-only calls and iterator arms in both
lowerers. Alternatives may use different field offsets. Call loans share the
storage proof with public effects; iterator loans use the existing whole-owner
stability proof, without expanding the public iterator effect contract.
Exceptions, representation conversions, owner mutation and unproved lifetime
boundaries keep their snapshots. Explicit snapshots read the selected field
before any later argument can mutate its owner.

The new strict rejection checks exposed unreported ordinary union-field
snapshots on both routes. They are now counted, including iteration snapshots;
`.copy()` authorizes the independent result. Hosted container stores now
recognize all already-owned record results, including explicit copies, instead
of demanding a second implicit copy after the requested one. Both routes pass
array push/literal/replacement and dictionary-store cases with live-byte checks.

Sixteen hosted checks and both native paired groups pass on x86-64/C
(41.55 seconds for the paired groups). Five additional modules pass standalone
strict checking on both routes: tokens, syntax normalization, namespace lookup,
type tests and generic type-alias instantiation. Intentional owning snapshots
have comments; strict adoption reaches **50 physical bootstrap modules**.
Eight fixtures bring the acceptance/execution manifest to 381.

The independent frozen `25236513` checkpoint prepared/emitted the hosted seed
in 211.62/216.67 seconds and reached a byte-identical three-generation native
fixed point (last generations 61/62 seconds under concurrent validation).
Its complete native inventory contains 4,108 sites across 54,871 lines,
74.867/KLOC, passing the unchanged 4,500/85 gates. Its full 373-case parity run
is still running; this checkpoint does not claim that result or certify the
subsequent common-field changes. The hosted inventory at that revision retains
2,072 implicit runtime-sized obligations in 86 modules before this adoption.

Checkpoint (2026-09-28): last-use proofs now distinguish mutually exclusive
conditional arms in both lowerers. Persistent branch paths take one word per
read and one entry per arm. Later compatible reads and borrowed readers still
block transfer, and loop-depth checks retain owners needed by another iteration.
Both searches cap pairwise branch comparisons at 4,096 per owner; exhaustion
retains the copy. No condition is assumed true to justify a transfer.

Frozen integration at `99f2592e` completed with **363/365**, not a full pass.
Both compilers agreed on the two changed outcomes. One was a real regression:
consuming-input inference mistook a proved temporary record loan for an owning
constructor. Both analyses now exclude those borrowed roots as consumption
endpoints. The other fixture tested an unused identity return, which can now
transfer; it now retains a genuine implicit-copy obligation in the unused body.
Its rejection still precedes reachability pruning. The complete native copy
inventory at that frozen revision is 4,149 sites across 54,797 lines, or
75.716/KLOC, passing the unchanged 4,500/85 gates. The three-generation fixed
point passed (111/56/58 seconds, first generation executing the hosted-built
seed). The full manifest must be rerun at a later corrected checkpoint.

Nineteen initial hosted branch checks pass, followed by 61 focused ownership
and regression checks. All three native paired groups pass on x86-64/C
(61.99 seconds), including the 100-arm budget rejection, constructor loans,
loop exits and retained snapshots. The revised unused-function fixture rejects
on both routes. Move-note assertions now check distinct source sites and both
valid payload-transfer forms rather than incidental wording/counts.
Four fixtures bring the manifest to 373. Token strict adoption remains pending:
the branch fix clears interpolation's last-use copy, but standalone checking
also exposes a common-field borrowing gap across a record union. Strict
adoption remains 45 physical bootstrap modules.

Checkpoint (2026-09-28): hosted lowering now synthesizes stable getter
variants for direct terminal record/cell reads. The complete guard/effect
prefix remains, while the variant lends its caller's storage. Source and
reader stability, argument borrowing, exact stored representation and absence
of captures/donating parameters are prerequisites. Borrow dependencies prevent
later owner moves, and a returned borrowed record still creates its own owner.
Native retains its additional getter-forwarding support; hosted forwarding
wrappers remain on their ordinary result protocol in this slice.

Both routes can elide an explicit default-copy getter fallback for a proved
reader without lifecycle operations. HIR's `node_at` now states its owning
snapshot with `.copy()`, and the module enables `$explicit_copies` on both
routes. Strict adoption reaches 45 physical bootstrap modules. Token lookups
state the same fallback, but token-module adoption still awaits mutually
exclusive branch last-use handling; no unnecessary snapshot was added there.

Twenty hosted getter checks pass, with 34 surrounding checks in the earlier
slice. Paired record/union cases pass on x86-64/C, including zero allocations
for repeated reads, allocating disabled-optimization controls, guards, side
effects, retained snapshots and escaping results. Two fixtures bring the
manifest to 369. The frozen `99f2592e` pair reaches identical three-generation
native output (last generations 56/58 seconds); its full 365-case manifest is
running separately. Its hosted runtime inventory is 2,126 obligations in 88
modules, before the family-transfer/getter changes.

Checkpoint (2026-09-28): hosted record donation now checks complete dynamic
families instead of rejecting every ancestor layout. Last-use owned values
transfer descendant-only array fields, nested records and inline union payloads;
source cells are emptied for normal cleanup. The layout proof follows recursive
payloads finitely and retains the fallback for prepared fixed-array storage.
Native already transfers these complete owned layouts; no source rule changes.

Eight hosted checks and paired x86-64/C cases pass, including active record,
array, string and absent union alternatives, independent retained snapshots and
stable live-storage counters. The surrounding hosted suite passes 94 checks.
Two fixtures bring the manifest to 367. Full integration remains a separate
frozen checkpoint; the independent hosted build at `99f2592e` prepared in
236.43 seconds and emitted in 241.65 seconds under concurrent validation.

Checkpoint (2026-09-28): direct single-use aggregate inputs now transfer
through constructors and explicit or implicit returns. Both compilers trace
transparent checked wrappers, including payload-preserving union injections.
The hosted route gives donated runtime arrays a distinct owning parameter;
source cleanup sees an emptied descriptor after transfer. Native inline record
fields honor consuming uses instead of silently copying them. Fixed-array
prepared storage retains its existing calling protocol.

The native consuming-input analysis now uses reverse dependencies and a queue
seeded by actual ownership boundaries. A forwarding cycle cannot establish its
own ownership proof. Defaults, conditional/repeated uses, captures and function
values remain conservative. No source calling convention or effect syntax
changes. Retained callers still owe independent snapshots.

The surrounding hosted suite passes 93 checks, and both paired groups pass
on x86-64 and C (70.39 seconds), including stable live-storage counters across
2,000 calls, optional results, nested array literals and record-field transfers.
Five fixtures bring the full manifest to 365. A preliminary frozen hosted
inventory prepared successfully in 216.51 seconds; its emission harness then
called a nonexistent `render` method, so that run certifies no executable. The
next integration checkpoint must use the corrected `source` emitter and the
final source revision. Compiler-wide strict adoption remains open.

Checkpoint (2026-09-28): array-selection loans now compose through other
selected views and nested single-expression blocks. A finite dependency
worklist establishes each source from stable storage, rejects self-supporting
cycles, and revokes connected loans when a reader requires ownership. Both
lowerers retain the original owner through all dependent last reads. Internal
unions of array lengths are checked at their actual leaf layouts. Effect
checking follows that same proved selection instead of charging its erased
join casts for storage or unknown behavior; condition/leaf effects remain.

Fresh conditional call/literal results may also seed a private owner. Copies
from existing names, captures, exposure and writes remain outside that proof.
`source_names.dewy` and `import_syntax.dewy` now describe their read-only lists
as immutable selections and enable `$explicit_copies` without adding `.copy()`;
both modules pass both compiler routes. Strict adoption is now 44 physical
bootstrap modules. Compiler-wide adoption remains open.

The expanded hosted storage suite passes 45 checks; all three paired groups
pass on x86-64/C (83.87 seconds), including zero-allocation repetition, branch
laziness, preserved snapshots, multistage liveness and rejection cases. An
independent hosted-built native driver, followed by the native-built driver
with matching effect analysis, supplies the paired route. Four fixtures bring
the full manifest to 360. Full frozen integration is still certified at
`41a4a3e2`; this checkpoint does not substitute focused checks for that gate.

Checkpoint (2026-09-28): both source mutation pre-scans now distinguish call
keyword labels from writes to caller bindings. `read(values=values)` inside
an iteration no longer falsely says that `values` changed. Argument values
still contribute their nested assignments, mutating calls and place exposure.
This fixes both iterator exclusion and preliminary loop fact invalidation;
it does not weaken the later checked effect analysis.

Five focused hosted cases and paired x86-64/C execution pass, along with 32
surrounding loop/fact checks. Set and dictionary iteration, nested mutating
argument blocks, direct mutation and keyword places are covered. Two fixtures
bring the full manifest to 356. The shared-selection batch remains in progress.

Checkpoint (2026-09-28): hosted direct single-use union parameters now share
native's consuming-input protocol. A caller supplies an independent frame cell;
the callee transfers or releases its active payload. Fresh arguments and
last-use locals transfer, while a retained source still requires its ordinary
snapshot. Keyword normalization and forwarding use the same dependency worklist
as record inputs. Conditional/repeated uses, captures, function values and
prepared recursive payload trees retain their previous conservative protocols.

Thirteen hosted checks and the 78-test surrounding ownership suite pass,
including paired x86-64/C execution. Additional paired cases cover direct member
injection, runtime-array payloads and absent alternatives. Repeated-call live
storage counters remain stable. Three fixtures bring the manifest to 354;
this hosted parity change does not alter the language's source calling rules.

Frozen revision `41a4a3e2` also reaches an identical three-generation native
fixed point (60/58/58 seconds under concurrent validation). Its complete native
inventory reports 3,986 sites across 54,652 lines, or 72.934/KLOC, below the
unchanged 4,500/85 gates. The frozen hosted inventory reports 2,106 nonexplicit
runtime-sized obligations in 90 bootstrap modules; compiler-wide strict adoption
remains open. All 351 cases in its frozen paired integration manifest pass.

Checkpoint (2026-09-28): shared storage proofs distinguish private fresh
owners from incoming aliases. An unwritten local created by a literal or
ordinary value call may lend its storage across unrelated ambient effects,
provided no capture, direct place/raw exposure or representation escape can
reach it. Parameters retain the whole-call-graph alias guard. Named
projections and array selections use this same proof in allocation checking
and both lowerers. Three additional compiler modules (`method_syntax`,
`module_directives`, `path_values`) now enable `$explicit_copies` without
adding explicit copies, and pass both compiler routes.

The captured-owner regression also exposed a hosted last-use bug: after
lifting, hidden capture arguments were absent from the syntactic use scan,
allowing an array to move before a later closure read. The scan now honors
the original capture inventory. Unknown capture lifetimes keep their
snapshot obligation; no new closure semantics were introduced.

Nine focused hosted checks and the paired private-owner group pass, including
zero-allocation repetition, union fields, mutation, address exposure and
captured reads. The broader capture/ownership suite passes all 125 checks
(335.28 seconds). The complete native compiler passes hosted checking and
builds through the updated native driver. The execution driver now normalizes
entry/library/cache paths like the real CLI; a mixed relative/absolute path
regression also verifies warm-cache identity. Three new fixtures bring the
full manifest to 351. Full compiler-wide strict adoption and the final Phase 1
integration/scaling/audit milestones remain open.

Checkpoint (2026-09-28): allocation contracts and both lowerers share a
read-only array-selection proof. Complete conditional leaves may borrow
stable arrays or use bounded scalar frame literals, with lazy arm evaluation
and owner liveness retained through the selected view. Owning/escaping uses
keep the existing copy or last-use transfer. Limits are 64 scalar elements per
literal and 4 KiB of selection literals per function. General statement-bearing
arms remain owning. Ordinary call results can supply stable private owners
under the existing whole-call-graph stability proof.

Set/dictionary algebra now borrows operands while constructing its fresh
result. Only a potentially invalidated left operand needs a snapshot; hosted
reporting now includes that snapshot instead of silently cloning both inputs.
Fresh operand owners, including fields of returned records, retain cleanup.
Native statement legalization also uses a writable initialization slot for
conditional const declarations; source constness remains checked normally.

An independent hosted-built native driver compiled the updated compiler
sources, followed by native-built driver generations. Five paired x86-64/C
groups pass (145.03 seconds), covering array selections, set algebra, ordinary
conditional moves, named projection loans and record argument loans. Focused
hosted runs and 50 adjacent dictionary/set checks also pass. Mutation, owning
return, oversized frame arms, aliasing inputs, effectful later operands and
repeated-call allocation/retained-storage cases are included. Four fixtures
extend the full manifest to 348; full frozen integration remains certified at
`07335a43` until the next complete run. Compiler-wide strict adoption is still
open; these proofs do not authorize unreported copies or added explicit-copy
annotations solely to meet a count.

Checkpoint (2026-09-28): frozen revision `07335a43` passes all 344 paired
compiler acceptance/execution cases. Its native integration build reaches a
three-generation identical fixed point; generations two and three take 54 and
57 seconds under concurrent validation load. These results certify that
revision, not later working-tree edits. The parity tool and fixtures were run
from the frozen checkout so relative bootstrap imports use the same revision.
The expanded strict-policy inventory still has 2,152 nonexplicit runtime-sized
copy obligations in 93 bootstrap modules; compiler-wide adoption remains open.

Checkpoint (2026-09-28): resource liveness retains symbolic identities for
unchanged integer inputs and proposes ordinary checked disjointness assertions
when move-only array components would otherwise overlap. The final bounds pass
must prove these assertions after implicit lifecycle effects are installed;
unknown separation never authorizes a transfer. Cleanup retains each actual
selector and presence flag. Mutated/exposed/captured inputs, arbitrary selector
expressions, possibly overlapping selected stores and whole-owner reads keep
the conservative path. Copyable values retain their existing copy fallback.
This first selector boundary covers function inputs, not arbitrary later locals.
Sixteen hosted cases, 28 surrounding hosted checks and five paired x86-64/C
groups pass (96.03 seconds). Cases cover ordering and disequality guards,
fixed/runtime index combinations, nested fields, conditional transfers, three
independent slots, later reads/replacements and repeated-call retained storage.
The native driver was rebuilt from the updated sources for these paired checks.

Checkpoint (2026-09-28): independent hosted bootstrap validation exposed a
regression in union member injection: a generated array load from a dictionary
was mistaken for a fresh call result, allowing its stored descriptor to be
emptied. Lookup now names that borrowed handle before the value boundary and
reports its snapshot once. Nine lookup/view/optional-dictionary checks pass.
A fresh complete hosted-built native compiler succeeds (143.24 seconds checking,
38.72 lowering, 4.57 emission, 22.84 backend) and executes the repeated-lookup
regression successfully. Existing native-driver tests alone did not exercise
this construction path; independent hosted builds remain an integration gate.

Checkpoint (2026-09-28): hosted direct calls now share native's ownership
protocol for ordinary record inputs whose sole unconditional use donates them
to array push/insert or another proved input. A dependency worklist starts at
actual consumers; forwarding cycles alone establish nothing. Function values,
captures, defaults, conditional/repeated uses and lifecycle records retain
their existing protocols. Owning record parameters also participate in ordinary
last-use field transfer, keeping caller snapshots and callee cleanup consistent.
Seven positive cases and five rejection cases pass in both compilers on
x86-64/C, including a twelve-helper chain, keyword calls, retained views and
repeated-call memory counters. The complete compiler source passes hosted
policy checking. This closes a hosted acceptance gap without introducing a
source ownership annotation. The surrounding ownership/copy suite passes all
146 checks (501.68 seconds); the fresh hosted-built native compiler also
passes the consuming-input fixture through the parity runner.

Checkpoint (2026-09-28): hosted union payload injection now reports ordinary
member copies, including optional results, iterator elements and fixed arrays
with dynamic components. These copies previously bypassed `$explicit_copies`.
Explicit snapshots retain one policy entry; last-use record/array locals can
use the existing field/descriptor transfer, and a narrowed owned optional can
transfer its exact-layout payload back into a union. The emptied original cell
retains its lexical cleanup. Live sources, family conversions and prepared
frame trees keep their copy obligations. Five focused hosted positive cases and
four rejections, 124 surrounding hosted checks, and a further 80 checks after the
narrowed-payload change pass. Paired execution covers payload survival and
retained-byte counters; all three paired injection/local-move/widening groups
pass. The complete compiler source also passes hosted policy checking.
`key_facts.dewy` passes strict mode in both compilers,
bringing adoption to 39 physical modules.

Integration at `bff02558`: three native generations reached an identical fixed
point (generations 2/3: 53/58 seconds under concurrent validation). A fresh
hosted-built driver passed all 52 capture tests. The full manifest passed
337/338 cases: both compilers correctly rejected the raw-exposed global's stale
length proof in `startup_storage_exposure`. That fixture now establishes the
current extent before indexing, and its unguarded form is an explicit rejection
regression. This is a corrected fixture expectation, not a weakened proof rule.

Checkpoint (2026-09-28): nonescaping, read-only local functions can borrow
enclosing resource owners and local places. Capturing a place retains its loan
through the enclosing scope, including dependent aliases and default arguments;
owner relocation, raw exposure, writes through captures and escaping function
values remain rejected. Captured owners stay in their enclosing cleanup list:
the lifted callee borrows them, and must neither drop nor consume them. This
also fixes native leaks of captured arrays and records. Twenty paired positive
cases and twelve paired rejections pass, plus surrounding dictionary places,
resource views, partial records and iteration checks. Repeated-call kernels
check retained bytes, lifecycle counts and returned aggregate survival. These
checks extend the implemented capture boundary; they do not implement escaping
or writable closures.

Checkpoint (2026-09-28): deferred local functions no longer inherit stale
numeric facts about mutable captures. Previously a function declared while a
captured divisor was nonzero (or an array nonempty) could retain that evidence
after the caller changed it. Both analyzers now expire mutable captured value
and route facts at function entry, preserving unchanged array extents when
only elements can change. Scalar snapshots, declared storage contracts and
local guards retain their normal proofs. Expression/predicate metadata stays
inside the function's analysis, including defaults. Eight rejection cases and
nine positive cases pass in both compilers on x86-64/C; 80 surrounding hosted
checks pass. Native lowering also accepts the complete compiler source with
the corrected fact rule. The parity manifest adds the stale-divisor rejection.

Integration at `eae8789e`: three native generations reached an identical
fixed point (generations 2/3: 53/60 seconds under concurrent validation).
All 335 parity cases passed. A separately hosted-built driver passed all 28
strict-unused-body and local-union-widening tests (365.21 seconds including
its build). This predates the capture changes and does not close Phase 1.

Checkpoint (2026-09-28): strict-copy obligations now survive unused-function
and unused-import pruning. Native graph assembly retains strict bodies and
their dependencies through lowering, then follows lowered runtime references
to omit unreachable functions. Hosted module assembly likewise retains strict
imported bodies for lowering, matching its existing entry-module behavior;
µDewy removes their unreachable executable code. Callback values, recursive
components, defaults and generated helpers keep their dependency edges.

This exposed two previously hidden source cases. The optional parser token
report now explicitly snapshots its borrowed pointer array into the owning
Report; it remains a visible diagnostic-path copy, not a new loan proof.
The unused `forwarded_values` compatibility wrapper was removed from both
implementations; all callers already consume the complete `prove` result.
The full compiler source passes both hosted analysis and native lowering with
all 38 strict modules checked, including unused bodies. The 47 strict-policy
and required-view checks, two imported-dependency cases and a paired token
report regression pass. The parity manifest now contains 335 cases; fresh
full integration for this checkpoint remains separate.

Checkpoint (2026-09-28): a last-use owned union local can widen into a union
with more alternatives while preserving the active payload's representation.
Hosted lowering moves the payload and empties the source cell; native lowering
acquires ownership once before converting, reusing its normal last-use rule.
Live values, retained views, repeated-loop uses and incompatible layouts retain
copies; explicit copies remain explicit. Thirty-one hosted checks and five
paired x86-64/C groups pass, including lifecycle and family-layout regressions,
large bigint alternatives and retained-byte counters across repeated calls.
Another 32 hosted family-layout/array/lifecycle checks pass.

This batch also exposed a strict-policy coverage gap: native graph assembly
can discard unused functions before checking their implicit copies, unlike
hosted lowering. Reachable rejection/value-independence cases are verified;
unused-body strict checking is the next corrective step. Test selections now
use exact native-test exclusions where needed: `-k 'not native'` also matches
that substring inside parametrized source text such as "alternatives".

Checkpoint (2026-09-28): hosted union argument conversion now consumes the
existing scope-borrow evidence for stable local owners, matching the native
call planner. Every known target must be read-only, later arguments and live
places must preserve the route, and raw/external aliases or possible owning
parameter protocols keep the ordinary copy. This is a lowering proof, not a
new public effect promise. Focused checks include narrowed optional bigint
fields, keyword calls, large values and later writes that must see a snapshot.
Ten focused checks (including a repeated zero-allocation kernel), both paired
x86-64/C groups, and 67 adjacent ownership/length checks pass.
`length_proofs.dewy` also solves the requested
shifted gap directly, avoiding a negated-bigint temporary; it passes strict
copy checking standalone in both compilers. Adoption reaches 38 physical
modules, without adding explicit-copy annotations to hide a missing proof.

The fresh hosted-built driver at `b934932d` passed all 42 weighted-invariant,
linear-candidate and named-projection checks (331.03 seconds including its
build). The newer `47e15597` reached a three-generation native fixed point,
with generations 2/3 taking 49/54 seconds under concurrent checking. Its
complete 331-case parity run passed. These are separate checkpoints;
Phase 1 remains open.

Checkpoint (2026-09-28): fixed temporary record arguments can lend stable
array handles and scalar fields to a known read-only callee that only projects
the root. The shared call-specific proof controls public allocation effects
and both lowerers; the root owns no fields and is reused across loop iterations.
Scalar field evaluation and defaults retain their effects. Fresh aggregate
fields, different layouts, lifecycle values, unknown callbacks, conflicting
writes, whole-root forwarding and more than 4 KiB of call roots per function
retain ordinary storage obligations. This adds no source syntax or ownership
exception. Twenty focused checks, including paired x86-64/C execution, and
125 surrounding hosted checks pass. Kernels check zero allocation, returned
array independence, a 200,000-iteration loop and both sides of the root budget.

Checkpoint (2026-09-28): constructor-private field bindings now participate
in lexical storage/effect inventories, including parameter default expressions.
A later field default reading an earlier field is private to its construction;
nested functions still treat captured fields as external. This removes false
ambient-effect/copy obligations without hiding actual globals or mutation.
Hosted checks cover nested defaults, structural literals, globals and captures;
paired execution also checks zero allocation across repeated calls.

Integration at `b934932d`: three native generations reached an identical
fixed point, with generations 2/3 taking 47/51 seconds under concurrent load.
The complete native inventory reports 4,112 copy sites (2,901 records, 562
arrays, 649 cells), within the 4,500-site gate. All 329 paired cases passed;
this checkpoint does not close Phase 1.

Checkpoint (2026-09-28): a separate finite weighted-sum domain now carries
invariants such as `2*i<=j` through unequal counter steps. It shares entry,
join, widening, affine-update, alias invalidation, scope retirement, snapshot
and array-length transfer rules with the existing fact store. Scalar locals
and named record fields use one checked affine rule, including the arithmetic
width before conversion to the destination. Normalized queries retain named
terms even when their current interval is exact. Arbitrary-precision weights
participate in structural identity; native hash collisions compare complete
coefficients. No source assumption is introduced by candidate discovery.

The source vocabulary selects at most 32 weighted rows per loop. Each state
retains at most 128 including derived copies: otherwise aliases of a many-term
fact can generate exponentially many combinations. Exhaustion contributes no
proof, and expired rows release capacity. Hosted/native fact-state comparisons
cover joins, widening, invalidation, length changes, vacuity and collisions;
paired x86-64/C tests cover counters, snapshots, record fields and wrapping
rejection. Focused hosted runs pass 45 field/affine checks, 72 surrounding
linear/snapshot/route checks, 32 state/convergence checks, and 16 weighted/budget
checks. A fresh complete bootstrap/parity checkpoint is still required for
this batch; Phase 1 remains open for the other checklist items.

Checkpoint (2026-09-28): bounded linear source queries now select difference
candidates for loop checking. For example, `2*lower<=?2*upper` selects the
`lower`/`upper` pair even when neither variable has an exact initial value in
the selected group. Selection uses literal scaling, addition and subtraction,
with 128 expression visits, 32 terms and the existing shared 64-pair loop
budget. Entry intervals and every advancing edge establish the actual facts;
wrapping, unknown calls and failed candidates retain conservative behavior.
Twelve focused hosted checks and two paired x86-64/C groups pass, including
multi-term sums, 70 unrelated counters, continue paths and rejection of
invalid entry/backedge/wrapping/nonlinear obligations. These remain ordinary
difference qualifiers, not general coefficient-weighted invariant facts.

Checkpoint (2026-09-28): naming a stable parameter projection now preserves
its storage evidence when forwarding the name or a descendant to a known
read-only callee. Local views use the same field-access permission as direct
argument forwarding: an unrelated sibling write need not invalidate the view,
while overlapping writes, captures, escaping places and unknown callbacks keep
their ordinary copy/allocation obligations. Allocation contracts and both
lowerers consume this shared proof. Thirteen hosted acceptance/rejection checks and
two paired x86-64/C groups pass, including a repeated zero-allocation kernel.
Projection chains use a dependency worklist: each candidate waits for its
named owner, so cycles and unknown owners cannot seed a proof. Other owner
classes remain conservative.

Integration at `4361396c`: three native generations reached an identical fixed
point, with x86-64/C pipeline execution checks. Generations 2/3 took 49/52 seconds
under concurrent checking. All 326 parity cases passed. The broad hosted selection passed 4,715 tests
with 13 skips in 1,874.04 seconds; the named-projection changes postdate
that frozen source checkpoint.

Checkpoint (2026-09-27): hosted tagged locals now transfer their owned
payload at a proved last use into a return, binding, record field, or array
element, matching the native path. The tag cell retains its frame lifetime;
its payload is emptied on the consuming edge so lexical cleanup cannot
release the new owner's value. Live inferred views, later reads, repeated
loop uses, explicit snapshots, and payloads containing prepared frame trees
retain ordinary copying. This closes the strict-copy gap in
`invocation/update.dewy`, bringing adoption to 21 physical modules. No
explicit-copy annotations were added to work around missing proofs.
Validation: 95 hosted surrounding checks and the paired union-transfer
group pass on x86-64/C, including zero retained bytes over 200 calls. A
fixed-array payload regression caught an overbroad optional-cell transfer
during development; frame-dependent payloads now retain the layout copy.

Integration checkpoint at `0bcab4b0`: three native generations reached an
identical fixed point; all 227 paired cases passed. A separately rebuilt
hosted native driver passed 50 focused getter, join, qualifier, partial-hook,
and constant-slot checks. Builds took 49 and 55 seconds for generations 2
and 3 during concurrent checking; these are correctness evidence, not
isolated throughput measurements. The union-transfer changes above postdate
that checkpoint and have their own focused paired checks.

Checkpoint (2026-09-27): hosted storage borrowing now distinguishes installed
assertion-reporting calls from source evaluation, matching native
`RuntimeFailure` handling. The compiler's diagnostic allocator/I/O support
does not force snapshots of unrelated source arrays. Messages and diagnostic
operands still contribute their ordinary effects; explicit source calls to
reporters remain ordinary calls. This exclusion is specific to borrowing:
public effect inference and other global-write consumers still see report
implementation effects. A pure place selection from the same record can
also preserve the existing proof that two sibling fields are disjoint;
effectful selectors and other possible ambient aliases remain conservative.
`semantic/container_values.dewy` now passes `$explicit_copies` standalone in
both compilers, bringing adoption to 22 physical modules. Validation: 156
hosted surrounding checks, paired execution on x86-64/C, a zero-allocation
guarded-reader kernel, and failed-assertion messages that mutate their source
while still observing the original snapshot.

Integration follow-up (2026-09-27): `450bd71a` reached a three-generation
native fixed point, but its freshly hosted-built driver crashed in parser
cleanup. Whole-cell last-use evidence had also marked a narrowed array
payload as an array-owner binding. Array transfer then treated the tag cell
as a descriptor and cleared the cell pointer. The move analysis now keeps
those representations distinct: taking a narrowed payload requires a
separate proof and currently retains its ordinary copy. Thirteen hosted
union-transfer checks and the paired native group pass, with new narrowed
return and record-field regressions. A fresh hosted-driver rebuild at
`e4263c30` subsequently passed all 21 focused union-transfer and reporting
borrow checks (332.19 seconds including the build), closing that regression.

Checkpoint (2026-09-27): both storage-exposure scans now include module
initialization as well as function bodies and defaults. Previously an address
saved during startup could mutate a global array while a later value call
incorrectly borrowed it. Source snapshots now remain independent in that
case; mutable-local-place validation consumes the same corrected inventory.
The native scan visits the combined roots once per HIR node. Hosted borrowing
also now recognizes unexposed `const` module owners as stable, matching the
existing native rule. Required/inferred record and dictionary views can use
their process lifetime; raw exposure still prevents that proof. Validation:
103 hosted surrounding checks, paired startup-exposure/const-view groups on
x86-64/C, and a zero-allocation repeated const-table lookup kernel. The
`syntax.dewy` BaseInfo lookup now borrows, but that module still has a separate
union-result conversion copy and is not marked `$explicit_copies` yet.

Checkpoint (2026-09-27): a fresh ordinary call's union result now widens by
transferring its payload when the active members keep identical tags and
owned-handle layouts. The same cell-transfer operation handles unchanged
union results. Family conversions and prepared frame trees retain their
layout copy; this does not add borrowing or a new source operation.
`semantic/syntax.dewy` now passes `$explicit_copies` standalone in both
compilers, bringing adoption to 23 modules. Validation: 61 surrounding hosted
checks, plus the paired widening group on x86-64/C, including array/record
payloads, container insertion, fixed-layout conversion and zero retained
bytes over repeated calls.

Checkpoint (2026-09-27): projecting an enclosing field contract onto a
descendant now preserves the complete proposition in both analyzers. Only
the subject and its projection change; the bound's value/length projection,
resolved identities, tested type, condition and address-space provenance
remain intact. The native HIR fixture generator also distinguishes ordinary
calls from hosted-only installed reporting calls. Validation: the native
HIR projection/effect comparisons and five surrounding hosted refinement
checks pass (seven checks total).

Integration at `cabf68ec`: three native generations reached an identical
fixed point. A separately hosted-built driver passed all 35 focused union,
reporting-borrow, startup-exposure, const-owner and widening checks. The
broader hosted selection passed 4,249 checks with 13 skips; all 232 paired
manifest cases passed. Generation 2/3 builds took
62/87 seconds under concurrent test load, not isolated timing measurements.

Checkpoint (2026-09-27): hosted lowering now uses last-use evidence when a
local record enters an array literal, push/insert, or indexed replacement.
The destination receives an arena-owned root; owned strings and dynamic
array fields transfer using the same clearing protocol as record returns.
Local cleanup remains valid on paths that retain the source. Prepared trees,
aggregate union fields, inherited extra layouts and borrowed fields retain
their conservative copy. This matches the native path for the newly covered
shapes. Validation: nine hosted cases, the paired x86-64/C group and 40
surrounding hosted checks pass. Tests include retained views, repeated-loop
uses, COW snapshots, fixed-layout fallback and zero retained bytes over 200
branch calls. `binary_literals.dewy` now moves its diagnostic Pointer locals;
its remaining narrowed-array payload copy still prevents strict adoption.

Checkpoint (2026-09-27): narrowed runtime-array payloads now have a distinct
last-use transfer marker in hosted lowering. The transfer takes the array
descriptor and clears only the owning cell's payload, never interpreting
the cell itself as an array or clearing its address. Returns, bindings,
record/array stores and reinjection into a union share that operation.
Repeated-loop uses and live views retain snapshots. Nested array stores
also now report their fallback copies, closing a strict-policy reporting
hole. `semantic/binary_literals.dewy` passes `$explicit_copies` standalone
in both compilers, bringing adoption to 24 physical modules. Validation:
ten focused hosted checks, paired x86-64/C acceptance and execution, and
50 surrounding hosted checks pass. A paired counter kernel proves zero
allocation for a narrowed payload binding and zero retained bytes over
repeated calls. These changes postdate the full `cabf68ec` integration above.

Checkpoint (2026-09-27): the same element-transfer sites now consume ordinary
owned runtime arrays at last use, matching native lowering. Borrowed locals
remain ineligible; retained views and repeated loop uses still require the
newly reported snapshot. The owned-storage classification uses one HIR
walk for records, cells and arrays. Validation: paired acceptance/execution
on x86-64/C, 20 record/payload/counter checks and 26 surrounding hosted checks
pass. A reserved row container takes a COW-backed array descriptor with
zero allocation at insertion, preserves its explicit snapshot and retains
zero bytes over 100 calls.

Integration at `0b24cedc`: three native generations reached an identical
fixed point, a fresh hosted-built driver passed all 35 record/payload/union
checks, and all 235 paired manifest cases passed. Generation 2/3 builds took
53/56 seconds under concurrent checking. The ordinary-array element changes
above have separate focused checks and postdate this isolated checkpoint.

Checkpoint (2026-09-27): stable dictionary/set entry properties now lend
their original entries directly to single and combined iterators in both
lowerers. The existing whole-function storage proof must establish source
stability; ordinary property values and loops that mutate their source keep
their snapshots. Selectors still evaluate once, and lifecycle lowering
continues to own hook invocation and resource snapshots. This removes the
temporary key set and entry arrays in `semantic/builtins.dewy`, which now
passes `$explicit_copies` standalone in both compilers (25 physical modules).
Validation: five hosted cases, paired x86-64/C iteration and lifecycle groups,
26 hosted lifecycle checks and 49 surrounding iterator/dictionary checks
pass. A paired counter kernel repeatedly iterates scalar/record dictionary
values, dictionary keys and set values with zero allocation after warmup.

## Strict-copy cleanup

The inherited uncommitted CLI-only `$explicit_copies` implementation was
removed on 2026-09-20, with its patch and tests archived under
`../dewy-build-artifacts/phase1-2026-09-20`. It depended on incomplete copy
notes, bypassed non-CLI compilation, and prescribed remedies that did not
yet exist. This abandons that partial implementation, not the approved
directive. Reintroduce the policy with the relevant semantic/lowering API,
explicit remedies, source provenance, and acceptance-parity tests. Existing
`dewy analyze` copy reports remain available.

## Validation discipline

Checkpoint: uniform set insertion is implemented in both checkers as
`set.push(value)`, with the old `add` spelling retained as an alias. Both
spellings use the same insertion and mutation rules. Hosted tests cover
execution and rejection of const mutation; the native compiler executes
the shared fixture with its expected result 42.

Checkpoint: both bounds analyzers compose transfers for small, statically
finite loops before falling back to widening. A shared exploration budget
bounds nested work; every reachable body entry participates in validation,
and break/continue exits are retained. This closes `nat_types` without
changing its expected result. It also carries exact array growth through
small fixed loops; general symbolic loop induction remains outstanding.
Comparison narrowing now retains observed field bounds when excluding a
value, so a nonnegative field unequal to zero is positive in either operand
order. Targeted checks passed, and a second-generation native compiler passed
all 11 cases in `tests/fixtures/phase1_parity_cases.json` against the hosted
compiler. The broader corpus passed 210/211 cases and exposed a native `$prototype`
builtin-identity mismatch: registered builtin arithmetic was mistaken for a
user-defined function. The corrected native compiler runs `prototype_panic`
with the expected panic status 102 and still rejects the shadowed-intrinsic
regression. Both cases are now in the focused manifest. A fresh full paired
run remains required at the next integration checkpoint.

Each implementation batch needs acceptance/rejection and independent
execution outcomes, with hosted/native agreement. Ownership batches also
need second-generation native execution. Run complete build/fixed-point
checks at integration checkpoints, not for every small edit. Maintain
separate timing rows for C-built and direct-built executing compilers;
30 seconds is the minimum native target and 10 seconds the stretch goal.

Checkpoint: explicit `.copy()` for arrays, records, dictionaries, and sets
is represented in HIR and both lowerers, with receiver evaluation once and
independent mutation. Existing record members named `copy` take precedence.
Copied numeric, length, and membership facts belong to the destination; an
inferred record initializer now seeds its field facts in both analyzers.
Copy notes carry an explicit-intent flag for the later enforcement policy.
The operation participates in hosted representation discovery and definite
initialization; owned and discarded temporaries are released, including
array results returned through another copy. The lifetime kernel reports
zero retained bytes over 100 repeated calls in both compilers. The native
second-generation compiler built in 48.63 seconds; the C-built seed's first
generation took 21.71 seconds. This remains above the direct-route target.
Hosted copy/report gates passed 11 tests. All 14 focused parity cases
passed against the second-generation native compiler, including independent
expected panic diagnostics; the fresh full 211-case corpus also passed against that compiler.

Design review: `PHASE1_DESIGN_PROPOSALS.md` separates reviewed proof/effect
direction from outstanding proposals. David approved `$proof` with direct
statement calls, checked termination/purity and erasure; `:> <P>` is proof-
only, while ordinary functions use `:> T & <P>` (including `void`). The
unsafe boundary is `$unsafe_assume cond [, message]`. Positive effect rows
are upper bounds, omitted rows are inferred, and `no_effects` is the preferred
empty-row spelling. Negative guarantees (`no reads<resource>` and `no reads`, rejecting empty
family arguments) are also approved. Effect identity declarations and
effect-parameter syntax still have details to review. Implementation is
pending; approval does not mark 1.2 or 1.3 complete.

Checkpoint: callable/numeric unions at juxtaposition now reject with the
explicit pipe-call and multiplication forms in both compilers, without
suggesting parentheses. A numeric token on the right starts a separate
expression. Coefficient multiplication and parenthesized calls retain their
distinct precedences. Hosted parser/semantic/ownership gates passed 67 tests;
a rebuilt native compiler rejects the ambiguous-union fixture and runs the
precedence fixture with result 42.

Checkpoint: loop analysis now proposes a bounded equality vocabulary from
exact entry values of changing bindings and their field/length routes. The
ordinary loop fixed point must preserve each candidate on every backedge;
branch and early-break exits still join their actual facts. Constant scalar
shifts transform both sides of order relations, preserving negative gaps
between matching increments. This proves parallel-array length equality and
length/counter growth through unbounded trip counts. Missing pushes and
early breaks reject. Ten targeted proof tests and all 21 focused parity
cases passed. The updated compiler builds using the preceding direct native
compiler (50.12 seconds); the second-generation build also took 50.12 seconds
and passed all 21 focused parity cases. Its fresh full corpus also passed
all 211 cases against the paired hosted snapshot.
The wider symbolic range-iterator and proof-boundary work remains pending.

Checkpoint: hosted descriptor-backed array locals now use the existing
stable-route borrow proof already used by native lowering and hosted record
locals. Read-only field reads allocate zero bytes across 100 calls. A source
or destination write keeps value independence, and returning the local or
storing it in a returned record still acquires independent storage. Twenty-
one ownership gates passed, with the escape kernel checked separately on
both direct and C backends. The shared native parity fixture also passed.
Explicit local `@` demands and mutable local places are still outstanding.

Checkpoint: explicit string `.copy()` now participates in both checkers and
lowerers. Returning a copy, storing it in a record or array, copying a fresh
result, and discarding a copy all retain the normal owner-word lifetime
rules. Copy notes distinguish explicit string copies; static strings and
fresh owned results can still avoid a physical clone. Twenty-six hosted
string/ownership checks passed, followed by all eight explicit-copy tests
including the string report check. The native lifetime fixture retains zero
bytes across 100 calls, and all 22 focused parity cases passed against a
new second-generation compiler. General union copies and strict-copy
enforcement remain outstanding.

Checkpoint: both parsers canonicalize digit labels (`x_12`, `x_1_2`, and
`x₁₂`; `x‾12` and `x¹²`) and the micro-sign/mu alias at t1, preserving t0
source text and spans. Letter labels and ASCII/Greek distinctions remain.
Hosted synthesized names that round-trip through Dewy source use suffixes
stable under normalization. Hosted emission encodes non-ASCII names without
colliding with source-written ASCII names, including calls and debug metadata;
native lowering does the same for descriptive debug symbols while retaining
its ordinary binding-id symbols. No µDewy syntax changes. Twenty-one token
checks, 15 t1 parser parity cases, and 48 hosted execution/synthesis/debug
checks passed. A rebuilt native compiler passed all 23 focused parity cases
and both ordinary and debug execution of the identifier fixture (42).
The direct seed built it in 55.82 seconds. The wider Unicode repertoire and
doubled-marker escape remain open, and no rule for them was introduced.

Proof-boundary prerequisite: hosted `:> void & <P>` now checks its facts at
each explicit return and fallthrough without expecting a runtime value from
the body. Native checking already handles this form. Both type displays
retain `void &` so ordinary function contracts are not printed as proof-only
`:> <P>` syntax. The fact-bearing procedure fixture mutates an empty array
and returns 42 in the native compiler; the hosted fact suite passes 25 tests.
The separate `$proof` marker and statement-call checks are still in progress.


Checkpoint: the initial `$proof` boundary is implemented in both compilers.
Proofs have explicit HIR/binding identity, fact-only returns, direct statement
calls, pure arguments, finite bodies and an acyclic call graph. They erase
only after validation; callbacks, first-class values, mutation/effects and
`$prototype` deferral are rejected. Named and keyword-only parameters and
imported proofs retain their contracts. Native snapshot codecs preserve the
new metadata. `$unsafe_assume` and source effect rows remain pending.

The same work fixes general fact-contract rules: dependent arguments are
checked after substitution (including literals), known order relationships
can settle assertions, and mathematical affine evidence is not inferred
from possibly wrapping word arithmetic. Native empty void procedures now
check fallthrough obligations. Replacing a nominal record in a loop no
longer reinstalls the first variant's field type on exit.

Validation: 109 hosted proof/fact/call/prototype tests, two native type and
comparison harnesses, 20 direct native acceptance/rejection cases, and all
33 focused parity cases passed. A native compiler rebuilt itself in 59.94s;
a subsequent native generation with the keyword-only contract fix built in
62.50s and executed the composed proof and variant-loop fixtures (42).
These are integration timings, not a claim to meet the under-30s target.
The wider 211-case paired corpus is running at this checkpoint.
Artifacts: `../dewy-build-artifacts/phase1-proofs-stage2-2026-09-20` and
`../dewy-build-artifacts/phase1-proofs-final-2026-09-20`.


Full-corpus follow-up: 208/211 paired cases passed. The three failures
(`place_slots`, `type_values`, `length_terms`) all exposed an identifier
normalization gap in native generated dispatch helpers: parser-normalized
`__dewy_brand₀` did not find its raw `__dewy_brand_0` alias. Hidden aliases
now use the same t1 canonicalization as their generated source. A fresh
native build (59.24s) executes all three with result 42; they are also in
the focused parity manifest. This fix changes synthesis lookup, not user
identifier semantics. Artifact: `../dewy-build-artifacts/phase1-synthesis-2026-09-20`.

Checkpoint: initial `$unsafe_assume cond [, message]` support now lands in
both compilers. Pure unknown facts enter the normal mutation-aware state;
the condition is erased, messages are static, and checked proofs cannot use
unchecked assumptions. Source audits survive folded conditions, unused
checked functions and prelude caching. Ordinary, debug and test builds write
versioned `.unsafe.json` sidecars; analysis also displays them. Empty reports
replace stale ones. Consumer coverage is deliberately conservative: checks
in the same function, not exact proof-dependency provenance. That refinement
remains required for the full audit milestone. Known contradictions are
explicitly unsupported while their policy is under design review.

Validation: 43 hosted unsafe/proof tests, 30 prototype/fact regressions,
eight native acceptance/rejection and JSON-escaping checks, and all 39 focused
paired cases passed. The native seed built the updated compiler in 60.04s;
this is an integration checkpoint, still above the performance target.
Artifacts: `../dewy-build-artifacts/phase1-unsafe-2026-09-20`.

Checkpoint: explicit `.copy()` now accepts unions whose alternatives have
builtin value-copy semantics, without hiding a declared `copy` member. Only
the active payload is copied, the receiver is evaluated once, and destination
stores can consume the snapshot directly rather than copy an extra temporary.
Both general tagged unions and optional aggregates retain normal ownership.

Validation: 60 hosted ownership/copy checks passed, including C execution,
member precedence, single receiver evaluation and zero retained bytes across
repeated mixed-alternative snapshots. Native generations built in 60.64s and
60.14s, both running the lifetime fixture with zero retained bytes and exit
42. All 41 focused paired cases passed against the second generation.
Artifacts: `../dewy-build-artifacts/phase1-union-copy-stage2-2026-09-20`.

Naming review: the source form is `$unsafe_assume cond [, message]`, replacing
the intermediate `$unsafe_assert` spelling. Unknown assumptions are accepted
and audited; proven-false assumptions are rejected, including contradictions
from a guard or a declared width. The optional message and all mutation,
erasure and proof-body restrictions remain unchanged.

Validation: 47 hosted assumption/proof checks passed. A fresh native compiler
built in 60.38s, executed the assumed-index fixture (42), rejected literal,
guarded and width-derived contradictions, and rejected the superseded spelling.
Artifacts: `../dewy-build-artifacts/phase1-assume-2026-09-20`.

Checkpoint: copy inventories now include hosted local array snapshots in
both raw stack and descriptor representations; the view/ownership kernel
reports four sites in both compilers (two escapes and two independent mutable
snapshots), with no copy for the read-only local. Native summaries now count
string copies too. `tools/copy_report.py --max-copies N` provides a static
site-count gate, and `--json` saves a versioned inventory. The tool rejects
malformed, partial or summary-inconsistent output before filtering files.
This verifies report transport, not completeness of all lowering paths;
additional coverage and compiler-wide budgets remain outstanding.

Validation: 18 hosted reporting/explicit-copy checks passed. Both hosted and
native inventories passed `--only readonly_array_field_view.dewy --max-copies 4`.
The native executable was the reviewed-assumption checkpoint, which already
contains the summary correction. Runtime allocation gates remain distinct
from these static site budgets.

Checkpoint: abstract range counters can now use inductively proved word
storage in both compilers. The proof covers the initial value and every
normal/continue backedge, including step headroom and nested bounds learned
from an outer counter. Failed candidate bounds are discarded before normal
validation; neither a circular assertion nor `$prototype` can justify wrapping
an otherwise unbounded counter. The native backend now rejects an unproved
unbounded numeric iterator instead of silently using word arithmetic.

Validation: 88 hosted range/loop checks, the native bounds harness, seven
native overflow/continue/circular-proof rejection checks, and all 45 focused
paired cases passed. Native generations built in 62.99s and 59.59s; both run
the nested-counter fixture with result 42. General bigint iterator lowering
and broader liquid inference remain open.
Artifacts: `../dewy-build-artifacts/phase1-counters-stage2-2026-09-20`.

Checkpoint: both compilers now check source `no_effects` and its desugared
`Effect<>` form. Public rows live separately from internal parameter-access
summaries and participate in callable subtyping, signature substitution,
native type interning and prelude serialization. Callback parameters also
accept the reviewed `f:(args):>Result & no_effects` shape. Unknown callback
behavior cannot satisfy the empty row. Defaults and direct-call dependencies
are included; purity does not imply termination.

The initial inference subset covers scalar computation, private scalar
mutation and read-only value access. Unsupported storage operations remain
unknown; returning a runtime-length `.copy()` cannot claim purity just because
COW may defer its allocation. Named source effects, negative source guarantees,
row generics, complete inferred callable rows, and a complete allocation model
remain outstanding. The native checker skips this pass when its type arena
contains no effect contracts.

Validation: 93 focused row/contract/proof/access checks and 53 signature,
generic, runtime-key and native type-factory regressions passed. Both native
generations execute the callback/private-mutation fixture (42); 19 native
acceptance/rejection probes and all 48 paired cases passed. Integration builds
were 64.11s and 69.42s, with other checks running concurrently; these are not
isolated performance measurements or a new fixed-point certification.
Artifacts: `../dewy-build-artifacts/phase1-effects-stage2-2026-09-20`.

Checkpoint: verified the settled unit-like nominal value rule across both
backends and compilers. The execution fixture returns ordinary/error sentinels
through unions, tests their types, passes their sole values as arguments and
preserves identity through imported aliases. A separate empty mint with the
same name remains distinct. This closes the Phase 1.4 verification item without
changing the language or its runtime representation.

Validation: 12 hosted nominal checks, x86/C execution, and execution with the
second-generation effect-contract compiler returned the expected result (42).

Checkpoint: the six reviewed names (`extern`, `intrinsic`, `none`, `void`,
`end`, `new`) are now reserved in source bindings in both compilers. The
check covers declarations, parameters, fields, methods, loop/unpack targets,
generic binders and import aliases. It distinguishes binding patterns from
match type patterns, so `<none>` remains valid; synthesized last-index bindings
also retain their existing role. `untyped` remains available to users.
Compiler/library locals and fields now use ordinary names (`limit`,
`intrinsic_call`, `replacement`, etc.). This changes the string replacement
keyword argument from `new` to `replacement`; positional calls are unchanged.
It reserves `new` without implementing the later axis-insertion feature.

Validation: all 104 reserved-name checks passed, including a Dewy validator
harness over 96 binding forms and x86/C execution. The related text/source-line
and fact regressions passed (108 checks); dependent-index and brand tests also
passed. Native generations built in 62.55s and 62.79s, both running the role
fixture with result 42. All 52 focused hosted/native paired cases passed.
Artifacts: `../dewy-build-artifacts/phase1-reserved-stage2-2026-09-20`.

Effect-cache follow-up: a typed snapshot now explicitly exercises nonempty
public permissions, a parameter-route exclusion, a symbolic row binder, an
empty row and an omitted row. Decode preserves each contract and re-interns
the signature at its original id. Three cache checks passed, including x86/C
execution and regeneration freshness. This verifies the IR/cache foundation;
it does not claim source support for named rows or row generics yet.

Named-effect checkpoint: both source checkers now resolve nominal resource
identities, caller-owned place slots and stored-field routes. Positive
`reads<Resource>` / `mutates<Resource>` rows are closed upper bounds;
`no reads<Resource>` and whole-family `no reads` retain open negative
guarantees. Empty family applications diagnose the distinction. Signature
display preserves rows, including exclusions. The new `no` prefix is confined
to effect contracts; old compiler/test locals named `no` are `false_value`.

Public analysis now substitutes place routes at direct and callback calls,
checks scalar place reads/writes, and preserves shared negative guarantees
across call-graph propagation. Taking an address does not itself read its
contents. Private scalar storage disappears at a call boundary, while unknown
operations and unproved aggregate transfers remain conservative. Recursive
routes widen only positively; truncating a negative route would be unsound.
Hidden method receivers shift effect slots, and binding a receiver does not
silently erase its possible effects. Row generics and full allocation/failure
modeling are still outstanding.

Validation: 85 focused row/contract checks passed, including x86/C execution;
21 method/function-value regressions passed. Three related native-analysis
harnesses also passed. Native source gates passed all 42 initial cases and
12 additional boundary cases (position-only parameters, method-slot identity,
malformed rows, and use of `no` outside contracts). The final native generation
built in 59.49s and executed the imported-resource/place fixture with result
42. This is a correctness checkpoint, not the sub-30s performance target.
Artifacts: `../dewy-build-artifacts/phase1-named-effects-stage3-2026-09-20`.
All 55 expanded hosted/native paired parity cases passed.

Row-generic checkpoint: `<E:Effect>` is kind-checked separately from ordinary
type parameters in both compilers. Callback contracts determine row arguments;
repeated constraints join, mixed `<T E:Effect>` signatures substitute both
kinds, and instance/cache identity includes the inferred row. Effect binders
cannot enter value types or runtime expressions. Unknown callback behavior
stays unknown. Static function handles require neither an external read nor
an aggregate transfer at a higher-order call.

The initial inference intentionally leaves underdetermined decompositions,
effect-polymorphic type aliases, negative row arguments, and callback-relative
place subjects pending. The last case needs subject scope preserved rather
than interpreting a callback's slot number as the enclosing function's slot.
These are conservative rejections/lost precision, not new source semantics.

Validation: 111 focused hosted row/contract/generic regressions passed,
including x86/C execution of mixed type/row generics. Nine native source
acceptance/rejection probes passed. Two cache checks passed (108.63s), verifying
row binder kinds/identities, binding values and instantiated row arguments
survive an x86/C snapshot round trip, plus generated-code freshness. Native
generations built in 60.74s and 60.09s and both executed the row-generic fixture
with result 42. All 58 expanded hosted/native paired parity cases passed.
Artifacts: `../dewy-build-artifacts/phase1-row-generics-stage2-2026-09-20`.

Copy-inventory follow-up: hosted same-union snapshots and union conversions
now report the copy that lowering emits; an explicit union `.copy()` does not
also become an implicit-copy note at the same site. Native ownership copies
of strings, including copies selected through the shared copy-kind helper,
now appear in the inventory. Recursive fields remain covered by their enclosing
aggregate-copy decision rather than counting each generated helper separately.
This closes specific reporting gaps; it does not claim the whole inventory
or `$explicit_copies` implementation is complete.

Validation: 24 hosted copy/report/source-provenance regressions passed. Native
generations built in 60.39s and 60.20s and executed the coverage fixture with
result 42. Native `analyze` reports both cell and string sites in that fixture.
Artifacts: `../dewy-build-artifacts/phase1-copy-coverage-stage2-2026-09-20`.

Copy-budget tooling now supports exact file/directory scopes and static
sites per thousand physical Dewy source lines. Zero-copy files contribute
to the denominator; malformed, partial, or source-unresolvable inventories
cannot pass a scoped gate. Both hosted and native summary formats are
validated before filtering. Nine tool regressions passed, and the real
hosted/native ownership kernel each reports four sites in 39 lines. Its
stable regression budget remains four sites; density (102.564 sites/kloc)
is supplementary and says nothing about runtime bytes or frequency.

Hosted string-move checkpoint: a single-use local holding an explicit string
snapshot or an owned call result can transfer into a binding, record, array
literal, push, or element/field store. Earlier views and loop backedges stay
conservative; frame descriptors never enter this path. The source slot is
cleared before normal cleanup, including for source-const bindings. Returned
views still retain independent bytes, with a conditional copy note. Move
collection also records returns during its first traversal instead of
rescanning the function for every transfer candidate.

Validation: 32 hosted move/copy/report regressions passed, including x86/C
execution, const storage, earlier views, repeated loop uses and zero retained
bytes over 100 calls. A measured element replacement allocates zero bytes;
disabling moves provides a positive allocating control. The existing second-
generation native compiler also executes the shared fixture with result 42.
No native lowering changed in this batch, so no new self-build was needed.

Borrow/move correctness checkpoint: an inferred local view now extends its
owner's liveness through that view's reads, transitively through further
views. Native borrowed getter results use the same dependency rule. Previously,
moving an array after its last spelled read could allow a destination write to
change a live snapshot of one of its records (99 instead of the required 42).
Both move planners now retain the owner when a later dependent read needs it.
Once the borrowed read is finished, the move remains available; direct whole-
value returns still transfer at function exit.

Validation: 69 ownership/borrow/native-lowering regressions passed, including
x86/C execution; two focused hosted borrow tests also passed. The native
expired-borrow kernel confirms zero allocation for the later transfer on both
backends. Native generations built in 63.80s and 62.84s; both execute the live
borrow and string-move fixtures with result 42. All 60 expanded paired cases
passed against the second generation. These are correctness integration
builds, still above the under-30s native target. A fresh broader corpus run is
starting against this fixed snapshot.
Artifacts: `../dewy-build-artifacts/phase1-move-borrows-stage2-2026-09-20`.

Hosted array-binding checkpoint: descriptor-backed locals can now take a
last-use array value, including an explicit `.copy()` result. Live borrowed
views, later named reads, loop backedges and exposed raw/unknown aliases keep
copies conservative. A heap descriptor transfers directly (including its
existing COW reference), with the source slot cleared; moving it no longer
allocates a second descriptor. Frame-backed storage retains the checked
adopt-or-copy path. Cleanup now releases an arena descriptor independently of
whether it still owns the buffer, fixing a 64-byte-per-iteration leak exposed
by the new transfer kernel.

Validation: 82 move, explicit-copy, sharing, ownership, provenance and lifetime
checks passed, including x86/C execution. The new binding kernel retains zero
bytes over 100 calls and executes with result 42 in the existing second native
generation. A COW-backed local transfer allocates zero bytes on both hosted
backends; disabling moves gives an allocating positive control. This batch
changes hosted lowering only; the native implementation already moves these
bindings. The broader paired run remains pinned to the preceding snapshot.

The full paired corpus at the borrow/move snapshot passed all 211 cases.
This broader run used the fixed second-generation snapshot above, before the
later hosted array-binding and module-provenance work.

Module-provenance checkpoint: assembled hosted HIR now keeps each top-level
item's defining source in `hir.Program` metadata, mirroring the native module
graph's source map. Source attribution survives ordinary HIR rebuilding and
proof erasure. Global startup copy notes now point to the imported module's
initializer rather than to an unrelated span in the entry file. This metadata
also travels through direct checking/code-generation APIs; no CLI scan is used.

Validation: 21 initial provenance/traversal/copy tests, 66 cache/proof/generic/
native-effect-analysis regressions, and four final provenance checks passed.
The direct API test covers both global initialization and a bare top-level
copy with an imported erased proof. Hosted and native CLI inventories both
attribute the global snapshot to dependency.dewy, and the scoped hosted gate
counts its one copy. Strict-copy enforcement remains pending.

Explicit-view checkpoint: both compilers recognize `const name = @route`
for local record and array storage. The declaration retains a view demand
through HIR rewriting and native snapshot serialization; a failed borrow
proof reports the conflicting write where available, rather than falling
back to a copy. Whole-binding views participate in the same transitive owner
liveness used by inferred field/element views. Returning or storing a view's
value still creates an independent value. Mutable local places, other value
kinds, and more precise lifetime intervals remain pending; this first subset
requires function-wide owner stability.

Validation: 83 initial ownership regressions passed, as did 20 local-view,
HIR traversal and native snapshot checks (including x86/C round trips).
The view kernel allocates zero bytes across 100 reads, and its escaped values
remain independent. Eight native acceptance/rejection probes passed. Native
generations built in 61.79s and 63.42s, with the latter executing both the
explicit-view and index-evaluation kernels (42). These remain correctness
integration timings above the native performance target.
Artifacts: `../dewy-build-artifacts/phase1-local-views-stage2-2026-09-20`.

The index-evaluation kernel exposed a hosted lowering bug predating local
views: a singleton index fact erased evaluation of an effectful expression.
Array reads/stores, nested places and string indexing now evaluate it once
before subsequent operands. Literal and scalar-name reads can still use the
proven value directly, including the contextual `end` binding. A first paired
run passed 63/64 cases and caught that `end` regression; it was fixed rather
than changing the fixture's expected result. All 64 cases passed on the final focused rerun. Hosted follow-up gates
passed 94 and 74 checks, covering the changed
diagnostics, width-aware addressing, effectful indices and local views.

The full paired corpus at the local-view/index checkpoint passed 211/211
cases. This run preceded the following union and lazy-string changes.

Union-view checkpoint: required local views now support tagged unions,
optionals, strings and string-literal enums. They retain the source owner
through dependent views and allocate neither replacement cells nor string
handles. Pure inspection of ordinary by-value input can declare
`no_effects`; a view does not hide a place parameter's external read.
Native `.length` also accepts closed string-literal unions by decoding the
active enum before reading its descriptor.

A cold native string length or grapheme-type query now counts without
allocating a boundary table. The shared Unicode scanner has a count-only
sink, with a scalar invalid-input result; existing public segmentation
wrappers preserve their optional results. Compiler-created frame views call
that scanner directly through an imported binding, avoiding a by-value
wrapper's conservative copy. Length and boundary-table caches are separate.
Index/slice comparisons now explicitly request offsets instead of depending
on an earlier length read to have materialized them. General runtime
refinement-predicate tests remain pending; the shape kernel uses `grapheme`.

Validation: the union batch passed 103 hosted effect/row/view checks and
65/65 paired cases at its earlier snapshot. The completed string batch
passed 16 hosted checks, including count-only Unicode conformance and all
ASCII pairs on x86 and C. Native descriptor/lifetime/scratch/Unicode/string
comparison regressions passed on both targets. Cold ASCII and Unicode
length/shape queries allocate zero bytes and later indexing remains valid.
Two generations execute all three new kernels with result 42. Their builds
took 62.89s and 67.40s (the latter shared the machine with another integration
job), above the native target. The expanded paired run passed all 67 cases.
Artifacts: `../dewy-build-artifacts/phase1-string-count-stage3-2026-09-20`.


Scalar-view checkpoint: the frontend now recognizes a view demand by its
stored route rather than an aggregate-kind whitelist. Both lowerers retain
word width and signedness; native storage matching ignores proven array
lengths and fact qualifiers that leave the representation unchanged.
Dictionary/set reads and array joins no longer incorrectly require an
owning local slot solely for read-side cache maintenance. Stores, removals,
place exposure and source instability still reject a required view. Native
rejections now report relevant binding/storage proof failures.

Validation: 31 initial hosted local/union/scalar checks passed; all 12
expanded scalar/container checks also passed, including x86/C execution.
The final native compiler built in 63.25s and runs the scalar/container,
union, string-union and cold-length kernels with result 42. Four additional
native probes passed: prelude-free scalar views and rejection of scalar,
dictionary and set owner mutations. This remains above the native build
target. Artifacts: `../dewy-build-artifacts/phase1-scalar-views-stage6-2026-09-20`.


Explicit-copy policy checkpoint: the approved module directive is carried
through hosted checked-HIR assembly (including direct API use) and native
module options/snapshots. Both lowering boundaries reject recorded implicit
runtime-sized copies in marked modules, preserve unmarked dependency policy,
and allow explicit copies and proven views/moves. Fixed outer layouts are
checked transitively, including concrete child fields; grapheme counts do
not bound string bytes. No COW deferral is treated as a proof of no copy.
The classifier is memoized within the closed compilation. Hosted reporting
now also records array argument/assignment copies, fixed-array field copies,
and owned optional/union parameter cells.

This replaces the removed CLI-only implementation, but does not close the
report-completeness or ownership-parity work. Native mutating by-value
parameters can still receive a conservative entry copy after the caller has
prepared owned storage. A function that explicitly copies a read-only input
into its working local passes both implementations; eliminating redundant
entry copies remains an ownership optimization, not grounds to suppress a
copy note.

Validation: 48 copy/view/provenance/native-cache regressions passed, followed
by 28 hosted policy/classification/provenance checks, 15 copy-bound tests
(including execution of the native classifier on x86/C), and 38 follow-up
report/policy checks. Six native policy/import probes and both explicit/fixed
copy kernels on C passed. The native snapshot kernel preserves an enabled
directive through serialization, and the native bound classifier includes
runtime-sized fields carried through a parent or structural type. Two native
generations built in 66.48s and 64.81s; the latter executes all six view/string/
copy kernels with result 42. These are correctness timings above target.
All 71 paired cases passed at that snapshot. The focused five-case follow-up
also passed against the final hosted report-site changes; the shared manifest
now has 73 cases.
Artifacts: `../dewy-build-artifacts/phase1-strict-copy-stage4-2026-09-20`.


Allocation-contract checkpoint: David approved bare `allocates` and
`no allocates`. Both parsers/kind checkers represent them as the ordinary
subjectless allocation atom and reject resource arguments, including empty
`<>`. Public checking now distinguishes logical copies, aggregate
construction and implicit value boundaries from entirely unknown behavior.
Permission does not authorize external reads/writes, and propagates through
calls, defaults, recursion and row-parameter substitution. COW deferral is
not evidence of no allocation. Storage boundaries remain conservative until
backend placement/move evidence is available; failure policy remains open.

Native lowering now places proven nonescaping scalar places in one frame
slot per local/parameter, reused across loops. This removes a hidden arena
allocation on private scalar mutation paths accepted as effect-free. The
public check uses the same escape summaries: a private place sent through an
unresolved callback or forwarding helper conservatively requires allocation
permission. Captured/escaping slots retain their existing storage protocol.

Validation: 97 existing hosted public-row/generic checks passed, as did 80
allocation/place/row regressions and the final 36 allocation checks. All 33
native acceptance/rejection probes passed, including private places through
callbacks, and both new kernels execute on x86 and C. The native generation
built with the frame-slot change executes the allocation, scalar-place and
strict-copy kernels (42); the final generation built in 65.03s. All 77 paired
Phase 1 cases passed. The build timing remains above target.
Artifacts: `../dewy-build-artifacts/phase1-allocation-effects-stage4-2026-09-20`.

Direct array ownership checkpoint: native direct-only functions can own a
caller-prepared mutable array when escape summaries prove it cannot be kept.
The caller transfers a fresh/moved/copied value; the callee releases it on
normal and early exits, including replacement and forwarding through a place.
This is separate from single-use consumption: reading the parameter does not
consume it. First-class functions, defaults, captures and runtime entrypoints
retain the ordinary ABI. Callback target analysis now includes only observed
function values (and still treats raw callable ingress as unknown), rather
than every function with a compatible signature. Shared HIR nodes are checked
by parent-child use, so a direct call cannot hide a value use of the same node.

Hosted lowering now retains and releases caller-prepared nonescaping argument
snapshots. Rebound parameters own their replacement storage separately from
the caller's incoming descriptor. Mutable array parameters of functions used
as values isolate their contents on entry; callback forwarding cannot mutate
the caller's ordinary by-value input. Fresh nested literal elements transfer
into lasting replacement buffers instead of leaking their initial owners.
Strict-copy accounting uses the source's known outer extent at a runtime-length
parameter boundary, while retaining the destination's child-storage costs.
True unbounded implicit argument copies remain errors under `$explicit_copies`.

Validation so far: the direct native second generation built in 64.26 seconds
and passed the three ownership kernels on x86 and C. The broad paired corpus
passed 211/211. The final hosted ownership/strict-copy group passed 19 tests,
and 35 array/lifetime regressions passed. Native timing remains above target;
this checkpoint does not certify a new fixed point or complete Phase 1.
Artifacts: `../dewy-build-artifacts/phase1-owned-parameters-stage3-2026-09-20`.

A proof gap exposed by the nested-array lifetime kernel remains: checking
`rows[0].length` does not currently establish a stable fact route for a later
`rows[0][0]`. A named local row view does carry that fact, but the general
indexed-route proof and its mutation invalidation are still required; the
fixture's local views do not constitute a fix for that proof gap.
Final integration check: all 82 paired Phase 1 cases passed, including the
nested-array lifetime kernel and both bounded/unbounded strict-copy argument
cases. Results: `../dewy-build-artifacts/phase1-owned-parameters-final-parity-2026-09-20`.

Indexed-fact checkpoint: field routes now also admit constant index selectors.
A guard on `rows[0].length` can justify `rows[0][0]` without a named local
view, including records containing rows, string elements and deeper nesting.
An index expression is still evaluated normally; known index values do not
erase its effects. A component write conservatively drops indexed evidence
for the root, including writes through places and element relocation. Recursive
invalidation removes element evidence rooted at the projected sequence too.
Dynamic index identities and finer disjoint-index preservation remain pending.

Validation: 31 hosted index/container/order tests, 64 proof/loop/refinement
regressions, and two native registry/fact-transfer unit tests passed. The native
compiler built in 66.26 seconds, executes the indexed-read kernel on x86 and C (42), and
passes all 14 acceptance/rejection probes. All seven paired index cases passed,
including invalidation by replacement, shifting and effectful index evaluation.
Artifacts: `../dewy-build-artifacts/phase1-indexed-routes-stage1-2026-09-20`
and `../dewy-build-artifacts/phase1-indexed-routes-parity-2026-09-20`.

Iterator allocation contracts now consume the existing bounds proof. Public
effect validation runs after bounds checking, and accepts private numeric
range counters when their finite extent fits a word or every advancing edge
is proved to fit. Unbounded continue paths cannot borrow the parser's guard
hint as evidence. Counter reads and direct scalar arguments use that same
proof; loop-body allocation, external reads/writes and unknown behavior keep
their ordinary effects. This permits natural counted loops under `no_effects`
and `no allocates` without requiring a hand-written scalar while loop.

Validation: 13 iterator checks and the 36 allocation checks passed, alongside
144 existing effect/proof/unsafe tests. A native generation built in 66.62s,
executes the iterator allocation-counter kernel on x86 and C (42, no arena
allocations), and passes all 12 acceptance/rejection probes. All 16 paired
effect cases passed, including an unbounded continue-edge rejection.
Artifacts: `../dewy-build-artifacts/phase1-iterator-effects-stage1-2026-09-20`
and `../dewy-build-artifacts/phase1-iterator-effects-parity-2026-09-20`.

Fresh replacement report correction: hosted assignment of a fresh nested
array literal to lasting runtime-length storage already transfers its element
owners. It now reports that operation as a move, instead of an unproven
independent copy. This keeps `$explicit_copies` acceptance aligned with native
for nested string/array replacements and preserves the report entry describing
why lifetime promotion is needed. Actual snapshot sites retain their copy notes.
Validation: 23 strict-copy, ownership and array-release tests and all eight
paired strict-copy cases passed. The new fixture executes on x86 and C through
hosted lowering and through the existing native compiler.
Artifacts: `../dewy-build-artifacts/phase1-fresh-replacement-parity-2026-09-20`.

Required views now have a lexical-scope proof as well as the original
whole-function proof. A private owner may change before and after the view's
containing block, but any overlapping write, mutable place or unresolved call
within that block prevents the view. Captured or addressed owners stay on the
conservative path. Derived local views remain within that block; ordinary
values leaving it retain independent-value semantics. Diagnostics search the
relevant block rather than blaming a harmless earlier write. This first
shorter lifetime is explicit-demand-only; ordinary inference and last-use
intervals within a block remain separate work.

The additional scope scan runs only for functions containing required views;
the bootstrap's ordinary borrow analysis keeps its existing path. Native
bookkeeping uses numeric scope keys, since optional numeric keys still lack a
native hash implementation (an implementation gap, not a new design rule).

Validation: 41 hosted view tests initially passed; the expanded scope tests
and ownership/copy-report regressions passed 29 checks. Native passed all ten
focused probes, including printing through a view, copying a value out and
rejecting an addressed owner. The allocation/lifetime kernel passes on x86
and C, with zero view allocations and no retained storage over 100 calls. A
second native generation built in 67.16 seconds and executes both the scope
and iterator-effect kernels (42). These remain correctness timings above target.
Artifacts: `../dewy-build-artifacts/phase1-scoped-views-stage2-2026-09-20`.


Dictionary-key parity correction: hosted lowering no longer hashes the address
of an unsupported tagged cell or aggregate as if it were the key's value.
Such a lookup could silently miss a separately owned equal value. It now
rejects the same unsupported representations as native; fixed-width words,
bools, strings and word enums retain their existing value hashes. This does
not settle a user-defined hashing protocol or implement aggregate key equality.
Validation: 16 hosted dictionary/set tests passed; native rejects all five
unsupported representation probes and executes the supported-key kernel (42).
The hosted kernel executes on x86 and C. The change was prepared in an isolated
checkout while the preceding full integration runs used unchanged sources.

Integration closure for these checkpoints: the scoped-view second-generation
compiler passed all 211 broad corpus cases and all 91 then-current Phase 1
cases. The subsequent hosted-only dictionary-key correction passed both new
paired cases, bringing the focused manifest to 93. Artifacts:
`../dewy-build-artifacts/phase1-scoped-views-full-parity-2026-09-20`,
`../dewy-build-artifacts/phase1-scoped-views-parity-2026-09-20`, and
`../dewy-build-artifacts/phase1-key-validation-parity-2026-09-20`.

Lifecycle design review: David approved the zero-argument compiler-only
member shape, internal borrowed receiver, return types and automatic field
cleanup order. Observable effects are allowed under ordinary effect
contracts; implicit copy/move and temporary drop counts may change through
elision. The proposal and storage design notes now reflect that decision.
Hook implementation, raw-resource ownership contracts and remaining failure
behavior are still outstanding. Phase 1 is not complete.

Lifecycle declaration foundation: both checkers retain the metatag's role
separately from the ordinary method name, require one zero-argument member
per role on a nominal owner, check drop's void result and copy/move's exact
nominal result, and reject manual calls or function values. Even a field-free
body receives the original object through an internal place. Copy receivers
are read-only through projections, forwarded places and nested functions.
Ordinary effect contracts still check hook bodies; observable unannotated
hooks are allowed. Result inference continues to work. Native cache codecs
preserve the new member metadata.

This is declaration support, not automatic resource lifetime support. Both
code-generation routes reject runtime hooks explicitly. The native guard
runs before reachability pruning, which would otherwise erase a hidden hook
and silently compile its object with ordinary memberwise semantics. Inherited
hooks were explicitly pending at this checkpoint; the parent-portion direction
has since been approved. Next, implicit ownership operations must be visible to effect/fact
analysis and reachability as well as to cleanup and copy lowering.

Validation: the initial hosted declaration/method suites passed 39 tests;
the effect/declaration suite passed 122, and the expanded declaration suite
passed 28. Native passed all 16 focused acceptance/rejection probes (including
the explicit lowering limitation), the existing scoped-view and iterator
execution kernels, and all four new paired rejection fixtures. The native
build took 65.66 seconds, still above target. The focused manifest has 97
cases; no new full-corpus result is claimed for this batch. Artifacts:
`../dewy-build-artifacts/phase1-lifecycle-declarations-stage1-2026-09-20` and
`../dewy-build-artifacts/phase1-lifecycle-declarations-parity-2026-09-20`.

Lifecycle call checking and cleanup foundation: explicit custom `.copy()`
operations now resolve to checked calls with an internal read-only receiver,
including const sources. Their effects and returned facts come from the hook,
not from a memberwise copy of the source. Drop-only explicit copies are
rejected. Lifecycle members cannot escape through inherited callable fields.
HIR and native snapshot codecs retain each function's lifecycle role.

The internal receiver is private to the lifecycle operation for public effect
contracts; ordinary alias analysis still sees its place accesses. Both effect
checkers now include projected member/index writes, including possible storage
detachment and independent by-value parameter storage. Cleanup releases nested
scopes and record fields in reverse order. Runtime lifecycle invocation remains
explicitly gated until automatic ownership operations have correct checking
and lowering; these declaration/call checks alone do not enable resources.

Validation: all 101 Phase 1 paired cases passed, including seven lifecycle
rejections whose expected diagnostic fragments are now checked. Hosted checks
passed 142 effect/allocation/declaration tests, 37 final declaration tests,
35 copy/method/report regressions and 26 ownership/cleanup tests. Native passed
26 focused probes and three execution kernels; the projected-store kernel also
passed hosted x86 and C. The final native generation built in 64.35 seconds,
still above the performance target. Artifacts:
`../dewy-build-artifacts/phase1-lifecycle-calls-stage3-2026-09-20` and
`../dewy-build-artifacts/phase1-lifecycle-calls-parity-2026-09-20`.

David approved parent-portion lifecycle inheritance and clarified the review
policy: proceed provisionally with obvious choices consistent with Dewy and
report them; seek advance review for fundamental new language directions.

Inherited lifecycle checking now composes through the immediate parent in
both implementations. Each hidden helper borrows its child source once,
invokes the parent operation once, and reconstructs the complete child from
the returned parent portion and the added fields. The ordinary constructor
checker rejects parent results that cannot establish a strengthened child
contract. Added custom-copy effects remain visible. Inherited drop bodies
delegate to the parent body; complete-child field cleanup remains the
responsibility of the pending ownership lowering. Runtime hooks are still
explicitly rejected, so this is not a resource-lifetime completion claim.

The provisional override rule follows the role rather than the member name:
an explicitly tagged child operation replaces that inherited role, while an
ordinary same-named method cannot silently remove it. A child override
supplies the complete operation; it does not also run the overridden body.

Validation: 121 hosted lifecycle/method/effect checks and the final expanded
47 lifecycle checks passed. Native passed the previous 26 focused probes
and six additional inheritance probes, including multi-level copy, move,
override and strengthened-contract checking. The build took 64.30 seconds
and executed all three existing view/ownership/projected-store kernels (42).
All 11 lifecycle parity cases passed with required diagnostic fragments;
the focused manifest now has 105 cases. Artifacts:
`../dewy-build-artifacts/phase1-lifecycle-inheritance-stage1-2026-09-20` and
`../dewy-build-artifacts/phase1-lifecycle-inheritance-parity-2026-09-20`.

Required local views now use statement intervals through the last use of
their derived aliases in both lowerers. Owners may change earlier and later
in the same block. The dependency closure includes aggregate forwarding and
explicit derived scalar views; an explicit `.copy()` creates an independent
snapshot. Loops and conditional statements remain indivisible, preventing
a later iteration or branch from reading invalidated storage. Captured,
exposed and outward-stored aliases retain the containing-block proof, and
addressed owners still need stronger evidence. Ordinary inferred views keep
their existing fast path. Conflict diagnostics search the selected interval,
so an earlier unrelated write no longer receives the blame.

Validation: 50 hosted view/copy checks passed initially; one old rejection
expected an unused view to block a later write and was updated to read the
view after that write. The corrected local-view and ownership/report suites
passed 34 checks. Native passed all 14 last-use acceptance/rejection probes
and all ten paired view fixtures. The new allocation kernel executes on
hosted x86/C and native, allocates nothing for the views and retains no
storage over 100 repetitions. The native generation built in 63.41 seconds
and also executes the previous three kernels (42), still above target.
The focused manifest now has 108 cases. Artifacts:
`../dewy-build-artifacts/phase1-view-last-use-stage1-2026-09-20` and
`../dewy-build-artifacts/phase1-view-last-use-parity-2026-09-20`.

Lifecycle follow-up: structural extension of an existing nominal identity is
not a new child mint. Its hook adaptation previously attempted to look up a
nonexistent nominal parent and could fail internally. Both checkers now
diagnose this unsupported composition explicitly. Hosted passed 48 lifecycle
checks; the new paired fixture passed with the expected diagnostic. A fresh
native generation built in 67.19 seconds while integration tests were also
running, then executed the three existing kernels (42). Artifacts:
`../dewy-build-artifacts/phase1-lifecycle-structural-guard-2026-09-20` and
`../dewy-build-artifacts/phase1-lifecycle-structural-guard-parity-2026-09-20`.

Integration closure: the last-use-view compiler passed all 211 broad corpus
cases and all 108 then-current Phase 1 cases. The structural-composition
diagnostic follow-up passed its additional paired case, bringing the focused
manifest to 109. The broad runs used unchanged sources while the follow-up
was prepared in an isolated checkout. Artifacts:
`../dewy-build-artifacts/phase1-view-last-use-full-parity-2026-09-20` and
`../dewy-build-artifacts/phase1-view-last-use-full-phase1-parity-2026-09-20`.

Nominal writable-prefix correction: an inherited mutating method could write
a wider parent value into a child's strengthened field while checking still
trusted the child invariant. Both checkers now require matching writable
field types, refinements and mutability across that prefix. Read-only value
methods retain ordinary subtyping. The compiler-only copy receiver has a
separate read-only compatibility check that preserves field representation;
this also permits inherited copies of const children without granting source
code a mutable alias. Constructor checking still owes the child's result
invariants. This correction does not yet settle whole-value replacement or
escape through a parent place; those need the existing effect summaries to
prove that the complete child's identity and additional invariants survive.

Validation: 90 hosted declaration/place/method checks and 15 final method
barrier checks passed, including execution on x86 and C. Native passed six
focused probes and both new paired fixtures. A fresh generation built in
63.57 seconds and executed the three existing kernels (42). Artifacts:
`../dewy-build-artifacts/phase1-nominal-place-contracts-2026-09-20` and
`../dewy-build-artifacts/phase1-nominal-place-contract-parity-2026-09-20`.

Parent-place identity proof: both compilers now use transitive parameter
access summaries to reject whole-parent replacement or escape through a
child's wider nominal view. Field-only updates and independent value reads
remain valid, including through imported helpers. Unknown callbacks cannot
supply that proof. The pass sees all loaded source functions before runtime
pruning, so an unused invalid function cannot disappear before checking.
The native effect collector now accepts several module roots without
repeating collection. Existing overload dispatch still rejects a mismatched
place type before this proof is reached. Sibling-field invariants remain
restricted to immutable records under the existing type rules.

Validation: 112 hosted place/lifecycle/effect checks passed. The fresh native
generation built in 64.90 seconds, executed the three ownership kernels (42),
and passed all five paired nominal-place cases. The focused manifest now
has 114 cases. Artifacts:
`../dewy-build-artifacts/phase1-parent-place-effects-2026-09-20` and
`../dewy-build-artifacts/phase1-parent-place-effects-parity-2026-09-20`.

Inferred const projection views now reuse the last-use interval proof when
their owner is not stable for the whole function. Alias dependencies are
collected once per containing block and shared by its candidate views;
already-proven whole-function borrows keep their existing fast path.
Conflicting writes still select independent copies, or the existing
`$explicit_copies` diagnostic. No new source form was introduced.

Validation: the hosted ownership/view/report/strict-copy batch passed 109
checks, with one new test initially expecting the wrong diagnostic text;
after correcting that expectation, all nine new inferred-view tests passed.
The fresh native generation built in 63.90 seconds and passed the three
ownership kernels plus all eleven paired view fixtures. The inferred-view
kernel allocates nothing for the views and retains no storage across 100
repetitions on hosted x86/C and native. The focused manifest has 115 cases.
Artifacts: `../dewy-build-artifacts/phase1-inferred-view-last-use-2026-09-20`
and `../dewy-build-artifacts/phase1-inferred-view-last-use-parity-2026-09-20`.

Public effect checking now runs over the complete checked module graph,
after bounds validation has certified iterator storage and before runtime
pruning. Direct imported helpers, including transitive imports, participate
in the same fixed point as local functions. An omitted row no longer turns
a known imported helper into an unknown operation. Unused imported contracts
are still checked, and unknown operations/allocations remain conservative.
Native effect collection is shared with its access-summary solve rather than
traversing the graph twice. This does not yet infer rows into callback types.

Validation: 164 hosted public-effect, allocation and lifecycle checks passed.
The fresh native generation built in 63.66 seconds, executed the three
ownership kernels (42), and passed all 24 paired effect fixtures. The focused
manifest now has 118 cases. Artifacts:
`../dewy-build-artifacts/phase1-imported-effects-2026-09-20` and
`../dewy-build-artifacts/phase1-imported-effects-parity-2026-09-20`.

Integration checkpoint: the imported-effect generation passed all 118 Phase 1
parity cases on unchanged sources. Follow-up work was prepared in a separate
checkout while that run completed. Artifact:
`../dewy-build-artifacts/phase1-imported-effects-full-phase1-2026-09-20`.

Synthesized explicit copies now propagate move-only capability through
record fields, array elements, dictionary storage and union alternatives.
A nested drop-only resource cannot acquire a copy operation merely by being
wrapped in a container. Diagnostics identify the component path. A custom
copy hook remains responsible for constructing its own complete result and
may acquire fresh move-only members. Recursive capability queries terminate
without treating a cycle itself as evidence of move-only storage. These are
capability checks, not runtime lifecycle implementation: automatic copy/move
and cleanup remain gated. This follows the existing resource rule and adds
no syntax or ownership annotation.

Validation: 72 hosted lifecycle/copy checks passed. A fresh native generation
built in 68.32 seconds while the integration run was active, executed the
three ownership kernels (42), and passed all six nested-resource probes plus
the paired diagnostic fixture. The focused manifest now has 119 cases.
Artifacts: `../dewy-build-artifacts/phase1-lifecycle-components-2026-09-20`
and `../dewy-build-artifacts/phase1-lifecycle-components-parity-2026-09-20`.

Imported lifecycle declarations now remain in the hosted runtime dependency
graph until ownership operations have explicit call edges. Otherwise pruning
could remove a hidden hook and bypass the runtime implementation gate for
an imported resource. Native validation already rejects before pruning.
Both used and unused imported hook declarations are covered. Validation:
51 hosted lifecycle checks and the new paired imported-resource diagnostic
passed. The focused manifest has 120 cases. Artifact:
`../dewy-build-artifacts/phase1-lifecycle-import-gate-parity-2026-09-20`.

Broad integration: the lifecycle-component generation passed all 211 broad
compiler/parser corpus cases on fixed sources. Together with the preceding
118-case Phase 1 run and the two new paired lifecycle cases, this closes the
current integration checkpoint; it does not complete Phase 1. Artifact:
`../dewy-build-artifacts/phase1-lifecycle-components-full-parity-2026-09-20`.

Runtime drop now supports fresh local nominal owners with word fields in both
compilers, including inherited and imported drops, reverse lexical order,
early returns and loop exits. Return values are captured before cleanup;
backing storage is released after the hook. Calls are explicit checked HIR,
so hook writes invalidate later facts and enter public effect contracts.
Unsupported ownership shapes still receive source fact/effect diagnostics
before the implementation-gap diagnostic. Copy/move hooks, aggregate fields,
owning transfers, escaping resources and implicit value returns with local
owners remain explicitly gated. No new source form was introduced.

Validation: the hosted lifecycle/place/effect batch passed 92 checks, followed
by all 14 final runtime tests on x86 and C. The fresh native generation built
in 67.16 seconds and passed the three ownership kernels (42). All 18 paired
lifecycle cases passed, including the new cleanup, no-retained-storage,
effect and stale-fact fixtures. The focused manifest now has 124 cases.
Artifacts: `../dewy-build-artifacts/phase1-lifecycle-drop-runtime-2026-09-20`
and `../dewy-build-artifacts/phase1-lifecycle-drop-parity-final-2026-09-20`.

Tight right-hand numeric adjacency now retains both call and multiply
readings in both parsers. Whitespace remains a separator. The hosted checker
now preserves call-target context through single grouping parentheses,
matching native; `(f)2` no longer auto-calls `f` before seeing its argument.
Callable-or-number unions still require explicit call pipes or multiplication.
Validation: 40 hosted adjacency/function-value/keyword-call tests passed.
A fresh native generation built in 66.31 seconds, passed three ownership
kernels and the extended paired precedence fixture (including `g(1)2` and
both call/multiply exponentiation). Artifacts:
`../dewy-build-artifacts/phase1-tight-numeric-adjacency-2026-09-21` and
`../dewy-build-artifacts/phase1-tight-numeric-adjacency-parity-2026-09-21`.

Hosted lowering no longer erases refinements in place on the shared checked
graph. The cached prelude retained some of those nodes, so a later compilation
could lose parameter facts (observed in `Report.point`'s `addr` parameters).
Erasure now rebuilds changed DAG paths before lowering constructs its identity
indexes. A regression reuses one checked program twice and verifies that its
parameter facts survive and its generated program remains identical.
Validation: 28 lowering/physical-unit/union-refinement checks passed.

Local drop now also handles ordinary aggregate fields, including strings and
arrays: the hook runs while those fields are live and automatic storage
cleanup follows. Scalar implicit results are captured before drop, just like
explicit returns. Lifecycle-bearing nested fields, resource transfers and
copy/move hooks remain pending. Validation: 69 hosted lifecycle checks passed,
including x86/C execution, and all 20 paired lifecycle fixtures passed. The
new aggregate fixture checks inherited cleanup, a snapshot across array
mutation, field mutation inside drop, and zero retained bytes over 100 calls.
The fresh native generation built in 65.81 seconds and passed three ownership
kernels. The focused manifest has 126 cases. Artifacts:
`../dewy-build-artifacts/phase1-lifecycle-aggregate-drop-2026-09-21` and
`../dewy-build-artifacts/phase1-lifecycle-aggregate-drop-parity-2026-09-21`.

Integration checkpoint: the combined drop/adjacency generation built in
65.21 seconds, passed the three ownership kernels, and passed all 126 Phase 1
parity cases against fixed sources. Nested-field follow-up work stayed in an
isolated checkout during this run. This is an integration checkpoint, not
completion of Phase 1; native self-build time remains above the 30-second
target. Artifacts: `../dewy-build-artifacts/phase1-drop-integration-2026-09-21`
and `../dewy-build-artifacts/phase1-drop-full-parity-2026-09-21`.

Nested record ownership now materializes containing hooks before reverse
field cleanup, recursively, including wrappers with no hook of their own.
Fresh constructor trees are supported; transferring an existing resource
into a field, replacing a resource field, resource arrays/unions, and general
owning arguments/results remain explicitly unsupported. The native pass
resolves operations through the checked nominal-owner inventory, since
method descriptors can precede binding resolution. Hosted fact revalidation
now uses each function's original source for diagnostics across imports.

Validation: 72 hosted lifecycle checks passed, followed by 34 runtime and
refinement checks after adding the imported-diagnostic regression. Native
built in 70.71 seconds during the independent integration run, passed the
three ownership kernels, all seven paired drop-runtime cases, and both new
nested effect/fact rejection cases. The nested fixture checks hook/field
order and zero retained bytes across 100 calls. The focused manifest has
129 cases. Artifacts:
`../dewy-build-artifacts/phase1-lifecycle-nested-drop-2026-09-21`,
`../dewy-build-artifacts/phase1-lifecycle-nested-drop-parity-final-2026-09-21`
and `../dewy-build-artifacts/phase1-lifecycle-nested-drop-facts-2026-09-21`.

Explicit custom copy hooks now execute when they construct a fresh result,
including a fresh wrapper whose fields call their own copy hooks. Internal
receivers stay borrowed and read-only; the result becomes a separate local
owner and is dropped independently. Hook effects and return facts remain
ordinary checked calls. This does not yet support inferred moves/copies,
inherited copies consuming an intermediate parent result, general owning
arguments/results, or containers of resources. Those forms still diagnose
the missing ownership operation rather than falling back to memberwise copy.

Validation: 84 hosted lifecycle/capability checks passed, followed by four
runtime fixture checks after extending the copy fixture with nested hooks.
The fresh native generation built in 67.26 seconds, passed three ownership
kernels and all 24 paired lifecycle cases. The copy fixture checks independent
mutation, exercised hook/drop counts, and zero retained bytes across 100
iterations on hosted x86/C and native. The focused manifest has 130 cases.
Artifacts: `../dewy-build-artifacts/phase1-lifecycle-copy-runtime-2026-09-21`
and `../dewy-build-artifacts/phase1-lifecycle-copy-runtime-parity-2026-09-21`.

## Test repair and ownership continuation (2026-09-21)

The original failing local suite is repaired: the fixed baseline passed
3,347 tests with 14 skips, and CI run 35565972436 passed. The recovery release
published `native-8406363e1299` after three byte-identical generations and
execution checks on both backends. Test drivers are cached within a pytest
worker; each source case still executes in its own process and cache.

Resource factories and callbacks now return fresh owners. Result evaluation
precedes cleanup, including aggregate field snapshots and copy hooks with
scratch owners. Ordinary `@` parameters lend resource records without
transferring ownership; nested fields and callback forwarding are covered.
Explicit returns transfer local owners along the exiting path, including
branches and loops, and release the remaining owners. Hosted record binding
moves now reuse storage at proven last use, matching the native behavior.
Their allocation regression has a positive control with moves disabled.

The expanded full suite passed 3,368 cases and exposed two regressions:
construction-time move bookkeeping was missing, and optional widening was
misclassified in the copy inventory. Both are fixed; all 11 targeted
copy-inventory, binding-identity and record-move checks passed afterward.
The full suite must still be rerun on the combined follow-up changes.

Inherited copy wrappers now consume the intermediate parent's fields into
the complete child instead of dropping those resources prematurely. Explicit
HIR metadata identifies the checked composition; snapshot codecs preserve
it. Native parent-place contracts compare proposition identities rather than
array storage addresses. All 95 lifecycle, identity and snapshot checks passed.

Explicit owner returns now invoke custom move hooks. The consumed owner's
own drop hook is skipped; remaining nested resources still receive automatic
cleanup. Inherited hooks compose the parent operation with ordinary added
fields. Hook effects invalidate caller facts and participate in effect
contracts; a returned fact must hold for the hook's result. All 96 targeted
checks passed, including hosted x86/C and native execution, inheritance,
effect rejection, and no retained storage across repeated calls.

These checkpoints do not complete Phase 1. General local resource transfers,
resource containers, owning parameters, mutable local places, shared storage
proofs for allocation contracts, and inferred callable effect rows remain
work to finish. Existing rejection gates remain explicit until their
ownership operations are implemented. New integration and second-generation
checks are required before certifying the combined changes.

Implicit resource results now follow the explicit-return ownership path.
Conditional results and nested scopes preserve cleanup order; a value before
trailing statements is saved before those statements and transferred after
them. This also fixes a premature return in that resource-result case.
All 42 hosted/native lifecycle checks passed. The combined committed snapshot
then built three native generations; the last two are byte-identical and the
bootstrap execution checks passed on both output backends. The final generation
took 110 seconds under concurrent test load; this is an integration result,
not a performance-target claim. Artifacts:
`../dewy-build-artifacts/phase1-ownership-integration-2026-09-21`.

Same-scope local resource bindings now transfer an owner at proven last use,
invoking a custom move hook where declared and retaining nested cleanup for
fields left behind. Captures, later uses and outer-owner conditional transfers
do not acquire this proof. Lexical ownership is established before cleanup
introduces artificial reads. All 102 lifecycle/declaration checks passed,
including ordinary and custom moves, loops and branches, hook effect/fact
rejection, and repeated-call storage accounting on hosted x86/C and native.
Outer-owner conditional consumption, inferred resource views/copies and field
transfers remain outstanding; this is not the complete ownership model.

The fixed-point generation passed 135/136 original Phase 1 manifest entries;
the sole failure was an obsolete rejection expectation for importing a
move-hook declaration without moving it. Both compilers accepted that already
supported program. Renamed it to `lifecycle_imported_owner`, required exit 42,
and reran the case against the same native generation: passed. All 136
integration cases therefore have checked expected outcomes. Artifacts:
`../dewy-build-artifacts/phase1-ownership-parity-2026-09-21` and
`../dewy-build-artifacts/phase1-imported-owner-parity-2026-09-21`.

Fresh arrays now own their resource elements, including nested arrays, empty
arrays, record array fields and factory results. Cleanup borrows each array
through a checked helper, runs element hooks in reverse order, then leaves
backing storage release to normal lowering. Helper reuse avoids duplicating
nested loops at every exit and gives each receiver a stable proof identity.
Generated bindings and module provenance remain explicit in HIR. Aggregate
mutation, resource union/dictionary handling and inferred element copies are
not covered by this batch.

Validation: the hosted lifetime fixture passed on x86 and C; 27 hosted
lifecycle checks passed before native compilation found an incorrect internal
binding-kind spelling. After correcting it, all eight native lifecycle cases
passed. Three final hosted lifetime/effect checks and two native rejection
cases passed, including propagation of implicit element-drop effects and
invalidation of caller facts. No storage remains after 100 repeated calls.

Ordinary by-value resource parameters now receive ownership from fresh
arguments, factory results and explicit custom copies, including callbacks
and default arguments. Parameters drop in reverse order after later locals;
returning a parameter transfers it to the caller. Scalar and aggregate field
results are captured before parameter cleanup. Existing `@` parameters retain
their borrowed lifetime. Named-owner argument transfers and implicit copies
still need the general ownership plan.

Validation: all 100 lifecycle/declaration checks passed, including the shared
owning-parameter fixture on hosted x86/C and native. Two additional hosted and
two native effect/fact rejection cases passed. Repeated calls retain no storage.

Remaining correctness issue found while extending the fixture: preliminary
source bounds validation runs before lifecycle operations are inserted. It
can retain a counter fact across a call whose implicit drop will change that
counter, then incorrectly consider a combined counter/length guard impossible.
For example, a later `if drops not=?6 or values.length not=?2 return 7` can
lose the length proof when earlier checks established `drops=?3`. Ownership
materialization and proof validation need an ordered shared pipeline; the
final post-materialization validation is necessary but cannot undo an earlier
false rejection. Keep this as a Phase 1 correctness task, not a source-style
requirement to split such guards.

Full-suite checkpoint: commit `744f25d7` passed 3,379 tests with 14 skips
(1,985 seconds). The test inputs stayed fixed while later work proceeded in
separate checkouts. The combined local-move/array/parameter tree then passed
100 hosted checks and built two byte-identical native generations with both
backend execution checks. The final generation took 60 seconds under load.
Artifacts: `../dewy-build-artifacts/phase1-resource-ownership-integration-2026-09-21`.
Targeted second-generation lifecycle parity passed all 33 cases; the full-suite
checkpoint is green on CI (run 35572685303).

Ownership/proof ordering follow-up: both file and in-memory hosted modules
now materialize lifecycle operations before their first bounds and effect
validation, matching native ordering. A module-local pass uses a cached hook
inventory and marks the finished program so backend entry points cannot
insert cleanup twice. The combined counter/array-length guard now compiles
unchanged. Contradictory assertions and effect contracts are rejected by the
semantic entry point as well as code generation.

Custom copy receivers can now be factory and constructor temporaries,
including nested copies and inherited hooks. Each receiver is evaluated once;
the copy result is captured before dropping its temporary receiver. A shared
fixture checks hook counts, independent storage and repeated-call reclamation.

The prior combined ownership generation passed all 33 lifecycle manifest
cases against the hosted compiler. The 744f25d7 full-suite checkpoint passed
3,379 tests (14 skipped), and its CI run 35572685303 is green.

Validation for this follow-up: 65 hosted/native lifecycle checks passed,
including both output backends; all 53 module, prelude-cache, imported-effect,
prototype and representation checks passed. The earlier hosted lifecycle
coverage passed 108 cases before the temporary-receiver additions.


Expression exits now carry their enclosing ownership context through blocks,
conditions and selectors. Hosted `or_throw` is expanded to the same checked
binding/test/return structure used natively before ownership validation.
Propagated optional and record-error results release locals and owning
parameters in reverse order; ordinary successful results keep their usual
path. Rewritten selector expressions are retained in hosted HIR.

A captured `none` return previously lost its unit tag during lowering; unit
absence now needs no capture before cleanup. A literal-valued conditional
also emitted its literal type as a micro-Dewy variable annotation: the flow
temporary now uses its already-selected runtime type.

Validation: 60 lifecycle checks passed on the initial hosted/native batch,
including both output backends. All 12 hosted propagation/error checks
passed. The extended selector-propagation fixture then passed hosted and
native execution on both backends; the three hosted ownership-order and
temporary-copy integration checks also passed. Full integration follows the
next ownership batch; this does not complete Phase 1.


Read-only local resource aliases now retain one logical owner. Same-scope
bindings whose source and destination are never written or captured can
share the original owner, including chains and explicit const views. Last-use
owner transfers still take precedence. Writes, escaping owners, field moves
and general cross-scope resource aliases need further ownership analysis.

The common view lifetime proof now works backward through blocks and return
edges. Cleanup after a captured return value is outside that view's live
interval, while loop backedges retain aliases read on later iterations.
Captured/outward aliases keep their conservative lexical lifetime. A known
nonescaping place call before or after a view no longer disqualifies its owner
for the entire function; overlapping writes during the view still fail.
Unknown or retaining place calls keep their exclusion.

Validation: the initial resource-view/lifetime batch passed 50 tests, including
native execution. After integration with expression exits and preserving the
lexical fallback, all 56 combined hosted/native checks passed. Two obsolete
rejections now test nonescaping calls outside the live interval and a genuine
conflict inside it. Shared fixtures check one drop and no retained storage.


The resource-view and expression-exit integration (`4deadf4e`) built two
byte-identical native generations. Both generated backend execution checks
passed, followed by all 36 lifecycle parity cases against the second-generation
compiler. Generation times were 85 and 80 seconds while the full test suite
was running; these are integration results, not isolated performance claims.

Resource unions and optional owners now clean up only their active alternative,
including union elements in resource arrays. A union transfer dispatches a
custom move only for the alternatives that declare one; remaining fields of
that consumed alternative drop, while intact alternatives transfer their
nested owners. Drop calls still participate in effect and fact checking.

Narrowed array elements retain their declared storage layout when loading or
taking a place. Optional projections bind an already-evaluated cell rather
than copying and reevaluating their selector. Fresh safe-navigation receivers
and frame-rooted record results packed into unions release their temporary
owned storage after the statement. Shared fixtures exercise custom moves,
optional absence, selector evaluation once, and repeated calls without retained
storage.

The immutable `4deadf4e` integration passed the full local suite: **3,401
passed, 14 skipped** in 1,870.74 seconds. The subsequent union changes have
separate focused coverage. GitHub API rate limiting prevented a fresh CI status
query at this checkpoint; the prior `744f25d7` CI run was successful.

Validation: all six focused union/forward-reference checks passed, including
native execution on both output backends. The preceding run also passed all
21 adjacent hosted optional/union checks. Resource-union fixtures retain zero
storage over 100 iterations; cleanup effects reject empty contracts and stale
assertions in both compilers.


Ordinary implicit function results now preserve their evaluation position even
when statements follow them. Hosted lowering previously returned immediately;
native block cleanup treated the last statement as the result. Both now save
the expressed value and run trailing statements before returning/releasing the
scope. The shared regression covers scalar, string, array, record, optional
and conditional results, mutation after evaluation, and zero retained storage.
All eight focused result-order and lifecycle integration checks passed,
including hosted/native execution on both output backends. Mixed explicit
and implicit returns retain their existing source-checking rules.


Independent resource values now invoke a declared `$__copy__` hook when a
surviving source cannot move or share a read-only view. This covers local
bindings, projected resources and ordinary owning arguments. Calls enter HIR
before fact/effect validation; refinements must hold for the hook's result,
not merely its source. The HIR call retains implicit-copy intent for copy
reports and `$explicit_copies`; native snapshot serialization preserves it.
Proven local moves and views still take precedence. Synthesized copies of
containers/records containing custom-copy components remain outstanding.

All 12 focused inferred-copy, resource-union and resource-view checks passed,
including hosted/native execution on both backends. The shared fixture checks
independent mutation, hook effects/counts and zero retained storage over 100
iterations; rejection cases cover effect contracts, strict-copy policy and
stale facts. Snapshot-codec validation follows regeneration for the new HIR
metadata.

The regenerated native snapshot codec passed all three snapshot/schema checks,
including round-tripping an implicit-copy call and effect contracts on both
output backends. The four hosted inferred-copy checks also passed after
integration with the implicit-result ordering fix (seven checks total).


Resource arrays now accept fresh/copied owners through `push` and `insert`,
transfer ownership through `pop` (including indexed removal), and change
capacity through `reserve`. Discarded resource-valued expressions capture and
drop their result once, including discarded pops and factory calls. Their
cleanup remains checked HIR, so its effects and invalidated facts reach callers.
Element overwrite, `clear`/`truncate`, field transfers and transfers from
existing move-only bindings still require further lifetime handling.

Validation: all nine focused array-method, union and implicit-result-order
checks passed, including hosted/native execution on both backends. After
integration with inferred custom copies, all seven hosted array/copy checks
passed; the existing native driver also rejected both discarded-element
fact/effect violations. The fixture retains zero storage across 100 calls.
The preceding inferred-copy revision additionally passed all 134 broader
hosted lifecycle, explicit-copy, copy-source and prelude-cache checks.


The `c277e5d8` integration reached a native fixed point: generations 2 and 3
were byte-identical for both compilers, and paired execution checks passed
with both output backends. The seed predates the lowering changes, so its
first generation differed as expected and a third generation was required.
The final two generations took 63 and 71 seconds under concurrent test load.
All 41 lifecycle/result-order/receiver-lifetime cases then passed against that
native pair. This is an integration checkpoint, not a performance claim.

Replacing a local or owning parameter now evaluates the new value before
running the old owner's drop, then stores the replacement. The binding keeps
one current owner on branch and scope exits. Ownership follows the declared
storage even when an optional is currently `none`; a narrowed read type does
not erase that storage's lifetime. Borrowed owners still cannot be replaced.

Validation: three focused replacement checks passed in both compilers; the
expanded shared fixture also passed hosted/native execution on both backends.
It covers initializer reads from the old owner, optional absence/reentry,
owning parameters, conditional replacement, invalidated facts and zero retained
storage across 100 calls. The preceding integration also passed 11 adjacent
array/inferred-copy checks. Field replacement and conditional consumption of
outer owners remain pending.


Clearing a resource array now drops its elements in reverse order before the
normal storage release. One checked helper borrows the receiver, so an indexed
route is evaluated once. Its ordinary `void & <items.length =? 0>` return
contract preserves the builtin's length guarantee; no special proof assumption
or caller guard is introduced. Hosted array methods now accept indexed stored
arrays through the same root/immutability checks as fields, matching native
checking. Const roots and explicitly fixed-length storage still reject mutation.

Validation: all eight focused clear/narrowed-array checks passed, including
hosted/native execution on both backends. The shared fixture checks empty and
nonempty arrays, reinsertion, nested arrays, an effectful selector evaluated
once, the static post-call length fact and zero retained storage. Additional
paired checks reject const and fixed-length indexed mutation. Truncation,
element overwrite and general field transfers remain outstanding.

After integration with replacement, all eight hosted clear/replacement/narrowed
array checks passed, including the const and fixed-length diagnostic assertions.

Truncation now transfers the relation `new_length = min(old_length, count)`:
it retains the count upper bound, proves equality when the count fits, and
preserves existing index facts when no elements can be removed. These rules
use pre-mutation named terms and intervals, without reevaluating arguments.
A count proven at least the length is also nonnegative through that relation.

The regression exposed premature place invalidation in both analyzers. Taking
an address now evaluates its route without applying the callee's writes;
argument preconditions can still refer to that endpoint. Contracts are checked
again against evidence common to the argument snapshot and call-entry state,
so later arguments cannot invalidate them silently. Endpoint writes are then
applied before result facts. Fifteen focused hosted checks and the native
acceptance/rejection harness passed, including execution on both backends.

Full-suite checkpoint `40586e70`: 3,424 passed and 14 skipped in 1,855.84s.
The subsequent truncation/call-entry change also passed all 76 adjacent hosted
array, dependent-index, projected-place and length/order-fact checks.

CI follow-up: the release job at `40586e70` reached packaging after verifying
three native generations, but packaging still compared stages 1 and 2. It
now compares the last two stages recorded in the checked manifest and verifies
the distributed binaries against the final stage. Unrecorded stale stage files
do not change that choice. Eight packaging checks passed, including valid-hash
mismatches and three-generation builds with different stage-1 output. The
updated script also packaged the actual verified `c277e5d8` three-generation
pair successfully. The remote pytest workflow was still running at this check.

Synthesized record and union copies now construct independent resource
components through their declared hooks, including nested wrappers, optional
absence and fresh temporary receivers. A helper borrows the receiver once;
component calls and result obligations remain ordinary checked HIR. Types
containing move-only components cannot acquire an independent copied owner.
The copy report labels implicit operations as resource copies, classifying
union storage separately from records. Array/container copies remain pending.

Validation: all 132 hosted lifecycle checks passed. The component-copy and
existing inferred-copy harnesses passed hosted/native execution on both output
backends and their rejection cases. The shared fixture checks hook results,
independent mutation, effect checking and zero retained storage over 100 calls.
A test-harness adjustment retains the existing unsupported-lifetime diagnostic
category for an inferred move-only conflict; it still requires native rejection.

Bounds checking now reuses the transitive parameter-effect proof to preserve
facts across read-only, nonescaping place calls. Unknown callees, ambiguous
pairings, writes and escaping storage remain conservative; implicit global
writes still invalidate their own roots. Argument evaluation and call-entry
preconditions retain the ordering established in the preceding fix.
Relational result contracts also retain their current numeric consequence,
so a returned array with the source's known length carries that exact length.
The source's ordinary copy loop proves this contract through its loop invariant.

Validation: eight focused hosted cases and the native acceptance/rejection
harness passed on both output backends. All 83 adjacent hosted effect,
truncation, dependent-index and projected/length-fact checks passed. This does
not yet preserve untouched subfields of a parameter that the callee mutates
elsewhere; that needs finer route-specific invalidation.

Imported read-only calls now use the loaded declaration graph in both
compilers. Previously the source module's isolated effect scan could not
resolve an imported body, so a safe borrow lost its facts. Native validation
shares one transitive summary across the loaded modules, including generated
lifecycle helpers placed in a different module. Standalone bounds-analysis
clients retain the single-root default. Unknown calls and imported mutators
still invalidate borrowed endpoints.

Validation: nine hosted call-fact checks passed. The imported reader/mutator
harness passed native/hosted acceptance, rejection and execution on both
backends using the current integration driver. A new fixed-point integration
is still required; this local comparison alone does not certify it.

Synthesized array copies now build each resource element through checked copy
operations, including nested arrays, optional elements and fixed-length arrays.
The helper proves its result length against the borrowed source; inferred
copies retain an implicit-cost note, while explicit copies work under
`$explicit_copies`. Component hooks may change values, so their output is
constructed rather than treated as a physical snapshot of the source.

Generated clear helpers now contain an explicit return proof obligation.
Their earlier signature declared the zero-length fact but did not itself
cause the body to be checked. Tests remove the clear operation, or the append
from a generated copy loop, and require bounds validation to reject the broken
helper. This corrects that validation gap rather than trusting generated HIR.

Array element facts now retain common static lengths from literal elements,
copy them to independent arrays, and widen or forget them on insertion and
mutation. Evidence comes from evaluated values' static types, not reevaluating
an argument or reading a binding after another argument changed it. Mutating
an indexed child invalidates the parent's common element facts.

The hosted result ABI now supports exact outer arrays containing dynamic rows,
strings and optional cells. Nested rows own their storage; result writes retain
owned elements rather than leaving handles into a released source. Optional
array places lend the selected cell, matching the parameter ABI.

Validation: 78 focused checks passed, including three native comparison groups,
strict explicit-copy acceptance and implicit-copy rejection, generated-contract
corruption checks, and existing fixed-array lowering. The shared resource-copy
fixture checks seven copies, twelve drops, independent mutation and zero retained
storage over 100 repetitions on both output backends. Imported-effect integration
and broader ownership regressions are checked separately before the native
fixed-point checkpoint.

After importing the module-effect fix, all 181 adjacent hosted lifecycle, array
storage, projected-place, borrowed-call and generated-contract checks passed.
The remote pytest checkpoint at `40586e70` and the post-packaging-fix native
release at `d858cf4e` both completed successfully.

Checkpoint: indexed array and record-field routes now retain length facts
when their selector is an immutable local. Re-entering that declaration in
a loop invalidates the old selection; writes through other indices still
invalidate potentially aliased routes. Receiver mutations preserve their
newly established length while dropping dependent element evidence. The
hosted resident-prelude rollback also removes selector dependencies for
discarded routes, and the native cache schema includes this metadata.
This prepares ordinary fact tracking for mutable local places; it does not
yet implement those places or establish disjointness between indices.
Validation: 39 hosted cache/bounds checks passed; the immutable-selector
acceptance/rejection corpus, including record fields, executes through both
compilers and both output backends.

Checkpoint: warm-prelude differential execution caught three lifecycle
fixtures failing in a self-built compiler despite byte-identical generations.
A flow join from a record union to its parent retained the child payload
without converting its storage: cleanup then used the parent's allocator
size class, and the union wrapper was abandoned. Native joins now consume
their already-evaluated owner through the same conversion used for checked
casts. Retagged cell results transfer directly; unchanged cells need no copy.
The hosted counterpart now retains the destination record type when lowering
a flow binding and extracts/copies a union payload into that layout, instead
of treating its cell address as a record. The regression exercises both
branches, differently sized descendants, independent mutation and zero
retained bytes. Validation: 80 focused ownership/copy checks passed; the new
join regression and four adjacent union/lifecycle fixtures run through both
compilers and both output backends, using a freshly native-built driver.
An earlier version of the native conversion also produced byte-identical
second and third generations and passed the three warm-cache regressions.

Follow-up from the reduced case: explicit stored `(Base & ~Child) | Child`
reached an unhandled `TypeAnd` in hosted union-storage selection. The record-
family checkpoint below closes that storage gap; the concrete child-union
reproducer above independently covers the earlier flow ownership fix.

Full-suite checkpoint at `b23ff134`: 3,481 passed, 14 skipped, two failures
in stale harness interfaces. The query-cache spy now forwards the shared
effect context; the length-transfer kernel comparison passes its caller's
truncate decisions and excludes caller-installed named-count relations.
Those relations retain independent source-level acceptance/rejection tests.
All 20 affected and adjacent checks pass after repair. The later flow-join
fix was validated separately as recorded above.

Integration checkpoint at `a91af1f9`: the direct native compiler pair reached
byte-identical second and third generations, with no hosted compiler or C
backend in the loop. Those generations took 62 s and 74 s respectively;
these are integration measurements, not a performance-target claim. All
152 Phase 1 parity cases passed against the final pair, including the
warm-cache lifecycle cases. The release job at `47fbc9cd` also passed.
Artifacts: `../dewy-build-artifacts/phase1-flow-join-final-2026-09-21` and
`../dewy-build-artifacts/phase1-flow-join-parity-2026-09-21`.

Checkpoint: scalar snapshots retain equality in the ordinary mutable fact
state. Changing either endpoint invalidates or transfers that relationship;
no special trusted rule is used for compiler-generated temporaries. Hosted
result contracts also retain the numeric consequences of symbolic bounds,
matching native comparison refinement. Parameter annotations now constrain
hosted assignment storage consistently with annotated locals and native
parameters. Previously a private parameter could be assigned an out-of-
contract value while its old facts were reinstalled by analysis.
Validation: 72 adjacent hosted checks passed. The scalar snapshot and
parameter-store corpus passes both compilers and both output backends using
a freshly native-built driver. Indexed scalar selections remain separate
work; snapshot equality does not equate every element of an array.

Checkpoint: resource-array `truncate` drops its suffix in reverse order before
releasing element storage. Counts above the current length are a no-op;
negative counts still require a proof failure. Selectors and the count are
captured once. The suffix helper proves that it preserves array length,
then the existing builtin transfer computes `min(old_length, count)`. This
uses an ordinary checked pre/postcondition, not a trusted generated fact.
May-write summaries reject selector/count expressions which replace or
relocate the selected receiver; proven read-only borrowed calls remain
usable. Hosted summaries include imported bodies as well as local hooks.

Validation: the final candidate passed 32 hosted/native checks, including
both x86-64 and C execution, symbolic length contracts, selector/count
side effects, imported counts, invalidation, and an intentionally damaged
helper whose length claim must be rejected. Repeated nested resource
truncation retains zero bytes. The preceding paired batch also passed the
clear, const-index, and ordinary truncation corpora (49 passing checks;
its two failures were repaired in this final batch). Seventy-two adjacent
hosted annotation/bounds/place checks passed. The native driver was built
by the verified native pair, not by the hosted compiler. Whole-compiler
integration and the updated full suite are separate subsequent gates.

Checkpoint: scalar facts now follow indexed elements selected by a literal or
immutable binding, alongside the existing field and sequence-length routes.
A guard can establish a selected denominator is nonzero, and a store can
establish its new value. Writes through potentially aliased indices, owner
mutation, and loop re-entry invalidate the evidence; mutable selectors do
not acquire persistent element identities. Assignment analysis evaluates
its operands once and records the result only when its target stayed stable.
Validation: eight hosted acceptance/rejection cases pass. The bounds-only
native visitor agrees with hosted analysis, and a freshly native-built
program driver passes the cases through both compilers and both backends.
These are ordinary array facts, not a special rule for generated helpers or
permission to assume distinct indices are disjoint.

Checkpoint: resource field and element replacement now uses the same lifetime
order as local-owner replacement. Selectors and the new value are evaluated
once, the old value's drop and component cleanup run, and the replacement is
stored through the rooted mutable place. Optional absence, nested arrays and
borrowed receivers follow the same path. A shared selector helper also serves
truncation; may-write summaries fence side effects that invalidate a selected
receiver. Drop calls remain ordinary checked operations, so their fact and
effect consequences are visible before lowering.
Validation: 28 focused checks passed using a freshly native-built program
driver, covering both compilers and both x86-64/C backends, adjacent clear and
truncate behavior, imported effects, optional/nested replacement, single
selector evaluation and zero retained bytes over repeated replacements.

Integration checkpoint at `61a044bd`: the direct native pair reached a
byte-identical generation 2/3 fixed point and passed its execution checks.
All 155 Phase 1 parity cases passed with shared prelude caching against the
final pair. Generations 2 and 3 took 131 s and 164 s while the full suite and
other checks ran concurrently; these timings are not performance baselines.
Artifacts: `../dewy-build-artifacts/phase1-truncate-integration-2026-09-21`
and `../dewy-build-artifacts/phase1-truncate-parity-2026-09-21`.

Full-suite checkpoint at `61a044bd`: 3,514 passed, 14 skipped, one bounds-
visitor mismatch. Native retained the identity of a block's saved scalar
result while hosted analysis retained only its numeric interval. Hosted
blocks now expose that identity only when trailing statements cannot change
it; assignments and mutable calls invalidate it. All 65 cases now agree
with the native bounds visitor produced by the full run.

The new result-order regression also exposed hosted conditional-return
lowering using a branch's last statement as its result. It now saves the
unique expressed value before trailing statements and returns it afterward,
matching the native implementation and the existing function-body rule.
Validation: 17 adjacent hosted checks pass. Positive/negative result-fact
cases and string/array snapshot cases pass both compilers and both backends.
No µDewy semantics changed. The full-suite count above records the original
run; it is not a claim that the entire suite was rerun after this repair.

Integration checkpoint at `1ef6c8d1`: the direct native pair again reached a
byte-identical generation 2/3 fixed point and passed execution checks. All
eight selected integration cases passed, including indexed scalar facts,
resource slots and block-result repair. Generations 2/3 took 64/73 s; this
remains above the native latency target. Artifacts are under
`../dewy-build-artifacts/phase1-resource-slots-integration-2026-09-21`
and `phase1-resource-slots-parity-2026-09-21`.

Checkpoint: mutable local places now select rooted bindings, record fields
and array elements. Selectors are captured once; ordinary checked assertions
prove valid selection at declaration, including an unused place. The same
structured lifetime analysis as required views includes derived aliases and
rejects owner replacement/resizing before their last use, captures and raw
exposure. Normal place lowering retains COW snapshot independence and const
barriers; no raw pointer survives between uses.

Storage contracts remain invariant, including declared refinements. Alias
writes invalidate source-checker owner facts and vice versa. Before ordinary
fact/effect/lifecycle checking, rooted selections replace alias reads/writes
and rebind dependent fact identities, including projected terms and nested
types. Native type factories preserve arena keys; only functions containing
aliases are rewritten. Speculation and hosted prelude rollback retain the new
metadata correctly. Debuggers currently expose the rooted owner instead of a
separately stored alias variable. Dictionary-entry and captured/exposed-owner
places still need further lifetime work.

Validation: 60 adjacent hosted view/cache checks passed. The final 37
acceptance/rejection cases and integration fixture pass both compilers and
both x86-64/C backends through a fresh native-built program driver. Coverage
includes generic instances, loop selectors, dependent refinements, alias
invalidation, resource replacement/drop, effects and explicit-copy policy.
The former test requiring mutable places to be unsupported was removed;
rejections for unstable selections and const storage remain.

CI checkpoint at `1ef6c8d1`: 3,517 passed, 32 skipped, one failure. The
remaining failure was an obsolete test expecting resource-field replacement
to be unsupported, after that operation had landed. It now executes the
replacement and checks the exact `42` then `1` drop trace; all 51 adjacent
hosted lifecycle checks pass. This updates the expected supported behavior,
not the compiler's acceptance rules. CI's release workflow passed separately.


Checkpoint: the same last-use proof now supplies existing owners to function
arguments, forwarded owning parameters, record/array construction, insertion
and field/element replacement. These are ownership inputs with one rule,
not separate syntax-specific move permissions. A first if condition is an
unconditional input site; branch bodies, repeated loop conditions and later
arms cannot consume an outer owner through this same-block proof.

Dependent read-only aliases extend the source lifetime, accounting for when
those aliases are created. The destination of the current transfer is not
an already-live alias. Custom move hooks run as checked calls, their remaining
nested fields are released, and the consumed owner does not drop twice.
Surviving sources requiring independent ownership still need a copy hook;
that rejection is now an ordinary ownership diagnostic. This does not yet
implement conditional outer-owner joins or field ownership transfers.

Validation: all 70 adjacent hosted lifecycle checks pass. Twelve new execution
cases, six adjacent/integration kernels and six rejection cases pass both
compilers and x86-64/C backends through a freshly native-built program driver.
The kernel checks exact hook/drop counts and zero retained arena bytes over
100 repetitions. Existing local-transfer, move-effect, resource-view and union
fixtures remain covered. Tests that formerly required array/record transfers
to be unsupported now check their single-drop execution behavior.


Integration checkpoint at `c2cc99a7`: the direct native pair reached another
byte-identical generation 2/3 fixed point, and all 160 parity cases passed.
The interrupted full pytest run found 17 failures (2,791 passed, 14 skipped),
mostly sharing a hosted build failure in the native program driver. This is
not a full-suite pass: native fixed points did not detect a hosted/source
parity gap in a bare `capture` declaration shadowing the prelude function.

The declaration now explicitly shadows with `let`; native function
predeclaration and imported-binding assignment enforce the existing rule.
A local-view diagnostic now supplies its required pointer message. The shared
source-checker tests no longer expect mutable local places to be unimplemented:
local usage is supported, while a module-level escaping selection is rejected.
37 adjacent checks passed; an initially malformed new execution case was
corrected to suppress its discarded call result. All corrected foreign-name,
import mutation, explicit-shadow and local-view cases pass both compilers and
both backends through a freshly hosted-built native program driver.


Loop-entry repair: source checking now distinguishes one-time iterator inputs
from repeated Boolean predicates and loop bodies. Both checkers retain entry
facts for iterable evaluation, then invalidate facts about backedge writes
before checking repeated code. This fixes a guarded pop nested inside an
iterator expression without requiring a split source expression.

The negative regression exposed an older native gap: unindexed pop had no
final non-empty obligation, so a two-iteration loop could pop a one-element
array twice. Both bounds visitors now prove positive length at each reachable
pop. The hosted source visitor defers dynamic proofs to this stage, permitting
valid finite-loop pops and retaining immediate empty-array diagnostics. Its
bounds visitor also evaluates an array-method receiver before the arguments.

Validation: 68 hosted iterator/array checks passed; four positive and four
negative cases pass both compilers and both backends using a fresh native
program driver. The old native pair accepted the over-pop counterexample;
the repaired driver rejects it. Finite two-element/two-pop iteration and the
nested guarded worklist loop execute with result 42. Repeated predicates and
an unguarded parameter pop reject. The integration manifest now includes the
worklist and over-pop cases.


Placement checkpoint: both allocation-effect checkers and lowerers now use
one bounded proof for fixed scalar local arrays. Only length/element accesses
are permitted: descriptor escapes, captures, address-taking, replacement and
resizing exclude this route. A conservative 4 KiB budget per function bounds
frame storage. Each slot is allocated in the prologue and reused when its
declaration executes again. Native descriptors mark the frame as owner;
ordinary release does not free it and writes need no COW detach.

This permits `no allocates`/`no_effects` for proven local array computation,
including inferred calls and defaults, while retaining allocation permission
for unproved aggregate storage. It is an implementation proof budget, not a
source array-size limit. General placement, scoped arenas, escaping aggregates
and placement through nonescaping calls remain further work.

Validation: 119 adjacent hosted allocation/effect checks passed. Five runtime
cases and eight rejection cases passed both compilers and x86-64/C backends
through a freshly native-built driver. The kernel repeats 10,000 times with
zero arena bytes allocated, covering mutable words, bools, narrow integers and
empty arrays. Capture/escape, resize/rebinding and per-function budget limits
reject. The hosted compiler also successfully emitted the updated native
program driver. Additional iterator rejection probes exposed a pre-existing
native unindexed-pop proof gap, repaired separately; they are not counted as
passes here.


Recursive ownership checkpoint: cleanup now closes recursive type expansion
with checked borrowed helper calls, publishing each helper identity before
building its body. Runtime recursion follows the active, finite stored values.
Hooks still run before fields, and fields/array elements retain reverse cleanup
order. Transparent casts naming a fresh value through a recursive alias retain
its ownership; they do not create an implicit copy. Arrays containing recursive
optional-link records work. The separate language gap for recursion *through*
`array<Self>` remains unimplemented, as does general recursive field transfer.

Validation: 66 hosted lifecycle checks passed. Five execution cases and two
rejections pass both compilers and both backends through a fresh native-built
program driver. Coverage includes linked and branching records, reverse array
cleanup, recursive factories, exact hook order/counts, effect contracts and
move-only independence. A 100-call kernel drops all 300 nodes and retains zero
arena bytes. No new source syntax or lifecycle semantics were introduced.


Integration checkpoint at `386475fb`: native generations 2/3 are byte
identical and execution checks pass on the direct and C backends. Generation
2/3 took 92/97 s with other tests running; these are not isolated performance
measurements and remain above the latency target. Artifacts are under
`../dewy-build-artifacts/phase1-placement-integration-2026-09-21`.

The next interrupted full run at `fc9030f4` recorded 3,425 passes, 14 skips and
two failures. One was the newly exposed unindexed-pop gap repaired above;
the other was an outdated generated snapshot codec omitting `local_place_roots`.
The codec is regenerated, its outer format is bumped to 7, and the snapshot
fixture now checks that nonempty owner-map data survives. The generator
freshness test passes. A new full run includes these fixes and recursive cleanup;
these interrupted counts must not be represented as a full-suite success.

Native execution-test groups now share only their checked prelude cache within
a worker and compiler binary. Each input still starts a fresh process and
Session. Explicit cold-cache tests retain an opt-out. A paired two-group
probe took 33.82 s cold and 4.38 s warm, with acceptance/rejection and both
backends checked. This removes repeated setup rather than reducing coverage.

Recursive-copy checkpoint (2026-09-21): hosted method hoisting now publishes
a fully annotated signature before checking its body, matching native method
predeclaration. A copy hook can therefore recursively copy its optional tail.
Both ownership passes also accept fresh conditional/block initializers,
capturing each branch's expressed value before releasing its local owners.
Trailing statements retain their original evaluation order. Synthesized
recursive wrapper copies use the same component-hook rules. This does not
introduce first-class lifecycle hooks or conditional consumption of outer
owners. Read-only receivers, move-only restrictions and effects remain checked.

Validation: 92 hosted adjacent lifecycle cases passed; four positive and three
negative cases passed on both compilers, with each positive executed through
x86-64 and C. Cases cover custom and synthesized recursive copies, branch
cleanup, trailing statements, receiver writes and empty effect contracts.

Branch-local result checkpoint (2026-09-21): an expressed value in a resource
block is now an owning input to the existing bounded last-use analysis.
Move-only locals can leave either branch without a synthesized copy; later
reads/writes and dependent aliases still prevent transfer. Statements after
the value retain their evaluation point. Outer-owner joins remain separate.
Validation: ten hosted checks and six positive/four negative paired cases
passed, with all positives executed through x86-64 and C.

Affine-loop checkpoint (2026-09-21): the bounded qualifier vocabulary now
connects exact entry-value groups with constant differences, while retaining
separate equality groups when another counter advances at a different rate.
Every advancing edge must preserve a candidate. At most 64 entry terms are
considered, with linear-size stars rather than all pairs. A one-hop reduction
combines interval and difference evidence when proving an update fits its
word. Rollover invalidates affine facts, including a narrow operation widened
into a wider destination; mathematical order cannot survive modular wrap.

Validation: 32 adjacent hosted loop/proof checks passed. Five positive and six
negative cases passed both compilers and x86-64/C; the new native driver also
successfully checked and emitted its own complete source. The manifest adds
nonzero parallel-array differences and narrow-operation rollover rejection.
This extends the bounded proof machinery without adding source syntax.

Completed full-suite checkpoint at `c2cc5330`: 3,628 passed, 14 skipped, two
failed in 2,341.73 s. Both failures were outdated expectations: a guarded pop
retains a weaker nonnegative difference, and fixed nonescaping scalar arrays
now satisfy `no allocates` through frame placement. The revised tests retain
strict-positivity/index rejection and runtime-length escaping-array rejection;
all 21 adjacent tests passed. The website's unchecked `nat64` sum now checks
fixed-width overflow, and all 329 published examples validate. These repairs,
recursive copies, branch-local transfers and affine qualifiers are integrated
at `bd17c8c5`; 43 focused integrated checks pass. The previous CI run at
`fc9030f4` completed with 3,585 passes, 32 skips and only the two already-fixed
pop/snapshot failures. Website CI is green at `bd17c8c5`; full CI remains a
separate gate, not a claimed pass.

A fresh native inventory of `c2cc5330`, using the verified `386475fb` native
pair, records 4,919 bootstrap-only static copy sites across 45,661 physical
Dewy lines (107.729 sites/KLOC): 1,185 records, 667 arrays, 479 cells and 2,588
strings. This is a scoped inventory, not a comparison with the earlier
whole-program baseline, nor a count of runtime allocations/bytes. Detailed
output is `/tmp/dewy-phase1-copy-inventory.json`. The reporting path rescanned source prefixes and rendered thousands of
source excerpts that the inventory tool then discarded. Concise reporting
and shared source geometry address that avoidable work.

Copy-inventory gate checkpoint: `dewy analyze --brief` preserves every copy
entry/count without rich excerpts; hosted move, representation and cap notes
remain available in concise form, and unsafe auditing is not suppressed.
Native reporting reuses immutable source-line indexes, and lowering memoizes
copy type names. The inventory tool defaults to concise mode, with
`--legacy-analyze` retained for historical compiler seeds. The existing native
command test now gates the bootstrap at 5,000 static sites and 110 sites/KLOC.

Validation: 14 hosted report/CLI checks and 11 options/tool checks passed.
Native rich/concise inventories agree with CRLF and Unicode source offsets.
A padded-source warm probe took 3.199 s rich versus 1.520/1.473 s concise,
with identical entries; this measures reporting overhead, not compiler build
latency. The full own-source gate records 4,932 sites over 45,710 Dewy lines
(107.898/KLOC), taking 62.98 s and 2,694,940 KiB peak RSS. Artifacts are
`/tmp/dewy-phase1-copy-budget.{json,log}`. These budgets are static reporting
ratchets, not permission to hide copies or substitutes for byte-level kernels.

Integration checkpoint at `bd17c8c5`: direct native generations 2/3 are byte
identical; generation times were 64/74 s with other work running, still above
the latency target. Direct and C execution checks pass, and all 168 expanded
hosted/native parity cases pass. The pair and parity outputs are under
`../dewy-build-artifacts/phase1-affine-{integration,parity}-2026-09-21`.
The concise-report change is subsequent to this fixed-point certification.

## Unwritten local view lifetimes (2026-09-21)

An unwritten `let` projection now uses the same shorter lifetime proof as a
`const` projection in both compilers. The source must remain stable through
the last use of the view and its derived aliases; captured, exposed, written
or escaping bindings still need independent values. This introduces no new
aliasing semantics. Early source eligibility checks avoid scanning scopes
whose owners cannot satisfy the private-storage proof.

Validation: 71 adjacent hosted checks passed. A freshly built native program
driver passed 12 positive and one negative case against the hosted compiler,
with accepted programs executed through both direct and C backends. The
strict-copy fixture checks zero allocation during reads and zero retained
storage after repeated calls; writes through scalar and array fields, owner
mutation, and a captured local retain independent values.

## Shared forwarding storage proof (2026-09-21)

Allocation contracts and both lowerers now share a read-only array-parameter
forwarding proof. A whole-caller access summary rules out later-argument
writes; a closed call graph excludes nonlocal storage, raw operations and
unresolved callbacks. Parameter and representation agreement are required.
Default expressions participate in the graph. Native operator purity uses
the binding registry, so a user function named like an intrinsic cannot
acquire its guarantees. Recursive and named forwarding can satisfy
`no allocates` or `no_effects` without treating COW deferral as proof.

Validation: 73 adjacent hosted checks passed. A fresh native driver passed
the zero-allocation fixture and six rejection cases against hosted checking;
the fixture executes through direct x86-64 and C. That driver also checked
and emitted its own complete source successfully (20 MB of emitted µDewy).
This is the first shared argument-storage slice; other projection borrows,
moves and placement still need to feed allocation checking.

Full CI checkpoint at `bd17c8c5`: **3,636 passed, 32 skipped**, in 2,618.68 s.
The website and native release checks are also green. Subsequent concise
reporting, unwritten-let views and forwarding proofs have their own targeted
validation and await the next full integration run.

## Excluded record-family storage (2026-09-21)

Hosted checking and lowering now share the native compiler's structural-base
query: exclusions restrict values while comparable positive record types
determine layout. Logical alternatives retain their own tags and predicates.
Union packing selects among descendant/exclusion alternatives by dynamic
brand when the source fits the union collectively. Native checking now permits
that already-proven case to reach its existing dynamic packing path.

Field reads/writes, copies, release and lifecycle capability queries use the
positive storage view. Nested descendant tests no longer treat every excluded
record family as disjoint from all other records. Splitting a stored parent
alternative into several descendants preserves the correct child field offsets.

Validation: 58 adjacent hosted checks passed, followed by all 12 final focused
cases. Nine positive and three negative programs pass both compilers, with
positives executed through x86-64 and C. They cover parent/child/grandchild
values, sibling narrowing, independent fixed-array copies, frame-only storage,
move-only resources and rejected copies, logical fact retention and zero
retained allocation after repeated calls. The hosted compiler also checked
and emitted the complete native test driver (49,897,821 bytes).

The preceding forwarding-proof snapshot's native own-source inventory passes
the unchanged 5,000-site / 110-per-KLOC gate at **4,865 sites / 45,841 lines =
106.128 per KLOC** (67.85 s; 2,712,860 KiB peak RSS). This is a static inventory,
not a runtime byte count or a full native build latency measurement.

## Inherited resource moves (2026-09-21)

Compiler-generated inherited move wrappers now adopt added resource fields,
including arrays and multiple inheritance levels. The original user hook still
operates on its parent portion. Cleanup follows the composition chain and drops
only that hook's leftover fields; transferred child fields belong to the result.
This privilege applies only to checked compiler-generated composition, not to
ordinary borrowed receivers. Inherited copy hooks still require copyable added
fields. No surface syntax or hook invocation guarantees change.

Validation: 44 adjacent hosted checks passed. A fresh native driver passes the
fixture and two rejection cases against hosted checking; accepted programs run
on x86-64 and C. Exact drop traces distinguish the consumed parent fields from
transferred children, and arena counters check complete storage reclamation.

## Storage integration checkpoint (2026-09-21)

At `38b8cec8`, generations 2/3 of both native compilers are byte identical
through the direct x86-64 route. Direct and C execution checks pass, as do
all **173** explicit parity cases. Artifacts are under
`../dewy-build-artifacts/phase1-storage-{integration,parity}-2026-09-21`.
Generation times were 68/78 seconds with concurrent work, not isolated
performance baselines; the direct-route latency target remains outstanding.

## Conditional resource consumption (2026-09-21)

A backwards liveness pass joins the possible future reads of each branch.
An owning input at last use may consume an outer owner on that path. Aliases,
captures, overlapping sibling arguments and later uses retain ownership; loop
backedges remain conservative. Existing same-block transfers remain available.
The compiler inserts an ordinary boolean only for owners needing conditional
cleanup. This tracks logical resource ownership; the storage lowerer retains
its separate borrow/copy/move decisions. No source annotation is needed.

Flags are initialized beside the owner's declaration, or at entry for owning
parameters. Transferred owners remain in lexical cleanup lists, preserving
scope and loop boundaries. Custom moves still clean their leftover fields
before deactivation. Native lowering now treats unscoped void statement groups
as part of their enclosing storage lifetime, while selected arms retain their
own scope; generated transfer declarations are not released before later uses.

Validation: all 207 selected hosted lifecycle checks passed, plus the repeated
conditional kernel. A fresh native driver passes ten positive and six negative
conditional cases against hosted checking, running accepted cases through both
x86-64 and C. Adjacent consumption, recursive copies, inherited moves, resource
array operations and ordinary container text cases pass on the same routes.
The driver checked and emitted its own complete source (20,910,854 bytes;
70.83 seconds, 3,016,084 KiB peak RSS). This batch follows the fixed-point
checkpoint above and is not yet a new fixed-point certification.

## Iteration-local ownership (2026-09-21)

The branch liveness proof now distinguishes owners created during an iteration
from owners that must survive its backedge. Iteration-local owners may transfer
inside conditional branches, including break/continue paths and nested loops.
A return ends the function rather than advancing the loop, so an owning input
on that exit may also consume an outer owner. Other repeated consumption of
outer owners remains rejected. No loop-count heuristic or source annotation
is involved; the distinction comes from birth scopes and control-flow exits.

Validation: 23 focused and 68 adjacent hosted checks passed. Four positive and
three negative cases pass a freshly built native driver against hosted checking,
with all accepted cases executed through x86-64 and C. They check immediate
versus end-of-iteration drop timing, break/continue cleanup, function returns,
nested loops, rejected repeated consumption, and complete storage reclamation.

## Resource iterator source lifetimes (2026-09-21)

Resource arrays and dictionaries now use ordinary lexical owners for iterator
sources. Existing move, copy and read-only-view proofs choose how to keep each
source alive. Read-only loop bindings borrow their elements; an owning value
boundary in the body invokes the usual checked copy. Fresh factory results
receive logical cleanup on returns, breaks, continues and normal completion.
Dictionary key/value leaves share one evaluated receiver. Multi-iterator setup
preserves source evaluation order, including ordinary sources before resources.
The existing restriction on dictionary mutation during iteration is unchanged.

The hosted borrow planner now recognizes stable single-place parameters when
no ambient call or alias can change their storage. Native lowering no longer
rejects an addressed source after the borrow planner has proven its lifetime.
The hosted padded-iterator path stores a borrowed element word into its cell;
it must not treat an already-lowered record load as an owning function call.

Validation: 21 focused hosted checks and 59 adjacent borrow/view checks pass.
Resource iteration and place-view programs run through hosted/native checking
and x86-64/C execution, including zero retained bytes over 100 early-return
loops. The final source-order/dictionary-source/view bundle passes five
positive and seven negative cases. The rebuilt native driver checks and emits
its own source (21,229,873 bytes). The preceding `5e4281cb` direct-route fixed
point also completed all 184 explicit hosted/native parity cases; this newer
batch is not yet a fresh fixed-point certification. These changes do not
complete Phase 1: entry places, broader field transfers and placement, full
strict-copy acceptance, effect-row inference and proof provenance still need
work.

## Dictionary fallback lifetime correction (2026-09-21)

The first executable effect-row inference kernel exposed a hosted `.get`
lifetime bug. A read-only record binding borrowed the dictionary's storage,
but a missing key selected a newly constructed fallback. Statement cleanup
released that fallback's nested strings before the next statement used them.
Both lowerers now require an independently owned result when an unproven
lookup can select a fallback; stability of the dictionary alone is not a
lifetime proof for the fallback. Proven entry borrows retain their usual path.

The reduced fixture fails before the hosted fix and passes afterwards on
x86-64 and C, including zero retained bytes across 100 calls. The newly built
native driver passes the same fixture and the effect solver kernel against
the hosted compiler on both backends. Nine focused and 34 adjacent hosted
checks passed. Source-level inference is still being connected to the solver.

Integration checkpoint: `f7e5c1ec` closes the direct native bootstrap with
byte-identical generations 2/3, direct/C execution checks, and all **186**
explicit hosted/native parity cases. Generation times were 68/79 seconds
with concurrent work, not isolated latency baselines. Artifacts are under
`../dewy-build-artifacts/phase1-iteration-f7e5c1ec-*`. CI also completed at
`5e4281cb`: **3,803 passed, 32 skipped** in 55m24s. Neither result certifies the
newer fallback correction as a new fixed point.

## Public effect-row inference machinery (in progress, 2026-09-21)

Both implementations now have an independent monotone row solver. Function
bodies seed possible behavior; selected assignment constraints widen inferred
destination rows. Unknown operations and unresolved user row parameters remain
unknown or symbolic. Explicit permissions are removed before inferring a row's
residual; negative contracts are checked against the result and never erase
possible effects. Reverse dependency worklists handle recursion and long chains.
The public-effect body inventory is now callable without a written contract;
ordinary validation reuses it. Connecting inferred rows to source callable
types and recording selected-boundary obligations is still outstanding.

Validation: 33 focused/adjacent hosted checks pass. The Dewy solver executes
through both hosted and native checking on x86-64 and C. Three written-effect
programs and five rejection cases also agree across the two compilers after
the inventory refactor. This is an internal foundation checkpoint, not a
claim that callable-type inference is complete.

## Reassigned callback call targets (2026-09-21)

The inferred-callable tests exposed an independent native lowering bug: a
callback variable reassigned from one function to another could still call
its initial function. Call-target discovery now invalidates initializer-only
resolution after assignment or writable exposure. Saved function handles
retain their value semantics. The focused regression passes hosted/native
checking and x86-64/C execution, including repeated assignment and a saved
handle. Function-handle place parameters remain separately unsupported.

## Inferred callable rows (2026-09-21)

Omitted function-literal rows now receive compiler identities shared by
prebinding, body checking and generic specialization. Ordinary callback type
annotations with no row remain open. The fixed point combines body behavior
and selected value-boundary constraints; speculative subtype/overload probes
do not contribute assignments. Deferred checks preserve the actual value
type, survive lifecycle insertion and erase before runtime lowering. Native
cache codecs retain the new metadata. Internal identities are not displayed
as source syntax.

A copied callback handle gets an independent inference variable: reassigning
it cannot widen its source function's own row. Compatible conditional callable
shapes join possible behavior instead of introducing distinct runtime variants
solely because their inferred rows differ. Recursive and generic callbacks
retain their body effects, and unknown operations stay unknown. Union and
overload boundary checks are conservative when several alternatives compete.

Scoped polymorphic place rows still need a retained substitution environment.
Until that exists, moving an unresolved inference variable to a different
place scope contributes unknown behavior rather than reusing an unrelated
parameter index. Preserving open negative guarantees through inferred wrappers
also remains pending; the positive-row solver does not infer such exclusions.

Validation so far: 142 adjacent hosted effect/lifecycle/proof checks and 44
focused row/callable checks pass. The preceding native build passed seven
positive and six negative callback cases on x86-64/C against hosted checking,
and checked/emitted its own source (21,670,022 bytes; 61.95 seconds and
3,101,360 KiB peak RSS under concurrent work). The final batch passes eight positive and eight negative cases on both
compilers/backends, including lifecycle cleanup. After the unannotated-program
fast path and literal-reassignment correction, another 104 hosted checks and
the final two positive/three negative native cases pass. Twelve hosted cache
checks preserve cold/resident/on-disk behavior. These are bounded development checks, not
a new native fixed-point or latency certification.

The rebuilt native CLI reports **4,992** bootstrap copy sites over 47,049
source lines (**106.102/KLOC**), within the unchanged 5,000/110 gates. Inventory:
`../dewy-build-artifacts/phase1-inferred-effects-copies.json`. The absolute
budget is close; subsequent batches must keep reducing unproved copies.

## Immediate dictionary key borrows (2026-09-21)

Native membership and default-free lookups now borrow a string binding until
probing finishes. The probe runs no user code, so a later assignment to the
binding does not require an independent handle. Longer intervals still use
the existing stability proof; in particular, an eager lookup default can
change the key and retains the earlier snapshot. This is a lowering proof,
with no new surface syntax. Hosted probes already read these keys directly.

Validation: the key-lifetime fixture passes both compilers on x86-64 and C,
including an eager default that changes a global key. Native analysis removes
five unnecessary key-copy sites in that fixture while retaining the default's
snapshot. The command test checks this inventory distinction; the runtime
fixture also checks that a warmed membership probe allocates no storage.


## Negative guarantees through inferred wrappers (2026-09-21)

Possible effects still grow from bodies and selected assignments. Alongside
that least fixed point, exclusions shrink over a finite vocabulary gathered
from bodies and obligations. Requirements only nominate candidates; every
body and incoming assignment must establish each surviving guarantee. An
unknown operation removes unsupported candidates even in a recursive cycle.
Written permissions are removed before checking an inferred residual.

Both implementations preserve open guarantees through inferred callable
wrappers without pretending those wrappers are pure. Generic row substitution
still carries positive rows, so negative guarantees across a user `E` remain
separate work, as do scoped place substitutions and competing callable
alternatives.

Validation: 22 hosted callable/guarantee checks pass. The native solver kernel,
positive source wrapper and unknown-callback rejection agree with hosted
checking on x86-64 and C. A rebuilt CLI checked the compiler's own source.
The batch initially exceeded the copy gate (5,031 sites); immediate dictionary
key borrowing removes 50 sites in the combined-source inventory, bringing it
to 4,981 (105.642/KLOC), under the unchanged 5,000/110 limits. This preliminary
combined inventory uses the key-borrow CLI; the integrated source remains due
for its own fixed-point check.

The preceding callable-inference revision, `69b8eb8d`, separately completed
191/191 hosted/native parity cases and a byte-identical direct native fixed
point. Its generation timings were 65 and 77 seconds under concurrent work;
these are not isolated latency benchmarks and do not meet the 30-second goal.

## Generic negative effect guarantees (2026-09-21)

Generic row arguments now carry complete contracts, including negative
promises. Inference combines permissions and retains only guarantees shared
by every contributing callback. An unknown callback removes unsupported
exclusions; adding a permission can invalidate an inherited exclusion.
Explicitly written exclusions remain obligations on the complete row.

Binding metadata, signature substitution, instance cache identity and native
prelude serialization preserve these contracts. The ordinary inferred-row
solver shares the same substitution helper. Callback-relative place exclusions
remain rejected as generic row arguments until their scope can be represented;
they must not accidentally name a slot in the enclosing signature.

Validation: 60 hosted effect checks and 12 hosted prelude-cache checks pass.
Two positive programs and one rejection case agree on both compilers and
x86-64/C. A native cached prelude containing two distinct negative-only generic
instances produces identical output before and after restoration, and both
outputs execute correctly on both backends. The rebuilt native CLI reports
4,985 bootstrap copy sites over 47,170 source lines (105.682/KLOC), within the
unchanged 5,000/110 gates. Inventory:
`../dewy-build-artifacts/phase1-generic-guarantees-copies.json`.

The preceding integrated revision, `181db533`, reached another byte-identical
direct fixed point, with native execution checks on both backends. Its own
rebuilt pair confirms 4,981 sites over 47,154 lines (105.633/KLOC). Generation
2/3 took 70/80 seconds during concurrent work; the latency target remains open.

## Full-suite regression repairs (2026-09-21)

The user's failure report was reproducible in CI: revision `80a83728` had
15 failures, 3,866 passes and 32 skips. Earlier selected parity checks did
not establish that the full suite passed. Roadmap work paused for these
repairs:

- Callable arrays and loop captures join the effect rows of otherwise
  identical signatures. Distinct inferred rows no longer cause a misleading
  homogeneous-element error, and the join retains every possible effect.
- Deferred effect checks preserve callable binding, receiver and default
  metadata. This repairs method/default-argument errors and runtime crashes
  without dropping the effect obligations carried by those checks.
- Native method-body inference uses the complete parameter scope, including
  the hidden receiver. Only written contracts need their source parameter
  indices shifted. Prebound signatures retain their inference identity.
- Generic-signature expectations now account for per-instance inferred rows.
  The snapshot regression uses complete generic effect contracts, including
  negative guarantees, rather than the superseded positive-row representation.

The complete local run collected 3,923 tests and finished with **3,904 passed,
14 skipped and five failures** in 76m54s. It started before the final snapshot
fixture and native method repairs landed. The snapshot failure passes its
focused pytest rerun; both method/ordered-call failures pass their original
test functions against the rebuilt native checker. The other two failures
were filesystem fixtures affected by this development session's `/tmp` quota;
both pass their focused pytest rerun after old development artifacts were
moved to disk-backed storage. There were no other failures. This is full-suite
coverage followed by targeted repairs, **not a claim that one final full-suite
invocation was all green**. Local evidence lives in
`../dewy-build-artifacts/pytest-repairs-full.{log,xml}` and the focused repair
logs alongside it.

The first ten new callable regression tests passed in that full run. The final
method repair adds five passing hosted cases and a native harness covering
three valid programs and two rejected contracts, checked against hosted
execution on x86-64 and C. Existing native move-hook and inferred-callback
checks also pass with the rebuilt driver. These checks preserve rejection of
unknown/effectful callbacks under pure contracts and of methods whose written
mutation permission names the wrong argument.

The final compiler repair (`3794df8b`, built in its isolated worktree as
`c5095e30`) closes a three-generation C-backed native bootstrap of both Dewy
and µDewy, with byte-identical final compiler generations and runtime checks
on x86-64/C. The resulting pair is
`../dewy-build-artifacts/pytest-repairs-native-pair`. Its own copy inventory is
**4,985 sites over 47,211 lines (105.590/KLOC)**, within the unchanged 5,000/110
gates (`pytest-repairs-final-copies.json`). Generation 2/3 took 199/201 seconds
while the full suite was running; these are not isolated latency measurements.
Phase 1 and the performance target remain unfinished.

## Effect validation activation (2026-09-21)

The native type table now distinguishes inferred body metadata from contracts
that impose obligations. Omitted rows and private inference variables alone
no longer trigger whole-program public-effect validation and erasure scans.
Explicit permissions, empty rows, exclusions and user row parameters activate
the existing complete validation path. Activation is monotone and remains
part of the cached type table; importing a constrained callable cannot disable
it. Proof functions retain their independent validation/erasure trigger.

Validation: 123 hosted effect/proof checks pass. A freshly built native driver
passes the activation kernel and generic negative-guarantee fixture on x86-64
and C against hosted execution, and rejects both lifecycle and generic
guarantee violations. This removes unnecessary work without changing effect
semantics; no isolated latency improvement has been measured yet.

## Projection stability and forwarded place storage (2026-09-21)

The storage evidence shared with allocation checking now asks whether writes,
rebindings or escapes overlap the particular projection being forwarded.
An untouched sibling field can remain borrowed; replacing an ancestor or
mutating a descendant cannot. Array selectors still use the conservative
shared index step. Ordinary whole-parameter read-only cases take the existing
fast path without constructing a route. Raw exposure, unknown callees and
lifecycle-bearing values retain their restrictions.

The tests also exposed an accounting gap: forwarding a scalar field/element
to a mutating helper could omit the storage obligation imposed on a direct
projected write. Both public-effect analyzers now use the same projected-store
rule for these calls. A disjoint borrow does not establish that mutating the
other field is allocation-free. Known read-only element calls and proven
scalar frame places still satisfy empty rows.

Validation: 16 new hosted cases pass, with eight valid programs and eight
rejections checked by a second-generation native driver against hosted
checking/execution on x86-64 and C. The adjacent aggregate-borrow/access and
public-allocation/effect checks pass (29 and 106 existing hosted cases).
These are bounded checks, not another complete pytest or fixed-point run.

## Frame storage through nonescaping place calls (2026-09-21)

Fixed scalar arrays and scalar records may now lend element/field addresses
to known nonescaping callees while remaining in reusable frame storage. The
public allocation checker and lowering consume the solved parameter escape
summaries. Every possible target and argument position must establish the
lifetime; unknown callbacks, captured owners, whole-container uses, resizing
and the existing frame-size limit retain their restrictions. Forwarding,
recursion and keyword argument pairing need no new source annotations.

The effect collector retains call sites for the new proof, avoiding another
whole-HIR traversal. The native borrow planner also exposes its already
validated place sites to placement. Projection stability shares the route
overlap query instead of constructing concatenated mutation/escape arrays.
The new native escape proof updates its sets rather than rebuilding them at
each call; this removes accidental repeated copying of the growing result.

Validation: the new hosted cases and adjacent frame/projection checks passed
(40 in the first run, with one additional rejection case corrected to avoid
an unrelated bounds error; the corrected six new cases and 52 adjacent
allocation/access checks pass). A second-generation native driver agrees with
hosted checking on five execution kernels and 14 rejections on x86-64/C.
The new 10,000-iteration kernel observes zero arena allocation while passing
array-element and record-field addresses through helpers. Initial compiler
inventory was 4,995 sites over 47,295 lines (105.614/KLOC), within the unchanged
gates. That inventory precedes the final set-update cleanup; a fresh native
fixed point and final inventory are the next integration check.

Integration follow-up: `23a0d7a6` completed the three-generation C-backed
native bootstrap with byte-identical final Dewy and µDewy generations. The
resulting pair passes all **211/211** cases in the hosted/native parity
corpus on the direct x86-64 backend. Its final inventory is **4,986 sites over
47,300 lines (105.412/KLOC)**, within the unchanged 5,000/110 gates. Artifacts:
`../dewy-build-artifacts/phase1-frame-placement-23a0d7a6`,
`phase1-frame-places-parity`, and `phase1-frame-places-final-copies.json`.
Generation 2/3 took 190/198 seconds including C compilation and concurrent
development work; these are not isolated latency measurements.

## Nested getter projections (2026-09-21)

Both lowerers extend the existing direct-getter specialization from one field
to a checked field path, such as `node_at(nodes id).position.start`. They keep
the original arguments, default evaluation, guards, prefix effects and cleanup.
The complete source owner stays alive while the path is read; only the leaf
needs an independent lifetime. Integers/bools pass directly, while selected
strings and runtime-length arrays are retained before temporary-owner cleanup.
Constructors and unsupported control-flow results keep the ordinary route.
Variant identity includes the full path, so different nested fields with the
same final name cannot share the wrong implementation.

Validation: six existing hosted projection tests and four new hosted tests
pass. The nested scalar kernel allocates/copies/retains zero arena bytes; its
hosted positive control with specialization disabled allocates over 100 KB.
The second-generation native driver agrees on this kernel, effects/defaults,
temporary string/array lifetimes, and the failing runtime guard on x86-64/C.
Its rebuilt native CLI reports **4,987 sites over 47,324 source lines
(105.380/KLOC)** in the isolated checkout, within the unchanged gates.
Artifacts use the `../dewy-build-artifacts/phase1-nested-projections-` prefix.
Integration follow-up: the three-generation direct x86-64 bootstrap also
completed, with byte-identical final Dewy and µDewy generations and passing
runtime checks on x86-64/C. Generation 2/3 took 67/77 seconds during concurrent
development; these are integration timings, not isolated latency measurements.
The 211-case corpus certification above belongs to the preceding placement
checkpoint. Phase 1 remains in progress.


## Whole-owner frame loans (2026-09-21)

The shared placement proof now distinguishes call-only addresses from whole
owners whose storage remains fixed. Known nonescaping helpers may read whole
fixed scalar arrays or update fields of scalar records in reusable frame
storage. Every resolved target and argument position must establish the
relevant guarantee; owner replacement, array mutation/resizing, raw exposure,
captures, unknown callbacks and by-value whole-owner uses remain conservative.
This extends the existing place protocol without a new source annotation.

Hosted raw arrays receive a borrowed call descriptor and slot. Native frame
arrays also keep the addressable handle slot in the frame, with no arena cleanup
for either block. The storage budget includes that slot. A 10,000-iteration
kernel observes zero arena allocation through forwarding, recursion and keyword
calls, including whole-array reads and whole-record field mutation.

Validation: 62 focused hosted allocation/access checks pass; the frame groups
also passed (29 initial checks and 20 corrected checks after the hosted call
adapter). A second-generation native driver agrees with hosted checking and
execution on 15 kernels and 18 rejections across x86-64/C. The compiler inventory
is 4,988 sites over 47,364 lines (105.312/KLOC), within the unchanged gates.
Artifacts use `../dewy-build-artifacts/phase1-whole-frame-` prefixes. This slice
has bounded second-generation validation; the preceding nested-getter checkpoint
is the most recent full native fixed point.


## Conditional callable access summaries (2026-09-21)

Access/effect analysis now retains all known targets of a conditional callable
value, including stable aliases and checked value wrappers. Dispatch selection
is applied inside each possible overload value rather than selecting one
runtime branch. Every alternative must justify a loan; unresolved arms,
reassigned handles and alias cycles remain unknown. Public effects also check
the selector expression, while constructing an overload set only evaluates its
operands. Native borrowing reuses this target resolution and the already
collected access graph.

Shared choices use a bounded graph walk rather than enumerating paths; ordinary
direct calls keep their fast path and unresolved ingress/intrinsics create no
search state. A shared graph with 65,536 paths and an unresolved cycle have
explicit regressions. Choosing either of two known read-only array helpers now
retains frame placement and zero arena allocation across repeated calls.

Validation: 94 adjacent hosted effect/placement tests passed initially; 38
hosted callback/projection cases pass after the overload-evaluation correction.
The final focused run passes 11 tests, including native/hosted effect-summary
parity on the shared graph. A second-generation native driver passes 11 runtime
kernels and 16 rejections against hosted checking on x86-64/C. The inventory is
4,991 sites over 47,432 lines (105.224/KLOC), within the unchanged gates.
Artifacts use `../dewy-build-artifacts/phase1-conditional-place-` prefixes.
These are focused checks, not a new complete pytest run or fixed point.


## Default-argument assumption audit coverage (2026-09-21)

The audit collector now enters a function through all of its executable HIR
children, including parameter defaults, while keeping nested function scopes
separate. Previously a default's assumption could disappear from the sidecar
when the collector skipped straight to the body. Unused functions and explicitly
overridden defaults still retain their source assumptions. This is inventory
coverage; consumer lists remain the documented conservative function-scope
candidates, not exact proof dependencies.

Validation: all 18 hosted assumption checks pass, plus the two parameterized
resident/persistent prelude-cache cases. The fresh native CLI retains the named
default audit for unused, used and overridden defaults on x86-64/C; all six
executables return 42. It rejects a proven-false unused default and replaces a
stale sidecar after removal. Repeated native invocations also retain an unused
imported default with its original source path. The native command regression
now covers these cases alongside its existing invocation checks. Artifacts use
the `../dewy-build-artifacts/phase1-default-audit-` prefix.


Integration checkpoint: `3e30f72a` completed the three-generation direct x86-64
bootstrap with byte-identical final Dewy and µDewy binaries and passing runtime
checks. Generation 2/3 took 66/76 seconds during concurrent development; these
are integration timings, not isolated latency measurements. The certified pair
reports 4,991 copy sites over 47,440 lines (105.207/KLOC). Artifacts:
`../dewy-build-artifacts/phase1-loans-audit-3e30f72a` and
`phase1-loans-audit-copies.json`. Native cache invalidation after removing the
imported default also replaces its audit with an empty report.

## Stable local values at ordinary call boundaries (2026-09-21)

The shared storage proof now lends fresh local array/record owners to known
read-only by-value callees. Local owners must remain unwritten and unexposed
throughout the containing function, including defaults; call-graph checks still
exclude nonlocal/raw access and unresolved callbacks. Incoming parameter loans
retain their existing route proofs. Fixed outer array lengths may erase at the
boundary when the element representation stays identical. Lifecycle values and
alias initializers retain their independent ownership requirements.

Frame placement consumes the same per-call evidence, including keyword calls,
so small scalar owners no longer need an explicit `@` to avoid allocation.
Occurrence counting still rejects a separate escaping use of the same HIR node.
The shared 4 KiB budget is unchanged. The direct-write query was extracted from
predicate effects and reused over the existing unique function inventory rather
than adding another recursive traversal.

Validation: 34 initial hosted storage checks, 44 adjacent effect/borrow checks,
and the final 11 local-value checks pass. Native/hosted predicate dependency
parity passes. A second-generation native driver passes ten runtime kernels and
14 rejections against hosted checking on x86-64/C, including snapshots across
later argument mutation, captured-write rejection, keyword calls and the storage
budget. The 10,000-iteration kernel observes no arena allocation. The measured
compiler inventory is 4,992 sites over 47,474 lines (105.152/KLOC), within the
unchanged gates; subsequent edits only clarify comments/tests. Artifacts use
`../dewy-build-artifacts/phase1-frame-values-`. These are bounded checks, not a
new full-suite or fixed-point certification.

## Dictionary array views and hosted parity (2026-09-22)

Proven dictionary array entries now lend their stored descriptors through the
existing local-view lifetime proof. Read-only inferred bindings use the same
route; explicit demands reject conflicting writes and temporary fallbacks.
Returning a view or explicitly copying it still creates an independent value.
Hosted checking now follows dictionary storage to its named owner, matching
native checking for both record and array entry views.

The compiler's storage analysis uses checked views for retained function bodies,
local-owner maps, reverse call edges and parameter summaries. Function body
inventories move into their table after the final local read. The native
inventory falls from 4,992 to 4,986 sites over 47,487 lines (104.997/KLOC), with
unchanged budgets. Ten hosted view cases and 61 adjacent lifetime checks pass;
six runtime kernels and five rejections agree across hosted/native checking and
x86-64/C execution. The eager-default case explicitly checks receiver mutation.

The full hosted compiler build also exposed two parity gaps. Optional numeric
calls and conditional `none` arms now retain common payload bounds without
proving presence or preserving facts across assignment. Four execution cases
and three rejections agree on both compiler/backend routes; 36 adjacent bounds
checks pass. Read-only defaulted record parameters now borrow supplied values
in hosted lowering. Cleanup uses the existing ABI presence bit, so only omitted
defaults are owned locally. Mutable/escaping/resource parameters retain their
existing ownership requirements. Ten selected parameter/default tests pass,
and two repeated lifetime kernels agree on both compilers and backends.

Checkpoint `eea60209` closes another three-generation direct bootstrap: the final
Dewy and µDewy generations are byte-identical and runtime checks pass. Generation
2/3 took 69/82 seconds with concurrent development, not isolated latency samples.
The subsequent hosted-only default fix emits and links the complete compiler
(54,290,861 bytes of µDewy); its executable reports the expected version and compiles the frame-value
fixture, which exits with the expected 42. Full corpus parity passed all
211 explicit cases against the certified pair and hosted checkpoint `1e3eefa6`. Artifacts use the
`../dewy-build-artifacts/phase1-dictionary-views-`, `phase1-dictionary-array-views-`,
`phase1-optional-conditional-bounds-` and `phase1-readonly-defaults-` prefixes.
These checkpoints do not complete Phase 1 or certify a new full pytest run.


## Stable string comparison roots (2026-09-22)

Native whole-string and slice/index comparisons borrow roots whose existing
storage proof establishes stability. Other roots retain an owning snapshot
through evaluation of the right operand. Nested spans retain the same owner,
selectors execute once in source order, and only owned roots are released.
The hosted comparison path now snapshots a left value when the right operand
may replace its source, including transitive calls, module initializers,
defaults and early returns. String-valued flow temporaries use their runtime
handle representation even when the semantic type is a string literal.

The native compiler inventory drops by 596 sites to **4,390 over 47,488 lines
(92.444/KLOC)**. CI budgets ratchet to **4,500 sites and 100/KLOC**. This measures
static copy sites, not elapsed time or runtime copied bytes. The Unicode
comparison kernel runs 1,000 iterations without arena allocation under
`$explicit_copies`. Eight hosted snapshot cases pass; paired x86-64/C runs
also cover the allocation kernel, eleven existing descriptor/lifetime kernels,
four text cases and three rejections.

Checkpoint `a708b511` closes the three-generation direct x86-64 bootstrap with
byte-identical final Dewy and µDewy generations and passing runtime checks.
The certified pair reports the same 4,390 sites over 47,501 source lines
(92.419/KLOC) in the integrated checkout and passes the tighter gates.
Generation 2/3 took 64/82 seconds during concurrent work, not isolated latency
measurements. Artifacts use `../dewy-build-artifacts/phase1-string-comparison-views-`
and `phase1-string-views-` prefixes. These are focused checks and a fixed point,
not a new complete pytest or corpus certification of this checkpoint.


## Scoped inferred call rows (2026-09-22)

Public effect analysis now retains a call's subject mapping as a solver
projection. It resolves the callee row before translating parameter slots and
field routes, including reassigned callbacks, keyword calls and nested wrappers.
Private arguments erase only their own storage effects; unknown behavior stays
unknown. Body equations and selected callable-boundary constraints use one
solver rather than a separate body-call fixed point followed by row inference.
These equations are transient analysis data, not new type syntax or cache data.

Negative guarantees translate without broadening their routes. Written
exclusions nominate candidates; inverse call mappings propagate those demands
to source scopes by removing prefixes and renaming slots. The finite vocabulary
therefore remains route suffixes even with recursion. Every candidate still
needs evidence from all defining rules. Deep positive paths retain the existing
widening, while deep exclusions drop. General user-written polymorphic `E` rows
with callback-relative place subjects remain conservative: this checkpoint
retains environments for inferred call equations, not those generic binders.
Function-handle assignment also no longer implies allocation by itself;
projected storage writes still retain their separate storage obligation.

The solver kernel exposed a hosted iterator bug: optional record elements in a
composite iterator were wrapped as present records instead of preserving their
stored tags. Optional scalar/string and general union cells now use the same
borrowed tag/payload transfer. Dictionary entries, nested record storage and
padded array iteration preserve absence and execute correctly.

Validation: 125 hosted effect checks passed before the negative-demand
extension; 95 adjacent proof/allocation/cache/iterator checks pass after the
final correction. The solver kernel, six scoped-call programs and three
optional-iterator programs pass hosted/native checking and x86-64/C execution;
five wrong-scope/forbidden-effect cases are rejected by both compilers. The
native inventory is **4,408 sites over 47,545 lines (92.712/KLOC)** in the isolated
checkout, within the tighter 4,500/100 gates. Artifacts use
`../dewy-build-artifacts/phase1-scoped-inferred-` prefixes. The latest certified
full fixed point remains the preceding string-view checkpoint; this slice has
second-generation execution checks. Phase 1 remains in progress.


Integration checkpoint: `e145a7f2` completed the three-generation direct x86-64
bootstrap with byte-identical final Dewy and µDewy binaries and passing runtime
checks. Generation 2/3 took 66/81 seconds during concurrent work, not isolated
latency samples. The certified pair is
`../dewy-build-artifacts/phase1-scoped-effects-e145a7f2`; the preceding 211-case
corpus result belongs to the dictionary-view checkpoint.


## Ownership at loop exits (2026-09-22)

Logical ownership liveness now follows the selected loop continuation for
`break` and `continue`, including labeled exits. Repeating paths retain outer
owners; a break path may transfer one at its last use when nothing after the
selected loop needs it. Nested loops retain the enclosing continuation, so
breaking only the inner loop cannot consume an owner needed on the next outer
iteration. Existing alias/capture checks and conditional cleanup flags remain
authoritative. Custom move hooks and owning parameters use the same path proof.
No new move syntax or resource representation is introduced.

Validation: 36 focused hosted loop/branch checks pass. A second-generation
native driver passes 19 runtime kernels and 16 rejection cases against hosted
checking on x86-64/C, including labeled exits, live aliases, continued paths,
custom moves, drop counts and repeated-call retained-memory checks. The native
inventory is **4,411 sites over 47,551 lines (92.764/KLOC)** in the isolated
checkout, within the 4,500/100 gates. The reference now describes scoped effect
inference and the supported conditional resource transfers. Artifacts use
`../dewy-build-artifacts/phase1-loop-exit-` prefixes. The latest complete native
fixed point remains `e145a7f2`; this is a bounded second-generation ownership
checkpoint, not completion of Phase 1.


Broader hosted validation after `21fe9314`: `pytest -q -k 'not bootstrap and
not native'` completed with 3,400 passed, 14 skipped and one failure in 446 s.
The failure expected a stable known read-only function alias to require an
array copy, predating the local-value loan proof. That expectation now accepts
the proved loan; a new incoming-unknown-callback case still requires a copy.
All 58 static-array tests pass after this test correction. This is the broader
hosted selection plus a focused repair, not a complete all-route pytest run.
The log is `../dewy-build-artifacts/phase1-effects-exits-hosted-suite.log`.


## Mutable dictionary entry places (2026-09-22)

Both compilers now accept local mutable places selecting proven dictionary
entries. The shared lifetime rule retains the stored owner through the last
use of all dependent aliases; other dictionary mutations in that interval
remain conservatively conflicting. Keys and enclosing array selectors are
captured once. The rewritten route probes the saved key instead of keeping a
physical position that compaction can invalidate. Missing entries, const
ancestors, captures and changed owners remain errors.

Entry fact identities distinguish dictionary keys from array indices and
retain const-selector reentry dependencies. Alias-dependent contracts rebind
to those same identities. Payload writes invalidate value facts while keeping
ancestor dictionary membership, without retaining cached entry positions.
Native mutable routes now detach shared dictionary/value-array storage before
selecting payload storage, and record/array payload detachment writes the new
handle back into the entry slot. Optional record payloads retain their stored
union layout. Resource replacement uses ordinary drop-before-store cleanup.

Validation: 106 adjacent hosted checks passed, followed by 31 focused checks
after correcting the optional-value fixture and adding a repeated-call kernel.
Two additional strict-copy/dependent-contract cases passed paired execution.
Together the fresh second-generation native driver agrees with hosted checking
on 21 runtime kernels and 12 rejection cases, with execution on x86-64 and C.
The repeated-call kernel preserves earlier snapshots and retains no arena
bytes over 100 calls, including a dictionary with tombstones. The native
snapshot tests initially caught shared record/array mutation and pass after
routing detachment back through the entry slot. Logs/artifacts use
`../dewy-build-artifacts/phase1-entry-` prefixes. This is a bounded checkpoint;
the latest full fixed point is still `e145a7f2`.

Additional probes identified existing gaps outside this slice: ordinary
membership is forgotten at loop entry; unnamed `totaldict` receivers need
better totality propagation; hosted array layout does not yet erase a nested
`totaldict` refinement. These probes are not counted as passing coverage.
Phase 1 remains in progress.


Integration checkpoint: `a240f952` completed the three-generation direct x86-64
bootstrap with byte-identical final Dewy and µDewy binaries and passing native
runtime checks. Generation 2/3 took 66/74 seconds during concurrent work;
these are not isolated latency measurements. The pair is
`../dewy-build-artifacts/phase1-entry-places-a240f952`. Its inventory is
**4,414 sites over 47,648 lines (92.638/KLOC)**, within the 4,500/100 gates.
The full corpus checkpoint remains the earlier 211-case dictionary-view run.


## Public container storage effects (2026-09-22)

Public inference now gives built-in array growth/removal/reservation/joining,
dictionary/set operations and array iteration bounded read/mutation/allocation
rows instead of making the whole operation unknown. Storage permission remains
conservative: even lookup may construct/compact a hash index, and mutation can
detach shared backing storage. These are permissions, not claims that every
execution allocates. Selector, argument and eager-default effects propagate;
unknown callees still cannot satisfy a closed row. Lifecycle hook calls remain
subject to the ordinary validation after ownership rewriting.

A dictionary entry selection uses its containing dictionary as its public
subject, not an internal values-array path. Address formation itself reads the
keys, so a write-only callee cannot silently justify `no reads<table>`. Array
addresses retain their existing selector-only rule. Sort callbacks remain
unknown until their implicit call equations are represented.

Validation: 20 initial hosted container checks and 140 adjacent
allocation/effect/lifecycle checks pass. A fresh second-generation native driver
agrees with hosted execution on 16 container/scoped-effect kernels and 16
rejections across x86-64/C, including eager defaults, effectful selectors,
transitive wrappers, missing permissions and resource drop hooks. This includes
the added dictionary-address read exclusion regression. Artifacts use
`../dewy-build-artifacts/phase1-container-effects-` prefixes. The preceding
dictionary-place commit is the latest complete native fixed point; Phase 1
remains in progress.

## Sort callback effects and option evaluation (2026-09-22)

Sort keys now contribute their invoked bodies or callback contracts to the
public effect equations. Function-handle selection contributes its own effects;
known conditional/reassigned targets join, unconstrained callbacks stay unknown,
and generic row arguments retain their guarantees. Sort still needs storage
permission. Global-write summaries also follow the implicit key call through
wrappers, preserving snapshots across callback writes. String-to-string
widening retains the operand's effects without inventing unknown behavior.

Hosted lowering now evaluates sort options once in source order, including on
empty arrays, and saves indirect key-call results before numeric normalization.
The native lowerer already used these evaluation rules. No µDewy evaluation
semantics changed.

Validation: 32 focused hosted tests passed. A fresh native driver passed 26
runtime kernels and 22 rejection cases against hosted checking, with x86-64/C
execution, including the adjacent container/scoped-effect groups. Artifacts:
`../dewy-build-artifacts/phase1-sort-effects-*`. The preceding broad hosted run
at `82d73625` passed 3,456 tests with 14 skipped in 522.18 seconds using
`-k 'not bootstrap and not native'`; that is not a complete all-route pytest run.
The latest complete native fixed point remains `a240f952`. Phase 1 continues.

## Total dictionaries as value guarantees (2026-09-22)

`totaldict` now retains its named guarantee through factory results, optional
narrowing, record-field reads and array storage. Unnamed receivers can use the
same totality proof as bindings. Contextual storage wrappers retain already
proved totality rather than losing it at a second argument/element check.
Literal key evidence survives conversion to the storage key type. Hosted array
layout now erases element refinements through the shared representation query.

The same bounds remain enforced at construction, replacement and removal:
a partial result cannot stand in for a total dictionary, and clear/pop cannot
remove a required key. Proved value refinements preserve their operand effects;
accessing a computed owned container still accounts for producing that value.

Validation: 76 hosted object/entry-place checks passed before the final effect
classification; 107 hosted total-dictionary/public/container-effect checks
passed afterward. A fresh native driver passes seven runtime kernels and nine
rejections against hosted checking on x86-64/C. A repeated temporary lookup
calls its factory once per iteration and retains no arena bytes over 100 calls.
Artifacts use `../dewy-build-artifacts/phase1-totaldict-` prefixes. Full integration
checks are running separately; these focused checks do not complete Phase 1.

## Sort storage lifetimes (2026-09-22)

Both checkers now reject sort keys and option expressions that can invalidate
selected receiver storage. The shared call graph follows wrappers and known
callback targets. Private owning values remain independent of unrelated
callbacks; captured/exposed owners and borrowed receivers require a stable
call graph or a contract proving no mutation. Borrowed receivers conservatively
include externally reachable owners because their caller may supply an alias.
This does not add closure mutation support: writes to enclosing function locals
remain a separate unsupported case.

Validation: the fresh native driver agrees with hosted checking on 15 runtime
kernels and 13 rejections (including the preceding sort effect group), executing
on both x86-64 and C. Cases include by-value snapshots, mutable record key
arguments, captured receivers, transitive writes, effect-qualified keys and
option evaluation. Artifacts use `phase1-sort-lifetimes-*` under
`../dewy-build-artifacts`. Phase 1 remains in progress.


Integration checkpoint: `f729d465` completed the three-generation direct x86-64
bootstrap with byte-identical final Dewy and µDewy binaries and passing x86-64/C
runtime checks. Generation 1/2/3 took 162/124/78 seconds under concurrent load;
these are not isolated latency measurements. The pair is
`../dewy-build-artifacts/phase1-totaldict-f729d465`. Copy inventory: **4,418 sites
over 47,770 lines (92.485/KLOC)**, within the 4,500/100 gates. The broad hosted
selection (`-k 'not bootstrap and not native'`) passed **3,488 tests with 14
skipped** in 569.44 seconds. These integration results precede the sort storage
lifetime change; its fresh paired checks are recorded separately above.


## Owning field returns (2026-09-22)

Returning a resource field from a local owning record or by-value parameter now
transfers that field and drops the remaining fields in reverse order. Nested
synthesized wrappers, optional fields, arrays of resources, conditional exits
and custom moves on the selected field share the rule. A custom move still
cleans up the consumed component's remaining fields and must establish the
return facts. Wrappers with their own lifecycle hooks conservatively retain
the complete-receiver requirement; borrowed parameters/views cannot donate
ownership. Native last-use rewriting no longer promotes an explicit resource
view to an owning transfer, fixing a paired acceptance mismatch.

Validation: 278 adjacent hosted lifecycle tests passed before the final explicit
view guard; the final focused hosted selection passed 13 tests. A fresh native
driver agrees on eight runtime kernels and five rejections, with x86-64/C
execution. The array-field kernel checks 100 calls with no retained arena bytes.
Artifacts: `../dewy-build-artifacts/phase1-field-return-*`. General partial
transfers and array-element returns remain pending; Phase 1 is not complete.


## Returning owned array components (2026-09-22)

An exiting array owner can now transfer a selected element, including mixed
field/index paths, nested arrays, optional results and custom moves. Selectors
are saved once before the result is evaluated; conflicting receiver writes
remain errors. Reverse cleanup skips the transferred component and drops its
siblings. Nested array traversal uses a checked borrowed helper so each loop
has a stable array identity. This extends the existing exit-transfer rule;
there is no new source syntax or partially initialized value available to user
code. Non-exiting partial transfers still require further lifetime work.

These tests also found and fixed a shared-HIR constant-index bug. Both bounds
analyzers now retain a constant only when all checked occurrences agree;
disagreement with another constant or a dynamic occurrence removes it. Native
discharge clears stale annotations on revalidation. Hosted graph-level tests
cover arrays and strings; the paired nested-record cleanup test would otherwise
drop the wrong indexed record.

Validation: 23 hosted field/element tests passed before the final reduction in
helper generation; the final ten element tests passed afterward. There are 34
passing adjacent bounds/index/generated-contract checks, plus the two added
string graph checks. A fresh native driver passes 15 execution kernels and
eight rejection cases against hosted checking on x86-64 and C. Dynamic selection
is evaluated once; the repeated-call kernel retains no arena bytes over 100
calls. Artifacts use `../dewy-build-artifacts/phase1-element-return-*` and
`phase1-index-adjacent.log`. Phase 1 remains in progress.


Integration checkpoint: `7f040b71` completed the three-generation direct x86-64
bootstrap with byte-identical final Dewy and µDewy binaries and passing native
runtime checks, including x86-64/C execution. Generation 1/2/3 took 154/141/104
seconds under concurrent test load; these are not isolated latency results.
The pair is `../dewy-build-artifacts/phase1-component-returns-7f040b71`.
Copy inventory is **4,452 sites over 48,103 lines (92.551/KLOC)**, within the
4,500/100 gates. The broad hosted selection (`-k 'not bootstrap and not native'`)
passed **3,527 tests with 14 skipped** in 590.13 seconds. This is not a complete
all-route pytest run; fresh paired checks for this batch are recorded above.

## Nested scalar record placement (2026-09-22)

The shared nonescaping frame proof now includes records containing nested scalar
records, under the existing 4 KiB per-function budget. Repeated field shapes
count separately; recursive, dynamic-storage and lifecycle-managed shapes do
not qualify. Native lowering initializes compatible nested record literals
directly in their parent's frame storage, preserving field order and earlier
field bindings used by defaults. Nominal adaptation retains its existing
storage obligations. Public allocation inference uses the same literal-tree
proof, including ordinary read-only forwarding and known nonescaping places.

Validation: 38 hosted adjacent placement/loan tests passed, followed by ten
final nested-record checks. A fresh driver agrees with hosted checking on 14
runtime kernels and 14 rejections on x86-64/C. The kernels verify zero arena
allocation, including 100,000 loop iterations, nested nominal records, scalar
field mutation, defaults and read-only/by-place calls. Copies that need an
independent value, escapes, dynamic fields and oversized shapes remain
conservative. Artifacts: `../dewy-build-artifacts/phase1-nested-frame-*`.
Phase 1 continues.

## Explicit fixed-record copies in frame storage (2026-09-22)

The same placement proof now supplies independent frame storage for explicit
copies of scalar records, including nested records and copies into inline
fields. Fresh literal/copy chains can initialize that destination directly;
a copy of an existing value writes its scalar fields into independent storage.
Source evaluation and nested field defaults keep their original order. The
source owner may itself remain in frame storage because `.copy()` does not
expose its address. Escaping results and dynamic/resource storage retain their
allocation obligations; COW is not used to justify the exclusion.

Validation: seven focused hosted tests pass. A fresh native driver agrees on
11 runtime kernels and five rejections (including nested-record placement),
with x86-64/C execution. Kernels check value independence, by-value parameters,
fresh-copy chains, inline-field copies and zero arena allocation over 100,000
iterations. Artifacts use `../dewy-build-artifacts/phase1-frame-copy-*`.


## Explicit fixed-array copies in frame storage (2026-09-22)

Fixed scalar arrays now use the shared 4 KiB frame budget for explicit copies
as well as literals. Copies of existing arrays write independent data; fresh
literal/copy chains initialize the destination directly. Native descriptors
mark frame ownership so writes need no COW detachment and cleanup cannot free
the frame. Dynamic, resizing and escaping arrays keep allocation obligations.

The paired tests exposed proof witnesses hiding an explicitly typed initializer
from native placement. Both analyses now look through representation-preserving
obligations and their discharged one-value blocks. Ordinary proof validation
still rejects a false length; placement does not assert it.

Validation: 25 adjacent hosted tests passed before adding two refinement cases.
The final fresh native driver agrees with hosted checking on 17 runtime kernels
and nine rejection cases on both x86-64 and C. This includes the added refinement
cases, independent narrow-word/boolean copies, fresh chains and zero arena
allocation over 100,000 iterations. Artifacts: `phase1-frame-array-copy-*`.


## Frame-copy integration checkpoint (2026-09-22)

Source `113146f1` closes the three-generation direct x86-64 bootstrap. Both
compiler binaries in generations two and three are byte-identical, and the
pair's x86-64/C execution checks pass. Artifacts are in
`../dewy-build-artifacts/phase1-frame-copies-113146f1`. Generations took 163,
191 and 131 seconds under concurrent test/build load; these are validation
runs, not isolated performance measurements.

The broad `tests/python_misc -k 'not bootstrap and not native'` selection passed
3,554 tests with 14 skips in 771 seconds. This is not the all-route pytest suite;
a few selected import tests also exercise native drivers. The new pair reports
4,457 bootstrap copy sites across 48,220 source lines (92.431/KLOC), within
unchanged 4,500-site and 100/KLOC gates. Logs and JSON use the
`phase1-frame-copies-*` artifact prefix. Phase 1 remains in progress.

## Last-use component inputs (2026-09-22)

Owning bindings, calls, record construction and array construction now transfer
a field or element when its containing local/by-value owner has no later use.
The proof is shared with whole-owner input transfers: it excludes captures,
borrowed owners, surviving aliases and conditional/repeated parent-scope uses.
Custom wrapper hooks still require complete receivers. Selectors are saved
once, and receiver-changing selector effects remain rejected.

The wrapper keeps its lexical cleanup. Cleanup skips the transferred component,
or cleans only its remaining fields after a custom move, and drops siblings in
reverse order. The selected owner cleans up independently, including after
returns and loop exits. This does not yet allow transferring one component
while subsequent code continues to use siblings of the same owner.

Sixteen focused hosted cases passed, including dynamic selections over 100
calls without retained arena growth. The adjacent lifecycle selection passed
304 tests; a fresh native driver agrees with hosted checking on 26 runtime
kernels and 13 rejections on x86-64/C, including field/element returns.
Artifacts use `phase1-component-moves-*`. This feature is newer than the
`113146f1` integration certificate.


## Re-established ownership across loop backedges (2026-09-22)

Resource liveness now solves a finite backward fixed point at loop conditions.
Whole-value assignment kills the previous value's future liveness; `continue`
(including labeled exits) contributes to the selected loop's backedge, and
`break` retains the continuation after that loop. A consuming input may move
when every advancing path supplies a replacement before the next use. This
also handles owning inputs in loop conditions. Captures, overlapping arguments
and live aliases retain their existing exclusions.

Replacement evaluates the new value first, conditionally cleans up the previous
owner, stores the replacement, and re-enables its cleanup flag. A move does not
leave that binding permanently exempt from cleanup. Custom move hooks and
nested storage use the same protocol.

Validation: 52 adjacent hosted checks passed. Fresh native/hosted comparisons
passed 20 runtime kernels on x86-64/C and 16 rejection cases across renewal,
iteration-local ownership and loop exits. The nested-array move kernel runs
100 renewals with no retained arena growth. One initially selected explicit-view
negative hit a pre-existing unsupported-lifetime diagnostic rather than the
intended move rejection; the final case uses an inferred alias and reaches
that rejection on both routes. Runtime cases were not rerun unnecessarily;
rejection checks and the two final storage kernels ran separately.
Artifacts use `phase1-renewed-owners-*`. Broader partial ownership and the
remaining Phase 1 proof/effect work are still in progress.


## Disjoint record component ownership (2026-09-22)

Same-block component liveness now compares member paths. A move of `pair.first`
no longer conflicts with a later read, write or transfer of `pair.second`.
Whole-owner uses and ancestor/descendant routes overlap; captures and surviving
whole-owner aliases still block the proof. Indexed transfers retain the earlier
whole-root last-use rule until index disjointness joins this analysis.

Cleanup retains all transferred paths, not just one. It recursively skips each
moved component, cleans custom-move remnants, and releases untouched siblings
in reverse order. Returned components combine with prior transfers. Union
alternatives preserve this metadata, and recursive cleanup follows a finite
selected path before using its ordinary per-shape helper; previously those two
routes could forget a selection and repeat its drop.

Validation: 71 hosted adjacent cases passed. Fresh hosted/native comparisons
passed 28 runtime kernels on x86-64/C and 15 rejections, including recursive
and optional owners, multiple transfers, sibling replacement, custom move
remnants, and 100 array-field transfers without retained arena growth.
Artifacts use `phase1-partial-records-*`. Field reinitialization, conditional
partial ownership and broader indexed disjointness remain conservative.


## Partial-record integration checkpoint (2026-09-22)

At `e8d2a2da`, the direct x86-64 three-generation bootstrap completed with
byte-identical second/third generations of both compilers and passing x86-64/C
execution checks. Generation times were 165/152/130 seconds under concurrent
load, not isolated performance measurements. The broad
`tests/python_misc -k "not bootstrap and not native"` selection passed 3,603
tests with 14 skips; this selection is not the complete all-route suite.

The fresh native copy inventory contains 4,479 sites over 48,324 source lines
(92.687/KLOC), within the unchanged 4,500-site and 100/KLOC gates. Artifacts
are `phase1-partial-records-e8d2a2da/`, `phase1-partial-records-bootstrap.log`,
`phase1-partial-records-broad.log`, and `phase1-partial-records-inventory.json`.
Full corpus certification remains a separate gate.


## Effect-parameterized type aliases (2026-09-22)

Generic type aliases now accept the existing separately kind-checked `E:Effect`
parameters in both compilers. Applications resolve argument kinds before
substitution: `Action<no_effects>` supplies a row and `Action<E>` forwards one.
The row table is keyed by lexical binder identity, separate from value-type
arguments. Positive bounds, open negative guarantees and nested callable
binders retain ordinary substitution behavior. Mixed type/row aliases,
composition and imports use the same mechanism. Native checking now resolves
applied generic aliases through module namespaces as well.

Validation: 18 final focused hosted checks pass; 41 adjacent generic/row checks
passed before correcting one fixture that exercised unsupported non-literal
callable field storage. The final fixture uses an ordinary function literal.
A fresh native driver agrees on eight runtime kernels and ten rejections,
with x86-64/C execution. Cold/restored prelude snapshots retain alias row kinds,
emit byte-identical output, execute correctly and reject a value type supplied
as a row. Artifacts use `phase1-effect-aliases-*`. Callback-relative place rows
and other remaining Phase 1 work are still in progress.


## Reinitializing transferred record fields (2026-09-22)

A direct same-block assignment to a field, its containing record, or the whole
owner now starts a new lifetime after a component transfer. The liveness proof
checks every RHS read before that renewal; the target occurrence alone is not
a read of the old value. Conditional replacements, live aliases and borrowed
owners remain conservative.

Cleanup drops the still-owned old descendants and custom-move remnants, then
forgets only the replaced route's extraction metadata. The new value receives
normal cleanup. Returning before replacement retains the earlier partial
cleanup plan; returning the complete record after replacement transfers all
its renewed fields.

Validation: 62 adjacent hosted cases passed before adding two final exit/multi-
field fixtures; the final focused selection passed 15. A freshly built native
driver and the hosted compiler agree on 20 runtime kernels and 12 rejections,
with x86-64/C execution. Repeated array-field replacement retained no arena
allocation across 100 calls. Artifacts use `phase1-field-renewal-*`.


## Full corpus checkpoint (2026-09-22)

All 211 default corpus cases passed acceptance/rejection and expected runtime
comparisons using native pair `phase1-partial-records-e8d2a2da` and frozen hosted
source `28dbe7db`, through direct x86-64 output with shared checked-prelude
caches. The report is `phase1-partial-records-corpus.json` and its log is
`phase1-partial-records-corpus.log`. This certifies the corpus at those inputs;
field renewal and subsequent source changes retain their separate focused
validation until the next integration checkpoint.


## Read-only tagged-union storage and defaults (2026-09-22)

The shared forwarding proof now includes ordinary tagged unions, retaining
lifecycle, mutation, raw-exposure and callback exclusions. Closed literal
materialization cannot expose existing caller storage; casts of names/calls
remain conservative. The hosted optional parameter ABI now borrows read-only
cells like general unions. Supplied default arguments borrow, while omitted
defaults initialize and clean up their own payloads.

The native effect inventory recognizes absent-arm boxing as allocation-free,
matching static empty cells. Native general unions now share that representation
with optionals. Mutable container slots privatize empty tag cells at the owning
store: a regression caught one array element changing another absent element
through the shared cell. Hosted general-union places now use a consistent direct
cell ABI for bindings, fields and elements, fixing a projected-field crash.

Validation across the final focused runs covers 18 paired runtime kernels
(16 new and two adjacent forwarding fixtures) and 15 rejections on hosted/native
and x86-64/C. The first 12 kernels passed before the mutable-slot/ABI fixes;
the remaining six and all rejections passed afterward. Hosted selections passed
35 adjacent borrow/default checks and 25 of 26 later focused checks; the final
fixture was changed from unsupported whole-dictionary-entry borrowing to entry
replacement and passed paired validation. Allocation counters cover recursive
forwarding, supplied defaults and 100 omitted empty defaults; owning defaults
retain no arena growth over 100 calls. Artifacts use `phase1-union-borrows-*`.

A seed inventory before the final empty-cell changes measured 4,496 copies
over 48,434 lines (92.827/KLOC), within the existing gate. It is not a fresh
compiler certificate. Stable indexed type-test facts are recorded but not yet
consumed consistently on subsequent reads; general whole-entry dictionary
places also remain a separate checker gap.

## Union-borrow integration checkpoint (2026-09-22)

Frozen source `a6f1f6bc` completed the three-generation direct x86-64 bootstrap;
Dewy and µDewy generations 2 and 3 are byte-identical. The pipeline's x86-64
and C execution checks passed. The broad `tests/python_misc` selection excluding
`bootstrap` and `native` names passed 3,656 tests with 14 skips in 677.16 seconds.
This selection is not all-route pytest or CI certification.

The fresh native pair reports 4,496 static copy sites over 48,458 bootstrap
source lines (92.781/KLOC), passing the unchanged 4,500/100 gates. The count
is static inventory, not a speed measurement. Native generations 2 and 3
took 146 and 119 seconds under concurrent regression load; these are not
isolated performance samples. Artifacts: `phase1-union-borrows-a6f1f6bc`,
`phase1-union-borrows-bootstrap.log`, `phase1-union-borrows-broad.log`, and
`phase1-union-borrows-inventory.json` in the build-artifacts directory.

## Stable indexed type alternatives (2026-09-22)

Literal and const-selected array elements and proven dictionary entries now
consume their branch type facts in both checkers. Predicate-result contracts
use the same route identities. Reads narrow; assignments and place parameters
retain the declared storage type. Hosted dictionary lowering now unpacks a
narrowed payload from its original tagged storage, matching native lowering.

Projected writes use one mutation-prefix rule: a selector may alias another
selector, while a field write preserves facts about its ancestors. Array
mutation and dictionary replacement/removal invalidate descendant facts,
including nested containers. Dictionary membership and unaffected tombstone
positions retain their existing contracts. Ordinary dynamic selectors remain
conservative; this does not add disjoint-element ownership proofs.

Validation: 73 adjacent hosted checks passed. A fresh native driver then passed
14 runtime kernels and 10 rejection cases against hosted compilation on both
x86-64 and C (the final dynamic nested-mutation pair has its own log).
Artifacts use `phase1-indexed-facts-*`. The final source inventory using the
previous native seed is exactly 4,500 sites over 48,494 lines (92.795/KLOC);
the gate is unchanged, and this is not a fresh self-bootstrap certificate.

## Union-borrow corpus parity (2026-09-22)

All 211 default corpus cases passed with native pair
`phase1-union-borrows-a6f1f6bc` and frozen hosted source `d21ac971`, using
direct x86-64 output and shared checked-prelude caches. Reports:
`phase1-union-borrows-corpus.json` and `.log`. This checkpoint predates indexed
type-fact changes, whose focused paired validation is recorded separately.

## Inferred views of local tagged projections (2026-09-22)

Hosted lowering now uses the ordinary stable-route proof for implicit local
union views, retaining dependent-view liveness when considering moves of the
container. Both lowerers allow proven dictionary entries to lend tagged
storage. Native narrowing can lend an existing union alternative's payload
without requiring the read and storage types to be identical. Conversions that
retag a record family still need independent result storage.

A fresh native driver passed 12 runtime kernels and two rejection cases against
hosted compilation on x86-64 and C. Allocation counters cover 100 repeated
reads of optional/general union elements, fields, dictionary entries, narrowed
records, string payloads and array payloads. Mutation, source consumption and
returned values retain independent ownership. Hosted selections passed 38
adjacent tests and all 14 final focused tests. Artifacts use
`phase1-inferred-union-views-*`.

The previous seed's inventory reports 4,501 sites on this source; that seed
does not implement the new borrow proof. A fresh integration inventory must
pass the existing 4,500/100 gates before this checkpoint is certified.

## Local union-view integration checkpoint (2026-09-22)

Frozen source `582fbe53` completed the three-generation direct x86-64 bootstrap.
Both Dewy and µDewy generations 2 and 3 are byte-identical; x86-64/C pipeline
execution checks passed. The fresh pair reports 4,483 copies over 48,522
bootstrap lines (92.391/KLOC), passing the unchanged 4,500/100 gates. The
previous seed could not account for the new borrow optimization; the fresh
inventory is the certificate. Static counts are not timing measurements.

The broad selection excluding `bootstrap` and `native` names passed 3,694
tests with 14 skips in 733.61 seconds. The preceding indexed-fact checkpoint
(`4fe3cb18`) passed 3,680 with 14 skips in 677.61 seconds. These selections
do not certify all-route pytest/CI. Bootstrap generations 2/3 took 69/83
seconds under concurrent work, not isolated benchmark conditions.
Artifacts: `phase1-union-views-582fbe53`, `phase1-union-views-bootstrap.log`,
`phase1-union-views-inventory.json`, `phase1-union-views-broad.log`, and
`phase1-indexed-facts-broad.log`.

## Shared local-view allocation evidence (2026-09-22)

The storage-borrow analysis now returns local-view evidence alongside its
argument proofs. Allocation contracts and both lowerers consume that evidence.
An unwritten, uncaptured field/element read from an ordinary read-only by-value
parameter can therefore satisfy `no allocates` or `no_effects`. The proof
requires identical stored/read representations and excludes lifecycle hooks,
raw/nonlocal exposure and unresolved calls. More precise scoped lowerer views
remain conservative in source allocation contracts.

Validation: 182 adjacent hosted checks and 28 focused hosted checks passed.
A fresh native driver passed nine runtime cases and five rejections against
hosted compilation on x86-64/C. A caller-side allocation counter verifies a
contracted union view creates no storage. Mutated locals, replaced sources,
escaping results and runtime-sized explicit copies still require allocation;
fixed scalar copies retain their existing frame-placement permission. Artifacts
use `phase1-local-view-effects-*`.

The shared local-view proof also covers stored strings. Hosted declaration
lowering now consumes that evidence for strings, extends the source owner's
liveness, and excludes the borrowed descriptor from owning string moves.
Three additional paired runtime kernels and one rejection passed on both
backends, including zero-allocation field/element reads and an escaping string
that survives source cleanup. All 38 hosted string/view/copy checks passed;
artifacts are `phase1-local-view-effects-strings-*`.

## Projected parent/child union representations (2026-09-22)

Four runtime regressions reproduced a hosted mismatch: a parent record handle
or a cell tagged as its parent was consumed as a cell tagged with child types.
Projected reads now share one conversion boundary across arrays, dictionary
entries, explicit fields and implicit receiver fields. Conversions preserve
receiver evaluation order and keep a separate prelude; narrowing never changes
the stored layout. Native lowering already follows this rule.

All 73 hosted projection/family/view checks passed. Eight runtime kernels
passed hosted/native and x86-64/C comparisons using the fresh local-view-effect
driver. Cases cover parent records, optional parent cells, dictionary entries,
implicit method fields and an escaping narrowed optional whose original array
is cleared. Artifacts use `phase1-projected-family-*`.


## Shared-view integration checkpoint (2026-09-22)

Frozen source `41a8eae2` passed the three-generation direct x86-64 bootstrap:
both compiler executables are byte-identical in generations two and three,
and the x86-64/C pipeline execution checks passed. The fresh native pair
reports 4,485 copy sites over 48,563 bootstrap lines (92.354/KLOC), within the
unchanged 4,500-site and 100/KLOC budgets. Concurrent generation timings of
142/179 seconds are not isolated performance measurements.

The broad `tests/python_misc` selection excluding `bootstrap` and `native`
names passed 3,720 tests with 14 skips in 861.73 seconds. This is not an
all-route pytest or CI certificate. Logs and the inventory use
`phase1-shared-views-*`; the pair is `phase1-shared-views-41a8eae2`.
Phase 1 remains in progress.

## Structural hosted fact identities (2026-09-22)

Hosted index, nonzero, order and remainder facts now use distinct immutable
structural keys. Scalar and length terms retain their unbounded signed-id
encoding. Fixed 20/21-bit packing could silently change the identity or kind
of a fact at large binding ids, including confusing a real array with the
nonzero sentinel. The native representation was already structural.

Nine direct regressions cover identity, invalidation, transfer and proof
separation through 80-bit synthetic ids. The expanded native fact-state
comparison checks joins, widening, narrowing and invalidation past the old
packing boundaries. All 56 selected proof/loop checks passed (including three
paired native kernels), as did four direct native analysis comparisons.
Artifacts use `phase1-structural-facts-*`. This removes an identity limit; it
does not claim to complete the general liquid qualifier engine.

## Disjoint binding and route allocation (2026-09-22)

Declaration ids are odd and lazily allocated projection ids are even in both
compilers. The independent sequences preserve declaration identities when
validation adds routes, without the previous overlap at 524,288 declarations.
No cache schema changed: hosted source digests and native executable identities
already invalidate old snapshots. Resident-prelude rollback now removes each
kind using its own cursor and removes all associated route metadata; it no
longer discards older routes merely because their numeric ids are large.

Eighteen initial checks passed, including cache reuse and native allocation;
an allocation fixture exposed its assumption that adjacent route ids differ
by one. Fixtures now retain allocated identities. Both repaired native binding
checks passed, followed by twelve hosted/native x86-64/C executions covering
small/large snapshot tables and repeated subtree queries. Existing 4 MB/25 MB
allocation budgets passed unchanged. Artifacts use `phase1-binding-ids-*`.


## Finite relational-chain proof search (2026-09-22)

Both proof engines now follow established order edges with a finite worklist
instead of stopping after two recursive steps. Each edge contributes its
signed difference bound; only stronger arrivals revisit a term. The edge
count bounds relaxation even for contradictory positive cycles. Missing links,
invalidated links and unreachable destinations still supply no evidence.

Forty selected hosted proof/loop checks passed. The expanded direct native
relation comparison covers long weighted chains, weak alternate paths and
cycles. A fresh driver passed two runtime kernels and three rejections on
both x86-64/C routes, including array access through an eight-term ordering
chain and rejection of a contradictory unsafe assumption. Artifacts use
`phase1-relational-closure-*`. Arithmetic difference-bound consumers still
read direct edges and are the next integration step.


## Relational-proof integration checkpoint (2026-09-22)

Frozen source `099937f3` passed the three-generation direct x86-64 bootstrap
with byte-identical Dewy and µDewy executables in the last two generations.
The x86-64/C pipeline checks passed. Generation timings of 214/197 seconds
were collected under concurrent checks, not as isolated performance results.
The fresh pair reports 4,492 copy sites over 48,605 bootstrap lines
(92.418/KLOC), inside the unchanged 4,500/100 limits.

The broad selection excluding `bootstrap` and `native` names passed 3,738 tests
with 14 skips in 966.26 seconds. The full default corpus passed 211/211 native
versus hosted comparisons on direct x86-64 with a shared prelude cache. This
certifies the structural fact identities, disjoint binding ids and predicate
chain search; it predates the arithmetic/provenance follow-ups. It does not
stand for all-route pytest or CI. Artifacts use `phase1-relational-*`, with the
native pair in `phase1-relational-099937f3`.

## Shared difference search for arithmetic (2026-09-22)

Arithmetic differences and slice lengths now query the same finite graph as
ordering predicates. The graph can return the strongest established bound,
including negative gaps, instead of looking only for a direct edge. Transfers
retain address-cap provenance and prefer an equally strong uncapped path.
Known predicate proofs still return directly; a term without outgoing order
facts does not construct a graph.

The final focused run passed 17 checks, including an independent simple-path
oracle over 40 consistent graphs. Three direct native analysis comparisons
passed across the relation, expression-interval and term-fact layers. A fresh
native driver passed three runtime cases and three rejections against hosted
compilation on x86-64/C, including a nonnegative difference established through
eight terms. Earlier adjacent hosted loop/proof checks also passed. Artifacts
use `phase1-difference-closure-*`. The general qualifier engine and exact unsafe
assumption provenance remain larger tasks.


## Preserve address-cap provenance through fact transfers (2026-09-22)

Nonzero narrowing, length changes, remainder shifts, affine fact transfers and
implied order evidence now retain their input intervals' address-cap flag.
Length widening records when an unbounded endpoint is replaced by the target
cap, while an unchanged explicit bound stays uncapped. This fixes provenance
loss without changing the numeric proof rules; it is not exact unsafe-assumption
dependency tracking.

Fifteen focused checks passed, including four direct hosted/native analysis
comparisons with capped states and length changes. A fresh native driver passed
four runtime kernels and three rejections on x86-64/C. The added runtime kernel
checks the returned provenance after length transfer, remainder shifting,
widening and implied evidence. Artifacts use `phase1-address-provenance-*`.


## Arithmetic/provenance integration checkpoint (2026-09-22)

Frozen source `d4a181b5` passed the three-generation direct x86-64 bootstrap;
Dewy and µDewy are byte-identical across the final two generations, and the
x86-64/C pipeline checks passed. Concurrent generation times of 142/121 seconds
are not isolated benchmarks. The fresh native copy inventory is 4,497 sites
over 48,626 bootstrap lines (92.481/KLOC), within the unchanged 4,500/100 gates.
The broad selection excluding `bootstrap` and `native` names passed 3,744 tests
with 14 skips in 616.29 seconds. This is not an all-route pytest/CI certificate;
the last full 211-case corpus comparison remains the preceding `099937f3`
checkpoint. Artifacts use `phase1-proof-bounds-*`.

A subsequent generic-specialization experiment for the search helper was
measured and discarded. Across 100 long-chain queries, native allocation
traffic fell from 1,167,200 to 1,138,400 bytes and hosted traffic from 1,176,032
to 1,054,400 bytes (identical on x86-64/C). However its seeded inventory rose to
4,504 sites, exceeding the count budget; no gate was raised. Specializing the
loop duplicates copy sites. The underlying opportunity is borrowing an
aggregate while temporarily boxing it for a known read-only union parameter.
The retained implementation keeps one search body. Experiment artifacts use
`phase1-proof-search-storage-*`.


## Borrowed union call conversions (2026-09-22)

Both compilers can lend a stable ordinary aggregate to a known read-only
union parameter. Exact-member widening reuses the existing tagged cell;
injection puts the existing payload handle into a 16-byte caller frame cell.
The slot is reused across loop iterations and owns no payload. This uses the
same storage proof for `no_effects`/`no allocates` checking and lowering.
Family conversions, lifecycle-bearing storage, later argument writes, raw
exposure and unresolved callbacks retain their existing obligations. Owning
results still copy; a returned value does not retain the temporary cell.

A shared representation query now distinguishes exact tagged value casts
from casts that may expose an address. Native contextual typing explicitly
inserts the former; hosted calls may instead carry the target only in their
formal signature. Hosted lowering now carries proof identities through call
normalization and handles union wrapping before array argument adapters.
Program-wide tags permit widening without renumbering alternatives.

Validation: 12 runtime cases and five rejection cases agree on fresh native
and hosted compilers with x86-64/C execution. The rejection tests require an
effect-contract diagnostic, including the corrected named callback signature.
A repeated call kernel performs 100 injections without arena allocation.
Ninety-seven focused/adjacent hosted tests passed before the final diagnostic
strengthening; the final five contract-rejection checks pass on both routes.
A full bootstrap and inventory checkpoint follows; this is not a claim that
Phase 1 or the full test matrix is complete.

## Signed remainder bounds (2026-09-22)

Fixed a proof-engine correctness bug in both compilers: fixed-width signed
remainder had been given a nonnegative interval whenever its divisor was
positive. That could accept `$assert x % 3 >=? 0` for an arbitrary signed
`x`, or use the invented sign to justify an array index. Runtime arithmetic
was already correct and is unchanged. Truncating remainder now follows the
dividend's sign and is bounded by both the dividend and divisor magnitude;
mathematical floor modulo keeps the divisor's sign. Unknown endpoints stay
unknown, and an exactly zero divisor supplies no result bound.

Validation: an exhaustive small-integer oracle checks every nonzero divisor
in all intervals with endpoints from -5 through 5, for both conventions.
Three runtime and three rejection cases agree on a fresh native driver and
hosted compiler, with x86-64/C execution. The native interval kernel matches
hosted transfers including negative and unbounded divisors; its three tests
and 29 focused/adjacent hosted proof checks pass. This fixes sign soundness;
symbolic remainder-versus-divisor relations remain the next proof step.

## Union query storage and checkpoint follow-up (2026-09-22)

The `05222239` union-loan implementation completed a three-generation direct
x86-64 bootstrap with byte-identical generations 2 and 3 and x86-64/C pipeline
execution. Generations 2/3 took 154/111 seconds while other checks ran; these
are not isolated performance measurements. Its broad Python selection
reported 3,760 passes, 14 skips and one failure building a hosted-generated
native driver. An explicit common array annotation repairs that failure;
the same imported-resource-truncate test then passes through that driver.

Its fresh inventory was 4,506 copies (92.543/KLOC), above the 4,500-site gate.
The common union representation query now compares existing members without
normalizing or privately copying the type table. Grouped optional-string
payloads retain the normalization path. Native lowering also consumes the
explicit checked cast destination rather than reconstructing keyword/positional
signatures; unlike hosted HIR, native contextual union conversion is explicit.

The follow-up passes the cross-product of the type-query fixture's source
and destination types against hosted results, including grouped strings and
refinements. A fresh driver passes all 12 runtime and five contract-rejection
cases on both compilers and x86-64/C. The preliminary source inventory is
4,499 sites (92.376/KLOC); the merged checkpoint still needs a fresh full
compiler inventory, especially after the separate remainder-bound fix.

## Remainder relations (2026-09-22)

A checked primitive remainder now contributes a relation to its live named
nonzero divisor: below a positive divisor, or above a negative divisor. Both
compilers feed this into the existing term graph used by source contracts,
including direct array-index expressions. The dividend's sign remains a
separate obligation. Divisor/array mutation invalidates the relation, user
functions named `__mod__` do not receive it, and address-cap metadata travels
with the derived bounds.

Validation: nine hosted runtime/rejection tests pass. A fresh native driver
agrees on four runtime cases and five rejection cases, with both x86-64 and C
execution. The direct native term-fact kernel comparison also passes. This
extends the finite proof vocabulary; it does not complete the general liquid
invariant engine or unsafe-assumption dependency reporting.
## Checked compound operations and interval storage (2026-09-22)

Hosted HIR now retains the selected checked arithmetic call for a compound
assignment, as native HIR already does. This closes both the missing bounds
transfer for `//=` (exposed by bootstrap byte packing) and a bypass of ordinary
nonzero-divisor checking for primitive `//=`/`%=`. Operand hints retain the
destination representation without incorrectly requiring its store facts;
shift counts retain their independent unsigned type. Runtime arithmetic and
µDewy semantics are unchanged.

The native remainder interval computes its maximum absolute divisor endpoint
without copying boxed values into three temporary selections. Its direct
interval-kernel comparison passes, and the preliminary source inventory falls
from 4,503 to 4,499 sites (92.344/KLOC). This is a static storage measurement,
not evidence of an elapsed-time improvement.

Validation: 19 focused hosted bounds/runtime tests pass; four compound
refinement/native interval kernel tests pass. A fresh native driver agrees
on six runtime and five rejection cases with x86-64/C execution. The broader
combined checkpoint, including the separate remainder relations, follows.

## Remainder integration checkpoint (2026-09-22)

Source `2cae5f76` completes a three-generation direct x86-64 bootstrap; both
compilers are byte-identical between generations 2 and 3, and the pair passes
x86-64/C pipeline execution. Generations 2/3 took 151/144 seconds during
concurrent validation, not an isolated latency measurement. Its fresh native
inventory is 4,500 sites and 92.298/KLOC, meeting both existing budgets.
Artifacts use `phase1-remainder-*`.

The broad Python selection excluding `bootstrap` and `native` names reports
3,787 passes, 14 skips and two stale HIR-shape assertions. Both expected a
retained `+=` operator; they now check the ordinary assignment and preserved
checked `__add__` call. The two complete containing test modules pass all
34 tests afterward. The former imported native-driver build failure is fixed.
This does not certify all-route pytest/CI or complete Phase 1.

## Nested container mutation and lifecycle selections (2026-09-22)

Native container methods now recognize proven dictionary entries as rooted
places. Hosted const checks follow the same route to its owning binding and
immutable fields. Both bounds analyzers include dictionary selectors in the
existing receiver-stability check, rejecting arguments that invalidate the
selected outer dictionary. Ordinary writes still preserve independent value
snapshots through the existing entry storage lowering.

Lifecycle cleanup and mutation now share captured dictionary keys, just as
array routes already share captured indices. Cleanup may compact storage, so
subsequent accesses recheck the captured key rather than retaining an old
physical position. This fixes repeated key evaluation when clearing a nested
resource dictionary; captured-root write summaries also follow entry routes.

Validation: a fresh native driver agrees with hosted on nine runtime and seven
rejection cases, with x86-64/C execution. Runtime cases include independent
snapshots, tombstones, nested entries, and once-only resource cleanup. Rejection
diagnostics were checked for receiver invalidation, missing membership, view
conflicts, const storage and effect contracts. Nineteen focused hosted tests and
82 adjacent ownership/borrow tests pass. Broader integration follows.

## Borrow-graph storage (2026-09-22)

The native borrow analysis extends adjacency sets through checked entry places
instead of copying each set out and back per edge. Candidate intersection now
filters the existing allowed set once, avoiding a temporary difference and the
three owning inputs to the set operators. This preserves the existing proof
rule and candidate order. The entry-place spelling also compiles with the
preceding native seed, without needing a language staging workaround.

The preliminary inventory on this branch is 4,503 sites before incorporating
the separately verified four-site interval simplification; the combined source
must be checked against the unchanged 4,500-site gate. The adjacency change is
in the fresh driver used for the nested-container tests. The final filter
change is source-checked; its execution is covered by the next full native
integration checkpoint. Static counts do not establish a latency improvement.

## Refined resource storage (2026-09-22)

A checked top-level refinement does not change a resource's ownership layout.
Both lifecycle passes now compare the underlying storage types when accepting
an annotated owner, retaining nominal identity and the original fact
obligations. This permits total dictionaries containing resources and refined
resource records without treating them as an unsupported non-fresh owner.
The normal freshness/move/copy rules still apply afterward.

Validation: seven hosted tests pass. A fresh native driver agrees on three
runtime and four rejection cases with x86-64/C execution. Cases cover replacing
a total dictionary entry, once-only nested cleanup, refined record cleanup,
missing total keys, false field facts, forbidden total-key removal and hook
effects. No facts or resource obligations are discharged by layout equality.
## Division interval endpoints (2026-09-22)

Both proof kernels now calculate division bounds directly from monotone
endpoints, normalizing negative divisor intervals by negating both operands.
This covers one-sided unbounded ranges and negative machine-word divisors;
truncation and floor division remain distinct. Divisor intervals crossing zero
still require separate nonzero evidence and provide no quotient interval here.
The native kernel no longer constructs numerator, divisor and candidate arrays.

Validation: seven hosted tests pass, including an exhaustive small-integer
interval oracle for both rounding rules. Three interval-kernel comparisons
pass, and a fresh native driver agrees with hosted on three runtime and two
rejection cases on x86-64/C. The seeded source inventory is 4,491 sites; a
fresh integration checkpoint remains necessary. This count is not a timing.

## Scalar locals in checked proofs (2026-09-22)

A checked proof can now name intermediate integer and boolean facts with
`const`, including trusted measures of its parameters and earlier locals.
Lexical blocks retain their own available bindings. Mutable locals, aggregate
owners, runtime calls and mutable enclosing reads remain outside this finite,
effect-free erased subset. Returned facts still mention only parameters, and
every normal exit must establish the conclusion.

Both interval evaluators also retain literal boolean values through bindings:
`const answer=true; $assert answer` now proves, while a false initializer or
subsequent false assignment does not. This is ordinary fact propagation, not
a proof-only exception.

Validation: eleven focused hosted cases pass; the existing proof-boundary
cases also pass. A fresh native driver agrees on four runtime and seven
rejection cases, executing accepted programs on x86-64 and C. Aggregate local
rejection protects erasure from hiding lifecycle effects.
## Disjoint constant-index resource transfers (2026-09-22)

The same-block last-use proof now distinguishes constant array indices as well
as record fields. Moving `xs[0]` no longer prevents later use or transfer of
`xs[1]`. Nested arrays and multiple fields within one element use the same
route proof. Dynamic indices, whole-array uses, resize/clear and borrowed
owners remain conservative; this does not infer arbitrary index disequality.

Cleanup retains every transferred path. Equal literal indices group their
field exclusions before recursive cleanup, including helper boundaries for
nested arrays. Untransferred components still drop in reverse order; custom
move hooks retain their normal remaining-field cleanup. Literal selectors need
no extra capture binding. Native route tables now extend through checked entry
places and read through views, avoiding copied lookup results.

Validation: 27 initial hosted cases (including existing partial-record cases)
pass, followed by all eleven focused cases including a custom move. A fresh
native driver agrees with hosted on six runtime and five rejection cases on
x86-64/C, both before and after route-table storage changes. The seeded source
inventory is 4,495 sites / 92.047 per KLOC, within the unchanged gate. Fresh
compiler integration remains necessary; static counts are not timings.

## Nested-entry native and full-suite checkpoint (2026-09-22)

Source `3139fe4a` completed a three-generation direct x86-64 bootstrap of both
Dewy and µDewy. Generations two and three are byte-identical for both compilers;
x86-64/C pipeline execution checks pass. Those generations took 154 and 207
seconds with concurrent validation, not an isolated performance measurement.
The fresh compiler inventory is 4,499 sites / 48,780 source lines / 92.230
per KLOC, within the unchanged 4,500-site and 100/KLOC gates. All 211 corpus
parity cases pass against the same frozen hosted source.

The complete pytest invocation at that checkpoint finished with 4,465 passes,
27 skips and one failure in 3,496.79 seconds. The failure is the lower-level
native scalar-transmute case: lowering treated a scalar element's bit cast as
a mutation and copied its containing array. The fix and a rerun of the full
scalar-lowering case group are tracked separately below. This run is broader
than the prior selections, but is not a clean full-suite/CI certificate.

## Scalar bit reinterpretation storage (2026-09-23)

Transmuting a scalar to another scalar exposes no storage. Native lowering no
longer marks the operand's root binding mutated for it, so a read-only array
parameter whose element bits are reinterpreted stays borrowed instead of
being copied. This repairs the full-suite scalar-lowering failure above.
Both effect inventories now visit a scalar-to-scalar transmute's operand
rather than treating it as an unknown operation: operand effects still count,
while aggregate transmutes keep their raw-exposure boundary.

Validation: five hosted cases (two `no allocates` readers, three effect-
contract rejections) and 369 hosted effect tests pass. A fresh native driver
agrees on the same cases, and the complete native scalar-lowering group,
which failed on `4a3ce3cb` locally and in CI, passes. Fresh bootstrap
integration follows at the next checkpoint.

## Named comparison results (2026-09-23)

A primitive comparison or `not` whose operand intervals decide it now has an
exact boolean value in both interval evaluators, so `const r=a<=?c` followed
by `$assert r` (or `$assert not (not r)`) proves from the same evidence as the
direct assertion, including inside `$proof` bodies. Operands are not
re-evaluated for this: the observed intervals are reused, and an ordered
relation is consulted only while the left operand's identity is still live
(`n<?change(@n)` stays unproven). User functions named like the primitive
operators receive no such value.

Native lowering folds a decided operand into the initializer, which exposed a
µDewy parser defect in both implementations: a declaration initializer that
started with a stable atom stopped after it, so `const b:bool = 42 >? 43` (or
a top-level `const G:int = 40 + 2`) was a syntax error. A stable value is now
accepted only when no operator, call or transmute follows.

Validation: four runtime and four rejection cases pass on hosted; the native
driver agrees on all eight with x86-64/C execution. A new µDewy parity case
runs local and top-level stable-prefix initializers through both µDewy
compilers on x86-64/C; all 87 µDewy parity tests pass.

## Immediate string reads through fields and elements (2026-09-23)

Checkpoint first: source `d6130c73` completed a three-generation direct
x86-64 bootstrap (81/71/85 seconds, byte-identical generations two and
three, pair execution checks passed; artifacts `phase1-d6130c73`). Its fresh
inventory was 4,501 sites, one over the 4,500-site gate: the new boolean-value
rule read a binding record and an operator through optional lookups. It now
uses a copy-free builtin query (`bindings.builtin_binding`) and a `const`
operator view.

Native lowering previously borrowed a string handle for an immediate builtin
consumer only when the operand was a bare identifier; a field or element read
(`f.name =? name` in a loop, `"<{p.name}>"`) retained and released a shared
descriptor around every use. A route of fields and elements down to a binding
now qualifies too, unless an index on it was snapshotted. Consumers opt in
only when nothing runs between the read and the use: a type test; string
equality for its right operand, and for its left when the right operand is
quiet (literals, identifiers, field reads and proven element reads); an
interpolation part when every later part is quiet. `holder.name =?
rename(@holder)` and `"{h.name}-{rename(@h)}"` keep the earlier snapshot.
Hosted lowering never copied these reads, so this changes no hosted output.

Validation: the new `string_read_borrows` fixture passes both compilers on
x86-64/C and is in the focused parity manifest; the native command test now
checks its copy rows. 427 native/hosted string, lowering, view and borrow
tests pass. The compiler inventory falls from 4,501 to 4,141 sites (strings
2,038 → 1,673), measured with a compiler built from this source by the
`d6130c73` pair. Second-generation integration follows.

## Borrowed string operands for slicing, concatenation and narrowed reads (2026-09-23)

Checkpoint first: source `add81b06` completed a three-generation direct
x86-64 bootstrap from the `d6130c73` pair (82/74/86 seconds, byte-identical
generations two and three, pair execution checks passed; artifacts
`phase1-add81b06`).

The immediate-consumer rule above now covers more native string operations.
A string index or slice borrows its base when the index or range endpoints
are quiet: the resulting view retains the base's owner itself, so the
retain/release pair around it was redundant. A frame-resident descriptor has
no owner word and is never used as such a base. Concatenation copies both
operands' bytes before anything else runs, so it borrows the right operand
and, when the right operand is quiet, the left. Reads narrowed from a
`string?` or string-union cell (`t.label isnt? none and t.label =? text`)
load the cell's payload word in place and now qualify like plain string
routes, through an identifier, field or element or through an explicit cast.

Validation: the `string_read_borrows` fixture gained narrowed-optional,
index/slice and concatenation cases, including `h.name + rename(@h)` (left
snapshot kept) and `rename(@h) + h.name` (right read after the call); it
passes both compilers on x86-64/C. The command test now derives the expected
copy rows from the fixture text: exactly the owned binding and the three
operands read before a mutating call remain. The compiler inventory falls
from 4,141 to 3,827 sites (strings 1,673 → 1,359).

## Moves on paths that end in a return; place-lent array moves (2026-09-23)

Checkpoint first: source `520e3445` completed a three-generation direct
x86-64 bootstrap from the `add81b06` pair (82/71/84 seconds, byte-identical
generations two and three, pair execution checks passed; artifacts
`phase1-520e3445`).

Both move analyses took a use's textual position as its path position: a
transfer was a last use only if no reference to the local followed it
anywhere in the function (or it was itself returned). A transfer that falls
through to a later `return` statement of an enclosing block is now also a
last use when nothing in between uses the local or its borrowers, no `break`
or `continue` intervenes, and no loop boundary separates the two: the text
after that return belongs to other paths. Both compilers implement the same
rule, with statement spans per block and sequence intervals checked at the end
(`moves.dewy`, `_compute_moves`).

Native lowering also refused every move of a local it had lent as a place
(`fill(@prefix)`), because such arrays and strings live in a box. A place
argument cannot outlive its call, so the handle now moves out and the box is
emptied; closure captures, which also box, never reach the move set because
their uses are nested. Hosted lowering already moved these locals.

Validation: the new `exit_path_moves` fixture covers moves through nested
arms, a return inside a loop, and a place-lent local; a later use,
`continue` and `break` between transfer and return keep their copies. Hosted
move notes and both compilers' x86-64/C execution agree, and native analysis
reports exactly the three negative sites. The compiler inventory falls from
3,827 to 3,692 sites (arrays 733 → 602).

## Read-only `get` views (2026-09-23)

A dictionary `get` without a default produced an owned optional in both
lowerings: the stored record was shared or copied into a new cell, and the
binding released both at scope exit. This is the arena-lookup shape the 1.1
strategy names first. A `let`/`const` bound to such a `get` now views the
stored element when the existing local-view proof holds (the binding is never
written, lent as a place, captured or exposed, and the dictionary's values
route is stable for its lifetime): elements that are already that optional
are referred to directly; otherwise a frame cell holds the tag and the stored
handle, and a miss uses the `none` cell. The view owns nothing, so there is
no copy and no release; escaping uses (returns, owning arguments, stores)
still copy from it. Lookups with a default, union-valued elements beyond
`T | none`, and rebound or mutated-around bindings keep their owned results.

Both compilers implement the rule (`get_view_lookup` / `view_cell` in
`lower.dewy`; `_get_view_lookup` and `_extract_dict_lookup(view=True)` hosted).

Validation: the new `get_views` fixture covers record, optional-record and
string elements, misses, a loop-local view, a dictionary written while its
binding lives and a rebound binding. Both compilers execute it on x86-64/C,
and the hosted copy notes and native command test pin exactly the three
owned lookups. The compiler inventory falls from 3,692 to 3,637 sites.

The complete pytest run at `520e3445` (in a detached snapshot, concurrent
with other validation) reported 4,523 passes, 27 skips and one failure:
`test_native_global_call_facts_from_source` exceeded its 60-second
subprocess limit. Run alone, the call takes 31.5 seconds at `520e3445` and
30.7 seconds at this session's starting commit `4a3ce3cb`, so the timeout
came from machine load, not a slowdown; the margin is noted for CI.

## Viewed `get` defaults and loop sources (2026-09-23)

Checkpoint first: source `bde5e33e` completed a three-generation direct
x86-64 bootstrap from the `520e3445` pair (88/78/89 seconds, byte-identical
generations two and three, pair execution checks passed; artifacts
`phase1-bde5e33e`).

Native lowering copied the stored element of `d.get(k default)`, often an
array iterated once (`loop route in routes.get(root [])`), which the relation
and effect analyses do on hot paths. Such a lookup now reads the stored
element in place when its storage type is the result's and either a
read-only binding's local-view proof holds or, for a loop source, no write in
the function reaches the dictionary. The default is still evaluated eagerly;
the lowering keeps it alive until the view's scope or loop arm ends and
releases it there (`state.kept_fallback`, `keep_fallback`). Hosted lowering
already read these elements in place. Explicit `@` view demands still reject
`get` results in both compilers, since a lookup result or its fallback is not
the dictionary's storage; views of `get` remain inferred only.

Hosted review found a pre-existing iteration bug that native does not have:
hosted re-reads a loop's source route on every step, so replacing the
variable, the dictionary entry or the looked-up element inside the body
changes or frees what the loop iterates. The new `iteration_snapshots`
fixture records the intended value semantics (native passes it); the hosted
fix follows separately.

Validation: `get_views` gained a defaulted loop source and binding; both
compilers pass it on x86-64/C, and 526 dictionary, iterator, loop and view
tests pass. The one failure in that run, an explicit `@values.get(1 [42])`
that native briefly accepted, is fixed by the inference-only rule above. The
compiler inventory falls from 3,637 to 3,621 sites.

## Loop sources keep their entry value (2026-09-23)

Checkpoint first: `bde5e33e` passed all 200 focused parity cases and the
full 211-case corpus against its bootstrapped pair.

Both compilers mishandled a loop whose body replaces its own source. Hosted
re-read the source route at every step (`loop x in xs {xs=[1000]}` summed
20 instead of 42) and read freed storage when the replaced source was a
dictionary entry. Native read the storage the replacement had just released:
with allocations in the body reusing that block, an array loop summed 27
instead of 42, and a string loop crashed. A loop now iterates the value its
source had on entry. When the source is a route whose root binding the loop
body writes, lends as a place or mutates, or whose root other code can reach
(a global, a capture or a place parameter), both lowerings iterate a shared
copy-on-write snapshot held for the loop and released when it ends. Sources
nothing in the body can change are still read in place, as are temporaries,
which the loop already owns.

The first native version tested whole-function stability instead of the
loop body. The compiler's own `$explicit_copies` modules rejected the
resulting snapshot of a list pushed before (not during) its loop, which is
why the rule is scoped to the body. Remaining snapshots add 43 inventory
sites (3,621 → 3,664); each is a loop that does write its source.

Validation: the `iteration_snapshots` fixture covers a reassigned local,
a replaced dictionary entry, a written `get` source, and array and string
sources whose freed storage the body reuses. Both compilers return 42 on
x86-64/C. A compiler built from this source analyzes its own sources under
`$explicit_copies`. The everyday gate (`-m "not slow"`, run from a copy of the
tree without `.git`) passed 4,505 tests; its three failures were the
measurement-cache tests, which need `git rev-parse` and fail for that reason
alone.

## Runtime effect of this session's copy reductions (2026-09-24)

Checkpoint first: `c498be68` completed a three-generation direct x86-64
bootstrap from the `bde5e33e` pair (85/74/86 seconds, byte-identical
generations two and three) and passed all 201 focused parity cases, the full
211-case corpus and the native command test (inventory and copy-row gates).

On a quiet machine, the bootstrapped compilers from `3139fe4a` (before this
session's ownership work) and `c498be68` compiled the same source
(`c498be68`'s `dewy/bootstrap/main.dewy`, cold, direct x86-64) in 84.1/83.7
and 85.0/85.6 seconds. Top-level `--timings` storage, old → new:

| Phase | Allocated | Copied |
| --- | --- | --- |
| frontend (incl. prelude analysis 6.42 → 7.26 GB) | 21.19 → 22.00 GB | 0.602 → 0.623 GB |
| validation | 14.80 → 14.98 GB | 0.341 → 0.353 GB |
| initialization and reachability | 1.09 → 1.09 GB | 0.353 → 0.353 GB |
| lowering | 15.36 → 15.29 GB | 0.210 → 0.202 GB |
| emission | 3.33 → 3.33 GB | 0.081 → 0.081 GB |

The static inventory fell from 4,501 to 3,664 sites over the same interval,
yet runtime bytes and time did not move: logical copies are about 3% of the
~56 GB allocated, and the removed sites were not hot. (The small frontend
increase comes from the source itself growing, e.g. the boolean-value rule,
not from the lowering changes.) Static copy sites remain the regression gate
the roadmap asks for, but further compile-time progress needs allocation
volume by site at runtime, which the current counters do not attribute.
The next measurement step is per-site allocation attribution (counting
allocations by the lowering site that requested them) before choosing more
ownership mechanisms by where the bytes go.

## Seed release and direct-route throughput (2026-09-24)

The published native seed (`native-5638d42371b5`) predated syntax the
compiler now uses (dictionary entry places), so every `Release native Dewy`
push failed. A `workflow_dispatch` run with `hosted_seed=true` rebuilt stage
zero with the hosted compiler, verified three native generations and
published `native-948ee309a58f`. A following ordinary run seeded from that
release, verified again and produced a byte-identical package.

Throughput, cold direct-built self-builds on a quiet machine, each pair on
its own source: the fully direct pair of 2026-09-18 (`a09a4b4a`, 39.3k
lines) took 61.9/61.8 seconds with validation at 7.6 s and lowering at 12.6
s; the `c498be68` pair (49.2k lines) takes 85.0/85.6 seconds with validation
at 21.0 s and lowering at 18.1 s. The source grew 25% while validation grew
about 2.8x; the entry of 2026-09-20 recorded 44.6 s under the same cold
protocol. Throughput is about 580 lines/s against the 1.6k lines/s (30 s)
target, and the growth sits in the Phase 1 analyses that ROADMAP's lever 6
says must stay linear. `--timings` has no breakdown inside validation yet.

## Validation and lowering breakdown (2026-09-24)

`--timings` now reports sub-phases: `validation.local_places`,
`validation.lifecycle`, `validation.place_contracts`,
`validation.storage_lifetimes`, `validation.prepare`, per-module
`validation.proofs` and `validation.bounds:<path>`,
`validation.public_effects` and `validation.representation_and_reports`
(the prelude analysis reports the same stages), and `lowering.captures`,
`lowering.borrowing`, `lowering.normalize` and an accumulated
`lowering.moves`. Bounds checking also reports each function that takes 20 ms
or more as `bounds.function:<path>@<offset>#<node>`.

First measurement of the `c498be68` source (85 s cold direct build):
bounds checking is the largest single cost, 10.3 s inside prelude analysis
and 15.1 s on the program. Two causes account for most of it:

1. `library/reporting.dewy` takes 9.6 s. `Report` is a structural type
   with ~500 lines of methods, and each of `Error`, `Warning`, `Info` and
   `Hint` (`type of Report & [severity=...]`) receives its own copy of every
   method body, so `layout` alone is checked five times (distinct HIR nodes,
   1.65 s each). Methods inherited from a non-minted parent take the child's
   name as their owner, which defeats the reuse minted families already get.
2. A loop's fixed point re-analyzes its body on every widening/narrowing
   pass (up to 11), including each nested loop's own fixed point, so cost
   grows as passes^depth. `layout` nests loops three and four deep; the
   slowest program functions (`borrowing.details` 1.9 s, a `p0.dewy`
   function 1.3 s) have the same shape. This is the superlinear analysis
   ROADMAP lever 6 rules out.

Lowering: captures 1.3 s, borrowing 4.1 s, normalization 3.7 s, moves
0.2 s; the remaining ~9.5 s is per-function lowering itself.

## First throughput fixes from the breakdown (2026-09-24)

Three changes, each measured with compilers built by the `c498be68` pair
and compiling the same source (cold, direct x86-64):

1. `Report` in `library/reporting.dewy` is now a minted family root
   (`let Report = type of [...]`). Minted families already compile an
   inherited method once for its declaring owner; the structural `Report`
   gave each of `Error`, `Warning`, `Info` and `Hint` its own copy of every
   method body, which prelude analysis then checked five times. Prelude
   analysis falls from 9.5 s to 2.4 s and the self-build from about 82 s to
   74 s. Direct `Report[...]` construction and `Report` parameters work as
   before (a family root is constructible; children are its subtypes), on
   both compilers.
2. The relational proof search built its adjacency lists with
   `get`/push/store-back, copying a list for every edge; it now extends
   them in place (about 0.5 s).
3. The generic arena allocator clears recycled blocks eight words per step
   from 64 bytes up (about 3 s on the direct route). A throwaway build that
   skipped clearing entirely produced identical µDewy output only ~3.7 s
   faster, so clearing is not the remaining allocator cost.

A 20 ms sample of the full self-build with source-named symbols (`dewy
debug --build`) now attributes 13.4% of samples to `_arena_alloc` and 7.0%
to `_arena_release` themselves, plus array/cell construction helpers: the
cost is the number of allocations, not their size. Bounds checking remains
about 20 s; the relational search (`decide_order` → `ordered` → `search`)
scans every fact twice per comparison. The waiting time for the backend
process is 5%.

Checkpoint: `be0749ff` completed a three-generation direct x86-64 bootstrap
from the `c498be68` pair (75/69/74 seconds, byte-identical generations two
and three) and passed 201/201 focused and 211/211 corpus parity cases and
the native command test. Quiet, cold, each bootstrapped pair on its own
source: `c498be68` 84.9/84.5 s, `be0749ff` 73.8/73.8 s (prelude analysis
10.1 → 2.4 s, frontend 30.7 → 21.9 s, validation 20.8 → 19.9 s, lowering
18.0 → 17.1 s). An experiment sharing one relation graph among a
comparison's order queries produced identical output and no measurable
change, so it was not kept: the relational search was hot only inside
`Report.layout`.

Remaining cost ranking: frontend imports/checking ~19 s, bounds on the
program ~13 s, per-function lowering ~9.5 s, backend 7 s, allocator entry
points ~20% of samples overall. The allocation count is the remaining
general lever; ROADMAP ties it to the context allocator, whose surface is
still undecided.

## Context allocators: first slices (2026-09-24)

Implementation of the approved design, steps (1)–(3):

1. **Runtime.** Region memory in `library/linux/system.dewy` comes from
   reserved address ranges (1 GB, halving on failure, up to 32 ranges) with
   an owner table per 64 KB chunk, so `_allocator_of(address)` answers
   "which region owns this block" by address alone (0 for the heap, -1 for
   a released region's chunk). Every `_arena_alloc*` entry point allocates
   from the current context when one is set, and every `_arena_release*`
   ignores region blocks. `Arena` (`reset`, `release`, dropped with its
   owner) is a prelude type; `_allocator_enter(@arena)`/`_allocator_exit`
   switch the context and create the region lazily.
2. **Owner-aware sharing.** A record, array or string is shared (reference
   counted) only if it belongs to the heap or to the current context;
   otherwise copying it makes an independent copy in the current context.
   Growth allocates from the owner of the array descriptor. This is the
   store-owner rule at runtime: a value that leaves a region is copied.
3. **The directive.** `$allocator(@a) { ... }` parses and checks in both
   compilers (`hir.AllocatorBlock`), as a statement or as an expression.
   The arena is lent to its block (using it inside is an error). The
   lexical escapes (the block's value, stores into outer bindings, fields,
   elements, dictionaries, `push`/`insert`, returns) are copy notes, and
   under `$explicit_copies` errors unless written `.copy()`, identically
   in both compilers (`allocator_escapes.py`/`.dewy`).
4. **Native placement, first rule.** The native lowering gives a block
   its arena unless something inside could keep a value beyond it:
   - a store of owned storage (a string, array, record or cell) into
     storage rooted outside the block;
   - a dictionary update or place argument rooted outside the block;
   - a nested function literal;
   - a call of a function with captures;
   - a callee that may itself do such a store to a global, or call
     unknown code.
   Callback targets come from the borrowing analysis's callback
   resolution, and `sort` key literals are ordinary callees. Raw memory
   and system calls are the arena-aware runtime's, so they do not count.
   Scalar stores into outer storage are safe because growth and
   copy-on-write detach allocate where the written structure lives
   (`_arena_alloc_for`). Every exit (end, `break`/`continue`, `return`)
   restores the previous context, then copies the value out and releases
   the arena original. A nested block's arena place does not disqualify
   the outer block. Other blocks allocate from the enclosing context,
   which is always correct. Placement is not observable through values,
   so the hosted compiler lowers every allocator block as an ordinary
   block and the two agree on behavior. Only `Arena.handle` shows the
   difference (`test_native_arena_placement`).

Found on the way, both hosted:

- A flow arm's result read from an owned array local after the arm
  released it (`let s = {let xs = f() kept = xs xs}` gave an empty `s`);
  the result now takes its own reference.
- A loop condition that needs statements (a brand range test for a type
  with descendants: `value is? Block and value.items.length =? 1`) was
  hoisted into `let test:bool = condition`. µDewy `and`/`or` are bitwise
  outside `if`/`loop` conditions, so the right operand ran for every
  node. Adding the first descendant of `hir.Block` crashed the
  hosted-built native driver this way. The test is now an `if` that sets
  the flag.

Found by the gate: the prelude now has a lifecycle hook (`Arena`'s
`$__drop__`), so hosted module loading takes the lifecycle path for every
module. That path attaches the binding registry to the program, and
`test_sort_keys` walked into its parser syntax (the walk now visits HIR
nodes only). Hosted compiles of a small program cost about 0.1 s more.
David decided to keep the hook (an arena that goes out of scope releases
its region) and revisit if the cost becomes a problem.

## The bounds checker as first customer: no gain at module granularity (2026-09-24)

`validate_module` ran inside `$allocator(@scratch)`, with the arena reset
after each module. It qualified for its arena, and its output was
byte-identical. Timings are quiet, cold self-builds of the same source,
both compilers built by the `a49d6a58` pair.

1. **First runtime.** The whole build took 82.0 s → 92.7 s, and validation
   24.9 s → 30.5 s. The profile shows region allocation (a call into
   `_region_alloc` plus clearing each block) costing more than the heap
   allocation it replaced. Every release inside a region also looked up
   the region's owner.
2. **After the runtime fixes below.** Validation takes the same time as
   on the heap (25.2 s against 25.1 s), and the build is still about 3 s
   slower.

The reason is structural. The checker allocates and frees temporaries
constantly. The heap reuses a freed block at once, so the working set
stays small and warm. In an arena a release frees nothing: the largest
module's arena grew to about 1.5 GB (24,013 chunk mappings) and needed a
second address range. The number of allocations, the actual cost, is
unchanged. The change was not committed. Arenas pay where values live
until the reset (per function or per iteration). For churny phases the
lever is fewer allocations.

Runtime fixes kept from this (`library/linux/system.dewy`):

- **Allocation.** Context allocation bumps inline and does not clear
  each block. A chunk is cleared once, when a context allocation opens
  it. Clearing at reset instead broke `native_string_lifetimes` in the
  hosted backend: hosted code reads a frame region's storage after the
  region is reset (it worked because the chunk was not yet reused). That
  is a latent hosted bug to fix; for now resets leave chunks untouched.
- **Large blocks.** A block larger than a chunk comes from the heap, and
  a release frees it there. Oversized region runs were reused only at an
  exact size, so growing arrays left runs of every size and exhausted
  the address range.
- **Address range.** The first range is 8 GB, halving when the
  address-space limit refuses. With one range everything between
  `_region_low` and `_region_high` is region memory. A release, a share
  test and growth then need two comparisons, not an owner lookup.

Later placement work: copying owned values into outer storage at the
store (with runtime owner checks), so blocks that store results outside
can use their arena too.

## Fewer allocations: fact-state joins (2026-09-24)

About 72% of self-build samples are in runtime helpers (allocation,
copies, shares, releases, dictionary probes). They are spread thinly over
the callers. The largest concentrated group was the bounds checker's
`fact_state.join` and the `put` calls it makes (about 5%). The join
collected every input state's facts into a hashed candidate state, which
it then discarded. It now walks each state's entries and skips a fact an
earlier state holds (a hash lookup). The result is the same, including
the interval of a fact that is vacuous everywhere. Validation: 25.1 s →
23.9 s; self-build: 82.6 s → 81.2 s; 3.1 GB less allocated;
byte-identical output.

## The size-class allocator entries were never used (2026-09-24)

Generated code was meant to call `_arena_alloc_16`, `_arena_release_64`
and the other constant-size entries since 0eaa88fb, but neither compiler
ever did. Identifiers spell `_16` as the subscript `₁₆`, so the entries
are bound as `_arena_alloc₁₆`. Both compilers looked them up by the ASCII
spelling: the native helper lists and `arena_class_helper`, and the
hosted `BACKEND_RUNTIME_HELPERS` and `_runtime_helper` lookups. Every
allocation and release took the general entry, which computes a class
from a runtime size.

Both compilers now look the entries up by their bound names. They use
only the power-of-two entries (8 to 256 bytes), mapping any constant size
of 256 or less to its class. Those share the general entries' free lists,
so a block may be released either way. The one-word-larger classes (24,
40, 72, 136, 264) keep lists of their own and stay unused.

The general entries also got cheaper: sizes up to 256 take a
three-comparison class test. (Clearing only the requested size was tried
and dropped: a reused block is zero across its class width by contract,
`test_arena_size_classes`.)

Self-build (cold, same source, against the `c3717db5` pair): 80.6 s →
74.7 s. Validation took 23.8 s → 21.6 s, frontend 23.4 s → 21.7 s and
lowering 18.3 s → 16.9 s. Output is byte-identical between generations.

A first version built the helper name by interpolation (`"{prefix}{width}"`
with a subscript string). That copied the string's storage at every
allocation and release site and added 160 MB of copies to lowering. The
names are now literals.

## Direct x86-64 objects (2026-09-24)

First object writer of the "Direct binary fast path" (ROADMAP), step 3 of
the agreed order.

**Measurement (step 1).** Under load, the self-build's µDewy backend used
12.7 s of CPU. µDewy itself (tokenizing, parsing and code generation,
which are interleaved because the parser drives the backend) was about
6.4 s; tokenizing was about a quarter of that. `as` over the eight chunks
was 5.8 s, and `ld` 0.4 s.

**What landed.**

- `udewy/backend/elf.py` and `udewy/bootstrap/backend/elf.udewy`: an ELF64
  relocatable writer. It writes sections with flags and alignment, a
  section symbol per section, local then global symbols, and RELA tables.
  `.L` labels stay out of the symbol table. It declares the GNU OS/ABI when
  a section uses `SHF_GNU_RETAIN`, as gas does; otherwise
  `ld --gc-sections` ignores the flag.
- `udewy/backend/x86_64_object.py` and
  `udewy/bootstrap/backend/x86_64_object.udewy`: an assembler for exactly
  the x86-64 backend's closed set. That is about 45 mnemonics and the
  directives `.text`, `.data`, `.bss`, `.section`, `.globl`, `.weak`,
  `.hidden`, `.extern`, `.quad`, `.byte`, `.balign` and `.zero`. Branches
  are always near and local labels resolve at the end. `call`/`jmp` to a
  symbol use `R_X86_64_PLT32`, RIP-relative operands `R_X86_64_PC32`, and
  `.quad sym` `R_X86_64_64`. Anything else is an error, never a guess.
- The native module is still split into chunks. Each chunk is assembled
  by a forked child from memory, so no assembly text is written or read
  back. Both compilers take the path with `UDEWY_OBJECT=direct`. It omits
  debug metadata for now: `debug` builds need the assembler until the
  direct path writes `.debug_line`.
- `tools/compare_objects.py`: the per-symbol comparator from the
  acceptance checks. It compares instruction sequences with branch targets
  as instruction indices, collapses NOP padding, and compares relocations,
  data bytes and relocations, section types, flags and alignment, and
  symbols. It ignores gas's `.note.gnu.property`.
- `udewy --assemble in.s out.o` and
  `python -m udewy.backend.x86_64_object in.s out.o` run the direct path
  on its own.

**Checks.** Every section of the compiler's own assembly (61,183 sections)
agrees with gas, and so does the encoder edge-case fixture
`tests/fixtures/x86_64_encoding_edges.s`. The Python and native
assemblers write byte-identical objects. A compiler built from direct
objects rebuilds itself to byte-identical µDewy.
`tests/python_misc/test_direct_objects.py` covers:
- comparator self-test and determinism;
- programs with the same exit codes, stdout and stderr on both paths,
  in both µDewy implementations;
- an extern `.o` and a shared library through the PLT;
- the same `ld` error for an undefined symbol;
- `--gc-sections` removing an unreferenced function while keeping a
  retained section;
- a non-executable stack.

**Cost.** Under load, on the compiler's 55 MB assembly: native
`--assemble` uses about 2.1 s of CPU against 5.9 s for `as`. The whole
backend step, split into 8 chunks: direct 10.4–11.5 s wall and 9.5 s CPU,
against 12.3–13.1 s wall and 13.4 s CPU through `as`. The encoder still
re-parses the backend's text. Emitting instructions without text is the
larger remaining cut.

## µDewy bytecode: recorder and player (2026-09-24)

Step 2 of the direct binary fast path. `udewy/BYTECODE.md` specifies the
format. It is a recording of the 53 backend calls the µDewy parser makes
(six pure queries are left out), with LEB128 operands. Ids are renumbered
densely per id space (functions, globals, strings, statics, slots, split
labels), so a stream does not depend on the backend that recorded it.
Stable values keep their kind, and a player turns them back into its own
backend's references.

- The native recorder and player are in `udewy/bootstrap/stream.udewy`,
  generated from one operation table. The recorder swaps the backend's
  function pointers and records only the parser's own calls: the default
  `binary_immediate` calls `save_value`, `push_const_i64` and `binary_op`
  itself, and recording those too made replay emit them twice. The Python
  recorder and player are in `udewy/stream.py`. The recorder wraps the
  backend and carries each reference's kind and label on the reference
  value itself (a `str` or `int` subclass).
- `UDEWY_RECORD=path` records a compile, and an input ending in `.ubc` is
  played instead of tokenized and parsed. Both compilers support both.

**Checks.** The compiler's own µDewy (23 MB) records to a 16.5 MB stream
whose replay produces byte-identical assembly, with and without debug
information. On `udewy/tests` programs and a globals fixture, the Python
and native recorders write byte-identical streams, and replay reaches the
parsed assembly in both implementations (`tests/python_misc/test_udewy_stream.py`).

**Cost.** Under load, with direct objects for both runs: compiling the
compiler's µDewy source took 8.4 s wall and 9.5 s CPU; replaying its
stream took 5.2 s wall and 6.4 s CPU. That difference is what step 4
(Dewy writing the stream instead of µDewy text) removes from a cold
compile, along with part of Dewy's 3.5 s text emission.

## Direct wasm32 modules (2026-09-25)

Part of step 5. The wasm32 backend's WAT is a closed dialect: module-level
`type`, `import`, `global`, `table`, `func`, `elem`, `data` and `export`
forms, and flat function bodies with labeled `block`/`loop`/`if` and about
60 instructions. `udewy/backend/wasm_binary.py` and
`udewy/bootstrap/backend/wasm_binary.udewy` encode it in `wat2wasm`'s
section order with minimal LEB128 sizes. `UDEWY_OBJECT=direct` uses them
instead of running `wat2wasm`, and `udewy --assemble in.wat out.wasm` runs
the native one on its own.

Every `udewy/tests` program that builds for wasm32 (40 of them) encodes
byte-identically to `wat2wasm`, in both implementations. The modules pass
`wasm-validate`, and the compile path writes the same module either way
(`tests/python_misc/test_direct_wasm.py`). Two bugs came up while matching
`wat2wasm`: a function's signature must end at its first instruction (an
`if (result i64)` is a block type), and a `(type ...)` after the header
belongs to a `call_indirect`.

## Direct AArch64 objects (2026-09-25)

The rest of step 5. `udewy/backend/aarch64_object.py` and
`udewy/bootstrap/backend/aarch64_object.udewy` assemble the arm backend's
closed set into ELF objects (`EM_AARCH64`) on the shared writer. The set is
about 55 mnemonics with pre- and post-index, unscaled and scaled
addressing. The encoders resolve the aliases an assembler does: `mov` as
`orr`, `add #0`, `movz`, `movn` or a bitmask `orr`; `csetm`/`cset` as
`csinv`/`csinc`; `cmp` as `subs`; immediate shifts as `ubfm`/`sbfm`.
`ldr xN, =imm` becomes one `movz` when that builds the constant, and
otherwise a load from a literal pool at the end of the section, which is
what `llvm-mc` does. Relocations are `ADR_PREL_PG_HI21`, `ADD_ABS_LO12_NC`,
`CALL26`, `JUMP26` and `ABS64`. `UDEWY_OBJECT=direct` uses them (only `ld`
is still needed), and `udewy --assemble in.s out.o --target arm` runs the
native one.

No AArch64 binutils or emulator is available here, so `llvm-mc` is the
reference, and the checks cover encoding, not execution. Every
`udewy/tests` program the Python arm backend builds (54) matches `llvm-mc`
section for section, with the same relocations. So do the 37 the native
arm backend builds, through the native encoder. The Python and native
encoders write byte-identical objects, and a logical-immediate fixture
matches too (`tests/python_misc/test_direct_aarch64.py`). The acceptance
list still wants linking and running once a toolchain or emulator is
available.

Found later with RISC-V: neither encoder word-aligned the code sections it
filled (alignment 1), so `ld` could have placed code off a 4-byte boundary.
Both now word-align any section that holds an instruction. The tests
compare section headers too (type, flags, alignment, NOBITS size).

## Direct RISC-V objects (2026-09-25)

Step 7. `udewy/backend/riscv_object.py` and
`udewy/bootstrap/backend/riscv_object.udewy` assemble the riscv backend's
closed set (RV64IMFD plus the pseudo-instructions it uses) into ELF objects
(`EM_RISCV`, double-float ABI) on the shared writer. They use the long form
the roadmap chose, with nothing compressed and no `R_RISCV_RELAX`:
- `la` is `auipc` + `addi`. The high part carries `PCREL_HI20` against the
  target. The low part carries `PCREL_LO12_I` against the `auipc`'s own kept
  `.Lpcrel_hiN` label.
- `call` is `auipc` + `jalr` with `CALL_PLT`. A local function in the same
  section is reached without a relocation, as `llvm-mc` does for recursion.
- `li` expands to LLVM's RISCVMatInt sequence
  (`udewy/backend/riscv_materialize.py`). On 17,189 fuzzed constants it
  matches `llvm-mc` instruction for instruction.
- A conditional branch whose label is out of ±4 KiB becomes the inverted
  branch over a `jal`. The Python encoder lays out items until nothing
  changes. The native one emits in place and inserts the `jal` words in
  batches, shifting labels, pending items and relocations. Neither re-pads
  alignment inside code, which the backend never emits; both refuse that
  case.

RISC-V relocations name local symbols themselves rather than section
symbol plus offset, so the ELF writers gained kept symbols and `e_flags`.

The checks use `llvm-mc -mattr=+m,+f,+d,-relax,-c` as the reference, since
no RISC-V binutils or qemu is available here. All 54 `udewy/tests` programs
the riscv backend builds match it, along with an edge fixture (relaxed
branches, `li` shapes, swapped pseudo-branches, data relocations with
addends). The comparison covers section contents, relocations, and
headers. The one header difference: `llvm-mc` leaves `.section`-made code
sections byte-aligned, where the direct path word-aligns them. The Python
and native encoders write byte-identical objects
(`tests/python_misc/test_direct_riscv.py`). `UDEWY_OBJECT=direct` uses the
encoders in both backends, and `udewy --assemble in.s out.o --target riscv`
runs the native one. Linking and running still wait for a toolchain.

## Direct x86-64 objects with debug information (2026-09-25)

Step 6. Debug builds no longer fall back to `as` under
`UDEWY_OBJECT=direct`, in either µDewy. Both x86-64 writers now also
accept:
- `;`-separated statements, with `#` and `;` ignored inside string
  literals;
- `.uleb128`, `.value`, `.long` and `.string`;
- label differences in `.quad`/`.long`, resolved once every label is
  placed;
- `.long label` as `R_X86_64_32`.

From the `.file`/`.loc` rows they write the `.debug_line` program the
backend used to leave to gas. It has a DWARF 3 header like gas's (line base
-5, range 14, directories split from base names) and one sequence per
section, which starts with `DW_LNE_set_address` through the section symbol.
The closed set also gained the SSE moves and conversions used by float
extern calls (`movd`/`movq` between general and xmm registers,
`cvtsi2ss/sd`, `cvttss2si/sd2si`). Before this, three SDL/GL demos could
not take the direct path at all.

The check goes further than per-symbol equivalence. gas's `{disp32}`
prefix forces its jumps near, giving the direct path's layout, and against
that reference every section matches byte for byte except `.debug_line`.
That includes `.debug_info`, where function lengths and label differences
live. `.debug_line` matches in decoded rows
(`readelf --debug-dump=decodedline`) and in its relocations' targets. All
57 `udewy/tests` programs pass, and the native writer produces identical
bytes. The native backend's own DWARF spelling matches too. gdb stops on a
µDewy source line in binaries built on the direct path by either compiler,
and the gdb/lldb/editor debugging suites pass on direct objects
(`tests/python_misc/test_direct_objects.py`).

Unrelated fix on the way: two slow-marked tests in `test_breakpoint.py`
failed on HEAD because their HIR walkers descended into node *classes*
(which also have `__dataclass_fields__`). Skipping those made the walkers
revisit shared nodes endlessly, so they now keep a visited set.

## Step 4 sizing: Dewy writing the bytecode stream (2026-09-25)

Steps 1–3 and 5–7 are in place, and this is the one left. The emitters
(`dewy/backend/udewy/emit.py`, `dewy/bootstrap/backend/udewy/emit.dewy`
and `program.dewy`, about 1,350 lines between them) write µDewy text from
lowered HIR. A stream writer would walk the same HIR. To play back to the
*same assembly* as the text route (the obvious oracle), it has to make p0's
calls in p0's order:
- operators in postfix order, with `binary_immediate` for a literal
  right-hand side;
- `save_value` around call arguments;
- `cond_and/or_split` inside conditions;
- strings interned at first use;
- functions declared at first reference;
- global initializers synthesized into `__udewy_global_init_N__` with
  `set_module_init`;
- the reachability set computed from the function-reference graph.

That is p0's driving logic (about 1,900 lines) fused into the emitter, in
both Dewy compilers. The payoff is the tokenize-and-parse share of the
µDewy stage. Earlier, under load, playing the compiler's stream took 5.2 s
against 8.4 s for parse plus code generation. So step 4 saves roughly 2–3 s
of the self-build, minus whatever writing the stream costs over writing
text.

## Past 65,535 sections (2026-09-25)

The full suite under `UDEWY_OBJECT=direct` turned up a real gap. A debug
build is never split into chunks, so one object holds every function
section and its relocation section. A Dewy program's object passes 0xff00
sections, and the writers packed section indices into 16-bit fields. Both
ELF writers now use extended numbering the way gas does:
- a symbol whose section index is ≥ `SHN_LORESERVE` holds `SHN_XINDEX`,
  and the real index goes in a parallel `.symtab_shndx` table;
- the header count and string-table index move into section header 0.

A 65,290-section fixture matches gas in section contents and headers, the
native writer's bytes equal Python's, and the result links and runs.

The acceptance run: the whole everyday suite with `UDEWY_OBJECT=direct`, so
every µDewy build on every target writes its objects directly. After the
numbering fix, 4,615 tests passed. The 52 failures were all tests that read
the text the direct path no longer writes (`.s`/`.wat` in the cache, the
`as`-then-`ld` command list), plus one code-size ratio that always-near
jumps dilute (9.3% against a 10% bound). Those tests now pin the assembler
path, and all five files pass in both modes.

## Direct objects become the native default; running AArch64 and RISC-V (2026-09-25)

Agreed with David: the native µDewy now writes its objects (and wasm
modules) itself by default, and `UDEWY_OBJECT=as` selects the assembler
(`be_direct_objects` in `common.udewy`). The Python µDewy keeps the
assembler by default, since it is the faster route there. Tests that read
the assembler's text now set `UDEWY_OBJECT=as` explicitly instead of
clearing the variable.

Cross tools now come from pixi (`pixi global install --environment cross
binutils_impl_linux-aarch64 binutils_impl_linux-riscv64
qemu-execve-aarch64 qemu-execve-riscv64`), plus distro-named symlinks
(`aarch64-linux-gnu-as`/`ld`, `riscv64-linux-gnu-*`) in `~/.local/bin`.

With those, every `udewy/tests` program that builds for AArch64 and RISC-V
runs under qemu with the same exit code and output on the assembler and
direct paths: 122 builds with the Python compiler and 98 with the native
one. The rest need host-only libraries or web intrinsics, or are library
modules. The direct test suites gained an execution check.

Running the code also exposed an old bug in both backends, on both paths.
`__alloca__` evaluated while call arguments were spilled put its buffer
between the spilled words, so every later argument was read from the wrong
slot and `test_alloca_spills` crashed. Like x86-64, the backends now slide
the spilled words below the new top of the stack. More than 255 (AArch64)
or 127 (RISC-V) pending values is a compile error, not an out-of-range
offset.

## Step 4: the Dewy compilers write µDewy bytecode (2026-09-25)

David approved step 4 after the sizing above. Both Dewy compilers now keep
a module's bytecode (`<name>.ubc`) in the cache instead of its µDewy text.
`DEWY_EMIT=udewy` keeps the text for reading, and is an interim knob (see
the roadmap's note on build settings).

**Native.** `emit.dewy`'s Writer has a stream mode. At every emission site
the text spelling and the token spelling sit side by side, so the two
routes cannot drift apart unnoticed. In stream mode it records the µDewy
tokens the text would tokenize to:
- `name(` fuses into one call token and `)(` into an expression call, only
  when the text has no space between them;
- update operators fold into one assignment token;
- type annotations split at `<`;
- `true`/`false` are number tokens;
- `# @loc` markers become marker entries.

`bytecode.dewy` parses those tokens with a port of `udewy/p0.py`
(statements, precedence climbing, literal immediates, the parenthesis rule
inside conditions, stable initializers, `__static_words__` and
`__static_alloca__`, global initializer functions, reachability). It
parses one top-level declaration at a time and writes the stream directly.
`$include_bytes` globals go into a prologue that plays first, as their
declarations do in text. Their ids are allocated at first use, which the
players accept (ids map through tables).

**Hosted.** `udewy.frontend.entry_point` takes the text from memory and a
record path. The CLI compiles from memory, through the direct bridge or
the parser, and records the backend calls of that compile as the `.ubc`.

**Checks.**
- An oracle compares the two routes: the native compiler writes both the
  text and the stream, the text is parsed by the Python µDewy parser with
  no source path, the stream is played, and the assemblies must be equal.
  They are equal for hello world (x86-64 plain and debug, AArch64,
  RISC-V) and for the compiler itself: 56 MB of assembly, from 10.7 MB of
  bytecode against 23.8 MB of text.
- A compiler built through the stream (gen3) is byte-identical to one built
  through text (gen2).
- `tests/python_misc/test_dewy_bytecode.py` covers five programs, plain and
  debug, played on x86-64 and AArch64, and runs them. It also checks the
  hosted artifact.

**Timing.** Self-build with a direct-route compiler, while other work
loaded the machine: emission 3.84 → 3.34 s (tokens, parse and encode
together cost less than formatting text), the µDewy backend 5.26 → 3.38 s
(replay instead of tokenize and parse), total 77.8 → 72.7 s.

## Narrowed records stay handles (2026-09-25)

A new profile of the self-build puts about 27% of samples in the
allocation machinery, and `_copy_object` alone is 13% inclusive. The
largest source was narrowing. `AST` is a branded parent record, so a local
of that type holds one handle and the brand sits at +24. Narrowing it with
`node is? A|B|…` gives a union of children, which is stored as a tagged
cell. So every narrowed read packed a cell around a copy of the whole
record. A read back as the parent (for example, passing the node on to
`push_children`) then unpacked the cell and copied the record again, and
released both afterwards. Tree walks paid this on every node.

The lowering now reads such a value through the record's own handle when
the cell is never needed:
- `narrowed_record` recognizes the two shapes: a local whose read type
  narrows a stored record type, and a cast narrowing a record-valued
  expression. It returns the borrowed handle.
- A forwarded field read (`node.value` over a union) reads the field in
  place when every member keeps it at one offset and one type
  (`forwarded_in_place`).
- Upcasts back to a record, and borrowed record arguments, read the
  handle.
- Owned uses take one copy instead of two plus a cell.
- A cast that consumers treat as owning a fresh value (a cast of a packing
  cast) still returns a copy, so no consumer ever releases the local's own
  handle.

Generated code: 5,032 → 4,062 `_copy_object` call sites and 8,598 → 7,690
cell constructions. Self-build (cold, two rounds each): 73.7 s → 70.1 s,
with 160.9 → 151.2 GB allocated. Generations 6 and 7 are identical.

The general fix is representational. A union whose members all carry
brands could be a handle itself, discriminated by the brand, which would
make every narrowing free. That would change union storage in both
compilers, so it is a design question for David, not part of this slice.

A native miscompile turned up on the way, and was fixed. It affects a
dictionary read through a field of a record that a call returns
(`layout(n @state).offsets.get(k)`, or `k in? layout(n @state).offsets`).
The lookup treated the dictionary field as the temporary to release. When
the call returns a block shared with storage it keeps (here a cache in a
mutable argument, as `object_layout` does), releasing the field on its own
freed the cached dictionary's arrays, and the next lookup crashed. Now
`dict_parts` evaluates such a record once, looks up through its field, and
releases the record itself (`DictParts.owner`). Hosted was not affected.
Pair check `native_cached_record_fields` covers lookups, membership,
lengths and iteration through such fields.

## Record unions are handles (2026-09-25)

David approved the representational fix proposed in the previous entry,
and said representation choices are generally mine when they serve
performance. A count of the self-build's union cells (a counting patch on
the compiler's own µDewy) showed why it matters: 167.6 M cells were
allocated. 62 % of them had a record payload, which was usually a fresh copy
as well:
- 30 % were unbranded records, mostly `Interval?`, `bigint?` and the fact
  state's `State?`.
- 25 % were narrowing results inside one family (`(AST & ~X) | X`).
- 7 % were other branded records.
Scalar payloads (`int64`, 33 %) are the remaining cell traffic.

Native lowering now classifies such unions separately
(`layouts.record_union`). A union qualifies when its non-`none` alternatives
are records of one storage root: a single shape, or records of one brand
family, whose root is their nearest common ancestor. Unit error mints stay
in cells. Such a union is stored as the root's handle:
- A value is a block with the root's full layout, or zero for `none`.
- Record queries (`object_valued`, `object_type`, `object_layout`, the
  copy/release/write helpers) see the root through `storage_base`.
- Type tests read the brand word, with a zero check when the union can be
  `none`.
- Narrowing to a member, widening to the root and packing a root-sized
  record are free.
- A field of such a type holds the handle in one word (`field_read`/
  `field_write`, copies share the block, releases go through the handle).
  This also keeps recursive families finite.
- Copies, uniqueness and pinning skip zero.
- Forwarded field reads load one offset when every alternative keeps it
  there; otherwise they dispatch on the brand.
- Tagged cells convert at their boundaries: `cell_pack` packs zero as
  `none`, a narrowed cell read yields the payload handle (zero for a `none`
  tag), and `get`, iterator targets and borrowed union loans use the
  handle directly.
- A cast between a record and a record union follows the record-upcast
  ownership rule for both cast kinds (`relative_cast`). The first build
  missed this for representation casts. `return result` in a function
  returning `State?` then copied the local while the return path also
  transferred it, which leaked every refined fact state (about 90 MB
  retained per compile). Finding it took a type bisection switch and an
  allocation-site tracer over the lowered µDewy (see the Validation
  paragraph).

Self-build, cold, two rounds each against `phase1-q`: 71.5 s → 61.6 s, with
152.0 → 122.7 GB allocated and peak arena bytes 3,017 → 2,933 MB. The 3-gen
fixed point holds (generations 2 and 3 are byte-identical).

Hosted lowering keeps its cells. The new fixture also crashed the hosted
binary, a bug that predates this change. A loop target of record type,
narrowed to several children and passed as a union, went out as the bare
record pointer: iterator targets were never entered in `object_storage`,
so no family view was built. Iterator discovery now registers them.

Validation: pair check `native_record_unions`
(`tests/fixtures/native_record_unions.dewy`, also run hosted by
`tests/python_misc/test_record_unions.py` on x86-64 and C). It covers:
- family unions from narrowed roots, including loop targets;
- nullable records in fields, arrays, dictionaries and `get`;
- mixed record/scalar cells;
- fact-state style transfers through place parameters;
- optional `bigint` bounds.
A second pass must leave `_arena_live_bytes` unchanged. The old native
compiler fails that leak check, and so did the first cut of this change.
The leak was found by compiling a driver that runs `graph.compile` four
times. It retained 166 MB per round with record unions and 76 MB without,
which is a pre-existing native leak, left for the allocation work.
Bisecting the root type ids narrowed the extra retention to `State?`. The
tracer then located the leaking allocation site in
`comparison_facts.refine`. After the fix, the driver retains 75.7 MB per
round.

Gate: 4,742 passed, 1 failed. The failure was `test_native_compiler_command`,
which expected the coverage fixture's `Box|none` snapshot to be reported as
a cell copy. It is a record copy now, so the test checks the copy site; the
rerun passes. A 3-generation bootstrap from `phase1-q` gives identical
generations (`phase1-r`), and `tools/check_native.sh` passes on that pair.

## Allocation sites: lazy strings, in-place Unicode tables, const views (2026-09-25)

A per-statement allocation counter over the self-build's lowered µDewy
(`__site` stores before each statement, counted in the arena entry points)
attributed 631 M allocations. The largest findable costs were:

- Every dynamic string segmented eagerly. `lazy_strings` requires the
  `_utf8_grapheme_scan` runtime helper, which `library/unicode/runtime.dewy`
  provides as an import alias (`from … import scan as …`) since 2026-09-20.
  An alias is not an export, so the helper never reached `prelude_bindings`
  and lazy segmentation stayed off. Each `"{id}"` then built a boundary
  table, a byte descriptor, a scratch array and two optional cells.
  `graph.runtime_helpers` now also finds a helper in a prelude module's
  scope.
- With segmentation lazy, the cold length query in `cold_string_length`
  showed a second cost. A non-ASCII scalar copied a whole Unicode property
  table (about 24 KB) per lookup, because `property(table:array<uint8> …)`
  materializes its binary-literal argument. The segmenter now reads the
  tables in place (`table_byte`, selected by a small `TABLE` enum). This
  also speeds up eager segmentation of any non-ASCII text.
- `const` globals never change after startup, so borrowing now treats them
  as stable owners (`captures.Plan.constants`). `info = BASE_SPECS[base]` in
  the tokenizer used to copy the record every call and rebuild its inner
  set's hash index each time (14 M allocations). It is now a view, and the
  index is built once.
- Traversals that allocated `hir.children(node)` per node now push onto
  their worklist: `effects.collect_roots` (via `push_children_reversed`, which
  keeps the source order), `predicate_effects`, `hir_facts`, `public_effects`,
  and `captures.discover`/`locals`/`references`, which were recursive and are
  now worklists with the same preorder.

Self-build against the record-union compiler, cold, two rounds with a test
running alongside: 64.0 s → 59.8 s, 122.7 → 105.0 GB allocated, peak
2,935 → 2,843 MB. Generations 2 and 3 are identical.

Gate: 4,736 passed, 7 failed. All seven were `test_library_graphemes` cases,
whose harness calls the library's `word(bytes offset)` helper. The first cut
had changed that helper's signature. It is public again, and the in-place
reader is `table_word`. The rerun passes, along with the union-view and
string-descriptor tests. A 3-generation bootstrap from `phase1-r` gives
identical generations (`phase1-s`), and `check_native` passes on that pair.

## Allocation sites, second pass (2026-09-25)

A re-profile after the previous slice (493 M allocations) led to four more
source-level fixes in the compiler's own analyses:
- `fact_state.find` returned `addr?`, a heap cell per call (17.6 M). The
  entries now answer through `position_of`, a plain word that is -1 when
  absent. `join` reads held intervals in place instead of through
  `evidence`, which copied each interval into a union. Its vacuous branch
  no longer copies the candidate interval up front.
- The tokenizer's `is_based_digit` scanned the base's alphabet as grapheme
  views, one string descriptor per character (7.8 M). The digit sets are
  now built once (`BASE_DIGITS`, `FOLDED_DIGITS`). Only a case-insensitive
  miss still casefolds.
- `has_proposition` built two escaped `identity_key` strings per
  comparison. `propositions.same_identity` compares the same fields
  directly.
- The bounds checker's `evaluate_inner` and the effect analysis's child
  visits staged children in a fresh array per node. They now use a segment
  of a shared stack (`Checker.child_stack`, `Analysis.child_stack`) above
  the caller's segment.

Self-build, cold, two rounds each: `phase1-q` 68.5 s / 152.1 GB, `phase1-s`
55.7 s / 105.1 GB, this slice 53.2 s / 91.2 GB. Peak memory is unchanged at
2,847 MB.

Gate: 4,743 passed. A 3-generation bootstrap from `phase1-s` gives identical
generations (`phase1-t`), and `check_native` passes on that pair.

## Prelude validation reuse; lazy initialization requirements (2026-09-25)

The saved prelude validation (`proofs.Prelude`) was never reused, in cold
or warm builds. `lifecycle_runtime.prepare` ran over every module, prelude
included, after the prelude's decisions were saved. It rewrote prelude
bodies, which is an edit inside the saved graph, and `reusable` then
discarded the saved decisions. So every compilation, even of a hello-world
program, bounds-checked the whole prelude again (about 3 s, mostly
`reporting.layout`). Now:
- The prelude stage runs the lifecycle rewrite over the prelude before
  analyzing and caching it (`modules.dewy`).
- Full validation passes `prepared=` (the saved prelude's module count).
  Lifecycle collects hooks from every module, but rewrites only the bodies
  of later modules and only reads settled items.
- Generated lifecycle helpers join the last (entry) module instead of the
  first, which is a prelude module.
A warm hello-world compile went from 6.0 s to 2.9 s (validation 3.5 s →
0.27 s). A cold one went from 9.9 s to 7.1 s, both measured under load.

The initialization analysis recorded every requirement into every
enclosing call frame, on each cache hit as well (`record_requirements`, 3 %
of the self-build's samples). A nested call starts from its caller's
initialized set, so an inner frame's available bindings contain an outer
frame's. Requirements are now recorded in the innermost frame and merged
into the parent once, when the frame closes. A cached call drops the
frame's own id from the calls it assumed.

Self-build, cold, two rounds: `phase1-t` 53.2 s → 50.2 s, 90.9 → 87.7 GB
allocated. Initialization and reachability 2.5 s → 1.2 s; validation
16.2 s → 14.6 s. Generations 2 and 3 are identical.

Gate: 4,743 passed. A 3-generation bootstrap from `phase1-t` gives identical
generations (`phase1-u`), and `check_native` passes on that pair.

## Warm compiles: prelude cache key and restore (2026-09-25)

With prelude validation reused, `prelude_restore` dominated a warm
hello-world compile. A profile showed where it went:
- `prelude_cache.locate` read the whole compiler executable (22 MB) byte by
  byte with `push`, only to hash it for the cache key. The key now uses the
  executable's stat identity: device, inode, size and modification time.
  That comes from `_file_stamp` in `library/linux/files.dewy`, a
  compiler-private helper beside `_file_mode`.
- `restore` copied the 16 MB payload out of the file's bytes before
  decoding it. The codec gains `decode_from(@reader)`, emitted by
  `tools/generate_native_cache.py`, and the checksum is taken over the
  payload in place (`fingerprint_from`).
- `_read_bytes_at` reserves the file's size (fstat) once, instead of
  growing per 4 KB chunk.

A warm hello-world compile now takes 1.75 s: 6.0 s before this session's
validation reuse, and 2.9 s after it. Restore takes 1.1 s, split between the
per-byte file read and the decode. The self-build is unaffected (it is
cold). Generations 2 and 3 are identical.

Gate: 4,743 passed. A 3-generation bootstrap from `phase1-u` gives identical
generations (`phase1-v`), and `check_native` passes on that pair.

## Compile leak: argument temporaries, raw-exposure cleanup; range ends (2026-09-26)

A repeat-compile driver (`compile_once` per round, retained bytes measured
between round starts) put the true per-compile leak at 1.72 MB after the
earlier 2026-09-26 fixes. An allocation-site tracer that also records the
calling site found these:

- **Unproven `get` passed to a read-only parameter** (native). The borrowed
  argument path evaluated `snapshot.numbers.get(id)` with `expression`,
  which shares the stored element into an owned result, but treated it as
  a view, so nothing released it. `call_argument` now reads the stored
  element in place (`dict_lookup(view=true)`) when `get_view_lookup`
  allows. Otherwise the owned result is passed and released after the
  call. Every `meet(facts.lookup(...) ...)`-style interval in the bounds
  analysis leaked through this path: 1.72 MB → 433 KB per compile.
- **Raw exposure switched off all cleanup** (native). A raw intrinsic with
  an aggregate operand (`__load_i64__(c_path)`) disabled cleanup for every
  local of the function, so `_read_bytes_at` never released its result's
  source array. The exposed array or string is pinned, and releasing
  pinned storage does nothing, so only record and cell exposure (whose
  blocks are not pinned) still disables cleanup.
- **Pinned C paths** (library). Each file operation pinned a
  NUL-terminated path copy. `_c_path_into` now copies the path into the
  caller's PATH_MAX frame buffer; the prelude cache's rename uses it too.
  Together with the previous item: 433 KB → 89 KB per compile.
- **Projected getter reads retained twice** (native). `srcfile(...).body`
  lowers through a getter projection that returns the selected leaf,
  already owned. `expression_owns` still answered as for a borrowed
  getter's field, so the consumer retained it again. One handle leaked per
  use, and it kept each source text and its boundary table alive.
  `projected_read` now decides both the lowering and the ownership:
  89 KB → 7 KB per compile.
- **Record literals pushed into arrays** (hosted). A `move` copy of a dying
  literal cloned its record-typed cell payload (e.g. a `bigint` field) and
  abandoned the original. A dead temporary's arena payload now changes
  owner by handle (`take`); `adopt` keeps cloning, because its source is
  released later.
- **Keyed sort** (hosted). Each key call copied the element into a frame
  slot without releasing it, and the record and radix buffers were never
  released. The key now reads the stored element, as in native, and both
  buffers are released.
- Also in this batch: intrinsic operand temporaries are released after the
  call; a literal sort key is analyzed like a direct call instead of
  poisoning its callers' borrows; `t2` compares child id arrays element-wise
  (`same_ids`) instead of with `=?`; and by-value arguments to a callee that
  keeps its own share are reclaimed (`reclaimable_arguments`).

**Parity.**
- A bare runtime range `0..n` is inclusive in both compilers (native had
  treated it as `[0..n)`); `native_runtime_range_ends` covers it.
- Hosted now converts an abstract `int` to a fixed width with a
  range-proven value cast, like native, so `(i % 7) as addr` over a loop
  counter compiles on both. An unprovable conversion is still rejected by
  both.

New fixture `native_argument_temporaries` (pair check 61 and hosted
x86-64/C tests) checks `get` arguments, optional and string lookups,
defaulted lookups, literal pushes with `bigint` fields, a keyed sort and a
projected getter read.
It requires an unchanged live arena on a second run. It fails on the old
native (2) and on the old hosted (2).

Known leftovers:
- Hosted still leaks in `bytes as string|none`.
- `write_bytes` pins what it writes; see the scoped raw access proposal.
- `nat_types` needs no decision: it passes (42).
- Proposals for array/record `=?` and scoped raw access are in
  `PHASE1_DESIGN_PROPOSALS.md`.

Per-compile retained memory on the repeat-compile driver (hello world) went
4.2 MB (`phase1-v`) → 7 KB. Self-build: 50.7 → 49.5 s, peak RSS
2.88 → 2.63 GB.

Validation:
- Gate: 4,747 passed.
- A 3-generation bootstrap from `phase1-w` gives identical generations
  (`phase1-x`), and `check_native` passes on that pair.
- The intermediate `phase1-w` pair (without the projected-read fix)
  also bootstrapped identically and passed `check_native`.

## Conditional component transfers (2026-09-26)

A component can now leave its owner on some paths only, in both compilers:

```dewy
if yes {taken=consume(pair.left)}        # pair.right is still read later
loop i in [0..3) {
    total+=consume(pair.left)
    pair.left=Handle[10+i]               # renewal before the next iteration
}
```

Both were rejected before ("requires an independent copy"). Branch-aware
liveness (`ownership_liveness`) now keeps entries per field route: a read of
`pair.right` no longer keeps `pair.left` alive. A field assignment kills the
replaced component and leaves a *store* entry, which needs the enclosing
storage (so consuming an ancestor stays rejected) but not the old component.
A consumed component gets a flag in its owner (`component_flags`), declared
with the owner. Consumption clears it; the owner's cleanup (scope exit,
return, break, whole replacement) drops that component only while the flag
is set; and a field replacement drops the old value under the same guard,
then sets it again. Whole-owner replacement restores all of an owner's
component flags. Only field routes through hook-free wrappers to components
without a custom move qualify. Element routes and custom moves keep today's
rules, and a later read of a maybe-moved component, a consuming loop
without renewal, or whole-owner use after the transfer are still rejected.

Also, hosted: a fresh `bytes as string | none` now moves into its optional
local instead of being copied, which leaked the decoded string (hosted
only). The decode-and-return pattern joins `native_argument_temporaries`.

New tests: `test_lifecycle_conditional_components.py` (six runtime cases,
three rejections, the `lifecycle_conditional_components` kernel, and the
native comparison). The kernel checks that every handle is dropped exactly
once.

Validation:
- Gate: 4,758 passed.
- A 3-generation bootstrap from `phase1-x` gives identical generations
  (`phase1-y`), and `check_native` passes on that pair.

## `push` is the only set insertion (2026-09-26)

David: insertion is only `push`; no compatibility aliases like `add`
(ROADMAP 1.4 item 8). Both checkers now reject `s.add(x)`: "a set has no
member `add`" points to `push`, and a dictionary or set otherwise lists its
members instead of its internal record fields. The HIR insertion operation
keeps its internal name. 439 uses in the compiler, library, fixtures and
programs, 23 in Dewy sources embedded in Python tests, and the learn book's
set example now use `push`. Module functions and record methods that happen
to be named `add` (`ranges.add`, `dense.add`, `effect_rows.add`, `o.add`)
are unaffected. The name-based mutating-method lists no longer include `add`.
`tools/generate_native_cache.py` emits `push` for set decoding, and the HIR
display prints set insertion as `.push(`.

Validation:
- Gate: 4,758 passed, plus 1 failure: the codec-currency check, before
  the generator fix. With the fix it passes, together with the display
  tests.
- A 3-generation bootstrap from `phase1-y` gives identical generations
  (`phase1-z`), and `check_native` passes on that pair.

## Value equality of arrays and records (2026-09-27)

David decided that `=?` is always an element-wise/field-wise comparison,
never of handles. Before this, native compared handles (`a =? a` true,
equal copies false), and hosted answered differently again.

Both backends now lower `=?`/`not =?` on arrays, records and record unions
to one generated helper per compared layout (`value_equal_*`):
- arrays: equal lengths, then elements pairwise;
- records: the brand first (a family record compares its own concrete
  type's fields), then each field;
- union cells: the tag, then the active payload;
- strings: the existing byte helper;
- anything else: word equality.

Nested aggregates recurse through their own helpers. Record unions treat
zero as `none`. Hosted keeps an exact-length local's elements in the frame,
so its array helper takes a data pointer and a length per side. Both
checkers accept arrays with the same element type whatever their static
lengths (a different length is simply unequal), so `[1 2 3] =? [1 2]` is
`false` rather than a type error. Dictionaries and sets inside a compared
value are rejected. Their equality stays open.

Call results compared directly are released afterwards (hosted
`_discarded_call_result`, native owned operands).

Found while testing:
- **Native** packed a string literal into a union argument
  (`tagged('q')` for `string?`) but treated the cell as static data, so
  the 16-byte cell leaked. `static_literal` no longer looks through a
  packing cast. The case joins `native_argument_temporaries`.
- `xs =? []` is rejected by both compilers: an empty literal has no element
  type to infer from the other operand.

New fixture `value_equality` (pair check 62 and hosted x86-64/C tests):
arrays, records, families, optionals, string and nested arrays, mixed
unions. It requires unchanged live memory on a second run.

Self-hosting is unaffected: the native compiler built with the new
semantics reaches a fixed point (generations 3 and 4 identical), and the
self-build stays at about 48 s.

Validation:
- Gate: 4,761 passed.
- A 3-generation bootstrap from `phase1-z` gives identical generations
  (`phase1-a2`), and `check_native` passes on that pair.

Juxtaposition ambiguity was also measured (for the rejected narrowing): 622
`Ambiguous` nodes in a self-build, 0.87 s of checking, about 2% of the
build. Details are in `PHASE1_DESIGN_PROPOSALS.md`.

## Shared strings are not copies (2026-09-27)

David: explicit copies are for copies that actually cost something, and
sharing immutable data is not one. Both compilers therefore stop recording a
string share as a copy (`note_copy`/`_note_copy`). A string still counts
when it is requested with `.copy()` or leaves an `$allocator` block. Hosted
still copies frame-region strings into the arena when they escape. That is a
placement choice, not a copy the program asks for: `dewy analyze` still
reports its runtime-sized cost, but a separate policy exemption keeps
`$explicit_copies` acceptance independent of backend placement. The exemption
also applies recursively to immutable strings in records, fixed arrays and
unions; runtime-length mutable arrays still carry an unbounded copy obligation.
Allocator-boundary copies retain their recursive byte-copy obligation.

The compiler's copy inventory goes from 4,111 to 2,631 sites: 1,534
record, 706 array and 391 cell. The largest reasons are
"may be used again, no proven last-use move" (883) and "stays owned by its
container, nothing borrows it" (810). New parity case
`strict_copy_shared_strings`: shared strings under `$explicit_copies` are
accepted by both compilers (the previous native rejected it).

Review follow-up: the shared-string exemption now follows nested records,
fixed arrays, unions and nominal child fields in both compilers. Separate
memo tables retain the physical byte-copy bound and the shared-string bound;
`CopyNote.policy_exempt` records the policy choice without claiming bounded
physical work. Allocator escapes use the byte-copy rule. Mutable payload
fixtures continue to reject implicit copies and accept explicit remedies.
Hosted copy/report tests, native classification, and a freshly hosted-built
native driver pass the shared-string snapshot and mutable-copy cases (both
x86-64 and C execution). The original pending shared-string changes are now
completed by this slice; the reported site-count reduction is not a timing
measurement.


## Review closure: target contracts and allocator visibility (2026-09-27)

`UBC2` records the target and ABI revision before the operation stream. Both
µDewy readers reject a different target, unknown ABI revision, and old UBC1
streams before replay. Both Dewy emitters propagate the selected target.
The native bootstrap uses source text for generation zero's handoff so an
old seed's untagged stream is never misinterpreted by a new reader. Following
generations exercise the new stream format.

`$allocator(@arena)` now covers the whole following expression in both
parsers, including arithmetic, flow arms and nested directives. It desugars
to the existing scoped block. Both analysis commands report fallback
placement: hosted identifies its unimplemented placement, while native gives
the failed lifetime condition (outer stores, captures or unresolved callees).
No fallback is reported when native proves the request eligible. The escape
inventory now finds the expressed result before trailing void statements;
such a statement must not hide a runtime-sized allocator escape from policy.

Validation so far: all 57 µDewy stream checks passed; shared-string policy
passed 19 hosted/native checks through a fresh hosted-built driver; all nine
hosted allocator checks passed. A complete native compiler rebuilt from these
sources runs the expression fixture on x86-64 and C with result 42, and its
analysis reports exactly the outer-store fallback in the placement fixture.
The two-generation direct bootstrap passed, with byte-identical Dewy and
µDewy generations and the native execution checks passing. Artifacts and
source hashes are in `../dewy-build-artifacts/phase1-review-followup`; the
49/54-second generation times are integration observations, not isolated
performance benchmarks (hosted tests ran concurrently). The paired driver
suite passed all 31 stream/allocator tests, including independently
hosted-built native drivers. All 64 focused parser regressions passed, and
all nine strict-copy acceptance/execution cases agreed with the verified
second-generation native compiler. The trailing-result regression is also
recorded in the phase-1 parity manifest. Scoped raw loans (`$lend`), general owner promotion and
no-allocation warnings remain separate implementation work.


## Allocator scopes with no allocation work (2026-09-27)

Both compilers now warn when the checked body of an allocator scope requires
no allocation. Scope equations reuse the public-effect inventory and solver,
including direct calls, negative callback guarantees and nested scopes.
Warnings run after contract validation and lifecycle materialization; an
unverified annotation is never proof. Logical copies and unresolved behavior
retain their allocation possibility. Arena entry may create region metadata,
so it retains its conservative public effects even when its body warns.

Native whole-program diagnostics are returned separately from cached module
proof decisions. Restoring a checked prelude cannot retain stale scope warnings.
The execution-test driver now renders analysis warnings like the native CLI.

Validation: 45 existing hosted allocation/allocator checks passed, followed by
14 hosted allocator checks with the new regressions. The six focused warning
checks passed using a freshly native-built program driver, including repeated
compilation with a shared prelude. The initial hosted-built driver test used
the old driver fixture that did not render warnings and failed that diagnostic
assertion; the fixture is now corrected. A fresh hosted-built route and full
integration remain to be verified for this checkpoint.


## Conditional custom moves and container fields (2026-09-27)

Per-field liveness now permits conditional transfers of custom-move records,
whole resource arrays and resource union fields through hook-free wrappers.
A custom move's result is saved first; its source's remaining nested resources
are dropped on the consuming path before clearing the component flag. An
untaken path retains ordinary cleanup. Replacing the field restores ownership.
Arrays transfer their complete element ownership; unions select the active arm.
Hooked wrapper and conditional element-route restrictions remain in place.

Both implementations pass the new branch/loop/replacement and active-union
kernels. The custom-move kernel checks cleanup order and retained allocation
bytes over 40 repeated calls. Existing last-use component, field renewal and
conditional ownership tests also pass. The combined fresh hosted-built native
suite passed **122 tests**, including both execution backends and allocator
warnings with cold/warm preludes. The direct two-generation bootstrap passed,
with byte-identical Dewy and µDewy binaries and all native execution checks:
`../dewy-build-artifacts/phase1-scopes-and-moves`. This also verifies the fresh
hosted-built warning route left outstanding at the prior checkpoint.

The full 206-case parity run was stopped after 67 passing cases to prioritize
a newly reproduced loop-budget correctness defect (see the next checkpoint).
It is not recorded as a completed parity run. Phase 1 remains in progress.


## Loop convergence is an obligation, not a budget (2026-09-27)

The convergence audit found a correctness defect in both compilers: widening
stopped after eight transfers even when its candidate was still changing,
then used that candidate for proof. A 24-variable shift chain reproduced an
accepted `$assert x0 =? 0` that becomes false on later iterations. Both
compilers now discard the unstable loop-carried facts at budget exhaustion.
Narrowing and final validation start from a safe unknown state, never from an
unverified invariant. This may reject a proof requiring more precision; it
cannot silently certify an unfinished analysis.

A separate hosted defect omitted evaluation of a while condition during
widening and narrowing. Writes made by the condition therefore failed to
propagate through later loop iterations. Condition evaluation now participates
in every transfer, as it already did in the native analyzer. A three-variable
regression distinguishes this defect from the iteration budget.

Validation so far: 46 hosted loop/qualifier regressions passed; three paired
native driver groups passed, including ordinary while loops, single/multiple
iterators, condition effects, negative proofs and runtime behavior. Four
manifest regressions require the specific assertion diagnostic. The updated
native generation has passed its execution checks; fixed-point and full
parity verification are in progress. No performance claim is made from
these concurrent runs.


## Interpolation snapshots and cleanup (2026-09-27)

The proof-convergence checkpoint closed a two-generation native fixed point.
Its full parity run passed 209/210 cases, exposing a hosted interpolation
snapshot defect: a later expression could replace a previously read field
before its bytes were copied. Borrow planning now records only conflicting
parts, preserving the evidence through callable rewriting and concatenation
normalization. Stable field reads keep borrowing.

The lifetime regression also exposed two cleanup gaps. Hosted string flow
results now establish the same ownership convention in every arm, and their
temporary consumers release them. Native interpolation retains evaluated
pieces in a cleanup frame, so an early return from a later field releases
previous pieces too. Repeated normal/early paths have zero retained bytes.
Validation: ten focused hosted comparison/interpolation tests and 34 broader
hosted string/ownership tests passed; four native-built driver groups passed
on both execution backends (including scoped-read tests being developed in
parallel). Fresh hosted-built driver and fixed-point verification continue
at the next checkpoint. Phase 1 remains open.


## Checked read-only storage loans (2026-09-27)

Both compilers accept the approved `$lend(bytes) { ... }` form for named byte
arrays. A finite provenance analysis tracks addresses through scalar locals,
assignments and loop backedges; escaping results, enclosing stores, captures,
owner mutations and unmodeled callees are rejected. Raw loads and the modeled
synchronous write syscall are permitted. Only validated address extractions
receive the nonescaping marker; other raw operations keep their existing
exposure semantics. Native builtin identities are checked through the binding
registry, not just their spelling. The native HIR cache format is version 8.
Hosted fixed arrays return their existing data address, while descriptor-based
arrays load the data field; neither checked path pins the buffer.

Validation: 15 hosted acceptance/rejection tests passed, and the native-built
driver passed the corresponding paired cases on x86-64 and C. The repeated
read kernel retains zero bytes and preserves later independent mutation.
A three-generation native build passed its execution checks and produced
byte-identical final Dewy/µDewy generations at
`../dewy-build-artifacts/phase1-scoped-reads`. The final two builds took 50/53
seconds alongside other tests; these are not isolated performance measurements.
The fresh hosted-built driver check passed all 21 tests. Library adoption,
writable reservations/length commits and bulk reads remain next; the read-only
subset does not close the storage item or Phase 1.


## Scoped output consumers (2026-09-27)

Stdout, stderr and file writes use checked read loans on the supported
x86-64/C route. Other targets retain their existing implementation until
their syscall lifetime models are available. The permission now includes
validated synchronous consumers and loads, not just address extraction.
Otherwise the native ambient graph conservatively retained the caller's
snapshot despite the callee's checked loan.

Native snapshot reclamation also uses the particular parameter's lifetime:
a nonescaping, uncaptured, unexposed parameter cannot retain its caller's
private snapshot merely because the function opens/closes a file or performs
an unrelated raw operation. Ambient writes still block borrowing; this is
cleanup evidence, not a new aliasing exemption. Five native-built paired
loan/allocation/projection groups passed (both execution backends), including
repeated stdout/stderr/file writes with zero retained bytes. Additional
ambient-graph regressions and the next full parity checkpoint are pending.


## Writable storage loans and checked commits (2026-09-27)

Both compilers now implement `$lend(@bytes reserve=n)` for named growable
arrays of unrestricted bytes. Entry evaluates the extra reservation once,
captures the length bound, detaches shared snapshots and invalidates element
facts. The existing reserve operation supplies storage. `set_length` inside
the loan owes ordinary nonnegative and reservation-bound obligations; there
is no implicit trap. The checked body permits byte stores and synchronous
x86-64/C reads, rejects escaping addresses/aliases/owner mutation, and keeps
normal cleanup on every exit. This checks lifetime and commit bounds, not
the correctness of arbitrary raw pointer arithmetic.

The bound uses finite sum relations already supported by the proof state.
New sum evidence requires stable operands and a nonwrapping result; writes
invalidate its identities. Transparent proof obligations retain scalar-copy
equality, while casts do not gain that exemption. Tests cover partial and
keyword commits, COW independence, one-time reservation evaluation, stale
facts, invalid length commits and repeated zero-retained-byte operation.
All 23 focused hosted tests, four native-built paired groups (both execution
backends), and 35 surrounding proof/loop/affine tests passed.

The preceding output checkpoint passed all 215 parity cases and a native
three-generation fixed point in the isolated `phase1-output-integration`
build. Six ambient-analysis regressions also passed. The manifest now has
217 cases. Bulk file-read adoption and a new integration checkpoint follow;
this does not close Phase 1.


## Bulk file reads into scoped storage (2026-09-27)

The x86-64/C `_read_bytes_at` path now reads chunks directly into reserved
private array storage and commits only the returned initialized length. It
retains the fstat reservation, short-read loop and existing error values.
Other targets retain the previous byte-push route. No per-byte load/push
loop remains on the supported bulk path.

Hosted and native-built tests execute on both backends, check every byte
across multiple chunks and a short tail, preserve independent snapshots,
handle empty/missing/directory inputs and retain zero bytes after repeated
reads. Native fixed-point and broad integration checks follow this checkpoint.


## Conditional ownership of literal array slots (2026-09-27)

Ownership liveness now uses stable field and literal-index paths. The same
conditional component flags govern nested record/array cleanup, custom move
remainders and slot replacement. Reading an array's length keeps its storage
alive without treating every element as read; consuming the whole array
still conflicts with that observation. Dynamic selectors remain conservative.
A replacement retires old extraction metadata and restores the new component.

Eleven focused hosted checks passed, including nested arrays, array fields,
branch choices, repeated custom moves/replacement with zero retained bytes,
and rejection of future overlapping uses. The native-built driver passed the
paired element and existing component groups on x86-64/C; additional opposite-
branch and whole-owner length-use checks passed separately. Sixty-seven
surrounding hosted ownership checks also passed. This closes the literal-slot
case, not general dynamic disjointness or the complete ownership item.

The bulk-read checkpoint also passed its three-generation native fixed point
and execution checks (`phase1-bulk-integration`). All 217 parity cases passed against that isolated checkpoint. The broad
hosted run passed 4,113 tests (13 skipped) and exposed one decoded-string
lifetime failure, corrected at the next checkpoint.


## Decoded strings escaping through aggregates (2026-09-27)

Hosted string placement now follows returned aggregate payloads as well as
direct string returns. Region-backed decoded payloads are copied into owning
cells; arena-backed payloads can transfer. Retagging a fresh decoded optional
releases its original payload after copying, including when the two signatures
use different equivalent string spellings. This fixes the broad-suite crash
and the related leak exposed by repeated implicit/record returns.

Twenty-three focused checks passed, including the formerly failing test and
a paired hosted/native fixture on both execution backends. The fixture checks
explicit, named-local, implicit and record returns, outer-field assignment,
subsequent string operations and zero retained bytes over repeated calls. The
native implementation already passes these cases and needs no corresponding
change. The parity manifest now includes this regression.


## Generic rows with explicit place permissions (2026-09-27)

David approved keeping callback-local place permissions explicit in each
signature, with `E` carrying the remaining nonlocal effects. The call rule
translates those permissions normally, including reordered parameters and
field routes. Positive place effects cannot escape into `E`. Callback-local
exclusions are omitted from that remainder rather than rejecting otherwise
valid inference; explicit exclusions still apply at the callback boundary.

Thirty focused checks passed using a native-built driver, including paired
execution/rejection tests on both backends. Tests cover unrelated wrapper
slots, incorrect translated permissions, nominal remainders and exclusions.
More general place-bearing generic rows remain a separately reviewed design;
they are outside this approved Phase 1 subset.


## Resource array sorting (2026-09-27)

Sort now permutes existing resource owners and supplies each owning key
callback with a checked independent copy. A noncapturing internal adapter
keeps logical copy hooks, copy-policy notes and public/ambient effects in
ordinary HIR. It does not introduce source callback or closure syntax.
The receiver lifetime check includes the adapter's effects even when the
source key promises purity. Move-only elements still reject when the key
requires an independent owner.

Both lowerers release the caller-side key snapshot after each invocation;
the source key performs logical drop of its private argument. Hosted
statement temporaries now use the per-iteration boundary rather than waiting
until the sort ends. The native prelude cache format is version 9 because
ArrayMethod now carries the optional internal adapter.

Eight focused checks passed, including the native-built paired group on
x86-64/C, exact copy/drop counts, reverse order, a 40-element sort, zero
retained bytes and rejection of hidden effects/receiver mutation/forbidden
copies. The three paired resource/effect/lifetime groups passed together;
26 surrounding hosted sort checks also passed. Full integration follows.


## Resource-sort integration and hosted escape correction (2026-09-27)

The resource-sort checkpoint (`4b24b067`) passed a three-generation native
fixed point and execution checks at `../dewy-build-artifacts/phase1-resource-sort-integration`.
All 221 paired manifest cases passed against that isolated source checkout.
The broad hosted suite passed 4,133 tests (13 skipped) and found four failures:
three aggregate-return lifetime kernels and one obsolete row-inference test.

The decoded-string correction had unnecessarily marked every returned
aggregate child as escaping, including temporary numeric-formatting buffers.
Owning aggregate writes already acquire their payloads; keep their child
formatting buffers scoped and apply the explicit region/arena distinction at
the decoded optional transfer. The crash and repeated optional-return fixture
still pass, and the three aggregate lifetime kernels no longer retain bytes.
The row test now checks that callback-local exclusions are dropped from `E`
and cannot establish a wrapper guarantee, matching the approved boundary.
All 66 focused aggregate/string/effect checks passed after these corrections.


## Required views of resource projections (2026-09-27)

`const item=@items[i]` and required field/dictionary-entry views now borrow
the existing resource owner without adding a second cleanup. Alias dependencies
keep the owner live through derived names; a view is never eligible as an
independent owner for transfer. The existing lowering proof still checks
physical storage stability and escaping/captured storage. Array writes that
may detach storage remain conservative, including sibling slots.

Logical mutation conflicts also run in ownership liveness before reachability.
This prevents an unused resource function from hiding a clear/replacement
through a live view. The backwards branch/loop analysis checks live aliases
and translated call writes, preserving field prefixes above indexed storage.
This covers resource ownership contracts; general required-view validation
for ordinary values before native reachability remains to be audited.

Twenty-one focused hosted/native checks passed on both backends, including
dynamic indices, dictionary views, chained aliases, repeated zero-retained-
byte loops, rejection of consumed/replaced owners and unused-function errors.
Thirty-nine adjacent hosted view/conditional/renewal checks passed before the
source-contract extension; its 24-case focused subset passed afterward. The
manifest now has 222 cases. Broader integration follows the next batch.


## Copy-policy adoption and inventory scope (2026-09-27)

`semantic/source_lines.dewy`, `text_shapes.dewy` and `target_values.dewy`
now opt into `$explicit_copies`. Each passed hosted standalone lowering and
the native-built compiler driver with the policy enabled. No compensating
`.copy()` calls were added. Compiler-source adoption remains incomplete.

A full-main inventory using the bulk-integration native seed reported 2,583
static sites (1,531 record, 658 array, 394 cell) over 52,644 physical bootstrap
source lines: 49.065/KLOC. The hosted inventory reported 5,625 sites, including
1,766 string placement copies exempt from the source policy. These are static
reports for the reachable main program, not allocation counts or a certificate
of every function in every imported file. In particular parser CLI functions
unused by the compiler require separate standalone checks.

Those checks exposed two remaining cases, so the parser wrappers have not
been marked strict: constructing a Report from its by-value pointer array
requires an owning field copy, and native `read_input(argv)` still falls back
to a copy because unrelated raw I/O blocks the array borrow. Hosted accepts
the latter without a source copy. These are follow-up proof/acceptance work,
not reasons to add explicit copies merely to enable the directive.


## Argument storage independent of unrelated raw work (2026-09-27)

Native array arguments now use the particular parameter's nonescaping,
uncaptured, unexposed lifetime proof even when its callee performs unrelated
raw work. The source still needs independent storage: exposed/global owners,
ambient writes through places/captures, and overlapping later arguments keep
the snapshot. This enables `$explicit_copies` in `parser/parser.dewy` without
adding explicit copies; standalone lowering passed in both compilers.

The paired kernels exposed a hosted correctness gap: forwarding an array
through a place could observe a callee's global mutation. Hosted array call
planning now consults the existing exposure/ambient graph before selecting
representations, and checks later argument evaluation too. Fixed versus
growable storage no longer determines borrow safety; the actual representation
still selects the descriptor adapter. Two duplicate classification helpers
were removed. A grown local array now passes strict mode with zero allocation
across repeated read-only calls.

Nine focused hosted cases and their paired native group passed on both
execution backends, including exposed aliases, ambient place writes, later
argument writes and private-copy cleanup. The copy/clear kernel warms the
source's persistent COW control block before checking per-call retention.
The surrounding sharing/field-call/effects/review batch passed 39 tests; the
final later-argument extension passed the focused group afterward. A fresh
hosted-built route and fixed-point check remain for this batch. The manifest
now has 223 cases. Phase 1 remains open.


## Required-view contracts before reachability (2026-09-27)

Native graph assembly now preserves a separate proof graph containing unused
functions with explicit views and their dependencies. Runtime emission still
uses the original reachable graph. The borrow plan and representation predicate
are shared with lowering; this checks source demands without emitting unused
functions or analyzing every unused library function for storage. Imported
source locations survive into the conflict diagnostic.

Hosted imported-function pruning had the same gap. Assembly now validates
those otherwise discarded demands using the existing borrow analyzer and the
same extracted predicate/report used by lowering. It skips that extra analysis
when all demands already reach normal lowering. No second definition of view
safety or new source syntax was introduced.

Forty-eight focused hosted view/last-use/place checks and four native-built
paired groups passed on both execution backends, including ordinary/resource
projections, unused/imported failures, mutation through helpers, derived aliases,
raw exposure and writes after the last view use. Native regression execution
preserves the source-module filename and conflicting write in diagnostics.
The earlier full-graph prototype passed its main source-contract group but
found the hosted imported-function gap; it was narrowed before this checkpoint
to avoid pulling all unused library bodies into the storage analysis.
Fresh hosted-built and fixed-point integration follow this batch.


## Array-boundary integration follow-up (2026-09-27)

The broad hosted run at the argument-borrow checkpoint completed with 4,163
passes and 14 failures. Eleven focused representation queries exposed a setup
dependency introduced by the refactor: array classification now builds its
borrow plan itself, after discovery. Three code-shape checks caught avoidable
copies of globals and a selected overload mistaken for raw exposure. Global
arguments may borrow when the callee has no ambient writes; places and captures
keep the same condition. Hosted exposure analysis now consumes already resolved
ordinary value calls, including overload selections, instead of guessing from
the callee's spelling. Native global borrowing uses the corresponding rule.

The surrounding regression batch passed 335 tests and left one overload-shape
assertion, then all 72 targeted checks passed after its correction. None of
the original failing assertions was relaxed. The paired argument group passes
on both backends, including zero-allocation global/overload reads and the
required snapshots across ambient/raw writes. The nonlocal-root inventory is
built once per analysis, not once per argument.

The preceding view-contract checkpoint (`7fe7854d`) closed a three-generation
native fixed point with execution checks at
`../dewy-build-artifacts/phase1-view-contract-integration`. Its fresh hosted-built
native-driver suite passed all 60 selected view/resource/effect/argument checks.
All 223 parity cases passed against that isolated snapshot. The newest global/overload corrections
remain covered by the focused batch pending the next integration checkpoint.


## Five more compiler modules under copy policy (2026-09-27)

`invocation/options.dewy`, `invocation/platform.dewy`, `semantic/lifecycle.dewy`,
`semantic/prelude.dewy` and `main.dewy` now enable `$explicit_copies`. All five
passed standalone hosted and native-built lowering, including the real compiler
entry graph. No `.copy()` calls were added to satisfy the directive. This checks
each marked physical module; the entry directive does not silently opt all of
its imports into the policy. Adoption across the remaining compiler modules
is still required.


## Borrow tagged getter results from stable owners (2026-09-27)

The native getter projection now lends tagged cells as well as records. It
requires an existing stored representation, a known capture-free getter with
one terminal parameter route, and a stable caller owner. Forwarding getters
retain that route; dependent locals extend the backing owner's lifetime.
Retagging that needs a new cell stays on the owning path. Full getter prefixes,
including guards and side effects, still execute. Ordinary escaping boundaries
still acquire independent values.

The tagged-read kernel allocates zero bytes across 100 native reads. Hosted
lowering retains its safe copying path (9,600 bytes for the same kernel); both
retain zero bytes after the warmed measurement. Seventy surrounding checks
passed, including paired native execution on x86-64/C, mutation/snapshot cases,
owner donation with a live view, escaping returns, empty alternatives, effectful
prefixes and a failing runtime guard. The preceding nine focused checks also
passed. This is a native storage optimization, not a new source-level borrowing
contract or a claim of complete hosted placement parity.


## Borrow join inputs and preserve separator evaluation order (2026-09-27)

Native string-array joins no longer acquire an independent input unconditionally.
They borrow for the duration of the read, retaining and releasing a fresh
receiver when necessary. Both borrow analyzers now use their existing later-
operand conflict proof for separators, including globals reached through place
parameters. A conflicting separator gets a snapshot before evaluation. This
also fixes a hosted value-semantics bug: clearing/repopulating the receiver in
the separator previously changed `['a' 'b'].join(...)` into `new-b`.

The snapshot is reported with its reason and obeys `$explicit_copies` for
runtime-length inputs. Fixed arrays of shared immutable strings retain the
approved exemption. Thirty-five join/string/lifetime checks passed, including
paired native execution, positional/keyword separators, ambient writes and
repeated temporary/snapshot cleanup. The parity manifest now has 224 cases.
`paths.dewy` and `invocation/cache.dewy` passed standalone lowering with the
policy in both compilers and now enable it without added `.copy()` calls.
The ordinary join test itself enables the directive, gating the eliminated
runtime-array input copy independently of result-string placement.


## Guard-selected finite qualifiers (2026-09-27)

The candidate audit found that while-loop guards did not select difference
pairs, although body predicates did. Both analyzers now merge guard/body
vocabularies under the same deduplicated 64-pair budget, considering the guard
first. Entry intervals still justify each proposed bound, and every advancing
edge must preserve it. No guard fact is assumed for a zero-trip loop.

Forty-seven hosted surrounding checks passed; the subsequent 43-check batch
includes paired native execution and a case with 70 unrelated changing
bindings that exceed the exact-value seed budget. Invalid entry states,
unequal updates, omitted updates on a continue edge and mutation in the guard
remain rejected. The new case is in the 225-case manifest. The source-selected
vocabulary remains intentionally finite; this adds no arbitrary nonlinear or
quantified propositions to the proof language.

The preceding getter/join checkpoint (`00bb38cd`) closed a three-generation
native fixed point with execution/scaling checks at
`../dewy-build-artifacts/phase1-getter-join-integration`. Its independent broad
hosted suite and 224-case parity manifest are still running against that
checkpoint; their eventual results must not be attributed to the newer guard
change without the separate focused evidence above.


## Partial ownership through copy/move-only wrappers (2026-09-27)

Both lifecycle passes now distinguish hooks needed during cleanup from hooks
for whole-value operations. A wrapper with copy/move hooks but no drop hook
can transfer a field and later clean up its remaining fields. Moving that
field does not invoke the wrapper's copy/move operation. A wrapper drop hook
still requires a complete receiver; reading a consumed field remains invalid.
This follows the existing field-transfer rule rather than adding a new hook
protocol or an invocation-count guarantee.

Fifty-two hosted surrounding checks and all four native paired groups passed
on x86-64/C. Coverage includes ordinary/returned field transfers, conditional
consumption and renewal, independent copy-only/move-only wrappers, rejected
post-consumption reads and drop-hook receivers, zero unintended wrapper-hook
calls, and zero retained bytes across 200 conditional invocations. The fixture
is now in the 226-case manifest.

The isolated `00bb38cd` getter/join checkpoint passed all 224 parity cases and
the broad hosted run passed 4,210 tests (1,040.42 seconds). Its refreshed native
compiler-source copy inventory is 2,379 static sites: 1,501 record, 552 array,
326 cell, over 52,812 lines (45.047 sites/KLOC). The previous inventory had
2,583 sites and 49.065 sites/KLOC. These are static counts, not runtime bytes
or an isolated performance measurement. The newer guard and wrapper changes
have the focused validation above pending their next full integration.


## Constant-slot ownership follows checked facts (2026-09-27)

Both resource-liveness passes now use an index's checked constant identity,
not just literal syntax. Named/aliased/arithmetic constants and a call with a
checked constant result can select the same partially owned slot. Canonical
cleanup selectors retain the original evaluation once, and backward liveness
visits selector reads and writes separately. Reads within the selector happen
before the selected component transfers; other call operands retain the
existing conservative donation rule. Dynamic unknown indices still need a
whole-owner last use or an independent copy.

Seventy-two hosted ownership checks and all six native paired groups passed
on x86-64/C, including nested slots, conditional consumption/renewal and
custom component moves. Regressions preserve side-effecting selectors, reject
reads of consumed slots (including inside later read/store selectors), and
reject selectors that invalidate the receiver. An additional paired lifetime
kernel retains zero bytes across 200 conditional invocations and observes the
expected 101 selector calls. It is included in the 227-case manifest. This
extends the existing constant-slot rule; general runtime index identities and
conditional dynamic-slot ownership remain separate work.


## Copy-policy adoption in signatures and debug formatting (2026-09-27)

`semantic/array_methods.dewy` and `backend/udewy/debug.dewy` now enable
`$explicit_copies` after standalone hosted and native-built lowering passed
with the directive. No implementation changes or `.copy()` annotations were
needed. Four other probed modules still failed hosted proofs and remain
unmarked: update invocation, container values, binary literals and syntax.
In particular, a zero count in the reachable compiler inventory does not
certify standalone/otherwise-unused function bodies. Compiler-source adoption
now covers 20 physical modules and remains incomplete.


## Entry snapshots: reporting, explicit copies and temporary cleanup (2026-09-27)

Both lowerers now report `.keys` / `.values` materialization as one
source-level copy. Applying `.copy()` explicitly authorizes that snapshot
without materializing a second one. Ordinary property snapshots retain their
independence, while stable iteration continues to use the shared borrowing
proof. This closes a reporting hole in values snapshots and the native keys
path; hosted keys previously reported their synthetic bookkeeping stores
instead of the source operation.

Hosted keys snapshots now build their owned storage directly and participate
in frame-record temporary cleanup. Discarded snapshots, direct call arguments,
and direct returns previously retained their entry arrays; the new counter
fixture retains zero bytes across 100 calls. Validation: 13 focused hosted
checks, the paired snapshot and iteration groups on x86-64/C, and 48 surrounding
hosted dictionary/lifecycle/copy-policy checks pass. Full compiler integration
remains a separate checkpoint.


## Strict-copy adoption: namespace and type dispatch helpers (2026-09-27)

`semantic/namespaces.dewy`, `semantic/type_names.dewy` and
`semantic/container_methods.dewy` were tested with `$explicit_copies`. Each passed
standalone lowering through both the hosted compiler and the native program
driver; no copy annotations or algorithm changes were needed. Standalone probes initially suggested adoption of these modules; the full
compiler subsequently rejected the imported namespace return. The directives
are withdrawn pending full-graph acceptance, so adoption remains 25 physical
modules. Standalone success alone is insufficient. Nine other small-module probes remain unmarked: their
failures include independently mutated parameter copies, borrowed payloads
stored into containers, and projected arrays assigned through branch joins.
Those need deliberate copy boundaries or shared ownership proofs, not a
blanket policy exemption.

The entry-snapshot integration also caught a missed temporary-helper rename
in hosted union construction. The caller is corrected, and the counter fixture
now includes an optional key-set result; paired x86-64/C execution retains
zero bytes.


## Integration and fixed-array replacement storage (2026-09-27)

At `70da28c6`, three native generations reached an identical fixed point,
a fresh hosted-built driver passed all 24 entry-snapshot/iteration/array-move
checks, and all 239 paired manifest cases passed. The copy inventory reports
2,404 sites across 52,900 physical lines (45.444/KLOC), within the unchanged
3,000/60 budget. The additional reported snapshot sites close diagnostic gaps;
this count is not a timing improvement. Generation 2/3 builds each took 54 s
under concurrent checking, not isolated benchmark timings.

A subsequent conditional-resource test exposed an existing hosted replacement
bug, also reproducible with constant indices: fixed-array assignment inside
a loop reused frame storage still owned by the prior replacement. Releasing
the old value could therefore invalidate the new one. Descriptor-backed
replacements now receive lasting independent storage before the old value is
released, just like runtime-length replacements. The paired fixed-array
regression retains zero bytes across 100 calls; 60 hosted allocation/frame
checks pass. Dynamic resource selection is a separate in-progress change.


## Conditional runtime-selected resource transfers (2026-09-27)

Both ownership passes now admit a conditional transfer from a runtime-selected
array route when the complete owner has no later use on that path. The same
backward liveness proof rejects retained views, later reads and unreplenished
loop backedges. Captured selectors and a presence flag record the executed
route; cleanup omits that component and drops the remaining elements in their
normal reverse order at the original lexical boundary. Whole-owner replacement
cleans its remaining components and resets those flags. Custom move hooks clean
the selected old component on the consuming edge, as for constant slots.
Runtime route metadata is indexed by owner rather than scanning every function's
transfers at each cleanup site.

Validation: 12 focused hosted checks, three paired dynamic/constant/conditional
slot groups on x86-64/C, and 54 surrounding hosted ownership checks pass.
Coverage includes mutually exclusive selectors, selector evaluation once,
selector-variable reassignment, owning parameters, replenished loops, nested
routes, custom moves, and zero retained bytes over 100 conditional calls.
This does not prove arbitrary runtime indices disjoint or permit later reads
of another slot without evidence. A nested array with unknown inner extent
still needs a bounds proof the current indexed-length facts cannot always
express; the nested cleanup regression uses a declared fixed inner extent to
test ownership independently of that remaining proof-engine gap.


## Numeric facts for mutable index selectors (2026-09-27)

Both numeric analyzers now identify array routes selected by a named runtime
parameter or local. Guards on nested lengths and scalar element values carry
through subsequent reads of the same selection. Selector assignment, compound
updates, mutating place calls, local mutable aliases and loop advancement
invalidate dependent route facts before carrying forward affine relationships.
Ordinary source-level type narrowing retains its const-selector rule; creating
an identity for numeric analysis does not promise a persistent narrowed type.

Nested range endpoints exposed a separate ambiguity-handling gap. Hosted
runtime-range normalization now factors only a common range prefix and leaves
the endpoint to ordinary type-directed checking. Native bracketed ranges
likewise resolve ambiguous range readings before attaching their bounds.
`loop column in [0..rows[row].length)` now checks directly. The conditional
resource regression also uses an unknown inner extent rather than a fixed-size
workaround.

The preceding `a702b875` integration reached a three-generation native fixed
point, passed all 241 paired manifest cases, and passed 24 checks with a freshly
hosted-built native driver (320.40 seconds including its build). The selector
change has its own focused checks: 90 surrounding hosted checks and three
paired selector/const-route/scalar groups passed on x86-64/C. New paired cases
include nested loops, element nonzero facts, writes through aliases, changed
selectors after container snapshots, and conditional resource cleanup. The
manifest now has 243 cases; its full run remains a separate integration gate.


## Hosted region-aware storage ownership (2026-09-27)

Before enabling hosted scoped placement, three prerequisite regressions were
reproduced using the allocator runtime directly: copying region-backed arrays
could retain their data after reset; growth could put a heap array's new buffer
in the caller's region; and detaching a nested shared array could publish region
storage through its heap owner. All three now preserve the owning lifetime.

Hosted array/string sharing checks backing-storage eligibility and allocates
reference counts beside the retained buffers. Growth uses the existing
owner-directed allocator. Recursive COW detachment temporarily selects the
owner's context, including private child descriptors, then restores the calling
context. The internal `_allocator_enter_for` helper extends runtime machinery,
not language syntax or allocation contracts. Required helpers survive hosted
prelude pruning. Native lowering already preserves these tested lifetimes.

Five hosted ownership checks and the paired initial four cases pass on x86-64/C;
a repeated nested mutation/reset kernel retains zero bytes over 100 calls.
Twenty-five surrounding hosted allocator/replacement/snapshot checks also pass.
The kernel is in the 244-case manifest. Actual hosted `$allocator` block
placement remains separate work; this fixes its storage prerequisites without
claiming the existing placement fallback is gone.


## Projected string membership parity (2026-09-28)

The `fea499c5` native pair reached a three-generation fixed point (generations
2/3 took 52/53 s under concurrent work), but its fresh hosted-driver build found
a checker parity gap in the new range code. A string field's literal-union
membership fact was recorded yet ignored by the hosted read path, which only
consumed record/union facts. String fields now consume those facts too. Native
field reads already did; its indexed array/dictionary reads now use the same
rule. Writes still check the declared storage type and invalidate read facts.
This fixes the underlying projection rule rather than adding a temporary
variable to work around the range constructor's failed proof.

Focused tests cover assertions, early-return guards, array and dictionary
selections, optional literal-union results, independent place arguments,
replacement with another string and rejection after direct/call mutations.
The fixture raises the parity manifest to 245 cases. The earlier hosted-driver
failure remains an integration gate until a fresh build with this fix passes.
Validation for the projection fix: 46 surrounding hosted checks and the paired
field/index/dictionary group pass on x86-64/C, including both stale-fact
rejections. The native program driver was rebuilt with the native index change.


## Hosted scalar/void allocator scope placement (2026-09-28)

The hosted lowerer now enters the requested allocator for proved scalar/void
blocks and restores it after their normal fallthrough. Placement checks direct
and transitive publication of owned storage, outer destinations, callbacks and
captured storage. Unknown lifetimes keep the enclosing allocator with a specific
fallback reason. Normal nested scopes and scalar writes to outer arrays use the
region-aware storage primitives above. Source escape diagnostics and strict-copy
acceptance remain independent of this placement decision.

This is a bounded placement step: aggregate block results and scopes containing
control-flow exits still use the enclosing allocator. Their copy-out and lexical
cleanup must be coordinated before broadening placement. No new allocator
syntax or failure policy is introduced.

Validation: 27 surrounding hosted allocator/storage/frame checks, two lifetime
fallback cases, and the paired scalar-placement fixture pass on x86-64/C. The
fixture checks actual region handles, nested restoration, owned global-store
fallback and outer-array growth/detachment surviving reset. It is in the
246-case manifest. The blanket hosted-fallback expectation now correctly reports
only the unsupported block in the original allocator fixture.


## Dynamic transfers preserve unrelated siblings (2026-09-28)

Both ownership analyses now preserve the stable prefix before an unknown array
selector. Transferring `owner.items[index]` requires the containing array to be
dead, while unrelated fields such as `owner.sibling` remain readable and
replaceable. Saved runtime selectors still identify precisely the element to
omit from cleanup; the prefix is liveness evidence, not the cleanup route.

Cleanup currently admits at most one dynamic transfer per owner on an executed
path. Mutually exclusive alternatives work; simultaneous transfers and partial
replacement of the containing array remain rejected until their cleanup and
flag-renewal protocols are generalized. Whole-owner rebinding retains its
existing renewal protocol. These restrictions prevent double cleanup rather
than silently accepting an unsupported ownership shape.

Validation: 20 hosted dynamic-transfer checks, 36 surrounding partial-hook,
conditional, disjoint-field and replacement checks, and both paired dynamic
groups pass. Cases include nested constant outer selections, sibling replacement,
container mutation rejection and simultaneous-transfer rejection. A repeated
kernel retains zero bytes on both backends; it is in the 247-case manifest.

The preceding `734a479f` checkpoint's fresh hosted-built native driver passed
all 32 focused selector, allocator-storage and projected-string checks (299.04 s
including its build). `ef2fa9d0` reached a three-generation native fixed point;
its broad hosted and 246-case parity runs are still in progress.


Integration at `ef2fa9d0`: all 246 paired manifest cases passed, in addition to
the three-generation fixed point above. The broad hosted selection completed
with 4,333 passes, 13 skips and one brittle generated-code assertion: it assumed
the main function's eager temporaries always had suffixes 1 and 2. Added prelude
helpers legitimately use earlier suffixes. The test now checks the ordered calls
and exact reuse of their captured operands without depending on global temporary
numbering; all 32 control-flow checks pass with that correction. No compiler
semantics changed to accommodate the assertion.


## Independent cleanup for disjoint dynamic transfers (2026-09-28)

The next ownership step removes the previous one-dynamic-transfer-per-owner
restriction for proved disjoint containing arrays. Each saved route now carries
its own presence predicate down the cleanup tree. Array traversal adds selector
mismatches to that predicate, so a transferred element is skipped only at its
actual saved path. Independent fields can therefore transfer simultaneously;
possibly overlapping selections within the same array remain conservative.

Nested cleanup helpers capture both selectors and presence conditions as checked
scalar arguments. This also preserves static partial-transfer flags through
nested array helpers. Cleanup walks each structural portion with its relevant
conditions instead of selecting among whole-owner cleanup copies. Partial
replacement of a dynamically consumed array still needs flag renewal and remains
unsupported; whole-owner rebinding keeps its existing protocol.

Validation: 62 hosted surrounding ownership checks, three paired dynamic groups,
and an additional mixed static/dynamic nested-array check pass on x86-64/C.
Cases cover all four combinations of independent branches, nested arrays,
constant outer elements, sibling transfers, changed selectors and overlapping
route rejection. The new nested repeated-call fixture retains zero bytes and is
included in the 248-case manifest. The preceding full 246-case checkpoint remains
the integration baseline until this extension completes its fresh build gates.


Hosted placement follow-up (2026-09-28): local `break`/`continue` edges whose
target loops remain inside an allocator block no longer force heap fallback.
Scope analysis checks actual loop depth; returns and edges leaving the allocator
scope still retain the documented conservative fallback. Two hosted cases and
the paired placement case pass, including context restoration and continued
fallback for a nonlocal exit. This fixture brings the manifest to 249 cases.


## Constructor arguments retain caller bindings (2026-09-28)

The disequality-fact implementation exposed an existing constructor scope bug:
`Pair[right left]`, in a caller with `left` and `right` parameters, rebound the
second argument to the newly constructed first field. Both checkers now resolve
supplied positional/keyword arguments in the caller's scope, as the reference
already specifies. Defaults and dependent field contracts still resolve earlier
fields from this construction. Explicit callback literals likewise keep caller
bindings; ordinary object-literal methods retain their sibling scope.

Validation: 24 constructor/immutable-record checks, 15 default/lifetime checks,
and seven focused hosted/paired checks pass. Regressions cover swapped arguments,
keywords, default-derived values, callback/global scope and rejection of a value
that meets an outer name's value but violates the constructed sibling contract.
The fixture is in the 250-case manifest. A compiler built by the old checker can
still contain this misresolution in its own newly compiled code; fresh native
generations are required before certifying the pending disequality extension.

The preceding cleanup checkpoint `c72625b0` reached a three-generation fixed
point (generation 3 took 56 s under concurrent checks). Its fresh hosted-built
native driver passed all 30 focused dynamic ownership checks in 332.92 s,
including its build. Phase 1 remains in progress.


## Finite disequality facts (2026-09-28)

The bounds engines now retain a symmetric disequality between current binding
or length identities. `if a not=? b {$assert a not=? b}` no longer needs an
ordering or disjoint numeric intervals to justify its own guard. Reversed
operands share one structural identity, and a non-strict order plus disequality
establishes a strict integer order regardless of guard order. Successful ordinary
bounds checks keep their existing direct path before querying this extra fact.

Joins retain common disequalities; scalar writes, changed selectors, projected
mutation, place calls and length changes invalidate the affected identities.
The domain does not infer an ordering from disequality alone or synthesize all
pairs. Single-expression grouping is transparent to predicate paths, including
negation, while later-write exclusions still apply. Source dependent-disequality
contracts remain separate work; this step adds the established guard fact.

Validation: 67 surrounding hosted proof/loop/key checks, 12 structural-key and
native fact-state/comparison/path driver checks, the paired disequality and
convergence groups, and contradictory unsafe-assumption rejection pass. New
cases cover fields, indexed selections, lengths, branch joins, loops, mutation,
place calls and reversed operands. The positive and stale-fact fixtures bring
the manifest to 252 cases. Native validation used a driver rebuilt by the
constructor-corrected compiler; the earlier miscompiled factory was not accepted
as evidence. The new factory keeps ordinary source spelling.

Constructor checkpoint `e6d355a1` reached another three-generation fixed point
(generations 2/3: 51/55 s under concurrent checks). Its fresh hosted-built driver
passed 10 constructor and scoped-placement checks in 266.80 s including build.
The full 250-case parity run is in progress.


## Dependent disequality contracts (2026-09-28)

The existing named-bound contract syntax now accepts `not=?` in both checkers.
Its obligations and transfers use the same symmetric finite fact as guards,
without choosing an order or synthesizing unrelated term pairs. Coverage includes
scalar/length parameters, result promises, boolean predicate arms, direct checked
proof calls and immutable sibling-field contracts. Saving a scalar or length
carries the observed disequalities into the new binding; changing the source
invalidates only facts that still mention that source. A length copied into a
scalar supplies ordinary order bounds, never an invented array identity.

A dependent exclusion is not a literal zero exclusion: `b not=? a` does not
justify `b not=? 0`. Postconditions likewise cannot refer back to a by-value
argument's current source if the invocation changed that source. Both have
negative regressions. Unsupported expressions still leave obligations unknown.

Validation: 136 surrounding hosted contract/proof tests passed, followed by 55
focused contract/index/key checks and 22 final contract cases. The paired
contract and guard groups passed on x86-64/C; the final length-snapshot and
sibling-length cases also passed against the rebuilt native driver. Positive
result-contract and stale-argument fixtures bring the manifest to 254 cases.
This is focused evidence; the new checkpoint still needs fresh-build integration.

The preceding constructor checkpoint `e6d355a1` completed all 250 manifest
cases. Its copy inventory is 2,417 sites across 53,081 lines (45.534/KLOC), below
both unchanged gates of 3,000 sites and 60/KLOC. Phase 1 remains incomplete.


## Direct owning record parameters (2026-09-28)

Direct, nonescaping mutable record parameters can now use the existing owning
argument protocol in both lowerers. Fresh arguments transfer once; proved last-use
locals transfer their owned fields; live sources supply one independent copy.
The callee releases its fields on normal/early exits and replacement, without a
second entry copy. First-class callbacks, captured/exposed parameters, defaults
and lifecycle-bearing records retain the ordinary boundary. Native reuses the
aggregate cleanup protocol; hosted keeps the root in the caller frame and shares
the existing record-field transfer used for array element stores.

Owning arguments participate in the same last-use traversal as other storage
boundaries. Transfers inside a return expression are candidates only after
checking all its later operand reads and live borrowers. Repeated loop uses,
live views and a later argument reading the source prevent early donation.
This is an internal calling convention, not a new source ownership operation.

Validation: 23 focused hosted checks and 70 surrounding record/array/callback
checks passed. Three paired groups passed on x86-64/C. The repeated-call kernel
keeps zero retained bytes over 100 calls; native takes the descriptor, while
hosted still spends one 64-byte descriptor transfer. Its budget has a positive
control that exceeds the bound when record transfer is disabled. The fixture
brings the parity manifest to 255 cases. Fresh complete-build integration remains
required before certifying this new convention on compiler sources.

The preceding disequality checkpoint `ee5a3fc0` reached a three-generation native
fixed point (generation 3: 55 s under concurrent checks). Its fresh hosted-built
driver passed all 43 focused contract/guard checks in 329.18 s including build.


## Mixed disequality evidence at joins (2026-09-28)

Joins now preserve an already selected disequality when a peer path proves it
through a direct strict order or disjoint intervals. No ordering is inferred
from inequality alone, no all-pairs candidates are synthesized, and equality or
a merely non-strict peer path still prevents the joined conclusion. Thirty-seven
hosted disequality/convergence checks and both paired groups pass. Positive and
non-strict-counterexample fixtures bring the manifest to 257 cases.

`semantic/finite_facts.md` now inventories the implemented contract fragment,
identities, facts, transfers, joins and candidate/convergence budgets. It separates
candidate selection from evidence and records remaining linear-combination,
aggregate-summary, nested-scaling and unsafe-audit work explicitly.

The owning-record checkpoint `36fd8465` reached a three-generation native fixed
point (generations 2/3: 53/55 s under concurrent checks). Its fresh hosted driver,
broader hosted suite and 255-case parity run are the current integration gates;
this join extension has its focused checks but postdates that frozen snapshot.

## Single-pass loop analysis and outward exits (2026-09-28)

Both analyzers now memoize structural control summaries. A while body with no
fallthrough or continue targeting its own condition needs one checked transfer,
without widening/narrowing searches. Nested local continues are consumed by
their own loops; outward continues prevent this optimization at their target.
The ten-level nested-break regression drops from 620,010 transfers to 32;
eighteen levels take 56. This measures transfer visits, not a claim that all
nested-loop inference is linear. Loops with advancing edges remain scaling work.

This also exposed a hosted correctness bug: nested loop analysis discarded
outward break/continue states. Both finite and general iterator boundaries and
while boundaries now preserve them, including iterator-binding cleanup. A
three-iteration outward-continue program could previously prove its counter was
still zero; that false assertion is now rejected. Positive and negative tests
cover while, finite iterator, general iterator and multi-iterator inner loops.

Validation: 72 surrounding hosted checks, 24 final focused checks, and the paired
single-pass/labeled-exit groups pass. Three fixtures bring the parity manifest to
260 cases. Complete fresh-build integration remains pending for this checkpoint.
The preceding owning-record snapshot completed all 255 parity cases and its
fresh hosted driver passed 35 checks (379.67 seconds including build); its broader
hosted suite remains running separately.

## Bounded search across loop nests (2026-09-28)

The existing per-loop pass cap could still multiply through nested advancing
loops. Both analyzers now share 4,096 speculative search steps across a loop
nest. Exhaustion discards an unstable head, while ordinary condition/body
validation still runs. A separate top-level loop receives a fresh budget;
proof precision in unrelated loops does not depend on earlier search effort.
This is an implementation search limit, not a language loop-depth restriction.

Hosted transfer counts are 15,811 at eight levels and 16,327 at eighteen levels
for the advancing-loop probe. This bounds the repeated transfers, not all work
in a transfer: fact-set size and qualifier scans still need measurements.
Validation: 59 surrounding hosted checks and the paired nested/convergence
budget groups pass on x86-64/C. Tests include runtime behavior, false assertions
inside/after the exhausted nest, iterator nests and an independent later loop.
Two fixtures bring the manifest to 262 cases.

The preceding loop-exit checkpoint `3cc21750` reached a three-generation native
fixed point (generation 3: 59 seconds under concurrent checks). A fresh
hosted-built driver passed both loop-exit and mixed-disequality groups in
337.06 seconds including build. Its 260-case manifest run remains in progress.

## Expression evidence for disequality (2026-09-28)

The broader hosted suite exposed an obsolete test expecting dependent length
disequality syntax to be unimplemented. The syntax now works, but its example
also exposed missing entailment: `src.length + 1` already proves strictly greater
than `src.length`, so it can establish the dependent disequality too. Both
obligation checkers now reuse the existing checked expression-order rules;
unknown or false order results never establish the opposite ordering.

Validation: all 36 hosted length-term/disequality checks and the paired contract
group pass on x86-64/C. Equal expressions and a conditional equal result remain
rejected. The updated expectation checks both acceptance and refutation; the new
positive fixture brings the parity manifest to 263 cases. The broader hosted
run remains tied to the preceding frozen snapshot and still records the old
expectation as a failure, not a newly certified full-suite pass.

## Nested record stores and copy-report coverage (2026-09-28)

Both inline-record store shortcuts omitted copy reporting for a live source.
They now expose that snapshot to `$explicit_copies`. Hosted lowering also uses
its existing checked field-adoption operation to initialize an inline destination
from a last-use record; nested-field stores participate in the same liveness
walk as element stores. Fresh explicit snapshots transfer their owned fields.

The native shortcut also bypassed consuming reads. A last-use record now takes
the ordinary owning path: its fields are retained into the inline destination,
then its temporary root is released before the following mutation. This removes
the extra live array owner that forced an otherwise unnecessary COW detachment.
No new ownership syntax or source-visible value-sharing rule is introduced.

Validation: 48 hosted record/element/parameter checks, 37 surrounding policy and
lifecycle checks, and both paired record-field/element groups pass on x86-64/C.
Regressions include retained sources/views, later constructor operands, repeated
uses, explicit snapshots, nested records, branches and fixed-layout fallback.
The allocation kernel permits at most 64 bytes and retains zero bytes over 100
calls; disabling hosted field adoption exceeds that budget. Positive and negative
fixtures bring the manifest to 265 cases. Fresh hosted/native build integration
remains required for this expanded policy-report coverage.

The preceding loop-exit checkpoint `3cc21750` completed all 260 parity cases.
The broader hosted run at `36fd8465` is still running; its obsolete disequality
expectation was repaired separately at `e3796a0a`.

## Strict-copy adoption checkpoint (2026-09-28)

`semantic/namespaces.dewy`, `semantic/type_names.dewy` and
`semantic/container_methods.dewy` now enable `$explicit_copies`, bringing adoption
to 28 physical modules. Each passed standalone lowering in both compilers with
the expanded inline-field copy reporting. Only the policy directive was added;
no `.copy()` annotations or control-flow rewrites were needed. Whole-graph
adoption and the final copy inventory remain open.

## Replacing owned record fields (2026-09-28)

Hosted lowering now applies the same last-use adoption proof when replacing an
existing record field, matching the native replacement path. The replacement
acquires its contents before the old field is released, then its inline bytes
move into the destination. A temporary frame root suffices. Later source reads,
retained views and repeated uses still require a reported independent copy.

All 30 record-field checks pass, including the paired x86-64/C group and two
allocation-budget positive controls. Both construction and replacement retain
zero bytes over 100 calls and stay within 64 bytes per measured transfer; turning
off adoption exceeds the budget. The replacement fixture brings the manifest to
266 cases. Three-generation integration at the preceding `f899b2b5` snapshot
completed (generation 3: 59 seconds under concurrent checks); its fresh hosted
driver, 265-case manifest run and copy inventory are still in progress.

## Integration and inventory audit (2026-09-28)

At `f899b2b5`, the fresh hosted-built driver passed all three selected groups
(record fields, nested-loop budget and disequality contracts) in 374.66 seconds
including build. The earlier `36fd8465` broad hosted snapshot completed with
4,420 passes, 13 skips and one failure in 3,215.57 seconds: its obsolete
length-disequality expectation. That expectation and its missing expression
entailment were fixed and retested at `e3796a0a`. This is not a claim that the
complete later tree has already passed a fresh broad run.

The expanded inline-field reporting exposes a real inventory-baseline problem:
`f899b2b5` reports 4,301 sites across 53,255 lines (80.762/KLOC), exceeding the
unchanged 3,000/60 gates. The self-build succeeding does not close this gate.
Of its 2,015 field-store notes, 1,336 concern the two-word Span record; the report
also includes runtime-sized records/cells whose snapshots were previously
invisible. Preserve the complete report while auditing cost categories and
remaining transfer opportunities; do not silently erase entries or claim a
passing budget from the former incomplete inventory. The full report is at
`/tmp/dewy-record-field-copy-budget.json` in this session. The 265-case paired
manifest remains running at this snapshot.

## Adoption validation correction (2026-09-28)

Whole-program checking found that the standalone adoption probe above was not
sufficient: unused exports were not lowered. `namespaces.field` still snapshots
a runtime-sized ModuleField on return, and the standalone result did not certify
that path. The premature directives on `namespaces` and `type_names` are removed;
they need reachable-function tests before adoption. `container_methods` retains
its directive pending the full-graph check, making the current physical count
26. Do not interpret standalone module acceptance as complete copy-policy
coverage or insert explicit copies merely to preserve an adoption count.

## Element exclusions and vacuous-summary invalidation (2026-09-28)

Array element summaries now transfer symmetric disequalities in both compilers
and nonzero facts in hosted analysis (native already transferred the latter).
Reads, iterator bindings and array copies retain the supported exclusions;
foreign insertions and writes invalidate them. Comparisons consume incoming
nonzero evidence before refining their own condition. Hosted invalidation also
removes nonzero route evidence after writes and uses length intervals, rather
than scalar nonzero identities, for length exclusions.

The new clear/reinsert counterexample exposed a pre-existing summary bug: old
facts about an empty array's elements could describe its first replacement.
Both store transfers now discard those vacuous route facts before collecting
incoming evidence. This also prevents a symmetric relation from producing a
false self-disequality through an old element route. Negative tests cover
ordinary order facts, field division after a zero write, length after clear,
and comparison operands that mutate an earlier operand's source.

Validation: 74 hosted surrounding exclusion/contract checks, 41 loop/invalidation
checks, and the final 21-case group including paired x86-64/C execution pass.
Three fixtures bring the manifest to 269 cases. Whole-program native driver
construction also passes with `container_methods`' directive; adoption remains
26 physical modules. The preceding `f899b2b5` snapshot completed all 265 parity
cases; the current proof changes still need their fresh-build integration.

## Corrected copy-budget baseline (2026-09-28)

David delegated the rebaseline decision. The complete inventory gate now allows
4,500 sites and 85/KLOC, about 5% above the corrected inventory; no filtering or
strict-policy/allocation-rule change accompanies it. At `9ef254b8`, the native
report measures 4,303 sites / 53,278 lines / 80.765 per KLOC and passes both
limits. The earlier failed 3,000/60 result remains valid historical evidence of
incomplete baseline accounting. Details are in `bootstrap/PHASE0_MEASUREMENTS.md`.

That snapshot also reached an identical three-generation native fixed point
(generation 3: 55 seconds under concurrent checking). Its independently rebuilt
hosted driver passed the two record-field/element-exclusion groups in 334.49
seconds including build. The full 269-case manifest is still running.

## Symmetric element ordering (2026-09-28)

Both analyzers now normalize either endpoint of an ordering relation when
storing/reading/copying array element summaries. A lower bound such as `b < a`
survives storing `a`, just as an upper bound already did. The gap retains its
orientation, and the other endpoint keeps its declaration/route identity.
Foreign elements, indexed/field writes and bound reassignment still invalidate
unsupported facts; clearing cannot resurrect old bounds.

Validation: all 33 element-order/exclusion checks pass including paired native
execution on x86-64/C. A separate direct hosted/native fact-state comparison
also passes. Two fixtures bring the manifest to 271 cases; the full integration
in progress remains the preceding 269-case snapshot.

## Element ranges and evaluated-value identity (2026-09-28)

Uniform element summaries now transfer numeric intervals alongside relational
facts in both compilers. Direct scalar/field reads and saved elements consume
these bounds. Foreign stores still weaken the common summary.

Evaluation-order counterexamples exposed two mistakes. Element stores could
re-read a binding changed by a later constructor field or insertion argument;
those identities now require stability before symbolic transfer. Static type
lengths remain valid independently. Hosted record declarations also replayed
numeric field initializers after constructing the record; they now consume the
field's captured binding interval, matching native snapshot use. A later field
changing `a` cannot change the earlier field initialized from `a`, nor can analysis
repeat an initializer's effects.

Validation: 42 combined element-order/exclusion checks pass including native
x86-64/C execution; 42 surrounding loop/order checks and the direct element-state
comparison pass. The final 28-case group adds the positive record snapshot and
record-default/refined-field regressions. Three fixtures bring the manifest to
274. The preceding `9ef254b8` integration completed all 269 cases; later changes
need their own full integration checkpoint.

## Uniform vacuity across element predicates (2026-09-28)

Joins and loop searches now apply the empty-element rule to every supported
fact kind, including value/length intervals, exclusions and either ordering
endpoint. A branch that stores nothing does not erase a fact true of all
existing elements. This does not seed facts on a nonempty path or permit old
summaries to describe replacement elements.

Validation: the direct hosted/native join/narrow/widen comparison passes with
new interval, reverse-order and exclusion states. The combined element groups
pass 52 checks including native execution on x86-64/C. Branches containing a
foreign value and clear/reinsert paths still reject unsupported claims. Two
fixtures bring the full manifest to 276 cases.

## Insertion allocator boundary (2026-09-28)

Both allocator escape scanners now select argument zero of `insert(value idx)`,
matching `push(value)`, rather than accidentally reporting the scalar index.
Named arguments retain the same rule. This closes a missing copy note and a
strict-policy acceptance hole when a runtime-sized value enters an outer array
from an allocator block. The ordinary placement fallback still protects storage;
this change makes its source-level boundary visible and enforced.

Validation: six insertion checks pass including native x86-64/C execution and
rejections; 24 surrounding hosted allocator checks pass. Explicit `.copy()`
remains accepted, and resetting the arena leaves the inserted snapshot valid.
Two fixtures bring the manifest to 278 cases.

## Receiver evaluation and public effects (2026-09-28)

A statically known `.typename` now preserves evaluation of a computed receiver
in both compilers. Knowing its name does not erase a call, its effects, or its
cleanup. Hosted brand dispatch also now captures computed receivers inside the
expression, instead of hoisting them before an enclosing conditional or reading
an effectful member receiver separately in multiple arms. The same helper serves
brand-directed string conversions. Plain names/type values retain their cheap
constant path.

Validation: seven checks pass including native x86-64/C execution and an empty
effect-row rejection; 20 surrounding brand/conversion/interpolation checks pass.
Three fixtures bring the manifest to 281 cases. This closes the explicit TODO
in native `type_names.instance` without introducing a new evaluation rule.

## Hosted allocator exit cleanup (2026-09-28)

Hosted lowering now registers allocator restoration as an ordinary lexical
cleanup action. Normal exits, scalar/void returns and outward loop exits unwind
it after inner owned values and hooks, matching native cleanup order. Nested
arenas restore in reverse order; return operands evaluate before cleanup. This
replaces the separate fallthrough-only exit insertion and removes the generic
control-flow fallback. Aggregate block/return copy-out and outer owned stores
retain their explicit fallbacks.

Validation: 20 allocator exit/insertion/storage checks pass including paired
x86-64/C execution, and 17 further hosted allocator checks pass. Tests observe
allocator identity after return/break/continue, nested scopes and labeled exits;
a drop hook confirms that cleanup precedes restoration. Three fixtures bring
the manifest to 284 cases. Module-level Arena ownership is still unsupported by
lifecycle lowering; this does not claim coverage of that separate boundary.

The preceding `9dc8ae48` snapshot reached a three-generation native fixed point
(generation 3: 60 seconds under concurrent tests), and its fresh hosted-built
driver passed all four new groups in 364.57 seconds including build. Its full
281-case parity and broad hosted runs remain in progress.

## Destination-owned tag cells (2026-09-28)

Native array detachment now places recursively copied elements in the array's
allocator, matching the hosted clone context. Anchoring only the buffer left
nested tag cells in a temporary region. Both lowerers also promote an owned
optional/union replacement into its destination array's allocator before
publishing it. Promotion consumes the original cell and payload exactly once;
source evaluation remains in its original allocator context. This closes indexed
tag-cell replacement, not every aggregate store or allocator escape path.

The hosted container-element checker now accepts dynamic arrays in supported
unions, using the existing backend handle representation. Fixed-length array
alternatives have not been added by this change.

Validation: 25 allocator storage/exit/insertion checks and 56 surrounding
strict-copy, optional-array, narrowing and union checks pass. The final storage
group passes 12 checks, including paired x86-64/C execution, a reset/reuse test,
repeated promotion with no retained heap bytes, and source allocator evaluation
order. Four fixtures bring the parity manifest to 288 cases.

The preceding `9dc8ae48` integration completed all 281 parity cases and the broad
hosted run (4,551 passed, 13 skipped). Its complete copy inventory is 4,306 sites
across 53,302 lines (80.785/KLOC), within the corrected 4,500/85 gate. These results
complement its three-generation fixed point and fresh hosted-built driver checks;
they do not yet include the allocator exit and destination-cell follow-ups.

## Reachable strict-copy adoption (2026-09-28)

Five further modules enable `$explicit_copies`: parser CLI, cache bytes, source
views, type names and timing. The complete compiler entry point passes native
and hosted analysis with these directives, including reachable exports. Adoption
now covers 31 physical modules. Bounded Span/Alternative stores remain reported;
no new explicit copies or reporting exemptions were added. The namespace
lookup's independent generic-alias snapshot remains a separate open site.

The `a4c05062` destination-cell snapshot reached an identical three-generation
native fixed point (generation 3: 55 seconds under concurrent analysis). Its
broader parity checkpoint is separate from these directive-only changes.

## Sequence identities in element facts (2026-09-28)

Element summaries now rename every occurrence of a stored value's identity in
both compilers, including length projections and the sequence/upper/offset ends
of index and remainder relations. The operation preserves relation direction
and keeps scalar terms distinct from lengths. Static length evidence uses the
same incoming-summary join, removing the separate length-only transfer path.
Only matching facts are rebuilt; unrelated state entries are left alone.

Validation: 71 combined element/order/exclusion/empty-join checks pass, including
native execution on x86-64/C. The final sequence group passes 21 checks, adding
independent nested-array snapshots and length-changing mutation rejection. Two
direct hosted/native fact-state comparisons pass, including the new sequence
endpoints. Four fixtures bring the manifest to 292 cases. The broader owning-cell
snapshot parity run remains separate and in progress.

## Hosted owned-array replacement (2026-09-28)

Hosted array assignment now consumes independently owned dynamic-array call
results instead of cloning them. Dynamic-array local replacements also use the
existing last-use analysis and transfer helper, including narrowed owning cells.
The new value is prepared before releasing the old one; place parameters publish
the replacement back to their caller. Later source/alias uses and exposed storage
retain the ordinary copy obligation. Native lowering already uses these transfer
rules. This repairs a hosted strict-policy gap found while adopting the layout
module, without adding a policy exemption.

Validation: 47 replacement, strict-policy and surrounding array/record transfer
checks pass, including native x86-64/C execution. Repeated replacements retain no
heap bytes, shared source snapshots remain independent, and a live source/view
prevents the move. Three fixtures bring the manifest to 295 cases.

The preceding `a4c05062` ownership snapshot completed all 288 parity cases in
addition to its identical three-generation fixed point. Later fact-transfer and
replacement work awaits the next frozen integration snapshot.

## Shared traversal scratch for copy and layout queries (2026-09-28)

Native copy classification and layout traversal now keep one mutable recursion
path per query, pushing before inspecting children and popping on every normal
result, including Pending. Sibling components reuse that scratch instead of
copying a set at each recursive edge. Cached copy classifications return before
allocating scratch. This follows the hosted traversal protocol; cycle handling,
brand descendants and separate string-sharing memo modes are unchanged.

Both modules now enable `$explicit_copies`, bringing adoption to 33 modules. The
complete native entry-point analysis passes, and the hosted layout/copy fixtures
exercise the same strict modules. No copies were hidden: the native report has no
remaining sites in these two modules. The hosted assignment repair above was
required for layout adoption.

Validation: 23 copy-bound checks and two layout/dictionary-layout checks pass on
x86-64/C, including repeated sibling types and shared-string classification. The
copy-bound fixture is now included in the full 296-case parity manifest. A fresh
integration will cover these modules as part of the complete compiler.


## Allocation profile and a counting correction (2026-09-28)

`tools/allocation_sites.py` attributes a native program's arena allocations
to source statements by instrumenting its debug µDewy. On the compiler's own
sources at `86a86d8a`, a self-build makes 402 M allocations totaling about
32 GB, with 2.6 GB peak live. The breakdown, and why none of it is
frame-resident yet, is in `bootstrap/PERFORMANCE.md` ("Allocation profile of
a self-build"). `ROADMAP.md` 1.1 schedules the fixes.

The allocated totals recorded in this ledger from 2026-09-24 to 2026-09-27
summed every `dewy storage` line of `--timings`. Those lines nest (per-module
imports, sub-phases), so the totals overstate the real volume about
threefold. For example, the 87.7 GB recorded for `phase1-u` corresponds to
roughly 31 GB. Comparisons between the recorded totals still roughly hold.
Sum only the top-level phases.

## Machine arithmetic in affine evidence (2026-09-28)

A guard or stored sum/difference now supplies an affine relation only when its
mathematical result fits the machine result type. Previously, wrapping arithmetic
could supply a false order: `uint8(255)+1 < 1` does not establish `255 < 1`, and
storing `uint8(0)-1` does not preserve the source's upper bound. Both compilers
check the operation before transferring evidence; native storage uses the already
observed operand intervals rather than replaying evaluation. Named user functions
do not acquire affine meaning merely by spelling their names like operators.

Validation: 55 focused hosted checks, 66 surrounding finite-fact checks, 60
combined paired checks, and three direct hosted/native fact-state comparisons
pass. Three fixtures bring the manifest to 299 cases. These checks include
unsigned/signed 8- and 64-bit guards, underflowing storage, and successful guarded
nonwrapping operations.

The preceding `65b46249` snapshot reached an identical three-generation native
fixed point and passed four fresh hosted-built driver checks. Its complete copy
inventory is 4,296 sites across 53,360 lines (80.51/KLOC), within the corrected
4,500/85 gate. Generation 3 took 74 seconds while hosted checks ran concurrently;
that is integration evidence, not an isolated performance measurement.


## Sequence-transfer integration checkpoint (2026-09-28)

The frozen `65b46249` compiler passed all 296 parity fixtures. Its broad hosted
run finished with 4,588 passes, 13 skips and one stale rejection expectation:
`test_union_containers` still rejected dynamic-array union members after the
destination-owner storage work enabled them. That expectation now specifically
covers fixed-length array alternatives, which remain unsupported. The updated
container group passes with the surrounding hosted checks (65 total). Dynamic
array ownership and reset/reuse already have paired execution coverage in the
allocator storage group; no implementation restriction was restored to satisfy
the old expectation.

## Operator identity through proofs and lowering (2026-09-28)

Both analyzers now require builtin identity before deriving intrinsic arithmetic,
comparison, negation, length-offset or update facts. A user function's checked
return contract remains available; its spelling supplies no additional theorem.
Native arithmetic validation follows the same identity rule.

Hosted operator dispatch now preserves the identity of lexical declarations,
matching the native source-binding model, instead of emitting a binding-less
call with a user signature. Hosted lowering also stops resolving actual intrinsic
identifiers through a same-named lexical declaration; a user `__add__` previously
captured imported prelude arithmetic. Logical operator rewriting now applies
only to builtins in both checkers: an ordinary user call evaluates its arguments
and retains its own result/effects. This preserves lexical shadowing and changes
no µDewy short-circuit rules.

Validation: 65 hosted identity/affine/type-fact/container checks, 52 further
hosted operator/proof checks, four direct hosted/native arithmetic/length/predicate
state comparisons, and 32 combined paired checks pass. The final expanded
operator group passes all 12 checks, including x86-64/C execution, lexical
operator syntax, effectful logical arguments and a written result contract.
Five fixtures bring the manifest to 304 cases.

The `0c203273` native snapshot reached identical three-generation output
(generation 3: 58 seconds under concurrent work). Its fresh hosted-built driver
exposed a tag-handling omission: BigInt comparison helpers have real function
bindings and an explicit checked `integer_operation` tag. Hosted guard refinement
now retains that tag path, as native refinement already did. The focused
operator/narrowing group passes 12 hosted checks, and the previously failing
binary-literal compiler module checks successfully. Fresh hosted integration
is being rerun with this correction; the earlier driver failure is not a pass.

## Read-only calls through narrowed record unions (2026-09-28)

Native argument borrowing now recovers the stable source route through
record/union casts. The existing lowering check still decides whether the
representations share a handle; a real cell conversion retains its copy and
cleanup. Previously route discovery stopped at a representation cast even when
lowering already supported borrowing that same record handle.

A family-narrowing kernel with 1,000 read-only calls now allocates zero bytes,
down from 32,000, matching the hosted compiler. This is the AST-reader pattern
identified by the allocation profile; it is not yet a measured reduction of
the complete self-build's 32 GB total.

The paired alias tests also found and fixed a hosted snapshot bug. Conflict
routes now see through value/representation/proof wrappers, and a narrowed union
passed to a parent parameter uses that parameter's record layout when an
independent snapshot is required. Later argument writes and same-call place
aliases preserve the earlier value. Keyword and explicit-cast variants pass.

Validation: 13 hosted record/field-call checks, five final hosted cases, three
paired borrowing groups, and the final five-case paired kernel pass on x86-64/C.
Three fixtures bring the manifest to 307 cases. The preceding arithmetic/tag
snapshot also passed both fresh hosted-built driver groups (319 seconds including
build); its full 304-case parity run is separate and still in progress.

The first `bbdffdfe` full bootstrap run stopped at the existing argument-temporary
fixture. Route recovery exposed an owned dictionary-lookup fallback to the
union-loan shortcut, which passed it without releasing it. That shortcut now
requires a nonowning source. Owned lookups use the existing proven view path or
ordinary temporary cleanup. The full temporary fixture is included alongside
the narrowed-record regressions; both paired groups pass (82 seconds), retaining
the zero-allocation read-only kernel. This failure was caught before claiming
a new native fixed point.

## Reuse completed lifecycle resource queries (2026-09-28)

The native lifecycle rewrite now keeps a type-id cache in its pass-local Plan,
matching the hosted pass's cache lifetime. Both resource-bearing and negative
answers are retained. Recursive walks still finish with their own visited set
before publishing an answer, so a partially explored cycle cannot create a
false negative. Newly synthesized types have new ids; a new rewrite pass starts
with an empty cache. This removes repeated scratch arrays/sets for the same
checked type without changing hook selection or ownership rules.

Validation: the direct kernel passes with native compilation and with a fresh
hosted-built executable on x86-64/C. It covers cycles with and without a nested
hook and 2,000 warmed negative queries with zero allocated bytes. Twenty-seven
recursive copy/drop, resource-replacement and union checks pass, including
paired execution. The kernel brings the parity manifest to 308 cases. Full
self-build volume and timing are still to be measured for this batch.

The `573a2b1b` parity snapshot passed 303 of 304 cases. The native failure in
`length_terms.dewy` came from counter-bound discovery rejecting a builtin with
a stable binding id. That query now consults the registry rather than accepting
only binding-less intrinsics. User functions with the same spelling still do
not establish a counter bound. The direct HIR comparison includes a shadowed
operator, and the full length-term fixture joins the focused operator group:
15 checks pass, including paired x86-64/C execution. A new frozen integration
will cover this correction together with the borrow and lifecycle-query work.

## Reserve surviving fact joins (2026-09-28)

The native fact-state join uses the largest input as a capacity hint for its
value/chain arrays. Reservation happens only when the first fact survives;
empty joins retain empty buffers, and zero/single-input fast paths are unchanged.
The hint is not a bound: implied evidence can retain more than any one input.
The complete hosted/native fact-state comparison passes (5.87 seconds).
A full self-build allocation delta has not yet been measured.

## Preserve union selection in borrowed cells (2026-09-28)

The `ecd0547f` integration passed the first-generation x86-64/C execution
checks, but generation 2 crashed while parsing the next self-build. A reduced
case exposed the mistake: forwarding `A?` into `A|B|none` borrowed the nullable
record handle but tagged it as the whole source union. An absent handle was
therefore treated as a present record. The wider route discovery made this
previously unexercised shortcut reachable.

Borrowed frame cells now reuse ordinary union packing's member selection,
including its absent-value branch and dynamic record-family selection. The
proven owner retains the payload; only the destination cell's storage differs
from an owned conversion. Dictionary getter frame views use the same helper.
No source-language semantics changed. Both regression fixtures are in the
native-pair smoke checks, so this failure is caught before another self-build.

Validation: 38 borrowing, argument-cleanup and union-getter checks pass,
including hosted/native x86-64/C execution (190 seconds). The complete parity
manifest now has 310 cases. The preceding frozen hosted-built driver passed
both borrowing/operator groups (318 seconds including its independent build).
A new frozen three-generation run and complete parity run will certify this
correction; the failed `ecd0547f` run is not a fixed-point checkpoint.

The `11fa4515` frozen snapshot reached byte-identical native generations 2 and
3 on the direct x86-64 route. Both generations took 55 seconds with concurrent
validation; these are not isolated performance measurements. Its independent
hosted-built borrowing driver passed (310 seconds including build). The earlier
`bbdffdfe` broad hosted snapshot finished with 4,626 passed and 13 skipped
(1,876 seconds); later corrections have their focused checks above.
The complete `11fa4515` copy inventory is 3,996 sites over 53,417 lines,
74.807646/KLOC, within the unchanged 4,500/85 gates. It retains the full inventory,
including bounded inline records. The measured preceding `65b46249` inventory
was 4,296 sites. Full end-to-end parity remains a separate running gate.

An isolated native join kernel (100 joins, two 100-fact inputs, identical
compiler seed for both source versions) allocated 4,326,400 bytes before the
reservation change and 4,134,400 after, a 192,000-byte/4.4% reduction. This is a
kernel result, not a claim about total compiler allocation volume.

## Update analysis collections through their proven owners (2026-09-28)

Brand-family adjacency construction now extends a checked dictionary-entry
place instead of copying and replacing the sibling array for every child.
This removes quadratic storage traffic in a wide family: the 512-sibling
native kernel falls from 4,248,216 allocated bytes to 8,776. The fixture gates
linear bookkeeping and retains insertion order. It also passes through fresh
hosted compilation on x86-64/C. Existing numbering/independent-snapshot checks
pass.

Predicate write discovery reads an existing call summary through a required
view, adding its members to the separately owned result. The direct comparison
now covers supplied summaries and checks that mutating its result leaves the
summaries unchanged. The expanded hosted-built comparison passes (314 seconds);
the original comparison also passes under native compilation. Both modules
enable `$explicit_copies`, bringing adoption to 35 modules without broadening
the exemptions. The manifest adds the adjacency kernel (311 cases).

The `11fa4515` frozen end-to-end run completed: **310/310 parity cases passed**,
including the earlier length-counter failure and both borrowed-union regressions.

## Publish relational transfers after deriving only their updates (2026-09-28)

A large direct predicate test exposed states exceeding 100,000 facts. Relational
copying took a complete environment snapshot for every stored value or field,
even when only a few facts mentioned that source. Both implementations now
collect derived entries while reading the unchanged input, then publish them.
The native pass avoids detaching/copying the unrelated entry array; the hosted
pass avoids allocating an item tuple for every unrelated fact. The operation
still observes the original evidence throughout and never feeds a derived fact
back into the same transfer. Copying a term to itself does no work.

The native kernel with 1,000 unrelated facts and 100 distinct transfers falls
from 4,419,328 allocated bytes to 113,152 (about 39x). Its allocation gate and
explicit result/provenance checks also pass through hosted compilation on
x86-64/C. The complete direct relational/fact-state comparisons pass, and 113
hosted affine, scalar-snapshot, disequality and element-sequence regressions
pass. The manifest includes the kernel (312 cases). These are scoped allocation
improvements, not a reduction of the fact vocabulary or a claim that its dense
relation growth is solved. The large predicate comparison still identifies that
growth as further proof-engine scaling work.

The `20220d1a` frozen snapshot also reached identical native generations 2 and
3 (46 and 51 seconds). The expanded predicate-summary comparison passed under
native compilation as well. An additional 1,000 deterministic mixed-fact
relational transfers exactly match the preceding hosted implementation,
including scalar/length terms, large identities, collisions between derived
keys, and address-cap metadata.

## Retain only affected facts during length changes (2026-09-28)

Length transfer now follows the same selective-update rule. Native analysis
collects changed entries and removals while reading the environment, then
publishes them; it no longer detaches the entire values array. Hosted analysis
updates existing dictionary values in place and defers removals, avoiding a
whole-state item list. Each transformation still observes its original interval.

A kernel with 1,000 unrelated facts and 100 length changes drops from 896,000
allocated bytes to 108,800 (about 8.2x). Its expected final bound, cap provenance,
state size and allocation budget pass under native compilation and hosted
x86-64/C compilation. The direct state/relational comparisons pass, covering
index and disequality invalidation, growth/shrinkage and cancelling endpoints.
Another 1,000 deterministic mixed-fact length changes exactly match the previous
hosted implementation. The manifest adds the kernel (313 cases); this follow-up
has focused verification, beyond the frozen fixed-point checkpoint above.

## Bound constructor-private proof lifetimes (2026-09-28)

Both analyzers now expire a literal's private field bindings after its enclosing
declaration or assignment has installed the value. Earlier fields remain
available during default evaluation; completed destination routes and unrelated
source facts survive. Syntax discovery is cached separately from dynamically
allocated routes, and expiration scans the fact state once for the whole set.
Nested function bodies retain their separate analysis. No qualifier budget was
reduced and no unknown obligation was promoted to evidence.

A 128-constructor experiment previously accumulated 66,304 facts; its peak is
now 264 (hosted compilation 2.40 s to 0.88 s in this small check). New hosted and
native-analyzer scaling regressions require linear state size and verify every
completed record's field intervals. The direct regressions pass on x86-64/C
(134.15 s including hosted compilation of the native analyzer). All 38 adjacent
hosted constructor/default, scalar snapshot and array-fact checks pass, as do
the three paired groups on both backends (71.50 s). The native parity manifest
now contains 314 cases. Full integration follows this focused checkpoint.

## Renew containing arrays after conditional element transfers (2026-09-28)

Hosted and native ownership now permit replacing the statically selected
containing array (or an ancestor record) after a runtime-selected element
transfers out. Cleanup uses the saved selectors and presence flags to drop only
the old value's still-owned components. The replacement resets flags under its
route; sibling regions retain their independent flags. This works across loop
backedges and when replacement evaluation changes the original selector.

The liveness rule is shared with ordinary component renewal: a store needs its
ancestors, not the old value it wholly replaces. Reading an old element, storing
inside a possibly partial array, or renewing only on an unrelated conditional
path still cannot justify a transfer. No dynamic disjointness assumption or
resource copy was added. Potentially overlapping dynamic routes remain a
separate lifetime-proof task.

Validation: 49 adjacent hosted checks passed, followed by all nine tests in the
expanded renewal group. All five paired ownership groups passed on hosted/native
x86-64/C (114.02 s), including multiple simultaneous regions and zero retained
storage over repeated renewal. The new loop fixture joins the parity manifest
(315 cases). The preceding `ad4c959c` constructor-lifetime snapshot reached a
three-generation direct native fixed point; generations 2/3 took 51/59 seconds
under concurrent checking. Its standalone native analyzer scaling kernel also
returned 42. Full parity and broad hosted checks for that snapshot are ongoing.

## Conditional value moves (2026-09-28)

Both last-use analyses now carry a consuming position through the selected
arm of an `if` and the final expression of a value block. Conditions and
preceding statements remain ordinary reads, and loop reuse, later reads and
live views still prevent transfer. Hosted lowering now gives array-valued
conditionals one owning descriptor convention, with temporary cleanup for
reads and adoption for bindings/stores. Descriptor-backed owners retain
that status when an exact length is inferred. This also removes a redundant
copy of conditional results that previously lost the first allocation.

Validation: 11 focused hosted checks, 28 adjacent array/default/flow checks,
34 preceding move/borrow checks, and three paired native groups pass on
x86-64 and C (56.72 seconds). Repeated-call counters warm allocator metadata
first, then check that value storage does not accumulate. The parity
manifest now has 316 cases. The broad hosted run of the preceding
`ad4c959c` integration finished with 4,631 passed and 13 skipped in 1,865.39
seconds; this does not claim broad certification of subsequent edits.

## Fresh tagged values during startup (2026-09-28)

Native conversion ownership now follows fresh cell storage independently of
lexical cleanup being enabled. Module initialization adopts a newly packed or
converted cell instead of reporting and performing another logical copy. A
read of an existing global still requires its ordinary copy/borrow proof.
This repairs the strict-copy rejection of the zero endpoint in the global
`Interval[1 0]` constructor without exempting BigInt copies from policy.

Hosted startup now uses the binding's declared type at its initialization
store. Using the initializer's narrower type could write a record directly
into a tagged global's cell, omitting the tag. An obsolete early rejection of
global heterogeneous unions containing `none` has been removed: existing
cell allocation and packing now handle them. Regressions pass globals through
ordinary function boundaries so constant propagation cannot hide a bad tag.

Validation: four focused hosted checks and their native x86-64/C group pass,
including a retained-source strict-copy rejection. Thirty-three adjacent
global, union, array-move and sharing checks also pass. The integration
manifest now contains 317 cases.

## Transitive evidence for exact updates (2026-09-28)

Both analyzers now use the established difference graph when one-hop interval
reduction cannot prove an affine update nonwrapping. Forward paths bound the
subject above; reverse paths bound it below. Each bound retains its endpoint
and path provenance. A finite edge-count relaxation prevents contradictory
cycles from diverging; only proved path bounds are returned. Ordinary counters
keep the existing cheaper path. This retains relations across an `int8` update
whose limiting guard is five or more ordered terms away, without assuming the
source assertion or overlooking the arithmetic's own width.

Validation: 45 hosted update/loop/overflow/provenance checks, three paired
native x86-64/C groups (63.06 seconds), and the direct hosted/native relational
kernel comparison pass. The kernel includes long chains, reverse bounds,
length identities, negative gaps and address-cap evidence. It caught and
helped remove a spurious hosted cap marker on an unknown endpoint. The
manifest has 318 cases.

The preceding `eb154c85` startup/ownership snapshot reached an identical
three-generation native fixed point (generations 2/3: 47/50 seconds under
concurrent checking). Its complete 317-case parity run is still underway.

## Expire lexical facts and batch native cleanup (2026-09-28)

Hosted statement/value-arm scope exits now remove all facts mentioning local
bindings, their descendants and selector-dependent routes, rather than only
the locals' scalar intervals. Constructor cleanup shares the same expiration
walk. Copies stored into outer owners keep their own evidence. Native scope
cleanup now collects the same retired route closure and scans the fact state
and expression identity maps once, instead of once per local. Normal, break
and continue exits share that operation, including early exits from value
arms. Saved numeric expression results survive; dead storage identities do not.

A 128-scope hosted probe drops from 16,514 peak facts to 4, and from 5.628
seconds to 0.684 seconds with the prelude warmed. The native cleanup kernel
compares batched cleanup with repeated individual invalidations: allocations
fall from 405,264 to 209,648 bytes when hosted-built, and from 278,448 to
212,704 bytes when native-built. Its gate checks surviving external facts,
expired selector descendants and saved snapshots, and caps batched requests
at 256,000 bytes.

Validation: 44 adjacent hosted fact/loop checks, two new scope checks, 51
additional global/constructor/proof checks, the standalone cleanup kernel,
and three paired scope/snapshot/element groups pass. A fresh driver after the
exit-path consolidation passes both new fixtures on hosted/native x86-64/C
(50.62 seconds). The manifest now has 320 cases.

The preceding `eb154c85` snapshot completed all 317 parity cases, in addition
to its identical three-generation native fixed point. Transitive update and
scope cleanup changes postdate that frozen integration. Phase 1 remains open
for the completion checklist above.

Checkpoint (2026-09-28): hosted last-use transfer now includes dictionary value
stores and ordinary record replacement, matching native lowering. Dictionary
keys remain reads. A record replacement stages the adopted fields before
releasing the old destination, and clears transferred source handles for its
later cleanup. The shared eligibility check retains conservative fallback for
prepared trees, incompatible descendant layouts, and borrowed fields. Later
reads, live views and repeated outer-owner use in a loop still prevent moves.
Validation: eight hosted acceptance/rejection cases and the paired x86-64/C
group pass, including repeated nested-dictionary insertion/replacement,
record/set replacement and zero retained bytes. The surrounding proof and
ownership selection passed 127 checks. Two expected-result fixtures join the
parity manifest; full integration for this checkpoint is still pending.

Checkpoint (2026-09-28): both proof engines now answer bounded linear comparison
queries over the existing difference graph. Normalization handles addition,
subtraction, constant multiplication and cancellation, with checked machine
width at every intermediate. Opposite coefficients consume concrete established
order paths; unmatched terms retain interval evidence. This is deliberately
incomplete query entailment, not speculative assumptions or new loop invariants.
The shared limits are 128 expression visits and 32 distinct terms. Unknown
operations, opaque calls, expired identities, possible wrapping and budget
exhaustion cannot establish an assertion. Validation: 21 focused hosted cases,
the paired x86-64/C group, and 127 surrounding proof/ownership checks pass.
The cases include weighted sums, strictness, equality, cancellation, transitive
relations, mutation invalidation, narrow-word overflow and budget exhaustion.
The finite vocabulary document records the supported fragment and limits; final
integration and the remaining Phase 1 audit/lifetime work are still open.

Checkpoint (2026-09-28): strict-copy adoption now covers 37 physical modules.
`analyze/storage_borrows.dewy` consumes the hosted dictionary-store and record-
replacement proofs above. `prelude_cache.dewy` gives the loaded byte buffer one
owner, the Reader, and performs later length/checksum checks through that owner.
This removes its unnecessary buffer snapshot without adding explicit copies.
The complete native compiler analysis accepts both directives. A hosted lowering
inventory found no policy failures, followed by the full enforced prelude-cache
regression passing (228.54 seconds including its hosted driver build and cold,
warm, stale-input and corrupt-cache checks).

Integration follow-up: `2dd7c9ae` reached a three-generation native fixed point,
including x86-64/C execution checks. Generations 2/3 took 50/55 seconds under
concurrent checking; these are not isolated performance measurements. Full
parity at this newer checkpoint is still pending.

Checkpoint (2026-09-28): partial resource transfers through wrappers with drop
hooks now consume the ordinary transitive parameter-effect summaries. A wrapper
may keep a hole only when its drop cannot read, mutate, replace or expose that
route; unknown calls and overlapping access prevent the proof. The hook still
runs before remaining-field cleanup. No destructor is skipped and no new source
annotation is needed. Hosted and native lowering use their existing checked hook
identities; native lookup uses the hoisted hook inventory, not syntax bindings.
Validation: 11 focused hosted cases and the paired x86-64/C group pass, covering
conditional moves, returned fields, nested wrappers, runtime-selected elements,
transitive helper reads, permitted sibling mutation and rejected missing-field
accesses. Fifty-six surrounding hosted checks and three paired groups pass.

The preceding scope-cleanup checkpoint `7b9799ca` passed all 320 parity cases.
The newer linear-query checkpoint's complete parity run remains in progress.

Checkpoint (2026-09-28): ownership liveness now retains field suffixes below
unknown array indices. A wildcard footprint proves `rows[i].left` disjoint from
`rows[j].right` without claiming anything about i and j. The cleanup plan still
stores only the static containing region and captures actual selectors once.
Reads of overlapping fields, whole-owner reads and selected-slot replacements
keep the resource live. Exact containment remains separate for assignment kills:
a selected write cannot erase liveness for every possible slot. Complete
containing-region replacement retains the previous renewal rule.
Validation: 24 hosted checks and three paired x86-64/C groups pass. New cases
exercise equal and unequal indices, conditional transfers, scalar sibling reads,
selector mutation after capture, and rejected same-field reads/transfers and
possibly overlapping replacements. This closes dynamic field disjointness;
proofs of distinct runtime indices themselves remain a separate case.

Checkpoint (2026-09-28): native `.typename` no longer captures an aggregate
when its receiver is already a named local/parameter. Its brand tests and
literal result arms cannot mutate that receiver. Computed receivers still
capture once at the original evaluation point, including inside conditionals.
This matches the hosted checker and removes a strict-copy rejection for naming
a borrowed record while it remains live. Seven hosted cases and the paired
x86-64/C group pass, retaining the existing computed-receiver, member-receiver,
conditional evaluation, conversion-dispatch and effect-contract coverage.

Full integration at `2dd7c9ae`: all 323 parity cases passed, in addition to the
three-generation fixed point recorded above. The hook/footprint/typename changes
postdate that checkpoint and have the focused paired evidence recorded here.
