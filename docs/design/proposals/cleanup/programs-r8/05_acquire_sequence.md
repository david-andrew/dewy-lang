# 05. Several resources acquired in sequence; a later one fails

`upload` opens a file to read, connects to a server and opens a receipt to write. Any
acquisition can fail after earlier ones succeeded; those earlier owners are dropped on that
failure exit.

## (a) Implicit

```dewy
import p"@lib/std/files.dewy" as files
import p"@lib/std/net.dewy" as net

upload = (path:Path host:string) => {
    let input = files.open(path 'r') or_throw
    let conn = net.tcp_connect(host 9000) or_throw              # fails: input closes on this exit
    let receipt = files.open(p"{path}.receipt" 'w') or_throw     # fails: conn, then input, close
    loop chunk in input.chunks(65536) { conn.send(chunk or_throw) or_throw; }
    receipt.write_text("sent {path} to {host}\n") or_throw;
}   # receipt flushes, conn closes, input closes
```

The three hooks can fail on the fallthrough with nothing written. On every failure exit, each
live hook's failure can join, so each failure kind comes in up to eight shapes:
`SocketConnectFailed`, `SocketConnectFailed & FileCloseFailed`, `FileOpenFailed &
SocketCloseFailed & FileCloseFailed`, … Under D42 Q1's narrow rule a caller's
`??<SocketConnectFailed> retry()` consumes the first shape and passes the second on whole, so
whether `upload` retries depends on whether a *reader* closed cleanly.

## (b) Marked scope

```dewy
upload = (path:Path host:string) => {
    let input = files.open(path 'r') or_throw
    let conn = net.tcp_connect(host 9000) or_throw
    let receipt = files.open(p"{path}.receipt" 'w') or_throw
    loop chunk in input.chunks(65536) { conn.send(chunk or_throw) or_throw; }
    receipt.write_text("sent {path} to {host}\n") or_throw;
} or_throw
```

One token covers three owners. The failure shapes are as in (a).

## (c) Value-tied `defer`

```dewy
upload = (path:Path host:string) => {
    let input = files.open(path 'r') or_throw
    defer input.close() or_throw
    let conn = net.tcp_connect(host 9000) or_throw
    defer conn.close() or_throw
    let receipt = files.open(p"{path}.receipt" 'w') or_throw
    defer receipt.close() or_throw
    loop chunk in input.chunks(65536) { conn.send(chunk or_throw) or_throw; }
    receipt.write_text("sent {path} to {host}\n") or_throw;
}
```

Three lines; the Go and Zig shape. A defer registered after a failing acquisition doesn't run,
so each `defer` sits right after its acquisition.

## (d) Explicit close

```dewy
upload = (path:Path host:string) => {
    let input = files.open(path 'r') or_throw
    let conn = net.tcp_connect(host 9000) or_throw
    let receipt = files.open(p"{path}.receipt" 'w') or_throw
    loop chunk in input.chunks(65536) { conn.send(chunk or_throw) or_throw; }
    receipt.write_text("sent {path} to {host}\n") or_throw;
    receipt.close() or_throw            # if this fails, conn and input close on that exit and join
    conn.close() or_throw
    input.close() or_throw
}
```

## (e) Disposition on the binding

```dewy
upload = (path:Path host:string) => {
    let input drop or_throw = files.open(path 'r') or_throw
    let conn drop or_throw = net.tcp_connect(host 9000) or_throw
    let receipt drop or_throw = files.open(p"{path}.receipt" 'w') or_throw
    loop chunk in input.chunks(65536) { conn.send(chunk or_throw) or_throw; }
    receipt.write_text("sent {path} to {host}\n") or_throw;
}
```

## (f) Finish on success, clean up on failure

```dewy
upload = (path:Path host:string) => {
    let input = files.open(path 'r') or_throw
    let conn = net.tcp_connect(host 9000) or_throw
    let receipt = files.open(p"{path}.receipt" 'w') or_throw
    loop chunk in input.chunks(65536) { conn.send(chunk or_throw) or_throw; }
    receipt.write_text("sent {path} to {host}\n") or_throw;
    receipt.close() or_throw
}
```

Only the receipt's cleanup does work, so only it is written, and only it can join a failure:
each failure kind has at most two shapes (`SocketSendFailed`, `SocketSendFailed &
FileWriteFailed`), and a caller's `??<SocketConnectFailed> retry()` always consumes a failed
connect, since nothing that can fail is live when the connect fails.

## Scores

| | Added over (a) | Hidden | Lossy | Forgotten | Shapes per failure kind |
|---|---|---|---|---|---|
| (a) | — | 1 exit, 3 hooks | 0 | — | up to 8 |
| (b) | 1 token | 0 | 0 | warning | up to 8 |
| (c) | 3 lines | 0 | 0 | warning per owner | up to 8 |
| (d) | 3 lines | 0 | 0 | warning per owner | up to 8 |
| (e) | 3 clauses | 0 | 0 | error | up to 8 |
| (f) | 1 line | 0 | 0 | error | at most 2 |
