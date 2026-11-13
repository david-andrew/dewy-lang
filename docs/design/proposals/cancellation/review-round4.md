# Review, cancellation round 4

**Reviewed:**

- `round4.md`, with round 3's sections that it keeps;
- `programs-r4/` (23 programs);
- `dogfood-round4.md`, read after grading.

**Checked against:** `review-round3.md`, `soundness-round3.md`, decisions batches 3–10, D40–D42 and LANGUAGE.md.

**Count: 2 must-fix, 4 should-fix, 3 notes.**

Every earlier must-fix is resolved. The confinement rules are now complete, and the value model matches batch 10.

The two must-fixes are both in round 4's new `within` rule. Keeping a value that a canceled child handled is right for the best-move idiom, but:

- because `??` consumes `Canceled` like any failure (batch 10), a plain `?? default` inside a `within` child silently turns a missed deadline into a success;
- the rule's companion compile error rejects ordinary code whose child was never canceled at all.

Each needs only a narrower rule.

The questions are settled in substance, but not ready as text. Round 4 says Q1–Q5 are "as in round 3", and round 3 says Q1 and Q5 are "as in round 2". So David would have to assemble most questions from three documents, and several lack a question sentence, an enclosing function or what he gives up (Part 4).

## Part 1: earlier must-fixes

### `review-round3.md`

| Finding | Resolved? | Evidence |
|---|---|---|
| MF1: capture carries `Canceled` into another request | **Yes** | Rule 4 covers protected bodies, cleanup (receiver fields and `defer` captures) and tasks spawned into an outside group, by capture, argument or receiver. My registry scenario's `app.spawn(() => { pause or_throw; … })` is now an error, with the `is? Canceled` fix-it (program 22). |
| MF2: flag idempotence against batch 10 | **Yes** | Withdrawn. `e1 and e2` of two possible `Canceled`s is batch 10's same-type error. `ErrorStack` keeps error-only elements. Automatic cleanup is `Canceled & ErrorStack<…>`. `$origin`, `$trace` and `$parts` are defined. One wrinkle remains in N1. |
| MF3: a canceled sibling's ordinary failures dropped | **Yes, with one ambiguity** | A sibling's whole failure is kept beside the exit, and program 12 reports a cut-off job. What counts as a sibling's "failure" under C3 is S2. |

### `soundness-round3.md`

| Finding | Resolved? | Evidence |
|---|---|---|
| M1: fresh-request ingress, drop-hook receivers | **Yes** | Rule 4, at every request-changing edge. Both specimens are now errors. Descendant requests (items, `race`/`first_ok`/`within` children, tasks of a group made inside the work) are correctly exempt, because they close whenever the work does. |
| M2: projections don't sanitize; `Failed and [cause=r]` | **Yes** | Rule 3's invariant covers every facet, including plain-record facets, minted facets and stack elements, at construction, combination and mutation. Projections stay shallow, and `as ~Canceled` is distinguished from `as error`. |
| M3: canceled successes and continuing bindings | **Yes** | `let n = wait_value ?? 42` publishes 42. A binding that may hold `Canceled` holds the parent's own, which is legal in the closed parent work. |
| M4: flag idempotence | **Yes** | As MF2 above. |

**Program 09 note.** dogfood-round4 checks programs 09 and 19 under rule 4: `accept_all` spawns into a `Tasks` passed in, so rule 4 applies. Only `conn` crosses, and it comes from `accept or_throw`, so it can't hold `Canceled`. That is correct.

## Part 2: must-fix

### MF1. A `within` child's `?? default` turns a missed deadline into a success

**The rule.** §2.3's `within` row: "a handled, `Canceled`-free value is kept". Batch 10 makes `??`, `?? void` and catch-all arms consume `Canceled` like any failure, so in a `within` child almost every default *handles* the cancellation without meaning to.

```dewy
from_cache = (key:string) => cache_lookup(key) ?? none          # none: "not cached"
price = (key:string) => first_ok(@within(50ms @from_cache(key)) @db_get(key))
```

**Round 3.** At 50 ms, `within` gave `Timeout`, a failure, so `first_ok` waited for `db_get`.

**Round 4.**

1. At 50 ms the lookup's wait returns `Canceled`, and `?? none` consumes it.
2. `from_cache` returns `none`, a success whose type can't hold `Canceled`, so `within` publishes it.
3. `first_ok` takes `none` as its first success and cancels `db_get`.
4. `price` is `none`, though the database had the answer.

The same happens for `within(2s @(() => http.get_text(u) ?? ""))`, which gives `""`, and for any `e:exception => fallback` arm. Nothing in default mode reports it, because `$explicit_cancellation` is a `$bulletproof` tag. dogfood-round4's analogy with Python cuts the other way: asyncio counts a body that swallows its cancellation inside `timeout()` as a bug, not a feature.

**What the best-move idiom actually needs.** The child deliberately chooses a value on cancellation, as program 23's `<Canceled> => return best` does.

**Fix.** `within` and `protect_from_cancel` keep a canceled child's value only when that value comes from a branch that names `Canceled`:

- a `<Canceled>` or `c:Canceled` arm;
- an `is? Canceled` test;
- a `??<Canceled …>` handler.

A value produced by a handler that doesn't name it (`??`, `?? void`, a catch-all) gives `Timeout`, as in round 3.

This is a static fact about the return path, the same kind as rule 4's summaries. It needs no new syntax, and program 23 already satisfies it. A child that writes `?? none` and *wants* the default on timeout writes `??<~Canceled> none` and handles the `Timeout` at the call. List it in Q8.

### MF2. "A result type that may hold `Canceled` nested is an error at the call" rejects children that were never canceled

**The rule.** The §2.3 `within` row and program 23's comment (lines 18–19). The general rule above the table says a non-free success "is never published", and that "each kind of boundary below says what happens instead". For `within`, the "instead" is a compile error at the call, even on runs where the deadline never passes:

```dewy
load_both = () => [user=http.get_text(u1) prefs=http.get_text(u2)]   # fields: string | HttpError, + Canceled in C
main = () => {
    match within(2s @load_both) {           # round 4: error at the call
        both:[user:string | HttpError prefs:string | HttpError] => show(both)
        <Timeout> => printl"slow"
    }
}
```

This is program 14's pairing shape, which round 3 made "ordinary code", moved under a deadline. The `parallel` join already has the right rule for the same situation: a canceled child's value is never published, and an uncanceled child holds no `Canceled`, so its value is published as a refinement (§2.4).

**Fix.** Give `within` and `protect_from_cancel` the join's rule:

- **Not canceled:** publish the child's value as a refinement, with the narrowed field types.
- **Canceled by this boundary:**
  - a `Canceled`-free value returned through a branch that names `Canceled` is kept (MF1);
  - otherwise the result is `Timeout`, with any kept failures.

Drop the compile error, and correct program 23's comment.

## Part 3: should-fix

### S1. Q6's "persisting undo" is classified by the hook kind, which contradicts D40 Q4's definition of `$__abandon__`

D40 Q4: `$__abandon__` is "for a value whose cleanup throws its work away … the work takes effect only through an explicit `commit`". An atomic write's temp file fits that exactly, since the rename is its commit.

Round 4 instead:

- moves the temp-file removal to a drop hook (D42 Q5 edit);
- says the standard library uses `$__abandon__` only for rollbacks and process stops;
- treats any user `$__abandon__` hook as a persisting undo.

So a user who follows D40 Q4 and writes a staged-write type with `$__abandon__ = () => remove(temp)` makes every `race` or `first_ok` over it a compile error, while the identical standard-library write is litter.

**Fix.** Decide persistence by the failure, not the hook. For example, D40 Q4's text could reserve `$__abandon__` for undos whose effects persist, and send temp-file staging to `$__drop__`. Or the error family could carry the distinction. Either way, state it in D40 Q4's knock-on edit, which round 4 doesn't list.

### S2. "Each sibling's whole failure is kept beside the exit" needs its C3 boundary

C3 makes an item's errors per-item *values* unless the item uses `or_throw`. For `parallel ( let a = fetch(x); let b = fetch(y) or_throw )`, if `b` leaves while `a` is canceled, is `a`'s value part of the "sibling's failure"?

- If yes, a binding's error, which C3 says is a value, now joins the function's exit failure.
- If no, say so.

The rule program 12 needs is narrower: a canceled sibling's *forwarded* failure (its `or_throw`, as at program 12 line 16) and its cleanup failures are kept. Values bound by `let` are dropped with the bindings nobody will read.

**A related effect worth a warning.** A sibling whose catch-all converts its cancellation into an ordinary error (`e:exception => return Failed["…{e}"]`) now adds that error beside every early exit. `$explicit_cancellation` catches it in strict mode. A default-mode warning on a catch-all that can take `Canceled` in an item would help.

### S3. `$origin` of later cancellations points at the first

§2.2: a `Canceled`'s `$origin` and `$trace` "are those of the cancellation point that first returned it in this work". After `let a = sleep(1s)` and, later, `let b = lock_all(x y)`, `b.$origin` reports the `sleep` line.

That matches "one recorded cancellation per work", but it defeats the point of `$origin`, which batch 10 describes as "where they occurred", for anyone debugging where a canceled task stopped. Either:

- give each returned `Canceled` the origin of the point that returned it, keeping one recorded request; the two operands of a combination are still the same type, so batch 10's rule still applies;
- or add a second metatag for "where the request was closed".

### S4. The Q8 row for `within` must change with MF1

Under MF1 the row becomes: "keeps a value its child returned from a branch that names `Canceled`; otherwise `Timeout`".

## Part 4: are the questions ready for David?

The coordinator asked, for each question that is ready:

- does it lead with a minimal example (with the enclosing function where the question is about leaving it), then the question, then a recommendation and whether it's reversible;
- does it state what David gives up?

**Common problem.** No question is self-contained in round 4. Q1–Q5 point to round 3, and round 3's Q1 and Q5 point to round 2. Before David sees them, write one questions section with all eight questions complete, in the open_decisions format.

| Q | Substance | Example and enclosing function | Question sentence | Rec, reversible | What David gives up | Verdict |
|---|---|---|---|---|---|---|
| Q1 inferred effect | settled | round 3's `transfer` shows the function but only one context, and the comment "in a parallel item" has no item; show the call from `main` and from a parallel item | missing since round 2 | yes, yes | "a written result type never shows `Canceled`; writing it is an error" is in round 2 only | **not ready as text**; ready once consolidated |
| Q2 confinement | settled (four rules) | round 3's lines are fragments: `return Canceled` is about leaving, so it needs its enclosing function; `failures.lock.push(r)` needs the item it runs in; rule 3 and rule 4 have no example line | present (round 3) | yes, yes | round 4's bullet adds ingress; add rule 3 ("a cancellation can't sit inside another error's fields: combine instead") | **not ready as text** |
| Q3 `$until_others_finish` | settled | fine, apart from round 3's `…` in the `task.tasks` lines | present | yes, yes (spelling free) | missing: a marked item can't bind names read outside it, can't hold a lock across a wait, and runs its tail canceled; a marked signal listener may lose a pending notification | **nearly ready**: add the give-ups |
| Q4 `task.cancel_request` | settled | two fragment lines; show the caller's function and the worker's `select` together | missing (only "Rec:") | yes, yes | missing: forgetting to pass the request is silent; "closed" means canceled *or ended* | **not ready as text** |
| Q5 iteration ends at cancellation | settled | about leaving and continuing, so it needs the enclosing function and a line after the loop that shows code runs on | missing since round 2 | yes, yes | missing: a loop ended by cancellation looks like a loop that ran out, and code after it runs in the canceled task | **not ready as text** |
| Q6 discard losers' results | needs S1 | two lines with undefined helpers; show `backup_to` and a raced subprocess | missing (title only) | yes, yes | missing: losers' close failures and stray temp files are discarded with no run-time report, visible only in hover | **not ready** (S1, then text) |
| Q7 `$no_discarded_failures` | settled | the tag floats above the call; under batch 9 it must sit at the top of a function body or the file, so show `main = () => { $no_discarded_failures … }` | missing: the line under the example is a statement | yes, yes | nothing (opt-in); say so | **nearly ready**: enclosing function and a question sentence |
| Q8 documented-behaviour changes | needs MF1 | split over round 3's table and round 4's three rows | n/a (table) | yes, yes | each row's "against" column serves | **not ready**: merge the tables and fix the `within` row |

## Part 5: notes

- **N1.** Rule 4's fix-it (carry `x is? Canceled`) is the right shape. Program 22 shows it costs one line.
- **N2.** Rule 2's work-local mutex limit is honestly labelled as an implementation limit.
- **N3.** dogfood-round4 claims Trio's `move_on_after` and asyncio's `timeout` keep a body's handled value. Both treat swallowing cancellation inside a deadline scope as suspect, which supports MF1's narrowing rather than round 4's broad rule. Drop the analogy, or state it with that caveat.

## Verdict

Every earlier must-fix is resolved. The design is one narrow `within` rule (MF1 and MF2) and one classification (S1) away from settled. The questions need consolidating into one self-contained section before David sees them:

| Ready after consolidation | Ready once MF1/MF2 and S1 are fixed |
|---|---|
| Q1, Q2, Q3, Q4, Q5, Q7 | Q6, Q8 |
