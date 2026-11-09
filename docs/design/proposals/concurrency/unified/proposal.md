# One `parallel`: a unified concurrency surface for Dewy (proposal, 2026-11-01)

## BLUF

- **One keyword, `parallel`, means "these run at the same time".** It has three shapes: the loop (`parallel x in xs {…}`), the comprehension (`[parallel x in xs e]`) and a new block (`parallel { a  b  c }`, where each statement is one item).
- **There is no separate waiting lane in the syntax.** The compiler picks the execution strategy from the body's inferred effects:
  - a body that never waits runs on the work-stealing pool, chunked or inline;
  - a body that may wait gets one task per item, all making progress together.
  - Your example `[parallel i in [0..2) step(i)]`, where one step waits on the other, then simply works.
- **Removed:** the keywords `concurrent` and `spawn`, `concurrent g {…}`, `spawn(g) e`, `cancel(g)`, `parallel_map`, `parallel_range` and `parallel_update`, and the never-built `[concurrent …]` and `select {…}`.
- **Added (library only, no grammar):**
  - `tasks(body)` with `Tasks.spawn(@f(x))` and `.cancel`, for work that outlives a function;
  - `select(op op …)` over operation values (`ch.receiving`, `ch.sending(v)`, `timeout(d)`), consumed with an ordinary `match`;
  - receivers usable as loop sources (`loop job in jobs`).
- **One failure rule:**
  - errors stay per-item values;
  - `or_throw` inside an item means "abort everything": siblings are canceled and joined, then the error leaves the enclosing function, exactly as it would in a sequential `loop`.
- **Precision is opt-in through things that already exist:**
  - `& no blocks` (must stay compute-only);
  - `$parallel_safe` (an export contract);
  - `$no_deadlocks` (certificates);
  - placement context.
- **Kept unchanged:** channels, `Unsent`, `spsc`, `mpmc`, `Mutex`/`lock_all`, `Atomic`, `within`, `race`, `serve`, `pipeline` and `$no_deadlocks`.

## 1. The unified model

- **What a reader sees is what it means.** In `parallel`, every item is logically started at once, and the construct ends when every item has ended. Any interleaving of the items is a legal run.
- **Constraints, not lanes.** The obligations on items are one set, all inferred and none written. They don't form one strong/weak ladder; they are separate properties, each checked where it matters:
  1. **Race freedom (always).** An item writes only places no other item touches: its own `@x` element, a disjoint field or partition, or a place nothing else in the construct reads. Shared state goes through synchronized handles (`Atomic`, `Mutex`, channels). Captures must be `Send`/`Sync` (inferred).
  2. **Waiting (inferred `blocks`) chooses the strategy, never legality.**
     - *No `blocks` in the body:* no item can wait on another, so the runtime may chunk, steal or run items inline. The only difference is timing, and the inline order is one of the legal interleavings.
     - *`blocks` in the body:* each item is a task. Admission never makes a waiting item wait for an unstarted sibling: whenever a started item waits, the runtime starts more.
     - Polling an atomic in a loop counts as waiting (already the rule for spins). The analysis still warns, because a channel or a lock waits better.
  3. **Determinism.** Collected results are in input order. Reductions are reordered only when an associative operator is proven; otherwise they take the sequential order. What depends on timing is only the interleaving of side effects through shared handles, and which failure comes first.
  4. **Lifetime is structured.** Nothing outlives its construct. Work that must outlive a function goes into a `Tasks` group that the caller owns.
- **Why effects suffice (the earlier objection).** The old #118 argument said that reusing `parallel` for waiting work changes semantics. Under this model it doesn't:
  - *Per-item errors versus fail-fast* is chosen by the existing `or_throw`, not by the construct.
  - *Admission failure* follows the allocation policy (decision 7), so it adds no new result types.
  - *Cancellation* adds nothing to the construct's type, because scopes report it at their boundaries (§5).
  - When a helper starts to block, the loop silently moves from the pool to tasks. Its *cost* changes and its *meaning* does not. That is the whole point of having no colours.
  - When the cost matters, say so with `& no blocks` on the helper or the callback type.
- **The runtime's duties (from the soundness check):**
  - a waiting task releases its worker;
  - opaque foreign blocking gets compensating capacity, or a diagnostic;
  - long CPU stretches inside tasks get preemption (on the threads backend) or safepoints (M:N);
  - a target that can't run waiting items yet (wasm, before stackless lowering) gets a compile diagnostic, never silent serialization.
- **Device placement stays separate.** A GPU is placement context. Only bodies that never wait can be offloaded.

## 2. Inventory

| Construct | Verdict | Why |
|---|---|---|
| `parallel x in xs {…}` | **Keep**, redefined as "at the same time" | Matches the reader. The strategy is inferred, so blocking bodies are now legal. |
| `[parallel x in xs e]` | **Keep**, same | Also replaces the `[concurrent …]` gather. Per-item results unless `or_throw`. |
| `parallel { s1  s2 }` | **New shape** of the existing keyword | Fixed, heterogeneous fan-out (two different calls). Replaces `concurrent {}` + `spawn`. `let` items bind after the block, as `concurrent` did. |
| `concurrent {…}`, `spawn f()` | **Remove** | Covered by the block. Two fewer keywords. |
| `concurrent g {…}`, `spawn(g) e`, `cancel(g)`, `TaskGroup` | **Replace** with `tasks(body)`, `Tasks`, `g.spawn(@f(x))` and `g.cancel` | Explicit long-lived groups are rare. A library function and two methods suffice, in the same shape as `serve(handler body)`. |
| `[concurrent x in xs …]` | **Drop** (never built) | It is `[parallel …]`. |
| `select {…}` syntax | **Drop** (never built) | It becomes the library `select(ops)` + `match` (§3). |
| `race(@a @b)` | **Keep** | It runs whole calls and discards the losers' work. That differs from `select`, which commits exactly one operation. Already decided. |
| `within(d @f)` | **Keep** | The most common timeout. It is a deadline scope: its own expiry gives `Timeout`. |
| `parallel_map`, `parallel_range`, `parallel_update` | **Remove** | The comprehension, the `@x` loop and the block (`parallel { sort(@left)  sort(@right) }`) cover them. There is no legacy to keep. |
| `Channel<T>`/`channel<T>(n)` | **Keep** | `send` gives `void \| Unsent<T>` (accepted). Add the op members `.receiving` and `.sending(v)`, and iteration. |
| `spsc<T N>` + `.split`, `mpmc<T>(n)` + `Busy` | **Keep** (accepted) | Same verbs, the same op members and iteration as channels. |
| `Mutex`, `lock`, `try_lock`, `lock_all` | **Keep** | `lock` doesn't cancel; `lock_all` does (decided). |
| `Atomic<T>` with explicit orders, `CachePadded<T>` | **Keep**, expert lane | Unchanged. |
| `serve`/`Service`/`.request`, `pipeline` | **Keep** | They are *certified* protocols for `$no_deadlocks`, built on `parallel` and channels. |
| `$no_deadlocks`, `& no blocks` | **Keep** | They are the precision opt-ins. |
| `$parallel_safe` | **Keep, narrowed** | "Safe to call from several items at once" now means race-free only, because blocking no longer disqualifies anything. |
| `Canceled`, `Closed`, `Timeout`, `Unsent`, `Full`, `Busy` | **Keep** | Outcomes as values. |
| `SeqLock`, `Snapshot`, `Sequencer` | Unchanged | Outside this proposal (stage-4 library). |

## 3. `select` without new syntax

### The shape

```dewy
Job:type = [id:int]
Command:type = [name:string]

dispatch = (jobs:Channel<Job> control:Channel<Command>) => {
    loop true {
        match select(control.receiving  jobs.receiving  timeout(100ms)) {
            c:Command => if c.name =? "stop" break
            j:Job => printl"job {j.id}"
            t:Timeout => printl"idle"
            c:Closed => break
            c:Canceled => break
        }
    }
}
```

### What each piece is

- `control.receiving` is an ordinary zero-argument method, so it takes no parentheses. It returns an **operation value** `Op<Command | Closed>`. Making it waits for nothing, takes nothing and registers nothing: it is just a description, "receive from `control`".
- `timeout(100ms)` is an ordinary function returning `Op<Timeout>`. It becomes ready 100 ms after `select` starts waiting.
- `select(…)` is an ordinary library function taking any number of `Op` values. It waits until at least one is ready, then **commits exactly one**:
  - a losing receive takes no message;
  - a losing send moves no payload;
  - registrations are removed before it returns.
- **Type of `select`'s result:** the union of the ops' result types, plus `Canceled`, because `select` is a wait, and so a cancellation point.
  - Here that is `Command | Job | Timeout | Closed | Canceled`.
- `match` is the existing `match`, with type patterns. It is not a new arm grammar and no function literals are involved.
- **Ties:** when several ops are ready, the earliest argument wins. Order is priority, so `control` goes first, and tests are deterministic. The alternative is a random choice, as Go does (decision 5).

### Sending as an op

`out.sending(msg)` gives `Op<void | Unsent<Msg>>`. The payload moves only if that op commits; otherwise `msg` is still the caller's.

```dewy
let out = channel<int>(1)
let back = channel<int>(1)
match select(out.sending(42)  back.receiving) {
    v:void => printl"sent"
    u:Unsent<int> => printl"not sent: {u.reason}"
    n:int => printl"got {n} first"
    c:Closed => printl"back closed"
    c:Canceled => printl"canceled"
}
```

### Limits, stated plainly

- Two receives of the same payload type are indistinguishable in `match`. For a fan-in merge that is exactly what you want. To tell them apart, use distinct payload types, or the later `op.then(f)` (decision 5b).
- Only library primitives implement `Op`. Arbitrary calls are not transactional, so racing calls stays `race`.

## 4. Common tasks

Every snippet declares what it uses. None needs an annotation.

**Parallel map and reduction.**

```dewy
let squares = [parallel i in [0..1000000) i*i]   # never waits: chunked across cores
let total = sum(squares)                          # same order as the sequential sum, every run
```

**Fetching N URLs at once, with a timeout.** `get` is a stand-in for an HTTP call; its `sleep` makes it wait.

```dewy
get = (url:string) => {
    sleep(50ms) or_throw
    "page at {url}"
}
fetch_all = (urls:array<string>) => [parallel url in urls get(url) or_throw]

main = () => {
    let urls = ["a.example" "b.example" "c.example"]
    let pages = within(2s @fetch_all(urls)) or_throw         # one deadline for all of them
    let each = [parallel url in urls within(1s @get(url))]   # per URL: array<string | Timeout | Canceled>
    printl"{pages.length} {each.length}"
}
```

- `fetch_all` aborts on the first failure. `each` keeps every outcome. The difference is only whether there is an `or_throw`.

**Producer and consumer.**

```dewy
main = () => {
    let numbers = channel<int>(16)
    let total = 0
    parallel {
        {                                             # item 1: the producer
            loop i in [0..1000) { numbers.send(i) or_throw }
            numbers.close
        }
        loop n in numbers { total += n }              # item 2: ends when numbers closes
    }
    printl"{total}"                                   # 499500
}
```

- `total` is written by one item only, so it is legal, and it is read after the join.

**A worker pool.** For pure compute there is no pool to build: `[parallel j in jobs handle(j)]` is already sized to the cores. A pool is for limiting *waiting* work, such as at most 8 connections at once:

```dewy
handle = (job:int) => {
    sleep(5ms) or_throw
    job * 2
}

main = () => {
    let jobs = channel<int>(64)
    let results = channel<int>(64)
    let total = 0
    parallel {
        {
            loop j in [0..1000) { jobs.send(j) or_throw }
            jobs.close
        }
        {
            parallel worker in [0..8) {
                loop j in jobs { results.send(handle(j) or_throw) or_throw }
            }
            results.close
        }
        loop r in results { total += r }
    }
    printl"{total}"
}
```

**Waiting on several channels plus a timeout.** See `dispatch` in §3.

**A game job system (per-frame parallel update).**

```dewy
Particle:type = [x:float64 vx:float64]
World:type = [particles:array<Particle> heat:array<float64> frames:int]

diffuse = (@heat:array<float64> dt:float64) => {
    parallel @h in heat { h *= 1.0 - dt }
}

frame = (@world:World dt:float64) => {
    parallel {
        parallel @p in world.particles { p.x += p.vx * dt }   # many small jobs
        diffuse(@world.heat dt)                               # another field, so disjoint
    }
    world.frames += 1                                         # after the join: sequential again
}
```

- Nothing in `frame` waits, so it all runs on the stealing pool with zero task cost.
- To make that a guarantee for a hot path, add `:>void & no blocks` to `frame`.

**Background tasks that outlive a function.**

```dewy
autosave = () => {
    loop true {
        sleep(30s) or_throw
        printl"saved"
    }
}
start_autosave = (group:Tasks) => group.spawn(@autosave)   # returns at once
play = () => sleep(2s)

main = () => {
    tasks((group:Tasks) => {
        start_autosave(group)   # autosave lives on in main's group
        play or_throw
        group.cancel            # stop the background work; tasks still joins it
    }) or_throw
}
```

**Cancellation.**

```dewy
slow = (n:int) => {
    sleep(100ms) or_throw   # a cancellation point
    n
}

main = () => {
    let quick = within(1s @slow(1))     # 1
    let late = within(10ms @slow(2))    # Timeout: slow's sleep gave Canceled, within names its own deadline
    tasks((group:Tasks) => {
        group.spawn(@slow(3))
        group.cancel                    # slow(3) gets Canceled at its sleep; tasks returns normally
    }) or_throw
    let firsts = [parallel n in [1 2 3] within(50ms @slow(n)) or_throw]
    # the first Timeout cancels the other two, joins them, and leaves main with Timeout
}
```

## 5. Failure and cancellation: one rule set for every construct

1. **Errors are values.** An item's result is whatever its body gives. A comprehension collects them, and nothing is canceled.
2. **`or_throw` in an item aborts the construct.**
   - The item fails, its siblings are canceled, and every item is joined, with cleanup.
   - The error then goes where `or_throw` would take it in a sequential `loop`: out of the enclosing function.
   - The first failure in time wins. Siblings' `Canceled` are not reported; any other genuine failures are attached as causes (#80).
   - The same rule holds for `parallel` blocks, `tasks` (a spawned task's failure cancels the group and its body), `race` and `select`.
3. **Every construct is a cancel scope, and nesting propagates.**
   - The scopes are `parallel` (each of its shapes), `tasks`, `within`, `race` and `select`.
   - Canceling a scope cancels everything inside it.
   - It is **level-triggered**: after a cancel, every cancellation point in the scope returns `Canceled` until the scope exits. Swallowing it is therefore harmless.
4. **Cancellation points are the waits:** channel and queue operations, `sleep`, I/O, process waits, `select`, `lock_all`, and joins of waiting items.
   - Not `lock` (decided), not console output, and not compute. A `parallel` that never waits runs to completion.
5. **A construct adds no outcomes of its own.**
   - A `parallel`'s value has the type of the equivalent sequential loop.
   - A cancellation from outside surfaces at the scope that owns the reason:
     - `within` gives `Timeout` for its own deadline;
     - `tasks` absorbs its own `.cancel`;
     - a parent's cancellation stays `Canceled`, and reaching `main` it is reported like any other error.
6. **Joins always happen.** No construct returns while a child runs. Cleanup (`defer`, drop hooks) is shielded, with a grace deadline.
7. **Resources.** Starting a task is an allocation, so it follows the decided allocation policy:
   - in ordinary code, exhaustion ends the process with a report;
   - under `$explicit_allocation_failure`, the construct gives `OutOfMemory`.
8. **Deadlocks are algorithm bugs, checked as today.** The default analysis rejects demonstrated cycles (channels, locks, joins). `$no_deadlocks` demands certificates. Timeouts are recovery, not proofs.

## 6. Decisions for David

Each decision lists its new and removed spellings. All of them are reversible before release.

1. **`parallel` means "at the same time"; the strategy is inferred from `blocks`.**
   - *Recommend:* yes, and allow waiting bodies. This retires the rule "a `parallel` body must not block".
   - *Alternatives:* keep a separate waiting construct (`[concurrent …]`, which you rejected), or make every item a task (simple, but it loses zero-cost compute loops).
   - *Spellings:* none new.
   - *Unblocks:* gathering task results, and #118.
2. **The block form `parallel { … }`, where each top-level statement is one item.**
   - `let` items bind after the block.
   - An item that reads another item's binding is a compile error naming both.
   - `{ … }` groups several statements into one item.
   - *Recommend:* yes.
   - *Alternatives:* a library `both(@f @g)` (needs heterogeneous tuples), or keeping `concurrent {}` + `spawn`.
   - *Removes* the keywords `concurrent` and `spawn`.
3. **Failure through `or_throw` (rule 5.2).**
   - *Recommend:* per-item values unless `or_throw`, which aborts the whole construct.
   - *Alternative:* parallel constructs are always fail-fast. That loses "fetch all, report each".
   - *Spellings:* none.
4. **Long-lived groups go through the library: `tasks(body)`, `Tasks`, `g.spawn(@f(x))`, `g.cancel`.**
   - *Recommend:* yes.
   - *Alternative names:* `scope`/`Scope` (the soundness check's suggestion), `nursery`, `group`.
   - *Removes* `concurrent g {…}`, `spawn(g) e`, `cancel(g)` and `TaskGroup`.
5. **`select(ops…)` + `match`, with `Op<T>`, `ch.receiving`, `ch.sending(v)` and `timeout(d)` (also on `spsc` ends and `mpmc`).**
   - *Recommend:* yes, with argument order as priority.
   - *Alternatives:*
     - random fair choice;
     - names such as `receive_op(ch)`/`after(d)`;
     - (5b) also an `op.then(f)` transform for labeling same-typed channels. Recommend deferring it until a program needs it.
   - *Removes* the `select { x = … => … }` grammar.
6. **Receivers as loop sources.**
   - `loop x in rx` receives until `Closed` (and stops on `Canceled`, which is level-triggered, so nothing is lost).
   - `parallel x in rx` starts an item per value as it arrives, so a server is `parallel conn in listener { serve_one(conn) }`.
   - *Recommend:* yes, as a natural extension of "any iterable source".
   - *Alternative:* explicit `receive` loops only.
7. **Task admission failure follows the allocation policy**, instead of `OutOfMemory` appearing in every spawn type as it does today.
   - *Recommend:* yes.
   - *Alternative:* keep `OutOfMemory` everywhere.
8. **Remove `parallel_map`, `parallel_range` and `parallel_update`.**
   - *Recommend:* yes.
   - *Alternative:* keep them as library conveniences.
9. **`$parallel_safe` narrows to race-freedom** (callbacks may now block).
   - *Recommend:* yes. This follows from 1.
10. **Concurrency limits as a metatag** (for example a cap on simultaneous waiting items).
    - *Recommend:* defer. The worker-pool idiom covers it until a real program wants more.
    - *Alternative:* a setting such as `$max_items = 8` on the line before a `parallel`.
11. **Kept as is, for the record:** `within`, `race`, `serve`, `pipeline`, `Unsent`/`spsc`/`mpmc` (accepted), `Mutex`/`lock_all`, `Atomic` orders, `& no blocks` and `$no_deadlocks`.
