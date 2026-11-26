# 14. Returning an owner while another close is pending, and one `defer` spelling's three exit sets

New in round 10. `handoff` is the review's counterexample; `settle` shows on one function how the
same `defer` line covers different exits.

## The replaced owner

```dewy
import p"@lib/std/files.dewy" as files

handoff_round9 = (dir:Path) => {
    let receipt = files.open(p"{dir}/r.txt" 'w') or_throw
    defer receipt.close() or_throw
    let body = files.open(p"{dir}/body.txt" 'w') or_throw
    body.write_text("x") or_throw;
    body
}
```

Under round 9, if `receipt`'s close failed after `body` was computed, the failure replaced
`body`, which was then dropped: its flush ran implicitly, and implicit cleanup can't fail, so its
buffered text was lost with no report. Round 10 rejects it:

```text
error: handoff_round9 returns body (FileWriter, line 4) at line 6, but receipt's deferred close
       (line 3) can still fail after that, and body would then be dropped unfinished.
       Close receipt before returning:  receipt.close() or_throw
```

(Round 9 also reported `body` as open if its write fails; that error is unchanged.)

```dewy
handoff = (dir:Path) => {
    let receipt = files.open(p"{dir}/r.txt" 'w') or_throw
    defer receipt.close() or_throw
    let body = files.open(p"{dir}/body.txt" 'w') or_throw
    defer body.close() or_throw        # failure exits only: the return moves body
    body.write_text("x") or_throw;
    receipt.close() or_throw           # turns receipt's defer off; if it fails, body's defer closes body
    body                               # no defer that can fail is live here
}
```

The same rule covers a block's value and a lazy body's item:

```dewy
let w = {
    let tmp = files.open(p"scratch.txt" 'w') or_throw
    defer tmp.close() or_throw
    files.open(p"out.txt" 'w') or_throw    # error: the block's value owes, and tmp's close can fail after it
}
```

A value whose failure-exit cleanup can't fail (a `Socket`, which aborts) may be replaced, since
nothing is lost.

## One spelling, three exit sets

```dewy
settle = (db:Db dir:Path) => {
    let log = files.open(p"{dir}/settle.log" 'a') or_throw
    defer log.close() or_throw          # (1) every exit: nothing consumes log
    let tx = db.begin() or_throw
    defer tx.rollback() or_throw        # (2) failure exits: every success path must consume tx
    let report = files.open(p"{dir}/report.txt" 'w') or_throw
    defer report.close() or_throw       # (3) failure exits: the return moves report out
    let total = tx.settle_all() or_throw
    log.write_text("settled {total}\n") or_throw;
    report.write_text("total {total}\n") or_throw;
    tx.commit() or_throw
    report                              # error: log's close can still fail after this (§1)
}
```

Which exits each line covers isn't on the line: it follows from `commit` and the return further
down. A Go reader gets (2) right, since `Rollback` after `Commit` is a no-op there, and (3) wrong.
The last line is also §1's error: the function returns an owner while `log`'s close is pending.
Fixed:

```dewy
    tx.commit() or_throw
    log.close() or_throw
    report
```

## Scores

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 4 | 5 | 4 | 5 | 5 |

Obvious 4: the three exit sets. Concise 4: an explicit close before returning an owner, in a
function that already has a `defer` for it. Rust returns `body` and drops `receipt` silently;
Python's `with` around `receipt` would raise from `__exit__` after `body` is computed and drop
`body`, flushing it in its finalizer, where a failure is only printed: the same hole.
