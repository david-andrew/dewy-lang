# Round-6 paper programs

These 19 files are full-function design scenarios, including intentionally bad before-versions. They are **not runnable fixtures** and were not compiled. A suffix on a scoped loop body has the proposed round-6 semantics, not a claim about today's parser. File names and line numbers are stable inputs to dogfood-round6.md.

## Reading and grades

Read the corrected/recommended version as the proposed idiom; before-versions are counterexamples, not promised accepted programs. File 08's before-version must be rejected by the new marker rule. Files 02, 06 and 10 deliberately show waits that can hang under block-end timing. Do not run them against real services. No window, network service, audio, benchmark or compiler was launched for this packet.

Ownership/type signatures follow the surrounding Dewy proposals: by-value owner parameters move where permitted; an `@` parameter receives a place; `@f` denotes a handle; a once-run task lambda may move captures. A normal value-returning zero-argument call omits parentheses. A side-effect operation with success result `void` keeps `()`, including a fallible close/commit whose other alternatives are exceptions. Hooks are assigned functions, never tags before an ordinary method. No SQL examples or format-specifier interpolation is used.

Some APIs are deliberately illustrative. These contracts are assumptions for reading the examples, **not shipped libraries, approved names, foreign ABI verification, or requests to add names**. Imported `*_case.dewy` modules below are documentation placeholders and are not supplied as implementations. Standard files/net/task APIs also depend on the accepted designs being implemented. Completion grades assess the specified scenario, with gaps called out per row; they do not certify production packages.

## Contracts needed by each scenario

| Files | Required contract |
|---|---|
| 01 | `Mutex<Ledger>.lock` lends the ledger and keeps an infallible guard. `Path.append_text` completes its own file before returning. Journal I/O is intentionally protected. |
| 02, 07 | `socket_case.connect` returns an owning stream with infallible local release. `send` borrows it and can fail. Release signals EOF; `wait_for_upload_status` cannot finish until EOF. Conversely `apply_side_channel_update` requires the stream session still alive. These are two different service protocols, chosen to expose both timing mistakes. |
| 03, 08, 09, 11, 12, 19 | `files.open` returns a buffered File. Writes may be accepted before flush; close/implicit completion consumes the resource and can return FileError. `Path.read_text` and whole-value operations finish their own resources. A failure is not rollback or durability. Explicit close consumes even on failure. |
| 04 | `ticker_case.every` returns a source owning an active timer/queue; `next` waits for one tick; infallible release stops the timer. `compute_report` takes appreciable work but does not use the source. `terminal.raw` returns a restoring owner; terminal reads operate on the ambient terminal, so mode has no later source read. Restore can fail. |
| 05, 06 | `source_case.socket` and `.file` expose the same borrowed `read_bytes`; socket release cannot fail, file release can. `Pair` owns one of each and has no extra outer hook. A reader lambda owns its capture, borrows it for each call, and may be called repeatedly; its return byte array is independent of the stream. `wait_for_reader_eof()` waits on an external service's EOF observation. `show_sizes` is a non-failing void observer. |
| 10 | Spsc endpoint destruction closes its direction; receiver drains before Closed. `app.spawn` takes the once-run receiver capture. `reporter.wait` returns its completed result and joins real task cleanup. Cancellation may abort draining. |
| 13 | `render_case.Tree` has a label and finite children; `draw(label depth)` can return a render error. Comparison is within an application depth limit that prevents arithmetic/stack overflow. No generic recursion safety claim. |
| 14 | `Request` and `Response` have no cleanup duties. `serve(request)` returns ordinary success/exception/cancellation values and finishes its own locals. `clock.now` is non-failing. `metrics.observe(duration)` is non-failing, nonblocking, void, and writes a bounded in-memory metric, not a possibly failing log file. |
| 15 | `Editor` is task-confined mutable state; the caller passes its place. `paint(@editor row)` may fail and consults the busy flag. Changing that flag and restoring a saved bool are non-failing. No global synchronization is inferred. Reentrant use must restore the prior value, never blindly false. |
| 16 | An illustrative foreign renderer exposes process-global get/set diagnostics plus render. The same host mutex serializes **all** calls, including any allowed reentry policy; foreign code cannot bypass it. Get/set restoration is trusted no-fail/no-alloc/no-block; render may return an ordinary error or participate in supported host unwinding. Raw longjmp across Dewy frames is excluded. The bindings/trusted contracts were not verified against a real C library. |
| 17 | Shared Channel is bidirectional; total handle count cannot infer end-of-sending. `close()` is infallible and idempotent; one coordinator closes after its joined producers end. Removing that protocol action can hang a consumer retaining its own handle. |
| 18 | `db_case.begin` returns the library's transaction; methods debit/find_account/credit/commit illustrate native operations. `find_account` may return none. Commit consumes. `db.rollback(handle)` is the raw operation behind the illustrative assigned abandon hook and may fail. The shown Transaction type demonstrates hook form, not the exported implementation of begin or a safe public raw-handle wrapper. |

## Expected checks, not executed tests

- Every initialized owner finishes exactly once, unless moved into another live owner or successfully handed off.
- Before/after timing traces: locks, sockets, file readback, ticker retention, generic instances, captured owners, branches, loop bodies and unscoped parallel bindings.
- Local-exit markers: fallthrough, break, continue, labels, explicit return, no-owner scope, consumed-before-jump paths, and collector body values.
- Fallible close never inserts an error into a collector as ordinary data. A failure of pending cleanup prevents that body's success result from being published.
- Result-capture versions preserve Canceled without `??`, and distinguish ordinary results from panic/exit unwinding.
- No multi-error record spelling is assumed. D40 Q3 owns representation, extraction and cancellation-carrying inspection.
