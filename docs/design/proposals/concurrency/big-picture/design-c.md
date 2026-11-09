# Wanting for nothing: width by proof, overlap by scope

## BLUF

- Dewy already proves the facts other languages guess: effects, shapes, disjoint places, associative operators. Those proofs are the 80% parallelism story. A schedule keyword is the 20%.
- The lazy path is a sequential meaning with a guaranteed representation: SIMD, then cores, on bulk ops the facts clear. GPU stays explicit placement, then the same ops. Waiting overlaps only inside `tasks`.
- `parallel` stays the decided in-place partition spelling, and it does not wait. Proposal v2's one keyword with three inferred strategies is the design to freeze.
- The 80/20 rule everywhere: one meaning, a representation the compiler picks, and a row or metatag that *forbids* a cost. Unknown is an error that names the fact.

## Eight principles

1. **The result is sequential. The schedule is a representation**, chosen the way `bigint` versus a word is, and only when the proof says the values match.
   `let y = (a .* b) .+ c` — same bits as the scalar reading; lanes, then cores, if `a` is on the CPU.

2. **Bulk ops go wide with no keyword. Carried loops stay one thread.** Operators, `f.(xs)`, pure comprehensions, and `sum` of a proven-associative operator. A loop-carried write is sequential because that is what it says.
   `let squares = [loop i in [0..n) i * i]` threads; `loop i in [1..n) { a[i] += a[i - 1] }` does not.

3. **A park inside a bulk op is an error, not a slower strategy.** The diagnostic names the forcing call. The fix-it is `& no blocks` on that callee, or moving the call into `tasks`.
   `[loop url in urls get(url)]` errors: "`get` may block; write `tasks.over(urls @get)`."

4. **In-place partitions keep the decided `parallel`, and the body must not wait.** Disjoint `@` elements, per-worker regions, join before the next line. Sibling waits stay the compile error lane (a) already adopted.
   `parallel @p in world.particles { p.x += p.vx * dt }`

5. **Overlap of waiting is a scope, written once.** Blocking stays uncolored. A `loop` of `get` is sequential on purpose. `tasks` is structured, windowed, joins, and cancels as a scope. No third shape of `parallel`, no `[concurrent …]`.
   `let pages = tasks.over(urls @get) or_throw`

6. **Floats do not change.** A fixed tree is a different answer for `float64`. Integer `sum` may tree when `+` is proven associative. Float `sum` stays left-to-right unless the call names the tree.
   `sum(counts)` may tree; `sum(energies)` does not; `sum(energies 'tree)` does, and the order is part of the result.

7. **Same memory can be implicit. A different memory cannot.** SIMD and cores share the array, so they are legal representations of a bulk op. A GPU is another address space: `xs.to(dev)` is the opt-in, mixing devices is already a compile error, and the same `.*` is the kernel. Fork-join of 8-wide chunks is not a vectorizer, and a work-stealing pool is not a launch.
   `let y = (a.to(dev) .* b.to(dev)).to('cpu')`

8. **`explain` is the ladder, and a row is the expert dial.** Hover names the representation (scalar, SIMD, cores, device) and the fact that blocked the next one (effect, alias, AoS stride, shape, non-associative float). `& no blocks`, `& no allocates`, `$no_hidden_costs`, `$no_deadlocks`, and `$sequential` forbid a representation. They do not request one.
   `explain squares` → "8 cores, chunks of 1024; SIMD width 4; not on the GPU: data is on `'cpu'`."

Layout sits under 7 and 8. SoA, alignment, and cache-line padding are representation facts of the same type. An implicit parallel write into an AoS field that will false-share or gather itself to death stays scalar, and `explain` says `to(layout: 'soa')`. Halo exchange is a value phase between sequential steps, not a lock in the body: `phase(tiles @stencil)`.

## What the current proposals get wrong

- **Most code should stay one thread.** Scripts, the compiler, and any loop with a carried dependence, a print, or a lock want a stable debug order and a cheap compile. Implicit *everything* makes the schedule the meaning, and races the default. Implicit *bulk ops whose proofs already exist* is the Dewy-shaped cut.
- **A `parallel` keyword is the wrong 80%.** `[loop x in xs f(x)]` and `f.(xs)` already say "this is a map." Requiring `parallel` there is OpenMP's mistake, and lazy programmers will not type it. The keyword earns its keep on in-place partition updates, which a comprehension cannot say. It does not earn a second life as I/O fan-out or as heterogeneous `parallel { let a = … { … } }`. That block is a third construct wearing the token David already spent on data parallelism. He is right to resist another loop- or capture-shaped form; v2 adds one and calls it the same word.
- **Waiting I/O should not be implicitly concurrent.** Implicit *blocking* is the decided, correct rule: no `async`, no colour, `Block` inferred. Implicit *overlap* is a hidden failure domain, a hidden window, and unbounded admission. Go kept `go` for that reason. v2 C1 makes overlap the default whenever a body may park, including on a sibling, and then needs three runtimes to keep it from deadlocking. The adopted lane (a) rule was the right one: a body that may wait on a sibling is illegal in `parallel`, full stop.
- **Strategy inference is a hidden mode.** Pool, window, and task-per-item preserve result order and change memory, cancellation, GPU eligibility, and stack cost. A log helper that takes a lock flips a particle loop from chunked and GPU-eligible to one stack per particle. The note lives in hover. `Opaque` calls are already top in the effect design; they will take the worst strategy on any realistic game or scientific call.
- **One hierarchy for lanes, cores, and devices oversells the performance note.** SIMD is instruction selection on straight-line bulk code. Cores are a join tree over partitions. A GPU is a launch and a copy. Treating them as recursive fork-join produces chunked scalar code that never hits a vector unit, and a pool that tries to offload whatever happened to be `& no blocks`.
- **v2 spends the surface on the 20%.** `select`, `op.then`, and a may-park analysis are expert concurrency. None of them makes `f.(xs)` use the machine. The stage-1 kernels (fib, matmul, stencil) are the right measurements, and the pure ones should pass with no `parallel`.

## The risk

The 80/20 promise dies if the easy path's cost is a whole-program guess. A callee edit that adds a park, an opaque call, or an unknown effect silently changes the representation of every bulk caller. The program stays correct and gets slower, the reason is three calls deep, and the lazy programmer has no token to hold onto. Experts learn to distrust `parallel` and pin `& no blocks` everywhere, which is a second dialect. The same analysis fights the compile north star: effect solving is demand-driven and budgeted, and a may-sibling-wait query on every comprehension is a new whole-tree pass the effects note already forbids.

Defuse it by refusing the fallback. A bulk op or a `parallel` body has one legal representation family: SIMD and a chunked pool, or scalar, chosen by local facts (shape, the callee's settled row, disjoint `@` elements). A `Block`, a `Spawn`, or an `Opaque` row is a compile error naming the call, with the `tasks.over` fix-it. Cost does not change unless the callee's row changes, and a row change is already a source edit the checker reports. `$sequential` forces scalar for debugging. GPU never joins this ladder; placement does.

Ship that refusal, and `explain`, before any further concurrency spelling. The acceptance check is a pure comprehension and an `f.(xs)` that go wide with no keyword, a float `sum` whose bits match the left fold, a stencil `explain` that says why it stayed scalar, and a `get` inside a comprehension that will not compile. `tasks.over` is the one library function for overlapped waits. Freeze v2's three strategies.

## 80/20 past concurrency

- The pattern already exists: prove it, return a value, assert it, or cross `unsafe`. Rows and metatags forbid a cost (`$no_hidden_costs`, `& no blocks`). They never request the fast path. A keyword per hardware feature is how the 20% colonizes the grammar.
- Unknown stays unknown. Effects widen to top and fail closed. Inserting a lock, a copy, or a task per item when a proof is missing is the quieter codegen the safety note already rejects for partitions.
- Ordinary code keeps COW, checks, and one thread for small trip counts, with `T1/Tseq` held to the adopted 1.1 so the implicit form is free when it does not pay. Strict code is the same source plus prohibitions. Kernels push a device, a layout, or a scheduler context the way they push an allocator.
- `Atomic`, `spsc`/`mpmc`, `Mutex`/`lock_all`, and `$no_deadlocks` stay danger opt-in for sharing that is real. Inside a bulk op that is the smell `explain` points at.
