# Runtime-chosen settings

Final rules. Earlier rounds hold where this page does not replace them. No new spelling.

## Rules

A cap, ceiling, schedule, or policy starts at its line and covers the rest of that scope, then callees and tasks started there. `{ $program.max_cores = cores; run() }` is that scope. One warning if a call or an allocation sits above the setting in the same scope. Code settings and markers still cover the whole scope. `$fast_math = flag` starts at its line only when `flag` is not a constant.

The entry header (file-level settings after the imports, before the first declaration) is the default. A function in the entry file replaces it when no entry-file cap is already on the stack, so `server` may raise a header of 2 to 8. A nested cap takes the minimum. A setting in any other module only narrows the limit in force, with a warning when a looser literal is visible. A library never raises what the program chose. After the call, the header is back. When the program ends, the entry task group is stopped and joined.

The tightest cap in force wins for literals, locals, and function values. A looser inner literal warns and runs at the tighter cap. It is not a compile error for a literal and a refusal for a value. Zero is not "unlimited." `available_cores` is the cap after affinity, then cut to the machine. On `wasm32` a cap above 1 warns and runs at 1.

`$program.max_memory` counts reserved bytes of live Dewy heap blocks allocated while a memory cap is on the stack. The size is the size class of the request plus its 16-byte header: 32, 64, 128, … through 256KiB, or a 64KiB-rounded mapping above that. The 4MiB slabs, their free slots, and thread freelists are not charged. A returned block keeps its size class on every budget then in force until it is freed, not the slab. Bookkeeping is one side-table word per such live block. One warning per build, at the first reachable site, states the size class and the site count. A core cap does not warn.

`$runtime_checks` cannot be chosen from a value. The fixes are `$runtime_checks` on the function, or `xs.get(i)`. `$fast_math` does not recompile a concrete function in another module. A generic instance is compiled under the caller's code vector unless that function sets the setting. `$fast_math = false` on the generic pins IEEE. A caller's `$fast_math` that does reach a generic from another module warns once per build and names the pin. A finite table of known handles is specialized. An open function parameter is called as declared.

A direct call sees the caller's zone, gap, and fold. A function value captures those frames at the `@` that creates it, and a library zone does not retarget it. `table = [@a @b]` captures at those `@`s. Passing a top-level function creates the handle at the argument, in the caller. Caps and schedules do not capture; they follow the caller that runs the value, or the chain at `spawn`. A zone-less `zoned"..."` under a runtime zone is a compile error at the direct call or at the `@`, naming the literal. `zoned(text zone=z fold='later' gap='next')` is the existing call. `today` takes no zone argument. Policy does not change a result type. `$explicit_allocation_failure` still does, and it stays module metadata.

## Decisions that changed

- Round 1's next-statement attachment is withdrawn. Q6 is not adopted. A runtime `$runtime_checks` stays rejected.
- Round 4 let a library replace the header, and started a cap at its line only when the value read a local. Both are withdrawn.
- Round 5 charged a whole slab to one cap. Withdrawn. The cap charges the block's reserved bytes. A generic from another module still follows the caller's `$fast_math`, and that now warns unless the library wrote `$fast_math = false`. A function value keeps the policy at its `@`. Caps stay with the runner.

## Floors

The grade floor is 4 (`dogfood-round6.md` for the three programs this round changes; `dogfood-round5.md` for the rest).

Inherent to dynamic scope: `run()` does not repeat the cap (`programs-r5/01_laptop_server.dewy:5`); `today` does not take the zone (`programs-r2/05_user_zone.dewy:5`, and `programs-r6/R3_zone_server.dewy:16`); a handler table does not show which function runs (`programs-r4/R1_app.dewy:12`).

Inherent to static proofs: `$runtime_checks = debug` is an error (`programs-r4/R2_debug_flag.dewy:10`).

Kept on purpose, and still a 4: a looser cap says 8 or 16 and runs tighter (`programs-r5/01_lib.dewy:2`, `programs-r5/09_nested_caps.dewy:4`); `lib.ieee_add` and an unpinned generic under `$fast_math` warn instead of changing silently (`programs-r6/11_fast_math.dewy:14`); past a memory cap the process ends unless the module opted into `OutOfMemory` (`programs-r4/03_game_profile.dewy:5`). `available_memory` is not a member.

No new spellings.
