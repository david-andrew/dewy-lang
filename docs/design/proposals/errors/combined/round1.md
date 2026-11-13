# Combining failures, David's design: round 1

David's direction (decisions.md, batch 10): `e1 & e2` combines two failures into an unordered
set typed `E1 & E2`; `v as T` takes one part out; two failures of one type go in an error stack
(`type of error & array`); origins and traces are metatag members produced on demand. This round
fills in the rules he left open and compares the result with the earlier `ErrorGroup` proposal
(`proposals/errors/round4.md`). Fourteen paper programs are in `programs/`; nothing was compiled.

## Minimal examples

### Combine two

```dewy
QuotaExceeded:type = type of error & [message:string]
Offline:type = type of error & [host:string]
check_backup = (used_mb:int host_up:bool) => {
    if used_mb >? 100 and not host_up return QuotaExceeded["over quota"] & Offline["backup.local"]
    if used_mb >? 100 return QuotaExceeded["over quota"]
    if not host_up return Offline["backup.local"]
}   # void | QuotaExceeded | Offline | QuotaExceeded & Offline
```

### Take one out with `as`

```dewy
host_of = (failure:QuotaExceeded & Offline):>string => {
    let offline = failure as Offline     # proven: Offline is one of the parts
    return offline.host
}
```

### Match all four cases

```dewy
report = ():>void => {
    let result = total_bytes             # int | QuotaExceeded | Offline | QuotaExceeded & Offline
    match result {
        both:QuotaExceeded & Offline => printl"both failed: {both}"
        quota:QuotaExceeded => printl"just the quota: {quota.message}"
        offline:Offline => printl"just the network: {offline.host}"
        n:int => printl"{n} bytes in use"
    }
}
```

Arm order doesn't matter: `quota:QuotaExceeded` never takes the pair, because it doesn't name
`Offline`. Leave out the first arm and the match isn't total: the error names
`QuotaExceeded & Offline`. (Program 01 is David's sketch completed.)

### A handler that must not swallow

```dewy
limit_or_default = (path:Path) => {
    return read_limit(path) ??<ParseError> 100
}   # ParseError alone gives 100; ParseError & FileCloseFailed passes through unchanged

limit_or_default_by_hand = (path:Path) => {
    let limit = read_limit(path)
    if limit is? ParseError return 100   # error: `limit` may be ParseError & FileCloseFailed, and this
    return limit                         # drops FileCloseFailed unnamed. Name it, forward it, or write `limit;`
}

strict_limit = (path:Path):>int | ParseError | FileError | Canceled => {
    return read_limit(path) or_throw     # error: read_limit can give ParseError & FileCloseFailed,
}                                        # which this result type doesn't hold whole
```

### Cancellation

```dewy
poll = (sensor:Sensor) => {
    loop true {
        let reading = sensor.read(timeout=1s) ?? continue   # a timeout: read again
        record(reading)
    }
}
```

Today (D4 Q1) `??` doesn't default `Canceled`: after Ctrl-C, `poll` leaves at that `??`, as
`or_throw` would. If `??` defaulted it, the loop would spin: cancellation is level-triggered, so
every later read is canceled at once and `continue`s. Point 2 below weighs keeping this against
the alternatives. A cleanup that fails during cancellation gives `Canceled & FileCloseFailed`:

```dewy
save = (path:Path frames:array<Frame>) => {
    let out = files.open(path 'w') or_throw
    loop frame in frames {
        out.write_bytes(frame.pixels) or_throw;
        sleep(10ms) or_throw             # Ctrl-C here, then the close fails: Canceled & FileCloseFailed
    }
}
```

### A stack accumulating in a loop

```dewy
RowError:type = type of error & [row:int message:string]
check_rows = (rows:array<string>) => {
    let problems:array<RowError> = []
    loop i in [0..rows.length) {
        if to_int(rows[i]) is? error problems.push(RowError[i+1 "not a whole number"])
    }
    ErrorStack[problems...] or_throw     # an empty array makes no stack: nothing is forwarded
    return rows.length
}   # int | ErrorStack<RowError>
```

When the first failure is already in hand, `&=` appends to a stack:

```dewy
connect_patiently = (host:string) => {
    let first = connect(host)
    if first isnt? ConnectFailed return first
    let failures = ErrorStack[first]
    loop _ in [1..4] {
        let next = connect(host)
        if next isnt? ConnectFailed return next
        failures &= next                 # push; failures stays an ErrorStack<ConnectFailed>
    }
    return failures
}
```

### Cleanup with distinct error types

```dewy
write_report = (path:Path rows:array<Row>) => {
    let out = files.open(path 'w') or_throw
    loop row in rows out.write_text("{row.name},{row.score}\n") or_throw;
}   # a write fails, then the close fails: FileWriteFailed & FileCloseFailed

split_scores = (rows:array<Row> passed_path:Path failed_path:Path) => {
    let passed = files.open(passed_path 'w') or_throw
    let failed = files.open(failed_path 'w') or_throw
    loop row in rows {
        if row.score >=? 50 { passed.write_text("{row.name}\n") or_throw; }
        else { failed.write_text("{row.name}\n") or_throw; }
    }
}   # both closes fail: ErrorStack<FileCloseFailed>, `failed` then `passed`
```

### Where an error came from

```dewy
main = (argv:array<string>) => {
    let copied = copy_file(p(argv[1]) p(argv[2])) or_throw<Canceled>
    if copied is? error {
        loop part in copied.$parts printl("{part.$origin}: {part}" file=stderr)
        exit(1)
    }
}
# copy.dewy:7:5 in copy_file: FileWriteFailed: no space left on device (b.bin)
# copy.dewy:6:5 in copy_file: FileCloseFailed: the last writes may not be on disk (b.bin)
```

Because this program reads `$origin`, the failure types that can reach that read store a 4-byte
site number; nothing else pays. No code reads `$trace`, so no trace is captured anywhere.

### Three spellings in the sketch that need changing

- `match combined_fn() as result { … }` is new syntax and collides with `as` conversion
  (`combined_fn() as result` already means "convert to the type `result`"). Bind first
  (`let result = combined_fn`) or name each arm (`both:E1 & E2 => …`), as above. Not proposed.
- `e1, e2 = result as E1, result as E2` parses as `result as (E1, result) as E2`: `,` binds tighter
  than `as`. Write two lets, or parenthesize each `as`.
- `f1()`: a zero-argument call that gives a value drops its parentheses (`f1`).

## Point 1: handlers must not silently swallow parts

**Rule: using a part is free; handling takes the whole failure, so it must name every part.**

- **Using a part** never changes the value: `is? E1` (true when some part is an `E1`),
  `v as E1`, passing `v` to an `E1` parameter, reading a field that only one part has. The caller
  still holds all of `v`.
- **Handling** consumes: `??<E>`, plain `??`, a `match` arm. It takes a combination only when `E`
  names every part (a part is named by its own type, a family it belongs to, `error` or
  `exception`). Otherwise `??<E>` passes the combination through unchanged, and a `match` arm
  doesn't take it, so totality asks for an arm that does.
- **Forwarding** keeps the whole value: `return`, `or_throw`, and storing in a typed place.
  `or_throw<E>` forwards a combination when **any** part matches `E` (forwarding loses nothing).
  A declared result, field or variable admits a combination only when its type holds it whole:
  the combination is listed (`ParseError & FileCloseFailed`), or the type is `error` or
  `exception`, or a family that has no fields the parts share. `FileError` declares
  `path` and `message`, which every file failure has, so `FileError` holds one file failure, not
  two (reading `.path` on two would be ambiguous). `error` declares no fields and holds any
  combination of errors.
- **Dropping** is checked: a variable holding a combination may not go out of use on a path
  where some part was never named (by `is?`, `as`, an arm, a handler, or a parameter of its
  type). The fix-it offers forwarding it, naming it, or dropping it explicitly with `;`, the
  decided way to drop a value. This check runs only where a combination is in a variable's type.

Examples, each in its enclosing function, with `read_limit` from program 02
(`int | FileError | ParseError | Canceled | FileReadFailed & FileCloseFailed | ParseError & FileCloseFailed | Canceled & FileCloseFailed`):

```dewy
a = (path:Path) => read_limit(path) ??<ParseError> 100
    # int | FileError | Canceled | FileReadFailed & FileCloseFailed | ParseError & FileCloseFailed | ...
b = (path:Path) => read_limit(path) ??<ParseError | FileCloseFailed> 100
    # ParseError & FileCloseFailed is now named in full: it becomes 100 too
c = (path:Path) => read_limit(path) ??<error> 0
    # every failure except a Canceled one (point 2)
d = (path:Path) => read_limit(path) ?? 0
    # same as c: plain `??` names every part of every failure, except Canceled under option A
e = (path:Path) => read_limit(path) or_throw<FileCloseFailed>
    # forwards FileCloseFailed and the combinations containing it (not the Canceled one, under A);
    # ParseError alone stays
```

Why (b) and not the alternatives David listed:

| Rule | `??<E1>` on `E1 & E2` | Cost |
|---|---|---|
| (a) exact type only | passes through | `??<E1 \| E2>` doesn't handle `E1 & E2` either; you must list `E1 \| E2 \| E1 & E2`. Combinations multiply in every handler. |
| **(b) every part named** | passes through | One rule for `??`, arms and `or_throw` (mirrored). Nothing unnamed is ever consumed. |
| (c) handle the named part, keep the rest | gives `E2` | `??` produces a value, so the `E1` fallback is computed and thrown away and the result is still a failure. Python's `except*` does this for side-effecting blocks; for a value-producing `??` it is confusing. |
| (d) compile error unless every part is named | error | Safe but blocks the natural `??<E1> 0` then `or_throw` of the rest. (b) gives the same safety with no error. |

**Plain `??`** names everything, so it consumes any combination (and stacks), except
those carrying `Canceled` under option A.

**`match` arms follow the handler rule**, which is the one place where `match` and `is?` differ:
`if result is? QuotaExceeded` is true for the pair (David's sketch, "works if E1 or E1 & E2 was
returned"), but the arm `quota:QuotaExceeded` doesn't take it. The arm binds `quota` with the
alternatives it took, so a binding never hides a part: without the pair arm before it,
`problem:FileError` in program 05 would take `FileWriteFailed & FileCloseFailed` too (every part
is a `FileError`), and `problem` would have that pair in its type, so `problem.path` would be an
error there while `return problem` is fine.

## Point 2: cancellation

### The original reasoning (D4 Q1, batch 4, 2026-11-07)

The question asked: "Turn this on, and no `??` can swallow Ctrl-C … Without it,
`input_int("n? ") ?? 0` turns Ctrl-C into 0, and a receive loop with `?? ""` spins. Python's
`except Exception` and Trio make the same choice." The recorded reason: "Ctrl-C must never become
a default value or a silent exit 0." Two facts carry it:

1. **Cancellation is level-triggered** (concurrency proposal v5): once a scope is canceled, every
   later wait in it gives `Canceled` again at once. Consuming one `Canceled` doesn't reset it, so a
   loop that defaults it and goes round again never waits and never ends.
2. **A defaulted `Canceled` is indistinguishable from the value it became**, so a program that
   reaches the end of `main` exits 0 after Ctrl-C.

`$explicit_cancellation` (batch 5, in `$bulletproof`) makes each place where `Canceled` would pass
a `??` silently a compile error, with the fix-it `or_throw<Canceled>`.

### The options

**A. Keep: `??` passes `Canceled` on** (today's rule).

```dewy
poll = (sensor:Sensor) => {
    loop true {
        let reading = sensor.read(timeout=1s) ?? continue   # Timeout: read again. Canceled: leave poll
        record(reading)
    }
}
ask = () => {
    let rounds = input_int("rounds? ") ?? 10    # bad text: 10. Ctrl-C: leave ask, exit 130
    play(rounds)
}
```

**B. `??` defaults `Canceled` like any failure, with a compile-time warning at each `??` that can
see it** (an error under `$explicit_cancellation`).

```dewy
poll = (sensor:Sensor) => {
    loop true {
        let reading = sensor.read(timeout=1s) ?? continue   # warning: this `??` also defaults Canceled
        record(reading)                                     # after Ctrl-C: spins, every read canceled at once
    }
}
ask = () => {
    let rounds = input_int("rounds? ") ?? 10    # warning; Ctrl-C at the prompt gives 10
    play(rounds)                                # a play that never waits runs to the end: exit 0
}
```

**D. Always explicit: `$explicit_cancellation` on by default.** A `??` that can see `Canceled` is a
compile error until the code says what happens to it:

```dewy
poll = (sensor:Sensor) => {
    loop true {
        let reading = sensor.read(timeout=1s) or_throw<Canceled> ?? continue
        record(reading)
    }
}
ask = () => {
    let rounds = input_int("rounds? ") or_throw<Canceled> ?? 10
    play(rounds)
}
```

| | A (keep) | B (catch, warn) | D (explicit) |
|---|---|---|---|
| `??` means | any failure except cancellation | any failure | any failure; cancellation must be dealt with first |
| A hidden exit at `??` | yes: shown in hover and in the function's type (a declared `:>int` rejects it) | no | no |
| Ctrl-C in a retry loop | stops | spins until a second Ctrl-C forces exit | stops |
| Ctrl-C at a prompt with a default | exit 130 | continues with the default; exit 0 if nothing else waits | exit 130 |
| Noise | none | a warning on most `??` in I/O code: every file operation, wait and read is a cancellation point | `or_throw<Canceled>` on most `??` in I/O code |
| Peers | Python (`except Exception` misses `KeyboardInterrupt`, `CancelledError`), Trio | Go (`ctx.Err()` is an ordinary error), Swift (`try?` swallows `CancellationError`) | none common |

The fourteen programs have only three `??`: two on `to_int` (03 line 10, 08 line 13), which
can't be canceled, and one typed `??<…>` on a file read (02 line 14), which can. They handle I/O
with `or_throw<Canceled>` and `is?`, so they don't measure this. LANGUAGE.md's own examples
put `??` on cancellable reads (`input_int("n? ") ?? 0`, `read_line() ?? ""`) as often as on pure
ones (`to_int(text) ?? 0`, `env("HOME") ?? "/"`). Where `??` meets I/O, B's warning fires on
correct code, which teaches people to ignore it, and D adds `or_throw<Canceled>`.

**Recommendation: keep A.** The bypass is not invisible: the inferred result type gains
`Canceled`, a declared result that lacks it rejects the `??` (so a reader of a signature always
knows), and per batch 9's condition for cleanup ("the language, highlighting and hover show"), the
editor marks every `??` that passes cancellation on, the way it marks cleanup that can fail. What
would change this recommendation: evidence that `??` in real Dewy code is mostly on pure
operations (parsing, lookups), where nothing can be canceled and the question doesn't arise.

### How each option treats `Canceled & E1`

`Canceled & FileCloseFailed` arises when a canceled body's cleanup also fails.

- **Under A**, a combination carrying `Canceled` behaves as `Canceled` does for every test and
  handler that doesn't name `Canceled`: **adding parts to a `Canceled` never makes it pass a test
  that `Canceled` alone would fail.** So plain `??`, `??<FileCloseFailed>` and collectors pass it
  on; `is? error` and `is? FileCloseFailed` are false; `is? Canceled` and `is? exception` are true;
  `or_throw<Canceled>` forwards it; `??<Canceled | FileCloseFailed>` and an arm
  `both:Canceled & FileCloseFailed` handle it; `as FileCloseFailed` still takes the part out. Without
  this rule `if r is? error continue` would drop a cancellation that `is? error` never sees today.
  The cost: a declared result must list `Canceled & FileCloseFailed` to forward it (inferred results
  do this by themselves).
- **Under B** it is an ordinary combination: plain `??` consumes it with the warning;
  `is? error` is true.
- **Under D** a `??` that can see it is an error until `or_throw<Canceled>` forwards it.

```dewy
save_quietly = (path:Path frames:array<Frame>) => {
    save(path frames) ?? void                     # A: Canceled & FileCloseFailed leaves save_quietly
}
save_reporting = (path:Path frames:array<Frame>) => {
    let saved = save(path frames)
    if saved is? FileCloseFailed printl"{(saved as FileCloseFailed).path} may be incomplete"
    saved or_throw                                # A: is? is false for the carrier; it is forwarded here
}
```

## Point 3: distinct error types per operation

Yes: give each operation that can fail at cleanup its own type, so a body failure and a cleanup
failure of one resource are always different types and combine with `&`. Group each resource's
types under a family so one handler covers them (`??<FileError>` consumes
`FileWriteFailed & FileCloseFailed`, since every part is named).

| Resource | Family | Body | Cleanup |
|---|---|---|---|
| Files | `FileError` [path message] | `FileNotFound`, `FileAccessDenied`, `IsDirectory`, `FileExists` (existing), `FileReadFailed`, `FileWriteFailed` | `FileCloseFailed`: the final flush or close failed; the last writes may not be on disk |
| Sockets (`net`) | `NetError` [message] (existing) | `SocketConnectFailed`, `SocketListenFailed`, `SocketSendFailed`, `SocketReceiveFailed` | `SocketCloseFailed` |
| Processes | `ProcessError` [program message] | `SpawnError` (existing), `ProcessWaitFailed` | `ProcessStopFailed`: abandoning a child (`$__abandon__`) couldn't stop it |
| Transactions (`db`) | `DbError` [message] | `QueryFailed`, `CommitFailed` | `RollbackFailed`: abandoning (`$__abandon__`) couldn't roll back |

- **Change to LANGUAGE.md:** `FileError` today is the catch-all *sibling* of `FileNotFound` and the
  rest. Here it becomes their parent, and the catch-all cases go to the operation that failed
  (`FileReadFailed`, `FileWriteFailed`; directory changes such as `mkdir` and `rename` give
  `FileWriteFailed` for I/O faults). One-shot path methods (`read_text`, `write_text`) own no
  handle after they return, so they never produce a combination.
- **Library messages are constants plus a shared path**, so building a cleanup failure never
  allocates.

**What automatic cleanup produces**, at each exit of a scope with fallible cleanup:

1. One owner: body failure `E` and cleanup failure `C` of different types: `E & C`. The body may
   already be a combination: `E1 & E2` and `C` give `E1 & E2 & C` (flat).
2. Several live owners whose cleanup fails with the same type (two `File`s, or an
   `array<File>`): an `ErrorStack<C>` in cleanup order (reverse acquisition). The shape is fixed by
   the code, not by how many happened to fail: with two live `File`s the cleanup failure type is
   `ErrorStack<FileCloseFailed>` holding one or two entries, never a bare `FileCloseFailed` that
   becomes a stack in production. At an exit where only one of them is live (the second `open`
   failed), it is a bare `FileCloseFailed`.
3. Owners of different types: `FileCloseFailed & SocketCloseFailed`.
4. A body failure of the cleanup's own type (an explicit `a.close() or_throw`, then `b`'s automatic
   close fails): the two go into `ErrorStack<FileCloseFailed>`, body first.
5. A canceled body: `Canceled & C` (point 2).
6. An array of owners reserves room for its cleanup failures as it grows, so a stack built at
   cleanup never allocates and allocation failure can't lose a failure. Two named owners need a
   fixed-size stack, which lives inline. This answers the round-3 review's N3 gate for this design;
   its cost is one failure-sized slot per owner in an owner array.

**Generic code where `T & U` meets `T == U`:** combining distributes over unions, and two failures
of one type are a stack, so `T & U` at an instance where both are `DiskLow` is `ErrorStack<DiskLow>`,
holding the left operand then the right (program 13). Only code where the types are definitely the
same (`e1a:E1 & e1b:E1`, written in concrete code) is the compile error David asked for, with the
fix-it `ErrorStack[e1a e1b]`; where they may or may not be the same (unions, type parameters,
`FileError & FileNotFound`), that alternative of the type is the stack. Inside a generic body,
`x as T` on `T & U` is rejected because it is ambiguous at `T == U`: forward `x`, or walk
`x.$parts`.

## Point 4: `as` on combined values in general

- **Projection:** `v as T` on a combination takes the one part that is a `T`. If every part is a
  `T` and `T` holds the combination whole (`error`), it is an ordinary widening and keeps every part.
  If several parts are `T` but `T` can't hold them whole, it is ambiguous: "both parts are
  `FileError`s; name one (`as FileWriteFailed`)".
- **Proven or not:** `x as T` must be proven, as today (batch 4, D11 Q1). On a value whose static
  type is the combination, a part is always proven. On a union with combination alternatives
  (`int | E1 | E1 & E2`), it needs a guard (`if result is? E1`) or a `match`; `result as E1?` gives
  the part or `none` without a guard, as `as T?` already does.
- **Parameters:** passing a combination where a part's type is expected passes that part
  (program 11, `greet(profile)`). The caller keeps the whole value, and the dropped-part check
  sees whether the caller later loses the rest.
- **Records** (not errors): `user & settings` keeps both records. A field that only one part has
  is read directly (`profile.theme`); one that several parts have is ambiguous
  (`(profile as User).id`). A declared record intersection (`Name:type = A & B`) is unchanged: it
  is one record whose shared field has the intersected type, read directly. A `Name` value passes
  as a combination of `A` and `B` (its one record is both); a combination of separately built `A`
  and `B` with a shared field passes as a `Name` only by building one.
- **Functions:** an overload set (`@f & @g`, discussion points) is a combination of functions; a
  call goes to the one overload that fits, and `(handlers as (int:>string))` takes one out.
- **`is?`** asks "can this be used as a `T`?": true when the value or one of its parts is a `T`
  (except under option A for carriers of `Canceled`). In its true branch `as T` is proven unless
  ambiguous.

## Point 5: the error stack

- **Spelling:** `ErrorStack<E>` in the prelude, defined in the library as
  `type of error & array<E>`, nonempty. Built like any error, `ErrorStack[a b]` or
  `ErrorStack[failures...]`. A program may mint its own (`FormErrors:type = type of error & array<FieldError>`);
  pushing comes from one library overload of `__and__` on `error & array<E>`, so it works for
  both. Cold-read candidates are in names.txt (`stack` also reads as "stack trace").
- **No empty stack:** a stack holds at least one failure. `ErrorStack[xs...]` on an array not
  proven nonempty gives `void | ErrorStack<E>`: no failures, no failure. This is what makes
  `ErrorStack[problems...] or_throw` the whole accumulation idiom.
- **`&` on a stack:** `stack & e` with `e` an element type pushes and returns the stack;
  `stack &= e` pushes in place; `stack & other_stack` of the same element type appends it. A
  failure of another type combines with the stack as a part:
  `ErrorStack<FileCloseFailed> & FileWriteFailed`. `Canceled` is never an element.
- **Order:** push order; cleanup stacks in cleanup order; iteration (`loop e in stack`) and
  `$parts` follow it.
- **`is?`:** a stack is not one `E`, so `stack is? E` is false and `stack as E` doesn't exist;
  `is? ErrorStack<E>`, `is? error` and `is? exception` are true. For elements, ask the array
  (`loop e in stack`, `stack[0]`).
- **Handlers and arms:** `??<E>` names every element when it names `E`, so `??<FileCloseFailed>`
  and `??<FileError>` consume `ErrorStack<FileCloseFailed>`. An arm binds a value as its type, so
  `close:FileCloseFailed` doesn't take a stack; write `closes:ErrorStack<FileCloseFailed>`.
- **Reporting:** an unhandled stack reaching `main` prints one line per element, numbered, and
  exits with its element type's code. An unhandled combination prints one line per part. With
  several codes, the lowest wins (an unordered set has no "first"); a combination carrying
  `Canceled` exits as `Canceled` alone would.
- **In a loop:** an ordinary array and `ErrorStack[xs...]` at the end (program 03, 04, 07), or a
  seeded stack and `&=` (program 10, the example above).

## Point 6: origins and traces

`resources/discussion_points.md` has no spelling for these (only a wish for "the relevant stack
trace" in a state dump, line 2112). Proposed names, all metatag members (cold read pending):

- **`e.$origin`**: a `SourceLocation` [file line column function], where `e` was made. A failure
  made inside a function tagged `$origin_at_caller` takes its caller's position instead; the
  standard library tags its I/O functions this way, so `FileNotFound` points at the program's
  `files.open` line, not at the library. A cleanup failure's origin is the line that bound its
  owner (`let out = files.open(…)`), which identifies the resource.
- **`e.$trace`**: `array<SourceLocation>`, the calls active when `e` was made, innermost first,
  at most 64; a task's trace ends with the line that started the task.
- **`e.$parts`**: the failures inside `e`, as `array<exception>`: `[e]` for one failure, the parts
  of a combination (stacks expanded in order) in a fixed order (the order the part types are
  declared in the program). For records and functions combined with `&`, their parts.
- On a combination, `$origin` and `$trace` belong to the parts, so reading them on the
  combination is ambiguous, like any member several parts have: use `as` or `$parts`. A stack has
  its own origin (where it was built) and its elements keep theirs.

**Demand-driven, precisely:**

- Every construction site has a site number at compile time. That costs nothing at run time.
- A failure type stores its site number in its values only if some read of `$origin` can see a
  value of that type. The compiler already knows which failure types flow where (it infers result
  types from them), so this is computed per type, not per value. With no read, nothing is stored.
  With a read: 4 bytes in each value of those types, which can grow results that contain them, and
  one table row per site (file, line, column, function name) in the binary.
- `$origin_at_caller` passes the caller's site number as a hidden argument, again only to
  functions whose failures can reach an `$origin` read.
- A trace is captured when a failure is made only if some read of `$trace` can see its type. The
  capture walks the stack (cost proportional to depth, paid only on the failure path), needs frame
  information for the functions involved (binary size), and stores the frames out of line; if that
  storage can't be allocated, `$trace` is empty rather than failing.
- Debug builds (`-g`) print origins and traces for failures that reach `main`, so a debug build
  reads them for those types; release builds don't, unless the program does.
- Measure before accepting: result sizes and instruction counts for unit errors, `T | E` results
  and arrays of results with and without an `$origin` read, and the binary-size cost of the site
  table, on the flagship panel.

## Natural extensions (reported, not decided)

- **`parallel` blocks combine independent failures.** Today a `parallel` block returns its first
  failure and cancels the rest. An unordered set fits concurrent failures well: two items that
  fail on their own (not because the first failure canceled them) could return `A & B`, or an
  `ErrorStack<A>` in item order when the types match. Program 07 `load_both` shows it. This
  changes `parallel`'s result and belongs to the concurrency design.
- **`or_throw(& previous)`** stays as David described: the shape for combining on forward, if it is
  ever wanted.

## Comparison with the `ErrorGroup` proposal (round 4)

| | David's design (this round) | ErrorGroup (round 4) |
|---|---|---|
| Combining two | `a & b`, typed `A & B` | `a & b`, typed `ErrorGroup` |
| Order, duplicates | unordered set; repeats go in an ordered stack | ordered tree, duplicates allowed |
| What the type tells the caller | exactly which combinations can occur | only "a group" |
| Handling | `??<E>` takes a combination when E names every part; arms likewise | `??<FileError>` never takes a group; recovery needs `errors.recover` |
| Taking parts out | `as E1`, proven by the type | `.errors`, then narrow each child |
| Cancellation | carriers behave as `Canceled` for tests (option A) | a hidden "carries Canceled" flag; `is? Canceled` false while `or_throw<Canceled>` forwards |
| Allocation | none for combinations (fixed layout); stacks reserve ahead | a group node per combination |
| New names | `ErrorStack`, `$origin`, `$trace`, `$parts`, `$origin_at_caller` | `ErrorGroup`, `.errors`, `join`, `leaves`, `with_context`, `report`, `recover`, `$origin`, `SourceLocation` |

**Where David's design is better.**

- The type is honest. `read_limit` says it can fail with `ParseError & FileCloseFailed`; with a
  group the caller learns only that something grouped can come back, and its handlers silently
  don't apply (round 4's own discoverability grade for that was 3).
- Handling needs no protocol. Round 4 needed a recovery helper (`errors.recover<E>`) with a
  six-point contract to repair one kind inside a group; here `??<E>`, arms and `as` do it, because
  the parts are typed.
- Cancellation is simpler to teach. Round 4's carried flag made `is? Canceled` false while
  `or_throw<Canceled>` forwarded (its floor grade, 3). Here a carrier answers `is? Canceled` true.
- No allocation for combinations, which removes round 4's open gate on losing failures when memory
  runs out, except for owner arrays, where reservation answers it.
- Fewer names: no group type, join, leaves, context or recover functions.

**Where it is worse.**

- **Types grow.** Every owner with fallible cleanup adds combination alternatives to its scope's
  result: `write_report` gains `FileWriteFailed & FileCloseFailed` and
  `Canceled & FileCloseFailed`, where round 4 added one `ErrorGroup`. Inferred results hide the
  writing cost; declared ones must list the combinations or widen to `error`, because families
  with shared fields can't hold two parts. Hover needs a compact display.
- **No order between different kinds.** Which of `FileWriteFailed & FileCloseFailed` happened first
  is known only from the kinds (body before cleanup) or `$origin`. Round 4 kept it. For exit codes
  this design needs a rule (lowest code), where round 4 took the first.
- **`match` and `is?` differ on combinations** (an arm `E1` doesn't take `E1 & E2`; `is? E1` is
  true), and a stack is covered by `??<E>` but not by an arm `e:E`. These are two consistent
  principles (use versus handle), but a reader must learn both.
- **The dropped-part check is new flow analysis**, demand-driven but still a rule a newcomer meets
  as a compile error.
- **Dynamic counts are second-class**: a stack is one type repeated. A collection of failures of
  mixed types (`array<error>`) becomes `ErrorStack<error>`, whose elements need `match` to use,
  much as round 4's children did.
- **Option A's dominance rule** adds one more place where `Canceled` is special; under option B it
  disappears.

## Questions for David

1. (semantics, his open point) Handlers name every part (rule b), with `or_throw<E>` forwarding on
   any part and the dropped-part check. **Rec:** yes. Reversible before release.
2. (a) Cancellation: keep A, or B, or D. **Rec:** A, with editor marking. Reversible.
3. (a) `FileError` becomes the family parent of the file failures (LANGUAGE.md says sibling), and
   the vocabulary above. **Rec:** yes; names to be cold-read.
4. (b) `ErrorStack<E>`, and `ErrorStack[xs...]` giving `void` for an empty array. **Rec:** yes.
5. (c) `$origin`, `$trace`, `$parts`, `$origin_at_caller`, `SourceLocation`. **Rec:** cold-read first.
6. (b) The `parallel` extension. **Rec:** design it with the concurrency proposal.
