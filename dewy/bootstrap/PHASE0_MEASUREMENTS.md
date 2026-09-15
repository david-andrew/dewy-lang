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
`--cache-state warm` performs a separately recorded priming build, removes
the executable, and times a fresh process rebuilding it with analysis caches
retained. This measures a warm rebuild, not the CLI's up-to-date-binary
shortcut. Priming observations remain under `run-XX/priming/` with separate
logs; a failed priming build is not reported as a warm sample.
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

### µDewy trivia and precedence queries

The hosted scanner now consumes adjacent whitespace/comments as one run and
continues directly to its following token; provisional-colon diagnostics still
run before skipping layout. Identifier starts and provisional token kinds use
precomputed sets. The hosted expression parser uses a precedence table, and
both expression parsers query precedence once per edge. Hosted line indexing
scans newline matches rather than iterating every character in Python.

On the saved 34,845,199-byte hosted self-build input (3,238,688 tokens), isolated
stage measurements before/after were 6.430/5.838 seconds for tokenization and
14.752/11.855 seconds for parsing plus assembly emission. Both token hashes
and the complete 154,658,886-byte assembly hashes are identical. This is a
backend-stage measurement, not a new full-build result. Artifacts:
`phase0-performance/hosted-micro-stages-{before,after}.json` and
`micro-scanner-gates.log`. All 42 targeted scanner, annotation, precedence,
debug-location, and conditional-short-circuit checks passed, including execution
through the hosted and bootstrap µDewy compilers.

### Optional µDewy debug metadata

Both µDewy CLIs now accept `--no-debug-info`; their default remains unchanged.
Ordinary Dewy builds request it, while `dewy debug` retains source maps and
variable metadata. Skipping metadata also skips source-line/marker indexing,
variable-scope construction and DWARF assembly; diagnostics and breakpoint
instructions remain intact. This changes tooling metadata, not µDewy evaluation
or its conditional-only short-circuit rule.

On the same saved hosted input as the scanner measurement, parsing/emission
fell from 11.855 to 8.526 seconds; assembly fell from 154,658,886 to 111,248,215
bytes. With the native µDewy compiler and the saved native self-build input,
complete backend invocations took 16.93 seconds with metadata and 13.04 without;
peak RSS fell from 2,994,132 to 2,570,892 KiB. Assembly fell from 222,639,473 to
143,027,454 bytes, and executable size from 42,767,192 to 27,914,448 bytes.
The two executable `.text` sections have identical SHA-256
`8504e2c43893b2ae399e21e5388ab2f912facffbd827e1b6de09de370ef7944c`.
These are backend measurements, not full Dewy-build timings.

Three C-accelerated native µDewy generations produced the same executable hash
`7e3fd2d95de4497361564aadc47f876c1a66872f7ae68455f36bc33adecc49fd`.
Fourteen targeted µDewy metadata/diagnostic/short-circuit checks and four Dewy
CLI, source-map and invocation-option checks passed. The Dewy CLI regression
checks ordinary and debug assembly, execution and separate cache artifacts.
Artifacts: `phase0-performance/hosted-micro-no-debug.json`,
`native-micro-debug-metadata.json`, `udewy-debug-stages.json`,
`micro-debug-metadata-gates.log`, `dewy-debug-metadata-gates.log`.

### Full-build checkpoint after metadata and allocator changes

Revision `3c89ce12`: a fresh hosted full executable build of the same frozen
`3c699a2f` source/library used by the previous hosted baseline took **109.877
seconds** (117.493 previously). Checking/lowering/emission/backend were
51.694/24.138/4.610/23.777 seconds; peak RSS 1,379,052 KiB. The updated native
C seed built frozen `3c89ce12` source/library into a direct executable in
**72.661 seconds** (79.460 for the previous seed/source checkpoint). Native
frontend/validation/preparation/lowering/emission/backend were
18.738/9.728/4.653/18.333/5.584/13.294 seconds; peak RSS 5,916,612 KiB.
The native comparison includes the allocator and source changes, not just
metadata. Neither result meets the 60-second target. The native executable
still embeds a different target than its C seed; this is not a matching-target
Dewy fixed-point certificate.

Artifacts: `phase0-performance/host-debug-metadata-full`,
`native-debug-metadata-c`, and `native-debug-metadata-full`. All use fresh
processes and build directories; OS caches are uncontrolled.

### Shared ambient-effect graph for native borrowing

Borrowing now traverses each function once to collect opaque operations,
global writes, reverse call edges, and the subset of edges which share caller
storage through places or captures. Three separate worklist propagations
retain the previous distinctions: ambient mutation, opaque effects affecting
borrowing, and actual storage retention. Standalone ambient queries remain
available. Installed failure-support code remains separate from source-message
effects, as before.

A 256-function/17,408-node synthetic graph queried eight times took a median
**1.190 seconds before and 0.406 seconds after** (three runs each, native C seed
`3c89ce12`, direct x86-64 kernel). Cumulative payload allocation fell from
**496,219,552 to 168,786,208 bytes**; both returned checksum 4104 and exit 42.
Artifacts: `phase0-performance/ambient-graph-measurement` (inputs, build logs,
three samples and results). The comparison compiles the prior graph walk from
frozen `3c89ce12` and the shared walk from the working source using the same
compiler and runtime library.

All five source-effects/storage-boundary fixtures passed, including the new
explicit global-write/value-call/place-call/capture-call distinction in
`native_ambient_graph.dewy`; the existing fixtures cover recursive propagation,
unknown callbacks, failure messages and indexed borrowing. Four additional
hosted container-flow execution checks passed on direct x86-64 and C. This
batch has not yet received a full native self-build performance measurement.

### Hosted string-body queries and debug-variable collection

String lowering now retains each literal's initializer candidates and return
expressions within one lowerer, instead of rescanning that body for individual
variable queries. Rewritten function literals have independent entries; cache
entries retain their literal so object-id reuse cannot cross bodies. String
walkers also reuse the existing dataclass-field metadata cache. Ordinary
emission explicitly skips the checker's debug-variable collection; typechecking
API defaults and debug emission retain their previous metadata behavior.

A 256-local body queried 1,000 times took 1.817 seconds before and 0.001813
seconds after, returning the same 256,000-entry checksum. A fresh hosted `t0`
module executable build took 11.335 seconds before and 10.436 after; lowering
fell from 1.346 to 1.205 seconds and peak RSS from 161,304 to 140,824 KiB.
Both emitted the same µDewy after normalizing the build directory and the
physical path of an identical casefold data file. The latter path follows the
hosted package location; both files' bytes were checked, rather than assuming
the library-root option pinned this include. These are bounded measurements,
not a new full-build result. Nineteen string storage/ownership, rewritten-body,
and ordinary/debug CLI checks passed.

Artifacts: `phase0-performance/string-candidate-{before,after}.json`,
`hosted-string-queries-{before,after}`, `hosted-string-query-output-check.json`,
and `hosted-string-query-gates.log`.

### Resolve transitive effects only for places

Both effect analyzers now resolve and pair a callee only when a call contains
a place argument. Evaluating the callee and every argument still contributes
its effects. Ordinary value arguments cross an independent-value boundary,
so the callee's parameter summary cannot add a mutation or escape to the
caller's value. Native pairing is deferred to the first place in the call;
subsequent places reuse it. Existing opaque-call and recursive-place behavior
is unchanged.

For 64 functions with 32 value calls each, analyzed eight times, native median
runtime fell from 0.466 to 0.329 seconds across three runs; cumulative payload
allocation fell from 195,842,016 to 136,594,144 bytes. All 512 checked parameter
summaries remained root reads with no mutation, rebinding or escape. The same
hosted query workload improved more modestly: median 0.210 to 0.194 seconds.
Fifteen hosted/native effect tests passed, including value versus place calls,
indirect calls, recursive propagation, routes and dependency-worklist budgets.
Artifacts: `phase0-performance/value-call-effect-measurement`,
`value-call-effects-{before,after}.json`, and `value-call-effect-gates.log`.

### Lowering state reuse and integration checkpoint

Hosted lowering now shares one private nominal type graph across its runtime
representation queries. Checking has already settled that graph; lowering
only asks subtype questions and does not add links or promotion rules. Primitive
equality signatures also share lowerer-local instances. Each compilation gets
fresh state. Fifty-eight targeted query-cache, family-union, brand, container
and enum checks pass, including an assertion that lowering constructs its
nominal graph once.

The next fresh hosted full executable build, with the same frozen `3c699a2f`
source and library, took **106.375 seconds**, versus 109.877 at the prior
checkpoint. Checking took 50.232 seconds, lowering 22.103, emission 4.512 and
the backend 24.175; peak process RSS was 1,376,292 KiB. This includes the string
query and lazy effect-pairing batches above, not just nominal-graph reuse.
Generated µDewy remains 34,759,644 bytes and is byte-identical after normalizing
build directories. Artifacts: `phase0-performance/host-lowering-state-full`,
`lowering-state-output-check.json`, `lowering-type-system-short-gates.log` and
`lowering-type-system-cache-gates-fixed.log`. The latter rerun corrects a test
fixture's accidental collision with the prelude's `Child` type.

The native integration checkpoint uses the C-built `910f4ea3` seed, frozen
source/library at that revision, and the µDewy seed supporting debug-metadata
omission. It took **73.017 seconds**, effectively flat against the preceding
72.661-second sample. Frontend, validation, preparation, lowering, emission and
backend took 19.647, 9.470, 4.564, 17.528, 5.802 and 13.669 seconds respectively;
peak process RSS was 5,896,268 KiB. The output was 49,038,939 µDewy bytes. This
is a direct executable build driven by a C-built compiler, not a new
matching-target fixed-point verification. Artifact: `native-effect-queries-full`.
The latest bounded GDB lowering sample still finds allocation/copy/release
inside effect traversal prominent; smaller effect-query kernels alone have
not established an end-to-end gain. Both full-build targets remain unmet.

### Read-only getter locals

Native lowering can now retain a getter's record result as a local view when
both the local binding and the source owner remain unwritten for the entire
function. The scope proof reuses capture/write summaries and the transitive
opaque-operation graph. Globals, captures, places, written bindings and
functions with opaque operations are excluded. A specialized getter preserves
its guards and side effects while returning the existing record storage.

This initial slice requires a direct getter with one terminal route read from
an explicitly supplied, non-default value parameter. The corresponding caller
argument must be an identifier already proven safe to borrow at that call.
Ordinary value boundaries still copy when required: returning the local,
passing it to a mutating callee, and storing it into another owned value retain
independent values. No new source spelling or ownership semantics is introduced.

The `native_getter_locals.dewy` gate reads a branded record with a string field
1,000 times, checks the sum, and requires **zero cumulative payload allocation**
for those reads. Expected-result checks cover local mutation, source rebinding,
place exposure, returned-value independence, temporary input owners, an omitted
default owner, a mutating getter, and a guard with an observable side effect.
All pass on direct x86-64 and C output. The existing scalar/aggregate projection,
return-cleanup and temporary-element checks also pass using the same freshly
built lowering driver. Artifacts: `phase0-performance/getter-locals-gates.log`
and `getter-locals-boundaries.log`. A full native measurement remains pending.

The getter-local integration checkpoint rebuilt the frozen `b342b2dc` compiler
twice through C. The first generation contains the lowering rule; the second
applies it to the compiler itself (four getter variants, 201 call sites).
Those builds took 146.590 and 141.134 seconds including C compilation.
The resulting second-generation compiler built the same source into a direct
executable in **67.754 seconds**, versus 73.017 at the prior checkpoint.
Frontend, validation, preparation, lowering, emission and backend took 17.653,
8.577, 4.555, 16.112, 5.338 and 13.147 seconds; peak process RSS was 5,910,864
KiB. This crosses neither the one-minute target nor a matching-target fixed
point. Artifacts: `native-getter-locals-c{1,2}`, `source-getter-locals.json` and
`native-getter-locals-full`.

### Hosted position-aware token probes

Common `t0` probes now scan the original source at an offset. Existing token
extensions can still provide the suffix-based `eat` method; unmatched legacy
probes share one lazily copied suffix at that position. Overriding `eat` clears
an inherited position-aware probe, just as it clears an inherited first-character
promise. Identifier, number, exponent, operator, delimiter and layout matching
retain their previous precedence and context behavior. The lone-carriage-return
warning now reports the file offset rather than the current suffix's offset.

Tokenizing the frozen 298,500-character native checker module took a median
**0.682 seconds before and 0.259 after**, across three samples each. An untimed
instrumented scan counted 77,305 whole-suffix copies totaling 11,386,251,761
characters before, versus 7,882 copies/1,168,144,429 characters after. The
remaining suffix probes primarily handle strings and comments; ordinary token
sequences have a zero-suffix-copy regression budget. All 113 frozen bootstrap
module token graphs are byte-identical when pickled, including source locations
and matching delimiter links. Eighty-four hosted token, diagnostic and parser
regressions pass. These lexer results do not establish a new full hosted build
time. Artifacts: `offset-token-{before,after}.json`, the corresponding logs,
and `offset-token-probe-fixed-gates.log`.

The scope proof now also accepts stable parameter field routes. Existing
parameter summaries distinguish mutations, rebinding and escapes on prefixes,
so writing `state.output` need not copy a local read from `state.input`.
A place owner additionally requires no ambient writes and, conservatively,
only one place parameter in its function. Captured and global owners remain
excluded. No index-disjointness assumption is introduced.
The extended gate performs another 1,000 getter reads through a place-owned
field while incrementing an unrelated field, again with zero payload allocation.
Writes into the owner field and writes through a global alias preserve the
original local value by taking the copy fallback. Both output targets and
all preceding getter/projection lifetime cases pass. Artifact:
`getter-field-locals-gates.log`. This extension is not yet in a native seed or
full-build timing; the 67.754-second result above covers whole-binding proofs.

### Hosted callable-shape selection

Juxtaposition with a resolved function name or namespace function export now
selects the call interpretation before checking impossible indexing/product
alternatives. Union types and functions accepting zero arguments retain the
general path: `make[0]` can index an implicitly called function's result.
Failed calls preserve the existing definite-error classification. Namespace,
object, keyword, generic and precedence checks pass, including execution of
the implicit-call indexing case and a budget against discarded index probes.

One cold build of the frozen `t0.dewy` module took **11.386 seconds before and
10.134 after**; checking took 7.203 and 6.699 seconds, respectively. This is a
bounded sample, not a new full-build result. Emitted µDewy is identical after
normalizing include paths, with all included bytes verified identical.
Artifacts: `hosted-call-shapes-{before,after}`, `call-shapes-output-check.json`,
`call-shape-fixed-gates.log` and `call-shape-namespace-gates.log`.

The field-aware getter checkpoint built two C generations of frozen
`3789e114` source/library in 141.297 and 140.457 seconds. Generation two
contains five getter variants and 430 call sites. Its full direct executable
build took **67.855 seconds**, effectively flat against 67.754. Frontend,
validation, preparation, lowering, emission and backend took 17.958, 8.156,
4.517, 16.245, 4.896 and 13.673 seconds; peak process RSS was 5,916,856 KiB.
The emitted µDewy is 49,178,122 bytes. The working tree had unrelated hosted
edits, but both source and library inputs came from the recorded snapshot.
Artifacts: `source-getter-fields.json`, `native-getter-fields-c{1,2}` and
`native-getter-fields-full`. This remains a measurement rather than a new
matching-target fixed-point certificate.

### Hosted stable-pass queries

Read-only bounds validation now shares representation/normalization queries
for one pass. Its scope ends before imports or representation selection can
change type descriptions. Lowering also builds each callable's runtime ABI
once, retaining the original type with its cached signature. Both caches
expire before later compilations; no cache spans mutable type resolution.
Sixty-nine targeted tests pass, covering cache lifetimes, callable ABI slots,
keyword calls, generics, places, conditional bounds and big-integer selection.
Artifact: `stable-pass-query-gates.log`. Full-build measurement is pending.

### Initialization certificates indexed by call

Native initialization indexes successful certificates by function and concrete
callback arguments. It previously scanned every certificate for every call.
Both implementations now record only caller-supplied initialization requirements;
parameters and receiver fields are initialized by the invocation. A cached
check therefore avoids copying the caller's full availability set. Recursive
ancestor assumptions and callback-dependent reads remain part of reuse checks.

The native kernel with 256 functions, 2,048 calls and 2,048 initialized bindings
took a median **0.603 seconds before and 0.088 after**, across three runs each.
Cumulative payload allocation fell from **311,951,160 to 43,036,392 bytes**;
both retained 256 certificates and returned the expected result. Both kernels
were compiled with the same field-getter C seed and µDewy seed. This is not
a new full-build measurement. Artifact: `initialization-cache-measurement`.

Hosted recursion, captures, objects and callback checks pass, as do the native
initialization comparisons with explicit ready/pending callback cases. An older
test still expected a copied global string literal; the preceding revision
already used static storage. Its assertion now matches that representation
and executes the program to verify startup initialization. Artifacts:
`initialization-caller-cache-gates.log`, `initialization-indexed-gates.log` and
`initialization-indexed-callback-gates.log`.

The next cold hosted full executable build took **99.962 seconds**, versus
106.375 at the previous hosted checkpoint. Both use frozen `3c699a2f` source
and library; hosted packages are now `dacac211`. Checking took 41.710 seconds,
lowering 23.109, emission 4.611 and the backend 24.374. Peak process RSS was
1,378,740 KiB; emitted µDewy was 34,759,636 bytes. This includes the offset lexer,
call-shape selection, stable query scopes and initialization certificates.
It remains above the one-minute target. Artifacts: `host-stable-passes-full`
and `source-initialization-index.json`.

### Packed initialization availability

Native initialization now represents available binding ids with a packed
bitmap. Compiler binding ids are allocated densely; certificates and recursion
sets remain sparse. A snapshot still has value semantics, but its first write
copies words of bits rather than the full availability hash table. Duplicate
insertion performs no write or detachment. The internal module documents why
this representation is inappropriate for arbitrary sparse ids.

The same initialization kernel took a median **0.098 seconds with indexed hash
sets and 0.025 with bitmaps**. Cumulative payload allocation fell from
43,036,392 to **9,539,288 bytes**, retaining 256 certificates in both cases.
Boundary checks cover ids 0, 63, 64, 127, 128 and 100,000, independent writes
to both snapshots, sparse requirement queries, and zero allocation for 10,000
duplicate insertions. They pass on direct and C output, alongside the native
initialization comparisons. Artifacts: `dense-initialization-measurement` and
`dense-initialization-unsigned-gates.log` (the final run uses an explicitly
unsigned shift count). No full native rebuild includes this batch yet.

The hosted full output comparison has the same 466,764 lines. After include
paths are accounted for, differences are 21 nominal-discriminator strings
and 3,071 lines containing checker-generated binding names or mangled nominal
ids. Eliminating speculative call readings changes those allocation counters.
There are no other differing lines; this structural comparison is not a
byte-identical result or a fixed-point certificate. Included bytes agree.
Artifact: `stable-pass-output-check.json`.

### Native owned returns

An explicit return of an unboxed, unconditionally owned local now transfers
its storage to the caller. The active cleanup entry proves ownership; that
entry is skipped only on the returning path. Borrowed views, caller-owned
arguments, conditionally owned defaults, captures and conversions retain the
copy fallback. Array length facts may differ when the element representation
is identical. No source ownership syntax or value semantics changed.

The return gate records allocation immediately after construction and requires
**zero additional allocation on return** for records, arrays, strings and union
values. It checks both return branches, independent caller-owned inputs,
rebound parameters and defaults, and stable live allocation across 100 complete
calls. Both direct and C outputs pass, along with the preceding getter-local,
projection, guard and temporary-lifetime checks. Artifact:
`return-move-storage-gates.log`. Lowering test drivers now omit debugger
metadata, which these execution checks do not consume. Full measurement of
the native initialization and return batches is pending.

### Generated exit suffixes

Both emitters stop a lowered statement list after an unconditional return,
break, continue, or exhaustive conditional whose arms all exit. Loops remain
conservative. This runs after source validation and ownership lowering, so
unreachable source still receives its semantic checks. It removes duplicate
returns and normal-exit cleanup that can never execute.

Native emission checks pass on direct and C output; hosted exit, initialization
and conditional-bounds checks also pass. The frozen `3c699a2f` tokenizer module
emits 1,916,646 bytes versus 1,917,447 before. Single cold invocations took
10.033 and 11.089 seconds respectively; the small text reduction does not
justify attributing that timing difference to this change. Artifacts:
`measure-exit-suffix.log`, `exit-suffix-gates.log` and
`exit-suffix-hosted-gates.log`.

### Initialization and owned-return integration checkpoint

Two C generations built from `8876bec6` source with the recorded compiler
wrapper in 140.530 and 136.057 seconds. The second generation applies the
new owned-return lowering to the compiler itself. Using that seed on the
same frozen `3789e114` source and library as the field-getter checkpoint,
a complete direct executable build took **63.796 seconds**, down from
67.855. Frontend: 18.114; validation: 7.529; initialization/reachability:
1.626; lowering: 15.871; emission: 4.796; backend: 13.535 seconds. Peak
process RSS was 5,902,900 KiB and output was 48,662,145 bytes. The target
is still unmet. This is an integration measurement, not a new fixed-point
certificate. Artifacts: `native-owned-exits-c1`, `native-owned-exits-c2`,
`source-owned-exits.json` and `native-owned-exits-full`.

### Hosted string body indexes

The read-only string return, initializer, candidate and iterator queries
share a body traversal, preserving shared HIR nodes and excluding nested
function bodies. Rewritten literals and new lowerers get fresh indexes.
Destination-ABI escape checks reuse discovery's runtime calls and identifier
bindings instead of traversing the whole program twice. Twenty-six focused
string ownership, region, local, scratch and index checks pass. Performance
measurement is pending. Artifact: `string-body-index-gates.log`.

The hosted body-index tokenizer measurement took 11.437 seconds before and
10.635 after; lowering took **1.068 and 0.944 seconds**. Both use frozen
`3c699a2f` source/library, with hosted packages `8876bec6` and `6dd53cbb`.
Generated output is identical after included bytes are verified and their
physical paths normalized. Artifacts: `measure-string-index.log` and
`string-index-output-check.json`.

### Signed structural normalization correction

A subtype comparison exposed an existing inconsistency: the positive side of
an array/record atom normalized its children, while the negative side could
retain a redundant intersection such as `int64 & any`. Both implementations
now normalize those children before complementing the outer atom. This does
not complement the element type. Hosted normalization and dispatch checks,
and native identity/rollback checks on direct and C output, pass (13 tests).
Artifact: `signed-normalization-gates.log`. This is a correctness fix needed
before comparing faster atom proofs against the general Boolean relation.

### Sufficient atom proofs before Boolean normalization

Both subtype entry points now accept an already successful atom implication
for records, arrays, strings, integer literals and callable types. A failed
probe still uses the complete emptiness relation; it does not become a
rejection. Hosted all-pairs comparisons against Boolean differences include
unnormalized nested types. The native algebra/dispatch/metadata comparison
and a zero-extra-type-entry gate for 64 fresh array widenings pass, alongside
hosted normalization and immutable-record checks (35 tests). No mutable
checker query is cached across calls. Measurement is pending. Artifact:
`atomic-subtype-pair-gates.log`.

The atom-proof checkpoint's two C generations (`dd972e99`) emitted identical
µDewy (SHA-256 `1b728a38679865b941059730ee27f0fd69e6b0f571a3c960eb669c124faf364e`).
The resulting seed built frozen `3789e114` source/library in **62.840 seconds**,
with 5,900,800 KiB peak process RSS and exactly the same emitted µDewy as the
owned-exit checkpoint. Phase timings were frontend 17.603, validation 8.117,
preparation 1.372, lowering 15.750, emission 4.669 and backend 12.997 seconds.
The small timing change is not strong evidence of a large win. The hosted
tokenizer comparison regressed from 9.983 to 11.136 seconds (checking 6.438
to 6.859); neither this single sample nor its earlier passes establishes a
hosted speedup. Artifacts: `native-atomic-subtypes-full` and
`measure-atomic-subtypes-module.log`.

### Bulk hosted µDewy based-data scanning and decoding

Valid binary/hex runs are scanned in bulk, preserving the first invalid
character's location. Packing removes comments and the existing separators,
then uses byte/integer conversion with the same right-padding of partial
bytes. No µDewy token kinds or expression semantics change.

For 256 KiB of payload with separators and comments, median scan-plus-decode
time over three runs fell from **0.275 to 0.00506 seconds for hex**, and from
**0.860 to 0.0186 seconds for binary**. Both produced identical expected bytes.
Packing, partial-byte, offset, invalid-digit, comment, scanner and constant
binding checks pass as part of the 59-test integration group. Artifacts:
`measure-bulk-data.log` and `direct-atoms-bulk-data-gates.log`. Full hosted
build impact is not measured yet.

### Direct atomic decisions and shared Boolean members

Both subtype implementations now decide an atom-to-atom comparison directly
after child normalization when the initial raw proof fails. Such a comparison
has one positive and one negative literal, so it does not require constructing
a Boolean formula. They also recognize shared-description containment among
union members and the dual rule for intersections. Membership misses retain
the general solver, and there is no persistent mutable checker cache.

The hosted all-pairs comparison includes raw nested conjunctions, reordered
unions, strengthened intersections, and immutable records. Native matrix and
dispatch comparisons pass; fresh union widenings and intersection projections
add no auxiliary type entries. These and the binary-data/scanner/cache checks
pass in the 59-test group (`direct-atoms-bulk-data-gates.log`). The preceding
atom checkpoint showed no hosted benefit; measure this broader replacement
before attributing a speedup.

The next cold hosted full build, using `cb6db449` packages and frozen
`3c699a2f` source/library, took **95.701 seconds**, down from 99.962 at the
previous full hosted checkpoint. Checking: 41.337; lowering: 20.653; emission:
4.752; backend: 23.142 seconds. Peak process RSS was 1,379,396 KiB and emitted
µDewy was 34,750,055 bytes. This includes body indexes, signed normalization,
bulk based data and the direct atom/shared-member rules. It remains well
above the target. Artifact: `host-direct-atoms-full`.

The measurement tool now records garbage-collection duration and reclaimed
objects by phase without changing collection policy. In this full invocation,
GC took 1.395 seconds during checking, 2.963 during lowering and 2.154 in the
backend (73, 103 and 66 collections respectively). There were no uncollectable
objects. These times are included in the phase and total invocation timings.

The preceding `dd972e99` C compiler generations also have byte-identical
executables: 6,108,840 bytes, SHA-256
`7fa1e6bf0378d1d5bfc357243c9e57df3ec5b03c96844d7ecdf80caf1b67798f`.
This confirms that Dewy checkpoint's binary fixed point; it does not replace
the complete paired corpus/release gates. Artifact:
`atomic-seed-binary-comparison.json`.

### Nested-function validation parity

The hosted bounds validator no longer records a function as checked during
an exploratory loop pass that suppresses diagnostics. The later validating
pass must inspect that body. The native validator already enforced this rule.
The frozen `cb6db449` hosted compiler accepted an inner function with an
unprovable `$assert` inside a loop; the corrected hosted and native visitors
both reject it and accept its explicitly guarded counterpart. These cases
and nominal/conditional-bound regressions pass (22 tests). Artifact:
`nominal-rejections-loop-functions-gates.log`.

### Nominal atom rejection and paired child normalization

A nominal target depends only on the source atom's outer category/brand.
Both implementations now keep its negative result without normalizing fields.
When two structural atoms do require child normalization, hosted queries
share one memo across both inputs. Tests retain mutable-description behavior
and require one visit per shared child; the complete native algebra matrix
also passes (`nominal-rejections-loop-functions-gates.log`).

The `cb6db449` native checkpoint, before this final nominal rejection change,
built frozen `3789e114` source/library in **61.487 seconds**: frontend 17.509,
validation 7.742, preparation 1.373, lowering 14.732, emission 5.000 and backend
12.828. Peak process RSS was 5,821,176 KiB and generated µDewy was unchanged
from the 63.796-second checkpoint (48,662,145 bytes). Both C generations
emitted identical µDewy. The one-minute target remains unmet. Artifacts:
`native-direct-atoms-full`, `native-direct-atoms-c1`, `native-direct-atoms-c2`
and `source-direct-atoms.json`.

### Hosted HIR to backend bridge

Ordinary hosted x86-64 and C builds now pass legalized HIR to the existing
µDewy backend protocol. They retain the emitted µDewy artifact, linker inputs,
and CLI behavior. Debugger builds and other targets keep the source route.
The bridge shares module setup, function reachability, static data, uncommon
word operations, and condition parsing with µDewy; it does not change µDewy's
conditional-only short circuiting. Checking and lowering run once.

In an in-process comparison using frozen `3c699a2f` parser `t0` source/library,
backend generation took 1.101 seconds through source/token parsing and 0.573
through the bridge. This is a bounded backend measurement, not a complete
invocation or an acceptance-target result. The resulting module programs
agreed on their missing-input diagnostic and exit status. Artifact:
`direct-bridge-module/results.json`.

Independent expected-result comparisons cover both backends for aggregate
snapshots, conditional side effects, indirect callee/argument order, Unicode,
integer widths, and static data. CLI checks cover binary includes, arguments,
timings, cached builds, and separate debugger metadata. The static/reference
group passes 51 tests; the initial CLI/cache/include group passes 31 tests.
Artifacts: `direct-bridge-static-gates.log`, `direct-bridge-cli-gates.log`.

The complete cold hosted build at `b4aef021` took **93.142 seconds** with
the same frozen compiler/library workload. Checking: 41.220; lowering: 21.456;
emission: 4.463; backend: 19.080 seconds. Backend GC fell to 0.028 seconds,
but retaining HIR through backend generation increased peak process RSS to
1,556,788 KiB. The emitted µDewy differs from the preceding build only in
four artifact/snapshot include paths. Artifact: `host-backend-bridge-full`.

### Hosted parser grammar queries

A fresh profile over 125 compiler/library modules found 18.3 million ABC
instance checks and repeated construction of numeric precedence alternatives.
Operator-union membership is now cached per concrete token class, preserving
subclass support. Combined precedence/binding-power descriptions are shared
by their numeric choices; token positions and ambiguity alternatives remain
per parse. This applies only to the fixed parser grammar, not mutable
semantic type descriptions.

Parsing the same 125 frozen modules, without profiling, took 12.194 seconds
before and 10.700 after. All 125 serialized parse trees were byte-identical.
The parser/reference, native differential, precedence, literal-boundary and
candidate-filter group passes 254 tests. Artifacts: `compare-parser-batch.log`,
`parser-grammar-before.json`, `parser-grammar-after.json`,
`parser-grammar-gates.log`. These are parser measurements, not another full
compiler build.

### Shared HIR syntax traversal

Hosted structural analyses now share child-field descriptions resolved once
from the HIR declarations. They visit checked syntax, including object fields,
bound parameters and keyword arguments, without repeatedly walking spans,
type descriptions or scalar metadata. Bounds assignment discovery,
initialization function discovery, bigint representation, module renaming,
effect/predicate scans and local renaming use this helper. Runtime evaluation
and effect ordering remain the responsibility of each analysis.

This also fixes a hosted bounds gap: mutation inside an object-field
initializer was omitted from the global-assignment inventory. A global could
then retain its initial constant bounds inside a function. The frozen hosted
compiler accepted the isolated bad assertion; the corrected hosted and native
validators both reject it. Artifacts: `hir-children-native-mutation.log` and
`tests/python_misc/test_hir_children.py`.

Before the final effect/local-renaming adoption, the representative t0 module
build changed from 10.284 to 9.232 seconds, with checking 6.349 to 6.170 and
peak process RSS 172,840 to 151,408 KiB. This is a modest checking improvement;
do not attribute the whole invocation difference to the traversal. The main
bounds/initialization/modules/representation group passes 47 tests, the added
native mutation comparison passes, and the final shared-traversal/effects/
borrowing/backend group passes 36 tests. Artifacts: `measure-hir-children.log`,
`hir-children-gates.log`, `hir-children-shared-gates.log`.

The compiler built through the hosted backend bridge passed the x86-64
integration bundle, then the larger native-pair script stopped at a stale
`State.length` access in `native_predicate_path_scaling.dewy`.
The preceding `host-direct-atoms-full` executable rejects the same case with
the same diagnostic. The indexed fact store exposes `State.values.length`;
the fixture is corrected accordingly. This was not an optional-array or
bridge regression. The rerun with the profile-guided seed passes the pair
execution script on both x86-64 and C, including analysis scaling and test
discovery (`check-pgo-native-pair.log`). Artifacts:
`check-host-backend-bridge-pair.log` and the two
`host-*-full-predicate-check/result.json` records.

### Profile-guided native seed experiment

The saved `cb6db449` native C2 source was recompiled with GCC 16.2.1 using
`-O2 -flto=8 -fno-tree-pre -fno-code-hoisting`, first with instrumentation and
then with the resulting profile. Training compiled frozen `3c699a2f` compiler
source/library; measurement compiled frozen `3789e114` source/library through
the direct backend, as in the preceding 61.487-second native checkpoint.
Profile mismatches and missing data were compilation errors.

The resulting full invocation took **54.894 seconds**: frontend 12.098,
validation 6.621, preparation 1.203, lowering 14.413, emission 4.078, and backend
14.436. Peak process RSS was 5,820,112 KiB. Generated µDewy was byte-identical
to the ordinary seed's output: 48,662,145 bytes, SHA-256
`de9ee754cbbd12840510b42a06ff5ee30854f30534a9160a750c053ff5bcb654`.
Focused tests may have overlapped part of this experiment; repeat the final
acceptance measurements without competing work. This first result crosses
the native time target, but does not complete Phase 0 or certify a release.

Instrumented seed compilation took 92.025 seconds, the training command
78.251, and profile-use compilation 85.826. These preparation costs are
reported separately; no training is needed for each later compiler invocation.
The reproducible shell procedure is `tools/profile_dewy_seed.sh`; real GCC
tests verify counter generation/use, an untrained execution path, and failure
when training produces no counters (two tests).

Artifacts: `pgo-seed-experiment/steps.json`, `metadata.json`, counter files,
`full-measurement/results.jsonl`, and `pgo-script-gates.log`. The pair execution
script passes both output backends (`check-pgo-native-pair.log`). The
unaccelerated bootstrap goal, full corpus/parity and release gates remain open.

The quiet repeat took **46.560 seconds**, with the same byte-identical µDewy:
frontend 11.454, validation 4.990, preparation 0.957, lowering 10.694, emission
3.772, backend 12.745; peak process RSS 5,820,448 KiB. No other tests ran
during this invocation. The native time target is met on this recorded route.
Artifact: `native-pgo-quiet-full`.

The corresponding quiet hosted checkpoint at `60260b89` took **87.749
seconds**: checking 37.440, lowering 20.064, emission 4.568, backend 19.466;
peak process RSS 1,517,688 KiB. It includes shared HIR traversal and parser
grammar lookups, and remains above the hosted target. Artifacts:
`host-shared-hir-full`, `source-shared-hir.json`.

### Literal-result effects in hosted bounds validation

A literal return type does not make a call pure. The hosted validator
previously returned the known interval before visiting a literal-typed
expression, losing mutations from its arguments/callee. For example,
`change=(@n:int64):>1=>{n=-1 return 1}` could leave an old positive fact about
`n` after `change(@n)`. The hosted visitor now evaluates the expression first
and then applies its literal result fact, matching the native validator.
The paired regression rejects the stale assertion while retaining the proof
that the result equals 1. Common member/call dispatch was also moved ahead
of unrelated expression kinds; call transfer rules and argument order are
unchanged. The bounds/conditional-result/bigint group passes 27 tests.
Artifact: `literal-result-effects-gates.log`.

### Consume saved x86 operands in their cache registers

At `e806569f`, both µDewy implementations consume saved binary operands and
store values directly from the x86 register cache. Division and shifts retain
the hardware-register staging they require. Spill, argument evaluation, narrow
store and boolean semantics are unchanged. The new deep-expression fixture
covers spills across direct/indirect calls, side effects, comparisons and stores;
the register/bridge group passes 46 tests (10 unavailable backends skipped),
and the final parity/ABI/extern group passes 44 tests.

On the frozen t0 module, assembly shrank from 6,497,957 to 5,527,668 bytes and
the executable from 1,291,912 to 1,144,456 bytes, with identical tokenization
output. That small compile-time sample did not improve (1.367 to 1.567 seconds).
The full hosted checkpoint took **85.529 seconds**, with checking 37.220,
lowering 19.556, emission 4.578 and backend 18.047; peak process RSS was
1,430,748 KiB. Artifacts: `cached-operands-module-results.json`,
`host-cached-operands-full`, `source-cached-operands.json`.

The initial native checkpoint took **54.579 seconds**, but used a directly
compiled µDewy seed where the preceding 46.560-second run used a C-compiled
µDewy seed. It is a separate route measurement, not a regression comparison.
The Dewy seed was still the same profile-guided C executable. Generated µDewy
remained byte-identical (48,662,145 bytes, SHA-256 `de9ee754…654`).

A quiet comparison recompiling that same emitted µDewy isolates the backend:

| µDewy seed | Complete backend invocation | Peak process RSS (KiB) | Assembly bytes | Executable bytes |
| --- | ---: | ---: | ---: | ---: |
| Previous, C-compiled | 12.841 s | 2,555,412 | 141,645,447 | 27,714,256 |
| Cached operands, C-compiled | 11.187 s | 2,243,732 | 118,210,066 | 24,347,344 |
| Cached operands, directly compiled | 19.704 s | 2,242,276 | 118,210,066 | 24,347,344 |

The two new seeds emit byte-identical assembly. The directly compiled µDewy
compiler reaches a byte-identical generation-2/3 fixed point (SHA-256
`0b822aac254e823c39a1f769b7ef5bc4e7125ce2d055a95702175c10ffd499a4`);
the C route also reaches an identical two-generation result (SHA-256
`e1336b24e1bd74c653c2f24cd203e51c7f0c789162b6e81f7ed5fe1f76f43e8c`).
These certify the µDewy builds only; the complete direct Dewy bootstrap and
remaining Phase 0 corpus/parity gates are still open. Artifacts:
`build-cached-operands-micro.log`, `build-cached-operands-c-micro.log`,
`cached-operands-micro-routes.json` and `native-cached-operands-full`.

### Bounds rules selected once per HIR class

The hosted bounds evaluator now has separate handlers for its expression
kinds, with cached class dispatch that preserves first-match inheritance.
Each visit still evaluates against the current fact state, including effects,
obligations and conditional evaluation. An unreachable duplicate obligation
branch was removed. Tagged integer records retain their existing constant rule.

The representative module's checking time changed only modestly, from 6.155
to 6.075 seconds; the complete samples were 9.283 and 9.482 seconds. This is
primarily a simplification and removal of repeated dispatch work, not evidence
of a major full-build speedup. Generated µDewy differs only in four artifact
include paths. The bounds/refinements/result-facts/HIR group passes 28 tests;
an additional inherited-node regression checks changing state and mutable-place
invalidation. Artifacts: `measure-bounds-dispatch.log`,
`bounds-dispatch-gates.log`, `bounds-dispatch-inheritance.log`.

### Stack allocations with live x86 expression spills

An isolated cross-backend test found a pre-existing µDewy x86 bug: an
`__alloca__` used as a later call argument moved the stack pointer away from
earlier spilled arguments, so later pops consumed the wrong words. Both x86
implementations now relocate live spill words below the allocated buffer.
Forward copying handles overlap for small buffers; popped arguments leave the
buffer alive until function return. The eight-byte allocation granularity and
µDewy's eager-expression/conditional-short-circuit rules remain unchanged.

The new fixture covers direct and indirect eight-argument calls, repeated
small/large/zero-size allocations, overlapping spill movement, and buffer
contents after subsequent allocations and calls. It passes through hosted and
native µDewy with x86 and C output; the full parity/ABI/extern group passes
46 tests. Artifacts: `alloca-spill-repro.json`, `alloca-spill-gates.log`.

### Lowering walks syntax and probes effect-route prefixes

The refreshed hosted lowering profile still spent time walking spans and type
metadata in dimension erasure, captured-write checks and string lifetime
queries. These passes now use the shared HIR child declarations, retaining
parameter/default traversal where required. Effect coverage probes the bounded
prefixes of a queried route instead of scanning every stored sibling route.
The quiet full hosted build took **82.525 seconds**: checking 36.142,
lowering 17.325, emission 4.436 and backend 18.074, with peak process RSS
1,473,360 KiB. Artifact: `host-lowering-syntax-full` (frozen `b6c5b387`
packages and the same frozen compiler/library workload).

The capture scan now reaches keyword argument expressions: a nested function
writing `n` inside `consume(value={n=7; 0})` previously passed hosted lowering.
The corrected hosted and native compilers both reject the unsupported capture
write. The isolated comparison is `captured-keyword-write-comparison.json`.

The ownership/string/effects group passes 86 tests; units, predicate effects
and container-removal facts pass 26, and lowering-query/capture regressions
pass three. Four test helpers still imported the old effects traversal; they
now use `hir.children`, and all 2,478 Python tests collect. Collection success
is not a full-suite execution result. Artifacts: `lowering-syntax-gates.log`,
`lowering-syntax-units-gates.log`, `lowering-syntax-capture-gates.log`,
`lowering-syntax-collection.log`, and `host-lowering-after-dispatch/lowering.prof`.


The corresponding quiet native checkpoint took **45.809 seconds** with the
same profile-guided C Dewy seed and the new C-built µDewy seed: frontend
11.924, validation 4.990, preparation 0.892, lowering 11.115, emission 3.895
and backend 11.022; peak process RSS 5,820,252 KiB. Generated µDewy remains
byte-identical at 48,662,145 bytes (SHA-256 `de9ee754…654`). The native pair
execution script passes both x86-64 and C output, including analysis scaling
and test discovery. Artifacts: `native-spill-safe-full`,
`check-spill-safe-native-pair.log`.

The allocation-corrected µDewy compiler again reaches identical two-generation
results through C (SHA-256
`a0c16d6859f7a33c30e4b29fb111eebfcb818ef394d5cee42f32f31807b9607a`)
and direct x86-64 (SHA-256
`036d0428f2d195ce7d54c85726ae28fb6b3ff322dfc09765fc68d15382fedc3c`).
The C generations took about 6.6 seconds each; direct generations took 0.30
and 0.44 seconds. This refreshes µDewy verification, not the complete Dewy
fixed point or release. Artifacts: `build-spill-safe-micro.log`,
`source-lowering-syntax.json`.

### Compact hosted compiler records

HIR, type descriptions, source spans and bounds intervals now use Python
slotted dataclasses. Their declared fields, mutability, weak references and
shared/cyclic pickle graphs retain their behavior; each instance no longer
needs an attribute dictionary. Parser cache identities now include the
reporting module, whose `Span` representation participates in cached syntax.
The custom path-literal constructor explicitly initializes its inherited
`immutable=False` field, previously supplied by the class default.

This also exposed `DictContains.hoisted`, which the hosted checker assigned
dynamically. It is now a declared field, matching native HIR and surviving
replacement/pickling. The initial failure took excessive memory while pytest
rendered a checker context; shorter traceback reporting isolated it. This was
a test-reporting cost, not a successful compiler invocation measurement.

The core/cache/type/recursive group passes 85 cases, followed by 109 storage,
units, effects, ownership, strings and container checks (including the corrected
new storage fixture). A quiet t0 module comparison changed 9.282 to **8.780
seconds**, checking 6.221 to 5.866, with peak process RSS 141,768 to 134,396 KiB.
Generated µDewy differs only in four include paths. The subsequent quiet full
build at `1a83d30a` took **85.881 seconds**: checking 38.956, lowering 18.033,
emission 4.515 and backend 18.960; peak process RSS 1,347,288 KiB. Memory falls,
but this full invocation does not establish a speed improvement over the
82.525-second prior checkpoint. Artifacts: `host-compact-records-full`,
`slotted-records-core-fixed-gates.log`,
`slotted-records-execution-gates.log`, `measure-record-storage-module.log`,
`slotted-records.diff`.

The checker context now has a bounded diagnostic representation rather than
recursively printing shared module contexts and syntax. The regression checks
that it does not visit either module backreferences or synthesized syntax.
Artifact: `context-display-gates.log` (one passing test).

### Direct condition/integer emission and demand-driven string lengths

The fresh hosted profile separates checking, lowering, and backend generation
(`host-compact-stage-profiles`). Checking consumed 78.713 profiled seconds,
excluding parsing; lowering consumed 55.990. Backend generation consumed
42.236, with 88,310 generated fragments accounting for 18.299 seconds of
printing/tokenizing/parsing. These are profiled costs, not invocation times.

The HIR bridge now emits lazy `and`/`or` conditions and signed/unsigned narrow
integer operations with the existing µDewy backend primitives. Value
expressions remain eager at that layer; Dewy's value-position lazy operations
have already become control flow during lowering. Static data and uncommon
fragments retain the source parser. The string-literal type relation computes
byte, scalar or grapheme length only when the target demands that unit.

The bridge's seven existing execution checks pass both direct x86-64 and C;
seven added length/condition/width checks pass, including nested negation,
loop conditions, 16/32-bit wrapping, combining characters, CRLF and emoji.
A quiet module comparison changes **8.932 to 8.732 seconds**, checking 6.077
to 5.928 and backend 1.013 to 0.870. Peak process RSS changes 140,020 to
133,884 KiB. Full-build impact remains unmeasured. Artifacts:
`direct-condition-width-gates.log`, `direct-condition-new-gates.log`,
`measure-direct-fragments-fixed.log`; baseline packages are frozen from
`1a83d30a` in `source-direct-fragments-before`.

### Reuse unchanged storage cleanup and emit literal globals directly

The final storage passes retain unchanged blocks and flow arms, comparing
child identity rather than structural equality. Distinct occurrences remain
distinct; changed parents are still rebuilt without modifying their input.
The storage/array-sharing group passes 13 tests. Region/release checks pass
12 initially, with three older object-release expectations also failing when
unconditional reconstruction is restored. Those checks now follow the shared
release helpers and distinguish initial string materialization from the
subsequent move of array elements; all six object-release cases pass.
Artifacts: `storage-cleanup-gates.log`, `storage-region-release-gates.log`,
`storage-region-release-baseline.log`, `object-release-updated-gates.log`.

The quiet full checkpoint at `06657fe4`, including direct condition/integer
emission, takes **77.970 seconds**: checking 36.687, lowering 17.235, emission
4.427 and backend 14.183; peak process RSS 1,347,376 KiB. This is an improvement
from 85.881 seconds, but remains above the hosted target. The separate native
checkpoint remains 45.809 seconds on the recorded PGO C-seed route.
Artifact: `host-direct-cleanup-full`.

The next bridge batch emits literal global bytes and stable word tables
through µDewy's existing static values/relocations. Unsupported initializers
fall back before allocating any partial static word table. Forward callable
references and mutable-global initializers keep the parser's handling. Nine
bridge execution cases pass both direct and C output; two additional checks
compare the complete generated assembly/C text against source-parsed static
declarations, including a retained callable reference and dynamic fallback.
The quiet module comparison changes 9.533 to **8.380 seconds**, with backend
0.837 to 0.758; variation in checking and startup also contributes to the
whole-invocation difference. Full-build impact of this last batch is not yet
measured. Artifacts: `direct-static-data-gates.log`,
`direct-static-relocation-gates.log`, `measure-static-data.log`.

### Token context inventory and recursion dispatch

The first seven t2 rewrites operate independently inside token lists and do
not replace list-containing tokens. They now share one inventory of those
lists, retaining phase order. Partial operators, operator functions and
keyword/chaining passes keep their recursive ordering because they inspect
or replace containers. Recursive helpers remain available for the reference
comparison. Token recursion also reuses the fixed registry's concrete-class
handler, including inherited handlers, without repeating generic dispatch's
weak-key bookkeeping at every leaf.

Across the same 125 compiler/library source files, quiet parsing changes
**10.389 to 9.310 seconds**. Every serialized AST hash matches the preceding
parser. The 18 grammar/dispatch/reference-pipeline checks and 103 token,
literal-boundary, partial-operator and precedence checks pass. Artifacts:
`parser-contexts-{before,after}.json`, `token-context-inventory-expanded-gates.log`,
`parser-context-integration-gates.log`. The preceding profile is
`host-parser-compact.prof` (42.618 profiled seconds); no full-build improvement
is inferred from that profile or the standalone parse measurement.

### Scoped subtype decisions

Subtype results and normalization are reused inside individual pure type-test,
join, and overload decisions. Checking never carries that cache across an
alias/fact update or generic body check. The existing stable validation and
lowering scopes also reuse compound subtype results. Entries retain operands,
separate type systems, and invalidate that system's relations when its nominal
graph changes. Primitive reachability keeps its direct path.

The cache/type/dispatch group passes 59 cases; a further 46 join, narrowing,
literal and type-fact cases pass. The full `type_facts.dewy` fixture fails in
both the changed compiler and the frozen pre-cache compiler: a known prefix
length is not substituted into a symbolic slice-remainder relation. That
existing proof gap is separate follow-up work, not a passing gate.
A quiet module comparison changes **9.182 to 8.230 seconds**, with checking
5.918 to 5.634; startup/checking variation contributes to the whole-invocation
difference. Artifacts: `subtype-decision-gates.log`, `subtype-flow-gates.log`,
`type-facts-prior-cache-baseline.log`, `measure-subtype-decision.log`.

### Named-prefix slice facts

The shared call-result transfer now retains both a named prefix's symbolic
remainder relation and the numeric consequence of its known minimum length.
Previously the symbolic case suppressed the numeric one, so advancing a
scanner by a known delimiter width lost its bound. The complete hosted
`type_facts.dewy` fixture now passes. The 26-case gate includes rejection of
excessive advancement and source mutation, and a compiled native transfer
check for both facts and invalidation. Artifact: `named-prefix-fact-gates.log`.
This closes the proof regression noted above; it does not close the native
fixture's earlier type-predicate acceptance gap.

The next quiet complete checkpoint, at `aa5af033`, takes **76.564 seconds**:
checking 36.298, lowering 17.064, emission 4.446 and backend 13.084; peak
process RSS 1,344,956 KiB. This includes the static-data, token-context, scoped
subtype and named-prefix batches. The hosted target remains unmet. Artifact:
`host-static-context-subtype-full`.

### Nominal token classification

Token kinds now use ordinary Python inheritance tests, preserving ABC
abstract-method enforcement. Virtual registration is explicitly unsupported:
it cannot supply token fields or enter the existing descendant-based token
inventory. Contexts likewise use ordinary inheritance. This removes the
virtual-subclass bookkeeping from millions of parser membership tests without
changing grammar, precedence, candidate order or subclass extension handling.

The 122 parser, extension, abstract-contract and diagnostic checks pass.
Quiet parsing of all 125 compiler/library files changes **8.872 to 7.428
seconds**, with identical serialized AST hashes. Full-build impact remains
unmeasured. Artifacts: `token-membership-fixed-gates.log`,
`measure-token-membership.log`, `parser-token-membership-{before,after}.json`.
An exploratory conservative count of lowered function references found only
one unreferenced function (357 bytes) in this self-build, so moving function
reachability earlier was not pursued as a performance optimization.

### HIR child plans and Python collection batches

Structural HIR walks derive flat node, node-list and keyword-map access from
the existing annotation inventory once per class. Mixed containers still
use the general traversal. Preorder walking uses an explicit stack, retaining
field order and repeated shared occurrences without recursive generator
forwarding. The native traversal already selects fields from its node kinds.
The 14 child-plan, native traversal, bounds-dispatch and lowering-index checks
pass, including a depth-2000 walk and comparison to the generic field walker.

The Python compilation scope also increases its ordinary allocation interval
from 50,000 to 500,000, keeping automatic cycle collection enabled and
restoring the embedding caller's policy. Existing deliberately large caller
thresholds remain untouched. All five policy checks pass. The module sample
changes 9.133 to **8.381 seconds**, with checking 5.848 to 5.732 and lowering
0.703 to 0.758; collection work moves between phases rather than disappearing.
This small workload does not establish a full-build benefit or memory cost.
Artifacts: `hir-child-plan-gates.log`, `collection-batch-gates.log`,
`measure-hir-plan.log`.

The quiet full checkpoint at `f356a528` takes **73.711 seconds**: checking
33.419, lowering 16.952, emission 4.465 and backend 13.474; peak process RSS
1,280,744 KiB. This combines nominal token classification and HIR child plans
with the collection policy. Collection counts fall substantially, but their
total observed cost is still about four seconds, so the timing does not
establish a substantial collection-time improvement. Artifact:
`host-token-hir-collection-full`.

### Constructor field inventory

Ordinary dataclass reconstruction in lowering, emission and checking now
reuses the constructor field-name inventory. It still reads current instance
contents, skips reading overridden fields, calls the normal constructor and
post-init hook, and creates a fresh record even for an unchanged replacement.
Records with pseudo-fields or non-init fields retain standard dataclass
replacement. This caches class rules rather than mutable object values.

The 22 initial passing reconstruction/storage checks, four final constructor
and reference-output checks, and 45 checker/type/prelude-cache checks pass.
The source-output comparison uses standard reconstruction throughout both
checking and lowering as its reference. The bounded module comparison for
the lowering/emission part changes **9.333 to 8.229 seconds**; lowering changes
0.871 to 0.779. Checking/startup variation also contributes to the total.
The checker extension's full-build effect remains unmeasured. Artifacts:
`reconstruction-gates.log`, `compilation-reconstruction-reference-gates.log`,
`checker-reconstruction-corrected-gates.log`, `measure-reconstruction.log`.

### Direct bridge dispatch

The fresh module profile finds only 304 source-parser fallbacks, totaling
about 0.005 seconds without profiling. The larger remaining bridge cost is
its per-expression and per-call dispatch. Expressions now select a handler
once per concrete HIR class (including inherited classes). Calls classify
operator names once and reuse backend-local intrinsic arity/static-argument
metadata. Every occurrence still emits in evaluation order.

All 11 existing bridge cases pass on direct/C output. Two additional cases
exercise inherited node classes and two evaluations of one shared call node,
with explicit result 12 through both the source and HIR routes. Three paired
module code-generation samples have identical assembly/C hashes throughout.
Median generation time changes **0.330 to 0.290 seconds** for x86-64 and
**0.384 to 0.348 seconds** for C. These timings exclude checking, lowering and
external toolchain work; they are not whole-build results. The measurement
driver now records source loading, code generation and toolchain time within
the existing aggregate backend phase to locate the remaining complete-build
cost. Artifacts: `host-backend-current-module/backend.prof`,
`profile-bridge-fragments.log`, `bridge-dispatch-gates.log`,
`bridge-dispatch-occurrence-gates.log`, `bridge-dispatch-module/results.json`.

The quiet complete checkpoint at `11edf7b6` takes **70.904 seconds**:
checking 32.801, lowering 15.891, emission 4.432 and backend 12.263; peak
process RSS 1,281,348 KiB. Within the backend, code generation takes 5.055
seconds and assembly/linking 7.091. The hosted target remains unmet.
Artifact: `host-reconstruction-dispatch-full`.

On that exact assembly, GNU `as` takes 6.426 seconds, LLVM `llvm-mc` 6.779
and Clang's integrated assembler 7.179; linking takes 0.866–0.917 seconds.
Each resulting compiler passes a `--help` smoke check. This is a toolchain
timing experiment, not full compiler verification; GNU remains the default.
Artifact: `assembler-comparison/results.json`.

### Immediate word operands

Both µDewy parsers recognize a literal right operand only when it occupies
the complete expression at the current precedence. Calls, casts and tighter
operators retain recursive parsing. The backend protocol supplies a normal
stack-sequence fallback; x86-64 uses immediate arithmetic, bitwise operations,
signed comparisons and masked shifts where encodable. The HIR bridge uses
the same operation. Older saved operands remain untouched, boolean results
remain all-zero/all-one words, and condition-only short circuiting is unchanged.

The 38 µDewy parity, precedence, immediate and HIR bridge cases pass, including
both hosted and native µDewy compilers on direct/C output. A separate 1,400
operation boundary matrix uses independently calculated expected word results.
The two immediate tests pass again after simplifying instruction dispatch.
Artifacts: `immediate-complete-gates.log`, `immediate-dispatch-gates.log`.

For the frozen tokenizer module, assembly shrinks **5,524,929 to 4,678,466
bytes** and its executable **1,144,104 to 955,688 bytes**. Three paired samples
against the generic operand sequence give median generation 0.285 to 0.327
seconds and toolchain 0.404 to 0.348 seconds. The combined times are close;
this establishes smaller output, not a substantial hosted compile-time win.
The first version's higher dispatch cost was reduced before this measurement.
Full-build and native-seed effects remain to be measured. Artifacts:
`immediate-operands-module/results.json`, `immediate-dispatch-module/results.json`.

The updated µDewy sources also reach two-generation fixed points without
Python: C generations take 6.45/6.30 seconds with identical SHA-256
`de2ad6d5129a19283f79b4904c5af28fb7345719cf57fbd89102feeb3aef4387`;
direct x86-64 generations take 0.33/0.44 seconds with identical SHA-256
`2156e48ed9d705b1e8782d743aaba2edce5053bfad4491f1129d7492bac8b3ab`.
This verifies the µDewy pair, not a fresh full Dewy fixed point. Artifact:
`build-immediate-micro.log`, `udewy-immediate-{c,x86_64}-stage{1,2}`.

### Source-emission dispatch

A fresh full profile finds 1.94 million AST emission dispatches and 717,000
call dispatches, including a no-op integer-support check. Source emission
now selects handlers by concrete node class and resolves inherited classes
using the original ordered cases. Call emission classifies name and arity
once. No expression contents or rendered text are cached; scoped names,
evaluation order, diagnostics and debug locations keep their existing rules.

All 26 bridge, intrinsic and debug-location cases pass. Three paired frozen
tokenizer-module samples produce identical source hashes with and without
debug locations. Median emission time changes **0.259 to 0.160 seconds**
without locations and **0.291 to 0.190 seconds** with them. The comparison is in
`source-dispatch-module/results.json`; the full profile preceding this batch
is `host-immediate-stage-profiles`, and the execution gate is
`source-dispatch-gates.log`.

### Completed parser reductions

The hosted reduction loop stops once every alternative has one item, keeping
the existing final AST validation. Already complete alternatives do not enter
another shunting pass while their peers reduce, and an initial single AST
returns directly. This removes a pass that cannot find adjacent operators;
precedence, quantum alternatives and ambiguity diagnostics are unchanged.
The native Pratt parser does not perform this redundant reduction pass.

All 191 grammar, precedence, partial-operator, literal-boundary and bootstrap
parser cases pass. All 125 frozen compiler/library files retain identical
serialized parse-tree hashes; parsing changes **7.145 to 6.455 seconds**.
Artifacts: `parser-terminal-gates.log`, `measure-parser-terminal.log`,
`parser-terminal-{before,after}.json`.

The quiet complete checkpoint at `38759e1b` takes **68.252 seconds hosted**:
checking 32.722, lowering 16.199, emission 2.655 and backend 11.105 (code
generation 4.690, toolchain 6.295); peak process RSS 1,199,328 KiB. Native
takes **45.507 seconds** with the same PGO Dewy seed and the new C-built
µDewy seed: frontend 11.980, validation 5.044, initialization/reachability
0.866, lowering 10.653, emission 3.896 and backend 10.996; peak process RSS
5,819,860 KiB. Native µDewy output remains byte identical. These combine the
immediate, source-dispatch and terminal-reduction batches; the hosted target
remains unmet. Artifacts: `host-immediate-dispatch-full`, `native-immediate-full`.

### Effect transfer equations

Hosted effect analysis now scans each function body and its defaults once
for local effects and statically resolved place-argument transfers. The
worklist propagates parameter summaries along those routes without rescanning
caller syntax. Value boundaries, opaque calls, selected overloads and the
finite route-depth abstraction retain their existing rules. Recursive
self-transfers snapshot their source before extending its route sets.

All 32 effect, native comparison and borrowing checks pass. The 200-function
forwarding test now requires exactly one scan per body. Three paired samples
on the full compiler's checked HIR compare every effect set against the old
solver: all summaries agree for **1,385 functions**. Body visits fall from
2,264 to 1,385 and median analysis time from **1.632 to 0.720 seconds**.
The input HIR is prepared once; those are analysis-only timings, not full
builds. The native solver remains the independent comparison implementation
at this checkpoint. Artifacts: `effect-transfers-gates.log`,
`effect-transfers-full-analysis/results.json`, `measure-effect-transfers-fixed.log`.

The native analyzer now records the same transfer equations during its local
body/default scan. This also removes its separate caller-discovery traversal.
The analysis record owns the graph; mutable place parameters carry updates
through the visitor, and ordinary value semantics snapshot recursive sources.

The native/hosted effect comparison and five existing storage/callback graph
fixtures pass. A new 128-function recursive graph with 32 local reads per
body verifies propagation, retained reads and absence of spurious escapes or
rebindings. Five paired executions through the old/new direct x86-64 programs
return 42; median runtime, including graph construction, changes **21.5 to
17.0 milliseconds**. This is a bounded kernel, not a full-build result.
The existing PGO native seed also compiles the updated analyzer and kernel;
that native-built executable returns 42. Its build overlaps an isolated
regression check, so its phase timings are not a performance sample.
Artifacts: `native-effect-transfers-gates.log`, `native-effect-graph-place-gate.log`,
`native-effect-transfer-kernel/results.json`, `native-effect-transfer-seed-check`.

### Identifier extraction

Hosted lowering now finishes identifier reads in a dedicated storage-view
handler instead of continuing through the full expression dispatch. It asks
for runtime union members only on storage paths that use that information.
Plain integer, boolean and void leaves return directly. The existing object
field, enum, optional, narrowed-family and union payload rules remain intact.

All 51 targeted storage, narrowing, identity and literal checks pass. Three
paired module lowerings, each using an independent copy of the same checked
HIR, retain identical emitted source. Median lowering changes **0.739 to
0.717 seconds**; the old-path third sample takes 1.775 seconds, so this is
a small local improvement with a collection outlier, not a major performance
claim. Artifacts: `identifier-extraction-gates.log`,
`identifier-extraction-module/results.json`.

### Immutable interval evidence

Hosted interval arithmetic reuses unchanged ordinary operands when both bounds
and the address-cap evidence agree. The identity sentinel for vacuous facts
is never returned by arithmetic. Fixed word ranges and address-space bounds
are shared by their numeric width, signedness and target limit; no flow-state
or type-dependent analysis result is cached.

The initial arithmetic batch passes 32 evidence and bounds checks. A fresh
module comparison changes total compilation from **6.178 to 5.952 seconds**,
with checking **5.293 to 4.978 seconds**. Generated source agrees after
normalizing three build-directory include paths, and every included file has
identical bytes. This is one bounded sample, not a full-build measurement.
The subsequent numeric-range helpers pass 21 targeted checks, including native
comparisons and changing target limits; they are not included in those timings.
Artifacts: `interval-reuse-gates.log`, `measure-interval-reuse.log`,
`interval-output-equivalence.json`, `immutable-range-gates.log`.

### Final intrinsic operands

Both µDewy parsers and the hosted direct HIR bridge leave an intrinsic's last
runtime argument in the current-value position. They save each preceding
argument before evaluating the next one. Static arguments still emit no runtime
code. This removes one redundant save/restore pair per intrinsic, including
loads and stores, without changing ordinary call argument handling.

All 83 targeted backend, native comparison, bridge, ABI and evaluation checks
pass. A new fixture checks mutation between arguments, indirect and nested
calls, and allocations under spilled operands. Three paired tokenizer-module
samples change median code generation **0.316 to 0.264 seconds** and toolchain
time **0.369 to 0.317 seconds**. Assembly shrinks **4,678,466 to 4,080,748 bytes**
and the executable **955,688 to 865,576 bytes**. These are bounded backend
samples, not complete compiler builds. Artifacts: `intrinsic-operands-gates.log`,
`intrinsic-operands-module/results.json`.


Two native generations of the updated µDewy compiler agree for each backend:
C takes 6.52/6.30 seconds, SHA-256
`6fc6155115b3c7937bf67a6c81d83302741513fca346fcebf008d25b93f9c947`;
x86-64 takes 0.30/0.43 seconds, SHA-256
`165b26f81e6429b305113466b283cf56e18d7fe73e2e26910c884b7422a4d3fa`.
Artifacts: `build-intrinsic-micro.log`, `udewy-intrinsic-{c,x86_64}-stage{1,2}`.
This is a µDewy fixed-point check, not a new full Dewy fixed point.

The complete checkpoint at `b4830c5d` takes **66.696 seconds hosted**:
checking 32.845, lowering 15.192, emission 2.932 and backend 9.978
(code generation 4.563, toolchain 5.285); peak process RSS 1,158,380 KiB.
The same PGO native Dewy seed with the updated C-built µDewy takes
**43.903 seconds**: frontend 11.813, validation 5.177,
initialization/reachability 1.041, lowering 10.970, emission 3.807 and
backend 8.947; peak process RSS 5,820,500 KiB. Native emitted µDewy remains
byte identical. Hosted remains above the full-build target. These are fresh
processes with empty build directories and the previously recorded frozen
compiler/library inputs; OS page caches remain uncontrolled.
Artifacts: `host-effect-intrinsic-full`, `native-intrinsic-full`.

### Isolated operator reductions

The hosted parser directly reduces a single binary, prefix or postfix
operator when its operands are already parsed and no precedence competition
remains. Binary uses still win over unary readings, quantum juxtaposition
alternatives stay on the operator, and nonassociative errors share the same
validation as the general shunting path. Flat operators and semicolon atoms
retain their existing handling.

All 225 targeted parser checks pass, including direct comparisons with the
general shunting path and matching nonassociative diagnostics. The 125 frozen
compiler/library parse-tree hashes are unchanged. Parsing changes **6.472 to
6.340 seconds** in one bounded pair; this is a small local improvement, not
a full-build result. Artifacts: `parser-isolated-complete-gates.log`,
`parser-isolated-{before,after}.json`, `measure-parser-isolated.log`.

### Direct memory displacements

Both x86-64 µDewy backends fold an immediately preceding add/subtract
immediate into a load/store's signed 32-bit displacement. The function code
buffer and its length establish adjacency; instructions, labels and debug
directives are barriers. Store operands may still spill, and effective
addresses keep 64-bit wrapping. Other backends retain their existing code.

The 49 existing targeted checks pass. The new displacement fixture initially
reused overlapping test buffers; after separating those buffers, both native
and hosted compilers pass it on x86-64 and C. It covers every memory width,
signedness, displacement limits, intervening operations and spilled stores.
Artifacts: `address-displacements-gates.log`,
`address-displacements-boundary-gates.log`.

Three module pairs with folding disabled/enabled retain roughly equal code
generation time (median **0.278/0.279 seconds**), while toolchain time changes
**0.316 to 0.293 seconds**. Assembly shrinks **4,080,748 to 3,926,235 bytes**
and the executable **865,576 to 836,904 bytes**. The disabled measurement
still includes bookkeeping for potential displacements. A separate comparison
against the previous backend on the native effect-analysis workload changes
code generation **0.867 to 0.908 seconds**, toolchain **0.399 to 0.344 seconds**,
and executable size **941,184 to 904,320 bytes**. Nine paired executions all
return 42; runtime remains about 17 milliseconds with no material measured
improvement. This is a code-size and toolchain improvement, not a demonstrated
full-compiler runtime gain. Artifacts: `address-displacements-module/results.json`,
`address-displacement-execution/results.json`.

Two other hosted lowering prototypes were discarded after measurement:
class-based transformation/extraction dispatch added substantial handler code
for little module improvement; sharing generated word leaves was slower in
both the module and full-program lowering comparisons (**13.735 to 15.073
seconds** for the latter single pair). Both retained identical emitted source.
The current implementation keeps fresh generated leaves. Artifacts:
`lowering-dispatch-module/results.json`, `generated-word-leaves-module/results.json`,
`generated-word-leaves-full-analysis/results.json`.

### Integrated native pair checkpoint

The frozen `4c785f86` source builds two byte-identical native generations
through `tools/bootstrap_native.sh --target c`, without Python. Generation
one takes 118 seconds and generation two 132 seconds, including both Dewy
and µDewy builds and C compilation. These are bootstrap generation timings,
not the earlier direct-output single-compiler performance measurement.
The execution gates pass with both x86-64 and C output, including ownership,
array sharing, analysis scaling, Unicode, and native test discovery.

Dewy stage 1/stage 2 SHA-256:
`82b6bb83ba06fa590f6cb030f383b6ba960ca6e0e2516ccd46ea86bc67f933a1`.
µDewy stage 1/stage 2 SHA-256:
`fe37eb31f17df3398fa277d5080cb65af9a7a22a30e81bad6f63a4c280175631`.
Artifacts: `source-current-pair`, `native-current-pair.log`,
`native-current-pair/SHA256SUMS`. Inputs are the previously recorded PGO
Dewy seed and intrinsic-operand C µDewy stage 2; C compilation uses LTO with
8 jobs, PRE/code hoisting disabled, and ccache disabled. The build handoff
now accepts the current `--no-debug-info` argument as well as older seeds'
four-argument invocation; ten focused build-tool gates pass. This refreshes
the C-accelerated fixed point, not the full corpus or a bootstrap without C.

### Scope labels and outward loop exits

Native checking now collects labels throughout their lexical scope, rejects
active shadowing and cross-function exits, and resolves the nearest loop
whose parent scope declares the label. Branch contexts retain that control
information; function contexts reset it. Native lowering uses private
per-function (or module-initializer) exit signals for µDewy's nearest-loop
control flow. Cleanup proceeds one boundary at a time, including temporary
iterator owners. Intermediate loops that break to a signal checkpoint no
longer carry the source sequence's `never` type past that checkpoint.

All 44 focused tests pass. The new gate compares six accepted cases through
both compilers and both x86-64/C backends, checks seven rejection cases, and
checks unchanged native live bytes over repeated three-level iterator exits.
The original control-flow suite also had an assertion tied to a generated
temporary's ordinal; it now checks the result temporary's consistent identity
without depending on how many temporaries the prelude generated. Artifacts:
`native-labels-final-gates.log`. These are isolated checker/lowering gates;
full native CLI and refreshed corpus verification follow separately.


The frozen `49ad4c12` compiler builds successfully through the verified
`4c785f86` C seed (without PGO) with direct x86-64 output in **53.774 seconds**:
frontend 18.199, validation 8.046, initialization/reachability 1.639,
lowering 10.583, emission 4.856, and backend 8.216. Peak process RSS is
5,544,516 KiB; emitted µDewy is 49,029,734 bytes. This meets the native target
on another C-seed route; hosted remains at its earlier 66.696-second checkpoint.
Artifacts: `source-native-labels`, `native-labels-full`.

The resulting direct-built native CLI passes `labeled_loop_exits.dewy` and
`iterator_labeled_exits.dewy`. Both other labeled fixtures reach the distinct
non-conjunctive iterator-formula gap. This direct-built compiler takes about
26 seconds to compile the first small fixture with its prelude; the fully
direct route still needs performance work. For the broader corpus refresh,
the same emitted µDewy was compiled to C with LTO8 and PRE/code hoisting off.
That single-generation C seed has SHA-256
`8d2929388f969ad20cbef62108ed1e0aa46f19163521af21310a0a9b97e59d72`;
it is not a newly certified two-generation pair. Artifacts:
`parity-native-labels`, `build-native-labels-c-seed.sh`, `native-labels-c-seed`.

### Immutable capture facts

The refreshed frozen CLI exposed a regression in `array_call_adapters.dewy`:
resetting caller flow state for a deferred function also forgot an annotated
constant array's initializer length. Native immutable bindings now retain the
initialization-derived read type separately from the written store contract.
Mutable bindings still retain only their contract across the function boundary;
no caller branch state is copied into the callee.

The capture regression gate passes the original mutable capture cases, the
complete adapter fixture, and constant arrays used by ordinary calls and lazy
defaults (including a local constant), through both compilers and x86-64/C.
Artifact: `native-const-capture-gates.log`. The full frozen CLI refresh continues
with its original seed; a later integration check must verify this follow-up.

### Native cache codec foundation

`semantic/cache_bytes.dewy` encodes little-endian words, signed integers,
booleans, UTF-8 strings, byte arrays and canonical bigints. Invalid or partial
input marks the reader failed; container counts are bounded by remaining
bytes, and a snapshot is complete only at end of input without a failure.
The primitive round-trip and malformed-input fixture returns 42 through the
hosted compiler and the `49ad4c12` native C seed on both x86-64 and C output.
Artifacts: `cache-bytes-gates.log`, `cache-bytes-native{,-c}.log`.

This is the codec foundation only: native checked-prelude caching is not yet
implemented. The schema probe finds that the session's syntax/HIR/type edges
are already arena indices, which can be restored without changing identities.
The eventual cache still needs complete typed snapshot encoding, validation,
input/version/target invalidation, atomic installation, and cold/warm checks.
The native pair integration bundle now includes the byte codec, immutable
capture facts and labeled iterator cleanup for the next pair checkpoint.
