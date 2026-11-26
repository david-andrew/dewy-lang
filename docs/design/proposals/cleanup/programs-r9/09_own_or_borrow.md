# 09. A helper that takes ownership versus one that borrows

`write_header` borrows the writer with `@`; `finish_report` takes it. `report` lends it to the
first and hands it to the second.

## (g) Written cleanup

```dewy
import p"@lib/std/files.dewy" as files
Totals:type = [count:int sum:int]

write_header = (@out:FileWriter title:string) => out.write_text("# {title}\n")   # borrows

finish_report = (out:FileWriter totals:Totals) => {                               # takes
    defer out.close() or_throw
    out.write_text("count {totals.count}\nsum {totals.sum}\n") or_throw;
}

report = (path:Path totals:Totals) => {
    let out = files.open(path 'w') or_throw
    defer out.close() or_throw                   # if write_header fails; the move below turns it off
    write_header(@out "Totals") or_throw;
    finish_report(out totals) or_throw
}
```

Round 8's rule 7 stays: for a type that owes, a plain parameter takes the duty and `@` lends it;
the mode isn't inferred from callers. Adding `printl"{out.size}"` after the `finish_report` call
is a use-after-move error at that line.

## (g-auto)

`report` needs no `defer`: a failing `write_header` cleans `out` up automatically. `finish_report`
can write its close at the end instead of the `defer`.

## Scores

| | Added over (a) | Hidden | Forgotten |
|---|---|---|---|
| (g) | 2 lines | 0 | error |
| (g-auto) | 1 line | 0 | error |

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |
