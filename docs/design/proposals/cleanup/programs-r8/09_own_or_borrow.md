# 09. A helper that takes ownership versus one that borrows

`write_header` borrows the writer with `@`; `finish_report` takes it. `report` lends it to the
first and hands it to the second at its last use.

## (a) Implicit

```dewy
import p"@lib/std/files.dewy" as files
Totals:type = [count:int sum:int]

write_header = (@out:File title:string) => out.write_text("# {title}\n")   # borrows: report keeps out

finish_report = (out:File totals:Totals) => {                                # takes out
    out.write_text("count {totals.count}\nsum {totals.sum}\n") or_throw;
}   # out flushes here: a failure becomes finish_report's result

report = (path:Path totals:Totals) => {
    let out = files.open(path 'w') or_throw
    write_header(@out "Totals") or_throw;
    finish_report(out totals) or_throw       # out's last use: it moves in
}
```

`report` forwards the flush failure visibly (its `or_throw` is on the call that contains it), but
`finish_report` produces it from no line. A lender can't lose its duty: `write_header` can't
close a borrowed `out` (closing consumes), so the flush stays with `report` until the move.

## (b) Marked scope

```dewy
finish_report = (out:File totals:Totals) => {
    out.write_text("count {totals.count}\nsum {totals.sum}\n") or_throw;
} or_throw

report = (path:Path totals:Totals) => {      # no marker: out moves out on the success path
    let out = files.open(path 'w') or_throw
    write_header(@out "Totals") or_throw;
    finish_report(out totals) or_throw
}
```

## (c) Value-tied `defer`

```dewy
finish_report = (out:File totals:Totals) => {
    defer out.close() or_throw
    out.write_text("count {totals.count}\nsum {totals.sum}\n") or_throw;
}
```

A `defer out.close()` in `report` would be canceled by the move into `finish_report` (or, under
pinning, forbid it).

## (d) Explicit close

```dewy
finish_report = (out:File totals:Totals) => {
    out.write_text("count {totals.count}\nsum {totals.sum}\n") or_throw;
    out.close() or_throw
}
```

## (e) Disposition on the binding

```dewy
finish_report = (out:File drop or_throw totals:Totals) => {
    out.write_text("count {totals.count}\nsum {totals.sum}\n") or_throw;
}
```

## (f) Finish on success, clean up on failure

```dewy
finish_report = (out:File totals:Totals) => {
    out.write_text("count {totals.count}\nsum {totals.sum}\n") or_throw;
    out.close() or_throw
}
```

Without the close: an error at `finish_report`'s `}`, as in program 01.

## The edit that moves the duty

Someone adds `printl"wrote {path}: {out.size} bytes"` after the `finish_report` call. `out` is no
longer at its last use there, so the call can't move it.

- If the parameter's mode follows the call (the caller lends because it still needs `out`), the
  flush moves from `finish_report`'s `}` to `report`'s `}` without either function's text
  changing near it. Under (a) the failure silently moves to another function's result; under (b)
  `finish_report`'s marker becomes unneeded and `report` gains a warning; under (c) and (d)
  `finish_report`'s close becomes an error (it can't close a borrowed value).
- If a plain parameter of a type with fallible cleanup always takes ownership, the added line is
  a use-after-move error at that line, and nothing moves silently.

(f) needs the second rule for such types, and so does any approach that wants the duty's place to
be readable from the signatures: `(out:File)` takes the duty, `(@out:File)` leaves it. The
inference may stay for types whose cleanup can't fail, where the difference is unobservable.

## Scores

| | Added over (a) | Hidden | Lossy | Forgotten |
|---|---|---|---|---|
| (a) | — | 1 | 0 | — |
| (b) | 1 token | 0 | 0 | warning |
| (c) | 1 line | 0 | 0 | warning |
| (d) | 1 line | 0 | 0 | warning |
| (e) | 1 clause in the signature | 0 | 0 | error |
| (f) | 1 line | 0 | 0 | error |
