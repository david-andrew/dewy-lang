# String shapes, action names, stale handles, UI

Answers to the feedback on open decision D11. **Tested** means I ran it on today's compiler (scratch: `~/dev/tmp/design-1106/x`). **New** means it needs your approval.

## Summary

- **Strings:** one new option, `Melody:type = string<shape=@melody_error>`, on the existing refinement rule. It replaces the private `@check_constant` attribute.
- **Actions:** no new language feature. A literal union plus a generic `Controls<Action>` already gives a type error (**tested**).
- **Physics:** yes, people want the choice, but per call, not as a program-wide tag. The existing rule already gives all three behaviors; only `w.get(b)` is missing.
- **UI:** a layout built as a value has no "open" state to leave behind. Until then, `ui_begin` closes the open menu itself.

## 1. String shapes

### What exists

- `@check_constant(validator(param) "message")` is on `regex` (`compiler/check_constant.jo`). It runs the library's own code on a literal and reports the returned text as the error.
  - It is the right engine, with the wrong surface: Jo only, per parameter, and runtime strings pass unchecked.
- **Tested:** adding it to a Jo `melody` already gives this error:
  ```
  error: not a melody: 'G9x' is not a note: the octave is one digit, 0 to 9 (C4, F#3, Bb5)
      x += melody("C4 E4 G9x")
                  ^
  ```
- The refinement rule already has the rest: refuted is a compile error, unproven is a compile error by default, and `$runtime_checks` makes it a run-time check.
- `date"…"` needs no literal mechanism: `f"…"` is already a call with a literal argument.

### Recommended spelling

**New:** a `shape=` option inside `string<…>`, following `uint8<overflow='wrap'>`. No new grammar.

The validator is an ordinary function, `(text:string):>string|none`, the same contract as `regex_error`. It returns none when the text is fine, otherwise what is wrong.

```dewy
note_error = (t:string):>string|none => {
    if t.length =? 0 return "a note cannot be empty"
    if not ("ABCDEFGabcdefg".contains(t[0..1))) return "'{t}' is not a note: it starts with a letter from A to G"
    let at = 1
    if at <? t.length and (t[at..at+1) =? "#" or t[at..at+1) =? "b") at += 1
    if at =? t.length return none
    if at+1 =? t.length and "0123456789".contains(t[at..at+1)) return none
    return "'{t}' is not a note: the octave is one digit (C4, F#3, Bb5)"
}
melody_error = (text:string):>string|none => {
    loop word in text.split(" ") {
        if word =? "" or word =? "-" or word =? "." continue
        let why = note_error(word)
        if why not=? none return why
    }
    return none
}
Melody:type = string<shape=@melody_error>
melody = (notes:Melody bpm=120.0 wave=Wave.triangle volume=0.3 step=0.5):>Sound => { ... }
```

Use:

```dewy
let theme = melody("A3 - C4 E4 - D4" 70.0 Wave.sine 0.18)
let fanfare = melody"C4 E4 G4"
melody("C4 E4 G9x")       # error: "C4 E4 G9x" is not a Melody: 'G9x' is not a note: the octave ...

let typed = read_line ?? ""
melody(typed)             # error: cannot prove this string is a Melody
                          #   help: `if typed is? Melody`, `Melody(typed)`, or `$runtime_checks`
if typed is? Melody play(melody(typed))
let tune:Melody = Melody(typed) ?? "C4"
let strict = Melody(typed) or_throw
if melody_error(typed) is? string printl"bad tune"
```

### Rules

| Value stored in a shaped type | Result |
|---|---|
| Literal, or a `const` holding one, that fits | Stored; no run-time check |
| Literal that doesn't fit | Compile error at the literal, with the validator's text |
| Any other string | Ordinary obligation: compile error, or a check under `$runtime_checks` |
| `s is? Melody` | Runs the validator and narrows `s` |
| `Melody(s)` | **New:** `Melody | ShapeError` (provisional name), `message` holding the validator's text; a literal drops the error member, as `regex` does |

- At run time a `Melody` is a plain `string`, so it passes to `string` parameters at no cost.
- A panic under `$runtime_checks` names only the type, not the text (the 10-23 no-leak decision).

**Functions that return another type** (`regex`, `date`) use an overload, keeping today's spellings:

```dewy
Pattern:type = string<shape=@regex_error>
regex = ((p:Pattern):>Regex => compile(p)) & ((p:string):>Regex|RegexError => ...)
```

**New rule, needed for this:** a constant string goes to the shaped overload and stays there. A bad literal is a compile error; it doesn't fall through to the `string` overload. This replaces `check_constant`'s result narrowing.

**It composes with literal unions:** the literal is tried against the members, then against each shape, and the error lists them all.

```dewy
Tempo:type = 'slow' | 'fast' | string<shape=@bpm_error>
```

### Other formats

| Format | Definition | Note |
|---|---|---|
| Regex | `string<shape=@regex_error>` | Exists today as the validator |
| Date, zone | `string<shape=@date_error>` | `date"2027-01-31"` is a call |
| Format spec | `<T>string<shape=@format_error<T>>` | Generic validator, so `panic_format_spec`'s separate grammar in the compiler can go |
| Color | `string<shape=@hex_color_error>` | |
| SQL-like | `string<shape=@sql_error>` | Syntax only. `"… {id}"` isn't a literal, but `$runtime_checks` would let it through, so injection safety needs a separate design |

### Alternatives

| Spelling | For | Against |
|---|---|---|
| **A. `string<shape=@melody_error>`** (recommended) | Reuses refinements and type options; message from the validator | One new option word |
| B. `string<s => melody_ok(s)>` | No new word | Lifts "no calls in predicates" in general; a bool gives no reason for the error |
| C. `Melody:type = type of string` plus a literal hook | Own methods; distinct type | `type of string` is unsupported; wrapping at every string use; magic hook name |
| D. `$check_constant melody_error(notes) "…"` on the function, like `$warn_if` | Smallest change | No type to store or pass; runtime strings accepted silently, which you ruled out |

### Prior art

From my own knowledge; I didn't look these up for this note.

- **C++20 `std::format_string`:** the closest match. A `consteval` constructor checks the literal, and `std::runtime_format` marks runtime text.
- **Scala `refined` and Iron (`String :| Match[…]`):** the same model as a library: literals at compile time, `refineEither` at run time. They show the demand.
- **Zig `comptime fmt`:** an ordinary validator with `@compileError`, but no type to carry and no runtime path.
- **TypeScript template literal types:** compose with unions, but the pattern language is separate, deep types hit limits, messages are fixed, and `as` doesn't check.
- **Rust:** `const fn` is limited; proc macros (`sqlx::query!`) are arbitrary and slow builds. This is the cost to avoid.
- **Kotlin value classes:** `init { require(…) }` checks at run time only.
- **Idris:** `fromString` with an `auto` proof `So (valid s)`: the same idea as dependent types.

### Compile-speed cost

Measured with instruction counts on `desktop-msi-redfox`, using a 39-token melody through today's constant-check path:

| Literals checked | `check` instructions |
|---|---|
| 0 | 283 M |
| 1 | 285 M |
| 2 | 286 M |
| 100 (all the same) | 441 M |

- That is about **1.6 M per literal**, with no memoization yet. Ten melodies add about 16 M, around 5% of this tiny program's compile; a real game has far more to compile, so its share is smaller.
- **Memoize on (validator, interned text):** repeats then cost only a lookup.
- **Demand-driven:** a validator is instantiated only when a constant meets a shape. A program with no shaped constants pays only a table check per call.
- **No fuel limit:** a validator that never ends hangs the build (**tested**: killed at 120 s). That matches `checked_eval.dewy` ("general compile-time execution is trusted"), and I'd keep it.

### Work needed

- Port `@check_constant` to the type option, then delete the attribute.
- **Evaluator gap (tested):** `text.split` fails at compile time ("raw representation casts are not supported", from `__memchr`). The validator above runs at run time today, and a byte-loop version runs at compile time. Library string operations must work in the evaluator, or every validator stays a byte loop.
- **Union bug (tested):** `'auto' | string<length >? 0>` rejects `'x'` with "not one of 'auto'".
- **Interim, two lines, works today:** add `@check_constant(melody_error(notes), "not a melody")` to `melody` and `melody_loop` in `lib/game/audio.jo`.

## 2. Action names

The game declares a union and gives each member its bindings. No compiler special case is involved.

```dewy
Action:type = 'jump' | 'left' | 'right' | 'pause'

let input = Controls<Action>[binds=[
    'jump'  -> [Input.key(Key.space) Input.key(Key.up) Input.button(PadButton.a)]
    'left'  -> [Input.key(Key.a) Input.key(Key.left) Input.stick(0 (-1))]
    'right' -> [Input.key(Key.d) Input.key(Key.right) Input.stick(0 1)]
    'pause' -> [Input.key(Key.escape) Input.button(PadButton.start)]
]]

update = (dt:float64):>void => {
    if input.pressed('jump') jump
    let x = input.axis('left' 'right')
    if input.pressed('jump' player=1) jump_second
}
```

The library is generic and knows nothing about the game's set:

```dewy
Binding:type = array<Input>
pressed = (b:Binding player=-1):>bool => ...
Controls:type = <A>[binds:totaldict<A Binding>]
pressed = <A>(c:Controls<A> name:A player=-1):>bool => c.binds[name].pressed(player)
axis = <A>(c:Controls<A> neg:A pos:A player=-1):>float64 => ...
```

- **Tested** (with a stub `Input`):
  - A missing binding is a compile error: `this totaldict has no entry for 'left'`.
  - A misspelling is a compile error today, and it already names the valid ones:
    ```
    error: no version of 'pressed' takes (Controls<…> string): argument 'name' expects 'jump' | 'left' | 'right', found string
    ```
- **Worth a small diagnostic change:** `'jmup' is not an Action: one of 'jump' | 'left' | 'right' (did you mean 'jump'?)`.
- A generic rebind screen takes the same value: `ui_controls(@input)`, walking `members(A)`. Separate sets just work: `Controls<MenuAction>` beside `Controls<Action>`.

**Actions from a run-time config** come in two cases.

*Rebinding known actions* is the usual one. Each name is tested, and unknown names are reported rather than fatal, so a stale save can't crash the game (**tested**):

```dewy
load_bindings = <A>(@c:Controls<A> text:string):>array<string> => {
    let unknown:array<string> = []
    loop line in text.split("\n") {
        let parts = line.split("\t")
        if parts.length not=? 2 continue
        let name = parts[0]
        if name is? A c.binds[name] = parse_inputs(parts[1])
        else unknown.push(name)
    }
    return unknown
}
```

*Actions unknown when compiling* (mods) skip `Controls` and use an ordinary `dict<string Binding>`, where `mods.get(name)` gives `Binding | none` (**tested**).

**Rejected:**
- *Keeping the free `action_pressed('jump')`:* global state has no type parameter, so the library would have to find `Action` by name, which is compiler magic.
- *Collecting `action("…")` names across the program:* also magic.
- *Returning `false` (the old D11c suggestion):* it hides the typo.

**Gap (tested):** a generic function can't take `totaldict<A Binding>`, though a generic record can. Fixing it would allow a shorter `controls<Action>([...])`; it isn't required.

## 3. Physics handles

### Do people want a choice?

Yes, but per call rather than per program.

| Library or engine | Direct read | Value read |
|---|---|---|
| Rapier, `slotmap` (Rust) | `set[h]` panics | `set.get(h)` gives an `Option` |
| Bevy | `commands.entity(e)` panics | `query.get(e)` gives a `Result` |
| Unity, Godot | Exception or logged error | `== null`, `is_instance_valid` |

- Within one game, people use both: panic for "the player always exists", a value for "this enemy may be gone".
- I know of no engine with a program-wide switch that changes what `pos` returns. It would fork the API: a helper written for one mode wouldn't compile in another.
- Proving a handle live across frames isn't something games do. It matters locally and in the certifiable lane.

### Recommendation: the existing rule, no new tags

| You want | Spelling | Tag |
|---|---|---|
| Panic if stale | `w.pos(ball)` | `$runtime_checks` |
| The thing or none | `w.get(ball)` (**new**: `BodyState | none`) | None |
| Proven | `w.pos(ball)` under `if w.has(ball)` or right after `add` | None (the default; also `$bulletproof`) |

Tags decide only what happens to an *unproven* `w.pos`; they never change its type.

**Most of this exists (tested):** `w.pos(ball)` without `$runtime_checks` is already a compile error with a fix-it, and 25 of the 36 example and template modules already carry that tag. `Pool` has the full rule, and `pool.remove(h); pool[h]` gives "the handle is no longer in the pool".

**One `get`, not `get_pos`:** the 2D world has 49 uses of the handle lookup and the 3D world has 47 of its equivalent. Doubling each accessor is too much surface. `w.get(b)` returns a small record of scalar readings (`pos angle velocity spin mass kind tag`).

### The common game path

```dewy
$runtime_checks
let ball = world.add_circle(vec2(0 0) 8)

draw = ():>void => { circle(world.pos(ball) 8 WHITE) }      # never removed: plain read
```

```dewy
let enemy:physics.Body|none = world.add_box(at size)        # may go away: hold it as optional

update = (dt:float64):>void => {
    if enemy is? physics.Body and world.pos(enemy).y >? 700.0 {
        world.remove(enemy);
        enemy = none
    }
}
```

With no tag at all, the fix-it offers `w.get(ball)`.

### Options evaluated

| Option | Common path | Verdict |
|---|---|---|
| Existing rule (above) | One tag line; plain `w.pos(ball)` | **Recommended** |
| Consuming handles (`w.remove` takes `ball`) | `contacts()`, `bodies()` and `bodies_at()` return aliases that moves can't see, and handles usually live in module globals, where owners are unsupported | Rejected. It only catches `remove; pos` in one scope, which a refuted fact catches without move-only types (`Pool` does) |
| No-op or default value (the old D11b suggestion) | Easy, then a removed ball draws at the origin | Withdraw it: it hides the bug |
| New `$stale_handles='panic'\|'none'\|'proven'` | Changes result types per module | Rejected: forks the API |

### Stages

1. **Library only:** add `w.get`, rename `alive` to `w.has`, and make `remove` return `bool` as `Pool` does. Under no tag, `if w.has(b) { w.pos(b) }` is still an error until stage 2; the fix-it points to `w.get`.
2. **Compiler, time-boxed:** `facts.jo` recognizes `Pool` by its file path (`fact_pool_call`), so a wrapper like `World` can't carry the proof.
   - Move body storage onto a `Pool`. A wrapper whose body is just `__bodies.has(h)` or `__bodies[h]` then publishes that same fact and obligation to its caller.
   - No new spelling is needed, and the path check goes away.
   - `w.remove(ball); w.pos(ball)` becomes a compile error, even under `$runtime_checks`.
   - If it doesn't pan out, stage 1 stands alone.

**Same rule elsewhere:** in `lib/`, generation-checked handles appear only in `Pool` and the two physics worlds. `Joint` should join them: its reads and writes silently do nothing today. A joint can die when its body is removed, so that is a good case for `w.get(j)`; `joint_alive` goes.

## 4. UI

I found no Clay work in `~/dev/slop-lang`, so this is a direction, not a port. A frame's UI is a value, so nothing is open while your code runs and an early `return` can't leave anything behind:

```dewy
Choice:type = 'resume' | 'settings' | 'quit'

pause_menu = ():>Ui<Choice> => column(gap=12 padding=24 at=vec2(640 340) [
    text("Paused" size=36)
    button('resume' "Resume")
    button('settings' "Settings")
    row(gap=8 [text("Volume") meter(volume)])
    button('quit' "Quit")
])

draw = ():>void => {
    let picked = ui(pause_menu)             # lays out, draws, handles focus: Choice|none
    if picked =? 'resume' paused = false
    else if picked =? 'quit' quit
}
```

- Item ids are a literal union, so a misspelled id is a type error, as with actions.
- Focus and scroll live in the library, keyed by id; each frame's tree can use a per-frame arena.
- Open question for the real design: how sliders and text fields return values.

**Interim:** remove the panic. `ui_begin` finishes an open menu itself by calling `ui_end`, with a debug-build warning (the D11a suggestion). It takes a few lines. The scoped `ui_menu` form isn't worth adding as a stopgap.

## 5. The two tests

| Topic | Common path easy, ergonomic, fast? | When it doesn't fit, is adjusting straightforward? |
|---|---|---|
| String shapes | Yes: pass a literal; no run-time cost; about 1.6 M instructions per distinct literal | Yes: `is?`, `Melody(s) ?? x`, `or_throw`, or `$runtime_checks` |
| Actions | Yes: one union line and one table; typos stop compiling | Yes: `is? A` for config, `dict<string Binding>` for mods |
| Physics | Yes: `w.pos(ball)` with the existing tag; no check where proven | Yes: swap to `w.get`, or add a guard |
| UI | Yes once built: no pairing to remember | Yes for the interim; stateful widgets need their own design |

## Decisions for you

Each has a recommendation; all are reversible until the libraries depend on them.

1. **`string<shape=@f>` and the name `ShapeError`.** Recommended. Unblocks melody, date, regex and format. Alternative word: `format=`, but it collides with the format-string meaning.
2. **Make `Action(s)` and `let a:Action = s` follow the rule.** Recommended: this changes established semantics.
   - **Tested:** both compile without `$runtime_checks` today and panic on a bad string, a trap the no-traps default should forbid. `LANGUAGE.md` documents it.
   - Proposed: `Action(s)` gives `Action | ShapeError`, and the store is an ordinary obligation.
3. **A constant string never falls through from a shaped overload to a `string` overload.** Recommended. It keeps `regex(r"…")` and `date"…"` infallible with today's spellings.
4. **Replace `action`/`action_pressed` with `Controls<A>`.** Recommended. Unblocks the type error; library names `Controls` and `Binding` are provisional.
5. **`w.get`, and `w.has` replacing `alive` and `joint_alive`; withdraw the D11b and D11c no-op suggestions.** Recommended.

## Outside this task

- `$assert validator("literal")` cost about 370 M instructions per run in my measurement, against 1.6 M through the constant-check path. The validator in that test also had an unproven slice, so this is unclean and undiagnosed, but worth a look.
