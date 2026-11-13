# Readiness check, cancellation round 5

This is a readiness pass, not a full review. I read:

- `round5.md`;
- `soundness-round4.md`, for its M1;
- programs 23–26 in `programs-r5/`, the only ones that changed;
- the grade rows of `dogfood-round5.md`.

I checked the D44 text against decisions.md batches 3–10, and against D40 Q4 as round 5 amends it.

**Count: 3 must-fix.**

1. One hole remains in the `within` fix.
2. Q8 leaves out two places where D44 departs from David's batch 10.
3. Q6 depends on a name that hasn't been cold-read.

Everything else is ready, or one small edit away.

## 1. Are the earlier must-fixes resolved?

| Finding | Resolved? | Evidence |
|---|---|---|
| Review round 4 MF1: a `?? default` in a `within` child hides a missed deadline | **Mostly. See M1.** | Program 24: `cache_lookup(key) ?? none` under `within(50ms …)` now gives `Timeout`, and `first_ok` waits for the database. But §1.1 implements "came through a handler that names `Canceled`" as *request state*, and that lets the hazard back in. |
| Review round 4 MF2: a compile error rejects children that were never canceled | **Yes** | Program 25: `within(2s @load_both)` compiles. An uncanceled child is published as a narrowed view, as at a join. A canceled one gives `Timeout`. Round 4's compile error is withdrawn. |
| Soundness round 4 M1: repeated non-error exceptions have no legal aggregate | **Yes, for soundness** | The error stack takes any exception except `Canceled`, and program 26 returns `ErrorStack[Stopped[1] Stopped[2]]`. This changes batch 10's stated stack type, which M2 covers. |

### M1. "The work's request records whether its cancellation was handled by naming it" lets an unrelated named test unlock a later default

§1.1 says the named-handler condition is "request state, not a tag on values". So any branch that names `Canceled`, anywhere in the child, marks the request. A later plain default then publishes again:

```dewy
from_cache = (key:string) => {
    let warm = cache_ping()                                  # the deadline lands here
    if warm is? Canceled log("cache slow: falling back")     # names Canceled: the request is marked
    cache_lookup(key) ?? none                                # Canceled again at once; ?? gives none
}
price = (key:string) => first_ok(@within(50ms @from_cache(key)) @db_get(key))   # price is none
```

That is exactly the round 4 hazard: `first_ok` takes `none` and cancels the database lookup. The D44 Q8 row, "unless the child's value came from a branch that names `Canceled`", describes the right rule. It is about the *value's* path. §1.1's mechanism doesn't implement that rule.

**Fix.** Decide it at the return site, statically:

- A return or final expression that sits lexically inside a branch that names `Canceled` sets the "kept" bit when it executes.
- Any other return leaves the bit clear.

Program 23's `<Canceled> => return best` still qualifies, and `from_cache` above gives `Timeout`. In §1.1, replace "The work's request records whether its cancellation was handled by naming it. That is request state, not a tag on values." with:

> Whether a value was returned from a branch that names `Canceled` is decided at the return site; the runtime records which kind of return ended the child. That is request state, not a tag on values.

### M2. Q8 leaves out two departures from batch 10

1. **The stack's type.** Batch 10 defines the error stack as `type of error & array`. D44 makes it an `error` only when every element is one, and an `exception` otherwise. Q8's row cites only "D42 Q6", which is the stack's *name* question. In the row "The error stack may hold any exception except `Canceled`", change the Against cell from `D42 Q6` to `batch 10 (the stack was an error); D42 Q6`.
2. **`??` uniformity at `within`.** David said today that `Canceled` "ought to behave uniformly under `??` / `or_throw`". Inside the child it still does: `?? none` consumes it. But after the deadline, `within` keeps the value only if it came from a branch that names `Canceled`. So `x ?? none` and `x ??<Canceled | Miss> none` now give different results at the deadline. That is the one place where how `Canceled` was consumed matters. David should see it named. In the `within` row, change the Against cell from `` `within` `` to:

   > `within`; batch 10's uniform `??`: a plain `??` still consumes `Canceled` in the child, but `within` then gives `Timeout`

### M3. Q6 depends on `UndoFailed`, which hasn't been cold-read

Q6's Rec says so itself: "`UndoFailed` is a new error family, not yet cold-read". AGENTS.md requires the cold read before a name reaches open_decisions.md. Run it against two or three candidates, such as `UndoFailed`, `PersistingUndoFailed` and `UnreversedEffect`. Then replace that sentence with the result, for example "`UndoFailed` was read correctly cold (3/3, …)". If the name fails, rename it everywhere in D44 and the knock-on edits.

## 2. Is each question ready as written?

**The format checked:**

- a minimal example, with its enclosing function where the question is about leaving it;
- the question in one sentence;
- **Rec:** with reversibility;
- a "You give up:" line;
- no history or trivia.

| Q | Verdict |
|---|---|
| Q1 | Not ready. One edit. |
| Q2 | Ready. |
| Q3 | Ready. |
| Q4 | Ready. |
| Q5 | Ready. |
| Q6 | Not ready: M3, plus an example edit. |
| Q7 | Ready. |
| Q8 | Not ready: M2's two cells, plus one row edit. |

### Q1: not ready (one edit)

The structure is right: the enclosing function, calls from `main` and from an item, one sentence, a Rec with reversibility, and a give-up line. But the example doesn't type-check:

- `show(home) or_throw` passes `string | HttpError` to `show`;
- if `show` is void, the `or_throw` also triggers David's own "`or_throw` forwards nothing" warning;
- `news` is bound in a scoped `{}` block and never used.

**Edit.** Replace example lines 55–58:

```dewy
    parallel {
        let news = fetch_text("https://example.org/news")   # string | HttpError | Canceled
        show(home) or_throw
    }
```

with:

```dewy
    parallel {
        printl(fetch_text("https://example.org/news") ?? "no news")   # inside: string | HttpError | Canceled
        printl(home ?? "offline")
    }
```

### Q2: ready

- **Example.** The enclosing function `probe` shows both ways to leave it (`return Failed and …`, `return Canceled`) and all four errors.
- **Question.** One sentence, then its list.
- **Rec and give-up.** Both present, and "`??` and `or_throw` treat it like any failure" matches David's words.

Optional polish:

- a blank line between the four-item list and the Rec bullets, so Markdown doesn't merge them;
- `;` after the `protect_from_cancel(…)` line, since its result is dropped.

### Q3: ready

- **Example.** The enclosing function returns `n` after the block. This isn't a leave-the-function question.
- **Question.** One sentence plus a one-line context sentence.
- **Rec, reversibility and give-up.** All present, and the give-up covers bindings, locks across waits and the canceled tail.

### Q4: ready

- **Example.** It shows the caller and the worker's `select` with both arms. `<Canceled> => return` leaves `serve_jobs`, which is shown.
- **Question.** One sentence.
- **Rec, reversibility and give-up.** Present. The give-up names both limits: nothing checks the request is passed, and "gave up" and "finished" look the same.

### Q5: ready

- **Example.** It shows both enclosing functions, and a line after the loop that still runs.
- **Question.** One sentence.
- **Rec, reversibility and give-up.** Present.

The Rec's "replaces `merged`'s … rule" is the reason, not history.

### Q6: not ready

There are three issues:

1. **The cold read.** Run it, per M3.
2. **The example.** `migrate = () => race(@apply_on(primary) @apply_on(replica))` races one migration against itself on two databases, which isn't something a program would do. Replace those two lines with a case that is natural and still involves an `UndoFailed`:

   ```dewy
   fastest = (args:array<string>) => race(@run_tool("rg" args) @run_tool("grep" args))
   # error: a loser's ProcessStopFailed (an UndoFailed) can't be discarded; handle it in run_tool
   ```

3. **Two parents.** Under D42 Q5's vocabulary, `RollbackFailed` sits under `DbError` and `ProcessStopFailed` under `ProcessError`. Being an `UndoFailed` as well needs two parents. Add one clause to Q6's question or to the D40 Q4 knock-on edit:

   > (`RollbackFailed:type = type of DbError & UndoFailed`; `ProcessStopFailed` likewise under `ProcessError`)

The question sentence, Rec, reversibility and give-up are otherwise fine.

### Q7: ready

- **Example.** The tag sits at the top of `main`'s body, as batch 9's placement rule requires.
- **Question.** One sentence.
- **Rec, reversibility and give-up.** Present. The give-up ("nothing by default") is the honest one.

It uses `backup_to` from Q6's example, which is acceptable within one D44 section.

### Q8: not ready

1. **The two cells.** Make M2's two changes to the Against column.
2. **History in one row.** The `??` loop row says "(it was a warning)". D42 Q2's warning was only ever proposed, never documented behaviour, so that is history and not accurate. Replace the row:

   | A `??` that falls back round a loop on a closed wait is an error where the wait is visible (it was a warning) | `jobs.receive ?? continue` | D42 Q2 |
   |---|---|---|

   with:

   | `select`'s progress rule also covers a `??` fallback on a wait in a loop: an error where the wait is visible | `jobs.receive ?? continue` | LANGUAGE.md's `select` progress rule; replaces the open D42 Q2 |
   |---|---|---|

The example, question sentence, Rec, reversibility and give-up are otherwise fine.

## 3. Contradictions with decisions batches 3–10 and the amended D40 Q4

Apart from M2, I found none:

- **Batch 3 C3.** A sibling now keeps only what it *forwarded*, which is C3's own exit, plus its cleanup failures. A marked item's `or_throw` is listed in Q8.
- **Batches 4, 5 and 10.** `Canceled` is ordinary under `??` and `or_throw`. `$explicit_cancellation` is restated as a knock-on edit to the open D42 Q3.
- **Batch 7.** The `select` change is in Q8. `race`, `first_ok` and `Task`'s names are unchanged.
- **Batches 8 and 9.** Every marker prefixes its construct, and `$no_discarded_failures` sits at the top of a function body. The signal-closure rule is unchanged, and "cancellation leaves the loop" is Q5. `parallel ( … )` exports a binding (Q3's `n`).
- **D40 Q4, as amended.** It stays consistent with batch 9's "`$__abandon__` … throws its work away". The amendment only adds which failures count as failed undos, and Q6 is the question that puts that to David.
  - The files module's "temporary file removed in its drop hook" agrees with "a staging file's failed removal is ordinary cleanup, whichever hook removes it".
  - The two-parent clause in Q6's edit 3 is the only gap.

## 4. Programs

Only programs 23–26 changed.

**Program 23.** Only its comments changed, so its grades stand (4/4/5/5/5).

The new programs:

| # | Program | Obvious | Discoverable | Concise | Safe | Complete | Cited lines |
|---|---|---|---|---|---|---|---|
| 24 | within: a default vs a named branch | 4 | 4 | 5 | 5 | 5 | O 5–7: the child's `none` is ignored after the deadline; D 3 and 11: `??<~Canceled>` versus `??` has to be learned |
| 25 | a pair under one deadline | 5 | 5 | 4 | 5 | 5 | C 9: the arm spells out the whole record type |
| 26 | repeated sibling failures | 3 | 3 | 4 | 5 | 5 | O 14 and 23–25: a `return` from `run` becomes a stack of the workers' stops; D 18–20: only hover shows that `run` can give one, either or both; C 18–21: three arms for none, one or several |

Program 26 is a specimen for an edge case (workers that turn their own cancellation into a failure), not a typical program. Its 3s are the price of retaining forwarded failures, which D40 Q1 and D42 Q1 require.

**Floor:**

| | Floor | Programs at it |
|---|---|---|
| Mine | 3 | 08 (discoverable), 26 (obvious, discoverable) |
| The author's | 3 | 08 only |

No grade differs from the author's by 2 or more: 26's obvious and discoverable and 25's discoverable and concise each differ by 1.

## Verdict

After M1's one-sentence fix to §1.1 and the edits above, D44 is ready to paste:

| Q | Ready? | What's needed |
|---|---|---|
| Q1 | After one edit | Replace the four example lines (§2) |
| Q2 | Yes | — |
| Q3 | Yes | — |
| Q4 | Yes | — |
| Q5 | Yes | — |
| Q6 | After the cold read and two edits | Cold-read `UndoFailed`; replace the `migrate` example; add the two-parent clause |
| Q7 | Yes | — |
| Q8 | After three cell and row edits | M2's two Against cells; replace the `??` loop row |
