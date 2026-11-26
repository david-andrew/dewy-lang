# 04. A transaction

`transfer` moves money. A replayed request is already applied, so it leaves early with success.
A short balance returns `Declined`, a failure exit. `rename_account` forgot its commit.

## (g) Written cleanup

```dewy
Declined:type = type of error & [balance:int]

transfer = (db:Db request:RequestId from:AccountId to:AccountId amount:int) => {
    let tx = db.begin() or_throw
    defer tx.rollback() or_throw                          # fires only on failure exits
    if tx.applied(request) or_throw { tx.rollback() or_throw; return }
    let balance = tx.balance(from) or_throw
    if balance <? amount return Declined[balance]         # rolls back; both failing: ErrorStack[Declined RollbackFailed]
    tx.add(from 0-amount) or_throw;
    tx.add(to amount) or_throw;
    tx.mark_applied(request) or_throw;
    tx.commit() or_throw                                  # consumes tx: the defer is off on this path
}
```

The `defer` is Zig's `errdefer`, with no second keyword: every success path must consume `tx`
(rule 5), so the deferred rollback can only ever run on a failure exit. A failed commit consumes
`tx` too (D42, D43), so the defer doesn't run after it.

`rename_account`:

```text
error: tx (Transaction, line 2) is uncommitted where rename_account ends (line 4).
       Its changes would be rolled back.
       Commit them:  tx.commit() or_throw
       or roll back: tx.rollback() or_throw
```

`defer tx.commit() or_throw`:

```text
error: a defer runs on failure exits, and tx.commit() publishes the work.
       Commit where the work ends, and defer the rollback:  defer tx.rollback() or_throw
```

The compiler knows `rollback` abandons because `Transaction` assigns it as its abandon
(`$__abandon__ = rollback`, batch 9's assignment form).

## (g-auto)

```dewy
transfer = (db:Db request:RequestId from:AccountId to:AccountId amount:int) => {
    let tx = db.begin() or_throw
    if tx.applied(request) or_throw { tx.rollback() or_throw; return }
    let balance = tx.balance(from) or_throw
    if balance <? amount return Declined[balance]         # rolls back; a failed rollback joins, unwritten
    tx.add(from 0-amount) or_throw;
    tx.add(to amount) or_throw;
    tx.mark_applied(request) or_throw;
    tx.commit() or_throw
}
```

## Scores

| | Added over (a) | Hidden | Forgotten `commit` |
|---|---|---|---|
| (g) | 1 line, 1 brace group, 1 call | 0 | error naming the commit |
| (g-auto) | 1 brace group, 1 call | 0 | error naming the commit |

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 5 | 5 | 4 | 5 | 5 |

Concise 4, as in round 8: the replay exit rolls back explicitly. Python's `with conn:` commits
on any normal exit (the replay would commit, harmlessly here, wrongly in general); Go writes
`defer tx.Rollback()` and a forgotten commit is silent; `sqlx` rolls back silently on drop.
