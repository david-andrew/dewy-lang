# Cleanup round 6: predictable timing, visible exits, a narrow defer

## Three recommendations

**1. Run observable cleanup hooks at the end of the owning scoped block.** Moves transfer the duty, consuming operations finish it earlier, and a smaller `{ … }` selects an earlier boundary. Plain storage without observable cleanup can still die at last use. Reject the round-5 split by fallibility. This is a recommendation to David, not a recorded decision. On the explicit scenario panel below, block-end and last-use tie in raw surprises (six each); block-end has a narrow severity advantage, 14 to 15. The important reason to prefer it is that programmers can move a visible boundary rather than manufacture a later use. There is no measured usability claim and no claim that lexical cleanup wins every workload.

Before (round-5 infallible socket; the server requires the session alive during its side-channel update):

```dewy
update = () => {
    let stream = service.connect or_throw
    stream.send("begin") or_throw
    service.apply_side_channel_update() or_throw
} # Last-use closes the session before the side-channel update.
```

After (same source, uniform block-end rule):

```dewy
update = () => {
    let stream = service.connect or_throw
    stream.send("begin") or_throw
    service.apply_side_channel_update() or_throw
} # Session closes here, after the update.
```

This benefit has an equally real converse: a peer waiting for EOF can hang while this scope remains open. Program 02 includes both protocols and an explicit shorter block; program 10 repairs the existing sender-then-join pattern.

**2. Require `or_throw` on an inner owning block/body whose implicit fallible cleanup can replace a local continuation with a function exit.** Missing acknowledgement is a compile error. The familiar surface is `loop … { … } or_throw` or `{ … } or_throw`; its cleanup meaning applies on every exit of that body, including `break` and `continue`. This is new control-flow semantics for an existing spelling, and needs approval. It is not merely today's postfix operator reached after a loop. Explicit function exits remain explicit already; their cleanup failures are function results as decided.

Before:

```dewy
write_all = (paths:array<Path>) => {
    loop path in paths {
        let out = files.open(path 'w') or_throw
        out.write_text("row\n") or_throw;
        if path =? p"last.txt" break
    }
    printl("all completed")
}
```

After:

```dewy
write_all = (paths:array<Path>) => {
    loop path in paths {
        let out = files.open(path 'w') or_throw
        out.write_text("row\n") or_throw;
        if path =? p"last.txt" break
    } or_throw
    printl("all completed")
}
```

If close fails, the suffix is the written authorization to leave `write_all`; the post-loop print is skipped. A normal `break` still reaches it. Each iteration completes before the next begins. This recommendation favors readable scope-level acknowledgement over a new form of `break`; it does **not** give a marker on the exact jump line. That limitation receives a real grading deduction.

**3. Keep `defer` narrowly for a non-failing, void, one-off exit action, especially restoration of external state across supported unwinding.** Do not use it for recursive indentation or an ordinary result-timing wrapper. Many returns alone do not establish its necessity. It remains useful when introducing an owning wrapper or splitting a function merely to restore existing state would obscure the operation.

Before (stateful recursive indentation):

```dewy
render = (node:Tree @indent:int64) => {
    draw(node.label indent) or_throw
    indent += 1
    defer indent -= 1
    loop child in node.children { render(child @indent) or_throw }
}
```

After (the stronger default):

```dewy
render = (node:Tree depth:int64=0) => {
    draw(node.label depth) or_throw
    loop child in node.children { render(child depth+1) or_throw }
}
```

The case that still earns `defer` is program 16's serialized foreign global flag: save its old value, change it, register restoration, call the legacy renderer. The ABI has no per-call parameter to pass instead. A library should provide an owner when that pattern becomes reusable.

## Scope, authority, and evidence

Owned output: this directory only. Acceptance: the three decisions above argued with concrete counterexamples; at least ten full-function paper programs; honest O/D/C/S/K grades with line evidence; comparison to all five requested peer languages; no checkout modifications or commits. Budget: approximately two hours maximum. Non-goals: compiler implementation, performance work, new database design, changing cancellation policy, and choosing D40 Q3's multi-error representation.

Read: round5.md, summary.md, amendments.md, review-round4.md, regrade-round5.md, all 24 programs-r5, D40, decisions batch 9, and the relevant ownership/language rules. Authoritative source paths are under `~/dev/dewy-lang/docs/`. D40 explicitly puts combining errors back under design: this round does **not** silently adopt `CleanupError[primary cleanup]` as settled. Where two errors coincide, programs say both must survive and defer representation/splitting to Q3. Cancellation cannot become silent success.

Batch 9 binds the following: cleanup failure is the enclosing function's result; editor highlighting/hover expose cleanup; `$__abandon__` denotes abandoned work; hooks are assigned functions; `()` does not create a scope, `{}` does; `parallel ( … )` bindings belong to the enclosing scope. No file here changes those decisions. Hook examples in program 18 use only assigned-function form.

These are design programs, not executed tests. `programs-r6/README.md` states illustrative library contracts and intentional negative examples. No fixture backend, runtime performance or successful compilation is claimed. The grades distinguish a coherent paper example from an implemented capability.

## 1. Timing: compare the actual surprises

### Rules being compared

- **L — last use:** every owner finishes after its last necessary use, including the uses imposed by loans, captures and defers. On a path with no source use it can finish immediately. It cannot ignore a future iteration, a borrow, or a deferred read. An optimizer must respect observable effects; "proven" must be specified independently of optimization settings if this becomes a language guarantee.
- **M — round-5 mixed:** infallible ordinary owners use L; fallible owners and kept lending guards use block-end; containing records/arrays/unions/closures conservatively inherit held status.
- **B — block-end:** all observable cleanup duties belong to a lexical owning scope. Borrow liveness may still end at last use. Hook-free storage may be reclaimed earlier when unobservable. Explicit consume/move still has its ordinary meaning.

The panel asks what plausible source-level intent the rule violates *before its repair*. It counts a delay, premature cleanup, or unstable control-flow boundary once per scenario. A compiler warning is useful but does not erase the surprise; a known deadlock becoming a compile error is safer but is still a source migration. Scores: 1 = avoidable retention/work; 2 = misleading result, ordering, or maintenance trap; 3 = hang, broken critical region, or broken required protocol. These are editorial severity judgments, not measured probabilities. Multiple symptoms in a row are not separate votes.

| Case and concrete evidence | Weight | L | M | B |
|---|---:|---:|---:|---:|
| T1 Ledger access followed by protected journal append, 01:3–8 | 3 | 1 | 0 | 0 |
| T2 Lock held across unrelated sleep, 01:10–15 | 2 | 0 | 1 | 1 |
| T3 Socket EOF required before status wait, 02:3–7 | 3 | 0 | 0 | 1 |
| T4 Session must remain alive for side-channel update, 02:17–23 | 3 | 1 | 1 | 0 |
| T5 Buffered file read through a separate path before flush, 03:2–6 | 2 | 0 | 1 | 1 |
| T6 Last-use close failure skips independent audit tail, 03:16–22 | 2 | 1 | 0 | 0 |
| T7 Timer retained through unrelated expensive computation, 04:3–8 | 1 | 0 | 0 | 1 |
| T8 Never-read raw-mode owner restored before the read, 04:10–15 | 3 | 1 | 0 | 0 |
| T9 Same generic body has different cleanup placement by instance, 05:3–16 | 2 | 0 | 1 | 0 |
| T10 Wrapping socket with fallible sibling changes its lifetime, 05:18–25 | 2 | 0 | 1 | 0 |
| T11 Last call of closure followed by wait for captured stream EOF, 06:7–13 | 3 | 0 | 0 | 1 |
| T12 Optional last use in a branch; adding later diagnostic use changes protocol, 07:2–16 | 2 | 1 | 1 | 0 |
| T13 Sender survives while the reporter waits for Closed, 10:8–14 | 3 | 0 | 0 | 1 |
| T14 Unread non-failing effectful owner runs before body, 18:4–12 | 2 | 1 | 1 | 0 |
| C1 Per-iteration locals release before the next iteration, 08:13–26 | — | 0 | 0 | 0 |
| C2 `parallel ( … )` does not own lifted names; real uses survive join, 09:8–23 | — | 0 | 0 | 0 |
| C3 Returning a closure transfers its capture, 06:2–5 | — | 0 | 0 | 0 |
| **Raw surprises (14 discriminating cases)** | | **6** | **7** | **6** |
| **Severity total** | | **15** | **15** | **14** |

The three control cases are deliberately not counted as wins. All candidates can keep a loop-backedge use alive, honor a moved capture, and respect the agreed unscoped parallel form. Last-use does not mean dropping a value while a real future use exists. Failure visibility at loop exits is addressed in section 2 for all timing choices; it is not counted repeatedly in this timing score.

**How much should the tally persuade us? Not very much by itself.** Changing a single severity weight by one can erase B's lead. T3/T11/T13 share an EOF/end-of-input dependency; T9/T10 share mixed-category instability. This is an adversarial coverage panel, not a frequency-balanced population. Double the weight of the three EOF/join cases and B loses decisively (23 against 15 and 15). A channel-heavy application could reasonably prefer L. Conversely, a region-heavy application hits T1/T4/T8 much more. The arithmetic does not establish a universal minimum of surprises.

The recommendation comes from the *repair and maintenance model*: B has a boundary visible in the code, stable under adding a diagnostic read, changing a concrete type, or adding a fallible field. To shorten it, end the block, consume the owner, or move it into a real operation. To lengthen L, the author needs an artificial use, an explicit lifetime facility, or a type classified as a guard. The latter two effectively reintroduce a second timing system. M retains the major early socket/probe surprises and adds representation-sensitive timing, while also retaining the held-lock/file costs. I would choose B for a general-purpose language, and document its early-close cases prominently rather than claim zero surprises.

### Boundaries and hard cases under B

1. An owned parameter belongs to its function; a local binding belongs to the nearest owning `{ … }`. A loop's braced body owns its per-iteration locals. Branch/arm braced locals belong there. An alias/place can cease to be usable earlier, but the associated kept guard remains held. Deadlock and wait checks use the guard's actual held interval.
2. Moving an owner transfers the duty; it does not run its hook. A returned owner, including a returned closure's captures, belongs to the caller after successful handoff. If other cleanup prevents handoff, finish the withheld owner exactly once. An explicit consuming close/commit ends its duty even when it fails; no second close.
3. A record or array retains its owned children until it is consumed, moved, or its scope ends; changing a field's fallibility never changes that boundary. Partial moves remain subject to the existing outer-hook restrictions. A union's active alternative owns cleanup; narrowing changes neither binding scope nor release timing.
4. `parallel ( … )` creates no owning scope. The visible `let`s belong to the enclosing block; an item's nested function or scoped block owns its private locals. `parallel { … }` has its own scoped bindings. Initialization flags cover partial acquisition/cancellation, and cleanup effects must participate in dependency scheduling before publication. No "drop at join" exception for unscoped names.
5. A bare effectful owner expression is an anonymous owner in the same scope, following the round-5 amendment. It must not silently become a statement temporary. Example: program 04's discarded raw-mode owner. Give an inlay/warning naming the boundary; do not suggest deleting a purposeful unread guard. Owners consumed by a call are governed by that call's ownership contract. An inline lending guard used only for `f(@(m.lock))` keeps its established statement boundary; it does not create a named owning local. This existing distinction must be documented beside anonymous ordinary owners, not hidden behind "every expression lives to the brace".
6. Defers continue before local owner cleanup, LIFO within their scope; owners retain the existing reverse acquisition ordering, hook-before-fields and initialized-only plan. Plain no-hook storage is not automatically held merely to match source braces, unless a live duty still needs it.
7. A never-used socket/Probe is still meaningful if its hook has effects. A semantic lifetime cannot be optimized away merely because no source expression reads the binding. Dead-store elimination is permitted only when the effect is demonstrably unobservable, including allocation/release contracts and external effects.

### Repairs and real costs

- Program 01's smaller block preserves protected tail I/O but ends before the unrelated wait. The lock-order/wait diagnostics must cover the longer interval; a hint is not proof against dynamic deadlocks.
- Program 02 closes a socket in an inner block before waiting for peer status. It requires no `or_throw` if release truly cannot fail. The socket-close contract must not pretend to report successful delivery to the peer.
- Program 03 writes inside `{ … } or_throw`, then reads back. Reporting completion/durability from inside a still-owning scope remains wrong; flush is not fsync.
- Program 06 extracts a real `read_chunk` operation so the capture closes before waiting. Moving or returning a closure means its environment can outlive its creator; B does not make escaping capture cleanup lexical to the creator.
- Program 10 moves the sender into `produce`. Its return closes the endpoint before the join. Do **not** mechanically remove explicit closes from old D4 under B; the prior last-use proof is invalid. A shorter block with a suitably arranged task scope or an explicit consuming endpoint operation is another possible repair; this round does not invent that operation.
- Tickers and sockets can remain alive longer, so B has real resource/power/latency costs even without a leak. Keep the relevant scope short. No benchmark was run, and no percentage speed claim follows from this design pass.

## 2. Visible exits: alternatives and the selected rule

### Research: what existing languages really establish

Python `with` visibly introduces a managed region and calls `__exit__` on normal completion and control transfer; cleanup can raise and prevent the intended transfer. It does not mark every potentially exceptional `break`, and a `with` binding does not give a lexical variable scope. Borrow the recognizable region, not a claim that Python solves explicit-exit visibility. [Python compound statements](https://docs.python.org/3/reference/compound_stmts.html#the-with-statement)

Rust associates locals/temporaries with drop scopes and performs destruction when those scopes are left. `Drop::drop` has no error result; `std::fs::File` ignores errors detected by its Drop close. Borrow stable owner scopes, but do not copy close-error loss or equate non-lexical borrows with non-lexical destruction. [Rust drop scopes](https://doc.rust-lang.org/stable/reference/destructors.html#drop-scopes), [Drop trait](https://doc.rust-lang.org/stable/core/ops/trait.Drop.html), [File](https://doc.rust-lang.org/std/fs/struct.File.html)

Swift `defer` runs at scope exit in reverse order and cannot transfer control outside the defer. That supports a small restoration construct. Swift's automatic reference lifetime is more nuanced than a universal closing-brace destructor guarantee: its implementation documents lexical lifetimes with deinit barriers and permitted lifetime shortening. The prior amendment's blanket "what Python, Rust and Swift do" was too broad. [Swift statement specification](https://github.com/swiftlang/swift-book/blob/main/TSPL.docc/ReferenceManual/Statements.md#defer-statement), [Swift SIL lifetime documentation](https://github.com/swiftlang/swift/blob/main/docs/SIL/SIL.md#lexical-lifetimes-and-deinit-barriers)

Zig supplies scope-exit `defer` and an error-return-only `errdefer`; return from a defer expression is forbidden. Error checking and cleanup registration remain explicit work for the author. It is useful evidence for keeping cleanup actions simple, not a solution to automatic fallible destructors. [Zig defer](https://ziglang.org/documentation/master/#defer), [Zig errdefer](https://ziglang.org/documentation/master/#errdefer)

Go defers until the *surrounding function* returns, evaluates call arguments at registration, and discards deferred call results. A named result can be changed by a deferred closure. Deferring a close inside a long loop therefore differs from a Dewy per-iteration block duty. [Go defer specification](https://go.dev/ref/spec#Defer_statements)

TypeScript's `using`/`await using` visibly declares a disposal obligation, disposes at scope exit, and can propagate disposal errors. `SuppressedError` retains both a pending error and a disposal error. This is the closest prior art for automatic fallible cleanup, but `using` still has no explicit marker at each jump. Its error container is evidence for Q3, not a choice made here. [TypeScript 5.2 resource management](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-2.html)

Research accessed for this round; primary documentation only. No peer-language code was executed. Source-derived summaries are deliberately short; the Dewy choices below are design inferences.

### Brainstorm, including the unpleasant alternatives

Every code example below includes the function whose control flow is affected. Examples marked "candidate" are not recommended/accepted syntax.

**A. Treat every exceptional value produced by a loop as something its trailing `or_throw` sees.** This closely follows the spitball. Nonexception values flow onward; the first exception stops the loop.

```dewy
summaries = (paths:array<Path>) => {
    loop path in paths {
        let out = files.open(path 'w') or_throw
        out.write_text("row\n") or_throw;
        if path =? p"last.txt" break
        path
    } or_throw
}
```

Problem: Dewy loops already express body values and can feed collectors. Is a *deliberately produced error value* data or a failed loop? Is a cleanup error delivered after earlier items have escaped? How does an outer collector stop a nonlocal `return`, or a labeled break that skips it? An ordinary postfix operation on the finished value does not answer those questions. Reject a general "first exceptional thing anywhere" implicit scan. Keep explicit `value or_throw` where a produced exception is meant to propagate. For cleanup only, A can be narrowed into the selected boundary policy below.

**B. Require owners to be bound outside the loop.**

```dewy
write_all = (paths:array<Path>) => {
    let out = files.open(p"all.txt" 'w') or_throw
    loop path in paths {
        out.write_text(path as string) or_throw;
        if path =? p"last.txt" break
    }
    printl("all accepted")
}
```

Works for one output spanning the entire loop. Fails the original per-path output requirement. Hoisting an array of outputs retains every descriptor and delays failure; replacing one outer owner reintroduces fallible cleanup at assignment. Reject as a general rule; offer it only when the intended resource already spans all iterations.

**C. Require the owning inner block/body to acknowledge fallible local exits.**

```dewy
save = (path:Path) => {
    {
        let out = files.open(path 'w') or_throw
        out.write_text("row\n") or_throw;
    } or_throw
    printl("file completed")
}
```

Selected. It uses existing braces and the established meaning "a failure can leave this function." Require it statically, so forgetting it cannot produce hidden successful-looking flow. It is an exit policy, not a local error-catching scope or callback. The semantics on a jump are additional language work and cannot be sold as a zero-change desugaring.

**D. Forbid every implicit fallible cleanup on a local exit; require explicit consumption/handling.**

```dewy
write_all = (paths:array<Path>) => {
    loop path in paths {
        let out = files.open(path 'w') or_throw
        out.write_text("row\n") or_throw;
        out.close() or_throw
        if path =? p"last.txt" break
    }
}
```

Very clear and no new surface. Still safely automatic on `return`/`or_throw`. But many paths require repeated closes, factoring, or state tokens; generic cleanup needs a universal consuming operation not currently chosen. New early local exits cause mechanical fixes. Keep as an escape hatch (program 12), not the default idiom.

**E. Make completion failure an ordinary loop/block result and require handling it.**

```dewy
write_all = (paths:array<Path>) => {
    let completed = loop path in paths {
        let out = files.open(path 'w') or_throw
        out.write_text("row\n") or_throw;
    }
    completed or_throw
    printl("all completed")
}
```

Candidate only: this would make cleanup errors capturable locally. It is attractive for retrying an iteration but competes with normal loop-produced values, and conflicts with the binding function-result direction if the local block now intercepts a failed `return`. It also needs a rule for labeled transfers and already-expressed values. Reject for this round. A real function already provides a result you may capture without changing what `return` means.

**F. Put the marker on each jump (`break or_throw`, `continue or_throw`) and the block end.**

```dewy
write_all = (paths:array<Path>) => {
    loop path in paths {
        let out = files.open(path 'w') or_throw
        out.write_text("row\n") or_throw;
        if path =? p"skip.txt" continue or_throw
        if path =? p"last.txt" break or_throw
    } or_throw
}
```

Candidate new grammar only. Strongest literal visibility at the jump. Also repeats a single owning-scope policy at every edge and still needs an end-of-body marker. It implies `break` is a value on which normal `or_throw` operates unless taught specially. Do not request these new jump forms now. If David requires the marker physically on the jump line, F is the honest alternative; C does not fully meet that stronger condition.

**G. Mark acquisition (`using`, a fallible-owning binding qualifier, or a lifetime tag).**

```dewy
write_all = (paths:array<Path>) => {
    loop path in paths {
        using out = files.open(path 'w') or_throw
        out.write_text("row\n") or_throw;
        if path =? p"last.txt" break
    }
}
```

Candidate only. Makes the duty visible like TypeScript, but the jump still says nothing about a function exit. Adds a spelling and teaches two ways to bind resources. It would need naming review; none is being submitted here. Reject for this task.

**H. Helper function or whole-value operation.**

```dewy
write_one = (path:Path) => {
    let out = files.open(path 'w') or_throw
    out.write_text("row\n") or_throw;
}
write_all = (paths:array<Path>) => {
    loop path in paths {
        write_one(path) or_throw
        if path =? p"last.txt" break
    }
}
```

Already works. A `path.write_text` whole-value operation is shorter still when no streaming is needed. Recommend both where natural. They cannot replace all lexical regions: factoring a region containing caller-directed `break`/`return` needs extra return tokens, and acquiring through a callback was previously rejected.

**I. Editor-only highlighting, or forbidding fallible hooks entirely.** The former was precisely the concern David raised; highlighting supplements text. The latter contradicts the accepted automatic function-result cleanup direction or loses real flush errors. Neither is an answer within this task.

### Precise selected semantics

Call the scope that holds an owner's duty its owning scope; this is explanatory prose, not a new language name.

1. **When required:** if an inner scoped block/body has a reachable exit that normally continues within this function, and its implicit cleanup can fail, that block/body needs a cleanup `or_throw` suffix. Such exits include fallthrough, `break`, and `continue`, including labeled ones crossing it. Omit the suffix only if there is no such implicit failure edge (all relevant owners consumed/moved), or all reachable exits already leave the function. Function-body fallthrough already returns the function result. No redundant suffix on the function declaration.
2. **Attachment:** the suffix immediately on a braced loop body (`loop … { … } or_throw`) applies per iteration to that body's completion. It is not a catch around the whole loop's accumulated values. A plain `{ … } or_throw` attaches to that block. Branch/arm scoped bodies use the same immediate-body rule; grammar/precedence must be pinned before implementation, with grouping where otherwise ambiguous. No suffix on `parallel ( … )` can end an owner's duty it does not own.
3. **Successful cleanup:** continue the pending action unchanged: normal fallthrough, jump to the next iteration, jump out of a labeled loop, or a pending function return. There is no re-evaluation of the body, no delayed failure list, and no extra success value contributed to a collector.
4. **Failed cleanup:** run all remaining required cleanup for the crossed scopes exactly once, retain all causes, cancel a pending local jump, and leave the enclosing function. Do not execute any later statement in that iteration, any later iteration, or a post-loop continuation. Nothing resumes at a brace. Existing `return`/`or_throw` still target the enclosing function, not the block.
5. **Why a suffix runs on continue:** it is associated with the scope's exit edges, just as a registered cleanup is. Ordinary postfix evaluation alone would be skipped; a compiler treating this as ordinary evaluation is wrong. The new semantics must appear in the language reference and lowering tests. This is the largest teachability cost of C.
6. **Coverage is local:** an outer loop/block suffix is not blanket authorization for an unmarked inner scope to skip intervening code. Mark the inner scope that can fail on a local continuation. A jump crossing several fallible owning scopes needs each such boundary acknowledged; already-visible function exits need no new marker. This costs punctuation in nested resource-heavy code but prevents distant policy surprises.
7. **Ordinary expressions and values:** ordinary explicit `expression or_throw` keeps its existing value behavior. A cleanup suffix does not recursively inspect arrays, scan arbitrary produced values, or reinterpret an explicit `return error_value` as local handling. The cleanup path is an additional exit effect, never an ordinary generator item. A successful owning expression result remains pending until cleanup succeeds, then moves; if cleanup fails, complete the withheld result too. Partial output already observed by a consumer cannot be rolled back.
8. **Local handling:** consume/handle an owner's explicit `close()` before a local jump, or capture the result of a real helper (program 12). `({ … } or_throw) ?? …` cannot catch the function exit, exactly as a `??` cannot catch an explicit `return` inside its operand. A plain inner block yielding a value does not silently acquire catch semantics. `or_throw<E>` cannot acknowledge unselected cleanup errors: reject unless every reachable cleanup failure is forwarded or eliminated by explicit handling; a full `or_throw` is the normal spelling.
9. **Diagnostics:** error on the owning binding and first uncovered local exit, with a fix-it at that exact scope/body suffix. Example: "out can fail while completing this continue; add or_throw to this loop body, or consume and handle out before this exit." Hover the jump and suffix together, show the precise cleanup boundary and failure kinds. Existing acquisition `or_throw` acknowledges acquisition, not all future cleanup. Recheck generic instances; an infallible instance may not need a marker, but writing one is permitted for a reusable generic.
10. **Exceptional control paths:** when already returning an error, an additional cleanup failure joins it under Q3, rather than replacing evidence. Cancellation remains cancellation even with cleanup failures; defaulting must not consume it. Panic/exit use the established cleanup plan and are not made recoverable by a suffix. The child-stop protocol keeps the amendment's independent stop timeout; this proposal does not reintroduce an unbounded normal child shutdown.

### Required acceptance traces before claiming this is implemented

| Trigger | Required observation |
|---|---|
| Empty loop | No body owner constructed, no close; continuation runs |
| Body fallthrough, successful close | Next iteration starts only after close |
| Body fallthrough, failed close | Function failure; later iterations/continuation absent |
| `continue`, successful/failed close | Respectively next iteration / function failure |
| `break`, successful/failed close | Respectively after-loop continuation / function failure |
| `break $outer` through marked inner scopes | Each crossed duty attempted once; failure suppresses target jump |
| Explicit `return 7` with failed close | Replace pending 7, no local resumption |
| Owning result pending when another hook fails | Finish withheld owner once; preserve all failures |
| Body already failing, two failed cleanups | All causes survive in Q3 representation; no double close |
| Canceled during cleanup | Existing grace/cancellation semantics; suffix never swallows it |
| Parallel sibling fails before/after acquisition | Clean initialized owners only; preserve sibling and cleanup errors |
| Loop yields ordinary values and close fails | Cleanup is not a collected value; earlier delivered output stays delivered |
| Outer marker but uncovered inner fallible scope | Compile error naming the inner scope |
| Owner consumed on every locally continuing path | No redundant cleanup marker required |
| Generic T changes infallible to fallible | Same release boundary; marker/result diagnostics update |

This is a test specification, not a claim that any of these tests ran. The collector interaction and selective error combination remain especially important integration gates; grading does not round those gaps up to 5.

## 3. Does defer survive the functional rewrite?

### Recursive render: remove mutable state

Program 13 gives both full functions. Parameter `depth` expresses the actual input to drawing; it needs no restoration, works for failing descendants, and avoids shared mutable indentation across concurrent renderers. Both versions need the same practical recursion/depth policy. Verdict for this example: **drop defer from the program**. Preserving the construct is not justified by this use.

### Time a request even when it fails: capture, record, forward

```dewy
handle = (request:Request) => {
    let start = clock.now
    let result = serve(request)
    metrics.observe(clock.now-start)
    return result
}
```

This is the ordinary-result rewrite, including `Canceled` and combined cleanup errors. There is no `??`, no default and no catch that mistakes cancellation for success. The result is merely held and forwarded unchanged. `serve` has completed its own resources before returning, so the timer includes its cleanup. Program 14 uses a bounded, non-failing metrics sink; a normal file logger that can fail is not eligible for narrow defer, and its result needs a separate explicit policy in either version.

A deferred timer is not intrinsically more complete: Dewy's defers run before the same scope's local owners complete. A timer in a resource-owning handler may stop before a slow flush. A worker/helper boundary is useful even when defer is available. The straight-line rewrite does miss panic or explicit process-exit unwinding; this difference is real only if that is the requirement. Neither scheme promises behavior after SIGKILL, power loss, or unsafe foreign nonlocal escape.

Verdict for ordinary response/error/cancellation timing: **prefer result capture**. If the requirement includes supported unwinding, keep a narrow deferred metric action or a reusable instrumentation owner, and state the exact interval measured.

### Search for the strongest remaining examples

| Case | Best no-defer rewrite | What defer actually buys | Verdict |
|---|---|---|---|
| Several early returns in a request | Call a real worker, capture result, record, forward | Avoids a helper only; also observes supported unwinding | Not sufficient by itself |
| Recursive depth/indentation | Pass depth | Nothing; removes an unnecessary mutation/restoration pair | Prefer functional form |
| Task-confined editor busy state, program 15 | Helper body with captured result, restore previous flag, forward | Keeps policy beside change; preserves restoration during supported unwinding | Keep for one-off integration; owner if reused |
| Legacy C global diagnostic toggle, program 16 | Capture foreign call result then restore; or add a restoring owner | ABI cannot accept functional state; plain capture misses unwinding; owner adds a nominal protocol | Strongest keep case, under serialization contract |
| End sending on shared Channel, program 17 | Capture whole producer-coordinator result, close, forward | Local one-line obligation across exits without extra worker | Keep explicitly documented protocol carve-out |
| Rollback DB transaction | Owning transaction with `$__abandon__`, explicit commit | Nothing; manual defer duplicates library ownership and can hide failure | Do not use defer |
| File/socket/timer/mutex lifetime | Owning value or kept guard, optional smaller scope | Nothing for mandatory release; can create duplicate duties | Do not use defer |
| Restoration itself can fail | Owner with fallible cleanup or explicit result handling | Narrow defer cannot express it safely | Reject that defer |
| User action truly must run after all local cleanup | Worker boundary or correctly ordered owner | Existing defer-before-locals does not provide it | Do not broaden defer order silently |

A proposed universal "scope guard" owning a callback would encode the same machinery and still require a second registration line, plus introduce capture/ordering questions. It is an alternative implementation/library style, not evidence that the need disappeared. A private C guard should be added by an established library when reusable; this round does not reopen the blocked local-nominal encapsulation proposal.

### A real C analogue, and why it does not justify a blanket pattern

The GNU Scientific Library documents a real save/change/restore global obligation: `gsl_set_error_handler` and `gsl_set_error_handler_off` return the old handler so it can be restored. Its manual also says the handler is program-wide and discourages changing it in multithreaded programs except during setup. A single-threaded host embedding a foreign numerical operation is a plausible restoration case; an ordinary concurrent application should normally set its error policy once instead of toggling it around each call. This supports the existence of program 16's problem, not the safety of its hypothetical binding. [GSL manual, error handlers](https://www.gnu.org/software/gsl/doc/latex/gsl-ref.pdf), [GSL threading guidance](https://www.gnu.org/software/gsl/doc/html/usage.html#thread-safety)

The important test is stronger than "C has globals": can the option be passed as a parameter or fixed once? If so, prefer that. Can restoration fail, allocate, block, or escape the host's unwind machinery? Then narrow defer cannot simply promise it away. Does a wrapper already own the session/context? Put restoration in that owner. Only the remaining one-off, checked, restorable external-state action is the steelman. The research therefore narrows the keep verdict rather than manufacturing an FFI safety win.

### Exact retained boundary

Keep the existing provisional form; no new keyword, tag, member name, or public guard type. Registration runs when reached, scoped to the owning `{ … }`; LIFO before owner cleanup. Captured values/places must remain valid until execution. The deferred action must be checked transitively non-failing, `void`, and unable to `return`, `break`, `continue`, `or_throw`, panic or exit. An unknown foreign call is not eligible just because C declares it `void`; its trusted contract must actually establish those properties. A non-failing restoration that can block still needs the existing cancellation/grace analysis; examples 15–16 choose nonblocking restoration.

Do not enforce "one-off" by an arbitrary syntactic whitelist. It is guidance separating a local action from a library resource's mandatory release. Review recurring use as a candidate owner abstraction. Forgetting an arbitrary external restoration remains possible; compiler checks on an existing defer cannot infer the missing registration. That is why programs 15–17 do not receive safety 5.

Shared `Channel`/`mpmc` are the explicit protocol exception: the value releases its storage, but knowing when *all producers* have finished is not last-overall-reference destruction. Keep explicit close as agreed. Say "resource release is automatic; some coordination protocols still require an explicit action," rather than the round-5 absolute claim contradicted by its own channel program.

## Integration risks, costs, and approval boundary

- **Actual new semantics:** all observable hooks move to lexical owner boundaries; kept guards retain the R5 extension over the old loan rule; missing inner-scope completion acknowledgement becomes an error; a body suffix attaches to all its exit edges. C is a proposal for David, not an accepted spelling rule. No new public names are submitted, and no cold-reading exercise was run or claimed.
- **Inherited unresolved work:** Q3 error combination and cancellation-preserving inspection, unsafe foreign wrapper encapsulation, cleanup on destructive replacement, and implementation of owner summaries. This round makes no all-cases-complete claim. In particular a fallible old-value drop on assignment is not a block exit: new block suffixes do not magically make `destination = new_owner` visibly fallible. Use explicit consumption/replacement results until that separate visibility question is settled.
- **Anonymous and temporary owners:** the inherited discarded-owner retention rule differs from an inline lending guard's statement lifetime. This is still a discoverability cost, with named locals the recommended readable form. A complete expression-temporary table is needed for implementation; this pass does not claim all subexpression forms have been validated.
- **Compiler cost:** reuse indexed lifecycle summaries and cleanup CFG edges. Scope attachment can be a boolean/policy on an existing scope node; marker coverage is checked only for scopes with fallible cleanup obligations. Expected work is proportional to those scopes and generated exit/cleanup edges, with cached per-type summaries. Worst-case cleanup edge duplication and type-set union cost are not proved linear in source length. Measure flagship instruction counts before implementation lands, not wall-clock on this host.
- **Runtime cost:** no extra heap registration is required by the marker. Block-end changes resource retention, lock contention, timer activity and synchronization ordering; those are observable costs, not optimized-away bookkeeping. No performance pilot belongs in this paper-only task.
- **Migration:** review all former last-use-close-before-wait patterns, particularly D4/program21 and its Spsc reporter; do not simply switch the rule globally. Add diagnostics where identities prove a wait cycle. Documentation updates belong to the coordinator after approval, including ownership.md, user_managed_storage.md, LANGUAGE.md and the relevant decisions. Nothing in that checkout was edited here.

The submitted recommendation is B + explicit scope completion acknowledgement + narrow defer. It clears the main round-5 generic-timing and invisible-exit problems on paper, but it is not a gold-standard all-5 packet. The grading file records the remaining weak points and the concrete revisions already made.
