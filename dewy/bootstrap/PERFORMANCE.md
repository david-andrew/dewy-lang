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
