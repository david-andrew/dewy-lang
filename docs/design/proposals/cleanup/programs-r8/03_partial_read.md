# 03. A socket-backed cursor read partially

David's example. `db.scan(table)` gives a generator that owns a socket; closing it early tells the
server to stop sending. `first_row` takes one row, `find` stops at a match, and `greet_first`
passes a fresh generator, which moves into `first_row`.

## (a) Implicit

```dewy
Row:type = [id:int name:string]

first_row = (rows:generator<Row | SocketReceiveFailed>) => {
    loop row in rows { return row }     # rows' socket closes on this exit
    none                                # and on this one
}

find = (rows:generator<Row | SocketReceiveFailed> name:string) => {
    loop row in rows {
        let r = row or_throw            # failure exit: a failed close joins
        if r.name =? name return r      # success exit
    }
    none                                # success exit
}

greet_first = (db:Db) => {
    let first = first_row(db.scan("users")) or_throw<error>
    printl"hello {first}"
}
```

`SocketCloseFailed` appears in both functions' results from no written line, and `greet_first`
forwards it as though the first row had failed to arrive.

## (b) Marked scope

```dewy
first_row = (rows:generator<Row | SocketReceiveFailed>) => {
    loop row in rows { return row }
    none
} or_throw

find = (rows:generator<Row | SocketReceiveFailed> name:string) => {
    loop row in rows {
        let r = row or_throw
        if r.name =? name return r
    }
    none
} or_throw
```

To log a failed close instead of forwarding it, the marker can't help: `} ??<SocketCloseFailed>
none` would also turn a found row into `none`. That needs (d)'s restructuring.

## (c) Value-tied `defer`

```dewy
first_row = (rows:generator<Row | SocketReceiveFailed>) => {
    defer drop(rows) or_throw           # the loop only borrows rows, so the defer can pin it
    loop row in rows { return row }
    none
}

find = (rows:generator<Row | SocketReceiveFailed> name:string) => {
    defer drop(rows) ?? log_warning("cursor close failed")    # handling, per value, keeps the row
    loop row in rows {
        let r = row or_throw
        if r.name =? name return r
    }
    none
}
```

## (d) Explicit close

```dewy
first_row = (rows:generator<Row | SocketReceiveFailed>) => {
    let found:Row | SocketReceiveFailed | none = none
    loop row in rows { found = row; break }
    drop(rows) or_throw
    found
}

find = (rows:generator<Row | SocketReceiveFailed> name:string) => {
    let found:Row | none = none
    loop row in rows {
        let r = row or_throw
        if r.name =? name { found = r; break }
    }
    drop(rows) or_throw
    found
}
```

Each early `return` becomes a variable and a `break`, because a close at the bottom is skipped
by `return`.

## (e) Disposition on the binding

```dewy
first_row = (rows:generator<Row | SocketReceiveFailed> drop or_throw) => {
    loop row in rows { return row }
    none
}

find = (rows:generator<Row | SocketReceiveFailed> drop or_throw name:string) => {
    loop row in rows {
        let r = row or_throw
        if r.name =? name return r
    }
    none
}
```

The clause puts the forward in the signature, where callers see it.

## (f) Finish on success, clean up on failure

```dewy
first_row = (rows:generator<Row | SocketReceiveFailed>) => {
    loop row in rows { return row }     # rows is released here: a socket close can't fail
    none
}

find = (rows:generator<Row | SocketReceiveFailed> name:string) => {
    loop row in rows {
        let r = row or_throw
        if r.name =? name return r
    }
    none
}
```

Nothing written, and nothing hidden: the generator's only owner is a socket, whose release
can't fail. Hover on `return row` reads "releases rows (socket)". A program that wants the
close status anyway calls `rows.close()`, which returns `void | SocketCloseFailed`, and writes
`first_row` as (d) does. If the generator's frame held a writer instead, `first_row` would get
program 08's error.

## Ownership depends on the call

`greet_first` passes a temporary, so `rows` moves into `first_row` and closes there. If a caller
binds the generator and reads it after the call (`let rows = db.scan("users"); first_row(rows);
printl(rows.count)`), the call can no longer move it, and the socket closes in the caller
instead. Under (a) the close failure then moves from `first_row`'s result to the caller's,
changed by a line in another function. (b)–(e) move their required text the same way. (f) is
unaffected here only because the release can't fail; program 09 has the general case.

## Scores

| | Added over (a) | Hidden | Lossy | Forgotten |
|---|---|---|---|---|
| (a) | — | 4 | 0 | — |
| (b) | 2 tokens | 0 | 0 (4 if unmarked) | warning |
| (c) | 2 lines; needs `drop` | 0 | 0 | warning |
| (d) | 6 lines, two rewritten loops; needs `drop` | 0 | 0 | warning |
| (e) | 2 clauses | 0 | 0 | error |
| (f) | 0 | 0 | 0, by contract: the OS close error isn't a Dewy failure | — |
