# Decisions waiting on David

- **Only open items.** Once you answer one, it moves to [decisions.md](decisions.md), with what was considered and why, and is removed from here.
- **What gets asked:** a semantic question only appears here if it fails one of two tests:
  1. Is the common (80%) path easy, ergonomic and fast?
  2. If the common path doesn't fit, is it straightforward to adjust?

  If both pass, the semantics are taken, and only the syntax is here for you to review.
- **Answering:** reply per item, e.g. "D4 yes, D15a a". Anything you skip stays pending.
- **Example conventions:**
  - Arguments are space-separated, `=?` is equality, value-returning zero-argument calls drop their parentheses, and void calls keep `()`.
  - `or_throw` forwards an error to the caller, `??` substitutes a default for any error or `none`, and `??<E>` does so only for error type `E`.
  - `@f` is a handle to function `f`, and `$name` is a metatag prefixing what it attaches to. Imports of files name their `.dewy` extension; formatting uses `fmt`.
  - Small examples are excerpts. Whole programs follow the questions in each section.
- **Earlier answers and revisions:** see [decisions.md](decisions.md) and the git log.
- **Question kinds:** (a) changes something you decided; (b) new syntax or surface; (c) names only. Question numbers are kept as first asked, so answered ones leave gaps.

**Questions at a glance**
- **(a) Changes something you decided:**
  - D40 Q2, Q5, Q6: cleanup timing, `defer`, and visible cleanup exits;
  - D38 Q1: snake_case naming style;
  - D31 Q1: default gap and fold policies;
  - D31 Q2: `$program.time_zone*` settings under your entry-point rule;
  - D31 Q6: the prefix (`strict_`, `try_`, or per function).
- **(b) New syntax or surface:**
  - D43 Q1, Q2: native database v1 and a database-filter inspection pilot;
  - D41 Q1–Q3: `check_cancel()`, `protect_from_cancel(limit @work)`, `task.tasks(@body)` as ordinary calls;
  - D39 Q1: brackets nest, separators make dimensions (n-D from a nest by shaped type or `stack`);
  - D11 Q2: `check=` or `valid_if=`;
  - D11 Q3: `__read__` or `$reader`;
  - D11 Q4: the checked constructor `Roll(count=…)`;
  - D31 Q5: `Instant<width=64>`;
  - D33 Q1: a self-naming alias;
  - D37 Q1: `iso_basic` and `""`.
- **(c) Names only:**
  - D43 Q3: core database names, with `related` being renamed;
  - D10 Q4–Q8;
  - D11 Q5, Q6;
  - D28 Q1–Q4;
  - D29 Q1;
  - D31 Q4, Q7;
  - D34 Q1;
  - D35 Q1;
  - D36 Q1;
  - D37 Q2;
  - D38 Q2: prefer familiar words;
  - D39 Q2: `stack` and `Ragged`.
- **Unchanged:** D30 (function types without parentheses), D32 (time zone data license) and D21 (packages).

---

## P1: blocking current work

### D40. Cleanup: timing, visible exits and whether `defer` stays

Resources clean themselves up: files flush and close, sockets close, locks unlock, and uncommitted transactions roll back. You decided that a cleanup failure becomes the function's result, with hover and highlighting showing the cleanup (Q1), and that `$__abandon__` discards unpublished work (Q4). `defer` is kept provisionally (Q5). Shared `channel` and `mpmc` keep explicit `close()` (agreed). Combining failures moves from the old Q3 to D42.

#### Q2 (a). Clean up at block end or after last use?

A session must stay open while a separate service applies an update. `Batch` owns a large buffer that its cleanup hook audits; `decode` returns a small summary without borrowing that buffer.

| Last use can close too early | Block end can retain too long |
|---|---|
| `update = () => {`<br>`    let session = service.connect or_throw`<br>`    session.send("begin") or_throw`<br>`    service.apply_side_channel_update() or_throw`<br>`} # Last use closes before the update.` | `summarize = (path:Path) => {`<br>`    let batch = Batch[path.read_bytes or_throw]`<br>`    let summary = decode(@batch.bytes) or_throw`<br>`    long_tail(summary) or_throw`<br>`    return summary`<br>`} # Block end retains the buffer through long_tail.` |

A shorter scoped block repairs the second case:

```dewy
summarize = (path:Path) => {
    let summary = {
        let batch = Batch[path.read_bytes or_throw]
        decode(@batch.bytes) or_throw
    }
    long_tail(summary) or_throw
    return summary
}
```

Run observable cleanup at the owning block's end, or after the owner's last use? Moves transfer the duty and consuming operations can finish it earlier under either rule.

**Rec:** block end, with braces to shorten the lifetime. Its visible boundary stays stable when a later use is added, a generic function gets a different type, or a record gains a fallible field. The adversarial surprise panel slightly favors last use: raw counts **6/7/7**, severity **15/15/17**, for last-use/mixed/block-end; those judgments do not establish real-world frequencies. The recommendation rests on stability under edits and generic code. Plain storage may still be reclaimed early when unobservable. **Reversible:** before implementation; changing observable timing after release can break programs.

#### Q6 (a, new). Show a possible function exit at local cleanup boundaries

```dewy
write_all = (names:array<string>) => {
    loop name in names {
        let out = open(p"{name}.txt" 'w') or_throw
        out.write_text(name) or_throw;
        if name =? "last" break   # Failed close would leave write_all here.
    }
    printl("all written")        # Then this is skipped, without a visible exit above.
}
```

| A. Explicit consuming close | B. Mark an inner block | C. Group the loop body |
|---|---|---|
| `write_all = (names:array<string>) => {`<br>`    loop name in names {`<br>`        let out = open(p"{name}.txt" 'w') or_throw`<br>`        out.write_text(name) or_throw;`<br>`        out.close() or_throw`<br>`        if name =? "last" break`<br>`    }`<br>`    printl("all written")`<br>`}` | `write_all = (names:array<string>) => {`<br>`    loop name in names {`<br>`        {`<br>`            let out = open(p"{name}.txt" 'w') or_throw`<br>`            out.write_text(name) or_throw;`<br>`            if name =? "last" break`<br>`        } or_throw`<br>`    }`<br>`    printl("all written")`<br>`}` | `write_all = (names:array<string>) => {`<br>`    loop name in names ({`<br>`        let out = open(p"{name}.txt" 'w') or_throw`<br>`        out.write_text(name) or_throw;`<br>`        if name =? "last" break`<br>`    } or_throw)`<br>`    printl("all written")`<br>`}` |

Reject a locally continuing exit (`break`, `continue`, or an inner block's end) while fallible cleanup remains unmarked, with a fix-it offering A or B? In B and C the block's `or_throw` acknowledges cleanup on every exit, including jumps that skip its textual end.

**Rec:** A for simple loops, B for complex bodies; this is also the independent review's preference. A places `or_throw` at the failing operation; successful or failed consuming close removes the duty, so cleanup never closes it twice. When conditions or work cannot move after close, B keeps one cleanup region across the existing jumps. C is coherent, but a reader must know that `loop … { … } or_throw` attaches to the whole loop and cannot mark its body. If body failure and cleanup failure both occur, both survive in that order; D42 Q1 decides their representation. **Reversible:** before release; the checked marker rule becomes a control-flow contract afterward.

#### Q5 (a). Does `defer` still earn its place?

These two cases get simpler without restoration. Timing here covers every ordinary result, including errors and cancellation; `serve` owns its internal cleanup.

| With `defer` | Functional rewrite |
|---|---|
| `render = (node:Tree @indent:int64) => {`<br>`    draw(node.label indent) or_throw`<br>`    indent += 1`<br>`    defer indent -= 1`<br>`    loop child in node.children { render(child @indent) or_throw }`<br>`}` | `render = (node:Tree depth:int64=0) => {`<br>`    draw(node.label depth) or_throw`<br>`    loop child in node.children { render(child depth+1) or_throw }`<br>`}` |
| `handle = (request:Request) => {`<br>`    let start = clock.now`<br>`    defer metrics.observe(clock.now-start)`<br>`    return serve(request) or_throw`<br>`}` | `handle = (request:Request) => {`<br>`    let start = clock.now`<br>`    let result = serve(request)`<br>`    metrics.observe(clock.now-start)`<br>`    return result`<br>`}` |

The remaining case restores a C library's global flag across all supported unwinding. Both versions require the same process-wide lock; getting and setting the flag cannot fail, allocate, block or panic.

| One-off `defer` | Small reusable owner |
|---|---|
| `render_quiet = (gate:Mutex<int> scene:Scene) => {`<br>`    let held = @(gate.lock)`<br>`    let prior = $unsafe legacy.get_diagnostics`<br>`    $unsafe legacy.set_diagnostics(false)`<br>`    defer $unsafe legacy.set_diagnostics(prior)`<br>`    return $unsafe legacy.render(scene) or_throw`<br>`}` | `SavedDiagnostics:type = type of [prior:bool`<br>`    $__drop__ = ():>void => { $unsafe legacy.set_diagnostics(prior) }`<br>`]`<br>`render_quiet = (gate:Mutex<int> scene:Scene) => {`<br>`    let held = @(gate.lock)`<br>`    let saved = SavedDiagnostics[$unsafe legacy.get_diagnostics]`<br>`    $unsafe legacy.set_diagnostics(false)`<br>`    return $unsafe legacy.render(scene) or_throw`<br>`}` |

Drop `defer`, using parameters, result capture and small owners instead, or keep its checked one-line form for one-off restoration? Result capture does not cover panic unwinding; the owner does, and it restores the flag before unlocking.

**Rec:** drop, unless you value the one-line form for one-off restorations. Round 7 recommends dropping it; the independent review would keep it provisionally because restoring one borrowed value is shorter with `defer` (the example below). If kept, it remains non-failing and cannot `return`, `break` or `or_throw`. Removal must wait for validation that a local callback owner preserves the caller's borrow and effects and cannot escape; copying the bool is not equivalent. **Reversible:** before release; deletion later breaks source.

#### One borrowed value, both ways

`paint` may fail. Both versions restore the caller's `busy` value on return and supported unwinding; the callback owner must stay local.

| One-off `defer` | Local callback owner |
|---|---|
| `refresh = (@busy:bool) => {`<br>`    let prior = busy`<br>`    busy = true`<br>`    defer busy = prior`<br>`    paint() or_throw`<br>`}` | `RestoreAction:type = type of [action:(():>void & no panics & no allocates & no blocks)`<br>`    $__drop__ = ():>void => action()`<br>`]`<br>`refresh = (@busy:bool) => {`<br>`    let prior = busy`<br>`    let restore = ($capture @busy):>void => { busy = prior }`<br>`    let saved = RestoreAction[@restore]`<br>`    busy = true`<br>`    paint() or_throw`<br>`}` |

Paper dogfood, surprise panel and independent review, with remaining implementation limits: [cleanup proposal](proposals/cleanup/) (round 7 and its review; not all-5).

### D42. Combining failures and seeing where each came from

**Being redesigned around your 2026-11-13 design** (batch 10): `e1 & e2` typed `E1 & E2` as an unordered set, `as` to take a part out, the error stack (`type of error & array`) for repeats, metatag members produced on demand. It comes back compared with the earlier `ErrorGroup` proposal (`proposals/errors/round4.md`), with answers on how `??<E>` treats a combination, how cancellation fits, and distinct error types per operation for cleanup.

### D43. A native database first version, and ordinary lambdas later

The native interface uses Dewy records, functions and methods. It may start on SQLite and later use a Dewy engine; SQL remains a separate first-class interface, as you decided. A selector is a typed value describing a record field; methods such as `lt` build a predicate the database can execute.

#### Q1 (b). Typed storage, indexed queries and explicit commit

```dewy
import p"@lib/std/database.dewy" as database
Account:type = [id:string balance:int]
const A = database.fields_of<Account>
const accounts = [accounts=database.collection<Account>(key=A.id
    indexes=[database.index(A.balance)])]
open_accounts = () => {
    return database.open(accounts p"accounts.db") or_throw
}
```

```dewy
overdrawn = <S>(store:S) => {
    return store.accounts.where(A.balance.lt(0))
        .page(size=20 max_scanned=1000) or_throw
}
```

```dewy
move_one = <S>(store:S) => {
    let tx = store.begin(timeout=2s) or_throw
    let a = tx.accounts.require("ada") or_throw
    let b = tx.accounts.require("bea") or_throw
    tx.accounts.replace([a... balance=a.balance-1]) or_throw
    tx.accounts.replace([b... balance=b.balance+1]) or_throw
    tx.commit() or_throw
}
```

Take this library-only v1 shape: typed collections and references, selectors for planned queries, and task-owned transactions with explicit `commit()`? Other exits abandon unpublished work; cleanup never commits.

**Rec:** yes. Adding an index must preserve values and order; unsupported exact operations use a warned exact local evaluator or fail explicitly. A page size bounds output, while `max_scanned` bounds logical visits; it does not bound bytes or all execution time. The full first release also includes related records, aggregates, structural migrations, backup/restore, search and the separate SQL adapter; those are separable library modules, not prerequisites for the first storage slice. **Reversible:** library surface can evolve before release; stored schema and reference identity need migration contracts afterward.

#### Q2 (b). Ship selectors, then pilot inspection for database filters?

Left and right are alternatives using the same schemas. `S` in the date-range example is the Sale field-selector record; `P.author` is a stored reference, and `A.email` selects its author's email.

| Query | Selectors in v1 | Ordinary lambdas with future inspection |
|---|---|---|
| Negative balances | `negative = <DB>(store:DB) => {`<br>`    return store.accounts.where(A.balance.lt(0)).all or_throw`<br>`}` | `negative = <DB>(store:DB) => {`<br>`    return store.accounts.where((a) => a.balance <? 0).all or_throw`<br>`}` |
| Date range and compound order | `by_day = <DB>(store:DB lo:int hi:int) => {`<br>`    return store.sales.where(database.all_of([S.day.ge(lo) S.day.lt(hi)]))`<br>`        .sorted(key=database.tuple(S.day S.id)).all or_throw`<br>`}` | `by_day = <DB>(store:DB lo:int hi:int) => {`<br>`    return store.sales.where((s) => lo <=? s.day and s.day <? hi)`<br>`        .sorted(key=(s):>[int string] => [s.day s.id]).all or_throw`<br>`}` |
| Posts with an author's email | `by_author = <DB>(store:DB email:string) => {`<br>`    return store.posts.where(database.related(P.author A.email).eq(email))`<br>`        .include([author=P.author tags=P.tags]).all or_throw`<br>`}` | `by_author = <DB>(store:DB email:string) => {`<br>`    return store.posts.include([author=P.author tags=P.tags])`<br>`        .where((row) => row.related.author.email =? email).all or_throw`<br>`}` |

Function inspection would let a `code.Function<F>` parameter receive the callable's resolved typed body and capture descriptions as read-only compile-time data, plus its original executable function at run time. Ordinary lambda type checking happens first, and capture values stay at run time under explicit access and privacy rules.

Ship only selectors first, or also pilot this general language feature for database filters? The lambda column shows the longer-term convenience; its tuple-key translation and included-row filter are beyond the initial one-comparison pilot.

**Rec:** ship v1 on selectors; pilot inspection for database filters only. It could later support test assertions showing a failing subexpression, automatic differentiation and GPU kernels, but needs substantial compiler work. Translation must never change values, errors, ordering or observable effects; unsupported translation or exhausted planning falls back to running the original checked pure, terminating lambda locally, with a warning. Effectful or unproved callbacks instead require an ordinary loop over materialized rows. The compiler cannot prove an arbitrary translator correct merely from its signature; primitive mappings and backend validation belong to the trusted implementation. Before the pilot, specify the typed planning/fallback interface and bound compiler work and retained/emitted size. Optional planning must not drain a budget needed by a future demanded transformation with no fallback, such as differentiation. Keep `$__collect__` and direct comprehension translation, assertions, differentiation and GPU execution out of this pilot. **Reversible:** the experiment can be dropped; a released inspection interface is a substantial language commitment.

#### Q3 (c). Core database names

```dewy
lookup = <S>(store:S id:string) => {
    let account = store.accounts.get(id) or_throw   # May be none.
    return account
}
reference = <S>(store:S id:string) => {
    return store.accounts.reference(id) or_throw   # Checks existence; may fail.
}
```

Use the core names below, while renaming the related-field selector currently spelled `database.related(P.author A.email)`? Round 4 offers no replacement candidate, so that spelling is being renamed rather than put forward as approved.

**Rec:** yes to the remaining core names, with the low-confidence `reference` and `present_only` contracts made explicit before release. `unique(A.email)` permits only one `none`; `unique(A.email present_only=true)` constrains present values only. **Reversible:** names are easy to change before release.

Core names: `fields_of`, `collection`, `Ref`, `open(create= read_only=)`, `memory`, `get`, `require`, `insert`, `reference`, `replace`, `put`, `begin(timeout=)`, `commit`, `rollback`, `snapshot`, `close`; `index`, `unique(present_only=)`, `tuple`, `eq`, `lt`, `ge`, `contains`, `all_of`, `where`, `sorted(key= reverse=)`, `all`, `count`, `page(size= after= max_scanned= max_bytes= timeout=)`, `explain`, `include`, `update`, `delete`; result `.items`, `.next`, `.record`, `.related`. Additional release-module names and error names are not covered by this core ballot.

Paper dogfood remains below all-5; the 45-line core cold read conveyed broad roles except `related` (two readers inferred a join), with low confidence for `present_only` and `reference`; inspection names have not been cold-read: [database proposal](proposals/database/), [function-inspection proposal](proposals/function-inspection/).

### D41. Cancellation helpers as ordinary calls: `check_cancel`, `protect_from_cancel`, `task.tasks`

Ctrl-C, or a failing sibling in a `parallel` block, cancels work. Waits (channels, `sleep`, signals) notice it on their own. These three library calls cover the rest, with no new syntax. Batch 5 left them open ("being redesigned as visible scopes"); the scope-block form was not taken (batch 8), so they come back as ordinary calls.

#### Q1 (b). A cancellation checkpoint in long computations

```dewy
loop i in [0..1_000_000_000) {
    check_cancel() or_throw              # stops here once Ctrl-C arrives
    total += score(i)
}
```

A loop that never waits doesn't notice Ctrl-C until it reaches a checkpoint. Use `check_cancel()` for that?

**Rec:** yes; reversible.

#### Q2 (b). Finishing a save after Ctrl-C

```dewy
match protect_from_cancel(5s @save(best)) {
    saved:Path => printl"saved to {saved}"
    <Timeout> => printl("save didn't finish within 5 s" file=stderr)
    problem:error => printl("save failed: {problem}" file=stderr)
}
```

After Ctrl-C, `save` still runs, for up to 5 s, then the program exits with 130 as usual. Use `protect_from_cancel(limit @work)`? A save stuck inside a C call can't be interrupted, only waited for.

**Rec:** yes; reversible.

#### Q3 (b). A group of tasks started one by one

```dewy
import p"@lib/std/tasks.dewy" as task

accept_all = (port:int group:Tasks) => loop true {
    let conn = accept(port) or_throw
    group.spawn(@handle(conn))           # one task per connection
}
serve = (port:int) => task.tasks(@accept_all(port))   # returns once every task has finished
```

`parallel` covers a known set of items; a server starts a task per connection. `task.tasks(@body)` runs `body` with a fresh group and returns after all of its tasks finish; if one fails, the rest are stopped and waited for, then the failure comes back. Use `task.tasks` from `@lib/std/tasks.dewy` for this?

**Rec:** yes; reversible.

Dogfooded in the concurrency and signals rounds; names read cold. Full rules: `proposals/concurrency/unified/proposal-v5.md`, `proposals/signals/summary.md`.

---

## P2: unblocks common friction

### D10. Safety defaults and tag names (#108)

Safe defaults reject unproven hazards and unconfined paths; tags grant permissions or require stronger proofs. No tag changes a type except the already flagged `$explicit_allocation_failure`.

**Decided by you (2026-11-07):** `@(m.lock)` gives the locked place; `@(m.lock())` is legal, and `@m.lock` is the method handle.

**Decided by you (2026-11-07):** calls keep useful results; a statement ignoring one writes `;`, with no `$discardable_result`.

**Decided by you (2026-11-07):** renames such as `starts_with`, `set_permissions` and `int(text)` wait for the naming-style decision (D38).

#### Q4 (c). Safety tag names

```dewy
$prove_local_asserts
run()                       # prove local $runtime_assert conditions
$allow_unproven_narrowing
let byte = value as uint8   # permit a run-time narrowing check
$prove_no_counter_overflow
let count = count_rows      # require counter overflow proofs
```

Use `$prove_local_asserts`, `$allow_unproven_narrowing` and `$prove_no_counter_overflow`? The first replaces `$count_local_asserts_as_panics`, which was read poorly.

**Rec:** yes.

#### Q5 (c). Random and secure names

```dewy
let roll = random([1..6])                  # also floats, quantities, durations and dates
let bytes = fast_random_bytes(16)
let secret_bytes = secure_random_bytes(16) or_throw
let token = secure_token or_throw
let winner = secure_random([1..100]) or_throw   # plain, unpredictable value
let generator = rng
let seed = generator.seed
```

Use these names, with no bare `random_bytes`?

**Rec:** yes.

#### Q6 (c). Path names

```dewy
let name = FileName(text) or_throw
let file = base.confine(text) or_throw
let safe_name = sanitize_file_name(text)
let relative:SubPath = file.relative_to(base)
```

Use `FileName`, `base.confine(text)`, `sanitize_file_name` and `SubPath`? `RelativePath` failed to convey that the path cannot escape.

**Rec:** yes.

#### Q7 (c). File and process names

```dewy
let last = text.find_last("x")
let folder = config_dir("game") or_throw
folder.make_dir or_throw;
folder.remove_dir or_throw;
file.append_text("saved") or_throw;
loop line in stdin_lines printl(line)
loop line in file.follow_lines printl(line)
let process:Process = start_process("git" ["status"] stdout='pipe') or_throw
```

Use the library names and keywords below, with one name for each file operation's method and function forms? D38 may respell multi-word names.

**Rec:** yes.

**Details:**

- Folders: `config_dir(app)`, `data_dir`, `cache_dir`, `home_dir`, `temp_dir`.
- Keywords: `copy_to(… progress=)`, `write_bytes(… permissions=)`, `input(… hidden=)`, `to_json(… secrets='reveal')`.
- Processes: `start_process(… cwd= env= stdin= stdout= stderr= new_group=)`, `Process`, `.kill`, `ExitStatus` with `.success .code .signal`, and `set_current_dir`.

#### Q8 (c). Float extras

```dewy
let close = a.is_close(b rel=0.01 abs=0.0)
let x = to_float(text allow_nonfinite=true) ?? 0.0
let finite:Finite = value
let same_temperature = room.is_close(before abs=0.5K)
```

Use `is_close`, `allow_nonfinite=true` and `Finite`? `abs=` defaults to the operand type's zero; temperature readings require a `TemperatureDifference` for `abs=` and have no `rel=` (D34).

**Rec:** yes.

#### Other details

- `$bulletproof` compiles hello world. Counter proofs accept any proven-bounded step, including `Atomic.add`; printing scalars does not allocate.
- Float constants retain `x.is_finite` as the guard and a `float64.min` fix-it. A string builder, `which` and HTTP remain library work.

#### The whole design in one program

```dewy
Reset:type = [user:string token:secret<string>]
let saves = p"saves"

issue = (user:string) => Reset[user secure_token or_throw]       # secret<string> | NoEntropy

save = (slot:string data:string) => {
    let file = saves.confine("{slot}.sav") or_throw  # SafePath, or PathEscape back to the caller
    file.write_text(data) or_throw                   # the Path written: save's result
}

main = () => {
    saves.make_dirs or_throw;                        # gives back the path; `;` drops it
    loop name in saves.list or_throw printl'{name}: {p"{saves}/{name}".size or_throw}'   # FileName: confined; a DataSize
    let slot = input("save name? ") or_throw
    let f = save(slot "level=3") ?? { printl"pick a plain name"; return }      # "../x" is a PathEscape
    save(sanitize_file_name(slot) "level=4") or_throw;                         # any text made one safe name; `;` drops the path
    let level = to_int(input("level? ") or_throw) ?? 1   # bad text gives 1; Ctrl-C still stops (D4)
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

Dogfooded; names read cold. Full rules: `proposals/bulletproof/round3.md` and `proposals/integration/amendments.md`.

### D11. Compile-time shapes, action names, audio handles and removed physics bodies (#131–#133)

Shapes check literals while compiling and validate outside text through `T(text)`. A failed conversion, checked constructor or text reader returns `ValidationError`; shapes replace `$check_constant` and `$error_if`.

**Decided by you (2026-11-07):** `let a:Action = s` and `s as Action` require proof; narrowing never panics at run time, and `Action(s)` returns the failure as a value.

#### Q2 (b). Validation keyword

```dewy
Sku:type = string<check=@sku_problem>   # preserves a message
Sku:type = string<valid_if=@is_sku>      # alternative suggests a bool
```

Use `check=` for the validator? `valid_if=` read best but suggests a bool, which cannot explain the failure; `shape=` read poorly.

**Rec:** `check=`.

#### Q3 (b). How a type reads text

```dewy
__read__ = (text:string):>Roll | ValidationError => …
# or a tag on an ordinary function:
$reader
parse_roll = (text:string):>Roll | ValidationError => …
let dice = Roll(text) or_throw
```

Use a `__read__` protocol found by its result type, like `__as__` and `__add__`, or a `$reader` tag? `Roll(text)`, `input_field` and union readers use the chosen reader.

**Rec:** `__read__`: one mechanism with the library's protocols.

#### Q4 (b). Checked record constructor

```dewy
Roll:type = [count:int64<(1 <=? x <=? 100)> sides:int64<(2 <=? x <=? 1000)>]
let literal = Roll[3 6]                 # proven literal
let checked = Roll(count=n sides=6)     # Roll | ValidationError
```

Add `Roll(count=3 sides=6)` as a checked record constructor, while `Roll[…]` stays the proven literal?

**Rec:** yes.

#### Q5 (c). One validation error name

```dewy
let shaped = Sku(text)         # Sku | ValidationError
let checked = Roll(count=n sides=6)   # Roll | ValidationError
let parsed = Roll(text)        # Roll | ValidationError
```

Use `ValidationError` for “this is not a valid T” in every shape conversion, checked constructor and text reader? It replaces `ShapeError`, `ParseError` and `TextError`.

**Rec:** yes.

#### Q6 (c). Audio and controls names

```dewy
let tune:PlayingSound = play(melody("E4/2 E4*3"))
tune.pause(); tune.resume(); tune.stop()
let running = tune.running; let paused = tune.paused
let position = tune.position; let length = sound.length
let lost = input.rebind('jump' 0 Input.key(Key.w) conflict=policy)
controls_editor(@input)
let pressed = input.pressed_at('tap')
let at_press = sound.position_at(reading)
```

Use these audio and controls names, plus the companion names below? `pressed_at` and `position_at` read weakly, and the latter can sound like spatial placement; `CountHoleTemplate` and `CountedPattern` both failed, with the former kept as the better library-author name.

**Rec:** yes.

**Details:**

- Audio also has `.wait`; an unheld sound plays to its end, and `.running` stays true while paused.
- Controls: `reset`, `save`, `load`, `bindings`, `input_hint`, `listen_for_press` with `.next`.
- Validation: `forbid`, `load_sound`, `CountHoleTemplate` for checking computed pattern widths. `load_sound(path)` gives `Sound | ValidationError | FileNotFound`.

#### Other details

- Shapes work on any type, may read other parameters and may select shaped overloads; passing constant, effect-free calls fold. A failed constant never falls through to a plain `string` overload. Refinements read through their base reader and then their check.
- For removed physics bodies, `w.get(ball)` gives `BodyState | none`; `w.pos(ball)` is proven after `add` or within `if w.has(ball)`, or checked under `$allow_unproven`. After `w.remove(ball)`, `w.pos(ball)` is an error even under that tag. `w.has` replaces `alive` and `joint_alive`.
- `input.pressed_at` gives the event's `ClockReading | none`; `sound.position_at(reading)` gives the song position at that moment. `Controls<A>` and `Binding` replace `action` and `action_pressed`.

#### The whole design in programs

```dewy
sku_problem = (text:string):>string | none =>
    if text.length =? 8 and text.startswith("SKU-") none
    else "'{text}' is not a SKU: SKU- and four characters, like SKU-12AB"
Sku:type = string<check=@sku_problem>
Port:type = int64<(1 <=? x <=? 65535)>
Roll:type = [count:int64<(1 <=? x <=? 100)> sides:int64<(2 <=? x <=? 1000)>]
__read__ = (text:string):>Roll | ValidationError => {          # how a Roll reads from text, like "3d6"
    let parts = text.split("d")
    if parts.length not=? 2 return ValidationError[message="write dice like 3d6" input=text]
    Roll(count=to_int(parts[0]) or_throw sides=to_int(parts[1]) or_throw)  # checked constructor: Roll | ValidationError
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
    play(tone(440Hz 80ms));                    # `;` drops the handle; the sound still plays to the end
    printl'{item} {port} {dice} {b} {f2(1.5)} {day(date"2026-11-07")}'
    f2("hi")                                   # compile error: fmt'.2f' formats numbers; found string
    tune.stop()
}
```

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
    input.save(p"controls.txt") or_throw;                # only the player's changes; `;` drops the path
    let unknown = input.load(p"controls.txt") or_throw   # names a stale file had; never a crash
    printl"{lost} {unknown}"
}
```

Dogfooded; names read cold, with the weak names flagged above. Full rules: `proposals/ui/round2-with-string-shapes.md` and `proposals/integration/amendments.md`.

### D28. Clay-style UI

A frame's UI is a value tree. Widgets write into variables, picks use your union, and input fields read human text; no new syntax is needed.

#### Q1 (c). Core UI names

```dewy
let tree = column(gap=12 pad=24 width=420 [
    text("Paused" size=36)
    button('resume' "Resume" id='resume')
])
let picked = ui<Choice>(back='resume' align='center' tree)
```

Use `column row box grid scroll floating tooltip modal spacer text image button checkbox slider choice progress`, `ui`, `show`, `pick=`, `id=`, `pad`, the sizes, the nine-point `align`, and `back=`?

**Rec:** yes.

#### Q2 (c). Typed input names

```dewy
input_field("Port" @port hidden=false lines=1 read=@read_port error=problem)
let can_save = valid("Port")
let duration = Duration.parse_human("30 days") or_throw
```

Use `input_field`, `valid(id)`, `hidden=`, `lines=`, `read=`, `error=` and `T.parse_human(text)`? `from_label` was read as enum lookup.

**Rec:** yes.

#### Q3 (c). Other widget names

```dewy
if changed("Volume") update_volume()
if committed("Name") save_name()
choice("Mode" @mode style='tabs')
slider("Volume" @volume [0.0..1.0] step=0.05 value_text=fmt'.0%')
plot(values range=[0.0..1.0] style='bars')
```

Use these widget names and the companion names and keywords below?

**Rec:** yes.

**Details:**

- `label`; choice styles `'dropdown' 'segments' 'list' 'tabs'`; slider keywords `scale='log'`, `suffix=`, `descending=`.
- `table`, `heading`, `TableSort`, `divider`; `tip=`, `shortcut=`, `enabled=`, `selected=`, `animate=`.
- `panel`, `menu_bar`, `menu`, `context_menu`, `collapsible`, `layers`, `row(wrap=)`.
- `drag=`, `ui(drop=)`, `right_clicked`, `double_clicked`, `dragged`, `ui(focus= player=)`.

#### Q4 (c). Checkbox derived state

```dewy
checkbox("Ready" checked=downloads_done)   # displays derived state
checkbox("Full screen" @fullscreen)        # lets the checkbox change it
```

Use `checkbox(title checked=expr)` for derived state? Since it was mistaken for two-way binding, a plain variable there gets the hint “to let the checkbox change it, write `@x`”.

**Rec:** yes, with the hint.

#### Other details

- The tree uses the last frame's layout; stale state cannot crash. Ids in `valid`, `changed` and `committed` are checked against the same function's tree.
- Input widgets draw: they cannot be in a `const` tree; a tree retained across frames draws them disabled. Static subtrees may be `const`.
- Frame code may do file I/O, but cannot wait on channels, tasks or timers. A game's `update` takes `dt:Duration`.
- `label(none)` is `""`. `T.parse_human` accepts programmer text too; a duration accepts “30 days” as 720 hours and rejects “1 month”. A choice with no list uses union text order.
- `scroll`, `grid`, `floating`, wrapping, table column sizing and drag and drop are least proven; there is no `no allocates` builder yet.

#### The whole design in one program

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

draw = () => if screen =? 'paused' pause_menu()

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
    if picked =? 'save' p"settings.txt".write_text("{player} {port} {keep}") ?? { news = "not saved" };  # file I/O in draw compiles; `;` drops the path
    else if picked =? 'resume' screen = 'playing'
    else if picked =? 'quit' screen = 'title'
}
```

Dogfooded; names read cold. Full rules: `proposals/ui/round2-with-string-shapes.md` and `proposals/integration/amendments.md`.

---

## P3: lower stakes

### D29. Dates: weekday names, dates from numbers, stepping (all reversible)

Weekdays have names, dates can be built from numbers, and discrete ranges step by days or another calendar unit.

#### Q1 (c). Date and stepping names

```dewy
let d = date(2026 11 10)
let weekday:Weekday = d.weekday
let t = time_of_day(9 30 second=0)
let friday = d.next('friday'); let zoned_friday = z.next('friday')
let second = d.nth_weekday_of_month(2 'tuesday')
let anniversary = born.next_anniversary(after=d)
let week = d.floor(1week); let first = days_of_week[0]
loop day in [d..d + 1month).step(1day) printl(day)
```

Use `Weekday` and its seven members, `iso_weekday`, `next`, `nth_weekday_of_month`, `next_anniversary(after=)`, `floor`, `step`, `days_of_week`, `date(year month day)` and `time_of_day(hour minute second=0)`? `weekdays` was read as Monday to Friday.

**Rec:** yes. **Reversible:** yes.

#### The whole design in one program

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

Dogfooded; names read cold. Full rules: `proposals/time/units-and-format-round1.md` and `proposals/integration/amendments.md`.

### D30. Function types without the outer parentheses

Bare function types shorten annotations, but make labeled parameters ambiguous between lambdas and types.

```dewy
apply = (f:int:>int x:int):>int => f(x)              # bare: parses and runs
g = (x:int64:>int64) => x(1)                         # a parameter x of type int64:>int64
let h:(x:int64:>int64) = (v:int64):>int64 => v+1     # a function type with labeled parameter x:int64
```

Allow function types without their outer parentheses? The bare form also fails in lambda results and after `is?`; `f:int:>int?` can only mean an optional result, while the built `f:(int:>int)` is unambiguous.

**Rec:** leave bare off. Today it gets the hint "a function type takes parentheses here". **Reversible:** yes.

### D31. Time spellings: zoned defaults, rounding, ranges, compact instants, one prefix (all reversible)

A clock change can skip a local time (a gap) or repeat one (a fold). Zoned arithmetic has default policies for both; ranges name their bounds, and strict calls return failures as values. Rounding keeps your per-type defaults.

**Decided by you (2026-11-07):** `rounding=` replaces `ties=` on numeric and time rounding, `quantize` and `fmt`; `select` uses `priority=` (batch 8).

#### Q1 (a). Default gap and fold policies

```dewy
let meet = zoned"2026-10-31T01:30[America/New_York]"
let next = meet + 1day                    # fold: take the earlier time
let strict = meet.add(1day gap='reject' fold='reject')   # failures as values
```

Use default policies that move gaps forward and choose the earlier time in a fold, replacing “never guesses”? A literal hitting either warns; explicit rejecting policies remain one argument away.

**Rec:** yes. **Reversible:** yes.

#### Q2 (a). Program time-zone settings

```dewy
$program.time_zone = 'America/New_York'
$program.time_zone_rules = 'urgent.bin'
# Alternative rules: $program.time_zone_source = 'host'

main = () => printl(today)   # header applies when this file is the entry
```

Replace `$time.zone`, `$time.rules` and `$time.zone_source` with these `$program.*` names under your entry-point rule? They belong in the entry header or inside a file's `main` that runs as entry; elsewhere they are compile errors naming both allowed places.

**Rec:** yes. **Reversible:** yes.

**Details:**

- This narrows D15a: a main file with no zone no longer leaves libraries and scopes free to choose the program's zone. A library may set its own test `main`'s zone, or pass `zone=` / call `t.in_zone(z)` for a particular zone.
- Your D4 Q7 answer (batch 9) lets any function set a zone at the top of its body, for its calls and tasks (a per-user zone, say). With it, the entry-only rule here applies only to the file header; a library's own header can't set the program's zone.

#### Q4 (c). Range bound names

```dewy
let r = [date"2026-01-01"..date"2026-02-01")
printl'{r.start} {r.end} {r.includes_start} {r.includes_end}'
# arrays keep .first / .last: actual members, rather than bounds
```

Replace `Range<T>`'s `.first`, `.last` and inclusion names with `.start`, `.end`, `.includes_start` and `.includes_end`? A half-open range's upper bound is not a member.

**Rec:** yes. **Reversible:** yes.

#### Q5 (b). Compact instants through a value parameter

```dewy
let t = instant"2026-01-01T00:00:00.5Z"
let compact = convert<Instant<width=64>>(t)   # Instant<width=64> | OutOfRange
```

Use `Instant<width=64>` as an ordinary value parameter whose alias body is computed while compiling? This general facility also serves `uint<bits>` families.

**Rec:** yes; the fallback is a separate type, `CompactInstant`. **Reversible:** yes.

#### Q6 (a). One prefix for failures as values

```dewy
let day = strict_today
let sum = t.strict_add(1day)
let zoned = t.strict_in_zone(zone"Asia/Tokyo")
# alternative shared prefix: try_today / try_add / try_in_zone
```

Keep `strict_` for the same call with its failures as values, switch to `try_`, or name each function separately? `strict_today` is your earlier choice; no prefix reads well on every function.

**Rec:** keep `strict_`, unless you prefer `try_`. **Reversible:** yes.

**Details:**

- The family is `strict_today`, `strict_add`, `strict_in_zone`, `strict_elapsed`, `strict_zone` and `$time.only_strict_today`; it pairs with `$time.strict`.
- `strict_add` was read as overflow checking; `strict_in_zone` as “strictly inside a zone”. `checked_add` read correctly, but `checked_today` sounded like “something was checked today”. `try_today` read no better; `try_` can suggest an optional or boolean result rather than a failure value.
- One prefix makes the careful twin discoverable. Hovers and fix-its state the strict call's result type.

#### Q7 (c). Time operation and policy names

```dewy
let bucket = t.floor(1minute); let ceiling = t.ceil(1minute)
let rounded = t.round(1s rounding='nearest_even')
let meeting = z.at(time_of_day"09:00")
let local_meeting = d.at(time_of_day"09:00")
let l = local"2026-11-01T01:30"
let later = l.in_zone(zone"America/New_York" fold='later')
```

Use `floor`, `ceil`, `round`, `at`, `time_of_day`, `local`, `fold='later'`, `$time.no_assumed_zone`, the `$time.no_assumed_*` family and `$time.no_dropped_zone`? `strict_elapsed` and `strict_zone` follow Q6.

**Rec:** yes. **Reversible:** yes.

#### Other details

- Rounding modes are `nearest_away`, `nearest_even`, `nearest_toward_zero`, `nearest_up`, `nearest_down`, `floor`, `ceil`, `toward_zero`, `away_from_zero`. Exact values round half away from zero; floats half to even.
- Range emptiness requires declared discreteness (`next_up`) or density (`$no_next_value`); otherwise `is_empty` is an error. `$no_next_value` and `$no_successor` both read weakly as permission to take an unproven next value; the former remains the library-author name.
- `in_zone` is total. Integer multiples of on-grid ticks stay on-grid, and proven-nonzero division gives plain values. Readers give `T | ValidationError`; strict tags name strict functions rather than change result types.

#### The whole design in programs

```dewy
$program.time_zone = 'America/New_York'                    # program settings: entry header, or inside entry main
$program.time_zone_rules = 'urgent.bin'                    # a rule pack beside the entry file

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

```dewy
# meetings.dewy: a library; `dewy meetings.dewy` runs this main, and importing the file never does
next_meeting = (after:Instant):>ZonedDateTime => (after.in_zone(zone"Asia/Tokyo") + 1day).at(time_of_day"09:00")
main = () => {
    $program.time_zone = 'Asia/Tokyo'      # applies only when this file is the entry
    printl(next_meeting(now.nominal))
}
```

Dogfooded; names read cold, with the prefix limits above. Full rules: `proposals/time/units-and-format-round1.md` and `proposals/integration/amendments.md`.

### D32. Unicode-licensed time zone data in the repository

The rule pack maps Windows zone names to IANA names using Unicode's CLDR table. Keeping it requires Unicode's copyright and permission notice alongside the data; the project currently uses Apache-2.0 WITH LLVM-exception with no NOTICE file.

```dewy
$program.time_zone = 'system'   # Windows: use the mapping, or warn and fall back to UTC

main = () => printl(today)
```

Keep the table and add Unicode's notice beside it (a), or drop the table (b)? Without it, Windows programs must explicitly choose an IANA zone through the program setting or `TZ` to avoid the UTC fallback.

**Rec:** (a). Windows machines report only their Windows name, so without the table every Windows program needs a setting. **Reversible:** yes.

### D33. A type alias that names itself in a self-length refinement

A self-length refinement constrains array elements using that array's length. Naming it with an alias lets functions return it directly.

#### Q1 (b). An alias that refers to its own length

```dewy
Parents:type = array<int64<(<? Parents.length)>>
make_parents = (n:int64<(>? 0)>):>Parents => {   # named result type
    let p:Parents = [0]
    loop p.length <? n { p.push(p.length) }
    p
}
```

Allow an alias to name itself in a self-length refinement? This is the first such self-reference; every other alias self-reference stays an error, and the existing workaround is an output parameter or a record field.

**Rec:** add it when returning these arrays matters. **Reversible:** yes.

Dogfooded. Full rules: `proposals/time/units-and-format-round1.md`.

### D34. A temperature difference type, and readings as numbers

A temperature reading and a temperature difference are distinct types. A reading exposes its number on a chosen scale; comparing readings requires a difference as the tolerance.

#### Q1 (c). Temperature and thermal resistance names

```dewy
let rise:TemperatureDifference = 70°F - 30°F
let wall:ThermalResistance = 25.0r_value_us
let metric = wall as r_value_si
let room:Temperature = 21.4°C
let bare = room.value_in(°C)   # 21.4, without the unit
```

Add `TemperatureDifference` and `q.value_in(unit)`, and replace `RValue`, `R`, `RSI` with `ThermalResistance`, `r_value_us`, `r_value_si`? The old names failed the cold read.

**Rec:** yes. **Reversible:** yes.

#### The whole design in one program

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

Dogfooded; names read cold. Full rules: `proposals/time/units-and-format-round1.md` and `proposals/integration/amendments.md`.

### D35. `in_zone` on a zoned time, and a total `in_zone`

`in_zone` shows the same moment in another zone and always returns a value. Its strict twin reports when the answer extends beyond the zone's recorded transitions.

#### Q1 (c). Zone conversion names

```dewy
let slot = zoned"2026-11-01T09:00[America/New_York]"
let berlin = slot.in_zone(zone"Europe/Berlin")          # ZonedDateTime
let checked = slot.nominal.strict_in_zone(zone"Asia/Tokyo")   # may be OutsideCoverage
```

Add `zoned_time.in_zone(zone)` and `strict_in_zone`, with the strict prefix following D31 Q6?

**Rec:** add both. **Reversible:** yes.

**Details:** `in_zone` uses the TZif footer rule forward and local mean time backward; `$time.no_assumed_extrapolation` requires the strict call.

#### The whole design in one program

```dewy
$program.time_zone = 'America/New_York'

const where = fmt'weekday_short hour:minute zone'
let slot = zoned("2026-11-01T09:00" zone=zone"America/New_York")   # constant text: folds to a value
let berlin = slot.in_zone(zone"Europe/Berlin")             # a ZonedDateTime
printl(where(berlin))                                      # Sun 15:00 Europe/Berlin
printl(slot.nominal.strict_in_zone(zone"Asia/Tokyo"))      # ZonedDateTime | OutsideCoverage, for the strict
```

Dogfooded; names read cold. Full rules: `proposals/time/units-and-format-round1.md`.

### D36. Unit dimensions and the missing common units

The units library names common dimensions and units. Quantities keep their written unit and read back from printed text; `Quantity` and `Unit` handle dimensions learned only at run time.

#### Q1 (c). Dimension, unit and run-time names

```dewy
let used:Energy = 1392kWh
let cap:DataSize = 512MiB
let q = Quantity("5.5lb") or_throw
let u = Unit("kg") or_throw
let converted = q.to(u)   # Quantity | DimensionMismatch
printl(q.dimension)
```

Use the dimension, unit and run-time names below? `DataSize` replaces `Information`, which sounded like a log message; `stick_butter_us` read weakly and has `butter_stick_us` as an alternative.

**Rec:** yes. **Reversible:** yes.

**Details:**

- Dimensions: `Area Volume Speed Acceleration Force Energy Power Pressure ThermalResistance DataSize Frequency Charge Voltage Resistance Density Torque`.
- Units: `lb oz stone short_ton long_ton tonne nmi acre hectare ha gallon_us gallon_uk quart_us pint_us pint_uk fl_oz_us cup_us tbsp_us tsp_us tbsp tsp stick_butter_us mph knot kPa MPa hPa bar mbar atm psi mmHg inHg Wh MWh GWh cal kcal eV therm hp lbf standard_gravity C Ah mAh rpm bit B byte kB MB GB TB KiB MiB GiB TiB kbit Mbit Gbit`.
- Run time: `Quantity(text)`, `Unit(text)`, `q.to(u)`, `.dimension`, `DimensionMismatch`.

#### Other details

- Bare dimensions default to `float64`; `Area<rational>` stays exact, and exact arguments round once into float parameters. `B = 8bit`, `MB` is 10⁶ bytes and `MiB` is 2²⁰ bytes.
- SI prefixes are generated for SI units. Nothing prints an unwritable unit: `10min` is an error pointing to `10minute`. Dimension readers accept text; JSON writes quantities as printed text. The run-time unit table links only when used.
- Money is outside this round: until user-declared base dimensions, it is exact `rational` and mixed currencies are not caught.

#### The whole design in one program

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

Dogfooded; names read cold. Full rules: `proposals/time/units-and-format-round1.md` and `proposals/integration/amendments.md`.

### D37. `fmt` patterns for dates, times, durations and units

`fmt` checks word-based date and time patterns while compiling. Number patterns keep units, and readers accept the same patterns and the text they write.

#### Q1 (b). Compact pattern spellings

```dewy
let sent = instant"2026-11-08T02:05:00Z"
printl(fmt'iso_basic'(sent))                 # 20261108T020500Z
printl(fmt'year""month""day-hour""minute'(sent))   # "" joins fields with no separator
```

Use `iso_basic` for compact ISO output and `""` for joining fields in other compact stamps? These cover iCalendar, signatures and file names without member-by-member padding.

**Rec:** yes to both. **Reversible:** yes.

#### Q2 (c). Pattern fields and types

```dewy
const when:DateTimePattern = fmt'weekday day month_name, hour12:minute am_pm'
const number:NumberPattern = fmt'.2f'
const count:IntegerPattern = fmt',d'
const text:TextPattern = fmt'>12'
const time:TimePattern = fmt'hour:minute'
const day:DatePattern = fmt'year-month-day'
const zoned:ZonedPattern = fmt'year-month-day hour:minute offset'
```

Use these pattern type names and the field words below?

**Rec:** yes. **Reversible:** yes.

**Details:**

- Fields: `year month month_name month_short day weekday weekday_short hour hour12 am_pm minute second millisecond microsecond nanosecond offset zone zone_short`.

#### Other details

- Pattern kinds do not overlap: integer style selects an integer pattern, other number options a number pattern, fill/alignment/width alone a text pattern, and field words a date/time pattern. Number patterns use Python's mini-language.
- Adjacent numeric fields joined by `- / . :` or `""` have two digits, except a duration's unpadded first field. `hour12` needs `am_pm`; `zone_short` writes but does not read; pattern holes must be counts.
- `iso_basic` writes an instant with `Z`, a zoned time with its offset, a local time without an offset, and a date alone; readers accept each. An `Instant` pattern uses `$program.time_zone`, while plain interpolation stays ISO UTC.
- Exact rounding stays half away from zero; float rounding stays half to even. `DatePattern(text)` and `NumberPattern(text)` support run-time patterns. TR35 letters, `x.format(…)` and `format(x spec)` are removed, following D19e.

#### The whole design in one program

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

Dogfooded; names read cold. Full rules: `proposals/time/units-and-format-round1.md` and `proposals/integration/amendments.md`.

### D38. Naming style: snake_case or Julia-style joined words

A consistent separator makes multi-word names predictable. A separate rule chooses familiar words for those names.

#### Q1 (a). snake_case or joined words

```dewy
"report.txt".starts_with("rep")   # snake_case
"report.txt".startswith("rep")    # joined words
d.nth_weekday_of_month(2 'tuesday')   # vs d.nthweekdayofmonth(2 'tuesday')
```

Use snake_case under the rule below, replacing your earlier `startswith` and `endswith` choice? This releases the renames waiting in D10; it takes about ten renames, while joined words take over 120 plus tags, keyword arguments and union members.

**Rec:** yes.

**Details:**

- Put `_` between English words. English single words stay joined: `weekday`, `uppercase`, `filename`.
- No abbreviations except the fixed list (`dir`, `len`, math names, `printl`). “Did you mean” ignores underscores and case, so `startswith` points to `starts_with`.

#### Q2 (c). Prefer familiar words

```dewy
text.capitalize
text.rfind("x")
text.lines
mapping.contains_key(key)
```

When choosing words, prefer the name programmers already know from Python, Rust, JavaScript or Go, unless it misleads in Dewy?

**Rec:** yes.

Names tested cold. Full study and tests: `proposals/naming-style/`.

### D39. Nested array literals: brackets nest, separators make dimensions

Separators build multidimensional arrays from scalars; brackets build arrays of arrays. A shaped type or a fallible `stack` call turns nested arrays into a multidimensional array.

**Decided by you:** batch 6's separator rule stays, including `(f();)` when discarding inside an array.

#### Q1 (b). Brackets nest; separators make dimensions

```dewy
m = [1 2 ; 3 4]                              # 2×2
rows = [[1 2] [3 4]]                         # array of arrays
let t:array<int length=[2 2]> = [[1 2] [3 4]] # shaped type asks for 2×2
rows[1].push(5)                              # nested rows may differ in length
```

Keep brackets as nesting and separators as dimensions, with multidimensional conversion only through a shaped type or `stack`? Automatic collapse breaks row mutation and requires annotations when row lengths are known only at run time.

**Rec:** yes. **Reversible:** yes.

**Details:**

- `[xs ; ys]` becomes an array of arrays, like `[xs ys]`, rather than stacking rows. `[[1 2 3]]` holds one array, not a 1×3 array.
- `xs[new]` gives `length=[1 n]`; `[1 2 3 ;]` is also 1×3. `v[.. new]` is a column with `length=[n 1]`.
- Comprehensions contribute one flat run: spacing or separators inside their statement/block body never add dimensions. For a matrix, build nested rows, then use a shaped type or `stack`.

#### Q2 (c). Stacking nested arrays

```dewy
rows = [loop line in lines line.split(",")]
table = stack(rows) or_throw   # n-D array | Ragged; empty rows also fail
```

Use `stack(rows)` and `Ragged`, including failure for an empty list? `stack_rows` suggests only two dimensions, while `stack` also makes cubes from frames.

**Rec:** `stack` and `Ragged`.

Dogfooded; names read cold. Full design, review and parser fixtures: `proposals/array-literals/round2.md`; the parser makes one forward scan per gap, skips comments and does not backtrack.

---

## P4: open-ended

### D21. Packages (#78)

Dependencies live in one flat `libs/` beside the program and use ordinary path imports. An optional `dewy add/update/audit` tool manages them; the compiler never fetches, and there is no lockfile, registry or solver.

#### D21a. A library's own dependency

```dewy
from p"@root/libs/geom/lib.dewy" import Point   # a: main file's folder
from p"@libs/geom/lib.dewy" import Point        # b: shorter
from p"../geom/lib.dewy" import Point           # c: relative sibling
```

How should a library name a dependency so the path works both in its own repository and under a program's `libs/`? (a) follows `@lib`; (b) is one letter from Dewy's own `@lib`; (c) needs flat libraries and puts the dependency outside the library's own repository.

**Rec:** (a).

#### D21b. Metatag names

```dewy
# libs/shapes/lib.dewy (author)
$dewy.version = '0.1.0'
$lib.name = 'shapes'
$lib.version = '1.2.0'
$lib.license = 'MIT'
$needs(name='geom' url='https://github.com/someone/geom' min='2.0.0')
# libs.dewy (tool)
$vendor(name='shapes' url='https://github.com/someone/shapes' commit='9f2c…' digest='sha256:…')
```

Use these metatag names for the library author's `lib.dewy` metadata and the tool-written `libs.dewy` pin (commit and digest)?

Full reasoning: `proposals/packages/synthesis.md`. Flat layout, author metadata and consumer pins are taken unless you object.
