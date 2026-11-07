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
- **Status:** revising into v3 after your notes. Accepted parts and directions are in decisions.md (batch 3).
- **v3 will answer:** dependency-aware block items; `?? void` filtering; opt-in cancellation; the `select` signature and how to tell channels apart without `.then`; why `Tasks` is its own type; ranges as sequences; plain rewrites of C7, C9 and C11; and the Zig cancellation design.

---

## P2: unblocks common friction

### D10. Safety defaults and tag names (#108)
- **Status:** accepted parts are in decisions.md (batch 3). Names are being re-picked by testing candidates on readers with no context, and they come back here with the winners. Proposal: `docs/design/proposals/bulletproof/round2.md`.
- **Still open, Q3: should joined paths be a compile error by default?**

```dewy
let name = read_line ?? ""
printl(p"{root}/{name}".exists)              # name could be "../../etc/passwd"
printl(root.confine(name).exists or_throw)   # the confined form
```

  - **a)** Compile error by default; a script that doesn't care writes one tag line at the top (an `$allow_…` name, picked in the naming test).
  - **b)** Warning by default, and an error only under `$bulletproof` and the confinement tag.
  - **Rec:** (a). The danger only comes from pieces you don't control: archive entries, uploads, user input. The cost for a quick script is one line, with a fix-it the editor applies. Under (b), the most common way this bug ships stays a warning.

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

### D31. More spellings added while building time (all built, all reversible)
Turn these on and each works as shown; say no to any and it is removed.

```dewy
$time.rules = 'urgent.bin'                               # a rule file beside the main file, rather than v6's descriptor
Box:type = <T=int64>[v:T]                                # bare Box means Box<int64>; this is how bare Date means Date<Gregorian>
let b:Box = Box[1]
let t = instant"2026-01-01T00:00:00Z"
let small = convert<Instant<width=64>>(t)                # Name<option=N> always means a type declared Name_option_N
let r = [date"2026-01-01"..date"2026-02-01")
printl"{r.first} {r.last} {r.includes_first} {r.includes_last} {r.is_empty}"
printl"{quantize(t rounding='floor' tick=1s)}"           # also 'nearest_even', 'nearest_away', 'ceil', 'toward_zero'; gives the value and what was lost
let at = time_of_day"09:30"
let l = local"2026-11-01T01:30"
printl"{date"2026-11-01".at(at)} {l.in_zone(zone("America/New_York") fold='later')}"
printl"{date"2026-11-01".format("EEEE d MMMM y")} {date("1/11/2026" "d/M/y")}"   # Unicode's date letters; a two-digit year doesn't read
```

- **Rec:** keep all of them. `Name<option=N>` standing for `Name_option_N` is the one to look at hardest, as it is a naming convention the compiler knows about.
- **Reversible:** yes.

### D32. Unicode-licensed time zone data in the repository
Mapping Windows zone names to IANA names uses Unicode's CLDR table, now stored in the rule pack. Its license asks that its copyright and permission notice travel with copies, and the project has kept to Apache-2.0 WITH LLVM-exception with no NOTICE file.

- **Options:**
  - **a) Keep the table and add Unicode's notice** next to the data file.
  - **b) Drop the table.** On Windows, `'system'` then warns and reads times as UTC unless `$time.zone` or `TZ` names an IANA zone.
- **Rec:** (a). Windows machines report only their Windows name, so without the table every Windows program needs a setting.
- **Reversible:** yes.

### D34. A temperature difference type, and the names for R-values
Turn on a difference type and passing a reading where a difference belongs is a compile error naming the fix, instead of silently counting from absolute zero. Today the same call compiles and gives 517 W where 39 W is right.

```dewy
from units import ft, °F, BTU, R, RValue, Length, Temperature
heat_loss = (area:float64*Length^2 rise:float64*TemperatureDifference r:float64*RValue) => area*rise/r
let a:float64*Length^2 = 8ft*40ft
let wall:float64*RValue = 25.0R
let rise = 70°F - 30°F
printl"{heat_loss(a rise wall) as (BTU/hour):.1f}"           # fine
printl"{heat_loss(a 70°F wall) as (BTU/hour):.1f}"           # compile error, names `70°F - 30°F`
```

- **Rec:** add `TemperatureDifference`. It is not built. An unannotated parameter already rejects a reading.
- **Also built provisionally, for you to see:** the names `R`, `RSI` and `RValue`, plus `BTU`, `kJ`, `kW`, `kWh`, `ft`/`foot`/`feet`, `yd`/`yard`/`yards`, `mile`/`miles`.
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
```

Today the same contract works on a `let`, a parameter or a record field, so a function can fill one given by `@` or return it inside a record.

- **Rec:** add it, as the next step if returning these arrays turns out to matter. It would be the first alias allowed to refer to itself this way.
- **Reversible:** yes.

### D35. `in_zone` on a zoned time
Turn this on and a zoned time shows the same moment in another zone directly, as an `Instant` already does. Not built.

```dewy
let slot = zoned("2026-11-01T09:00" zone=zone"America/New_York")
printl(slot.in_zone(zone"Europe/Berlin"))            # proposed
printl(slot.nominal.in_zone(zone"Europe/Berlin"))    # today
```

- **Rec:** add it.
- **Reversible:** yes.

### D36. Names for common derived unit dimensions
Turn this on and `units` names the common derived dimensions, as it already names `RValue`, so a field reads `power:float64*Power` instead of `float64*Mass*Length^2/Time^3`. Not built.

```dewy
from units import kW, Power
Appliance:type = [name:string power:float64*Power]
let kettle = Appliance["kettle" 2.2kW]
```

- **Names:** `Area`, `Volume`, `Speed`, `Acceleration`, `Force`, `Energy`, `Power`, `Pressure`.
- **Rec:** add them.
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
