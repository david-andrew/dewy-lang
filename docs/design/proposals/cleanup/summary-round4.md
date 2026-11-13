# Cleanup round 4

**Verdict: keep `defer` narrowly. Choose automatic fallible owner completion at an ordinary block’s exit, with whole-value operations as the common path.** No acquisition callbacks or new block syntax. Completion errors are ordinary enclosing-function results. Shared Channel APIs remain unchanged; their automatic-close gap is explicit.

## File write: a late flush error

Before:

```dewy
write_body = (@out:File) => {
    out.write_bytes([1 2 3]) or_throw;
}
save = () => open(p"/dev/full" 'w' @write_body)
main = () => save or_throw
```

After:

```dewy
save = () => {
    let out = open(p"/dev/full" 'w') or_throw
    out.write_bytes([1 2 3]) or_throw;
    return                 # flush failure replaces this success
}
main = () => save or_throw
```

Before is the rejected round-3 callback. After uses one ordinary function. The three bytes are buffered; Linux /dev/full rejects the eventual flush. The result includes FileError; no success is delivered first.

## TCP: early return

Before:

```dewy
fetch = () => {
    let s = net.tcp_connect("127.0.0.1" 8080) or_throw
    defer net.tcp_close(s)
    let reply = net.tcp_receive(s)
    if reply is? none return
    printl((reply or_throw).length)
}
```

After:

```dewy
fetch = () => {
    let s = net.tcp_connect("127.0.0.1" 8080) or_throw
    let reply = net.tcp_receive(s)
    if reply is? none return
    printl((reply or_throw).length)
}
```

The stream owns infallible local release. EOF, error and cancellation need no paired close line. This does not promise peer acknowledgement.

## Channel closure: use the existing single-producer queue

Before:

```dewy
produce = (q:Channel<int64>) => {
    defer q.close()
    loop n in [0..10) { q.send(n) or_throw }
}
let q = channel<int64>(16)
parallel { produce(q) or_throw; drain(q) or_throw }
```

After:

```dewy
produce = (tx:SpscSender<int64>) => {
    loop n in [0..10) { tx.send(n) or_throw }
}
let [tx rx] = spsc<int64 16>.split
parallel { produce(tx) or_throw; drain(rx) or_throw }
```

This is an existing API choice for one producer/consumer, not a new Sender/Receiver redesign. Shared Channel/Mpmc still require explicit close coordination; the smaller last-handle rule fails below. Their broader automatic-close design remains a separate optional question.

## Mutex: the whole operation stays locked

Before:

```dewy
let state = mutex(State[100])
{
    let value = @(state.lock())
    value.balance += 10
    write_journal() or_throw  # value already had its last use
}
```

After:

```dewy
operate = (@value:State) => {
    value.balance += 10
    write_journal() or_throw
}
let state = mutex(State[100])
operate(@(state.lock())) or_throw
```

The before form unlocks too early for this requirement. The after form uses the existing lending-call statement: the lock lasts until operate returns, including its tail I/O. This helper is a protected operation, not an acquisition callback.

## One-off “done”

Before:

```dewy
scan = (rows:array<string>) => {
    if rows.length =? 0 { printl"done"; return }
    loop row in rows { if row =? "bad" { printl"done"; return Invalid } }
    printl"done"
}
scan(rows) or_throw
```

After:

```dewy
scan = (rows:array<string>) => {
    defer printl"done"
    loop row in rows { if row =? "bad" return Invalid }
    return
}
scan(rows) or_throw
```

Keep one checked non-failing defer. Arbitrary omitted program intent is not inferable; resource factories must not depend on this registration.

## Rules and approval

- Infallible zero-argument owners keep last-use release. Fallible/outcome-aware owners complete at their owning block’s exit. Moves transfer the duty; returned owners complete in the receiver.
- Extend existing `$__drop__` to return `void | E`. On success exits, F replaces success; on failure exits, CleanupError retains both. A failed cleanup crossing break/continue returns from the enclosing function. No rejected callback return is resumed. Explicit consuming close remains optional for early release/local recovery.
- An optional ordinary `successful:bool` hook parameter supplies the current success/failure bit. It enables transaction commit/rollback and owned process wait/stop without remembered flags, passing an error object, or adding a keyword. This is a new hook contract, explicitly needing approval.
- Complete all initialized resources; preserve reverse field/element order and defer-before-owner order. Mutations publish a valid replacement before forwarding an old cleanup failure. Failed return handoff also completes the withheld owning result.
- Keep shielded cleanup and cooperative joining. No normal-path 100 ms cap; canceled cleanup shares the existing 100 ms grace through the unwind episode. Record native failures independently of deadlines. Never detach or blindly retry close.
- Keep non-failing one-off defer, existing Mutex lending and CleanupError pairing. Shared Channel last-handle drop cannot close a receiver that still holds a send-capable Channel; inferred sending leases/endpoints are a separate optional question. Existing spsc already closes automatically.

**Alternative (b):** compiler-enforced finish on normal paths would catch omission and is viable, but still requires close at every successful return/break and an aggregate consume. It retains most failure/unwind machinery. Prefer (a), with (b) only if implicit exit failures are rejected.

**Changes:** no acquisition callback APIs, Sender/Receiver redesign, new timeout setting or local nominal extension in the main proposal. The latter is only an isolated C-example packaging dependency. Update LANGUAGE hook/lifetime/error/cancellation/file sections and the two resource defers in D4; use existing spsc for its single reporter or retain shared-channel close coordination. Historical rounds are unchanged; checkout read-only, no commits.

**Names to approve:** CleanupError, .primary and .cleanup. Hook result/parameter contracts and implicit exit semantics need semantic approval, with existing spellings. Stream/terminal/db/game sketches are not a new naming ballot. See round4.md, programs-r4/ and dogfood-round4.md for exact rules, grades and implementation limits. Paper review only; no compilation, execution or performance measurement.

**Dogfood floor: 3/5** across seventeen paper programs. Shared Channel still requires close coordination, the C example retains an isolated packaging dependency, and replacement can return an error after installing a valid new owner. Straight-line streaming cleanup now scores 4s or better; these remaining 3s are explained and cited in dogfood-round4.md rather than hidden. Names have not been cold-tested.
