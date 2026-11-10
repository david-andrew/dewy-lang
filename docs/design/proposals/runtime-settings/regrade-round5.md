# Independent regrade: runtime-chosen settings, round 5

Read `round5.md`, `summary.md`, `programs-r5/`, and the earlier regrades. Did not read `dogfood-round5.md`. Nothing compiled. Unchanged programs (03, 05, 07, 08, 12, 14, R1, R2, R3) are graded from `programs-r4/` and `programs-r2/` where the round-5 rules affect them.

Floor: **3**. Program 11 (safety) and R3 (discoverable) carry the two new must-fixes below. With those closed I would give 4.

## 1. Earlier must-fixes

| Item | Verdict |
|---|---|
| N9 header is only a default, a library can exceed it | Resolved. A setting outside the entry file only narrows (`round5.md`, "A library cannot raise the program"). `01_laptop_server.dewy` now runs `lib.wide` at 2 from `laptop` and `main`, at 8 only from `server`, which is in the entry file and replaces the header. Deleting the line inside `laptop` no longer lets the library past the header. |
| N10 memory-cap warning | Resolved: one warning per build with the site count; per-page owner so uncapped allocations stay on the fast path. The costs of the per-page scheme are N17 below. |
| N13 `$fast_math` across modules | Resolved for a concrete function (library writes `$fast_math` itself, `lib.fast_add`) and for a generic (`lib.add3`, instance compiled in the caller). `11_fast_math.dewy` now has an output that differs. A hole in the generic half is N18. |
| By-class start rule | Resolved. One rule for caps, ceilings, schedules and policies; bare code settings cover the scope; the block `{ $program.max_cores = cores; run() }` is the quiet form (`10_config_cores.dewy:7-11`, `09_nested_caps.dewy:12`). `$fast_math = flag` with a non-constant flag starts at its line, the one exception, stated. |

## 2. New must-fixes

- **N17. The per-page owner makes the cap's unit and footprint undefined.** "A page is charged to only one innermost budget" and "adds the page's bytes to `live`" mean a capped scope takes at least one page per size class it touches, and per worker thread if tasks allocate for it. Consequences the round does not state: (a) a server with thousands of small handlers each under its own `$program.max_memory` pins pages per handler (no sharing of a size-class page across caps); (b) a returned small value, a 24-byte string handed back to an uncapped or outer caller, keeps its whole page charged to the inner and every outer budget until freed (`04_request_memory.dewy` block 2 shows the effect only for 4MiB values, where a block is its own mapping); (c) the cap then means "pages", not bytes the program allocated, so 32MiB gives an unstated smaller amount. The warning text says "each mapped page records its budget" but gives no page size, no minimum charge, and no worst case. State the page size and size classes, the minimum footprint per capped scope, and give the cost in the warning. This is the new measurement the memory design needs, since it is the whole cost of N10's fix.
- **N18. A generic library function silently takes the caller's `$fast_math`, which defeats the reason concrete functions are protected.** Round 5 refuses to recompile `lib.ieee_add` because "the library may rely on strict IEEE", then compiles `lib.add3` generically under the caller's flag (`11_fast_math.dewy:16-19`) with no warning. A generic compensated sum, or a generic sort that checks for NaN, is the same code the author wanted to protect, and is broken the same way. Either warn at the call ("this generic instance is compiled under `$fast_math`; `lib.add3` may rely on IEEE") and say the library pins it with `$fast_math = false` (which LANGUAGE.md already spells), or limit the generic rule to functions the library marks.
- **N19. A function that sets `$time.zone` changes the zone its callbacks see.** Policy is "innermost frame wins ... including a library function". A library `report = (rows handler) => { $time.zone = zone"UTC"; ... handler(row) }` runs the app's `handler` under UTC, and the handler's `{today}` is in UTC with no sign at the handler or the call (R3's `audit` reads `{today}` in a zone chosen two functions away; add a library between and it changes). For caps this is harmless (only narrows), for zone, gap and fold it is a semantic change to code the library never saw. Decide: a parameter call restores the frames captured where the function value was created, or a library function that sets policy and calls a parameter warns once.

## 3. Regrade of changed and affected programs

| Program | O | D | C | S | P | Lines under 5 |
|---|---|---|---|---|---|---|
| 01 laptop_server | 5 | 4 | 5 | 5 | 4 | D: `run()` (`:8`) and `lib.wide()` (`:9`): the cap arrives by extent; and `laptop` repeats the header's 2. P: no `--cores N` without 10. |
| 02 checks_harness | 5 | 5 | 5 | 5 | 4 | P: plain `probe` is the compile error and cannot be in the file; the two blocks are the only legal calls. Inherent. |
| 03 game_profile (r4) | 5 | 4 | 4 | 3 | 4 | S: `max_memory = 256MiB` (`:5`) ends the process. D/C: two repeated profile bodies. |
| 04 request_memory | 4 | 4 | 3 | 4 | 4 | C: 40 lines for three cases. O: the reader must compute 2^23 reservations (500_000 `int64`s reserve 4MiB, 8_000_000 reserve 64MiB) to see why a line passes or fails; N17 hides the real accounting (pages). |
| 05 user_zone | 4 | 4 | 5 | 4 | 4 | `$time.zone = user.zone` reads like assignment; unchanged. |
| 06 bench_cores | 5 | 4 | 4 | 5 | 4 | D/C: three bracketed blocks (`:9-11`). P: a million trivial items does not time a cap well. |
| 07 task_outlives | 4 | 4 | 5 | 4 | 4 | Unchanged (`app.spawn(@child(app done));` discards a handle). |
| 08 app + library | 5 | 4 | 4 | 5 | 4 | Library `main` cap never installed here. Now fine for safety: a library cap only narrows. |
| 09 nested_caps | 4 | 4 | 4 | 4 | 4 | O: `wider` says 16, runs at 8 (`:3-4`). C: `from_file` needs the guard plus a block. |
| 10 config_cores | 5 | 4 | 4 | 5 | 5 | D: the block (`:7-11`) is the only quiet form; the flat form warns. C: the `if cores <? 1 {...exit(2)}` guard exists to prove `>= 1`. |
| 11 fast_math | 4 | 4 | 5 | 3 | 5 | S: N18 (`:16-19`). D: nothing in `11_lib.dewy` says `lib.add3` will be recompiled under a caller's flag. |
| 12 wasm_entry (r2) | 4 | 4 | 5 | 4 | 3 | Unchanged: a cap above 1 warns and runs at 1; nothing else about the target. |
| 13 app + lib | 4 | 4 | 4 | 4 | 5 | D: the transitive literal in `13_lib.dewy:1-3` fails only at `13_app_bad.dewy:7`. C: `fold='later' gap='next'`. The flat form needs a call (`zone(...)`) above the setting, so it warns (see section 5). |
| 14 replay (r2) | 5 | 4 | 5 | 5 | 4 | Unchanged. |
| R1 indexer + app (r4) | 4 | 4 | 5 | 5 | 4 | O: `index` says 8, runs at 2. Library narrowing now consistent with the header rule. |
| R2 flag (r4) | 4 | 5 | 5 | 5 | 4 | P: no path for "check only when argv says debug". Inherent. |
| R3 zone_server (r2) | 4 | 3 | 4 | 3 | 3 | D/S: N19, and `handle`'s 32MiB under N17 with returned `pages`. P: no library between `serve` and `audit` showing the zone through a callback. |

## 4. The four classes of 4 in summary.md

- **`run()` does not repeat the cap (01), `today` does not take the zone (05), a handler table hides which function runs (R1).** Inherent to dynamic scope. Accept.
- **`$runtime_checks = debug` is an error (R2).** Inherent to proofs: one build cannot check an unproved index only sometimes. Accept. The error message offers the two fixes.
- **A looser cap says 8 or 16 and runs at the tighter limit (01_lib, 09).** A deliberate trade I accept: the alternative (a library raising the program) was N9, and the warning names both numbers. The line costs a point because it is a lie that the compiler tells you about.
- **`lib.ieee_add` under `$fast_math` stays IEEE (11).** A deliberate trade I accept for concrete functions, but not as the rule stands for generics (N18): that half contradicts its reason.
- **Past `$program.max_memory` the process ends (03).** A deliberate trade I accept for now, because `available_memory` is a new member and needs a cold read and David's approval. It is not inherent: `$explicit_allocation_failure` and a read like `available_cores` exist or are proposed, so this stays a 4 until that member is decided.

## 5. Not must-fix (noted)

- The by-class warning "a call or allocation above this setting" fires on the flat form of the plain program, because the local is made by a call (`let z = zone(...) or_throw` above `$time.zone = z`, `13_app_bad.dewy:4-5`). The block is the quiet form, so this is a style push, not an error; a data-dependence exemption would be more precise but the author rejected it as fuzzy.
- `$explicit_allocation_failure` is written before `from units import MiB` in `04_request_memory.dewy:1-3`, while the entry-header rule says settings follow the imports. Metadata, not a frame; cosmetic.
