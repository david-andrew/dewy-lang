# Cleanup round 3 — final recommendation

**Keep `defer` narrowly:** a checked, infallible scope-exit action for one-off program behavior and low-level adapters. Standard resource acquisition must not require a matching release line: infallible release belongs to the acquired owner; fallible completion belongs to an ordinary acquisition callback that returns completion errors. Keep last-use destruction and existing place lending. Add no cleanup keyword, block grammar, pinning tag or implicit fallible-drop effect. There are thirteen paper programs, with a final design floor of **4/5**, not an assertion that every case is effortless or implemented.

```dewy
# D4 today
let tick = ticker(500ms)
defer tick.stop()
loop i in [0..4) tick.next or_throw;

# Proposed: timer ownership handles every exit and early last use.
let tick = ticker(500ms)
loop i in [0..4) tick.next or_throw;

# Fallible completion: the one acquisition expression includes its region.
files.open(p"copied.bin" 'write' @copy_into) or_throw
```

Round 1 explains the alternatives and documentation inventory. Round 2 replaces its provisional channel/failure rules. This round and contracts.md are the final rules where those drafts differ. No earlier round has been rewritten. Programs are the final illustrative versions; their initial candidates are described in the revision record rather than claimed to be unchanged historical fixtures.

## Final rules

1. **Owners release themselves.** TcpStream, TcpListener, ticker, GPU assets, loaded audio buffers and channel endpoints have exactly-once non-failing release. Drop means local release/retirement, not a successful network protocol, guaranteed persistence, or that work observed by a handle has stopped. A Task/PlayingSound observation handle is not automatically an owner of the task/voice's execution. Existing task groups, GPU submissions and playback own their work/resources as specified.
2. **Fallible acquisition scopes are ordinary calls.** Files needing close-error observation, temporary paths, terminal mode, interactive processes and transactions use acquisition callbacks. Existing fully completed helpers such as `Path.copy_to`, `Path.write_bytes`, `run` and `capture` remain the shortest path. No safe bare fallible writer is exposed that can silently lose a required completion failure on normal drop. A wrapper owns its resource and lends it with `@`; the callback cannot move it out, return a borrowed view or let a child task outlive it. Acquire inside a task, or join tasks inside the callback.
3. **Both failures survive.** A normal callback result is withheld until completion. Success + completion failure returns that failure. Body failure + completion failure returns ordinary `CleanupError[primary=E cleanup=F]`; repeated failures nest in attempt order. `none` is success; another exception-valued outcome is failure. Errors inside a successful record/array are data. All initialized resources are attempted; first error does not skip close/rollback/other resources. Failed completion destroys a withheld owning success result instead of leaking it.
4. **The pair is explicit in the result type.** Ordinary `or_throw`, `match`, `??` and main reporting handle it. No hidden cause list is appended to arbitrary nominal errors. A bare FileError arm does not match the pair. A paired Canceled is an ordinary CleanupError with Canceled retained in primary; it is failure, not cancellation-normal shutdown or Ctrl-C exit 130. Default diagnostics show safe kind/message information for both causes, bounded in depth. Full payloads stay private unless ordinary debugging requests them.
5. **Timing uses the existing call statement.** A local borrowed place unlocks at its last use, not its enclosing brace. For a critical region, write `operate(@(m.lock()))`; the lending method's guard lasts through the entire call, including a tail action after the helper's final field read. A helper's own defer completes before that call returns and the lock releases. A discarded unused drop guard is not a region and is not recommended. No dummy read or general keep-alive primitive is added.
6. **Channels own sending/receiving capabilities separately.** `channel<T>(n)` and `mpmc<T>(n)` return `[Sender<T> Receiver<T>]`, each move-only. Consuming `.split` duplicates a multi-producer/consumer capability into two owners; it does not leave a root owner behind. Last sender (including outstanding sending permits) releases => buffered values drain, then `Closed<T>`. Last receiver releases => senders wake with `Unsent<T>` retaining their payload. `spsc` keeps its unique existing endpoints. Closing one producer does not close its siblings. A consciously retained sender can still keep a stream open; there is no universal distributed-termination proof.
7. **Defer is an ad hoc action, not a resource protocol.** It runs once, LIFO, on leaving its immediately enclosing executed block, before local owners; it retains variables it reads. Its residual summary must be non-failing void, with no escaping return/break/continue/or_throw/panic/exit. Explicit local handling is allowed if the resulting action satisfies that contract. `defer printl"done"` and a one-off flag reset qualify. Mandatory library safety must not depend on callers writing either one. No compiler can infer arbitrary forgotten program intent; an unused-result diagnostic is not a general missing-defer proof.
8. **Cancellation has no silent cleanup shortcut.** Existing defers/drop hooks keep their 100 ms shielded cleanup policy, including captured owners in a task canceled before it starts. Ordinary scoped completion first runs normally. If it reaches Canceled, resume its remaining phase state under existing `protect_from_cancel(100ms @finish)`; a scoped API's `timeout=` changes that cancellation-cleanup grace only. Normal completion has no invented 100 ms cap; an explicit surrounding within still applies. Independent scopes can add grace budgets. Deadlines cooperate and join; they neither detach work nor certify a slow foreign release completed on time. Do not advertise a task-wide 100 ms upper bound. A timeout/failure does not skip nonblocking local release or erase an earlier error. The continuation algorithm below supersedes round 2's always-shielded prototype.
9. **Panic and process exit have a different result boundary.** Sequential callback epilogues do not resume after compiler-controlled panic/exit. Their raw owner's verified/trusted non-failing backstop must attempt bounded emergency release and report unfinished output, uncompleted rollback/restoration/removal or native release failures. It cannot quietly treat abandoning a buffer as success. An adapter unable to supply that backstop is not a safe scoped resource. The resulting abnormal termination has no ordinary success result to return; normal success always observes fallible completion as values. Forced kills, power loss, foreign longjmp/fault and forced third Ctrl-C have no cleanup guarantee.
10. **Aggregates and moves retain established rules.** Structural records/arrays own their elements, initialized prefixes unwind on construction failure, outer hooks precede reverse field cleanup, and array elements drop in reverse order. Returning an infallible owner or putting it in a once-run task transfers cleanup. Breaking a loop cleans only crossed scopes, with liveness deciding any outer owner release; a loop backedge prevents an unsafe early move. A fallible file collection must have its own scoped owner/finalizer, which attempts every initialized file and composes failures; it cannot pretend an array of void destructors observes flush errors.

## Dogfood review and final repairs

The final scores and line-by-line comparisons are in dogfood.md. They are a single author's paper review, not independent reader results or execution evidence.

- **File copy, program 01:** ordinary named callbacks plus a borrowed context express two live streams with no owner-capturing generic closure and no error-erasing void callback type. EOF returns to the read acquisition, then the output acquisition flushes and closes. A destination flush failure is visible on the main expression without another completion call. This costs more function structure than Python's two with managers. Existing `Path.copy_to` remains the common unmodified copy.
- **Whole-region mutex, program 04:** a tempting local guard dies before the tail I/O. The existing lending call already pins it to the whole helper call. Added no language mechanism. The flag-reset defer inside the helper illustrates the narrow residual use; a reusable state protocol would own the reset itself.
- **Terminal Ctrl-C, program 05:** OS raw mode normally disables signal generation. Added an explicit library `signals=true` option so this program really receives default SIGINT cancellation. With signal generation disabled, Ctrl-C is byte 3 and must be handled as input. The final wrapper restores the precise prior state and reports restore failure rather than suppressing it.
- **Cancellation, program 07:** an owning capture cannot be passed through an ordinary reusable partial function handle as though it were a one-shot callable. The actual once-run spawn lambda takes the owner. The parent consumes expected child Canceled at wait, then checks its own cancellation separately. No new generic once-function type.
- **GPU/audio, program 08:** setup-local assets cannot be assumed to live across an engine callback after main returns. An explicit state record is borrowed for the engine call. GPU fence retention and playback-owned sample references prevent early destruction and preserve D11's dropped observer behavior.
- **C wrapping, program 09:** replaced the initial curl pilot. C void cleanup can invoke callbacks or perform protocol shutdown, and exporting raw handle fields permits forged owner construction. PCRE2 with its default allocator supplies a smaller real release contract. Its owner is privately captured in a move-only callable; the nominal helper is local to the factory. This relies on local nominal declarations with ordinary hooks, a lexical capability now confirmed absent by reader-source inspection. The proposal explicitly extends the existing local type declaration to closed nominal lifecycle records. The exact existing failure and bounded addition are below. This is a stated implementation dependency and completeness floor, not hidden passing evidence.
- **Transaction, program 10:** distinguish a failed commit from proof of successful rollback. Driver uncertainty becomes an explicit application error (`CommitUnknown`), and a still-active transaction is rolled back before returning. A failed rollback is paired. A generic `errdefer` would not make this policy automatic.
- **Collection, program 12:** the final comment now says loop break does not itself set the aggregate's lifetime. Last-use analysis still applies. No fabricated rule that every outer array waits to the function brace.
- **Library composition, program 13:** the generic callback's actual result is inferred before overload selection. Coercing a failing final expression to a contextual void callback would erase precisely the error this design intends to preserve. Its signature must not do that.

All final sub-5 grades are cited to source lines. The remaining 4s reflect indirect completion/timing, callback structure and its control-flow boundary, deliberate error pairing/cancellation classification, raw-terminal details, scheduler/driver dependencies and the not-yet-implemented lexical C-helper capability. A syntax/library iteration within this brief does not honestly turn those into all-5s. The three-round limit ends here.

## What is new, including the uncomfortable parts

- **Library behavior:** ordinary resource hooks on standard values; ordinary scoped acquisition functions/overloads; move-only channel endpoints and consuming split; CleanupError and recursive safe reporting; the terminal signals option; material-cost warnings for finalizers, atomics and retained GPU storage. Examples' db/game modules are illustrative application APIs, not new promised standard modules.
- **Semantic change:** defer's non-failing, no-escape residual contract. It requires David's acceptance; this is not described as a previously decided rule.
- **One definite compiler capability addition:** support the existing local declaration form for a closed nominal lifecycle record. The current reader rejects this; the source-inspection addendum below gives the precise failure, counterexamples and minimal scope. This is not passed off as only library work. More generally, safe wrappers need actual encapsulation, not an assumption that nominal means opaque. No new keyword is proposed.
- **Implementation work:** prove checked callback nonescape using existing @/call summaries; infer callback results without contextual error erasure; supply real no-fail abnormal-exit backstops; preserve queue permits across last-sender closure; validate reachable concrete lifecycle summaries; expose costs at acquisition. This is not a zero-work library rename.
- **No additions:** cleanup grammar, with/using/inline blocks, pin/unpin, new effects, hidden throwing destructors, errdefer, mandatory explicit-consume types, arbitrary intent inference, or a background cleanup service.

For each addition, the existing-construct comparison is explicit: a void drop cannot produce a finalization result; an ordinary callback can; a shared bidirectional channel cannot identify its last sender; independent owning capabilities can; an unused guard cannot define a region at last-use; an existing lending call can; public raw fields do not give abstraction safety; a private owner capture and a lexically hidden helper can. There is no justification here for inventing new syntax.

## Exact D4 changes

1. `ticks_with_autosave`: delete `defer tick.stop()`. Drop of the timer cancels its registration at the last `tick.next` use or an earlier exit. Keep `saver.stop()` when it means an intentional early task stop; timer ownership does not own saver.
2. `fetch`: delete `defer net.tcp_close(stream)`. The returned TcpStream owner releases the OS descriptor after the final receive/use or on any earlier exit. Keep `output.write_bytes(response) or_throw` as the checked output completion operation.
3. The completed-output reporter: acquire `let [tx rx] = channel<Path>(4)`. Move `rx` into progress and `tx` into a named producer helper taking `Sender<Path>`. That helper's return drops the sender before the parent waits for progress. Join progress before the entry function ends when its reports must finish; last-sender close alone does not imply the reporter finished, and BackgroundTasks shutdown may otherwise cancel it. No `defer completed.close()` and no retained shared root.
4. Update D4's other chat/command examples to consume independent producer and consumer endpoints; ordinary returns replace producer `close()` lines. Preserve existing select type-qualified outcomes and Unsent.value semantics. Include permit ownership in reserve/send prose.

LANGUAGE.md touchpoints are the inventory in round 1 plus a concrete section describing the new scoped API contracts and their timeout= cancellation-grace meaning. Existing defer references in default/drop effect summaries (around 913), refinement rejection rules (1391,1433), move/capture liveness (2193 and 3999) remain meaningful for the retained one-off construct; keep them, with links to its new non-failing contract. This is not a global search-and-delete of the word defer. Remove legacy defer examples without globally renaming unrelated APIs. ownership.md retains no-fail hooks, existing cleanup order, liveness and moves. decisions.md's batch-7 temporary cleanup direction changes only after approval. Do not rewrite earlier proposal rounds; no open_decisions.md item or new syntax name has been added by this read-only subtask.

## Cost and implementation gates

Full details: contracts.md. A scalar owner adds its known release, not a mandatory allocation or virtual call. Channel endpoints add capability accounting; task-shared counts can be atomic and waking waiters can lock. Arrays clean O(live elements). Scoped acquisition adds a direct callback, a cancellation-path finalizer shield/deadline, phase state and union result; failure trees may allocate under the existing allocation policy. GPU/audio physical release can be deferred and retain memory. Normal success need not allocate an error tree.

Report material costs where the user acquires the value: possible blocking cleanup, default/explicit cancellation-finalization grace and additive budgets, unknown foreign waits, significant shared counts/retained memory. Existing strict cost/proof lanes reject unadmitted allocation/opaque claims. Do not mark a C void function nonblocking just because its result is void. No performance timing is claimed; no machine tests are launched. A later implementation must run focused and quick gates, then full/bootstrap/fixed point for its batch, and the flagship instruction-count panel before landing a new analysis.

Compiler validation is demand-driven at reachable lifecycle/call obligations, cached by concrete type/function instance with indexed owner/place state. Reuse existing bounded liveness and no-escape checks. Container cleanup is generated linear traversal, not a new solver per element. Do not add a general whole-program inference pass for missing side effects or arbitrary reference cycles in the name of removing defer.

## Rejected alternatives remain rejected

Round 1 compares defer, `defer <expr> {...}`, Python with, Swift/Go defer, Zig errdefer, Rust RAII, C#/TypeScript using, must-consume types, fallible drop effects and a generic on-exit guard. Nothing found in dogfood makes new cleanup syntax necessary. Python/C#/TypeScript's ability to keep early return in the surrounding function is better than this callback boundary; that is honestly scored. They still require per-acquisition context/disposal opt-in, which this proposal puts inside the acquisition API.

## Names and readiness

names.txt lists proposed public names/overloads and separate illustrative spellings as usage examples. David's discussion notes were consulted and the final proposed names were searched there; **they have not had three fresh cold readers**. This is a completed design subtask and a packet for that review, not a claim of a cold-tested, approved decision. No files outside this directory were written and nothing was committed.

## Source-review addendum: the local C-helper dependency is real

A final read-only source check resolved the earlier uncertainty. `compiler/dewy_reader_seed.jo:6544–6557` explicitly leaves local nominal declarations unread, and 5848–5856 rejects local methods; `compiler/dewy_reader.dewy:6847` has the same diagnostic. The existing fixture `tests/cases/object/local_type.dewy:2` / `.err:1` records “methods on a local type; declare the type at module level.” This is source inspection, not a test execution.

Trying the existing forms first exposes the exact problem:

```dewy
# Existing local plain record: no drop hook, so not a self-cleaning C owner.
let Code:type = [handle:ptr<uint8>]

# Existing module nominal record: can own cleanup, but a public raw field and
# constructor are not a safe encapsulated interface merely because nominal.
Code = type of [handle:ptr<uint8>
    $__drop__
    release = ():>void => $unsafe pcre_free(handle)
]
```

For the small library-author case, the minimal addition is to accept the existing local declaration form with a closed nominal lifecycle record, as program 09 now writes `let Code:type = type of [...]`. Its hook reads its own field and calls the module extern; it captures no runtime local. Mint one nominal identity at compilation per lexical declaration/concrete generic instance, not at every function invocation. Reuse ordinary hook checks and private, owning closure captures. This adds no token/keyword, no general privacy syntax, no generative runtime type, no heap guard and no new liveness analysis.

This is additional frontend capability, explicitly requested by the design and gated like other compiler work. It is not already supported and no program is claimed to compile. If David prefers not to expand local declarations, the cleanup verdict and standard ownership/callback split still stand; the general C-wrapper author case then remains an unsafe adapter until a separately approved encapsulation route exists. The final recommendation includes this small capability, with completeness 4 for its unimplemented state.

## Final cancellation correction: no normal-path 100 ms cap

Round 2's simplest wrapper always called `protect_from_cancel(100ms @finish)`. That has a fixable defect: a successful uncanceled file copy can acquire a surprising 100 ms flush deadline. Existing result values, phase state and protection already let the library avoid it. This is a third-round correction, not a new compiler primitive.

```dewy
let result = body(@owner)              # a value; no premature or_throw
let attempted = finish_steps(@owner)   # real failures recorded in owner state
if attempted is? Canceled {
    let protected = task.protect_from_cancel(timeout @finish_steps(@owner))
    let resumed = collect_finish_result(@owner protected)
    if result is? exception {
        if result isnt? none return combine(result resumed)
    }
    return combine(Canceled resumed)
}
return combine(result collect_finish_result(@owner attempted))
```

`finish_steps` is an internal resumable phase runner; it records progress and real errors in its owning state and returns void when its phases finish, or Canceled at a safe pause. `collect_finish_result` folds the recorded errors plus a boundary failure such as Timeout after the protected call has joined. Thus a deadline cannot overwrite a real flush/close error that the inner call already recorded. The collector consumes/drains its ledger once, so the same error is not added twice. Both helpers are ordinary adapter implementation functions over fields/values, not new public APIs or compiler-recognized hooks. Canceled means “pause remaining finalization and enter cleanup grace,” not “silently abandon this still-owned resource.” Resuming continues only unperformed phases; collection then returns all recorded real completion failures; it never retries a close that may have taken effect. Success on a fully finished state is idempotent. There is no invisible cancellation exception or new public resumable-resource protocol.

If the body already failed (including Canceled), keep that primary failure and combine it with the resumed completion result. Do not turn the same ambient cancellation into a spurious pair of two Canceled values. If the body succeeded but completion was canceled, Canceled becomes the primary outcome even when shielded completion succeeds: catching cancellation for cleanup must not turn a canceled operation into normal success. A real flush/close failure plus that cancellation is still a pair. This also handles `none` as a successful body result.

`timeout=100ms` on these scoped APIs now means cancellation-finalization grace **only**. A normal slow flush is not capped. Use existing `within(5s @files.open(...))` for a deadline over the whole operation; that deadline can still be followed by cleanup grace. An explicit larger timeout permits longer cleanup after cancellation. This reused spelling still needs a clear signature and receives a discoverability 4. No new timeout name or setting is introduced.

The actual adapter must be resumable at safe cancellation points. If it cannot meet that internal contract, it cannot use this runner; expose its uninterruptible wait/cost and join it rather than detach it. Remaining completion steps run despite earlier errors, and the final returned result includes every real recorded failure. A timeout of the resumed operation still reaches the raw owner's emergency release/reporting path. The default grace is cooperative and per finalized scoped operation, not a task-wide join bound.
