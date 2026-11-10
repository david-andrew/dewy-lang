# Independent regrade: runtime-chosen settings, rounds 2 and 3

Read: `round2.md`, `round3.md`, `programs-r2/`, `programs-r3/`, my `regrade-round1.md`, `review-round1.md`, and (for the decision text) `decisions.md` batch 5. Written before opening `dogfood-round2.md` / the grades in `dogfood-round3.md` beyond the final comparison section. Nothing was compiled.

Floor: **3**. See "New problems" N1 and N3 (undefined, common) and the grades for 04, 10, R3.

## 1. Are the round-1 must-fixes resolved?

| # | Source | Verdict | Where / what is left |
|---|---|---|---|
| Mine 1 | Body-level tag covers only next statement | Resolved | round2 "Where a setting is written": a tag covers its whole scope, including statements above it; blocks for two counts (`programs-r2/06:6-8`). Creates N1. |
| Mine 2 | Inner-above-outer: compile error vs runtime refusal | Resolved | Minimum on the chain everywhere (round2 "Caps"); `R1_app.dewy:7-10` now runs at 2 with a warning. Side effect N2. |
| Mine 3 | Memory accounting edges | Mostly resolved | Reserved block, chain walk, owner pointer, return/free, shared parallel budget all stated. Left: growth of a block owned by another chain (N4); refcount cost (N5). |
| Mine 4 | Outliving tasks, transitivity | Resolved | "A task captures the chain by reference", grandchild case stated; `07_task_outlives.dewy` now has `search -> child -> work`. |
| Mine 5 | `$runtime_checks = flag` illegal in main use | Resolved as a rule | Error text given. The program that showed it (R2) was replaced by a `$fast_math` branch, so no file shows the error or what a user does instead. |
| Mine 6 | Dynamic cap unvalidated | Resolved in text | `cores >= 1` obligation; refined param `int<1 <=? cores>` (`10_config_cores.dewy:1`). Spelling `int<1 <=? cores>` is the guard-arm form from LANGUAGE.md 5089 reused on a parameter; I could not confirm it is legal there. Local-value case is N1. |
| Mine 7 | Function values / variants | Resolved for a finite local table | "Function values" section; R1 table works. Open-set parameter behaves differently (N6). |
| Review M1 | Attachment contradictions | Resolved by withdrawal | Round 1 attachment dropped; module metadata separate. Cost: David's brief picture (tag above function) no longer compiles; round2 says so openly. His decision text (batch 5) only says "a function ... that sets them", so it is compatible. |
| Review M2 | Bundles / signature policies | Resolved | `$default_row` stays in the bundle; metadata installed on import. |
| Review M3 | chunk size / affinity | Resolved | Separate classes; `available_cores` defined. |
| Review M4 | Shared budget identity | Resolved | Budget objects, atomic reserve with rollback, permit per pool. |
| Review M5 | Policy result type | Resolved for same-module; N3 for cross-module | `zoned"..."` under runtime zone is a compile error "including through callers in the same module" only. |
| Review M6 | Costs | Partly | O(D) and 8-byte owner stated; N5 and the process-wide cost of a shared allocator are not. |
| Review S1-S5 | Specialization key, tables, argument order, cap validation, cooperative replay | Resolved | `14_replay.dewy:6-17` now has a producer and consumer. |

## 2. New problems from the revision

**Must-fix**

- **N1. A cap value that is a local, not a parameter.** Tags cover the whole scope and are evaluated at scope entry with only parameters in scope (round2 "Order: ... the callee's setting expressions (parameters are in scope)"). The most common program therefore does not work:

  ```dewy
  main = () => {
      let cores = to_int((p"cores.txt".read_text or_throw).trim) or_throw
      $program.max_cores = cores     // covers the let above it, and cores is not yet defined
      run()
  }
  ```
  The doc never says this is an error, never gives its message, and the fix (wrap the rest in a block, or move it to a parameter of a helper as in `10_config_cores.dewy`) is nowhere shown. Program 10 only works because it was rewritten to take `cores` as a parameter. State the rule and the diagnostic, or allow a tag after the last `let` it uses to begin the extent at that point (a rule change).
- **N3. `zoned"..."` literal in a library called under a runtime zone.** The error is only for same-module callers. `literal_stamp` in a library, called from an app inside `$time.zone = z` with `z` read at run time, has no stated outcome: compile error in the library (impossible, it was fine alone), run-time parse with no failure type (breaks "one result type"), or a trap. Define it, probably as an error at the cross-module call.

**Should-fix**

- **N2. A file-level cap is a ceiling, never a default.** `$program.max_cores = 2` at the top of the entry file and `server = () => { $program.max_cores = 8 ...}` runs `server` at 2 with a warning. "Defaults in the header, overrides in functions" is the first thing people write. Say so in the idiom text, or exempt the entry header from the minimum.
- **N4. Growing a block from another chain.** "A realloc that grows reserves the difference first": on which chain, the block's stored one or the current one? `handle` (32MiB) appending to an array owned by `serve` (512MiB) is undefined.
- **N5. Cost claims still low.** A budget object "lives until ... no heap block still charges it" needs a count or hazard on every allocation and free, beyond the atomics per chain level. "If no chain can reach an allocation the pointer is deleted" is false for a shared allocator: a cap in any one function makes every allocation consult it and every block carry 8 bytes. `max_memory` counts Dewy heap blocks only (not mappings, files, GPU); say so.
- **N6. Table versus parameter.** Passing the same handles as a function-typed parameter silently stops `$fast_math` from reaching them (one warning). A refactor changes numerics. Make the warning name the lost setting.
- **N7. Warnings still fire on the feature.** `06` warns "not folded" on a benchmark that compares caps; R3's `today` warns under a runtime zone. A warning every user of the feature gets will be ignored. Warn only when something actually could have been folded.
- **N8. Name.** `$program.max_cores` inside `handler` now means "this call's cap", not the program's. Not a spelling change request; flag for David.

## 3. Regrade (strict; 5 means no line wants a different surface or rule)

| Program | O | D | C | S | P | Lines under 5 |
|---|---|---|---|---|---|---|
| 01 laptop_server | 5 | 4 | 5 | 5 | 4 | D: `run()` (`programs-r2/01:5`), the cap arrives by dynamic extent; nothing at `run` says so. P: no `--cores N`; that needs a refined parameter (10) and N1. |
| 02 checks_harness (r3) | 4 | 4 | 5 | 5 | 3 | O: `{ $runtime_checks ... }` (`programs-r3/02:9-12`) wraps a print of `sum_of` and `probe` together, so the reader cannot tell the tag is only there to make `probe` legal. P: the plain `probe` is never shown; a harness cannot run its unproved code both ways, which is the real harness job. |
| 03 game_profile | 5 | 4 | 4 | 3 | 4 | D: caps are in functions that only print. C: two tags per profile function plus a wrapper-free but duplicated body. S: `max_memory = 256MiB` (`:5`) ends the process at the cap; no `available_memory` to shed load beside `available_cores`. |
| 04 request_memory | 4 | 4 | 4 | 4 | 3 | O: `"ping"` allocates a few bytes; the 32MiB line (`:4`) is never reached. P: no case of exceeding the cap, returned block charged to a dead scope (`page`, `:12`), or growth (N4). S: what the user sees at the cap is "ends". |
| 05 user_zone | 4 | 4 | 5 | 4 | 4 | O: `$time.zone = user.zone` (`:4`) reads like an assignment but is scope-wide, including lines above it. S: a runtime zone typed wrong is `or_throw` in `main` (good) but `{today}` of an unset zone is the host zone silently. P: no parallel handlers. |
| 06 bench_cores | 5 | 4 | 4 | 4 | 3 | C: three bracketed blocks with `;`. S: warning on correct code (N7). P: the timing (`now`) was removed, so it no longer benchmarks anything; a million `i` does not show a cap's effect. |
| 07 task_outlives | 4 | 4 | 5 | 4 | 4 | O: `app.spawn(@child(app done));` (`:13`) discards a handle with `;` and partial application is a convention the doc never states. S: nothing shows the 32MiB budget surviving. P: no cancellation if `main` ends. |
| 08 library + app | 5 | 4 | 4 | 4 | 4 | D: `main` in a library with `$program.max_cores = 8` (`08_library:15`) is never installed here (the app is the entry); the only effect is a warning. P: no library function carries `$program.max_cores` (R1 does). |
| 09 nested_caps | 4 | 4 | 5 | 4 | 4 | O: `wider` says 16 and runs at 8 (`:3`). S: a looser line that silently runs tighter, only a warning. P: no runtime value, no task. |
| 10 config_cores | 3 | 3 | 3 | 4 | 3 | O/D: the cap is in a helper `play` taking a refined `int<1 <=? cores>` (`:1`) just to make N1 go away; `main` cannot set it itself. C: helper plus refinement plus guard in `main` for one number (Python: `os.cpu_count()`; Go: `GOMAXPROCS(n)`). P: `cores` above hardware not addressed. |
| 11 fast_math | 5 | 4 | 5 | 4 | 4 | D: `$fast_math` block (`:14-16`) silently compiles `dot` twice; the warning is the only clue. S: float results differ; opt-in so fine. P: no call out of the module, so the warning for a library callee is not shown. |
| 12 wasm_entry | 4 | 4 | 5 | 4 | 3 | O: `max_cores = 4` (`:4`) runs at 1 with a warning. P: nothing about files, threads or `wasm32` besides a warning. |
| 13 fold_call (r3) | 4 | 4 | 4 | 4 | 5 | C: three tags to parse one string (`:7-9`); every comparison language passes zone, gap and fold as arguments to the one call. S: `zoned(text) or_throw` keeps a failure type the policies make impossible. O: `user_stamp` mutating the zone for `zoned(text)` only reads obviously after learning scope rules. |
| 14 replay | 5 | 4 | 5 | 5 | 4 | D: `let n = ch.receive or_throw` (`:14`) only works because waits yield; nothing at `$parallel.off` says "cooperative". P: no busy-wait case. |
| R1 indexer + app | 4 | 4 | 5 | 4 | 4 | O: `index` says 8 (`R1_indexer:3`) and runs at 2. D: `h(words)` table dispatch (`R1_app:10`). S: a library bumping 4 to 8 warns every capped caller. P: N6 variant (parameter instead of table) not shown. |
| R2 flag | 4 | 4 | 5 | 5 | 2 | P: the case I asked for, a `$runtime_checks` chosen from a flag, is not in the file; the replacement `$fast_math` is a static `if`, not a run-time flag at all (the rule text calls it a run-time flag but the file branches in source). O: no file shows the diagnostic. |
| R3 zone_server | 4 | 3 | 4 | 4 | 3 | D: `audit` reads `{today}` (`:12`) in the Tokyo zone set in `handle`, in a task started before the tag line. C/S: `render` called both from `handle` and the spawned `audit`, warning noise (N7). P: no handler under both a runtime zone and a library literal (N3); `pages` returned from `handle` charging two budgets (N4/N5) not examined. |

Floor 3 comes from 10 (O/D/C 3, P 3: the common "read config, set cap" needs a helper and a refinement), 02 P, 04 P, R2 P, and the unaddressed N1/N3.

## 4. Against dogfood-round3.md

Its floor is 4 and it says the remaining 4s (unwritten dynamic-extent use, ambient zone, process-ends-at-cap, unseen charges) are inherent. I disagree on the floor, and agree only in part on inherence.

- Floor: 04, 10, R2, R3 and 06 are not 5 on P in my read, because the programs do not exercise the cases the rules were written for (exceeding a cap, returning a charged block, runtime literal, local cap value). Several of its 5s (08, 10, 13) rest on programs rewritten to avoid the hard case: 10 now takes a refined parameter; R2 no longer has a flag; 13 avoids a library literal.
- Inherent: `run()` not showing its cap (01, 11), ambient zone (05, R3), and the table/handle dispatch are inherent to dynamic scoping; any alternative is an explicit-argument design. Those 4s are fair.
- Not inherent: `today` and `zoned` taking explicit zone/gap/fold arguments is a spelling question David can add (13's C and S are a choice, not forced); an `available_memory` read beside `available_cores` removes 03's S 4 (new member, so David's call); N1 and N3 are rule gaps, not inherence; a looser inner literal "silently runs tighter" (09, R1) is the cost of the minimum rule, not of the feature.
