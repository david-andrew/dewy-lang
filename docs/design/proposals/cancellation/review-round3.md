# Review, cancellation round 3

**Reviewed:**

- `round3.md`, `programs-r3/` (20 programs) and `dogfood-round3.md`, the last read after grading;
- against `review-round2.md`, `soundness-round2.md`, `brief.md`, decisions.md batches 3–10, D40–D42, LANGUAGE.md 3580–4150 and the v5 task proposal.

**Count: 3 must-fix, 6 should-fix, 5 notes.**

Round 3 is the right shape. Confinement is smaller than round 2's ban, it is sound in every case the earlier checks raised, and the new programs 14–18 show it leaves ordinary code ordinary. Three problems remain, all fixable in text without new machinery:

- Confinement doesn't stop a `Canceled` being carried, by capture, into work that runs under a *different* request.
- The "flag" representation changes batch 10's rule for `&` without asking David.
- The boundary table contradicts its own principle about a canceled work's ordinary failures, so program 12 silently loses a cut-off job.

## Part 1: are the earlier must-fixes resolved?

### `review-round2.md`

| Finding | Resolved? | Notes |
|---|---|---|
| MF1: `Task.wait()` as a join stops the task; a foreign `Canceled` through `.wait()` | **Yes** | `.wait()` is an ordinary wait and never reports the task's own `Canceled` (§2.1.4, program 20). |
| MF2: protection's limit counts from entry | **Yes** | It counts from cancellation (§2.1.5). Program 12 no longer caps normal jobs. What happens to the cut-off job's `Timeout` is MF3 below. |
| MF3: Q2's cost untested | **Yes** | Programs 14–18 cover every row of my table, and only the shared store remains an error. One pattern is still untested: partition writes in a `parallel` loop (S5). |

### `soundness-round2.md`

| Finding | Resolved? | Notes |
|---|---|---|
| R1: cleanup `Timeout` changes ordinary types between contexts | **Yes** | "One body, no exceptions" is withdrawn and types are per context. Grace expiry now gives the task's `Canceled` rather than `Timeout`, so cleanup adds only the flag. |
| R2: `Canceled` inside combinations and stacks | **Yes, for soundness** | It is a flag, merged by `&`, by stacks and by cleanup, and boundaries clear it. That contradicts the letter of batch 10 (MF2). |
| R3: the join rule cancels protected work | **Yes** | Protection is no longer a join for the parent's cancellation (§2.1.5). |

## Part 2: must-fix

### MF1. Confinement lets a `Canceled` cross into another request domain by capture or read

**What breaks.** §2.2 defines a *work* by its request. Its publication rule covers only *writes* to shared or outer places, and it explicitly allows "local captures" and items reading enclosing locals. That fails wherever code runs under a different request than the one that produced the `Canceled`:

- a `protect_from_cancel` body;
- a cleanup body (`defer`, drop hooks);
- a task spawned into `BackgroundTasks`, or into a `Tasks` group whose request is open.

The containment theorem rests on "a work whose request didn't close can't hold `Canceled` at all". These three paths make that false. soundness-round2 N4 warned about exactly this: "A task can enter a new request domain during protection or cleanup, so 'same task' alone is insufficient."

**Scenario.** A background task reports success for work it never did:

```dewy
start_upload = (app:BackgroundTasks registry:Mutex<array<Task>> file:Path) => {
    let pause = sleep(1s)                                           # Canceled when the item is canceled
    let t = app.spawn(() => { pause or_throw; upload(file) or_throw })   # a local capture: allowed
    registry.lock.push(t)                                           # a Task handle: allowed (its type holds no Canceled)
}
main = (app:BackgroundTasks) => {
    let registry = mutex([]:array<Task>)
    within(500ms @start_upload(app registry p"a.bin")) ?? void
    loop t in @(registry.lock) t.wait() or_throw                   # void: "uploaded"
}
```

The deadline cancels `start_upload` during its sleep. It still spawns the task, which captures `pause` (a `Canceled`), and stores the handle.

The task's request is open. It forwards the captured `Canceled` and ends. `.wait()` "never reports the waited task's own `Canceled`", so `main` sees `void`. The upload never happened, and nothing reports it.

**The same in a protected body.** `protect_from_cancel(2s () => race(@(() => { r or_throw }) @save_now))` lets the stale `Canceled` win the race and cancel `save_now`. That is the very save that protection was meant to shield.

**Fix.** Add a fourth rule to §2.2:

> A value that may hold `Canceled` can't be captured or read by code that runs under a different request: a protected body, a cleanup body, or a spawned task.

The fix-it is to test it first and capture the result: `let canceled = pause is? Canceled`.

- `parallel` items reading the enclosing work's locals stay allowed, because their requests close whenever the enclosing one does.
- Rule 2's "shared handle" should also name `spawn` explicitly.
- The check is the same structural may-hold summary, applied at closure creation for these three call kinds.

### MF2. The "flag" representation changes batch 10's `&` design and is not put to David

**What batch 10 says.** `e1 & e2` is "an unordered set" of typed parts, and "two failures of the same type are a compile error pointing to the error stack". Errors carry metatag members, "where they occurred and stack traces", produced on demand. D42 Q8 names them `$origin`, `$trace` and `$parts`.

**What round 3 says** (§2.2, Representation):

- `Canceled & Canceled` is `Canceled`, idempotent.
- Error stacks "merge the flags".
- "Batch 10's 'two of one type need the stack' doesn't apply to it."

**Is it a contradiction?** In substance, no. Batch 10's rule exists so that two different values of one type aren't lost. Every `Canceled` in a work describes the same closed request, so merging loses nothing, *provided* `Canceled` carries no per-occurrence data. In letter, yes. It is an exception to a rule David wrote ten hours ago, and it isn't in Q8 or in any question. It also leaves three things undefined:

1. **`$origin` and `$trace` on `Canceled`.** Which wait's location does a merged flag report: the first, the last, or the boundary that closed the request?
2. **`failure.$parts`.** Does it list a `Canceled` part? D42 Q8's `loop part in failure.$parts printl("{part.$origin}: {part}")` must either print it once or skip it.
3. **Stacks.** If a stack "merges the flags", does `stack[0]` still test `is? Canceled`, or does the flag move from the elements to the stack? Element access must say which.

**Fix.**

- Keep the flag as the internal representation; that choice is ours.
- State the user-visible rule as: "`Canceled` is a part with no per-occurrence data, so `&` with itself is idempotent; it is the one exception to the same-type rule". Add it to Q8 against batch 10.
- Define `$origin` as the first cancellation point that returned it, and `$trace` likewise.
- Say that `$parts` lists `Canceled` once.
- Say that a stack holds the flag as a whole while its elements keep their own `is? Canceled` answers.

None of this needs new syntax.

### MF3. A canceled work's ordinary failures: the principle says publish, the table and program 12 say drop

**The two rules disagree.**

- **The principle** (§2.2): "A work whose request closed doesn't publish its success value… Its failure value is published with the `Canceled` component removed."
- **The table** (§2.4, *parallel, leaving early*) keeps only the siblings' *cleanup* failures. It says nothing of a sibling's ordinary failure, such as one that happens during its protected tail.

**Program 12** relies on dropping it (lines 28–29): "A job still running 30 s after SIGTERM gets `Timeout`; it is a canceled sibling's result … so it is dropped".

```dewy
parallel {
    process_queue(p"queue" done) or_throw          # canceled by line 23's return; its protected job
    loop _ in signals.sigterm { …; return }        # then times out: Timeout, or a real RunError
}
```

Under the principle, `process_queue`'s residual (`Timeout`, or a genuine `RunError` from the job's last 30 s) is published beside `main`'s `return`, so `main` exits with that failure's code. Under program 12's reading it vanishes. That is a silent loss of exactly the kind D42 Q1 forbids ("a failure part disappears only through an action that names it"), and Q6 carefully protects against it elsewhere.

**Fix.** Follow the principle, and amend the table:

> A sibling canceled by an early exit contributes its whole failure residual, not only its cleanup failures, beside the exit (`return v` becomes that failure, as D40 Q1 does).

Program 12 then reports a job cut off after SIGTERM through `main`'s exit status. That is what its "finish the current job" promise needs. If dropping is preferred, it must be a stated discard, like Q6's, listed in D42 Q1's amended action list.

## Part 3: what the coordinator asked

### Is confinement sound and enforceable, and is it smaller than the ban?

**Sound,** with MF1 added. The three rules plus MF1's fourth make every `Canceled` live only inside a work whose request is closed. Every soundness-round2 specimen now types correctly:

- `pack` and `count_alternatives` are per context;
- the nested failing owners are one flag plus a stack of `CloseFailed`;
- protection is shielded.

**Enforceable and decidable.**

- The may-hold summary is structural and memoized per type, like `Send`.
- The by-place "writes a may-hold value" summary is a monotone fixpoint per parameter.
- MF1's check reuses the may-hold summary at closure creation.
- All of this is demand-driven over demanded instances.

**Cost.** The cost bound in §2.3 is honestly scoped (lattice height times body control-flow work). It must still be measured on the flagship panel before landing, as §2.10 says.

**Smaller than the ban: yes, clearly.**

| | Round 2's ban | Round 3's confinement |
|---|---|---|
| Local records, arrays, collectors | error | allowed |
| Arguments, generics, logging, catch-alls | error | allowed |
| Written local and parameter types naming `Canceled` | error | allowed |
| Constructing, shared stores, error fields | error | error |
| Capture into another request domain | error | allowed (MF1 makes it an error) |

**What confinement costs instead of the ban:**

- second bodies for generics whose type argument differs by context (programs 15, 17 and 18);
- two summaries;
- a copy at the join wherever narrowing changes a layout (S4).

These are compiler costs, not surface. That is the right trade by David's "the compiler works harder" rule.

### Does "`Canceled` as a flag merged by `&`" contradict batch 10?

In letter, yes; in substance, no. See MF2. It should go to David as the one exception to the same-type rule, with the metadata defined.

### Does Q6 make program 11 too verbose?

Yes, and it reaches well beyond program 11.

- **Program 11.** Handling an abandoned temp file takes 9 lines (lines 6–15) where round 2 had 1. The arm uses `as ~FileRemoveFailed`, which is an undecided extension.
- **It bites every `race` or `first_ok` over:**
  - an atomic file write. Program 02 line 16 and LANGUAGE treat `write_text` and `write_bytes` as atomic replaces, so that means *every* file write;
  - a subprocess, which can fail with `ProcessStopFailed`;
  - a transaction, which can fail with `RollbackFailed`.

  All of these become compile errors until each item handles the failure itself.
- **The arm has a gap.** If `FileRemoveFailed` is the value's only part, `as ~FileRemoveFailed` has nothing left to return (D42 Q4: an error when the kept facets can't form a value).

**Fix: narrow "abandon failure" to failed undos whose effects persist outside the program's own scratch space.**

- **Undo failures that must never be discarded:**
  - `RollbackFailed`: a transaction's changes may persist;
  - `ProcessStopFailed`: the child process is still running.
- **Litter, which is discarded with the loser like a failed close:** a temp file that couldn't be removed beside an intact original. Hover lists it, and Q7's strict tag catches it.

Program 11 then returns to one line. The compile error remains where it protects something. This doesn't bring back round 1's mixed winner/loser arms.

### Does Q7's strict tag earn its keep?

Only if narrowed. Q7 says that under the tag, "every failure a loser can give must be handled inside its work". That includes a loser's *primary* failures, and `first_ok`'s earlier failures, which are its whole contract ("the first success, else the first failure"). Under that reading `$bulletproof` makes `first_ok(@lookup(a) @lookup(b))` an error unless each lookup can't fail, so `first_ok` becomes unusable in certifiable code.

**Fix.** Scope the tag to *secondary* failures: cleanup and abandon failures of results the group discards. The program never saw those, whereas it chose to discard the primary results by calling `first_ok`.

So narrowed, it earns its keep. It is the opt-out that "every convenience axiom needs an opt-out demanding real proof" asks for, it belongs in `$bulletproof` beside `$explicit_cancellation`, and it is a separate tag, consistent with how `$bulletproof` is assembled. Its names (`names-r3.txt`) still need the cold read.

## Part 4: should-fix

### S1. `within` no longer returns a handled child's value; list it, and consider the smaller rule

§2.4: under its own deadline, `within` gives `Timeout`, and "a success value is not published". That rules out the anytime idiom:

```dewy
best_move = (board:Board) => {
    let best = first_move(board)
    loop depth in [1..) { match search(board depth) { m:Move => best = m; <Canceled> => return best } }
}
let move = within(1s @best_move(board))        # round 3: always Timeout once 1 s passes
```

LANGUAGE.md ("returns `Timeout` when its own deadline expires") supports round 3's reading, so it isn't a reversal. But rounds 1 and 2 said the opposite, and it isn't in Q8.

**Fix.**

- List it in Q8.
- Offer the smaller sound rule as an alternative: publish a canceled child's success when its type can't hold `Canceled`. Iterative deepening is a common deadline idiom, and the only workaround today is a `Mutex` (program 02's shape).

### S2. Narrowing at the join is a copy wherever it changes layout

§2.4 and §2.10 say element narrowing is "a static view, since the reserved tag is never set", with "no other conversion needed".

**Where the view works.** That holds when the narrowed member is a union that already carries a failure, if every such union reserves the tag (state that as the representation rule).

**Where it doesn't.** It fails when the member is a plain type:

```dewy
let rows = [parallel f in files [path=f n=count_primes_in(f)]]   # n: int | Canceled inside, int after
```

`int` and `int | Canceled` don't share a layout. An `array<[path:Path n:int]>` passed to code compiled for that type needs the narrow layout, so the join copies.

**Fix.** Say so, count the copy in §2.10's costs, and warn under `$no_hidden_costs`.

### S3. Partition writes in a `parallel` loop are errors in every item; this is untested

v4 and v5 let a loop item write its own partition: `parallel i in [0..n) { results[i] = fetch(urls[i]) }`.

Under rule 2 that writes a may-hold value into an enclosing variable from an item, so it is an error in every item, because every item counts. It must be an error: an item canceled by a `break` would leave a `Canceled` in `results[i]` for code after the loop.

The fix-it should rewrite to the comprehension form, as program 14 does, or add `or_throw<Canceled>`. Add a program for it.

### S4. Rule 2's "a place reached through a `Mutex`" also bans a mutex local to the work

`let m = mutex([]); @(m.lock).push(r)` inside one item publishes nothing. It is conservative and harmless, and rare in practice. Note it as an implementation limit, as soundness N4 suggested, rather than as a rule.

### S5. §2.6's "cleanup is `protect_from_cancel` word for word" is not quite true

Protection's expiry gives `Timeout` (§2.1.5). Cleanup's grace expiry gives the task's `Canceled` (§2.1.6, the R1 fix). The difference is right, but say "with one difference: expiry gives the task's `Canceled`".

### S6. Type inspection gives context-dependent values

Program 18 prints 2 in `main` and 3 in the item, from the same expression. That follows from per-context types, which David accepted. But the stated warning lives only under `$no_hidden_costs`, which is a *cost* lane, while this is a *behaviour* difference. Show both answers in hover, and warn by default when type inspection's result differs between a function's two instances.

## Part 5: notes

- **N1. Program 12's second SIGTERM.** It is swallowed for up to 30 s of draining. That is stated in §2.8 and fine.
- **N2. The `.wait` spelling.** `indexer.wait` (a handle, program 20) and `watcher.wait()` (a call, program 13) are both correct under existing surface. A one-line note in the docs would save the trip the dogfood reports.
- **N3. Unchecked Zig issue numbers.** The Zig correction at the end of round3.md is good. The two issue numbers in §2.9 remain unchecked; drop them if they can't be verified.
- **N4. The strict check for Q6.** It is context-independent, per soundness S3. Good.
- **N5. Dependencies through channels on a marked producer.** These are not checked (§2.7). That is honest. A "this block never ends" warning on the *essential* side, when it is parked on a channel only a marked item sends to, would catch the common case cheaply.

## Ready for David?

**Nearly.** Fix MF1–MF3: one added confinement rule, a Q8 row and metadata definitions for the flag, and one table row plus program 12's comment. Narrow Q6 and Q7 as in Part 3, and list S1 in Q8.

After that, Q1–Q5 and Q8 are ready as written. Q6 and Q7 are ready once narrowed. Their names still need the cold read.
