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
