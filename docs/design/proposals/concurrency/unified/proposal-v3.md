# One `parallel`, v3 (2026-11-07)

Revises `docs/design/proposals/concurrency/unified/proposal-v2.md` using David's D4 feedback. Already approved and unchanged here: the three shapes, `tasks`, the removals, C1 (items may wait, including on each other, with the strategy inferred), C8 and C10.

## BLUF

- **Block form: David's version.** Every top-level statement in `parallel { … }` is an item. An item that uses data an earlier item produces waits for it; the compiler builds the dependency graph. Values come out as they would sequentially. Only effects that go through shared handles (channels, files, the terminal) can interleave. Two confusion cases remain (§3). The worst one is reported by the existing channel analysis; the other two show in hover and `explain`.
- **`x ?? void` filters failures out anywhere.** It's allowed exactly where an `if` without `else` may give no value: collectors, comprehension bodies and statements. In a place that needs one value it's an error with fix-its. It needs no new rule beyond multi-expressions, but it doesn't work today (tested).
- **`or_throw` leaves the function** (agreed with David). Leaving cancels and joins the siblings, because nothing outlives its construct. For fail-fast over just one part, put that part in a small named function.
- **Cancellation:** compute-only `parallel` runs to completion by default. **`check_cancel or_throw`** in a body opts in to stopping early, taken from Zig's `checkCancel`. Ctrl-C cancels `main`; a second Ctrl-C ends the process at once.
- **`select` takes function handles and keyword arguments:** `select(command=@commands.receive message=@chat.receive timeout=1s)`. The argument names tag the result, so `.receiving`, `.sending`, `Op<T>`, `timeout(d)` and `.then` are all gone.
- **`Tasks` stays a distinct type.** It owns lifetimes; it is not a container of task handles.
- **Metatags move into four namespaces:**
  - `$parallel.*` for scoped tuning;
  - `$placement.*` for device and cores;
  - `$storage.layout`;
  - `$limits.*` for program-wide limits such as one core.
- **Ranges are never turned into arrays.** A parameter that only loops takes `Iterable<T>`. A range doesn't satisfy `array<int>`, and shouldn't.
- **`$parallel_safe`: delete it.** Inference covers it, and what's left of its meaning is race freedom.

## 1. What changed from v2

| v2 | v3 |
|---|---|
| Block items are `let` or `{…}`; reading another item's `let` is an error | Every statement is an item; reading an earlier item's data waits (§3) |
| No way to drop failures | `x ?? void`, a general rule (§4) |
| C4 (c): stop only where the type already has `Canceled` (found unstable) | Run to completion; `check_cancel` opts in (§5) |
| `ch.receiving`, `Op<T>`, `timeout(d)`, `op.then(f)` | `select(name=@ch.receive … timeout=d)` (§6) |
| `$window`, `$grain`, `$cores`, … | Namespaced (§8) |
| `sum(xs 'tree')` | `sum(xs order='tree')` |
| `$parallel_safe` narrowed | Deleted (§10) |
| — | Ctrl-C: the first cancels, a second ends the process |
| — | `[parallel …]` collects like `[loop …]`. Today a block body gives `[[1] [] [3]]` where `loop` gives `[1 3]` (tested) |

## 2. The revised model

- **One meaning:** the items start together, and the construct ends when they've all ended. Any interleaving is a legal run.
- **The strategy is inferred** (C1, approved): a chunked pool, a bounded window or a task per item. Hover and `explain` show which.
- **Three ways to treat a failing item, each one word:**
  - keep it as a value (the default);
  - drop it with `?? void`;
  - substitute a default with `?? d`;
  - abort with `or_throw`.
- **`or_throw` means leaving the function, as everywhere else.** Leaving a function that still has items running means canceling and joining them first. Fail-fast isn't a separate rule; it follows from structured lifetimes.
  - **Scoped fail-fast:** a named local function gives the abort a smaller scope.

```dewy
Invalid:type = type of error
parse_age = (text:string):>int | Invalid => {
    let n = to_int(text)
    if n is? error return Invalid
    n
}
main = () => {
    let texts = ["31" "abc" "45"]
    all_or_nothing = () => [parallel t in texts parse_age(t) or_throw]
    let ages = all_or_nothing                         # array<int> | Invalid; main continues
    match ages {
        a:array<int> => printl"ages {a}"
        e:Invalid => printl"one entry was not a number"
    }
}
```

- Results keep input order. Reductions keep sequential order, except under a proven associative operator or `order='tree'`.

## 3. The block form

### The rule

- **Every top-level statement is an item.** A `{ … }` group is one item and runs in order inside, as braces do everywhere.
- **An item waits for an earlier item when:**
  - it reads a binding that the earlier item declares; or
  - both touch the same variable, field or element, and at least one of them writes it. This uses the same disjointness analysis as `@x`.
- **Handles create no wait.** Channels, queues, `Atomic`, `Mutex`, files, the terminal and the network are how items talk to each other, so items that share a handle run together.
- **Promise:** every value comes out as the sequential block would compute it. Only effects through handles and the outside world may interleave.
- **Where bindings are visible:**
  - `let` items are visible to later items, which wait for them, and after the block.
  - Reading a later item's binding is an error, as it is in sequential code.
  - Edges only point forward, so the graph can't have a cycle.
- **Failure:** an item's `or_throw` cancels the items still running, never starts the ones waiting on it, joins everything and leaves the function.
- **What you can see:** hover over `parallel` and `explain` draw the graph, e.g. "4 items, 2 start at once; `map` waits for `config`". A note appears when the edges chain every item ("these run one after another: each writes `total`").
- **Value:** the block gives what its items give, in source order, as any block does (multi-expressions). This is a natural extension, flagged.

```dewy
Config:type = [root:string]
load_config = () => {
    sleep(20ms) or_throw                             # stands in for reading a file
    Config["assets"]
}
load_map = (c:Config) => {
    sleep(50ms) or_throw
    "{c.root}/map"
}
load_sprites = (c:Config) => {
    sleep(40ms) or_throw
    "{c.root}/sprites"
}
load_sounds = () => {
    sleep(30ms) or_throw
    "sounds"
}
main = () => {
    parallel {
        let config = load_config or_throw            # starts at once
        let map = load_map(config) or_throw          # waits for config
        let sprites = load_sprites(config) or_throw  # waits for config, then runs beside map
        let sounds = load_sounds or_throw            # starts at once
    }
    printl"{map} {sprites} {sounds}"                 # after every item ends: about 70 ms in all
}
```

- **Both tests pass.** You write the steps in order and the compiler finds the overlap. To force an order, use the earlier result, wrap the steps in `{ }`, or move one after the block.

### Where it can confuse (the honest cases)

**Case 1: an effect with no data link runs immediately.**

```dewy
show_progress = (config:Config) => {
    parallel {
        printl"loading…"                              # item 1
        let map = load_map(config) or_throw           # item 2
        printl"done"                                  # item 3: uses nothing above, so it starts at once
    }
}
```

- "done" can print first, because nothing ties it to `map`. Hover shows "item 3 waits for nothing".
- **The fix:** `printl"done: {map}"`, or move the line after the block.
- **No error:** an independent `play_music` in that spot is exactly what `parallel` is for, and the compiler can't tell the two apart.

**Case 2: an order that is a protocol, not data.**

```dewy
sum_numbers = () => {
    let numbers = channel<int>(16)
    let total = 0
    parallel {
        loop i in [0..100) { numbers.send(i) or_throw }   # item 1: producer
        numbers.close                                    # item 2: shares only a handle, so it runs at once
        loop n in numbers { total += n } or_throw        # item 3: consumer
    }
    total
}
```

- `close` can run before the sends, which then fail with `Unsent(Closed)`.
- **How it surfaces:** the channel analysis already walks each item's waits. A `close` not ordered after another item's sends on the same channel is an error naming both, with the fix-it "put item 2 in item 1's `{ }`".

**Case 3: setup through the outside world.**

```dewy
save_then_load = () => {
    parallel {
        write_file(p"volume.txt" "3") or_throw           # item 1
        let text = read_file(p"volume.txt") or_throw     # item 2: may read the old file
    }
    text
}
```

- The file system is invisible to the graph, so there's no diagnostic. **The fix:** `{ }` around both.
- **v2 had the same hole:** its rule only demanded `{ write_file(…) }`, which races the same way.
- For a database or server, pass the handle along (`let db = open_db`, then `query(db)`), and the binding creates the wait.

**Case 4: silent serialization.** `total += slow_a` and then `total += slow_b` both write `total`, so the second waits. The result is correct, and hover notes the chain. **The fix:** `let a = slow_a`, `let b = slow_b`, then `total += a + b` after the block.

**Verdict:** adopt David's rule.
- Case 1 is what `parallel` means.
- Case 2, the common real bug, gets an error.
- Case 3 is the price of having an outside world, and v2 paid it too.
- Case 4 is only slow, and gets a note.

## 4. Filtering with `?? void` (a general rule)

- **Meaning:** `x ?? void` gives `x`'s success value, or **no value** when `x` is an error or `none`. `x ??<E> void` drops only error type `E`.
- **Where it's allowed:** exactly where `if ok x` without `else` may give no value (multi-expressions), so it adds no new context rule.

| Context | `x ?? void` | Why it's coherent (or not) |
|---|---|---|
| A collector element, comprehension body or loop capture (`[…]`, `[loop …]`, `[parallel …]`) | Keeps the value or drops it | A collector takes 0..n values per element |
| A statement in a body, or a `parallel x in xs { … }` body | Discards the failure | Like the attached `;`, but only for the failure |
| A one-value place: an operand, an argument, an index, a condition, `let a =`, or a written `:>T` result | **Error** | Nothing would fill the place. Fix-its: `?? default`, `?? none` (gives an optional), `or_throw`, `match` |
| A function body with no written result | **Error** (provisional) | `f = (n) => check(n) ?? void` would quietly change `f`'s count to vary. Write the filter at the collector |

```dewy
Invalid:type = type of error
parse_age = (text:string):>int | Invalid => {
    let n = to_int(text)
    if n is? error return Invalid
    n
}
main = () => {
    let texts = ["31" "abc" "45"]
    let ages = [parallel t in texts parse_age(t) ?? void]   # [31 45]
    let each = [parallel t in texts parse_age(t)]           # [31 Invalid 45]
    let zeros = [loop t in texts parse_age(t) ?? 0]         # [31 0 45]
    printl"{ages} {each} {zeros}"
}
```

- **Today** (tested in `~/dev/tmp/design-1107/scratch/`): `?? void` is rejected, and `[parallel …]` with a filtered block body nests (`[[1] [] [3]]`).
- **To build:**
  - `void` accepted on the right of `??`;
  - `[parallel …]` following the collector rule, with per-chunk buffers and an ordered concatenation so filtered results keep input order.
- **Both tests pass:** dropping failures takes one word, and the error in a one-value place names the alternatives.

## 5. Cancellation

### C4: the default and the opt-in

- **Default:** a compute-only `parallel` runs to completion when canceled from outside, and its type gains no `Canceled`. A sibling's `or_throw` still stops new chunks.
- **Opt-in:** `check_cancel or_throw` in a body.
  - `check_cancel` is a pure cancellation point: it gives `void | Canceled` and does nothing else.
  - `Canceled` enters the type by the ordinary `or_throw` rule.
  - The compiler may check once per chunk, since which items ran before a cancel depends on scheduling anyway.
  - It works the same in a plain `loop`.
- **Ranges:** pass the range directly. `[parallel i in [0..n) …]` splits it arithmetically and builds no array (§9).

```dewy
score = (n:int):>int => {
    let s = 0
    loop k in [0..n) { s += (k * k) % 7 }
    s
}
total = (n:int) => sum([parallel i in [0..n) score(i)])        # int: always finishes
total_or_stop = (n:int) => sum([parallel i in [0..n) {
    check_cancel or_throw                                       # opt in: stop when canceled
    score(i)
}])                                                             # int | Canceled
main = () => {
    let full = total(2000)                                      # int
    let quick = within(10ms @total_or_stop(200000))             # int | Timeout
    printl"{full} {quick}"
}
```

- **Ctrl-C** (the "can't kill it" pain), taken and flagged:
  - The first Ctrl-C cancels `main`'s scope: waits give `Canceled`, cleanup runs, and the program exits with a report.
  - A second Ctrl-C, or the grace deadline running out, ends the process at once and reports that cleanup was skipped.
- **Both tests pass:** callers see no `Canceled` they didn't ask for, Ctrl-C always works, and one line makes a computation stoppable.

### Zig's design and what we take

**Sources:**
- Andrew Kelley, "Zig's New Async I/O (Text Version)", 2025-10-29: <https://andrewkelley.me/post/zig-new-async-io-text-version.html>
- `lib/std/Io.zig` on Codeberg master, read 2026-11-07: <https://codeberg.org/ziglang/zig/src/branch/master/lib/std/Io.zig>
- Issues [#31340](https://codeberg.org/ziglang/zig/issues/31340) and [#35564](https://codeberg.org/ziglang/zig/issues/35564)
- Forum thread: <https://ziggit.dev/t/canceling-awaited-future-group-etc-is-impossible/15466>

**Zig's design (quotes are from the source's doc comments):**

- `io.async(f, args)` "*may*" run `f` before returning. `io.concurrent` guarantees a unit of concurrency, or fails with `error.ConcurrencyUnavailable`.
- `future.cancel(io)` is "equivalent to `await` but places a cancelation request". The task gets `error.Canceled` at its next cancelation point, meaning any `Io` call whose error set includes `Canceled`.
  - Both calls are idempotent.
  - The idiom is `defer future.cancel(io)`, and `cancel` returns the result so the deferred call can free it.
- **Edge-triggered:** "only the next cancelation point… will return `error.Canceled`". Ignoring it is "usually a bug", and `recancel` re-arms the request.
- `CancelProtection` blocks cancelation for a region. `checkCancel` is "a pure cancelation point". `Queue` has `putUncancelable`.
- `Group` is "an unordered set of tasks which can only be awaited or canceled as a whole". `Select` waits for one of several tasks and cancels the rest.
- **The edge-triggered rule is fragile:**
  - #31340 asks for easier debugging of "dropped acknowledged cancelations".
  - #35564 reports `Condition.wait` swallowing `Canceled`.

**Point by point:**

| Point | Zig | Here | Take |
|---|---|---|---|
| Inline or concurrent | The caller picks `async` or `concurrent` | Inferred; a target that can't park gets a compile-time diagnostic | Keep ours |
| Cleanup on every exit | `defer future.cancel(io)`, written by hand | Leaving a construct cancels and joins | Keep ours: it can't be forgotten |
| Edge or level | Edge, plus `recancel` | Level | Keep ours: it prevents both open issues |
| Pure check | `checkCancel` | Missing | **Adopt** as `check_cancel` |
| Protected region | `CancelProtection` | Shielded `defer` | Revisit only if a program needs it |
| Groups | `Group` | `tasks` | Same idea |
| First of several | `Select` over tasks | `race` over calls, `select` over channel operations | Same split |

**Couldn't verify:**
- A talk called "Getting Cancelled": searches found nothing by that title, so this summary comes from the source and the post.
- Whether the 0.16 release matches Codeberg master.
- How `Batch` works over lower-level operations.
- The forum's claim that a future can't be both awaited and canceled (second-hand).

## 6. `select`

### What it is, in plain words

- `select` waits on several channel operations and **performs exactly one**, the first that can proceed.
  - A losing receive takes nothing, and a losing send delivers nothing.
  - You `match` on which one happened.
- **Operations are passed as function handles, as `within` and `race` already take calls:**
  - `@inbox.receive` is "receive from `inbox`", not yet done. Without the `@`, `inbox.receive` would wait right there.
  - `@out.send("ping")` is the same for a send.
- **`Op<T>` is gone.** In v2 it was the type of such a not-yet-done operation; now that is just a handle.
  - Only handles to `Channel`, `mpmc` or `spsc` operations are accepted.
  - Any other handle is an error that points to `race`.

### Signature

```dewy
select(...waits ... timeout:Duration | none = none  ties:'fair' | 'first' = 'fair')
```

- **`waits`**, positional or named:
  - A positional wait adds its result: `T | Closed` for a receive, `Sent | Unsent<T>` for a send. `Sent` exists because `void` can't be matched.
  - A **named** wait `name=@ch.receive` adds a one-field record `[name: its result]`, so the name tags the result.
- **`timeout`** (keyword-only, default: wait forever) adds `Timeout`.
- **`ties`** (keyword-only): `'fair'`, the default, picks at random among ready operations and is seeded in tests. `'first'` prefers earlier arguments and can starve later ones.
- **`Canceled`** is always in the result, since `select` is a wait.
- **Rule:** two positional waits whose results overlap are an error with a fix-it: "both can give `Closed`; name them: `select(a=… b=…)`".
- **Implementation:**
  - The signature needs typed rest parameters, which are not built yet. They are a general primitive, so `select` needs no special compiler support.
  - Matching on the tagged results works today with named record types (tested, `scratch/s1.dewy`).
  - Unions of anonymous records don't match yet (`s2.dewy`).

### Telling two same-typed channels apart (no callbacks)

```dewy
relay = (commands:Channel<string> chat:Channel<string>) => {
    loop true {
        match select(command=@commands.receive  message=@chat.receive  timeout=1s) {
            [command:string] => printl"command: {command}"
            [message:string] => printl"chat: {message}"
            [command:Closed] => return "commands closed"      # each close is told apart by its name
            [message:Closed] => return "chat closed"
            <Timeout> => printl"idle"
            <Canceled> => return Canceled
        }
    }
}
main = () => {
    let commands = channel<string>(4)
    let chat = channel<string>(4)
    parallel {
        {                                                    # producer: chat messages, then close
            chat.send("hi") or_throw
            chat.send("bye") or_throw
            chat.close
        }
        {                                                    # producer: one command after 50 ms, then close
            sleep(50ms) or_throw
            commands.send("quit") or_throw
            commands.close
        }
        let why = relay(commands chat) or_throw              # consumer: relays until either channel closes
    }
    printl"stopped: {why}"
}
```

- **The short form, for one channel:** `match select(@inbox.receive timeout=1s) { n:int => … <Closed> => … <Timeout> => … <Canceled> => … }`.
- `race(@a @b)` stays for whole calls: it runs them and cancels the losers.
- **Both tests pass:** no new grammar or callbacks. The arguments are named only when you need to tell results apart, and the compile error says so.

## 7. Should `Tasks` be its own type, or `Task[]`?

- **Keep `Tasks` a distinct type.** It is an **owner**, not a container:
  - `tasks(body)` doesn't return until every member has ended;
  - it is a cancel scope (`.cancel`);
  - its first failure cancels the rest.
- **There is no `Task` value.** `.spawn` returns nothing, and results come back through channels or the block form.
- **Task handles in an array** would bring back what structured lifetimes remove: handles dropped without a join, awaited one by one, or moved out of their scope.
- `Tasks` is a copyable handle passed down, as `serve` passes `Service`.

```dewy
autosave = () => {
    loop true {
        sleep(30s) or_throw
        printl"saved"
    }
}
start_autosave = (group:Tasks) => group.spawn(@autosave)    # returns at once; autosave lives in the caller's group
play = () => sleep(2s)
main = () => {
    tasks((group:Tasks) => {
        start_autosave(group)
        play or_throw
        group.cancel                                         # tasks joins autosave, then returns
    }) or_throw
}
```

## 8. Metatag structure and candidate names

**Structure:**
- Scoped settings follow the existing scope rule: they cover a module, a function or a block. To target one construct, wrap it in a block.
- Program-wide limits follow the `$build.mode` precedent: set once, by the main file, at the top level.

| Namespace | Scope | Setting | Candidate names (recommendation first) | Meaning |
|---|---|---|---|---|
| `$parallel` | scope | items in flight | **`$parallel.max_concurrent = 8`**, `$parallel.in_flight`, `$parallel.max_waiting` | The window. Rejected where items may wait on each other |
| | | chunk size | **`$parallel.chunk = 64`**, `$parallel.min_chunk`, `$parallel.grain` | Minimum items per chunk. Results unchanged |
| | | workers | **`$parallel.workers = 2`**, `$parallel.threads` | At most N workers for this scope, within `$limits.cores` |
| | | run in order | **`$parallel = false`**, `$parallel.off`, `$sequential` | Debugging. Rejected where items wait on each other |
| | | scheduler | **`$parallel.scheduler = @my_scheduler`** | Expert leaf |
| `$placement` | scope | device | **`$placement.device = 'gpu'`**, `$place.device`, `$device` | Explicit placement |
| | | cores | **`$placement.cores = [0 1]`** | Pin to these cores |
| `$storage` | declaration | layout | **`$storage.layout = 'soa'`**, `$layout.soa`, `$layout` | Data layout, not concurrency |
| `$limits` | program (main file, once) | cores | **`$limits.cores = 1`**, `$resources.cores`, `$runtime.cores` | "Single core": all work shares one core. Items still interleave at waits |
| | | memory | **`$limits.memory = 512MB`** | Exceeding it follows the allocation policy |
| | | live tasks | **`$limits.tasks = 10000`** | Admission past it follows the allocation policy (C9). It never waits, so it can't deadlock siblings |

- **Combining:** `$limits.*` caps every scope, and a scoped setting above a limit is an error naming both. `$limits.cores = 1` still allows items that wait on each other, since a parked task releases the core.
- **Not metatags:**
  - Float sum order is a keyword-only argument with a default, following the discussion-points convention: `sum(xs order='tree')`, default `'sequential'`.
  - `& no blocks` stays the way to lock out waiting.

## 9. Ranges and an `Iterable` type

- **Today:**
  - `IntRange` is a lazy stored range.
  - Records with `length` and `__index__` loop as indexed sequences.
  - Iterators with `next` are provisional.
  - No type means "anything a loop visits".
  - Tested: an `xs:array<int>` parameter rejects `[0..5)` ("found IntRange"). An untyped `xs`, or `r:IntRange`, works.
- **How `parallel` splits its source:**
  - Indexed sources are split into chunks by position.
  - A range is split arithmetically and never built into an array.
  - Iterators and receivers feed the window one item at a time.
- **A range shouldn't satisfy `array<int>`:** it has no storage, `push` or element writes.
- **Add `Iterable<T>`:**
  - It is satisfied by anything `loop x in` accepts, and is structural.
  - Generic instances keep each source's fast path, so a range stays a range.

```dewy
heavy = (xs:Iterable<int>) => [parallel x in xs x*x]
main = () => {
    let a = heavy([0..1000000))                          # range: split arithmetically, no array built
    let b = heavy([3 1 4])                               # array: split by position
    printl"{a.length} {b}"
}
```

- **Deferred:** `Sequence<T>` (length plus position), added when a program needs indexing through a parameter. The discussion points already sketch `sequence<T> | iterable<T>`.

## 10. C7, C9 and C11, rewritten as plain questions

**C7. When a loop reads from a channel and the program is canceled partway through, should the loop report it?**

```dewy
sum_all = (numbers:Channel<int>) => {
    let total = 0
    loop n in numbers { total += n } or_throw    # ends normally when numbers is closed
    total
}
```

- If the loop simply stopped on cancel, `sum_all` would return a partial total as if it were complete.
- **Recommendation:** the loop's value is `void` when the channel closes and `Canceled` when canceled, so `or_throw` forwards it and a partial total can't pass for a whole one.
- **Second part:** should `parallel j in jobs { … }` handle at most a fixed number of jobs at once (the window, `$parallel.max_concurrent`) instead of starting a task for every arriving job? **Recommendation:** yes, when the jobs don't wait on each other; otherwise one task per job, with the note from C1.

**C9. If memory runs out while a `parallel` is starting its tasks, what happens?**

```dewy
fetch = (n:int) => {
    sleep(1s) or_throw                           # each item waits, so each needs its own task
    n
}
main = () => {
    let all = [parallel n in [0..50000000) fetch(n)]   # 50 million tasks
    printl"{all.length}"
}
```

- **(a) The same as any allocation:** the program ends with a report. Under `$explicit_allocation_failure`, the construct gives `OutOfMemory`.
- **(b)** Every `parallel` that may start tasks has `OutOfMemory` in its type, so every caller handles it.
- **Recommendation:** (a). `explain` already warns about task-per-item constructs with large counts, and `$limits.tasks` makes the cap explicit.

**C11. Is `$parallel_safe` still needed, and should it be called `$race_free`?**

- **What it checks now:** the callback writes nothing shared (globals, or captures, even through calls), and what it captures or returns can cross threads (`Send`/`Sync`). Both are **race freedom**. The nonblocking part is gone, because items may now wait.
- **The other risks are checked elsewhere:**
  - deadlocks, by the deadlock analysis and `$no_deadlocks`;
  - resources, by `explain`, `$limits` and the allocation policy;
  - panics, by the same policy as sequential code;
  - secrets, by `secret<T>`.
  - Interleaved output is part of the meaning, not a hazard.
  - So "race-free" leaves nothing unsafe unchecked.
- **Deleting it still holds, and more strongly:**
  - Inference records the requirement in the signature and checks every call site.
  - The tag only confirms what inference found.
  - A library newly adding the requirement is a change to its exported signature, which a general check should catch; it doesn't need a concurrency tag.
- **Recommendation:** delete `$parallel_safe`. If kept, name it `$race_free`.

## Examples in the other common shapes

Producer and consumer:

```dewy
main = () => {
    let numbers = channel<int>(16)
    let total = 0
    parallel {
        {                                                  # producer: sends 0..999, then closes
            loop i in [0..1000) { numbers.send(i) or_throw }
            numbers.close
        }
        loop n in numbers { total += n } or_throw          # consumer: adds until the channel closes
    }
    printl"{total}"                                        # 499500
}
```

Worker pool:

```dewy
handle = (job:int) => {
    sleep(5ms) or_throw                                    # stands in for real work that waits
    job * 2
}
main = () => {
    let jobs = channel<int>(64)
    parallel {
        {                                                  # producer: queues 1000 jobs, then closes
            loop j in [0..1000) { jobs.send(j) or_throw }
            jobs.close
        }
        parallel j in jobs {                               # workers: a bounded number of jobs at a time
            let r = handle(j) or_throw
            printl"{r}"
        } or_throw
    }
}
```

Game frame:

```dewy
Particle:type = [x:float64 vx:float64]
World:type = [particles:array<Particle> heat:array<float64> frames:int]
cool = (@heat:array<float64> dt:float64) => {
    parallel @h in heat { h *= 1.0 - dt }                  # each cell changes only itself
}
frame = (@world:World dt:float64):>void & no blocks => {   # `& no blocks`: a compile error if anything here could wait
    parallel {
        parallel @p in world.particles { p.x += p.vx * dt }   # item 1: moves the particles
        cool(@world.heat dt)                                   # item 2: cools the heat grid
    }
    # The two items change different arrays (particles and heat), so neither waits for the other and their order doesn't matter.
    world.frames += 1                                      # runs after both items finish
}
```

## Questions for David (syntax and names only)

Every semantic change above passes both tests and is taken. These are the spellings, each with a recommendation. All are reversible until release.

1. **`check_cancel`**, the pure cancellation point. Alternatives: `cancel_point`, `stop_if_canceled`. **Recommendation:** `check_cancel`.
2. **`select` arguments:**
   - handles (`@ch.receive`, `@ch.send(v)`) instead of `.receiving` and `.sending(v)`;
   - the keyword arguments `timeout=` and `ties='fair' | 'first'` (alternatives `prefer=`, `priority=`);
   - `Sent` as a committed send's result.
   - **Recommendation:** all as written. Removes `Op<T>`, `timeout(d)` and `.then`.
3. **Metatag namespaces** `$parallel`, `$placement`, `$storage` and `$limits`, and the names in §8's table, for cold-reader testing. **Recommendation:** the bold names.
4. **`sum(xs order='tree')`.** Alternatives: `rounding=`, `grouping=`. **Recommendation:** `order`.
5. **`Iterable<T>`**, for "anything a loop visits". Alternatives: `Sequence<T>`, `Loopable<T>`. **Recommendation:** `Iterable<T>` now; `Sequence<T>` later, for positional access.
6. **`$parallel_safe`.** **Recommendation:** delete it. If kept, rename it `$race_free`.
7. **Flagged only, not a question:**
   - Ctrl-C semantics: the first cancels, a second ends the process;
   - a `parallel` block gives its items' values in source order;
   - `?? void` in a function body with no written result is an error.
