**BLUF:** Yes: use one structured `parallel` operation, infer callback obligations, and specialize execution internally. Its guarantee must be **independent scheduling progress for admitted items**, not simultaneous CPU execution or successful completion. Dependency deadlock remains an algorithm error; scheduler-induced starvation is the implementation’s responsibility. Effects help select implementations but are not sufficient liveness proofs.

## 1. Soundness verdict and conditions

- **Scope:** Independent, read-only design review; owned output is this file. No implementation, benchmarks, repository edits, or review of the separate proposal. Budget: selective reading and under 2,000 words. Baseline: `safety_and_concurrency.md` adopted direction/deadlock/decided rules; `effects.md`; `LANGUAGE.md` parallel, tasks, channels, certificates. The implemented surface currently has serializable `parallel` plus `concurrent`/`spawn`; these examples propose replacing that distinction.
- **Verdict:** One construct can cover both lanes if it preserves structured lifetime, inferred transfer/disjointness checks, cancellation, and a backend capable of progressing every admitted runnable item. These are intersecting constraints, not simply one stronger/weaker ladder: race freedom, determinism, liveness, placement, and resource bounds are separate properties. Stronger inferred facts permit cheaper implementations without extra required tags or function colours.
- **Serialization proof:** `no blocks` alone is insufficient: `while !flag.load {}` can wait on a sibling without a blocking primitive. Include atomic polling, callbacks, hidden lifecycle hooks, joins, FFI and escaped aliases. Prove relevant independence/termination and preserve observable effect ordering, deadlines and cancellation; otherwise retain independent execution. Unknown effects choose the conservative runtime, rather than assuming independence. Do not require programmers to annotate callback safety; preserve symbolic callback effects through higher-order inference. `Send`/`Sync` alone do not prove disjoint writes or deterministic results.
- **Progress costs:** A fixed pool that executes blocking tasks inline can strand their producers. Parking waits must release execution capacity; opaque blocking requires dedicated/compensating capacity or rejection. Non-yielding CPU work needs preemption or bounded compiler safepoints for runnable-task fairness. A purely cooperative backend cannot promise arbitrary progress. Unsupported targets must diagnose the operation or return an explicit capability/resource failure, never silently serialize dependency-bearing work. Admission must not block behind work whose prerequisite has not been admitted; partial failure cancels and joins admitted children.
- **Memory/nesting:** Independent suspension costs at least live continuation state per suspended item, often a reserved stack, plus captures and results. A million dependent items cannot automatically become four chunks. Static stack bounds are conditional; recursion/FFI need fallback reservations and resource accounting. Pure independent items can share worker stacks/regions. Nested groups share scheduling capacity; joining must park/help rather than monopolize the workers their descendants require. Reclaim an arena only after every task using it has joined.
- **Determinism/reductions:** Preserve input-order map results and the existing sequential reduction order by default. A fixed tree is reproducible but changes floating-point answers relative to a left fold; it needs a separately specified reduction contract. Reassociation requires a proved lawful operator or explicit relaxed numerical policy. General communication, synchronized mutation, and completion order remain schedule-dependent even without data races.
- **Failure/cancellation:** Keep first observed child exception canceling siblings, level-triggered `Canceled`, and join-before-return, including cleanup. Concurrent failures make “first” schedule-dependent; deterministic success does not imply deterministic selected failure. Parent cancellation stays `Canceled`; only expiry of the local deadline becomes `Timeout`. Successful cancellation does not undo completed I/O or sends. Deadlines request cancellation; return can exceed the deadline while joining non-cooperative code or cleanup. CPU-specialized paths must preserve the specified cancellation contract.
- **GPU:** Device placement is separate from logical concurrency. Offload only device-compatible computation with a supported synchronization/progress model. Ordinary GPU launches do not guarantee all blocks are resident; cross-block waits can deadlock behind unscheduled blocks. Reject unsupported forced placement or fall back to the host when placement is merely a preference. Keep reduction and cancellation semantics across lowering.
- **`$no_deadlocks`:** Preserve the stronger opt-in proof: every wait, including cleanup and implicit joins, needs checked dependencies, lock order, a channel protocol certificate, or an audited boundary. Bounded-channel cycles remain possible under perfect scheduling. Timeouts are recovery, not certificates. State fairness, terminating local computation and cooperating external peers as assumptions; infer safety conservatively, rejecting unproved obligations only in the opted-in scope. Unification changes syntax, not this theorem.

## 2. Prior art: lesson / applicability

- These are design lessons from primary documentation, not claims that their APIs should be copied.

| System | Lesson | Applicability to Dewy |
|---|---|---|
| [Go WaitGroup](https://pkg.go.dev/sync#WaitGroup), [errgroup](https://pkg.go.dev/golang.org/x/sync/errgroup) | Goroutines supply concurrency; WaitGroup joins, while errgroup adds errors/context cancellation. Admission limits can block launches. | Combine lifetime/failure policy; avoid bounded admission deadlocking prerequisites. |
| [Java Loom](https://docs.oracle.com/en/java/javase/25/core/virtual-threads.html), [structured scopes](https://docs.oracle.com/en/java/javase/25/core/structured-concurrency.html) | Virtual threads preserve ordinary blocking call style; scopes organize lifetime and failure. | Strong evidence colours are unnecessary; runtime integration and per-task state still cost resources. |
| [Swift async let/task groups](https://raw.githubusercontent.com/swiftlang/swift-book/main/TSPL.docc/LanguageGuide/Concurrency.md) | Fixed and dynamic children share structured lifetime; cancellation is cooperative. | Unify fixed/dynamic fan-out, retain transfer checks; do not promise cancellation forcibly stops code. |
| [Kotlin coroutines](https://kotlinlang.org/docs/coroutines-basics.html) | Suspending work releases its thread; `suspend` colours functions. | Adopt scheduling/lifetime ideas; Dewy inference replaces the required declaration marker. |
| [Trio nurseries](https://trio.readthedocs.io/en/stable/reference-core.html) | Nursery exit joins; failure cancels siblings; cancellation is level-triggered; a nursery can be passed outward. | Closest lifetime/cancellation model; longer-lived owner replaces detachment. |
| [Rayon](https://docs.rs/rayon/latest/rayon/fn.join.html) / [Tokio](https://docs.rs/tokio/latest/tokio/task/index.html) | CPU work stealing and suspendable tasks have different blocking assumptions; Rayon warns of sibling-wait deadlock. | One surface still needs distinct scheduling strategies and conservative blocking boundaries. |
| [Zig std.Io](https://raw.githubusercontent.com/ziglang/zig/master/lib/std/Io.zig) | `async` permits immediate execution; `concurrent` strengthens progress and may fail with `ConcurrencyUnavailable`. | Hide the choice only when inferred proofs justify it; preserve explicit inability to provide concurrency. |
| [Cilk](https://www.opencilk.org/doc/tutorials/introduction-to-cilk-programming/) / [OpenMP](https://www.openmp.org/spec-html/5.0/openmpsu51.html) | Cilk expresses potential parallelism; OpenMP scheduling constraints can interact with locks and deadlock. | Keep cheap serializable execution where proved valid; task syntax alone supplies no universal progress theorem. |
| [Erlang processes](https://www.erlang.org/doc/system/ref_man_processes.html) | Lightweight isolated processes communicate through messages and support links/monitors. | Tasks plus channels suffice for actors; isolation does not itself provide structured lifetime or bounded backpressure. |
| [Chapel forall/coforall](https://chapel-lang.org/docs/primers/loops.html#task-parallel-loops) | `forall` permits hardware-sized task decomposition; `coforall` creates one task per iteration, permitting inter-iteration synchronization at greater resource cost. | Direct counterexample to cost-free unification. Dewy can infer the distinction internally, but cannot erase its scheduling/memory consequences. |

## 3. `select` without new syntax

- **Recommend one ordinary call:** `select(receive_op(inbox) timeout_op(2s))`, returning a tagged union consumed by ordinary `match`. Operation construction registers nothing and consumes nothing. Selection registers alternatives together; one linearization point commits exactly one ready operation. Losing receives consume no message; losing sends transfer no payload; registrations are removed before return. Already-canceled scope returns `Canceled`; a concurrent commit/cancel race has one ordered winner. Specify fair arbitration among simultaneously ready alternatives and the timer’s monotonic start point at selection entry.
- Operations are single-use values with checked lifetimes and ownership. Support only primitives/compositions implementing the selection protocol; arbitrary HTTP calls are not transactional operations. Racing ordinary tasks then canceling losers cannot implement this guarantee: two receives may already have consumed messages. CML-style transactional choice is a useful model, not a promise of distributed rollback.
- **Self-contained proposed Dewy example:** `concurrency` is the proposed library module, importing every non-prelude name below. `channel<int>(1)` declares a bounded integer inbox; `receive_op` creates a dormant receive, `timeout_op` a timer alternative, and `select` commits one. Imported union alternatives are `Received`, `Closed`, `Timeout`, `Canceled`; `value` is bound by its pattern. `int` and `printl` are prelude names. No sender exists here, so the uncanceled example times out.

```dewy
from concurrency import channel, receive_op, timeout_op, select,
                        Received, Closed, Timeout, Canceled
let inbox = channel<int>(1)
let chosen = select(receive_op(inbox) timeout_op(2s))
let answer = match chosen {
    Received(value) => value
    Closed => -1
    Timeout => 0
    Canceled => -2
}
printl(answer)
```

## 4. Smallest recommended common surface

- **One semantic operation, ordinary calls:** propose `parallel(xs @f)` for ordered map; `parallel([@a @b])` for a homogeneous job collection; `parallel(owner @job)` to enroll one child in an existing owner and return after admission. `scope(@body)` supplies that owner and joins its children. These are proposed overloads/library spellings requiring David’s surface approval, not implemented APIs. No new loop, capture, `async`, `await`, `spawn`, or selection grammar is needed. Choosing a longer lifetime necessarily needs an owner value; effects cannot infer the programmer’s desired lifetime.
- Supporting library names below: `within` establishes a deadline; `cancel` cancels an owner; `sleep` is cancellable; `channel`, `Channel` and `Closed` retain current channel meaning; `TaskGroup` is the owner type. Each snippet uses these library/prelude declarations. Effects, transfer properties and callback parallel-safety are inferred. Expert callable types, placement policies and `$no_deadlocks` refine guarantees without mandatory common-case tags.
- **Parallel map:** no blocking effects; specialize to chunks or inline work.

```dewy
square = (x:int) => x*x
let squares = parallel([1 2 3] @square) or_throw
```

- **Fetch N URLs:** `get` is the imported HTTP client operation; the literal array supplies N. Deadline covers the entire structured map, including its children.

```dewy
from http import get
let urls = ["https://example.org/a" "https://example.org/b"]
fetch_all = () => parallel(urls @get) or_throw
let pages = within(2s @fetch_all) or_throw
```

- **Producer/consumer:** capacity one; both jobs return `void`, avoiding heterogeneous job-array inference.

```dewy
produce = (q:Channel<int>) => {
    q.send(42) or_throw
    q.close
}
consume = (q:Channel<int>) => { printl(q.receive or_throw) }
let q = channel<int>(1)
parallel([@produce(q) @consume(q)]) or_throw
```

- **Outlive creator:** `start` returns while `background` remains owned by the enclosing scope. Captures must outlive their use; no borrowed creator stack can escape. Child cancellation/deadlines derive from the owner, not an expired creator scope.

```dewy
background = () => { sleep(1s) or_throw }
start = (owner:TaskGroup) => { parallel(owner @background) or_throw }
application = (owner:TaskGroup) => { start(owner) or_throw }
scope(@application) or_throw
```

- **Cancellation:** persistent within the owner; closing `scope` still joins cleanup. The child may observe cancellation before starting or during sleep.

```dewy
worker = () => { sleep(10s) or_throw }
stop = (owner:TaskGroup) => {
    parallel(owner @worker) or_throw
    cancel(owner)
}
scope(@stop) or_throw
```
