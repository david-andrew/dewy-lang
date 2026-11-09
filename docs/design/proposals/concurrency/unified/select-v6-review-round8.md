- Reviewed all 18 programs, the proposal, questions, relevant LANGUAGE sections, and v5. Paper review only; no compiler or performance validation.
- Grades were fixed before reading the three earlier reviews. No author grades were read.
- Verdict: keep the owner's receiver spelling for the common case. It removes real wrapper ceremony. Do not accept the present identity, widening, generic-name, or clash rules as a sound specification.
- Best version: `heart.Tick` denotes a source refinement of a particular result. Keep ordinary `Tick` matching every source. Do not claim it is an ordinary reusable subtype whose runtime identity survives only in selected contexts.

- **Concrete rules for the improved version:**
- Give every prepared wait a provenance key. Capture the receiver binding and its version when preparing it. Map that key to argument slots in each selection. Never infer provenance from channel pointer equality.
- Preserve that key through `@`, locals, `if ... else none`, and generic helpers that preserve a wait. Programs 02, 06, 10–12 require this; ordinary callable return types alone are insufficient.
- Resolve `heart.Tick` to all relevant slots prepared through that version of `heart`. Two operations on that receiver share its qualifier. This is useful grouping, but cannot identify which operation completed.
- For finer granularity, let a named prepared operation qualify its outcomes too: `let receive = @outbound.receive`; `let reserve = @outbound.reserve`; then `<(@receive).Closed>` and `<(@reserve).Closed>`. This deliberately extends r8's receiver-only rule.
- The same extension handles receiver-less work: `let web = @load(url)`; `race(@web @cache.receive)` can match `page:(@web).string`. Qualifying a function value needs `(@web)`: `web.string` would first call it under ordinary Dewy rules.
- Reject visibly duplicated operations as redundant. Aliased registrations must remain safe without an alias proof. One receiver qualifier groups repeated registrations; named waits distinguish them when needed.
- `other = heart` does not create another physical receiver. Distinct qualifiers may label distinct prepared arguments, but must be described as provenance through bindings. The present “per value, different even when equal” explanation contradicts itself.
- Allow source refinements while matching an intact result or a local copy of it. Extracted payload bindings have ordinary payload types. Returning, sending, field storage, and conversion to an ordinary union erase provenance; later qualified matching must error, never become a broad match.
- Specify local copies, assignments, joins, captures, and generic identity calls explicitly. `let got = ...` cannot both preserve provenance and fall under an unqualified “storing widens” rule.
- Reject a qualified use if its receiver path has changed since wait preparation. Track ancestor field replacement too: changing `child` or `child.stdout` matters. An immutable named wait remains usable after the original receiver variable changes.
- Do not freeze a receiver merely because an old result exists. Permit reassignment when no later qualified use depends on that version. Explicitly widening or dropping the result ends that dependency.
- Keep `merged` iteration payloads plain as decided. Its `.next` retains source refinements. Selecting `@inbox.next` must compose inner provenance with outer provenance rather than overwrite the original source index.
- Direct `receive` should support the same qualifier with one implicit source. This makes 10 and 13 legal without adding a pointless one-wait `select`. State this extension explicitly.
- Generic outcome selection must refer to type identities, not the spelling of a type parameter. Alpha-renaming `<A>` to `<Closed>` must not change whether a program is valid.
- Candidate escape syntax: `a.<A>` selects payload alternatives in resolved type `A`; `events.<Event>` selects both string and int64. Keep `heart.Tick` and `chat.string` as convenient unambiguous forms. This new punctuation is a proposal, not an approved or reader-tested spelling.
- For unions, define the selector as source provenance plus an ordinary type predicate. Transparent aliases then work without synthesizing an `Event` member. Preserve nominal subtype identity and ordinary first-matching-arm rules.
- Call-level `Timeout` and `Canceled` have no source. A payload `Timeout` does have a source. The blanket sentence excluding `Timeout` members contradicts the later `box.Timeout` example; distinguish provenance, not just type names.
- Retain v5's exclusion of transport-control payloads, or specify a separate payload/control discriminant. A payload `Closed` must not become indistinguishable from transport closure through union normalization.

- **Clashes and readability:**
- `chat.string` initially reads as a field. A type member is learnable, and completion showing “outcome type: string from chat” would help. This is a real discoverability cost, not a soundness objection to the spelling.
- Existing-wins plus a warning is insufficient. Adding a library field can silently broaden a user's pattern or remove a generic capability. The special multi-source error misses single-source uses and uses after widening.
- Keep ordinary member lookup outside source selection. Any ambiguous source-qualified pattern must error, regardless of source count. Offer an explicit selector such as `heart.<Tick>` that bypasses member lookup. Never require a client to rename a third-party field.
- Name collisions between two outcomes need the same escape, not deletion of both capabilities. Same short names from different modules and `Closed<X>` versus `Closed<Y>` must remain distinguishable by resolved types.

- **Compiler cost:**
- A winner index plus the outcome tag is enough for a flat selection. No allocation or runtime map is inherently needed. This is a credible runtime advantage over heap wrappers, though v5 records need not allocate either.
- “Ordinary lookup plus a clash check” understates checker work. Provenance through partials, optional waits, joins, nested merging, generic substitution, and path mutation needs explicit indexed state.
- Build outcome descriptors lazily per reached protocol instance, not per receiver value. Index prepared waits and source sets. Flat registration and descriptor construction should be linear in waits plus outcomes, apart from existing union normalization.
- Index exact source arms; do not compare every arm with every receiver. General grouped or overlapping patterns still pay their existing coverage cost. State the bound for that cost separately.
- Elide the winner tag only after proving no later use can observe provenance. A local binding or generic call can defer that use. Otherwise carry the tag conservatively.
- Gate the checker work with flagship instruction counts before landing. No measured compile-cost claim is supported by this paper round.

- **Comparison with the shortest correct alternatives:**
- Go attaches the operation directly to its case: `case v, ok := <-chat:`. Same payload types and aliases need no dependent types. Dewy's grouped plain-type arm is shorter when origin is irrelevant. [Go specification](https://go.dev/ref/spec#Select_statements).
- Tokio attaches a future and binding to each branch: `v = chat.recv() => ...`. Branch guards also avoid separate optional-wait locals. Dropping losing futures requires cancellation safety; that is not Dewy's non-canceling select contract. [Tokio](https://tokio.rs/tokio/tutorial/select).
- For 01–03, 05–07, 09–13, compare Go's case loops and Tokio's guarded branches with asyncio task maps plus `wait`, TypeScript tagged promise/channel adapters, and Swift tagged task-group or stream adapters. Dewy is especially concise for draining; its generic and field-path rules are currently less predictable.
- For 04, 08, 16b, compare timed send/receive or timer cases, Tokio timeout/send-timeout, asyncio timeout/wait-for, TypeScript abort-aware timer races, and Swift a scoped timer child. Include ownership recovery and stopping/joining work in every comparison.
- For 14b, 15b, 17a, 17b, compare Go result fan-in plus cancellation, Tokio racing futures, asyncio wait/as-completed plus cancellation and joining, TypeScript Promise.race/any plus explicit abort, and Swift task-group next plus cancelAll. Bare Promise.race is not a correct replacement for a canceling race. [ECMAScript](https://tc39.es/ecma262/multipage/control-abstraction-objects.html#sec-promise.race).
- asyncio `wait(FIRST_COMPLETED)` preserves pending tasks; cleanup and task-to-source association remain explicit. Swift task groups provide child lifetime and cancellation machinery. These are the relevant correctness baselines, not bare await counts. [asyncio](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait), [Swift structured concurrency](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0304-structured-concurrency.md).
- V5 is simpler for escaping results, arbitrary operations, generics, and collisions. The owner's version is shorter for the common local match. Neither is strictly better across those uses; retain the owner's common form with an explicit escape.
- Side by side, same two sources:
```dewy
# Improved owner's form.
match select(@heart.next @sweep.next) or_throw<Canceled> {
    <heart.Tick> => printl"beat"
    <sweep.Tick> => printl"sweep"
}
# V5: caller labels are ordinary fields and can survive returning the result.
match select([beat=@heart.next] [sweep=@sweep.next]) or_throw<Canceled> {
    [beat:Tick] => printl"beat"
    [sweep:Tick] => printl"sweep"
}
```

- **Grades:** tuples are obvious / discoverable / concise / safe / complete. Five means no missing capability or avoidable friction for this program's task. These grade the supplied programs under the supplied rules, not my repaired rules.
- **01 chat_command: 5/4/5/5/4.** `merged` plus `.open`/`.next` is less discoverable than Go/Tokio cases. Better Dewy: keep this form, but specify final-close retirement and the `open` proof in the r8 contract. Fixable documentation gap; the separate drain primitive is an inherent owner choice.
- **02 stdout_stderr: 4/3/4/4/3.** `.string` and four optional-wait locals/arms cost more reasoning than guarded Go/Tokio branches. Better Dewy: these same arms with guaranteed provenance through `out_wait`/`err_wait` and collision escape. Fixable; field-like reading remains a surface cost.
- **03 two_tickers: 5/4/5/4/4.** Excellent common spelling; generic identity and clash behavior still affect safety. Better Dewy: retain the sketch with binding-version provenance and hard ambiguity errors. Fixable.
- **04 selected_send: 4/3/4/2/3.** `offer` busy-polls forever on a full channel without a consumer. Better Dewy: poll once for the demonstration, then retry with blocking `worker.send(pending)`. Teach `.value` recovery explicitly. Fixable; explicit recovery has an inherent ownership cost.
- **05 ctrl_c: 4/4/5/5/4.** Clear scoped catcher. Listener escape/Closed behavior conflicts with v5, and the demo omits interrupted input. Better Dewy: state the borrowed listener rule and add a real interrupted-input case. Fixable; OS signal routing remains domain knowledge.
- **06 merge: 4/2/4/3/2.** `a.A` makes validity depend on generic parameter names and unresolved union substitution. Better Dewy: `item:a.<A>` under the proposed explicit-selector rule, including A=B and union instantiations. Fixable. `only_left` also handles and prints right values despite its name.
- **07 worker_pool: 4/3/5/4/4.** Stateless deadlines are improved. Past absolute deadlines, zero polling, and listed priority still need learning; listed priority can starve lower inputs by choice. Better Dewy: keep the decided rules and show an actual worker pool using 06's array fan-in. Discoverability cost is partly inherent; demo coverage is fixable.
- **08 single_timeout: 5/4/5/5/5.** Direct timed receive is the right form and exercises repeated polls. Better Dewy: show this first in timeout completion/help. Remaining discoverability is fixable.
- **09 drain_all: 5/4/5/5/4.** Good idle-versus-finished observation. Better Dewy: keep the bound handle and remove the false comment that same-typed closes cannot be distinguished. Teach qualified close arms as the manual alternative. Fixable.
- **10 backpressure: 4/3/4/3/3.** Different receiver closes now work. The permit arm needs its wait's nonempty-array fact; `print_all` uses an unsupported direct-receive qualifier. Better Dewy: specify fact transport and direct-call qualification, then retain this pump. Fixable. Same-receiver receive/reserve needs named-wait qualifiers.
- **11 library_types: 4/3/4/4/3.** Plain channel fields are a major improvement over wrappers. Nested mutable paths and delayed wait locals have no complete provenance rule. Better Dewy: capture field-path versions or bind named waits and qualify those. Fixable; fake launch does not test process I/O.
- **12 overlap_error: 4/3/4/4/3.** Same costs as 02; no overlap error is actually demonstrated. Better Dewy: retain `show`, add a deliberate broad-before-qualified negative example, and require its unreachable-arm diagnostic. Fixable.
- **13 union_payload: 4/3/4/2/2.** `any_close` leaves Canceled uncovered; direct receivers use members outside the allowed context. Better Dewy: `or_throw<Closed | Canceled>` and direct-call source refinements; offer `events.<Event>` for grouped payloads. Fixable; plain family forwarding remains a learnable type-directed feature.
- **14b mirrors_race: 5/4/5/5/5.** Correct race shape. `@load.(sources)...` combines partial application, elementwise mapping, and spread. Better Dewy: completion should expand its concrete callable-array type. Discoverability is fixable; the composition itself is concise.
- **15b fetch_or_cache_race: 4/3/5/4/3.** Cache qualification followed by residual plain string is reasonable, but arbitrary work cannot be similarly named. Better Dewy: bind `web = @load(url)` and allow `(@web).string`. Fixable; keep the bound receive and losing-receive guarantee.
- **16b work_timeout_within: 5/4/5/5/4.** Good primitive. The immediate mock cannot demonstrate cancellation or timeout; the lambda is unnecessary. Better Dewy: `within(30s @load(url))`, with a cancelable blocking mock for coverage. Fixable; cooperative join can exceed the deadline inherently.
- **17a first_ok_select: 3/3/3/3/2.** `fetch` forwards failures excluded by its annotation, creates results before merging, and claims merged retires on an error. Better Dewy: annotate Channel plus Canceled/Unsent, run actual producers concurrently, and say retirement happens on close. Or use 17b for the stated cancel-on-success task. Fixable comparator, not evidence against merged draining.
- **17b first_ok_race: 5/4/5/5/4.** Concise first-success primitive with an explicit all-failed choice. Better Dewy: show an actually delayed failing/succeeding pair; specify tie handling for equally early failures. Fixable coverage/spec detail; earliest failure is accepted here.
- **Floor: 2**, including recommended programs 06 and 13. This is not an all-5 round. The design gaps, invalid examples, and ordinary teaching costs should not be conflated.

- **Coverage and contradictions:**
- 01–03, 05, 07–09, 11–12, 14b–17b have exhaustive match shapes assuming valid qualifiers, the intended listener contract, and inherited operation signatures. This does not validate 17a's enclosing function annotation.
- 13 `any_close`: after `or_throw<Closed>`, the scrutinee is `string | int64 | Canceled`; string/int64 arms omit Canceled. Its enclosing `| Canceled` annotation does not forward it automatically inside a match.
- 10 `print_all` and 13 `take`/`wait_alarm` qualify direct receive results. The proposal only grants discrimination to select, merged.next, and race results. Add direct operations explicitly, or use plain `Job`, `string`, `int64`, and `Closed<T>` there.
- 15b's final `page:string` is not statically redundant: the declared load result includes string after `cache.string` is removed. It never runs in this mock because load always returns FetchError. `cache.Closed` also never runs because cache stays open.
- 05's first Closed arm cannot run in this setup: lines closes only later. The last Line arm runs only if Ctrl-C won the earlier select; it is not unconditionally dead. Ctrl-C arms require external input and can genuinely run.
- 04 `offer`'s retry arm is not exercised by main: its calls occur with room available. Main separately exercises Timeout and Closed recovery. Distinguish missing demo coverage from an unreachable type arm.
- 02 read_chunk's none branch is reachable at n=2. 03 sweep eventually fires under the stated fairness; its loop no longer exits before sweep by construction.
- 13 wait_alarm covers payload, poll timeout, and closed across its three calls. 09's comment about inseparable closes is stale. 17b's all-failed success arm is legal by its declared signature but never runs for those URLs.
- 17a merged sees FetchError as an item and continues that source until Closed. Early return stops consuming; it does not cancel unfinished producers. The owner decisions remain intact.
- v5 permits an escaped Ctrl-C listener and gives Closed after scope exit. R8 programs assume only CtrlC/Canceled and supply no replacement escape rule. Carry the borrowed-lifetime decision into the normative contract, not only earlier review prose.
- Qualified-before-plain overlap is legal and ordered. Plain-before-qualified is unreachable. Keep source provenance until coverage checking; normalizing `heart.Tick | sweep.Tick` to Tick too early would destroy both arms.

- **Dewy rules:**
- Formatting passes: all interpolation is ordinary `{value}`; no `{x:.2f}` and no environment variables appear. `fmt` is the required route if precision is added.
- Actual zero-argument void calls retain `()`; value reads such as receive, next, open, length, and now omit it. Partial handles such as `@heart.next` do not invoke the operation. No remaining `@job.wait` issue.
- 17a needs `fetch` to return `Channel<string | FetchError> | Canceled | Unsent<string | FetchError>` if it retains its sends. R8 does not supply that signature.

- **Earlier reviews' top issues, checked after independent grades:**
- R3 wrappers/minted sources: fixed for common concrete receivers; generic source qualification remains incomplete.
- R3 merged protocols/open/fairness: partly; programs use open correctly and array fan-in exists, but r8 needs the full inherited contract in one place.
- R3 syntactic spin check: partly; zero-timeout select backedges are covered, but 04's Unsent.reason Timeout retry still spins.
- R3 none waits/ownership: partly; reserve and const cap remove slot claims, but provenance must carry enabling facts into the selected arm.
- R3 remaining rule gaps: partly; deadlines and listener naming are fixed; covariance and listener escape need explicit standing rules.
- R4 deadline starvation: fixed as specified; listed starvation is the chosen priority policy.
- R4 selected-send ownership: fixed in the common path by send(timeout=), payload recovery, and reserve.
- R4 wait facts/slot claims: partly; claims disappear, but qualified outcomes still need the enabling fact rule.
- R4 initial open/array fan-in: fixed in the programs.
- R4 inconsistent single waits: fixed; direct qualified receives introduce a separate new specification gap.
- R6 stateful deadlines: fixed; no cross-call rotation state remains.
- R6 indistinguishable pump closes: fixed for different receivers; partly overall because two operations on one receiver still merge.
- R6 job.wait examples: fixed by removal.
- R6 direct-send Canceled/selected-send machinery: fixed in the declared r8 contract and programs.
- R6 unspecified surface: partly; string minting/ticker brands disappear, first failure and bound race work are stated, but member identity/generics/clashes replace those gaps.

- **Top five remaining issues, in order:**
- **1. Provenance is underspecified.** Define immutable wait keys, binding versions, aliases, delayed locals, nested merged provenance, direct calls, widening, and mutation invalidation. Use result refinements; keep the owner's sketch unchanged.
- **2. Generic names and collisions can remove or broaden a capability.** Add an explicit type selector; make ambiguous source patterns hard errors. Never require clients to rename library members or generic parameters.
- **3. Programs are not all valid or safe.** Fix 13's missing Canceled arm, 17a's annotation and retirement claim, direct-call qualifiers, and 04's unbounded poll retry. Preserve source enabling facts in 10.
- **4. Receiver-only qualification cannot express chosen finer granularity.** Extend outcome selection to stable named partials for two operations on one receiver and receiver-less race work. Preserve grouping by receiver as the default.
- **5. The checker-cost claim omits the new analysis.** Specify demand-driven indexed provenance and coverage, cache descriptors, and measure flagship instruction counts before approval to land. No runtime identity map is necessary.
