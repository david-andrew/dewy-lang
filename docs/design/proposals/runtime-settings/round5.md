# Runtime-chosen settings, round 5

Round 4 stands except where this file says otherwise. No new spelling. `available_memory` is still only a proposal: it has not had a cold read, so 03 and 04 do not call it.

## Where a setting starts

By class, not by what the right-hand side reads.

A **cap, ceiling, schedule, or policy** starts at its line and covers the rest of that scope, then callees and tasks started there. That is `$program.max_cores`, `$program.max_memory`, `$program.max_tasks`, `$parallel.max_cores`, `$parallel.max_concurrent`, `$parallel.chunk_size`, `$placement.cores`, `$parallel.off`, `$parallel.scheduler`, `$placement.device`, and `$time.zone`, `$time.rules`, `$time.zone_source`, `$time.gap`, `$time.fold`. A literal 4 and a local `cores` start at the same kind of line. Moving the 4 into a `let` does not change which statements are covered.

```dewy
let cores = to_int((p"cores.txt".read_text or_throw).trim) or_throw
if cores <? 1 exit(2)
{ $program.max_cores = cores; run() }
```

The block is the scope. The setting is its first line, so the `read_text` above it is not under the cap and does not warn. The same setting written in the function after that call does warn.

One warning, at the setting, when any call or any allocation sits lexically above it in the same scope. It names the first one: "`read_text` above this setting is not under it." A `let` of a name, or arithmetic that does not call and does not allocate, does not warn. A guard that prints is a call and does warn. Nothing else is exempt.

A local used by the setting and defined below it is a compile error: "`cores` is defined below this setting. Move the setting below it, or write `{ $program.max_cores = cores; run() }`."

A **code setting or a marker** still covers the whole scope, wherever it sits, as LANGUAGE.md says. `$runtime_checks` at the bottom of a block checks an index above it. `$fast_math` written on a function covers that function. The one evaluation exception: `$fast_math = flag` when `flag` is not a compile-time constant starts at its line, because the value does not exist at entry. Bare `$fast_math` and `$fast_math = true` cover the whole scope.

Parameter copies are bound before the body. A cap in the body is not in force for them. The caller pays for those copies. Arguments and defaults already run in the caller.

The entry header is the file-level cap and policy settings after the imports and before the first declaration. A file-level cap lower in the file starts at that line; functions above it are not under it, and the warning says so.

## A library cannot raise the program

Batch 4: a library does not pick the program's settings. The entry header is the default. A function or block in the **entry file** replaces that default when no entry-file cap is already on the stack. `main` that sets a cap has chosen for the whole run; a function it calls can only narrow, even in the entry file. `main` that does not set one leaves `laptop` and `server` free to replace the header. After that call returns, the header is back.

A nested cap, in the entry file or not, takes the **minimum** with the cap already in force. A setting in **any other module** can only narrow the limit in force. It never replaces the header and never raises an entry function's cap. Literals, locals, and function values use that same minimum. A looser literal warns once: "this asks for 8 cores; the call allows 2; the call runs at 2." A looser runtime value is the same minimum, with no warning and no refusal.

So a header of 2 keeps `lib.wide`, which asks for 8, at 2 even when `laptop` sets nothing. `server` in the entry file may set 8 and replace the header. `lib.wide` called from `server` runs at 8. Deleting the line inside `laptop` does not let the library go past the header. A library file-level cap is still installed only when that file is the entry.

Policy is not a minimum. The innermost zone, gap, or fold still wins inside the function that sets it, including a library function, and does not leak back to the caller. A library file-level zone is still not the importer's zone.

## Memory

Prefer a **per-page owner** over a word on every block. The allocator's mapped page has one budget record. A page is charged to only one innermost budget, so a size-class page is not shared across caps. Allocations with no memory cap on the stack use unowned pages and stay on today's fast path: no owner word, no chain walk. Allocations under a cap take a page for that budget, add the page's bytes to `live` along the chain, and store the budget on the page. Free subtracts on that same `live` atomic; the page record is the retain. When the subtract hits zero and no scope or task holds the budget, the budget is freed. There is no second atomic and no hazard epoch.

A grow allocates the **full new size** on the current chain and, on success, frees the old pages back to their budget. The old bytes do not stay charged, and the block does not collect a list of growth owners. A one-byte append of a large array reserves the whole new array under the grower's cap. If it does not fit, the array is unchanged and the old charge stays. Failure is the allocating module's policy.

`$program.max_memory` counts those Dewy heap pages only, not files, GPU memory, thread stacks, or foreign mappings. One warning, once per build, at the first reachable `$program.max_memory`: "this cap checks allocations made while a memory cap is on the stack (N sites). Each mapped page records its budget. Allocations with no cap on the stack stay on the fast path." A core cap or a task cap does not warn.

`int64` in the programs is 8 bytes. `MiB` is 2^20 bytes, as the units design already has it. A reservation is the next power of two at least that big. 500_000 `int64`s are 4_000_000 bytes and reserve 2^22 (4MiB); 6MiB holds one of those and not two. 8_000_000 `int64`s reserve 2^26, which is over 32MiB and under 128MiB. This round adds no size-to-int conversion, so 04 counts elements instead of writing `40 * 1024 * 1024` beside `64MiB`.

## Another module's code

A caller's `$fast_math`, `$no_nan`, or `$no_inf` does **not** recompile a concrete function in another module. That library may rely on strict IEEE. The call keeps the library's numerics. One warning, naming the callee: "`lib.ieee_add` is not compiled under `$fast_math`. This call uses the library's numerics." Inlining does not sneak the caller's flag in.

Two ways to get fast math from a library, both already spellings:

- The library writes `$fast_math` on that function (`lib.fast_add`). The caller just calls it.
- The library function is generic. The instance is compiled in the caller's module, under the caller's code vector, so a `$fast_math` scope around `lib.add3(...)` does specialize that instance.

A parameter of function type is still called as declared. The warning names the setting and the parameter. Caps and zones still apply.

`$runtime_checks` chosen from a value is still not a variant. The error text is unchanged. The fix that runs in both builds is `xs.get(i)`.

## Zone literals across modules

A `zoned"..."` that names its zone in the text is a plain value. One that does not is checked against every frame that can reach it.

The check walks the callee, including other functions in that library it calls. `stamp` calling `inner` is the same literal as a literal written in `stamp`. The library is fine alone when every frame it can see is a constant. A caller in another module whose zone, gap, or fold is a runtime value is a compile error **at the call**, naming the literal's file and line. A known handle (`let f = lib.stamp`) is the same check. A finite table of known handles is checked per target. No second body, no trap, no new failure arm on the library.

A call through a function parameter whose target the compiler cannot list, under a runtime zone, gap, or fold, is a compile error at that call: "this target is not a known function, and `$time.zone` is chosen at run time. A `zoned"..."` inside it would not be a plain value. Call a known function, or parse with `zoned(text zone=z fold='later' gap='next')`." A library patch that adds a zone-less literal breaks those callers at their call, and the message names the new line.

A library function that sets `$time.zone = zone"UTC"` itself puts a constant frame around its own literals. The caller's runtime zone does not reach them.

## What changed from round 4

- A runtime cap starts at its line even when the value is a literal. Round 4 did that only when the value read a local.
- The entry header is a default entry functions may replace. A library setting only narrows. Round 4 let the library replace the header.
- The owner is one record per mapped page, not a word on every block and not a list of growth owners. A grow reserves the full new size and frees the old pages. The once-per-build warning is back.
- A concrete library function is not specialized under the caller's `$fast_math`. A generic instance is.

## Should-fixes

Taken: N11 (transitive literals, known handles, open parameters, a patch fails the caller); N12 (one page record, full new size, no owner list); N14 (no exemption list: any call or allocation above the setting warns; the block is the quiet form); N15 (04 returns the new array instead of dropping `OutOfMemory` on a mutating `extend`, and counts `int64`s); N16 (`sum_of` runs with `$runtime_checks` and without it).

Not taken: adopting `available_memory` before a cold read. A core cap still does not warn.
