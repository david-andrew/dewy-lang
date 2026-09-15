# Phase 0 performance campaign

The acceptance target remains a complete compiler executable build in under
60 seconds through **each** implementation. The module measurements below
are bounded development gates; they do not establish that full-build target.
See [ROADMAP.md](../ROADMAP.md#dedicated-performance-campaign).

## Reproduction and isolation

`tools/measure_compiler.py SOURCE --output NEW_DIRECTORY` measures the hosted
CLI, including its in-process µDewy backend. Add `--native-executable PATH`
and `--udewy-executable PATH` to measure the native pair. Each run uses a fresh
process and empty artifact directory. OS page caches are uncontrolled.
`--profile` adds hosted cProfile data; its elapsed times include profiling
overhead and must not be compared to unprofiled acceptance measurements.
JSON records retain source/revision identity, options, wall time, maximum
process RSS, generated-source sizes/hashes, and hosted phase timings. Maximum
process RSS is not the sum of simultaneously resident child processes.

`tools/check_compiler_parity.py --native-executable PATH --udewy-executable PATH
--output NEW_DIRECTORY` checks each existing end-to-end fixture independently.
Compilation and execution results are separate; expected exits and output are
checked before comparing implementations. `--cases FILE` also accepts negative
cases, and `--hosted-root PATH` pins a source snapshot while development
continues. A timeout, crash, or backend failure does not count as a successful
language rejection. Exact diagnostic wording is not part of parity.
The default inventory includes ten isolated rejection fixtures for names,
initialization, types, bounds, const mutation and stored contracts. Both
baseline compilers reject all ten at the language-checking boundary.
Expected runtime reports use explicit `diagnostic_stderr` fragments from the
fixture expectations, checked independently along with exit/stdout. Those
reports may differ in formatting or additional notes; raw stderr differences
remain in the record. Ordinary program stderr still requires exact bytes.

## Initial bounded baseline — 2026-09-14

Machine: Intel Core i7-6700, 3.40 GHz, Linux x86-64. Python 3.14.7, GCC
16.2.1, GNU assembler/linker 2.46.1. Source revision `18fadc66`, module
`dewy/bootstrap/parser/t0.dewy` (SHA-256
`b884a751e3e46eb4779d0f774651237eee985eacdf7630c08bc6532473a88847`).
Native compiler: the verified eighteenth pair, Dewy executable SHA-256
`5140aa2f2bfb5b2a09656d33c59db8f631c49d14e8b1c90ca7adaa99a3243ae8`.
Both invocations produce a direct x86-64 executable; the native compiler
itself was built through C. Default CLI options: hosted emission includes
location markers, native ordinary compilation does not.

| Implementation | Complete invocation | Checking | Lowering | Emission | Backend | Maximum process RSS | µDewy bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hosted baseline | 34.74 s | 15.51 s | 11.01 s | 2.59 s | 4.71 s | 274,828 KiB | 5,675,282 |
| Native baseline | 61.70 s | — | — | — | — | 941,620 KiB | 5,984,229 |
| Hosted representation query cache | 25.21 s | 15.11 s | 3.67 s | 0.87 s | 4.60 s | 275,424 KiB | 5,675,291 |
| Hosted traversal batch | 23.56 s | 13.40 s | 3.47 s | 0.86 s | 5.01 s | 273,076 KiB | 5,675,288 |
| Hosted lexer batch | 21.20 s | 10.53 s | 4.16 s | 0.92 s | 4.67 s | 273,148 KiB | 5,675,273 |

These are single samples, with other work on separate CPUs; use repeated
samples for close comparisons. The nine-byte output difference is entirely
the embedded benchmark directory names in three `$include_bytes` paths.
After normalizing those directory names, emitted text is identical.

The first batch caches representation queries by input identity during
lowering/emission, object layouts and union tags per lowerer, and resolved
source paths per emission. Checked type objects remain strongly referenced
until the scope ends. No query cache spans checker mutations, alias resolution,
brand registration, or compilations. Regression checks cover failed-scope
cleanup, mutable unions, identical uncached output, expected execution, and
array-sharing budgets on direct and C output routes.

The traversal batch caches class field metadata, preserves unchanged subtrees
during module renaming, and walks the prelude dependency graph once per
reachable declaration. Both compilers skip predicate-read traversal when the
invalidated-binding set is empty. Output again matches the original after
directory normalization. Prelude cache restoration, effect summaries, and
native short-circuit proof-path checks pass (22 focused tests).

The next hosted profile shifts attention to cold prelude checking, repeated
analysis traversals, and the µDewy tokenizer. Native phase profiling and
checked-prelude caching remain separate work. The initial full native
self-build baseline remains the approximately 25-minute generation recorded
in [PERFORMANCE.md](PERFORMANCE.md#completed-native-fixed-point-2026-09-14).

## Shared native record operations

The verified native compiler emitted 96.7 MB for its own source: 19.7 MB was
record copy helpers and 7.3 MB release helpers. Parent views repeatedly
expanded every descendant's concrete fields, including inline nested records
and union cells. Native lowering now shares family dispatch separately from
exact field operations. Arena-free copies stay in their caller's frame.

The twelve-level `native_record_family_helpers.dewy` kernel drops from
281,377 to 124,977 bytes of µDewy (56% smaller), with checking/lowering/emission
through the dedicated direct lowering driver falling from 6.27 to 4.38 seconds.
Both versions execute correctly through direct and C backends. Its committed
160 KB output budget catches reintroducing the expansion. Another new kernel
checks descendant copies through nested records, arrays and optional cells;
128 repeated scopes retain zero arena bytes. Thirty-nine existing record,
brand and reclamation cases also pass on both output routes. These are kernel
results, not yet a measurement of the full compiler's new generated size.

## Lexer copying and next integration seed

Sampling the full hosted build exposed a source suffix copy for every token
class probe. Sharing that suffix across probes, selecting longest matches in
one pass, and using offsets for inner delimiter tests reduces tokenization of
`bootstrap/backend/udewy/lower.dewy` from 44.83 to 3.83 seconds. Both versions
produce exactly the same 70,656 token kinds, texts, spans and indices (combined
SHA-256 `ce923f4d2e8bd993c82d280c10a68695ebe21c8ef8a728cc5dc2834e28fdaedf`).
The µDewy tokenizer also groups ordinary symbol probes by initial character,
retaining longest-match order and contextual token handling. Forty-nine lexer,
literal-boundary and µDewy precedence/type tests pass. These changes preserve
µDewy's conditional-only short-circuit rule.

A full hosted C build of revision `8116d279` successfully produced the next
native test compiler: 113.7 MB of µDewy and 215.3 MB of C. Its initial sampling
profiler substantially perturbed checking and interrupted the measurement
parent; the compiler child completed successfully. This is an integration
artifact, **not a clean full-build timing**. Recorded phase times include
198.5 seconds checking, 103.2 lowering, 17.4 emission, and 428.6 backend; maximum
process RSS was 6,735,356 KiB. The build bypassed ccache and used GCC with
eight LTO jobs.

That hosted-built seed compiles the t0 module in 71.71 seconds, producing
4,583,067 bytes of µDewy (23% less than the verified native baseline), with
maximum process RSS of 3,571,432 KiB. The seed's storage behavior differs from
the native-built baseline, so this does not establish a runtime improvement
for the helper batch: generation provenance must accompany native timings.
It has not yet passed a new native fixed-point verification. The sub-minute
full-build target remains open.

## Hosted record-family helpers

The hosted backend now also selects shared concrete-field helpers for arena
copies and releases. Non-moving result writes reuse ordinary arena copies
when their fields need no caller-prepared fixed-array storage; move/adopt and
prepared-array cases retain their separate rules. The guarded twelve-level
inheritance fixture shrinks from 2,544,010 to 607,930 bytes (76% smaller), with
both outputs returning the expected result through direct and C backends.
The new hosted output budget is 700 KB, including reachable runtime code.
Another execution case covers fixed arrays nested in both base and descendant
fields, so sharing cannot silently discard prepared destination storage.
Sixty-six focused ownership, array-sharing, release and default-argument tests
pass alongside those two new cases.

The inheritance fixture now also guards its variable-length indexed reads
and writes, allowing the complete hosted checker to validate it. Its native
lowering-driver output is 146,253 bytes, still below the existing 160 KB gate,
and executes correctly on both routes. The earlier 124,977-byte native kernel
measurement predates those guards; compare like fixture revisions.

## Isolated parity repair: lenient set pop

The accepted-program inventory exposed a native crash in `sets.dewy`.
`pop(key default=none)` returned bare payloads on both branches instead of
the optional cell its checked result type requires; discarding a missing
result then dereferenced zero during cleanup. Native lowering now packs
both alternatives and releases an unused packed default with its result
type. The isolated fixture crashes through both old output backends and
returns 42 through both updated backends. The hosted version also returns
42. Cases cover present/absent/discarded integer and string results, eager
defaults, and zero retained arena growth over 64 repeated scopes. A fresh
full-native corpus run remains an integration gate.

## Full-build checkpoint and array copy expansion

The complete `e305d2e6` source snapshot (including the imported
`tools/dewy_test.dewy`) builds through hosted Python and GCC in 667.44 seconds:
83.59 checking, 107.57 lowering, 18.87 emission, and 451.94 in the backend.
Maximum process RSS is 6,948,352 KiB. A short nonblocking 5 Hz sample spans
late lowering, emission and µDewy tokenization; other kernel tests overlap
the C build. Treat this as an integration measurement, not a controlled
acceptance run. Its native test seed builds t0 in 69.40 seconds and emits
4,275,940 bytes, with maximum process RSS 3,554,960 KiB. It is not a newly
verified native fixed point.

The 118.9 MB full hosted output includes 12.1 MB of source-location comments
and 12.7 MB of variable comments. The longer snapshot paths explain much of
the increase from the earlier build; record helpers account for only a small
part of the remaining 94 MB of code. Most code sits in ordinary functions.

Hosted lowering now shares complete non-moving dynamic-array copies,
including their wide-union fallback loops. Both paths already return
arena-owned descriptors. Frame-rooted records can also share their field
operations when every nested allocation already has arena lifetime; fixed
arrays and moves retain their distinct rules. The t0 module emits 5,466,153
bytes in 21.06 seconds (a bounded sample), so this alone is not the large
full-build improvement still needed. A 24-caller, twelve-alternative union
array kernel drops from 946,621 to 729,334 bytes, under an 850 KB gate.

That kernel also exposed an older hosted leak when overwriting optional or
union array elements. The replacement now releases the old cell and its
active payload after detachment, while respecting pinned containers. The
native implementation already reclaimed these cells. Both implementations
now return the expected result with zero growth across repeated kernel
scopes on direct and C backends; additional cases cover self-replacement and
pinned old-cell pointers. Sixty-nine existing ownership, sharing, string,
array and object tests pass with array helper sharing enabled.

## Static literals and shared value dispatch

The hosted ordinary CLI now omits source/variable debug metadata. `dewy debug`
retains both, in its existing separate cache artifact; the codegen API keeps
its explicit/default debug controls. Literal bytes, packed grapheme offsets,
and descriptors are emitted as relocatable static data. Descriptors remain
separate per lowering site. This removes repeated initialization stores;
it does not add a source-level interning rule. Repeated large ASCII, combined
Unicode graphemes, and empty literals pass direct and C execution checks.

The same t0 module drops from 5,466,153 bytes to 4,299,559 bytes and 19.65 s
with static literals and ordinary debug metadata omitted. Sharing string
release, cell-payload release, and union-copy dispatch reduces it further to
3,697,941 bytes, with 230,500 KiB peak process RSS. The latter sample took
20.21 s (11.57 checking, 3.42 lowering, 0.55 emission, 3.71 backend) while
other validation was running; use its output size, not the small wall-time
difference, to compare these batches. This is still a module benchmark,
not achievement of the full-build target.

Copy helpers retain distinct prepared/unprepared and move modes. Copies
that might construct fixed-size storage in the caller's frame remain
inline. Release helpers only dispatch ownership and reclaim existing
storage. The 24-caller union-array kernel is now 309,077 bytes, with a
400 KB regression budget (formerly 729,334 bytes after array-helper sharing).
Thirty focused release/ownership tests and twenty-five copy-helper tests
pass. The broader union/recursive/ownership group passed 109 cases and
exposed two fixed-array temporary lifetime failures; after the lifetime fix,
all thirteen record/result regressions pass, including those two failures.

Array element ownership is now consistent on the hosted side: literals,
copies, and prepared array results own their record roots as well as fields,
even when the pointer buffer is frame-backed. Replacing an element releases
the old value after materializing its replacement; raw exposure preserves
pinned old elements. Scope exit releases copied record roots, and temporary
fixed-array results release their elements after reads. The combined test
covers inheritance, fixed results, self-replacement, preserved snapshots,
repeated-scope reclamation, and raw pointers without assuming brand layout.
It also found a native omission: index replacement released pinned elements.
The corrected native lowering passes the same kernel on direct and C routes.

Artifacts: `phase0-performance/host-static-literals-t0`,
`host-cell-helpers-t0`, `shared-release-union-kernel.udewy`,
`static-literal-*-gates.log`, `record-replace-complete-gates.log`,
`pinned-replacement-native-gates.log`, `shared-release-gates.log`,
`shared-cell-copy-gates.log`, `shared-cell-ownership-gates.log`, and
`fixed-result-lifetime-gates.log`. The reusable native lowering driver is
recorded in `pinned-replacement/driver-path.txt`; it includes the pinned
replacement fix, but is not a new full native compiler or fixed point.

## Full build checkpoint: shared value helpers

A pinned `3e15bcfd` snapshot (including the compiler packages, library, tools,
and VERSION) builds the complete C-backed compiler executable in **479.40 s**:
84.26 s checking, 99.98 s lowering, 11.14 s emission, and 278.02 s in the
backend. Maximum process RSS is 4,653,972 KiB. Its 69,050,267-byte µDewy source
has SHA-256 `6f9fd8fa964712f849aca7c850e1aebccfebe14f6fbf4892d48ee7089024085f`.
The preceding `e305d2e6` checkpoint took 667.44 s and emitted 118,865,274 bytes.
This is about 28% less wall time and 42% less generated text; normal debug
metadata is part of the older text. Both checkpoints bypass ccache and use
GCC with eight LTO jobs. Other validation overlapped these builds, so these
are integration observations rather than controlled acceptance samples.
A late, nonblocking profiler attempt collected no samples while the Python
parent waited on C compilation.

The resulting hosted-built compiler completes the native t0 invocation in
66.22 s, producing 4,276,283 bytes, with 3,182,688 KiB peak process RSS. This
remains well outside the desired native performance; no new native fixed
point is claimed. Artifacts are `host-full-value-helpers` and
`native-value-helpers-t0` under the campaign artifact directory.

## Bounds query scope

Syntactic predicate read/write queries and declared-type numeric intervals
are now cached per bounds validator. Checked HIR structure and declared types
remain stable within this pass; recording a constant index does not change
its binding reads/writes. The constructing checker keeps uncached queries,
and state-dependent interval evaluation remains uncached. Fifty-one focused
bounds, predicate invalidation, width and refinement tests pass. A cache-on /
cache-off t0 comparison emits identical text (3,697,407 bytes, SHA-256
`defff774b4bc4991432bbdb8235f9f70fdd22f76617ea7609201b3d4e34a875e`).
Its warm checking samples were 2.29 and 2.27 seconds respectively: no wall-time
improvement is established by that small sample. The ordinary isolated-cache
CLI sample took 19.10 seconds; it must not be compared with the warm prelude
comparison as the same workload. See `bounds-query-gates.log`,
`bounds-queries-{cached,uncached}.log`, and `host-bounds-queries-t0`.

## Dependency worklists

Hosted parameter effects now discover the summaries they read and revisit
only affected callers. HIR discovery visits shared nodes once (overload
alternatives can legitimately reuse a function literal). Default expression
bodies, including function literals stored in defaults, are included in
hosted discovery and summaries, as in the native analysis.

Native parameter effects build reverse place-call dependencies, while
capture propagation and ambient-write propagation use their own reverse
edges. Value boundaries, callback resolution, lexical-local filtering,
recursive route normalization, and the existing conservative raw-storage
rules are preserved. Worklists change scheduling, not the effect vocabulary.

A 200-function hosted forwarding-chain regression establishes the expected
mutation at every parameter with fewer than 600 summary visits; the former
whole-program solver required over 40,000. Native differential checks include
a 32-function chain, recursion, overload sharing, unknown callees, and default
expression effects. The 128-function native capture/ambient kernel includes
a cycle and a disconnected function. Built by the same hosted compiler, the
old source takes 147–150 ms to analyze it; the worklist source takes 31–33 ms
(three runs each). Its complete emitted harness grows from 20,048,997 to
20,533,952 bytes, so this optimization trades a little implementation code
for less repeated execution. Both versions return the expected result.

The three existing native effect/borrowing gates pass, the expanded capture
kernel passes, and the final 34-test group covers hosted effects, native
summary parity, array sharing, and local/loop captures. Two isolated hosted
t0 CLI invocations take 16.80 and 16.95 seconds, with lowering at 2.93 and
2.85 seconds and roughly 237,260 KiB peak process RSS. These measurements
precede the final default-expression discovery addition; a full self-build
with the worklist batch is still pending.

Artifacts: `host-worklists-t0`, `analysis-worklist-comparison-complete.log`,
`effect-worklist-chain-gate.log`, `capture-worklist-complete-gate.log`, and
`worklist-final-gates.log`. The old/new kernel sources and emitted programs
are retained as `analysis-worklist-{old,new}.{dewy,udewy}`.

## Scalar getter projections

Both lowerers can specialize a direct record-returning getter when its caller
immediately reads a fixed-width integer or boolean field. The variant keeps
the original argument/default/capture ABI, effects, guards, and cleanup, but
reads the scalar before the whole record would be copied. No pointer or view
escapes the callee. The first rule accepts one terminal route read; constructors,
indirect calls, aggregate fields and multiple return paths retain their usual
lowering. Native implicit block results also keep the fallback for now. Native
HIR may share arena nodes, so a read reused in the unchanged prefix is excluded.

`native_scalar_projection.dewy` performs 3,000 reads from a record family whose
descendants contain owned arrays and strings. Hosted projection uses **zero
arena allocations, copied bytes and retained bytes**; disabling the rule in
the same compiler allocates more than 100 KB, while still reclaiming it. The
native lowering kernel reaches the same zero budgets. Expected-result checks
cover lazy defaults, argument order, captures, indirect dispatch, constructor
effects, failed guards and mutation of private arguments on direct and C routes.
The native kernel driver enters below fact validation and runtime-report
installation; its adapted plain-index guard checks are not a substitute for
full-compiler validation. Ordinary raw-effect borrowing restrictions remain
intact. In particular, a raw failure syscall conservatively causes argument
snapshots, so the valid-input allocation gate uses a divergent guard instead.

The broader latency evidence is modest. A 150-function checking/lowering
driver workload takes 4.97/4.88/4.84 seconds with the preceding driver and
4.71/4.68/4.75 with the worklist/projection driver. Both emitted executables
return 42, and emitted size is unchanged at 172,202 bytes. This comparison
includes the worklist batch and precedes the final cheap rejection path for
ordinary field reads; it does not isolate projection's wall-time effect.
Two hosted t0 builds take 18.46 and 17.70 seconds and emit 3,697,956 bytes.
This module does not substantially exercise projected getters, and no hosted
compile-time improvement is claimed. One small native gate overlapped the
first sample. A new full compiler checkpoint is pending.

Artifacts: `scalar-projection/{native-complete-gates,hosted-regressions,
final-gates,driver-comparison}.log`, its comparison script and emitted kernels,
and `host-projected-getters-t0`, under the campaign artifact directory.

### Full projection checkpoint

The complete C-backed compiler built from the projection/worklist snapshot
in **450.51 s**: checking 78.29 s, lowering 85.83 s, emission 10.29 s, and
backend 269.88 s. Peak process RSS was 4,727,208 KiB. It emitted 69,976,136
bytes of µDewy (SHA-256
`c4d12746daa407cd53752cc84af570a7af50d33052c704d8c77b35f8ecd37534`),
which the C backend expanded to 164,365,560 bytes. Short nonblocking profile
samples and small validation jobs overlapped this checkpoint; it remains an
integration observation. The full-build target is not met.

That executable passes both projection fixtures through the **full native
compiler**, including checking, fact validation and runtime-report installation.
Both return 42; the allocation fixture still reports `0 0 0`. Native t0 takes
65.55 s and emits 4,276,283 bytes, with 3,182,356 KiB peak process RSS. Hosted
regressions overlapped the first portion, and this result does not establish a
close latency improvement over 66.22 s. Artifacts: `host-full-getter-projections`,
`native-getter-projections-t0`, and `scalar-projection/full-native-gates.log`.

## Stable brand numbers and record preparation

Hosted lowering now computes the complete brand numbering once per lowerer,
as native lowering already does. The numbering itself builds parent-to-child
adjacency once, preserving registration order, preorder ranges and postorder
table insertion. Each new compilation gets a fresh table after checking has
finished registering brands. Runtime type tests, constructors, type values
and record copy/release dispatch reuse it.

A controlled 256-brand lowering/emission kernel, using the same checked HIR
and other caches, fell from **2.85/2.57 s to 0.195/0.192 s**. The former lookup
pattern rebuilt the complete forest 1,026 times; the new lowerer builds it
once. All four outputs are identical: 94,006 bytes, SHA-256
`bc4255a27582eb191cbe06a84dcccd7c44e88fb7ef5c28ca5d1341b613d9a69c`.
This is a bounded query result, not a full-build speedup estimate.

The stable per-record query for caller-prepared fixed-array storage is cached
too. Records needing none skip preparation altogether; scalar fields no
longer construct address HIR that is immediately discarded. Fixed-array and
nested prepared storage retain their allocation and lifetime rules. Nineteen
final query, record, object-array and temporary-lifetime regressions pass,
including fresh brand tables across successive programs. Artifacts:
`compare-brand-queries.py`, `brand-query-comparison.log`,
`brand-query-complete-gates.log`, and `brand-preparation-gates.log`.

## C toolchain experiment

Homebrew Clang 22.1.8 at `-O1` did not finish compiling the projection
checkpoint's 164 MB generated C within a 300-second limit. No executable
or runtime comparison resulted, and the normal GCC route is unchanged.
A small native validation compile overlapped the first 32 seconds. The
timing wrapper's peak RSS does not include the terminated compiler child,
so it is not a usable memory measurement. Artifacts:
`c-toolchain/clang-o1{.log,-time.txt}`.

## Preserve normalized type subtrees

Hosted negation normalization now retains record fields, arrays and other
type structures whose normalized children are unchanged. It revisits children
on every query, including mutable union lists; this is not a cache over
changing checker state. Metadata on rebuilt fields and records is preserved.

A 1,000-query nested-record kernel takes **3.76/3.61 s before and
0.87/0.88 s after**, producing equal types. The unchanged path needs no
dataclass replacements. The final normalization/query group passes ten
checks; the preceding broader group passed 24 checks, with one test-only
API-name error corrected in that final run. Artifacts:
`normalization-{comparison,final-gates,gates}.log` and
`compare-normalization.py`. These are bounded results, not a full-build
speedup claim.

## Active union records and result lifetimes

Hosted prepared union cells now allocate record roots only for the active
alternative when its family needs no caller-prepared fixed arrays. Fixed
arrays, records containing them (including descendants), and the no-arena
route retain prepared trees. Copies still own independent values. A dead
call result with no frame trees transfers its payload and clears the old
cell; conversions requiring copies release the temporary after the copy.

The lifetime audit also fixed result-cell forwarding being attempted for
container methods, and added the missing arena-element to frame-result
conversion for popped union cells. A repeated replacement/retag/pop kernel
formerly retained 74,400 bytes per 300 iterations with prepared records;
the first handle experiment retained 84,000. The final hosted version passes
the 4 KiB repeated-run budget, alongside mixed fixed/dynamic union storage.
All 62 selected union, sharing, record and popped-element checks pass.

The preliminary representation-only t0 comparison shrinks emitted text from
3,697,407 to 3,606,809 bytes (2.5%). Its 4.7–5.4 second in-process compilation
samples show no reliable latency improvement and precede the lifetime fixes.
The native kernel initially passed the value checks but retained 40,800
bytes per 300 iterations. Representation casts now use the owned-cell
conversion path already used for logical casts, retiring fresh source cells
and any intermediate retagged cell after preserving the result. The same
kernel now passes the 4 KiB budget on both direct and C routes. Capture and
wide-range regressions pass with that native lowering driver too; full native
driver validation remains part of the next integration checkpoint.
Artifacts: `active-union-{t0,final-gates,lifetimes}.log` and
`active-union/{probes,native-gates,native-retention-probe}.log`, plus
`owned-cell-casts/{gates,boundary-gates}.log`.

## Shared array release operations

Hosted array cleanup now shares the complete owner/refcount dispatch and
recursive element cleanup once per element representation, matching the
native lowerer's existing helper strategy. Descriptor evaluation stays at
the call site; release ordering, pinned storage and descriptor ownership
remain unchanged. Twenty selected sharing, popped-element, union-retention
and record-family checks pass on direct and C routes.

With all other current changes held fixed, outlining reduces t0 output from
**3,619,080 to 3,283,675 bytes (9.3%)**. In-process samples were
5.16/5.45 s inline and 4.94/5.42 s outlined; the separate C toolchain
experiment overlapped, so no close latency improvement is claimed.
Artifacts: `array-release-{gates,t0}.log` and retained emitted programs.

## C word helpers and optimization-level tradeoff

Compiling the pinned 164 MB C file with GCC `-O1 -flto=8` takes **95.96 s**
and 2,550,748 KiB peak process RSS, but the resulting compiler times out at
180 seconds compiling t0. Disassembly shows eight separate byte loads and
shifts for a word read, plus helper calls. The normal backend remains `-O2`.

Both µDewy C emitters now use `static inline` fixed-size `memcpy` helpers for
wide memory operations. They preserve native byte order, unaligned access,
signed extension, and C aliasing rules. No µDewy semantics or default C
optimization level changed. Expected-result checks cover `-O0`, `-O1`, and
`-O2`, unaligned accesses with neighboring sentinel bytes, signed loads,
static function/object words, and the hosted/bootstrap C implementations.
The selected group passes 32 checks; the remaining helper-spelling assertion
passes after updating it to the new generated C representation.

Replacing only those helpers in the same pinned C file produces a compiler
in **95.78 s** at `-O1`, with 2,969,484 KiB peak RSS. It compiles pinned t0 in
108.84 s (3,184,544 KiB peak process RSS), improving on the timeout but still
too slow to select `-O1` as the default. Small validation/measurement jobs
overlapped these experiments; none establishes a full-build acceptance time.
Artifacts: `c-toolchain/{memory-snapshot.json,gcc-memory-o1*,gcc-o1*,
memory-helper-*}`, `native-gcc-o1-t0`, and `native-gcc-memory-o1-t0`.

## Active-value integration checkpoint

The hosted C-backed executable build at `1fa828cc` finishes in **333.72 s**:
checking 72.28 s, lowering 68.81 s, emission 8.50 s, and backend 178.21 s.
It emits **60,668,904 bytes** of µDewy and peaks at 4,064,844 KiB process RSS.
The previous checkpoint took 450.51 s and emitted 69,976,136 bytes. Both use
the normal GCC `-O2` route with the recorded `-flto=8` wrapper. Small
regression jobs overlapped; these are integration observations, not isolated
acceptance samples or a new native fixed point. The executable remains far
above the full-build target.

That executable passes full native CLI compilation and execution of the
union-retention, capture-facts, scalar-projection and projection-effects
fixtures. It also passes the original `sets`, `integer_widths`, and
`local_captures` corpus programs, closing the three previously isolated
execution failures. Set output and exit status match the corpus's expected
92; the other six return 42. Individual compiles take 17.0–18.2 s, including
the prelude. This is a seven-program integration check, not a new full-corpus
result. Artifacts: `source-active-values/snapshot.json`,
`host-full-active-values`, and `active-values-integration/gates.log`.

## Index native syntax-reference identities

Each session now indexes syntax references by source, syntax node, and scope,
instead of scanning all prior references for every lookup or insertion.
The index is outside speculative state snapshots. Rollback removes discarded
suffix entries; lazily indexed preloaded references retain first-match
identity, including duplicates.

The nested-transaction regression passes with scope/source distinctions,
rollback followed by reused positions, and preloaded duplicates. A single
native executable compares the former linear lookup with the index: inserting
4,000 references and looking them up again takes **0.272/0.272 s linear versus
0.054/0.054 s indexed**. At 1,000 references the indexed path takes 0.014 s,
showing the expected scaling in this bounded kernel. Full CLI validation
jobs overlapped; no full-checker speedup is claimed. Artifacts:
`syntax-index-{gates,bench}.log` and `syntax-index-bench.py`.

The `1fa828cc` native executable subsequently compiles pinned t0 in
**39.79 s**, with 3,112,352 KiB peak process RSS and 4,310,586 emitted bytes.
This invocation used a fresh process and build directory, pinned source and
library inputs, and the verified eighteenth µDewy executable on the direct
backend. OS page caches were uncontrolled. No compiler jobs overlapped the
timed invocation. This is a module measurement, not the full-build target.
Artifacts: `native-active-values-t0`.

## Prune unused hosted imported functions before lowering

Hosted module assembly now follows runtime dependencies through imported
functions as well as the prelude, as native graph assembly already does.
Unreferenced imported bodies are removed before recursive renaming, analysis
and lowering. Entry declarations remain available to HIR tools and no-main
module compilation. User module initializers retain load order; callbacks,
lazy defaults, backend helpers and debugger formatters retain their dependencies.
All source bodies are still checked and validated before this pruning.

For p0, emitted text falls from **7,871,421 to 7,574,584 bytes (3.8%)**.
In-process old/new/new/old samples take 12.60/11.66/10.98/11.56 s; cache order
and overlapping regression checks limit latency comparisons. The imports and
prelude-cache group passes 31 checks, with two test-only mistakes corrected
in the final three-test group. Expected execution covers callback tables,
defaults, startup dependencies, unused-body rejection and complete entry HIR.
Artifacts: `import-reachability-{gates,final-gates,bench}.log` and
`compare-import-reachability.py`.

## Hoist native cleanup exclusions out of individual functions

Native lowering formerly rebuilt the same union of all captured bindings
once per function, repeatedly scanning and copying the complete function
graph and growing exclusion set. It now collects those bindings once, along
with escaping places, and shares that immutable result across function
lowering. Cleanup eligibility and binding order are unchanged.

Compared with the `1fa828cc` lowering driver, the current driver lowers a
300-function capture kernel in **2.13/2.14 s versus 4.60/4.46 s**. At 900
functions it takes **7.67/7.68 s versus 63.30/64.62 s**. Both sizes produce
byte-identical µDewy across the drivers and return the expected 42. The new
driver also contains the syntax-reference index and hosted import-pruning
build changes, so these are combined checkpoint measurements, not isolated
attribution to the hoist. A small brand regression overlaps part of the
larger comparison. Union retention, capture facts, and the original capture
corpus fixture pass direct/C checks with this driver. Artifacts:
`cleanup-exclusions/{build,gates}.log` and `cleanup-exclusions/compare.py`.

## Cache native runtime representations and index brand numbering

Lowering now memoizes successful runtime-type validation and cell alternatives
within its own stable type arena, including negative cell answers. Failed
validation is not cached: a later use still reports its own source span.
Brand numbering builds one child adjacency index, and lowering looks up
numbered brands by name. Registry insertion order and the existing tags stay
unchanged; neither cache survives a compilation.

A 150-function kernel with nested record and array fields lowers in
**5.61/5.68 s versus 8.04/7.89 s**, emitting the same **59,047 bytes** in all
four samples. The direct/C executions return 42, as do the union-retention,
capture-facts and local-capture cases. Scoped-cache tests cover distinct
arenas, appended types, modified returned lists and failure locations;
brand tests cover numbering order and independently modified registries.
The sharing/lifetime follow-up passes 13 tests. These remain bounded kernel
results, not full-build acceptance measurements.

The cache work exposed a hosted array-union widening bug: consumers received
the tag-cell address instead of its active array descriptor. The correction
covers branches, fresh call results, declarations, assignment, returns and
arguments on direct/C backends. Native lowering already handles the narrowed
optional-array case. The expanded explicit overlapping-array-union case
subsequently passed native checking and full CLI execution at the checkpoint
below. Artifacts: `native-type-cache-final/{gates,widening}.log`,
`native-runtime-type-final-gates.log`, `native-brand-index-final-gates.log`,
and `array-union-{consumer-corrected,sharing}-gates.log`. The earlier
`native-type-cache` driver contains the hosted bug and is not a valid seed.

## Runtime-cache integration checkpoint

A frozen `32a1570e` hosted build produced a complete C-backed compiler in
**343.10 s**: checking 71.51 s, lowering 71.14 s, emission 8.67 s, backend
185.77 s. Peak RSS was **3,871,900 KiB** and generated µDewy was
**60,258,591 bytes** (SHA-256
`45f17e539b4dec92fc51b91ab6d232bcef0628d2b9e2b8c71e901318230a16ed`).
It used normal GCC `-O2`, `-flto=8`, and bypassed ccache. Small regressions
overlapped this build, so it is an integration observation, not an isolated
acceptance measurement or a new native fixed point.

That executable compiles and runs the expanded array-union fixture, scalar
and aggregate getter fixtures, and the sets corpus fixture with their
expected results, taking 17.2–18.3 s per invocation. It predates owned-handle
getter projections and hosted shared string buffers. A subsequent native
build of the lowering driver exceeded its 240 s bound; samples showed
refinement key formatting and string cloning during record copies. Further
full builds are deferred until the corresponding bounded gates pass.
Artifacts: `source-runtime-caches`, `host-full-runtime-caches`,
`runtime-caches-integration/gates.log`, and
`aggregate-getter-native-build{,-stack,-stack-2}.log` (stack samples use
`.txt` instead of `.log`). The full-build target remains unmet.

## Hosted immutable string buffers

Owned strings now retain shared immutable backing buffers through private
descriptors. Lasting copies use one outlined clone helper; frame-backed,
borrowed, and raw-exposed strings retain copying fallbacks. Raw exposure
separates existing snapshots before pinning storage. This remains a
provisional accelerator under the ownership design question in
`PERFORMANCE.md`, not a language-level promise of constant-cost mutation.

The record-copy gate performs 100 copies with 16-byte and 64-KiB text
payloads. Both sizes allocate the same amount, below **16 KiB**, on direct
and C backends, with zero retained storage after the calls. Disabling buffer
sharing provides the positive control. Raw snapshot isolation, Unicode
views, reassignment, optional returns, discarded calls, and growing arrays
retain their execution and lifetime checks. Artifacts:
`shared-string-buffer-gates.log`, `shared-string-lifetime-corrected-gates.log`,
and `shared-string-getter-corrected-gates.log`.

## Retain only a getter's selected aggregate field

Direct getters can now return a selected owned string or dynamic-array
handle without first copying the complete result record. The call boundary,
arguments, defaults, side effects and guards remain intact. The selected
handle gains its lifetime before the source's locals are released; a field
of an owned temporary receiver is retained exactly once. Synthetic dictionary
keys/values routes continue to identify the complete table during lowering.

Hosted selected-field allocation is less than half the full-record control,
with zero retained storage. A hosted-built native lowering driver passes
scalar, effect, guard, aggregate, and temporary-element cases on both direct
and C backends; the aggregate gate allocates less than 32,000 bytes for 100
pairs of calls and retains none. The small driver supplies an ASCII-only
segmentation hook for these ASCII lifetime cases; it does not replace the
full Unicode runtime tests. Driver build time was 152.50 s, with other small
checks overlapping. Artifacts: `shared-string-getter-corrected-gates.log`
and `shared-string-getter-final/{build,corrected-gates}.log`.

## Compare refinement contracts without formatting keys

Native subtype coverage now compares proposition fields directly. It ignores
resolved subject/term binding ids for contract identity, retains all source
contract fields, and compares tested types structurally. Storage interning
continues to preserve proof provenance. A cross-product regression checks
agreement with the old serialized keys, including absent versus literal
`none` strings, conditional booleans, large/negative integers, and equivalent
types with different constructor defaults.

For 100 equivalent typed-proposition comparisons, the hosted-built program
allocates **6,400 bytes versus 928,000** through formatting; direct and C
executions pass. The full native CLI builds and runs the same gate, allocating
**12,800 bytes versus 4,844,800**. Both return the expected 42. These are
allocation kernel measurements, not full-checker timings. Artifacts:
`proposition-identity-cost-gates.log` and
`proposition-identity-native-corrected-gates.log`.

## Shared-string integration checkpoint

A frozen `54007516` hosted build completed in **327.28 s**, compared with
343.10 s at `32a1570e`: checking 72.53 s, lowering 68.29 s, emission 8.58 s,
and backend 171.86 s. Peak RSS was **3,732,484 KiB**. Generated µDewy was
**57,453,649 bytes**, SHA-256
`f855390e1e46d4ed5a07fca1634845212bfd3c170b51fcc83baea38ec911abf7`.
This used GCC `-O2`, `-flto=8`, and disabled ccache, with no other compilation
jobs running. The fresh process and build directory do not control OS page
caches. The earlier 343.10 s checkpoint had small overlapping tests, so the
full-build comparison is observational.

Using that executable on the same pinned `source-active-values` t0 input and
library takes **27.82 s**, versus the previous **39.79 s**, with peak RSS
**2,172,672 KiB** versus **3,112,352 KiB**. The emitted **4,310,586 bytes** are
byte-identical (SHA-256
`ec7aa66b51f6e26182eae15cad4cd78d47c1f543eddd2d5cb038a229ff30257f`).
Both measurements use the same native µDewy executable, a fresh process and
empty build directory, and no overlapping compilation jobs. They measure a
combined checkpoint, not individual attribution to string sharing.

Artifacts: `source-shared-strings`, `host-full-shared-strings`, and
`native-shared-strings-t0`. This checkpoint is a working integration seed,
not a new two-generation fixed point. The sub-minute complete-build target
still requires substantial checking, lowering, and backend improvements.

## Type interning index owned by the arena

The native type table now keeps `entries` and `positions` together. A missing
key inserts directly instead of scanning the arena; forks retain independent
indexes, and rollback removes the discarded suffix's keys before reusing ids.
The result of `intern` still carries `i <? nodes.entries.length`. Supporting
that contract required nested field-route bounds and correct call snapshots
in both checkers; it was not replaced with an unchecked integer result.

A bounded kernel inserts and then looks up each of 1,000, 4,000, and 16,000
array types. Both versions were generated by the same hosted compiler and
executed through the direct backend, alternating old/new/new/old. The old
arena source is pinned at `e6c6ddf7`; all invocations return the expected 42.
These are process wall times with warm OS pages, not compiler-build timings.

| Types inserted and reused | Old arena | Indexed arena |
| --- | ---: | ---: |
| 1,000 | 0.0955–0.0985 s | 0.0726–0.0735 s |
| 4,000 | 0.6641–0.6925 s | 0.3236–0.3376 s |
| 16,000 | 6.4186–7.3186 s | 1.2942–1.3385 s |

Artifacts, frozen arena sources, the measurement script, and individual
samples are in `phase0-performance/type-arena-index/`. Independent arenas,
forks, clearing, truncation, and alias resolution pass direct/C execution.
Brand numbering and nested checker rollback pass; type algebra, aliases,
queries, display, and aggregate layouts agree with hosted results. The
updated native source-validation driver also accepts the indexed arena with
the full prelude. Native execution of the new complete compiler and a fresh
fixed-point comparison remain separate integration gates.

## Smaller µDewy token records and C integer literals

Hosted µDewy tokens now use fixed object slots. For the preprocessed 4,399,645
byte t0 artifact (368,822 tokens), separate processes using the previous
scanner with slots peak at 61,872–61,924 KiB, versus 73,532–73,632 KiB without
slots. Tokenization timings overlap (roughly 0.7–0.8 seconds); this establishes
a memory reduction, not a throughput improvement. An experimental combined
regex scanner also preserved the token streams but did not improve these
samples, so the existing run scanners were retained.

Both µDewy C emitters now spell small word constants without leading zeroes,
while retaining `UINT64_C` and the complete 64-bit bit pattern. The previous
full compiler C artifact contains 766,466 padded word literals. Omitting
padding removes 10,755,004 bytes from that 135,317,721-byte file (projected
124,562,717 bytes). This is a text-size calculation, not a new complete build
or a measured C compiler speedup. Token, annotation, literal, C execution,
and hosted/native µDewy output checks pass. Artifacts are in
`phase0-performance/udewy-text/`.

A separate toolchain probe compiled the unchanged shared-string integration
C source with Clang 22.1.8, `-std=c99 -O2`: 288.31 seconds and peak process RSS
3,207,156 KiB. The resulting compiler builds the pinned t0 module in 22.81
seconds, producing the same 4,310,586-byte µDewy artifact and SHA-256 as the
GCC-built compiler (27.82 seconds in the earlier sample). Clang improves this
execution sample but costs substantially more to build; it has not replaced
the default toolchain. Short regression checks overlapped part of the C
compilation, so this probe is not an isolated acceptance run. Logs are in
`phase0-performance/clang-shared-strings/` and
`phase0-performance/native-clang-shared-strings-t0/`.

The matching GCC 16.2.1 `-O1 -flto=8` probe built the same old C source in
80.12 seconds (peak process RSS 3,025,768 KiB), but its compiler needed 73.41
seconds for t0. Output remained byte-identical. This is a substantial runtime
regression against the `-O2` compiler, so the cheaper optimization level was
not adopted. The GCC pass report and timing logs are in
`phase0-performance/gcc-o1-shared-strings/`; module records are in
`phase0-performance/native-gcc-o1-shared-strings-t0/`.

## Indexed-arena integration and repeated type queries

The compiler frozen at `7cadb2c3` builds through the hosted C route in
324.72 seconds: checking 70.19, lowering 67.76, emission 8.08, and backend
172.91 seconds; peak process RSS is 3,742,296 KiB. The generated µDewy is
57,628,213 bytes, SHA-256
`997a7ed518cbc237ae0a0f5c8b9da46a962ee019164ec5fcce96cab6d61368a7`.
This uses the same machine, fresh build directory, GCC 16.2.1 `-O2` and
`-flto=8`, without concurrent compilation. Its native t0 invocation takes
28.47 seconds and peaks at 2,174,236 KiB. These timings do not show a material
end-to-end improvement over the preceding integration seed. Artifacts are
`source-indexed-arena`, `host-full-indexed-arena`, and `native-indexed-arena-t0`.
The complete-build target remains unmet; this is not a new fixed point.

The next query batch bypasses Boolean normalization for nominal subtype
queries in both implementations. Hosted graph reachability is cached until
the graph changes, including resident-prelude rollback. Native normal forms
are cached with their type arena; truncation invalidates results before ids
can be reused. Alias targets remain outside the normal form of a named atom.
The hosted mutable type-tree normalizer is deliberately not identity-cached.

A native CLI-compiled kernel repeats normalization of a 32-field record 128
times. Cached queries allocate 2,048 bytes, compared with 196,608 for the
uncached outer walk, and return the expected 42. Direct/C hosted-generated
kernel checks also pass, including arena forks, rollback, reused result ids,
and alias resolution. Logs are in `query-cache-native` and
`normalization-query-gates.log`.

The hosted t0 sample before this batch is 15.84 seconds (checking 9.23,
lowering 2.55); after it is 15.49 seconds (checking 9.05, lowering 2.50).
Both use the same pinned module/library, direct backend and separate empty
build directories. This small single-sample difference does not establish a
build-time speedup. Logs are `host-before-nominal-queries-t0` and
`host-nominal-queries-t0`. Native whole-module timings for this query batch
remain an integration gate.

## Shared dictionary rebuild implementations

Both lowerers now outline arena-backed dictionary/set rebuilds by their
entry storage and field layout. Every lookup still tests whether a rebuild
is needed, but its cold compaction, hashing, allocation, and table-fill code
is emitted once per helper. Arena-free lowering retains the existing inline
path so newly allocated storage cannot outlive a helper frame.

The pinned hosted t0 direct build now emits 2,224,589 bytes of µDewy, versus
2,965,235 before outlining (25% smaller). Its single fresh-process sample is
13.94 seconds: checking 8.52, lowering 2.19, emission 0.32, backend 2.05;
peak process RSS 164,436 KiB. The previous sample is 15.49 seconds and
196,448 KiB. Checking also varied despite no checker edits in this batch,
so the time difference should not all be attributed to outlining. Artifacts
are in `host-shared-dict-rebuild-t0` and `host-nominal-queries-t0`.

The reusable native lowering driver's generated µDewy decreases from
57,354,225 to 43,677,513 bytes in this combined development checkpoint.
That comparison includes concurrent snapshot-analysis source changes and
is not an isolated timing experiment or full compiler build. Hosted and
native lowering both pass direct/C expected-result checks for scalar widths,
record payloads with arrays, tombstones, compaction, growth, insertion order,
Unicode keys, and saved dictionary independence. Repeated lookup sites also
have an explicit helper-count/code-growth regression. Logs are
`shared-dict-native-gates.log`, `shared-dict-rebuild-hosted.log`, and
`shared-dict-execution-gates.log`.

Dictionary probes now share their search loop as well. A probe returns a
single table slot; reading that slot recovers the matching entry or a miss,
so the helper needs no allocated result tuple. Hosted helpers share across
value types when key storage and relevant field offsets match. Native
insertion retains the already computed hash. Source argument evaluation and
missing-entry positions remain at the call site.

The native scalar-width dictionary kernel now emits 307,284 bytes, versus
380,109 with rebuild sharing alone (19% smaller). Direct/C execution passes,
along with bool, signed-byte, and full-width unsigned keys, exactly-once key
calls, tombstones, and the aggregate/Unicode kernel. The reusable lowering
driver emits 41,062,392 bytes with this batch; its source also contains the
new probe generator, so that is a combined checkpoint rather than a pure
output comparison. Logs are `shared-dict-probes-hosted.log`,
`shared-dict-probes-widths.log`, and `shared-dict-probe-driver.log`.

## Shared-dictionary full integration checkpoint

The frozen `1ce9c366` compiler builds through the hosted C route in 355.45
seconds: checking 67.88, lowering 59.87, emission 5.28, and backend 216.49;
peak process RSS is 2,495,812 KiB. It emits 38,589,624 bytes of µDewy,
SHA-256 `e3293edb53029c516d14d2fe3fb2e15854d13fc39a84fa85e603d6fa9f7a79d7`,
and 83,987,921 bytes of C. The preceding integration was 324.72 seconds,
57,628,213 bytes of µDewy, 125,039,048 bytes of C, and 3,742,296 KiB.

This is a full-build **time regression** despite smaller code, lower memory,
and cheaper lowering/emission. A single GCC LTO partition remained busy for
more than two minutes after most other partitions finished. That observation
does not identify the responsible optimization pass; backend profiling and
further code-shape work are still required. Both runs used GCC 16.2.1 `-O2`
with `-flto=8`, empty build directories, disabled ccache, and no overlapping
compilation jobs. Source and logs are retained in `source-shared-dictionaries`
and `host-full-shared-dictionaries`.

The resulting native compiler builds the same pinned t0 module in 22.91
seconds, versus 28.47 previously, with peak process RSS 2,062,660 KiB. Its
output is 3,724,614 bytes, SHA-256
`c718853f9d13add1aa9483d63ccb6a366d5ef35a4389daa2358b9fc30b8beb90`.
This isolated run is in `native-shared-dictionaries-t0`. The native execution
improvement does not establish the full-build target, and the new integration
seed is not a fresh two-generation fixed point.

## Native nominal graph queries

Nominal edges and their transitive closure now live in one `subtyping.Graph`
value. Adding an edge updates the affected descendants once; checking subtype
membership does not walk the edge list. Checker forks/rollback restore both
parts together, and type-name lookup uses the same indexed names. Promotion
rules remain separate from inheritance.

The query checks the child's presence and then uses the proven dictionary
lookup directly. This avoids constructing an optional copy of its ancestor
set. A full native CLI-compiled kernel performs 128 positive and 128 negative
queries with **zero allocated bytes**, versus 241,664 bytes for the previous
edge-scanning algorithm run as an independent control. Both paths return the
expected answers. This is an allocation result, not a full compiler timing.
The graph kernel also compares a complete small relation after each late edge,
including cycles, and checks independent values and restored snapshots.
Hosted-generated direct/C execution, the type-algebra differential group,
and actual nested Session rollback pass. Artifacts are `nominal-graph-native`
and `nominal-graph-snapshot-gates.log`.

## Array growth and C optimization integration

Frozen `5d67b83e` builds through the hosted C route in **231.74 seconds**,
versus 355.45 at the preceding checkpoint. This combines nominal indexing,
shared array relocation, and the measured GCC accelerator options
`-O2 -flto=8 -fno-tree-pre -fno-code-hoisting`. Checking takes 66.45 s,
lowering 56.48 s, emission 4.49 s, and backend compilation/linking 98.59 s.
Peak process RSS is 2,228,984 KiB; emitted µDewy is 33,799,460 bytes,
SHA-256 `f0202296b580a3595cd2595337541dc115908614fb4aa8184764b35d9a3f8815`.
The source snapshot and isolated invocation are `source-array-growth` and
`host-full-array-growth`; caches are empty and ccache is disabled.

That seed compiles the pinned `t0` source in 22.21 s with peak process RSS
2,042,992 KiB, emitting 3,509,937 bytes, SHA-256
`0b9937ceda2d3f07d24ac688c3210c69094556813adbf6916ef7d56aab5238c2`.
The isolated run is `native-array-growth-t0`. This improves the complete
hosted build but does not meet the full-build target or refresh the fixed
point. [PERFORMANCE.md](PERFORMANCE.md#bounding-c-optimizer-work) records
the separate C profiling experiments that motivated the options.

The following fact-index batch replaces formatted lookup keys with integer
buckets and structural comparisons. Five thousand lookups allocate
1,120,000 bytes instead of 5,424,000 in hosted-generated code, and 1,920,000
instead of 10,712,000 through the full native CLI. Collision, removal,
snapshot, and proof-oracle checks pass. Artifacts are `fact-lookup-before`,
`fact-index-native`, `fact-index-native-before`, and the `fact-index-*gates`
logs. This is an allocation result; whole-compiler timing with that batch
remains a separate integration measurement.

### Fact-index integration and deferred type descriptions

The frozen `c4658546` hosted build (`source-fact-index`, archived with its
manifest beside the measurements) succeeds in **231.76 seconds**, including
68.59 seconds checking, 57.41 lowering, 4.51 emission, and 95.53 backend.
It uses the same GCC/LTO/no-PRE options as the previous checkpoint, an empty
build directory, disabled ccache, and no overlapping compilation jobs.
Peak process RSS is 2,229,668 KiB; emitted µDewy is 33,768,252 bytes
(SHA-256 `0cc77ed439516933b56f6f26c4bdef3d377585037a753772037b64d2b07a26b5`).
The full-build target remains unmet.

That native seed builds the pinned t0 in **19.85 seconds** (previously
22.21), with byte-identical µDewy: 3,509,937 bytes and SHA-256
`0b9937ceda2d3f07d24ac688c3210c69094556813adbf6916ef7d56aab5238c2`.
Its opt-in phase reports divide this into 6.25 seconds frontend checking,
4.88 validation, 0.04 initialization/reachability, 6.02 lowering,
0.90 emission, and 1.37 backend. Peak process RSS is 2,151,196 KiB.
All twelve contract/aliasing/invalidation cases pass through the complete
hosted and native CLIs. Artifacts: `host-full-fact-index`,
`native-fact-index-t0`, and `fact-index-contracts` under the Phase 0 root.

The next type-factory batch probes the arena's storage key before building
recursive structural identity strings and retained descriptions. It keeps
key/shape encodings and metadata distinctions unchanged. A kernel repeating
4,000 already-interned object, function, refined, and array types allocates
**35,808,000 → 3,496,000 bytes** when hosted-compiled (direct and C routes),
and **174,600,000 → 27,648,000 bytes** when both versions are compiled by the
same `c4658546` native seed. These are allocation results, not whole-compiler
speedups. Both variants check their returned identities and arena size;
existing algebra, display, deep-shape, fork, and rollback tests pass.
Artifacts: `type-factory-before`, `type-factory-after`,
`type-factory-native-before`, `type-factory-native-after`, and their logs.

### Hosted full-source profile and runtime union ordering

A bounded profile of frozen `c4658546` on the full compiler source completed
checking and was interrupted during lowering at 400 seconds to retain call
data. It did **not** produce a compiler. Its 238.47 profiled checking seconds
and 162.02 partial lowering seconds are diagnostic data, not an unprofiled
build comparison (`host-full-profile/run-00/hosted.prof`). A short native t0
sampling run overlapped part of this profile; do not use either as an isolated
time measurement. Sampling captured 132 stacks, with `shapes_key` in 35,
supporting the earlier factory batch (`native-fact-index-samples`).

The hosted profile attributes about 67 seconds to `runtime_union_members`
sorting by `repr`: record defaults and method bodies were rendered recursively
merely to choose tag order. Hosted ordering now walks structural comparison
fields, terminates recursion at alias identity, and shares nested keys for
one pure traversal (or the enclosing stable lowering scope). This follows the
native implementation's existing structural-order policy. Numeric tag order
is internal; None remains tag zero, and each spelling of the same member set
must agree. Declaration metadata cannot influence the order, and same-name
recursive aliases remain distinct by binding identity. Tests cover opaque
metadata that must never be rendered, a shared type DAG, cache lifetime,
recursive aliases, and existing union/enum execution fixtures.

An exploratory adjacent-temporary fold reduced the frozen generated C from
74,384,681 to 68,709,917 bytes, eliminating 134,757 declarations. The Python
prototype took 10.74 seconds and has no established backend-time benefit;
it was **not** adopted. Its script and output remain in the artifact tree.

### Hosted token traversal dispatch

The same full-source profile recorded 17.56 million `isinstance` calls from
`t2.recurse_into`, accounting for 15.32 profiled seconds. The traversal now
uses standard-library class dispatch, retaining the same phase ordering and
container boundaries while caching the appropriate handler for leaves and
containers (including subclasses).

Postprocessing all 112 `.dewy` files in the frozen bootstrap directory takes
**16.19 → 12.96 seconds** in isolated, unprofiled process runs. Timing excludes
source reads and verification serialization. Every per-file serialized token
tree has the same SHA-256 before and after. All 166 parser differential,
literal-boundary, and partial-operator checks pass. Artifacts are
`t2-before.json`, `t2-after.json`, their logs, and `t2-dispatch-gates.log`.
This is a parser workload result, not a new full compiler build measurement.

### Combined type-description integration

Frozen `99d6162a` (`source-type-descriptions`, with archive and manifest)
builds the complete compiler through the hosted C route in **216.01 seconds**.
Checking is 67.80 s, lowering **35.97 s** (previously 57.41), emission 4.60 s,
and backend 101.51 s. Peak process RSS is 2,229,000 KiB. This uses the same
GCC/LTO/no-PRE flags, disabled ccache, empty build directory, and no overlapping
compilation jobs. Emitted µDewy is 33,823,436 bytes, SHA-256
`068092b0b483cdb5bec567899bb9b703b673134aa0a85edf8895514e8af1ab85`.

Its native seed builds pinned t0 in **13.24 seconds**, versus 19.85 before
deferred type construction, with identical 3,509,937-byte µDewy and SHA-256
`0b9937ceda2d3f07d24ac688c3210c69094556813adbf6916ef7d56aab5238c2`.
Frontend takes 3.59 s, validation 4.93 s, initialization/reachability 0.04 s,
lowering 2.20 s, emission 0.88 s, and backend 1.26 s. Peak process RSS is
2,148,724 KiB. This was an isolated invocation; the full native build and
fixed-point refresh remain separate gates. Artifacts: `host-full-type-descriptions`
and `native-type-descriptions-t0`.

The following hosted lowering batch shares a function's initializer index
between ownership analyses, reducing four walks of the same transformed
body to one without retaining results across rewrites. Runtime helper lookup
also reuses discovery results: hits preserve the first matching declaration,
and misses expire when discovery appends a function. Eleven targeted tests
pass, including direct/C ownership and growth execution, helper discovery
lifetime, and the single-walk cost gate (`lowering-index-gates.log`). No full
build speedup is claimed for this follow-up batch yet.

### Shared fixed-width integer limits

All twelve contract/aliasing/invalidation cases also pass through the
`99d6162a` full native CLI and its pinned hosted reference
(`type-descriptions-contracts`).

Native fixed-width range queries previously rebuilt `2^bits` with BigInt
multiplication on every call. The bounds now derive once from the existing
width/signedness table, and both range queries and integer-literal fit checks
use them. They are keyed by primitive name, independent of arena ids and
per-program facts; abstract `int`/`uint` behavior is unchanged.

For 2,000 range queries, hosted-generated direct/C code allocates
**19,760,000 → 1,296,000 bytes**; code compiled by the same `99d6162a` native
seed allocates **29,724,000 → 1,312,000 bytes**. Tests independently check all
eight signed/unsigned endpoints against Python integer arithmetic, acceptance
at either endpoint and rejection immediately outside, unknown types, and
independent arenas reusing the same ids. Four focused range/type-query tests
pass, alongside the native CLI-compiled kernel. Artifacts are
`fixed-width-before`, `fixed-width-gates.log`, `fixed-width-native-before`,
`fixed-width-native-after`, and `fixed-width-native.log`.
These are query allocation measurements; the table's one-time initialization
is outside the repeated-query counter, and a complete build includes it.

### Identity proof-state operations

A one-path join now returns an independent value of that path's state;
Python copies its mutable mapping and native Dewy retains its value snapshot.
Native `put` also skips an identical replacement, including comparison of
`capped` provenance. Actual endpoint/provenance changes still detach through
the ordinary store path. This avoids forcing copy-on-write for facts that an
expression recorder or loop pass merely reinstalls.

One hundred singleton joins and identical updates over a 64-entry state
allocate **14,899,240 → 96,040 bytes** in hosted-generated direct/C code and
**17,219,240 → 151,240 bytes** when both variants are compiled by the same
`99d6162a` native seed. This kernel excludes initial state construction.
Tests check later value/provenance changes against retained snapshots, empty
joins, all existing fact kinds in the differential singleton-join matrix,
collision handling, and the complete native bounds test. Artifacts are
`fact-identity-before`, `fact-identity-after`, `fact-identity-native-before`,
`fact-identity-native-after`, and the `fact-identity-*gates.log` files.
Whole-compiler timing for the latest proof-query batches remains pending.


### Proof-query integration and self-build acceptance repair

Frozen `661c5b88` (`source-proof-identities`, archive and manifest retained)
builds the complete compiler through the hosted C route in **204.33 seconds**:
checking 64.83 s, lowering 33.14 s, emission 4.55 s, backend 95.97 s. Peak
process RSS is 2,232,304 KiB. Toolchain, flags, cache controls, and isolated
execution match the preceding C checkpoint. Emitted µDewy is 33,865,993 bytes,
SHA-256 `6acbfd708cc1f6810a8c49dede7d3e6fd5083bf7811aa01e4af928a9e098070d`.

The resulting native seed builds pinned t0 in **12.49 seconds**, peak RSS
1,671,108 KiB. Frontend is 3.77 s, validation 3.93 s, initialization/reachability
0.04 s, lowering 2.23 s, emission 0.91 s, backend 1.24 s. Generated µDewy is
byte-identical to the preceding pinned t0 checkpoints. Artifacts:
`host-full-proof-identities` and `native-proof-identities-t0`.

The subsequent full native invocation **failed during frontend checking**
after 39.45 s (`native-proof-identities-full`); it is not a successful build
timing. Dictionary helper cache keys introduced an interpolation of the entire
offsets dictionary, exposing native's still-missing structural conversion.
Both probe/rebuild keys now encode their five accessed offsets in a fixed
order. Missing fields remain distinct, and irrelevant map insertion order
no longer affects reuse. A focused test verifies reordered maps, each changed
offset, a missing values field, and retained snapshots; it passes through
hosted direct/C code and the full native CLI. Existing dictionary growth,
compaction, sharing, and helper-count gates pass too. Artifacts:
`dictionary-layout-key-*`. The full native build is retried separately.


### Complete native direct build and interpolation parity

The `661c5b88` hosted seed compiles frozen `4e86c14f` source
(`source-dictionary-layout`, archive and manifest retained) into a complete
native executable through native µDewy's direct x86-64 backend in
**128.43 seconds**. No Python participates in compilation; Python only drives
the measurement. Frontend is 40.25 s, validation 12.77 s, startup/reachability
2.62 s, lowering 37.48 s, emission 12.57 s, backend 19.91 s. Peak process RSS
is **8,557,888 KiB**. The isolated invocation uses an empty build directory,
with OS page caches uncontrolled. This is one generation, not a refreshed
fixed point or evidence of the under-60-second target. Emitted µDewy is
48,828,932 bytes, SHA-256
`8087f70d6231135978b5025de4845d86484ce4c9be1485a0e3b1446a7a14407c`.
Artifacts: `native-dictionary-layout-full`.

A separate GDB sampling run of the same source and seed records 314 stacks
(`native-full-proof-identities-samples`). Type construction and Boolean
combination remain prominent in frontend/lowering; 27 lowering samples
include `function_type`, and 23 include `shapes_key`. Rendering spends most
of its sampled time in the program-level renderer rather than expression
visits. These are diagnostic samples with debugger overhead, not new timing
baselines. Backend wait samples do not identify the child compiler's costs.

The hosted compiler now captures a computed union interpolation field inside
its expression, matching the native approach. It no longer hoists a call
before its containing statement or treats a member's effectful receiver as
free to re-evaluate. Expression-bodied functions consequently work too.
Expected-result execution checks cover field order, skipped branches,
returned record fields, optional strings, and retained results; they pass on
hosted direct/C output and the native CLI (`union-interpolation-*`). The
32 focused union/conversion/printing tests pass after correcting the newly
accepted expression-body test's parameter to prove its index in bounds.
Structural conversion and brand-dispatch hoisting remain separate work.


### Native-built code and repeated type-query batch

Native µDewy compiles the preceding native-emitted compiler source through
GCC in **133.79 seconds**, peak process RSS 3,682,976 KiB, with the same
O2/LTO/no-PRE flags, disabled ccache, and empty output directory. This times
only the backend and does not replace the complete invocation measurement.
The resulting native-built executable builds pinned t0 in **23.76 seconds**,
peak RSS **540,256 KiB**, producing the same µDewy bytes/hash as the hosted-built
seed. Frontend is 6.90 s, validation 9.86 s, preparation 0.12 s, lowering
4.49 s, emission 0.87 s, backend 1.21 s. Its lower memory use accompanies a
runtime regression against the hosted-built seed; the remaining native
lowering costs must be measured on this native-built code too. Artifacts:
`native-dictionary-layout-c` and `native-built-dictionary-layout-t0`.

The next type-query batch caches Boolean constructor requests in their arena,
keeps generated anonymous function signatures in terms of type ids until an
intern miss, and makes contract coverage reflexive without recursively
comparing the same record's fields. Truncation clears both new caches before
ids can be reused. Alias target updates cannot change these constructors'
structural identities; subtype answers depending on inheritance are not
cached here. Required/named/place signatures remain distinct.

A 500-iteration query kernel allocates **41,765,632 → 600,000 bytes** in
hosted-generated direct code and **61,404,008 → 3,408,000 bytes** when both
variants are compiled by the same native-built C executable. Five focused
type tests pass (including the 4,356-pair subtype matrix, normalization,
dispatch, joins, metadata, deep encodings, forks and rollback); the query
kernel passes through both hosted backends and the native CLI. No full-build
speedup is claimed for this batch yet. Artifacts: `type-query-reuse-*`.


### Hosted syntax and debug-binding traversal

Hosted growth/write scans now visit parsed syntax children without walking
operator tokens, locations, or literal payload metadata. A loop's mutated
and replaced names come from one traversal, preserving their distinct sets.
Debug-binding collection uses the existing HIR child traversal, retaining
its function/parameter boundaries without descending through type metadata.
Class metadata is cached; mutable AST contents are always read anew.

The complete scan workload over 98 frozen compiler sources takes
**4.64 → 0.50 seconds**, excluding source reading and parsing. All growth,
mutation, replacement, and container-route results match exactly. This
workload scans each whole source for all four queries; ordinary checking
runs write scans on loop bodies, so it is not a full-checking speedup claim.
The sources exclude bootstrap test fixtures containing intentionally reserved
or invalid syntax. Thirty-one focused loop/iterator and debugger metadata
checks pass. Artifacts: `syntax-scans-{before,after}.{json,log}`,
`measure-syntax-scans.py`, and `syntax-traversal-gates.log`.


### Compact structural type identities

Native structural keys now refer to exact, interned child shapes within their
type arena. Metadata-distinct stored entries can share a structural id;
semantic equality compares those ids without copying complete type records.
The structural index compares complete compact keys, not hashes alone. It
survives truncation so a reused stored-description slot cannot change the
meaning of an existing child reference, and table snapshots retain their own
index. Keys and ids are arena-local, not a cross-arena serialization format.
Alias resolution explicitly preserves the reference's structural identity.
Numeric union tag order remains internal and is canonical within the program.

For two metadata-distinct but structurally equal binary DAGs twelve layers
deep, construction allocates **79,391,936 → 139,328 bytes** in hosted-generated
direct code. The root key shrinks from **299,511 to 39 characters**. The test
also checks distinct field names, separate aliases sharing a target, retained
forks, and stored-id reuse after full truncation. Ten focused type/container
checks pass, including the subtype/normalization/dispatch matrix and direct/C
execution. Artifacts: `structural-ids-*` and `container-length-final-gates.log`.
Native-built kernel and full compiler timing remain integration gates.

Constructing the structural index exposed a missing language fact: dictionary
and set lengths used unrestricted `int64` in both checkers. Their stored live
count and source `.length` now carry the existing `addr` contract, as array
and string lengths already do. This preserves the invariant even on hosted
writes through the exposed live field; a negative count is rejected. A real
container fixture checks counts after removal and clearing. Existing native
seeds lack this length fact, so the updated hosted compiler provides the next
seed before native compilation of this new source is verified.

### Structural identity integration and hosted ASCII segmentation

The hosted C build of `13b1ee96` completes in **203.58 seconds**, peak process
RSS 2,239,740 KiB: checking 61.41 s, lowering 35.82 s, emission 4.66 s,
backend 95.43 s. Its executable builds pinned t0 in **11.59 seconds**
(previously 12.49 s), with lowering **2.23 → 1.39 s**, and identical emitted
µDewy. The structural-identity kernel passes through the native CLI with
allocation **220,538,976 → 563,040 bytes** and key length **299,511 → 39**;
the dictionary/set length fixture also passes through the full native CLI.

A full direct native build of frozen `13b1ee96` completes in **94.81 seconds**
(previously 128.43 s), peak process RSS **7,851,532 KiB** (previously
8,557,888 KiB). Frontend 26.07 s, validation 12.52 s, preparation 2.80 s,
lowering 19.60 s, emission 12.88 s, backend 18.23 s. It emits 48,818,721 bytes
of µDewy, SHA-256
`3ba35c9e07fcfbf4f16626ced7d0cafc5679075abbbb637c6c7172b26f1589f7`.
These are isolated fresh-process/empty-output measurements on the recorded
machine and toolchains, with OS page caches uncontrolled. This is one native
generation, not a refreshed fixed point or the sub-minute acceptance target.
Artifacts: `host-full-structural-ids`, `native-structural-ids-{t0,full}`,
`structural-ids-native-gates`.

The remaining emission cost exposed a hosted/native implementation mismatch:
hosted-generated string materialization binary-searched three Unicode property
tables even for ASCII. Hosted lowering now uses the same ASCII properties as
the native library, retaining the complete grapheme state machine for CR/LF
and non-ASCII transitions. No Unicode data or string semantics changed.

A repeated join of 7.4 MB of ASCII takes **5.26 → 0.32 seconds** on the direct
backend and **0.60 → 0.070 seconds** on GCC (medians of three isolated runtime
samples, excluding compilation). All return the expected total length.
Twenty-nine selected checks pass, including the full Unicode 16 grapheme
corpus, all 16,384 ASCII pairs and invalid UTF-8 through runtime decoding on
both backends, independent library segmentation, and string join/slice checks.
Artifacts: `ascii-segmentation/{before,after}.udewy`, `results.json`, `gates.log`.
Full compiler timing with this hosted optimization remains an integration gate.

An updated checking-only hosted profile is retained in
`host-check-structural-ids-profile`. Parsing accounts for 76.4 of its 207.1
profiled seconds, and bounds validation 34.1. These include instrumentation
overhead (and brief overlapping small regressions); they identify candidates,
not new baseline timings. The next batch should address those measured costs.

### Hosted token candidate indexes

Hosted t1 now declares each compound token's possible starting t0 classes and
caches candidates by the actual first-token class. Inheritance is honored;
an extension without a filter remains an exhaustive candidate. Matching order,
longest-match selection, and ambiguous-match diagnostics are unchanged.
Hosted t0's symbol probe uses a first-character index while preserving the
original longest-first spelling order. No accepted spelling changed.

Tokenizing 112 frozen compiler/test sources through t2 takes **13.10 → 10.00
seconds**, excluding source reads and serialization. Serialized token hashes
match for all 112 files. These runs were isolated and uncached at the parser
level. The 246 selected parser checks pass, including comparison against t1's
exhaustive candidate list, inherited/unknown token cases, compound literal
boundaries, and hosted/native parser comparisons. Artifacts:
`hosted-probes-{before,after}.{json,log}` and `hosted-probes-gates.log`.

Separately, native µDewy builds the `13b1ee96` native-emitted compiler through
GCC in **132.58 seconds**, peak process RSS 3,680,396 KiB (backend only).
Its executable builds pinned t0 in **24.27 seconds**, peak RSS 519,792 KiB,
with identical µDewy bytes to the hosted-built seed. Frontend 7.31 s,
validation 10.73 s, preparation 0.12 s, lowering 3.73 s, emission 0.85 s,
backend 1.22 s. Lowering improved from the preceding native-built executable's
4.49 s, but total runtime did not improve; the native-built code needs its
own profile. Artifacts: `native-structural-ids-c`, `native-built-structural-ids-t0`.

### Defer discarded diagnostic rendering

`ReportException` now carries the report as its exception argument, allowing
Python's ordinary exception formatting to render it on demand. A failed
speculative interpretation of valid source no longer lays out a source
excerpt only to discard it. Explicit exception text and notebook tracebacks
still render the same report; final color policy is applied at display time,
and the structured report survives exception pickling.

Twenty-eight diagnostic/ambiguity/assertion checks pass. A bounded kernel of
2,500 constructed diagnostics takes 0.153 s when eagerly rendered and 0.0044 s
when merely carried; this demonstrates the removed work, not a full-checking
speedup. Artifacts: `lazy-report-{kernel.json,gates.log}`. Full checking with
the parser and diagnostic batches remains an integration measurement.

### Refresh the native µDewy benchmark seed

Sampling the native-built compiler found a benchmark setup issue: the retained
`native-pair-cow-eighteen/udewy` seed predates the committed fixed-size `memcpy`
C memory helpers. It still emitted byte-by-byte word loads. The older native
C measurements above accurately describe that pinned executable, but do not
measure the current µDewy C emitter and cannot establish a native-lowering
regression independently of that backend difference.

Rebuilding current µDewy natively takes 3.25 s. Using it to compile the exact
same native-emitted compiler µDewy reduces the C-backend build from
**132.58 to 84.73 seconds**, peak process RSS 3,617,112 KiB. That compiler's
pinned t0 build takes **12.24 seconds** (previously 24.27 s), peak RSS
519,372 KiB, with identical emitted µDewy. Frontend 3.40 s, validation 5.19 s,
preparation 0.065 s, lowering 1.71 s, emission 0.37 s, backend 1.25 s.
Both backend-build and t0 measurements are isolated; the source, GCC flags,
and cache policy are unchanged. The native rebuilt µDewy passes the expected
word-memory and core-runtime programs on both direct and C backends.
Artifacts: `udewy-memory-refresh`, `native-current-micro-c`,
`native-built-current-micro-t0`, and `refreshed-micro-gates`.

### Hosted normalization shares child graphs

Hosted normal-form construction now memoizes repeated child identities within
one query. Checking gets a fresh memo for each query, so later mutations of
unions and unresolved descriptions remain visible. Existing stable lowering
scopes can reuse results between queries. Memo entries retain their input
objects; metadata-distinct descriptions do not become one stored description.
A changed shared child is normalized once and remains shared in its parents.

Twenty normalizations of a twelve-level shared graph take **0.79–0.84 seconds
before and 0.0025 seconds after**. Cold checking of the pinned tokenizer takes
7.25–7.35 s before and 7.17 s after; this is near the baseline, not evidence
of a substantial whole-checker speedup. An initial context-manager-per-query
implementation took 7.72–7.76 s and was replaced with an explicitly passed
memo before landing. Eleven selected checks pass, including the native/hosted
4,356-pair type-algebra matrix, deep shapes, mutation between queries, shared
normalized children, metadata retention, and nested lowering-scope lifetime.
Artifacts: `measure-nnf.py`, `nnf-*`, and `nnf-gates-final.log`.

### Refreshed native generations and hosted direct integration

Current µDewy generations two and three build in 3.42/3.32 seconds and have
identical executable SHA-256
`80f0edde749624a4f24c31f6dcda7a09aad3780e9e2c5c736f5f8fc044741222`.
Generation one refreshed the source from the older seed; generation two also
uses the new C helpers in its own executable. Subsequent native measurements
use generation three, recorded in `udewy-memory-generations.json`.

The current native-built Dewy executable, with that µDewy, builds frozen
`13b1ee96` through the direct backend in **149.47 seconds**, peak process RSS
5,877,064 KiB. Frontend 27.66 s, validation 24.65 s, preparation 5.14 s,
lowering 67.48 s, emission 5.52 s, backend 16.75 s. Its emitted µDewy exactly
matches the preceding generation: 48,818,721 bytes and SHA-256
`3ba35c9e07fcfbf4f16626ced7d0cafc5679075abbbb637c6c7172b26f1589f7`.
This verifies repeatable native Dewy emission and a µDewy executable fixed
point; it does not replace the remaining full pair/corpus/release gates.
The native lowerer's poor full-source scaling was not visible in the smaller
t0 benchmark. Artifacts: `native-built-structural-ids-full`.

The hosted direct-backend build of frozen `091eab3b` completes in **134.53
seconds**, peak process RSS 1,616,756 KiB: checking 54.54 s, lowering 34.27 s,
emission 4.67 s, hosted µDewy backend 35.25 s. It emits 34,492,849 bytes,
SHA-256 `15d4197a7f50978e5fa63a942d2938e82e011ab229eebee740aacecf867f91e1`.
This is a fresh full executable build with no C backend or preexisting build
cache; it remains above the sub-minute target. Its overall time is not a
like-for-like comparison with the earlier C-backend invocation. Artifacts:
`host-full-queries-direct`; frozen source and manifest: `source-hosted-queries`.

### Keep HIR traversal failure reporting out of reader effects

Sampling the native-built compiler's full lowering phase found dictionary
rebuilding in 230 of 450 stacks, chiefly during capture analysis. The HIR
traversal fallback used ordinary printing and `exit`, making its callers
transitively opaque to the borrowing analysis. Recursive readers consequently
copied their otherwise read-only inputs; a lazy symbol-key view repeatedly
rebuilt its index on those temporary copies.

The final traversal case now uses the existing runtime-assertion mechanism.
Unknown variants still report an internal error and exit 101, while failure
reporting no longer disables borrowing throughout callers. The assertion's
message expression remains part of the source effect analysis.

A native-compiled kernel with 64 functions, 4,096 identifier references, and
8,192 symbols takes **4.12 seconds before and 0.03 seconds after**. Cumulative
arena payload allocation falls from **1,094,064,136 to 11,599,240 bytes**, with
identical capture results. A repeated allocation check agrees; its timings
overlapped regression tests and are not an isolated benchmark. Seven selected
checks pass: capture allocation, valid/failing traversal, borrowing boundaries,
callback effects, worklists, index snapshots, and hosted/native effect agreement.
Two initial fixture issues (an inferred global-counter singleton annotation
and counting argv without the executable) were corrected before landing.
Artifacts: `capture-reader-gates`; full self-build impact remains to be measured.

The rebuilt native C seed then builds frozen `8a5c2b6b` through the direct
backend in **103.57 seconds**, down from 149.47 s. Lowering falls from
67.48 to **23.37 seconds**. Frontend 27.48 s, validation 23.46 s, preparation
4.73 s, emission 5.46 s, backend 16.75 s; peak process RSS 5,875,660 KiB.
This is an isolated fresh executable build and remains above the target.
Artifacts: `native-reader-effects-c` and `native-reader-effects-full`.

The seed was built with target `c`, while this measurement requested
`x86_64`. Their emitted µDewy therefore does not have the same hash: after
normalizing function names, the sole difference is the embedded `$target`
default in the checker session (`c` versus `x86_64`). Matching-target native
generations remain necessary for fixed-point certification. The refreshed
seed also passes the capture fixture with the same 11,599,240-byte allocation.

### Treat joining an array as a read

Both parameter-effect analyzers previously classified all array methods as
mutations. `join` now records a receiver read, matching its settled semantics
and the capture/write-target analysis. The separator expression still runs
through effect analysis, so a separator that writes through a place prevents
a read-only summary. The HIR descriptions now spell out that distinction.
Fifteen semantic/effect checks and eighteen join/call-storage checks pass,
including native/hosted summary agreement and aliasing argument evaluation.
Artifacts: `capture-reader-gates/join-effects.log` and `join-storage.log`.

### Index source lines while materializing runtime reports

A bounded profile of validation and preparation found runtime-report
materialization in 69 of 190 stacks. Source line lookup repeatedly scanned
the file prefix: line number, line start, and line end each repeated that
work. The lowering pass now builds a grapheme-based line index lazily for
each source it reports on, then uses binary search. The cache dies with the
pass; mutable source files cannot leave stale geometry in a later session.

In an isolated native-compiled kernel, locating 1,000 end-of-file reports in
a 1,000-line source takes **10.88 seconds before and 0.0053 seconds after**,
including index construction. Arena payload allocation drops from
**5,184,003,544 to 1,796,656 bytes**. Both compute the expected location sum.
The first timing overlapped regression checks; `isolated-measurement.json`
is the retained performance comparison. Full-build impact remains unmeasured.

Hosted-built and native-built fixtures pass the same explicit geometry and
report-construction checks: empty sources, CRLF, trailing newline, combining
characters, emoji sequences, EOF offsets, multiline clipping, multiple source
identities, first-row offsets, assertion/expectation/fail reports, and repeated
lowering without duplicate helper construction. The geometry test compares
array entries explicitly; aggregate comparison remains the separately recorded
design/parity question. Artifacts: `source-lines-gates`,
`native-reader-validation-samples`, and `source-lines-*-gate*.log`.

### Group binding routes by their owning root

The same validation profile found whole-registry route scans in binding
invalidation. The native registry now stores route groups keyed by root;
route allocation, subtree queries, element promises, projected replacement,
and field initialization read just the relevant group. A binding's existing
`route_root` metadata locates its group for reverse lookup. This is the
primary representation, so rollback needs no separately synchronized index.
Route allocation order and per-root insertion order remain unchanged.

The isolated native kernel with 512 roots, 1,024 routes, and 10,000 paired
identity/subtree queries takes **0.169 seconds before and 0.028 seconds after**.
Its cumulative temporary allocation increases from **3.20 to 5.92 MB** due
to retrieving the small group views; the speedup comes from avoiding unrelated
roots, not from eliminating all temporary owners. Seven targeted tests pass,
covering scope/route identities, lookup cost, transaction rollback and ID
reuse, element promises, nested length terms, bounds validation, and container
membership snapshots. The kernel also passes through the native CLI.
Artifacts: `root-route-measurement`, `root-route-*-gate*.log`.

The native C compiler rebuilt with these changes (`3c699a2f`) completes a
fresh full direct-backend self-build in **91.00 seconds**, versus 103.57 s
before the batch. Frontend 26.78 s, validation **10.51 s** (was 23.46 s),
preparation 4.90 s, lowering 23.48 s, emission 5.71 s, backend 17.27 s;
peak process RSS 5,895,944 KiB. The generated µDewy is 49,055,931 bytes.
Both the source and library are frozen together. The resulting compiler
still exceeds the full-build target; matching-target generation verification
also remains separate from this measurement. Artifacts:
`native-indexed-validation-c`, `native-indexed-validation-full`.

### Filter hosted t0 probes by their possible starting character

Token classes now declare conservative first-character sets. The context
candidate cache filters against those sets while retaining match order,
longest-match selection, and precedence. Context-dependent number/string
matchers remain unfiltered. An extension overriding `eat` must redeclare
its prefix promise; otherwise it automatically uses exhaustive matching.
The cache is bounded so arbitrary Unicode input cannot grow it indefinitely.

Parsing the same 112 frozen compiler sources through t2 falls from **10.22
to 8.12 seconds**, with byte-identical serialized token streams in every
case. Seventy-two targeted checks pass, including exhaustive/indexed token
and diagnostic comparisons, subclass extensions, and incomplete-source
reporting. Artifacts: `hosted-t0-probes-{before,after}.json` and
`hosted-t0-candidate-gates.log`. Full hosted build impact is not yet measured.

### Precompute native operator binding powers

Frontend sampling found precedence lookup in 51 of 185 stacks. Each lookup
scanned every precedence row and repeatedly acquired the row's operator set.
The native parser now derives a symbol-to-powers dictionary once from the
existing table. Multiple fixities and ambiguous juxtaposition still merge all
possible powers; absent sides are assigned only after merging alternatives.
Reserved operators without precedence remain unresolved as before.

An isolated native kernel making 3,000 lookups falls from **0.211 to 0.0167
seconds**, and cumulative payload allocation from **84,856,008 to 4,728,008
bytes**. The allocation gate and 145 parser/table checks pass, including all
hosted precedence entries, repeated/unknown alternatives, parser fixture
trees, diagnostics, Unicode spans, and invocation behavior. An initial test
incorrectly shortened the hosted `CombinedAssignmentOp` label; correcting the
test's spelling made it exercise the intended entry. Full self-build impact
is not yet measured. Artifacts: `native-indexed-frontend-samples`,
`binding-power-measurement`, `binding-power-*-gates.log`.

### Share hosted generated signatures and preserve HIR graph sharing

The updated hosted lowering profile records 282,281 constructions of the same
word-binary signature, and substantial work rediscovering locals and rebuilding
shared HIR. Generated primitive-only intrinsic signatures now belong to one
lowerer; composite metadata and signatures from other compilations cannot enter
that cache. Local-name preparation caches class traversal metadata and visits
shared subtrees once, preserving sharing through per-function renaming.

Sixty-two focused checks pass, including a 24-level shared expression graph
whose shadowed binding must be renamed without altering the original, signature
width/lifetime distinctions, ownership identities, and static-array execution.
The frozen t0 module emits identical µDewy apart from output-directory paths.
Its fresh full build regresses from **11.79 to 12.39 seconds** (lowering 1.58
to 2.01 s); this batch is not a demonstrated small-module win.

The full frozen `3c699a2f` compiler builds through the hosted direct route in
**129.37 seconds**: checking 54.49 s, lowering **29.00 s**, emission 4.53 s,
backend 35.98 s; peak process RSS 1,615,208 KiB. The earlier full hosted result
was 134.53 s with 34.27 s lowering, on the slightly earlier `091eab3b` source;
that source difference limits the before/after comparison. Neither reaches
the target. Artifacts: `hosted-current-lowering.prof`, `host-signatures-t0-*`,
`host-shared-signatures-full`, and `hosted-signature-gates.log`.

### Avoid serialized keys for native primitive-type hits

The refreshed native lowering profile found primitive creation in 42 of 159
stacks, with quoting and string construction inside the supposedly cheap hit
path. A type table now remembers primitive ids by their original names. The
cache forks with the table and clears on suffix truncation, before ids can be
reused. A miss still uses the canonical storage-key interner, including
descriptions installed directly through `intern`.

An isolated native kernel making 20,000 repeated queries falls from **0.233
to 0.00481 seconds**; payload allocation falls from **86,080,000 to 320,000
bytes**. Three targeted tests pass, covering primitive allocation, table
snapshots, rollback, id reuse, direct interning, and the existing structural
factory/query gates on direct and C backends. Full native self-build impact
remains unmeasured. Artifacts: `primitive-lookup-measurement`,
`primitive-lookup-gates.log`, `native-indexed-lowering-samples`.

Rebuilding these native changes together (`74df3542`) brings the isolated
fresh direct-backend self-build to **79.46 seconds**, versus 91.00 s at the
preceding checkpoint. Frontend **20.61 s**, validation 10.30 s, preparation
4.84 s, lowering **18.87 s**, emission 5.62 s, backend 16.80 s; peak process
RSS 5,930,452 KiB. Emitted µDewy is 49,208,780 bytes. The refreshed compiler
also compiles and executes the primitive lookup fixture with expected result
42 and 320,000-byte allocation. Source and library are frozen together in
`source-precedence-primitives`; artifacts are `native-precedence-primitives-c`
and `native-precedence-primitives-full`. This remains above the target and
does not replace matching-target fixed-point and corpus certification.

### Space out Python collection while constructing compiler graphs

Collection callbacks measured **13.49 seconds** of cyclic GC in a 72.99 s
hosted emission run using the existing prelude cache. Lowering alone triggered
five full-heap collections taking 7.52 s while its graph was still live.
This observation is not a cold-build acceptance measurement.

The Python implementations now raise the allocation threshold to 50,000
during code generation and µDewy compilation. Cyclic collection stays enabled;
an embedding caller's disabled or higher-threshold policy is respected, and
the original thresholds are restored on success or failure. Nested compiler
calls retain the outer policy. This changes Python implementation scheduling,
not Dewy or µDewy storage semantics.

On the **same frozen `3c699a2f` source and library**, the isolated fresh full
hosted direct build falls from **129.37 to 117.49 seconds**. Checking 51.17 s,
lowering 24.06 s, emission 4.56 s, backend 32.29 s. Peak process RSS rises
from 1,615,208 to **1,629,400 KiB** (about 14 MiB, under 1%). Generated µDewy
is byte-identical after normalizing only build-directory include paths.
Five policy tests cover nesting, failure restoration, caller overrides, and
cycle reclamation. Artifacts: `hosted-gc-events.json`,
`host-collection-threshold-full`, `collection-threshold-output-check.json`,
and `compilation-gc-policy-gates.log`.

### Bound allocator size-class calculations

Allocator class lookup now handles common descriptor sizes directly and uses
a bounded bit-length calculation for larger blocks. Computing a class's width
uses a shift instead of a second doubling loop. Free-list layout, counters,
block reuse, and zeroing remain unchanged. The unsigned shift count is explicit;
the native compound-shift contextualization gap found here is retained in the
parity inventory, with ordinary assignments used in the library for now.

The isolated native kernel makes 1.2 million class/width pairs across descriptor
and array sizes: **0.0477 seconds before, 0.0244 seconds after**, with identical
checksum 107486081600000. Seven targeted checks pass, covering power-of-two
boundaries, zero/small requests, width wrapping, reused-block clearing, live-byte
accounting, and string/loop regions; the boundary test runs on both backends.
Full native build impact is not yet measured. Artifacts:
`arena-class-measurement`, `arena-class-storage-gates.log`.
