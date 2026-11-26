# 07. One file per iteration, with `break` and `continue`

D40 Q6's case, with a `continue` after the open as well as before it.

## (a) Implicit

```dewy
import p"@lib/std/files.dewy" as files

write_all = (names:array<string>) => {
    loop name in names {
        if name =? "" continue                           # nothing open yet
        let out = files.open(p"{name}.txt" 'w') or_throw
        if name.startswith("draft") continue             # out flushes here (an empty file)
        out.write_text(name) or_throw;
        if name =? "last" break                          # and here
    }                                                    # and at the end of each iteration
    printl("all written")
}
```

A failed flush at `continue`, `break` or the iteration's end leaves `write_all` there, and
`printl` is skipped with no exit written above it.

## (b) Marked scope

```dewy
write_all = (names:array<string>) => {
    loop name in names ({
        if name =? "" continue
        let out = files.open(p"{name}.txt" 'w') or_throw
        if name.startswith("draft") continue
        out.write_text(name) or_throw;
        if name =? "last" break
    } or_throw)
    printl("all written")
}
```

Round 7's grouping. `loop name in names { … } or_throw` would mark the loop, not its body, and is
rejected for an uncovered body.

## (c) Value-tied `defer`

```dewy
write_all = (names:array<string>) => {
    loop name in names {
        if name =? "" continue
        let out = files.open(p"{name}.txt" 'w') or_throw
        defer out.close() or_throw                       # runs at each of this iteration's exits
        if name.startswith("draft") continue
        out.write_text(name) or_throw;
        if name =? "last" break
    }
    printl("all written")
}
```

A failing deferred close at `continue` leaves `write_all`: the `defer` line shows that an exit
can happen, but not at which line.

## (d) Explicit close

```dewy
write_all = (names:array<string>) => {
    loop name in names {
        if name =? "" continue
        let out = files.open(p"{name}.txt" 'w') or_throw
        if name.startswith("draft") { out.close() or_throw; continue }
        out.write_text(name) or_throw;
        out.close() or_throw
        if name =? "last" break
    }
    printl("all written")
}
```

Every exit from `write_all` is now a written `or_throw`.

## (e) Disposition on the binding

```dewy
write_all = (names:array<string>) => {
    loop name in names {
        if name =? "" continue
        let out drop or_throw = files.open(p"{name}.txt" 'w') or_throw
        if name.startswith("draft") continue
        out.write_text(name) or_throw;
        if name =? "last" break
    }
    printl("all written")
}
```

## (f) Finish on success, clean up on failure

```dewy
write_all = (names:array<string>) => {
    loop name in names {
        if name =? "" continue
        let out = files.open(p"{name}.txt" 'w') or_throw
        if name.startswith("draft") { out.close() or_throw; continue }
        out.write_text(name) or_throw;
        out.close() or_throw
        if name =? "last" break
    }
    printl("all written")
}
```

The same text as (d), but forgetting either close is an error at the `continue` or the
iteration's end, offering the close or (b)'s grouping. If `out` were opened for reading, nothing
would be written: the iteration releases it.

## Scores

| | Added over (a) | Hidden | Lossy | Forgotten |
|---|---|---|---|---|
| (a) | — | 3 | 0 | — |
| (b) | 1 grouping (4 characters) | 0 | 0 | rejected under Q6, or warning |
| (c) | 1 line | 0 | 0 | warning |
| (d) | 2 lines, 1 brace group | 0 | 0 | warning |
| (e) | 1 clause | 0 | 0 | error |
| (f) | 2 lines, 1 brace group | 0 | 0 | error |
