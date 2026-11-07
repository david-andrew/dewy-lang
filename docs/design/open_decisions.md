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

### D15c. Date spellings
```dewy
age(date"2000-02-29" on=date"2027-02-28")                  # 26; `on` defaults to today
let gap = date"2027-02-28" - date"2000-02-29"              # a Period
gap.years                                                  # 26 (a Feb-29 birthday counts on March 1)
gap.total_days                                             # 9861
```
- **Rec:** both, as shown: `age` as a top-level function, and `Date - Date` gives a `Period`.

### D15e. A clearer name for `today_support`
- **What it is:** `today` always gives one `Date`. This is the careful version, which refuses to pretend when the clock can't say. It's rarely needed.

```dewy
match strict_today {
    d:Date => printl"{d}"                         # the normal case
    a:AmbiguousToday => printl"{a.dates}"         # 23:59:59 with a ±2s clock: 2026-11-06 or 2026-11-07
    u:UnknownToday => printl"clock was never set"
}
```

- **One function, not two:** this returns the same union `today` gives under `$time.explicit_clock_accuracy`, so the range of possible dates lives on `AmbiguousToday`, with no separate query.
- **Options:** `strict_today`, `pedantic_today`, `careful_today`, `checked_today`.
- **Rec:** `strict_today`, since "strict" is already the word for this in the time design. `pedantic_today` is your suggestion and also reads correctly.

### D10. Safety defaults and tag names (#108)
- **BLUF:** with no tags, anything a program can reasonably meet is a value or a compile error, and crashing takes one written word. A tag's first word tells you its direction. Full proposal and the cold-read review of the names: `docs/design/proposals/bulletproof/round2.md`, `round2-review.md`.
- **Exceptions that stay trusted, and why:**
  - **Out of memory and stack overflow:** the program ends with a report. Otherwise every call would be fallible. `$explicit_allocation_failure` is the opt-in for memory.
  - **IEEE floats:** `1.0/0.0` is `inf`. Proving every `/` would wreck game math. `$no_nan_or_inf` is the opt-in.

**What changes with no tags**

| The program does | It gets |
|---|---|
| `input_int("n? ")` at end of input | `int \| EndOfInput \| FileError \| Canceled` |
| `input("name? ")` at end of input | `string \| EndOfInput \| FileError \| Canceled` (today `""`, so a loop can spin forever) |
| `read_stdin` with a read error | Adds `FileError` (today partial text, as if complete) |
| `window("x" 320 200)` with no display | `void \| WindowError` |
| `texture(…)`, or `load_wav(bytes)` on a bad file | A named error value |
| A draw call when the driver fails | Stays `void`; the error is kept and returned at the end of the frame, with no exit |
| `crypto.random_bytes(16)` with no entropy | `array<uint8> \| NoEntropy` |
| `printl` to a full disk | Stays `void`; the program exits 1 with an error at the end. A closed pipe (`\| head`) exits quietly |

```dewy
main = () => {
    let name = input("name? ") or_throw     # just crash: report, exit 1
    let age = input_int("age? ") ?? 0       # or use a default
    printl"{name} is {age}"
}
```

**How to read a tag**

| First word | Direction | When it acts |
|---|---|---|
| `$no_X` | Safer: X can't happen here | Compile error |
| `$prove_X` | Safer: stop trusting X, prove it | Compile error |
| `$explicit_X` | Safer: X must be spelled out in the source or a type | Compile error if omitted |
| `$panic_on_X` | Less safe: X compiles, and if it goes wrong the program ends with a report | Run time |
| `$assume_X` | Less safe: a person's claim, and nothing checks it | Never checked |

**The tags: turn this on, and…**

| Tag | …this happens | Was |
|---|---|---|
| `$no_nan_or_inf` (or `$no_nan`, `$no_inf`) | `total/n` is a compile error unless it's proven to give neither | `$finite_floats` |
| `$no_deadlocks` | A channel wait the compiler can't prove finishes is a compile error | |
| `$no_hidden_costs` | A hidden allocation, costly copy or panic is a compile error | |
| `$no_assumed_externs` | `$assume_waits_outside` and an extern's `& no_effects` are compile errors | |
| `$prove_confined_paths` | `p(args[0]).exists` is a compile error until the path is confined to a base | `$confine_external_paths` |
| `$prove_counter_bounds` | `c += 1` in a loop with no bound, or `parallel` over an unbounded range, is a compile error | `$no_assumed_bounds` |
| `$prove_library_asserts` | Calling a library function that reaches an unproven `assert`, like `graphemes(text)`, is a compile error | |
| `$prove_library_runtime_checks` | Calling library code that relies on a hidden index, division or narrowing check is a compile error | |
| `$prove_library_arena_safety` | `printl(xs)` inside an arena block is a compile error until `printl` is proven not to keep the storage | |
| `$prove_library_drop_cannot_fail` | `@(m.lock)` is a compile error until the library proves releasing can't fail | |
| `$prove_library` | All four library tags. Your code can't fix these errors; the library must be proven | |
| `$prove_finite_float_args` (line above a function) | Calling it with an unguarded float is a compile error; the body may rely on finite values | `$prove_finite_inputs` |
| `$explicit_copies` | `let b = a` on an array is a compile error; write `.copy` | |
| `$explicit_allocation_failure` | Allocating functions return `T \| OutOfMemory`, and using that as `T` is a compile error | |
| `$explicit_module_panic_calls` | Calling a `$runtime_assert` function in your own module is a compile error too | `$assume_local_asserts=false` |
| `$time.explicit_*` | e.g. `$time.explicit_clock_accuracy`: `today.year` is a compile error, because `today` may be `AmbiguousToday` | `$time.require_*` |
| `$panic_on_unproven` | An unproven index or division compiles; if it fails, the program reports and exits 101 | `$runtime_checks` |
| `$prototype` | The same, with a warning at each site. For development only | |
| `$assume_waits_outside` | "This foreign call only waits on the outside world." Unchecked; allowed only in the adapter's body | `$audited_wait` |
| `$unsafe` | Unchanged | |
| `$bulletproof` | Every safer tag; rejects every less-safe tag except `$unsafe`. **It's not usable yet:** even `printl(1)` fails until the library is proven | |

**Removed**
- `$verify_protocols`: see question 4.
- `$explicit_environment_failure`: input failure is always a value now.
- `$explicit_graphics_failure`: graphics failures are values by default.
- `$prove_finite_inputs`: `$no_inf` already rejects unproven arguments, so only the argument contract above remains.

**Named float constants** (also `float32`). `.min` is the most negative finite value, matching `int64.min` and unlike C's `DBL_MIN`.

```dewy
float64.max   float64.min   float64.min_positive   float64.min_subnormal
float64.epsilon   float64.max_exact_int   float64.inf   float64.nan
if float64.min <=? x <=? float64.max same(x)       # proves x is finite
if is_finite(x) same(x)                            # the same fact
```

**Questions:**
1. Approve this naming grammar and these names? Rec: yes. The rename is mechanical, but `$runtime_checks` alone has 2,403 uses.
2. `$panic_on_unproven` or `$crash_on_unproven`? Rec: `panic`, matching `panic` and `& no panics`.
3. Make joined paths a compile error by default? `p"{root}/{name}".exists` would need `root.confine(name) or_throw`. Rec: yes, by your direction. This changes your decided warning.
4. Make `$no_deadlocks` mean what it says? `serve` and `pipeline` would lose their trusted status until a nightly model check proves them, so 24 uses in 15 files become errors under that tag. What stays stated plainly: a fair scheduler, and any `$assume_waits_outside` you wrote. Spin loops and servers that never answer are hangs, not deadlocks; `within` handles those. Rec: yes.

**Also found:** 21 of 29 example programs carry `$runtime_checks`, which fails the common-path test. 6 can drop it now, 4 hit `ui_begin` and `add_box` (being fixed), and 11 hit compiler proof gaps. These are going to the coordinator as work, not a question.

### D11. Compile-time string shapes and game calls (#131–#133)
- **BLUF:** bad action names and melodies become compile errors, with one new word (`shape=`). Removed physics bodies use the existing proven/value/checked rule, with no new tags. Full design: `docs/design/proposals/string-shapes/round1.md`.

**D11a. String shapes.** The checker is ordinary Dewy code run on literals at compile time, and any library can define one. (`@` because it passes the function, and a bare name would call it.)

```dewy
melody_error = (text:string):>string|none => …     # none if fine, otherwise what's wrong
Melody:type = string<shape=@melody_error>
melody = (notes:Melody bpm=120.0):>Sound => …

melody("C4 E4 G4")          # fine, with no run-time cost
melody("C4 E4 G9x")         # compile error: 'G9x' is not a note: the octave is one digit (C4, F#3, Bb5)
melody(typed)               # compile error: cannot prove this string is a Melody
if typed is? Melody play(melody(typed))
let tune = Melody(typed) ?? "C4"
let strict = Melody(typed) or_throw
```

- It also fits regex, `date"…"`, format strings, colors and SQL syntax, and composes with unions: `Tempo:type = 'slow' | 'fast' | string<shape=@bpm_error>`.
- A failed conversion gives `ShapeError`, with the checker's message.
- **Cost:** about 1.6 M instructions per distinct literal, measured on the desktop; repeats become a lookup. A checker that never ends hangs the build, the same as other compile-time code.
- Rec: this spelling. Considered: `string<s => melody_ok(s)>` (needs calls in predicates generally, and a bool can't say what's wrong); a tag on the function (gives no type to store, and lets runtime strings through, which you ruled out).

**D11b. Action names.** No language feature: a string union already does this (tested on today's compiler).

```dewy
Action:type = 'jump' | 'left' | 'right' | 'pause'
let input = Controls<Action>[binds=[
    'jump'  -> [Input.key(Key.space) Input.button(PadButton.a)]
    'left'  -> [Input.key(Key.a) Input.stick(0 (-1))]
    'right' -> [Input.key(Key.d) Input.stick(0 1)]
    'pause' -> [Input.key(Key.escape)]
]]
input.pressed('jump')       # fine
input.pressed('jmup')       # compile error naming the valid actions
```

- Leaving out a binding is a compile error too. Config files test each name with `if name is? Action`, so a stale save can't crash the game.
- Rec: `Controls<A>` and `Binding` replace `action`/`action_pressed`.

**D11c. Removed physics bodies.** Your question was whether people want a choice. Yes, but per call rather than per program: Rapier, `slotmap` and Bevy each offer both a panicking read and a value read, and games use both. A program-wide tag that changes what `pos` returns would mean a helper written for one mode doesn't compile in another. The existing rule gives all three behaviors:

| You want | Write | Tag |
|---|---|---|
| The thing or `none` | `w.get(ball)`, giving `BodyState \| none` | None |
| Proven | `w.pos(ball)` right after `add`, or inside `if w.has(ball)` | None |
| Panic if stale | `w.pos(ball)` | `$panic_on_unproven` |

- `w.remove(ball); w.pos(ball)` becomes a compile error even under `$panic_on_unproven`.
- `if w.has(ball)` only proves `w.pos` after a later compiler stage; until then, the error points to `w.get`.
- Rec: add `w.get` and `w.has`. `w.has` replaces `alive` and `joint_alive`. Considered and rejected: silently returning a default (a removed ball draws at the origin); handles consumed by `remove` (they're usually aliased in module globals).

**UI.** See D28. In the meantime, `ui_begin` closes an open menu itself, with a debug warning.

### D28. Clay-style UI
- **BLUF:** a frame's UI is a plain value, so nothing is ever "open" and the `ui_begin` panic can't exist. No new syntax. Full design: `docs/design/proposals/ui/round1.md`.

```dewy
Choice:type = 'resume' | 'quit'
Screen:type = 'playing' | 'paused' | 'title'
let screen:Screen = 'paused'
let volume:float64 = 0.8
let muted = false

pause_menu = ():>void => {
    let picked = ui<Choice>(back='resume' align='center' column(gap=12 pad=24 width=420 align='center' [
        text("Paused" size=36)
        button('resume' "Resume")
        slider("Volume" @volume 0.0 1.0 step=0.05)     # writes straight to your variable
        if not muted progress(volume)                  # if and loop work inside the array
        button('quit' "Quit to the title")
    ]))
    if picked =? 'resume' screen = 'playing'
    else if picked =? 'quit' screen = 'title'
}
```

- **Common path:** the example above. Mouse, touch, keyboard and gamepad all work with no further code, and `button('resume2' …)` is a compile error when it isn't in `Choice`.
- **When that doesn't fit:**
  - **Reading a button beside it:** `button("Sell")` then `if clicked("Sell") sell(item)` on the next line.
  - **Reacting to a change:** compare with the old value after the tree.
  - **Custom drawing:** reserve a `box(id='map' width=200 height=200 [])` and draw into `rect_of('map')`.
  - **Tests:** `layout(tree 1280 720)` returns plain draw commands, with no window.
  - **Speed:** reuse a static tree, which saved 40% of the frame in a measurement.
- **Semantics taken:**
  - **A value tree, not scoped blocks.** Tested on today's compiler: inside a closure block, `return` only leaves the closure, and writing a local needs `$capture`. Guard-style blocks go silently wrong if the guard isn't bound. The tree costs 16–19% more per frame, about 0.1% of a 60 Hz frame.
  - **Interaction comes from the last frame's layout,** as in Clay, since that's what the player aimed at.
  - **Stale state can't crash.** A removed pressed item cancels the press, and a removed focused item moves focus.
- **Cost:** 378K instructions for a 238-element screen, measured on the desktop in a release build. That's about 0.5% of a 60 Hz frame, with the time estimated from cycles.
- **Risk:** `scroll`, `grid`, `floating` and text wrapping compile in the prototype but don't behave yet, so their cost and design are the least proven. `no allocates` code can't use the tree; a fixed-pool builder would come later.
- **Names to review** (rec: yes to all):
  1. Widgets: `column row box grid scroll floating tooltip modal spacer text image button checkbox slider choice text_field progress`.
  2. `ui(tree)` returns a pick; `show(tree)` is for a tree with no picks.
  3. `pick=` is what comes back, and `id=` is identity only.
  4. `pad` rather than `padding`, pairing with `gap`.
  5. Sizes: `'fit'`, `'grow'`, a number, `part(0.5)`, `grow(low= high=)`, `fit(high=)`. `part` exists because `width=1/2` means half a unit.
  6. A single nine-point `align`: `'top_left'`, `'top'`, … `'bottom_right'`.
  7. `back='resume'` on `ui`, so Escape or B returns that value.

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

### D26. `$capture @x` inside a task, where `x` comes from outside it
- **Status:** you hadn't seen this, so I took the rec provisionally. Tell me if you disagree.
- **Today:** this compiles and the writes silently disappear, because a task's capture is a snapshot.

```dewy
main = () => {
    let total = 0
    concurrent {
        spawn { printl([1 2 3].map(($capture @total y:int):>int => { total += y; y })) }
    }
    printl(total)   # prints 0
}
```

- **Taken:** a compile error saying the enclosing body holds its own copy, since a program that writes this almost certainly expects 6.
- **Considered:** keep it silent; warn.

### D27. `or_throw` in a `spawn { ... }` body
- **Status:** you hadn't seen this, so I took the rec provisionally. Tell me if you disagree.
- **Today:** a compile error, because the body has no declared result to forward the failure through.

```dewy
main = () => {
    let c = channel<int>(4)
    concurrent {
        spawn {
            c.send(1) or_throw
            c.close
        }
        printl(c.receive)
    }
}
```

- **Taken:** infer the result for `spawn` bodies, as for a function with no declared result. A failed task already fails its group, so forwarding fits.
- **Considered:** keep the error; infer it for every lambda.

### D29. Spellings added while building time (all built, all reversible)
Turn these on and each works as shown; say no to any and it is removed.

```dewy
$error_if true "write 24hour"                                # calling this overload is a compile error with that text
day_length = (n:float64):>Duration => 24hour

$check_constant date_error(text) "not a date"                # checks a constant argument at compile time and folds the result; library-only until string shapes replace it
parse_day = (text:string):>Date|ParseError => date(text)

let born = date"1990-03-15"
let d = date"2024-01-31"
let s = d - born
printl"{s.months} {s.days} {s.years} {s.total_days}"         # fields on the Span from Date - Date
printl"{d.add(1month overflow='next')}"                      # first of the next month instead of clamping
printl"{age(born on=d leap_day='february_28')}"              # overrides the 1 March default
printl"{d.weekday} {d.weekday_name} {d.month_name}"          # 0 is Monday; carried over from the old Date
```

- **Rec:** keep all of them. `$check_constant` is alternative D in [string-shapes](proposals/string-shapes/round1.md), so it may be replaced by D11's answer.
- **Reversible:** yes.

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
