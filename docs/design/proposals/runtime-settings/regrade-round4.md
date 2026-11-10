# Independent regrade: runtime-chosen settings, round 4

Read `round4.md`, `programs-r4/` plus unchanged files from `programs-r3/` and `programs-r2/`, and my `regrade-round3.md`. Did not read `dogfood-round4.md`. Nothing compiled.

Floor: **2** (program 11, completeness). Everything else is 3 or above.

## 1. N1 to N7

| # | Verdict | Where |
|---|---|---|
| N1 local-valued cap | Resolved in text, by a rule I would change (section 4). `10_config_cores.dewy` is now the plain form. The simpler fix the author did not weigh is a block: `{ $program.max_cores = cores; run() }` already works under round 2 with no new evaluation rule. |
| N2 header ceiling | Resolved, but it opens N9 below. |
| N3 cross-module literal | Resolved for a direct call (`13_app_bad.dewy:6`); transitive and function-value cases still open (N11). |
| N4 growth | Resolved ("Growth"), at a cost: a block carries one owner word per distinct growth budget, location unstated (N12). |
| N5 costs | Resolved: shared allocator, owner word, what the cap counts, retainers. One loose end: "each owner pointer on a block" is a retainer, yet "no second atomic per allocation"; works only if release-to-zero is detected on the same atomic as `live`. Say so. |
| N6 table vs parameter | Resolved: the warning names the setting and the parameter. |
| N7 noisy warnings | Mostly resolved; but the one warning David's rule requires was dropped (N10). |

## 2. New problems

**Must-fix**

- **N9. The entry header cannot protect the machine, and one spelling has two meanings.** Round 4: file-level `$program.max_cores = 2` is a default that any function setting a cap replaces; the header is "not on the chain." A library function that sets 8 and is called from a `laptop` that sets nothing runs at 8 (`01_laptop_server.dewy:1-7` plus any library call like `R1_indexer.index`). The same line inside `main` is a cap and does bound libraries (`08_app`). Adding or deleting `$program.max_cores = 2` inside `laptop` changes whether a dependency can exceed it. A user who writes `$program.max_cores = 2` at the top of the program to keep a laptop usable is told a dependency may use 8. Fix: a setting in a module other than the entry module can only narrow (minimum with the header), while functions in the entry file replace the default. Then David's header-default plus override idiom works and a library cannot widen.
- **N10. The cost warning for `$program.max_memory` was dropped, against David's standing rule** (a feature that costs performance warns). "A scope that sets a cap is the same" as per-use noise is true of the chain walk, but the process-wide cost (every Dewy allocation takes the checking allocator, 8 bytes per live block, in every module) is not per use: it is one fact per build. Warn once per build at the first reachable `$program.max_memory`: "this cap makes every Dewy heap allocation in the process checked and adds one word per block (N sites)". Also consider removing the cost instead: an owner per page or arena (side table by address) means blocks allocated outside any cap pay nothing.
- **N13. `$fast_math` on a library call does nothing, so program 11 shows nothing.** `programs-r4/11_fast_math.dewy:15-16` (`{ $fast_math; lib.dot(xs ys) }`) and `:7-8` (`apply`) compile the same code as the plain call: another module is not recompiled and a function parameter is not retargeted. Output is the same three numbers with warnings. A user cannot get a fast-math `dot` from a library without copying its source. Say what happens for a generic or inlined library function (instantiated in the caller's module, so does it take the caller's setting?), and give the one real way to get fast math from a library (the library offers a `$fast_math` entry, or generics instantiate under the caller).

**Should-fix**

- **N11. Cross-module literal check beyond a direct call.** `lib.stamp` calling `lib.inner` with a zone-less `zoned"..."`, or `@lib.stamp` called through a parameter under a runtime zone: not stated. Also a library patch that adds such a literal breaks every runtime-zone caller, at the caller's line.
- **N12. Growth owners.** "8 per extra growth owner": where stored, bounded by what.
- **N14. The "call above the setting warns" rule is a heuristic.** `09_nested_caps.dewy:15-17` and `10_config_cores.dewy:5-7` rely on "the lets the value reads and the guard do not warn". A debug `printl"cores={cores}"` above the cap, or a guard that logs (`printl(... file=stderr)` in the `if`, as these programs do) is a call above the setting. State precisely what is exempt.
- **N15. `grow` in `04_request_memory.dewy:25-29` does not compile as written under the design's own rules:** `cache.extend(extra)` mutates a parameter and drops its `OutOfMemory` (the module has `$explicit_allocation_failure`), so `grow` cannot return `int` as the caller's `n is? OutOfMemory` expects. Also `"x" * (40 * 1024 * 1024)` is hand arithmetic next to `$program.max_memory = 64MiB`; there is no stated size-to-int step, which is the same gap the author cites to keep 03 at 4.
- **N16. `02` lost the point.** `sum_of` is now only called plain, so "the same code with and without `$runtime_checks`" (the brief) is gone.
- `available_memory` should go through its cold read; two programs (03, 04) want it.

## 3. Regrade

| Program | O | D | C | S | P | Lines under 5 |
|---|---|---|---|---|---|---|
| 01 laptop_server (r4) | 4 | 4 | 5 | 3 | 4 | O/D: `laptop = () => run()` (`:5`) sets nothing and gets 2 from the header while `server` writes its cap; the idiom David wrote had both functions set tags. S: N9. P: no `--cores N` without 10. |
| 02 checks_harness (r4) | 4 | 4 | 5 | 5 | 3 | P: N16, and no plain `probe`. O: the block tag exists only to make `probe` legal. |
| 03 game_profile (r4) | 5 | 4 | 4 | 3 | 4 | S: `max_memory = 256MiB` (`:5`) ends the process; `available_memory` not available. C: two profile functions repeat a body. D: cap per function visible only by reading both. |
| 04 request_memory (r4) | 3 | 3 | 3 | 4 | 4 | O/D/C: 40 lines; `"x" * (40 * 1024 * 1024)` (`:22`); N15 (`:25-29`). S: the program tests the right cases (cap fails, page stays charged, growth) but one does not compile under the rules. |
| 05 user_zone (r2) | 4 | 4 | 5 | 4 | 4 | `$time.zone = user.zone` reads like assignment; host zone if not tagged. No parallel handlers. Unchanged. |
| 06 bench_cores (r4) | 5 | 4 | 4 | 5 | 4 | D/C: `{ $program.max_cores = 1; work() }` (`:9-11`). P: pool start cost sits in the first block, and a one-million `i` loop is light for timing. |
| 07 task_outlives (r2) | 4 | 4 | 5 | 4 | 4 | `app.spawn(@child(app done));` discards a handle; no memory charge shown. Unchanged. |
| 08 app + library (r2) | 5 | 4 | 4 | 4 | 4 | D: `$program.max_cores = 8` in library `main` is never installed. P: no library function with a cap; R1 has it. |
| 09 nested_caps (r4) | 4 | 4 | 4 | 4 | 4 | O: `wider` says 16, runs at 8 (`:3-4`). C: `from_file` is 8 lines for a number (`:8-15`). N14. |
| 10 config_cores (r4) | 5 | 4 | 4 | 5 | 5 | D: the tag starts at its line, not the function, and nothing at the line says so. C: the `if cores <? 1 {... exit(2)}` exists only to prove `>= 1` (Python: `max(1, n)`). |
| 11 fast_math (r4) | 3 | 3 | 4 | 3 | 2 | N13 (`:7-8`, `:15-16`): both fast_math uses are no-ops with warnings. S: a tag that silently does not apply is only a warning. |
| 12 wasm_entry (r2) | 4 | 4 | 5 | 4 | 3 | `max_cores = 4` runs at 1 with a warning; nothing else about the target. |
| 13 app + lib (r4) | 4 | 4 | 4 | 4 | 4 | D: the failure for `lib.stamp()` under a runtime zone appears only at the call (`13_app_bad.dewy:6`), never in the library. C: `fold='later' gap='next'` stringly. P: N11. |
| 14 replay (r2) | 5 | 4 | 5 | 5 | 4 | D: nothing at `$parallel.off` says waits yield. P: no busy-wait. |
| R1 indexer + app (r4) | 4 | 4 | 5 | 4 | 4 | O: `index` says 8, runs at 2 (`R1_indexer:3`). P: a table called through the parameter is shown, a setting that fails is not. |
| R2 flag (r4) | 4 | 5 | 5 | 5 | 4 | P: no path for "check only when argv says debug"; `$runtime_checks` on the function is on in every build. |
| R3 zone_server (r2) | 4 | 3 | 4 | 4 | 3 | D: `audit` reads `{today}` in the zone `handle` set. P: no library literal under a runtime zone (N11), no returned charged block under 512MiB shown. |

## 4. The two questions

**(1) Start point by class instead of by right-hand side.** Yes: simpler and more consistent, and the right-hand-side rule has concrete costs. Today `let cores = 4` then `$program.max_cores = cores` and `$program.max_cores = 4` cover different statements: moving a literal into a `let` silently shrinks the frame, and the compensating warning ("this cap starts here ... `run()` above it is not under the cap") needs its own exemption list (N14). By class: runtime caps, policies and schedules start at their line to the end of the scope; code settings are text properties, so a bare `$fast_math` or `$runtime_checks` covers the whole scope (an index above the tag still needs checks). The exception is a code setting given a value (`$fast_math = flag`), which has to start at its line anyway, so the cleanest statement is "a setting given a value starts at its line; a bare setting covers the scope".

Reasons against, all small: (a) it changes LANGUAGE.md's sentence for literal-valued settings at the bottom of a scope (rare; the common placement is the top, where the two rules agree); (b) parameter-binding copies are no longer under the callee's cap, so the caller pays; round 4 already treats them that way for local-valued settings; (c) a tag written low by habit leaves the top uncovered, so keep the single "a call or allocation above this setting is not under it" warning for every valued setting.

The block form also stays legal and needs no rule at all; I would also have the diagnostic for a local defined below suggest it.

**(2) Warn for the memory cap.** Yes, and the author's reason for dropping it does not hold. The "fires on every use" argument applies to the chain walk, which is the call's own cost. The process-wide owner word and checking allocator is one fact per build, independent of how often the cap is used, so a single warning at the first reachable `$program.max_memory` (with a site count) is not noise and is exactly David's rule. A core cap or task cap should not warn (permit take only on `spawn`/`parallel`). If the cost can be removed rather than warned (owner per page or arena), say that is the alternative.

## 5. Are the remaining 4s inherent?

Partly. Inherent to dynamic scoping: `run()` not showing its cap, ambient zone (05, R3), and the line that says 16 while running at 8 (09, R1) as long as the rule is the minimum. Not inherent:
- 01's O/D and S 3: they come from the header-default choice (N9), not from the feature.
- 03's S: the process ending at the cap; `available_memory` is already proposed, and `$explicit_allocation_failure` exists.
- 11: all of it; a design choice that code settings stop at the module boundary.
- 04's C and 13's C: no size-to-int step, and stringly `fold='later'`.
- 13's D: the library never shows the error the caller will get.
