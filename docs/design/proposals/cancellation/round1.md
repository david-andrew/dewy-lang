# Cancellation, round 1: `Canceled` only where something can cancel

## 1. Verdict

Take David's rule. A result has `Canceled` in it only where something can cancel the work, and the compiler infers where that is, the same way it infers waiting. The formal model is the one David liked:

- Every task has a cancel request: a channel with no payload that only its group can close.
- Every standard wait returns when its own event happens or when the request closes, whichever comes first.
- Nothing can close the entry task's request, so a program that starts no group never sees `Canceled`. With no handler, Ctrl-C keeps the OS default.
- A group consumes the `Canceled` it causes and keeps whatever cleanup failures come with it.

A second mechanism, *incidental work*, generalizes the signal rule from batch 9: once only incidental work is left in a group, the group cancels it.

The claim "Canceled never escapes into code that started no group" holds for every `Canceled` a wait produces, with three adjustments:

- `Task.wait()` stops reporting the `Canceled` that a `stop()` caused.
- A canceled send gives `Canceled`, not `Unsent` with reason `Canceled`.
- Values read after a `parallel` block are narrowed.

Explicitly constructed `Canceled` values, stored data and requests passed between tasks as data are ordinary values (§2.3).

**A wait in code nothing can cancel**

```dewy
# before                                   # after
main = () => {                             main = () => {
    sleep(10s) or_throw   # void | Canceled    sleep(10s)            # void
    printl"late hello"                         printl"late hello"
}                                          }   # Ctrl-C: the OS default ends the process
```

**David's race: unchanged inside the items, and `main` no longer forwards anything**

```dewy
fast = () => { sleep(1s) or_throw; "fast" }   # string | Canceled: fast is a race item
main = () => {
    let winner = race(@slow @fast) or_throw   # warning: race gives string here; this
    printl"winner: {winner}"                  # or_throw forwards nothing
}   # prints slow: start, slow: woken early, slow: done, winner: fast
```

**Saving on Ctrl-C** (before: D41 Q2's root cancellation, then `protect_from_cancel` and exit 130)

```dewy
optimize = (best:Mutex<Route> cities:array<City>) => parallel {
    improve(best cities)                       # cancellable: check_cancel() or_throw inside
    loop _ in signals.ctrl_c { printl"stopping early"; return }   # ends the block
}
main = () => {
    let best = mutex(first_route(cities))
    optimize(best cities)                      # void: the block consumes the Canceled it causes
    save_route(@(best.lock) p"best-route.txt") or_throw;
}
```

**Incidental work** (before: a done channel, or a `race` in which a spinner failure would cancel the work)

```dewy
main = () => parallel {
    $incidental spin("counting")               # doesn't keep the block alive
    count_lines(p"big.txt") or_throw           # warning: count_lines gives void; this
}                                              # or_throw forwards nothing
```

**One function, two contexts**

```dewy
main = () => {
    let base = load_config(p"app.toml") or_throw          # Config | FileError | ParseError
    parallel (
        let local = load_config(p"local.toml") ?? base    # here also | Canceled
        let theme = load_theme(base.theme) or_throw
    )
}   # hover on load_config: "+ Canceled at lines 4 and 5 (parallel items); not at line 2"
```

## 2. The rules

### 2.1 The cancel request

1. **One request per task.** The request is a channel with no payload. Only the task's group can close it, and once closed it stays closed.
2. **Standard waits watch it.** These are the standard waits:
   - channel `send` and `receive`;
   - `sleep`, and `next` on tickers and signal sources;
   - file, stdin, process and network I/O;
   - `lock_all`;
   - `select`, and the joins of `race`, `first_ok`, `within`, `parallel`, `task.tasks` and `Task.wait()`;
   - a wait on a request (§2.5).

   Each one returns when its own event happens or the request closes, whichever comes first. If the request closed, it returns `Canceled` without doing its work. If the request was already closed before the call, the call returns `Canceled` at once.
   - `check_cancel()` returns `Canceled` exactly when the request is closed.
   - Nothing else stops for cancellation: console output, `lock` and plain computation run straight through.
   - "Every later wait returns `Canceled` again" is therefore not a separate level-triggered rule (LANGUAGE.md line 3634). It is what a closed channel does.
3. **Who closes it.** A group closes the request of each of its unfinished children when one of these happens:
   - `race` gets its first result, or `first_ok` gets its first success.
   - A `within` deadline passes. Its child's request closes when the deadline passes or when `within`'s own request closes.
   - A `protect_from_cancel` deadline passes. Its body runs on a fresh request that is not linked to the parent's; that is all masking means.
   - A `parallel` item leaves the block: `or_throw` or `return` leaves the function, or `break` or `continue` leaves an enclosing loop.
   - Only incidental work remains (§2.6).
   - In `task.tasks`, a child or the body fails, or the body leaves.
   - `BackgroundTasks` closes all its tasks' requests at program end, and `task.stop()` closes one task's request.
   - The group's own request closes, and the close passes down to its children.

   Nothing closes the entry task's request. With no handler, Ctrl-C is the OS default (§2.7), so nothing above `main` can cancel it.
4. **A canceled send gives `Canceled`.** That is the call's own result, as batch 7 already says for timed sends. `Unsent` keeps the reasons `Full`, `Closed`, `Busy` and `Timeout`. The payload is dropped with the canceled task's other locals.
   - This is a natural extension, flagged. The group must be able to recognize its own cancellation and consume it; an `Unsent[reason=Canceled]` would slip past it and leave the function as an ordinary failure.

### 2.2 Cancellable contexts and the inference

**Definition.** Code is *cancellable* when it runs on a request that something can close. These are cancellable:

- the items of `race`, `first_ok`, `within` and `protect_from_cancel`;
- every `parallel` item: block items, loop iterations and comprehension elements;
- the body of `task.tasks`, and every spawned task, whether in `Tasks` or `BackgroundTasks`;
- everything those call.

Everything else is not cancellable: `main`, a script's top level, and whatever they call outside a group.

- **Every `parallel` item counts**, even when nothing in its block can leave early. Otherwise adding an `or_throw` to one item would change the types inside another (agreed with David). Hover then shows `| Canceled` with the note "nothing in this block can cancel it now: no item leaves early and none is incidental".
- **Where contexts come from.** Every group construct (`race`, `first_ok`, `within`, `protect_from_cancel`, `parallel`, `task.tasks`, `spawn`) is built on one runtime primitive, which starts work on a closable request. The compiler marks the work started there as cancellable. A combinator someone writes over `task.tasks` or `spawn` is therefore handled correctly with no annotation.
- **Instances.** Each function has at most two typed instances: one where it is not cancellable and one where it is. Which ones exist depends on where the function is reached from, starting at the entry and following calls on demand.
  - In the cancellable instance, a standard wait's result includes `| Canceled`. That member then flows through `or_throw`, `return`, matches and inferred results like any other failure.
  - In the other instance it is absent.
- **A group's own result.** Joining a group is itself a wait, so a group inside cancellable code also gives that code's `Canceled`. Elsewhere it gives none: `race(@slow @fast)` in `main` is `string`.
- **Function handles stored and called later.**
  - What matters is where the handle is *called*. `race(@slow @fast)` takes its handles in `main` but calls them inside race items, so both run cancellable.
  - A function's type carries an inferred mark, "may pass on cancellation", in the way the `blocks` effect is inferred. The mark is set when the function can reach a wait or `check_cancel` whose `Canceled` it passes on. A call through a handle adds `| Canceled` exactly when the call is cancellable and the mark is set.
  - Where the callee isn't known, for example an array of handles to several functions, the mark is the union of their marks.
  - At run time there is no flag and no second code pointer. A handle points to the one compiled body (§2.10), and that body reads the running task's request, which every wait already does.
- **Recursion and mutual recursion.**
  - The analysis works on (function, context) pairs, so there are at most twice as many nodes as functions, and propagation terminates.
  - Result inference is Dewy's existing fixpoint over inferred results, run per instance. Mutual recursion is handled per strongly connected component, as it is today.
  - Example: `crawl = (url depth) => [parallel link in links(url) crawl(link depth-1)]`. The top call from `main` is not cancellable; every recursive call is.
- **Library modules.** Loading is lazy and whole-program, with no library image (decided), so instances exist only for what the program actually uses.
  - When a library file is opened alone, and in generated docs, the signature is shown in a form that covers both contexts: `retry(attempts pause op) :> R   (+ Canceled where cancellable: while it sleeps between attempts)`.
  - This is display text, not source syntax. How a *written* result type treats cancellation is Q1.
- **`parallel x in xs` loops and comprehensions.** Every iteration or element is cancellable. Values read after the loop are covered in §2.3.
- **`task.tasks` (D41 Q3).** Its body and every task spawned into it are cancellable.
- **`select`** is a standard wait. It gives `| Canceled` only in cancellable code. Elsewhere it gives the union of its waits' outcomes, plus `Timeout` with `timeout=`.
- **`within` inside `race`.** The race closes `within`'s request, and `within` closes its child's. The child returns `Canceled`. `within` sees that its parent's request closed rather than its own deadline, so it returns `Canceled`, and the race drops it. If the deadline fires first, `within` returns `Timeout`, and that can win the race as an ordinary result. If both happen, the parent's cause wins.
- **The REPL** runs each input as a race item against Ctrl-C (batch 9), so code typed at the prompt is cancellable.

### 2.3 Where `Canceled` goes: the claim, checked

**What holds.** The group that closed a request consumes every `Canceled` a wait produces because of it:

- **`race` and `first_ok`.**
  - They drop the losers' results, and `first_ok` also drops earlier failures once something succeeds.
  - A winner's result never holds this group's `Canceled`, because requests close only after there is a winner.
  - When the outer request closes, every child returns `Canceled`, and the group forwards it to the outer group.
- **`within`.**
  - A `Canceled` caused by its own deadline becomes `Timeout`.
  - A `Canceled` caused by its parent stays `Canceled` and reaches the parent's group.
  - A child that handles its cancellation and returns a value returns that value.
  - `protect_from_cancel` treats its own deadline the same way.
- **`parallel`.**
  - When the block closes requests because one item is leaving, that item's exit wins and the siblings' `Canceled` is dropped.
  - After a block that completes, this block canceled none of its essential items. That is because it closes their requests only on an exit that skips the code after it. So values read after the block carry no `Canceled` from this block. They carry the enclosing code's `Canceled` only where the enclosing function is itself cancellable.
  - For example, in `main`, `parallel ( let a = fetch(x); let b = fetch(y) or_throw )` leaves `a: string | FetchError` after the block. Inside it, `a` may still be `Canceled`.
- **Incidental items.**
  - When the block ends an incidental item, that item's `or_throw` of the `Canceled` ends the item only and the block drops it. C3 ("`or_throw` leaves the function") still holds for every other failure.
  - An incidental item can't declare a name that is read after the block (error), because once canceled it has no value.
- **`task.tasks`.** When it stops the other tasks because one failed, it drops their `Canceled` and returns the failure.
- **`Task.stop()`, then `.wait()`.** The `Canceled` that the stop caused is not reported. `.wait()` gives `void | E`, plus the waiter's own `Canceled` where the waiter is cancellable.
  - This changes the v5 proposal's "a task that ended canceled still reports `Canceled`".
  - The idiom `worker.wait() ??<Canceled> { check_cancel() or_throw }` goes.

**Where the claim, as stated, is wrong**

1. **Explicit values.** `return Canceled`, and a `Canceled` read from a variable, are ordinary failures. Their type includes `Canceled` in every context, and one can reach `main`, where it exits with `Canceled`'s ordinary code.
   - The standard library must never make a context `Canceled` by hand. `signals.dewy`'s `if code =? 2 return Canceled` has to forward the runtime primitive's own `Canceled` instead (§3).
2. **Data a cancellable task stored.** A `Canceled` inside a record field or a mutex-guarded collection is data, and its type keeps `Canceled` in every context. Hover outside the group says "stored by a cancellable task at line N". A channel can't carry one bare, because payloads that may be exceptions are already rejected.
3. **A request passed as data** (level 3, §2.5). Waiting on *another* task's request gives the waiter a `Canceled` that its own group didn't cause. The waiter's code handles it like any other value (program 08).
4. **Cleanup failures** travel with `Canceled` (§2.4).

`main` can still receive a `Canceled` through 1–3. It never receives one from a wait.

### 2.4 A canceled task whose cleanup fails

- **Cleanup runs shielded.** Drop hooks and `defer` run as `protect_from_cancel(grace @cleanup)`, on a fresh request that only the grace deadline closes. The grace is 100 ms by default, or the acquisition's `timeout=`.
- **The group keeps everything but its own `Canceled`.** A canceled sibling whose file fails to flush returns `Canceled & FlushError` (D42). The group removes exactly the `Canceled` part it caused, as `as` would, and keeps the rest.
  - Where the failing work was the group's *only* work (`within`'s child), what's kept is that work's own failure: `Timeout & FlushError`.
  - Where the group drops that work's result (race and `first_ok` losers, and the siblings of an item that is leaving), the kept failure comes back wrapped, so it can't be mistaken for the winner's failure or the leaving item's: `AfterCancel<FlushError>` (Q5).
  - It then joins the group's result by D40 Q1 (a cleanup failure becomes the result) and D42 (`&`):

| Group | What comes back |
|---|---|
| `race` or `first_ok`, winner succeeded | the wrapped loser failures replace the success; several combine with `&` |
| `race`, winner failed with `E` | `E & AfterCancel<FlushError>` |
| `within`, its own deadline | `Timeout & FlushError` |
| `parallel`, an item leaves with `X` | `X & AfterCancel<FlushError>` |
| `parallel`, `return v` | `AfterCancel<FlushError>` replaces `v`, as a cleanup failure at a return does |
| `parallel`, `break` | the block is a cleanup boundary under D40 Q6, so a fallible sibling cleanup needs the block's marker (natural extension) |
| incidental item ended | the item's own `FlushError`, which is the item's value: its `or_throw` forwards it, or `;` drops it |

- **Out of scope.** When cleanup itself runs out of grace, the resource is abandoned and reports its own failure. The cleanup design owns that.

### 2.5 The three levels for user code, and the nameable request

1. **Anything that calls a standard wait is already cancellable,** and that includes a custom wait built on `select`.
2. **`check_cancel()` is the checkpoint** for CPU loops that don't wait (D41 Q1).
   - In code nothing can cancel, it warns: "nothing can cancel this; Ctrl-C ends the process".
   - In a function with both instances it doesn't warn, because one instance needs it.
   - The compiler may batch checks, as v5 allows.
3. **A custom wait** waits on its own event or on a request.
   - `task.cancel_request` (Q3) is the request in force at that point, the one the next wait would watch. Its type is `task.CancelRequest`.
   - `.wait` gives `Canceled` when the request closes. Where nothing can cancel, it never ends, and it warns.
   - Waiting on your own request is incidental (§2.6). It waits for the group, so it can't keep the group alive.

   Be honest about where level 3 earns its keep:
   - `select` is already a standard wait, so naming your *own* request in a select adds nothing.
   - The request is needed when cancellation has to cross between tasks through data: a caller puts `task.cancel_request` into a job, and a long-lived worker watches it (program 08).
   - The worker's `match select(@codec.finished @job.cancel.wait)` tells the two cancellations apart only with batch 7's source-qualified arm, `<job.cancel.Canceled>`. `select`'s exact signature (spreads, the four-wait limit, `Waitable<R>`) is still open, so the example uses only what batch 7 decided.
   - Handing a request to a foreign wait (an FFI poll) would need a native handle member. No program needed one, so none is proposed.
   - `check_cancel` still reads right beside `cancel_request`: "check the cancel request". Beside `cancellation` it reads less well. Beside `stop_request` it doesn't match (stop vs cancel), so that candidate goes in the cold read only as a control.

### 2.6 Incidental work

- **The rule.** An item keeps its group alive unless it is *incidental*. An item is incidental in two cases:
  - its statement is prefixed with `$incidental` (Q2), which covers the whole item;
  - it is parked in an incidental wait: a statement prefixed with `$incidental` inside any function, as in the standard library's signal waits, or a wait on its own request.

  Once every unfinished item of a group is incidental, the group closes their requests, joins them, and drops their `Canceled`, keeping any cleanup failures (§2.4).
  - An item with an event pending isn't parked, so it runs its handler first.
  - An item is parked incidentally only if all of its live activity is, including race or `within` children it owns.
  - A nested group counts as one wait in the outer group.
- **The signal rule becomes an instance of it.**
  - In `@lib/std/signals.dewy`, `next` prefixes its runtime wait with `$incidental`. Batch 9's "once only signal listeners remain, their sources close and the loops end" is then exactly this rule.
  - The closure reaches a parked listener as its group's `Canceled`, so `Closed<E>` disappears from signal results. `signals.sighup.next` is `Signal` where nothing can cancel it.
  - Iteration ends as it does on any cancellation (Q4).
  - A notification already pending still runs, because its listener isn't parked. That matches today's "closure preserves one pending notification".
  - With no group there is nothing to close, so a plain signal-service loop in `main` runs forever, as today.
- **The signal proposal's counterexamples go away.** A timer or ticker loop marked `$incidental` no longer keeps its group alive (program 12, compared with the signals proposal's programs 26 and 27), and done channels for spinners and status lines go.
- **Diagnostics.**
  - Every item incidental: error, "the block would cancel them as soon as it starts".
  - `$incidental` where no group can be (code nothing can cancel): warning, "nothing to keep alive here".
  - An incidental item binding a name that is read after the block: error.
- **Spawned tasks** put the tag inside their body: `group.spawn(() => { $incidental heartbeat() })`.
- **No separate "is the real work done?" check is needed.**
  - An incidental CPU loop uses `check_cancel()`, because ending incidental work closes its request.
  - An item that wants to tidy up handles the `Canceled` from its wait. Program 05's spinner clears its line.
  - What an item can't tell is whether it ended because the work finished or because a sibling failed. No program needed that, and the code after the block knows.
- **Why a metatag.**
  - It changes no type, because every item is already cancellable.
  - It prefixes what it attaches to (batch 8).
  - One tag covers block items, waits inside helpers (signals) and spawned task bodies.
  - Metatags already steer run-time behaviour of constructs (`$parallel.*`, `$clamp`).
- **Alternatives weighed.**
  - A library call, `task.incidental(@spin("counting"))`: it works, but every block item would need a handle or a lambda (`task.incidental(() => { … })`), and the signal library would need the same call around its wait.
  - `race(@count_lines(path) @spin("counting"))`: no new mechanism for one job and one spinner, but a spinner failure wins the race and cancels the job, and it doesn't extend to several items or to signals.

### 2.7 Ctrl-C

- **No handler.** With no intercepting wait attached, Ctrl-C keeps the OS default: the process ends at once without cleanup. A shell sees 130 (killed by SIGINT); on Windows the status is `STATUS_CONTROL_C_EXIT`. This is what LANGUAGE.md line 3833 already says for before attachment, now made the whole rule.
- **A handler.** `loop _ in signals.ctrl_c { …; return }` is written as a `parallel` item.
  - The first wait attaches it, and it intercepts until its block ends.
  - Its `return` ends the group and cancels the other items.
  - Its wait is incidental, so the loop also ends when the work does.
  - To run code after the work stops, put the block in a small function, as program 02 does: the handler's `return` leaves that function, not `main`.
- **Observers.** `.observe` never asks for cancellation, so LANGUAGE.md's "an attached Ctrl-C observer without an interceptor requests root cancellation and exits 130" goes. An observer sees a press only if the process survives it, which means another owner intercepts it.
- **Emergency exit.** Three presses within a second still force an exit while a handler intercepts, so a stuck handler can't make a program unkillable.
- **Exit status after a handled press.** The program chooses: `return` exits 0, and `exit(130)` reports the interruption. Dying by a re-raised SIGINT, so that shells stop their loops, is a runtime detail for the signals work.
- **The cost of David's default.** A program with no handler loses buffered output and leaves temporary files when it is killed. Atomic writes keep the old file. Raw terminal mode with `signals=false` gets byte 3 instead of being killed. This matches C, Go and Rust, but not Python, which runs `finally` on KeyboardInterrupt.

### 2.8 The two exceptions, and why they are unavoidable

**1. The request travels implicitly through calls.**

- Cancellation belongs to the running task, as its stack does. Every wait runs in exactly one task, and that task's group is the only thing that can stop it.
- An explicit parameter (Go's `ctx`) colours every function that might wait, transitively. When a deep helper starts waiting, every signature above it changes. That is the async colouring Dewy rejected for waiting itself.
- An explicit parameter is also easy to lose. A helper that calls `context.Background()` or `context.TODO()` silently cuts cancellation off, a well-known class of Go bug. Implicit travel through calls can't be lost.
- Implicit travel hides no control flow. The inference shows in types exactly where cancellation arrives, and a function still leaves only where its source says.
- The request becomes explicit where the call structure can't carry it: between tasks, through data (`task.cancel_request`).

**2. Cleanup is shielded.**

- A closed request stays closed. Without the shield, every flush and close in a canceled task would fail with `Canceled` at once, which is exactly when cleanup matters.
- Shielding is not a new mechanism: cleanup runs under `protect_from_cancel` with the grace deadline, so it can't make a task unkillable.

### 2.9 What the programmer sees

| Where | Hover or diagnostic |
|---|---|
| A wait in code nothing can cancel | `sleep(10s): void` |
| A wait in cancellable code | `void \| Canceled — canceled when race (line 7) has a winner`: it names the group that can cancel it |
| A `parallel` item where nothing can leave early | `\| Canceled`, with "nothing in this block can cancel it now: no item leaves early and none is incidental" |
| A function used in both contexts | both results, and the call sites: "+ Canceled at lines 15, 16 (parallel items); not at line 13 (main)" |
| `or_throw` on a result with no failure | warning, when no instance needs it: "count_lines gives void; this or_throw forwards nothing" |
| `check_cancel()` or `<Canceled>` arms where nothing can cancel | warning: "nothing can cancel this" (only when no instance needs it) |
| A `within`, `race` or `first_ok` item with no cancellation point | warning: "nothing in count_primes notices the deadline; it runs to the end. Add check_cancel() in its loop" |
| A `parallel` item that ends only when canceled, in a block where nothing can cancel it | warning: "this block never ends: spin stops only when canceled, and nothing here cancels it. Mark it `$incidental`?" |
| A `??` that can consume `Canceled` falling back round a loop | the closed-source progress rule (§3, D42 Q2) |
| `$explicit_cancellation` | only in cancellable instances (§3, D42 Q3) |
| `$incidental` misuse | §2.6 |
| A written `\| Canceled` in a result (under Q1) | warning in code nothing can cancel: "Canceled is added where cancellable; written here it forces callers to handle one that can't happen" |

### 2.10 Cost

**Compile time.**

- The analysis is demand-driven. If no group construct is reachable from the entry, it does nothing. That covers the compiler's own self-build, the flagship panel and most CLIs, so the panel cost is zero by construction. A demanded run must still show its cost on the flagship panel before landing.
- Otherwise it seeds "cancellable" at each group call site and propagates it over the call graph. Each function enters the cancellable set at most once: O(F_c + E_c), counting the functions and call edges reachable from groups.
- Types carry one flag per inferred result, "context `Canceled`". A body is checked once, with the flag symbolic, rather than twice. Only the checks whose outcome depends on the flag run per existing instance, so at most twice: exhaustive matches, `:>` annotations, `$explicit_cancellation` and the warnings above.
- Memory is O(F + E_c), for each function's set of contexts plus the group sites that hover lists.
- An edit that changes a call site's context re-propagates only what can be reached from that site.

**Code size and run time.**

- One body per function. The cancellable body is also correct where nothing can cancel, because the root request never closes. Such a wait compares one pointer with the root's sentinel and skips registering on it. Callers that can't be canceled ignore the `Canceled` tag statically.
- So "compiled once per context" holds for types and diagnostics, and machine code is emitted once. A specialized copy for the non-cancellable context is an optional optimization within the inliner's budget, and `explain` lists any such copies.
- No warning is needed, because nothing doubles unless the optimizer chooses to. Had both copies always been emitted, the cost would be the size of the functions reached from both contexts: 4 of the 39 functions in these programs (`load_config`, `retry`, `count_primes`, `is_prime`).
- At run time, a wait in code nothing can cancel costs one comparison, and cancellable waits cost what they cost today.

### 2.11 Unchanged

- C3: errors stay per-item values unless an item uses `or_throw`.
- Batch 10: `??` and `or_throw` treat `Canceled` like any other failure, and `??<~Canceled>` defaults every failure except cancellation.
- `select` matches arms by type and allows source-qualified arms.
- The meanings of `race`, `first_ok` and `within`.
- `protect_from_cancel` (D41 Q2). Its use moves from "after Ctrl-C" to "after its group cancels it" (§3).

## 3. Knock-on edits

**D41** (title unchanged)
- *Intro*, replacing "Ctrl-C, or a failing sibling in a `parallel` block, cancels work. Waits (channels, `sleep`, signals) notice it on their own.":

  > A group cancels its unfinished work when it ends early: `race` or `first_ok` has its answer, a `parallel` item leaves the function, a `within` deadline passes, or only incidental work is left. Waits notice on their own. Ctrl-C cancels only through a `loop _ in signals.ctrl_c` item; with none, it ends the process.
- *Q1*: the example runs under a deadline. The comment changes from "stops here once Ctrl-C arrives" to "stops here once its group cancels it":
  ```dewy
  count_primes = (limit:int) => { loop n in [2..limit) { check_cancel() or_throw; … } }
  let n = within(3s @count_primes(1_000_000_000))   # int | Timeout
  ```
  Add: "Where nothing can cancel the loop, `check_cancel()` warns."
- *Q2*: retitle it "Finishing work after its group cancels it". After cancellation every wait returns `Canceled` at once (the request stays closed), so a canceled item that must still say goodbye protects that step:
  ```dewy
  chat = (conn:Conn) => {
      loop line in conn.lines show(line)                          # ends when the group cancels chat
      protect_from_cancel(1s @conn.send_text("bye\n")) ?? void    # runs on a fresh request, up to 1 s
  }
  ```
  Delete "After Ctrl-C, `save` still runs, for up to 5 s, then the program exits with 130". A save on Ctrl-C now belongs in the handler, which nothing has canceled (program 02).
- *Q3*: add "The body and every spawned task are cancellable. When one fails, the others are canceled and their `Canceled` is dropped."

**D42**
- *Q1*: the `poll` example gains the comment "`poll` runs as a parallel item". Where nothing can cancel it, `??<~Canceled>` is just `??`.
- *Q2*: withdraw it.
  - Where nothing can cancel, there's no `Canceled` to spin on.
  - In cancellable code, a closed request is a closed source, and LANGUAGE.md's existing `select` rule ("every arm that can take a close must advance that wait") covers it once that rule also applies to a `??` fallback on a wait inside a loop.
  - The extension also catches today's `jobs.receive ?? continue` spinning on a closed channel. Natural extension, flagged.
- *Q3*: new text:

  > Under `$explicit_cancellation` (in `$bulletproof`), in cancellable code, a handler that can consume `Canceled` must name it, as `??<~Canceled>` or `??<Canceled | …>`. Where nothing can cancel, there is no `Canceled` to name, so the tag asks nothing.

  The example becomes `ask` called as a parallel item.
- *Q7*: replace the example. Ctrl-C no longer reaches `main` as `Canceled`:
  - With no handler, the process ends.
  - With a handler, the group consumes the `Canceled` and keeps `AfterCancel<FileCloseFailed>`.

  New example: `save_frames(frames p"capture.bin") or_throw   # a write fails, then the close fails: FileWriteFailed & FileCloseFailed`. The reason for "highest code" ("a cancellation (130) outranks the cleanup failures it caused") is gone. The better reason now favours the *lowest* code: codes follow `main`'s declared error order, so the kind listed first wins. That is a reversal for David to weigh.

**D40**
- There is no Ctrl-C example in D40 as it stands (checked). The only "Ctrl-C, then save" examples are D41 Q2 and D42 Q7, both above. Q5's "Timing here covers every ordinary result, including errors and cancellation" stays true in cancellable code.

**D10 and D11 program comments**
- Line 533, "Ctrl-C still stops (D4)", and line 655, "Ctrl-C still stops", become "Ctrl-C ends the program".

**decisions.md** (when David decides)
- One entry superseding three things:
  - batch 4's Ctrl-C clause;
  - batch 9's "their sources close", which becomes "the group cancels its incidental work";
  - the v5 proposal's `.wait()` reporting.

**LANGUAGE.md** (when implemented)
- 277–278: delete "A `Canceled` contribution leaves the enclosing function… never collected". It has been stale since batch 10.
- 3581, 4158–4159: drop `| Canceled` from the written results (Q1).
- 3633–3641: replace the level-triggered rule with §2.1. "include it in their result type" becomes "in cancellable code".
- 3642–3655: `within` maps its own deadline to `Timeout`; groups consume the `Canceled` they cause (§2.3).
- 3656–3659: keep "travel implicitly through calls", with §2.8's reason. Replace "checking a blocking operation such as `sleep(0ns)`" with `check_cancel()`. Shielding is `protect_from_cancel(grace …)`.
- 3663–3664: "A `Canceled` from a wait never reaches `main`: the group that caused it consumes it."
- 3666–3675: replace with D42 Q3's new text.
- 3725–3730, 3744, 3761–3763: in cancellable code; a canceled send gives `Canceled`; drop `Canceled` from `Unsent`'s reasons.
- 3770: `Tick`, plus `Canceled` in cancellable code.
- 3784: delete the `<Canceled> => break` arm in that `main`, which would now warn.
- 3805–3858 (signals):
  - `next` gives `E` (+ `Canceled`), with no `Closed<E>`;
  - delete the observer's root-cancellation sentence (3830–3833);
  - restate the closure paragraphs (3838–3852) as the incidental rule;
  - "a timer loop … can keep a group alive" gains "unless it is `$incidental`".
- 3863: "plus `Canceled`" becomes "plus `Canceled` in cancellable code".
- 3966–3973: Q4.

**Library and proposal text**
- `lib/std/signals.dewy`:
  - `next` drops `Closed<E>` and the written `| Canceled`;
  - its wait gains `$incidental`;
  - `if code =? 2 return Canceled` forwards the runtime primitive's own `Canceled`.
- The v5 proposal's `.wait()` paragraph follows §2.3.

## 4. Questions for David

Names in Q2, Q3 and Q5 are not yet cold-read. The kit is `names.txt`, ready for the coordinator. The design was dogfooded on 13 programs (`dogfood-round1.md`); the lowest grade is 3.

### Q1 (a). A written result type doesn't mention context cancellation

```dewy
transfer = (src:Mutex<int64> dst:Mutex<int64> amount:int64):>void | DuplicateLock => {
    let [a b] = @(lock_all(src dst)) or_throw   # in a parallel item: void | DuplicateLock | Canceled
    a -= amount                                  # called from main: void | DuplicateLock
    b += amount
}
```

Should a written result type leave out the `Canceled` that comes from cancellable contexts, with the compiler adding it where the function is cancellable? A written `| Canceled` would then mean one the function makes itself.

- **Rec:** yes. Otherwise an annotation either breaks in cancellable code or forces every non-cancellable caller to handle a `Canceled` that can't happen.
- This changes "an annotation fixes the error set" for this one member, which is the result-type shadow of waiting, and waiting is inferred rather than written. Hover shows the member.
- **Reversible** before release.

### Q2 (b). Marking incidental work

```dewy
main = () => parallel {
    $incidental spin("counting")     # canceled once only incidental work is left
    count_lines(p"big.txt")
}
```

Should a metatag prefixing an item or statement mean "while this runs, it doesn't keep its group alive", with the group cancelling what's left once only incidental work remains? The signal rule from batch 9 becomes its instance.

- **Rec:** yes, spelled `$incidental`, pending the cold read. The other candidates are in `names.txt`. The library call `task.incidental(@work)` is the alternative.
- **Reversible:** the spelling, freely. The rule, before release.

### Q3 (c). The cancel request's name

```dewy
jobs.send(Job[path reply task.cancel_request]) or_throw     # caller
match select(@codec.finished @job.cancel.wait) {            # worker
    <job.cancel.Canceled> => codec.abort()
    <Canceled> => break
}
```

- **Rec:** `task.cancel_request`, of type `task.CancelRequest`, with `.wait`. The other candidates are in `names.txt`.
- `check_cancel()` stays beside it.
- **Reversible.**

### Q4 (a). Plain iteration over a source ends at cancellation

```dewy
loop job in jobs { process(job) }     # canceled: the loop ends; no Canceled item
loop job in jobs or_throw { … }       # canceled: leaves the function with Canceled
```

Should iterating any source (channels, `merged` inboxes, signals) end when canceled instead of yielding one `Canceled` item, as signal iteration already does?

- Today LANGUAGE.md (line 3967) gives a `merged` loop one `Canceled` item, so `loop _ in signals.ctrl_c { save(); return }` would run its body on cancellation if signals worked that way.
- **Rec:** yes.
- **Reversible** before release.

### Q5 (b). A canceled loser's cleanup failure comes back wrapped

```dewy
match race(@write_backup(p"/mnt/a" data) @write_backup(p"/mnt/b" data)) {
    <void> => printl"backed up"
    both:FileError & AfterCancel<FileCloseFailed> => printl"backup failed, and so did the other close"
    lost:AfterCancel<FileCloseFailed> => printl"backed up; the other copy failed to close: {lost.failure}"
    problem:error => printl("backup failed: {problem}" file=stderr)
}
```

Should a failure kept from work whose result the group dropped come back as `AfterCancel<E>`, so it can't be mistaken for the winner's own `E`? This covers race and `first_ok` losers, and the siblings of an item that is leaving.

- **Rec:** yes, name pending the cold read. Without it, telling the two apart needs `$origin` (D42 Q8), and a failed winner can be reported as "backed up".
- **Reversible** before release.
