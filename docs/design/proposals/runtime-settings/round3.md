# Runtime-chosen settings, round 3

Round 2 stands. No rule changes. Two programs scored under 5 for a reason a different program can remove. The rest stay under 5 because the rule is what the line shows, and changing the rule would bring back a must-fix or add a spelling.

`programs-r3/` replaces two files. Every other program is the one in `programs-r2/`.

- **02.** The `$runtime_checks` block is what makes `probe` compile. `probe` does not set the tag itself, so the block is the checked call of the unproved index, and `sum_of` is still called with the tag and without it. A plain call of `probe` is still the error in round 2. This file does not contain one, because then it would not compile.
- **13.** `user_stamp` is called on a fold (`2026-11-01T01:30`) and on a gap (`2026-03-08T02:30`), so both `$time.fold` and `$time.gap` are the policy of a call that needs them.

**03 stays at 4.** Past `$program.max_memory` the process ends, which is the allocation policy. A check that refuses first needs the asset size and `256MiB` as the same type. `256MiB` is a size, and this design does not add a conversion. Turning on `$explicit_allocation_failure` would change every allocation in the module to `T | OutOfMemory`.

Grades: `dogfood-round3.md`.
