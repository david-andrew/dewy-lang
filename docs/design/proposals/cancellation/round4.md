# Cancellation, round 4: confinement, completed

This round amends round 3. Every rule of round 3 stands except where a section below replaces it. Rounds 1–3 stay as written. §5 resolves each finding of `review-round3.md`, `soundness-round3.md`, `regrade-round3.md` and the round 3 cold read.

## 1. Verdict

Round 3's confinement is the design. Four gaps are closed, each by tightening or completing a rule, with no new kind of value:

1. **Ingress.** A value that may hold `Canceled` can't be carried into code that runs under a different request: a protected body, a cleanup hook, or a task spawned into an outside group. The fix-it captures `x is? Canceled`, a plain `bool`, instead.
2. **Failure values.** Inside a failure, `Canceled` may sit only in its cancellation facet; every other facet must be free of it. So removing that facet always leaves something publishable. Projections stay shallow, as D42 defines them.
3. **Publication.** A boundary publishes a canceled work's success value when its type can't hold `Canceled`, and its failures without the `Canceled` facet. This brings back "`within` keeps the best result found so far". A sibling that a `parallel` early exit canceled keeps its whole failure, not only its cleanup failures, so program 12 reports a job cut off after SIGTERM.
4. **Batch 10 unchanged.** Round 3's "`Canceled & Canceled` is `Canceled`" is withdrawn.
   - Users combining two `Canceled`s get batch 10's same-type error, like any type.
   - The runtime records a work's cancellation once, and is never asked to combine two.
   - Automatic cleanup gives `Canceled & ErrorStack<CloseFailed>`.

   No exception goes to David.

Q6 and Q7 are narrowed:

- Only undos whose effects persist (`RollbackFailed`, `ProcessStopFailed`) are never discarded. Program 11 is one line again.
- The strict tag, `$no_discarded_failures`, covers only the secondary failures of discarded results.

**Carrying a cancellation into protected work** (round 3: allowed, and unsound)

```dewy
let paused = sleep(1s)                                            # void | Canceled
protect_from_cancel(2s () => { paused or_throw; save() })         # error: paused may hold Canceled
let was_canceled = paused is? Canceled                            # the fix-it: carry a bool
protect_from_cancel(2s () => save_marker(was_canceled)) or_throw;
```

**The best result so far survives a deadline** (round 3: always `Timeout`)

```dewy
best_move = (board:Board) => {
    let best = first_move(board)
    loop depth in [1..) { match search(board depth) { m:Move => best = m; <Canceled> => return best } }
}
let move = within(1s @best_move(board))        # Move: the child handled its cancellation
```

**An atomic write in `first_ok` is one line again** (round 3: nine)

```dewy
backup_to = (dir:Path data:array<uint8>) => p"{dir}/backup.bin".write_bytes(data)
first_ok(@backup_to(p"/mnt/a" data) @backup_to(p"/mnt/b" data))   # a loser's stray temp file is litter
```

**A cut-off job is reported** (round 3: dropped)

```dewy
parallel {
    process_queue(p"queue" done) or_throw            # protected job times out after SIGTERM
    loop _ in signals.sigterm { return }             # main's result: that Timeout, not void
}
```

## 2. The rules (amending round 3)

### 2.1 Confinement: four rules (replaces round 3 §2.2's rule list)

A *work* is still what runs under one request. A value *may hold `Canceled`* by round 3's structural summary, which covers fields, elements, facets, captured environments, families and type arguments. The rules:

1. **No constructor.** Only the runtime makes `Canceled`. This now also covers aliases, descendant types, and generic or comptime constructors (soundness N3).
2. **No egress.** A value that may hold `Canceled` can't be written where it outlives its work or is shared with other work:
   - a variable of an enclosing function, written from a `parallel` item, partition writes such as `results[i] = …` included;
   - anything reached through a `Mutex`, an `Atomic`, a channel or another shared handle;
   - a global;
   - a place captured with `$capture @`, or borrowed in by `@` from outside the work.

   This rule is conservative. A mutex created and used inside one item is also refused (review S4), and that is an implementation limit, not part of the rule.
3. **Failure values keep `Canceled` in its facet** (replaces round 3 rule 3; soundness M2). Building, combining or mutating a failure value checks every facet except the cancellation facet for `Canceled`, and an error results if one may hold it. Facets are plain-record facets, minted facets with fields, and stack elements. So:
   - `Failed and [cause=r]` is an error at the `and` when `r` may hold `Canceled`;
   - `r and Failed` is fine.

   The invariant: removing a failure's cancellation facet always leaves a value with no `Canceled` anywhere in it.
4. **No ingress into a fresh request** (new; review MF1, soundness M1). A value that may hold `Canceled` can't flow into code that runs under a request that is neither its work's own nor a descendant of it:
   - a `protect_from_cancel` body;
   - a cleanup hook, through its receiver's fields (`Logged[value=r]` with a `$__drop__` that reads `value`), or through what `defer` captures;
   - a task spawned into a group not created inside this work: `BackgroundTasks`, or a `Tasks` passed in.

   It can't flow there by capture, argument or receiver field. The fix-it is to test first and carry the `bool`, `let was_canceled = r is? Canceled`, or to forward or handle the value before the call.
   - Allowed: `parallel` items, `race`, `first_ok` and `within` children, and tasks spawned into a `task.tasks` group created inside the work. Their requests descend from the work's, so they close whenever it does.
   - A value proven free of `Canceled` may go anywhere.

**Projections are shallow** (D42 Q4, unchanged).

- `v as ~Canceled` removes the cancellation facet and keeps every other facet, including a non-error exception facet. It is not a synonym for `as error`, which keeps only `error` facets and is an error when there are none.
- The may-hold summary is recomputed for the projected value. By rule 3 that result is free of `Canceled` for a failure value, so it may be published. For a plain record holding `Canceled` in a field, `as ~Canceled` changes nothing, and the record still may not be published.

**What the checker computes** (soundness N3). These are static facts about where values come from, not run-time tags on values. "No origin tracking" in round 3 means no *run-time* tracking.

- The structural may-hold summary, memoized per type.
- Domain-relative summaries for parameters, results, captures and receivers. Each takes one of four values: same work, caller-owned place, other work, unknown.
- Every request-changing edge (protect, cleanup, spawn) and every egress point checks these summaries, and an unknown summary is refused.

The cost is control-flow transfer work times a finite lattice height, plus type normalization and demanded specializations. Only context reachability has the simple O(|B| + |E|) bound. It has to be measured on the flagship panel before landing.

### 2.2 What `Canceled` is, as a value (replaces round 3 §2.2's "Representation"; review MF2, soundness M4)

- **The logical model is batch 10's.** `Canceled` is an ordinary typed part of a combination, a part with no fields.
  - `e1 and e2` where both may be `Canceled` is batch 10's same-type compile error, pointing to the error stack. The fix-it is to forward one.
  - The type *expression* `Canceled & Canceled` normalizes to `Canceled`, as any `T & T` does in the type algebra. That merges types, never values.
- **The runtime coalesces its own state, not values.** A work's cancellation is recorded once, when its request closes, and no user code combines two of them. When a canceled task's cleanup also runs out of grace, its result is that same recorded cancellation; no second value is made. The flag is how that one facet is stored, an internal choice.
- **Stacks keep their element constraint.** `ErrorStack` elements are errors, and `Canceled` is an exception, not an error, so `ErrorStack[r r]` is refused, as today.
  - Automatic cleanup of several failing owners gives `Canceled & ErrorStack<CloseFailed>`: a cancellation facet beside a stack of every ordinary failure, each kept.
  - A boundary removes the facet and leaves the stack untouched.
- **Metadata** (D42 Q8's names):
  - `$origin` and `$trace` of a `Canceled` are those of the cancellation point that first returned it in this work;
  - `$parts` lists it once, as one facet;
  - a stack's elements keep their own `$origin`, and none of them is `Canceled`.

### 2.3 Boundaries: what each publishes (replaces round 3 §2.4)

**General rule** (soundness M3, review MF3). When this boundary, or one above it, canceled a work:

- **Success values.** The work's success value is published if its type is structurally free of `Canceled`, and is never published otherwise. Each kind of boundary below says what happens instead.
- **Failure values.** The work's failure value is published with its cancellation facet removed. By rule 3 the rest is free of `Canceled`.
- **The facet itself.** It is consumed when this boundary caused it. It is translated when the boundary maps it, as `within` maps it to `Timeout`. It is propagated, as the parent's own, when the parent's request is closed.

| Boundary | Its own cancellation | From above | Not canceled |
|---|---|---|---|
| `race`, `first_ok` | losers' results discarded whole (Q6), except persisting-undo failures | drains, then the parent's `Canceled` plus every kept failure | the winner's complete result; `first_ok`'s first failure if all fail |
| `within` | facet becomes `Timeout`, other failures kept (`Timeout & FlushError`); a handled, `Canceled`-free value is kept (program 23); a result type that may hold `Canceled` nested is an error at the call | drains, then the parent's `Canceled` plus kept failures | the child's result |
| `protect_from_cancel` | as `within`'s own column | not closed by the parent (round 3 §2.1.5) | the body's result |
| cleanup | n/a | grace expiry: the task's one recorded `Canceled`, plus real cleanup failures | the hook's result |
| `parallel`, leaving early | each sibling's whole failure, its facet removed, is kept beside the exit (`X & RunError`, or replacing `return v`, as D40 Q1 does); successes are unused, because the code after the block doesn't run | items see `Canceled`; bindings published as the parent's own, types unchanged | per item, C3 |
| `parallel`, essential work done | marked items: facet consumed, other failures go where their `or_throw` or `;` sends them | as above | |
| `parallel`, continuing after cancellation from above | bindings keep their types: a handled value is published (`let n = f() ?? 42` is `42`); a value that may hold `Canceled` holds the parent's own, legal in the parent's work, which is closed (soundness M3) | | |
| comprehension | early exit only (no array) | drains, then `Canceled` plus every kept failure (`Canceled & ErrorStack<CloseFailed>`) for the expression | elements published; see §2.4 for the narrowed type |
| `task.tasks` | stopped children: facet consumed, failures kept; the first failure returned with every kept cleanup failure | drains, then `Canceled` plus all kept failures of the body and children (soundness S3) | the body's value, held until every child and the body's cleanup finish |
| `Task.wait()` | the task's own facet never reported; its other failures, cleanup included, are | the waiter's own `Canceled`; the task keeps running | the task's failures |

### 2.4 The narrowed view at a join (soundness S2, review S2)

A join publishes each element as a *refinement* of the value the child built:

- the same object and the same specialization;
- captures and generic methods unchanged;
- its readable field types narrowed (`page: string | HttpError`).

Nothing is reinstantiated, so a `Box<void | Canceled>` built in an item keeps its methods' specialization after the join.

- **When the refinement is free.** Where every failure-carrying union reserves the `Canceled` tag, the view reads the same layout.
- **When it costs a copy.** Where the narrowed member is a plain type, as in `[path=f n=count(f)]` with `n: int | Canceled` inside and `int` after, and the value is passed to code compiled for the narrow type, the join converts. That is one copy of the array, counted in §2.6. It warns under `$no_hidden_costs`.

### 2.5 Type inspection that differs by context (review S6; program 18)

Inspecting a type argument (`members`, `type of`, overloads on it) may answer differently in a function's two instances, because the cancellable instance's `T` may include `Canceled`.

- **That warns by default, not only under `$no_hidden_costs`,** because it is a behaviour difference, not a cost. The text: "count_alternatives inspects T, which is `void | Canceled` here and `void` at line 21: members gives 3 here and 2 there. Forward or handle `Canceled` before the call if they should agree."
- **Hover shows both answers.**

Program 18 now forwards before the call (line 24) and prints 2 in both places.

### 2.6 One body or two (amends round 3 §2.10)

Machine code is shared when the two instances lower alike. A second body is needed in three cases, the same as round 3:

- a type argument that differs by context;
- a local aggregate's layout;
- type inspection.

To these, round 4 adds §2.4's join copy where a refinement changes layout. Listed under `$no_hidden_costs` and in `explain`; type inspection also warns by default (§2.5). The dogfood shows two tiny duplicated generics, and no join copies, because programs 14 and 21 narrow unions that already carry failures.

### 2.7 Cleanup and protection (amends round 3 §2.6; review S5, soundness S1)

Cleanup shares protection's shield and deadline machinery, with a different adapter at its end:

- **Protection's expiry** gives `Timeout`.
- **Cleanup's expiry** gives the owning work's one recorded `Canceled`. That is only possible because the owning request is already closed, so it is a translation into that closed request, not a new cancellation.

In both, real ordinary failures are kept, every hook is joined, and an expiry asks the hook to stop; it never kills it. Rule 4 governs what may flow *into* either.

### 2.8 Q6 and Q7, narrowed

- **Q6.**
  - `race` and `first_ok` discard whole losing results, and `first_ok` also discards its earlier failures. Ordinary cleanup failures and litter go with them. An atomic write's temporary file is removed by its drop hook, so a failed removal beside an intact original is litter.
  - The exception is a *persisting undo* failure: a `$__abandon__` hook failure that leaves effects in place. In the standard library these are `RollbackFailed` (a transaction's changes may remain) and `ProcessStopFailed` (the child is still running). The standard library uses `$__abandon__` only for those. A user `$__abandon__` hook is treated the same way.
  - A `race` or `first_ok` whose work can give a persisting-undo failure is a compile error until the work handles it.
  - Hover on the call lists everything that is discarded.
- **Q7.** `$no_discarded_failures`, in `$bulletproof`, covers only the *secondary* failures of results a group discards: cleanup failures and litter. The losers' primary results remain `first_ok`'s contract. The check depends on what the group can discard, so it applies in non-cancellable code too. The fix-it is to handle the failure in the work, which program 11's one-line `backup_to` can do with a match. The cold read gave 3/3, at 3/4/4.

### 2.9 Smaller items

- **Diagnostics:**
  - **Partition writes in a `parallel` loop** (review S3; program 21) are rule 2 errors. The fix-it is to write `or_throw<Canceled>` on the value, or to build the array as a comprehension.
  - **A dependency on marked work** (review N5): an essential item parked on a channel that only a marked item sends to gets the "this block never ends" warning.
- **Documentation:**
  - **`.wait` spelling** (review N2): `t.wait()` is the void call, and `@t.wait` is its handle (program 20).
  - **Zig** (review N3): §2.9's two issue numbers couldn't be verified this round and are dropped. The quotes from `Io.zig` and the 0.16.0 release notes ("Only the logic that made the cancelation request can soundly ignore an error.Canceled", round 3's correction note) stand.

## 3. Knock-on edits (in addition to round 3 §3)

- **D42:**
  - **Q1**: the amended consuming-action list: "the losers of `race` and `first_ok`, and `first_ok`'s earlier failures, discarded whole, except persisting-undo failures".
  - **Q4**: add a note that `as ~E` keeps every facet but `E`, and is distinct from `as error`.
  - **Q5**: "the temporary file an atomic write abandons" becomes "… its drop hook removes"; `FileRemoveFailed` there is cleanup, not an undo.
  - **Q8**: `$origin`, `$trace` and `$parts` of `Canceled`, as in §2.2.
- **D41 Q2**: protection's limit starts at cancellation (round 3), and rule 4 forbids carrying a possible `Canceled` into the body.
- **LANGUAGE.md:**
  - Errors as values: §2.1's four rules and §2.2's value model.
  - `within`: "a child that forwards its cancellation gives `Timeout`; one that handles it keeps its value".
  - Cleanup: §2.7's two adapters.

## 4. Questions for David

23 programs are dogfooded (`dogfood-round4.md`); the lowest grade is 3. Names used: `$until_others_finish`, `task.cancel_request`, `task.CancelRequest`, `$no_discarded_failures`, all read correctly cold. No new names this round, so there is no `names-r4.txt`.

Q1–Q5 are as in round 3, and are ready:

- Q1, the inferred effect;
- Q2, confinement, now with four rules (§2.1). What you give up: you can't create a `Canceled`, and a value that may hold one can't be stored anywhere that outlives its work, nor carried into protected, cleanup or background code. Everything else works as for any error.
- Q3, `$until_others_finish`;
- Q4, `task.cancel_request`;
- Q5, iteration ends at cancellation.

### Q6 (a). `race` and `first_ok` discard losers' results, but never a failed undo whose effects persist

```dewy
first_ok(@backup_to(p"/mnt/a" data) @backup_to(p"/mnt/b" data))   # loser's stray temp file: discarded
race(@apply_with(tx1) @apply_with(tx2))   # error unless each handles RollbackFailed itself
```

- **Rec:** yes. D42 Q1's consuming-action list names these two actions. Hover lists what is discarded.
- **Reversible** before release.

### Q7 (c). `$no_discarded_failures`, in `$bulletproof`

```dewy
$no_discarded_failures
first_ok(@backup_to(a data) @backup_to(b data))    # error: a loser's temp-file removal could be discarded
```

Under the tag, a loser's cleanup failures and litter must be handled inside its work; its primary result stays discardable.

- **Rec:** yes. The name was read correctly by 3/3 cold, at 3/4/4.
- **Reversible.**

### Q8 (a). Changes to documented behaviour, taken together

Round 3's table stands. This round adds two rows and changes a third:

| Change | Example | Against |
|---|---|---|
| `within` keeps a value its child computed after handling its cancellation; a forwarded cancellation gives `Timeout` | `within(1s @best_move(board))` is a `Move` | LANGUAGE.md ("returns `Timeout` when its own deadline expires") |
| A sibling canceled by a `parallel` early exit keeps its whole failure beside the exit | program 12: a job cut off after SIGTERM is `main`'s result | round 3 §2.4, and only cleanup failures before |
| Cleanup grace expiry gives the work's one recorded `Canceled` (round 3's row, now with no idempotence exception) | `Canceled & ErrorStack<CloseFailed>` | LANGUAGE.md 3656–3659 |

- **Rec:** accept all. Reversible before release.

## 5. Resolution of every finding

**`review-round3.md`**

| Finding | Resolution |
|---|---|
| MF1: capture carries `Canceled` into another request | Rule 4 (ingress), with the `is? Canceled` fix-it; descendant requests allowed (§2.1; program 22). |
| MF2: flag idempotence against batch 10 | Withdrawn. Batch 10's same-type rule applies to `Canceled`; the runtime records one cancellation per work. Stacks keep error elements; metadata defined (§2.2). Nothing goes to David. |
| MF3: a canceled sibling's ordinary failures dropped | Whole failure kept beside the exit (§2.3); program 12 reports it. |
| Part 3: Q6 too verbose; the `as ~E` gap | Narrowed to persisting undos; program 11 is one line, and no `as ~E` is needed (§2.8). |
| Part 3: Q7 too broad | Secondary failures only; `$no_discarded_failures` (§2.8). |
| S1: `within` and the anytime idiom | Kept: handled, `Canceled`-free values survive (§2.3; program 23; Q8). |
| S2: join narrowing can be a copy | Stated, counted, warned under `$no_hidden_costs` (§2.4). |
| S3: partition writes | Rule 2 error with fix-it (program 21). |
| S4: a work-local mutex | An implementation limit (§2.1). |
| S5: cleanup vs protection | Two adapters, stated (§2.7). |
| S6: type inspection differs | A default warning, and hover shows both (§2.5; program 18). |
| N1, N4 | No action needed. |
| N2: `.wait` spelling | Documented (§2.9). |
| N3: unverified issue numbers | Dropped (§2.9). |
| N5: channel dependency on marked work | The never-ends warning covers it (§2.9). |

**`soundness-round3.md`**

| Finding | Resolution |
|---|---|
| M1: fresh-request ingress, including drop-hook receivers | Rule 4, at every request-changing edge: capture, argument, receiver fields, `defer` (§2.1). Both specimens are now errors, with the fix-it. |
| M2: projections don't sanitize; `Failed and [cause=r]` | Rule 3 is the normalizable-failure invariant over every facet, checked at construction, combination and mutation. Projections stay shallow, with the summary recomputed. `as ~Canceled` and `as error` are distinguished (§2.1). Both specimens are now errors. |
| M3: canceled successes and continuing bindings | Successes free of `Canceled` are published (`n` is `42`); other bindings are the parent's own in the closed parent work (§2.3). |
| M4: flag idempotence | As review MF2 above. `ErrorStack[r r]` is refused by the element constraint; automatic cleanup is `Canceled & ErrorStack<…>` (§2.2). |
| S1: cleanup is not protection word for word | Two adapters (§2.7). |
| S2: refinement view | Specified as a refinement of the same object; a copy where layout changes (§2.4). |
| S3: retained failures in the table | `task.tasks` and comprehension cells now list kept failures (§2.3). |
| N1–N2 | Confirmed. |
| N3: static domain facts | The checker's summaries are stated, and "no origin tracking" is qualified as run-time only (§2.1). |

**`regrade-round3.md`**

| Program | Resolution |
|---|---|
| 08 discoverable (3) | Unchanged. A forgotten request through a channel can't be seen; see `dogfood-round4.md`. |
| 11 obvious and concise (3) | One line again (§2.8). |
| 18 obvious (3) | A default warning, and the program forwards first (§2.5). |

**Cold read, round 3:** `$no_discarded_failures` adopted; `$keep_all_failures` dropped (misread).
