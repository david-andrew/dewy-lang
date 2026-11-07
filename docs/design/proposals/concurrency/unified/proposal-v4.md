# One `parallel`, v4 (2026-11-07)

Revises `docs/design/proposals/concurrency/unified/proposal-v3.md` and `names.md` against four reviews: `parallel-v3-soundness.md`, the parallel parts of `parallel-safety.md`, consistency-audit findings 4, 5, 9, 10, 12, 15 and 17, and D26/D27. Covers open items D4, D22, D26 and D27. Programs: `~/dev/tmp/rev-1107/parallel/` (paper unless marked; `probe/` holds today's compiler checks).

Unchanged from v3 and already approved: the three shapes, `tasks`, the removals, C1 (items may wait, the strategy is inferred), C3 (`or_throw` leaves the function), C5 (`select` is a library call used with `match`).

## BLUF

- **The block form keeps David's rule. Its promise is now stated precisely and holds.** If every item succeeds, every ordinary value matches a top-to-bottom run, given the same answers from handles (atomics, channels, locks, files, clocks). What a handle returns depends on timing. On failure, independent items may already have written, and nothing is rolled back. The analysis now also covers places, receivers, callees, closures and globals. An edge waits for its predecessor to complete successfully, and wait cycles go through the deadlock analysis (§3).
- **One sharing rule per construct (this resolves D26 against v3's `total` examples).** Block items share the function's variables, and the dependency graph orders their accesses. Loop bodies may write only their own element. A `group.spawn` task can't write outer variables. Moving a write between these forms gives the same result or a compile error, never a silent copy (§2).
- **`?? void` follows exactly the rules of an `if` without `else`.** v3's ban on using it in an inferred function body is dropped. The precise rule for which values are dropped is in §4. `xs.partition_failures` keeps both the successes and the failures.
- **Cancellation:** the first Ctrl-C prints a notice at once. A Ctrl-C that reaches the end of `main` exits with status 130 and prints no error report. `shielded(5s @save(best))` saves after a cancel. Writing `check_cancel` without `or_throw` is an error. `group.spawn` returns a `Task`, so one task can be canceled or waited on by itself (§5, §6).
- **`select`:**
  - The result types are exact, and every pair of waits must give results you can tell apart.
  - Operations come in through a reusable `Selectable` protocol, not just any function handle.
  - A send that loses keeps its payload.
  - `timeout=` also takes a deadline, and `ticker(1s)` can be one of the waits.
  - Proposed new syntax: `or_throw<Canceled>`, the mirror of `??<E>` (§7).
- **`parallel i in [0..n) { xs[i] … }` must compile.** The loop's range facts reach the body, and a write to `xs[i]` with the loop's own `i` is a write to its own partition (§8).
- **The core limit is counted in cores everywhere:**
  - `$program.max_cores` for the whole program;
  - `$parallel.max_cores` for a scope;
  - `$placement.cores = [0 1]` to pin to particular cores;
  - `available_cores` to read the current limit;
  - the `DEWY_MAX_CORES` environment variable, which can only lower it.

  `$parallel.off` now means a deterministic, source-order schedule, accepted everywhere. Every tag has a value type and a scope class (§9).
- **D26 and D27: nothing is left for David.** Both are restated in v4 forms and pass both tests. Delete them from open_decisions.md; D4 carries one flagged line for each.

## 1. Findings and where each is fixed

| Finding | Source | Fix |
|---|---|---|
| Sequential-value promise unsound (handles, failure, deadlock) | soundness §1 | §3: qualified promise, completion edges, wait analysis |
| Places, element fields, receivers, closures, globals missed | soundness §1 | §3 footprint rule |
| `?? void` cardinality, sink and filter set | soundness §2; audit 4 | §4 |
| `select` overlap incomplete; typed rest pack; handle protocol; send ownership | soundness §3; audit 9 | §7 |
| Unit of the core limit: cores or threads | safety 12; audit 10 | §9: cores |
| `group.spawn` returns nothing | safety 13 | §6: `Task` |
| First Ctrl-C looks ignored; no way to save on cancel; exit code | safety 07, 05 | §5 |
| `parallel i in [0..n) { xs[i] … }` rejected | safety 08 | §8 |
| D26 vs v3 block writes; D26/D27 use removed syntax | safety 13; audit 5, 17 | §2, §11 |
| Names disagree across D4, v3 and names.md | audit 10 | §9: one inventory; v3 §8 superseded |
| Scope class of each metatag | audit 12; safety 03, 04 | §9 |
| Words for the keyword arguments: `grouping=`, `rounding=`, `ties=` | audit 15 | §10 |
| `( … )` order inside a block | audit, appendix | §3.6 |
| `<Canceled>` arm in every `select`; ticker; names in the one-wait form | safety 05 | §7 |
| `or_throw` after `loop x in f() …`; a forgotten `} or_throw` | safety 02, 04 | §12 |
| Dropped failures can't be counted; `sum([parallel …])` fusion | safety 06 | §4 |
| `$parallel.off` overlaps `max_cores = 1` | safety 12 | §9 |
| A `printl` with no data link prints first | safety 13 | §3.7: a compile note |
| Block `let`s are visible after the block | safety 13 | §3.5: flagged |
| `Iterable<T>` vs David's `iterable<T>` | safety, cross-cutting | §13 |
| D22: printed signatures show the requirement | safety readiness | §11 D22 text |

## 2. Who may write what: one rule per construct

The rule follows from how many copies of the code run, and for how long.

| Construct | Runs | Writing a variable from outside it |
|---|---|---|
| Block item, `parallel { … }` | once, inside the block | **Allowed.** It writes the original; the dependency graph orders conflicting accesses (§3) |
| A helper or closure called by any of these | wherever its caller runs | Same as its caller. Its read and write summary (through `@` parameters and `$capture @x`) is substituted into the caller's analysis |
| Loop or comprehension body, `parallel x in xs` / `[parallel …]` | many copies at once | **Only its own partition:** `@x`, `xs[i]` with the loop's own `i` (§8), its own locals, and handles. Anything else is a race error that points to a reduction or to returning values |
| `group.spawn(f)` | beside its starter, for as long as the group lives | **Compile error** (D26): "this task runs beside the code that started it, so it can't change 'total'; send it back through a channel, or make it a `parallel` block item" |
| The body of `tasks(body)` | once, on the calling task | Ordinary closure rules (`$capture @x`), since the caller waits |

- **Moving code is safe.** Moving a write between an item, a helper, a closure, a loop body and a task gives the same result or a compile error, never a silently lost copy. That is the contract consistency-audit finding 5 asked for.
- **v3's examples are legal under this table.** `loop n in numbers { total += n } or_throw` is a block item. D26 applies to tasks, which run beside their starter.
- Today's compiler already reports the D26 error for the old `spawn` (`probe/d26.dewy`). The message wording is ours.

## 3. The block form, made sound

### 3.1 The rule

- Every top-level statement is an item. A `{ … }` group is one item and runs in order. A `( … )` group is also one item (§3.6). Metatag lines are not items; they cover the whole block.
- **Item j waits for an earlier item i (i before j in the source) when:**
  - j reads a binding that i declares; or
  - their **footprints** may overlap and at least one of them writes. This covers write-after-read and write-after-write as well as read-after-write.
- **Footprint:** the ordinary places an item reads and writes, resolved to a root plus a path, including:
  - transitive callees, each through a summary computed once per instance;
  - method receivers (`counter.bump` writes `counter.n`);
  - index and receiver evaluation, closure construction and captures (a `$capture @x` closure writes `x` when called), moves, and cleanup (`defer`, drop hooks);
  - globals, through callees.
- **Unknown means overlap.** An unresolved callable, or an alias that can't be ruled out, adds the edge. A fact that equality can't be proven is not a proof of disjointness: `bump(@rows[i].n)` against `rows[j].n` waits unless `i not=? j` is proved. Bounds checks prove nothing about disjointness.
- **Handles:** an operation on a handle's shared payload (send, receive, an atomic op, a lock, file, terminal or network I/O) creates no edge. Reading, replacing or creating the binding that holds the handle does. A record that contains a handle is not exempt as a whole; only the operation on the handle field is. `Send`/`Sync` says a value may cross threads, not that it is ordered.
- **Places:** an item that uses a place created *outside* the block (`let p = @xs[0]` before it, then `p = 7` inside) stays rejected, as today's capture rules reject shared places. A place made inside an item and passed down (`cool(@world.heat dt)`) is fine: its footprint is `W(world.heat)`.
- **Activation:** an item's captures and arguments are evaluated when it starts, after its predecessors, and count as its accesses. Capturing everything at block entry would freeze stale values.
- **Edges wait for successful completion.** A predecessor's bindings and writes are published when it finishes, cleanup included, and its completion happens before its dependents start. A failed or canceled item never releases its dependents.

### 3.2 The promise, qualified

> **If every item succeeds, every ordinary value the block computes (locals, fields, elements, through any path) equals what running the items top to bottom computes, given the same results from handle operations and the outside world.** A handle's result (an atomic load, a receive, a file read, a clock) depends on timing, and so does anything computed from it.

- `handles()` in `16_block_rules.dewy`: `counter.store(1)` beside `let seen = counter.load` gives 0 or 1, and this is stated. It needs no new analysis: handle results are inputs.
- **Proof sketch** (soundness §1): every conflicting pair of ordinary accesses is ordered and ordinary operations are deterministic, so adjacent independent steps commute, and any successful schedule can be rearranged into source order.

### 3.3 Failure

- An item's `or_throw` failure:
  1. stops activation of pending items, which end as skipped;
  2. cancels the running items and joins them;
  3. leaves the function with the first failure that happened.
- Moving an item from pending to running is serialized against cancellation, so a join never waits on work that can't start.
- **Excluded from the promise:** on the failing path, an independent item may already have written (`run` in soundness §1 can leave `x` at 1), and two independent failures may arrive in either order. Nothing is rolled back. Bindings after the block are never visible on that path, because the function has left.
- An item that completed successfully stays completed. A dependent that is already running when an unrelated sibling fails is canceled and joined like the others.

### 3.4 Deadlock and the close rule

- **A forward graph isn't a proof of deadlock freedom.** In `protocol()` (16), `let x = ch.receive ?? 0` waits for a send, and the send waits for `x`.
  - Item completion nodes and their edges feed the existing channel and lock wait analysis.
  - A demonstrated closed cycle is an error naming both items.
  - Unresolved cases warn, as they do today.
  - Under `$no_deadlocks`, dependency waits need certificates like channel waits, and unknown cases are errors.
- **The close rule is a protocol rule of its own,** not a deadlock check. A `close` of channel `c` in an item that isn't ordered after every other item that may send on `c` is an error naming both. The fix-it puts the close in the sender's `{ }`. Cost: one list of send and close sites per channel binding, linear in the sites.

### 3.5 Bindings after the block (flagged)

- Top-level `let` items are visible to later items and **after the block**. A `let` inside a `{ }` item stays inside it, as braces scope everywhere.
- No other braces in Dewy leak bindings. This one does because it is what makes the block useful, and the alternative stays legal: the block gives its items' values in source order, so `let [map sounds] = parallel { load_map(load_config or_throw) or_throw; load_sounds or_throw }` works too. **Flagged for David; not a question.**

### 3.6 `( … )` keeps order inside a block

- A parenthesized group is **one item**. Its expressions run once each, in source order (multi-expressions: substitution invariance and effects). Flattening its values doesn't make its parts separate items.
- It is not a statement block: no `let`, metatags or scope. Use `{ }` for those.
- **Checked today** outside `parallel`: `[(note("a") note("bb")) note("ccc")]` prints a, bb, ccc in order (`probe/grouporder.dewy`). A regression test beside the `{ }` case goes with the block form: `grouped()` in 16.

### 3.7 What you see

- Hover over `parallel` and `explain` draw the graph, e.g. "4 items; `map` waits for `config`; 2 ordered conservatively: couldn't tell `rows[i]` from `rows[j]`".
- **A compile note** (not an error) for an item that only prints, comes after other items, and has no edge to any of them: "`printl"done"` may print before item 2 finishes; link it (`printl"done: {map}"`) or move it after the block". A print as the first item, such as "loading…", gets no note.

### 3.8 Compile cost

- Let N be the checked nodes, A the access occurrences, P the indexed places, K the alias comparisons and E the edges. The cost is `O(N + A log P + K·C_alias + E)` plus summary propagation, and storage is `O(A + E)`. It uses root and path indexes and last-writer and read frontiers, not all pairs of items.
- **Demand-driven:** nothing runs without a block-form `parallel`. Only callees that the items reach get summaries, and those are reused per instance.
- **Bounded:** when path expansion passes a budget, it falls back to ordering at the root. That gives up parallelism, never soundness, and hover says so. Recursive summaries widen to "unknown"; an iteration limit is never treated as a proof.
- The wait-analysis reuse costs what it costs today (`O(W²)` per task's waits); it is not free.
- **Gate:** instruction counts on the flagship panel before landing. There is no whole-program alias solver.

## 4. `?? void`: the same rules as `if` without `else`

- **The filter set F:**
  - for `x ?? void`, F is every exception alternative of `x`, `none` included (the existing `??` classification, which also covers `Closed` and `Unsent<T>`);
  - for `x ??<E> void`, F is the alternatives matched by `E`. Naming a kind the operand can't hold is an error, as today.
- **Values:** with V the value alternatives of `x`, the result is `V \ F`, given zero or one time. A success that was already `void` stays zero values. `void` is never an element, `none` or a payload.
- **Where it's accepted:** exactly where a varying count is accepted:
  - collectors (`[…]`, `[loop …]`, `[parallel …]`), including blocks nested in them until another construct intervenes;
  - inferred function bodies. **v3's ban is dropped**: `filtered = (k) => maybe(k) ?? void` is like `conditional = (k) => if k 7`, and both collect to `[7]`;
  - an attached `;`;
  - a written `:>void` body or a void statement, **only if nothing is expressed on any path** (`sleep(1ms) ?? void`).
- **Rejected,** with fix-its `?? d`, `?? none`, `or_throw` and `match`: fixed-count bindings (`let x = …`), operands, indexes, conditions, named arguments, and a written one-value result. `bad = ():>void => { maybe(true) ?? void }` is an error because it can give 7. A fixed-count binding is rejected for its count, not because it is "one value".
- **Typing a collector:**
  - its element type comes from the retained contributions only, and filtered alternatives add no constraint;
  - an expected `array<int?>` doesn't undo an explicit filter: `[maybe(false) ?? void maybe(true) ?? void]` is `[7]`;
  - without a filter, a collector never drops `none`;
  - if every contribution is filtered and nothing else gives a type, an annotation is required, as for `[]`;
  - inference never guesses how many parallel items run.
- **No nesting:** `[parallel k in [false true] { maybe(k) ?? void; 9 }]` is `[9 7 9]`. Today it gives `[[9] [7 9]]`-style nesting (`probe/nest.dewy`: `[[1] [] [3]]`).
- **Keeping both sides:** `let [good failed] = results.partition_failures` gives `(array<T> array<F>)`, both in input order. The pipeline report "N bad lines, here are three" takes one line (`06_pipeline.dewy`). A new name; cold read pending.
- **Fusion is guaranteed:** a collector consumed only by a reduction (`sum([parallel …])`) builds no array, and hover says "fused". This is internal; stating it lets programmers rely on it.
- **Cost:** one exception partition per filtered expression plus the ordinary collector type joins. No new pass.

## 5. Cancellation

### `check_cancel`

- As in v3: a pure cancellation point giving `void | Canceled`, written `check_cancel or_throw`.
- **A bare `check_cancel` is already an error** under the sink rule (`probe/sink.dewy` shows the same message for `sleep(1ms)`): "propagate the failure with `or_throw`…".
- **No throttling by hand.** A check is one relaxed load, and in a hot loop the compiler batches it, every k iterations or once per chunk. Cancellation latency is unspecified anyway, so the dogfood's `if start % 100_000 =? 0` is unnecessary.

### Ctrl-C

1. **First press:** cancels `main`'s scope and prints at once on stderr: `interrupted: stopping (Ctrl-C again to quit now)`. Waits give `Canceled` and cleanup runs. Compute that hasn't opted in finishes its current construct.
2. **Second press:** ends the process at once, reports that cleanup was skipped, and exits with 130.
3. **`Canceled` from a Ctrl-C reaching the end of `main`:** prints `interrupted` and exits with 130, the shell convention. There is no `error: Canceled` report. If `main` handles the cancel and ends normally, the exit status is its own (07 exits with 0).

### Saving after a cancel: `shielded`

- **`shielded(d @f)`** runs `f` shielded from the caller's cancellation for at most `d`. It gives `f`'s result `| Timeout`.
  - It is the counterpart of `within(d @f)` and Zig's `CancelProtection`, as a library call with a bound so it can't hang.
  - Cancel scopes inside `f` still work, and so does `check_cancel` against the shield's own deadline.
  - A second Ctrl-C ends the process anyway: the user's override wins.
- `defer` cleanup keeps its 100 ms grace. `defer shielded(5s @flush(@buffer out));` gives one cleanup longer (`05_server_select.dewy`).
- **Why a call and not a block keyword:** it reuses the `within` pattern and adds no grammar. The deadline is required, so a shield can't make a program unkillable.

## 6. Tasks

- **`group.spawn(f)` returns a `Task`** with three operations, so one background task can be stopped by itself:
  - `.cancel` requests cancellation, returns at once, and can be called again safely.
  - `.wait` waits until the task has ended. It gives `void | Canceled` (the waiter's own cancellation) and never the task's value or error; a failure already fails the group.
  - `.running` gives a `bool`.
- **The structure still holds:** a `Task` holds no value and can't join or move a task out of its group. After the group ends, `.cancel` and `.wait` return at once and `.running` is false, so a `Task` that escapes is harmless.
- **`f` must give `void | E` or `never | E`.** A function that gives a value is an error: "a task's value would be lost; use a `parallel` block item or a channel". This keeps one way to get a result.
- **D27, settled by ordinary rules:** a spawned lambda is a lambda, so its result is inferred, and `or_throw` inside it forwards to that result. The group then fails with it.
- **`tasks(body)` takes `body:(Tasks :> void | E)`.**
  - Its values drop under the existing context-typed rule, so `group.spawn(@x)` statements need no `;` for the `Task` they return.
  - Results come out through block items or channels.
  - It returns `void | E | Canceled`.
- Restarting a track: `music.cancel; music.wait or_throw; music = group.spawn(@play_music(next))`. Without `.wait`, two tracks would overlap.

## 7. `select`

### Signature

```dewy
select(...waits:Selectable  timeout:Duration | Instant | none = none  ties:'fair' | 'first' = 'fair')
```

- `timeout=` takes a duration, which restarts on each call, or a monotonic **deadline** (`now + 1s`), which doesn't. Hover on `timeout=` says "restarts each call; for a period, use `ticker`".
- `ticker(1s)` returns a `Ticker` handle. Its `@tick.receive` is a wait that gives the tick's `Instant`. Missed ticks merge into one, and dropping the handle stops it. A new name; cold read pending.

### Exact result type (soundness §3)

- **Each operation's result:**
  - a receive on `T`: `T | Closed`;
  - a send of `T`: `Sent | Unsent<T>`. A union inside `T` doesn't distribute: a send of `int | string` gives `Unsent<int | string>`.
- A positional wait adds its result as is. A wait named `name=` adds the one-field record `[name: result]`.
- **The result** is the union of those, plus top-level `Canceled`, plus `Timeout` when `timeout` can be set. `ties` doesn't affect the type.
- **Real cancellation is always top-level `Canceled`.** A payload of type `Canceled` stays inside its record, so the implementation tracks where each outcome came from; it doesn't subtract types.
- **Exactly one operation commits** on an operation result, and none on `Timeout` or `Canceled`. Losing receives take nothing; losing sends deliver nothing. A close is a committed outcome. A send that has committed is never reported as `Canceled`.
- Worked types are in `17_select_types.dewy`.

### Telling results apart (replaces v3's positional-pair rule)

- **Every pair of contributions must be distinguishable:** positional with positional, positional with named, and either with the control outcomes (`Timeout` when a timeout is given, `Canceled`).
- **Rejected,** each with a fix-it naming the waits:
  - two positional receives, since both can give `Closed`;
  - two positional sends, since both can give `Sent`;
  - `@r.receive` where `r:Channel<Reply>` and `Reply = [reply:int]`, beside `reply=@b.receive`;
  - a positional `Channel<Timeout>` receive with a timeout.
- **Duplicate names are rejected.** `timeout` and `ties` are reserved, not wait names.
- **Generics:** the overlap check runs once per instance and is cached. A type variable never proves disjointness, and "unknown" requires names.
- **New rule: a channel's element type must be disjoint from `Closed` and `Canceled`.** Each instance is checked, and the error suggests a wrapping record. Without the rule, neither `receive` nor `select` can tell a `Closed` payload from the channel closing. It's a natural rule: closing a channel of `Closed` values means nothing.
- **Names are allowed with one wait,** and the docs teach them first: `select(reading=@data.receive timeout=1s)`. Adding a second channel then changes no arm (05b).

### What the library needs (audit 9)

- **The protocol `Selectable<R>`:** a member such as `Channel.receive` is a callable library value that also implements `__reserve__`, `__commit__` and `__release__`. These work against one shared selection token, which wakes once, commits one operation and releases the others.
  - `@ch.receive` is a bound handle that keeps that type.
  - `select` requires every wait to be `Selectable`. Any other handle is an error: "`@job.run` can't be selected: it isn't a channel operation; use `race`".
  - Any queue can implement it (`mpmc`, `spsc`, user queues). This is an ordinary protocol, not name matching.
- **Payload ownership of a send:**
  - `@out.send(job)` evaluates its arguments once, when written.
  - A payload held in a variable moves **only on the paths where the send commits**: `Sent`, or a committed `Unsent` that carries it. This is the existing rule that a conditional transfer moves only on the path that transferred it. On `Timeout`, `Canceled` or a loss, `job` is still the caller's (`offer` in 17).
  - A temporary payload belongs to the handle and is dropped when its send loses.
- **Prerequisites,** all general:
  - typed rest parameters as a **heterogeneous pack**, where each entry keeps its type, optional name and order, the keyword-only options stay separate, and names survive until the result type is built (also needed by `race`);
  - compile-time traversal of the pack;
  - building the result type (a union fold, one-field records, a conditional `Timeout`);
  - handles to bound methods that keep the protocol;
  - literal patterns inside tagged records (`[command:'flush']`), and matching unions of anonymous records (v3 `s2.dewy`).
- `$no_deadlocks` rejects `select` until the certificate analysis understands alternatives.
- **Cost:** packing and naming are linear in the pack. Overlap is bucketed by nominal identity and labels, with pair queries memoized. It runs only at `select` instances; measure on the flagship panel.

### `or_throw<E>` (new syntax, mirroring `??<E>`)

- **Proposal:** `x or_throw<E>` forwards only the exceptions matched by `E` and leaves the rest in the value.
  - `match select(…) or_throw<Canceled> { … }` handles `Timeout` and `Closed` in arms and forwards cancellation with no `<Canceled>` arm.
  - Likewise `within(10s @http.get(u)) or_throw<Canceled>` keeps `Timeout` as a value.
- **Without it,** today's legal workaround is `match select(…) ??<Canceled> return Canceled { … }`.
- **This is new syntax, so it's a question for David** (see the D4 text). It is reversible.

## 8. Indexed parallel loops: what the compiler must accept

Today `parallel i in [0..xs.length) { xs[i] += vs[i] * dt }` fails twice (`probe/idx3.dewy`, `probe/idx4.dewy`, `08_game_frame_today.dewy`).

1. **Range facts reach the body.** The variable of `parallel i in [a..b)` and of `[parallel i in [a..b) …]` carries `a <=? i <? b`, exactly as the sequential `loop` does (`probe/idx2.dewy` compiles). Facts about the enclosing scope (`vs.length =? xs.length` after a guard) hold too, because the body can't resize a captured array. This reuses the existing loop-fact code.
2. **Writes to the loop's own index are the loop's own partition.** In `parallel i in r { … }` over an integer range, a write path that starts with `xs[i]` (`xs[i] = …`, `xs[i] += …`, `xs[i].f = …`, `@xs[i]` passed to a callee) is accepted, provided that:
   - `i` is the loop's own variable, unchanged;
   - `xs` is **only written at `[i]`** in the body, and **only read at `[i]`** there, since reading `xs[i-1]` would race with iteration `i-1`'s write;
   - nothing in the body changes `xs`'s structure (push, remove, replace, resize).

   Arrays the body doesn't write can be read anywhere (`vs[i-1]`). Several arrays written at `[i]` (struct of arrays) are fine. `grid[i][j]` is fine: row `i` belongs to iteration `i`. Cost: one pass over the body's accesses.
3. **Length facts survive element-only writes.** A function whose `@` array parameter is only written at elements (through `parallel @p`, or `xs[i]` under rule 2) is summarized as "keeps the length", so `ps[0]` stays proven after `step(@ps dt)`.
- **Later, and not needed now:** injective index maps (`xs[2*i]`, `xs[i+k]`). They join when a program needs them.
- `$memory.layout = 'soa'` keeps element-wise code (`parallel @d in dots { d.x += d.v * dt }`). The index form is for SoA written by hand.

## 9. Metatags: the one current inventory

This replaces v3 §8. Names in **bold** are new or changed and go to the cold read. Classes:
- **Lexical:** covers the constructs written in the scope (module, function body, block), wherever the tag sits in it. It never covers a `parallel` inside a function that is called. Hover on the tag lists the constructs it reaches, and hover on a `parallel` lists the settings that govern it. To target one construct, wrap it in `{ }`; in a block, that brace group is one item.
- **Declaration:** applies to the next type declaration, as `$export` does.
- **Program:** set once, by the main file, at the top level, like `$build.mode`.

| Tag | Value | Class | Meaning |
|---|---|---|---|
| `$parallel.max_concurrent = 8` | int ≥ 1 | lexical | Most items in flight. Rejected where items wait on each other |
| `$parallel.chunk_size = 64` | int ≥ 1 | lexical | Minimum items per chunk; results unchanged |
| **`$parallel.max_cores = 2`** | int ≥ 1 | lexical | At most N cores run this scope's parallel work. Replaces `$parallel.threads` |
| `$parallel.off` | bool | lexical | **Redefined:** items run one at a time, in source order, switching only when one waits. Deterministic, so a debugging aid, and accepted everywhere: a waiting item yields, so it can't deadlock where the interleaved run wouldn't. A busy-wait on an atomic would spin (expert lane) |
| `$parallel.scheduler = @f` | function | lexical | Expert leaf |
| `$placement.device = 'gpu'` | `'cpu' \| 'gpu'` | lexical | Explicit placement |
| `$placement.cores = [0 1]` | array of int | lexical | Pin to these cores |
| `$memory.layout = 'soa'` | `'aos' \| 'soa'` | declaration | Data layout of the next type |
| `$program.max_cores = 1` | int ≥ 1 | program | At most N cores run the program's code at once, like `GOMAXPROCS`. A thread blocked in a system call doesn't count, so waits don't starve |
| `$program.max_memory = 512MiB` | size | program | Exceeding it follows the allocation policy. `MiB` is 2^20 and `MB` is 10^6 (units design) |
| `$program.max_tasks = 10000` | int ≥ 1 | program | Admission past it follows the allocation policy (C9) and never waits |

- **One unit, cores.** Threads are an implementation detail: the waiting lane may hold many blocked threads on one core, and the audit warns against equating the two.
  - `$program.max_cores` caps the program;
  - `$parallel.max_cores` caps a scope, and a value above the program cap is an error naming both;
  - `$placement.cores` pins to particular cores.
- **`DEWY_MAX_CORES`** replaces `DEWY_THREADS` (`lib/std/fork_join.jo:256`). An operator's run-time cap, like `GOMAXPROCS` or `RAYON_NUM_THREADS`, can only lower the effective count, so it is one rule, not a second way.
- **`available_cores`** gives the effective count where it's called: the minimum of the hardware or affinity mask, the program cap, the environment cap and the enclosing scoped cap. It's for sizing a pool (Go's `runtime.NumCPU`, Rust's `available_parallelism`). A new name; cold read pending.
- **`$parallel.off` vs `$program.max_cores = 1`:** different tools. One is a scoped, deterministic order for debugging. The other is a program-wide resource cap whose waits still interleave in any order.
- **The standing exception is flagged:** under `$explicit_allocation_failure`, admission past `$program.max_tasks` gives `OutOfMemory`. This is David's earlier exception to "a metatag never changes a result type"; nothing new.
- **LANGUAGE.md "Directives"** must stop saying a setting's value "must be a literal `true` or `false`". Each tag declares its value type, as the table does.

## 10. Words for the keyword arguments (audit 15)

- `grouping=` controls how a reduction associates: `sum(xs grouping='tree')`, with `'sequential'` the default. It also applies to `product` and `reduce`. **v3's `order=` is superseded.**
- `rounding=` is for numeric rounding only, with the values the stem lists. It never appears in this design.
- `ties=` is now only `select`'s fairness choice (`'fair' | 'first'`). Numerics use `rounding=`, so the word has a single meaning.

## 11. D22, D26 and D27 in v4 forms

- **D22.** Since C1, "parallel-safe" means **race-free only.** The nonblocking part of the 2026-11-01 rule is gone, because items may wait. The requirement is inferred and shown in hover, in printed signatures (`f: parallel-safe`) and in generated docs. Recommendation as before: delete `$parallel_safe`. Ready.
- **D26, restated:**
  - question: "a task started with `group.spawn` writes a variable from outside it: what happens?";
  - answer: a compile error (§2);
  - the cases David might expect to differ behave as he'd expect: a block item writing the same variable is allowed and ordered, and a loop body gets a race error with a reduction fix-it;
  - both tests pass: the common path (block items, reductions) is easy, and the fix (a channel or a block item) is named in the error;
  - **nothing left for David.**
- **D27, restated:** "`or_throw` inside a `group.spawn` lambda". It is moot as a separate rule: a lambda infers its result like any function, and a task's failure fails its group. In a block item, `or_throw` leaves the function (C3, decided). **Nothing left for David.**

## 12. `or_throw` placement around loops (C7)

- **Before `{`, `or_throw` binds to the iterable:** `loop name in input.list or_throw {` works. Today it fails with "a loop used as a value".
- **A brace-less loop body takes the rest of the line,** so in `loop i in r jobs.send(x) or_throw` the `or_throw` belongs to the send. C7's `} or_throw` form needs braces.
- **A forgotten `} or_throw`** on a channel loop that isn't the last statement is already an error under the sink rule (`probe/sink.dewy`). As the last statement of an inferred body, `Canceled` becomes part of the function's result type, so it is never lost.

## 13. `iterable<T>`

- Lowercase, following David's notes (`resources/discussion_points.md`: `sequence<T>|iterable<T>`) and the built-in `array<T>`. The meaning is unchanged: anything `loop x in` accepts. `sequence<T>` is still deferred.

## 14. Dogfood, re-run against v4

- The programs are in `~/dev/tmp/rev-1107/parallel/`. All are paper-only: the block form, `tasks`, `select`, `check_cancel` and `?? void` don't compile today (`dogfood-1107/a/probe/p1.dewy`, `p3.dewy`; `probe/voidfilter.dewy`).
- The compiled probes in `probe/` confirm each "today" claim above.
- Formatting uses `fmt` (`f2 = fmt'.2f'`, `{f2(s.x[0])}`).
- O = obvious, D = discoverable, C = concise, S = safe by default, X = complete. These grades are mine, from paper; a fresh dogfood pass should confirm them before David sees D4.

| # | Program | O | D | C | S | X | Was | What changed / floor |
|---|---|---|---|---|---|---|---|---|
| 03 | Fetch URLs | 5 | 5 | 5 | 5 | 4 | 4 3 4 4 2 | Lexical reach stated, hover shows it; `or_throw<Canceled>`; `partition_failures`. **X floor 4: no HTTP client** (library, outside this design) |
| 04 | Worker pool | 5 | 5 | 5 | 5 | 5 | 3 4 4 4 4 | The consumer item writes `total` (no atomic, so no overflow question); brace-less rule; forgotten `or_throw` is an error |
| 05 | `select` collector | 5 | 5 | 5 | 5 | 5 | 4 4 3 3 3 | `ticker`; `or_throw<Canceled>`; `defer shielded(…)` saves on cancel. C depends on `or_throw<E>`: without it, 4 |
| 05b | One channel | 5 | 5 | 5 | 5 | 5 | — | Names allowed with one wait |
| 06 | Pipeline | 5 | 5 | 5 | 5 | 5 | 4 3 3 4 2 | `partition_failures`; guaranteed fusion. Uses `int` fields: an `int64` field still needs a fixed-width parse (numbers topic; C 4 there) |
| 07 | Cancel, Ctrl-C | 5 | 5 | 5 | 5 | 5 | 3 3 4 3 2 | Notice on the first press; exit 130; `shielded`; no hand throttling. Uses `600s` until the units design settles `10min` |
| 08 | Game frame | 5 | 5 | 5 | 5 | 5 | 4 3 4 4 2 | Own-index writes and range facts; length kept. (Float `random` in a range is out of scope and left out) |
| 12 | Single core | 5 | 5 | 5 | 5 | 5 | 4 3 5 4 3 | One unit; `available_cores`; `MiB`; `$parallel.off` distinct and accepted where items wait |
| 13 | Loading + autosave | 5 | 5 | 5 | 5 | 5 | 3 4 5 4 3 | `Task` handles (`saver.wait`, `music.cancel`); the "done" note; `let` visibility flagged |
| 15 | D26/D27 in v4 | 5 | 5 | 5 | 5 | 5 | — | One rule per construct; errors name the fix |
| 16 | Block cases | 4 | 5 | 5 | 5 | 5 | — | **O floor 4 for the block form:** setup through the file system (v3 Case 3) can't be seen by any analysis. v2's explicit form had the same hole, and the only way out is dropping the inferred graph, which fails test 1. Everything else is ordered, reported or noted |
| 18 | `?? void` | 5 | 5 | 5 | 5 | 5 | — | Same as `if`; v3's exception removed |

**Floors:** 03's X depends on a library that doesn't exist yet. 16's O is the price of an outside world, and nothing better exists without giving up the block form. 05's C depends on David accepting `or_throw<E>`.

## 15. Replacement text for open_decisions.md

### D4. One unified `parallel` surface: v4
- **BLUF:** turn this on, and three forms cover all parallel and concurrent work:
  - a block whose steps wait only for the data they use;
  - a loop or comprehension that may write only its own element;
  - `tasks`, for work that lives in the background.

  Values come out as they would sequentially, except for what handles (channels, atomics, files) return. The semantics pass both tests and are taken, so only names and one piece of syntax are below. Full design: `docs/design/proposals/concurrency/unified/proposal-v4.md`.

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
parse_age = (text:string):>int | Invalid => to_int(text) ?? Invalid
score = (n:int):>int => (n * n) % 7
autosave = () => loop true {
    sleep(30s) or_throw
    printl"saved"
}
relay = (commands:Channel<string> chat:Channel<string>) => loop true {
    match select(command=@commands.receive  message=@chat.receive  timeout=1s) or_throw<Canceled> {
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
    let total = sum([parallel i in [0..1_000_000) {
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
        let saver = group.spawn(@autosave)          # a Task: stop this one alone
        sleep(2s) or_throw
        saver.cancel
    }) or_throw
    printl"{map} {sounds} {ages} {total} {why}"
}
```

- **The common path:**
  - write the steps in order in `parallel { }`, and the compiler runs whatever doesn't depend on something else;
  - `[parallel x in xs f(x)]` for maps;
  - `?? void` to drop failures, `.partition_failures` to keep both sides;
  - `check_cancel or_throw` to make a long computation stoppable.
- **How to adjust:**
  - to force an order, use the earlier result, wrap the steps in `{ }`, or move a step after the block;
  - `$parallel.off` replays a scope in source order for debugging;
  - `$program.max_cores = 1` keeps a program on one core;
  - `shielded(5s @save(x))` saves after a cancel.
- **Semantics taken:**
  - **Block rule:** an item waits for an earlier one whose data it uses (bindings, fields, elements, through calls and closures). If every item succeeds, ordinary values are the sequential ones; a handle's result depends on timing. On failure, pending items never start, running ones are canceled and joined, and nothing is rolled back. A cycle through a channel is an error, and so is a `close` that races the sends.
  - **Who may write:** block items may write the function's variables (ordered). Loop bodies may write only their own element, `xs[i]` with their own `i` included. A spawned task can't write outer variables; the error names a channel or a block item (D26, restated).
  - **`?? void`** works wherever `if` without `else` works, and is an error where a fixed count is needed.
  - **Cancellation:** compute runs to completion by default. The first Ctrl-C prints "stopping (Ctrl-C again to quit now)"; a second ends the process. An unhandled interrupt exits 130 with no error report.
  - **`group.spawn` returns a `Task`** that can be canceled or waited on by itself. `or_throw` in a spawned lambda forwards to its inferred result (D27, restated).
  - **`select`:** every wait's result must be distinguishable, and duplicate or overlapping waits are errors naming the fix. A send that loses keeps its payload. A channel's element type can't be `Closed` or `Canceled`.
  - **Cores are one unit:** program cap, scoped cap, pinning, `available_cores`, and an environment variable that only lowers it.
  - `parallel i in [0..n) { xs[i] … }` compiles; today it is rejected.
- **Spellings to review.** "Tested" means three cold readers read the name correctly (`proposals/concurrency/unified/names.md`); "cold read pending" names are not final yet.
  1. `check_cancel` (tested). **Rec:** yes.
  2. `select(name=@ch.receive … timeout=1s ties='fair')`: `ties='first'` for priority, `Sent` for a send's result, and `timeout=` also taking a deadline (tested, except for the deadline form). **Rec:** yes.
  3. **New syntax:** `x or_throw<E>` forwards only `E`, mirroring `??<E>`. With it, `match select(…) or_throw<Canceled> { … }` needs no `<Canceled>` arm. Without it you write `??<Canceled> return Canceled`. Reversible. **Rec:** yes.
  4. Metatags:
     - in a scope: `$parallel.max_concurrent`, `$parallel.chunk_size`, `$parallel.max_cores` (cold read pending; replaces `.threads`), `$parallel.off`, `$placement.device`, `$placement.cores`;
     - on a type: `$memory.layout`;
     - program-wide: `$program.max_cores`, `$program.max_memory`, `$program.max_tasks`.

     **Rec:** as written.
  5. `sum(xs grouping='tree')` (tested). **Rec:** yes.
  6. `iterable<T>`, lowercase as in your notes. **Rec:** yes.
  7. `Task` with `.cancel`, `.wait`, `.running` (cold read pending). **Rec:** as written.
  8. `shielded(5s @f)` (cold read pending; alternatives `uncanceled`, `protected`). **Rec:** `shielded`.
  9. `ticker(1s)` (cold read pending). **Rec:** yes.
  10. `available_cores` and `DEWY_MAX_CORES` (cold read pending). **Rec:** yes.
  11. `xs.partition_failures` (cold read pending; alternatives `split_failures`, `separate_failures`). **Rec:** `partition_failures`.
- **Flagged, not questions:**
  - the Ctrl-C behavior and exit status 130;
  - a block gives its items' values in source order;
  - a block's top-level `let`s are visible after it;
  - `( … )` is one item and keeps its order;
  - `$parallel.off` is now a deterministic replay;
  - `$program.max_tasks` gives `OutOfMemory` only under `$explicit_allocation_failure` (the standing exception).

### D22. Delete `$parallel_safe`?
- **BLUF:** delete it. Since items may wait, "parallel-safe" means only race-free, and the compiler already infers it per callback, with no tag.
- **Example:**

```dewy
apply_then_report = (xs:array<int> f:(int:>int) report:(array<int> :>void)) => {
    let ys = [parallel x in xs f(x)]   # inferred: f must be parallel-safe
    report(ys)                         # report runs once: no requirement
}
main = () => apply_then_report([1 2 3] (x) => x * 2 (ys) => printl(ys))
```

- **The common path:** write nothing. Hover, printed signatures (`f: parallel-safe`) and generated docs show the requirement, and each call is checked.
- **What the tag would add:** only a promise that a later edit can't stop passing the callback into parallel code. A change to an exported signature is caught in general, without a concurrency tag.
- **Rec:** delete. If kept, name it `$race_free`.

### D26 and D27
- **Delete both from open_decisions.md.** Restated in v4 forms, they pass both tests, and D4 carries them as taken semantics ("a spawned task can't write outer variables"; "`or_throw` in a spawned lambda forwards to its inferred result"). The decisions.md batch 2 line should point to D4 v4 instead of the removed `concurrent`/`spawn` forms.

## 16. New or changed names (for the cold read)

| Name | Kind | Intended meaning |
|---|---|---|
| `$parallel.max_cores` | scoped tag | At most N CPU cores run the parallel work in this scope (replaces `$parallel.threads`) |
| `$parallel.off` (changed meaning) | scoped tag | Run this scope's parallel items one at a time, in source order, switching only when one waits |
| `available_cores` | zero-arg function | How many CPU cores this code may use right now, after every cap |
| `DEWY_MAX_CORES` | environment variable | An operator's cap on cores for one run; can only lower the program's limit |
| `Task` | type | A handle to one background task in a group: stop it or wait for it, no result |
| `Task.cancel` | method | Ask this task to stop; returns at once |
| `Task.wait` | method | Wait until this task has ended |
| `Task.running` | member | Whether this task is still running |
| `shielded(d @f)` | function | Run `f` even though the caller is being canceled, for at most `d` |
| `ticker(d)` | function → `Ticker` | A source that delivers a tick every `d`, used as a wait in `select` |
| `Ticker` | type | The handle `ticker` returns; stops when dropped |
| `x or_throw<E>` | syntax | Forward only the failures of type `E`; keep the rest as values |
| `xs.partition_failures` | method | Split results into successes and failures, both in order |
| `Selectable<R>` | protocol type (in hover and errors) | An operation `select` can wait on and commit to exactly once |
| `__reserve__`, `__commit__`, `__release__` | protocol members (library authors) | Reserve an operation, commit the winner, release the losers |
| `iterable<T>` (case changed) | type | Anything a `loop x in` can visit |
| `timeout=` taking an `Instant` (changed) | keyword argument | Give up at this moment rather than after this long |

`grouping=`, `ties=`, `check_cancel`, `$parallel.max_concurrent`, `$parallel.chunk_size`, `$placement.*`, `$memory.layout` and `$program.*` are already tested and unchanged.

## 17. Out of scope: today's compiler, and notes for other topics

**Compiler bugs** (repro paths; not fixed):
1. No range facts in parallel bodies: `~/dev/tmp/rev-1107/parallel/probe/idx3.dewy` ("missing lower and upper bounds" on `xs[i]` in `[parallel i in [0..xs.length) …]`). The sequential `probe/idx2.dewy` compiles.
2. A write to the loop's own index is rejected as a captured write: `probe/idx4.dewy`.
3. `step(@ps)` loses `ps.length` facts though it writes only elements: `~/dev/tmp/dogfood-1107/a/08_game_frame_today.dewy:19`.
4. `[parallel …]` with a block body nests: `probe/nest.dewy` gives `[[1] [] [3]]` against `loop`'s `[1 3]`.
5. `?? void` is rejected ("found a type name"): `probe/voidfilter.dewy`.
6. `within`/`race` still carry `OutOfMemory` (`lib/std/tasks.jo:235`, `:244`), against C9.
7. LANGUAGE.md (around line 3383) teaches `sleep(0ns)` as a cancellation point; `check_cancel` replaces it once built.
8. Unions of anonymous records don't match (v3 `scratch/s2.dewy`).

**Notes for other topics:**
- **Strings/UI and multi-expressions:** "results carry something useful" collides with inferred bodies. A statement like `out.append_text(…) or_throw` now expresses a `Path`, so it needs `;` in any inferred or `:>void` body (05's `flush`), the same friction dogfood 02 found with `make_dirs`. This design avoids it for `group.spawn` only through the context-typed `tasks` body. A general rule is the coordinator's call.
- **Name collisions:** `tasks` with a to-do list variable, and the process `spawn(program args)` with `group.spawn`. Recommend renaming the process call (processes topic).
- **Atomics:** `Atomic.add` traps on overflow today; it should follow the counter rule (safety topic).
- **Units:** `10min` resolves to `min`; `MB` vs `MiB`.
- **Library:** an HTTP client (`http.get`).
