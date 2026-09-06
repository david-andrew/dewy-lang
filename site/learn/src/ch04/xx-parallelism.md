# High Performance Parallelism

Dewy aims for safe, high-performance parallelism in the standard library rather than a pile of locks in user code.

The shape it aims for is the one experts already write by hand: split the data into pieces each worker *owns*, do a lot of local work on each piece, and communicate rarely, hierarchically, and in large batches — results merged at the join, boundaries exchanged once per phase. Dewy's values copy by meaning and move when their last use is behind them, so handing a piece to a worker and getting the result back is a move, not a copy and not a shared handle; and whether two pieces overlap is a fact the compiler proves the way it proves an index is in bounds. Locks, atomics, and shared handles are for genuine sharing and FFI, and their appearance in a hot loop is something the compiler can point at.

Intended directions, without a chosen API yet:

- Partitions as the primary abstraction: one value split into owned, disjoint pieces, moved in and out of scoped fork-join tasks, each task allocating in its own region
- A work-stealing scheduler for CPU-bound fork-join work, with thread count, affinity, and chunking as a pushed context (like the allocator) rather than something kernels hardcode
- Parallel `loop` over proven-disjoint pieces for maps and reductions — reductions in a fixed tree, reordered only when the operator is proven to allow it, so results are deterministic
- Bulk-synchronous phases with boundary exchange for iterative kernels (stencils, simulations), instead of fine-grained sharing
- Layout (struct-of-arrays, alignment, padding against false sharing) as a representation choice of the same type
- Task graphs with futures for irregular dependencies; channels and cancellation for the concurrency of *waiting* (I/O, events), which is a separate design from parallelism
- GPU kernels and distributed collections as further levels of the same partition-and-merge hierarchy
- Safer low-level primitives (mutexes, channels) for simple shared state and FFI, not as the default way to speed up a loop

The concrete names, types, and how a partition or a parallel iterator is spelled are not yet determined.

A provisional design direction for the low-level contract (`Send` / `Sync`, `Arc`, `Mutex` as scoped places) and for making structured fork-join and parallel `loop` the default is recorded in the compiler note [`dewy/semantic/safety_and_concurrency.md`](../../../dewy/semantic/safety_and_concurrency.md).
