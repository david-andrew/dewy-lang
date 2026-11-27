# Concurrency and Parallel Work

> [Generated coverage](/status/#ref-concurrency) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

Dewy has two lanes for work that runs at the same time:

- **`parallel`** splits a calculation across cores. Its body must never wait, so the scheduler is free to run it on any core, or all of it on the caller.
- **`concurrent`** runs tasks that may wait (sleeps, files, processes, channels), each on a thread of its own, and joins them at its closing brace.

Both are checked for data races at compile time: work that runs at the same time cannot change shared state except through atomic handles, channels and other synchronized handles.

Waiting for the first of several events, deadlines, and the helpers that start or end cancellation are still being designed and are not described here.

## `parallel` Loops

`parallel x in xs body` visits an array or a bounded integer range. `[parallel x in xs value]` collects the results in input order, one per element, as a `loop` comprehension does.

<!-- dewy-example: {"mode":"run","stdout":"[0 1 4 9 16 25]\n[1 2 5 10 17 26]\n[2 4 10 20 34 52]\n"} -->
```dewy
let squares = [parallel i in [0..6) i*i]
let shifted = [parallel x in squares x+1]
let saved = shifted
parallel @x in shifted { x *= 2 }
printl(squares)
printl(saved)
printl(shifted)
```

- An ordinary loop binding is read-only. A mutable `@x` binding owns one element for the body, including its managed fields. Saved copies keep their values.
- Other captured variables and globals may be read but not changed, also through called functions.
- Writing a captured array by index is rejected; use the mutable element binding.
- `return`, `break` and `continue` cannot leave a parallel body.
- One named binding over an array or a bounded range is supported. Combined headers, destructuring and filtered collectors are not supported yet.
- Collection keeps source order, so a later `sum` adds in the same order as a sequential loop would. Scheduling never reorders a reduction.

<!-- dewy-example: {"mode":"reject","diagnostic":"must not change 'total', a variable it captured (a data race)"} -->
```dewy
main = () => {
    let total = 0
    parallel i in [0..10) { total += i }
}
```

<!-- dewy-example: {"mode":"reject","diagnostic":"return cannot leave a parallel body"} -->
```dewy
find = () => {
    parallel i in [0..4) { if i =? 2 return }
}
```

### The Body Must Not Wait

A parallel body must be proven nonblocking: sleeps, blocking I/O, channel waits, joins and unclassified foreign calls are rejected, also through called functions. Use `concurrent` for waiting work.

<!-- dewy-example: {"mode":"reject","diagnostic":"parallel body may block; use `concurrent` for waiting work"} -->
```dewy
nap = () => { sleep(10ms); }
parallel i in [0..4) { nap() }
```

`blocks` is an inferred effect. A function can exclude it in its result type with `:>T & no blocks` (see [Refinements, Effects, and Safety](refinements-and-effects.md)).

### Callbacks

A function may run its own callback parameter in parallel. Nothing is written in its signature: each call checks the function it is given as if that function were the parallel body. A wrapper that passes the callback on inherits the requirement.

<!-- dewy-example: {"mode":"run","stdout":"[1 4 9]\n"} -->
```dewy
apply = (f:(x:int:>int) xs:array<int>):>array<int> => [parallel x in xs f(x)]
square = (x:int):>int => x*x
printl(apply(@square [1 2 3]))
```

An unsafe argument is reported where it goes wrong, with notes naming the call and the parallel use:

<!-- dewy-example: {"mode":"reject","diagnostic":"must not change the global 'calls' (a data race)"} -->
```dewy
apply = (f:(x:int:>int) xs:array<int>):>array<int> => [parallel x in xs f(x)]
let calls = 0
counted = (x:int):>int => {
    calls += 1
    x
}
printl(apply(@counted [1 2 3]))
```

A function value the compiler cannot see at the call (from a record field, a table or a local copy) is an error in parallel code.

## `parallel` Blocks

A `parallel` block runs its statements beside each other and waits for all of them at its end. `parallel ( ... )` keeps the names its statements declare for after the block; `parallel { ... }` keeps them inside.

<!-- dewy-example: {"mode":"run","stdout":"55 500500\ninside: 20\n"} -->
```dewy
count_to = (n:int):>int => {
    let total = 0
    loop i in [1..n] { total += i }
    total
}
main = () => {
    parallel (
        let small = count_to(10)
        let large = count_to(1000)
    )
    printl"{small} {large}"
    parallel {
        let doubled = count_to(4) * 2
        printl"inside: {doubled}"
    }
}
```

Each statement is an item. A `let` item whose value calls something, without a written type, runs as a task. An item that reads another's binding starts once that value is made, so dependent items follow their inputs and the rest run beside them. An item ending in `or_throw` leaves the function with its failure after the block's tasks are joined, canceling its siblings first. A task item that would change what the block's own code holds is an error. A name from `parallel { ... }` used after the block is an error that suggests `parallel ( ... )`:

<!-- dewy-example: {"mode":"reject","diagnostic":"write `parallel ( ... )` to use it after the block"} -->
```dewy
count_to = (n:int):>int => n
main = () => {
    parallel {
        let a = count_to(10)
    }
    printl(a)
}
```

*Provisional:* a statement that declares nothing, writes no outside variable and has no `or_throw`, `return`, `break` or `continue` leaving it also runs as a task.

## Core Limits

Native programs use one persistent worker pool. `$program.max_cores = n` at the top of the entry file sets the default allowance, counting the caller. The same setting at the top of a function or block caps its dynamic extent; a nested cap takes the minimum with every active ancestor cap. `$program.max_cores = 1` runs the work on the caller.

<!-- dewy-example: {"mode":"run","stdout":"[0 10 20 30]\n"} -->
```dewy
$program.max_cores = 2
let xs = [parallel i in [0..4) i*10]
printl(xs)
```

Parallel work may always run sequentially, and gives the same results when it does. A caller waiting at a join helps run ready work. Web builds run parallel work serially (see [Targets](targets.md#what-differs-on-the-web)).

## Tasks: `concurrent` and `spawn`

`concurrent { ... }` is a structured task group. `spawn expression` starts a task on a thread of its own; the closing brace joins every child.

<!-- dewy-example: {"mode":"run","stdout":"42 40\n"} -->
```dewy
work = (n:int) => n*2
main = () => {
    concurrent {
        let a = spawn work(21)
        let b = spawn work(20)
    }
    printl"{a} {b}"
}
```

- A task's result is kept only by `let name = spawn ...` written directly in the block. After the block, the name holds the result, or `Canceled`, or `OutOfMemory` when no thread could be started.
- A spawn anywhere else is a statement (`loop x in xs { spawn work(x out) }`); such tasks send their results over a [channel](#channels).
- `spawn { ... }` runs a block as a task.
- Captures and results must be `Send` (see [Transfer Properties](#transfer-properties-send-and-sync)). A task holds its own copy of what it captures. It cannot read a mutable global its parent may change; capture a value or use an atomic handle.

<!-- dewy-example: {"mode":"reject","diagnostic":"expected int, found int | Canceled | OutOfMemory"} -->
```dewy
work = (n:int) => n*2
main = () => {
    concurrent {
        let a = spawn work(21)
    }
    let x:int = a
}
```

### Failure and the Group's Value

As an expression, `concurrent { ... }` gives `true` when every child succeeds, or the first failure a child returns. The first failure cancels its siblings; the join still waits for their cleanup. Returning early from the body cancels and joins the children.

<!-- dewy-example: {"mode":"run","stdout":"failed: too big: 3\n"} -->
```dewy
Bad:type = type of error & [message:string]
check = (n:int):>void | Bad => if n >? 2 return Bad["too big: {n}"]
slow = ():>void | Canceled => {
    sleep(5s) or_throw
    printl"slow finished"
}
main = () => {
    let outcome = concurrent {
        spawn slow()
        spawn check(3)
    }
    match outcome {
        e:Bad => printl"failed: {e.message}"
        _ => printl"all done"
    }
}
```

The failing check cancels the sleeping task, so the program ends at once and `slow finished` is never printed.

### Named Groups

`concurrent g { ... }` names the group, a `TaskGroup`. Pass it to helpers that start tasks with `spawn(g) expression`. `cancel(g)` cancels the group and everything under it.

<!-- dewy-example: {"mode":"run","stdout":"stopped: true\n"} -->
```dewy
heartbeat = ():>void | Canceled => {
    loop true { sleep(10ms) or_throw }
}
start = (g:TaskGroup) => {
    spawn(g) heartbeat()
}
main = () => {
    let outcome = concurrent g {
        start(g)
        sleep(30ms);
        cancel(g)
    }
    printl"stopped: {outcome is? Canceled}"
}
```

A helper whose final statement is `spawn(g) work()` returns `void`; no task handle escapes.

### Platforms

Tasks run on Linux, macOS and Windows. The web target has no tasks; `parallel` work is portable everywhere.

## `Canceled`

`Canceled` is an exception value (US spelling). Cancellation is level-triggered: once a scope is canceled, every later blocking operation in it gives `Canceled`. `sleep`, file and standard-input operations, process waits and channel waits include it in their result types; console output (`print`, `printl`, `console.*`) is not a cancellation point. Forward it with `or_throw`, or handle it.

- `??` never turns `Canceled` into a default: `x ?? 0` leaves the function with it, as `or_throw` would. Only `??<Canceled>` handles it.
- CPU work notices cancellation only at a blocking operation. An arbitrary computation is never forcibly stopped.
- Cleanup (`defer` and drop hooks) is shielded from cancellation, with a 100 ms grace deadline.
- `Canceled` reaching `main` is reported and exits with its kind's code, like any error.
- `$explicit_cancellation` (included in `$bulletproof`) makes each place where `??` or a collector would pass `Canceled` on silently an error, with the rewrite: `x or_throw<Canceled> ?? 0`.

<!-- dewy-example: {"mode":"reject","diagnostic":"use `Canceled` (US spelling)"} -->
```dewy
wait = ():>int | Cancelled => 1
```

How cancellation is requested and where `Canceled` may appear are under review; the rules above describe the current compiler.

## `Atomic<T>`

`atomic(0)` makes an `Atomic<int64>`, a shared counter. Copies of the handle share one value, so tasks and parallel iterations capture it freely. `atomic<T>(value)` selects another fixed-width integer payload.

<!-- dewy-example: {"mode":"run","stdout":"1000 999\ntrue\nfalse\n1\n"} -->
```dewy
let hits = atomic(0)
let best = atomic(0)
parallel i in [0..1000) {
    hits.add(1 'relaxed');
    best.set_max(i)
}
printl"{hits.load'acquire'} {best.load}"

let flag = atomic<int32>(0)
printl(flag.compare_swap(0 1))
printl(flag.compare_swap(0 2))
printl(flag.load)
```

| Operation | Gives |
|---|---|
| `load`, `get` | the value |
| `store(v)`, `set(v)` | `void` |
| `add(n)` | the new value (discard it with `;` as a statement) |
| `compare_swap(expected new)` | `true` when the value was `expected` and is now `new` |
| `set_max(v)` | `void`; the value becomes the larger of the two |

Each operation takes an optional compile-time memory order: `'relaxed'`, `'acquire'`, `'release'`, `'acq_rel'` or `'seq_cst'` (the default). Loads reject release orders and stores reject acquire orders. The native backend currently uses sequentially consistent instructions for every order, which is stronger than requested.

<!-- dewy-example: {"mode":"reject","diagnostic":"an atomic load cannot use release or acq_rel order"} -->
```dewy
let a = atomic(0)
printl(a.load('release'))
```

`add` is an overflow obligation like any arithmetic. Literal and bounded increments of an `Atomic<int64>` are covered by the counter-progress axiom; others need a proof, or `$runtime_checks`. A wrapping payload, `atomic<int64<overflow='wrap'>>(0)`, never fails. `$no_assumed_bounds` removes the axiom.

Synchronized handles come only from their factories (`atomic(...)`, `concurrent`, `spawn`). Zero-filled arrays, omitted fields and array growth cannot make one.

## Channels

A `Channel<T>` carries values between tasks in the order they were sent. `channel<T>(capacity)` makes one that holds at most `capacity` values; `capacity >? 0` is an obligation, and there is no unbounded channel. Copies of the handle share the channel. The payload must be `Send`.

<!-- dewy-example: {"mode":"run","stdout":"499500\n"} -->
```dewy
produce = (out:Channel<int64> n:int64):>void | Unsent<int64> => {
    loop i in [0..n) { out.send(i) or_throw }   # waits while out is full
    out.close()
}
main = () => {
    let numbers = channel<int64>(16)
    let total:int64 = 0
    concurrent {
        spawn produce(numbers 1000)
        loop true {
            let n = numbers.receive              # waits while numbers is empty
            if n is? Closed break
            total += n or_throw
        }
    }
    printl"{total}"
}
```

| Operation | Gives | Waits |
|---|---|---|
| `c.send(v)` | `void \| Unsent<T>` | while full |
| `c.receive` | `T \| Closed<T> \| Canceled` | while empty |
| `c.try_send(v)` | `void \| Unsent<T>` (reason `Full` when there is no room) | never |
| `c.try_receive` | `T \| Empty \| Closed<T> \| Busy \| Canceled` | never |
| `c.close` | `void`; closing again does nothing | never |

- After a close, a send gives `Unsent<T>` with reason `Closed` (never a trap). A receive takes what is still buffered, then gives `Closed<T>`. Tasks waiting on the channel wake.
- Sends and receives are blocking operations (a `parallel` body cannot use them) and cancellation points: canceled, a receive gives `Canceled` and a send gives `Unsent<T>` with reason `Canceled`.
- `Busy` means another task is mid-operation on the channel, rather than a misleading `Full` or `Empty`.
- `Unsent`, `Full`, `Empty` and `Closed` are exceptions, like `Canceled`; `Busy` is an error.

### `Unsent<T>`: a Failed Send Gives the Value Back

A send that fails returns `Unsent<T>`. Its `.value` is the exact payload offered and its `.reason` is `Full`, `Closed`, `Busy` or `Canceled`, so nothing is lost:

<!-- dewy-example: {"mode":"run","stdout":"unsent: 2 (Full)\n"} -->
```dewy
Message:type = [id:int64 body:string]
main = () => {
    let outbox = channel<Message>(1)
    outbox.try_send(Message[1 "hello"]) or_throw
    match outbox.try_send(Message[2 "again"]) {
        failed:Unsent<Message> => printl"unsent: {failed.value.id} ({failed.reason})"
        _ => printl"sent"
    }
}
```

`or_throw` forwards an `Unsent` like any exception. A task that fails with one fails its group with the reason.

`Closed<T>` and `Unsent<T>` are generic. Where a value is tested, the bare name means every instance (`is? Closed`, `<Closed>`, `or_throw<Closed>`); in an annotation write the argument, `Closed<int64>`.

A payload that is or may be `Closed`, `Canceled` or any exception is an error, since it could not be told apart from the outcome. Carry such a value in a record:

<!-- dewy-example: {"mode":"reject","diagnostic":"a channel's payload cannot be Canceled"} -->
```dewy
main = () => {
    let c = channel<int64 | Canceled>(4)
}
```

### `mpmc<T>(n)`: Many Senders and Receivers

`mpmc<T>(capacity)` makes an `Mpmc<T>`, a bounded lock-free queue for many senders and receivers, with the same verbs and outcomes as a channel. A non-waiting attempt that finds another task claiming the slot it wants gives `Busy`.

<!-- dewy-example: {"mode":"run","stdout":"9900\n"} -->
```dewy
fill = (jobs:Mpmc<int64> n:int64):>void | Unsent<int64> => {
    loop i in [0..n) { jobs.send(i) or_throw }
}
main = () => {
    let jobs = mpmc<int64>(64)
    let total = 0
    concurrent {
        spawn {
            concurrent {
                spawn fill(jobs 100)
                spawn fill(jobs 100)
            }
            jobs.close()
        }
        loop true {
            let job = jobs.receive
            if job is? Closed break
            total += job or_throw
        }
    }
    printl(total)
}
```

### `spsc<T N>`: One Sender, One Receiver

`spsc<T N>` makes a lock-free queue for exactly one sender and one receiver; its capacity `N` is a positive integer in the type. `.split` consumes the queue and gives the two ends, an `SpscSender<T>` and an `SpscReceiver<T>`, with the same verbs (`try_receive` never gives `Busy`).

Each end has exactly one owner. It moves instead of copying, so two tasks can never hold the same end. Dropping an end closes the queue: a producer can simply return, and the receiver drains what is left and then sees `Closed`.

<!-- dewy-example: {"mode":"run","stdout":"4950\n"} -->
```dewy
main = () => {
    let [tx rx] = spsc<int64 64>.split
    let total = 0
    concurrent {
        spawn {
            loop i in [0..100) { if tx.send(i) is? Unsent<int64> break }
            # Returning drops tx and closes the queue.
        }
        loop true {
            let n = rx.receive
            if n is? Closed break
            total += n or_throw
        }
    }
    printl(total)
}
```

Using the queue after `.split`, or an end after moving it, is a compile error:

<!-- dewy-example: {"mode":"reject","diagnostic":"later use of 'q' prevents this transfer"} -->
```dewy
main = () => {
    let q = spsc<int64 4>
    let [tx rx] = q.split
    let [tx2 rx2] = q.split
}
```

## Transfer Properties: `Send` and `Sync`

`Send` (a value may move into another task) and `Sync` (tasks may share it) are structural facts the compiler infers. Scalars, arrays, records and unions compose automatically. Raw-storage handles and escaping places do not. Atomic handles, channels and queues have shared identity and cross tasks.

A type opts out with a row. `$send = false` keeps a value from moving into a task (captured, bound or returned):

<!-- dewy-example: {"mode":"reject","diagnostic":"Counter opts out of Send with `$send=false`"} -->
```dewy
Counter:type = [n:int64 $send = false]
main = () => {
    let c = Counter[0]
    concurrent {
        spawn { printl(c.n) }
    }
}
```

`$sync = false` keeps a value out of storage that tasks share, such as a module-level binding a `parallel` body reads:

<!-- dewy-example: {"mode":"reject","diagnostic":"Cache opts out of Sync with `$sync=false`"} -->
```dewy
Cache:type = [n:int64 $sync = false]
let cache = Cache[3]
let xs = [parallel i in [0..4) i + cache.n]
```

A bare `$send` or `$sync` row claims the property. A claim the structure already gives needs nothing. One the compiler cannot verify (a raw `ptr<T>` field, for example) needs `$unsafe` before the type's declaration.

## Deadlock Checks

The compiler reads every task's channel and queue waits in order, with the loops around them and the locks held, and rejects waits it can show never end:

- a task sending more values into a channel than it holds before receiving from it;
- tasks that each fill a channel before receiving from the one the other fills;
- a task's sends filling a channel that is drained only after the task is joined;
- a lock held across a channel wait that the other side takes the lock to reach;
- a receive from a channel nothing sends into or closes.

<!-- dewy-example: {"mode":"reject","diagnostic":"it waits for itself forever"} -->
```dewy
main = () => {
    let c = channel<int64>(2)
    loop i in [0..3) { c.send(i) or_throw }
    printl(c.receive or_throw)
}
```

<!-- dewy-example: {"mode":"reject","diagnostic":"nothing sends into it or closes it: it waits forever"} -->
```dewy
main = () => {
    let c = channel<int64>(2)
    concurrent {
        spawn { printl(c.receive or_throw) }
    }
}
```

Where counts or capacities are not literal, or a group's failure may cancel the wait, it warns instead. Non-waiting attempts (`try_send`, `try_receive`) change the occupancy used to check later waits but never count as waits.

### Deadlock Certificates

`$no_deadlocks` (a setting for a module, function or block) asks for more: every wait in its scope needs a certificate, or it is an error naming the wait. Code under it cannot reach a state where its tasks wait on one another forever, given a fair scheduler, local computation that ends, and outside parties that answer. A certificate is one of:

- **the checked lock order**, for locks taken one inside another or together;
- **a structured join**: the end of `concurrent`, when every child's waits are certified and no lock is held across it;
- **an audited adapter**: a foreign function declared with `$audited_wait` (provisional spelling), checked by a person to wait only on the outside world. A foreign function whose row excludes `blocks` is trusted not to wait.

<!-- dewy-example: {"mode":"run","stdout":"42\n"} -->
```dewy
$no_deadlocks
work = (n:int) => n*2
main = () => {
    concurrent {
        let a = spawn work(21)
    }
    printl(a ?? 0)
}
```

A raw channel's or queue's `send` and `receive`, a loop polling an atomic another task sets, a call through a function value the compiler cannot follow, and a wait in a lifecycle hook have no certificate. Non-waiting attempts need none.

<!-- dewy-example: {"mode":"reject","diagnostic":"no certificate covers it (`$no_deadlocks`)"} -->
```dewy
$no_deadlocks
main = () => {
    let c = channel<int64>(4)
    concurrent {
        spawn { c.send(1) or_throw }
        printl(c.receive or_throw)
    }
}
```

`$bulletproof` includes `$no_deadlocks`. `$no_deadlocks = false` opts a nested scope out.
