# Cleanup round 9: written cleanup

A delta over [round 8](round8.md), after the [review](review-round8.md) and
[David's response](answers-r8.md). Programs: [programs-r9/](programs-r9/README.md).

## Summary

1. David's direction holds up, with one design: **implicit cleanup can't fail; cleanup that can
   fail is written, and the compiler checks that every exit accounts for it.** Call it (g).
2. What a value owes is part of its type, fixed where the value is made: a file opened `'r'` owes
   nothing, `'w'` owes its flush, a connection owes its sending side's finish. This closes the
   review's written-socket hole (program 05) without flow-sensitive typestate.
3. Unfinished work left unaccounted for is a compile error; leftovers (a temporary file or
   directory not removed) are a warning with a squiggle; `$no_discarded_failures` (D44 Q7) makes
   both errors. What can't fail never appears.
4. The usual way to account for a value is **one `defer` under it**. It covers every later exit,
   failure exits included, so linearity costs a line per value, not a line per exit. A move or a
   consuming call turns it off on that path, which makes a deferred rollback Zig's `errdefer`
   with no second keyword.
5. David's error stack built in one `defer` has an ordering bug (a later acquisition failing
   leaves the earlier values unhandled) and needs a `return` that replaces a failure already
   leaving. **One `defer` per value, folding automatically,** does what it meant (program 13).
6. Defers run **after the exit's value is computed, before leaving**, in reverse, all of them.
   A deferred `or_throw` adds its failure to what leaves; a defer can't change a success value.
   It passes David's nonlocality test: every defer that can change the outcome says `or_throw`
   on its own line, in the scope it affects.
7. Folding: **one failure comes back bare; several come back as an `ErrorStack`**, in the order
   they happened. Types stay small and the order is kept.
8. **D42's automatic joining is withdrawn for cleanup**: a cleanup failure joins only where a
   written line says so. It costs 12 lines over 13 programs, mostly in constructors, and it is the
   reversible direction: automatic joining can be added later without breaking a program.
9. Graded 1–5 on all 13 programs: 60 of 65 grades are 5. The 4s are three repeated abandons
   (the forgotten-commit check's price), a one-expression constructor, and generator drops.
10. The survey errors the review found are corrected below; none of them changes the
    recommendation, and two (Mojo, errcheck) now support it more directly.

## Recommendation

Adopt (g) for D40 Q1 and the explicit form of D42:

1. **Releases never appear.** Their cleanup can't fail and is never written.
2. **What a value owes is in its type**, fixed at construction (mode, or a consuming method that
   returns a new type, such as `finish_sending()`). Records, arrays, closures and generators owe
   what they hold.
3. **Every exit accounts for every owing value**: finished or moved on that path, or covered by
   a `defer` above it. Unfinished work: error. Leftovers: warning. Strict tag: both errors.
4. **Unpublished work** (`$__abandon__`) is decided at every success exit; a `defer` may only
   abandon it.
5. **`defer`** is scope-tied, runs after the exit's value, in reverse, all of them; it can add a
   failure (`or_throw`), handle one (`??`) or discard one (`;`), and can't `return`, `break` or
   change a success value.
6. **Folding**: one failure bare, several in an ordered `ErrorStack`, `Canceled` outside it.
7. **No automatic joining** of cleanup failures (D42's cleanup clause withdrawn).
8. **Parameters** keep round 8's rule 7; **generics, generators, tasks, race losers and hooks**
   follow "Compile-time rule" below.

The scope marker `} or_throw` from rounds 7–8 is not needed and is dropped: a `defer` in the
loop body answers D40 Q6, and one way is better than two.

## 1. The review's findings

### 1a. The written-socket hole: finishing versus releasing in the type

The review's point: round 8 classed every socket close as a release, but a socket that has sent
bytes has a buffer, a TLS `close_notify` and linger, so its finish is completion work. And one
`File` type for `'r'` and `'w'` can't carry the check. Three designs:

| | Separate types at construction | Typestate by flow | Split halves |
|---|---|---|---|
| How | `files.open(p 'r')` gives a `FileReader`, `'w'`/`'a'` a `FileWriter`, `'rw'` a `File` that owes as a writer; a `Socket` owes its sending side from the start; `conn.finish_sending()` consumes it and returns a `SocketReader` | `conn.send` moves `conn` from "nothing pending" to "must finish" | `let (input output) = conn.split()`; the writer owes, the reader doesn't |
| Borrowing helpers | nothing new | `send_all(@conn …)` must declare in its signature that it changes `conn`'s state | nothing new |
| After `if c conn.send(x)` | already owed | "maybe": owes anyway | already owed |
| Generic code | sees it in the type | must carry states | sees it in the type |
| Adding a line | can't change what is owed | can, far below the line (round 8's iteration 5 objection) | can't |
| Checker | round 7's per-exit liveness | flow typestate on every owner | per-exit liveness |

**Picked: separate types at construction**, with split halves as a library convenience for
sending and receiving in parallel (it is the same idea applied to a duplex value). Typestate is
rejected for the review's own reason: the verdict would depend on lines far from the exit.

Two consequences, both in [programs-r9/README.md](programs-r9/README.md)'s library model:

- **A connection's abandon is an abort**, a release: on a failure exit no `close_notify` is sent,
  so the peer sees a truncation, which is what a failed upload should look like. Its success
  exits must finish it, like any unpublished work. Program 05 now reads the server's
  acknowledgment too, because a successful `close` doesn't mean the bytes arrived.
- **A library type owes only for output its peer hasn't confirmed.** `db.scan` reads the server's
  reply before handing out the cursor, so the cursor holds a `SocketReader` and David's
  `first_row` still writes nothing (program 03). A bulk-insert stream would owe.

Program 05 under (g): `input` writes nothing, `conn` gets `finish_sending()` where the sending
ends, and `receipt` gets one `defer`. Forgetting the finish is an error naming the sending side.

### 1b. Citations corrected

| Round 8 said | Corrected |
|---|---|
| POSIX releases the descriptor whatever `close` returns, and it must not be retried after `EINTR` | That is Linux. The Linux `close(2)` page says POSIX.1-2024 standardized the HP-UX rule (after `EINTR` the descriptor may still be open) and that Linux doesn't conform. |
| Only the write side's close errors are actionable | Round 8's gloss. The man page says a close error may report an earlier failed write ("especially … with NFS and with disk quota"), and that a successful close doesn't put data on disk (`fsync`). |
| Every deterministic-destruction language made release infallible, including C#'s guidelines and Haskell's convention | True of Rust, C++ (`noexcept` destructors) and Swift (`deinit`, `defer`), and of Zig's `defer`. C#'s is advice: `Dispose` may throw, and `using` is written. Haskell's `bracket` release can throw. None of them split release from completion: they made the destructor unable to report and then flushed inside it anyway. |
| GHC 9.10 keeps the first exception as context (`WhileHandling`) | `WhileHandling` came with GHC 9.12's exception-context work (the review cites Well-Typed, "Exception Annotations", 2026). In 9.10 a throwing release replaces the body's exception. Under `WhileHandling` the release's exception is primary and the body's is context: the opposite of Java's suppressed. |
| Python converged on keeping both, with `ExceptionGroup` for several | A raising `__exit__` becomes the exception that propagates, with the body's as `__context__`. `with` never builds an `ExceptionGroup` (PEP 654 is `except*` and `TaskGroup`). The data model says an exception in `__del__` is ignored and a warning printed to `sys.stderr`; "Exception ignored in" through `sys.unraisablehook` is CPython's mechanism. |
| errcheck excludes read-side `Close` because its error isn't actionable | `errcheck`'s default exclusions don't include `Close`, and its maintainer argued that `Close` on a written file must be checked (issue 101). golangci-lint's default EXC0001 hides `.*Close` and `.*Flush` together, read or write, and projects such as restic and Gitaly turn it off for hiding close errors. |
| Vale and Mojo: the compiler forbids implicit destruction | Mojo's default is implicit destruction. Linear types are opt-in: `@explicit_destroy`, or leaving out implicit destructibility (`not Deinitable` / `ImplicitlyDestructible`, depending on the version), and a value never destroyed is a compile error. The decorator takes a message, e.g. `@explicit_destroy("Must call save_and_close() or discard()")`. Vale's "higher RAII" is a design article, not a checked rule here. |
| Austral, Linear Haskell: every path must consume | Austral yes. Linear Haskell is opt-in, per arrow. |
| Rust rejected linear types entirely because of unwinding | Unwinding is Beingessner's main argument; `mem::forget` and leaks are separate ones. |
| None regrets it for readers, sockets or locks | Withdrawn: not evidence, and wrong for sockets. Rust's own `BufWriter` example wraps a `TcpStream`. |

What still stands: Rust's `File` and `BufWriter` drop ignoring errors, `sqlx`'s silent rollback,
Go's bare `defer f.Close()` dropping the error, Zig's `return`-free `defer` and `errdefer`,
Swift's non-throwing `defer` and SE-0390, Java's suppressed exceptions (JLS 14.20.3), C#'s
replacing `Dispose` failure, Guava's reader/writer split in `closeQuietly`, Linux `close(2)` on
NFS and quota.

Mojo's opt-in now argues *for* (g): it is the closest shipped design, and its custom message is
the same idea as (g)'s errors that name the finishing call. errcheck's maintainer and the
projects turning off EXC0001 argue for checking writer closes, which (g) does.

### 1c. The compile-time rule and its cost

**The rule.** At each exit edge of a body, every live value whose type owes must be consumed on
that path (a finishing call, a move) or covered by a `defer` registered on that path. At a
success exit, a value with `$__abandon__` must be consumed. A body is a function, a block, a
loop iteration, a lazy body, a task body or a hook.

**Data it needs.** Per concrete type: what its cleanup can fail with and how strongly it is owed,
computed from its hooks and fields and cached with the type's lifecycle facts (ownership.md
already caches "needs cleanup" per type). Per body: the cleanup plan the compiler already builds
to emit scope exits lists the live owners at each exit with their drop flags. A registered
`defer` is one more flag per path, cleared by the same consuming call or move that clears the
drop flag.

**Cost.** O(exits × live owing values) per body, over a plan that already exists. It is
demand-driven: a body that holds no owing value does no work, and most bodies hold none.
Nothing has measured it; it should be checked on the flagship panel when it is built.

**Generic code.** Each generic body gets a one-bit summary per type parameter: "may drop a `T`
on some exit without accounting for it", computed once from the body. Calling such a body with a
`T` that owes is an error at the call, naming the line in the body. A body that accounts for its
`T`s (`defer drop(x) or_throw`, or returning `drop(x)`'s failures) accepts any `T`; for a `T`
that owes nothing, `drop` is a no-op and the `defer` compiles to nothing. The check runs once per
generic body, not once per instantiation, and doesn't assume monomorphization. The standard
containers account for their elements: operations that drop elements (`clear`, `truncate`) give
back the elements' cleanup failures, `void` for most types; overwriting an owing element is an
error offering to finish the old one first.

**Generators.** A lazy body is a body. Each suspension point is an exit where the consumer may
drop the generator, and the body's defers registered there run then (batch 11 already says this
for a non-failing `defer`). The generator's cleanup type is the union of what those defers can
fail with, and its inferred type carries it. A declared `generator<T>` parameter follows the
generic rule: a body that doesn't account for it accepts only generators that owe nothing
(programs 03, 08).

**Closures** owe what they capture by move, as records owe their fields. **Tasks**: a value moved
into a task body goes with it; a borrowed capture stays with the lender, whose scope outlives the
group. **Hooks**: a `$__drop__` or `$__abandon__` body owns the value's fields, may consume them,
and is checked like any body (program 11).

**Race losers.** No new analysis. A loser is canceled, which is a failure exit; its defers run
and their failures fold into its result; `race` and `first_ok` discard that result whole, except
an `UndoFailed` (D44 Q6), and `$no_discarded_failures` forbids the discard (D44 Q7). The check
reads the loser's result type: O(1) per call. The review's case, a loser's writer flush lost with
its result: the half-written file is there whether or not its flush failed, so the flush failure
adds little; raced writes should go through a temporary file, whose abandon removes the partial
output (program 10). A lint for a final-path writer inside a raced body is outside this round.

**Panics.** Defers run during unwinding. A defer's failure during a panic is reported with the
panic, since a panic isn't a value to fold into.

## 2. Several resources whose cleanup can fail

Program 13 writes David's `somefn` five ways. The short version:

| | Text for three writers | Every close runs | A body failure kept | Earlier values covered if a later open fails |
|---|---|---|---|---|
| A. One `defer` building the stack (David's sketch) | 7 lines | yes | only with new syntax to name the leaving value | **no**: compile error at the second open |
| **B. One `defer` per value** | 3 lines | yes | yes | yes |
| C. Closes joined at each exit (`errors.Join`) | 1 line per exit, plus B for failure exits | yes | yes | needs B |
| D. One marker for the scope | 1 token | yes | yes | yes; no line says which values |
| E. One owner for all (`defer drop(outs) or_throw`) | 2 lines | yes | yes | only once all are in it |

**Recommended: B.** It is what A meant, with each value's handling registered when the value
exists. The folding happens because every defer runs; a deferred `or_throw` adds to what is
leaving rather than leaving early. A stays possible for a function that wants a custom fold, as
plain code inside one `defer`, minus the `return`.

**One failure or always a stack:** one comes back bare, several as an ordered stack. A handler
for one kind then takes the common case, and the result type is `T | E1 | E2 |
ErrorStack<E1 | E2>` rather than D42's 2ⁿ combinations. Always a stack would make every caller
handle `ErrorStack[FileCloseFailed]` for a single failed close.

## 3. When `defer` runs

David's rule: after all regular computation, just before the actual return, and a failure may
replace the returned value. Generalized to scopes: **a `defer` runs when its scope is left, after
the exit's value is computed**: a function's return value, a block's value, or the jump decided
by `break` or `continue`. Program 13's table compares Go, Zig, Swift, Java `finally` and Python
`__exit__`. In short:

- **Go** has the same order but ties defers to the function, so a `defer` in a loop waits for the
  function's end, and changes a result through a closure assigning a named result: arbitrary code
  rewriting a variable. (g) ties defers to scopes and lets a defer *only add a failure*.
- **Zig and Swift** forbid failing defers, which sends fallible cleanup back to explicit calls at
  every exit (round 8's (f)). **Zig's `errdefer`** falls out of (g) without a keyword: a value's
  `defer` is off on any path that consumes it, and unpublished work must be consumed on every
  success path.
- **Java's `return` in `finally`** replaces even a failure already leaving; **Python's
  `__exit__`** can suppress one. (g)'s defers can do neither: a failure already leaving always
  stays.
- **Before the return expression** would break `return finish(@out)`.

**Against David's nonlocality criterion** ("plain code in the ordinary control flow, so nothing
feels nonlocal"): a `defer` runs away from its line, so the test is whether the text predicts it.

1. Every defer that can change an outcome has `or_throw` on its own line, in the scope whose
   exits it affects; the rest can't change anything.
2. The defers live at an exit are exactly those written above it in enclosing scopes, for values
   not yet consumed: a lexical rule, the same everywhere.
3. A defer can't change a success value, return, or swallow a failure, so the only nonlocal
   effect possible is the one its line names.
4. What text alone doesn't show: that `return summarize_empty(dir)` may come back as a failure,
   and that a `continue` can leave the function. The editor's hint at each exit ("then: close
   index, json, csv") shows it; Python's `with` has the same property and the same remedy.

It passes, with one rule to learn, which is less than the 11-12 rule asked (a failure from no
line at all) and about what Python's `with` asks.

**Consequence for D40 Q2 (timing).** Fallible cleanup is now always written: a `defer` pins its
value to the scope's end, and a finishing call happens at its line. Block end versus last use
then affects only releases, which can't fail. That shrinks Q2 to observable releases (a lock, Q2's
session example). Q2's recommendation (block end) stands, with lower stakes.

## 4. D42: explicit or automatic folding

Under (g-auto), (g)'s type split and success-exit rules hold, and on a failure exit an
unaccounted owing value is cleaned up by its hook with its failure joined automatically (D42 as
it stands). Each program shows both. The difference, in three programs:

| Program | (g), explicit | (g-auto), automatic |
|---|---|---|
| 01 `save` | `defer out.close() or_throw` under the open | `out.close() or_throw` at the end; a failed write's flush failure joins unwritten |
| 04 `transfer` | `defer tx.rollback() or_throw`, plus the replay's rollback | the replay's rollback only; `Declined & RollbackFailed` from no line |
| 06 `open_pair` | `defer main.close() or_throw` in case `audit`'s open fails | nothing |

Lines added, over all 13 programs: (g) 32, (g-auto) 20. The 12 extra lines are in constructors
that hand their values out (06, 11), unpublished work whose failure exits now need a `defer`
(02, 04, 10, 12), and one borrowing call (09).

**Recommended: explicit.**

- Every failure in a result has a written source, on failure exits too. Program 05's old problem
  (a handler for a failed connect missing it because a cleanup failure joined) can't recur
  silently: a joined failure comes from a line that says `or_throw`.
- A value's cleanup failure can be handled differently from the body's (`defer log.close() ??
  report(…)`), which automatic joining can't express on failure exits.
- The rule becomes one sentence: implicit cleanup can't fail. Under (g-auto) it has an exception
  for failure exits.
- It matches David's stated direction: a value that requires handling is handled on every path,
  as with Mojo's explicitly destroyed types, and the `defer` keeps that to a line per value.
- **It is the reversible direction.** Moving from explicit to automatic later breaks no program
  (the `defer`s just become optional). Moving from automatic to explicit rejects programs that
  compiled.

What remains of D42: the `&` laws, facets and `as` (Q2), the narrow handler rule (Q1), the library
vocabulary (Q3), the stack's name (Q4), the metatags (Q5) and the exit code (Q7) are unchanged.
Q6 changes: several failures from one exit, of any kinds, come back as one ordered stack rather
than `&` across kinds. `&` stays for combinations people write.

## 5. Dogfood

All 13 programs graded 1–5 against Python, Go, Rust, TypeScript and Swift; reasons in each file.

| Program | Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|---|
| 01 buffered writes | 5 | 5 | 5 | 5 | 5 |
| 02 temp file renamed in | 5 | 5 | 4 | 5 | 5 |
| 03 partial read | 5 | 5 | 5 | 5 | 5 |
| 04 transaction | 5 | 5 | 4 | 5 | 5 |
| 05 acquisitions in sequence | 5 | 5 | 5 | 5 | 5 |
| 06 moved owners | 5 | 4 → 5 | 5 | 5 | 5 |
| 07 loop exits | 5 | 5 | 5 | 5 | 5 |
| 08 generators | 4 | 5 | 5 | 5 | 5 |
| 09 own or borrow | 5 | 5 | 5 | 5 | 5 |
| 10 parallel, race | 5 | 5 | 5 | 5 | 5 |
| 11 wrapper type | 5 | 5 | 4 | 5 | 4 → 5 |
| 12 process, scratch dir | 5 | 5 | 4 | 5 | 5 |
| 13 three writers | 4 → 5 | 5 | 5 | 5 | 5 |

### Iterations

1. **11, complete.** Round 8 left hooked types without a finishing method (it needed Swift's
   `discard self`). Letting a hook own and consume its value's fields, checked like any body,
   closes it: `drop(archive)` is the finishing call, and the hook runs once. → 5. This replaces
   round 8's Q3.
2. **02, 04, 12, concise.** Each says its abandon twice: in the `defer` and at an intentional
   early success exit. Tried letting the `defer` cover success exits for unpublished work: an
   early `return` added later silently rolls back or discards, the `sqlx` bug. Tried requiring
   only that the publish appear on some path: misses the same added `return`. Tried, in 12,
   holding the read's result as a value and stopping before forwarding it
   (`let line = …read_line(); tail.stop() or_throw; line or_throw`): if both fail, the read's
   failure dies in a variable. Kept at 4; the repeat is the error's purpose.
3. **06, discoverable.** A newcomer must learn that `open_pair`'s second open can leave with
   `main` open. The error names exactly that at the second open, with the fix. → 5.
4. **11, concise.** `Archive[files.open(…) or_throw files.open(…) or_throw]` can't stay one
   expression. Tried letting a literal's finished fields fold into the failing field's `or_throw`
   on the same line: that is automatic joining inside one expression, and it reopens §4. Kept at
   4; Rust is one expression only because it drops the flush failure.
5. **13, obvious.** The editor's exit hint lists the defers that run at each exit. → 5.
6. **08, obvious.** That dropping a generator mid-stream runs its body's `defer`, and can fail,
   is learned from the error. Hover on the drop site shows it; naming it in the text would need
   new syntax. Kept at 4, as Python's `GeneratorExit` teaches the same thing.
7. **All, concise.** Tried (g-auto) throughout: 12 fewer lines, at the cost of §4's points. Not
   taken; offered to David as the alternative.

60 of 65 grades are 5. No version reached all 5s without bringing back a silent rollback or an
unwritten failure.

## 6. Consequences for open decisions

- **D40 Q1:** replace the recommendation with (g). The `$explicit_cleanup` placeholder isn't
  needed: the strict tag is D44 Q7's `$no_discarded_failures`.
- **D40 Q2:** block end stands; it now matters only for observable releases.
- **D40 Q5:** `defer` stays, and becomes the main cleanup form. It may fail (`or_throw`), which
  reverses batch 9's provisional "can't fail" and batch 11's lazy-body rule; David proposed this.
  It still can't `return` or `break`.
- **D40 Q6:** answered by a `defer` in the loop body (program 07). Options B and C go.
- **D42:** automatic joining of cleanup failures withdrawn; Q6 becomes "one bare, several in an
  ordered stack". Fewer shapes: readers and connections never join.
- **D44 Q6, Q7:** unchanged. A failed temporary-file removal is a leftover, discardable for a
  loser by default; the strict tag forbids it.
- **Batch 9 (`$__abandon__`):** unchanged, plus rule 5 and the abandon-only `defer`; a type
  names its abandoning method by assigning it (`$__abandon__ = rollback`).
- **Batch 11/12 (generators):** a lazy body's `defer` may fail; the generator's type owes it;
  generators Q6 is answered by §1c.

## 7. For David

**D40 Q1.** Turn this on, and implicit cleanup can never fail: closing a reader, aborting a
connection or unlocking says nothing and appears nowhere. Anything whose cleanup can fail (a
writer's flush, a transaction, a running child, an unpersisted temporary file) must be
accounted for on every exit, or the program doesn't compile; leftovers (a temporary directory
not removed) give a warning. The usual way is one `defer` under the value.

```dewy
save = (path:Path data:array<uint8>) => {
    let out = files.open(path 'w') or_throw
    defer out.close() or_throw          # runs after the result, on every exit; a failure replaces it
    out.write_bytes(data) or_throw;
}
```

- **Rec:** yes. **Reversible** before release; making an error a warning later breaks nothing,
  but making a release fallible later breaks callers, so the library's classification should be
  settled before the standard library ships its hooks.
- **Unblocks:** standard-library hook signatures, the checker, D40 Q5 and Q6, generators Q6.
- **You give up:** release errors (a reader's close) entirely; one line per writer; repeating an
  abandon at an intentional early success exit.

**D42 (reframed).** Turn this on, and a cleanup failure joins another failure only where a
written line says so: a `defer … or_throw`. One failure comes back bare; several from one exit
come back as an `ErrorStack` in the order they happened.

```dewy
export_all = (dir:Path) => {
    let csv = files.open(p"{dir}/rows.csv" 'w') or_throw
    defer csv.close() or_throw
    let json = files.open(p"{dir}/rows.json" 'w') or_throw
    defer json.close() or_throw
    …
}   # both closes fail: ErrorStack[FileWriteFailed FileCloseFailed], json's first
```

- **Rec:** yes, explicit. **Reversible:** adding automatic joining later breaks no program; the
  reverse would.
- **You give up:** 12 lines over 13 programs, mostly in constructors that hand their values out;
  `&` across kinds for cleanup failures (it stays for written combinations).

**New names, not cold-read yet:** `FileReader`, `FileWriter`, `SocketReader`, `finish_sending`,
`drop(x)`, and a way for a failure type to mark itself a leftover (one option is a family, as
`UndoFailed` is). They need the cold-read kit before reaching open_decisions.md.

## Outside this round's scope

- A lint for a `FileWriter` to a final path inside a raced body (program 10).
- Whether `&` on `void | E` values should treat `void` as identity and evaluate both sides
  (program 13, C); (g) doesn't need it.
- How `drop(x)` and `defer` interact with the `$unsafe` restoration examples of D40 Q5.

## Limits

Paper programs, not compiled. The grades are this round's own. Before deciding: an independent
review of (g), a cold read of the new names and of the error messages, and a cost check of the
per-exit rule on the flagship panel. The Mojo and golangci-lint corrections were checked against
their current documentation this round; the GHC row was checked only as far as 9.12's
exception-context changes; the other corrections follow the review's reading of its sources.
