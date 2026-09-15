# Native compiler performance and open storage design

Copy-on-write is a provisional implementation strategy, approved for making
native bootstrapping practical. It preserves value independence while sharing
aggregate backing storage until mutation. It is **not** a settled commitment
to unpredictable first-write latency in the language's long-term cost model.

Open design question: how can Dewy's types, facts, ownership and lifetime
information make copying and reclamation predictable, ideally zero-cost?
Candidates include statically established unique ownership, moves, bounded
borrows, immutable sharing, and storage partitioned by lifetime. Evaluate
nested updates and arrays with large backing buffers explicitly: an O(1)
snapshot can otherwise conceal an O(n) first write. Do not add source-level
ownership features without language-design review.

The optimized C route is a bootstrap accelerator. Reasonably performant
Dewy -> µDewy -> native machine code builds without the C backend remain an
explicit goal. General aggregate representation and analysis improvements
must benefit both execution routes. Keep both hosted and bootstrap lowering
implementations consistent, including place arguments and dynamic brands.

Performance gates precede expensive bootstrap generation checks. Use bounded
representative kernels for read-only graph access, context construction,
branch snapshots, nested mutations and repeated module analysis. Account for
copied bytes, allocations and peak live storage; test scaling and reclamation,
not just elapsed time. A full self-build is a final integration check, not the
inner development loop.

The first bounded sharing gate is `tests/python_misc/test_array_sharing.py`.
Its compiler-shaped context fixture constructs 500 checkers over graphs of
1,000 and 100,000 elements. Hosted-generated code on both x86_64 and C routes
allocates the same 196,000 bytes at either size, retains zero bytes, and
copies zero dynamic-array payload bytes during those constructions. This is
a kernel result, not evidence of a completed native self-build. Mutation and
raw-exposure fixtures separately verify value independence, including nested
places and growth after exposure. A forced dynamic copy checks that the copy
counter actually increases.

Internal `_arena_*_bytes` counters measure size-class payload allocation,
live and peak payload storage, and dynamic-array fallback copies. They do not
measure RSS, frame/static copies, or string-region bytes independently. These
are backend diagnostics: source analysis does not model implicit allocator
calls as language-visible effects. Read counters across an explicit function
boundary in fixtures; don't use their values as source-level proof facts.

Array descriptors remain private. The owner word currently distinguishes
frame/static storage (0), unique arena storage (1), a shared count pointer
(>1, explicitly marked by the shared flag), and raw-exposed pinned storage (-1). Exposing raw aggregate storage
first detaches existing snapshots and prevents subsequent sharing of the
exposed tree. Without a tracked raw-pointer lifetime, that tree is retained
conservatively. This is an implementation fallback, not a new ownership
feature or a change to value semantics.

Borrowed byte/grapheme arrays can retain a string descriptor in their owner
slot. The explicit shared flag distinguishes that pointer from a reference
count; raw exposure first gives such a view independent array storage.

That conservative lifetime also applies to source-level raw I/O buffers.
Ownership tests collect live-byte samples into reserved storage and print
them afterward, so the observer's pinned output buffers do not look like
retention by the operation being measured. Scoped borrowing for synchronous
I/O is a remaining opportunity to avoid this cost without weakening raw
pointer validity. Compiler-generated representation loads are internal reads;
they must not trigger the source-level exposure rule.

## Native gates after sharing and temporary reclamation

Fresh aggregate reads now use the same ownership classification as value
boundaries. Field/index reads preserve their result before releasing a fresh
receiver; type tests and length queries release it after computing the scalar
result. Skipped branches keep evaluation and cleanup together. Removed array
elements transfer ownership, and joins and set operations release private
input snapshots. The combined `native_read_temporaries.dewy` kernel retained
8,920,032 bytes per 5,000 iterations before this batch and zero afterward.
Both output backends pass; this is a bounded result, not a self-build claim.

Iterator arms now retain fresh sequence owners in a cleanup scope spanning
setup, body and fallback. Normal exit, break and return release the sequence;
continue keeps it for the next element. Fresh casts also reclaim union cells
after preserving their converted result, including flows joining arrays of
different lengths. The combined iterator/cast fixture retained 1,032,000 bytes
per 1,000 iterations before the cast fix and zero afterward.

String literals now use static descriptors as well as static bytes and
grapheme tables. Three literal evaluations per iteration previously retained
960,000 bytes over 5,000 iterations; the multibyte-string fixture now retains
zero. Dynamic strings and their views still need a fuller reclamation model.

The same checker-construction kernel compiled through native lowering now
allocates 616,000 bytes for 500 constructions, at both graph sizes, retains
zero bytes and copies zero dynamic-array payload bytes. The allocation count
differs from hosted lowering; the important properties are independence from
graph size and reclamation after the construction scope ends.

A hosted-generated native C seed successfully compiled and ran the sharing,
raw-exposure, checker-context and refined-union fixtures through its full
command-line pipeline. Each prelude-using fixture took approximately 35–36
seconds on the development machine; the sharing fixture peaked at about
2.5 GB RSS. The no-prelude literal took 0.07 seconds. These are bounded
integration results, not a claim that compiler self-hosting is complete.
The direct x86_64 seed passed the literal gate but exceeded the 90-second
limit on the first prelude-using fixture. Its performance remains unfinished.

Building the large C seed itself with the current C backend and `cc -O2`
took approximately 13 minutes. C compilation is consequently a separate
remaining cost from executing the native compiler. An `-O1` experiment
exceeded a five-minute cap and provides no evidence yet for changing the
default optimization level.

Parallel GCC link-time optimization reduces that build cost without changing
the generated C. On the 80 MiB source-validation driver, `-O2 -flto=8` built
in 4 minutes 15 seconds; ordinary `-O2` took 10 minutes 52 seconds. These
development-machine builds overlapped, and LTO used more total CPU time
(819 versus 618 seconds). Both native validator variants preserve the
stored-contract acceptance/rejection checks. Set `DEWY_BOOTSTRAP_LTO_JOBS=8`
for the opt-in bootstrap-script accelerator; the script probes support and
uses the same options for both generations. This does not replace the
required fixed-point comparison or establish native self-hosting by itself.

The bootstrap script separates Dewy emission from backend execution. A small
handoff records the seed's exact compile-only arguments; the script invokes
µDewy after the Dewy process exits. This releases the first seed's compilation
arena before µDewy and any C compiler need memory. Backend failures still
stop generation construction and prevent certification. The handoff uses no
hosted compiler and applies to both output backends.
For C output, the same compile-only handoff separates µDewy from the C
compiler: its exact argument vector is recorded and replayed after µDewy
exits. This avoids overlapping the µDewy parser arena with C compilation.
The original compiler search path is restored for launchers such as ccache,
and a failure in either process prevents certification.

Generation one must pass `tools/check_native.sh PAIR 1` before the bootstrap
script starts generation two. This exercises the new compiler's scalar,
library, value-independence and retention cases on both output backends,
along with native test discovery. A failing compiler cannot launch another
self-build or receive a fixed-point certificate. The same checker accepts a
completed pair without a generation argument.

`tests/fixtures/native_owned_union_temporaries.dewy` checks another important
boundary: optional flows and lookups already create owned cells. Its original
lookup/flow loop retained 680,000 bytes per 5,000 iterations. The expanded
fixture now also covers fresh function results, record-family views, and
smaller children converted to parent records or optional parents; native
lowering retains **zero bytes** after a second 5,000-iteration run. Existing
values still copy independently. Adopting a record requires matching storage
sizes; a differing destination layout copies and releases the original.
This is a bounded ownership result, not a completed native bootstrap claim.

## Linear native output emission

The twelfth native-pair attempt stopped at the 35 GiB aggregate RSS limit
while the seed rendered generation one. Lowering had finished; recursive
subtree strings and repeated `indent` passes consumed the remaining memory.
That attempt produced no first-generation Dewy executable or certificate.

The emitter now visits expressions, statements and function bodies with one
shared output writer. It writes each line's indentation once, reuses cached
indentation strings, and joins fragments at the output boundary. Startup and
program emission use the same writer. Errors still prevent publication of
partial code, and operand parentheses and µDewy boolean semantics are unchanged.

A bounded fixture with shared HIR leaves separates rendering from checking
and lowering. On the development machine, using hosted-built direct x86_64
executables for both versions:

| Nested blocks above the leaf body | Statements | Output bytes | Before | After | Peak RSS before / after |
| --- | --- | --- | --- | --- | --- |
| 32 | 1,000 | 148,356 | 7.95 s | 0.14 s | 31.8 / 6.7 MiB |
| 64 | 1,000 | 288,900 | 28.68 s | 0.25 s | 87.9 / 9.1 MiB |
| 64 | 4,000 | 1,104,900 | exceeded 60 s | 0.87 s | unmeasured / 22.2 MiB |

The completed old/new cases match byte for byte. All three new outputs also
match an independently constructed expected result, including every space
and newline. `native_emitter_scaling.dewy` and its emitter regression test
preserve this workload. These measurements justify another bounded-gated
self-build; they do not establish that the native bootstrap loop is closed.

The same fixture also passes after native Dewy compiles it to direct x86_64:
0.04, 0.06 and 0.22 seconds respectively, with peak RSS of 8.4, 12.3 and
35.1 MiB. Its outputs match the hosted-built writer exactly. Compiling that
fixture through the native C seed took 90.6 seconds. This separately checks
the writer's mutable buffer under native lowering, without a C backend in
the emitted fixture's execution route.

## Binary table reads and conversion ownership

With linear emission, native-pair attempt thirteen emitted generation one
normally in about 20.6 minutes, peaking at 24.2 GiB RSS. Its executable built
and passed the scalar check, but the first full-library check exceeded the
4 GiB gate. The runner stopped before generation two; there is still no
fixed-point certificate from that attempt.

A bounded sample found a concrete cause: each byte access in
`_casefold_word` copied the entire 24,912-byte case-folding table through an
implicit binary-to-array representation cast. The temporary arrays were also
missing from ownership classification. Even a minimal program using the
prelude reached 1.5 GiB RSS in 2.4 seconds through this path.

Read operands now borrow representation-compatible binary byte-array views.
Actual array values still materialize independent mutable storage, and fresh
binary/string array conversions are adopted and reclaimed at value and
lifetime boundaries. Binary literal descriptors are static, matching their
immutable data. This applies to ordinary binary reads, not just Unicode data.

`native_binary_views.dewy` checks implicit and explicit views, independent
mutable copies, and discarded byte/scalar array conversions. The previous
compiler fails its copy-counter check. Both output backends now pass the
zero-copy and bounded-retention checks; a direct-backend allocation measurement
reports exactly zero retained arena bytes. Dynamic string/view lifetimes remain unfinished and
are a separate issue; they were not the whole-table-copy path measured here.

A full-library workload also checks 1,000 `'AbC'.casefold` operations against
the actual included table. Native lowering copies zero payload bytes and
retains 408,000 arena bytes in the current string representation. The pair's
execution checks include this workload, with separate copy and retention
limits, before allowing generation two to start.

## Argument snapshots across raw-effect calls

Borrowing and reclamation need different call-graph rules. A transitive raw
effect can mutate storage visible to a caller, so it still prevents borrowing.
But an ordinary value call gives its raw callee an independent copy. Retaining
that inner copy does not require retaining the outer caller's argument snapshot.
Place arguments and lifted captures share storage and continue to propagate
retention. Direct raw access and unknown callbacks remain conservative.

This distinction matters for HIR readers: the explicit error-reporting fallback
in `hir.children` previously prevented reclamation throughout its caller graph.
Each unreleased arena snapshot then forced the next append to copy the graph.
`native_argument_lifetimes.dewy` checks repeated read/append operations, an
independent returned record, and deliberately retained raw record storage.
Through native lowering on both output backends, it passes the copy/retention
limits. For 512 appends, the direct backend measures 8 copied payload bytes
(down from 1,050,632) and zero retained bytes after a second run. The 8 bytes
come from the intentional mutation of a saved record's array field.

These bounded checks do not establish a completed bootstrap loop. Larger
compiler-reader checks and the native generation comparison remain required.

The actual `hir.children` and predicate readers also pass on both output
backends in `native_hir_reader_scaling.dewy`. The direct executable measures
zero copied array payload bytes for 512 read/append iterations and zero
retained arena bytes after repeating the workload. Native-pair verification
runs this check before allowing a second compiler generation. Compiling the
fixture with the C seed took 69 seconds for direct output and 85 seconds for
C output, peaking at 3.37 GiB. The seed built without C exceeded a 180-second
compilation limit on this larger fixture; that route still needs work.

The first compiler generated with this lifetime fix completed a minimal
full-prelude program in 26.2 seconds at 4.27 GiB RSS, and the 21-case integration
bundle in 31.4 seconds at 5.01 GiB. Both returned the expected result. The
initial 4 GiB guard stopped that integration run after compilation; separate
60-second, 6 GiB probes established these bounded peaks. This is a substantial
improvement over the preceding unbounded reader copies, but the full-prelude
cost remains high and the native fixed-point comparison is still pending.

## Callback argument lifetimes

The next larger native-reader check exposed retained snapshots in the bounds
pass's higher-order predicate traversal. Its leaf callback returns an optional
fact state and receives separate analysis data by place. Treating every such
call as an unknown storage escape prevents reclaiming the state and context
arguments, even when every possible leaf only reads those values.

Native storage analysis now merges all checked function literals compatible
with a callback parameter's signature. Borrowing and temporary reclamation
must be safe for every candidate; dispatch still calls the supplied pointer.
A compatible writer therefore prevents borrowing even if a particular caller
usually supplies a reader. This is an internal effect analysis, with no new
source-language feature or change to evaluation order.

The closed-program assumption applies only while all callable values originate
from checked literals. Raw access to callable storage disables this inference.
Records count conservatively because a branded descendant can contain extra
function-valued fields. Removing a quantity dimension while preserving the
underlying representation does not expose raw storage. Supporting separately
linked Dewy code or escaping closures will require revisiting this boundary.

Ordinary value conversions, including optional wrappers, preserve independent
ownership at argument, return, and assignment boundaries. Native storage
analysis can therefore distinguish those conversions from raw exposure; the
general semantic effect analysis retains its conservative default behavior.

The callback fixtures test merged reader/writer effects, optional return value
independence, raw-ingress fallback, and repeated read/append reclamation.
`native_predicate_path_scaling.dewy` additionally exercises the actual generic
`predicate_paths.refine` and conjunction traversal over a growing HIR arena.
Run positive callback performance gates separately from fixtures deliberately
exposing raw records: combining them legitimately disables the closed-program
inference for the resulting executable.

The bounded callback kernel passes through native lowering on both backends.
For 512 read/append iterations its direct executable measures zero copied
array payload bytes and zero retained arena bytes after a second run. The
larger predicate-path fixture copies 1,058,816 bytes with the preceding seed.
The full-prelude validation below additionally checks the real traversal;
native generation comparison remains a separate gate.

## Temporary container receivers

Iterator entry arrays borrow their owning set or dictionary. A fresh receiver
must remain alive for the loop arm and be released when that arm ends, including
an early return. Key/value unpacking also shares one evaluated dictionary;
evaluating the two entry views independently used to call its producer twice.

Container lowering now carries the temporary receiver's ownership through
iteration, views, membership, lookups, and mutation operations. Views and
lookup results preserve their independent payload before releasing a fresh
receiver. A found lookup releases its unused owned fallback. The hosted
compiler also releases enclosing statement temporaries before nested returns.

`native_container_receiver_lifetimes.dewy` covers these lifetimes, single
evaluation, nested key views, set algebra, early returns, and present/missing
lookups. It passes on both backends through hosted and native lowering; the
native direct executable retains zero arena bytes across 512 repetitions.

`native_analysis_scaling.dewy` groups the callback, actual HIR-reader, and
predicate-path checks so they share one prelude compilation per backend. It
remains separate from deliberate raw-exposure tests. Before the receiver fix,
the grouped predicate test already copied zero array payload bytes but retained
983,392 arena bytes per 512 visits. This larger gate still precedes any full
native generation comparison.

The updated grouped check passes on both output backends, taking 80.5 seconds
for direct output and 102.7 seconds for C output through the C seed. Its direct
executable measures zero copied/retained bytes for the HIR reader and zero
copied bytes with 352 retained bytes for 512 predicate visits. The 80 bounded
kernel executions and 23-case integration bundle also pass on both backends.
These checks justify a new compiler generation run; they do not certify a
completed native fixed point.

## Dynamic string construction scratch

The sixteenth pair attempt built generation one and passed the 23-case direct
integration bundle. The larger analysis compilation exceeded its 6 GiB guard;
a separate bounded diagnostic also exceeded 8 GiB. Allocation counters showed
live storage growing through checking and lowering, so generation two was not
started and that attempt produced no fixed-point certificate.

Every native dynamic string construction retained the UTF-8 validator's
optional growable offset array after copying its entries into the final
uint32 boundary table. The borrowed input descriptor also remained allocated.
Lowering now releases those scratch values after preserving the result, on
both valid and invalid input. Failed decodes release the unused byte snapshot;
integer interpolation uses fixed frame scratch for its decimal digits.

`native_string_scratch.dewy` keeps 256 completed 32-byte strings alive while
checking their construction cost and contents after allocator reuse. Native
lowering retains 92,232 bytes instead of 262,216 bytes for those results. A
second batch of 512 invalid decodes retains zero bytes. Both output backends
pass. This measures scratch reclamation: successful dynamic string backing
still has process-arena lifetime and needs a fuller ownership model.

The fixture also exposed a hosted formatting bug: unsigned 64-bit values
above the signed range were rendered as negative. Hosted interpolation now
uses an unsigned magnitude for every fixed width, covering `uint64.max` and
`int64.min` with the same digit loop. This changes no µDewy evaluation rules.

The accompanying Unicode fixture keeps concatenated clusters, joined strings,
and decoded byte arrays across later constructions. It also caught a hosted
array-layout mismatch: a copy into a runtime-length parameter treated an
optimized flat buffer as a descriptor. Dynamic copy dispatch now consults the
known physical extent first, preserving that buffer's layout even when its
source-level length fact has been widened.

## Native immutable string ownership

The seventeenth pair attempt passed all first-generation integration, analysis,
and invocation checks on both targets. Its second-generation compilation still
crossed the 35 GiB guard during lowering. Allocation counters showed live
storage accounting for most of that memory, even after validation scratch was
reclaimed. The bootstrap loop was not closed by that attempt.

Native dynamic strings now retain shared immutable backing through private
48-byte descriptors. The owner word names a control containing a reference
count and the original byte/boundary allocations and sizes. Copies retain the
control; slices and grapheme views retain it even when their pointers shift.
The last release returns the backing to the arena. Literal descriptors have
owner zero and need no allocation or release. Raw exposure pins storage
conservatively. These runtime helpers are Dewy code using the existing arena,
so this storage path also works through the direct µDewy backend.

Ownership follows ordinary value boundaries, including records, arrays,
optional cells, calls, returns, default arguments, and replacements. String
operators hold their operands across later evaluations and release them after
materialization. Dictionary probes release temporary keys; a replacement
releases the unused incoming key. Iteration releases each grapheme view before
advancing and releases the final view when leaving the arm. UTF-8 decoding
owns an independent byte allocation instead of retaining an anonymous array
snapshot; command-line decoding also copies the process-owned argv bytes.

Default arguments exposed another lifetime gap: the callee created the default
but did not reclaim it. Cleanup now uses the existing ABI presence flag to
release a missing default without releasing a supplied borrowed argument.
Boxed or reassigned aggregate parameters own a private local snapshot, so a
place into that local cannot release the caller's argument descriptor. Their
cleanup runs on explicit returns and implicit results, after preserving the
returned value.

`native_string_lifetimes.dewy` exercises aliases, returned parameters, slices,
record and array replacements, optional values, decoding, grapheme iteration,
joins, dictionary keys, defaults, and parameter rebinding. Before this work,
512 visits to its original workload retained 2,125,824 bytes. String ownership
alone reduced that to 86,016 bytes: one 168-byte default per visit. With default
and parameter cleanup, the expanded workload retains **zero bytes in each of
two batches of 512 visits**. The lowering driver passes this workload, string
construction scratch, argument lifetimes, and temporary container lifetimes on
both x86-64 and C. Full seed and self-bootstrap verification remain separate
gates; these bounded results do not constitute a fixed-point certificate.

The hosted backend retains string regions for frame-lifetime values. The
Phase 0 campaign also adds shared immutable backing for its owned arena
strings: the first snapshot promotes unique ownership to a shared count,
and later copies allocate only a descriptor. Borrowed, frame and pinned
strings retain the copying fallback. Raw exposure detaches shared backing
before pinning it. This is the hosted representation's own ownership
protocol; its control layout is not the native runtime's control layout.
Both release their buffers when the last tracked owner dies.

The checks cover the same value semantics; the stricter retention budget above
is checked on the native implementation. Reference counts remain provisional,
and the longer-term question of predictable, ideally zero-cost ownership at
the start of this document remains open.

## Completed native fixed point (2026-09-14)

The eighteenth pair attempt completed. The first and second generations of
both compilers are byte-identical; the emitted Dewy µDewy sources also match
at 96,688,561 bytes. All first-generation execution gates passed before
generation two began. `tools/bootstrap_native.sh --target c` took 56 minutes
23 seconds in total with GCC and eight LTO jobs. Generation builds took
1,494 and 1,521 seconds respectively; the remaining time was execution checks.

The Dewy process building generation two peaked at a sampled 9,421.9 MiB
(about 9.2 GiB), versus the previous attempt exceeding its 35 GiB guard.
Its checking/lowering/emission took approximately 1,318 seconds. The initial
hosted-produced native seed took approximately 1,292 seconds and peaked at
23,432.4 MiB. Sampling was every five seconds; these are process RSS samples,
not precise allocator high-water measurements. The original seed still has
the hosted backend's string-region behavior; subsequent generations use the
new native string ownership helpers.

The new compiler's bounded direct integration compilation peaked near
428 MiB instead of 1,541 MiB; grouped actual analysis peaked near 826 MiB
instead of 3,946 MiB. Those checks were slower in CPU time (roughly 25 versus
20 seconds and 80 versus 50 seconds in the sampled runs). The change solves
the memory growth that prevented the bootstrap; it does not solve compile
latency generally. Native checked-prelude caching, cheaper pure type queries,
less generated code, and predictable ownership remain performance work.

The full no-C self-bootstrap remains a separate verification goal. Broader
language parity also remains incomplete; see the observed corpus blockers in
[IMPLEMENTATION.md](IMPLEMENTATION.md#hosted-parity-gaps).

### Type arena lookup

`semantic/ty.dewy` owns an insertion-ordered description array and its key
index as a single `Table` value. Read-only APIs take that table; `intern`
inserts, `truncate` rolls back a suffix, and `resolve_alias` changes a target
without changing its key. A fork copies the array and index together under
ordinary value semantics. This removes the process-global interning hint and
the full-table scan that previously followed each new-key miss. The dependent
result bound names `nodes.entries.length`, preserving the checked arena-handle
contract. Benchmarks and integration limits are recorded in
[PHASE0_MEASUREMENTS.md](PHASE0_MEASUREMENTS.md#type-interning-index-owned-by-the-arena).

## Array reads across index effects

An array read evaluates its receiver before its index. Saving a descriptor
address is insufficient when the index replaces or mutates the source:
that descriptor or its backing storage can change before the element load.
Borrowing analysis now identifies these reads and acquires an independent
array descriptor before index evaluation. The existing COW rules preserve
its data, and the read releases the snapshot after keeping its result.
Aggregate elements already retained by this read are adopted by the next
value boundary; copying them again would abandon the first owned result.

The analysis shares route/effect checks with call arguments. Pure compiler
operators keep the cheap borrow, while source functions or callbacks with
the same spelling retain their ordinary effects. Unknown callbacks and
potentially aliasing place routes remain conservative. The focused native
lowering fixture covers replacement, element writes, append, callbacks,
global writes, aggregate results, exactly-once index evaluation, and zero
retained bytes over repeated calls. Its arithmetic-index loop allocates
zero bytes. Direct and C execution pass. The full native CLI built from
`1ce9c366` now passes all 12 nested-length contract cases against the frozen
hosted compiler, including the original array-snapshot failure. This is a
contract integration gate, not a refreshed full corpus or fixed point.

## Shared array relocation

Both lowerers now share array-growth code by stored element width (1, 2,
4, or 8 bytes). Growth relocates bits into disjoint storage; aggregate
elements are handles, so this operation neither clones nor releases their
payloads. Typed copy-on-write detachment remains separate. Native growth
also moves a complete stored element per iteration instead of copying
each byte separately. Pinned buffers retain their existing lifetime rule.

Hosted ownership, record, and dictionary-width gates pass on direct x86_64
and C. The native lowering driver passes explicit growth across all widths,
record/array/string-view elements, reserve argument evaluation, raw-exposed
growth, dictionary widths, and effectful index snapshots on both routes.
The native dictionary-width fixture shrank from 307,284 to 214,901 bytes
of emitted µDewy after sharing relocation. These are bounded lowering
checks; the next full compiler integration remains a separate gate.

## Bounding C optimizer work

Profiling the frozen `1ce9c366` compiler's generated C isolated a 141-second
LTO partition containing module initialization. Alias queries and partial
redundancy elimination accounted for almost all of it. Disabling that pass
for the saved partition reduced it to 3 seconds; relinking produced the
same `t0` µDewy bytes and similar native compile time (22.3 versus 22.9 s).

Both `-fno-tree-pre` and `-fno-code-hoisting` are needed for ordinary GCC
invocations: [GCC's pass gate](https://github.com/gcc-mirror/gcc/blob/master/gcc/tree-ssa-pre.cc)
enables the shared analysis for either optimization. Disabling only PRE
hit a 130-second cap. With both disabled, the frozen C built in 88.14 s
versus 196.56 s with the usual `-O2 -flto=8`; its native `t0` invocation
took 22.06 s and emitted identical µDewy. These were exploratory backend
runs, with short fixture checks overlapping part of the candidate builds.
The remaining `-O2` optimizations stay enabled.

`DEWY_BOOTSTRAP_GCC_NO_PRE=1` opts into these two switches for C bootstrap
builds. The script probes support before generation one, records the option,
and rejects a resume with different options. It combines with the existing
`DEWY_BOOTSTRAP_LTO_JOBS` option. Other routes retain their usual defaults.

An isolated integration build of frozen `5d67b83e`, including the nominal
graph and shared array-growth helpers, used these options with GCC 16.2.1,
eight LTO jobs, and ccache disabled on the recorded i7-6700 machine. The full
hosted invocation took **231.74 s**: checking 66.45 s, lowering 56.48 s,
emission 4.49 s, and downstream compilation/linking 98.59 s. Peak process
RSS was 2,228,984 KiB; emitted µDewy was 33,799,460 bytes, SHA-256
`f0202296b580a3595cd2595337541dc115908614fb4aa8184764b35d9a3f8815`.
An isolated native build of the pinned `t0` module took 22.21 s, peaked at
2,042,992 KiB, and emitted 3,509,937 bytes. These measurements use fresh
processes and empty build directories, with OS page caches uncontrolled.
The under-60-second full-build target and a refreshed fixed point remain
open; this checkpoint does not certify a new release.

## Structured native fact indexing

The native proof store now keeps dense entries and integer hash buckets.
Fact kinds, complete binding ids, projections, and offsets decide equality
inside a bucket; a hash collision cannot grant or discard evidence. Removal
moves the last entry and repairs its bucket position. Value copies retain
both parts of the state. Diagnostic formatting remains available through
`facts.describe`, with the same text used by the hosted differential tests.
This is an internal representation change, using existing language features.

For 1,000 repetitions of five constructed fact lookups, allocated bytes fell
from **5,424,000 to 1,120,000** in hosted-generated code, and from
**10,712,000 to 1,920,000** through the full native CLI. Both native kernels
were compiled by the same frozen `5d67b83e` seed. These counters measure
allocation, not peak RSS or a full compiler speedup.

The explicit collision/removal/snapshot fixture passes through hosted direct
x86_64 and C, and through the full native CLI/direct backend. Nineteen
focused tests pass across the index, state operations, relational and affine
facts, transfers, predicates, obligations, bounds, and slicing. Existing
expected-result and Python differential comparisons remain the oracle;
changing the index did not change the proof rules. Full self-build timing
with this representation is still a separate integration checkpoint.

## Optional profile-guided C seed

`tools/profile_dewy_seed.sh` builds a separate optimized variant of a Dewy
compiler whose C output already exists. Instrumentation, training, and profile
use are ordinary GCC operations; training runs the native Dewy/µDewy pair.
It does not change either language or replace bootstrap verification.

```sh
DEWY_UDEWY=/absolute/path/to/native/udewy \
DEWY_LIBRARY_ROOT=/absolute/path/to/pinned/library \
tools/profile_dewy_seed.sh /absolute/path/to/generated/main.c \
    /absolute/path/to/new/profile-build /absolute/path/to/bootstrap/main.dewy
```

The output contains `compiler`, the instrumented binary, counter data, command
and input hashes, and separate build/training logs with timings. Multiple
training sources may be supplied. Missing counters or mismatched profiles
fail the build. The default uses GCC, eight LTO jobs, and the existing PRE/
code-hoisting exclusions for these large generated translation units; select
the compiler with `DEWY_PGO_CC`, job count with `DEWY_BOOTSTRAP_LTO_JOBS`, or
restore those passes with `DEWY_BOOTSTRAP_GCC_NO_PRE=0`.

The first experiment built the full compiler in 54.894 seconds using the
optimized seed, versus 61.487 with the corresponding ordinary C seed, with
identical emitted µDewy. Instrumentation compilation cost 92.025 seconds,
training 78.251 seconds, and profile-use compilation 85.826 seconds. Those
are seed preparation costs, separate from the measured compiler invocation.
This is an optional C accelerator; performance of a complete bootstrap
without C acceleration remains a separate goal. Details and verification
limits are in `PHASE0_MEASUREMENTS.md`.
