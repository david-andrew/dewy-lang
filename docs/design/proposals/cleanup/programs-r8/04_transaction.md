# 04. A transaction

`transfer` moves money. A replayed request is already applied, so it leaves early with success.
A short balance returns `Declined`, a failure exit. `rename_account` forgot its commit.

## (a) Implicit

```dewy
Declined:type = type of error & [balance:int]

transfer = (db:Db request:RequestId from:AccountId to:AccountId amount:int) => {
    let tx = db.begin() or_throw
    if tx.applied(request) or_throw return              # success exit: tx rolls back
    let balance = tx.balance(from) or_throw
    if balance <? amount return Declined[balance]       # failure exit: Declined & RollbackFailed if both
    tx.add(from 0-amount) or_throw;
    tx.add(to amount) or_throw;
    tx.mark_applied(request) or_throw;
    tx.commit() or_throw                                # consumes tx on every outcome (D42)
}

rename_account = (db:Db id:AccountId name:string) => {
    let tx = db.begin() or_throw
    tx.set_name(id name) or_throw;
}   # forgot tx.commit(): the rename rolls back, and rename_account succeeds
```

On the replay exit a failed rollback becomes `transfer`'s result, unwritten. `rename_account`
returns success having changed nothing.

## (b) Marked scope

```dewy
transfer = (db:Db request:RequestId from:AccountId to:AccountId amount:int) => {
    let tx = db.begin() or_throw
    if tx.applied(request) or_throw return
    let balance = tx.balance(from) or_throw
    if balance <? amount return Declined[balance]
    tx.add(from 0-amount) or_throw;
    tx.add(to amount) or_throw;
    tx.mark_applied(request) or_throw;
    tx.commit() or_throw
} or_throw

rename_account = (db:Db id:AccountId name:string) => {
    let tx = db.begin() or_throw
    tx.set_name(id name) or_throw;
} or_throw      # acknowledges the rollback's failure; the forgotten commit stays
```

## (c) Value-tied `defer`

```dewy
transfer = (db:Db request:RequestId from:AccountId to:AccountId amount:int) => {
    let tx = db.begin() or_throw
    defer tx.rollback() or_throw        # canceled on the path where commit consumes tx
    if tx.applied(request) or_throw return
    let balance = tx.balance(from) or_throw
    if balance <? amount return Declined[balance]
    tx.add(from 0-amount) or_throw;
    tx.add(to amount) or_throw;
    tx.mark_applied(request) or_throw;
    tx.commit() or_throw
}

transfer_wrong = (db:Db from:AccountId to:AccountId amount:int) => {
    let tx = db.begin() or_throw
    defer tx.commit() or_throw          # Go habit: commits on every exit
    tx.add(from 0-amount) or_throw;
    tx.add(to amount) or_throw;         # fails: the defer commits half a transfer
}
```

## (d) Explicit close

```dewy
transfer = (db:Db request:RequestId from:AccountId to:AccountId amount:int) => {
    let tx = db.begin() or_throw
    if tx.applied(request) or_throw { tx.rollback() or_throw; return }
    let balance = tx.balance(from) or_throw
    if balance <? amount return Declined[balance]
    tx.add(from 0-amount) or_throw;
    tx.add(to amount) or_throw;
    tx.mark_applied(request) or_throw;
    tx.commit() or_throw
}
```

`rename_account` warns at `}` that `RollbackFailed` is discarded. That points at the forgotten
commit by accident; the warning's own fix-it would add `tx.rollback() or_throw`.

## (e) Disposition on the binding

```dewy
transfer = (db:Db request:RequestId from:AccountId to:AccountId amount:int) => {
    let tx drop or_throw = db.begin() or_throw
    if tx.applied(request) or_throw return
    let balance = tx.balance(from) or_throw
    if balance <? amount return Declined[balance]
    tx.add(from 0-amount) or_throw;
    tx.add(to amount) or_throw;
    tx.mark_applied(request) or_throw;
    tx.commit() or_throw
}
```

`rename_account` with the clause compiles and rolls back silently.

## (f) Finish on success, clean up on failure

```dewy
transfer = (db:Db request:RequestId from:AccountId to:AccountId amount:int) => {
    let tx = db.begin() or_throw
    if tx.applied(request) or_throw { tx.rollback() or_throw; return }
    let balance = tx.balance(from) or_throw
    if balance <? amount return Declined[balance]       # failure exit: rolls back by itself
    tx.add(from 0-amount) or_throw;
    tx.add(to amount) or_throw;
    tx.mark_applied(request) or_throw;
    tx.commit() or_throw
}
```

The replay exit is a success exit with work unpublished, so it says what happens to it. The
`Declined` exit is a failure exit, so the rollback is automatic and a failed rollback joins
(`Declined & RollbackFailed`). `rename_account`:

```text
error: tx (Transaction, line 2) is uncommitted where rename_account ends (line 4).
       Its changes would be rolled back.
       Commit them:    tx.commit() or_throw
       or roll back:   tx.rollback() or_throw
```

## Scores

| | Added over (a) | Hidden | Lossy | Forgotten `commit` |
|---|---|---|---|---|
| (a) | — | 1 | 0 | silent rollback, reported as success |
| (b) | 1 token | 0 | 0 | warning about the rollback; the fix-it keeps the bug |
| (c) | 1 line | 0 | 0 | silent; `defer commit` commits half a transfer |
| (d) | 1 brace group, 1 call | 0 | 0 | warning that happens to point at it |
| (e) | 1 clause | 0 | 0 | silent |
| (f) | 1 brace group, 1 call | 0 | 0 | error that names the forgotten commit |
