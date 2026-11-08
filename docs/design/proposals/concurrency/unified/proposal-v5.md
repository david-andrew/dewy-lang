# Parallel and concurrency surface, v5 — D4 response

- **BLUF:** keep the three approved parallel forms. Make a selected operation's identity an ordinary record field, make Ctrl-C interception and cancellation protection explicit callback scopes, and put construct settings before the construct. Keep cancellation in result types, with explicit checkpoints for compute and the approved `$explicit_cancellation` check for implicit forwarding.
- **Delivery:** design only; no repository changes, implementation, commits, or launches of example programs. Complete sources are in `programs/`; they target this proposal, rather than claiming support in today's compiler.
- **Owned:** this file and the companion programs under `~/dev/tmp/par5/`.
- **Acceptance:** answer all six review points; preserve the approved main example's shape; specify `select`'s actual polymorphic signature and protocol; exercise at least ten programs; give honest grades and remaining floors; supply replacement D4 text.
- **Non-goals:** implementing the compiler/runtime, redesigning channels or HTTP, changing the game API, performance pilots, editing other open items, or adding compatibility forms.
- **Budget:** one bounded design-and-paper-dogfood pass, including a consistency revision; no delegated work. Quota was checked before work; no agent launches were made.

## 1. What changed, and the source rules used

- Read D4, the entire v4 proposal, integration conventions and amendments, decisions (including batches 2–5), argparse/reflection, the relevant LANGUAGE sections, and GOALS.
- Searched `resources/discussion_points.md` with `/usr/bin/grep` for `with`, `scope`, `block`, `cancel`, `label`, `metatag`, and `$`.
- Relevant owner ideas:
  - `discussion_points.md:1193–1207`: lifetime-coupled resource cleanup, and concern that Python's `with` is verbose. That is a good fit for resource lifetime; signal interception has a separate, observable policy lifetime, so its exact extent deserves a visible callback scope.
  - `discussion_points.md:3375–3391`: `$` for tags/labels and `@` for handles. Use those roles rather than inventing an additional delimiter.
  - `LANGUAGE.md:4442`: `$rows` precedes its loop; a closure cannot break the caller's loop.
  - `LANGUAGE.md:5007`: settings currently cover the containing scope regardless of their position. Integration amendments also give a first-line-inside-`parallel` exception. V5 deliberately replaces that mixture with one prefix rule.
  - `LANGUAGE.md:646–692`: effect rows bound observable operation categories and preserve callback effects. V5 considers cancellation against that purpose, rather than treating today's inventory as a constraint.
- Decisions retained:
  - Three `parallel` forms; blocking strategy inferred; ordinary data dependencies order block items; task groups own task lifetimes.
  - `or_throw<E>` forwards **only** `E`; remaining alternatives stay in the expression. No cancellation exception is added to this operator.
  - `;` drops a value. A useful return from a write or spawn is bound or explicitly dropped.
  - Zero-argument calls with successful result `void` write `()` for their side effects, including `check_cancel()`, `close()`, `stop()`, and `Task.wait()`. Value-producing zero-argument calls omit them, including `now`, `receive`, `tick.next`, `load_config`, `length`, and `error`. Error alternatives do not change which successful-call convention applies.
  - `$explicit_cancellation` is approved and in `$bulletproof`; `BackgroundTasks` on `main` is approved for now; previously approved names are not resubmitted.
- Main corrections:
  - `select(command=...)` becomes `select([command=...])`; field construction and field matching are now visibly the same operation.
  - `catch_ctrl_c` changes from a handle-producing activation to a function which invokes a callback while interception is installed.
  - `protect_from_cancel` runs a supplied callback under a distinct, deadline-bearing cancellation scope. Passing `@save(value)` remains legal; writing the lambda makes the extent particularly visible.
  - `check_cancel()` stays a query/checkpoint with **no lasting activation**. Its caller's written `| Canceled` boundary and its explicit call show exactly where compute can end early.
  - No environment variable participates in settings. Both owner-suggested source entrypoint idioms are included.

## 2. `select`: one-field record arguments

### Alternatives considered

| Choice | Same-typed waits | Assessment |
|---|---|---|
| Positional tags, such as index 0/1 | Distinguishable by literal position | Reordering arguments changes the meaning of every arm; numbers hide domain intent. Reject. |
| Caller-supplied typed token beside each wait | Distinguishable by token type/value | Sound, but needs token declarations, wrapper names, or a new public adapter for this ordinary case. Reserve for an application-level abstraction. |
| A distinct nominal result wrapper per wait | Distinguishable nominally | Sound, but every pair of channels needs types unrelated to what the channels carry. Too much ceremony. |
| Match on the wait expression itself | Clear branch association | Becomes the removed `select { ... }` grammar, or needs matching on callable identity rather than values. Reject. |
| Arbitrary keyword arguments | Labels would be concise | An undeclared keyword pack is not the displayed positional signature, and option names occupy the same namespace. Reject. |
| **Ordinary one-field records passed positionally** | **Field names distinguish results** | **Choose.** No new grammar, no wrapper declarations, no option-name collision. |

- Example call: `select([command=@commands.receive] [message=@chat.receive] timeout=1s)`.
- `command` and `message` are **ordinary record field names**, supplied by the caller. They are not parameter names of `select` and not channel members.
- The input field contains an operation; the corresponding output field contains that operation's outcome.
- `select([timeout=@ch.receive] timeout=1s)` is legal: the record field and the call option are in different namespaces.
- One wait uses exactly the same form as several. Raw unlabelled waits are deliberately not a second convenience overload.

### Precise polymorphic signature

- The following is a **signature schema**, not an invented surface syntax for generic packs. `N`, `K_i`, `R_i`, and `D` are compile-time signature variables, not program identifiers. A compiler must print the instantiated Dewy signature.

```text
For N >= 1, distinct compile-time record keys K_0 ... K_(N-1),
and protocol outcome types R_0 ... R_(N-1):

select(
    ...waits : ([K_0: Waitable<R_0>], ... , [K_(N-1): Waitable<R_(N-1)>]),
    keyword-only timeout : D = none,
    keyword-only ties : 'fair' | 'first' = 'fair'
) -> [K_0: R_0] | ... | [K_(N-1): R_(N-1)] | Canceled | TimeoutPart(D)

D is a subtype of Duration | MonoPoint | Instant | none.
TimeoutPart(D) is never if D is only none; otherwise it is Timeout.
```

- `...waits` is a heterogeneous positional **pack**, not `array<Waitable<any>>` and not an arbitrary keyword pack. Each entry retains its field name, its own `R_i`, and source order.
- At an instance with an optional runtime timeout, include `Timeout` conservatively, even if that particular execution passes `none`.
- A non-`none` duration is validated as nonnegative; a past deadline is already ready. `ties=` determines the choice among ready operations, not the type.
- Two string receives with a timeout instantiate to:

```text
select(
  [command: Waitable<string | Closed>],
  [message: Waitable<string | Closed>],
  timeout: Duration,
  ties: 'fair' | 'first' = 'fair'
) -> [command: string | Closed] | [message: string | Closed] | Timeout | Canceled
```

- The result of `... or_throw<Canceled>` is exactly the two record alternatives plus `Timeout`. The `match` arms in program 01 cover those alternatives, splitting each field's `string | Closed` by pattern. No arm depends on two different `Channel<string>.receive` method types.
- Each selected record is a value even when its field contains `Closed` or `Unsent<T>`. `or_throw<Closed>` does not reach through a record to extract a field; matching stays explicit.
- Duplicate keys are errors naming both arguments. Multi-field or empty argument records are errors. Distinct keys establish disjoint result shapes even if all the `R_i` are identical.
- The typing rule is structural: given each `waits[i] : [K_i: Waitable<R_i>]`, form the union of the corresponding `[K_i:R_i]`, then add control outcomes. No pairwise payload-overlap solver is needed.
- Diagnostics teach the record: an unknown named wait argument such as `said=@lines.receive` errors with “write `[said=@lines.receive]`”. Match completion/hover offers each labelled `Closed` arm and top-level `Timeout` when applicable. `or_throw` never sees through those records.

### What `Waitable<R>` means

- `Waitable<R>` is the library's reservable-operation protocol. `R` is the outcome of committing the operation, **excluding cancellation of the selector itself**.
- A bound method handle retains both its callable interface and its reservation interface:

| Operation handle | Its protocol type | Calling it directly |
|---|---|---|
| `@ch.receive`, `ch:Channel<T>` | `Waitable<T | Closed>` | `T | Closed | Canceled` |
| `@ch.send(value)` | `Waitable<Sent | Unsent<T>>` | Existing `void | Unsent<T>`; its unsuccessful result retains the payload |
| `@tick.next` | `Waitable<ClockReading | Closed>` | `ClockReading | Closed | Canceled` |
| `@ctrl_c.next` | `Waitable<ClockReading | Closed>` | `ClockReading | Closed | Canceled` |

- `Sent` is the selected send's completion value. It makes an otherwise `void` success representable **inside the record**, and is not a replacement for direct send's successful `void`.
- The listener supplies a monotonic `ClockReading` for a press; no new event type is needed.
- `@ordinary_function` is not automatically waitable. Running competing functions is `race`, with its own cancellation/join contract.
- The protocol's reserve/commit/release methods coordinate through one selection token:
  - Reservation is tentative. Exactly one operation commits on an operation outcome.
  - `Timeout` or selector `Canceled` commits none.
  - A losing receive consumes nothing. A losing send delivers nothing.
  - Closing is an operation outcome: receive gives `[key=Closed]`; a closed send gives `[key=Unsent(...)]` retaining its payload.
  - A send already committed is never retroactively reported as selector cancellation.
  - A send's argument is evaluated once. A caller-owned payload moves only on a path that commits its send; a temporary belongs to the prepared operation and is destroyed if unused.
  - A canceled selector gives top-level `Canceled`, leaving caller-owned losing-send payloads available. Do not turn a selector cancellation into a labelled `Unsent` and accidentally hide it from `or_throw<Canceled>`.
  - A selection token cannot rendezvous with itself: a send and receive in the same `select` cannot make one another ready.
- Syntactically repeated identical operations can be diagnosed as redundant. Aliased handles must still be safe when not statically recognized; the token protocol, not a guessed alias proof, supplies correctness.
- Channel element types remain disjoint from `Closed` and `Canceled`, so **direct** receives are unambiguous. A channel of `Timeout` is fine inside a labelled wait: `[key:Timeout]` differs from top-level selector `Timeout`.
- Keep `timeout=` for durations/deadlines and `ties='fair'|'first'`. Fair selection must not perpetually prefer the first ready arm; `'first'` explicitly permits priority starvation. No promise of source order under `'fair'`.
- A relative timeout restarts at every call. Use a single saved deadline or a `ticker` for a period; none is inferred from a loop.

### General implementation requirements and cost

- Reuse heterogeneous pack traversal and compile-time record-field reflection/type construction from the reflection design. This is a library return-type computation, not knowledge of channel names in the checker.
- Compiler work at a reached instance is linear in pack size plus union canonicalization; keys use an indexed set. Cache the instantiated signature. No pass runs in programs that never use `select`.
- Runtime registration is O(N) with O(N) reservation storage, plus source-specific operations. Commit uses one shared winner token; losing registrations are released before returning.
- Deadlock certificates must model alternatives, so `$no_deadlocks` rejects an uncertified select rather than assuming the protocol proves the surrounding program live. Flagship instruction-count gates remain required before implementation lands.

## 3. Cancellation, Ctrl-C, checkpoints, and protected cleanup

### Choose result-typed cancellation

- **Choice: `Canceled` remains a result alternative. Do not move it to an effect row or add a second mandatory cancellation row.**
- This follows from the desired model, rather than the inventory of today's effects:
  - Cancellation is cooperative. It is observed at a named operation, and that operation may return without doing its work.
  - The caller needs the particular outcome, the same matching/defaulting/forwarding tools as other failures, and task-local control over where it is handled.
  - A written `:>T | Canceled` already states that the call can end without `T`; a written result lacking `Canceled` rejects an unhandled exit.
  - An effect-only model would either permit exits absent from the result (a second exception system), or re-encode the result's failure set in a row.
- An additional observation effect could distinguish “checks cancellation but handles it locally” from “never observes it.” That is a different, potentially useful guarantee. None of these programs needs it: placing checkpoints outside an invariant-sensitive update already gives the required control. Do not add a public effect spelling without such a use.
- A result contract without `Canceled` means **no unhandled cancellation result escapes**; it does not claim that the function never checks or handles cancellation internally. This is the precise limit, not a claim that results express every possible effect property.
- `& no blocks` is orthogonal: a nonblocking function can call `check_cancel()` and return `Canceled`. A blocking protected save can exclude **parent** cancellation while still returning file errors or `Timeout`.
- No asynchronous exception is injected at an arbitrary instruction. This keeps place invariants, ownership, and explicit forwarding coherent.

### How the three operations fit together

| Intent | Source form | Active extent | Type consequence |
|---|---|---|---|
| Observe a pending stop in compute | `check_cancel() or_throw` | This call only | The current function must allow `Canceled`, or explicitly handle it |
| Receive Ctrl-C as an event/input interruption | `task.catch_ctrl_c((ctrl_c) => { ... })` | Callback invocation and owned child work, until it has ended | Callback's actual result type is preserved; console operations have a stable `Interrupted` alternative |
| Complete a save despite the parent's pending stop | `task.protect_from_cancel(5s () => { ... })` | Callback and its owned child work, bounded cooperatively by a new deadline | Callback result plus `Timeout`; intrinsic callback failures remain |

- `catch_ctrl_c` and protection are ordinary library calls taking functions. There is no new block keyword or trailing-block grammar.
- The callback brackets are the visible policy lifetime. Assigning their eventual result to a variable neither starts nor extends the scope.
- For `catch_ctrl_c`, the exact result-polymorphic signature schema is `forall R: catch_ctrl_c(body: (L -> R)) -> R`, where `L` is the library-supplied listener type with the `.next` callable/protocol interfaces listed in section 2; it needs no new user-facing type name. Entry requires the foreground-task context. Its own setup adds no result alternative; callback failure alternatives are preserved, including `Canceled` and any `Interrupted` the callback forwards. Effects are inferred through the callback and the signal-routing implementation, rather than erased.
- Their callbacks are invoked once, synchronously on the calling task, and are not retained after return. Ordinary value/place capture rules apply; a callback does not silently gain write access to outer bindings.
- A callback `return` returns from the callback, not its caller. Handle the scope result outside it when the caller must return. A callback cannot break a loop outside it.
- All callbacks in these scope APIs, **including `tasks`**, are result-polymorphic, not implicitly void-typed. Preserve their values and errors; a callback whose own result is `void` stays void. A useful value must be bound, returned, or dropped with `;`. Frame callbacks keep their separate established contextual-void rule.

### Alternatives to callback scopes

- **Dedicated block form:** very readable, but duplicates function invocation and needs separate rules for values, early exits, and names. It earns no capability here.
- **Metatag before a block:** placement would be coherent, but catching a press changes which event happens, and protection changes which cancellation source is observed. These are runtime operations with results, not compile-time proof/settings tags. A tag which rewrites hidden throws would conflict with “a metatag never changes a type.”
- **Adapted `with`:** a general acquire/use/release abstraction may be useful elsewhere, but signal policy should not wait for a general context-manager protocol. A policy-owning block would still need a bound receiver and a result type, which the callback already provides.
- **Hold a listener / RAII activation:** concise, but aliasing a variable obscures how long interception lasts; exactly the owner's objection. Reject for this policy.
- **Library callback:** choose. It visibly groups the code, reuses ordinary functions and closure typing, and creates no exception to `return` or `break`.

### `check_cancel()` is not an activation

- Exact public operation: `check_cancel = ():>void | Canceled` (body is runtime/library supplied).
- It tests the **current task's** cancellation state. On success it does nothing. On a pending stop it gives `Canceled`; ignoring this possible failure is an error.
- It neither installs a catcher nor enables hidden checkpoints elsewhere, nor arms cancellation until a variable is dropped. Therefore turning it into a scope would obscure its actual role.
- Compute with no checkpoints and no cancelable operations runs to completion by default. To stop early, put explicit checkpoints at safe boundaries in the computation function. Program 05 stops a task; program 06 saves a best-so-far value after Ctrl-C.
- Within an update, place the checkpoint before acquiring/mutating an invariant, or after restoring it. No stop is injected between the checkpoint and the update.
- Compiler batching is permissible where it preserves the cooperative contract and cannot erase the only check in an unbounded loop. No source-level modulus/throttle is required. Long unchecked compute or foreign calls can still delay response; no invented millisecond latency guarantee.

### Ctrl-C default and catching

- Outside a catcher:
  - First Ctrl-C requests cancellation of the program's root scope and prints the stopping notice immediately.
  - Waits observe that request; opted-in compute observes it at a checkpoint. Cleanup runs and groups join.
  - A Ctrl-C-derived `Canceled` reaching `main` exits 130 without an ordinary error report.
  - The next Ctrl-C forces exit 130, reporting that cleanup was skipped.
- During `catch_ctrl_c`:
  - A press is routed to the active foreground catcher, **not** converted into a root cancellation request.
  - If the foreground console read is waiting, it receives `Interrupted` and consumes the press. The same press is not delivered a second time to `.next`.
  - Otherwise a press is available from `ctrl_c.next`, including `@ctrl_c.next` in `select`. Pending presses may coalesce, like ticker events; this is an event source, not an exact keypress log.
  - Three presses within one second force exit 130 even while caught or protected. This emergency override is not cancelable work.
  - A child process in the terminal's foreground process group still receives SIGINT directly; this API is not shell job control. A real shell also needs process groups and terminal handoff.
  - Existing parent cancellation requests are not cleared. Task.stop, sibling failure, deadlines, and other cancellation sources still work. Catching Ctrl-C is **not** general cancellation protection.
- Ownership:
  - Signal policy belongs to the program's foreground task. `catch_ctrl_c` requires that task, inferred through helpers just as callback constraints are inferred; invoking it from an ordinary spawned worker is a compile error naming the required foreground context.
  - Nested catch scopes on that task are allowed; only the innermost consumes a press. Exiting restores the previous route on every path.
  - This avoids two unrelated tasks racing to define the process's Ctrl-C policy. Child work owned by the callback may run, but the policy cannot remain installed after the callback returns; join it there or use a local `tasks` group.
  - The listener is a view of the scope. Retaining its handle cannot keep interception installed; after the scope ends its `.next` gives `Closed`.
- **Stable console types:** `input`, `input_int`, `input_float`, `read_line`, and stdin line iteration include `Interrupted` in their declared failure sets, regardless of where called. Outside interception the terminal Ctrl-C path chooses `Canceled`; inside it chooses `Interrupted`. Function types do not change based on an ambient metatag or dynamic call context.
  - This adds `Interrupted` to the corresponding console/input failure aliases.
  - `input(...) ??<Interrupted> continue ?? break` clears a line after a press, exits on ordinary end/input failure, and still forwards actual `Canceled`.
  - `catch_ctrl_c` does **not** subtract `Canceled` from a callback's result: a deadline or another task may still cancel it.
  - Visible type changes come from the written operations and handlers: naming `Interrupted` consumes that alternative; forwarding `Canceled` retains it at the containing function boundary.
- Do not add `.discard_pending` to the public proposal. A press delivered to a console read is consumed there; a queued press delivered through `.next` is consumed there. The old pending-clear name is withdrawn rather than sending an untested new member to D4.

### Protection has its own cancellation source

- Precise signature schema, with `R` the callback's entire result type and `F` its other effects:

```text
protect_from_cancel<R,F>(limit: positive Time quantity,
                         body: () -> R with effects F)
    -> R | Timeout with effects F plus timer/wait management
```

- Enter a new cancellation scope, run `body` exactly once even if the parent's cancellation was already requested, then restore the parent scope on all exits.
- Parent cancellation is masked for that scope and its owned children. It is not acknowledged or cleared on the parent.
- The required `limit` establishes the scope's own deadline. Cancellation due specifically to this deadline is translated to `Timeout`, using provenance, not a blanket substitution of every `Canceled` in `R`.
- Explicitly stopped child tasks and an intrinsic `Canceled` result can still be seen within this scope. A genuine `Canceled` returned by the callback stays `Canceled`.
- Normal callback errors remain errors. A write can still fail. Protection is not a transaction and guarantees no durability if writing fails or emergency exit occurs.
- On return, there is **no fabricated post-call cancellation throw**. A pending parent request is seen at the next cancellation point. This allows the caller to inspect a save's outcome and then explicitly return its original `Canceled`.
- **The bound is cooperative:** at expiry request stop and join owned work; if a callback computes without checks or waits in an uninterruptible foreign call, returning can take longer. Never claim a timeout can kill arbitrary code safely.
- A nested protection cannot extend an enclosing protection's deadline. It masks caller cancellation, not an already-established protection budget. Ordinary nesting takes the earlier protection deadline; an explicit protected defer replaces the default defer grace rather than being truncated to it.
- Default deferred cleanup retains the integrated 100 ms cancellation grace. `defer { protect_from_cancel(2s ...) ... }` gives that cleanup its explicit budget; it does not swallow errors by virtue of being deferred. Program 12 logs cleanup failures and leaves the original cancellation result intact.
- Save-on-Ctrl-C should normally use **default cancellation, then protection**, as program 06 does. Catching the signal is for shells, prompts, and explicit event-driven shutdown, not a prerequisite for a safe save.
- Teach the two deliberate endings after handling `search(@best) ??<Canceled> { ... }` side by side:
  - Protected save, then `return Canceled` **outside** the save callback: preserve interruption and exit 130.
  - Protected save, then fall out of the handler and finish `main` normally: deliberately accept the partial result and exit 0. Put normal-success-only saving in an `else`/separate return path to avoid a second save.
  - A `return Canceled` **inside** the save lambda returns from that lambda only. `protect_from_cancel(...) or_throw<Canceled>` explicitly forwards it; an `error` match arm must not swallow it as a broad `exception`.

### `$explicit_cancellation` remains exactly the approved check

- Default `??`, `?? void`, `?? return/break/continue`, a non-naming `??<E>`, and collectors forward `Canceled` instead of consuming it. Under the approved tag, that implicit forwarding is a compile error.
- `x or_throw<Canceled>` explicitly forwards only cancellation while retaining ordinary errors as data. It is the right annotation before `partition_failures` or a `select` match.
- `x or_throw<SomeOtherError>` does **not** forward cancellation; the remaining result still includes `Canceled`. A later collector must reject/forward it explicitly under the tag. This preserves the owner's orthogonality rule.
- `??<Canceled>` or a corresponding explicit `match` can deliberately handle it, with level-triggered state still pending unless a scope isolates it. A loop that continues under a canceled token can spin; consuming a value does not reset cancellation.
- The tag changes neither types nor runtime behavior. Prefix it to a function/block, or include it in a module's `$bulletproof` bundle. Do not ask D4 Q1 again.

## 4. Placement: settings prefix their target, language-wide

- **Recommendation: apply the prefix placement rule language-wide**, including later open items. Do not make concurrency a placement exception.
- A construct-affecting tag goes immediately **before** its target: declaration, loop/comprehension, expression block, or function. Several tags and a label form one prefix list; comments/blank lines do not split it.
- A tag on a function or plain block is inherited lexically by constructs written in that body. A tag on a loop or `parallel` governs that construct and its lexical descendants. An inner prefix can override it.
- It does not rewrite separately declared callees' lexical settings. Runtime resource restrictions on an executing parallel scope still constrain its child work; lexical compilation and runtime capacity are different things.
- `$memory.layout` remains a type-declaration setting. `$parallel.*` remains a parallel setting. A tag with an incompatible target, a duplicate setting on one target, or a `$parallel.*` setting with no governed parallel construct is an error naming the target.
- Existing declaration tags already point forward; `$parallel_safe` is deleted, so its old position is evidence for placement, not a tag to revive.
- **Exact header position:** one contiguous module-header metatag list may appear at file start (with no preceding imports), or immediately after the initial import section, and must precede the first non-import declaration or executable statement. Comments and blank lines do not split the list. Put imports needed by a header value before the header: `from units import MiB` makes `512MiB` available. Do not interleave imports into the header or add a second header later. Module-applicable tags in this initial header position annotate the implicit module; declaration-only tags still attach to the following declaration.
- After the first ordinary declaration/statement, tags prefix their explicit next construct; they cannot retroactively become module settings. A `$program.*` prefix directly before the entry `main` is also permitted, even after helper declarations: its value is resolved **when compiling**, never when calling `main`. A program tag on another ordinary function is an error. An imported file's own entry settings apply only when that file is the entry; explicit calls of another `main` retain the decided compile-time conflict rule.
- A standalone tag in the middle of a body attaches to the next construct. It no longer retroactively reconfigures the containing block. To cover a region, put it before `{ ... }`.
- Inside a comprehension, put the tag before `parallel`, inside the collector brackets. Program 04 uses that exact form. A construct prefix above `let results = [parallel ...]` errors with “move this inside the brackets, before `parallel`”; the tag is not a collected value. Hover shows the governed construct. A middle-of-file `$explicit_cancellation` prefix says “applies to `run` only; put it in the header to cover the module.”
- A value-producing decorated expression can be parenthesized/placed in a collector; the tag does not become a runtime expression or a parallel item.
- Keep the v4 setting value types: positive integers for limits/chunks, booleans for `.off`, core ID arrays for `.cores`, `'cpu'|'gpu'` for `.device`, `'aos'|'soa'` for `.layout`, and quantities for memory limits. “All settings are boolean” must be corrected in the guide when this design is implemented.
- `$parallel.off` retains deterministic source-priority cooperative scheduling: when the current item waits, another may run to resolve its wait. It is not a total-order promise for outside-world I/O. `$program.max_cores=1` is a resource cap and does not make scheduling deterministic.
- `max_concurrent` limits **immediate work items of each governed parallel construct**, not every descendant task in the program. As in v4, reject a cap which can strand items depending on each other. A finite download map is the common safe use.
- Caps count cores, not OS threads. `available_cores` reads the effective hardware/affinity allowance combined with program and active parallel core caps. It has no environment-variable component and cannot exceed hardware merely because a source cap is larger.

## 5. `main`, arguments, background tasks, and source profiles

### Entrypoint parameters compose by their types

- Automatic entry invocation may supply at most one parameter of canonical type `array<string>` and at most one of canonical type `BackgroundTasks`, in either source order, with arbitrary parameter names.
- Legal parameter sets: none; arguments only; background group only; both.
- The argument array contains the command's program arguments, excluding the executable/entry file. This is the existing argument-parsing meaning; it is not an argument descriptor or a task configuration object.
- The runtime-created background group is injected only at the selected file's automatic `main` invocation. There is no structural injection into arbitrary functions with those parameter types.
- Duplicate parameters of an injected type, an unsupported parameter type, or an ambiguous overload of entry `main` is a compile error. Aliases of an exact type are fine; merely accepting a supertype is not a new injection mechanism.
- The canonical example is `main = (argv:array<string> app:BackgroundTasks) => { ... }`; program 08 uses the ordinary `argparse` descriptor API, not a new CLI convention.
- `main` stays an ordinary function for explicit calls: the caller supplies every argument. Importing a module does not run its `main`; splat imports omit `main` as already decided.
- In game/UI programs the injected group lives through the final `update`/`draw`, after `main` returns, and stops/joins at program exit. An ordinary CLI's program lifetime ends when its main work finishes; keep a job needed for a final result alive by waiting on it explicitly.
- Group policies stay distinct:
  - `Tasks`: scoped, fail fast on a child failure; normal body completion joins its children. Stop persistent children explicitly before that join.
  - `BackgroundTasks`: program-owned; a child error prints once and remains on `.error`/`.wait`, without failing the group.
  - `.stop()` requests cancellation; **an owner stop and a self-stop are equally normal group shutdown**. A child ending `Canceled` because its owner/group/program is stopping neither fails the group nor prints a background-task error. Unrelated ordinary errors still follow the group's failure policy.
  - `.wait()` waits and gives `void | E | Canceled`; a task that ended canceled still reports `Canceled`, including after an owner stop. It also reports cancellation of the waiter. Group shutdown policy does not erase the handle's outcome. `.running` reports whether it ended; `.error` keeps its ordinary-error contract `E | none`; an expected stop is not an ordinary error. The canceled completion remains visible through `.wait()`.
  - When intentionally stopping one child, consume its wait's `Canceled` deliberately and still check the caller: `worker.wait() ??<Canceled> { check_cancel() or_throw }`. This avoids suppressing a simultaneous parent cancellation. The original program 05's unconditional `worker.wait() or_throw` predates this clarification and must use that handling when the example is updated.

### Where `tasks` comes from, and what it returns

- Teach the standard module as `task`: `task.tasks`, `task.catch_ctrl_c`, and `task.protect_from_cancel`. Examples currently spell the physical implementation import `import p"@lib/std/tasks.jo" as task`; `task` is the intended namespace, not a task-group instance. The implementation filename need not dictate a plural namespace.
- `tasks` is an exported **standard-library function**, not a keyword, injected local, callback parameter, or magical global group. By contrast, `BackgroundTasks` comes directly from `main`'s typed parameter and needs no task-module import.
- It creates a fresh group, invokes its callback once on the caller, then joins the children. **After a successful callback and successful join, return the callback's value, with its original value count and type.** Void stays void. No callback value is discarded by context.
- Precise signature schema: `forall R,E: task.tasks(body: (Tasks -> R)) -> R | E | Canceled`, where `R` is the callback's whole result and `E` is the union of ordinary failures of children spawned into this group. Effects and callback constraints are inferred as usual; retain the existing explicit-allocation-failure exception.
- A callback's early `return value` finishes **that callback**, then the group joins before publishing the value. It does not return from the surrounding function. An ordinary callback/child failure stops the other children, joins them, and returns the failure instead of any saved success value. Parent cancellation likewise joins before forwarding. `group.stop()` requests child shutdown but neither invents a callback value nor bypasses its remaining code.
- Child tasks still have the existing `void | E`/`never | E` contract; returning a value from the **group body** does not give spawned tasks an ignored return channel.
- Complete value-returning example, needing no shared outer result binding:

```dewy
import p"@lib/std/tasks.jo" as task

main = () => {
    let answer = task.tasks((group:Tasks) => {
        let job = group.spawn(() => printl"checking configuration")
        return 42
    }) or_throw
    printl"joined; answer {answer}"
}
```

### Per-environment settings are compile-time program settings

- **Withdraw the runtime startup-profile rule.** `$program.*` is fixed when compiling the selected entry file, not activated, sealed, or restored by calling an ordinary function. No startup-phase analysis or process-setting side effect is added.
- **Recommend separate entry files for different process caps.** Each imports its needed units/shared program, sets its header or prefixes its entry `main`, then calls an ordinary shared `run`. This is the owner's first idiom. Header values can use preceding imports.
- The owner's second idiom cannot choose different process caps from runtime `argv`: both branches belong to one compiled program, and an ordinary function call cannot retroactively change how it was configured. A target/build-mode selection known while compiling could choose one configuration, but tying laptop/server identity to debug/release would be an arbitrary deployment policy; this revision does not invent one or a new compile-time environment selector.
- One file may still have a function per environment for **ordinary application configuration**. Its fixed process cap stays on its header/entry `main`; passing a config record does not change that cap. Complete example:

```dewy
from units import MiB

Config:type = [workers:int]
run = (config:Config):>void => printl"{config.workers} requested workers; {available_cores} cores allowed"
laptop = ():>void => run(Config[2])
server = ():>void => run(Config[8])

$program.max_cores = 8
$program.max_memory = 512MiB
main = (argv:array<string> app:BackgroundTasks):>void => {
    let environment = argv.get(0) ?? "laptop"
    if environment =? "laptop" laptop()
    else if environment =? "server" server()
    else { printl("choose laptop or server" file=stderr); exit(2) }
}
```

- Both runtime choices here have the **same compiled caps**. `workers` is an application request, not a second program-setting mechanism. The shared program can use it for its own concurrency choices within the fixed cap.
- Complete separate-entry form using the existing companion shared program:

```dewy
# entry-small.dewy
from units import MiB
import p"09_environment_program.dewy" as program

$program.max_cores = 2
$program.max_memory = 512MiB
main = (argv:array<string> app:BackgroundTasks) => program.run(argv app)
```

- Here the tags are resolved before runtime and directly precede entry `main`; the imported shared program defines every application helper. For a module-wide header example, move that same contiguous tag list after imports and before **all** helper declarations; in the entry above both placements coincide.
- The original companion `10_environment_dispatch.dewy` is now a **rejected experiment**, not a valid v5 example. Its per-function program tags must not be taught. The corrected single-file form is the complete example above; companion files are not edited in this document-only follow-up.
- **Owner question Q7 below:** the second idiom is his proposal; ask explicitly whether to use separate entry files for process settings and ordinary config values for runtime dispatch. Do not quietly reinterpret his function as a runtime process setter.

## 6. Dogfood: complete sources, iterations, and honest grades

- **Original paper dogfood:** fourteen distinct application scenarios, sixteen source files. Shared-module and two-wrapper files are one scenario. These are first-pass artifacts: program 10 is withdrawn, and the updated value/stop/namespace rules in this document supersede the older sources. The supplied independent `dogfood.md` is a separate review; no post-fix independent scores are claimed.
- In the corrected document examples, explicit standard imports supply `task`, `net`, and `argparse`; the documented prelude supplies types, channels, clocks, I/O, and drawing names. Every application identifier is locally declared or explicitly imported. External dependencies are stated: downloader/CLI need an HTTP endpoint on loopback port 8080; the game needs a supported graphical target.
- Do not run these on the desktop to “validate the examples”: several features are design-only, and the game would open a window. No compiler success is claimed.
- Iterations in this pass:
  - Replaced ungrounded select keywords with one-field records; both successful strings and both `Closed` arms now follow mechanically from the signature.
  - Replaced listener assignment with an invocation-delimited catcher; no listener drop controls policy.
  - Kept actual cancellation in REPL results instead of claiming the catcher removes every `Canceled`.
  - Removed redundant `.discard_pending` by defining single consumption and coalescing.
  - Changed every successful-void zero-argument side-effect call to `()`; kept value calls bare.
  - Moved concurrency settings outside the governed construct/body; demonstrated comprehension placement explicitly.
  - Made the CLI's progress loop's `or_throw` apply to the loop, and its success-only reporter wait an explicit `.wait()`. The CLI deliberately defaults reporter errors with `?? void` and then inspects `.error`; actual cancellation still forwards.
  - Made the compute publication a fixed-width atomic and kept best-so-far state observable after joining.
  - Added cooperative deadline caveats and preserved the original cancel after a failed cleanup; a protected save is no longer presented as guaranteed success.
  - The first pass proposed a startup-phase rule; the independent dogfood rejected that second meaning of prefix tags. The follow-up below withdraws it and keeps process settings fixed when compiling.

### Grading method

- Each vector is **O D C S X K**: obvious, discoverable, concise, safe by default, complete, consistent; each 1–5. A 5 means no identified surface repair in this scenario, not measured superiority or verified implementation.
- Scores are this pass's design judgments from writing the Dewy programs and mapping the same requirements to the comparison idioms. They are **not** user studies, independent cold reads, benchmarks, or claims of executed equivalent implementations.
- Comparison basis uses competent idioms, not deliberately bad examples:
  - Python: task groups/timeouts and explicit cancellation handling. [Official asyncio task documentation](https://docs.python.org/3/library/asyncio-task.html).
  - Go: channels/select, context propagation and explicit lifecycle joins. [Official context design](https://go.dev/blog/context).
  - Rust: scoped threads for synchronous work and Tokio's select for async channels; account for cancellation safety rather than comparing only the standard library. [Scoped threads](https://doc.rust-lang.org/std/thread/fn.scope.html), [Tokio select](https://docs.rs/tokio/latest/tokio/macro.select.html).
  - TypeScript: promises plus platform abort signals and explicit worker/lifecycle code where needed. [TypeScript promise-related types](https://www.typescriptlang.org/docs/handbook/utility-types#awaitedtype), [DOM abort API specification](https://dom.spec.whatwg.org/#aborting-ongoing-activities).
  - Swift: structured task groups and cooperative cancellation. [Official concurrency guide](https://docs.swift.org/swift-book/LanguageGuide/Concurrency.html).
- These documents ground the comparison mechanisms; the numeric judgments below are my inference. Framework choice can improve a comparison score, especially for games, CLI parsing, and shutdown cleanup.

| Scenario / file | Dewy | Python | Go | Rust | TypeScript | Swift |
|---|---|---|---|---|---|---|
| 01 dependency-loading showcase | 5 4 5 5 5 4 | 4 4 4 4 5 4 | 4 4 3 4 5 4 | 3 4 3 5 5 4 | 4 4 4 4 5 4 | 4 4 4 5 5 4 |
| 02 REPL / caught Ctrl-C | 5 4 5 5 5 5 | 4 4 4 4 5 4 | 4 4 3 4 5 4 | 3 3 3 5 5 4 | 4 4 4 4 5 4 | 4 3 3 5 5 4 |
| 03 server / same-typed channels | 5 5 5 5 5 5 | 4 4 3 4 5 4 | 5 5 5 4 5 5 | 5 4 4 5 5 5 | 4 4 3 4 5 4 | 4 4 3 5 5 4 |
| 04 downloader / timeout / four in flight | 5 4 5 5 4 5 | 4 4 4 4 5 4 | 4 4 4 4 5 4 | 4 4 4 5 5 4 | 4 4 4 4 5 4 | 4 4 4 5 5 5 |
| 05 stop compute / retain best | 5 5 5 5 5 5 | 4 4 3 4 5 4 | 5 5 4 4 5 5 | 4 4 4 5 5 5 | 4 4 3 4 5 4 | 5 5 5 5 5 5 |
| 06 save on Ctrl-C | 5 4 5 5 5 5 | 4 4 3 4 5 4 | 4 4 4 4 5 4 | 4 4 3 5 5 4 | 4 4 3 4 5 4 | 4 4 4 5 5 4 |
| 07 game / background news | 5 4 5 5 5 5 | 4 4 4 4 5 4 | 4 4 4 4 5 4 | 4 4 4 5 5 4 | 5 5 4 4 5 5 | 5 5 5 5 5 5 |
| 08 CLI / arguments + program tasks | 5 5 5 5 5 5 | 5 5 4 4 5 5 | 5 5 4 4 5 5 | 5 5 4 5 5 5 | 5 5 4 4 5 5 | 5 5 4 5 5 5 |
| 09 separate environment entrypoints | 5 5 5 5 5 5 | 5 5 5 4 5 5 | 4 4 4 4 5 5 | 4 4 4 5 5 5 | 5 5 5 4 5 5 | 4 4 4 5 5 5 |
| 10 one entrypoint / source profiles | 4 4 4 5 5 4 | 5 5 5 4 5 5 | 5 5 5 4 5 5 | 5 4 4 5 5 5 | 5 5 5 4 5 5 | 5 4 4 5 5 5 |
| 11 retain failed sensor readings | 5 5 5 5 5 5 | 5 5 4 4 5 5 | 5 5 4 4 5 5 | 5 5 5 5 5 5 | 5 5 5 4 5 5 | 5 5 5 5 5 5 |
| 12 protected deferred cleanup | 5 4 5 5 5 5 | 4 4 3 4 5 4 | 5 4 4 4 5 5 | 4 4 3 5 5 4 | 4 4 4 4 5 4 | 4 4 4 5 5 4 |
| 13 Ctrl-C selected as an event | 5 4 5 5 5 5 | 4 4 3 4 5 4 | 5 5 5 4 5 5 | 5 4 4 5 5 5 | 4 4 4 4 5 4 | 4 4 4 5 5 4 |
| 14 selected send / no lost payload | 5 4 5 5 5 5 | 4 4 3 4 5 4 | 5 5 5 4 5 5 | 4 4 4 5 5 4 | 4 4 3 4 5 4 | 4 4 4 5 5 4 |

### Floors after iteration

- **01 D=4, K=4:** block bindings escaping the braces are inherited from v4 and remain unusual. Fixing that would change the approved example's shape and the parallel block design beyond this review. Keep the flag; do not report a perfect consistency score.
- **02/06/12/13 D=4:** readers must learn the foreground signal route and the difference between a shield and a signal catcher. The visible scopes and one-operation table reduce that burden; terminal signal behavior still needs documentation.
- **04 D=4, X=4:** the source is a complete raw HTTP response downloader, but a production downloader also needs a higher-level HTTP client for redirects, status validation, HTTPS, and streaming policies. That library is outside D4, not a missing concurrency mechanism. The `.http` output names avoid pretending the captured header+body bytes are decoded assets.
- **07 D=4:** `main` ending while frame hooks and its group continue is the game program-lifetime convention. The injected type explains ownership, but the hook lifetime must be taught.
- **10: withdrawn after independent dogfood.** The original table records the first pass's scores, not a validation of its runtime profile semantics. Separate entry files are recommended for process caps; the new complete example dispatches only ordinary config values. No fresh scores are claimed for that replacement.
- **14 D=4:** conditional ownership of a selected send is sound but advanced. An IDE must show ownership by match arm. For copyable strings in the complete program the concern is invisible; the same protocol must work with a move-only payload.
- No remaining floor is disguised as “ready: all 5.” Independent dogfood is recorded in `dogfood.md`; its must-fix items are addressed here, without claiming the revision was independently rechecked. The earlier grade table and companion programs predate these fixes.

## 7. Names and cold-read meanings

- **No newly coined tag or member names are needed.** The following inventory includes changed calling shapes, the removed name, and the already-existing names whose precise meaning matters. No fresh-reader test was run in this pass; do not describe changed calling shapes as independently cold-read. Prior naming evidence in the integrated proposals is not evidence that readers have seen v5.

| Name / form | Cold-read meaning intended | Status |
|---|---|---|
| `select([key=wait] ...)` | Wait on these labelled operations; return the winning label with its outcome | Changed call shape, existing record syntax |
| `Waitable<R>` | An operation that can reserve and commit a selectable outcome of type R | Existing integrated name; R is now explicit |
| `command`, `message`, `interrupt`, `write` | Application-chosen record keys identifying waits | Example fields, not new library API or reserved words |
| `catch_ctrl_c(callback)` | Run this callback while Ctrl-C is caught as events/input interruptions | Existing pending name, changed from handle factory |
| `ctrl_c` | The callback parameter through which this scope receives Ctrl-C events | Local example identifier, not a public type name |
| `ctrl_c.next` | Wait for the next caught press; return its clock reading | Existing source verb, exact event result specified |
| `Interrupted` | This console read was interrupted, rather than the task being canceled | Existing proposed failure; stable console signature clarified |
| `check_cancel()` | Check whether this task was asked to stop; return Canceled if so | Existing name; successful-void call convention applied |
| `protect_from_cancel(limit body)` | Run this body protected from the parent's cancel, within a cooperative budget | Existing name; explicit scope and provenance specified |
| `Canceled` | This operation did not complete because cancellation was observed | Retained result, no new row spelling |
| `$explicit_cancellation` | Require implicit cancellation forwarding to be written explicitly | Approved; included in `$bulletproof` |
| `task` | The standard namespace for scoped task, Ctrl-C and protection calls | Singular namespace recommended by independent dogfood; physical implementation import shown explicitly |
| `tasks(body)` | Run a body with its own task group, join, then return its value | Existing name; value preservation corrected after dogfood |
| `Tasks` | A scoped fail-fast task group | Existing public type |
| `BackgroundTasks` | The program-owned group whose lifetime includes frame hooks | Approved for now; composes with CLI arguments |
| `Task<E>` | One owned task whose ordinary failures are E | Expected stops do not fail its group; `.wait()` still exposes cancellation; `.error` keeps its ordinary-error contract |
| `discard_pending` | Former proposed member for forgetting queued presses | **Withdrawn**, not proposed for approval |
| `DEWY_MAX_CORES` | Former environment override of core limits | **Removed** by owner's instruction; no replacement variable |
| `$parallel.max_concurrent`, `.chunk_size`, `.max_cores`, `.off`, `.scheduler` | Parallel admission, granularity, core cap, replay schedule, expert scheduler | Retained; prefix placement and exact targets clarified |
| `$placement.device`, `.cores` | Where governed work runs | Retained; prefix placement |
| `$memory.layout` | Physical layout of the following type | Retained declaration tag |
| `$program.max_cores`, `.max_memory`, `.max_tasks` | Process limits fixed when compiling the entry file | Retained; ordinary-function startup-profile target withdrawn |
| `available_cores` | Effective current core allowance | Approved; environment input removed |
| `timeout=`, `ties=`, `Sent`, `ticker`, `.next`, `partition_failures`, `sum`, `iterable<T>`, `ch.drain`, `sleep(until=t)` | The already-approved timeout, fairness, completion, event, result-partitioning, reduction, iteration, nonwaiting drain and deadline operations | Retained without new questions |

- Naming gate: any later renaming of a tag/member must undergo the standing three-reader cold test before it is inserted into the repository's open questions. This pass avoids introducing any such spelling and makes no invented claim that the gate ran.

## 8. Replacement text for `open_decisions.md` D4

<!-- BEGIN REPLACEMENT D4 -->
### D4. One unified `parallel` surface: v5

- **BLUF:** three forms cover data-dependent steps, parallel iteration, and owned background work. `select` labels each wait with an ordinary one-field record, so same-typed channels are unambiguous. Ctrl-C catching and cleanup protection have visible callback scopes; compute stops only at explicit checkpoints or cancelable operations. Settings go before their target.
- **Status:** first-pass paper dogfood covered fourteen scenarios; independent dogfood in `~/dev/tmp/par5/dogfood.md` found must-fix issues, now corrected in this text. Your approved names, `$explicit_cancellation` and `main`'s `BackgroundTasks` parameter stay. The remaining surface questions are below; no repeated Q1 or Q3. Full design and complete sources: `~/dev/tmp/par5/parallel-v5.md`, `~/dev/tmp/par5/programs/`.

```dewy
# v5 design program; standard concurrency API is explicit at its use.
import p"@lib/std/tasks.jo" as task

Config:type = [root:string]
Invalid:type = type of error
load_config = () => {
    sleep(20ms) or_throw
    Config["assets"]
}
load_map = (c:Config) => {
    sleep(50ms) or_throw
    "{c.root}/map"
}
load_sounds = () => {
    sleep(30ms) or_throw
    "sounds"
}
parse_age = (text:string):>int | Invalid => to_int(text) ?? Invalid
score = (n:int):>int => (n * n) % 7
autosave = () => loop true {
    sleep(30s) or_throw
    printl"saved"
}
relay = (commands:Channel<string> chat:Channel<string>) => loop true {
    match select([command=@commands.receive] [message=@chat.receive] timeout=1s) or_throw<Canceled> {
        [command: string] => printl"command: {command}"
        [message: string] => printl"chat: {message}"
        [command: Closed] => return "commands closed"
        [message: Closed] => return "chat closed"
        <Timeout> => printl"idle"
    }
}
main = () => {
    parallel {
        let config = load_config or_throw
        let map = load_map(config) or_throw
        let sounds = load_sounds or_throw
    }
    let ages = [parallel t in ["31" "abc" "45"] parse_age(t) ?? void]
    let rounds = input_int("rounds? ") ?? 10
    let total = sum([parallel i in [0..rounds * 100_000) {
        check_cancel() or_throw
        score(i)
    }])
    let commands = channel<string>(4)
    let chat = channel<string>(4)
    parallel {
        {
            chat.send("hi") or_throw
            chat.close()
        }
        {
            commands.send("quit") or_throw
            commands.close()
        }
        let why = relay(commands chat) or_throw
    }
    task.tasks((group:Tasks) => {
        let saver = group.spawn(@autosave)
        let tick = ticker(500ms)
        defer tick.stop()
        loop i in [0..4) tick.next or_throw;
        saver.stop()
    }) or_throw
    printl"{map} {sounds} {ages} {total} {why}"
}
```

- **The common path:**
  - Write steps in order in `parallel { ... }`; independent steps can run together. Ordinary successful values match source order given the same handle results.
  - `[parallel x in xs f(x)]` maps; `?? void` filters ordinary failures, and `.partition_failures` retains successes and failures.
  - `select([command=@commands.receive] [message=@chat.receive] timeout=1s)` gives `[command:string|Closed] | [message:string|Closed] | Timeout | Canceled`. `or_throw<Canceled>` removes only the final alternative by forwarding it. Ordinary record field patterns distinguish the waits, including their `Closed` outcomes.
  - `task.tasks` is a function imported from the standard task module, not a language keyword or hidden local. It passes a fresh `Tasks` group to the callback, joins, then returns the callback's value. Void callbacks stay void; a useful group result needs a binding or `;`.
- **How to adjust:**
  - Link a step to an earlier result, group ordered statements in `{ ... }`, or put work after the parallel block to order it.
  - Prefix a loop/comprehension with `$parallel.max_concurrent=4` to cap work in flight. A collector spells the prefix inside its `[...]`, before `parallel`.
  - Prefix a block/function with `$parallel.off` for source-priority cooperative replay. One core is a separate resource policy.
  - Put `check_cancel() or_throw` at a safe point in compute. The function's result includes `Canceled`; no guard variable activates anything.
  - `task.protect_from_cancel(5s () => save(value))` lets a save run despite the parent's pending cancel. Its own deadline is cooperative, and the result still reports save errors or `Timeout`.
  - Put a prompt loop inside `task.catch_ctrl_c((ctrl_c) => { ... })` to take Ctrl-C as an event or `Interrupted` input result. The scope ends with the call, regardless of aliases to its listener.

- **A prompt with its own Ctrl-C behavior:** all application names below are declared; `input`, `Interrupted`, and the clock/printing types are standard-library/prelude names.

```dewy
# Ctrl-C during input clears the line; EOF/quit leaves the visible scope.
import p"@lib/std/tasks.jo" as task

repl = () => task.catch_ctrl_c((ctrl_c) => {
    loop true {
        let line = input("> ") ??<Interrupted> { printl(""); continue } ?? break
        if line =? "quit" break
        printl"you said {line}"
    }
})
main = () => {
    repl() or_throw
    # The catcher has ended even though ctrl_c was never dropped explicitly.
    printl"normal Ctrl-C behavior restored"
    sleep(100ms) or_throw
}
```

- **Save on Ctrl-C:** normal cancellation stops the search; a protected save handles its own errors and then preserves the original `Canceled` (exit 130).

```dewy
# Ctrl-C requests ordinary cancellation. Save, then preserve exit status 130.
import p"@lib/std/tasks.jo" as task

search = (@best:int):>void | Canceled => {
    loop n in [0..1_000_000_000) {
        check_cancel() or_throw
        if n % 7919 =? 0 best = n
    }
}
save = (best:int) => p"best.txt".write_text("{best}\n")
main = () => {
    let best:int = 0
    search(@best) ??<Canceled> {
        match task.protect_from_cancel(5s () => save(best)) or_throw<Canceled> {
            saved:Path => printl"saved to {saved}"
            <Timeout> => printl("save deadline expired" file=stderr)
            problem:error => printl("save failed: {problem}" file=stderr)
        }
        return Canceled
    }
    save(best) or_throw;
}
```

- **Arguments and program-lifetime tasks compose:** both parameter types are supplied at entry, in either order; an ordinary explicit call supplies both normally. `argparse` keeps its descriptor design. This complete CLI includes its HTTP helper; it saves full HTTP responses from localhost:8080.

```dewy
# Example command: dewy 08_cli_arguments_and_tasks.dewy /index.html count=3
import argparse
import p"@lib/std/tasks.jo" as task
import net

fetch = (resource:string output:Path) => {
    let stream = net.tcp_connect("127.0.0.1" 8080) or_throw
    defer net.tcp_close(stream)
    net.tcp_send(stream "GET {resource} HTTP/1.0\r\nHost: localhost\r\n\r\n") or_throw
    let response:array<uint8> = []
    loop true {
        let received = net.tcp_receive(stream)
        if received is? none break
        let bytes = received or_throw
        response.extend(bytes)
    }
    output.write_bytes(response) or_throw
}

const Args = [
    resource = argparse.Positional<string>(help="HTTP resource at localhost:8080")
    count = argparse.Named<int<1 <=? value <=? 100>>(default=1 help="number of captures")
]
progress = (completed:Channel<Path>) => {
    loop output in completed { printl"completed {output}" } or_throw
}
main = (argv:array<string> app:BackgroundTasks) => {
    let args = argparse.parse(Args argv about="capture HTTP responses")
    let completed = channel<Path>(4)
    let reporter = app.spawn(@progress(completed))
    defer completed.close()
    loop i in [0..args.count) {
        let output = within(5s @fetch(args.resource p"capture-{i}.http")) or_throw
        completed.send(output) or_throw
    }
    completed.close()
    reporter.wait() ?? void
    if reporter.error is? error printl"reporter failed: {reporter.error}"
}
```

- **Source-defined environments:**
  - Separate entry files import units/shared code first, then set a contiguous module header before declarations or prefix their entry `main`. Caps are fixed when compiling, with no environment-variable override.
  - One entry file may dispatch ordinary functions with ordinary application config values. It cannot choose different compiled process caps from runtime arguments. The first pass's program 10 is withdrawn. Q7 asks how to reconcile your second idiom; these are the corrected separate-entry and single-file application-config forms.

```dewy
# entry-small.dewy
from units import MiB
import p"09_environment_program.dewy" as program

$program.max_cores = 2
$program.max_memory = 512MiB
main = (argv:array<string> app:BackgroundTasks) => program.run(argv app)
```

```dewy
from units import MiB

Config:type = [workers:int]
run = (config:Config):>void => printl"{config.workers} requested workers; {available_cores} cores allowed"
laptop = ():>void => run(Config[2])
server = ():>void => run(Config[8])

$program.max_cores = 8
$program.max_memory = 512MiB
main = (argv:array<string> app:BackgroundTasks):>void => {
    let environment = argv.get(0) ?? "laptop"
    if environment =? "laptop" laptop()
    else if environment =? "server" server()
    else { printl("choose laptop or server" file=stderr); exit(2) }
}
```

- **Semantics taken:**
  - **Block ordering:** conflict/data edges wait for successful predecessors; on failure, pending work never starts, running work is canceled/joined, and no writes are rolled back. Handle outcomes depend on timing. Channel wait cycles and racing sends/closes retain the v4 checks.
  - **Writes:** block items may write outer variables under the dependency graph; loop items may write only their own partition; spawned tasks cannot write outer variables. Helpers preserve these rules.
  - **Scope results:** block items' values remain source-ordered; top-level block `let`s remain visible after the block; `( ... )` is one ordered item. The unusual binding scope stays flagged.
  - **Select diagnostics:** unknown named waits teach `[key=@operation]`; hover offers both labelled `Closed` arms plus `Timeout` where applicable. A misplaced comprehension tag above `let` says “move this inside the brackets, before `parallel`”.
  - **Group-body result:** `task.tasks(body)` preserves the body's value after joining, just like the other callback scopes; early `return` is local to the callback. Child failure/parent cancellation joins before returning a failure instead. No contextual-void suppression of useful group values.
  - **Select protocol:** positional arguments are distinct-key one-field records of `Waitable<R_i>`; return their corresponding `[key:R_i]` union plus top-level cancellation and applicable timeout. Losing receives consume nothing; losing sends retain their caller-owned payload. Match labels never come from arbitrary call keywords.
  - **Cancellation is result-typed:** `Canceled` remains visible in results and ordinary error handling. No second, hidden exception mechanism or cancellation row is needed for these programs. A result excluding `Canceled` forbids an unhandled cancel, without claiming the function never checks it locally.
  - **Explicit cancellation:** `$explicit_cancellation` is approved and included in `$bulletproof`. It rejects implicit forwarding through `??` and collectors. `or_throw<Canceled>` writes the forwarding; `or_throw<E>` with some other E leaves cancellation in the value.
  - **Ctrl-C scopes:** default Ctrl-C requests root cancellation; an unhandled Ctrl-C-derived cancel exits 130. Catching redirects presses only for the callback's lifetime, without masking other stop sources. Console signatures always include `Interrupted`; scope context does not rewrite their types. Three rapid presses force exit even while caught. Child-process signal/job-control behavior is unchanged.
  - **Protection:** run the body in a new scope despite a pending parent cancel, apply its own cooperative deadline, then restore the parent without clearing its request. A callback's intrinsic errors remain. Save failures must be reported; protection is not guaranteed persistence.
  - **Task policies:** a scoped group fails fast; `BackgroundTasks` reports a child error without ending the program. An owner/self/group stop is normal group shutdown: a canceled child does not fail the group or print a task error. `Task<E>.wait()` still gives `void|E|Canceled`; `.error` retains `E|none` for ordinary errors. Consume an expected child cancellation explicitly while still checking the caller for a concurrent stop. Event sources use `.next`.
  - **Frame code:** use nonwaiting `ch.drain` and background jobs; channel/task/timer waits remain errors in `update`/`draw`. The injected group survives `main` until the window closes.
  - **Entrypoint arguments:** accept at most one `array<string>` and one `BackgroundTasks`, by exact type rather than parameter name; no extra injections into ordinary helpers. Only the selected file's entry `main` runs automatically.
  - **Limits:** settings are in source, caps count cores, and `available_cores` combines hardware/affinity and source limits. No environment-variable cap. Program task admission retains the decided explicit-allocation-failure policy.
- **Surface questions for you:**
  - **Q4 (c): keep `catch_ctrl_c`, now taking a callback rather than returning an activating guard?** The callback's extent is the catching extent; its `ctrl_c` parameter receives presses. It unblocks shells and prompt loops without a policy-changing assignment. **Rec:** yes. Reversible library call-shape choice. The spelling was previously cold-read; its new invocation shape has been paper dogfooded, not independently retested. No new tag/member spelling is introduced.
  - **Q6 (a, b): make construct settings prefix their target language-wide?** Tags and labels sit before loops, blocks, and declarations. One contiguous module header may be at file start or after the initial imports, before the first ordinary declaration/statement; imported units are in scope. Later prefixes apply only to their next construct. Program settings may also directly prefix entry `main`, and are fixed at compile time. This replaces both current containing-scope placement and the first-line-inside-parallel exception. It unblocks consistent examples in every design item. **Rec:** yes. Reversible before the surface ships; broader than concurrency, and explicitly changes the prior placement direction.
  - **Q7 (a, b): use separate entry files when environments need different process caps, and ordinary config records when one entrypoint chooses at runtime?** Your second idiom cannot select compiled `$program.*` settings from runtime `argv`; putting them on ordinary functions would give a prefix tag a second, process-changing meaning. A one-file process configuration would need an environment already known when compiling, selected through an agreed target/build-mode/compile-time source value; no such environment selector is invented here. **Rec:** separate entry files for process settings; keep one-file functions for application config under one fixed process cap (complete examples above). This preserves compile-time settings and ordinary function-call semantics. It unblocks environment packaging; reversible source organization. Your proposed second idiom remains an explicit owner choice, not silently implemented as runtime configuration.
- **Flagged, not new questions:**
  - `check_cancel()` is an explicit checkpoint, not an ambient opt-in; it has no active lifetime to bracket. It lives inside an ordinary computation function whose result carries `Canceled`.
  - `protect_from_cancel` and `within` are cooperative: nonchecking compute or an uninterruptible foreign call can exceed the requested duration while being joined.
  - A foreground-task restriction keeps two unrelated background tasks from racing to own process signal policy; nested catchers restore the prior owner.
  - The standard console failure sets gain `Interrupted` uniformly. No metatag changes their type.
  - `$parallel.*` settings that govern nothing are errors. Declaration settings retain target checks.
- **Floors:** block-local bindings escaping braces remain unusual; different compiled process caps need separate entry files (Q7); full HTTP and real shell job control are library work. Several discoverability scores remain 4. There are no claims of compiler validation or fresh-reader scores.
- **Ready:** design review and syntax/name answers; not implementation landing. Approved Q1, Q3 and approved names are omitted from the questions.
<!-- END REPLACEMENT D4 -->

## Changes after dogfood

- `tasks` now preserves its callback's value after joining; explicit callback `return` stays local. Added a complete value-returning example and removed the contextual-void exception for this API.
- Withdrew runtime startup profiles and ordinary-function `$program.*` prefixes. Process settings stay compile-time; section 5 supplies honest separate-entry and runtime-config examples, and D4 Q7 explicitly asks the owner to choose the boundary.
- Headers may follow initial imports and must precede ordinary declarations/statements; one contiguous header, with imported units in scope. Entry-`main` program prefixes remain compile-time settings.
- Teach the singular `task` namespace, record-wait diagnostics, and expected-stop behavior: no group failure/no printed task error, but cancellation stays visible on task handles. These clarifications also appear in D4.
- Removed unnecessary lambda parentheses. The save example forwards callback cancellation before matching ordinary errors. The two deliberate endings are taught in section 3; no companion source files were silently regraded or changed.

## 9. Handoff and limits

- Repository changes required **after approval**, not performed here:
  - Integrate the selected record-wait signature and examples into the parallel proposal and D4.
  - Update the integrated conventions/amendments for callback scopes, stable `Interrupted` types, no environment-variable cap, and successful-void call spelling.
  - Apply prefix placement consistently in LANGUAGE and other design items if Q6 is accepted.
  - Record Q7's answer about separate entry files versus a future compile-time environment selector. No runtime profile extension is proposed.
- This follow-up used the supplied independent dogfood without launching another review; no fresh-reader results or new grade claims are invented.
- No changes are proposed to the already-approved vocabulary. No attribution/trailers, commits, branches, worktrees, or test jobs were created.
- Out-of-scope discoveries: the old guide's file-write return values and some existing call spelling differ from the integrated decisions; the examples intentionally follow the newer owner rules. HTTP parsing, production streaming/cancellation of partial downloads, and shell terminal handoff remain separate library work.
