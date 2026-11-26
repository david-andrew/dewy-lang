# 15. Handling a stack of unlike failures

New in round 10. Program 04's `transfer` with a low balance, when the deferred rollback fails
too, gives `ErrorStack[Declined RollbackFailed]` (D42 Q4 may rename it `ErrorList`). Each
handler form, under round 10's law:

```dewy
Declined:type = type of error & [balance:int]

show = (db:Db req:RequestId from:AccountId to:AccountId) => {
    let r = transfer(db req from to 500)

    if r is? Declined printl"declined"                     # true: is? sees elements, as it sees & parts
    if r is? RollbackFailed printl"rollback failed too"    # true

    let d = r as Declined?                                  # the Declined element: exactly one is a Declined
    if d is? Declined printl"balance was {d.balance}"

    loop part in r.$parts printl("{part.$origin}: {part}" file=stderr)   # in order: Declined, then RollbackFailed

    r ??<Declined> void or_throw;                           # not consumed: a ??<E> never takes a stack, so
                                                            # the stack (and its UndoFailed) is forwarded
}

retry_on_decline = (db:Db req:RequestId from:AccountId to:AccountId) => {
    transfer(db req from to 500) or_throw<RollbackFailed>;  # leaves with the whole stack: an element is a RollbackFailed
}

accept_both = (db:Db req:RequestId from:AccountId to:AccountId) => {
    transfer(db req from to 500) ??<ErrorStack<Declined | RollbackFailed>> void or_throw;   # consumed: every element fits
}

report = (r:int | Declined | ErrorStack<Declined | RollbackFailed>) => match r {
    n:int => printl"moved {n}"
    d:Declined => printl"declined at {d.balance}"           # never receives the stack
    s:ErrorStack<Declined | RollbackFailed> => printl"declined, and the rollback failed: {s}"
}
```

**Appending.** If `transfer` had called a helper that returned `ErrorStack[A B]` and the deferred
rollback then failed, the result is `ErrorStack[A B RollbackFailed]`, not a stack inside a stack.

## Against `&` (today's D42)

| | `Declined & RollbackFailed` | `ErrorStack[Declined RollbackFailed]` |
|---|---|---|
| `is? Declined` | true | true |
| `??<Declined>` | forwards (narrow rule) | forwards |
| `??<Declined \| RollbackFailed>` | consumes | forwards; `??<ErrorStack<Declined \| RollbackFailed>>` consumes |
| order | none | kept |
| type of a function with three fallible cleanups | 2ⁿ combinations | one stack type |

The one behavior that changes is the third row: a union handler no longer takes a combination
without naming the stack. That is D42 Q6's choice (a handler for one failure kind gets one
failure) extended to unlike kinds.

## Scores

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 5 | 4 → 5 | 5 | 5 | 5 |

Discoverable 4 → 5: that `??<Declined | RollbackFailed>` doesn't take the stack is learned when the
forwarded stack reaches `main`; the compiler can warn when a union handler covers every element
type of a stack in the input but doesn't name the stack ("this handler doesn't take
ErrorStack<Declined | RollbackFailed>; name it to handle both"). Round 10 adds that warning.
