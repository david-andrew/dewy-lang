# Guessability tests (2026-11-07)

## Test 1: guess the name from a description (30 functions)

Three readers were told "snake_case" and three were told "Julia's style". Exact matches:

| Style | Readers' scores |
|---|---|
| Julia | 26, 27, 27 / 30 |
| snake_case | 20, 20, 23 / 30 |

- **Confounded.** The Julia brief said "where Julia already has a function, use Julia's name", and the Julia key uses Julia's real names (`lastdayofmonth`, `haskey`, `uppercasefirst`). Readers were recalling Julia, not applying a style.
- **Not one miss in any of the six readers was a separator mistake.** Every snake_case miss was a different word, the one familiar from Python or Rust:
  - `capitalize` for `uppercase_first` (all three);
  - `contains_key` for `has_key`;
  - `rfind` for `find_last`;
  - `lines` for `each_line`;
  - `strip_prefix` for `remove_prefix`;
  - `next_up` for `next_float`;
  - `end_of_month` for `last_day_of_month`;
  - `weekdays` for `days_of_week`.
- **Lesson:** guessability depends far more on choosing the familiar word than on the separator.

## Test 2: spell Dewy-only names in Julia's style (24 names, words given)

Three readers were given the words of names no language has (e.g. "nth weekday of month") and spelled each in Julia's style.

- **All three agreed on only 12 of 24.** Pairwise agreement was 22, 12 and 14 of 24.
- Two readers joined almost everything (`nthweekdayofmonth`, `sanitizefilename`, `setcurrentdir`). The third underscored about half (`nth_weekday_of_month`, `secure_random_bytes`, `set_current_dir`), joined the rest (`daysofweek`, `startprocess`), and split one name internally (`catch_ctrlc`).
- Under snake_case these spellings are mechanical, so agreement is 24 of 24 by construction.
- **Lesson:** "join when readable" isn't predictable for new names. Half the time a programmer would have to look the spelling up or rely on the fix-it.
