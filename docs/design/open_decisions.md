# Decisions waiting on David

- **Only open items.** Once you answer one, it moves to [decisions.md](decisions.md), with what was considered and why, and is removed from here.
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

## P1: blocking current work

### D4. One unified `parallel` surface
- **Status:** nothing built yet; waiting for you to come back to it. Full design: `docs/design/proposals/concurrency/unified/proposal-v2.md` and `big-picture/synthesis.md`.
- **BLUF:** both tests pass with what's below, so the semantics are taken unless you object. The syntax is what needs your eyes.

**Common path: write the obvious thing**

```dewy
let ys = xs .* 2                               # pure bulk work goes wide automatically, no keyword
let total = sum(xs)                            # integers may split; floats stay in order, so results don't change
let sums = [parallel row in rows sum(row)]     # a pool of chunks, picked by the compiler
let pages = [parallel u in urls fetch(u)]      # the same word: waiting bodies get a bounded window of tasks
parallel {                                     # different things at once; both finish before the block ends
    let a = load_map
    let b = load_sprites
}
printl"{a} {b}"
let each = [parallel n in ns check(n)]         # errors stay per-item values: [1 Timeout 3]
let all = [parallel n in ns check(n) or_throw] # first error cancels the siblings and leaves the function
```

**When that doesn't fit: adjust one thing**

| Need | Write | Effect |
|---|---|---|
| Why did it pick that? | `explain`, editor hover | Shows the strategy and why, with a "why not" for anything not sped up |
| One core; a thread or window limit | `$cores = 1`, `$window = 8` | Applies to the scope; rejected if it conflicts with items waiting on each other |
| Chunk size, memory layout, scheduler | `$grain = 64`, `$layout = 'soa'`, `$scheduler = 'lifo'` | Performance only; results don't change |
| GPU | `$device = 'gpu'` or `xs.to(dev)` | Explicit placement; automatic offload comes later, if ever |
| Force sequential | `$sequential` | For debugging or small data |
| Faster float sum | `sum(xs 'tree')` | Opts into a different rounding order |
| Lock out waiting | `:>T & no blocks` | Compile error if a body may wait |
| Work that outlives a function | `tasks(body)` | Explicit long-lived group |
| Wait for the first of several | `select(ops)` + `match` | Fair choice; call `try_receive` first when you want priority |
| Your own scheduler or data structure | An expert leaf behind the same value interface | Callers don't change |

**Semantics taken** (the one real split among reviewers was whether items may wait on each other):
- **Items may wait, even on each other.** The compiler picks a chunk pool, a bounded window or one task per item from what the body may wait on. Where it can't bound memory, `explain` warns.
- **Compute-only `parallel`** checks for cancellation between chunks, and stops only where the result type already carries `Canceled`.
- **Failing to start a task** follows the allocation policy, with no `OutOfMemory` in every signature.
- **`loop x in rx`** gives `void` at `Closed` and `Canceled` on cancel. **`parallel x in rx`** is windowed.

**Syntax to review:**
1. **The three shapes:** `parallel x in xs { … }`, `[parallel x in xs f(x)]`, `parallel { … }`.
2. **Block items:** each is a `let` or a `{ … }` group (run in order inside). A bare expression is an error with a fix-it, so a stray line can't silently become a racing item.
3. **`select`** as a library call:

   ```dewy
   match select(inbox.receiving  out.sending("ping")  timeout(1s)) {
       n:int => printl"got {n}"
       s:Sent => printl"sent"
       u:Unsent<string> => printl"not sent: {u.reason}"
       c:Closed => printl"inbox closed"
       t:Timeout => printl"nothing within 1s"
       c:Canceled => printl"canceled"
   }
   ```
   Adds `select`, `Op<T>`, `.receiving`, `.sending(v)`, `timeout(d)`, `Sent`, and `op.then(f)`, which is needed to tell which of two channels closed.
4. **`tasks`:** `tasks(body)`, `Tasks`, `g.spawn(@f(x))`, `g.cancel`. Considered: `scope`, `nursery`.
5. **Metatag names:** `$grain`, `$window`, `$layout`, `$device`, `$cores`, `$scheduler`, `$sequential`. Other resource limits you want (e.g. memory) would go here too.
6. **Removed:** `concurrent`, `spawn`, `concurrent g {…}`, `spawn(g)`, `cancel(g)`, `TaskGroup`, `parallel_map`, `parallel_range`, `parallel_update`, the `select { … }` grammar.

---

## P2: unblocks common friction

### D15a. Which time zone does a program use when none is given?
- **Your note:** use and pin the system zone at build time unless specified; warn when it was assumed.
- **The catch:** a pinned *rules table* is good, but a pinned zone *name* makes a binary built in New York report New York's date for a user in Tokyo, and for a laptop that travels.

```dewy
printl(today)                              # warning: uses the time zone of the machine running this
$time.zone = 'America/New_York'            # always New York, wherever it runs; no warning
$time.zone = 'system'                      # the running machine's zone, on purpose; no warning
```

- **Options:**
  - **a)** Name read when the program runs; rules pinned at build. Warning as above.
  - **b)** Name and rules both pinned at build (your note, read literally).
- **Rec:** (a). Scripts get the expected answer, and `$time.zone` covers the fixed case.

### D15b. What does `$dewy.version` promise, and from when?
- **Direction taken:** your `$dewy.version = '0.1.0'`, per module, replacing editions.
- **Cost:** the compiler and standard library keep every past behavior change behind a version check forever, and modules on different versions must share data layouts. So breaking changes get rare and expensive once this starts.
- **Rec:**
  - The promise starts at the first tagged release; until then, the no-legacy rule stays (today's version is `0.0.0`).
  - With no declaration: compile as the current version, warn, and offer a fix-it that inserts it. `dewy new` writes it.

### D15c. Date spellings
```dewy
age(date"2000-02-29" on=date"2027-02-28")                  # 26; `on` defaults to today
let gap = date"2027-02-28" - date"2000-02-29"              # a Period
gap.years                                                  # 26 (a Feb-29 birthday counts on March 1)
gap.total_days                                             # 9861
```
- **Rec:** both, as shown: `age` as a top-level function, and `Date - Date` gives a `Period`.

### D15d. Intervals: reuse Dewy's range syntax?
- **Where you'd use one:** "did these bookings overlap", "which log lines fall in this window", "is this moment within the shift".
- **Why half-open:** 9:00–10:00 and 10:00–11:00 don't overlap, and they cover the morning with no gap.
- **Proposal:** v5 had `interval(a b)`, with a default to remember. Dewy ranges already spell each end, so there's no default.

```dewy
let shift = [start..end)
if now.nominal in shift printl"on shift"
shift.overlaps?([lunch..lunch + 1hour))
```

- **Rec:** ranges, dropping `interval(a b)`.

---

## P3: lower stakes

### D19e. Keep `{x:.2f}` next to a format function?
- **Today:** `"{x:.2f}"` is shorthand for `format(x ".2f")`.
- **Your note (`discussion_points.md`):** a higher-order `fmt`. A format string gives a function, so a computed width needs no new syntax.

```dewy
printl"{fmt'.2f'(x)}"
printl"{x |> fmt'.2f'}"
printl"{fmt'<{w}'(x)}"     # computed width: an ordinary interpolated string
```

- **Options:**
  - **a)** `fmt` only: remove `{x:spec}` and `format(x spec)`. One way to do it, but a little longer, and `x:>7` already reads like a return arrow.
  - **b)** Keep `{x:.2f}` as shorthand beside `fmt`.
- **Name:** your notes consider `f` and settle on `fmt`. `f` is shorter but a very common variable name.
- **Rec:** (a), with the name `fmt`.

### D22. Delete `$parallel_safe`?
- **Why it isn't the default:** the safety requirement is already inferred, with no tag. The compiler works out, per argument, which callbacks reach parallel code, and checks only those at each call. A function that writes a global really isn't parallel-safe, so it can't be "on" for everything.
- **What the tag adds:** only a promise on an exported function that a later edit can't stop passing the callback into parallel code. It's the only thing here that asks every callback to be parallel. That's what makes it reject this example:

```dewy
$parallel_safe
let apply_then_report = (xs:array<int> f:(int:>int) report:(array<int> :>void)) => {
    let ys = [parallel x in xs f(x)]   # inferred: f must be parallel-safe
    report(ys)                         # inferred: report runs once, no requirement
}
```

- **Rec:** delete the tag. Inference passes both tests, hover shows the requirement, and it can come back if a library ever needs it.

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

---

## In design: nothing needed from you yet

- **D10. Safety tags.** Being redesigned on your direction: unsafety is opted into, and each tag's name says what it does. It will come back as "turn this on, and doing X is a compile error" explanations. `proposals/bulletproof/`.
- **D11. Game library calls that crash today.** Being redesigned: string types with a compile-time checked shape (action names, melodies), and removed physics bodies. `ui_begin` waits on the Clay-style UI.
