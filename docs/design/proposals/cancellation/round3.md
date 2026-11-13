# Cancellation, round 3: `Canceled` only where something can cancel, and kept where it was made

This round replaces round 2's rules; rounds 1 and 2 stay as written. §5 says how each finding of `review-round2.md`, `soundness-round2.md`, `regrade-round2.md` and the round 2 cold read is resolved.

## 1. Verdict

David's rule stands, inferred like waiting: a result has `Canceled` only where something can cancel the work.

Round 2 made `Canceled` "control, not data". The soundness check shows the blanket ban doesn't buy what round 2 claimed:

- One compiled body still fails. A wait's result that is handled locally still changes ordinary types between contexts.
- The ban also rejects the commonest shapes of real code.

Round 3 replaces it with the smaller rule the soundness check describes, *confinement*:

> **`Canceled` is an ordinary failure inside the work it belongs to.** Store it in local lists and records, log it, pass it to helpers, catch it with `e:exception`. Two things are ruled out:
> - making one;
> - putting a value that may hold one somewhere that outlives that work (an outer variable written from a `parallel` item, a mutex, an atomic, a channel, a global, an error's field).
>
> The work's boundary publishes nothing that work produced after it was canceled, except its failures, with the `Canceled` removed.

Everything else follows:

- There is one kind of `Canceled`, always the current work's own.
- Boundaries recognize it by a flag, with no origin tracking.
- Types are per context: each function gets two typed instances, as David's "compiled once per context" said. Machine code is shared wherever the two lower alike, and duplicated only where a type argument, a local layout or type inspection differs.

Other changes:

- `Task.wait()` is an ordinary wait again.
- `protect_from_cancel`'s limit starts when cancellation does.
- A loser's failed rollback is never discarded.

**Pairing each input with its result is now ordinary code** (round 2: an error)

```dewy
let results = [parallel u in urls [url=u page=http.get_text(u)]]
# inside an item: page may be Canceled (a local record: fine)
# after the join: array<[url:string page:string | HttpError]>
```

**Logging and catch-alls are ordinary code** (round 2: errors)

```dewy
let r = net.ping(host)               # Duration | NetError | Canceled, in an item
report(host r)                       # fine: it stays in this item's work
failures.lock.push(r)                # error: failures is shared beyond this item; handle Canceled first
```

**"Finish the current job" now means what it says** (round 2: every job was capped at 30 s)

```dewy
check_cancel() or_throw                              # stop between jobs
protect_from_cancel(30s @run_job(file)) or_throw     # up to 30 s once canceled; no limit before
```

**Waiting for a task with a deadline doesn't stop it** (round 2: it did)

```dewy
match within(2s @indexer.wait) {
    <Timeout> => printl"still indexing; carrying on"   # the indexer keeps running
    _ => printl"index ready"
}
```

## 2. The rules

### 2.1 The request, waits, joins and protection

1. **The request.** Every task has a cancel request: a channel with no payload that only its group can close. Once closed it stays closed.
   - A handle to it is reference-counted.
   - Once the task ends, the request reads as closed. For another task holding it, "closed" means the holder was canceled *or* has ended. The `CancelRequest` documentation says so (review N2).
2. **Standard waits.** A standard wait returns `Canceled` when the current request closes, and its own request has priority. The standard waits are:
   - channel, `mpmc` and `spsc` `send`, `receive` and `reserve`;
   - `sleep`, and ticker and signal `next`;
   - file, stdin, process and network I/O;
   - `lock_all`;
   - `select`;
   - `Task.wait()`;
   - a `receive` on a request.

   `check_cancel()` is a checkpoint. `try_send` and `try_receive` never wait, so they are not cancellation points (§4 Q8): code that relied on them as its only checkpoint adds `check_cancel()`.
3. **Group joins.** A group join is one of: the end of `race`, `first_ok`, `within`, a `parallel` block, loop or comprehension, or `task.tasks`. When the joiner's request closes, the join closes its children's requests, drains (it waits for every child and its cleanup), then publishes per §2.4. A join never returns while a child runs.
4. **`Task.wait()` is not a join** (review MF1). The waited task isn't the waiter's child.
   - A canceled waiter stops waiting at once and gets its own `Canceled`. The task keeps running.
   - `.wait()` never reports the waited task's own `Canceled`, whoever caused it: the task's own group, a `stop()`, or program end. It gives `void | E`, where `E` is the task's other failures, cleanup included.
   - `.running` reads one instant. The task may still finish between that read and a `stop()`.
5. **`protect_from_cancel(limit @body)`** runs `body` on a fresh request that its parent's cancellation never closes (soundness R3).
   - The limit starts when the parent's request closes, or at entry if it is already closed (review MF2). With no cancellation, the body runs as long as it needs. A deadline counted from entry is spelled `within`.
   - When the limit passes, the body's request closes. The result is then `Timeout`, together with the body's other failures.
   - Otherwise the result is the body's own, and no `Canceled` is invented after it: the parent's closed request is seen at the next wait.
   - A protection nested inside another can't outlast the outer one's effective deadline.
6. **Cleanup** (drop hooks and `defer`) runs as `protect_from_cancel` with the grace limit: 100 ms by default, or the acquisition's `timeout=`.
   - The grace starts only once the owning task's request has closed. In a task nothing can cancel, cleanup has no deadline.
   - Grace running out gives the owning task's own `Canceled`, since its request is closed by then, not `Timeout` (soundness R1). The cleanup was cut short because its task was canceled, and the boundary that canceled the task consumes it like any other `Canceled`. A cleanup failure that really happened (`FileCloseFailed`) is kept beside it.
7. **Who closes a request.** A group closes the requests of its unfinished children in these cases:
   - `race` has its first complete result, or `first_ok` its first complete success. "Complete" means the work's own cleanup has finished, so a result that its cleanup turns into a failure is a failure (soundness S3).
   - A `within` deadline passes.
   - A `parallel` item's `or_throw` or `return` leaves the function, or its `break` or `continue` leaves an enclosing loop.
   - In `task.tasks`, a child fails, or the body fails or leaves by `or_throw`. A normal return of the body joins the children without canceling them.
   - An owning group's essential work is done: this ends its marked work (§2.7).
   - `task.stop()` closes one task's request. `BackgroundTasks` closes all of its tasks' requests at program end.
   - The group's own request closes, and the close passes down.
   - A spawn into a group whose request has already closed starts with its request closed (soundness N3).
   - Nothing closes the entry task's request.
8. **A canceled child doesn't necessarily return `Canceled`.** It may handle the cancellation and return a value or another failure, or compute until its next checkpoint.

### 2.2 Confinement (Q2)

- **The definition.** A *work* is what runs under one request: a group child or a protected or cleanup body, with everything it calls synchronously, until it returns to its boundary. A value *may hold `Canceled`* if its type may contain it anywhere:
  - as an alternative, a facet of a combination, or an element of an error stack;
  - in a field or element;
  - through a captured binding;
  - through a broad family (`exception`, `any`), or a type argument bound to one of these.

  That summary is structural and memoized per type, as `Send` is (soundness S1).
- **The rules.**
  1. **No constructor.** Only the runtime makes `Canceled`, and only for the work whose request closed. `return Canceled` is an error; bind and forward the one you have.
  2. **No publication outside the work.** A value that may hold `Canceled` can't be written into a place that outlives the work or is shared with other work:
     - a variable of an enclosing function, written from a `parallel` item;
     - a place reached through a `Mutex`, an `Atomic`, a channel or another shared handle;
     - a global;
     - a place a closure captured with `$capture @`;
     - a place borrowed in through an `@` parameter, unless the caller's place belongs to the same work.

     Sending one is already an error, because channel payloads that may be exceptions are rejected.
  3. **No `Canceled` inside an error's own fields.** `Wrapped[cause=r]` is an error when `r` may hold `Canceled`. Combine instead (`r and Wrapped[...]`), so the cancellation stays a facet that boundaries can see.
- **What is allowed.** Everything else is ordinary:
  - local bindings, records, arrays and collectors;
  - arguments, interpolation and logging;
  - catch-all arms;
  - generic type arguments, type inspection;
  - returning, including in one of several result values;
  - local captures;
  - written annotations of locals and parameters, `Canceled & …` included.

  An item may *read* the enclosing function's locals (review S4). Reading publishes nothing, and an item sees `Canceled` only when its own request closed.
- **Boundaries publish nothing a canceled work produced, except its failures.**
  - A work whose request closed doesn't publish its success value, whatever is inside it, fields and captures included. Its failure value is published with the `Canceled` component removed: consumed, translated to `Timeout`, or propagated, per §2.4.
  - A work whose request didn't close can't hold `Canceled` at all, because `Canceled` is made only when a request closes, and inner boundaries normalize their own.
  - Together with rules 1–3, this is the containment theorem (§2.4).
- **Representation** (soundness R2). Ambient cancellation is a flag on a failure value, not an element.
  - `&`, error stacks and automatic cleanup combination merge the flags: `Canceled & Canceled` is `Canceled`. It describes the work's one request, so a repeat isn't a second failure, and batch 10's "two of one type need the stack" doesn't apply to it.
  - Automatic cleanup appends only ordinary failures beside the flag.
  - `is? Canceled`, `<Canceled>` arms and `as Canceled` read the flag.
  - A boundary clears the flag, then publishes the residual, or nothing if nothing is left.
  - `as error` and `as ~Canceled` give the residual. Neither may hold `Canceled`, so the residual can be stored anywhere.
- **Foreign callbacks** (soundness S4). An `$export` callback with a fixed foreign signature can't pass on `Canceled`, because no foreign return slot can carry it. Where its cancellable instance could, it is an error unless it handles the cancellation. Foreign entry points are registered as roots, with an explicit context.

**Why confinement and not round 2's ban.** Each restriction has to earn its keep against "`Canceled` is an ordinary error".

- **No constructor.** It means a group can drop every `Canceled` it sees as its own. Zig says it is usually a bug to ignore `error.Canceled` (std.Io, `Future.cancel`). Dewy lets only the group that asked for the cancellation consume it, and nobody can make one for it.
- **No publication outside the work.** Without it, a `Canceled` reaches code whose request never closed. That needs a second kind of `Canceled`, or origin tracking on every value, which both checks rejected in round 1.
- **No `Canceled` in an error's fields.** Without it, a boundary would have to search inside a failure's fields to remove the cancellation. Combining with `and` already says "both".

Nothing else is needed for soundness, so nothing else is banned. Under the patterns the review counted, confinement leaves almost everything legal:

| Pattern | Round 2's ban | Confinement |
|---|---|---|
| `[parallel u in urls [url=u page=fetch(u)]]` | error in every element | fine (program 14) |
| `[loop u in urls fetch(u)]` inside an item | error | fine (program 15) |
| `xs.map(@fetch)`; a helper storing a callback's result in its own locals | error inside the library's body | fine (program 16) |
| a helper storing results in a shared cache | error | error at the store, naming the cancellable call (program 16): `or_throw` before storing |
| `log(r)`, `printl"{r}"`, `e:exception => report(e)` | error | fine (program 17) |
| `identity(sleep(0ns))` | error | fine; `identity` gets a second body (program 18) |
| `status = fetch_status()` from an item into `main`'s variable | error | error (§1's second example) |

### 2.3 Contexts and the inference

- **Cancellable code** (syntactic): the items of `race`, `first_ok` and `within`; every `parallel` item; the body of `task.tasks` and every spawned task; protected bodies; cleanup of a cancellable task; the REPL's input; and everything those call. Every `parallel` item counts (agreed with David). Hover notes "nothing in this block can cancel it now".
- **Context cancellation is an inferred effect (Q1).** It appears as `| Canceled` only in cancellable results. Written result types never mention it, and writing it is an error with a fix-it.
  - A written function type permits the effect by default. A call through one adds `| Canceled` at a cancellable call site.
  - `& no blocks` excludes the effect, with `check_cancel` counting as blocking. That over-excludes a callback that waits but handles its own cancellation; a precise row member for that would be new syntax, and isn't proposed (review S5).
- **Two typed instances per demanded specialization.**
  - The non-cancellable instance is typed from its own body. It is not derived by deleting `Canceled` from the other: a handled-`Canceled` branch is dead there, and its type drops out.
  - A written function type is a contract for both: the implementation conforms if its non-cancellable result fits it, and its cancellable result fits it plus the effect.
  - A handle points to a descriptor holding both entries, which are the same entry when the bodies are shared. A call in context *q* uses entry *q*.
  - An array of handles to several functions takes each entry's result pointwise.
- **The fixed point.** Unchanged from round 2 §2.3: (specialization, context) reachability over the resolved call graph, at O(|B| + |E|). Round 3 adds three summaries, each solved monotonically per instance with memoized type summaries:
  - the structural *may-hold-`Canceled`* summary;
  - for each by-place parameter and captured place, "writes a value that may hold `Canceled`";
  - the existing result fixpoint.

  Cost scales with the abstract lattice height and each body's control-flow work, not only with the edge count (soundness N5). Incremental edits invalidate both ways, callees and callers.
- **`select`, `within` in `race`, libraries, recursion and the REPL** are as in round 2.

### 2.4 Boundaries: what each publishes

**Containment theorem.** A value holding `Canceled` exists only inside a work whose request closed:

- it is made only there (rule 1);
- it can't be published outside it (rules 2 and 3);
- that work's boundary publishes only its failure residual (§2.2).

So no `Canceled` reaches code whose request is open, and nothing that holds one reaches `main`.

| Boundary | Work canceled by this boundary | Work canceled from above | Work not canceled |
|---|---|---|---|
| `race`, `first_ok` | losers' results discarded whole, except abandon failures (Q6) | drains; the join gives the enclosing work's `Canceled`, combined with any kept failures | the winner's complete result; `first_ok`'s first failure if all fail |
| `within` | `Timeout`, with the child's other failures kept (`Timeout & FileCloseFailed`); a success value is not published | drains, then `Canceled` with the kept failures; the parent wins a tie | the child's result |
| `protect_from_cancel` | `Timeout` with the kept failures, as `within` | not closed by the parent (§2.1.5) | the body's result |
| cleanup | n/a | grace expiry gives the task's own `Canceled`, plus real cleanup failures | the hook's result |
| `parallel`, leaving early | siblings' `Canceled` consumed, their cleanup failures kept beside the exit (`X & FlushError`); a `return v` becomes the cleanup failure (D40 Q1) | items see `Canceled`; bindings keep it where the enclosing work is cancellable | per item, C3 |
| `parallel`, essential work done | marked items' `Canceled` consumed, including one their `or_throw` forwards; their other failures still go wherever their `or_throw` or `;` sends them (soundness S3) | as above | |
| comprehension | only on early exit (no array) | drains, then `Canceled` for the whole expression | each element's value, with no `Canceled` in it: the element type is narrowed as a static view, since the reserved tag is never set |
| `task.tasks` | stopped children's `Canceled` consumed; the failure returned | drains, then `Canceled` | children's failures fail the group |
| `Task.wait()` | never reports the task's own `Canceled` | the waiter's own `Canceled`; the task keeps running | the task's failures |

- **Narrowing after a block where nothing can cancel the enclosing work.** Its request never closes, marked items can't bind outward names, and signal closure gives `Closed<E>`. So an item binding read after the block holds no `Canceled`, and its type is narrowed.

### 2.5 The three levels, and the request in data (Q4)

1. **Standard waits** make code cancellable on their own.
2. **`check_cancel()`** is the checkpoint for CPU loops. It warns where nothing can cancel.
3. **A request passed to another task.** `task.cancel_request` is the current work's request, of type `task.CancelRequest`: a receive-only end whose `receive` gives the existing `Closed<task.CancelRequest>` when it closes.
   - Receiving on your own request gives your own `Canceled` (priority), so the `Closed` always means *someone else's* request.
   - Cold readers read the two arms correctly in outline, but only 1 of 3 said why they differ. The hover now says it on each arm (program 08), as do the type's docs:
     - on `<Closed<task.CancelRequest>>`: "the caller's cancel request closed: the caller was canceled or has ended. This worker keeps running. Its own cancellation is the `<Canceled>` arm."
     - on `<Canceled>`: "this worker's own request closed: its group is stopping it."
   - Program 08 calls `check_cancel()` before its poll, so the worker's own cancellation isn't mistaken for "the caller is still here" (review S7).

### 2.6 Cleanup

As §2.1.6: shielded always, with grace only once the task is canceled, and grace expiry gives the task's `Canceled`. The shield's justification is round 2's (a closed request stays closed). That cleanup is `protect_from_cancel` with the grace limit is now true word for word, since protection's limit also starts at cancellation.

### 2.7 Incidental work (Q3)

- **The trigger.** An owning group (a `parallel` block, or `task.tasks` once its body has returned) has its essential work done when everything unfinished is one of:
  - parked in signal-only waits (batch 9, unchanged);
  - a marked item or marked spawned task.

  The trigger is a latched transition, checked in this order: publish ready dependents, test the condition, close the signal views once, close the marked work's requests once. It never reopens (soundness S2).
- **What it does:**
  - unmarked listeners get batch 9's behaviour unchanged: pending notifications drain, then `Closed<E>`, and code after the loop runs normally;
  - marked work is canceled.
- **Where the marker goes.** `$until_others_finish` prefixes a `parallel` item, or a `group.spawn(...)` statement inside `task.tasks` (review S3; program 19), and nothing else.
  - A marked item can't bind names read outside it.
  - In every mode, a marked item or task holding a lock across a wait is an error (review S2: today only `$no_deadlocks` checks it). Otherwise an essential item blocked on that lock, which isn't a wait, would keep the group alive forever.
  - Dependencies through channels or shared services aren't checked. A marked producer that essential work still needs is a design error the compiler can't see, and the docs say so.
- **A marked signal listener** opts into cancellation, which has priority. It may lose a pending notification, and its tail runs canceled (soundness S2). Unmarked listeners are batch 9's.
- **Diagnostics**, as in round 2:
  - every item marked: error;
  - a block of only listeners: warning;
  - an item that ends only when canceled, in a block where nothing cancels it: "this block never ends … mark it `$until_others_finish`?";
  - `break` out of a `signals.ctrl_c` loop while other work continues: warning.

### 2.8 Ctrl-C and signals

- **No handler:** the OS default.
- **A handler:** `loop _ in signals.ctrl_c { …; return }`.
- **`.observe`** never cancels.
- **The three-press forced exit goes.** A program that intercepts Ctrl-C owns it. Ctrl-\ or Ctrl-Break still ends a stuck program.
- **A second SIGTERM during a drain** is intercepted while the listener's block lives (batch 9). The escalation is SIGKILL, as with most daemons (review N3).

### 2.9 Zig

Checked against Zig's `lib/std/Io.zig` on Codeberg master, read 2026-11-13.

- **Delivery.** `Future.cancel` says: "After cancelation of a task is requested, only the next cancelation point in that task will return `error.Canceled`: future points will not re-signal the cancelation." It adds that "it is usually a bug to ignore `error.Canceled`".
  - `recancel` "re-arms the cancelation request, so that `error.Canceled` will be returned again from the next cancelation point".
  - proposal-v3 §5 lists two open Zig issues from that design: #31340, dropped acknowledged cancelations, and #35564, `Condition.wait` swallowing `Canceled`. Their numbers weren't re-checked this round.
  - Dewy's closed request stays closed, so a swallowed `Canceled` is reported again at the next wait.
- **Consumption.** `Group.async` says a "function returning `error.Canceled` does nothing because it is an cancelation propagation boundary". That is Dewy's "the boundary that canceled the work consumes its `Canceled`".
- **The request travels implicitly.** Zig carries the request inside its `io` value, which travels with execution for all I/O. Dewy infers waiting and has no `io`, so the request travels with the task.
- **A withdrawn quote.** The sentence "only the logic that made the cancelation request can soundly ignore error.Canceled", quoted in round 2, is not in `Io.zig`.

### 2.10 One body or two

The two typed instances share one machine body when they lower alike. That holds when they differ only in the top-level result tag: the result convention reserves the `Canceled` flag, and a non-cancellable caller ignores it.

| Two bodies are needed when the context changes… | Example |
|---|---|
| a type argument | `identity(sleep(0ns))`: `T` is `void` or `void \| Canceled` (program 18) |
| a local aggregate's layout | `[url=u page=fetch(u)]` built in a function reached from both contexts |
| type inspection | `members(T \| string)` over such a `T` (program 18) |

Dead branches that handle `Canceled` in the non-cancellable instance can still be shared.

- **Warning.** Only under the existing `$no_hidden_costs` strict lane, naming the function and the call sites in each context.
- **Cost.** The size of each duplicated body. In the 20 programs, two tiny generics are duplicated (`identity`, `count_alternatives`). `explain` lists them.
- **Run time:**
  - a non-cancellable wait compares one pointer with the root's sentinel;
  - a handle call costs one indirection through its descriptor;
  - no other conversion is needed, since a narrowed view reads the same layout.

  This is a design estimate, not a measurement. It has to be measured on the flagship panel, with the extra summaries, before landing.

## 3. Knock-on edits

Round 2's list stands, with these changes.

**D41**
- *Q2*: `protect_from_cancel(limit @work)`: "the limit starts when the caller is canceled, or at entry if it already was; a deadline from entry is `within`". The example is unchanged.
- *Q3*: add "`$until_others_finish group.spawn(…)` marks a task that the group cancels once only marked tasks remain".

**D42**
- *Q1*: amend the list of actions that may make a part disappear. Add "the losers of `race` and `first_ok`, and `first_ok`'s earlier failures, whose whole results are discarded; abandon failures excepted (cancellation round 3, Q6)". Under Q7's strict tag these actions no longer count.
- *Q3*: `$explicit_cancellation` keeps only its handler meaning: in cancellable code, a handler that can consume `Canceled` must name it. The discard check moves to Q7's tag.
- *Q4*: round 2's rewrite of `wrap` is withdrawn. Passing a combination that holds `Canceled` to a helper is allowed again, so `wrap` stands as written.
- *Q7*: as round 2. Additionally, `Canceled` can't reach `main`, so its exit code never applies.

**LANGUAGE.md**
- Errors as values: §2.2's three rules, in place of round 2's ban.
- 3633: as round 2.
- `protect_from_cancel` (in the cancellation paragraph, 3656–3659): the limit starts at cancellation.
- Channels: a canceled send gives `Canceled`, and its payload is dropped before `send` returns; a drop failure is combined with the `Canceled`. A `Reserved` permit stays valid until it sends or is dropped (soundness S3).
- 3997: `try_*` aren't cancellation points.
- FFI: §2.2's callback rule.

**Library and proposals**
- `signals.dewy` as round 2.
- v5's `.wait()` paragraph: §2.1.4.
- v5's protection contract: §2.1.5.

## 4. Questions for David

20 programs are dogfooded (`dogfood-round3.md`); the lowest grade is 3. `$until_others_finish` and `task.cancel_request` passed the cold read. The Q7 names, and a re-read of the arm-pair hover, are in `names-r3.txt`.

### Q1 (a). Cancellation is an inferred effect, never written in a result type

```dewy
transfer = (src:Mutex<int64> dst:Mutex<int64> amount:int64):>void | DuplicateLock => {
    let [a b] = @(lock_all(src dst)) or_throw   # in a parallel item: also | Canceled
    …
}
```

- **Rec:** yes, as in round 2. Reversible before release.

### Q2 (a). `Canceled` is ordinary inside its work, and stays there

**What you give up.** Two things:

- You can't create a `Canceled` yourself.
- A value that may hold one can't be written anywhere that outlives the work that was canceled: an outer variable from a `parallel` item, a mutex, an atomic, a channel, a global, or an error's own field.

Everything else works as for any error: local lists and records, logging and printing, helpers and generics, catch-all arms, and `??` and `or_throw`, which stay uniform, as you said.

```dewy
let results = [parallel u in urls [url=u page=http.get_text(u)]]   # fine
let r = net.ping(host)
report(host r)                         # fine
failures.lock.push(r)                  # error: shared beyond this item; write r or_throw first
return Canceled                        # error: only the runtime makes one
```

Should `Canceled` be confined to its work like this?

- **What it buys:** one kind of `Canceled`, always the current work's own, consumed by the group that caused it, with no tracking on values.
- **What it changes:** D42 Q3's "storing `Canceled` in a collection isn't consuming it" stays true inside the work. Stores that outlive it become errors.
- **The alternative:** keeping `Canceled` storable anywhere. Then a stored one must survive every group, two kinds of `Canceled` come back, and `main`'s types can mention it.
- **Rec:** yes. Reversible before release.

### Q3 (b). `$until_others_finish` on a `parallel` item or a spawned task

```dewy
parallel (
    $until_others_finish spin("counting")
    let n = count_lines(p"big.txt")
)
task.tasks((group:Tasks) => {
    $until_others_finish group.spawn(@report_stats(open))
    …
})
```

Should marked work not keep its group alive, and be canceled by the trigger that closes batch 9's signal views?

- The name was read correctly cold (3/3; 4/4/4, and 3/4/3 in context).
- **Rec:** yes. Reversible: the spelling, freely; the rule, before release.

### Q4 (c). The request handed to another task

```dewy
jobs.send(Job[path reply task.cancel_request]) or_throw
<Closed<task.CancelRequest>> => codec.abort()      # hover: the caller was canceled or has ended
```

- **Rec:** `task.cancel_request` and `task.CancelRequest`, both passed cold. The hover lines on the two arms are re-read in `names-r3.txt`.
- **Reversible.**

### Q5 (a). Iterating any source ends at cancellation

```dewy
loop job in jobs { process(job) }        # canceled: ends
loop job in jobs or_throw { … }          # canceled: leaves with Canceled
```

- **Rec:** yes, as round 2: it unifies with batch 9's signal iteration, and the hover names the group. Reversible before release.

### Q6 (a). `race` and `first_ok` discard losers' results, but never a failed undo

```dewy
let ip = first_ok(@dns.lookup(host via="1.1.1.1") @dns.lookup(host via="8.8.8.8"))
# Ip | DnsError: the slower lookup's failed socket close goes with its result
```

Should `race` and `first_ok` discard whole results? That covers losers' results, and `first_ok`'s failures before its success, ordinary cleanup failures included. The program declined those answers, and D42 Q1 would name these two actions as consuming them.

The exception is an *abandon* failure: a `$__abandon__` hook that couldn't undo (`RollbackFailed`, `ProcessStopFailed`, an abandoned temporary file's `FileRemoveFailed`). That means the work's effects may persist. A `race` or `first_ok` whose work can give one is a compile error until the work handles it itself (program 11's `left:FileRemoveFailed` arm).

- **Rec:** yes. This is stricter than letting such a failure replace the winner. Replacing it would bring back round 1's ambiguous winner-or-loser arms, and the error is static and has a fix-it.
- Hover on the call lists what is discarded. There is no debug-build logging, which removes round 2's only build-dependent behaviour (review N4).
- **Reversible** before release.

### Q7 (c). The strict tag that forbids discarding any failure

```dewy
$keep_all_failures                     # candidate name, in $bulletproof
first_ok(@backup_to(a data) @backup_to(b data))   # error unless backup_to handles its own failures
```

Under the tag, `race` and `first_ok` no longer count as consuming actions for failures. Every failure a loser can give must be handled inside its work. The fix-it is program 11's shape, which the program can write. The check depends on what the group can discard, so it applies in non-cancellable code too (soundness S3).

- **Rec:** a separate tag in `$bulletproof`. Candidates for the cold read: `$keep_all_failures`, `$no_discarded_failures`, `$explicit_discards`.
- **Reversible.**

### Q8 (a). Changes to documented behaviour, taken together

| Change | Example | Against |
|---|---|---|
| `select` gives `Canceled` only in cancellable code | `select(@a.receive)` in `main`: `int \| Closed<int>` | batch 7 |
| A canceled send gives `Canceled`; its payload is dropped before `send` returns; `reserve` keeps a payload | `out.send(conn)` canceled: `conn` closes | LANGUAGE.md channels |
| `try_send` and `try_receive` aren't cancellation points | `q.try_receive` gives `Empty`, never `Canceled` | LANGUAGE.md 3997 |
| `Task.wait()` is an ordinary wait and never reports the task's own `Canceled` | `within(2s @indexer.wait)` leaves the indexer running | v5 |
| `protect_from_cancel`'s limit starts at cancellation | `protect_from_cancel(30s @run_job(f))`: no limit until a stop | v5, D41 Q2 |
| Cleanup grace starts at cancellation, and its expiry gives `Canceled` | a slow final flush in `main` completes | LANGUAGE.md 3656–3659, round 1 |
| The three-press forced exit goes | the REPL survives repeated Ctrl-C | LANGUAGE.md 3831 |
| A marked item's `or_throw` of its block's `Canceled` ends only the item, and forwards its other failures | `$until_others_finish { sleep(1s) or_throw }` | C3 (otherwise unchanged) |
| D42 Q2's warning becomes the `select` progress rule's error where the wait is visible | `jobs.receive ?? continue` in a loop | D42 Q2 |
| Unhandled Ctrl-C: OS default; `.observe` never cancels | §2.8 | batch 9 (your preference) |

- **Rec:** accept all. Each is reversible before release.

## 5. Resolution of every finding

**`review-round2.md`**

| Finding | Resolution |
|---|---|
| MF1: `Task.wait()` as a join stops the task; foreign `Canceled` through `.wait()` | `.wait()` is an ordinary wait. It never reports the task's own `Canceled`, whoever caused it (§2.1.4; program 20). |
| MF2: protection's limit counts from entry | It counts from cancellation (§2.1.5). Program 12 is correct as written. |
| MF3: Q2's cost untested | Confinement replaces the ban. Programs 14–18 exercise every pattern in the review's table, and the shared-cache store is the only error (§2.2 table). The error is reported at the store, naming the cancellable call. |
| Part 3: the item-result relaxation | Subsumed: confinement allows every local aggregate, and joins narrow element types (§2.4). |
| Part 3: Q6 amendments | D42 Q1's list amended (§3). Abandon failures are never discarded (Q6). The strict check has its own tag, and program 11's fix-it applies (Q7). |
| S1: Q2's framing | Q2 opens with what is given up, and quotes "uniform under `??`/`or_throw`" as kept. |
| S2: lock across a wait, default mode | Now an error for marked work in every mode (§2.7). |
| S3: spawned helpers can't be marked | `$until_others_finish group.spawn(…)`. `task.tasks` is an owning group once its body returns (§2.7; program 19). |
| S4: multiple results; items reading enclosing locals | Both allowed: returning any value is fine, and reads publish nothing (§2.2). |
| S5: `& no blocks` over-excludes | Noted (§2.3). |
| S6: D42 Q2 replacement strength | Listed (Q8). |
| S7: program 08's poll | `check_cancel()` comes before the poll (§2.5). |
| N1: Zig citations | Verified against `Io.zig`. The unfound quote is withdrawn; the issue numbers are marked unchecked (§2.9). |
| N2: closed covers "ended" too | Said in the docs and the hover (§2.1.1, §2.5). |
| N3: second SIGTERM | Stated (§2.8). |
| N4: debug-only logging | Removed (Q6). |
| N5: soundness specimens | `identity(sleep(0ns))` is legal again, with a second body (program 18). |
| N6: program 03's `race` | Now `first_ok`. |

**`soundness-round2.md`**

| Finding | Resolution |
|---|---|
| R1: cleanup `Timeout` changes contextual types | Grace expiry gives the task's `Canceled`. Types are contextual anyway: two typed instances, with bodies shared only where they lower alike (§2.3, §2.10). "One body, no exceptions" is withdrawn. |
| R2: `Canceled` inside stacks and combinations | It is a flag on failure values, idempotent and merged by `&`, stacks and automatic cleanup. Boundaries clear it and publish the residual; no `Canceled` is allowed inside error fields (§2.2). |
| R3: the join rule cancels protected work | Protection is separate from joins: the parent's cancellation never closes its body, and its limit starts at cancellation (§2.1.5). |
| S1: a structural definition, families, selectors | The may-hold summary is structural over families and type arguments. Patterns, selectors and projections may name `Canceled`; `as error` and `as ~Canceled` give storable residuals (§2.2). |
| S2: marked listeners | Latched transition; a marked listener opts into cancellation (§2.7). |
| S3: Q6 and Q8 obligations | Winners chosen at complete results; the strict check is context-independent (Q7). Send drop timing and permit lifetime (§3); `.running` narrowed; the marked `or_throw` forwards other failures. |
| S4: foreign callbacks | Rule added (§2.2). |
| N3: `task.tasks` normalization and late spawns | Stated (§2.1.7, §2.4). |
| N4: the smaller sound restriction | Adopted as confinement (§2.2). |
| N5: cost scope | Stated (§2.3, §2.10). |

**`regrade-round2.md`**

| Program, axis | Resolution |
|---|---|
| 12 obvious, safe and complete (3) | Correct under §2.1.5: no cap without a stop, and 30 s after one. |
| 03 safe (4) | `first_ok` for DNS. |
| 11 complete (4: the fix-it isn't actionable) | The fix-it applies: the item matches its own `FileRemoveFailed`. |

**Cold read, round 2:** the arm pair now carries hover and doc lines (§2.5), to be re-read (`names-r3.txt`).

## Correction (after round 3)

The Zig quote withdrawn in §2.9 is real. It comes from the Zig 0.16.0 release notes (https://ziglang.org/download/0.16.0/release-notes.html, section "Cancelation"), not from `Io.zig`, which is why it wasn't found there:

- **The rule:** "Only the logic that made the cancelation request can soundly ignore an error.Canceled." It supports §2.2's "no constructor" rule and §2.4's "the boundary that canceled the work consumes its `Canceled`".
- **Its neighbouring sentences:**
  - "When cancelation is requested, the request may or may not be acknowledged."
  - "Acknowledged cancelation requests cause I/O operations to return error.Canceled."
  - `recancel` "rearms the cancelation request, so that the next check will have a chance to detect and acknowledge the request."
