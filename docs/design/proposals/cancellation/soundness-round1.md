Verdict: revise before implementation; the context-inference idea is viable, but round 1 does not yet specify a sound implementation.
Must-fix count: 4.
Decidability: the two-context reachability fixed point is finite and monotone; that alone does not establish termination or cost of full type inference.
Code sharing: possible for some functions, but one unconditionally cancellable compiled body is not equivalent to two contextual instances in general.
Containment: own-request cancellation can be consumed at its owning boundary; cancellation carried as data, foreign requests, and dynamic incidental shutdown invalidate the blanket claim.

This is a design review of `brief.md`, `round1.md`, all thirteen `programs-r1/` sources, the specified language sections, decisions batches 3, 9 and 10, and the relevant D41/D42 and task-proposal contracts. Programs below are self-contained design test cases, not claims of acceptance by the current compiler. Proposed APIs and metatags use round 1's spellings. No compilation, benchmark, repository edit or commit was performed. Line references are to the reviewed `round1.md` unless a different document is named.

## M1 — A cancellation bit is not a complete stored-callable type

**Severity: must-fix.** Rules: §2.2, lines 121–129; §2.10, line 303; Q1, lines 403–417.

The rule for a handle says to take its result and add a top-level `| Canceled` when its inferred bit and the calling context are both set. Context can instead change a field, an element type, a returned closure's captures, or a generic specialization. A top-level addition cannot describe those changes.

```dewy
pack = () => [outcome=sleep(1s)]

inspect = (op) => {
    let packet = op()
    if packet.outcome is? Canceled printl"observed cancellation inside a record"
    0
}

main = () => {
    let slot = [run=@pack]
    let callbacks = [@pack]
    let before = slot.run()
    printl(before)
    race(@inspect(callbacks[0]) @(() => 1));
}
```

The non-cancellable call produces `[outcome:void]`. The cancellable call must produce `[outcome:void | Canceled]`. `pack` does not forward a top-level failure at all. A losing `inspect` can observe an actual `Canceled` in `packet.outcome` before it finishes; dropping its eventual result does not make its intermediate execution unreachable.

If the handle keeps the first type and merely appends a top-level cancellation alternative, the field is incorrectly typed and the program is unsound. If it keeps `[outcome:void | Canceled]` in both contexts, it is sound but imprecise in `before`. If it keeps a complete context-indexed result scheme, it is sound and precise here. Round 1 must choose and specify one of the latter representations, rather than claiming the bit suffices.

Captures require a second distinction: invoking a closure in a new context does not retype data it captured in the old context.

```dewy
capture = () => {
    let saved = sleep(1s)
    () => saved
}

main = () => {
    let later = within(1ms @capture) or_throw
    printl(later())
}
```

Consider an execution in which `capture` starts, its sleep is canceled at the deadline, and it returns the closure. Section 2.3 explicitly permits a child that handles cancellation to return a successful value. The later root-context invocation can return that captured `Canceled`. The closure contains no wait and has no ambient cancellation to forward. Its captured result is ordinary data, so the correct root result retains `Canceled`. Neither recomputing the captured value's type in the invocation context nor using only a wait-reachability bit is sound. Rejecting that closure escape would also be safe, but would be an additional restriction, not the rule stated here.

**Suggested fix.** Use an internal callable scheme with two result descriptions, `R[noncancellable]` and `R[cancellable]`, or an equivalent symbolic type expression. Context dependencies must survive inside aggregate and generic types. Captured values retain their creation-time types; only newly executed operations use the invocation context. At an indirect call, instantiate the scheme in the caller's executing context. Merge schemes pointwise when combining compatible handles. Preserve independent, ordinary `Canceled` alternatives in both results.

The scheme need not introduce a user-written context parameter. It does, however, have to survive explicit function-type boundaries, record fields, arrays, channels and module interfaces. For a slot such as `[run:(():>int)]`, Q1 must say whether the callable contract implicitly quantifies over the inferred ambient-cancellation effect, and define assignment/subtyping in both contexts. For a more specific slot such as `[run:(():>[outcome:void])]`, Q1's top-level exception is insufficient: reject an incompatible `pack`, infer a richer contract, or require a conservative field type that includes `Canceled`. Quietly erasing the dependency is not an option. Programmer-visible context syntax is avoidable; ordinary types mentioning stored `Canceled` are not always avoidable.

## M2 — Ambient cancellation and foreign/data cancellation need separate origins

**Severity: must-fix.** Rules: §2.2 lines 127–139; §2.3 lines 145–176; §2.4 line 181; §2.5 lines 206–213; §3's ambient-only diagnostics and proposed LANGUAGE line 3663 replacement.

The exceptions in §2.3 are necessary, but they are not integrated into the handle rule or the claim that no wait-produced `Canceled` reaches `main`. A wait on someone else's closed request is a direct counterexample, without explicitly constructing `Canceled` or storing that failure value.

```dewy
import p"@lib/std/tasks.dewy" as task

Envelope:type = [request:task.CancelRequest]

publish = (out:Channel<Envelope>) => {
    out.send(Envelope[task.cancel_request]) or_throw
    sleep(1s) or_throw
}

await_other = (request:task.CancelRequest) => request.wait

main = (app:BackgroundTasks) => {
    let out = channel<Envelope>(1)
    let child = app.spawn(@publish(out))
    let message = out.receive or_throw
    child.stop()
    child.wait() or_throw
    let waits = [@await_other(message.request)]
    let result = waits[0]()
    printl(result)
}
```

Choose the ordinary execution in which `publish` remains asleep when stopped. The request is closed. The final invocation takes place in `main`, but it returns an actual wait-produced `Canceled`. Its correct type includes `Canceled` unconditionally. If the ambient-only handle rule removes it, the type is unsound. Applying §2.3's foreign-request exception instead is sound, but directly contradicts lines 14 and 176 and the proposed replacement at line 379. The analogous source-qualified `select` outcome remains possible in non-cancellable code too.

Replace the last two lines with any one of the following to exercise a group boundary:

```dewy
    let result = race(@await_other(message.request) @(() => { sleep(1s) or_throw; 7 }))
    printl(result)
```

```dewy
    let result = first_ok(@await_other(message.request))
    printl(result)
```

```dewy
    let result = within(1s @await_other(message.request))
    printl(result)
```

These are variants of the complete program above. The foreign cancellation can respectively win `race`, be the sole failure of `first_ok`, or complete `within` before its own deadline. In each case the root result must retain `Canceled`. It is not the new group's cancellation to drop or translate into `Timeout`.

Runtime provenance also matters when an old cancellation and a new owner stop coexist. A task may already hold a foreign cancellation when its current group closes its own request. Testing only “is this task canceled now?” cannot determine which cancellation the task returns. Likewise, `Canceled & FlushError` identifies failure kinds, not the request responsible for its cancellation part. The same issue affects `.wait()` after `.stop()`: suppress the stopped child's expected cancellation, preserve an intrinsic/foreign one, and independently observe cancellation of the waiter.

Ordinary binding cannot itself turn every contextual cancellation into an unrelated intrinsic failure. Otherwise `sleep(1s) or_throw` and `let r = sleep(1s); r or_throw` have incompatible containment behavior. Conversely, copying a cancellation into published data cannot justify removing it from that data's type. The phrase “a `Canceled` read from a variable” needs a more precise rule.

**Suggested fix.** Distinguish ambient-request cancellation from independent cancellation in type summaries, and specify runtime origin preservation wherever a boundary must remove exactly its own cancellation. A retained request identity or equivalent origin token is sufficient in principle; public error syntax need not change. Copying, returning, combining and extracting failures must have defined origin behavior. Requests passed as data must retain safe identity and lifetime after their task/group ends; a pointer into a destroyed task frame is insufficient.

The static analysis need not enumerate dynamic requests. Use a finite abstraction such as ambient, known owned boundary, and independent/unknown; retain `Canceled` conservatively when an origin cannot be proved local. A plain type test for `Canceled` must not authorize boundary-specific erasure.

Restate the containment theorem narrowly: an unwrapped cancellation propagated from a task's ambient request is consumed or translated at its responsible structured boundary, provided no other value path publishes it. This says nothing about all waits or all code that itself starts no group. `$explicit_cancellation` and spin diagnostics must inspect whether the expression can yield `Canceled`, including independent cancellation, rather than just the caller's ambient context.

## M3 — One cancellable machine body can change non-cancellable semantics

**Severity: must-fix.** Rules: §2.10 lines 303 and 309–312; binding brief §3's contextual instances; LANGUAGE's generic specialization and `members` rules.

Keeping a union tag and unreachable cancellation branches can share many ordinary bodies. It does not preserve arbitrary type-dependent computation. This example observes the inferred argument type through an existing generic operation, even though both executions finish their waits normally:

```dewy
count_alternatives = <T>(value:T) => {
    let count = 0
    loop alternative in members(T | string) { count += 1 }
    count
}

wait_value = () => { sleep(0ns) or_throw; 7 }
probe = () => count_alternatives(wait_value)

main = () => {
    printl(probe)
    parallel { printl(probe) }
}
```

In the non-cancellable typed instance, `T` is `int`, so `members(T | string)` has two alternatives. In the cancellable instance, `T` is `int | Canceled`, so it has three. The second instance is required even though this one-item `parallel` cannot trigger cancellation: every item counts by the binding decision.

Emitting only the cancellable specialization of `probe` computes three in both places. Emitting only its non-cancellable specialization computes two in both places. Neither implements the two contextual programs. Both `probe` results are `int`; appending a cancellation tag cannot repair this semantic difference. The same problem can arise with overload selection, type-dependent layouts and other generic operations. Also, “at most two” means per existing concrete generic specialization, not per source function.

The record example in M1 independently requires an ABI decision. A return with a `void` field and one with a tagged `void | Canceled` field are different source types. The caller cannot simply ignore a tag while assuming a different record layout. Arrays, nested records and function-returning functions make that requirement recursive.

**Suggested fix.** Preserve separate contextual typed IR and share machine code only after proving the lowered behavior and calling convention compatible. Alternatively, use a common representation plus context dispatch for every type-dependent operation. That dispatch must distinguish a closable request from the root/sentinel, not merely test whether cancellation has already happened. It is additional behavior absent from the current “the wait already reads the request” justification.

Stored handles then need a specified invocation adapter, contextual entry selection, or uniform context-aware body; the creation context must not fix the selected version. A uniform return envelope can support sharing, but its layout/conversion costs need accounting. Do not promise zero duplicated code or that all cost is one comparison inside each wait before these choices are made. The binding decision already permits contextual compilation, so selective sharing is an implementation optimization rather than a required semantic constraint.

A single shared body can soundly observe an internal `Canceled` while its non-cancellable caller's result type excludes it: for example, a non-cancellable helper can start `within`, whose child is cancellable. The emitted code must handle the child cancellation, translate its own deadline to `Timeout`, and only then return. Excluding top-level `Canceled` at the caller never licenses removing internal cancellation handling. It is sound to omit a caller-side branch only after proving that the boundary cannot publish that alternative, with the origin and incidental cases in M2/M4 resolved.

## M4 — Dynamic incidental shutdown invalidates the normal-completion and winner proofs

**Severity: must-fix.** Rules: §2.3 lines 149 and 158–162; §2.6 lines 219–237; correction “values read after a parallel block are narrowed.”

The narrowing proof assumes an essential item can be canceled only by an exit that skips the continuation. Section 2.6 adds another path: an initially ordinary item becomes incidental while parked inside a helper. The group can then cancel it and still reach its normal continuation.

```dewy
import p"@lib/std/signals.dewy" as signals

listen = () => signals.sigterm.next

main = () => {
    parallel (
        let event = listen
        sleep(0ns) or_throw
    )
    printl(event)
}
```

With no SIGTERM delivered, after the sleep finishes only the signal wait remains. Section 2.6 closes its request. `listen` returns `Canceled` as its value; it has no `or_throw` leaving `main`. If line 158 narrows `event` to `signals.Signal`, the continuation receives a value outside its type.

There is a potentially sound escape in line 237: reject an incidental item whose binding is read afterward. To cover this example, that prohibition must include *transitive, dynamically incidental* waits, including calls through handles, and must run before the narrowing proof. If that is the intended reading, this specimen must be a compile error, not a successful narrowing example. Classifying only explicitly tagged items is insufficient. Retaining `signals.Signal | Canceled` is the other sound, less restrictive result. The current proposal does not specify the necessary transitive analysis or its cost.

There is also a pre-winner problem for result-selecting groups:

```dewy
import p"@lib/std/signals.dewy" as signals

choose = (ready:bool) => {
    if ready return 7
    signals.sigterm.next or_throw;
    9
}

main = (argv:array<string>) => {
    let ready = argv.length >? 1
    let result = race(@choose(ready) @choose(ready))
    printl(result)
}
```

On an execution with `ready=false` and no signal, both initially runnable items eventually park incidentally. The general incidental rule cancels both before any winner exists. Both can then return the race's own `Canceled`, contradicting line 149's proof that this never happens. Dropping both leaves no `int` winner; returning one leaks a cancellation excluded by the root result; inventing `void` changes the result type. `first_ok` has the analogous all-failed case. A sound implementation may conservatively reject this program under “every item incidental,” but that requires a rule about *possible future* incidental states, not just the initial syntactic marking. It must say so and account for the rejection's imprecision.

**Suggested fix.** Define incidental shutdown separately for ordinary joining groups and winner-selecting/deadline groups, including exactly which owner may initiate it and what completion it publishes when no winner exists. For parallel result narrowing, require a proof that the result-producing item cannot be stopped on any path that reaches the continuation. Otherwise retain its `Canceled`, or reject the escaping binding under an explicit conservative transitive rule. Do not remove cancellation recursively from stored records/collections: §2.3 correctly treats those as data.

This also needs the stated “every child returns `Canceled`” at line 150 weakened. A child may handle cancellation and return a value, return another error, or compute forever without another checkpoint. Structured cancellation requests shutdown and joins; it does not determine every child's result or guarantee termination.

## S1 — Specify the actual fixed point and limit the linear-cost claim

**Severity: should-fix.** Rules: §2.2 lines 130–136; §2.10 lines 301–305.

The inexpensive part can be stated precisely. Let `B` be the demanded concrete function/body specializations, including callback bodies and cleanup bodies. Generic argument types and callable contracts are part of a specialization key. Let `Q = {N, C}` denote non-cancellable and cancellable execution. Let `Targets(e)` be a sound set of possible targets of call edge `e`, or use a sound callable summary in its place. Reachability is a subset `D` of `B × Q`.

For each reached `(b,q)`, a call site has a context transfer `tau_e(q)`:

- Ordinary direct calls and synchronous handle calls preserve `q`.
- A group child's execution, a task-group body, a spawned task, or a protected callback uses `C`, including when its caller is `N`.
- A cleanup callback uses its fresh grace request, hence `C`; shielding removes the old request, not its own grace deadline.
- The continuation after a group/protected call resumes in its caller's original `q`.
- Creating, copying, storing or sending a handle does not execute it and does not bind its future call context. Its stored captures keep their existing types.

The least fixed point is:

```text
D0 = {(entry, N)} plus the applicable runtime entry roots
D(i+1) = D(i) union
         {(g, tau_e(q)) : (b,q) in D(i), e is a call in b, g in Targets(e)}
```

The REPL's entry is instead seeded `C` as specified. Library/runtime entry callbacks require their actual contracts, rather than an assumption that every entry is `main`. An indirect call may demand a target in a context in which its handle was never created.

For a fixed finite `B` and sound fixed call graph, this operator is monotone on a finite powerset lattice. Each node is added once; a worklist terminates. Its cost is `O(|B_reached| + |E_reached|)` and corresponding graph storage, with at most two context nodes per existing specialization. SCCs are convenient for recursion but not needed to make this reachability terminate. A direct recursive cycle creates no new contexts after the two bits have settled.

```dewy
even_step = (n:int) => {
    if n <=? 0 return 0
    sleep(0ns) or_throw
    odd_step(n - 1)
}
odd_step = (n:int) => {
    if n <=? 0 return 0
    even_step(n - 1)
}
main = () => {
    printl(even_step(4))
    printl(within(1s @odd_step(4)))
}
```

Both functions acquire `N` and `C` instances. Their result summaries are `int` in `N`, `int | Canceled` in `C`. The root call of `within` gives `int | Timeout`. Cancellation in the recursive child is real when the deadline wins, but the boundary handles it. No additional recursion-related cancellation unsoundness is needed to explain this program. A self-recursive version has the same fixed-point behavior.

Result inference is a separate fixed point. One possible formulation uses maps from `(b,q)` to abstract return-value/type descriptions, with bottom initially, joins at control-flow merges, and per-body transfer functions reading callee summaries. A cancellation occurrence needs the distinctions in M2, and a result description needs aggregate/closure structure from M1. With a finite-height abstract domain and monotone transfer functions, ordinary worklist iteration terminates. A coarse bound includes the lattice height and cost of each transfer; it is not just the number of call edges.

Do not infer `R[N]` by blindly deleting `Canceled` from `R[C]`: nested independent cancellations remain, and type-reflective computation can select other types or values. The reachability bits are monotone; the claim that every part of type checking is a monotone one-bit propagation is not established. Context-sensitive overload/generic resolution must use the compiler's existing stabilization/termination rules.

In particular, unrestricted polymorphic recursion could keep creating new members of `B`; a finite number of source functions does not prove that this process terminates. Keep the existing rejection/bounding rule for unbounded specialization. Exact discovery of “this path can really be canceled” would additionally require deciding arbitrary program behavior. The intended conservative policy, including marking all parallel items, avoids that requirement and should remain explicit.

**Suggested fix.** State the linear bound only for context propagation over an already resolved graph. Separately account for indirect-target analysis, generic instantiation, contextual type checking, origin summaries and incidental analysis. An unknown handle either uses a conservative contract or expands to all compatible targets; the latter can make the graph dense. A union of cancellation bits is sound only for the restricted top-level effect case, not as a substitute for the other summaries.

Demand-driven discovery should start at actual entry roots and demand bodies/summaries as calls are reached, with extra context checks only for demanded instances. Hidden cleanup/protection operations count as roots of cancellable work too. “No group construct” in surface source does not prove zero work, and no measured flagship-panel result was supplied. Reuse the normal call graph to make the no-extra-context path inexpensive; measure before claiming zero cost.

Materializing all responsible group sites for every hover can require a group-by-function product even on a small shared graph. Store predecessor/provenance links and expand hover explanations lazily. Incremental deletions also need invalidation/recomputation of dependent summaries and callers; merely pushing reachability forward cannot retract an obsolete context or repair a caller's result type.

## S2 — Joining and cleanup need explicit context-transfer exceptions

**Severity: should-fix.** Rules: §2.1 lines 87–90; §2.4 lines 180–196; §2.8 lines 275–278; existing structured-join and `protect_from_cancel` contracts.

The ordinary-wait sentence says an already closed request produces `Canceled` immediately “without doing its work.” Applied literally to a group join, this permits returning before the owned children have finished. That conflicts with structured lifetime and the promise to keep cleanup failures.

```dewy
child = () => {
    sleep(1s) ?? void
    printl"child tail finished"
}
owned = () => {
    parallel { child() }
    printl"owned continuation"
}
main = () => {
    race(@owned @(() => 1));
    printl"race returned"
}
```

If the quick item wins while `child` is sleeping, the child handles cancellation and still executes its tail. The outer race cannot publish its result until that tail and all owned cleanup finish. A canceled join may request shutdown immediately, but its externally returned `Canceled` must wait for the mandatory drain. This does not require that `owned` run its ordinary continuation after cancellation; it requires that its children be joined before its enclosing boundary is released.

Shielding changes which request a wait observes:

```dewy
cleanup_wait = () => {
    if sleep(1ms) is? Canceled printl"cleanup grace expired"
}
main = () => {
    defer { cleanup_wait() }
    printl"body finished"
}
```

`cleanup_wait` is checked in `C` even though `main` is `N` and the source contains no explicit group. Its sleep can return grace-request `Canceled` if the cleanup cannot finish before that deadline. This helper handles it, so its own result is `void`; the deferred action remains non-failing. The parent request must not cancel this sleep. For a fallible drop hook, the inferred owner result must additionally include the documented cleanup failure/timeout mapping, even in `N`. “The cleanup design owns that” cannot mean omitting that summary from cancellation inference.

**Suggested fix.** Distinguish cancelable waiting from the required lifetime join. Cancellation of a group join starts cancellation-and-drain; only after draining may it return the caller's cancellation plus retained failures. Cleanup and protection enter a fresh request regardless of a pending parent request, then restore the parent context. Their inner waits may return their own cancellation, with a specified boundary translation. These transfer rules should be shared by typing and lowering. They also explain why a non-cancellable outer function can execute an internal cancellable instance without leaking its cancellation.

## N1 — Remaining boundary specimens and expected types

**Severity: note.** Rules: §2.2's call-site context, `task.tasks`, `select`, library and nested-group rules. These cases do not require rejecting the two-context idea; they are acceptance specimens for the corrected rules above.

### Handles sent across task boundaries

```dewy
Job:type = [run:(():>int)]
pause_then_value = () => { sleep(1s) or_throw; 7 }

worker = (jobs:Channel<Job>) => {
    let job = jobs.receive or_throw
    job.run()
}

main = () => {
    let jobs = channel<Job>(1)
    jobs.send(Job[@pause_then_value]) or_throw
    printl(within(1ms @worker(jobs)))
}
```

Under Q1 applied to callable fields, `Job.run` is implicitly context-polymorphic. Its invocation in `worker` gives `int | Canceled`, regardless of its construction in `main`. The child may actually return cancellation; the root `within` gives `int | Closed<Job> | Timeout` (plus any independently specified environmental failures), not its own ambient `Canceled`. If the annotated function field instead erases the inferred mark, this is unsound. If Q1 does not apply to callable fields, reject the assignment rather than accepting it and forgetting the effect. Channels impose their usual transfer requirements independently; the uncaptured function handle here needs no shared mutable capture.

### Generic forwarding

```dewy
identity = <T>(value:T):>T => value
pause = () => identity(sleep(0ns))
main = () => {
    pause()
    parallel { pause() or_throw }
}
```

The two `pause` results are `void` and `void | Canceled`. `identity` is instantiated with the corresponding argument types; those are generic specializations, not extra ambient states. The parallel item's cancellation alternative is impossible in this particular complete program, because nothing can close its request. It is intentional imprecision required by the binding “every item counts” rule, not unsoundness. The more demanding generic specimen is M3.

### Library used in both contexts

This is a complete two-module specimen, included here without creating either module:

```dewy
# library_wait.dewy
wait_value = () => { sleep(1s) or_throw; 7 }
```

```dewy
# application.dewy
import p"library_wait.dewy" as waits
main = () => {
    printl(waits.wait_value)
    printl(within(1ms @waits.wait_value))
}
```

The direct result is `int`; the protected child is `int | Canceled`; the root deadline call gives `int | Timeout`. Loading this module's source once is compatible with demanding both contextual instances. Round 1 explicitly says modules are lazy, whole-program inputs, not separately compiled library images. Consequently it does not supply a separate-binary ABI, and should not claim one. If a compiled image is later supported, its exported callable scheme and entry/return convention must preserve these same contracts. This simple helper can share code under a common return convention; M3 shows why arbitrary library helpers cannot be promised identical code.

### Tasks started one by one

```dewy
import p"@lib/std/tasks.dewy" as task

Broken:type = type of error
slow = () => { sleep(1s) or_throw }
fail = () => Broken

main = () => {
    let result = task.tasks((group:Tasks) => {
        let a = group.spawn(@slow)
        let b = group.spawn(@fail)
        sleep(1s) or_throw
    })
    printl(result)
}
```

The body and `slow` execute in `C`; their sleeps are `void | Canceled`. `fail` returns ordinary `Broken`. When it fails, the group can cancel the body and `slow`, join them, and return `Broken` to `main`. Conservative result typing may also retain `void`; no own-group cancellation needs to escape. Every late spawn must receive a closable child request, including spawns through helpers; start-before-failure races do not change that invariant.

The group body is result-polymorphic. Preserve the existing task proposal's distinction: successful callback completion/`return value` joins children and preserves the value; callback failure cancels them. Round 1's “body leaves” at line 100 is ambiguous about normal return and should not accidentally turn program 09's successful drain into cancellation. This is a specification clarification, not a need for a third cancellation context.

### Select without and with ambient cancellation

```dewy
poll = (jobs:Channel<int>) => select(@jobs.receive timeout=1ms)
main = () => {
    let jobs = channel<int>(1)
    printl(poll(jobs))
    printl(within(1ms @poll(jobs)))
}
```

In `N`, `poll` gives `int | Closed<int> | Timeout`; in `C` it additionally gives ambient `Canceled`. Either timeout may win in the second call, but the root `within` result needs no ambient cancellation. Prepared source handles are called/registered in the selecting task's context. If an arm instead waits on a foreign request, its independent `Canceled` remains in `N`, as in M2; a source-qualified arm distinguishes it from the select operation's own cancellation. This distinction is not optional precision.

### Within inside race, and race inside within

```dewy
slow = () => { sleep(1s) or_throw; 7 }
fast = () => 9
nested_race = () => race(@slow @slow)

main = () => {
    printl(race(@within(1ms @slow) @fast))
    printl(within(1ms @nested_race))
}
```

For `within` inside `race`, the child wait is `void | Canceled`. The `within` call is itself inside a race item, so it gives `int | Timeout | Canceled`: its own deadline translates, its parent's cancellation propagates. The root race gives `int | Timeout`; its loser cancellation is dropped after joining. Parent/deadline ties must use the specified parent precedence consistently, with recorded origin rather than guessing from a later check of both closed requests.

For `race` inside `within`, the inner race's parent is cancellable. On expiry it requests cancellation of both children, joins them, then returns parent cancellation. The outer `within` translates that to `Timeout`. The root result is again `int | Timeout`. Neither example requires an unbounded stack of static context kinds; dynamic owner identities belong to boundary handling. M4's incidental-before-winner case is separate and is not exercised here.

### Parallel inside a non-cancellable helper

```dewy
pause = () => { sleep(0ns) or_throw; 7 }
collect = () => {
    parallel (
        let a = pause
        let b = pause
    )
    [a b]
}
main = () => printl(collect)
```

Both `pause` items have `int | Canceled` inside the group, even though `collect` is reached in `N`. With no incidental wait, parent cancellation, explicit stored cancellation or early exit, their own request cannot close on a path that publishes these results. Narrowing the completed values to `int` is sound; `collect` returns an integer array. An implementation that merely propagates the caller's `N` into all descendants misses the nested group and is wrong. An implementation that keeps the element cancellation alternatives is sound but less precise than the proposed narrowing.

**Suggested disposition for N1.** Retain the intended call-site context rule and use these as typing/lowering acceptance cases. Do not add new user annotations merely to distinguish where a handle was created. Preserve independent errors, enforce both-context callable contracts, and keep contextual machine-code sharing conditional on M3's requirements.

## Assessment of the three containment corrections

**Severity: note.** Rules: opening claims at lines 14–20 and §2.3. The programs and fixes are M1–M4 and N1 above.

1. **Suppressing an owner-stop result from `Task.wait()`: conditionally sound.** It removes one important leak. It requires origin-aware suppression, preservation of independent child failures and cleanup failures, and a separate check of the waiter's cancellation. It does not prove that every result named `Canceled` is suppressible.
2. **Returning bare `Canceled` from a canceled send: sufficient for that direct result path, not necessary for soundness.** It makes own-request cancellation easier to recognize, but recognition still needs origin. A wrapper could also preserve provenance and be transformed deliberately. A record payload or other published data can still carry cancellation elsewhere; changing the send result does not establish global containment. Payload/resource cleanup can also add ordinary failures which the result summary must retain.
3. **Narrowing after parallel: sound only with a continuation-sensitive proof.** It works in N1's simple `collect`, and cannot strip explicit or independently stored cancellation. M4 breaks the blanket proof unless dynamically incidental producers are excluded or their cancellation alternatives retained.

The statement “every wait-produced `Canceled` is consumed by the group that caused it” is false as written. The exceptions already admitted by round 1 include values whose ultimate source was a wait, and M2 produces a fresh cancellation directly from a foreign-request wait in `main`. The useful theorem is about a particular ambient origin and a particular structured return path, not about the public failure kind everywhere in the program.
