# UI and string shapes, revision 2 (D11, D28)

Inputs: `docs/design/proposals/ui/round1.md`, `docs/design/proposals/string-shapes/round1.md`, D11 and D28 as they stand, `~/dev/tmp/dogfood-1107/time-ui.md` (programs 10, 11, 12, 14 and the UI rows of the ranked list), `consistency-audit.md` findings 2, 8, 11 and 16, `parallel-safety.md` (D11c's tag name), and the owner's formatting decision (`fmt` only).

Programs: `~/dev/tmp/rev-1107/ui/`. **Tested** means run or checked on master `d0f9714ef` on the desktop, nothing opened a window or played sound. **Paper** means not built. Stubs are marked in each file.

## BLUF

- **Shapes become the one literal-validation mechanism.** `T<shape=@f>` now works on any type, may name the function's other parameters, runs whenever all of its inputs are known while compiling, folds a passing call to its value, and lets a literal choose an overload and so its result type. That covers every `$check_constant` and `$error_if` in `lib/` (40 sites, mapped in §2.9). Both attributes go.
- **`fmt` works through it, with no compiler knowledge of patterns.** `fmt'.2f'` picks the overload whose pattern shape the literal fits, so it returns a function over numbers, and `fmt'EEEE d MMMM'` returns one over dates. A mismatch is a compile error. This is already true today for single literals (**tested**: `check_literal_picks_result.dewy`). Shapes widen it from one literal to a validated family.
- **No more traps on literal unions (finding 2).** `let a:Action = s` and `s as Action` become ordinary obligations, a compile error unless proven, like `x as uint8`. `Action(s)` reads text and gives `Action | ShapeError`, like `Melody(s)`. Today both compile without a tag and panic (**tested**: `check_union_panics_today.dewy`).
- **The UI core is unchanged.** The value tree, picks, `back=`, `@` places and `show` stay as the dogfood rated them. What changes:
  - `choice` binds a value of your type, not an index.
  - `slider` is generic: ints, floats, exact numbers, quantities, durations and two-thumb ranges, and it shows its value.
  - `field` is a typed input for any type with a reader. It shows the reader's error and replaces `text_field`.
  - New queries `changed(id)` and `committed(id)`.
  - `text(align=)`, a sortable `table`, and `plot`.
  - A coverage set measured against Dear ImGui, Clay, egui, SwiftUI and Flutter (§6.8).
- **Tree reuse can't freeze a slider (finding 16).** A widget that reads this frame's input is a drawing call, under the existing draw-context rule. A cached tree is a `const` (static parts only), and a stateful widget inside a `const` is a compile error. Today one compiles silently (**tested**: `check_const_slider_today.dewy`).
- **Audio returns a handle.** `play` gives `Playing` (`.stop`, `.playing`, `.position`, `.wait`). Lengths are `Duration`s and pitches are `Hz`. With no device, playback still ends on schedule (**tested**).
- **Rebinding is specified (D11b's must-fix).**
  - A save holds only the player's changes, so `reset` and new defaults just work.
  - `rebind` gives back the action that lost the input.
  - `capture` skips the press that started it.
  - `controls_editor(@input)` is the whole rebinding screen.
  - **Tested**: `check_rebind.dewy` and `p10_menus.dewy`.

## 1. Every finding and what happened to it

| Source | Finding | Done |
|---|---|---|
| time-ui must-fix 5 | `choice` takes an index into strings | Binds `@value:T`; options default to `members(T)`; labels via `label(x)`. §6.2. **Tested** |
| time-ui must-fix 5 | `slider` is `float64` only, shows no value | Generic over ordered numbers, quantities, `Duration`; two-thumb on a `Range`; shows its value, with `suffix=`. §6.3. **Tested** for `int64`, `float64`, `rational` |
| time-ui must-fix 6 | No rebinding API; the confirming key is captured | §5. **Tested** |
| time-ui should-fix | `play` gives an `int` | `Playing` handle. §4. **Tested** |
| time-ui should-fix | `tone(440.0 0.5)`, `duration(tune)` is a float | `tone(440Hz 500ms)`, `tune.length:Duration`. §4 |
| time-ui should-fix | No typed field; `rational(text)` gives `none` | `field` for any type with a reader. §6.4. **Tested** for `string` and `int64`. `rational(text)` giving `ParseError` belongs to whoever owns numbers: it's listed in §10 |
| time-ui should-fix | `changed(id)` | Added, with `committed(id)`. §6.5. **Tested** |
| time-ui should-fix | Right-aligned text; sortable table | `text(align=)`, `table` and `heading`. §6.6. **Tested** |
| time-ui should-fix | `plot` | §6.7. **Tested** (stub draws nothing) |
| time-ui nice | `label(x)` for union members | Added: `'move_left'` shows as "Move left". **Tested** |
| time-ui nice | Melody note lengths | `E4/2`, `E4*3` inside the shape. §4 |
| time-ui nice | Game `dt` as `float64*Time` | Not done here: it changes the game hooks, which D28 doesn't own. Recommended to the coordinator |
| time-ui nice | Ring buffer for histories | Not done: a collections item. `plot` takes any `array<float64>` |
| time-ui, D11a | `ShapeError` provisional | Kept provisional; in the names table |
| audit 2 | `BasePrefix(s)`, `s as BasePrefix` panic | §3. Same rule for literal unions and shapes |
| audit 8 | One literal-validation mechanism | §2, with an exact list of what it supports |
| audit 11 | D11c still says `$panic_on_unproven` | D11c now uses `$allow_unproven` |
| audit 16 | Reusing a tree freezes a slider | §6.9 |
| Owner, D19e | `fmt` only; the pattern narrows the input type | §2.5, and every example uses `fmt` |

## 2. Shapes: the one literal-validation mechanism

### 2.1 The form

```dewy
Name:type = T<shape=@validator>                    # an alias, used anywhere a type is
param:T<shape=@validator(other=other ...)>         # on a parameter, naming other parameters
```

- `T` is **any type**: `string`, a record, a quantity, a literal union, an alias.
- The validator is an ordinary function returning `string | none`: none when the value fits, otherwise what is wrong. This is the contract round 1 had and the time validators already follow.
- `@validator(…)` is the existing partial application: it binds some arguments now. The handle must leave **exactly one** parameter open, of type `T`, or **none** (§2.6).
- A shape on a parameter may name the declaration's other parameters, in either order. A cycle is a compile error. Sibling record fields work the same way, as dependent refinements already do (`high:int64<(>=? low)>`).
- A shape may name type parameters, so `<T>string<shape=@spec_error<T>>` is a family.

### 2.2 Constants

The validator runs while compiling when every input is a **constant**:
- a literal;
- a `const`;
- a never-reassigned `let` with a constant initializer (what `$check_constant` accepts today);
- a member of a literal union;
- a record, array, tuple or quantity built only from constants;
- a parameter default read from a metatag at the call site (`fold=$time.fold`);
- the folded result of another shaped call (§2.4), so `zoned("…" zone=zone"Europe/London")` chains.

An interpolated string with holes is not a constant.

### 2.3 What the checker does

| The argument | Result |
|---|---|
| Constant, and the validator gives none | Accepted; no run-time check |
| Constant, and the validator gives text | Compile error **at the argument**, with that text; a note names the type (`the argument must be a Melody`) |
| Already of the shaped type (declared `x:Melody`, narrowed by `is?`, the result of `Melody(s)`) | Accepted |
| Anything else | An ordinary obligation: a compile error with fix-its (`is?`, `Melody(s)`, `$allow_unproven`); under `$allow_unproven`, a check that ends the program, naming only the type |

- `s is? Melody` and a `match` arm `m:Melody =>` run the validator and narrow.
- A shape whose inputs include another parameter has no standalone type to narrow to. Such a parameter takes constants, or values that go to a sibling overload (§2.4).
- Memoized on (validator, inputs), so each repeat is a lookup.

### 2.4 Overloads, folding and result types

1. **A constant goes to the shaped overloads.** If its check fails, that is the error: it never falls through to a plain `string` overload. That keeps `date"…"` and `regex(r"…")` infallible with today's spellings (round 1, decision 3).
2. **A value that isn't proven shaped goes to the unshaped overload,** if there is one (`(text:string):>Date|ParseError`). If there isn't, it's the obligation above.
3. **Several shaped overloads:** a constant picks the one whose shape it fits. If it fits none, the error lists each validator's text. If it fits more than one, the call is ambiguous: a compile error naming both. Libraries keep their shapes disjoint, and their tests catch overlaps.
4. **The chosen overload's declared result is the call's type.** Narrowing comes from overloads, not from stripping error members. The old `$check_constant` narrowing goes, so a reader sees the infallible signature written down.
5. **Folding:** a call that matched a shaped overload, with every argument constant, to a function with no effects, is run while compiling and replaced by its value when that value is constant data. Constant data means records, arrays, strings, numbers, quantities, or a function handle whose bound arguments are constant data. A literal therefore costs nothing at run time. Folding is demand-driven: it only happens at shaped calls.

### 2.5 `fmt`: a literal chooses the input type

The owner's decision needs a pattern literal to choose what the returned function accepts. Rule 3 gives exactly that, using library code only:

```dewy
NumberPattern:type = string<shape=@number_pattern_error>   # '.2f' ',d' '.1%'
DateFormat:type = string<shape=@date_format_error>         # letters owned by the time revision
TextPattern:type = string<shape=@text_pattern_error>       # '>10' '^20'
fmt = ((p:NumberPattern):>((x:Real):>string) => …)
    & ((p:DateFormat):>((d:Date):>string) => …)
    & ((p:TextPattern):>((x:Display):>string) => …)

f2 = fmt'.2f'                                  # parsed once, while compiling
printl'total {f2(total)}, {fmt'.1%'share} of the budget, on {fmt'EEEE d MMMM'today}'
fmt'.2f'"hi"                                   # compile error: this function takes a number, found string
fmt'.2q'                                       # compile error: 'q' is not a number style (f e % d x b o)
```

- **Tested on today's compiler with singletons** (`check_literal_picks_result.dewy`):
  - `fmt = ((p:'.2f'):>((x:float64):>string) => …) & ((p:'upper'):>((s:string):>string) => …)` works;
  - `fmt('.2f')("hi")` is a compile error: `expected float64, found string`.
  - Shapes replace each singleton with a validated set.
- The category names (`Real`, `Display`), how many categories there are, and what a runtime or interpolated pattern gives all belong to the formatting revision. The mechanism supports any choice:
  - a `(p:string)` overload returning a fallible function;
  - no such overload, in which case a computed pattern is an obligation;
  - a width as a dependent parameter.
- **Considered and rejected:** a validator that returns a type, so one generic `fmt` computes its input type. That is type-level evaluation, which is new machinery. Overloads give the same result through existing resolution.
- **Parser gap (tested):** `{fmt'.2f'x}` doesn't parse yet ("expected one interpolation expression"), while `{fmt'.2f'(x)}` does. The error text also still suggests `format(value ".2f")`. Both are for the formatting revision (§10).

### 2.6 Refusing an overload (replaces `$error_if`)

A handle with **no** open input doesn't depend on the value, so it is decided for every call that resolves to that overload, constant or not:

```dewy
refuse = (why:string):>string => why                       # library, one line
__add__ = (t:Instant d:Days<shape=@refuse("a day is a calendar period, with no fixed length on an instant: write `24hour`, or add it to a date or a zoned time")>):>Instant => t
t + 1day        # compile error at `1day`, with that text
t + n*1day      # the same: the overload is chosen by type, and its shape always refuses
```

- This is rule 2.2 applied to a validator with no inputs: all of its inputs are known, so it runs. No new rule is involved.
- The body is never reached, but must type-check.
- `$warn_if` stays. It is a lint with a condition on arguments, not validation. Nothing here replaces it.

### 2.7 Conversions at run time

- **`T(x)` checks:** `Melody(s)`, `Action(s)` and `OnGrid(q)` give `T | ShapeError` (provisional name), whose `message` is the validator's text. A constant argument drops the error member, by rule 4.
- **`x as T`, `let v:T = x`, a `T` argument and a `T` result** are proven conversions: obligations. This is the same rule as `x as uint8` and `uint64(x)` on numbers.
- This splits the jobs cleanly. `T(text)` reads outside data and hands you the failure, as `date(text)` and `Melody(s)` do. `as` and stores claim a fact the compiler must see.
- `ShapeError` is `type of error & [message:string]`. It is not a `ParseError`, since shapes also guard quantities and records. `field` (§6.4) accepts readers that return either.

### 2.8 What shapes do not do

- They don't fix syntax beyond the literal. `"… {id}"` isn't a constant, so SQL injection safety needs its own design (unchanged from round 1).
- They have no fuel limit. A validator that never ends hangs the build, as other compile-time code does.
- **Evaluator gap (round 1, still open):** `text.split` doesn't run at compile time. Validators stay byte loops until the evaluator handles library string operations. This is the main implementation cost.

### 2.9 Porting today's 40 sites

| Today | Sites | Becomes |
|---|---|---|
| `$check_constant date_error(text)` on `date`, and the same for `instant`, `utc`, `zone`, `time_of_day`, `local` | 6 | `date = ((t:DateText):>Date => …) & ((t:string):>Date|ParseError => …)`, `DateText:type = string<shape=@date_error>`; folds to a record |
| `$check_constant date_read_error(text pattern)` and `…_pattern_only(pattern)`, for date, time and local | 6 | `text:string<shape=@date_read_error(pattern=pattern)>`, `pattern:DatePattern`, plus the `(text:string pattern:DatePattern):>Date|ParseError` sibling |
| `date_pattern_error(p)`, `time_pattern_error`, `local_pattern_error` in `civil.dewy` | 3 | `DatePattern`, `TimePattern`, `LocalPattern` aliases |
| `zoned_text_error(text fold gap scope)`, `zoned_error(text zone fold gap scope)`, `local_zone_error(l z fold gap)`, `policy_gap(fold gap)`, `zone_scope_error(scope)` | 5 | Dependent shapes naming those parameters; `fold`, `gap` and `scope` are constants through their metatag defaults; `zone` through a folded `zone"…"` |
| `tick_error(tick)` on `quantize` | 3 | `tick:Tick`, `Tick:type = (rational*Time)<shape=@tick_error>` |
| `compact_instant_error(t)`, `compact_duration_error(d)` on `convert` | 2 | `(t:Instant<shape=@compact_instant_error>):>T` overload beside the fallible one |
| `_grid_error(q)` on Duration and clock arithmetic | 10 | `OnGrid` overloads beside the `OffGrid` ones (§2.4) |
| `_nonzero_int`, `_nonzero_whole`, `_nonzero_duration`, `_span_divisor` | 5 | Plain refinements where they exist (`k:int<(not=? 0)>`); `Duration<shape=@nonzero_duration>` and `Days<shape=@nonzero_days>` for records |
| `regex_error(pattern)` in `regex.jo`; `melody_error(notes)` in `audio.jo` | 3 | `Pattern` and `Melody` aliases |
| `$error_if true "…"` in `core.dewy` | 8 | `@refuse("…")` shapes (§2.6) |
| The compiler's own format-spec grammar (`panic_format_spec`) | — | `fmt`'s pattern shapes (§2.5) |

### 2.10 Cost

- Measured in round 1: 1.6 M instructions per distinct literal through today's constant-check path, on the desktop (instruction counts). Repeats become lookups once memoized.
- A dependent shape runs once per distinct input tuple. Programs with no shaped constants pay one table check per call.
- To verify when landing, on the flagship panel per the performance rule: time's prelude now resolves about 40 shaped overloads instead of reading attributes.

## 3. Literal unions under the same rule (finding 2)

```dewy
Action:type = 'jump' | 'left' | 'right'
let s = read_line ?? ""
let a:Action = s           # compile error: cannot prove s is an Action
                           #   help: `if s is? Action`, `Action(s) ?? 'jump'`, or `$allow_unproven`
if s is? Action input.pressed(s)
let b = Action(s) ?? 'jump'
let c = Action(s) or_throw # ShapeError: 'jmup' is not an Action: one of 'jump' 'left' 'right' (did you mean 'jump'?)
let d = s as Action        # an obligation, like `x as uint8`
```

- **Tested today:** `let a:Action = s` and `s as Action` compile without any tag, and panic on bad text (`panic: a string that is not one of 'jump' | 'left'`). A constant `s` is already a compile error.
- This changes established semantics: LANGUAGE.md says "any other string is checked when the program runs". It goes to the owner as a semantic change carried by D11, with a recommendation. It passes both tests: the common path, constants, is untouched, and adjusting is one `is?` or one `?? default`.
- `'auto' | string<shape=@f>` and `'slow' | 'fast' | string<shape=@bpm_error>` compose as round 1 said: members first, then each shape, and the error lists them all.

## 4. Audio results (D11a's neighbor)

```dewy
Melody:type = string<shape=@melody_error>
melody = (notes:Melody bpm=120 wave=Wave.triangle volume=0.3):>Sound => …
tone = (pitch:float64*Frequency length:Duration wave=Wave.sine):>Sound => …
play = (s:Sound volume=1.0 looping=false):>Playing => …
# Playing: .playing:bool  .position:Duration  .stop  .pause  .resume  .wait:>void|Canceled
#          .volume (settable)
# Sound:   .length:Duration

let p = play(melody("E4/2 E4/2 G4*3 - C4"))     # /2 half a beat, *3 three beats, - holds, . rests
loop p.playing printl'{fmt'.1f'(p.position / 1s)} s'
p.wait or_throw
play(tone(440Hz 500ms))
```

- With no audio device, a `Playing` runs on the monotonic clock and ends at `.length`, so `loop p.playing` terminates. **Tested** in the stub: `p11_melody.dewy` needs no time bound.
- `.wait` can be `Canceled`, as `sleep` can (D4).
- Note lengths are a grammar change in `melody_error` and the player. Nothing in the language changes.

## 5. Controls: the rebinding companions (D11b)

```dewy
Action:type = 'jump' | 'left' | 'right' | 'pause'
let input = Controls<Action>[binds=[
    'jump'  -> [Input.key(Key.space) Input.button(PadButton.a)]
    'left'  -> [Input.key(Key.a) Input.stick(0 (-1))]
    'right' -> [Input.key(Key.d) Input.stick(0 1)]
    'pause' -> [Input.key(Key.escape) Input.button(PadButton.start)]
]]
input.pressed('jump')   input.down('left')   input.axis('left' 'right')
input.bindings('jump')                       # array<Input>: the player's, else the shipped ones
let lost = input.rebind('jump' 0 Input.key(Key.w) conflict='swap')   # Action | none: who had W
input.reset                                  # back to the shipped bindings; input.reset('jump') for one
let saved = input.save(p"controls.txt") or_throw     # the path; holds only the player's changes
let unknown = input.load(p"controls.txt") or_throw   # array<string>: names a stale file had
label(Input.key(Key.space))                  # "Space"; "Ⓐ" or "Cross" by the pad that was used last
let cap = capture                            # Capture: waits for the next new press
cap.next                                     # Input | 'cancel' | none, this frame
controls_editor(@input)                      # the whole rebinding screen, as a Node
input_hint(input 'jump')                     # a Node showing the current binding's glyph
```

- **The confirming press:** `capture` records what is held when it starts. A held input counts only after it has been let go, so the Enter, A or mouse click that chose "rebind" can't become the binding. **Tested**: `check_rebind.dewy` prints `none` for the held Enter, then binds D.
- **Cancelling:** Escape or B (`cancel=`) gives `'cancel'`. While a capture is open, `ui`'s `back=` and navigation are off, so the cancel doesn't also close the menu. **Tested** in the stub (`ui_capturing`).
- **Changes are kept apart from the shipped bindings.** This is Unity's "binding overrides" model:
  - `reset` is just clearing the changes;
  - a save file holds only what the player changed;
  - a game update that changes a default reaches every player who didn't rebind it.
- **Conflicts:**
  - `'swap'` (default): the other action takes the old input.
  - `'clear'`: the other action loses it.
  - `'allow'`: both keep it.
  - In all three, the action that had the input is returned, so a screen can say "W moved from Jump". **Tested.**
- `controls_editor(@input actions=members(A) slots=2)` is generic over any `Controls<A>`: one row per action, a button per slot, capture, conflict note. It replaces round 1's `ui_controls(@input)`. **Tested** in `p10_menus.dewy`.

## 6. UI

### 6.1 The core stays

Unchanged from round 1 (the part the dogfood rated ready):
- `ui<A>(tree back= align=)` returns a pick, and `show(tree)` is for a tree with no picks;
- containers and sizing; `pick=` against `id=`;
- `@` places, and answers from the last frame's layout;
- stale-state rules, the pure `layout` for tests, and custom drawing into `rect_of(id)`.

### 6.2 `choice` binds your value

```dewy
Difficulty:type = 'easy' | 'normal' | 'hard'
let difficulty:Difficulty = 'normal'
choice("Difficulty" @difficulty ['easy' 'normal' 'hard'])     # order as written; a typo is a compile error
choice("Category" @category)                                  # every member of the union, in text order
choice("Level" @level levels labels=(l:Level) => l.title)     # any type: give the options
choice("View" @tab style='tabs')                              # 'dropdown' (default) 'segments' 'list' 'tabs'
```

- Signature: `choice = <A T>(title:string @value:T options:array<T>=members(T) labels:((x:T):>string)=@label style='dropdown')`. **Tested** on today's compiler, including the `members(T)` default and the `@label` default.
- **Order:** a literal union's members are unordered by decided semantics (`members` lists text order whatever the spelling). An ordered choice therefore passes its list. The list is checked against the type, so the explicit form costs no safety.
- **Labels:** `label(x)` turns `'move_left'` into "Move left". It is an ordinary generic function: overload it for your own type, or pass `labels=`.
- **Styles:**
  - A focused dropdown cycles with left and right without opening, so gamepad menus get the "◀ Normal ▶" behavior with no extra style.
  - `'tabs'` is the tab bar. The content is ordinary code (`match tab { … }`), so only the visible tab is built.

### 6.3 `slider` is generic

```dewy
slider("Volume" @volume 0.0 1.0 step=0.05)          # float64 or rational; shows "0.80"
slider("Field of view" @fov 60 120 suffix="°")       # int64: whole steps, shows "90°"
slider("Mouse speed" @turn 30°/s 360°/s)             # a quantity: shows its unit
slider("Respawn delay" @delay 0s 5s step=250ms)      # a Duration
slider("Gravity" @g 0.1 100.0 scale='log')           # logarithmic
slider("Spawn band" @band 0 500)                     # band:Range<int64>: two thumbs
slider("Opacity" @alpha 0.0 1.0 value_text=(v:float64) => '{fmt'.0%'v}')
```

- One generic over any ordered `T` with `+`, `-`, a scale by a number, and `(a-b)/(c-d)` giving a number. That covers ints, floats, `rational`, quantities and `Duration`. An `int` slider moves in whole steps (default `step=1`).
- **Shows its value by default,** formatted by type. Decimals come from `step`, and units from the quantity. `suffix=` adds text, and `value_text=` replaces it. Ctrl-click, or Enter on a focused slider, types a value, as ImGui does.
- `low` and `high` may be in either order (descending sliders, as today's `ui_slider`).
- **Tested:** `int64`, `float64` and `rational` versions in `ui2.dewy`, used by `p10_menus.dewy` and `p14_overlay.dewy`.
- **Tested in `check_generic_quantity.dewy`:** one generic stepping body (`value + step*dx`, clamped) instantiates for `int64`, `rational` and `m/s`.
- **Found there:** the drag fraction `(value-low)/(high-low)` can't be proven nonzero inside a generic body, even after `if span not=? low - low`, because there is no generic zero. The fix belongs to the compiler (§10), and isn't a design change. Until it lands, the library writes one fraction helper per number family, and callers see nothing.

### 6.4 `field`: typed input for any type with a reader (replaces `text_field`)

```dewy
field("Name" @name hint="Your name")              # string
field("Amount" @amount)                           # rational: "12.50"; a bad one shows its error under the field
field("Due" @due)                                 # Date: text plus a calendar popup
field("Mass" @mass step=0.5kg)                    # a quantity: type it, or drag sideways to change it
field("Tint" @tint)                               # a colour: a swatch that opens a picker
field("Pin" @pin hidden=true)   field("Notes" @notes lines=4)
field("Code" @code read=@parse_code)              # your type: any (text:string):>T|ParseError|ShapeError
button('add' "Add" enabled=valid("Amount") and valid("Due"))
```

- **The variable only ever holds a valid value.** While the text doesn't read, the field keeps the text, shows the reader's `message`, and `valid(id)` is false.
- `@x` of type `T | none` maps empty text to `none`.
- Built-in readers cover strings, every number type, quantities, `Date`, `TimeOfDay`, `Duration`, colours, vectors, literal unions and shaped strings (`Melody(s)`). Anything else passes `read=`.
- **Tested:** the generic `field` with the `string` and `int64` readers (`p12_expenses.dewy`).

### 6.5 `changed` and `committed`

```dewy
checkbox("Full screen" @fullscreen)
if changed("Full screen") set_fullscreen(fullscreen)       # true from the widget's call to the frame's end
if committed("Volume") save_settings                       # once per drag, Enter, or focus leaving
```

- `changed` is egui's `.changed()`. `committed` is ImGui's `IsItemDeactivatedAfterEdit` and egui's `drag_stopped`. You need it for undo and for saving after a drag rather than during one.
- **Tested:** `changed` in `p10_menus.dewy`.

### 6.6 Alignment and tables

```dewy
Col:type = 'on' | 'what' | 'amount'
let sort = Sort<Col>[by='on']                         # [by:C descending:bool=false]
table("expenses" @sort [
    heading('on' "Date" width=120)
    heading('what' width='grow')                       # label defaults to label('what')
    heading('amount' width=100 align='right')
] [loop i in 0.. and e in shown row(pick=Row[i=i] [
    text('{e.on}')  text(e.what)  text(money(e.amount) align='right')
])])
```

- Clicking a heading sets `sort.by`, or flips `descending` on the same one. The program sorts its own data, as ImGui's sort specs and SwiftUI's `sortOrder` work.
- Each row's cells take their heading's width and alignment. Widths can be dragged, and the library remembers them per table id.
- Rows scroll inside the table, and long tables give only visible rows (`visible`, round 1).
- **Tested:** `table`, `heading`, `Sort` and `text(align=)` in `p12_expenses.dewy`.

### 6.7 `plot`

`plot(values width=200 height=48 low=0.0 high=1.0 kind='line'|'bars')` is ImGui's `PlotLines` and `PlotHistogram`. For axes, series and scatter, the existing `Chart` draws into a reserved `box`. **Tested** in `p14_overlay.dewy`; the stub draws nothing.

### 6.8 Coverage against the reference toolkits

Everything below is library code over the round-1 core: no syntax, and a value tree throughout.

| Need | Dear ImGui / egui / SwiftUI / Flutter / Clay | Dewy |
|---|---|---|
| Buttons, checkbox, radio, toggle | All | `button`, `checkbox` (`style='switch'`), `choice(style='list')` |
| Value pickers, tabs, segmented | Combo, ComboBox, Picker, DropdownButton, TabBar | `choice` with a `style=` |
| Sliders: int, float, log, range, units | SliderInt/Float, `.logarithmic`, RangeSlider | `slider` (§6.3) |
| Typed input, drag-to-edit numbers, date, colour, password, multi-line | InputText, DragValue, DatePicker, ColorEdit, SecureField, TextEditor | `field` (§6.4) |
| Change and edit-finished events | `changed`, `IsItemDeactivatedAfterEdit` | `changed`, `committed` |
| Hover, click, right-click, double-click, drag delta | Response API, gestures | `hovered`, `clicked`, `right_clicked`, `double_clicked`, `dragged(id):>vec2` |
| Tooltips | `on_hover_text`, `.help` | `tip=` on any node; `tooltip(kids)` for rich ones |
| Disabled and selected | BeginDisabled, `.disabled` | `enabled=` and `selected=` on any node (a container disables its subtree) |
| Shortcuts | Shortcut, `.keyboardShortcut` | `shortcut="Ctrl+S"` on a button: fires the pick even when not visible |
| Menus, menu bar, context menu | BeginMenuBar, Menu, context_menu | `menu_bar`, `menu(title kids)`, `context_menu(id kids)` |
| Movable panels, windows | Begin/End, egui Window | `panel(title @open kids)`: movable, resizable, position kept by the library |
| Collapsing sections | CollapsingHeader, DisclosureGroup | `collapsible(title kids open=)` |
| Dialogs | Modal, alert, Dialog | `modal(kids)` (round 1) |
| Tables with sort and resize | BeginTable, Table | `table`, `heading`, `Sort` (§6.6) |
| Graphs | PlotLines, egui_plot | `plot`; `Chart` in a `box` |
| Lazy long lists | Clipper, LazyVStack, ListView.builder | `visible(id rows row_height)` (round 1) |
| Layout: fit, grow, fixed, percent, gap, padding, alignment, wrap, overlap | Clay, Flutter Wrap and Stack, ZStack | Round 1 sizes; `row(wrap=true)`; `layers(kids)` |
| Floating and attached elements | Clay floating | `floating` (round 1) |
| Separators | Separator, Divider | `divider` |
| Progress and busy | ProgressBar, ProgressView, Spinner | `progress(amount)`; `progress(none)` spins |
| Drag and drop | DnD, Draggable/DragTarget | `drag=true` on a pickable node; `ui(drop=@f)`, with `f:(from:A onto:A):>A|none`, turns a drop into a pick |
| Implicit animation | `withAnimation`, AnimatedContainer | `animate=150ms` on a node: colour, size and position ease, keyed by id |
| Theme, fonts, scale, 9-slice skins, UI sounds | Style, Theme, environment | `Theme` record (round 1), plus `font=`, `scale=`, `background=image(t slice=12)`, `sounds=` |
| Focus: initial, per player | SetKeyboardFocusHere, FocusState | `ui(focus='resume')`; `ui(player=2)` gives a separate focus and only that pad |
| Input glyphs in prompts | Engine add-ons | `input_hint(input 'jump')` |
| Accessibility | AccessKit (egui), Semantics | Every node already carries a role and a label. A platform export from the tree is planned, not specified here |
| Docking, node editors | ImGui docking branch, imnodes | Not in v1. `panel` plus `rect_of` custom drawing is the path. Docking is an application framework, not a widget |

### 6.9 Reuse can't freeze a widget (finding 16)

- **Rule:** a widget that reads this frame's input or writes a place (`slider`, `checkbox`, `choice`, `field`, `table`, `controls_editor`), and every query (`hovered`, `clicked`, `changed`…), is a **drawing call**. It runs in `draw` or a helper reached only from `draw`, under the existing draw-context rule.
  - The library gets this by having its per-frame `sync` read through draw2d's existing `__outside_draw` guard. That is library-only, with no new mechanism.
  - A module-level `let` or a `const` that builds one is then a compile error: "slider reads this frame's input, so it is built in `draw` each frame; keep the static part in a `const`".
  - **Tested today:** `check_const_slider_today.dewy` puts a slider in a `const` tree and compiles and runs silently, so the guard is needed.
- **The reuse spelling is `const`.** A static subtree is built while compiling and spliced into the live tree:
  ```dewy
  const HELP = column(gap=2 [text("F3 hides this" size=12) text("F5 reloads" size=12)])
  show(column([HELP slider("Gravity" @gravity 0.0 30.0)]))
  ```
  **Tested:** `check_const_subtree.dewy`. This keeps round 1's measured 40% build saving where the content really is static.
- **A tree built in `draw` and kept in a variable for later frames** can't be caught statically without a new escape rule. So each stateful node carries the frame it was built in. `ui` draws a stale one disabled (not focusable), and a debug build prints, once, the label and "built in an earlier frame". Nothing freezes silently.

### 6.10 The worked menu, revised

`p10_menus.dewy`, checked and run (`p10_menus_t.dewy` adds the `<Pick>` type arguments today's inference gaps G1 and G2 need):

```dewy
settings_menu = ():>void => {
    let picked = ui<SettingsChoice>(back='back' align='center' column(gap=10 pad=24 width=480 [
        text("Settings" size=32)
        slider("Sound volume" @volume 0.0 1.0 step=0.05)
        checkbox("Full screen" @fullscreen)
        choice("Difficulty" @difficulty ['easy' 'normal' 'hard'])
        slider("Field of view" @fov 60 120 suffix="°")
        row(gap=8 [button('defaults' "Defaults") spacer button('back' "Back")])
    ]))
    if changed("Full screen") set_fullscreen(fullscreen)
    if picked =? 'defaults' { volume = 0.8; fullscreen = false; difficulty = 'normal'; fov = 90 }
    else if picked =? 'back' screen = 'paused'
}
```

Compared with the dogfood version, this drops `DIFFICULTIES`, `difficulty_index`, the `float64` FOV, the `text("{fov:.0f}°")` line and the `old_full` comparison.

## 7. Dogfood re-run

| # | Program | Status |
|---|---|---|
| 10 | `p10_menus.dewy`: pause, settings, rebinding | Checked and ran on the stubs (`ui2`, `controls2`, `editor2`) |
| 11 | `p11_melody.dewy` | Ran: `Playing`, `Duration` lengths, ends with no device. `Melody` lines are paper |
| 12 | `p12_expenses.dewy` | Checked and ran: `field`, value `choice`, `table`, `align`, `valid` |
| 14 | `p14_overlay.dewy` | Checked and ran: `plot`, `divider`, `tip=`, `suffix=` |
| 17 | `p17_inspector.dewy`: a level-editor inspector | Paper: `panel`, `menu_bar`, `choice(style='tabs')`, typed fields, `collapsible`, `committed` |
| 18 | `s1_shapes.dewy`: shapes, unions, `fmt` | Paper; the `fmt` part has a compiled singleton analog |
| 19 | `p19_inventory_drag.dewy` | Paper: drag and drop as a pick, `layers`, `animate=`, `input_hint` |

Scores (O obvious, D discoverable, C concise, S safe by default, X complete):

| # | O | D | C | S | X | What keeps it from 5 |
|---|---|---|---|---|---|---|
| 10 menus | 5 | 5 | 5 | 5 | 5 | Floor note: an unordered `choice("Difficulty" @difficulty)` lists Easy, Hard, Normal. That is the decided `members` order; the fix is the one-line list, which is checked |
| 11 melody | 5 | 5 | 5 | 5 | 5 | |
| 12 expenses | 5 | 5 | 4 | 5 | 5 | The per-column `match` for sort keys stays, since the keys have different types (`Date`, `string`, `rational`). `sorted(descending=)` (a language should-fix, §10) removes the `reversed` line. Floor 4: there is no shorter typed form without heterogeneous key functions |
| 14 overlay | 5 | 5 | 5 | 5 | 5 | |
| 17 inspector | 5 | 5 | 5 | 5 | 5 | Paper |
| 18 shapes and `fmt` | 5 | 4 | 5 | 5 | 5 | Discovering `@refuse` for library authors: one doc line under shapes. Not user-facing |
| 19 inventory | 5 | 4 | 5 | 5 | 5 | `drop=` as a function from two picks to a pick is learned once. It is the only spelling that keeps drops typed with no closures over locals |

## 8. Replacement text for open_decisions.md

### D11. Compile-time shapes, action names, audio handles and removed physics bodies (#131–#133)
- **BLUF:** turn this on, and a library can say what a valid literal looks like with ordinary Dewy code. Bad melodies, action names, dates and format patterns then become compile errors, constants cost nothing at run time, and text that comes from outside must be checked before it can crash. One new word, `shape=`. It replaces `$check_constant` and `$error_if`. Full design: `docs/design/proposals/string-shapes/round2.md`.

```dewy
melody_error = (text:string):>string|none => …     # none if fine, otherwise what's wrong
Melody:type = string<shape=@melody_error>
melody = (notes:Melody bpm=120):>Sound => …
Action:type = 'jump' | 'left' | 'right'
f2 = fmt'.2f'
let typed = read_line ?? ""

play(melody("C4 E4 G4"))                    # fine, nothing checked at run time
melody("C4 E4 G9x")                         # compile error: 'G9x' is not a note: the octave is one digit (C4, F#3, Bb5)
if typed is? Melody play(melody(typed))
let tune = Melody(typed) ?? "C4"            # Melody | ShapeError
let a:Action = typed                        # compile error: cannot prove typed is an Action
let b = Action(typed) ?? 'jump'             # Action | ShapeError, never a panic
let p = play(melody("E4/2 E4/2 G4*3"))      # a Playing handle: p.playing, p.position, p.stop, p.wait
printl'{f2(1.5)} {fmt'EEEE d MMMM'date"2026-11-07"}'
fmt'.2f'"hi"                                # compile error: this function takes a number, found string
```

- **Common path:** pass literals and they're checked and folded. Use `is?`, `T(text) ?? default` or `or_throw` for outside text.
- **Adjusting:**
  - Shapes work on any type, not just text.
  - They may read the function's other parameters (`date(text "d/M/y")` checks the text against that pattern).
  - Several shaped overloads let a literal choose the result type, which is how `fmt'.2f'` gives a function over numbers.
  - A shape with no input refuses an overload with a fix-it (`t + 1day` says "write `24hour`").
- **Semantics taken:**
  - A constant that fails never falls through to a plain `string` overload.
  - A passing call with all constant arguments and no effects folds to its value.
  - **Changed:** `let a:Action = s` and `s as Action` are obligations like `x as uint8`. Today they compile and panic on bad text.
  - `T(text)` gives `T | ShapeError`.
- **Cost:** about 1.6 M instructions per distinct literal (desktop, instruction counts); repeats are lookups.

**D11b. Action names and rebinding.** A literal union names the actions, and `Controls<A>` holds the shipped bindings and the player's changes apart:

```dewy
Action:type = 'jump' | 'left' | 'right' | 'pause'
let input = Controls<Action>[binds=[
    'jump'  -> [Input.key(Key.space) Input.button(PadButton.a)]
    'left'  -> [Input.key(Key.a) Input.stick(0 (-1))]
    'right' -> [Input.key(Key.d) Input.stick(0 1)]
    'pause' -> [Input.key(Key.escape)]
]]
input.pressed('jump')                                    # 'jmup' is a compile error naming the actions
let lost = input.rebind('jump' 0 Input.key(Key.w))       # gives the action that had W, which takes Jump's old key
input.save(p"controls.txt") or_throw                     # only the player's changes
let unknown = input.load(p"controls.txt") or_throw       # names a stale file had; never a crash
controls_editor(@input)                                  # the rebinding screen, ignoring the press that opened it
```

- `capture` waits for a new press, so the Enter or A that chose "rebind" can't become the binding. Escape cancels without closing the menu.
- `Controls<A>` and `Binding` replace `action` and `action_pressed`.

**D11c. Removed physics bodies.** Unchanged from round 1, except the tag: `w.get(ball)` gives `BodyState | none`; `w.pos(ball)` is proven after `add` or inside `if w.has(ball)`, or checked under `$allow_unproven`. `w.has` replaces `alive` and `joint_alive`.

- **Names to review (rec: yes to all; each to be read cold before you see it):**
  1. `shape=` on any type, and `ShapeError`.
  2. `refuse` (the library helper for a shape that always fails).
  3. `Playing` with `.playing .position .stop .pause .resume .wait`; `Sound.length`; note lengths `E4/2` and `E4*3`.
  4. `rebind(action slot input conflict=)` with `'swap' 'clear' 'allow'`; `reset`, `save`, `load`, `bindings`; `capture` and `.next`; `controls_editor`; `input_hint`.

### D28. Clay-style UI
- **BLUF:** turn this on, and a frame's UI is a plain value. Nothing is ever "open", widgets write straight into your variables, and picks come back typed against your own union. No new syntax. Full design: `docs/design/proposals/ui/round2.md`.

```dewy
Choice:type = 'resume' | 'quit'
Screen:type = 'playing' | 'paused' | 'title'
Difficulty:type = 'easy' | 'normal' | 'hard'
let screen:Screen = 'paused'
let volume = 0.8
let fov = 90
let difficulty:Difficulty = 'normal'
let fullscreen = false
set_fullscreen = (on:bool):>void => …

pause_menu = ():>void => {
    let picked = ui<Choice>(back='resume' align='center' column(gap=12 pad=24 width=420 [
        text("Paused" size=36)
        button('resume' "Resume")
        slider("Volume" @volume 0.0 1.0 step=0.05)                 # shows "0.80"
        slider("Field of view" @fov 60 120 suffix="°")              # whole numbers
        choice("Difficulty" @difficulty ['easy' 'normal' 'hard'])  # binds the value itself
        checkbox("Full screen" @fullscreen)
        button('quit' "Quit to the title" tip="Progress is saved")
    ]))
    if changed("Full screen") set_fullscreen(fullscreen)
    if picked =? 'resume' screen = 'playing'
    else if picked =? 'quit' screen = 'title'
}
```

- **Common path:** the example above. Mouse, touch, keyboard and gamepad all work with no further code, and `button('resume2' …)` is a compile error.
- **When that doesn't fit:**
  - **Typed input:** `field("Amount" @amount)` for any type with a reader, showing its error.
  - **Reacting:** `changed(id)` and `committed(id)`.
  - **Tables:** `table` with sortable `heading`s.
  - **Graphs:** `plot(values)`.
  - **Tools:** `panel`, `menu_bar`, `collapsible`, `choice(style='tabs')`.
  - **Drag and drop:** `drag=true` and `ui(drop=@f)`.
  - **Custom drawing:** reserve a `box(id='map' …)` and draw into `rect_of('map')`.
  - **Tests:** `layout(tree 1280 720)` gives plain draw commands.
  - **Speed:** keep static parts in a `const` and splice them in.
- **Semantics taken:**
  - A value tree, with interaction from the last frame's layout, as round 1 had.
  - Stale state can't crash.
  - A widget that reads input is a drawing call, so a `const` or module-level tree holding one is a compile error, and a tree kept across frames draws its widgets disabled with a debug warning rather than freezing them.
  - A `choice` without a list shows the union in text order.
- **Cost:** 378K instructions for a 238-element screen (desktop, release), about 0.5% of a 60 Hz frame.
- **Risk:** `scroll`, `grid`, `floating`, wrapping, `table` column sizing and drag and drop are the least proven. No `no allocates` builder yet.
- **Names to review (rec: yes to all; each to be read cold before you see it):**
  1. Round 1's: `column row box grid scroll floating tooltip modal spacer text image button checkbox slider choice progress`, `ui` and `show`, `pick=` and `id=`, `pad`, the sizes, the nine-point `align`, `back=`.
  2. `field` replacing `text_field`, with `valid(id)`, `hidden=`, `lines=`, `read=`.
  3. `changed(id)` and `committed(id)`.
  4. `choice`'s `style=`: `'dropdown' 'segments' 'list' 'tabs'`; and `label(x)`.
  5. `slider`'s `suffix=`, `value_text=`, `scale='log'`.
  6. `table`, `heading`, `Sort` (`by`, `descending`); `plot` with `kind='line'|'bars'`; `divider`.
  7. `tip=`, `shortcut=`, `enabled=`, `selected=`, `animate=` on any node.
  8. `panel`, `menu_bar`, `menu`, `context_menu`, `collapsible`, `layers`, `row(wrap=)`.
  9. `drag=` and `ui(drop=)`; `right_clicked`, `double_clicked`, `dragged`; `ui(focus= player=)`.

## 9. New or changed names, for the cold read

| Name | Intended meaning |
|---|---|
| `shape=` (on any type) | The value must pass this validator; checked while compiling for constants |
| `ShapeError` | The failure from `T(x)` when `x` doesn't fit `T`; `message` says why |
| `refuse("…")` | Library helper: a shape that always fails with this text, used to forbid an overload with a fix-it |
| `Playing` | A sound that is playing: what `play` returns |
| `.playing` | Whether it is still sounding |
| `.position` | How far it has played, as a `Duration` |
| `.stop` `.pause` `.resume` | End it, hold it, continue it |
| `.wait` | Block until it ends (can be `Canceled`) |
| `Sound.length` | How long a sound lasts, as a `Duration` |
| `E4/2`, `E4*3` in a melody | Half a beat; three beats |
| `rebind(action slot input)` | Put this input in this slot of the action; gives the action that had it |
| `conflict='swap' 'clear' 'allow'` | When another action has the input: it takes the old one, it loses it, or both keep it |
| `reset` | Go back to the bindings the game shipped |
| `save(path)` / `load(path)` | Write or read the player's binding changes; `load` gives unknown names |
| `bindings(action)` | The inputs an action currently has |
| `capture` / `.next` | Wait for the next new press; this frame's answer: an input, `'cancel'`, or none |
| `controls_editor(@input)` | A ready-made rebinding screen |
| `input_hint(input action)` | A UI element showing the key or button glyph currently bound |
| `field` | An input box for any type, showing why the text doesn't read |
| `valid(id)` | Whether that field's text currently reads |
| `hidden=` / `lines=` / `read=` | Password dots; several lines; your own reader |
| `changed(id)` | The widget's value changed this frame |
| `committed(id)` | An edit finished (drag released, Enter, focus left) |
| `label(x)` | The display text for a value: `'move_left'` → "Move left" |
| `style='dropdown' 'segments' 'list' 'tabs'` | How a `choice` looks |
| `suffix=` | Text after a slider's shown value |
| `value_text=` | A function giving the slider's shown text |
| `scale='log'` | The slider moves logarithmically |
| `table` / `heading` / `Sort` (`by`, `descending`) | A table with clickable column titles; which column it is sorted by, and which way |
| `plot` (`kind='line' 'bars'`) | A small graph of numbers |
| `divider` | A thin separating line |
| `tip=` | Text shown when hovering or focusing |
| `shortcut=` | A key combination that triggers this button |
| `enabled=` / `selected=` | Can be used; is highlighted as chosen |
| `animate=` | Changes to this element ease over this time |
| `panel` | A movable, resizable window inside the game or tool |
| `menu_bar` / `menu` / `context_menu` | A top menu row; one dropdown menu; a right-click menu |
| `collapsible` | A titled section that opens and closes |
| `layers` | Children drawn on top of each other |
| `row(wrap=true)` | Children flow onto the next line when out of room |
| `drag=` / `ui(drop=)` | This element can be dragged; how a drop becomes a pick |
| `right_clicked` / `double_clicked` / `dragged` | Those pointer events on an element |
| `ui(focus=)` / `ui(player=)` | Which element starts focused; which player's controller drives this menu |

## 10. Outside this task: bugs and slips found

- **Overload errors name an unrelated prelude function:** a typo in a `choice` option list reports `no 'choice' for string (use random_item(xs))`, from the prelude's random `choice`. Repro: `ui/p10_menus_t.dewy` with `'normal'` changed to `'nromal'`.
- **A parameter name hides a same-named function in defaults:** with a parameter called `label`, a default of `@label` refers to the parameter, and the error says "defaults referring to earlier parameters cannot yet be combined with mutable arguments". Repro: in `ui/ui2.dewy`, rename `choice`'s `title` back to `label`.
- **`int * 1ms` gives `OffGrid | Duration`,** though a whole number of milliseconds is always on the nanosecond grid. Repro: `ui/audio2.dewy`, `length`.
- **A local named like a unit hides it** (`ms`, `s`). The message is good for `s`, but for `ms*1ms` it misreports as `Duration + int`. Repro: `ui/audio2.dewy` before the rename (`let ms = …; d + ms*1ms`).
- **No nonzero proof in a generic body:** `if span not=? low - low { (value-low)/span }` still reports "cannot prove divisor is nonzero" for each instance. A comparison with the type's own zero should count. Repro: `ui/check_generic_quantity.dewy`.
- **`{fmt'.2f'x}` doesn't parse,** and the interpolation error still suggests `format(value ".2f")`, which the owner removed. Repro: `{fmt'.2f'x}` in any interpolation. For the formatting revision.
- **`.sum` over a mapped `int64` array needs a fit proof** (already in time-ui's should-fix list). Repro: `ui/p12_expenses.dewy`, original `total` line.
- **Inference gaps G1 and G2** (round 1) still need `<Pick>` on each widget, and a second explicit type for generic widgets (`choice<Pick Difficulty>`). `ui/typed2.py` applies them.
- **Splat-importing a UI module shadows prelude names** (`text`, `image`, `row`, `progress`, `sync`, `Align`, `Range`, `flatten`) with warnings. The real library must be the prelude's own `text` and `image` overloads, as round 1 planned.
- **Not done here, recommended to their owners:**
  - `sorted(descending=)`;
  - `rational(text)` giving `ParseError`;
  - game `dt` as `float64*Time`;
  - a ring buffer;
  - `match` arms `'on' =>` needing `<'on'> =>`;
  - `c:Column =>` not narrowing (time-ui program 12).
