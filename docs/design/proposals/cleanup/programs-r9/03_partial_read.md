# 03. A socket-backed cursor read partially

David's example. `db.scan(table)` gives a generator that holds a socket; dropping it early tells
the server to stop sending. `first_row` takes one row, `find` stops at a match.

## (g) Written cleanup

```dewy
Row:type = [id:int name:string]

first_row = (rows:generator<Row | SocketReceiveFailed>) => {
    loop row in rows { return row }     # rows is released here
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

Nothing written, as in round 8, but now for a reason the type carries. `db.scan` sent its query
and read the server's reply before handing out the cursor, so the cursor holds a `SocketReader`:
its sending side was finished inside the library, where the reply confirmed it. Releasing a
reader can't fail, so nothing appears.

A cursor that streamed *uploads* (a bulk insert) would hold a sending side, owe its finish, and
get program 05's treatment.

The declared parameter type `generator<Row | SocketReceiveFailed>` accepts a generator whose
cleanup can fail only if the body accounts for it (round 9, "Generics"). `first_row`'s body
doesn't, so passing it program 08's logging generator is an error at that call:

```text
error: first_row (line 1) can drop rows before its end, and this generator's frame holds
       out (FileWriter), whose close can fail.
       Read it to its end here, or give first_row a `defer drop(rows) or_throw`.
```

## Scores

| | Added over (a) | Hidden | Forgotten |
|---|---|---|---|
| (g) | 0 | 0 | — |
| (g-auto) | 0 | 0 | — |

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |
