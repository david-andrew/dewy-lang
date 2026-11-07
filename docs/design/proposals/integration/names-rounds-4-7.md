# Names: cold-read results (rounds 6–7) and what is final

Every name in `open-items.md` has now been read cold by three readers with no context. Rounds 1–5 are in `docs/design/proposals/*/names*.md` and the earlier name-pick tables, and rounds 6–7 are in `~/dev/tmp/naming-1107/guesses6-*.md` and `guesses7-*.md` (keys `key6.tsv`, `key7.tsv`). One renamed method, `.discard_pending`, hasn't been tested.

## Round 7 (final): picks

| Candidates | Result | Final |
|---|---|---|
| `listen_for_interrupt` / `catch_ctrl_c` | 4/3/3 against 5/4/3 | **`catch_ctrl_c`** |
| `ProgramTasks` / `BackgroundTasks` | 3/2/3 against 4/3/4 | **`BackgroundTasks`** |
| `task.failure` / `task.error` | `error` read slightly better | **`task.error`** |
| `T.from_label` / `T.parse_human` | `from_label` read as enum-variant lookup; `parse_human` 3/3/4 | **`T.parse_human`** (protocol hook `__parse_human__`) |
| `input_field(problem=)` / `error=` | | **`error=`** |
| `q.number_in(u)` / `q.value_in(u)` | | **`q.value_in(u)`** |
| `q.as_unit(u)` / `q.to(u)` | `to` 5/4/5 | **`q.to(u)`** |
| `rounding='nearest_up'` / `'half_up'` | `half_up` read both as "up" and "away from zero" | **`nearest_*`** |
| `set_current_dir` / `change_dir` | | **`set_current_dir`** |
| `p.follow_lines` / `p.watch_lines` | | **`p.follow_lines`** |
| `fmt'iso_basic'` / `fmt'iso_compact'` | | **`iso_basic`** |
| `Interrupted`, `days_of_week` (5/4/5), `start_process` keywords, `ExitStatus`, `DimensionMismatch`, `Quantity(text)`, `Unit(text)`, `load_sound`, `__read__`, `Roll(count= …)`, `z.next`, `tick.next` | Read correctly | **Kept** |
| `SubPath` | 3/3/3 | **Kept** (acceptable) |

## Round 7: weak or failed, flagged in the items

| Name | How it was read | Handling |
|---|---|---|
| `listener.clear` | All three: "remove every registered handler" | Renamed **`.discard_pending`**. **Untested**; flagged in D4 Q4 |
| `$no_next_value`, `$no_successor` | Both: "may take a next value without proof" (less safe) | Kept `$no_next_value`, the better of the two (confidence 3/2/2 against 2/2/2). A library-author tag; flagged weak in D31 |
| `CountHoleTemplate`, `CountedPattern` | Both: a counting pattern or numbered blanks | Kept `CountHoleTemplate` (library authors only); flagged weak in D11 Q6 |
| `input.pressed_at` | 2 of 3 correct (one: "whether pressed at a given time") | Kept; flagged in D11 Q6 |
| `sound.position_at` | 2 of 3 correct (one: "places a sound in space") | Kept; flagged in D11 Q6 |
| `strict_in_zone` | 2 of 3: "strictly inside a zone" | The prefix is an owner question again (D31 Q6), with the data from rounds 5–7 |

## Round 6: decisions still in force

| Was | Final | Why |
|---|---|---|
| `weekdays` | `days_of_week` | All three read `weekdays` as Monday to Friday |
| `RelativePath` | `SubPath` | Missed "can't escape its folder" |
| `r.every(step)` | `r.step(step)` | Read as a schedule |
| `refuse` | `forbid` | Weak |
| `checked_` prefix | Not recommended | `checked_today` read as "checked today" (2/1/2). See D31 Q6 |
| `$dense`, `$continuous` | `$no_next_value` | Read as memory layout |
| `p.follow` | `p.follow_lines` | One reader: following a symlink |
| `main = (app:Tasks)` | `main = (app:BackgroundTasks)` | No reader guessed the program lifetime |
| `checkbox(checked=)` | Kept, with a hint | Two of three read it as a two-way binding |

## Still untested
- `ctrl_c.discard_pending`: forget Ctrl-C presses that are waiting to be handled. Candidates to read beside it: `.drop_pending`, `.forget_presses`.
