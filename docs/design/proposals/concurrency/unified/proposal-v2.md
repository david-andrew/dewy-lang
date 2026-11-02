# One `parallel`: a unified concurrency surface for Dewy (proposal v2, 2026-11-01)

v2 folds in Grok's review (`grok-review.md`) and Sol's soundness check (`sol-check.md`). Where the reviewers disagreed with v1, §6 shows both sides.

## BLUF

- **One keyword, `parallel`, means "these items start together; the construct ends when they all end".** It has three shapes:
  - the loop `parallel x in xs {…}`;
  - the comprehension `[parallel x in xs e]`;
  - a block, `parallel { let a = f()  {…} }`, whose items are `let`s or `{…}` groups.
- **There is no separate waiting lane.** Items may wait, including on each other. The compiler picks one of three internal strategies from what the body may wait on:
  - a **chunked pool** when the body never parks;
  - a **bounded window** when it parks only on independent things;
  - **one task per item** when an item may wait on a sibling, or when the analysis can't tell.
  - Hover and `explain` show the choice. No tag is required.
- **Removed:**
  - the keywords `concurrent` and `spawn`;
  - `concurrent g {…}`, `spawn(g) e` and `cancel(g)`;
  - `parallel_map`, `parallel_range` and `parallel_update`;
  - the never-built `[concurrent …]` and `select {…}`.
- **Added (library, no grammar):**
  - `tasks(body)` with `Tasks.spawn` and `.cancel`;
  - `select(ops)` + `match`, with `ch.receiving`, `ch.sending(v)`, `timeout(d)`, `op.then(f)` and `Sent`;
  - receivers as loop sources.
- **One failure rule:** errors stay per-item values. `or_throw` in an item cancels the siblings, joins them, and leaves the enclosing function with that error.
- **Kept:** channels with `Unsent`, `spsc`, `mpmc`, `Mutex`/`lock_all`, `Atomic`, `within`, `race`, `serve`, `pipeline`, `$no_deadlocks` and `& no blocks`.

## 1. The model

- **What a reader sees is what it means.** All items are logically started at once, and any interleaving is a legal run. If two items wait on each other, that works. A genuine cycle is an algorithm bug, which the existing deadlock analysis reports.
- **Constraints are inferred and checked separately; none is written:**
  1. **Race freedom.** An item writes only places no other item touches: its `@x` element, a disjoint field, or a local nothing else uses. Shared state goes through `Atomic`, `Mutex` or channels. `Send`/`Sync` are inferred.
  2. **Waiting chooses the strategy, never legality.** The strategy is driven by *may park* (suspend until another task, a timer or the outside world acts) or *unknown*. It is not driven by the broad `blocks` bit, so non-parking I/O such as a log write stays on the pool.

     | Body | Strategy | Cost |
     |---|---|---|
     | Never parks | **Pool**: chunked, stolen, possibly inline | No task per item |
     | Parks only on independent things: network, files, timers, `within`, or a handle that no other item, and nothing waiting on the items, uses | **Window**: at most W items in flight, the next starting when one ends. W is a documented runtime default (a small multiple of the worker count) shown in hover | W tasks |
     | May wait on a sibling (shares a channel or lock with another item, polls an atomic one sets), or unknown (an opaque or foreign call, an untracked function value) | **Task per item**: every item admitted; a waiting item never waits for an unstarted one | One task per item |

  3. **Determinism.** Results come in input order. Reductions keep the sequential order unless an associative operator is proven. Timing affects only side effects through shared handles, and which failure comes first.
  4. **Structured lifetime.** Nothing outlives its construct. Work that outlives a function goes into a caller-owned `Tasks` group.
- **Strategy is visible but never required.**
  - Hover and `explain` name the strategy and the call that forced it.
  - One note appears in two cases:
    - the forcing call is not an obvious wait (`sleep`, `send`, `receive`, `lock`, `within`, `select`), for example a logging helper that turned out to wait on a lock;
    - the strategy is task-per-item and the trip count is large or unknown.
  - Nothing warns on every `parallel`. `& no blocks` pins a hot path to the pool.
- **The runtime's duties (Sol):**
  - a parked task releases its worker;
  - opaque foreign blocking gets compensating capacity, or a hard error;
  - long CPU stretches inside tasks get preemption (threads) or safepoints (M:N);
  - a target that can't park yet (wasm, before stackless lowering) gets a diagnostic, never silent serialization.
- **Placement stays separate.** A GPU is placement context, and only pool-strategy bodies are offloaded.
- **Why #118's objection no longer applies:** per-item values versus fail-fast is chosen by `or_throw`; admission is allocation; cancellation is reported where scopes end (§5). A helper that starts parking changes the cost (shown in hover), not the meaning.

## 2. Inventory

| Construct | Verdict | Why |
|---|---|---|
| `parallel` loop and comprehension | **Keep**, redefined | Matches the reader. Waiting is now legal and the strategy is inferred. Also replaces the never-built `[concurrent …]`. |
| `parallel { let a = …  {…} }` | **New shape** of the keyword | Heterogeneous fan-out with results. Replaces `concurrent {}` + `spawn`. |
| `concurrent`, `spawn`, `concurrent g`, `spawn(g)`, `cancel(g)`, `TaskGroup` | **Remove/replace** | The block form, plus `tasks`/`Tasks`/`.spawn`/`.cancel`. |
| `select {…}` grammar | **Drop** (never built) | Replaced by the `select(ops)` library function + `match`. |
| `race(@a @b)` | **Keep** | It runs whole calls and discards the losers. `select` commits exactly one operation. |
| `within(d @f)` | **Keep** | Deadline scope: its own expiry gives `Timeout`. |
| `parallel_map`/`_range`/`_update` | **Remove** | The `parallel` forms cover them. |
| `Channel`, `spsc`, `mpmc` | **Keep** | Plus the op members and iteration. `send` stays `void \| Unsent<T>` (accepted). |
| `Mutex`/`lock_all`, `Atomic`, `CachePadded`, `serve`, `pipeline`, `$no_deadlocks`, `& no blocks` | **Keep** | Unchanged; the last two are the precision opt-ins. |
| `$parallel_safe` | **Keep, narrowed** | Means race-free only, because waiting no longer disqualifies a callback. |

## 3. `select` without new syntax

```dewy
Job:type = [id:int]
Command:type = [name:string]
Quit:type = [why:string]
label_control = (r:Command | Closed) => match r {
    c:Command => c
    _ => Quit["control closed"]
}
dispatch = (jobs:Channel<Job> control:Channel<Command>) => {
    loop true {
        match select(control.receiving.then(@label_control)  jobs.receiving  timeout(100ms)) {
            c:Command => printl"command {c.name}"
            j:Job => printl"job {j.id}"
            t:Timeout => printl"idle"
            q:Quit => break                        # control closed
            c:Closed => break                      # only jobs can still give Closed
            c:Canceled => break
        }
    }
}
```

What each piece is:

- **`jobs.receiving`** is an ordinary zero-argument method, so it takes no parentheses. It returns an **operation value**, `Op<Job | Closed>`: a description of "receive from `jobs`". Making it waits for nothing, takes nothing and registers nothing.
- **`timeout(100ms)`** returns `Op<Timeout>`. It becomes ready 100 ms after `select` starts.
- **`op.then(f)`** returns a new op whose result is `f` applied to the original op's result. Here it relabels `control`'s `Closed` as `Quit`, so two channels' closes can be told apart. `f` runs after the commit, outside any internal lock.
- **`select(…)`** is a library function over any number of ops.
  - It waits until one is ready and **commits exactly one**: a losing receive takes no message, and a losing send moves no payload.
  - When several are ready, it chooses **fairly** (at random). Tests pin the order with the test runner's seed, or by passing one op.
  - Its result is the union of the ops' results plus `Canceled`, because `select` is a wait.
- **`match`** is the ordinary `match` with type patterns. There is no new arm grammar and no function literal.
- **Sending:** `out.sending(v)` gives `Op<Sent | Unsent<T>>`. `Sent` is a value, because `void` cannot be matched. The payload moves only if that op commits.
- **Limits:** only library primitives implement `Op`. Racing arbitrary calls stays `race`.

## 4. Common tasks

Every snippet declares what it uses, and none needs an annotation.

**Parallel map and reduction** (pool).

```dewy
let squares = [parallel i in [0..1000000) i*i]
let total = sum(squares)                     # sequential order, same result every run
```

**Fetching N URLs with a timeout** (window: `get` parks only on the network).

```dewy
get = (url:string) => {
    sleep(50ms) or_throw                     # stands in for a network wait
    "page at {url}"
}
fetch_all = (urls:array<string>) => [parallel url in urls get(url) or_throw]
main = () => {
    let urls = ["a.example" "b.example" "c.example"]
    let pages = within(2s @fetch_all(urls)) or_throw          # one deadline; first failure aborts
    let each = [parallel url in urls within(1s @get(url))]    # array<string | Timeout | Canceled>
    printl"{pages.length} {each.length}"
}
```

**Producer and consumer** (task per item: the items share `numbers`).

```dewy
main = () => {
    let numbers = channel<int>(16)
    let total = 0
    parallel {
        {
            loop i in [0..1000) { numbers.send(i) or_throw }
            numbers.close
        }
        { loop n in numbers { total += n } or_throw }   # Closed ends it; Canceled is forwarded
    }
    printl"{total}"                                    # 499500
}
```

**A worker pool.** A `parallel` over a receiver *is* the pool: it is windowed by default, so at most W jobs run at once.

```dewy
handle = (job:int) => {
    sleep(5ms) or_throw
    job * 2
}
main = () => {
    let jobs = channel<int>(64)
    parallel {
        {
            loop j in [0..1000) { jobs.send(j) or_throw }
            jobs.close
        }
        {
            parallel j in jobs {
                let r = handle(j) or_throw
                printl"{r}"
            } or_throw
        }
    }
}
```

- Exactly N workers is still `parallel w in [0..8) { loop j in jobs {…} or_throw }`.

**Waiting on several channels plus a timeout:** `dispatch` in §3.

**A game job system** (pool, with no task cost).

```dewy
Particle:type = [x:float64 vx:float64]
World:type = [particles:array<Particle> heat:array<float64> frames:int]
diffuse = (@heat:array<float64> dt:float64) => {
    parallel @h in heat { h *= 1.0 - dt }
}
frame = (@world:World dt:float64):>void & no blocks => {   # the row is optional: it pins the pool
    parallel {
        { parallel @p in world.particles { p.x += p.vx * dt } }
        { diffuse(@world.heat dt) }
    }
    world.frames += 1                                       # after the join
}
```

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
        start_autosave(group)    # autosave lives on in main's group
        play or_throw
        group.cancel             # tasks joins autosave, then returns normally
    }) or_throw
}
```

**Cancellation.**

```dewy
slow = (n:int) => {
    sleep(100ms) or_throw        # a cancellation point
    n
}
all_fast = () => [parallel n in [1 2 3] within(50ms @slow(n)) or_throw]
main = () => {
    let quick = within(1s @slow(1))       # 1
    let late = within(10ms @slow(2))      # Timeout: within names its own deadline
    match all_fast {
        xs:array<int> => printl"{xs}"
        t:Timeout => printl"too slow: the other items were canceled and joined"
        c:Canceled => printl"canceled from outside"
    }
}
```

## 5. Failure and cancellation: one rule set

1. **Errors are values.** An item's result is whatever its body gives. Comprehensions collect them, and nothing is canceled.
2. **`or_throw` in an item aborts the construct.**
   - The siblings are canceled. No new items or chunks start, and an in-flight chunk finishes. Every item is joined, with cleanup.
   - The error then leaves the enclosing function, exactly where it would go in a sequential `loop`.
   - Which error escapes is the **first in time**. Siblings' `Canceled` are dropped; other genuine failures are attached as causes (#80).
   - The same rule holds for `parallel` blocks, `tasks`, `race` and `select`.
3. **Every construct is a cancel scope.** Nesting propagates, and cancellation is **level-triggered**: after a cancel, every cancellation point in the scope gives `Canceled` until the scope exits.
4. **Cancellation points:**
   - **Always:** channel and queue operations, receiver loops, `sleep`, I/O, process waits, `select`, `lock_all`, and joins of window or task strategies.
   - **Never:** `lock` (decided) and console output.
   - **Pool-strategy constructs:** they check at chunk boundaries (C4). On cancel they start no new chunks and leave the enclosing function with `Canceled`. This happens only where that function's result type already carries `Canceled`; otherwise they finish, and the next wait sees the cancel.
5. **A construct adds no outcomes of its own.** Cancellation from outside is reported by the scope that owns the reason:
   - `within` gives `Timeout`;
   - `tasks` absorbs its own `.cancel`;
   - a parent's cancel stays `Canceled`, and reaching `main` it is reported like any error.
6. **Joins always happen.** Cleanup (`defer`, drop hooks) is shielded, with a grace deadline.
7. **Admission is allocation.** In ordinary code, exhaustion ends the process with a report. Under `$explicit_allocation_failure`, the construct gives `OutOfMemory`.
8. **Deadlocks** are checked by the existing analysis. `$no_deadlocks` demands certificates. Timeouts are recovery, not proofs.

## 6. Decisions for David

The C items below are ready to paste into a decision list. Each spelling is reversible until release.

**C1. Can `parallel` items wait, including on each other, with the execution strategy inferred?**
```dewy
step = (ch:Channel<int> i:int) => if i =? 0 (ch.receive or_throw) else {
    ch.send(42) or_throw
    0
}
main = () => {
    let ch = channel<int>(1)
    printl"{[parallel i in [0..2) step(ch i)]}"   # [42 0]: item 0 waits for item 1
}
```
- **v1 (Claude):** any `blocks` in the body gives one task per item, unbounded. A separate concurrency cap was deferred.
- **Grok:** that costs a stack per item, flips on harmless I/O, and drops GPU offload. Use three strategies keyed on "may park or unknown", with a default window.
- **Recommendation:** Grok's three strategies (§1), surfaced in hover and `explain`, with no required tag. A cap metatag is deferred until a program needs one; the window covers the common case.
- **Spellings:** none new. This retires "a `parallel` body must not block".

**C2. How are items written in the block form?**
```dewy
f = (n:int) => n + 1
g = (s:string) => s.length
main = () => {
    parallel {
        let a = f(1)
        let b = g("hi")
        { printl"two"  printl"lines, in order" }
    }
    printl"{a} {b}"
}
```
- **v1 (Claude):** every top-level statement is an item.
- **Grok:** then braces stop meaning "in order", and a stray statement silently becomes a racing item. Make each item a `let` or a `{…}` group, with a fix-it on a bare expression.
- **Recommendation:** Grok's rule.
  - Braces keep meaning "sequential", and items are marked visibly.
  - `let` items bind after the join; reading another item's `let` is an error naming both.
  - Wrapping everything in braces (`parallel { {a} {b} }`) would hide the `let` results inside their inner blocks.
- **Spellings:** adds the block shape. Removes the keywords `concurrent` and `spawn`.

**C3. Are failures per-item values unless `or_throw`, with `or_throw` aborting the construct?**
```dewy
check = (n:int) => if n =? 2 Timeout else n
main = () => {
    let each = [parallel n in [1 2 3] check(n)]           # [1 Timeout 3]: nothing canceled
    let all = [parallel n in [1 2 3] check(n) or_throw]   # leaves main with Timeout; siblings canceled
}
```
- **Options:** (a) per-item values unless `or_throw`; (b) always fail-fast.
- **Recommendation:** (a). The error that escapes is the first in time (both reviewers agree).
- **Spellings:** none.

**C4. Does a compute-only `parallel` stop early when canceled?**
```dewy
heavy = (xs:array<int>):>array<int> | Canceled => [parallel x in xs x*x]
main = () => {
    let xs = [parallel i in [0..1000000) i]
    let r = within(1ms @heavy(xs))          # chunks stop at the deadline: Timeout
}
```
- **Options:**
  - (a) it runs to completion (v1);
  - (b) it always stops, adding `Canceled` to every enclosing function, which is noise for every caller;
  - (c) it checks at chunk boundaries and stops only where the enclosing result type already carries `Canceled`.
- **Recommendation:** (c). Grok asked for boundary checks, and (c) keeps them without adding new outcomes. A sibling's `or_throw` always stops chunks.
- **Spellings:** none.

**C5. Should `select` be a library function over operation values, used with `match`?**
```dewy
main = () => {
    let inbox = channel<int>(1)
    let out = channel<string>(1)
    match select(inbox.receiving  out.sending("ping")  timeout(1s)) {
        n:int => printl"got {n}"
        s:Sent => printl"sent"
        u:Unsent<string> => printl"not sent: {u.reason}"
        c:Closed => printl"inbox closed"
        t:Timeout => printl"nothing within 1s"
        c:Canceled => printl"canceled"
    }
}
```
- **Tie-break, v1 (Claude):** the earliest argument wins, giving priority and deterministic tests.
- **Tie-break, Grok:** priority starves a later op that is always ready, so choose fairly.
- **Recommendation:** `select` + `match`, with a **fair** random choice. The test runner fixes the seed. When priority is needed, call `try_receive` first.
- **Spellings:** adds `select`, `Op<T>`, `.receiving`, `.sending(v)`, `timeout(d)` and `Sent` (on `Channel`, the `spsc` ends and `mpmc`). Removes the `select { x = … => … }` grammar.

**C6. Does `op.then(f)` ship now?**
- Example: `dispatch` in §3, which needs it to tell `control` closing from `jobs` closing.
- **v1 (Claude):** defer it until a program needs it.
- **Grok:** ship it now, because same-typed results and two `Closed`s are otherwise indistinguishable.
- **Recommendation:** ship it now. Without it, two channels can't both be selected safely.
- **Spellings:** adds `.then` on `Op`.

**C7. Can receivers be loop sources, and what do those loops give?**
```dewy
main = () => {
    let numbers = channel<int>(4)
    let total = 0
    parallel {
        {
            loop i in [0..10) { numbers.send(i) or_throw }
            numbers.close
        }
        { loop n in numbers { total += n } or_throw }
        # parallel n in numbers { … } would start one item per value, windowed
    }
    printl"{total}"
}
```
- **v1 (Claude):** `loop x in rx` stops on `Canceled` with nothing to show for it, and `parallel x in rx` is uncapped.
- **Grok:** that reports success after a partial consume, and an uncapped accept loop has no bound.
- **Recommendation:** Grok's version.
  - `loop x in rx` gives `void` at `Closed` and `Canceled` on cancel.
  - `parallel x in rx` is windowed.
- **Spellings:** adds iteration over receivers, and a receiver loop's value (`void | Canceled`).

**C8. Do long-lived groups move to the library: `tasks(body)`, `Tasks`, `g.spawn(@f(x))`, `g.cancel`?**
- Example: autosave in §4.
- **Options:** keep `concurrent g {…}` + `spawn(g)`; use other names (`scope`, `nursery`).
- **Recommendation:** `tasks`. Both reviewers agree.
- **Spellings:** adds `tasks`, `Tasks`, `.spawn` and `.cancel`. Removes `concurrent g`, `spawn(g)`, `cancel(g)` and `TaskGroup`.

**C9. Does task admission failure follow the allocation policy?**
```dewy
work = (n:int) => n * 2
let doubled = [parallel n in [1 2 3] work(n)]   # no OutOfMemory in the type
```
- **Options:** (a) the allocation policy: the process ends, or `OutOfMemory` under `$explicit_allocation_failure`; (b) `OutOfMemory` in every spawn's type, as today.
- **Recommendation:** (a).
- **Spellings:** none.

**C10. Should `parallel_map`, `parallel_range` and `parallel_update` be removed?**
```dewy
let sums = [parallel row in [[3 1] [4 2]] sum(row)]   # was parallel_map
```
- **Recommendation:** remove them, since the `parallel` forms cover them.
- **Spellings:** removes the three functions.

**C11. Should `$parallel_safe` mean race-free only?**
```dewy
$parallel_safe
apply_all = (xs:array<int> f:(x:int):>int) => [parallel x in xs f(x)]
```
- **Recommendation:** yes. Waiting no longer disqualifies a callback; its cost shows in hover, and `& no blocks` locks it out.
- **Spellings:** none.
