# Cleanup round 1 — owners first, a narrow defer

**Verdict: keep `defer` narrowly.** Acquisition should return a self-cleaning owner whenever release cannot fail; acquisition whose completion can fail should run an ordinary callback and return completion errors. Keep `defer` for infallible, one-off exit actions and the implementation of low-level adapters. Do not teach it beside opening a file, socket, ticker or channel. This is a proposal, not an accepted change or a compiler implementation.

```dewy
# Before (D4)
let stream = net.tcp_connect("127.0.0.1" 8080) or_throw
defer net.tcp_close(stream)
net.tcp_send(stream "hello") or_throw

# After: same acquire and use; TcpStream owns local release.
let stream = net.tcp_connect("127.0.0.1" 8080) or_throw
net.tcp_send(stream "hello") or_throw
```

## Scope and acceptance

Owned: this scratch directory only. The Dewy checkout is read-only. No code changes, commits, new syntax, global lifetime-mode change, background reaper, or invented nonlocal-return mechanism. Budget: three hours maximum. Acceptance: settle all cases in the brief; at least twelve realistic paper programs; explicit failure/cancellation/control-flow rules; honest comparative grades and up to three recorded rounds. The programs exercise a proposed library contract, not the current compiler. No executable or performance claim follows from them.

## Starting authority

Read LANGUAGE.md's place lending (1108–1161), records/collections (2088–2199), locks (3569 onward), cancellation (3625–3666), channels (3692–4040), errors (4140 onward), files/processes (4323 onward), networking (4462 onward) and foreign calls (4510 onward). Read decisions batches 3–8 and D4. `docs/design/ownership.md` additionally prohibits drop failure, panic and termination and specifies defer-before-owner cleanup. These restrictions matter: an automatic fallible drop would change established semantics.

Batch 3's `parallel` and library task groups supersede LANGUAGE.md's old `concurrent`/`spawn` syntax. Batch 8 rejects the `inline with` scope-block proposal. Its summary is useful evidence of problems, not authority for new syntax. Ordinary callbacks return from themselves. `resources/discussion_points.md:1193–1208` describes lifetime-attached cleanup and explicitly calls Python's context wrapping verbose; its `#on_cleanup` sketch still has the second step David now objects to.

## Rules

1. An owning value owns release. A socket, listener, ticker, texture, loaded sound and ordinary heap-backed buffer have exactly-once, non-failing release. Moves transfer the duty; borrows do not. A returned owner is released by its new owner, not its former function.
2. No new lifetime keyword. Ordinary owners retain last-use destruction. A returned place retains the lending method's locals until the place's last use. Use a helper with an `@` parameter when several statements form the protected operation.
3. A fallible completion is a result, not a drop effect. Existing `Path.copy_to`, `write_bytes`, `read_bytes`, process helpers, etc. must report completion errors before reporting success. Streaming acquisition has an ordinary callback overload, e.g. `files.open(path 'write' @body)`. The callback borrows the file; the wrapper owns and finalizes it. A bare fallible writer constructor is not the safe public route.
4. A scoped acquisition runs its callback once, obtains its result without `or_throw`, finishes, and combines the two results. A normal result is not delivered before finish. A body error must not be thrown away if finish fails too. Round 1 leaves the representation of that pair to review rather than pretending a plain `or_throw` handles it.
5. `defer` runs once at exit from the immediately enclosing ordinary block, in reverse registration order, before that block's local owners. It is registered only when execution reaches it. Deferred code may not escape with `return`, `break`, `continue`, `or_throw`, panic or exit, and must have a proven non-failing `void` summary. An explicitly handled failure is allowed if the residual action satisfies that contract. This restriction is new; the syntax is not.
6. A defer's free variables are live until execution of the defer. It therefore prevents an owner used there from moving out early. Do not register a release defer on an already self-cleaning standard resource. There is no general proof of a forgotten `printl"done"` or flag reset.
7. Cancellation still unwinds owners and defers, including when a task is canceled before its body begins. The existing 100 ms cleanup grace must cover this proposal's scoped completion too; the exact library boundary and composition need an explicit check in round 2. Forced process termination cannot promise user cleanup.

## Each requested case

### Every exit path

Automatic owners cover `return`, `or_throw`, `break`, `continue`, failed construction, replacement and compiler-controlled panic/exit. Returning an error **as a value** is not special unwinding: locals still die when that call returns. An error stored in an array is not automatically thrown. Scoped completion sees the callback's final value; a callback `return` reaches completion and then returns the acquisition call's result. An early return of the outer function must be written at that call (e.g. `return files.open(... @body)`), not inside the callback.

### One-off exit work

`defer printl"done"` remains one line. So does `defer { held = false }` after setting a program flag, when nothing exposes a reusable operation. A reusable busy flag API should perform set/body/reset itself. Restoration of terminal settings is a resource protocol and should be owned by the terminal API, not a copied defer at every use. Channel end-of-input should be owned by sender lifetimes. Do not pretend arbitrary obligations can be inferred from one assignment.

### Timing and locks

The following existing program is **wrong** for a whole critical region:

```dewy
let state = @(m.lock())
state.held = true
write_log()                 # lock may already have released
```

The lock lives through the last use of `state`, not this block's brace. A correct existing-construct version is a lending call passed directly to a helper:

```dewy
critical = (@state:State) => {
    state.held = true
    write_log() or_throw
    state.held = false
}
critical(@(m.lock())) or_throw
```

The helper's call statement holds the lent place until it returns, including all statements after the helper's last field read. A defer in the helper that needs `state` also finishes before that call returns. This is the already specified "statement holding it" rule, not lexical destruction for all owners. Do not add dummy reads or a magical keep-alive intrinsic.

### Files, including fallible flush/close

A file wrapper must attempt flush, any promised sync, and close, without claiming that these are the same operation. A failed flush does not skip close. The body may fail and cleanup may fail separately. The ordinary result must carry both; stderr-only reporting on normal exit is insufficient. Current `$__drop__:void` cannot return either error to a caller. A callback wrapper can, using ordinary values and branches. Its raw owner is a final backstop for panic, not a competing flush protocol. Round 2 must define the backstop's non-silent error policy.

### Channel closure

Provisional round-1 sketch: a channel exposes distinct copyable sending and receiving handles. Last sender drop closes sending; buffered items drain, then readers see existing `Closed<T>`. Last receiver drop wakes blocked senders with `Unsent<T>` preserving their payload. A sender's early return or cancellation therefore cannot strand its receiver. Review must check whether implicit copies or callback environments can accidentally retain sending rights across a receive/join.

### Other standard resources

| Resource | Owner and end behavior |
|---|---|
| Socket/listener | Release local OS handle; no promise of peer acknowledgement. An application protocol's final reply remains a checked operation. |
| Ticker | Drop cancels the timer registration and releases it; no user-written `tick.stop()` requirement. |
| Mutex | Mutex handle shares storage; the lending operation owns the acquisition guard, which unlocks when its place use ends. |
| Child process | Scoped process acquisition owns terminate-if-running and reap; normal exit status and termination/reap errors are values. A canceled wait does not mean the process has vanished. |
| Temp file/directory | Scoped helper owns deletion, including an error identifying a path left behind. Returning its Path does not transfer deletion ownership. |
| Terminal raw mode | Scoped helper owns exact saved-mode restoration; Ctrl-C uses ordinary task cancellation unless explicitly listened for. |
| GPU handle | Drop retires the resource; GPU submission/fence ownership keeps physical storage alive until safe destruction. It must not destroy an in-flight resource immediately. |
| Loaded audio buffer | Last owning buffer reference releases storage, including references held by playback. Dropping a playback observer does not truncate one-shot audio. |

### Cancellation and tasks

A once-run task takes an owner through an existing move capture. It releases its locals and captures before its group joins, even when cancellation skips the body. A resource returned by that task belongs to its result owner. Task handles are not themselves cancellation guards: the group owns execution. Ordinary scoped callbacks must not be confused with spawned once-run callbacks; an ordinary callable cannot take a captured move-only value and move it out on each call.

### Aggregates and loops

Existing structural records/arrays compose ownership. The outer hook runs first, then fields in reverse declaration order; owner arrays release elements in reverse live order. Partial construction releases only completed fields/elements. `pop` transfers; remove/replacement/clear releases once. A `break` only releases resources in scopes it crosses; loop-backedge liveness protects an owner used next iteration. A borrowed array of fallible resources must be finalized by its owning scoped batch wrapper; returning an array of borrowed handles is rejected.

### Raw C/OS resources

A C library with a non-failing release needs a nominal record with one handle field and a `$__drop__` method, plus a checked factory. This is a small one-time library cost, not an action every caller remembers. Release with meaningful errors instead needs the ordinary callback wrapper. Unsafe raw acquisitions are allowed to require manually paired release; safe standard APIs must not export that obligation. A leak warning cannot identify an arbitrary integer as a file descriptor without such a contract.

## What is new, and why existing forms do not already suffice

| Proposal | Existing attempt | Actual missing piece |
|---|---|---|
| Self-cleaning standard handles | `let s = tcp_connect(...)`; use it; return | The language already supports owners; the standard handle must implement the hook. No syntax. |
| Scoped fallible acquisition (`files.open`, `temp_dir`, `terminal.raw`, process and transaction callbacks) | Own a writer with `$__drop__:void` | Drop cannot return a flush error. Ordinary higher-order functions can; new library APIs only. |
| Separate channel endpoint types | Keep one shared bidirectional `Channel` | A reader holding the handle also keeps sending alive; no definition of "last sender" follows. New library representation/API. |
| Restricted defer | Use arbitrary fallible defer and forward from its exit | That recreates scope-block nonlocal-return problems. Restrict checked summaries instead. A semantic change to an existing construct, requiring David's approval. |
| Paired cleanup error | `let r=body(); finish() or_throw; r` | A finishing error replaces the body failure. Need a plain library error record; exact shape is next round. |

No change to `@`, `&`, metatag placement, `or_throw`, `??`, move inference, callable control flow, implicit effect rows or compiler syntax. Public library spellings below are provisional; `names.txt` in the final round is a cold-read packet, not a claim they passed a reader test. No item has been added to open_decisions.md.

## Considered and rejected

- **Remove every defer.** A nominal drop guard drops at last use, which is immediate for an unused `Done` guard. A wrapper callback works, but `done((...) => {...})` makes each one-off exit action into an extra function boundary. Keep the direct construct for this small case.
- **Defer as the default resource idiom.** Answers all exit paths after registration, but does not catch missing registration. David's three D4 examples are library ownership defects, not reasons to keep requiring defer there.
- **`defer <expr> {...}`.** Ties acquisition and policy together but asks each consumer to choose a cleanup policy the resource's author already knows. Returning/moving the resource would also need new lifetime rules. No failure of existing callbacks/owners justifies this grammar.
- **`with` / C# `using` / TypeScript `using`.** Clear lexical region and reusable cleanup protocol. They require opt-in at each acquisition, and a new syntax/protocol, where an ordinary acquisition callback suffices. Python's `with` runs `__exit__` on exits and can suppress an exception; this proposal deliberately does not offer suppression by the finalizer. [Python reference](https://docs.python.org/3/reference/compound_stmts.html#the-with-statement), [C# reference](https://learn.microsoft.com/dotnet/csharp/language-reference/keywords/using-statement).
- **Linear / must-consume resources.** Can diagnose forgetting a required `finish`, but force that second step into every return/error path. Ownership plus a callback makes consumer omission impossible at the acquisition boundary. A linear protocol might be right for an independently decided capability; do not add it just to preserve manual cleanup.
- **`errdefer`.** Failure-only actions do not solve missed registration; provisional resources can already be kept in an owner until success moves them out. Transactions require a semantic commit/rollback policy, not just "did a particular return use the error channel?" [Zig reference](https://ziglang.org/documentation/master/#errdefer).
- **Go.** Deferred calls run at function return and discard returned values; a file close error therefore needs extra handling. Do not borrow the discarded-error rule or function-wide timing. [Go specification](https://go.dev/ref/spec#Defer_statements).
- **Swift.** Scope-exit defer is a useful precedent for the retained one-off action. Deinitialization alone cannot decide the protected source region or give a caller a fallible completion result. [Swift statements](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/statements/).
- **Rust/C++ style RAII as a universal answer.** Good for infallible release and moves. Rust File drops ignore close errors, so this does not answer fallible completion by itself. [Rust File](https://doc.rust-lang.org/std/fs/struct.File.html), [Rust Drop](https://doc.rust-lang.org/std/ops/trait.Drop.html).
- **Automatic fallible drop / error effects on scope exit.** Would make a plain `return` acquire a new outcome at a liveness-selected source location, including in arrays and values already being handed off. This changes the accepted no-fail hook contract and needs substantial failure composition/control-flow rules. Ordinary callbacks first.
- **A global logging sink for all cleanup failures.** Reporting is better than silent loss, but a successful caller must be able to detect a failed save. Background logging is not the default substitute for a result.
- **An all-purpose `on_exit` guard factory.** A callback-backed guard still needs pinning at block end and special capture/one-shot rules. It adds a library name without removing the essential semantics of defer.

TypeScript's `SuppressedError` retains both body and disposal failures; that is useful library precedent for an explicit paired result, independent of its `using` grammar. [TypeScript 5.2](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-2.html).

## Required documentation changes if accepted

- LANGUAGE.md 2088–2199: retain no-fail hook contract; explain which library values actually own release and which handles merely observe execution; retain moves and aggregate cleanup.
- LANGUAGE.md 1108–1161 and 3569–3602: demonstrate the existing lending-call statement for a whole critical operation; explicitly warn that braces do not extend last use.
- LANGUAGE.md 3625–3655 and 3999–4008: distinguish owner/drop unwinding from ordinary callback completion, specify grace and joint failures, remove cleanup defers from task examples.
- LANGUAGE.md 3692–4040: separate channel capabilities and automatic endpoint closure; retain draining and `Unsent.value` guarantees. Exact constructor spelling awaits round 2.
- LANGUAGE.md 4140–4240: explain an ordinary callback return target and the cleanup-pair error; no hidden exception channel.
- LANGUAGE.md 4323–4510: make file-copy/write success include completion, make socket examples owner-based, specify process ownership.
- D4 examples at open_decisions.md 80–185: remove ticker and TCP release defers; replace completed channel's close defer with producer ownership. A progress reporter still needs a join if its output must finish before the program exits.
- decisions.md batch 7's cleanup paragraph is superseded **only if David accepts this design**. Batch 8's rejection of `inline` and all unrelated decisions stand. Historical proposals are not rewritten.

## Review questions for round 2

Channel root retention, two simultaneous failures, panic backstops, 100 ms composition, real callback control flow, and resources escaping a scoped API must be settled before grading the final programs.
