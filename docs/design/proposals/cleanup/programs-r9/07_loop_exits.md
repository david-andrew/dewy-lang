# 07. One file per iteration, with `break` and `continue`

D40 Q6's case, with a `continue` after the open as well as before it.

## (g) Written cleanup

```dewy
import p"@lib/std/files.dewy" as files

write_all = (names:array<string>) => {
    loop name in names {
        if name =? "" continue                           # nothing open yet
        let out = files.open(p"{name}.txt" 'w') or_throw
        defer out.close() or_throw                       # runs at each exit of this iteration
        if name.startswith("draft") continue
        out.write_text(name) or_throw;
        if name =? "last" break
    }
    printl("all written")
}
```

The `defer` belongs to the loop body's scope, so it runs at the iteration's end, at `continue`
and at `break`, after the jump is decided and before it happens. If the close fails, its
`or_throw` leaves `write_all` from the `defer`'s line, the same as any `or_throw` in the body. That
is the visible exit D40 Q6 asked for: it is written in the loop body, beside the open, not hidden
behind the `continue`. Go's `defer` would wait for the function's end and keep every file open
until then; Dewy's is tied to the scope.

## (g-auto)

The same text. With the close written at each exit instead (round 8's (f)), both closes are
needed, and the `defer` is shorter.

## Scores

| | Added over (a) | Hidden | Forgotten |
|---|---|---|---|
| (g) | 1 line | 0 | error at the first fallible line after the open |
| (g-auto) | 1 line | 0 | error at the `continue` |

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

Round 8 scored this program concise 4 (two closes, or a grouping). One `defer` in the body
replaces D40 Q6's options A, B and C. Python writes `with open(...) as out:` and indents the body.
