# Review, cancellation round 1

Reviewed: `round1.md`, `programs-r1/`, `dogfood-round1.md`, against `brief.md`, decisions.md batches 3–10, D40–D42 and LANGUAGE.md 3600–3990.

**Count: 5 must-fix, 9 should-fix, 8 notes.**

The core is sound and worth taking: `Canceled` only where a group can cancel, inferred like waiting, with the group consuming what it causes. The problems are at the edges, where round 1 claims more than its rules deliver:

- `Canceled` has two flavours under one name.
- "One compiled body" is not sound once that flavour reaches data layout.
- The incidental rule breaks signal-only `race` and `within`.
- The signal rule is not reproduced without behaviour change.
- A loser's cleanup failure replaces a winner's success, which the programs themselves don't follow.

---

## Must-fix

### M1. Two kinds of `Canceled` share one type, and the rule for which is which contradicts itself

**Rules involved.**

- §2.2 says the context member "flows through `or_throw`, `return`, matches and inferred results like any other failure".
- §2.3 item 1 says "`return Canceled`, and a `Canceled` read from a variable, are ordinary failures. Their type includes `Canceled` in every context."
- §2.3 items 2–3 add stored data and waits on another task's request.
- §2.10 says types carry "one flag per inferred result, 'context `Canceled`'".

So the type system has two members both spelled `Canceled`:

- a *context* one, which groups strip statically and which is absent in non-cancellable instances;
- an *ordinary* one, which survives everywhere.

At run time they are one value. Nothing says which one a local holds after `let r = sleep(1s)`, or after a match binding. Nothing says how `<Canceled>` arms, `as Canceled`, D42's `&` and `??<~Canceled>` treat each one, or how a group at run time removes "exactly the `Canceled` part it caused" (§2.4) when the value might be the other kind.

**Scenario 1: reading from a variable.**

```dewy
probe = (host:string) => {
    let r = net.ping(host)                           # Duration | NetError | Canceled (in an item)
    if r is? Canceled { log("probe {host} canceled"); return r }   # "read from a variable": ordinary?
    r
}
```

By §2.2, `return r` forwards the context member, and a `race` over `probe` strips it. By §2.3 item 1 it is ordinary: `probe`'s result keeps `Canceled` in `main`, and `race(@probe(a) @probe(b))` in `main` is `Duration | NetError | Canceled`. The two readings give different types to one of the most common shapes of cancellation code.

**Scenario 2: a wait's `Canceled` reaches `main`.** Block items may write the function's variables (v4/v5: "block items may write outer variables under the dependency graph").

```dewy
main = () => {
    let status = "starting"
    parallel {
        $incidental loop true { status = fetch_status(); sleep(1s) or_throw }   # string | HttpError | Canceled
        run_jobs() or_throw
    }
    printl"last status: {status}"     # status may be Canceled, from a wait, in main
}
```

When `run_jobs` ends, the block cancels the incidental item. `fetch_status` returns `Canceled`, and the item writes it into `status`. The §2.3 claim "`main` … never receives one from a wait" fails. The same happens when an item writes an outer variable and a sibling leaves an enclosing loop with `break`: the code after that loop runs.

**Fix.** Make there be one `Canceled`, the context one, and close the doors that create the other:

1. Constructing `Canceled` outside the runtime is an error. The standard library already has to stop doing it (§3, `signals.dewy`).
2. A wait on another task's request gives an existing non-cancellation type. See S5: the request as a receive-only channel end, whose close is `Closed<…>`.
3. Storing a context `Canceled` into a place that outlives the item is an error, with a fix-it to `or_throw` or `??<…>`:
   - places include an outer variable, a field, a collection and a mutex-guarded value;
   - the group's own collected result is the one exception, since the group consumes it.

   This matches the existing "a channel can't carry one bare".

Then §2.3's claim is exact. The flag is just "this instance is cancellable", `.wait()` and the groups need no run-time provenance, and hover's "stored by a cancellable task at line N" goes. If David wants explicit `Canceled` kept, the round must define the two flavours as distinct types, and define the conversions between them, before Q1 can be judged.

### M2. "One compiled body, types checked per context" is unsound once the context member reaches layout or type-directed code

**Rules involved.** §2.10 says:

- "One body per function. The cancellable body is also correct where nothing can cancel … Callers that can't be canceled ignore the `Canceled` tag statically."
- "A body is checked once, with the flag symbolic."

**When it works.** It holds only while the extra member appears solely in the function's returned tag. It fails when the member changes a stored layout:

```dewy
wait_two = () => [loop _ in [0..2) signals.sigusr1.next]
# from main: array<Signal>; in a parallel item: array<Signal | Canceled>
main = () => {
    let a = wait_two()                       # array<Signal>
    parallel { let b = wait_two(); other() }
    count_names(a)                           # count_names = (xs:array<Signal>) => ...
}
```

One body builds one element layout. Either `a` is a wide array typed as narrow, so every consumer of `array<Signal>` must accept two layouts, or the body is wrong for one caller.

**Narrowing after a parallel comprehension.** The same happens with §2.3's narrowing after a `parallel` comprehension. In program 03, `prefetch` builds `array<X | Canceled>` and retypes it as `array<X>` in a non-cancellable caller. The narrowing is either a copy or a second layout. And when `prefetch` is itself reached from both contexts, its one body must return both.

**Type-directed code.** It also fails wherever the flag picks code:

- a generic instantiated on the result type (`encode<T>`);
- an overload chosen by the argument's type;
- comptime enumeration of `T.types` (batch 7's `heart.types` machinery).

Each produces different code per context, so a symbolic flag can't be checked once and compiled once.

**Fix.**

- State the rule: one body when the context member reaches only return and forwarding positions; two bodies when it reaches a stored layout, a generic argument or comptime type inspection.
- Warn on the second case, naming the call sites. Rule 4 asks for that warning, and the brief asked when to warn.
- M1's no-storage rule shrinks the two-body case to generic and comptime use. That makes "one body" true almost everywhere, and makes the "4 of 39 functions" estimate an upper bound rather than an aside.

### M3. The incidental rule, applied to `race`, `within` and `first_ok`, breaks signal-only waits and leaves the result undefined

**Rules involved.**

- §2.1(3) lists "Only incidental work remains" among the triggers for *every* group.
- §2.2 counts `race`, `within` and `first_ok` as groups.
- §2.6 says "Once every unfinished item of a group is incidental, the group closes their requests", and signal `next` is marked `$incidental` in the library.

```dewy
main = () => {
    let server = start_server(app)
    let s = race(@signals.sigterm.next @signals.sighup.next)   # wait for whichever comes first
    server.shutdown(s.name)
}
```

**Today.** Under batch 9 and LANGUAGE.md 3828–3829 ("Owned `race` and `within` helpers inherit its signal owner"; outside a group the root subscription "does not close merely because it is waiting only for signals"), this waits for a signal.

**Under round 1.** Both race items are parked in incidental waits from the start, so the race cancels both at once. Every item then ends `Canceled`, which the race drops, so no rule says what `race` returns. `within(30s @signals.sigterm.next)` ("wait up to 30 s for SIGTERM") breaks the same way, and so does `first_ok` over signals.

**Fix.** Apply incidental closure only at *owning* groups: `parallel`, `task.tasks` and spawned tasks. `race`, `first_ok`, `within` and `protect_from_cancel` stay transparent, as batch 9's owner model already says. Their children count toward the owner's frontier, which §2.6's "including race or `within` children it owns" already half-states. Also say what a group returns if every item ends by the group's own cancellation. With the transparency fix this can only be an owning group with no essential work, which is already an error.

### M4. The batch 9 signal rule does not become an instance "exactly": three behaviours change, unstated

**Rule involved.** §2.6: "Batch 9's 'once only signal listeners remain, their sources close and the loops end' is then exactly this rule." It is not.

**1. Code after a listener loop now runs canceled.** Today closure gives `Closed<E>`, and "code after the loop and cleanup run normally" (LANGUAGE.md 3846). Under round 1 the item's request is closed, so every later wait returns `Canceled`:

```dewy
parallel {
    work() or_throw
    {
        loop _ in signals.sighup { reload() }
        p"stats.json".write_text(stats_json()) or_throw   # today: written; round 1: Canceled
    }
}
```

The stats are silently not written. Under §2.3 the item's `or_throw` of that `Canceled` "ends the item only".

**2. Manual `next` loops change type.** `next` gives `Signal | Canceled` instead of `Signal | Closed<Signal> | Canceled`. Existing `if s is? Closed break` code becomes a dead arm, and the loop now ends through a `Canceled` path instead.

**3. `or_throw` in an incidental item ends only the item.** This is a refinement of C3 (batch 3, "`or_throw` in an item leaves the enclosing function as it does anywhere"). It is presented as "C3 still holds". Program 12 line 19 (`heart.next or_throw;`) reads as leaving `main`, and doesn't.

**Fix.**

- Either list all three as changes to decided rules (batch 9, C3) in §4, with a recommendation, or keep batch 9's behaviour for code after a loop. The second option means incidental closure ends the *parked wait*, not the item: the wait returns `Canceled` once, and later waits in that item run normally. That is weaker than "close the request", and it would need its own argument.
- The `or_throw` refinement is best stated positively, as the general principle "a group consumes the `Canceled` it causes, including one forwarded by `or_throw`". Then it is an instance of the round's core rule, not an exception, but it should still be shown to David.

### M5. A canceled loser's cleanup failure replaces the winner's success, and the programs don't follow that rule

**Rule involved.** The §2.4 table, row 1: race or `first_ok` with a successful winner gives "the wrapped loser failures replace the success". The `parallel` `return v` row does the same.

**Scenario: program 03, lines 12–15.**

```dewy
let ip = race(@dns.lookup("example.org" via="1.1.1.1") @dns.lookup("example.org" via="8.8.8.8"))
printl"example.org is {ip ?? "unresolved"}"
```

The 8.8.8.8 lookup wins. The loser is canceled, and its socket close fails (`SocketCloseFailed`, D42 Q5). By §2.4, `ip` is `AfterCancel<SocketCloseFailed>`, so the program prints "unresolved" after a successful lookup.

**The programs disagree.**

- Program 03's own comment (line 13) gives `Ip | DnsError`.
- Program 04 line 11 gives `rational | CacheError | Timeout | DbError`.
- Program 03 line 18 omits `AfterCancel` too.

So the programs were not written to §2.4. Under §2.4, every `race` and `first_ok` over I/O gains `AfterCancel<…Close…>` members. That breaks the `race(...) or_throw` and `?? default` idioms, and adds the pair arm (program 11 lines 14, 22–23).

**Fix.** Discard a loser's cleanup failure with the loser's result. This removes Q5 and its new type.

- The group already discards that work. Its close or flush failure describes work nobody will use: program 11's loser file is half-written whether or not its close succeeds.
- D40 Q1 ("a cleanup failure is the function's result") is kept: it *is* the loser's result, and the group discards the loser's result.
- Hover on the group lists what is discarded.
- For certifiable builds, a strict tag (in the `$bulletproof` family) makes discarding a loser's cleanup failure an error that must be handled, in line with "every convenience axiom needs an opt-out demanding real proof".
- If David prefers to keep the failures, the minimum is that they never *replace* a success. Programs 03 and 04 must then be regraded with the extra members.

---

## Should-fix

### S1. A stored handle's type: written function types, and higher-order functions

**What round 1 says.** §2.2 says a function's type carries an inferred mark, and an unknown callee takes "the union of their marks".

**What it leaves open.**

1. **Written function types.** A function type that is *written* (a record field `on_key:(Key):>void`, or a parameter `op:():>T`) has no way to state the mark, because Q1 bans the member from written results. The rule must say what it defaults to. The sound default is "set": calls through it add `| Canceled` where cancellable. That makes a pure key callback in a parallel item give `int | Canceled`.
   - Suggest: a written function type that says `& no blocks` (already writable, D40 Q5) clears the mark, with `check_cancel` counting as a wait for this purpose.
2. **Higher-order functions.** `retry`'s result depends on `op`'s mark, so `retry` is instantiated per (context, mark of `op`), not per context alone. "At most two instances" and "O(F_c + E_c)" are per type instantiation. State that, as for any generic.
3. **Handles stored on the heap.** A heap-stored array of handles filled at run time makes "the union of their marks" a whole-program flow question. Say that a written element type decides it (point 1), and that inference never reaches into a field without a written type.

### S2. A canceled send drops its payload: say so, and name the way to keep it

**What round 1 says.** §2.1(4) says `Unsent` loses the reason `Canceled`, and "the payload is dropped with the canceled task's other locals".

**Why it matters.** That reverses LANGUAGE.md's "a send that fails gives its value back … nothing is lost" for one case. Under moves, an owned payload (a connection, a file, a job taken from a durable queue) is closed by drop, not handed back for re-queueing.

**What is missing from the wait list.** §2.1(2) also leaves out `try_send` and `try_receive`, which LANGUAGE.md 3997 calls cancellation points.

**Fix.**

- State the loss.
- Point to batch 7's `@out.reserve`. A canceled reserve leaves the value in the caller's hands, and `permit.send` can't fail. That is the existing payload-keeping path.
- Say whether `try_*` stop being cancellation points. That is a change to documented behaviour, and is probably right, since they never wait.

### S3. Q1 earns its keep, but only with one meaning of `Canceled`, and should be framed as the effect it is

**Is it an exception?** Yes. An annotation otherwise fixes the result type, and here the compiler adds a member.

**Does it earn its keep?** Yes. The alternative, requiring `| Canceled` in every annotated result where the function is cancellable, recolours annotated signatures whenever a deep helper starts waiting. That is the async colouring §2.8 rejects.

**Two corrections.**

1. Drop "a written `| Canceled` would then mean one the function makes itself". With M1 there is no such member. Writing `Canceled` in a result type is then an error with a fix-it ("added where cancellable; remove it"), not a second meaning. Without M1, one union holds two `Canceled`s, which no reader will follow.
2. Present it as what batch 5 already listed as open ("whether cancellation is an effect row"). Context cancellation is an inferred effect, like `blocks`, that shows up as a result member at cancellable call sites. Then "an annotation fixes the error set" stays true without an exception, and the remaining exception is the narrower, honest one: an effect can add a union member.

**Alternatives weighed.**

- **(a) Effect framing, as above.** Recommended.
- **(b) Written `| Canceled` meaning "where cancellable", required in every annotated cancellable function.** Rejected for the colouring reason above.
- **(c) An opt-in tag requiring it to be written.** For certifiable builds; a possible later addition.

### S4. Q4 is a unification, not a new special case, but its hazard needs naming

**Why it is a unification.** Batch 9 already decided "cancellation leaves the loop as it leaves any wait" for signal iteration. Q4 extends that to every source, and removes `merged`'s "one `Canceled` item, then end" special case (LANGUAGE.md 3966). So it *removes* an inconsistency, and §4 should say so instead of presenting it as new.

**The hazard.** A loop that ends at cancellation looks like a loop that ran out of input. The code after it runs in a canceled task, and can publish a partial result through anything that isn't a wait:

- a lock, which isn't a cancellation point;
- an atomic;
- an outer variable;
- `printl`.

```dewy
loop n in numbers { total += n }
results.lock.push(total)     # a partial total, published as if complete
```

**Fix.**

- Make `loop x in src or_throw` (batch 7's form) the taught idiom inside items when the code after the loop publishes.
- Show "ends early when canceled (group at line N)" in hover on the loop.
- Optionally warn when a loop that may end by cancellation is followed by a non-wait publication of a value the loop accumulated.

### S5. Level 3 (program 08): use the existing channel model instead of a new `CancelRequest.wait` that produces a second `Canceled`

**The problem.** `task.CancelRequest` with `.wait` giving `Canceled` creates the second flavour in M1. It also makes program 08's grade-3 arms (`<job.cancel.Canceled>` versus `<Canceled>`, lines 17–18) necessary.

Round 1 also says program 08 "uses only what batch 7 decided". It doesn't: batch 7's `select` takes channel, `mpmc` and ticker waits. `@codec.finished` and `@job.cancel.wait` need the undecided `Waitable<R>`.

**Fix, within existing constructs.** The request "is a channel with no payload that only its group can close", so expose exactly that. `task.cancel_request` is a receive-only end (`Receiver<…>`) of that channel, and its close is an ordinary `Closed<…>`:

```dewy
Job:type = [path:Path reply:Channel<Reply> cancel:task.CancelReceiver]   # or Receiver<…>, whatever the channel design names it
match select(@codec.done.receive @job.cancel.receive) {
    thumb:Thumb => job.reply.send(Reply[thumb]) ?? void
    <job.cancel.Closed> => codec.abort()      # the caller gave up: a close, not a Canceled
    <Canceled> => break                        # the worker itself
}
```

- The two arms now have different types.
- No new `.wait` member and no second `Canceled` are needed.
- `select` stays within batch 7, provided the codec reports through a channel.

**Two further fixes.**

- Have the worker skip jobs whose request is already closed before `codec.start`. Line 13 starts an expensive decode for callers who timed out while queued. A `select(@job.cancel.receive timeout=0s)` poll does it with existing constructs.
- Forgetting to pass the request stays silent. No construct fixes that, and that is honest.

### S6. `$incidental` inside a helper is non-local, and its interactions with siblings are unspecified

**What round 1 says.** §2.6 allows "a statement prefixed with `$incidental` inside any function".

**Non-locality.** Calling such a helper from essential work can end the caller's group, and nothing at the call site shows it. Program 12 line 23 is the case the author also marked down. That conflicts with David's D40 condition, "no hard-to-follow nonlocal behavior".

**Gaps.**

1. **Real work waiting on incidental work.** C1 lets items wait on each other. In `parallel ( $incidental let x = probe(); let y = use(x) )`, can a sibling read an incidental item's binding? If it can, does that wait keep `x` alive?
2. **An incidental item holding a lock** across its sleep. An essential item blocked on `lock` (not a wait) keeps the group alive forever, so the block never ends. The lock-order checker should report it.
3. **Where the rule applies at all.** The `task.tasks` body, `BackgroundTasks`, and items not yet started under `max_concurrent` are not covered.

**Fix.**

- Infer an "may park incidentally" mark, as for the cancel mark, and show it in hover at the call site.
- Restrict the inner-statement form to a statement that is itself a wait.
- State that a sibling waiting on an incidental item's value makes that item essential while it waits. The batch 9 rule already had "publish ready dependents before deciding closure".

### S7. Three presses within a second now force exit even while a handler intercepts: a new rule that breaks REPLs

**The change.** §2.7 extends LANGUAGE.md's forced exit, which today covers *observed* presses during root shutdown, to presses an interceptor is handling.

**Scenario.** In the REPL, which races `readl` against `signals.ctrl_c` (batch 9), a user presses Ctrl-C three times quickly to abandon a long expression. The REPL process exits and its session is lost. Python's REPL never does that.

**Fix.** Force exit only when the handler has not yet run since the first press (a stuck handler), or make it a setting. List it as a new rule either way.

### S8. "`task.tasks`: … or the body leaves" contradicts v5 and program 09's drain

**What conflicts.**

- §2.1(3) closes the children's requests when "the body leaves".
- v5 says "normal body completion joins its children".
- Program 09 line 28 relies on that: "tasks returns once every connection task has finished".

If "leaves" includes the body's normal return, program 09 cancels every open connection at SIGTERM instead of draining them.

**Fix.** Write "the body fails (or leaves by `or_throw`)".

### S9. Cleanup's grace deadline must apply only to a canceled task

**What round 1 says.** §2.4 says drop hooks and `defer` "run as `protect_from_cancel(grace @cleanup)`", which is unconditional.

**Consequences.**

1. In `main`, where nothing cancels, a slow final flush (network disk) is cut off after 100 ms and the resource is abandoned. Today it just completes.
2. Every program with a fallible drop hook (any file write) then reaches `protect_from_cancel`, a cancellable context. So §2.10's "if no group construct is reachable … it does nothing … panel cost is zero by construction" is false for the compiler's own build.

**Fix.** Cleanup is shielded from cancellation always, and the grace deadline starts only when the task's request is already closed, or closes during cleanup. In a non-cancellable task there is no deadline.

---

## Notes

- **N1. Hover examples name the wrong lines.** In round1.md §1, "One function, two contexts", the hover says "+ Canceled at lines 4 and 5". Line 5 is `load_theme`. Program 06 line 9 repeats it ("line 15 and line 16"; line 16 is `load_theme`). Since hover is the design's main answer to "where can this cancel", its examples should be right.
- **N2. D42 Q7's new rationale relies on an order that doesn't exist.** §3 says codes "follow `main`'s declared error order, so the kind listed first wins". Unions and `&` are unordered (batch 10), so this needs a real rule or should be dropped. Also, with M1 an explicit `Canceled` can no longer reach `main` at all, which strengthens the case to drop the "130 outranks" reason.
- **N3. New spellings missing from the cold-read kit.** `AfterCancel<E>`'s `.failure` (program 11 line 15; Q5) and `CancelRequest.wait` (Q3) are new and not in `names.txt`. S5 and M5 would remove both.
- **N4. Changes to decided rules to list plainly in §4.**
  - `select` gives `Canceled` only in cancellable code (batch 7 says "plus `Canceled`", always).
  - `Closed<E>` leaves signal results (batch 9).
  - `Task.wait()` stops reporting a stop's `Canceled` (v5 semantics under batch 5's accepted names). This also loses "finished" versus "stopped" from `.wait()`; say how a caller tells them apart, for example `.running` read before `stop()`.
  - `task.catch_ctrl_c` (v5) is superseded and absent from the knock-on edits.
- **N5. Extending the select progress rule (D42 Q2 withdrawn) turns a hint into a rule.** LANGUAGE.md's `select` progress rule reads as a requirement, while D42 Q2 proposed a warning, "a hint, not a proof", because waits inside callbacks aren't seen. Say whether the extended `??` rule is a warning or an error.
- **N6. A block made entirely of signal listeners still ends at once, without a diagnostic.** The "every item incidental" error covers only tagged items. A `parallel { loop _ in signals.sighup {…}; loop _ in signals.sigterm { return } }` block, with no other work, also ends immediately (as under batch 9). It should get the same error when the library mark is visible.
- **N7. Definition versus rule.** "Code is cancellable when it runs on a request that something can close" contradicts "every `parallel` item counts, even when nothing in its block can leave early". Define cancellable syntactically: the items of group constructs and what they call.
- **N8. Program bugs worth fixing before David sees them.**
  - 12 line 24 says "stopping after the current job", but `return` cancels `run_job` mid-job. The existing-construct fix is `check_cancel() or_throw` at the top of the loop, with `protect_from_cancel(limit @run_job(file))`.
  - 11 line 12 uses `race` where `first_ok` is meant: a fast failure on one disk cancels a good write on the other.
  - 11 line 6 truncates the previous good backup on the losing disk.
  - 05 line 7: `print("\r")` doesn't clear the line, and line 15 prints onto the spinner's line.
  - 13 line 6 claims `WatchError`, which nothing in `watch_assets` produces.

---

## The checklist, answered briefly

- **Inference.** The rule is decidable: finite (function, context) pairs and the existing fixpoint. It needs the following to be precise:
  - per-instantiation counting for higher-order functions and written function types (S1);
  - one flavour of `Canceled` (M1);
  - the honest one-body rule (M2).

  Recursion, libraries, `parallel x in xs`, `task.tasks` (but see S8), `select`, and `within` in `race` are handled correctly.
- **Q1.** It is an exception as written. It earns its keep as an effect, with written `Canceled` made an error (S3).
- **The claim and its three corrections.** The claim is true for waits only after M1's storage rule. The three corrections are visible in §1 and §2.3. The send change hides a payload loss (S2), `.wait()` loses information (N4), and the narrowing has the layout problem (M2). None of them is in §4.
- **`$incidental`.**
  - Every item incidental: an error for tagged items, but undefined for `race` and `within` (M3).
  - Holding a resource: cleanup is fine, a lock can wedge the group (S6).
  - Real work waiting on incidental work: unspecified (S6).
  - Nesting: fine for owning groups.
  - Signal rule without behaviour change: no (M4).
- **Q4.** It earns its keep as a unification with batch 9 (S4).
- **Q5.** It does not earn its keep. Discard losers' cleanup failures with their results (M5).
- **Program 08.** The request as a receive-only channel end, giving `Closed` (S5).
- **Unstated new syntax or rule changes.**
  - the forced exit (S7);
  - the C3 refinement (M4);
  - `select`, `Closed<E>`, `.wait()` and `try_*` (N4, S2);
  - the unconditional grace deadline (S9).
