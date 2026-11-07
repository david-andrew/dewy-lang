# Cold-read name picks, rounds 4–5 (2026-11-07)

Three readers with no context guessed each name. Use the picks; "ask" items go to the owner as questions with this data.

| Was | Pick | Note |
|---|---|---|
| `Information` (dimension) | `DataSize` | all three read `Information` as a log or info message |
| `ShapeError` | `ValidationError` | "shape" reads as array dimensions, which clashes with tensor shapes |
| `shape=@f` on types | ask: `check=@melody_problem` (rec, keeps the message) vs `valid_if=@is_melody` (read best, but implies a bool) | `shape=` read poorly |
| `capture` (rebinding) | `listen_for_press` | `capture` read as screenshot or closure, and clashes with `$capture` |
| `field` (UI input) | `input_field` | `field` read as a record field |
| `Playing` | `PlayingSound` | read as a state |
| `Selectable<R>` | `Waitable<R>` | read as a UI selectable |
| `Sort` (table) | `TableSort` | `SortOrder` reads as direction only |
| `$program.time_rules` | `$program.time_zone_rules` | |
| `$time.no_unchecked_today` | `$time.only_strict_today` (if the prefix stays `strict_`) | |
| `shielded(d @f)` | `protect_from_cancel(d @f)` | |
| `$count_local_asserts_as_panics` | `$prove_local_asserts` | |
| `to_file_name` | `sanitize_file_name` | |
| `$discardable_result` | ok (`$may_ignore_result` read the same) | |
| prefix for "same call, failures as values" | ask: `checked_` everywhere (rec; Rust precedent; `checked_add` 3/3) vs `strict_` (`strict_add` read as "fails on overflow"); `strict_today` was the owner's earlier pick, and all three spellings read about equally for `today` | |
| `x or_throw<E>` | ask: all three readers read it as "throw an `E`", not "forward only `E`" | |

Read fine: `$parallel.max_cores`, `$parallel.off`, `available_cores`, `DEWY_MAX_CORES`, `Task`, `.running`, `ticker`, `partition_failures`, `iterable<T>`, `$allow_unproven_narrowing`, `$prove_no_counter_overflow`, `FileName`, `base.confine`, `secure_token`, `secure_random`, `random(range)`, `rng`, `stdin_lines`, `is_close`, `allow_nonfinite=`, `find_last`, `set_permissions`, `start_process`, `Weekday` names, `iso_weekday`, `d.next`, `nth_weekday_of_month`, `next_anniversary`, `t.floor`, `$time.no_assumed_zone`, `$time.no_dropped_zone`, `$program.time_zone`, `$program.time_zone_source`, `.start`/`.end`/`.includes_end`, `Instant<width=64>`, `DatePattern`, `MB`/`MiB`, the `fmt` word patterns, `rebind`, `conflict=`, `controls_editor`, `input_hint`, `changed`, `committed`, `valid`, `label`, `style=`, `value_text=`, `scale='log'`, `plot`, `tip=`, `shortcut=`, `animate=`, `panel`, `collapsible`, `layers`, `row(wrap=true)`, `drag=`, `ui(player=)`.
