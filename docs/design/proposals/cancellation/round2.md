# Cancellation, round 2: `Canceled` only where something can cancel, and only as control

This round replaces round 1's rules; round 1 stays as written. Three checks ran on round 1: the review, the regrade and the soundness check. §5 says how each finding is resolved.

## 1. Verdict

David's rule stands. A result has `Canceled` in it only where something can cancel the work, and the compiler infers where that is, the way it infers waiting.

Round 1 was unsound at the edges: one name covered two kinds of `Canceled`, the one shared compiled body broke type-dependent code, and incidental shutdown broke two proofs. Round 2 fixes those with one rule instead of new machinery:

> **`Canceled` is control, not data.** The runtime alone makes it, and only for the task whose request closed. Code may test it, match it, combine it, default it, or forward it with `or_throw` or `return`. It can't be stored, collected, captured, sent, passed as an argument, or written in a type.

Everything else follows from that rule:

- There is one kind of `Canceled`. It is always the current task's own.
- A group recognizes its own cancellation from its own state, so there is no origin tracking.
- One compiled body is sound, with no exceptions.
- Requests passed between tasks give the existing `Closed<…>`.

Incidental work keeps batch 9's signal rule unchanged. A marked item is a second kind of non-essential work that the same trigger ends.

`race` and `first_ok` discard a loser's whole result, cleanup failures included. That is the result the program asked them to choose against.

**A wait in code nothing can cancel** (unchanged from round 1)

```dewy
main = () => {
    sleep(10s)                 # void: nothing here can cancel; Ctrl-C ends the process (OS default)
    printl"late hello"
}
```

**`Canceled` is control, not data** (round 1 let it be stored)

```dewy
probe = (host:string) => {
    let r = net.ping(host)                   # Duration | NetError | Canceled, in a race item
    if r is? Canceled return r               # fine: tested and forwarded
    log(r)                                   # error, in the cancellable instance: r may be Canceled;
}                                            # handle it first (r or_throw, or ??<~Canceled>)
```

**A request passed between tasks closes like a channel** (round 1 had two `Canceled` arms)

```dewy
match select(@done.receive @job.cancel.receive) {
    reply:Reply => job.reply.send(reply) ?? void
    <Closed<task.CancelRequest>> => codec.abort()   # the caller gave up
    <Canceled> => break                             # this worker was canceled
}
```

**Incidental work: batch 9's trigger, a second kind of non-essential work**

```dewy
main = () => parallel {
    process_queue(p"queue" done) or_throw
    $until_others_finish { let heart = ticker(10s); loop heart.next is? Tick printl"{done.load'relaxed'}" }
    loop _ in signals.sigterm { printl"finishing the current job"; return }
}   # queue done: the ticker item is canceled, and the signal views close (batch 9, unchanged)
```

**A loser's cleanup failure** (round 1 let it replace the winner's success)

```dewy
let ip = race(@dns.lookup(host via="1.1.1.1") @dns.lookup(host via="8.8.8.8"))
# Ip | DnsError: race discards the loser's whole result, a failed socket close included.
# Hover on race lists what it discards; $explicit_cancellation makes that an error.
```

## 2. The rules

### 2.1 The request, and who closes it

1. **The request.** Every task has a cancel request: a channel with no payload that only its group can close. Once closed it stays closed.
   - When the task ends, its request also reads as closed, for any holder of a handle to it (§2.6).
   - A handle stays valid after the task is gone. It is reference-counted and never points into a task frame.
2. **Standard waits.** These are the standard waits:
   - channel and `mpmc` `send`, `receive` and `reserve`;
   - `sleep`, and ticker and signal `next`;
   - file, stdin, process and network I/O;
   - `lock_all`;
   - `select`;
   - a receive on a request.

   Each one returns when its own event happens or the task's own request closes, whichever comes first. If the request closed, it returns `Canceled` without doing its work. The task's own request has priority.
   - `check_cancel()` gives `Canceled` exactly when the task's request is closed.
   - `try_send` and `try_receive` never wait, so they stop being cancellation points (Q7).
   - Nothing else stops for cancellation: console output, `lock` and computation run straight through.
   - "Every later wait returns `Canceled` again" is what a closed channel does. It is not a separate rule.
3. **Joins are not ordinary waits.** Joining `race`, `first_ok`, `within`, `protect_from_cancel`, `parallel` or `task.tasks`, or calling `Task.wait()`, works like this when the joiner's request closes:
   - the join closes its children's requests at once;
   - it then drains: it waits for every child to end and for every child's cleanup;
   - only after that does it give its result (§2.4).

   A join never returns while one of its children still runs.
4. **Who closes it.** A group closes the request of each of its unfinished children in these cases:
   - `race` has its first result, or `first_ok` its first success;
   - a `within` or `protect_from_cancel` deadline passes;
   - a `parallel` item's `or_throw` or `return` leaves the function, or its `break` or `continue` leaves an enclosing loop;
   - the group's essential work is done, for items marked `$until_others_finish` (§2.7);
   - in `task.tasks`, a child fails, or the body fails or leaves by `or_throw`. A normal return of the body joins the children without canceling them (v5, and program 09's drain);
   - `task.stop()` closes one task's request, and `BackgroundTasks` closes all of its tasks' requests at program end;
   - the group's own request closes, and the close passes down to its children.

   Nothing closes the entry task's request.
5. **Canceled children don't all return `Canceled`.** Closing a request asks the child to stop. The child may handle the `Canceled` and return a value, return another failure, or compute on until its next checkpoint. Its group joins whatever it returns.

### 2.2 `Canceled` is control, not data (Q2)

In every instance where `Canceled` can occur:

- **What code may do with it.** It may bind it to a local, test it (`is?`, `match`), combine it (`and`, `&`), take a part out with `as`, default it (`??`), and forward it (`or_throw`, `return`, a function's final expression).
- **What is an error.** Each of these is an error, with a fix-it to forward the `Canceled` first or handle it:
  - storing it in an outer variable, a field, an element, a mutex-guarded value or any place outside the function's locals;
  - collecting it in a sequential collector (`[loop u in urls fetch(u)]`);
  - capturing a binding that may hold it;
  - passing it as an argument, string interpolation included;
  - sending it;
  - writing it in any type;
  - using it as the operand of a type operator (`type of`, `members`).
- **No constructor.** `Canceled` has no constructor. `return Canceled` and `Canceled or_throw` are errors; bind the one you have instead (`c:Canceled => return c`).
- **Group results.** A group's results never hold its items' `Canceled` (§2.4). That is why `[parallel u in urls fetch(u)]` is allowed while the sequential collector above is not.
- **Bindings after a `parallel` block.** These are locals of the enclosing function. They keep `| Canceled` only where that function is itself cancellable, and are narrowed elsewhere (§2.4).

**Why this exception earns its keep.** Without it, `Canceled` has two kinds that share one name:

- the ambient one, which groups may consume;
- data: constructed, stored, or carried from another task.

Telling them apart takes origin tracking at run time and context-indexed types for every record, array and closure (soundness M1–M3). Programmers would see two things with one spelling.

With the rule, every `Canceled` that exists belongs to the task it is in. It was produced because that task's request closed, and it can reach only that task's boundaries, by forwarding. Each boundary recognizes its own cancellation from its own state, "did I close this request?", and never needs to inspect the value. That is Zig's rule, "only the logic that made the cancelation request can soundly ignore error.Canceled" (std.Io, as quoted for this round; not re-checked here), enforced by the compiler instead of by convention.

The cost is a fix-it at the rare places where code passes a possible `Canceled` along as a value. Two such places are in the design docs today:

- D42 Q4's `wrap` takes the combined failure as a parameter;
- D42 Q1's REPL arm writes `Canceled or_throw`.

Both have direct rewrites (§3).

### 2.3 Cancellable contexts, and the inference

- **Definition (syntactic).** These are cancellable:
  - the items of `race`, `first_ok`, `within` and `protect_from_cancel`;
  - every `parallel` item: block items, loop iterations, comprehension elements;
  - the body of `task.tasks` and every spawned task;
  - drop hooks and `defer` of a cancellable task (§2.5);
  - the REPL's input;
  - everything those call.

  `main`, a script's top level, and what they call outside a group are not cancellable. Every `parallel` item counts, even where nothing can leave early (agreed with David). Hover notes "nothing in this block can cancel it now".
- **Cancellation is an inferred effect (Q1).** Context cancellation is a property of a function, like `blocks`. It shows up as a `| Canceled` result alternative only at cancellable call sites.
  - A function type carries the inferred effect "may be canceled". It is set when the function can reach a standard wait or `check_cancel` whose `Canceled` it forwards.
  - Written types never mention it.
  - A written function type (a record field `on_key:(Key):>void`, a parameter `op:():>T`) permits the effect by default, so a call through it adds `| Canceled` at a cancellable call site.
  - `& no blocks` on a written function type excludes it: every cancellation point, `check_cancel` included, counts as blocking for this purpose. That is a natural extension, flagged.
- **The fixed point** (soundness S1).
  - Let `B` be the demanded concrete specializations, with each callable argument's effect part of its key, and `Q = {N, C}`.
  - Start from `{(entry, N)}` and the runtime's own roots (cleanup, the REPL).
  - Each call edge in `(b,q)` adds `(g, tau_e(q))` for each possible target `g`:
    - direct and handle calls keep `q`;
    - a group child, a task body, a spawned task, a protected body, and a cancellable task's cleanup use `C`;
    - the continuation after a group resumes in `q`.
  - Creating, storing or sending a handle executes nothing and binds no context. Captured bindings can't hold `Canceled` (§2.2), so captures need no context typing.
  - This is monotone on a finite lattice, so a worklist terminates. Propagation costs O(|B| + |E|) over the resolved call graph.
  - Result inference is the existing fixpoint over inferred results, run per instance. Generic specialization keeps its existing termination rule for unbounded polymorphic recursion.
  - Indirect-target analysis is a separate cost. An unknown handle uses its written type's effect, and the analysis never reaches into a field without a written type.
- **Handles stored and called later.**
  - What matters is where a handle is *called*: `race(@slow @fast)` calls its handles in race items, so both are cancellable.
  - An array of handles to several functions has the union of their effects as its element type's effect.
  - Since `Canceled` appears only as a top-level result alternative, one effect bit is a complete description. Soundness M1's `pack` (a field holding `sleep(1s)`) and `capture` (a closure capturing a possible `Canceled`) are compile errors in their cancellable instances.
- **Generics, recursion and libraries.**
  - A higher-order function such as `retry` is instantiated per (context, effect of `op`).
  - A type argument never includes `Canceled`, because values that may be `Canceled` can't be passed and written types exclude it. Generic code therefore behaves the same in both instances.
  - Recursive and mutually recursive functions get at most one `N` and one `C` node per specialization.
  - Libraries are loaded whole and lazily (decided). Hover on a library opened alone shows `retry(attempts pause op) :> R   (+ Canceled where cancellable: while it sleeps between attempts)`. That is display text, not syntax.
- **`select`** gives `| Canceled` only in cancellable code (Q7). Its other outcomes, including `Closed<task.CancelRequest>` from a request it waits on, are the same everywhere.
- **`within` inside `race`.** The race closes `within`'s request, and `within` closes its child's. `within` sees that its parent closed the request, so it gives `Canceled`, and the race discards it. If `within`'s deadline fires first, it gives `Timeout`. If both happen, the parent wins.

### 2.4 Where `Canceled` goes, and what groups keep

**The containment theorem.** A `Canceled` exists only in the task whose request closed. It moves only by being forwarded (§2.2), and it is consumed or translated at the first boundary that closed that request, or at a boundary below it. That boundary recognizes it from its own state.

At each boundary:

| Group | Its own cancellation | A parent's cancellation | Children's other results |
|---|---|---|---|
| `race`, `first_ok` | losers' results discarded whole (Q6) | drains, then gives `Canceled` | the winner's result, or `first_ok`'s first failure when all fail |
| `within`, `protect_from_cancel` | the child's `Canceled` becomes `Timeout`; a child that handled it keeps its value | drains, then gives `Canceled`; the parent wins a tie | the child's failures kept, cleanup included: `Timeout & FileCloseFailed` |
| `parallel`, leaving early | siblings' `Canceled` consumed; the exit wins | items see `Canceled`, and bindings keep it where the enclosing function is cancellable | siblings' cleanup failures kept: `X & FlushError`; a `return v` becomes the cleanup failure (D40 Q1) |
| `parallel`, essential work done | marked items' `Canceled` consumed, including one their `or_throw` forwards | as above | a marked item's other failures are its own value: its `or_throw` forwards them, or `;` drops them |
| comprehension or loop (`[parallel …]`) | only on early exit (the array is never produced) | drains, then the whole expression gives `Canceled`; no element holds it | per element, C3 |
| `task.tasks` | stopped children's `Canceled` consumed; the failure returned | drains, then gives `Canceled` | children's failures fail the group (v5) |
| `Task.stop()`, then `.wait()` | the stopped task's `Canceled` consumed: `.wait()` gives `void \| E` | the waiter's own `Canceled`, in cancellable code | the task's own failures, cleanup included |

- **Narrowing after a block** (soundness M4). Where the enclosing function is not cancellable:
  - its request never closes;
  - marked items can't declare names that other items or later code read (an error, checked statically on the item);
  - signal closure gives `Closed<E>`, never `Canceled`.

  So an essential item is canceled only on an exit that skips the code after the block, and its bindings are narrowed. Soundness M4's `let event = listen` is typed `Signal | Closed<Signal>`, never `Canceled`.
- **Telling "finished" from "stopped".** Read `.running` before `stop()`, as program 13 does.
- **The `or_throw` in a marked item.** It forwards the `Canceled` its block caused, and the block consumes it. That is the round's core rule ("a group consumes the cancellation it causes"), applied to the one case where an item's `or_throw` doesn't skip the code after the block. C3 holds for every other failure (Q7).

### 2.5 Cleanup

- **The shield.** Drop hooks and `defer` always run on a fresh request, never on the task's own.
- **The grace deadline.** It starts only when the owning task's request is already closed, or closes during cleanup. It is 100 ms by default, or the acquisition's `timeout=`. In a task nothing can cancel there is no deadline: a slow final flush in `main` completes.
- **Grace expiry.** The hook's waits give `Canceled`, and the hook's owner translates that into `Timeout`, as `protect_from_cancel` does. Hooks of a cancellable task are instantiated `C`, so their failure set gains `Timeout`. Hooks in `main` gain nothing.
- **Why this exception is unavoidable.** A closed request stays closed. Without the shield, every flush and close in a canceled task would fail at once, exactly when cleanup matters. It is not a new mechanism: shielding is `protect_from_cancel` with the grace deadline.

### 2.6 The three levels for user code

1. **Anything that calls a standard wait is already cancellable,** `select` included.
2. **`check_cancel()`** is the checkpoint for CPU loops. Where nothing can cancel, it warns.
3. **A custom wait** across tasks uses `task.cancel_request` (Q4). Its type, `task.CancelRequest`, is the receive-only end of the request channel.
   - `receive` waits until the request closes, then gives `Closed<task.CancelRequest>`, the existing close outcome. There is no new member and no second `Canceled`.
   - `receive(timeout=0s)` polls. Program 08 uses it to skip jobs whose caller gave up while queued.
   - Receiving on your own request gives your own `Canceled`, because your own request has priority, so `Closed<task.CancelRequest>` always means another task's.
   - A `Closed<…>` is ordinary data and may be stored or reach `main`.
   - Forgetting to pass the request is silent. Nothing structural can see a cancellation link carried through a channel, and the peer languages can't either.

`check_cancel` beside `cancel_request` passed the cold read: 3/3 at 5/4/4.

### 2.7 Incidental work: one trigger, two kinds of non-essential work

- **The trigger.** An owning group's essential work is done when all of its unfinished activity is one of:
  - parked in signal-only waits (batch 9's definition, unchanged: an all-signal `select` qualifies, a timeout doesn't);
  - inside an item marked `$until_others_finish`.

  The group body participates where there is one. Pending dependents are published first (batch 9).
- **What happens then:**
  - the group closes its signal views (batch 9, unchanged: pending notifications drain, then `Closed<E>`; iteration ends; code after the loop and cleanup run normally);
  - it closes the requests of its marked items.
- **Owning groups only.** The trigger applies to `parallel` blocks (batch 9's owners). `race`, `first_ok`, `within` and `protect_from_cancel` stay transparent: their children count in the owner's frontier, as batch 9 says. So `race(@signals.sigterm.next @signals.sighup.next)` in `main` waits for a signal, and `within(30s @signals.sigterm.next)` waits up to 30 s (review M3, soundness M4).
- **Where the marker goes.** `$until_others_finish` prefixes a `parallel` block item, and only that. There is no form inside a helper, so nothing non-local remains beyond batch 9's own signal waits (review S6).
  - A marked item can't bind names read outside it, which is an error.
  - A lock held across a wait is already an error (LANGUAGE.md, deadlock rules), so a marked item can't wedge an essential one.
  - A marked item not yet started under `max_concurrent` is never started.
- **Behaviour changes against batch 9.** None for any program without the marker. With it, the one change is the intended one: work inside a marked item no longer keeps the group alive.
- **Diagnostics.**
  - Every item marked: error.
  - A block made only of signal listeners: warning, "nothing here is essential: the block closes its signal views at once" (review N6).
  - An item that ends only when canceled, in a block where nothing cancels it: warning, "this block never ends … mark it `$until_others_finish`?".
  - `break` out of a `signals.ctrl_c` loop while other work continues: warning, "Ctrl-C stays intercepted until the block ends, and nothing will listen; `return` from a function that holds the block" (regrade 02).
- **No separate "is the real work done?" check.** A marked CPU loop uses `check_cancel()`. A marked item that tidies up handles the `Canceled` from its wait (program 05).
- **Spelling.** `$until_others_finish` was read correctly cold, 3/3 at 4/4/4. `$incidental` failed: readers got the role but not that it stops. The library call `task.incidental(@work)` is the alternative weighed in round 1.

### 2.8 Ctrl-C

- **With no intercepting wait,** Ctrl-C keeps the OS default: the process ends at once, with no cleanup. A shell sees 130; on Windows the status is `STATUS_CONTROL_C_EXIT`.
- **To clean up,** write `loop _ in signals.ctrl_c { …; return }` as a `parallel` item, and put the block in a small function if code must run after it (program 02).
- **`.observe`** never asks for cancellation.
- **The three-press forced exit goes (Q7).** It existed for the root-cancellation shutdown that no longer happens. A program that intercepts Ctrl-C owns it: the REPL survives repeated presses, and Ctrl-\ (SIGQUIT) or Ctrl-Break still ends a stuck program by OS default.
- **The cost of the OS default.** An unhandled press loses buffered output and leaves temporary files. Atomic writes keep the old file. This matches C, Go and Rust, but not Python.

### 2.9 Why the request travels implicitly, and Zig

- **Cancellation belongs to the running task,** as its stack does. Every wait runs in exactly one task, and only that task's group can stop it.
- **An explicit parameter colours every function that might wait,** transitively. Go's `ctx` is the example, and a forgotten one (`context.Background()`) silently cuts cancellation off.
- **Zig's std.Io supports this split** (proposal-v3 §5). Zig carries the request inside its `io` value, which travels with the execution for all I/O, not as a per-call cancellation argument. Dewy infers waiting, so it has no `io`, and the request rides with the task.
- **Level, not edge.** Zig delivers a cancellation once, at the next cancellation point, and needs `recancel` to re-arm it. Its open issues #31340 ("dropped acknowledged cancelations") and #35564 (`Condition.wait` swallowing `Canceled`) are the failure mode of that choice. A closed request stays closed, so a swallowed `Canceled` can't leave a task running on unstoppably: its next wait reports it again.
- **Zig's rule about swallowing.** Zig says only the code that made the cancelation request may ignore `error.Canceled`. Dewy's version is "a group consumes the cancellation it causes", and §2.2 makes it checked, since nobody else can make or keep one.

### 2.10 One body or two

Machine code is emitted once per function. It is sound because §2.2 removes every case that would need two bodies:

| What could differ between instances | Why it can't under §2.2 |
|---|---|
| a stored layout (a field, an element, a captured value) | `Canceled` can't be stored, collected or captured |
| a generic argument, or overload choice | a possible `Canceled` can't be passed, and written types exclude the effect, so no type argument includes `Canceled` |
| comptime type inspection (`members`, `type of`) | its operand can't include `Canceled` |
| the top-level result layout | the result convention reserves a `Canceled` tag. A non-cancellable caller unwraps the payload or remaps the tag: one move per call, no copy |

- **Run time.** A wait in non-cancellable code compares one pointer with the root sentinel and skips registering on it. A group inside non-cancellable code handles its children's `Canceled` itself, the same in both instances.
- **No warning is needed.** Nothing is duplicated. An optional specialized copy for the non-cancellable context is the inliner's choice, and `explain` lists it.
- **If David rejects Q2,** keeping `Canceled` as storable data, two bodies are required wherever the effect reaches a stored layout, a generic argument or type inspection. Each such case should warn, naming the call sites. The cost is the size of those functions' bodies, bounded by the functions reached from both contexts: 4 of the 39 in round 1's programs. Two independent origins would also need run-time tracking (soundness M2).
- **Compile cost.**
  - Propagation is O(|B| + |E|) over the resolved graph.
  - The checks that depend on the bit (exhaustive matches, the §2.2 errors, `$explicit_cancellation`, the warnings) run once per existing instance.
  - Hover keeps predecessor links and expands them lazily.
  - Incremental edits re-propagate forward from a changed site and recompute that site's dependent summaries.
  - Where no group is reachable, the extra work is one membership test per demanded body. That must be measured on the flagship panel before landing; no measurement exists yet.

## 3. Knock-on edits

Round 1's list stands where unchanged (D10 and D11 comments; LANGUAGE.md 277–278, 3633–3675). The changes are:

**D41**
- *Intro*: as in round 1.
- *Q1*: as in round 1.
- *Q2*: as in round 1, and add "cleanup is shielded the same way, with a deadline only once its task is canceled".
- *Q3*: "the body and every spawned task are cancellable; a child failure, or the body failing or leaving by `or_throw`, cancels the rest; a normal return joins them."

**D42**
- *Q1*: the REPL arm `<Canceled> => Canceled or_throw` becomes `c:Canceled => return c`. Add "Canceled is never stored; see the cancellation rules".
- *Q2*: withdrawn. The `select` progress rule extends to a `??` fallback on a wait in a loop. It is an error where the wait is written in the loop or in a known callee, as for `select`, and gives no diagnostic through a callback (review N5).
- *Q3*: under `$explicit_cancellation`, in cancellable code:
  - a handler that can consume `Canceled` must name it;
  - `race` or `first_ok` over work whose cleanup can fail is an error with the fix "handle it inside the work" (Q6).
- *Q4*: `wrap(job result:Canceled & …)` takes `Canceled` as a parameter, which is now an error. Write it where the failure arrives:
  ```dewy
  upload = (job:int) => {
      let result = send_all(job)                                   # Canceled & FileCloseFailed & …
      if result is? Canceled return (result as Canceled) and UploadFailed[job "upload failed" (result as error)]
      result
  }
  ```
- *Q7*: `Canceled` can't reach `main` at all now: it is never constructed or stored. So the "130 outranks" reason goes, and round 1's "declared order" reason is withdrawn (unions are unordered; review N2). Q7 is only about ordinary combinations such as `FileWriteFailed & FileCloseFailed`, and highest versus lowest code has no cancellation reason left.

**LANGUAGE.md** (in addition to round 1's list)
- 3633: "`Canceled` is an exception value" stays, and add §2.2's rule.
- 3729–3730, 3744: a canceled send gives `Canceled`, and its payload is dropped with the canceled task's locals. `@out.reserve` keeps a payload, because a canceled reserve leaves the value in the caller's hands (Q7).
- 3830–3833: delete the observer's root cancellation and the three-press forced exit (Q7).
- 3838–3858: keep the signal closure text, and add "items marked `$until_others_finish` don't keep the group alive; the same trigger cancels them".
- 3997: `try_send` and `try_receive` aren't cancellation points (Q7).

**Library**
- `lib/std/signals.dewy`: `next` keeps `Closed<E>` (batch 9) and drops its written `| Canceled` (Q1). `if code =? 2 return Canceled` forwards the runtime intrinsic's own `Canceled` (Q2).

**Proposals**
- v5's `.wait()` paragraph, and `task.catch_ctrl_c`: superseded. Batch 9 already took signals instead of `catch_ctrl_c`, and this round removes `.wait()`'s stop-`Canceled` (review N4).

## 4. Questions for David

13 programs dogfooded (`dogfood-round2.md`); the lowest grade is 3. Names in Q3 and Q4 passed a cold read; the new readings in `names-r2.txt` await another.

### Q1 (a). Context cancellation is an inferred effect, never written in a result type

```dewy
transfer = (src:Mutex<int64> dst:Mutex<int64> amount:int64):>void | DuplicateLock => {
    let [a b] = @(lock_all(src dst)) or_throw   # in a parallel item: also | Canceled
    a -= amount
    b += amount
}
```

Should cancellation be an inferred effect, like `blocks`? It would show up as `| Canceled` only at cancellable call sites, a written result type would never name it, and writing it would be an error with a fix-it.

- **Rec:** yes. "An annotation fixes the error set" then stays true of written types, and the one remaining exception is that an effect adds a result member. That is batch 5's open "whether cancellation is an effect row", answered.
- **Reversible** before release.

### Q2 (a). `Canceled` is control, not data

```dewy
let r = fetch(url)                  # string | HttpError | Canceled, in an item
if r is? Canceled return r          # fine
results.push(r)                     # error: forward or handle Canceled first
return Canceled                     # error: Canceled has no constructor; return the one you have
```

Should code be allowed to test, match, combine, default and forward `Canceled`, but never store, collect, capture, send, pass or construct it?

- **Rec:** yes. It is the one rule that makes one `Canceled`, one compiled body and no origin tracking sound together (§2.2, §2.10). The alternative is context-indexed types for every aggregate plus run-time origins.
- It changes D42 Q4's `wrap` example and LANGUAGE.md's collector text.
- **Reversible** before release, by adding the origin machinery.

### Q3 (b). `$until_others_finish` on a `parallel` item

```dewy
main = () => parallel (
    $until_others_finish spin("counting")      # canceled once the rest has finished
    let n = count_lines(p"big.txt")
)
```

Should a `parallel` item prefixed with `$until_others_finish` not keep its block alive, and be canceled by the same trigger that closes batch 9's signal views?

- **Rec:** yes. The name was read correctly cold (3/3, 4/4/4), and batch 9's behaviour is unchanged.
- **Reversible:** the spelling, freely; the rule, before release.

### Q4 (c). The request handed to another task

```dewy
jobs.send(Job[path reply task.cancel_request]) or_throw       # caller
<Closed<task.CancelRequest>> => codec.abort()                  # worker: the caller gave up
```

- **Rec:** `task.cancel_request`, of type `task.CancelRequest`. Both passed the cold read, 3/3 at 4/4/4.
- `receive` on it gives the existing `Closed<…>` when the caller's group cancels the caller or the caller ends.
- **Reversible.**

### Q5 (a). Iterating any source ends at cancellation

```dewy
loop job in jobs { process(job) }        # canceled: the loop ends
loop job in jobs or_throw { … }          # canceled: leaves with Canceled (teach this before publishing)
```

This extends batch 9's signal iteration rule to channels and `merged`, and removes `merged`'s one-`Canceled`-item special case (LANGUAGE.md 3967).

- Hover on a loop that may end this way says "ends early when canceled (group at line N)".
- **Rec:** yes. It is a unification.
- **Reversible** before release.

### Q6 (a). `race` and `first_ok` discard a loser's whole result, cleanup failures included

```dewy
let ip = race(@dns.lookup(host via="1.1.1.1") @dns.lookup(host via="8.8.8.8"))   # Ip | DnsError
```

Is a loser's failed close part of anything the program asked for? No. `race` and `first_ok` are actions whose named contract is to choose one result and drop the rest, so the loser's result, its close included, is a value the program declined.

- D40 Q1 holds: the failure *is* the loser's result.
- D42 Q1 holds: a part goes only through an action that names it, and here `race` or `first_ok` is that action.
- It surfaces in three places:
  - hover on the call lists "discards: losers' SocketCloseFailed";
  - a debug build logs each discarded failure once;
  - `$explicit_cancellation` makes the call an error until the work handles its own cleanup failure (certifiable mode).
- `within`, `parallel` and `task.tasks` keep cleanup failures, because there the canceled work is the program's own, not a declined alternative.

**Rec:** yes. Reversible before release.

### Q7 (a). Changes to documented behaviour, taken together

| Change | Example | Why |
|---|---|---|
| `select` gives `Canceled` only in cancellable code (batch 7: always) | `select(@a.receive)` in `main`: `int \| Closed<int>` | the core rule |
| A canceled send gives `Canceled` and drops its payload; `reserve` keeps it | `out.send(conn)` canceled: `conn` is closed by drop | a group must recognize its own cancellation |
| `try_send` and `try_receive` aren't cancellation points | `q.try_receive` gives `Empty`, never `Canceled` | they never wait |
| `Task.wait()` after `stop()` doesn't report the stop's `Canceled` | `w.stop(); w.wait() or_throw` gives `void \| E` | whoever stopped it consumes it |
| The three-press forced exit goes | the REPL survives repeated Ctrl-C | the root shutdown it protected no longer exists |
| A marked item's `or_throw` of its block's `Canceled` ends only the item | `$until_others_finish { sleep(1s) or_throw }` | the group consumes what it causes (C3 otherwise unchanged) |
| Ctrl-C unhandled: OS default; `.observe` never cancels | as §2.8 | your stated preference, listed for completeness |

**Rec:** accept all. Each is reversible before release.

## 5. Resolution of every finding

**Review (`review-round1.md`)**

| Finding | Resolution |
|---|---|
| M1: two kinds of `Canceled` | One kind. No constructor; never stored, collected, captured, passed or sent (§2.2, Q2). Foreign requests give `Closed<…>` (§2.6). Both scenarios are now errors at the store (`status = …`, `log(r)`), and `probe`'s `return r` is the context member. |
| M2: one body unsound with layout or type-directed code | Sound under §2.2: §2.10 shows why each case can't arise. If Q2 is rejected, two bodies are needed, with a warning and the stated cost. |
| M3: incidental closure breaks signal-only `race`/`within` | The trigger applies only at owning `parallel` blocks; `race`, `within`, `first_ok` and `protect_from_cancel` are transparent, as in batch 9 (§2.7). |
| M4: batch 9 not reproduced | Batch 9 is kept unchanged: views close with `Closed<E>`, and code after the loop runs normally. The marker adds a second kind of non-essential work. C3 refinement listed (Q7). |
| M5: loser cleanup failure replaces success | Discarded with the loser's result, with hover, a debug log and the strict tag (Q6). `AfterCancel` is gone. Programs 03 and 04's stated types are now correct. |
| S1: written function types, higher-order, heap | The effect is permitted by written types unless `& no blocks`. Higher-order functions are instantiated per (context, effect). An unknown handle uses its written type (§2.3). |
| S2: canceled send loses payload; `try_*` | Stated; `reserve` keeps it; `try_*` aren't cancellation points (Q7). |
| S3: frame Q1 as an effect | Done; written `Canceled` is an error (Q1). |
| S4: Q4 is a unification; name the hazard | Q5 says so. Hover on the loop; `or_throw` taught before publishing. |
| S5: request as receive-only channel end | Done (§2.6, program 08); `select` uses only channel waits; queued jobs whose caller gave up are skipped. |
| S6: `$incidental` in helpers is non-local | The marker is item-level only; marked items can't bind outward names; locks across waits are already errors; the scope is stated (§2.7). |
| S7: three-press forced exit | Removed; listed (Q7). |
| S8: `task.tasks` "body leaves" | "Fails or leaves by `or_throw`"; a normal return joins (§2.1). |
| S9: grace deadline everywhere | The deadline only once the task is canceled; non-cancellable cleanup stays `N` (§2.5). |
| N1: wrong hover lines | Program 06 and §1 corrected. |
| N2: D42 Q7 order | That reason is withdrawn (§3). |
| N3: unkitted spellings | `AfterCancel` and `.wait` are gone; the new readings are in `names-r2.txt`. |
| N4: unlisted decided-rule changes | Listed in Q7 and §3. `Closed<E>` stays in signals now. |
| N5: hint or rule | An error where seen; no diagnostic through callbacks (§3). |
| N6: block of only listeners | Warning (§2.7). |
| N7: definition vs rule | Syntactic definition (§2.3). |
| N8: program bugs | 12 finishes the current job (`check_cancel` plus `protect_from_cancel`); 11 uses `first_ok` and an atomic write; 05 prints after clearing; 13 forwards `WatchError`. |

**Soundness check (`soundness-round1.md`)**

| Finding | Resolution |
|---|---|
| M1: a bit can't describe aggregates and callables | With §2.2, `Canceled` occurs only as a top-level result alternative, so the bit is complete. `pack` and `capture` are errors in their cancellable instances. |
| M2: separate origins | No foreign `Canceled` exists: requests give `Closed<…>`, and none can be constructed or stored. A boundary recognizes its own cancellation from its own state (§2.4). `.wait()` after `stop()` is sound for the same reason. |
| M3: one body changes generic behaviour | Type arguments can't include `Canceled` (§2.10). `count_alternatives(wait_value)` is an error in its cancellable instance; the fix-it is `wait_value or_throw`. |
| M4: dynamic incidental breaks narrowing and winner proofs | Nothing becomes incidental dynamically except batch 9's signal waits, which give `Closed<E>`. Marked items are static and can't export bindings. Winner groups are transparent. "Every child returns `Canceled`" is weakened (§2.1.5). |
| S1: fixed point and costs | Stated (§2.3); costs separated, and zero-cost claimed only after measurement (§2.10). |
| S2: joins and cleanup transfers | Joins drain before returning (§2.1.3); cleanup runs on a fresh request, instantiated `C` in cancellable tasks (§2.5). |
| N1: specimens | Each of them types as the soundness check expects. The exceptions: `Job.run` in a field is effect-permitting (§2.3), and the foreign-request specimen now gives `Closed<task.CancelRequest>`. |

**Regrade (`regrade-round1.md`)**

| Program, axis | Resolution |
|---|---|
| 03 safe (5 → 3) | Losers discarded (Q6); the stated types are now true. |
| 05 complete (5 → 3) | The count prints after the block; the spinner blanks its line. |
| 11 safe (5 → 2) | `first_ok`, so a fast failure no longer cancels a good write; atomic replace, so the old backup survives. |
| 12 safe and complete (5 → 3) | It finishes the current job: `check_cancel` between jobs, `protect_from_cancel(30s …)` around one. |
| 02 discoverable (3) | The `break` warning (§2.7); the helper idiom is still taught. |

**Cold read:** `$incidental` is replaced by `$until_others_finish`; `task.cancel_request` and `task.CancelRequest` are kept.
