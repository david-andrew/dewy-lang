# 08. Generators that own resources

`headlines` returns a generator holding a socket's receiving side; `top3` keeps three items and
stops. `logged` returns a generator that writes each row it passes through to a log file;
`first_logged` takes one row and stops, which drops the generator mid-stream.

## (g) Written cleanup

```dewy
import p"@lib/std/files.dewy" as files
import p"@lib/std/net.dewy" as net
Headline:type = [title:string url:string]
Row:type = [id:int name:string]

headlines = (host:string) => {
    let conn = net.tcp_connect(host 7070) or_throw
    let feed = conn.finish_sending() or_throw          # nothing to send: finishing is immediate
    lazy loop line in feed.lines() or_throw parse_headline(line)
}

top3 = (host:string) => {
    let feed = headlines(host) or_throw
    let picked:array<Headline> = []
    loop item in feed {
        picked.push(item or_throw)
        if picked.length =? 3 break
    }
    picked                               # feed is released here: a reader owes nothing
}

logged = (source:generator<Row> log:Path) => {
    let out = files.open(log 'w') or_throw
    lazy {
        defer out.close() or_throw       # at the body's end, and when the consumer drops it mid-stream
        loop row in source { out.write_text("{row.name}\n") or_throw; row }
    }
}

first_logged = (source:generator<Row>) => {
    let rows = logged(source p"rows.log") or_throw
    defer drop(rows) or_throw            # rows' frame holds a writer
    loop row in rows { return row }      # row is computed, then rows is dropped: the log closes
    none
}
```

A lazy body is a body. Its `defer` runs at every way the body can end (batch 11 already says so
for a non-failing `defer`): its natural end, a failure, cancellation, and the consumer dropping
the generator while it is suspended. A failure from the deferred close is the generator's
cleanup failure, so the generator's type owes `FileWriteFailed | FileCloseFailed`, and its owner
accounts for it like any value: `first_logged`'s `defer drop(rows)`.

`headlines`'s `conn` must be finished before it moves into the generator, or the generator owes a
sending side. Here there is nothing to send, so `finish_sending()` costs one line. A protocol
library would do it inside.

`first_logged` without its `defer`:

```text
error: rows (generator from logged, line 2) can be dropped mid-stream at `return row` (line 3)
       and at line 4. Its frame holds out (FileWriter), whose close can fail with
       FileWriteFailed | FileCloseFailed.
       Drop it on every exit:  defer drop(rows) or_throw
       or read rows to its end.
```

## (g-auto)

`logged` writes `out.close() or_throw` at the lazy body's end (a success exit) and gets the
mid-stream drop for free; `first_logged` still needs the `defer`, since its exits are success
exits.

## Scores

| | Added over (a) | Hidden | Forgotten |
|---|---|---|---|
| (g) | 3 lines | 0 | error at the owner that can drop it |
| (g-auto) | 3 lines | 0 | error |

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 4 | 5 | 5 | 5 | 5 |

Obvious 4: that dropping a generator mid-stream runs its body's `defer`, and can therefore fail,
is learned from the error. Python's generator `close()` raises `GeneratorExit` in the body and
runs its `finally`, with the same lesson, and loses nothing only if the caller uses
`contextlib.closing`. Iteration 4 tried naming the effect at the drop site; hover already does.
