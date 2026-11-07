# Decisions waiting on David

- **Only open items.** Once you answer one, it moves to [decisions.md](decisions.md), with what was considered and why, and is removed from here.
- **Revised 2026-11-07:** D4, D10, D11, D22, D28, D29, D31 and D33–D37 were revised together. Independent agents dogfooded them twice, they were made consistent with each other, and every name was read cold by three readers with no context. Each item states its floors and whether it is ready. Shared rules: `docs/design/proposals/integration/conventions.md`.
- **Question kinds:** (a) changes something you decided; (b) new syntax or surface; (c) names only.
- **What gets asked:** a semantic question only appears here if it fails one of two tests:
  1. Is the common (80%) path easy, ergonomic and fast?
  2. If the common path doesn't fit, is it straightforward to adjust?

  If both pass, the semantics are taken, and only the syntax is here for you to review.
- **Answering:** reply per item, e.g. "D4 yes, D15a a". Anything you skip stays pending.
- **Example conventions:**
  - Arguments are space-separated, `=?` is equality, and zero-argument calls drop their parentheses.
  - `or_throw` forwards an error to the caller, `??` substitutes a default for any error or `none`, and `??<E>` does so only for error type `E`.
  - `@f` is a handle to function `f`, and `$name` is a metatag.

---

## The questions at a glance

**(a) Changes something you already decided**
1. D4 Q1: no `??` (or collector) can swallow Ctrl-C (`Canceled`); it passes through as `or_throw` would.
2. D10 Q1: `@(m.lock)` is the idiom for the place a zero-argument method gives.
3. D10 Q2: results that report on a write, removal or start can be dropped without `;` (`$discardable_result`). This changes the multi-expression rules.
4. D10 Q3: `starts_with`/`ends_with`, `set_permissions` and `int(text)`/`float64(text)` replace `startswith`, `chmod` and `to_int`/`to_float`.
5. D11 Q1: `let a:Action = s` and `s as Action` must be proven instead of panicking at run time.
6. D22 Q1: delete `$parallel_safe`.
7. D31 Q1: zoned arithmetic defaults to Temporal's "compatible" gap and fold policies instead of "never guesses".
8. D31 Q2: `$program.time_zone`, `$program.time_zone_rules` and `$program.time_zone_source`, set in the main file only.
9. D31 Q3: `rounding=` replaces `ties=`; your per-type defaults don't change.
10. D31 Q6: the prefix for "same call, failures as values" (rec: keep `strict_`).

**(b) New syntax or surface**
11. D4 Q2: `x or_throw_only<E>`.
12. D4 Q3: `main = (app:BackgroundTasks)`.
13. D11 Q2: the validation keyword `check=` (or `valid_if=`).
14. D11 Q3: `__read__` for a type's text reader.
15. D11 Q4: the checked record constructor `Roll(count=… sides=…)`.
16. D31 Q5: `Instant<width=64>` as a value parameter computed while compiling.
17. D33 Q1: an alias that names itself in a self-length refinement.
18. D37 Q1: the `iso_basic` pattern word and the `""` field joiner.

**(c) Names only**, rec yes to all: D4 Q4–Q5, D10 Q4–Q8, D11 Q5–Q6, D28 Q1–Q4, D29 Q1, D31 Q4 and Q7, D34 Q1, D35 Q1, D36 Q1, D37 Q2.

**Unchanged from before:** D30 (function types without parentheses), D32 (time zone data license) and D21 (packages).

---

## P1: blocking current work

### D4. One unified `parallel` surface: v4
- **BLUF:** turn this on, and three forms cover all parallel and concurrent work:
  - a block whose steps wait only for the data they use;
  - a loop or comprehension that may write only its own element;
  - task groups for background work, including one that lasts as long as the program.

  Values come out as they would sequentially, except for what handles (channels, atomics, files) return. Ctrl-C can't turn into a default value, and a program that wants Ctrl-C for itself, such as a shell, can catch it. Full design: `proposals/concurrency/unified/proposal-v4.md`.

```dewy
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
parse_age = (text:string):>int | Invalid => int(text) ?? Invalid
score = (n:int):>int => (n * n) % 7
autosave = () => loop true {
    sleep(30s) or_throw
    printl"saved"
}
relay = (commands:Channel<string> chat:Channel<string>) => loop true {
    match select(command=@commands.receive  message=@chat.receive  timeout=1s) or_throw_only<Canceled> {
        [command:string] => printl"command: {command}"
        [message:string] => printl"chat: {message}"
        [command:Closed] => return "commands closed"
        [message:Closed] => return "chat closed"
        <Timeout> => printl"idle"
    }
}
main = () => {
    parallel {
        let config = load_config or_throw          # starts at once
        let map = load_map(config) or_throw        # waits for config
        let sounds = load_sounds or_throw          # starts at once
    }
    let ages = [parallel t in ["31" "abc" "45"] parse_age(t) ?? void]   # [31 45]
    let rounds = input_int("rounds? ") ?? 10       # bad text gives 10; Ctrl-C still stops the program (exit 130)
    let total = sum([parallel i in [0..rounds * 100_000) {
        check_cancel or_throw                       # opt in: Ctrl-C stops this early
        score(i)
    }])
    let commands = channel<string>(4)
    let chat = channel<string>(4)
    parallel {
        {
            chat.send("hi") or_throw
            chat.close
        }
        {
            commands.send("quit") or_throw
            commands.close
        }
        let why = relay(commands chat) or_throw
    }
    tasks((group:Tasks) => {
        let saver = group.spawn(@autosave)          # a Task
        let tick = ticker(500ms)
        loop i in [0..4) tick.next or_throw        # wait for four ticks; .next is a receipt
        saver.stop                                  # stops this one task; the group ends normally
    }) or_throw
    printl"{map} {sounds} {ages} {total} {why}"
}
```

A program that catches Ctrl-C for itself, and one whose background work outlives `main`:

```dewy
repl = () => {
    let ctrl_c = catch_ctrl_c                      # while held, Ctrl-C cancels nothing
    loop true {
        let line = input("> ") ??<Interrupted> { printl""; continue } ?? break   # Ctrl-C clears the line; end of input leaves
        if line =? "quit" break
        printl"you said {line}"
    }
}

fetch_news = (out:Channel<string>) => loop true {
    out.send("patch 1.2 is out") or_throw          # stands in for a network call
    sleep(10minute) or_throw
}

main = (app:BackgroundTasks) => {                  # tasks here live as long as the program
    let news = channel<string>(4)
    let job = app.spawn(@fetch_news(news))         # a Task<Unsent<string> | Canceled>
    repl
    if job.error is? error printl"news failed: {job.error}"   # a failed task here doesn't end the program
}
```

- **The common path:**
  - write the steps in order in `parallel { }`, and the compiler runs whatever doesn't depend on something else;
  - `[parallel x in xs f(x)]` for maps;
  - `?? void` to drop failures, `.partition_failures` to keep both sides;
  - `check_cancel or_throw` to make a long computation stoppable.
- **How to adjust:**
  - to force an order, use the earlier result, wrap the steps in `{ }`, or move a step after the block;
  - `$parallel.max_concurrent = 4` as the first line of a loop body caps that loop;
  - `$parallel.off` replays a scope in source order;
  - `$program.max_cores = 1` keeps a program on one core;
  - `protect_from_cancel(5s @save(x))` saves after a cancel;
  - `catch_ctrl_c` takes Ctrl-C.
- **Semantics taken:**
  - **Block rule:** an item waits for an earlier one whose data it uses. If every item succeeds, ordinary values are the sequential ones; a handle's result depends on timing. On failure, pending items never start, running ones are canceled and joined, and nothing is rolled back. A cycle through a channel is an error, and so is a `close` that races the sends.
  - **Who may write:** block items may write the function's variables, and those writes are ordered. Loop bodies may write only their own element (`xs[i]` with their own `i`). A spawned task can't write outer variables; the error names a channel or a block item (D26, restated).
  - **`?? void`** works wherever `if` without `else` works.
  - **Handles share one set of verbs:**
    - `Task`, `PlayingSound`, `Process` and groups have `.stop`, `.wait` and `.running`. Sources of events (`Ticker`, the Ctrl-C catcher) have `.next`.
    - `Task<E>.wait` gives `void | E | Canceled`, and `.error` gives `E | none`.
    - Stopping something you started isn't a failure.
    - `or_throw` in a spawned lambda forwards to its inferred result (D27, restated).
  - **Program-lifetime group:** in a `BackgroundTasks` group, a failed task doesn't fail the group; its error prints once on stderr and stays on its handle. A scoped `tasks(…)` group fails fast, as decided.
  - **Ctrl-C while caught:**
    - a press is an event (`.next`, or `@ctrl_c.next` in `select`), and a console read in progress gives `Interrupted`;
    - three presses within one second still end the process;
    - a child process still gets the terminal's signal itself;
    - dropping the catcher restores the default.
  - **Clocks:** `timeout=` and `sleep(until=…)` take a monotonic deadline (`now + 1s`) or a wall-clock `Instant`, and waits accept any time quantity.
  - **Frame code:** `update` and `draw` may read and write files and the terminal. Waiting on a channel, task, `sleep` or `select` there is a compile error, and `ch.drain` reads what has arrived.
  - **A sound nobody holds** belongs to the program's group: exit waits for it, a looping one stops at exit, and Ctrl-C stops it.
  - **`select`:** every wait's result must be distinguishable. A send that loses keeps its payload. A channel's element type can't be `Closed` or `Canceled`.
  - **Cores are one unit:** program cap, scoped cap, pinning, `available_cores`, and an environment variable that can only lower it.
- **Questions for you:**
  1. **(a) Turn this on, and no `??` can swallow Ctrl-C.**
     - `??`, `?? void`, `?? return/break/continue` and `??<E>` (unless `E` names `Canceled`) don't default `Canceled`; it leaves the function as `or_throw` would. A collector never holds `Canceled`.
     - A program that wants Ctrl-C for itself holds `catch_ctrl_c` (Q4), so nothing is canceled and nothing needs defaulting.
     - It changes:
       - your 2026-10-23 `??` rule, which gains "except `Canceled`";
       - D14's `?? return/break/continue`;
       - C3's "errors stay per-item values".
     - Without it, `input_int("n? ") ?? 0` turns Ctrl-C into 0, and a receive loop with `?? ""` spins. Python's `except Exception` and Trio make the same choice.
     - **Rec:** yes. Reversible.
  2. **(b) `x or_throw_only<E>`** forwards only `E` and keeps the rest as values, mirroring `??<E>`. It shortens `match select(…)` and `within(…)`. Read correctly in round 6, where `or_throw<E>` read 0/3. Without it, write the arm `<Canceled> => return Canceled`. **Rec:** yes. Reversible.
  3. **(b) `main = (app:BackgroundTasks) => …`** gives a group whose tasks live as long as the program. In a UI program, that is until the window closes. A task that fails there doesn't end the program. Without it, a UI program has nowhere to put background work, because `update` and `draw` run after `main` returns. `BackgroundTasks` read 4/3/4, against 3/2/3 for `ProgramTasks`. **Rec:** yes. Reversible.
  4. **(c) `catch_ctrl_c`**, a handle that takes Ctrl-C while held, with `Interrupted` for an interrupted console read. Read 5/4/3, against 4/3/3 for `listen_for_interrupt`.
     - `ctrl_c.discard_pending` forgets presses not yet handled. It is **untested**: the tested `.clear` read 3/3 as "remove the registered handlers".
     - **Rec:** yes.
  5. **(c) Names** (read fine):
     - `check_cancel`;
     - `select(name=@ch.receive … timeout=1s ties='fair')`, `ties='first'`, `Sent`, `Waitable<R>`;
     - the metatags `$parallel.max_concurrent`, `.chunk_size`, `.max_cores`, `.off`, `$placement.device`, `.cores`, `$memory.layout`, `$program.max_cores`, `.max_memory`, `.max_tasks`;
     - `sum(xs grouping='tree')`, `iterable<T>`, `available_cores`, `DEWY_MAX_CORES`, `ticker`, `tick.next`, `partition_failures`;
     - `Task`, `.stop`, `.wait`, `.running`, `.error`;
     - `ch.drain`, `sleep(until=t)`, `protect_from_cancel`.

     **Rec:** yes.
- **Flagged, not questions:**
  - the Ctrl-C default and exit status 130;
  - a block gives its items' values in source order;
  - a block's top-level `let`s are visible after it;
  - `( … )` is one item;
  - `$parallel.off` is a deterministic replay;
  - a `$parallel.*` tag that governs nothing is an error;
  - `$program.max_tasks` gives `OutOfMemory` only under `$explicit_allocation_failure`.
- **Floors:** setup through the file system is invisible to the block analysis. The HTTP client, file-change notification and terminal hand-off for job control are library items.
- **Ready:** yes.

---

## P2: unblocks common friction

### D10. Safety defaults and tag names (#108)
- **BLUF:** turn on nothing, and a program can't crash or silently go wrong on anything it can reasonably meet. Each permission or stricter check is one tag line.
  - Joined paths become an error without breaking the common loops.
  - No tag changes a type.
  - `$bulletproof` compiles hello world.
  - A result that reports on a write, a removal or a start can be dropped without `;`.
  - Processes get the full surface a shell needs.

  Full design: `proposals/bulletproof/round3.md`.

```dewy
Reset:type = [user:string token:secret<string>]
let saves = p"saves"

issue = (user:string) => Reset[user secure_token or_throw]       # secret<string> | NoEntropy

save = (slot:string data:string) => {
    let file = saves.confine("{slot}.sav") or_throw  # SafePath, or PathEscape back to the caller
    file.write_text(data) or_throw                   # the Path written: save's result
}

main = () => {
    saves.make_dirs or_throw                         # gives back the path; a statement drops it
    loop name in saves.list or_throw printl'{name}: {p"{saves}/{name}".size or_throw}'   # FileName: confined; a DataSize
    let slot = input("save name? ") or_throw
    let f = save(slot "level=3") ?? { printl"pick a plain name"; return }      # "../x" is a PathEscape
    save(sanitize_file_name(slot) "level=4") or_throw                          # any text made one safe name; result dropped
    let level = int(input("level? ") or_throw) ?? 1   # bad text gives 1; Ctrl-C still stops (D4 Q1)
    let winner = secure_random([1..100]) or_throw    # unpredictable, and public: a plain int64
    let r = issue("ann") or_throw
    printl"{f} {level} {winner} {r} {r.token =? "guess"}"   # token=<redacted>; =? is constant-time
    let git = start_process("git" ["status" "--short"] cwd=saves stdout='pipe') or_throw
    loop line in git.stdout.lines printl"  {line}"
    let status = git.wait or_throw                   # ExitStatus: .success .code .signal
    if not status.success printl"git failed: {status.code}"
    let m = mutex<int64>(0)
    let v = @(m.lock)                                # the locked place, called like any zero-argument method
    v += random([1..6])
}
```

- **Common path:** nothing to write. Listing a folder, globbing, literals and numbered files need no confinement, secrets stay out of output, and statements that write files need no `;`.
- **To adjust:** one tag line or one call:
  - `$allow_unproven` (run-time checks);
  - `$allow_unconfined_paths`;
  - `base.confine(text) or_throw`, `FileName(text)` or `sanitize_file_name(text)`;
  - `.reveal`.
- **Semantics taken:**
  - Joining outside text to a folder is a compile error. `list` gives `FileName`s, `glob` and `walk` give `SafePath`s, and `relative_to` gives a `SubPath` that joins to any base.
  - No tag changes a result type: strict tags point to `strict_` functions (D31 Q6). `$finite_floats` asks for proofs and leaves declared types alone, and a signature that promises finiteness writes `Finite`. `$explicit_allocation_failure` stays the flagged exception.
  - Every reader is `T(text)` and gives `T | ValidationError` (D11).
  - **Secrets:**
    - comparisons are constant-time;
    - `secure_token` and `secure_random_bytes` are secrets, while `secure_random(range)` gives a plain, unpredictable value;
    - `input(prompt hidden=true)` gives a secret;
    - `to_json` of a secret is an error unless `secrets='reveal'`, which gives a `secret<string>`;
    - writing a secret creates the file `0o600`;
    - `from_json` fills secret fields.
  - **Files:**
    - `write_bytes(data permissions=)` creates the file with that mode;
    - sizes are `DataSize` quantities, and `modified` is an `Instant`;
    - `remove_file` and `remove_dir` give the removed path;
    - errors carry their path;
    - `config_dir(app)` and its siblings give per-user folders;
    - `p.follow_lines` tails a growing file.
  - **Processes:**
    - `start_process(program args cwd= env= stdin= stdout= stderr= new_group=)`, where each stream is `'inherit'`, `'null'`, `'pipe'`, a `Path` or another process's pipe, so `a | b` is two calls.
    - The result is a `Process` with the shared handle verbs plus `.kill` and `.id`.
    - `.wait` gives an `ExitStatus` (`.success .code .signal`).
    - `set_current_dir(path)` changes the program's folder.
  - The counter rule takes any proven-bounded step, `Atomic.add` included. `printl` of scalars doesn't allocate.
- **Names: turn this on, and…**

| Tag | …this happens |
|---|---|
| `$allow_unproven` | An unproven index, division, narrowing or refined argument compiles; if it fails, the program ends with a report. Narrower: `$allow_unproven_indexing`, `$allow_unproven_division`, `$allow_unproven_narrowing` |
| `$prototype` | The same, with a warning at each site |
| `$allow_unconfined_paths` | Outside text joined to a folder needs no confinement |
| `$prove_confined_paths` | Whole paths must be proven inside a base too |
| `$assume_extern_never_waits_on_tasks` / `$no_unverified_extern_waits` | Your unchecked claim on a C-call wrapper / such claims are errors |
| `$finite_floats` | Producing NaN or infinity without a proof is an error |
| `$no_hidden_copies` | `let b = a` on an array is an error; write `.copy` |
| `$explicit_allocation_failure` | Allocating returns `T \| OutOfMemory` (the one tag that changes types; flagged) |
| `$prove_local_asserts` | A call reaching a `$runtime_assert` in your module must prove its condition |
| `$prove_no_counter_overflow` | Counters, atomic counters, array sizes and huge `parallel` ranges need real overflow proofs |
| `$args.prove_finite_floats` | Above a function: callers prove float arguments finite |
| `$time.only_strict_today` | `today` is an error that names `strict_today` (follows D31 Q6) |
| `$prove_library_asserts`, `_runtime_checks`, `_arena_safety`, `_drop_cannot_fail`; `$no_trusted_library` (all four) | Library code reached must be proven; argument-dependent cases take a guard at your call |
| `$bulletproof` | All of the strict tags above, plus `$no_hidden_costs`, `$no_deadlocks` and `$time.strict`; the permissions are rejected inside it |

- **Questions for you:**
  1. **(a) `@(m.lock)` as the idiom** for the place a zero-argument method gives. It replaces the ownership doc's "write the optional parentheses", and `@(m.lock())` stays legal. **Rec:** yes.
  2. **(a) Turn this on, and a result that only reports on a write, a removal or a start can be dropped without `;`.**
     - A *receipt* is kept wherever a value is taken (a binding, an argument, a collector, an inferred function's last line) and dropped silently elsewhere. Its failure still needs handling.
     - Receipts:
       - handles;
       - an event from `.next`;
       - file-system writes and removals that return their path (the library gate enforces this, so no list can drift);
       - `Atomic.add` and `rebind`;
       - any function whose every result path ends in one.
     - Not receipts: `xs.pop` and readers.
     - This changes your multi-expression rule (a written `:>void` body expresses nothing; an inferred body expresses every value). In two dogfoods, it removed every `;` after `make_dirs`, `write_text`, `play`, `spawn` and `append_text`.
     - Spelling: `$discardable_result` (read fine).
     - **Rec:** yes. If declined, results stay useful and statements write `;`.
  3. **(a) Library renames of names you decided:**
     - `starts_with`/`ends_with` for `startswith`/`endswith`;
     - `set_permissions` for `chmod`;
     - `int(text)` and `float64(text)` for `to_int` and `to_float`, keeping `max_digits=` and `allow_nonfinite=`, so every reader is named for what it builds.

     All read fine. **Rec:** yes.
  4. **(c) Tag names:** `$prove_local_asserts` (replaces `$count_local_asserts_as_panics`, read 2/3), `$allow_unproven_narrowing` and `$prove_no_counter_overflow`. All read fine. **Rec:** yes.
  5. **(c) Random and secure names:**
     - `random(range)` for ints, floats, quantities, durations and dates;
     - `fast_random_bytes` and `secure_random_bytes`, with no bare `random_bytes`;
     - `secure_token`;
     - `secure_random(range)`, which gives a plain value;
     - `rng` with no argument and `.seed`.

     All read fine. **Rec:** yes.
  6. **(c) Path names:** `FileName`, `base.confine(text)` and `sanitize_file_name` (read fine), and `SubPath` (3/3/3, acceptable; `RelativePath` missed that it can't escape). **Rec:** yes.
  7. **(c) Other library names** (read fine):
     - `find_last`, `make_dir`, `remove_dir`, `append_text`, `stdin_lines`;
     - `config_dir(app)`, `data_dir`, `cache_dir`, `home_dir`, `temp_dir`, `p.follow_lines`;
     - `copy_to(… progress=)`, `write_bytes(… permissions=)`, `input(… hidden=)`, `to_json(… secrets='reveal')`;
     - `start_process(… cwd= env= stdin= stdout= stderr= new_group=)`, `Process`, `.kill`, `ExitStatus` (`.success .code .signal`), `set_current_dir`;
     - one name for each file operation's method and function forms.

     **Rec:** yes.
  8. **(c) Float extras:** `a.is_close(b rel= abs=)`, where `abs=` defaults to the zero of the operand's type. On temperature readings, `abs=` is a required `TemperatureDifference` and there is no `rel=` (D34). Also `allow_nonfinite=true` and `Finite` (read fine). **Rec:** yes.
- **Float constants:** as before, with `x.is_finite` as the guard and a `float64.min` fix-it.
- **Floors:** a string builder, `which`, and HTTP are library items.
- **Ready:** yes.

### D11. Compile-time shapes, action names, audio handles and removed physics bodies (#131–#133)
- **BLUF:** turn this on, and a library or a program can say what a valid literal looks like, and how its own type reads from text, with ordinary Dewy code.
  - Bad melodies, action names, dates and format patterns become compile errors, and constants cost nothing at run time.
  - Text from outside must be checked before it can crash, and every check that fails gives one error type, `ValidationError`.
  - It replaces `$check_constant` and `$error_if`.

  Full design: `proposals/string-shapes/round2.md`.

```dewy
sku_problem = (text:string):>string | none =>
    if text.length =? 8 and text.starts_with("SKU-") none
    else "'{text}' is not a SKU: SKU- and four characters, like SKU-12AB"
Sku:type = string<check=@sku_problem>
Port:type = int64<(1 <=? x <=? 65535)>
Roll:type = [count:int64<(1 <=? x <=? 100)> sides:int64<(2 <=? x <=? 1000)>]
__read__ = (text:string):>Roll | ValidationError => {          # how a Roll reads from text, like "3d6"
    let parts = text.split("d")
    if parts.length not=? 2 return ValidationError[message="write dice like 3d6" input=text]
    Roll(count=int(parts[0]) or_throw sides=int(parts[1]) or_throw)  # checked constructor: Roll | ValidationError
}
price = (item:Sku):>rational => 9.99
Action:type = 'jump' | 'left' | 'right'
const f2 = fmt'.2f'
const day = fmt'weekday day month_name'

main = () => {
    printl(price("SKU-12AB"))                  # checked while compiling; nothing at run time
    price("SKU-12")                            # compile error: 'SKU-12' is not a SKU: SKU- and four characters, like SKU-12AB
    let typed = read_line ?? ""                # end of input gives ""; Ctrl-C still stops
    let item = Sku(typed) ?? "SKU-0000"        # Sku | ValidationError
    let port = Port(typed) ?? 8080             # read as an int64, then "must be 1 to 65535"
    let dice = Roll(typed) ?? Roll[1 6]        # your own reader
    let a:Action = typed                       # compile error: cannot prove typed is an Action
    let b = Action(typed) ?? 'jump'            # never a panic
    let tune = play(melody("E4/2 E4/2 G4*3"))  # a PlayingSound: tune.running, tune.stop, tune.wait
    play(tone(440Hz 80ms))                     # a statement drops the handle; the sound still plays to the end
    printl'{item} {port} {dice} {b} {f2(1.5)} {day(date"2026-11-07")}'
    f2("hi")                                   # compile error: fmt'.2f' formats numbers; found string
    tune.stop
}
```

- **Common path:** pass literals, and they're checked and folded. For outside text, use `is?`, `T(text) ?? default` or `or_throw`.
- **Adjusting:**
  - Shapes work on any type.
  - They may read the function's other parameters: `date(text 'day/month/year')`.
  - Several shaped overloads let a literal choose the result type (`fmt'.2f'`).
  - `@forbid("…")` refuses an overload with a fix-it (`t + 1day` says "write `24hour`").
  - A validator overload on a `CountHoleTemplate` checks computed widths like `fmt'<{w}'`.
- **Semantics taken:**
  - A constant that fails never falls through to a plain `string` overload.
  - A passing call with all constant arguments and no effects folds to its value.
  - `T(x)` gives `T | ValidationError`.
  - A refinement or shape alias reads text through its base type's reader and then its check, and the message comes from the refinement.
  - Audio handles use D4's verbs. `.running` is true while paused, and `.paused` says which. A sound nobody holds plays to its end.
  - `load_sound(path)` gives `Sound | ValidationError | FileNotFound`.
- **Cost:** about 1.6 M instructions per distinct literal (desktop, instruction counts); repeats are lookups.

**D11b. Action names and rebinding.** A literal union names the actions, and `Controls<A>` keeps the shipped bindings apart from the player's changes:

```dewy
Action:type = 'jump' | 'left' | 'right' | 'pause'
let input = Controls<Action>[binds=[
    'jump'  -> [Input.key(Key.space) Input.button(PadButton.a)]
    'left'  -> [Input.key(Key.a) Input.stick(0 (-1))]
    'right' -> [Input.key(Key.d) Input.stick(0 1)]
    'pause' -> [Input.key(Key.escape)]
]]
main = () => {
    printl(input.pressed('jump'))                        # 'jmup' is a compile error naming the actions
    let lost = input.rebind('jump' 0 Input.key(Key.w))   # the action that had W; it takes Jump's old key
    input.save(p"controls.txt") or_throw                 # only the player's changes; the path is dropped
    let unknown = input.load(p"controls.txt") or_throw   # names a stale file had; never a crash
    printl"{lost} {unknown}"
}
```

- In a menu, `controls_editor(@input)` is the whole rebinding screen, and `listen_for_press` ignores the press that opened it.
- For rhythm, fighting and music games, `input.pressed_at('tap')` gives the press's own `ClockReading` or `none`, and `sound.position_at(reading)` gives the song position at that moment, so timing is judged by the event, not the frame.
- `Controls<A>` and `Binding` replace `action` and `action_pressed`.

**D11c. Removed physics bodies.** Unchanged from round 1, except the tag:
- `w.get(ball)` gives `BodyState | none`;
- `w.pos(ball)` is proven after `add` or inside `if w.has(ball)`, or checked under `$allow_unproven`;
- `w.remove(ball); w.pos(ball)` is a compile error even under `$allow_unproven`;
- `w.has` replaces `alive` and `joint_alive`.

- **Questions for you:**
  1. **(a) Turn this on, and `let a:Action = s` and `s as Action` must be proven, like `x as uint8`.** Today they compile and panic on bad text, which changes LANGUAGE.md's "any other string is checked when the program runs". **Rec:** yes.
  2. **(b) The validation keyword:**
     - `check=@sku_problem` keeps the validator's message.
     - `valid_if=@is_sku` read best cold, but it implies a `bool`, and a bool can't say what's wrong.
     - `shape=` read poorly.

     **Rec:** `check=`.
  3. **(b) How your own type reads text:**
     - a protocol function, `__read__ = (text:string):>Roll | ValidationError => …`, found by its result type like the library's `__as__` and `__add__` (read fine);
     - or a tag above an ordinary function, `$reader parse_roll = …`.

     `Roll(text)`, `input_field` and union readers then use it. **Rec:** `__read__`: one mechanism with the library's protocols.
  4. **(b) The checked constructor `Roll(count=3 sides=6)`.** It builds a record and gives `Roll | ValidationError` when a field breaks its rule, while `Roll[…]` stays the proven literal. Read fine. **Rec:** yes.
  5. **(c) `ValidationError`** is the one error for "this isn't a valid T": every shape conversion, checked constructor and text reader. It replaces `ShapeError`, `ParseError` and `TextError` (read fine). **Rec:** yes.
  6. **(c) Names:**
     - `PlayingSound` with `.stop .wait .running .paused .pause .resume .position`, and `Sound.length`;
     - `E4/2` and `E4*3`;
     - `rebind(action slot input conflict=)`, `reset`, `save`, `load`, `bindings`, `controls_editor`, `input_hint`, `listen_for_press` with `.next`;
     - `forbid`, `load_sound` (read fine).
     - **Weak, flagged:**
       - `input.pressed_at` and `sound.position_at` read only moderately well (one reader took `position_at` for placing a sound in space). They are niche.
       - `CountHoleTemplate` failed, as did `CountedPattern`, both read as counting matches or numbered blanks. It is a library-author name, kept as the better of the two.

     **Rec:** yes.
- **Ready:** yes.

### D28. Clay-style UI
- **BLUF:** turn this on, and a frame's UI is a plain value.
  - Nothing is ever "open", widgets write straight into your variables, and picks come back typed against your own union.
  - Fields show and read text the way people write it.
  - Background work lives in the program's group (D4), where a failure becomes a message rather than a closed window.
  - No new syntax. Full design: `proposals/ui/round2.md`.

```dewy
Choice:type = 'resume' | 'quit' | 'save'
Screen:type = 'playing' | 'paused' | 'title'
Difficulty:type = 'easy' | 'normal' | 'hard'
Port:type = int64<(1 <=? x <=? 65535)>
let screen:Screen = 'paused'
let volume = 0.8
let fov = 90
let difficulty:Difficulty = 'normal'
let fullscreen = false
let player = "ann"
let port:Port = 7000
let keep:Duration = 720hour                     # shown as "30 days"; a player may type "2 weeks"
let played:Duration = 0s
let news = ""
let app:BackgroundTasks                         # assigned by main, as for any module binding
let fetcher:Task? = none
let headlines = channel<string>(16)

set_fullscreen = (on:bool):>void => printl"full screen: {on}"
fetch_news = (out:Channel<string>) => loop true {
    out.send("patch 1.2 is out") or_throw       # stands in for a network call
    sleep(10minute) or_throw
}

main = (group:BackgroundTasks) => {             # lives until the window closes
    app = group
    fetcher = app.spawn(@fetch_news(headlines))
}

update = (dt:Duration) => {
    played += dt
    loop line in headlines.drain news = line    # what has arrived; never waits
    if fetcher is? Task and fetcher.error is? error news = "news unavailable: {fetcher.error}"
}

draw = () => if screen =? 'paused' pause_menu

pause_menu = ():>void => {
    let picked = ui<Choice>(back='resume' align='center' column(gap=12 pad=24 width=420 [
        text("Paused" size=36)
        text(news)
        button('resume' "Resume")
        input_field("Name" @player error=if player.trim.is_empty "a name can't be empty" else none)
        input_field("Port" @port)                                        # reads "7000"; shows "must be 1 to 65535"
        input_field("Keep logs for" @keep)                               # shows "30 days"; reads "2 weeks", "36h"
        slider("Volume" @volume [0.0..1.0] step=0.05 value_text=fmt'.0%')
        slider("Field of view" @fov [60..120] suffix="°")
        choice("Difficulty" @difficulty ['easy' 'normal' 'hard'])
        checkbox("Full screen" @fullscreen)
        button('save' "Save" enabled=all([valid("Name") valid("Port") valid("Keep logs for")]))
        button('quit' "Quit to the title" tip="Played {label(played)}")
    ]))
    if changed("Full screen") set_fullscreen(fullscreen)
    if picked =? 'save' p"settings.txt".write_text("{player} {port} {keep}") ?? { news = "not saved" }   # file I/O in draw compiles
    else if picked =? 'resume' screen = 'playing'
    else if picked =? 'quit' screen = 'title'
}
```

- **Common path:** the example above. Mouse, touch, keyboard and gamepad all work with no further code, and `button('resume2' …)` is a compile error.
- **When that doesn't fit:**
  - **Typed input:** `input_field("Amount" @amount)` for any type with a reader. It shows `label(x)` and reads with `T.parse_human`, which also takes programmer text. `read=` takes your own reader, and `error=expr` adds a cross-field check that shows under the field and makes `valid(id)` false.
  - **Reacting:** `changed(id)` and `committed(id)`; `checkbox(title checked=expr)` shows derived state.
  - **Tables:** `table`, `heading`, `TableSort`.
  - **Graphs:** `plot(values range=[0.0..1.0] style='bars')`.
  - **Tools:** `panel`, `menu_bar`, `collapsible`, `choice(style='tabs')`.
  - **Drag and drop:** `drag=true` and `ui(drop=@f)`.
  - **Custom drawing:** `box(id='map' …)` and `rect_of('map')`.
  - **Tests:** `layout(tree 1280 720)`.
  - **Speed:** `const` subtrees.
- **Semantics taken:**
  - A value tree, with interaction from the last frame's layout. Stale state can't crash.
  - A widget that reads input is a drawing call, so a `const` tree holding one is a compile error, and a tree kept across frames draws its widgets disabled.
  - Ids passed to `valid`, `changed` and `committed` are checked while compiling against the tree built in the same function.
  - Frame code may do file I/O, but not wait on channels, tasks or timers (D4).
  - Intervals are ranges, `style=` is how a widget looks, and `label(none)` is `""`.
  - `T.parse_human` reads a person's "30 days" as 720 hours and refuses "1 month", which has no fixed length.
- **Flagged, not questions:**
  - a game's `update` receives `dt:Duration`;
  - a `choice` without a list shows the union in text order.
- **Cost:** 378K instructions for a 238-element screen (desktop, release), about 0.5% of a 60 Hz frame.
- **Risk:** `scroll`, `grid`, `floating`, wrapping, `table` column sizing and drag and drop are the least proven, and there's no `no allocates` builder yet.
- **Questions for you:**
  1. **(c) Round 1's names:** `column row box grid scroll floating tooltip modal spacer text image button checkbox slider choice progress`, `ui` and `show`, `pick=` and `id=`, `pad`, the sizes, the nine-point `align`, `back=`. **Rec:** yes.
  2. **(c) Input names:** `input_field` with `valid(id)`, `hidden=`, `lines=`, `read=` and `error=`; `T.parse_human(text)` (3/3/4; `from_label` read as an enum lookup). **Rec:** yes.
  3. **(c) Widget names** (read fine):
     - `changed`, `committed`, `label`, `choice`'s `style='dropdown' 'segments' 'list' 'tabs'`;
     - `slider(title @v [low..high] step= value_text= scale='log' suffix= descending=)`;
     - `table`, `heading`, `TableSort`, `plot(range= style=)`, `divider`;
     - `tip=`, `shortcut=`, `enabled=`, `selected=`, `animate=`;
     - `panel`, `menu_bar`, `menu`, `context_menu`, `collapsible`, `layers`, `row(wrap=)`;
     - `drag=`, `ui(drop=)`, `right_clicked`, `double_clicked`, `dragged`, `ui(focus= player=)`.

     **Rec:** yes.
  4. **(c) `checkbox(title checked=expr)`** for derived state. Two of three readers took it for a two-way binding, so a plain variable written there gets the hint "to let the checkbox change it, write `@x`". **Rec:** yes, with the hint.
- **Ready:** yes.

---

## P3: lower stakes

### D22. Delete `$parallel_safe`?
- **BLUF:** delete it. Since items may wait, "parallel-safe" means only race-free, and the compiler already infers it per callback, with no tag.

```dewy
apply_then_report = (xs:array<int> f:(int:>int) report:(array<int> :>void)) => {
    let ys = [parallel x in xs f(x)]   # inferred: f must be parallel-safe
    report(ys)                         # report runs once: no requirement
}
main = () => apply_then_report([1 2 3] (x) => x * 2 (ys) => printl(ys))
```

- **The common path:** write nothing. Hover, printed signatures (`f: parallel-safe`) and generated docs show the requirement, and each call is checked.
- **What the tag would add:** only a promise that a later edit can't stop passing the callback into parallel code. A change to an exported signature is caught in general, without a concurrency tag.
- **Questions for you:**
  1. **(a) Delete the optional `$parallel_safe`** you allowed on 2026-11-01. **Rec:** delete. If kept, name it `$race_free`.
- **Ready:** yes.

### D29. Dates: weekday names, dates from numbers, stepping (all reversible)
Turn this on and:
- a weekday is a name, so comparing it with a number is a compile error;
- a date can be built from three numbers;
- a range of dates loops, by days or by any calendar step.

```dewy
$program.time_zone = 'Europe/London'
const long_day = fmt'weekday day month_name'
const short_day = fmt'weekday_short'
let d = date(2026 11 10)                               # constants are checked: date(2026 2 30) is a compile error
let born = date"2000-02-29"
printl(d.weekday =? 'tuesday')                         # true; `d.weekday =? 2` is a compile error
printl'{d.iso_weekday} {d.next('friday')} {d.nth_weekday_of_month(2 'tuesday')}'   # 2 2026-11-13 2026-11-10
printl(born.next_anniversary(after=d))                 # 2027-03-01, the same leap-day rule as `age`
printl'{d.add(1month overflow='next')} {age(born on=d leap_day='february_28')}'
printl'{d.floor(1month)} {long_day(d)} {days_of_week[0]}'   # 2026-11-01 Tuesday 10 November monday
let week = d.floor(1week)
loop day in [week..week + 1week) printl(short_day(day))     # Mon … Sun
loop first in [date"2026-01-01"..date"2027-01-01").step(1month) printl(first)   # the 1st of each month
loop n in [0..10).step(2) printl(n)                    # also integers: the same as [0,2..10)
let lesson = zoned"2026-09-08T09:00[America/New_York]"
printl(lesson.next('friday'))                          # 2026-09-11T09:00-04:00: the time and zone are kept
```

- **Common path:** `date(y m d)`, `d.weekday =? 'tuesday'`, `fmt'weekday day month_name'`, `loop day in [a..b)`.
- **To adjust:**
  - `d.iso_weekday` gives a number;
  - `date(y m d) ?? …` handles a run-time date that may not exist;
  - `nth_weekday_of_month(5 …)` gives `Date | InvalidDate`;
  - `r.step(s)` steps by another amount.
- **Semantics taken:**
  - Civil fields carry their ranges.
  - `weekday_name` goes, replaced by `label(d.weekday)` and the pattern word `weekday`.
  - A range of a discrete type loops, stepping by the type's unit.
  - `r.step(s)` works on every discrete range, ints included. Your decided `[a,b..c)` stays the arithmetic form for numbers, and `.step` is the only form for calendar steps, since `+1month` isn't a constant difference.
  - `z.next(w)` keeps the time of day and zone.
  - `overflow='next'` and `leap_day=` stay as built.
  - `$error_if` and `$check_constant` leave the user-facing design, replaced by shapes (D11).
- **Questions for you:**
  1. **(c) Names:**
     - `Weekday` and its seven members, `iso_weekday`, `d.next(w)` and `z.next(w)`, `nth_weekday_of_month`, `next_anniversary(after=)`, `d.floor`, `r.step(s)`;
     - `days_of_week` (5/4/5; `weekdays` read as Monday to Friday);
     - `date(year month day)` and `time_of_day(hour minute second=0)`.

     **Rec:** yes.
- **Reversible:** yes.
- **Ready:** yes.

### D30. Function types without the outer parentheses
Turn this on and `f:int:>int` works in annotations, but `(x:int:>int)` then means different things in a lambda and in a type, unless the labeled form becomes `((x:int):>int)`.

```dewy
apply = (f:int:>int x:int):>int => f(x)              # bare: parses and runs
g = (x:int64:>int64) => x(1)                         # a parameter x of type int64:>int64
let h:(x:int64:>int64) = (v:int64):>int64 => v+1     # a function type with labeled parameter x:int64
```

It also doesn't work in a lambda's result (`g=():>int64:>int64=>...`) or after `is?`, and `f:int:>int?` can only mean an optional result. `f:(int:>int)` is built and is what docs and printed types use.

- **Rec:** leave bare off. Today it gets the hint "a function type takes parentheses here".
- **Reversible:** yes.

### D31. Time spellings: zoned defaults, rounding, ranges, compact instants, one prefix (all reversible)
Turn this on and:
- adding a day to a zoned time always gives a zoned time;
- rounding has one keyword everywhere and follows your per-type defaults;
- a range's ends are `.start` and `.end`;
- `Instant<width=64>` is an ordinary type parameter;
- the call that gives its failures as values has one prefix.

```dewy
$program.time_zone = 'America/New_York'                    # program settings: main file only
$program.time_zone_rules = 'urgent.bin'                    # a rule pack beside the main file
Box:type = <T=int64>[v:T]                                  # bare Box means Box<int64>
let b:Box = Box[1]
let meet = zoned"2026-10-31T09:00[America/New_York]"
printl(meet + 1day)                                        # a ZonedDateTime: a gap moves forward, a fold takes the earlier
printl(meet.add(1day gap='reject' fold='reject'))          # ZonedDateTime | Gap | Ambiguous, when you ask
printl(meet.at(time_of_day"09:00"))
let t = instant"2026-01-01T00:00:00.5Z"
printl'{t.floor(1s)} {t.round(1s)} {t.round(1s rounding='nearest_even')} {quantize(t rounding='floor' tick=1s)}'   # …:00Z …:01Z …:00Z
printl'{round(2.5)} {round(2.5 rounding='nearest_even')} {round(2.7 rounding='toward_zero')}'   # 3 2 2
printl(convert<Instant<width=64>>(t))                      # Instant<width=64> | OutOfRange; errors print the type as written
printl(t.strict_in_zone(zone"Asia/Tokyo"))                 # ZonedDateTime | OutsideCoverage
let r = [date"2026-01-01"..date"2026-02-01")
printl'{r.start} {r.end} {r.includes_start} {r.includes_end} {(date"2026-01-01"..date"2026-01-02").is_empty}'   # … true
let l = local"2026-11-01T01:30"
printl(l.in_zone(zone"America/New_York" fold='later'))
```

- **Common path:**
  - zoned arithmetic, `at`, `in_zone` and `zoned(text)` give plain values;
  - `t.floor(1minute)` buckets;
  - `.start`/`.end` read as bounds;
  - rounding needs no keyword.
- **To adjust:**
  - pass `gap=`/`fold=`, or set `$time.gap`/`$time.fold` for a scope;
  - `quantize` gives the loss;
  - `strict_in_zone` and `strict_add` give failures as values;
  - `$time.no_assumed_policy` makes every unstated policy an error.
- **Semantics taken:**
  - **Rounding follows your decided defaults:** exact values (`rational`, decimals, `Duration` and `Instant` ticks) round half away from zero, and floats half to even. `fmt` follows them too, so `fmt'.2f'(0.125)` prints `0.13`.
  - A range is empty when nothing lies inside it. Discreteness is declared: a type is discrete through `next_up`, and dense through `$no_next_value` (as `rational` is). Anything else is an error at `is_empty`.
    - `$no_next_value` read weakly: it and `$no_successor` were both read as "may take a next value without proof". It is a library-author tag, kept as the better of the two.
  - `t.in_zone(z)` is total.
  - An integer times an on-grid tick is on the grid, and a proven-nonzero divisor gives a plain value.
  - Every text reader gives `T | ValidationError`.
  - No tag changes a result type: strict tags point to the prefixed functions (Q6), and `$time.require_*` becomes `$time.no_assumed_*`.
- **Questions for you:**
  1. **(a) Default gap and fold policies** (Temporal's "compatible") in place of the accepted time design's "never guesses". A literal that hits a gap or fold warns. **Rec:** yes. It is what Temporal, Python's `zoneinfo` and jiff do, and the union stays one argument away.
  2. **(a) `$program.time_zone`, `$program.time_zone_rules` and `$program.time_zone_source`** replace your `$time.zone`, `$time.rules` and `$time.zone_source`. Only the main file sets them, which narrows D15a's module and scope clause. Read fine. **Rec:** yes. It stops a library from compiling alone and failing when imported.
  3. **(a) One keyword, `rounding=`, replaces your decided `ties=`** on `round`, and `round`, `quantize`, time's `round` and `fmt` share it. Your per-type defaults don't change, and `ties=` then means only `select`'s fairness. Its nine values:
     - `'nearest_away'` and `'nearest_even'`;
     - `'nearest_toward_zero'`, `'nearest_up'` and `'nearest_down'` (your `'zero'`, `'up'` and `'down'`);
     - `'floor'`, `'ceil'`, `'toward_zero'` and `'away_from_zero'`.

     Read fine; `half_up` was avoided because readers split between "toward +∞" and "away from zero". **Rec:** yes. `floor` and `toward_zero` aren't tie rules, so `ties=` can't hold them, and one keyword is easier to find than two. The alternative is to keep `ties=` on `round` and use `rounding=` only where a directed mode is meaningful.
  4. **(c) `.start`/`.end`/`.includes_start`/`.includes_end`** replace the built `.first`/`.last`/… on `Range<T>`. Arrays' `.first`/`.last` are members, and a half-open range's `.last` isn't one. Read fine. **Rec:** yes.
  5. **(b) `Instant<width=64>` as a value parameter** whose alias body is computed while compiling. This is a general facility, also wanted for `uint<bits>` families. Read fine. **Rec:** yes; the fallback is a separate type, `CompactInstant`.
  6. **(a) The prefix for "the same call, with its failures as values"** (`strict_today` is yours, from D15e). No prefix reads well on every function:

     | Name | Readers' confidence (1–5) | How it was read |
     |---|---|---|
     | `strict_add` (round 5) | 3, 3, 4 | read as "fails on overflow" |
     | `strict_today` (round 5) | 3, 2, 3 | |
     | `strict_in_zone` (round 7) | 2, 2, 4 | two of three: "strictly inside a zone" |
     | `checked_add` (round 5) | all three correct | |
     | `checked_today` (round 6) | 2, 1, 2 | all three: "something was checked today" |
     | `try_add` (round 6) | 4, 3, 3 | |
     | `try_today` (round 6) | 3, 3, 2 | |

     - **Options:**
       - keep `strict_` everywhere (`strict_today`, `strict_add`, `strict_in_zone`, `strict_elapsed`, `strict_zone`, `$time.only_strict_today`);
       - `try_` everywhere;
       - no shared prefix, with a name chosen per function.
     - **Rec:** keep `strict_`, unless you prefer `try_`.
       - It is your earlier choice, and it pairs with the strict tags (`$time.only_strict_today`, `$time.strict`), so a reader learns one word for the whole strict family.
       - `try_` read a little better on arithmetic, but in Rust and C# `try_` means "returns an Option or a bool", not "returns the failure", and `try_today` read no better.
       - Per-function names lose the one thing the prefix gives: finding the careful twin of any call by typing `strict_`.
       - `strict_in_zone`'s misreading is answered by its hover and its fix-it, which name what it returns.
  7. **(c) Names:**
     - `t.floor`, `t.ceil`, `t.round`, `z.at`, `$time.no_assumed_zone` and the `$time.no_assumed_*` family, `$time.no_dropped_zone`, `time_of_day"…"`, `local"…"`, `fold='later'`, `d.at(t)`;
     - `strict_elapsed` and `strict_zone`, which follow Q6.

     **Rec:** yes.
- **Reversible:** yes.
- **Ready:** yes.

### D32. Unicode-licensed time zone data in the repository
Mapping Windows zone names to IANA names uses Unicode's CLDR table, now stored in the rule pack. Its license asks that its copyright and permission notice travel with copies, and the project has kept to Apache-2.0 WITH LLVM-exception with no NOTICE file.

- **Options:**
  - **a) Keep the table and add Unicode's notice** next to the data file.
  - **b) Drop the table.** On Windows, `'system'` then warns and reads times as UTC unless `$time.zone` or `TZ` names an IANA zone.
- **Rec:** (a). Windows machines report only their Windows name, so without the table every Windows program needs a setting.
- **Reversible:** yes.

### D33. A type alias that names itself in a self-length refinement
Turn this on and a function can return a self-length array, which has no type name to write today.

```dewy
Parents:type = array<int64<(<? Parents.length)>>
make_parents = (n:int64<(>? 0)>):>Parents => {
    let p:Parents = [0]
    loop p.length <? n { p.push(p.length) }
    p
}
let tree = make_parents(5)
printl'{fmt'<8'"parents"} {tree}'                         # parents  [0 1 2 3 4]
```

- **Common path:** the alias, as a result type.
- **To adjust:** today the same contract works on a `let`, a parameter or a record field, so a function can fill one given by `@` or return it inside a record.
- **Semantics taken:** only a self-length refinement may refer to its own alias. Any other self-reference stays an error.
- **Questions for you:**
  1. **(b) Allow an alias to name itself in a self-length refinement.** It would be the first alias allowed to refer to itself this way. **Rec:** add it when returning these arrays matters.
- **Reversible:** yes.
- **Ready:** yes.

### D34. A temperature difference type, and readings as numbers
Turn this on and:
- passing a reading where a difference belongs is a compile error naming the fix, instead of silently counting from absolute zero;
- a reading gives its bare number on any scale;
- comparing two readings takes a difference as its tolerance.

```dewy
from units import ft, °F, °C, K, BTU, r_value_us, Area, ThermalResistance, TemperatureDifference, Temperature
heat_loss = (area:Area rise:TemperatureDifference r:ThermalResistance) => area*rise/r
const wall = 25.0r_value_us
let rise = 70°F - 30°F                                      # a TemperatureDifference
printl'{fmt'.1f'(heat_loss(8ft*40ft rise wall) as BTU/hour)}'   # 512.0BTU/hour
printl(rise as °C)                                          # 22.(2)°C
let room:Temperature = 21.4°C
let before:Temperature = 21.1°C
printl'{fmt'.1f'(room.value_in(°C))} {fmt'.1f'(room.value_in(°F))}'   # 21.4 70.5: the bare reading on that scale
printl(room.is_close(before abs=0.5K))                      # true: a reading's tolerance is a difference
printl(heat_loss(8ft*40ft 70°F wall))                       # compile error: 70°F is a reading; a difference is `70°F - 30°F` or `20K`
printl(room / 1°C)                                          # compile error: dividing a reading scales it; for its number write room.value_in(°C)
```

- **Common path:** bare dimension names; exact values passed straight in; `t.value_in(°C)` for a CSV column.
- **To adjust:** `Area<rational>` keeps a value exact, and `20K` is a difference with no offset.
- **Semantics taken:**
  - An exact value rounds once into a float parameter.
  - D36's names default to `float64`.
  - A difference prints as an exact decimal, and `TemperatureDifference(text)` reads it back.
  - `q.value_in(unit)` works on every quantity. `/ unit` is the same thing on quantities that aren't readings, and on a reading it is refused with that fix-it.
  - `is_close` on readings requires `abs=` as a difference and has no `rel=`.
- **Questions for you:**
  1. **(c) Names:**
     - add `TemperatureDifference`;
     - rename the built `RValue`, `R` and `RSI` to `ThermalResistance`, `r_value_us` and `r_value_si`;
     - add `q.value_in(unit)`.

     All read fine; the old names failed. **Rec:** yes.
- **Reversible:** yes.
- **Ready:** yes.

### D35. `in_zone` on a zoned time, and a total `in_zone`
Turn this on and a zoned time shows the same moment in another zone directly, and showing a moment in a zone can't fail.

```dewy
$program.time_zone = 'America/New_York'
const where = fmt'weekday_short hour:minute zone'
let slot = zoned("2026-11-01T09:00" zone=zone"America/New_York")   # constant text: folds to a value
let berlin = slot.in_zone(zone"Europe/Berlin")             # a ZonedDateTime
printl(where(berlin))                                      # Sun 15:00 Europe/Berlin
printl(slot.nominal.strict_in_zone(zone"Asia/Tokyo"))      # ZonedDateTime | OutsideCoverage, for the strict
```

- **Common path:** `slot.in_zone(z)`, with no union to handle.
- **To adjust:** `strict_in_zone` reports when the answer extends the zone's data past its last transition or before its first. `$time.no_assumed_extrapolation` requires it.
- **Semantics taken:** `in_zone` uses the zone's TZif footer rule forward and local mean time back.
- **Questions for you:**
  1. **(c) Names:** `zoned_time.in_zone(zone)` (read fine) and `strict_in_zone`, whose prefix follows D31 Q6. **Rec:** add both.
- **Reversible:** yes.
- **Ready:** yes.

### D36. Unit dimensions and the missing common units
Turn this on and:
- `units` names the common dimensions and has the units a student, engineer or cook reaches for first;
- every quantity prints as text that reads back;
- a tool can read and convert quantities whose units it learns only at run time.

```dewy
from units import kW, kWh, kg, lb, psi, kPa, mph, km, MB, MiB, tbsp_us, mL, Power, Energy, Mass, DataSize
Appliance:type = [name:string power:Power]                   # float64 power, any unit of power
let kettle = Appliance["kettle" 2.2kW]
let used:Energy = 1392kWh
printl'{kettle.name} {used} {fmt'.1f'(150lb as kg)} {fmt'.0f'(32psi as kPa)} {fmt'.1f'(60mph as km/hour)}'   # kettle 1392kWh 68.0kg 221kPa 96.6km/hour
let cap:DataSize = 512MiB                                    # 2^20 bytes each; 512MB is 10^6 each
printl'{cap} {fmt'.0f'(3tbsp_us as mL)} {label(1.5tbsp_us)} {cap.value_in(MB)}'   # 512MiB 44mL 1 ½ tablespoons 536.870912
printl(Mass("250g") ?? 0kg)                                  # 250g: what prints reads back
main = () => {
    let q = Quantity(input("quantity? ") or_throw) or_throw  # any dimension: "5.5lb", "72°F", "1.5GiB"
    let u = Unit(input("to? ") or_throw) or_throw            # a unit by its written name
    printl(q.to(u) ?? "can't convert {q.dimension} to {u.dimension}")   # Quantity | DimensionMismatch
}
```

- **Common path:** import a unit by its usual name. A value prints in the unit you wrote, and `fmt` keeps it.
- **To adjust:**
  - `x as unit` picks another unit;
  - `x.value_in(unit)` (or `x / unit`, except on readings) gives the bare number;
  - `label(q)` gives text for people;
  - `Area<rational>` keeps a value exact;
  - `Quantity` and `Unit` work at run time.
- **Semantics taken:**
  - SI prefixes on every SI unit, generated.
  - `DataSize` as a ninth base dimension (`B = 8bit`). File sizes are `DataSize`s; `MB` is 10⁶ and `MiB` 2²⁰.
  - A quantity keeps its written unit.
  - Nothing prints a unit you can't write, and `10min` is an error naming `10minute`.
  - Each dimension name reads text, and JSON writes a quantity as its printed text.
  - `Quantity(text)` gives a value whose dimension is known only at run time (`.dimension`). `Unit(text)` looks a unit up by its written name: the unit table links only into programs that call it. `q.to(u)` gives `Quantity | DimensionMismatch`.
- **Next item, named, not in this round:** money. User-declared base dimensions (`USD:unit = base_unit("USD")`) make `5USD + 3EUR` a compile error. Until then, money is an exact `rational`, and adding currencies isn't caught.
- **Questions for you:**
  1. **(c) Names:**
     - **Dimensions:** `Area`, `Volume`, `Speed`, `Acceleration`, `Force`, `Energy`, `Power`, `Pressure`, `ThermalResistance`, `DataSize` (replaces `Information`, which read as a log message), `Frequency`, `Charge`, `Voltage`, `Resistance`, `Density`, `Torque`.
     - **Units:** `lb oz stone short_ton long_ton tonne nmi acre hectare ha gallon_us gallon_uk quart_us pint_us pint_uk fl_oz_us cup_us tbsp_us tsp_us tbsp tsp stick_butter_us mph knot kPa MPa hPa bar mbar atm psi mmHg inHg Wh MWh GWh cal kcal eV therm hp lbf standard_gravity C Ah mAh rpm bit B byte kB MB GB TB KiB MiB GiB TiB kbit Mbit Gbit`.
       - `stick_butter_us` read weakly (one reader took it for a joke). It is niche, and `butter_stick_us` is the alternative.
     - **Run time:** `Quantity(text)`, `Unit(text)`, `q.to(u)` (5/4/5), `.dimension`, `DimensionMismatch`.

     **Rec:** yes.
- **Reversible:** yes.
- **Ready:** yes.

### D37. `fmt` patterns for dates, times, durations and units
Turn this on and:
- a date or time pattern is written in words, so `hour:minute` can't print the month;
- a number pattern keeps a quantity's unit, and exact values round as you decided;
- an `Instant` prints in the program's zone;
- the compact ISO form the readers accept can be written too.

Each pattern is checked while compiling and decides what its function accepts, and the text it writes reads back.

```dewy
$program.time_zone = 'America/New_York'
const when = fmt'weekday day month_name, hour12:minute am_pm'     # dates with times
const money = fmt'>12,.2f'                                        # numbers
const lap = fmt'minute:second.millisecond'                        # durations
const stamp = fmt'iso_basic'                                      # 20261108T020500Z
const file_day = fmt'year""month""day-hour""minute'               # 20261107-2105: "" joins fields with nothing between
let meet = zoned"2026-11-07T21:05[America/New_York]"
let sent = instant"2026-11-08T02:05:00Z"
let names = ["North" "Île-de-France"]
let w = max(names[0].length names[1].length)
printl'{when(meet)}'                                              # Saturday 7 November, 9:05 PM
printl'{fmt'hour:minute'sent} {sent} {stamp(sent)} {file_day(meet)}'   # 21:05 2026-11-08T02:05:00Z 20261108T020500Z 20261107-2105
printl'{fmt'<{w}'(names[0])}|{money(1234.5)}|{money(0.125)}|{fmt',d'(1234)}'   # 0.125 prints 0.13: half away, as decided
printl'{fmt'.2f'(3.0303s)} {lap(91750ms)} {fmt'minute:second'(65s)}'   # 3.03s 1:31.750 1:05
printl(instant(stamp(sent)) ?? sent)                              # what iso_basic writes, instant(text) reads
let apache = instant("07/Nov/2026:05:15:31 -0500" 'day/month_short/year:hour:minute:second offset')
printl(apache)                                                    # 2026-11-07T10:15:31Z
printl(Duration("90minute") ?? 0s)
money("x")                                                        # compile error: fmt'>12,.2f' formats numbers; found string
fmt'HH:mm'                                                        # compile error: 'HH' is not a field. Did you mean fmt'hour:minute'?
```

- **Common path:**
  - `fmt'…'` once in a `const`, then call it or pass it (`value_text=fmt'.0%'`);
  - the ISO default needs no pattern;
  - reading takes the same pattern as writing.
- **To adjust:**
  - `t.in_zone(z)` for another zone;
  - `fmt'iso_basic'(z.local)` for a local stamp with no offset (iCalendar's `DTSTART;TZID=`);
  - interpolate members for an unusual padding;
  - `x.value_in(unit)` for a bare number;
  - `DatePattern(text)` or `NumberPattern(text)` for a pattern known only at run time.
- **Semantics taken:**
  - Number patterns are Python's mini-language, and the kinds can't overlap: an integer style makes an integer pattern, any other number option a number pattern, fill, align and width alone a text pattern, and field words a date or time pattern.
  - Exact values round by your decided per-type default (half away from zero), and floats half to even.
  - A number joined to another field by `- / . :` or `""` is two digits, except a duration's first field, which is unpadded.
  - `hour12` needs `am_pm`, and `zone_short` writes but doesn't read.
  - `iso_basic` writes the whole compact form:
    - an `Instant` writes `20261108T020500Z`;
    - a zoned time writes `20261107T210500-0500`;
    - a local time writes `20261107T210500`;
    - a date writes `20261107`.

    The readers accept each of them.
  - A date or time pattern on an `Instant` uses `$program.time_zone`; `"{t}"` stays ISO UTC.
  - A hole in a pattern must be a count.
  - TR35 letters, `x.format(…)` and `format(x spec)` are gone, following your D19e.
- **Questions for you:**
  1. **(b) Two pattern spellings:**
     - `iso_basic`, one word for the compact ISO form, so iCalendar, AWS signatures and stamped file names need no member-by-member padding (read fine);
     - `""`, an empty literal that joins two fields, for other compact stamps.

     **Rec:** yes to both.
  2. **(c) Names:**
     - **Fields** (the word patterns read fine): `year`, `month`, `month_name`, `month_short`, `day`, `weekday`, `weekday_short`, `hour`, `hour12`, `am_pm`, `minute`, `second`, `millisecond`, `microsecond`, `nanosecond`, `offset`, `zone`, `zone_short`.
     - **Kinds:** `TextPattern`, `NumberPattern`, `IntegerPattern`, `DatePattern`, `TimePattern`, `DateTimePattern`, `ZonedPattern`.

     **Rec:** yes.
- **Reversible:** yes.
- **Ready:** yes.

---

## P4: open-ended

### D21. Packages (#78)
- **BLUF:** your vendoring lean holds up. One flat `libs/` beside the program, ordinary path imports, and an optional small tool (`dewy add`, `update`, `audit`). The compiler never fetches, and there's no lockfile, registry or solver. Full reasoning: `docs/design/proposals/packages/synthesis.md`.
- **Semantics taken unless you object:** flat instead of nested; author's metadata in `lib.dewy`; the consumer's pin (commit and digest) in a `libs.dewy` at the program root.
- **D21a. How does a library name its own dependency?** The path must work in the library's own repo and under a program's `libs/`.
  - **a)** `from p"@root/libs/geom/lib.dewy" import Point`, where `@root` is the main file's folder. It follows the existing `p"@lib/…"`.
  - **b)** `p"@libs/geom/lib.dewy"`: shorter, but one letter from `@lib`, Dewy's own library.
  - **c)** `p"../geom/lib.dewy"`: no new spelling, but libraries must be flat, and in its own repo the dependency sits outside the repo.
  - Rec: (a).
- **D21b. Metatag names:**

```dewy
# libs/shapes/lib.dewy: written by the library's author
$dewy.version = '0.1.0'
$lib.name = 'shapes'
$lib.version = '1.2.0'
$lib.license = 'MIT'
$needs(name='geom' url='https://github.com/someone/geom' min='2.0.0')

# libs.dewy: written by the tool
$vendor(name='shapes' url='https://github.com/someone/shapes' commit='9f2c…' digest='sha256:…')
```
