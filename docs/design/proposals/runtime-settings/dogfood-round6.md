# Dogfood: runtime-chosen settings, round 6

Rules: `round6.md`. This file regrades the programs those three rules touch. Every other score is the one in `dogfood-round5.md`. A score under 5 names the line.

## Grades

| Program | O | D | C | S | P | Lines under 5 |
|---|---|---|---|---|---|---|
| 04 request_memory | 4 | 4 | 4 | 5 | 5 | O: `page_of(8_000_000)` (`programs-r5/04_request_memory.dewy:20`). 8_000_000 `int64`s reserve 64_028_672 bytes, which is over 32MiB. The line does not say so. D: `page_of(500_000)` (`:26`). That array reserves 4_063_232 bytes and, returned, keeps those bytes on the 6MiB budget. It does not keep a 4MiB slab. The line shows the failure, not the size class. C: `$explicit_allocation_failure` (`:1`). The three cases are the exceed (`:21`), the returned block (`:30`), and the growth (`:41`). |
| 11 fast_math | 4 | 4 | 5 | 4 | 5 | O: `lib.ieee_add(1e16 1.0 -1e16)` (`programs-r6/11_fast_math.dewy:16`). The `$fast_math` on `:13` does not recompile this concrete function. D and S: `lib.add3(...)` (`:14`). The instance is compiled under the caller's flag, and the warning names `add3` and `$fast_math = false`. The warning is not in the source, and missing it keeps the fast body. `lib.pinned` (`:15`) is that pin (`11_lib.dewy:11`). `lib.fast_add` (`:11`) is the library's own fast function. Plain `add3(1e16 1.0 -1e16)` is 0. The fast bodies may be 1. |
| R3 zone_server | 4 | 4 | 5 | 5 | 4 | O: `body="ping"` (`programs-r6/R3_zone_server.dewy:35`). The copies reserve a small size class on the 32MiB budget, not a slab. D: `printl"audit {r.user} {today}"` (`:16`). The zone is the one captured at `@audit(r)` (`:22`), which is under `r.zone`. `utc.run` sets UTC (`R3_lib.dewy:2`) and does not retarget that handle. `utc.run(note)` (`:29`) creates `note` in `serve`, where no zone is set, so `note`'s `today` is not UTC either. P: `let pages` (`:28`). Those arrays stay charged at their size class on both budgets, and nothing in the file reads that number. |

## Floor

4. The 3s from round 5's regrade were a generic taking `$fast_math` with no warning, and a library zone changing a callback's `today`. `lib.add3` now warns, `pinned` writes `$fast_math = false`, and `@audit(r)` keeps the zone it was created under. The remaining 4s are the ones `summary-final.md` lists. No new spellings.
