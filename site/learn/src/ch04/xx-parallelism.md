# High Performance Parallelism

Dewy aims for safe, high-performance parallelism in the standard library
rather than a pile of locks in user code.

Intended directions, without a chosen API yet:

- A work-stealing scheduler for CPU-bound fork-join work
- Parallel iteration over collections for maps and reductions
- Task graphs with futures for irregular dependencies
- GPU kernels and distributed collections as later tiers
- Safer low-level primitives (mutexes, channels) for simple shared state
  and FFI, not as the default way to speed up a loop

The concrete names, types, and how a parallel iterator is spelled are
not yet determined.
