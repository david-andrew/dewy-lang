# Cleanup round 8: who handles a failed cleanup

Synthesis of four independent brainstorm answers (answers 1–4) on reopened D40 Q1.

## The question

D40 Q1 (decided 2026-11-12) made a value's failed cleanup (a file's final flush, a socket
close) the result of the function that owned it, with nothing written:

```dewy
save = (data:array<uint8>) => {
    let out = open(p"/mnt/usb/data.bin" 'w') or_throw
    out.write_bytes(data) or_throw;     # buffered
}                                        # out flushes and closes here; a full disk fails HERE
first_row = (rows) => {
    loop row in rows { return row }      # rows' socket closes when first_row returns
    none
}
```

David reopened it: nothing in `first_row` forwards the socket's failed close, and `save`'s
`or_throw` forwards the write, not the flush at `}`. A failure appearing in the caller is hidden
nonlocal behavior. He wants warnings for unhandled cleanup failures and a metatag to forbid them.

## One cleanup point or several?

All four answers agree: **one owning scope, several possible exits.** A value is cleaned up
once per run, but the compiler only knows the set of places where it might be:

- `save` has two exits: the write's `or_throw` and the closing brace.
- `first_row` has two: `return row` and the fallthrough to `none`. The socket is not a separate
  point; it closes inside the generator's cleanup, wherever `rows` is dropped.
- A loop body adds `break`, `continue` and the end of each iteration.
- A move removes the exit on that path: `if keep { return out }`, `opened.push(f)`. The new
  owner (the caller, the array) takes over the duty. Lending with `@` leaves it with the lender.
- A reassignment (`out = open(other 'w')`) drops the old value mid-block, not at an exit; so
  would last-use timing (D40 Q2's alternative), at each branch's last read.

Everything here is known at compile time: the owning scope, its exits, and on which exits the
value may still be live (drop flags merged conservatively, as in round 7). Only which exit runs,
and whether the hook fails, is left to run time.

Consequence: a line at the end of the scope doesn't cover the value, because `return` and
`or_throw` never reach it. A form must cover every exit, as a scope marker or a `defer` does.

## Common baseline (all four)

- A cleanup hook never silently adds a failure to a function's result.
- An unhandled fallible cleanup is a **compile warning** naming the value, the exit and the
  failure type. At run time the cleanup still runs and its failure is discarded.
- A **strict metatag** (placeholder names in the answers: `$explicit_cleanup`,
  `$strict_cleanup`; likely in `$bulletproof`) makes the warning an error. It may merge with
  D44 Q7's `$no_discarded_failures` into one general tag.
- Explicit consuming calls keep working: `out.close() or_throw`, `out.close() ?? log(…)`, or a
  generic `drop(x)` that returns the hook's result. A consumed value has no duty left.

## Option A: mark the owning scope (answers 2, 3, 4)

```dewy
save = (data:array<uint8>) => {
    let out = open(p"/mnt/usb/data.bin" 'w') or_throw
    out.write_bytes(data) or_throw;
} or_throw
first_row = (rows) => {
    loop row in rows { return row }
    none
} or_throw
```

- Round 7's rule already makes `{ … } or_throw` acknowledge a block's cleanup on every exit,
  jumps included, and D40 Q6 requires it on locally continuing exits. This removes the
  function-exit exemption. No new syntax.
- Checks: a scope that may drop a fallible value on some exit needs a suffix whose selector
  covers that cleanup's failure types. Bare `or_throw` always does, and is allowed on
  infallible instances, so generic code carries it without forking. Inner continuing blocks
  need their own marker (as in Q6).
- Handling instead of forwarding: `} ??<FileCloseFailed> void`. That replaces the block's
  value, so it suits `save` but loses `first_row`'s row; there, close explicitly or lend.
- On a function body, forwarding the body's value is the same as returning it, so the suffix
  only says where cleanup failures go. On an inner block that yields a value, the suffix also
  selects that value (bare `or_throw` forwards a `none`; `or_throw<error>` keeps it).
- In `lazy { … } or_throw`, the forwarded failure becomes the generator's own cleanup failure,
  so its owner is marked one level up.
- Cost: one token per owning scope; covers several values at once. Two values needing different
  handling need a nested block or an explicit close.

## Option B: `defer` tied to the value (answer 1)

```dewy
save = (data:array<uint8>) => {
    let out = open(p"/mnt/usb/data.bin" 'w') or_throw
    defer out.close() or_throw
    out.write_bytes(data) or_throw;
}
first_row = (rows) => {
    defer drop(rows) or_throw        # generic: works for any owner, no-op if infallible
    loop row in rows { return row }
    none
}
```

- The `defer` consumes the named value and runs on every exit where it is still owned; its
  result takes ordinary handling (`or_throw`, `??`, `;`). It discharges the automatic hook.
- Checks: the deferred expression handles its result; the value leaves the unhandled set.
- Strengths: the decision sits beside the acquisition; each value has its own handling; no
  conflation with a block's value; no `loop … ({ … } or_throw)` grouping; works under either
  timing rule.
- Cost: one line per value; `defer` becomes fallible, reversing D40 Q5's provisional rule (and
  round 7's recommendation to drop it); generic code needs a universal consuming verb (`drop(x)`
  or `close()` on any type).

## Other ideas raised

- **On the binding** (all four): `let out drop or_throw = …` or `$forward_cleanup let out = …`.
  Covers every exit and reassignment under either timing; new grammar or tags per owner.
- **Scope-top tag** `$forward_cleanup` (1): a metatag that changes a result type.
- **Explicit close only** (1, 2, 3): every early exit needs its own close.
- **Library wrappers** `with_file(path 'w' (@out) => …)` (4): callbacks for every resource.
- **Call-site note** (3): warn at `first_row(db.rows("users"))` if the callee drops it unmarked.

## Where the answers agreed and disagreed

Agreed: one owning scope with several compile-time-known exits; a move hands the duty over; the
warning plus strict metatag baseline; explicit consuming calls stay; failure edges join with `&`.

Disagreed:
- **Form:** scope marker (2, 3, 4) versus value-tied `defer` (1).
- **Default severity:** warning with run-time discard (1, 3, 4) versus requiring the marker (2).
- **Failure exits:** answer 3 checks only exits that would otherwise succeed (on an `or_throw`
  line a joining cleanup failure isn't hidden); the others check every exit.
- **Grouping:** answer 4 writes `=> ({ … } or_throw)`; answers 2 and 3 put the suffix directly on
  the body. The parse needs settling.
- **Moves after `defer`:** answer 1 lets a move silently cancel the `defer`; answers 3 and 4 say
  the `defer` pins the value, forbidding a later conditional move.
- **What the strict tag rejects:** answer 2 also rejects a discard that doesn't name the failure
  type (`?? void`); the others allow any written discard.

## Risks of the scope marker

- **Two jobs for one suffix.** On a value-yielding inner block it both selects the value and
  authorizes cleanup; a selective suffix that misses the hook's type is an error.
- **Read as fallthrough-only.** `}` then `or_throw` may look like it runs only at the bottom.
  Highlighting and hover should point from each covered exit (`return row`) to its marker and
  list the values and failures it covers.
- **Reflexive boilerplate.** `} or_throw` on every body that touches a resource would bring D40
  Q1 back as habit. Mitigation: an "unneeded marker" lint where no fallible duty exists.
- **Depends on block-end timing.** If D40 Q2 picks last use, mid-block drops are not exits of
  the marked scope; the binding clause becomes the fallback spelling with the same check.
- **Mid-block drops.** Reassignment drops the old value before the scope ends; it needs an
  explicit close or gets the warning at the assignment.
