# 05. A reader, a connection and a writer, acquired in sequence

`upload` reads a file, sends it to a server and writes a receipt. Round 8 classed the
connection's close as a release; the review showed that a socket that has sent bytes is a writer
(a userspace buffer, TLS `close_notify`, `SO_LINGER`), so round 8's (f) let the forgotten finish
through. This version also reads the server's acknowledgment, because a clean close only means
the bytes left this machine: the kernel's `close` returns 0 with data still unacknowledged.

## Three ways to put "has sent bytes" in the type

**(i) Separate reader and writer types, chosen at construction.** `files.open(p 'r')` is a
`FileReader`, `'w'` a `FileWriter`, `'rw'` a `File` that owes what a writer owes. A connection is
duplex, so `Socket` owes its sending side's finish from the moment it exists, sent or not.
`conn.finish_sending()` consumes it and gives back a `SocketReader`. All ordinary types and moves.

**(ii) Typestate by flow.** `conn.send(...)` changes `conn`'s state from "nothing pending" to
"must finish", and only then does it owe. Rejected:
- a helper that borrows `@conn` and sends must declare in its signature that it changes the
  state, and every generic container of sockets has to track it;
- after an `if` where one branch sends, the state is "maybe", which owes anyway;
- adding a line in one branch changes what is owed at an exit far below, which is iteration 5's
  objection in round 8 and the review's point 2.

**(iii) Split halves.** `let (input output) = conn.split()` gives a reader and a writer that two
tasks can own. The writer owes; the reader doesn't. This is (i) applied to a duplex value, and
useful when sending and receiving run in parallel. A library can offer both.

**Picked: (i)**, with (iii) as a library convenience for concurrent use. The mode is fixed where
the value is made, so what a value owes never depends on what happened to it later, generic code
sees it in the type, and the checker stays the per-exit liveness check.

## (g) Written cleanup

```dewy
import p"@lib/std/files.dewy" as files
import p"@lib/std/net.dewy" as net
UploadRejected:type = type of error & [host:string reply:string]

upload = (path:Path host:string) => {
    let input = files.open(path 'r') or_throw                    # FileReader: owes nothing
    let conn = net.tcp_connect(host 9000) or_throw               # Socket: aborted on failure exits
    let receipt = files.open(p"{path}.receipt" 'w') or_throw
    defer receipt.close() or_throw
    loop chunk in input.chunks(65536) conn.send(chunk or_throw) or_throw;
    let replies = conn.finish_sending() or_throw                 # flush, close_notify, FIN; consumes conn
    let reply = replies.read_line() or_throw
    if reply not=? "ok" return UploadRejected[host reply]
    receipt.write_text("sent {path} to {host}\n") or_throw;
}
```

- `input` needs nothing: a reader's release can't fail, and nothing about it appears.
- `conn` needs no `defer`: its abandon is an abort, which is a release, and is what a failed
  upload should do (a `close_notify` would tell the peer the upload was complete). Its success
  exit needs the finish.
- `receipt` gets the writer idiom.

Forgetting `finish_sending` (or `close`):

```text
error: conn (Socket, line 3) has an unfinished sending side where upload ends (line 11).
       Finishing it can fail with SocketSendFailed | SocketCloseFailed.
       Finish it:  conn.close() or_throw
       or, to read a reply:  let replies = conn.finish_sending() or_throw
```

Shapes: a failed connect has nothing owing alive, so it always comes back bare and a caller's
`??<SocketConnectFailed> retry()` always takes it. A failed send gives `SocketSendFailed`, or
`ErrorStack[SocketSendFailed FileWriteFailed]` if the receipt's close fails too: at most two
shapes per failure kind (round 8's (a): up to eight).

## (g-auto)

```dewy
upload = (path:Path host:string) => {
    let input = files.open(path 'r') or_throw
    let conn = net.tcp_connect(host 9000) or_throw
    let receipt = files.open(p"{path}.receipt" 'w') or_throw
    loop chunk in input.chunks(65536) conn.send(chunk or_throw) or_throw;   # fails: receipt flushes; a failure joins, unwritten
    let replies = conn.finish_sending() or_throw
    let reply = replies.read_line() or_throw
    if reply not=? "ok" return UploadRejected[host reply]
    receipt.write_text("sent {path} to {host}\n") or_throw;
    receipt.close() or_throw
}
```

The same number of lines; the `defer` becomes a close at the end.

## Scores

| | Added over (a) | Hidden | Forgotten | Shapes per failure kind |
|---|---|---|---|---|
| (g) | 2 lines (`defer`, `finish_sending`) | 0 | error naming the sending side | at most 2 |
| (g-auto) | 2 lines | 0 | error | at most 2 |
| round 8 (f), as the review read it | 1 line | 1: the socket's flush | silent | at most 2 |

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

Python's `with socket.create_connection(...)` closes on exit and raises close errors, but a
failed upload sends an orderly FIN too; Go and Rust close silently; none of them reports a
forgotten `shutdown(SHUT_WR)`. Reading the acknowledgment is the protocol's job in every language.
