# Safety, concurrency, and obligations beyond Rust

BLUF: Dewy’s safety story is a single obligation rule — prove it, return a value, assert, or cross an explicit `unsafe` boundary — of which memory safety is a special case. Rust’s `Send` / `Sync` / `Mutex` / `Arc` invariants should be adopted as Dewy type properties and handle types, not as a borrow-centric `std::sync` clone. The default concurrent API should be structured fork-join and parallel iteration over proven-disjoint data; locks are the substrate for genuine sharing and FFI. Safety is half the design: the other half is a *performance model* — owned partitions, per-worker regions, communication that is rare, hierarchical, and batched, deterministic results — which Rust does not have and Dewy’s value semantics make natural (see [Locality and communication](#locality-and-communication-the-performance-model)). This note is provisional design direction. It does not settle surface syntax.

Related notes: [`no_traps.md`](no_traps.md), [`user_managed_storage.md`](user_managed_storage.md), [`value_semantics.md`](value_semantics.md), the reference “No Traps” / `unsafe` sections, [`resources/security_ideas.md`](../../resources/security_ideas.md), and the learn-book parallelism sketch.

## Two contracts

Rust’s safe fragment is memory safety and data-race freedom. The enforcement mechanism is the borrow checker plus auto traits. Safe Rust may still panic: `xs[i]` is safe and can abort; `get_unchecked` is `unsafe` because the type system does not track the fact. `unsafe` means memory-model superpowers (raw pointers, uninit, union punning, `unsafe` trait impls). Logical correctness, units, authority, and hidden aborts are taste.

Dewy’s safe fragment is trap-freedom plus proven preconditions. A compiled program does not abort on a path the programmer did not write. Indexing, nonzero division, narrowing, and refined contracts are bare instructions when the liquid solver can see the fact; otherwise a compile error, a value (`T | Overflow`), a `$runtime_assert`, or an explicit `unsafe` claim. Dewy’s `unsafe` is “a proof or memory-safety obligation the compiler has not established.” That is a broader and cleaner line than Rust’s, and socially riskier if it becomes the way to silence the solver.

Rust is the sharper industrial model for “do not alias mutably, do not data-race.” Dewy is a candidate for a larger model: the program is not allowed to be accidentally wrong, including traps, partial operations, units, and — if effects become capabilities — authority. It would be a better *overall* model only if it keeps Rust’s crispness on memory and concurrency while adding those axes, and only if everyday programs do not live in the solver’s `unknown` bucket.

## What stays a trust boundary

These are not “Rust is conservative.” They are operations whose meaning is “believe me about the machine,” and they stay `unsafe` in Dewy:

- raw allocation, alignment, initializing uninit storage, address arithmetic, constructing a handle from an address
- aliasing the language cannot see: self-referential layouts, parent pointers, intrusive lists
- representation lies: `transmute`, unchecked union punning, “these bytes are a `T`”
- FFI, syscalls, MMIO, inline asm (effects can make the Dewy side honest; they cannot verify libc)
- concurrency-primitive cores: `Arc` retain/release, mutex internals, atomics, “this payload may cross a thread”
- facts outside the liquid fragment that the program refuses to check at runtime

`Vec`, `Rc`, `Arc`, and `Mutex` therefore keep the Rust shape: a small trusted core, a large safe surface. See [`user_managed_storage.md`](user_managed_storage.md).

## What Dewy can take out of `unsafe`

Application-level Rust `unsafe` is often “skip this check” or “the borrow checker cannot see that this is fine.” Idealized Dewy is built to make those ordinary:

- proven indexing, slicing, nonzero division, narrowing, `unreachable` cases the solver already knows are dead
- nonescaping `@` helpers that mutate a caller’s local without lifetime annotations
- two mutable places in one call that analysis proves disjoint (sibling fields, constant indices, and — when the analysis can — dynamic partitions)
- typestate and contractual preconditions expressed as refinements (`int64 & ~0`, `array<length >? 0>`, `:>uint64<n => n <=? src.length>`)

`split_at_mut` is the middle case. Rust’s *use* is safe and its *implementation* is `unsafe`. Dewy should make more *uses* safe by treating “one place becomes two disjoint places” as a language rule or a single trusted primitive, then proving `0..i` and `i..n` disjoint as ordinary place facts.

Dewy is sometimes *stricter*: Rust allows safe-and-panicking `xs[i]`. Dewy will not. An unproven index is a guard, a `$runtime_assert`, a `get`, or `unsafe` — not a hidden check.

## Concurrency: adopt the invariants, not the surface

`Send`, `Sync`, `Mutex`, and `Arc` are portable because they answer questions Dewy must answer as soon as anything is concurrent:

- may this **value** cross a task boundary?
- may two tasks **hold** this value at once?

They are not really about borrows. They should be adopted as Dewy type properties and handle types.

### `Send` and `Sync` as type properties

Define them on values, not on a Dewy equivalent of `&T`:

- **`Send`:** this value may be transferred into another concurrent task.
- **`Sync`:** two tasks may hold this value at once.

Ordinary Dewy assignment copies meaning. Two tasks each holding an `int64` or an array are not sharing storage; `Send` is the interesting question (hidden thread-local or non-atomic guts). `Sync` matters for values with **shared identity**: `Rc`, `Arc`, `Mutex`, atomics, raw storage.

Composition is structural and automatic, the way Rust’s auto traits scale: a product is `Send` when its parts are. People should not write these bounds by hand on every object.

The usual table still works:

- `Rc<T>` is neither (non-atomic count).
- `Arc<T>` is both when `T` is.
- `Mutex<T>` is `Sync` when `T` is `Send` (the mutex is the shared thing; the payload is touched only under the lock).
- a place `@x` is not a `Send` value. Sharing a place across tasks is a separate, stricter rule and should stay hard.

Keep `Send` / `Sync` as type facts, not as effects. That matches Dewy’s split between “what value you get” and “what evaluation does.” `spawn` and “this call blocks on a lock” are effects. They *consult* `Send` / `Sync` on the values involved.

Do not grow a second, unrelated trait system just to spell these. They should look like other Dewy obligations: derived, proven, or `unsafe` to assert.

### `Arc` and `Mutex`

`Arc<T>` is a handle value: copy retains, release drops, `@arc` selects the handle, not the payload. That is the existing `Rc` story plus atomics plus a `Send`/`Sync` obligation on `T`. It must not turn `@` into a general pointer.

`Mutex<T>` is checked interior mutation. `lock` yields a lifetime-bounded mutable place into `T`, valid no longer than the guard. That is the scoped-place machinery [`user_managed_storage.md`](user_managed_storage.md) already wants for unique `Rc` access. The trusted root (“this memory may be mutated while others can see the mutex”) stays `unsafe`.

Do not adopt mutex poisoning. Rust poisons because panics unwind through a lock. Dewy is trap-free; a lock that aborts on the next acquire is against [`no_traps.md`](no_traps.md). A contested or abandoned lock is a returned value, or Dewy does not poison.

`@` is not `&`. Passing `@x` to another task must not become the default sharing mechanism. `Mutex` and `Arc` are *more* important in Dewy than in Rust precisely because places do not escape and do not share by default.

### Culture

The learn-book parallelism page is the user-facing rule: work-stealing, parallel iteration, and task graphs first; mutexes and channels for genuine shared state and FFI, not as the way to speed up a loop. Having Rust-shaped primitives does not mean adopting Rust’s “put a `Mutex` on it” as everyday style.

## Locality and communication: the performance model

Rust’s model answers *how do we share safely*. The performance of a parallel program written by an expert comes from *not sharing*: each processor does a lot of local, independent work on nearby memory, and communicates rarely, hierarchically, and in large batches. Rust is silent on this — rayon and crossbeam are libraries working around the borrow checker, and layout, placement, and communication structure are the programmer’s private craft. Dewy should make that shape the default, because its existing semantics already point at it:

- **Values copy by meaning and places do not escape**, so a worker holding a value holds *its own* value. There is no shared storage to protect unless a handle with identity (`Arc`, `Mutex`) is introduced deliberately.
- **Moves by liveness** are the transfer mechanism. Handing a partition to a child task and receiving the result back is a move in and a move out when the parent does not use the value in between — no copy, no atomics, no `Arc`. This is Dewy’s ownership transfer, and it needs no annotation.
- **Disjointness is a liquid fact.** `xs[0..i)` and `xs[i..]` are disjoint because they share the boundary `i`; `N` tiles of stride `s` are disjoint by linear arithmetic over `s`. The order and remainder facts the analysis holds today (`i <=? xs.length`, `n <=? j - i`) are the vocabulary; two-dimensional tiling (blocked matrices, stencils) needs a strided view and the same arithmetic.

### Partitions first

The primary abstraction is the **partition**, not the task: one value becomes `N` owned, disjoint pieces; workers compute on their pieces; the parent receives `N` results and merges. Tasks are the control structure that runs the pieces. Consequences:

- The fast path — owned pieces, no synchronization inside a piece — is what the plain spelling produces. `Arc`, `Mutex`, and atomics appear only when the program genuinely shares, and their presence in a hot loop is a smell the compiler can point at.
- Reductions merge *values*, in a fixed tree, at the parent. Communication is one message per child per join: rare and batched by construction. A reduction may reassociate only when the operator is proven associative (and commutative when the tree is not fixed); otherwise the tree order is stated and the result is deterministic.
- **Hierarchy is the same operation repeated.** Partitioning a value across sockets, then cores, then SIMD lanes is recursive fork-join with a merge at each level, so communication follows the machine’s tree: lanes merge into a core, cores into a socket, sockets into the node. GPU and distributed tiers are further levels of the same shape, not a second model.

### Layout and placement

Where data lives decides the speed, so the language and library need to give experts control without making everyone say it:

- **Per-worker regions by default.** A fork gives each child a region to allocate in; the parent releases them after the join. No per-object ownership traffic, no shared allocator contention. This is the scoped-arena model extended to tasks, and it is what “send a region, not a thousand handles” below means.
- **Layout is a representation choice, not a type change.** Struct-of-arrays versus array-of-structs, alignment, and padding are representation facts about a value of the *same* type, chosen at the partition or by an annotation, the way `bigint` versus a word is a representation of the same integer. Kernels should not have to be rewritten to change layout.
- **False sharing is the silent killer** of naïve parallel code: per-worker accumulators on one cache line serialize the machine. Per-worker regions already separate most state; where results are collected into one array, the collection is padded or gathered at the join, not written to in place by every worker.
- **Placement and scheduling are context, like the allocator.** Thread count, affinity, chunk size, and the scheduler itself are an implicit context a caller may push (as with the context allocator), so a library kernel never hardcodes them and an expert can pin a partition to a socket without touching the kernel.

### Iterative kernels: phases, not locks

Stencils, PDE solvers, iterative graph algorithms, and simulations alternate a local step with a boundary exchange. The right structure is **bulk-synchronous phases**: every partition computes on its own data, then the *boundaries* (halos) are exchanged — as values, in one batch per neighbor per phase — and the next phase starts. No lock, no fine-grained sharing, deterministic by construction. The exchange is between siblings through the parent or along declared neighbor edges; either way it is a typed value transfer the compiler can see, and the data-race question never arises because nobody writes what another reads within a phase.

### Determinism

A parallel program should produce the same answer as its sequential reading unless the programmer explicitly asks for a nondeterministic reduction (and proves the operator allows it). Scheduling — which worker ran which piece, when — must not leak into results. Fixed reduction trees and phase structure deliver that; racy accumulation is never an optimization the compiler performs.

### Concurrency of waiting is a different problem

Waiting on I/O, events, and timers — many tasks, mostly blocked — is not parallelism and should not share its design. It wants a cooperative scheduler, futures or channels, and a story for cancellation (an effect or a returned value, never an abort); it does not want partitions and regions. The two meet at effects (“this evaluation blocks”, “this evaluation spawns”) and at `Send`/`Sync` on the values that cross, and nowhere else. The staging below keeps them apart.

### What makes this fail

Three cliffs would turn the fast path into folklore, and each needs a compiler answer, not a style guide:

1. **The solver’s `unknown` bucket for partitions.** A partition the analysis cannot prove disjoint must not silently fall back to a lock or a copy. It is a compile error with the missing fact named, exactly like an unproven index — and the fragment has to be complete enough (linear arithmetic over strides and boundaries) that the common tilings prove.
2. **Silent copies.** A value that was copied into a child because a move was not proven is a performance cliff that looks like correct code. The compiler should be able to say *why* a value was copied (a later use, an escape), and an expert should be able to ask for the move and get an error instead of a copy.
3. **Hidden sharing.** An `Arc` retain or an atomic in a loop body that the programmer thought was owned. Handles with identity should be visible at the partition boundary — a partition of `Arc<T>` values is a different (and slower) thing than a partition of `T`, and the type says so.

## Beyond Rust

The rest of this note is Dewy-native target, not a port. Some items are already implied by existing notes; they are collected here so concurrency and safety work do not quietly become “Rust, but with refinements.”

### Ergonomics

**Scoped tasks as the default, detached spawn as the exception.** A parent owns its children and joins them before it returns. That makes a large class of “share this stack-allocated array with workers” safe without `Arc`: the place is valid for the join, the children cannot outlive it, and `Send` is required only for data that actually leaves the scope. Rust’s `thread::scope` is the special case; Dewy should invert that.

**Parallel `loop` and loop-capture, not a second iterator vocabulary.** The sequential language already treats `loop` as an expression that a surrounding `[]` can collect. The parallel form should be the same grammar with a disjointness and purity obligation, not a `rayon` combinator dialect. If the body is proven free of overlapping mutation (or writes only proven-disjoint partitions), no lock appears in user code.

**Language-level place splitting.** `xs[0..i)` and `xs[i..]` as two live mutable places, proven disjoint, should be an ordinary operation. Parallel for-each over slices is then safe code. The trusted box, if any, is one primitive that turns one place into N disjoint places; uses do not write `unsafe`.

**Nonescaping `@` stays invisible.** Lifetime-bearing places exist for payload access and lock guards. Everyday mutation through a helper should keep looking like `update(@values)` with no annotations. If concurrency forces lifetime syntax onto ordinary calls, the model has slipped back toward Rust’s surface.

**Fact-carrying library operations.** `startswith` already proves `prefix.length <=? text.length`. The same style should apply to concurrency and I/O: a successful `lock` proves the guard is the unique mutable place; a successful `CAS` proves the observed value; a channel receive that yields `T` (not `T | closed`) proves the sender is still live, or the type says otherwise. Callers should not re-prove what the primitive just established.

### Performance

**Uniqueness is a parallelism permission.** If analysis proves a value is uniquely owned, disjoint partitions may be written in parallel with no atomics, no `Arc`, and no lock. That is the sequential move/borrow story applied to tasks. `Arc` is for when uniqueness is *not* proven; the compiler should not emit retain traffic on the unique path.

**Proven preconditions are the check-elision story.** A proven index or nonzero divisor *is* the unchecked operation. The performance feature is the liquid fragment being complete enough that hot loops do not fall back to `$runtime_assert`.

**Send a region, not a thousand handles.** Fork-join over a compiler or a frame region — workers allocate in a region the parent created, parent releases the region after join — avoids per-object ownership traffic. This extends the scoped-arena model rather than inventing a concurrent GC, and it is the default of the [performance model](#locality-and-communication-the-performance-model) above, not an optimization.

**Parallel reductions need an algebraic obligation.** A parallel `sum` or `join` is only allowed to reorder when the operator is proven associative (and, if needed, commutative), or the implementation falls back to a deterministic tree with a stated order. Silent racy accumulation is not an optimization.

### Logical safety and correctness

**Trap-freedom is a security property.** Libraries do not abort. A caller that forgets a failure path cannot be surprised by a panic in a dependency. That is already [`no_traps.md`](no_traps.md); concurrency must not reintroduce thread-panic-as-control-flow, including poisoned locks and cancelled-task aborts. Cancellation is an effect or a returned value.

**Lock payloads carry refinements.** `Mutex<T>` should re-establish `T`’s invariants at unlock the way constructing a `Ratio` proves `bottom >? 0`. A guard that mutates `T` out of its refined type cannot be released until the facts hold again, or unlock returns a value. This is typestate on shared state, which Rust’s `Mutex<T>` does not do.

**Data-race freedom is not business atomicity.** `Send`/`Sync` prevent undefined races. They do not prevent two tasks from doing a lost update on a logical invariant. Where it matters, the type should say which facts a lock restores, or a channel should say which messages are exclusive. Do not pretend `Sync` solved that.

**Effects as authority.** The interesting security work beyond Rust is not a better mutex. It is compile-time capabilities: a function that talks to the network or the filesystem names that effect, and a higher-level API can require a proof of permission. See [`resources/security_ideas.md`](../../resources/security_ideas.md). Concurrent tasks inherit or are granted a subset of the parent’s effects; they do not silently gain the process’s full authority.

**Trusted versus untrusted inputs.** Brand or mint values that came from the outside (`env`, sockets, files) so privileged sinks cannot take them without an explicit boundary. This is the same refinement/brand machinery, aimed at injection and confused-deputy bugs Rust types do not see.

**Units and exact arithmetic stay in concurrent code.** A parallel numeric kernel should not be the place floats or stripped units sneak back in. If a GPU or SIMD tier appears later, it is a representation of the same quantities, not a second numeric language.

**Channels, when they exist, are typed protocols, not `any` queues.** At minimum: a payload type, a closed alternative in the receive type, and no implicit buffering of exception-family values that the sender did not name. Session-style “this is a request-response pair” can wait; silent `T` receives that may be hang-or-close should not.

**Deadlock is an open, later obligation.** Lock-ordering proofs or linear lock tokens would be a real step past Rust. They are not required to ship `Mutex`. Do not block the substrate on them; do not forget they are the next logical hole after data races.

## What not to copy

- `unsafe` as the everyday way to skip a bounds check
- mutex poisoning and panic-across-threads as an API
- `&T` / lifetime annotations as the default sharing story
- `Mutex`/`Arc` as the recommended way to write a parallel loop
- a trait system that exists only to name `Send` and `Sync`
- treating “the solver said unknown” as false, or as a license to insert a hidden check

## Staging

Follow [`user_managed_storage.md`](user_managed_storage.md) through `Rc` / `Weak` first. Concurrency is a later slice:

1. Define `Send` / `Sync` as structural type properties and the `unsafe` assertion that opts a type in or out.
2. Atomics with an explicit memory-order and an effect, sufficient for `Arc`.
3. `Arc<T>` as a library handle.
4. `Mutex<T>` as a library handle whose `lock` produces a scoped place; no poison.
5. Scoped fork-join in the library over **partitions**: a value split into `N` owned disjoint pieces (moved in, moved out by liveness), each child allocating in its own region, results merged at the join in a fixed tree; places into parent-owned data are allowed for the join when disjointness and `Send` (for detached captures only) hold. Disjointness is the order/remainder fact machinery, extended to strides and (later) two-dimensional tiles.
6. Parallel `loop` over proven-disjoint partitions, with reductions gated on algebraic obligations; the scheduler context (thread count, affinity, chunk size) pushed like the allocator.
7. Layout control as representation (SoA/AoS, alignment, padding) and bulk-synchronous phases with halo exchange for iterative kernels; the “why was this copied / shared” diagnostics.
8. Detached spawn, channels, futures, cancellation, and capability-restricted tasks — the concurrency-of-waiting design — after the scoped path is the default.

Step 5 is the ergonomic and performance win, and it is where the partition-first model is proven or not: if a blocked matrix multiply or a stencil cannot be written as owned partitions with no lock and no `unsafe`, the design has missed. Steps 3–4 are the substrate. Step 8 is what most people think of as “threads,” and it should stay the opt-in.

## Open design questions

- Surface spelling for `Send` / `Sync` as type properties, and how they appear in diagnostics.
- Whether a scoped child may hold a read-only place into parent data, a mutable disjoint place, or only owned / `Arc` values in the first slice.
- Memory-order vocabulary and how much of it safe library code may name.
- How cancellation is represented so it is neither a trap nor an implicit unwind through a lock.
- Whether unlock of a refined `Mutex<T>` is an obligation on the guard’s last use or an explicit call.
- How task-local effects interact with a pushed context allocator and with inherited capabilities.
- Whether lock ordering is in-language (later) or only a documented discipline at ship.
- How a partition is spelled: a library type (`Partitioned<T>` over a proven-disjoint split), a `loop` form, or both — and how a two-dimensional tile (stride, block) is expressed so its disjointness is a linear fact the analysis can hold.
- How the halo exchange of a phase is spelled (through the parent, or along declared neighbor edges) so it stays a typed, batched value transfer.
- How layout (SoA/AoS, alignment, cache-line padding) is chosen as a representation of the same type, and where — at the partition, at the declaration, or by context.
- What the scheduler context contains (pool, affinity, chunk size) and how a library kernel stays agnostic to it.
- The shape of the “why was this copied / where is this shared” diagnostic, so the fast path is verifiable rather than assumed.
