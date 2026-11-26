# 13. Three writers, and an early `return expensive()`

David's `somefn` ([answers-r8.md](../answers-r8.md)), made concrete. `export_all` writes rows to
a CSV file, a JSON file and an index. With no rows it returns early with the result of an
expensive call. Each writer's close can fail; a failure in one must not stop the others from
closing.

```dewy
import p"@lib/std/files.dewy" as files
Row:type = [id:int name:string]
```

## A. One `defer` that builds the stack by hand (David's sketch)

```dewy
export_all = (dir:Path rows:array<Row>) => {
    let csv = files.open(p"{dir}/rows.csv" 'w') or_throw
    let json = files.open(p"{dir}/rows.json" 'w') or_throw       # (1)
    let index = files.open(p"{dir}/index.txt" 'w') or_throw
    defer {
        let errors = ErrorStack                                  # (2)
        errors &= csv.close()
        errors &= json.close()
        errors &= index.close()
        if errors.length >? 0 return errors                      # (3)
    }
    if rows.length =? 0 return summarize_empty(dir)
    loop row in rows {
        csv.write_text("{row.id},{row.name}\n") or_throw;
        json.write_text("{row}\n") or_throw;
        index.write_text("{row.id}\n") or_throw;
    }
    rows.length
}
```

1. **Acquisition order.** If `json`'s open fails, `csv` is open and the `defer` isn't registered
   yet. Under David's rule ("leaving it unhandled is a compile error") this is an error at line
   2. Any `defer` written once after all acquisitions has this bug; each value needs its
   handling registered right after it exists. Go and Zig code puts each `defer` under its
   acquisition for the same reason.
2. **An empty stack.** D42 Q4 has the stack never empty, so starting from one needs a new rule
   (or starting from `void`, with `void &= e` giving `e`).
3. **`return` from a `defer`** replaces whatever was leaving. If a write already failed, that
   failure is lost unless the `defer` can see and include it, which needs a way to name the
   leaving value inside the `defer` (new syntax). And a `return v` in a `defer` could replace a
   success value with another, which is Java's `return` in `finally`, a well-known lint.

It is also seven lines for three values. What it gets right is the point of the exercise: every
close runs, and the folding is visible.

## B. One `defer` per value, folding automatically (recommended)

```dewy
export_all = (dir:Path rows:array<Row>) => {
    let csv = files.open(p"{dir}/rows.csv" 'w') or_throw
    defer csv.close() or_throw
    let json = files.open(p"{dir}/rows.json" 'w') or_throw       # fails: csv's defer runs
    defer json.close() or_throw
    let index = files.open(p"{dir}/index.txt" 'w') or_throw
    defer index.close() or_throw
    if rows.length =? 0 return summarize_empty(dir)
    loop row in rows {
        csv.write_text("{row.id},{row.name}\n") or_throw;
        json.write_text("{row}\n") or_throw;
        index.write_text("{row.id}\n") or_throw;
    }
    rows.length
}
```

At each exit the defers that are registered run in reverse (index, json, csv). Every one runs
even if an earlier one failed. A deferred `or_throw` doesn't leave on its own: it adds its failure
to what is leaving. Then:

| What failed | `export_all` gives |
|---|---|
| nothing | the value: `rows.length`, or `summarize_empty`'s result |
| one thing (a write, or one close) | that failure, bare |
| several (a write and a close, or two closes) | `ErrorStack[…]` in the order they happened: the body's failure first, then the closes in the order they ran |

Its failure type: `FileOpenFailed | FileWriteFailed | FileCloseFailed |
ErrorStack<FileWriteFailed | FileCloseFailed>` (with D42 Q3's leaves). A caller's
`??<FileCloseFailed>` takes one failed close; two are forwarded as a stack, never swallowed (D42
Q6's rule).

### Alone or always a stack?

| | One failure | Several | Result type | A handler for one kind |
|---|---|---|---|---|
| **Alone, then a stack** (recommended) | bare | stack, ordered | `T \| E1 \| E2 \| ErrorStack<E1 \| E2>` | takes the common case |
| Always a stack once a `defer` fails | `ErrorStack[E]` | stack | `T \| E1 \| ErrorStack<E1 \| E2>` | misses a lone failed close; every caller writes `??<ErrorStack<…>>` |
| D42's laws (`&` across kinds, a stack within one) | bare | `E1 & E2`, or a stack, or both | `T \| E1 \| E2 \| E1 & E2 \| ErrorStack<E1> \| ErrorStack<E1> & E2 \| …` | takes the common case |

"Alone, then a stack" keeps David's simple result type except for one bare member per kind, and
keeps the order (which matters to a reader: the write failed, *then* the close). D42's laws give
2ⁿ-shaped types and lose the order. `Canceled` stays outside the stack, as D44 requires:
`Canceled & ErrorStack[…]`.

## C. Closes combined at each exit

```dewy
    if rows.length =? 0 {
        let summary = summarize_empty(dir)
        (index.close() & json.close() & csv.close()) or_throw
        return summary
    }
    …
    (index.close() & json.close() & csv.close()) or_throw
    rows.length
```

Go's `errors.Join(a.Close(), b.Close())`. It covers only the exits where it is written; the
failure exits (an open or a write failing) still need defers, so it adds to B instead of
replacing it. It also needs `void` to be `&`'s identity and `&` on these values to evaluate both
sides; `and` short-circuits on booleans (LANGUAGE.md), so this would be a new rule.

## D. One marker for the scope (round 7, round 8's (b))

```dewy
export_all = (dir:Path rows:array<Row>) => {
    let csv = files.open(p"{dir}/rows.csv" 'w') or_throw
    let json = files.open(p"{dir}/rows.json" 'w') or_throw
    let index = files.open(p"{dir}/index.txt" 'w') or_throw
    if rows.length =? 0 return summarize_empty(dir)
    …
    rows.length
} or_throw
```

One token. It covers every exit and every value, which is its strength and its problem under
David's direction: no line says which values it folds, and `} or_throw` reads as running at the
bottom. With B available it is a second way to say the same thing.

## E. One owner for the three

```dewy
    let outs = [csv json index]                  # an array of writers owes what they owe
    defer drop(outs) or_throw
```

Useful when the writers form a collection anyway (program 06). Here it only renames B.

## When the defers run: `return summarize_empty(dir)`

Under David's timing, `summarize_empty(dir)` runs and produces its value; then index, json and
csv close; if any close failed, `export_all` gives the failure (or the stack) instead of the
summary, and the summary is dropped. Alternatives:

| Rule | What happens here |
|---|---|
| **David's: after the exit's value, before leaving** (recommended) | the summary is computed, the closes run, a failure replaces it |
| Before the return expression | `summarize_empty` could no longer use the writers (`return finish(@csv)` breaks) |
| Go: at function end, results assigned first; a deferred closure may rewrite a named result | same order, but the rewrite is arbitrary code assigning a variable; and a `defer` in a loop waits for the function's end |
| Zig, Swift: at scope end, can't fail or leave | the closes can't report: back to round 8's explicit closes at each exit |
| Java `finally` with `return` | replaces anything, including a failure already leaving: lossy |
| Python `__exit__` | runs after the value; may raise (chaining) or *suppress* the body's exception by returning true |

If `summarize_empty` is costly and a close is likely to fail, the function can close first and
call after; that is ordinary code (`csv.close() or_throw` before the `return`, which turns off
`csv`'s defer on that path).

## Scores (B)

| | Added over (a) | Hidden | Forgotten |
|---|---|---|---|
| A | 7 lines; error at line 2 | 0 | — |
| **B** | 3 lines | 0 | error at the first fallible line after an open |
| C | 3 lines + 2 groups, and B's defers for failure exits | 0 | error |
| D | 1 token | 0 | error |

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 4 → 5 | 5 | 5 | 5 | 5 |

Obvious 4 → 5 (iteration 5): a reader of `return summarize_empty(dir)` alone doesn't see that a
close can replace its value. The editor's exit hint ("then: close index, json, csv") at each exit
closes it, as it does for Python's `with`, whose readers have the same question. Go writes three
`defer`s and loses the failures (or writes a named-result closure per file); Python nests three
`with`s or uses an `ExitStack`; Rust and Swift write nothing and lose them; TypeScript writes three
`using`s and gets a `SuppressedError` chain.
