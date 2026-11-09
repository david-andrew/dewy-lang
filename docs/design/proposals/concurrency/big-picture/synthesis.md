# Dewy's 80/20 performance model: synthesis (2026-11-01)

This synthesis combines three independent designs, all in this folder: Design A (`design-a.md`), Design B (`design-b.md`) and Design C (`design-c.md`), and comes after proposal-v2 and its reviews.

## BLUF

- **Code says *what*; the compiler picks *how*.** One meaning per construct, with the compiler choosing the representation (scalar, SIMD, cores, later GPU), the way it already chooses `int` storage.
- **Refinements are orthogonal settings, not new constructs.** You add layout, placement, grain, window or "never wait" on top of the same code. The algorithm is never rewritten, and the grammar doesn't grow a new loop or capture shape per hardware feature.
- **Two levels of buy-in:**
  - **No keyword.** Pure bulk work (comprehensions, maps, broadcasts, reductions) automatically uses SIMD and all cores. The result is bit-identical to running it in order. This is new: v2 still required `parallel` for that.
  - **One word, `parallel`.** "Run these at the same time": items may overlap I/O, wait on each other, update disjoint places, and their side effects may interleave. This is the reading you gave: a deadlock there is the algorithm's problem, not the language's.
- **Unknown fails honest.** When the compiler can't prove something, it picks the safe choice (sequential, or a task per item) and `explain` says why. It never guesses optimistically.
- **Explain is part of the language promise.** Hover and `explain` show what ran where and what blocked the next rung ("not parallelized: iteration 3 reads iteration 2's write"). All three reviewers rank this as essential as the syntax.
- **Expert code replaces one leaf behind the same value interface:** SIMD types, atomics, lock-free queues, custom GPU kernels. This is the Rust "unsafe inside a safe API", Julia dispatch and Halide algorithm/schedule lesson.
- **Two splits remain:**
  - Should `parallel` items be allowed to wait on *each other*? Design A says yes. Design C says no, like Chapel's `forall`. Design B says you can't also bound memory then.
  - Should GPU use ever be automatic?

## Where other languages landed (Design B's survey, condensed)

| Lesson | Who learned it | What Dewy takes |
|---|---|---|
| Function coloring splits every API in two | Rust, Swift, Kotlin, JS (`async`) | No colors; blocking is an inferred effect (already decided) |
| Unstructured spawns leak work and memory | Go | Structured lifetimes only; long-lived work goes through an explicit `tasks` scope |
| Hidden shared pools and nested runtimes oversubscribe | Java parallel streams, OpenMP + BLAS | One runtime and one CPU budget across nesting and libraries |
| "Parallel made it slower": overhead beats small work | PLINQ, OpenMP | Automatic cutoffs, plus an expert `$grain`; `explain` shows the cutoff |
| Float reductions change answers with thread count | everyone | Sequential order by default; a tree only when requested |
| `forall` items needn't run simultaneously, so syncing between them deadlocks; `coforall` guarantees tasks but can spawn far too many | Chapel | The central open split (B2 below) |
| GPU transfers and launches dominate small jobs | CUDA, SYCL, Triton | Explicit placement first; automatic only with a real cost model |
| Separating algorithm from schedule lets experts tune without rewriting | Halide, Futhark | Settings refine the same code |
| Easy bulk syntax is what lazy programmers actually use | NumPy, Julia broadcasting | Bulk ops go wide automatically; no keyword needed |
| Complexity accretes when escape hatches interact | C++, Scala | Delete redundant constructs before release; one scope/error model |

## The ladder

**Rung 0: nothing written.** SIMD and multicore are applied automatically to proven-pure bulk work. The result is identical to sequential.

```dewy
twice = (x:float64) => x + x
let xs = [i in [0..1000000) 1.0]
let ys = [x in xs twice(x)]     # SIMD + all cores; same bits as a plain loop
let total = sum(ys)             # float sum: left-to-right order, so same bits
```

- **Falls back to sequential** whenever it can't prove safety: a callback with effects, a loop-carried dependency, I/O.
- **Floats** are never reassociated silently: `sum(ys 'tree')` asks for a tree. Integer sums may use a tree once the compiler proves that's equivalent.

**Rung 1: `parallel`.** Permission to overlap and to reorder side effects.

```dewy
fetch = (url:string):>string | NetError => http.get(url)
let urls = ["a.com" "b.com" "c.com"]
let pages = [parallel u in urls fetch(u)]          # all requests in flight at once; results in input order
Particle:type = [x:float64 vx:float64]
let ps = [Particle[1.0 0.5] Particle[2.0 0.25]]
parallel @p in ps { p.x += p.vx }                  # disjoint in-place update
```

- **Results** come back in input order. Errors are per-item values. `or_throw` inside an item cancels the siblings and leaves the function.
- **Strategy:** the compiler picks a CPU pool, a bounded window, or a task per item, and `explain` shows which.

**Rung 2: orthogonal refinements.** Each is a setting on the next construct or scope (all spellings are proposals):

```dewy
$layout = 'soa'                # store the array as struct-of-arrays
let ps = [Particle[1.0 0.5] Particle[2.0 0.25]]
$grain = 256                   # min items per chunk
$window = 8                    # at most 8 waiting items in flight
let pages = [parallel u in urls fetch(u)]
tick = (@ps:array<Particle>) & no blocks => { parallel @p in ps { p.x += p.vx } }  # pins "never waits"
$sequential                    # debugging: run the next construct in order
```

Placement and scheduling work the same way: `$device = 'gpu'`, `$cores = [0 1]`, `$scheduler = my_scheduler`.

**Rung 3: expert leaves behind the same interface.**

```dewy
twice4 = (v:Simd<float64 4>) => v + v
let ys = map_chunks(xs @twice4 @twice)              # explicit SIMD; scalar tail
let count = Atomic<int>(0)
parallel i in [0..4) { count.fetch_add(1 'relaxed') }
```

Expert leaves also include the lock-free queues (`spsc`, `mpmc`), `select`, and custom GPU kernels bound to an existing map (`$kernel = @twice_gpu`).

**Long-lived work.** `tasks(body)` is a library scope for work that outlives one call: background autosave, servers. It's the only place a task can outlive the expression that started it.

## Decisions for David (big-picture; they settle most of C1–C11)

- **B1. Do pure bulk operations go wide automatically, with no keyword?**
  - Rec: yes.
  - All three reviewers agree. It's the biggest lever for lazy programmers.
- **B2. May `parallel` items wait on *each other*?**

  ```dewy
  let ch = channel<int>(1)
  step = (i:int) => if i =? 0 (ch.receive or_throw) else { ch.send(42) or_throw; 0 }
  let r = [parallel i in [0..2) step(i)]
  ```

  - **(a) Yes.** This matches your reading ("they run at the same time"). The cost: the compiler can't bound memory when it can't tell which items wait on which, so it uses a task per item and `explain` warns on large or unknown counts. That's Design A's position.
  - **(b) No.** A wait on a sibling is a compile error that names the call; use explicit channels between `tasks` instead. This is Chapel `forall` and Design C's position: memory stays bounded and strategies stay simple, but your example becomes an error.
  - Rec: (a), since it's the reading you gave and the warning covers the cost. Design B notes that (a) means `$window` must be rejected when it conflicts with a sibling wait.
- **B3. Is concurrent I/O fan-out spelled with the same `parallel`?** (Design C wants a separate `tasks.over(urls @fetch)`.)
  - Rec: same word. One concept, "these at the same time"; the strategy is a representation.
- **B4. GPU:** explicit placement (`$device = 'gpu'` or `xs.to(dev)`) first; automatic offload only later, behind a cost and residency model.
  - Rec: yes.
- **B5. Float reductions:** sequential order by default; a tree only when requested (`sum(xs 'tree')`). Integers may use a tree when proven equivalent.
  - Rec: yes.
- **B6. Refinements are metatags or context, not new constructs.** Approve the direction, with `$grain`, `$window`, `$layout`, `$device`, `$cores`, `$scheduler` and `$sequential` as proposals.
  - Rec: yes.
- **B7. `explain` and actionable "why not" diagnostics** are a language deliverable, shipped before more concurrency surface.
  - Rec: yes.
- **B8. Keep the block form `parallel { let a = f()  { … } }`** for running different things at once, e.g. producer plus consumer. It replaces `concurrent {}` + `spawn`. Design C calls it a third construct.
  - Alternative: `tasks` only.
  - Rec: keep. It's the same word and replaces two keywords.

**Effect on C1–C11:** B2 decides C1. C4 (cancellation that depends on the result type) gets rethought, since Design B finds it unstable. C7's default window on receivers applies only when items are independent. The rest stand.

## 80/20 beyond concurrency

- **One meaning, compiler-chosen representation.** This is already how Dewy handles ints, copies and ownership. Keep applying it.
- **Refinements are orthogonal and checked.** A setting forbids a cost or pins a choice (`& no blocks`, `$no_hidden_costs`). It never switches you into a different dialect.
- **Unknown fails honest.** The safe choice plus an explanation, never optimism and never silence.
- **Expert power crosses a small, named boundary** and returns behind a safe value API (Rust's `unsafe` lesson). There is no global "trust me" mode.
- **Prune before release.** Every construct must justify itself against the others; that is the C++ and Scala lesson.
