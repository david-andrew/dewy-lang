# A declarative UI layout interface for Dewy

Scratch programs: `~/dev/tmp/design-1106/ui/`. **Tested** means I ran it on today's compiler. Measurements are instruction counts on the desktop (i7-6700), release build, per frame.

## 1. BLUF

- **A frame's UI is a plain value.** `column(gap=12 [ ... ])` returns a `Node`; `ui(tree)` lays it out, draws it and returns what was picked. Nothing is ever "open", so the `ui_begin` panic has no equivalent.
- **Children are an ordinary array literal.** `if`, `loop`, `let` and even `return` already work inside one. No new syntax.
- **Interaction is answered from the last completed layout, as in Clay,** resolved once per frame. Widgets ask while being built: `slider("Volume" @volume 0.0 1.0)` writes through its place and then returns a plain node.
- **Three ways interaction comes back:** the typed pick from `ui`; `@` places for stateful widgets; `clicked(id)` and `hovered(id)` anywhere, including right beside the widget.
- **Cost:** 378K instructions for a 238-element screen, about 0.5% of a 60 Hz frame (estimated from cycles). Allocation is not the bottleneck.

```dewy
Choice:type = 'resume' | 'quit'
Screen:type = 'playing' | 'paused' | 'title'
let screen:Screen = 'paused'
let volume:float64 = 0.8

pause_menu = ():>void => {
    let picked = ui<Choice>(back='resume' align='center' column(gap=12 pad=24 width=420 align='center' [
        text("Paused" size=36)
        button('resume' "Resume")
        slider("Volume" @volume 0.0 1.0 step=0.05)
        button('quit' "Quit to the title")
    ]))
    if picked =? 'resume' screen = 'playing'
    else if picked =? 'quit' screen = 'title'
}
```

Mouse, touch, keyboard and gamepad all work with no further code.

**Language gaps:** two inference fixes (§7) stand between this and today's compiler. Today it compiles with an explicit type on each widget, `button<Choice>(...)`.

## 2. The central choice

**Recommendation: (c), a value tree whose widgets answer while being built.** It adds about 19% to the frame over scoped blocks, and in exchange it can't be left open, has no capture rules, and is a value that tests can assert on.

### The options

- **(a) Pure value tree.** `ui(tree)` returns the pick. It has no good answer for sliders: a node can't hold a place, and returning each value by ID costs two lines per slider.
- **(b1) Scoped blocks as closures.** `column(gap=12 () => { text("Paused"); if button("Resume") paused = false })`.
- **(b2) Scoped blocks as drop guards.** `{ let c = column(gap=12); text("Paused"); if button("Resume") paused = false }`, closed by a `$__drop__` hook.
- **(c) Value tree, answers at construction.** (a) plus last-frame answers, so `slider(@v ...)` writes immediately and `clicked(id)` works anywhere.
- **(d) Message passing, as in Elm.** `ui` returns a list of messages, and a slider takes a function from value to message. It is sound but heavier for the 80% path, so I didn't prototype it. Payload picks (`Slot[i=3]`) keep its best part.
- **Rejected without a table row:** `ui_begin`/`ui_end` pairing (the bug itself); a trailing `column(gap=12) { ... }`, which is new syntax. **Tested:** today it parses as two expressions.

### Comparison

| | (b1) closures | (b2) guards | **(c) value + answers** |
|---|---|---|---|
| `if`/`loop` inside | Plain code | Plain code | Plain code in a collector (**tested**); one wrinkle below |
| Early `return` | **Tested:** leaves the closure only; the outer function continues | **Tested:** closes correctly | **Tested:** abandons the tree; nothing to close |
| Writing a local | **Tested:** compile error; needs `($capture @x)` per block | Plain code | Plain code (**tested**) |
| Interaction beside the widget | `if button(...)` | `if button(...)` | Two lines: `button(...)` then `if clicked(...)` |
| Forgetting something | Nothing to forget | A guard not bound to a name closes at once and the layout is silently wrong; `let c` warns as unused today | Nothing to forget |
| Answers typed against a union | Possible | Possible | Yes, and `ui` returns them |
| Frame cost, same screen | 318K | 326K | **378K** |
| Test with no window | Needs a recording run | Needs a recording run | `layout(tree w h)` is a pure function (**tested**) |
| Cache a static tree | No | No | Yes: saves 40% of the frame (**tested**: 225K) |
| `no allocates` | **Tested:** compiles with a fixed pool, capture-free block | Not established: a pool proof failed where the same code passed in (b1), undiagnosed | **Tested:** rejected, since a `Node` holds an array |
| New syntax | None | None, plus a warning exception | **None** |

### Why (c) wins

- **Both tests pass on the common path, and no rule has to be learned.** (b1) fails on a `return` that quietly doesn't return, and on `$capture` once you touch a local. (b2) fails on `let c` scaffolding with a silent failure when it's omitted.
- **The extra 60K instructions is 0.1% of a frame.** It isn't worth trading crash-proof structure for.
- **`if button(...)` is the one thing it loses.** The two-line form below stays adjacent, and most menus read better with the pick anyway.

```dewy
button("Sell")
if clicked("Sell") sell(item)     # a void call in a collector emits nothing (tested)
```

**The wrinkle, tested:** a bare `count = 5` directly inside `[ ]` is read as a record field and is an error. `if c count = 5` and `{ count += 1 }` both work. Worth a better diagnostic, since a UI tree invites it.

### Why the last layout, not this frame's

A value tree could hit-test against this frame's layout, since the whole tree is known before `ui` runs. It shouldn't:

- The player aimed at what was on screen, and that is the last frame's layout.
- A widget new this frame can't be clicked until it has been seen. This replaces today's `__ui_open_frame` special case by construction (**tested**: frame 1 gives none).
- One rule means `ui`, `clicked` and `slider` can never disagree.

### The strict lane

- Game code never enters it (GOALS), so `no allocates` trees aren't a v1 goal.
- The layout core works on a flat store, not the tree. A later non-allocating builder can feed that store with fixed pools.
- An arena doesn't change this. **Tested:** building the tree in `$allocator` costs 146K against 156K, 3% of the frame. Not worth a rule on the common path.

## 3. API

**BLUF:** about 20 short functions. Every container takes the same named arguments.

### Containers and leaves

```dewy
column(kids) row(kids) box(kids) grid(kids cols=6)   # all take the arguments below
scroll(name kids)                                    # clips; offset held by the library
floating(kids attach='parent' anchor='top_left' at=vec2(0 0) z=1 capture=false)
tooltip(kids)     # floating at the pointer
modal(kids)       # floating at the screen center: captures pointer and focus
spacer            # grows along its parent
text(s size= color= wrap= width=)
image(texture width= height=)
```

### Shared arguments

| Argument | Values | Default |
|---|---|---|
| `width`, `height` | `200`, `'fit'`, `'grow'`, `part(0.5)`, `grow(low=100 high=300)`, `fit(high=400)` | `'fit'` |
| `pad`, `gap` | `12`; `pad=Pad[x=8 y=4]` for per-axis | `0` |
| `align` | `'top_left'` `'top'` `'top_right'` `'left'` `'center'` `'right'` `'bottom_left'` `'bottom'` `'bottom_right'` | `'top_left'` |
| `color`, `radius`, `border`, `border_color` | `rgb(...)`, numbers | Theme or none |
| `pick` | A value of the tree's type: makes this clickable and focusable, and `ui` returns it | none |
| `id` | `'graph'`, `3`: identity only, for `hovered`, `rect_of` | none |

- **Tested:** the union parameter takes `width=200`, `width='grow'` and `width=part(0.5)`, and `button('quit')` shows its id as the label.
- **A trap, tested:** `width=1/2` means half a unit, not half the parent. That's why `part` exists.

### IDs

| Kind | How | Stability |
|---|---|---|
| Pick | `button('resume' "Resume")`, `box(pick=Slot[i=i] ...)` | The value is the identity, so it's stable in loops and under reordering |
| Stateful widget | The label: `slider("Volume" ...)`, or `id="gravity"` when the label changes each frame | Duplicate labels get an occurrence number; `id=` for reorderable lists |
| Anything else | `id='graph'` | Yours |

- `button` label defaults to the id's text: `button('Quit')` shows "Quit".
- Picks may be a plain string with no declared union: `ui(column([button("Play" "Play")]))`, then `p =? "Play"`. **Tested**, with no typo checking.
- Automatic position-based IDs aren't possible: a child is built before its parent, so it has no path yet. Labels and values avoid the need.

### Interaction

```dewy
ui<A>(tree back=none align='top_left' theme=default_theme controls=ui_controls):>A|none
show(tree align='top_left' theme=default_theme controls=ui_controls):>void   # for a tree with no picks
hovered(id) pressed(id) clicked(id) focused(id)      # bool, from the last layout
rect_of(id):>Rect|none
over_ui            # is the pointer on any UI (so a click doesn't reach the game world)
typing             # is a text field focused (so letters aren't game keys)
```

### Focus and navigation

- **Gamepad and keyboard work by default.** The first focusable item takes focus. Up, down, left and right move to the nearest focusable item in that direction, from the last layout.
- **Tested** on a column: up moved focus to the slider, and right changed it from 0.5 to 0.6. Not tested on grids.
- A focused slider or `choice` takes left and right for itself. A focused text field takes letters.
- `back='resume'` makes Escape or B return that value. It replaces `ui_back()`. It should count only if this tree was in the last layout, so the key that opened a menu doesn't close it (not yet in the stub).
- Bindings use `Controls<UiAction>` from the string-shapes proposal, with `UiAction:type = 'up'|'down'|'left'|'right'|'ok'|'back'`. A default exists; `controls=` replaces it for rebinding.
- `modal` traps focus and pointer. Focus is remembered per menu, so returning from Settings lands on the item you left.
- Local multiplayer (a `player=` argument with focus per player) is left for later.

## 4. Stateful widgets

**BLUF:** your value lives in your variable, reached through `@`. Only transient UI state (drag, caret, scroll offset) lives in the library, keyed by ID.

```dewy
slider("Volume" @volume 0.0 1.0 step=0.05)
checkbox("Mute" @muted)
choice("Level" LEVELS @level)
text_field("Name" @name hint="Your name")
progress(volume)
```

- **Tested, run to completion:** `@` works in a collector on a global, a local, a record field and an array element (`loop i in [0..xs.length) slider("V{i}" @xs[i] 0.0 1.0)`). One proof wrinkle: after that loop, the compiler no longer knows `xs.length`, so a later `xs[2]` needs a guard.
- A node never holds the place. The widget writes during the call and returns plain data, so no place rule is stretched.
- To react to a change, compare with the old value after the tree. No event channel is needed.

### Long lists

- Building 10,000 rows a frame is too slow. Scroll offset comes from the last frame, so a helper can give just the visible rows, with no closure: `loop row in visible('log' rows 24) ...`. Not built yet.

### Stale state

All lookups give `T|none`, so a missing ID can't crash.

| Situation | Result |
|---|---|
| Pressed item removed mid-press | Press cancelled; no pick (**tested**, ran) |
| Focused item removed | Focus moves to the first focusable (**tested**, ran) |
| `rect_of` an absent ID | `none` (**tested**, ran) |
| `ui` pick whose ID left this frame | `none` |
| Scroll or caret for an ID unseen for a while | Dropped (planned: after 10 s, with a size cap) |

## 5. Rendering

**BLUF:** a pure layout pass produces a plain array, and a small adapter turns it into existing draw calls.

```dewy
Command:type = [kind:'rect'|'text'|'image'|'border'|'clip'|'unclip' key:uint64
    x:float64 y:float64 w:float64 h:float64
    color:vec4 radius:float64 size:float64 text:string]

layout = <A>(tree:Node<A> width:float64 height:float64 measure=@text_width):>array<Command>
draw_commands = (cmds:array<Command>):>void      # ui() = answers + layout + draw_commands
```

- **Tests assert on layout with no window (tested):** `layout(column(...) 1280 720)` gave a text command at x=616, y=28.
- **The adapter** maps to `rect_rounded`, `rect_rounded_outline`, `text`, `sprite` and `clip`. `clip` isn't nested today, so the adapter intersects nested rectangles. Not built.
- **Drawing context:** `ui` and `show` are drawing calls, under the existing rule that they run from `draw`. `layout` runs anywhere.
- **Custom drawing:** reserve space with `box(id='map' width=200 height=200 [])`, then draw into `rect_of('map')`. No callback in the tree.
- **Text measurement:** `measure` is an ordinary function argument (**tested**). The default is `text_width`, which already works with no window (**tested**). It cost 38K for 123 labels, about 310 each, so a cache isn't justified yet.
- **Theme:** a plain `Theme` record passed to `ui`, with `themed(t kids)` for a subtree. Style left as `none` on a node is resolved top-down during flatten, so there's no global to mutate. Not yet in the stub.
- **Layering:** several `ui` calls per frame paint in order, and the topmost in the last layout gets the pointer, so a menu blocks the HUD beneath it.

## 6. Examples

**How they were tested:** I ran `dewy check` on all four against a working stub (`ui_clean.dewy`), with no `$runtime_checks` in the examples or the stub. Mechanical changes for today's compiler (`typed.py`): an explicit type on each generic widget, and ID constants for literals (gaps G1, G2). Example 3 also used a stub `Rect2` and a `printl` in place of `draw_chart`. `drive.dewy` ran the interaction checks.

**The stub** has real layout, picks, sliders, focus and stale handling. `grid`, `scroll`, `floating`, `wrap`, `image`, `radius` and `align` on `ui` compile but don't behave yet (`align` on containers handles `'center'` only). `theme`, `themed`, `controls`, `draw_commands`, `visible`, `over_ui` and `typing` aren't in it at all.

### Pause menu with gamepad navigation (checked; pick, slider, nav and back ran headless)

```dewy
Choice:type = 'resume' | 'settings' | 'quit'
Screen:type = 'playing' | 'paused' | 'settings' | 'title'
let screen:Screen = 'paused'
let volume:float64 = 0.8
let muted = false

pause_menu = ():>void => {
    let picked = ui<Choice>(back='resume' align='center' column(gap=12 pad=24 width=420 radius=12 align='center' color=rgba(0 0 0 0.75) [
        text("Paused" size=36)
        button('resume' "Resume")
        button('settings' "Settings")
        slider("Volume" @volume 0.0 1.0 step=0.05)
        if not muted progress(volume)
        checkbox("Mute" @muted)
        button('quit' "Quit to the title")
    ]))
    if picked =? 'resume' screen = 'playing'
    else if picked =? 'settings' screen = 'settings'
    else if picked =? 'quit' screen = 'title'
}
```

### Scrolling inventory grid with tooltips (checked; scroll, grid and tooltip placement not behaving yet)

```dewy
Slot:type = [i:int64]
Pick:type = 'close' | Slot
Item:type = [name:string info:string count:int64 icon:Texture]
const CELL = rgb(0.16 0.18 0.22)
const LIT = rgb(0.32 0.38 0.50)
let bag:array<Item> = []
let open_bag = true

use_item = (it:Item):>void => { printl("use {it.name}") }

inventory = ():>void => {
    let picked = ui<Pick>(back='close' align='center' column(gap=12 pad=16 radius=10 color=rgba(0 0 0 0.8) [
        row(gap=8 width='grow' [text("Inventory" size=28) spacer button('close' "Close")])
        scroll('bag' height=420 [
            grid(cols=6 gap=6 [
                loop i in 0.. and it in bag {
                    let slot = Slot[i=i]
                    let lit = hovered(slot) or focused(slot)
                    box(pick=slot width=64 height=64 radius=6 align='center' color=if lit LIT else CELL [
                        image(it.icon width=48 height=48)
                        text("{it.count}" size=14)
                    ])
                    if lit tooltip([text(it.name size=18) text(it.info wrap=260)])
                }
            ])
        ])
    ]))
    if picked =? 'close' open_bag = false
    else if picked is? Slot {
        let it = bag.get(picked.i)
        if it is? Item use_item(it)
    }
}
```

### Debug overlay inside a game (checked; `show` with no picks)

```dewy
let time_scale:float64 = 1.0
let wireframe = false

debug_overlay = (dt:float64 bodies:int64):>void => {
    show(align='top_right' column(gap=4 pad=8 radius=6 color=rgba(0 0 0 0.6) [
        text("{1.0/dt} fps  {bodies} bodies" size=14)
        box(id='graph' width=200 height=48 color=rgba(1 1 1 0.08) [])
        slider("Time scale" @time_scale 0.1 2.0 step=0.1)
        checkbox("Wireframe" @wireframe)
    ]))
    let r = rect_of('graph')
    if r is? Rect draw_chart(fps_chart r)
}
```

### A non-game tool: form and table (checked)

```dewy
Row:type = [i:int64]
Pick:type = 'add' | 'clear' | Row
Contact:type = [name:string email:string]
let contacts:array<Contact> = []
let name = ""
let email = ""
let selected:int64 = -1
const NAME_W = 220.0

cell = (s:string width:Size):>Node<Pick> => text(s width=width)

contact_tool = ():>void => {
    let picked = ui<Pick>(column(width='grow' height='grow' pad=16 gap=12 [
        text("Contacts" size=24)
        row(gap=8 width='grow' [
            text_field("Name" @name width=NAME_W)
            text_field("Email" @email hint="someone@example.org" width='grow')
            button('add' "Add" enabled=name.length >? 0)
            button('clear' "Clear" enabled=contacts.length >? 0)
        ])
        row(pad=4 width='grow' [cell("Name" NAME_W) cell("Email" 'grow')])
        scroll('table' width='grow' height='grow' [
            loop i in 0.. and c in contacts row(pick=Row[i=i] pad=4 width='grow'
                color=if i =? selected rgb(0.2 0.3 0.5) else rgba(0 0 0 0) [
                    cell(c.name NAME_W)
                    cell(c.email 'grow')
                ])
        ])
        text("{contacts.length} contacts" size=14)
    ]))
    if picked =? 'add' { contacts.push(Contact[name=name email=email]); name = ""; email = "" }
    else if picked =? 'clear' { contacts.clear(); selected = -1 }
    else if picked is? Row selected = picked.i
}
```

## 7. Gaps in today's compiler

**BLUF:** no new syntax. G1 and G2 are needed for the spelling above, G3 for correct IDs. G4 and G5 are worked around.

| # | Gap (all tested) | Needed for | Fix |
|---|---|---|---|
| G1 | A literal given to a bare `A` binds `A=string`, ignoring the expected type: `let x:Node<Choice> = button('resume' "R")` errors | Typed IDs without `<Choice>` | Extend `expected_binds` (`compiler/expr.jo:1529`), which already does this for literals inside an array |
| G2 | Expected type doesn't flow through a call argument into array elements: `column<Choice>([text("y")])` can't infer, while `let k:array<Node<Choice>> = [text("x")]` works | No `<Choice>` on leaves and on `spacer` | Pass the parameter type as the literal's expected type |
| G3 | **A bug:** `.hash()` on a union value disagrees with its member. A `Slot` held in `'a'|Slot` hashed to 0, so all slots would collide | Payload IDs | Fix `hash`. The stub works around it by hashing the interpolated text |
| G4 | A default naming an earlier parameter can't combine with an `@` argument (`id=label` on `slider`) | Tidier signature | Stub uses `id=""` |
| G5 | `Node<none>`: `A|none` with `A=none` is rejected | `ui` with no type | Avoided by `show`, whose parameter is `Node<NoPick>` |

I estimate G1 and G2 as small, but didn't build them.

**Outside this task, tested:** `docs/LANGUAGE.md` says a call inside `$allocator` may not change an outer variable through `@`, but a `float64` write that way compiled and ran. Either the doc or the check is off.

## 8. Performance

**BLUF: target at most 2K instructions per element in release, and no heap growth once warm, for up to 500 elements (about 1M a frame). The prototype is already there.**

Inventory screen, 238 elements and 206 commands, the slope between 1000- and 2000-frame runs:

| Measured (desktop i7-6700, release) | K instructions per frame |
|---|---|
| **Value tree, whole frame** | **378** (1,590 per element; about 255K cycles) |
| Of which building the tree | 156 |
| Of which flattening | 86 |
| Of which measuring, placing, commands | 136 (38 is text measuring) |
| Hover lookups (42) | 5 |
| Closures (b1) | 318 |
| Guards (b2) | 326 |
| Tree reused across frames | 225 |
| Tree built in an arena | 146 for the build alone, against 156 |
| 1,150 elements | 1,862 (1,619 per element: linear) |
| Same frame, development build | 609 |
| Proof-clean stub: union fields, fresh buffers, keys through text | 481 |

- **Estimated:** 75 µs on this desktop (cycles at the 3.4 GHz nominal clock, not wall-clock), about 0.45% of a 16.7 ms frame. Wall-clock on `redfox` hasn't been run.
- **Not measured:** draw calls (the same in every option), text wrapping, scroll clipping, floating sort. I'd expect wrapping to be the largest of these, and it's the reason to keep a word-level cache in reserve.
- **Clay** claims microsecond layout. I didn't run it, so I make no direct comparison. Ours is likely slower per element and is still well inside a frame.
- **Compile cost, not measured:** each distinct `A` instantiates only constructors, flatten and pick-finding; the layout core isn't generic. Measure on the flagship panel when landing, per the performance rule.

**No-crash claim, tested:** with an unproven index in the library, a caller with no `$runtime_checks` gets `calling ui may panic`. After guards, all four examples and the stub check clean with no tag. The existing effect inference is therefore the gate. `ui_unended` should become a positive test: this program must compile.

## 9. Migration

**BLUF:** replace everything in one change, no shims.

- **Delete:** `ui_begin`, `ui_end`, `ui_button`, `ui_slider`, `ui_switch`, `ui_choice`, `ui_text_field`, `ui_text`, `ui_back`, `ui_ready`, `ui_style`, and the `hud_*` family, which the design subsumes (`floating(attach='screen' at=...)` covers absolute placement). `ui_typing` and `hud_hovered` become `typing` and `over_ui`.
- **Convert:** `examples/{camera_roll,controls,netpong,reaction_field,rollback_lab}.dewy`; `lib/new/dewy/{arcade,online,story}.dewy` and their `lib/new/*.jo`; `lib/invite.jo`; `lib/game/controls.jo` (`ui_controls` becomes a function returning a `Node`, generic over `Controls<A>`, walking `members(A)`); `lib/game/window.jo`; `tests/fixtures/programs/slider_controls.dewy`.
- **Also touch:** `compiler/expr.jo:3643`, `compiler/habits.jo:149` and a comment at `compiler/check.jo:971` name these functions; `docs/LANGUAGE.md` around line 4975; `tests/cases/template_proofs/ui_unended.*`.
- **Order:** G1, G2 and G3; then the library with headless tests; then the callers.
- **Interim:** `lib/game/ui.jo` still panics after three unended menus. If the library won't land soon, take the small interim fix from the string-shapes proposal.

The arcade template, before and after:

```dewy
# before
ui_begin("pause" vec2(640 340))
if ui_button("Resume") or ui_back() screen = Screen.playing
if ui_button("Quit to the title") screen = Screen.title
ui_end()

# after
let picked = ui<PauseChoice>(back='resume' align='center' column(gap=12 [
    button('resume' "Resume")
    button('quit' "Quit to the title")
]))
if picked =? 'resume' screen = Screen.playing
else if picked =? 'quit' screen = Screen.title
```

The simple case is about the same length. The gains are in layout, sizing, typos and crashes.

## 10. The two tests

| Part | Common path easy, ergonomic, fast? | Adjusting straightforward when it doesn't fit? |
|---|---|---|
| Tree of values | Yes: ordinary call and array syntax | Yes: helpers are functions returning `Node`; reuse a tree for speed |
| Picks | Yes: one union line, one `if` per choice | Yes: payload values, plain strings, or `clicked` beside the widget |
| Places | Yes: `@volume` and done | Yes: any place works; compare afterward to react |
| IDs | Yes: usually none beyond the label | Yes: `id=` when a label changes |
| Sizing | Yes: `'fit'` default, `'grow'`, a number | Yes: `part`, `grow(low high)`, `fit(high)` |
| Navigation | Yes: free with no code | Partly: `controls=` and `pick` are easy; there's no per-item nav override yet |
| Rendering | Yes: `ui` draws | Yes: `layout` gives plain commands; reserve a `box` for custom drawing |
| Theme | Yes: default is built in | Yes: pass a record; `themed` for a subtree |
| Strict lane | Not a v1 path | **Partly:** needs a later fixed-pool builder over the same core |

## 11. Decisions for David

Names only; all reversible until callers depend on them.

1. **Widget names:** `column row box grid scroll floating tooltip modal spacer text image button checkbox slider choice text_field progress`. **Recommend yes.** `text` and `image` overload today's `text(s pos)` and `image(w h)`, told apart by arguments.
2. **`ui` for trees with picks and `show` for trees without.** **Recommend yes.** The alternative is `ui(...);` everywhere plus fixing G5.
3. **`pick=` for what comes back, `id=` for identity.** **Recommend yes.** They are different jobs, and one word for both made the debug overlay fail to type-check.
4. **`pad`, not `padding`.** **Recommend `pad`:** it's used constantly and pairs with `gap`.
5. **Sizes:** `'fit'`, `'grow'`, a number, `part(0.5)`, `grow(low= high=)`, `fit(high=)`. **Recommend yes.** The alternative `percent(50)` reads well but invites `0.5` mistakes.
6. **One nine-point `align`** rather than separate x and y. **Recommend yes.** It is one word and one union, reused for `anchor`.
7. **`back='resume'` on `ui`,** replacing `ui_back()`. **Recommend yes.**

## 12. What I'm least sure about

- **`clicked(id)` beside the pick.** Two ways to read a button may be one too many. I kept it because it answers the "next to the widget" need without closures. If you dislike the two-line form, (b1) is the fallback, at the cost of `$capture`.
- **Labels as identity.** The occurrence counter is simple, but reordering a list with duplicate labels moves focus to a neighbor for that frame.
- **Untested behavior:** text wrapping, scroll, floating placement and `grid` compile but don't work in the stub. Their cost is estimated, and the design carries the most risk there.
- **Spatial navigation** has only been run on a column. Dense or uneven grids may need tuning.
- **Build cost is 41% of the frame.** I haven't looked at what dominates it. Interpolated strings are the likely cause, so a screen heavy with text may scale worse than this one.
