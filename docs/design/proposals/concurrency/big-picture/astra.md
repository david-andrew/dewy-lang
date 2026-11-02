- **BLUF:** Make pure value computations automatically exploit SIMD, cores and, where profitable and semantically equivalent, GPUs. Keep `parallel` as the single explicit permission for concurrent execution. Add independent schedule controls around the same algorithm; do not make experts graduate to a different language. Proposal-v2 has the right surface economy, but its progress, resource and determinism promises need tightening before adoption.
- **Scope:** Design only; no implementation or new decisions. Based only on the shared brief, GOALS, the adopted/decided concurrency sections, and proposal-v2. Acceptance: a usable ladder, complete miniature sketches, explicit semantic boundaries, and a verdict. Budget: one short pass, under 2,500 words; no repository edits or benchmarks.
- **Sketch convention:** Each fenced snippet is independent and declares its application identifiers. Built-in types need no declaration. `import … from …` is illustrative import notation, not an asserted Dewy spelling; it explicitly binds proposed library names. All new metatags, library APIs and expert interfaces below are design sketches requiring David's approval, not claims that these programs compile today. Tiny inputs demonstrate semantics, not profitable parallel workloads.

- **Rung 0 — ordinary scalar code gets SIMD automatically.** Cost: zero words. Benefit: packed arithmetic, fused traversal and avoided intermediates when legal. Value semantics help alias analysis; they do not authorize changed floating-point rounding, overflow, exceptions, observable allocation or stateful-callback behavior. Use cheap local proofs in the default compiler; expensive search belongs in an optional optimization tier.
  ```dewy
  twice = (x:float64):>float64 => x + x
  let xs = [1.0 2.0 3.0 4.0]
  let ys = [x in xs twice(x)]
  ```
  - Vectorize this with the same per-element arithmetic. An opaque callback or loop-carried dependency prevents widening unless a reusable summary proves otherwise. No mandatory SIMD tag, including on callbacks.

- **Rung 1 — pure bulk values get cores automatically.** Cost: zero words. Benefit: map, comprehension and reduction scaling once useful work exceeds overhead. The default is “attempt parallel execution for proven-independent bulk operations,” never “assume safe until disproved.” Unknown effects select serial execution. Ordinary imperative loops retain ordered semantics, although equivalent machine-level transformations remain legal.
  ```dewy
  import sum from std.reduce
  let xs = [i in [0..1000000) 1.0]
  let total = sum(xs)
  ```
  - Infer purity, ownership and effects, including transitive effects. No shared mutation, ordered I/O, address-sensitive behavior, mutable captured closure state, observable nondeterminism or changed failure selection. Snapshot captures alone do not make per-worker copies of a stateful callback equivalent to sequential invocation.
  - For an existing sequential fold, preserve its order unless reassociation is proved equivalent. Floating-point addition is not generally associative. A separately specified reproducible bulk reduction may use a canonical index-based tree, identical on serial CPU, multicore and GPU; worker count and grain cannot change it. Decide that contract before implementation. Merely using a fixed tree per execution is insufficient.
  - Automatic scheduling adds no public cancellation alternative or first-in-time failure. Bodies returning error values can produce ordered arrays of errors; implicit parallelism must preserve sequential `or_throw` selection and observable effects. Otherwise retain serial execution.

- **Rung 2 — tensor operations get automatic placement.** Cost: zero words. Benefit: fusion, tiling, SIMD and large GPU execution through the same value operations.
  ```dewy
  import tensor from std.tensor
  let xs = tensor([i in [0..1000000) 1.0])
  let ys = xs + xs
  ```
  - Offload only eligible pure operations with equivalent numeric and failure semantics. Account for compilation, queueing, synchronization, transfers, residency and memory pressure, not just FLOPs or element count. Small work stays on CPU. Keep intermediate tensors resident when reuse pays; synchronize when values become observable.
  - No silent reduced precision, changed NaN handling, reassociation or contraction. Lacking equivalent device operations means CPU fallback. Device absence can fall back; device loss after dispatch must follow a defined failure/retry policy. Replay is safe only for pure work and must preserve cancellation and resource contracts.
  - Ship this incrementally: SIMD first, automatic CPU bulk scheduling next, automatic GPU placement after reliable cost and residency accounting. A generic “does not park” predicate is not a GPU eligibility proof.

- **Rung 3 — `parallel` makes concurrency intentional.** Cost: one word. Benefit: concurrent independent waits and explicit disjoint updates, plus visible permission to reorder otherwise ordered work.
  ```dewy
  import sleep from std.time
  fetch = (id:int) => {
      sleep(1ms) or_throw
      id
  }
  let results = [parallel id in [1 2 3] fetch(id) or_throw]
  ```
  - The word grants concurrency semantics; it neither forces multiple cores nor promises a speedup. Pure small bodies may still run inline. Results retain input order; external effects and first-in-time failure may vary. Those are semantic permissions unavailable to an unmarked comprehension.
  - Race freedom is mandatory and inferred, not an optimistic runtime assumption. Illegal sharing is a diagnostic, not silent serialization that could deadlock a cooperating program. Ordinary file/network operations never become concurrent merely because the compiler notices idle cores.

- **Rung 4 — layout makes locality intentional.** Cost: one representation tag at storage creation. Benefit: fewer unused bytes fetched, contiguous fields, better vectorization and GPU transfers; algorithm and field access remain unchanged.
  ```dewy
  Particle:type = [x:float64 vx:float64]
  $layout = "soa"
  let particles = [Particle[1.0 0.5] Particle[2.0 0.25]]
  parallel @p in particles { p.x += p.vx }
  ```
  - SoA must describe collection representation, not pretend each particle is a conventional contiguous record. Element places can be structured projections. FFI, stable addresses and pointer escapes can prohibit this representation or require an explicit packing boundary. Report conversion/copy costs. Automatic internal layout is allowed only when unobservable; AoS, SoA and tiled layouts are workload choices, not a universal ranking.

- **Rung 5 — `$device` chooses placement.** Cost: one contextual tag; tensor types and algorithm stay unchanged. Benefit: residency across several operations and predictable target selection.
  ```dewy
  import tensor from std.tensor
  $device = "gpu"
  let xs = tensor([1.0 2.0 3.0 4.0])
  let ys = xs + xs
  let zs = ys + xs
  ```
  - Recommend that an explicit target is a requirement with a visible unsupported-target result or diagnostic, not a silent hint; automatic placement remains opportunistic. Device selection must be resolved before dependent work. The exact error surface needs approval. A contextual requirement propagates through eligible calls; the hover exposes transfers and host boundaries. This is representation/placement, not `GpuTensor` infecting signatures.

- **Rung 6 — `& no blocks` locks in a property.** Cost: one effect exclusion on the hot function. Benefit: edits cannot accidentally introduce waiting; no callback coloring.
  ```dewy
  tick = (@xs:array<float64>):>void & no blocks => {
      parallel @x in xs { x += x }
  }
  let xs = [1.0 2.0 3.0 4.0]
  tick(@xs)
  ```
  - This is a checked contract, not an optimization switch or a latency guarantee. It excludes blocking implementations; it does not alone prove purity, device eligibility, absence of allocation, freedom from atomic spin loops or bounded execution time. A fork-join implementation must satisfy the effect contract under the language's definition of blocking. Add `& no allocates` and strict ownership only when needed; shared COW storage may then require an explicit uniqueness boundary.

- **Rung 7 — grain and window bound different costs.** Cost: one numeric tag per concern. Benefit: grain amortizes scheduling overhead; window caps admitted independent operations and their memory footprint.
  ```dewy
  import sleep from std.time
  let xs = [1.0 2.0 3.0 4.0]
  $grain = 256
  let ys = [parallel x in xs x + x]
  wait_one = (id:int) => { sleep(1ms) or_throw; id }
  $window = 2
  let ids = [parallel id in [1 2 3 4] wait_one(id) or_throw]
  ```
  - Proposed tags attach to the next construct. Grain is a schedule preference; window is a hard admission ceiling. Neither changes reduction association. Grain also affects cancellation latency; explain the trade-off.
  - A window is valid only where progress does not require an unadmitted item. If an explicit window conflicts with a sibling dependency, reject it with the dependency witness; never silently ignore the cap. Unknown dependencies cannot justify bounded admission. A bound on workers is separate: blocked tasks must release workers, and runnable dependencies must still make progress.

- **Rung 8 — explicit SIMD specializes one leaf.** Cost: a vector type and, when necessary, intrinsics. Benefit: lane operations, shuffles and target-specific instructions while callers retain ordinary arrays.
  ```dewy
  import Simd, map_chunks from std.simd
  twice4 = (v:Simd<float64 4>):>Simd<float64 4> => v + v
  twice = (x:float64):>float64 => x + x
  let xs = [1.0 2.0 3.0 4.0 5.0]
  let ys = map_chunks(xs @twice4 @twice)
  ```
  - Proposed `map_chunks` handles alignment, full vectors and scalar tails safely. Portable vectors need no danger opt-in; unchecked loads or instructions with unverifiable preconditions do. Keep the scalar reference as fallback. This replaces one leaf implementation, not the application; changed numeric semantics require an explicit separate contract.

- **Rung 9 — atomics and verified lock-free primitives expose communication.** Cost: explicit shared handles and memory orders. Benefit: counters, queues and publication without putting synchronization into unrelated computation.
  ```dewy
  import Atomic from std.atomic
  let count = Atomic<int>(0)
  parallel i in [0..4) { count.fetch_add(1 "relaxed") }
  let total = count.load("relaxed")
  ```
  - The structured join establishes completion; this counter is not a publication protocol. Prefer a reduction for actual counting. Atomic race freedom does not imply deterministic intermediate observations, fairness or progress.
  ```dewy
  import spsc from std.concurrent
  transfer = () => {
      let [tx rx] = spsc<int>(1)
      let result = 0
      parallel {
          { tx.send(7) or_throw }
          { result = rx.receive or_throw }
      }
      result
  }
  let answer = transfer or_throw
  ```
  - Proposed endpoint API: blocking operations are cancellation-aware, and linear endpoint capabilities enforce one producer and one consumer. The library owns memory reclamation and the model-checked protocol. A concurrent block connects existing compute leaves without rewriting them. Building a new unchecked reclamation scheme belongs at an explicit danger boundary.

- **Rung 10 — placement and schedulers become replaceable context.** Cost: a context tag plus configuration. Benefit: affinity, NUMA locality, dedicated pools and domain scheduling without kernel dependencies on worker identity.
  ```dewy
  import Scheduler from std.scheduler
  run = (scheduler:Scheduler xs:array<float64>) => {
      $scheduler = scheduler
      $cores = [0]
      [parallel x in xs x + x]
  }
  ```
  - The caller supplies a standard or custom scheduler through the same interface. Pinning limits migration; it does not guarantee realtime behavior. A custom scheduler must preserve joins, cancellation, admission failures and progress obligations, including on one selected core. Reject unsupported capabilities before entry. Nested calls inherit context; do not create an independent pool at every rung. Raw executor access that breaks these contracts is explicitly outside safe structured execution.

- **Rung 11 — custom GPU kernels replace selected implementations.** Cost: a kernel declaration and a schedule binding. Benefit: workgroup sizing, shared-memory tiling, subgroup operations and domain-specific fusion.
  ```dewy
  twice = (x:float64):>float64 => x + x
  $gpu_kernel
  twice_gpu = (x:float64):>float64 => x + x
  let xs = [1.0 2.0 3.0 4.0]
  $device = "gpu"
  $kernel = @twice_gpu
  $workgroup = 256
  let ys = [parallel x in xs twice(x)]
  ```
  - Proposed binding substitutes a checked per-element kernel for this map; tails are masked. Richer bulk kernels need declared read/write regions, synchronization rules and shape contracts. The tiny example intentionally preserves the algorithm. Equivalence of arbitrary replacement kernels is not generally provable: distinguish compiler-verified specializations from expert-supplied implementations with explicit responsibility and differential tests.
  - Halide's useful principle is algorithm/schedule separation. Do not promise every optimization needs no rewrite: a different algorithm, public storage ABI or cross-element fusion may require a new implementation. Preserve the public value interface and localize that change.

- **Visibility — explain the decision and the measured bill.** Hover should say, for example: “pure map; CPU pool; SIMD width 4; threshold not reached; executed serially,” or “GPU eligible; kept on CPU: estimated transfer dominates.” Distinguish compile-time proof, runtime choice, estimate and measurement.
  - Show inferred effects and their call chains; ownership/disjointness proof; vector width and tail; reduction association; placement/residency/transfers; fusion; grain/window; task count; cancellation boundaries; COW detach and allocation.
  - Give actionable negatives: “not vectorized: opaque callback”; “not parallelized: iteration reads the preceding write”; “not offloaded: observable I/O”; “window rejected: item 0 waits on item 5.” A missed heuristic is an informational remark, a violated explicit contract an error.
  - Profiles attribute time to useful work, scheduling, synchronization, copies, transfers and queueing. Correlate generated kernels to source. Offer serial/reference execution and differential checks for pure computations; seeded scheduling aids debugging but does not promise deterministic external I/O.

- **Verdict on v2:** Keep one `parallel`, inferred callback safety, structured lifetimes and inferred strategy. Do not equate “logically concurrent” with “all start together”: a window explicitly delays admission. Promise overlap sufficient for supported dependencies, not simultaneous starts.
  - Keep the compute/waiting distinction internally. Unknown behavior may require independently schedulable tasks, but unbounded task-per-item admission cannot be the universal fallback, especially for streaming sources. Specify exhaustion as a value or established allocation obligation; v2's process termination contradicts the adopted spawn-failure rule and needs an explicit decision.
  - Parking analysis is insufficient: atomic spinning, foreign blocking and nonpreemptive CPU loops can prevent progress. Likewise, nonparking logging is neither pure nor GPU-safe. Conservative summaries and bounded runtime guarantees matter more than one clever inference pass.
  - Specify window/cap behavior now. A received job may depend on a later job in the same stream; “receiver means window” is unsound without an independence contract. Diagnose unsupported combinations instead of hiding a deadlock behind backpressure.
  - Replace v2's broad “determinism” claim with exact promises: ordered results, defined reduction association, and explicit nondeterminism for effects/failure races. Remove the residual required `$parallel_safe` story; the brief says inference is decided.
  - More generally, the 80/20 rule should mean useful defaults plus orthogonal, checked refinements: storage, effects, placement and scheduling. Each refinement should expose its cost and preserve the value-level API. One keyword is worthwhile only if its guarantees remain understandable.
