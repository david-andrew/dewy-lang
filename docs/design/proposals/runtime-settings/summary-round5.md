# Runtime-chosen settings

Final rules. Rounds 2 and 4 hold where this page does not replace them. No new spelling.

## Rules

A cap, ceiling, schedule, or policy starts at its line and covers the rest of that scope, then callees and tasks started there. `{ $program.max_cores = cores; run() }` is that scope. One warning if a call or an allocation sits above the setting in the same scope. Code settings and markers still cover the whole scope. `$fast_math = flag` starts at its line only when `flag` is not a constant.

The entry header (file-level settings after the imports, before the first declaration) is the default. A function in the entry file replaces it when no entry-file cap is already on the stack, so `server` may raise a header of 2 to 8. A nested cap takes the minimum. A setting in any other module only narrows the limit in force, with a warning when a looser literal is visible. A library never raises what the program chose. After the call, the header is back. Tasks and returned pages keep the budget until they are freed. When the program ends, the entry task group is stopped and joined, and those budgets live until then.

The tightest cap in force wins for literals, locals, and function values. A looser inner literal warns and runs at the tighter cap. It is not a compile error for a literal and a refusal for a value. Zero is not "unlimited." `available_cores` is the cap after affinity, then cut to the machine. On `wasm32` a cap above 1 warns and runs at 1.

`$program.max_memory` counts Dewy heap pages only. Each mapped page has one budget record; a page belongs to one cap. Allocations with no memory cap on the stack stay on the fast path. One warning per build, at the first reachable site, with the site count. A grow reserves the full new size on the current chain and frees the old pages on success. `live` is the byte count; the page record is the retain; the subtract that hits zero is that same atomic. A core cap does not warn and does not add that record.

`$runtime_checks` cannot be chosen from a value. Unproved code is a compile error when checks are off, and proved code is the same either way. The fixes are `$runtime_checks` on the function, or `xs.get(i)`. `$fast_math = flag` is the runtime code setting that has two bodies. It does not recompile a concrete function in another module, and inlining does not either: the library may rely on IEEE. The warning names the callee. The library can write `$fast_math` on its own function, or offer a generic, whose instance is compiled under the caller's code vector. An open function parameter is called as declared; the warning names the setting. A finite table of known handles is specialized.

A zone-less `zoned"..."` is a plain value only under constant frames. The check walks callees in that library. A runtime zone at a call in another module, including through a known handle, is a compile error at the call, naming the literal. An unlistable function parameter under a runtime zone is the same error. No trap and no new failure arm. `zoned(text zone=z fold='later' gap='next')` is the call that already exists. `today` does not grow a zone argument. Policy does not change a result type. `$explicit_allocation_failure` still does, and it stays module metadata.

## Decisions that changed

- Round 1 attached a tag to the next statement. Withdrawn. Q6 is not adopted.
- Round 2 evaluated every cap at scope entry, and took the minimum with the entry header, so a function could not raise a default. A runtime `$runtime_checks` was rejected there and stays rejected.
- Round 4 started a cap at its line only when the value read a local, and let a library replace the header. Both are withdrawn. The owner word on every block, and the list of growth owners, are withdrawn in favor of one record per mapped page and a full new reservation on grow.

## Floors

The grade floor is 4 (`dogfood-round5.md`).

Inherent to dynamic scope: `run()` does not repeat the cap (`programs-r5/01_laptop_server.dewy:5`); `today` does not take the zone (`programs-r2/05_user_zone.dewy:5`); a handler table does not show which function runs (`programs-r4/R1_app.dewy:12`).

Inherent to static proofs: `$runtime_checks = debug` is an error (`programs-r4/R2_debug_flag.dewy:10`). One build cannot check an unproved index only some of the time.

Kept on purpose, and still a 4: a looser cap says 8 or 16 and runs at the tighter limit (`programs-r5/01_lib.dewy:2`, `programs-r5/09_nested_caps.dewy:4`), because a library must not raise the program; `lib.ieee_add` under `$fast_math` stays IEEE (`programs-r5/11_fast_math.dewy:18`); past `$program.max_memory` the process ends (`programs-r4/03_game_profile.dewy:5`), because `available_memory` has no cold read and is not a member.

No new spellings.
