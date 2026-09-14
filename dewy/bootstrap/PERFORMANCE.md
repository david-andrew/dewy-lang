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
