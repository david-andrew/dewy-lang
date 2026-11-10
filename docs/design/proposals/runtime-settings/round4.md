# Runtime-chosen settings, round 4

Round 2 still holds except where this file replaces it. No new syntax. `available_memory` is proposed below and not used: it has not had a cold read. Open D4 Q6 stays open. `$program.max_cores` is not renamed (N8).

The plain program is a local, then the setting, then the call. It compiles. The cap starts at the setting.

```dewy
main = () => {
    let cores = to_int((p"cores.txt".read_text or_throw).trim) or_throw
    if cores <? 1 { printl("cores must be at least 1" file=stderr); exit(2) }
    $program.max_cores = cores
    run()
}
```

## Where a setting is evaluated

LANGUAGE.md still holds for a setting that does not read a local: it covers the whole scope, wherever it sits, and it is evaluated on entry. Parameters are in scope. `$runtime_checks` at the bottom of a function still checks an index above it. A scope still sets each setting once.

A setting that reads a local is the case that rule cannot cover. The local does not exist at entry, and the setting textually follows the `let`. That setting is evaluated at its line, after the statements above it. The frame starts at that line and runs to the end of the scope, including callees and tasks started there. The statements above it are not in the frame. This is the change to "evaluated at entry, parameters only." It is required for the program above. Considered: keeping entry-time evaluation and making that program an error whose fix is a helper with a refined parameter. That is the form round 3 shipped, and it is the long way around the common case.

A local named by the setting and defined below it is a compile error at the setting: "`cores` is defined below this setting. A setting that reads a local is evaluated here; move it below `cores`." A call or an allocation above the setting warns once: "this cap starts here because it reads `cores`. `run()` above it is not under the cap." The `let`s the value reads, and the guard that proves the value, do not warn. That is the plain form.

`$fast_math = flag`, when `flag` is a local, is the same extent: the code below the line is compiled both ways, and the code above the line is the off body. `$runtime_checks = debug` resolves `debug` the same way and is still the error in "Code settings." Resolving the name does not make that flag a variant.

## Default and cap

These are different. Round 2 put the entry header on the minimum chain, so a function could not raise it. That rejects the first program people write.

**The entry file's header is a default.** A file-level `$program.max_cores`, `$program.max_memory`, `$program.max_tasks`, `$parallel.max_cores`, or `$parallel.max_concurrent` on the entry file is the limit used when no function and no block on the stack has set that setting. A function or a block that sets it **replaces** the default for its extent. It is not the minimum of the two. Replacing a default does not warn. A header of 2 and `server` setting 8 runs `server` at 8. `laptop` that sets nothing runs at 2. After `server` returns, the caller's later code is back to 2.

**A setting in a function or a block is a cap.** It bounds that scope and what it calls. An inner function or block takes the minimum with the cap already in force from an outer function or block. Literals, locals, and function values all take that minimum. A looser inner literal warns once and runs at the tighter cap: "this asks for 16 cores; `server` allows 8; the call runs at 8." A looser runtime value is the same minimum, with no warning and no refusal. There is no second behavior for the same mistake.

The header is not on that chain. A library function that sets 8, called when the only outer limit is the header's 2, runs at 8. The header was a default and the function replaced it. A ceiling has to be written in the function that should enforce it. `laptop` setting 2, then calling `index` which sets 8, runs at 2 and warns at `index`.

A file-level setting on a file that is not the entry is still installed only when that file is the entry. It is not the importer's default. Policy frames are unchanged: the innermost zone, gap, or fold wins, so a function's zone replaces the header zone too. For a zone, replacement and "innermost" are the same rule.

`$program.max_cores` in a function means this call's cap, not a process seal (N8). The same spelling in the entry header is the default. Not renamed here. David, if one of those should be a different name.

## Caps otherwise

The budget object, permits, `available_cores`, obligations, and wasm are as in round 2, with two edits.

The obligation sits at the setting. A local is proved by a guard above the setting in that same scope, or by a refined type on the local. A parameter is proved by a refined parameter, as before. Neither is required when the other is present. Omitting both is a compile error: "`cores` is not proved `>= 1`. Guard it before this setting." Under `$runtime_checks`, that check exits 101 and the rest of the scope does not run. A caller’s guard does not prove a callee’s parameter. Zero and negative are never "unlimited." Hardware does not have to be at least the cap: `available_cores` is the cap after affinity, then cut to the machine. Asking for 99 on a 4-core machine allows 4.

Order. Arguments and defaults run in the caller. On entry, settings that do not read locals are evaluated (parameters are in scope), checked, and pushed; they cover the whole scope, including parameter bindings that allocate. The body then runs. At a setting that reads a local, that expression runs, the obligation is checked, and the frame is pushed for the rest of the scope. A copy to bind a parameter is not under a cap the body has not reached.

## Memory

Round 2's charge (reserved Dewy heap block, chain walk, one owner pointer, returned blocks, shared parallel budget, grandchild tasks) stays. Growth and the process-wide cost were wrong or missing.

**Growth.** The difference `new - old` is reserved on the chain in force at the realloc, innermost last, and rolled back if it does not fit. The original bytes stay on the chain that allocated the block. They are not moved onto the grower. If this innermost budget is already the block's owner, the block adds the difference to that charge and still stores one pointer. If it is a different budget, the block stores another owner, the growth budget, and the extra bytes. A later growth under a third budget stores another. Free releases each charge along its own chain. The array is unchanged if the reserve fails. The failure is the allocation policy of the module that executes the grow.

`serve` allocated `cache` under 512MiB. `handle`, under 32MiB, appends. The extra bytes must fit in 32MiB and in 512MiB. The bytes `cache` already had stay on `serve` only. `handle` is not charged for them.

**What the cap counts.** Dewy heap blocks only: size classes and mappings from the Dewy allocator. Not files, GPU memory, thread stacks, or foreign mappings.

**Who pays.** One reachable `$program.max_memory`, in any module, selects the checking allocator for every Dewy heap allocation in the process. A block allocated outside a cap can be freed or grown inside one, and the freelist does not know which. Every live Dewy heap block carries the owner pointer (8 bytes, plus 8 per extra growth owner). An allocation with no frame charges a process root that has no limit; the pointer is still stored. The fast path that deletes the pointer remains only when no reachable code sets `$program.max_memory`. A core cap or a task cap does not add that word. It costs a permit take on `spawn` and `parallel` only.

**Lifetime.** `live` is the byte count, not the retain. The retainers are the scope, each task that captured the chain, and each owner pointer on a block. No hazard epoch and no second atomic per allocation beyond the chain walk and the pointer store. The budget is freed when the scope is gone, no task holds it, and no block points at it.

When the program ends, LANGUAGE.md already stops the entry `BackgroundTasks` group and joins it. Those tasks still hold their budgets until that join frees the blocks. `main` returning does not drop a budget a task still charges. A task that never finishes is stopped there; this design does not add a second cancellation spelling.

Depth 32 and 100,000 allocations is still 3.2 million atomic adds and 3.2 million releases on the chain, plus the pointer store, plus about 0.8MiB of owner words at 100,000 live blocks. A capped function in a library puts that word on blocks that never run under the cap. That is the cost of the shared allocator, not of the call itself.

## Policy, including another module

A `zoned"..."` literal that names its zone (`zoned"2026-10-26T09:00[America/New_York]"`) is a plain value. It does not read `$time.zone`.

A `zoned"..."` literal that does not name a zone reads the zone, gap, and fold in force where it runs.

- Same module: if every frame that can reach it is a compile-time constant, it is a plain value. If any is chosen at run time, the error is at the literal, as in round 2. One result type.
- Another module: the library is compiled without the importer, so a literal the library itself reaches only under constant frames is fine alone. Compiling a call looks at that literal. It does not build a second body. A caller whose zone, gap, and fold are compile-time constants keeps the plain value; the literal is checked under those constants. A caller whose zone, gap, or fold is a runtime value is a compile error **at the call**:

> `lib.stamp` contains `zoned"2026-03-08T02:30"` (`13_lib.dewy:1`). This call's `$time.zone` is chosen at run time, so that literal is not a plain value here. Parse with `zoned(text zone=z fold='later' gap='next')` and handle the failure, or call `stamp` from a scope whose zone is a constant.

No trap, no runtime parse, and the library's signature does not grow a failure arm. `zoned(text zone=z fold='later' gap='next')` is the call LANGUAGE.md already has. A bad string is still that call's failure. A gap or a repeated hour is resolved by the arguments, not left in the type. `today` does not grow a zone parameter in this design. A handler that wants every `today` in the request in one zone still writes `$time.zone`. Threading the zone through `today` would be a new argument on a name that does not have it.

A function that sets `$time.zone = zone"UTC"` itself puts a constant frame inside the literal's scope. The caller's runtime zone does not reach that literal. The call is legal. The error is only when the literal actually reads the runtime frame.

## Code settings and function values

`$runtime_checks` chosen from a value is still not a variant. The program a user writes is `R2_debug_flag.dewy`. The error is:

> `$runtime_checks` cannot be chosen at run time. With the flag off, `xs[i]` is not proved. Write `$runtime_checks` on this function, or prove the index (`xs.get(i)`).

If the body is already proved: "checks on and checks off are the same code; delete the flag." The fix that runs in both builds is `xs.get(i)` (`R2_fix.dewy`). `$runtime_checks` with no value, on the function, is the other fix, and it is on for every build. There is no runtime flag that means "check this index only when argv says debug."

`$fast_math = flag` stays the runtime code setting that has two real bodies.

A parameter of function type is called as declared. The caller's code settings do not retarget it. The warning names the setting and the parameter: "`f` is a function parameter. This call's `$fast_math` does not apply to `f`. A table of handles written in this scope is compiled for `$fast_math`; a parameter is not." The call stays usable. Caps and policies still apply: the declaration's cap, then the minimum with the caller's function caps, and the innermost zone. A refactor from a local table to a parameter changes numerics only for code settings, and the warning says which ones.

## `@` and `;`

`@child(app done)` is partial application, as LANGUAGE.md defines `@f(args)`. `app.spawn(...)` returns a handle. The `;` discards it. Neither is a setting spelling.

## Costs and warnings

Kept, each once: a function or block cap looser than a function or block cap already in force, when both are literals; `$fast_math` / `$no_nan` / `$no_inf` calling out of the module, naming the callee; a table that keeps more than one code body, with the count; `$parallel.off`, because waits yield, including in callees; `$program.max_cores` above 1 on a target with no worker threads, running at 1; an inner chunk size replacing an outer one; an empty affinity intersection (literals are an error, a dynamic empty set does not start the scope).

Dropped. A loop, a `today`, or a chunk reached under more than one cap or zone is the feature, not a missed fold. Warning there fires on every benchmark and every request handler. A scope that sets a cap is the same: the cost is the chain walk, and the warning would fire on every use. Replacing the entry header does not warn.

## `available_memory`

Proposed, not adopted. Beside `available_cores`, it would be the bytes still reservable on the tightest memory budget in force (the minimum of `limit - live` on the chain), counting the same Dewy heap blocks as the cap. A game can skip a load that does not fit instead of ending at the allocation. The name is the sibling of `available_cores` and still needs a cold read before it is a member. Programs do not call it. Past the cap, the program still ends, or returns `OutOfMemory` where the module has `$explicit_allocation_failure`.

## Decisions that move

- **Entry header.** Batch 4's "only at the top of the entry file or inside `main`" already moved in round 2. The header is a default, not the outer cap. A function may raise it. A function cap may not be raised by what it calls.
- **Calling another `main`.** Two function caps still take the minimum. Two header defaults are not both installed: the running entry's header is the default. `$target` and `$build.mode` stay a conflict error.
- **N1's evaluation rule** is the one change to LANGUAGE.md "holds throughout the scope, wherever it sits." Constant and parameter settings still do. A setting that reads a local starts at its line.

## Should-fixes

Taken: N2 (header default, function cap); N4 (growth difference on the current chain, original bytes stay); N5 (shared allocator, what the cap counts, retainers); N6 (the warning names `$fast_math` and the parameter). N7 in part: the "not folded" warning and the "this scope sets a cap" warning are dropped; the warnings that name a real surprise stay.

Not taken: renaming `$program.max_cores` (N8); adopting `available_memory` before a cold read; giving `today` a zone argument; making a looser inner function cap a compile error. The minimum stays one behavior, and the line that says 16 while running at 8 stays a 4 on purpose. A library must not be able to raise `laptop`'s cap.

## Rejected

- The config local is an error, and the fix is a helper with `int<1 <=? cores>`.
- The entry header is a ceiling.
- A `zoned"..."` literal in another module, reached under a runtime zone, becomes a runtime parse or a trap.
- Growing a block moves its original bytes onto the grower's budget.
- "No frame reaches this allocation" deletes the owner word while any reachable function sets `$program.max_memory`.
