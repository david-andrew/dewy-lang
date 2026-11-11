# Runtime-chosen settings, round 2

A function sets a resource cap or a policy for its own execution, and `main` calls the one it wants. The setting is written in the function, so it covers the whole function. `laptop()` runs at 2 cores, `server()` at 8, and after that call returns the caller's code is back to whatever was around it. Tasks started inside the call, and heap blocks they still hold, keep the budget. No new syntax. The line-above-the-function picture from the brief is not this design: a file-level setting covers the whole file, and open D4 Q6 is what would make a leading tag belong to the next declaration. This round does not take Q6.

```dewy
$program.max_cores = 2
laptop = () => {
    run()
}
$program.max_cores = 8
server = () => {
    run()
}
main = (argv:array<string>) => {
    if (argv.get(0) ?? "laptop") =? "laptop" laptop() else server()
}
```

`run` sees the cap of the function that called it. A second call is a second frame. The tightest cap in force wins, whether the numbers are literals, runtime values, or the function was taken from a table. A looser inner literal warns at that line and does not fail the build.

## What round 1 got wrong

Round 1 attached a tag to the next construct, including the next statement inside a function. That contradicts LANGUAGE.md ("holds throughout the scope") and the entry-point rule (a setting in `main` is that function, not its next line), and it made `$explicit_allocation_failure` before a function both a module header and an error. It also rejected a literal inner cap that was looser than the caller, but only refused a runtime or indirect one at run time. Those are one mistake. The memory rules did not say which budget a returned block or a grandchild task charges. A runtime `$runtime_checks` cannot do the job it looks like.

## Where a setting is written

Unchanged from LANGUAGE.md "Directives": a setting holds for the whole scope it is written in, wherever it sits in that scope. The module at file level, a function in its body, a block in its body. A scope sets each setting at most once. An inner scope may set it again.

A tag inside a function covers every statement of that function, including a statement above the tag and a callee the function calls. It does not cover only the next line. `let a = work(); report(a)` after `$program.max_cores = cores` is under that cap. Two counts in one function are two blocks, because a block is a scope:

```dewy
{ $program.max_cores = 1; work() }
{ $program.max_cores = 2; work() }
```

Writing the same setting twice in `main` with no inner block is a duplicate-setting error, as today.

**Module metadata** is not a call frame. It is installed with the module, imported or not: `$explicit_allocation_failure`, `$default_row`, `$dewy.version`, `$supported_targets`, `$target`, `$build.mode`. `$explicit_allocation_failure` before a function in a functions-only file is the module's allocation policy, not a prefix of that function and not an error. `$dewy.version` is only this class (it is not also a build-mode switch).

**File-level resource and policy settings** on the entry file are the outermost frame of the process. The same settings at file level in any other file apply only when that file is the entry, so a library header still cannot pick an importer's zone or core cap. A library that wants a cap when it is called puts the setting in the function.

`$bulletproof` and `$no_hidden_costs` keep every member they have today, including `$default_row`. `$default_row` is a default on functions **declared** in that scope. It is not a frame pushed onto callees, and it is not dropped to make the bundle fit a code vector. `$no_hidden_costs` on a function still opts that function's declarations into `no allocates & no panics` and still forbids `$runtime_checks` there. It does not rewrite another module's signatures. An imported module's `$explicit_allocation_failure` still adds `OutOfMemory` to that module's allocating calls.

## Classes

| Setting | Class | What a call does |
|---|---|---|
| `$program.max_cores`, `$program.max_memory`, `$program.max_tasks` | Cap | Pushes a shared budget for the dynamic extent. The tightest limit on the chain wins. |
| `$parallel.max_cores`, `$parallel.max_concurrent` | Cap | Same chain, counted separately (cores, items in flight). |
| `$parallel.chunk_size` | Granularity | Innermost value wins. It is a minimum items-per-chunk, not a core cap, and it is not mixed into `available_cores`. |
| `$placement.cores` | Affinity | Intersection of the sets on the chain. Empty means the scope does not start. |
| `$parallel.off` | Schedule | Cooperative source-priority replay for `parallel` entered during the extent, including in callees. One body. |
| `$parallel.scheduler`, `$placement.device` | Schedule | The extent's work uses that scheduler or device. One body. |
| `$time.zone`, `$time.rules`, `$time.zone_source`, `$time.gap`, `$time.fold` (and `$program.time_zone`, `$program.time_zone_rules`, `$program.time_zone_source` if that rename is accepted) | Policy | Innermost frame wins. Read when the operation needs it. One body, one result type. |
| `$runtime_checks`, `$prototype`, `$prototype_warnings`, `$fast_math`, `$no_nan`, `$no_inf`, `$finite_floats`, `$no_assumed_bounds`, `$explicit_copies`, `$explicit_cancellation`, `$confine_external_paths`, `$assume_local_asserts`, `$no_deadlocks`, `$time.strict`, `$time.only_strict_today`, `$time.no_assumed_*` | Code | Specializes same-module instances the scope reaches. Not a runtime flag for `$runtime_checks`. `$time.require_range` is not a second spelling of `$time.no_assumed_range`. |
| `$no_hidden_costs` | Code, whole bundle | As today, on the scope's own text and declarations. `$default_row` stays in it. |
| `$target`, `$build.mode` | Build | Fixed for the build. Choosing them from `argv` is a compile error. Another entry file, or `--target` / `--release`, builds the other one. |
| `$explicit_allocation_failure`, `$default_row`, `$dewy.version`, `$supported_targets` | Module metadata | Installed with the module, including when it is imported. |
| `$memory.layout`, `$unsafe`, `$extern`, `$intrinsic`, `$audited_wait`, `$send`, `$sync`, `$export`, `$shadowable`, `$test`, `$named` | Declaration or marker | Unchanged. Not a frame. |

`$bulletproof` is the bundle it already is. Its metadata member stays metadata; its code members are the module's code settings when the bundle is at file scope.

## Caps

Entering a scope that sets a cap creates a **budget object**: the limit it wrote, the amount in use, and the parent budget if the caller had one. The scope and every task started from it hold a reference. The object lives until those tasks have finished and no heap block still charges it. Popping the scope stops the scope's own code from using it. It does not erase the object.

The limit that applies is the **minimum** of the limits on that chain. An inner scope that asks for more than an ancestor allows runs at the ancestor's limit. Literals, runtime values, and calls through a function value use that same minimum. There is no compile error for the literal and no refusal at run time for the value.

A warning, once, at the inner setting, when both numbers are literals the compiler can see (a direct call, or a table whose targets are a written list of handles): "this asks for 8 cores; `laptop` allows 2; the call runs at 2." A library that changes 4 to 8 in a later version warns callers who already capped tighter. It does not fail their build. The warning is not limited to the same package: the contradiction is the same, and a warning is not a break. If the ancestor's limit is a runtime value, there is no warning; the minimum still applies. A looser request does not cost speed, so there is no runtime warning and no counter of how often it was ignored.

`available_cores` is the number of cores the extent is allowed to run on: the cardinality of the hardware set after the affinity intersection, then the minimum of the `$program.max_cores` and `$parallel.max_cores` limits on the chain. It is not how many are idle. Chunk size, item caps, and `$parallel.off` do not change it. `$parallel.off` still runs one item at a time only because the schedule says so.

A core permit is one slot in a budget. A runnable job holds one permit from **every** pool on its chain, so an outer cap of 2 limits the whole descendant tree to 2, even when one child asked for 1 and another for 2, and even when both children asked for 2. With no outer cap, sibling extents have no shared pool and their allowances add. That sum is the rule, not a diagnostic. A waiting thread releases its permits for the wait and takes them back after, so a blocked call does not eat a core.

`$program.max_tasks` is the same shape, counting admitted tasks instead of cores. An admission that does not fit rolls back the reservations it already added on the chain. Past the limit, admission follows the allocation policy already decided: the program ends, or `OutOfMemory` where `$explicit_allocation_failure` is on.

### Memory

The amount charged is the **reserved heap block** (the size class or mapping the allocator took), not the logical length, not a cumulative high-water mark, and not a stack slot. Stack frames are not charged. An arena's backing block is charged like a heap block to the chain in force when the arena grew; freeing the arena releases it.

A new block is reserved by adding its size to `live` on every budget in the chain, innermost last, each add atomic. If one budget would pass its limit, the adds already done are subtracted and the allocation fails. The block stores a pointer to the innermost budget (8 bytes on a 64-bit host; a side table is an implementation choice with the same number of records). `free` and a shrink subtract along that same chain. A realloc that grows reserves the difference first and then releases the old size. Copy-on-write charges the block once, to the chain that allocated it; another view of the same block adds nothing; a copy that allocates a new block charges the chain in force at the copy.

A fresh scope starts its **own** `live` at zero. It does not clear its ancestors. Three calls that each allocate 24MiB under an inner cap of 32MiB and return those blocks to a caller capped at 64MiB charge 24MiB to each inner budget and 72MiB to the outer one, so the third reservation fails against the outer budget. After the inner call returns, the block still charges both budgets until it is freed, under whatever scope frees it.

Parallel iterations of one scope share that scope's budget. They do not each get a fresh 32MiB.

A task captures the chain by reference. A task it starts later, including after the original call has returned, captures that same chain plus any budget its own scope creates. Two tasks that each allocate 32MiB under a 48MiB scope that has already returned still share the 48MiB object; the second reservation fails. They also still charge the entry's 128MiB budget. "The cap is gone when the call returns" is true of the caller's later code and false of those tasks and of blocks they have not freed.

If the reserved block does not fit, the failure is the allocation policy of the **module that is allocating**. A copy made to bind a parameter is the callee's allocation: the callee's module decides `OutOfMemory` or an environmental end, and the body does not start. Arguments and default expressions are evaluated in the **caller** before that, under the caller's budgets. A default that reads `$time.zone` reads the caller's frame, as LANGUAGE.md already says. Order: arguments and defaults, then the callee's setting expressions (parameters are in scope), then the obligation check on those values, then the budget push, then parameter bindings that allocate, then the body.

### The value of a cap

`$program.max_cores = cores` requires `cores >= 1`, and `$program.max_memory` requires a size greater than zero. A literal that fails is a compile error. A dynamic value is an ordinary obligation at the setting: proved by a refined parameter (`cores:int<1 <=? cores>`) or by a guard in **that same scope**, else a compile error, else a check under `$runtime_checks` that exits 101 and does not enter the rest of the scope. A guard in the caller does not prove the callee's parameter. The call proves a refined argument the usual way, so `if cores <? 1 exit(2) else play(cores)` works when `play` takes `int<1 <=? cores>`. Positivity is not a comparison with the ancestor cap, and proving it does not remove the budget walk.

Zero and negative never mean "all the cores" or "no limit."

On `wasm32` and any other target with no worker threads, an effective core cap above 1 warns once and runs at 1. The program still builds. Whether `read_text` exists on that target is not this design.

## Policy and result types

A zone, rule pack, zone source, gap, or fold on an inner scope replaces the outer one for that extent. A task keeps the policy frames in force when it was started, including after the caller returns, and a task it starts inherits those frames. The caller's later code does not. A literal zone name is checked while compiling. A runtime zone is a `Zone` from `zone(text)`, so a bad name is that call's `ValidationError`.

No policy setting changes a result type, and a function has one signature. A zone literal (`zoned"..."`) is a plain value only when every policy frame that can reach it is a compile-time constant, including through callers in the same module. If any reaching frame is chosen at run time, the literal is a compile error: "this literal is reached under a runtime zone; write `zoned(text)` and handle the failure." A `const` under a runtime policy is the same error. `zoned(text)` keeps the failure union it has today. Gap and fold do not appear or disappear from a signature because a caller set them; a function that needs a fallible add calls the form that returns the union (`add(gap='reject' fold='reject')`), and a function that needs a plain value uses a constant policy.

`$parallel.off` is source-priority **cooperative** replay: items run in source order, and an item that waits yields so a sibling can run. A producer and a consumer on one channel in one `parallel` block still complete. It is not a strict serial execution, and it is not "the code must be correct with no yielding." A busy-wait that never waits in the scheduler can still spin; that is the existing expert-lane limit. The frame covers `parallel` the extent enters, including in callees. One warning at the setting: "replay also covers `parallel` in functions this scope calls."

## Code settings

A code setting applies to the text of its scope and to **same-module** functions that scope calls which do not set the setting themselves. Another module is not recompiled. Its obligation policy, NaN policy, and fast-math choices stay what that module wrote. A call from a `$fast_math` scope into another module warns once: "this callee is not compiled under `$fast_math`." Library checks stay library checks.

The compiler's state is one concrete instance (a generic's declaration, its type arguments, and which closure) plus the normalized code-setting vector. A recursive call with the same state uses a pending entry, so it does not generate bodies forever. A cycle that flips a setting is two states. `panics` is part of the result of the checks-on state, as today. Walking the instantiated graph is O(S + T) in those states and edges. That is discovery, not proof or optimization. Each retained body is then compiled on its own. Identical machine code can be merged afterwards; the compile of both still happened.

A runtime value for `$runtime_checks`, `$prototype`, `$no_hidden_costs`, `$explicit_copies`, `$explicit_cancellation`, `$no_deadlocks`, or a `$time.strict` / `$time.no_assumed_*` tag is a compile error, not a variant:

> `$runtime_checks` cannot be chosen at run time. With the flag off, `xs[i]` is not proved. Write `$runtime_checks` on this function, or prove the index (`xs.get(i)`).

If the body is fully proved, the same flag is still an error: "checks on and checks off are the same code; delete the flag." The flag cannot defer a proof, which is the only reason to want it, and it cannot change proved code. `$fast_math = flag` is the runtime code setting that has a use: both bodies are legal, they differ, and the call picks one. That warns with the variant count.

Ten independent runtime `$fast_math`-shaped flags on one reachable body are 1,024 compilations. The compiler warns with the count and an estimate of the extra machine code (about the size of the differing bodies times the count). It does not refuse. Twenty flags is the same warning with a much larger estimate. The warning is the cost.

### Function values

A handle is the function, not a snapshot of the caller's frame. Calling it applies the **declaration's** settings, then the caller's resource and policy chain (tightest cap, innermost policy).

When every target of a call is a handle written in a local array (a handler table), each target is compiled for each code vector that reaches that call. The call loads the vector and jumps to that slot. One warning: "this call selects a `$fast_math` body at run time." If one target has no legal body for that vector, the error is at the unproved operation, naming the target and the vector. A direct call of a known function is still a static call. A call through the table is not.

A parameter of function type, or any set the compiler cannot list, is called as the declaration was compiled. The caller's `$fast_math` does not retarget it. The call warns once and remains usable. It is not a compile error merely because the target set is open.

## Costs and warnings

If no cap, schedule, or policy frame can reach an allocation or a `parallel`, the budget pointer and the permit take are deleted and today's fast path remains. A setting nobody uses does not create a state.

Where a memory chain can reach an allocation, each allocation and each free walks the chain. Depth 32 and 100,000 allocations is 3.2 million atomic adds and 3.2 million releases, plus the 8-byte owner on each live block (about 0.8MiB at 100,000 blocks). Core admission is an atomic take and release per pool on the chain, and a stolen job runs under the **job's** chain, not the thief's current one. The worker pool is sized to the hardware (or to the largest literal cap the program contains, when that is smaller), not frozen at one startup literal.

Warnings, each once:

- Inner literal cap looser than a visible literal ancestor, at the inner line. The minimum is used.
- A scope sets `$program.max_memory`, `$program.max_cores`, or `$program.max_tasks`. Allocations or admissions in that scope take the chain.
- A loop, a `today`, or a chunk size is reached under more than one value, so it was not folded. A benchmark that exists to compare three caps gets this warning. That is the cost of the comparison, not a defect in the benchmark.
- `$fast_math` (or `$no_nan` / `$no_inf`) calls out of the module.
- A call through a finite table selects a code body at run time, with the variant count and a size estimate when more than one body is kept.
- `$parallel.off` also replays `parallel` in callees.
- `$program.max_cores` above 1 on a target with no worker threads. It runs at 1.
- Inner `$parallel.chunk_size` replaces an outer one, or an affinity intersection is empty. An empty literal intersection is an error; a dynamic empty intersection does not start the scope.

No runtime "two caps overlap" warning. The permit pools already make an outer cap bind the tree, and a runtime warning would need its own counter.

## Decisions

- **Entry points** (batch 4) must change. Resource caps and the policy settings may be set in any function or block, not only at the top of the entry file or inside `main`. A file-level setting is still the module, and a non-entry file's file-level setting is still installed only when that file is the entry. The change is required because the idiom is two functions with two caps; a single process-wide slot cannot hold both. Considered: keeping the slot and using two entry files, which is Q7 and which David rejected.
- **Calling another file's `main`** (batch 4) must change for these settings. Two mains with two caps are two frames, and the tightest cap wins. The old error assumed one process-wide value. This is an owner decision, not an approved ledger edit: replace that conflict error with the frame rule for caps and policies. The error stays for `$target` and `$build.mode`. Considered: keeping the error, which makes `lib.main()` illegal whenever the caps differ and brings back the friction the idiom removes.
- **LANGUAGE.md's scope rule does not change.** Round 1's "the next statement" reading is withdrawn. Q6 is not adopted. v5's rule that a tag does not affect a callee's own settings is narrowed, not copied: resource, policy, and schedule frames do affect callees and tasks; code settings do not cross a module.
- **D31's** "a tag does not change a result type" stays. A runtime zone does not make a literal fallible; it makes the literal a compile error so the runtime parse is written on purpose.
- **v4's** "chunk size is a minimum" and "placement is a set of cores" stay. They are not numeric ceilings. v4's error when `$parallel.max_cores` exceeds `$program.max_cores` becomes the looser-cap warning above, so a library loop capped at 8 still runs inside a program capped at 2.

`$explicit_allocation_failure` stays the allocation-policy exception to "a tag does not change a result type," and it stays module metadata. No environment variable.

## Should-fixes

Taken: module metadata distinct from frames (review M1, M2); chunk size and affinity not mixed into core caps (M3); shared budget identity (M4); one result type (M5); real allocator and scheduler costs (M6); specialization keyed by instance (S1); finite handler tables (S2); argument evaluation in the caller (S3); refined caps (S4); cooperative replay, and no runtime overlap warning (S5); `$prototype_warnings` listed; `$dewy.version` listed once; the old `$time.require_*` names not revived; wasm's one core; `$fast_math` not retargeting another module; the primary spelling is a setting in the function or block, not a wrapper whose only line is a call.

Not taken: a warning when the next sibling calls `today` (the setting covers the whole scope, so the sibling is inside it on purpose); same-package-only warnings (a warning that is not an error does not make a library patch a break, and the other package is the same situation); adopting Q6 so the tag can sit above the function (that is the context sensitivity round 1 was graded down for).

## Rejected

- The next statement, or the next declaration, owns the tag.
- A looser inner cap is a compile error for literals and a run-time refusal otherwise.
- A copied limit, so two tasks each get a fresh 48MiB after the parent returns.
- A runtime `$runtime_checks` that either skips proofs or is rejected only sometimes.
- An open function-type parameter that fails to compile because its variants were not listed.
- "Nothing else pays" once a budget exists.
