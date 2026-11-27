# Concurrency and Parallel Work

Dewy has two ways to do more than one thing at a time, and it keeps them apart because they need different things from the machine:

- **`parallel`** splits a calculation across your cores. Its body is pure work that never waits, so the runtime may run it on any core, or all of it on the caller.
- **`concurrent`** runs tasks that may wait: on a sleep, a file, a process or each other. Each task gets a thread of its own, and the group waits for all of them at its closing brace.

Both are checked by the compiler. Code that runs at the same time cannot change shared state except through handles made for it, such as atomics and channels, so a data race is a compile error rather than a bug you find later. Channel waits that can never end are compile errors too.

## A parallel loop

Write `parallel` where you would write `loop`. In brackets it collects one result per element, in input order, just as a `loop` comprehension does:

<!-- dewy-example: {"mode": "run", "stdout": "[0 1 4 9 16 25 36 49]\n"} -->
```dewy
let squares = [parallel i in [0..8) i*i]
printl(squares)
```

Order is kept however the work was scheduled, so code that adds up the results gets the same total, in the same order, as a sequential loop. That matters for floating point, where the order of additions changes the answer.

Parallelism pays when each iteration does real work. Here each iteration counts the primes in its own block of a thousand numbers:

<!-- dewy-example: {"mode": "run", "stdout": "[168 135 127 120 119 114 117 107]\n1007\n"} -->
```dewy
is_prime = (n:int):>bool => {
    if n <? 2 return false
    loop d in 2..n {
        if d * d >? n break
        if n % d =? 0 return false
    }
    true
}

count_primes = (lo:int hi:int):>int => {
    let count = 0
    loop n in [lo..hi) { if is_prime(n) count += 1 }
    count
}

let per_block = [parallel b in [0..8) count_primes(b * 1000 (b + 1) * 1000)]
printl(per_block)
printl(sum(per_block))
```

`count_primes` is an ordinary function. Nothing about it says "parallel"; the compiler checks what it does when the parallel loop calls it.

### Changing elements in place

An ordinary loop binding is read-only. Write `@x` to give each iteration one element of the array to change:

<!-- dewy-example: {"mode": "run", "stdout": "[1 2 3 4]\n[10 20 30 40]\n"} -->
```dewy
main = () => {
    let prices = [1 2 3 4]
    let before = prices
    parallel @p in prices { p *= 10 }
    printl(before)
    printl(prices)
}
```

Each iteration owns its element, so no two iterations can touch the same one. `before` is a separate value and keeps the old prices (see [Values, Copies, and Places](values-and-places.md)).

## What the race check stops

In a parallel body, a captured variable may be read but not changed. Adding to a shared total is the classic data race, and the compiler names it:

<!-- dewy-example: {"mode": "reject", "diagnostic": "must not change 'total', a variable it captured (a data race)"} -->
```dewy
main = () => {
    let total = 0
    parallel i in [0..10) { total += i }
}
```

The check follows calls. A helper that changes a global is just as much a race when a parallel body calls it, and the error points at the write:

<!-- dewy-example: {"mode": "reject", "diagnostic": "must not change the global 'calls' (a data race)"} -->
```dewy
let calls = 0
counted = (x:int):>int => {
    calls += 1
    x * x
}
let xs = [parallel i in [0..4) counted(i)]
```

There are two good fixes. The usual one is to collect the results and combine them afterwards, as `sum(per_block)` did above. When the iterations really must share a counter, use an atomic one. `atomic(0)` makes a handle whose copies share one value, so a parallel body may capture it and add to it:

<!-- dewy-example: {"mode": "run", "stdout": "1000 999\n"} -->
```dewy
let hits = atomic(0)
let best = atomic(0)
parallel i in [0..1000) {
    hits.add(1);
    best.set_max(i)
}
printl"{hits.load} {best.load}"
```

`add` gives the new value; the `;` discards it. There are no locks to forget to take and no annotations to keep in sync: if the body compiles, it has no data race.

A parallel body also cannot `return`, `break` or `continue` out of itself, since the other iterations would have nowhere to go.

### The body must not wait

A parallel body must be proven never to wait. A sleep, blocking I/O or a channel wait in it, even inside a called function, is rejected:

<!-- dewy-example: {"mode": "reject", "diagnostic": "parallel body may block; use `concurrent` for waiting work"} -->
```dewy
nap = () => { sleep(10ms); }
parallel i in [0..4) { nap() }
```

This is what lets the runtime keep a fixed pool of workers busy: a body that waited would hold a core and do nothing. The compiler knows which functions may wait because `blocks` is one of the effects it infers for every function (see [Effects](effects.md)). Work that waits belongs in tasks, below.

## Parallel blocks

A `parallel` block runs its statements beside each other and waits for all of them at its end. With round brackets, the names it declares are kept for the code after it:

<!-- dewy-example: {"mode": "run", "stdout": "55 500500\n"} -->
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
}
```

Each `let` whose value calls something, and has no written type, runs as its own piece of work. An item that reads another item's name waits for that value first, so dependent steps follow their inputs and independent ones run side by side.

With braces, `parallel { ... }` keeps its names inside, like any block. Using one after the block is an error that tells you which bracket you wanted:

<!-- dewy-example: {"mode": "reject", "diagnostic": "write `parallel ( ... )` to use it after the block"} -->
```dewy
count_to = (n:int):>int => n
main = () => {
    parallel {
        let a = count_to(10)
    }
    printl(a)
}
```

## How many cores

Native programs share one pool of worker threads. `$program.max_cores = n` at the top of the entry file caps how many cores parallel work uses, counting the caller; at the top of a function or block it caps that code only. `$program.max_cores = 1` runs everything on the caller.

<!-- dewy-example: {"mode": "run", "stdout": "[0 10 20 30]\n"} -->
```dewy
$program.max_cores = 2
let xs = [parallel i in [0..4) i*10]
printl(xs)
```

Parallel work may always run sequentially and gives the same results when it does. That is what happens on the web target, which runs parallel work serially, so the same source is portable.

## Tasks: `concurrent` and `spawn`

For work that waits, open a `concurrent` block and start tasks in it with `spawn`. Each task runs on a thread of its own. The closing brace waits for every task started inside it, so no task outlives the block that made it:

<!-- dewy-example: {"mode": "run", "stdout": "fetched 3 and 4: 25\n"} -->
```dewy
fetch = (n:int):>int => {
    sleep(50ms);      # stands in for a slow request
    n * n
}

main = () => {
    concurrent {
        let a = spawn fetch(3)
        let b = spawn fetch(4)
    }
    printl"fetched 3 and 4: {(a ?? 0) + (b ?? 0)}"
}
```

The two fetches sleep at the same time, so the block takes about 50 ms, not 100. `sleep(...)` can be cut short (by cancellation, below), so its result is discarded with `;`.

After the block, `a` holds the task's result. A task might not produce one, though: it can be canceled, or no thread could be started for it. So the type of `a` is `int | Canceled | OutOfMemory`, and the compiler will not let you treat it as a plain `int`:

<!-- dewy-example: {"mode": "reject", "diagnostic": "expected int, found int | Canceled | OutOfMemory"} -->
```dewy
work = (n:int) => n*2
main = () => {
    concurrent {
        let a = spawn work(21)
    }
    let x:int = a
}
```

`a ?? 0` gives a default for running out of memory. `??` never swallows `Canceled`: it passes it on to the caller, as `or_throw` would, so a canceled program does not carry on with a made-up value.

A task gets its own copy of what it captures. It cannot read a mutable global that its parent may change; capture a value or use an atomic.

### When a task fails

A task can fail like any function, by returning an error. The first failure cancels the task's siblings and becomes the value of the whole `concurrent` block; the block still waits for the others to clean up:

<!-- dewy-example: {"mode": "run", "stdout": "failed: too big: 3\n"} -->
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

The program ends at once. `check` fails, which cancels `slow` in the middle of its five-second sleep; `sleep` gives `Canceled`, `or_throw` leaves `slow` with it, and `slow finished` is never printed. When every task succeeds, the block's value is `true`.

## Channels

Tasks that need to pass values to each other use a channel. `channel<T>(capacity)` makes a queue that holds at most `capacity` values; there is no unbounded channel, so a fast producer cannot fill memory. `send` waits while the channel is full, and `receive` waits while it is empty. When the producer is done it closes the channel, and the receiver sees `Closed` after the last value:

<!-- dewy-example: {"mode": "run", "stdout": "499500\n"} -->
```dewy
produce = (out:Channel<int64> n:int64):>void | Unsent<int64> => {
    loop i in [0..n) { out.send(i) or_throw }
    out.close()
}

main = () => {
    let numbers = channel<int64>(16)
    let total:int64 = 0
    concurrent {
        spawn produce(numbers 1000)
        loop true {
            let n = numbers.receive
            if n is? Closed break
            total += n or_throw
        }
    }
    printl"{total}"
}
```

Read the types as a checklist of what can happen:

- `receive` gives `int64 | Closed<int64> | Canceled`. The loop leaves on `Closed`, and `or_throw` passes `Canceled` on.
- `send` gives `void | Unsent<int64>`. A send can fail, because the channel was closed or the task canceled, and `Unsent` hands the value back in `.value`, so nothing is silently lost.
- `try_send` and `try_receive` never wait. They give `Full` or `Empty` instead.

<!-- dewy-example: {"mode": "run", "stdout": "sent 1\nunsent: 2 (Full)\n"} -->
```dewy
main = () => {
    let outbox = channel<int64>(1)
    outbox.try_send(1) or_throw
    printl"sent 1"
    match outbox.try_send(2) {
        failed:Unsent<int64> => printl"unsent: {failed.value} ({failed.reason})"
        _ => printl"sent 2"
    }
}
```

A channel handle is shared, like an atomic: copies of it are the same channel, which is why passing `numbers` to `produce` connects the two tasks.

## Deadlock checks

A deadlock is a wait that can never end. The compiler reads every task's channel waits in order, with the loops around them, and rejects the ones it can show are stuck. A task that sends more into a channel than it holds, before anything receives, waits for itself:

<!-- dewy-example: {"mode": "reject", "diagnostic": "it waits for itself forever"} -->
```dewy
main = () => {
    let c = channel<int64>(2)
    loop i in [0..3) { c.send(i) or_throw }
    printl(c.receive or_throw)
}
```

A receive from a channel that nothing sends into, or closes, waits forever:

<!-- dewy-example: {"mode": "reject", "diagnostic": "nothing sends into it or closes it: it waits forever"} -->
```dewy
main = () => {
    let c = channel<int64>(2)
    concurrent {
        spawn { printl(c.receive or_throw) }
    }
}
```

It also catches two tasks that each fill a channel before reading the other's, and a task whose sends fill a channel that is only drained after the task is joined. Where the counts or capacities are not constants, it warns instead of guessing.

For code that must never deadlock, `$no_deadlocks` on a module, function or block asks for more: every wait in it must come with a reason it ends, or it is an error. The end of a `concurrent` block counts when the tasks inside it are covered, so simple fork-and-join code needs nothing extra:

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
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

A raw channel's `send` and `receive` have no such certificate, so under `$no_deadlocks` they are errors until the code is restructured. The [reference](/reference/concurrency.html#deadlock-certificates) lists what counts as a certificate.

## What the checks buy you

Put together, the checks mean that code which compiles:

- has no data races: shared state changes only through atomics, channels and other synchronized handles;
- gives the same results from `parallel` work whether it ran on one core or eight;
- never leaves a task running after the block that started it, and turns the first failure into the block's value;
- has no channel wait that the compiler can see will never end, and with `$no_deadlocks`, no wait it cannot show will end.

You get these without writing lock annotations or lifetime markers: the compiler infers what each function touches and whether it waits, and checks every parallel body and task against that.

The [reference](/reference/concurrency.html) has the complete rules, including the other queue kinds (`mpmc` and `spsc`) and the `Send` and `Sync` transfer properties.
