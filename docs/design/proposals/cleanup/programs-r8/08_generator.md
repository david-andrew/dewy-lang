# 08. Generators that own resources

`headlines` returns a generator that owns a socket; `top3` keeps three items and stops.
`logged` returns a generator that writes each row it passes through to a log file;
`first_logged` takes one row and stops, which drops the generator mid-stream.

## (a) Implicit

```dewy
import p"@lib/std/files.dewy" as files
import p"@lib/std/net.dewy" as net
Headline:type = [title:string url:string]
Row:type = [id:int name:string]

headlines = (host:string) => {
    let conn = net.tcp_connect(host 7070) or_throw
    lazy loop line in conn.lines() or_throw parse_headline(line)    # conn moves into the generator
}

top3 = (host:string) => {
    let feed = headlines(host) or_throw
    let picked:array<Headline> = []
    loop item in feed {
        picked.push(item or_throw)       # failure exit: feed and its socket close; failures join
        if picked.length =? 3 break      # feed outlives the loop (batch 11)
    }
    picked
}   # feed closes here: a failed close becomes top3's result

logged = (source:generator<Row> log:Path) => {
    let out = files.open(log 'w') or_throw
    lazy loop row in source { out.write_text("{row.name}\n") or_throw; row }
}   # out moves into the generator; it flushes when the generator ends or is dropped

first_logged = (source:generator<Row>) => {
    let rows = logged(source p"rows.log") or_throw
    loop row in rows { return row }      # rows dropped mid-stream: the log's flush runs here
    none
}
```

Two levels hide a failure: the lazy body's natural end flushes `out` with nothing written, and
`first_logged`'s exits flush it through the generator's drop.

## (b) Marked scope

```dewy
top3 = (host:string) => {
    let feed = headlines(host) or_throw
    let picked:array<Headline> = []
    loop item in feed {
        picked.push(item or_throw)
        if picked.length =? 3 break
    }
    picked
} or_throw

logged = (source:generator<Row> log:Path) => {
    let out = files.open(log 'w') or_throw
    lazy ({ loop row in source { out.write_text("{row.name}\n") or_throw; row } } or_throw)
}   # the marked lazy body: its failed flush becomes the generator's failed close

first_logged = (source:generator<Row>) => {
    let rows = logged(source p"rows.log") or_throw
    loop row in rows { return row }
    none
} or_throw
```

## (c) Value-tied `defer`

```dewy
top3 = (host:string) => {
    let feed = headlines(host) or_throw
    defer drop(feed) or_throw
    let picked:array<Headline> = []
    loop item in feed {
        picked.push(item or_throw)
        if picked.length =? 3 break
    }
    picked
}

logged = (source:generator<Row> log:Path) => {
    let out = files.open(log 'w') or_throw
    lazy {
        defer out.close() or_throw       # batch 11 allows defer in a lazy body only if it can't fail
        loop row in source { out.write_text("{row.name}\n") or_throw; row }
    }
}

first_logged = (source:generator<Row>) => {
    let rows = logged(source p"rows.log") or_throw
    defer drop(rows) or_throw
    loop row in rows { return row }
    none
}
```

## (d) Explicit close

```dewy
top3 = (host:string) => {
    let feed = headlines(host) or_throw
    let picked:array<Headline> = []
    loop item in feed {
        picked.push(item or_throw)
        if picked.length =? 3 break
    }
    drop(feed) or_throw
    picked
}

logged = (source:generator<Row> log:Path) => {
    let out = files.open(log 'w') or_throw
    lazy {
        loop row in source { out.write_text("{row.name}\n") or_throw; row }
        out.close() or_throw
    }
}

first_logged = (source:generator<Row>) => {
    let rows = logged(source p"rows.log") or_throw
    let found:Row | FileWriteFailed | FileCloseFailed | none = none
    loop row in rows { found = row; break }
    drop(rows) or_throw
    found
}
```

## (e) Disposition on the binding

```dewy
top3 = (host:string) => {
    let feed drop or_throw = headlines(host) or_throw
    let picked:array<Headline> = []
    loop item in feed {
        picked.push(item or_throw)
        if picked.length =? 3 break
    }
    picked
}

logged = (source:generator<Row> log:Path) => {
    let out drop or_throw = files.open(log 'w') or_throw    # the move into the generator clears it,
    lazy loop row in source { out.write_text("{row.name}\n") or_throw; row }
}                                                          # so the clause says nothing here

first_logged = (source:generator<Row>) => {
    let rows drop or_throw = logged(source p"rows.log") or_throw
    loop row in rows { return row }
    none
}
```

Inside `logged` the clause is cleared by the move into the generator, so where the lazy body's
end flush goes still needs a rule of its own.

## (f) Finish on success, clean up on failure

```dewy
top3 = (host:string) => {
    let feed = headlines(host) or_throw
    let picked:array<Headline> = []
    loop item in feed {
        picked.push(item or_throw)
        if picked.length =? 3 break
    }
    picked                               # feed is released here: a socket close can't fail
}

logged = (source:generator<Row> log:Path) => {
    let out = files.open(log 'w') or_throw
    lazy {
        loop row in source { out.write_text("{row.name}\n") or_throw; row }
        out.close() or_throw             # the body's end is a success exit: finish the log
    }
}

first_logged = (source:generator<Row>) => {
    let rows = logged(source p"rows.log") or_throw
    loop row in rows { return row }
    none
} or_throw      # rows' frame holds a writer: dropping it mid-stream flushes, which can fail
```

`top3` needs nothing. `first_logged` without its marker:

```text
error: rows (generator from logged, line 2) can be dropped mid-stream at `return row` (line 3)
       and at line 4. Its frame holds out (File), whose flush can fail with
       FileWriteFailed | FileCloseFailed.
       Cover the body:           } or_throw
       or read rows to its end.
```

The generator's type says what its drop can do, so the error arrives at the owner that drops
it, as for any value.

## Scores

| | Added over (a) | Hidden | Lossy | Forgotten |
|---|---|---|---|---|
| (a) | — | 4 (socket 1, log 3) | 0 | — |
| (b) | 3 markers, 1 grouping | 0 | 0 | warning |
| (c) | 3 lines; fallible `defer` in a lazy body reverses batch 11 | 0 | 0 | warning |
| (d) | 5 lines, one rewritten loop | 0 | 0 | warning |
| (e) | 3 clauses; the lazy body's end flush is uncovered | 1 | 0 | error |
| (f) | 1 line, 1 token | 0 | 0 | error |
