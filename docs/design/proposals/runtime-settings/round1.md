# Runtime-chosen settings

Turn this on and the entry file you already wanted compiles. Each setting belongs to the next construct, the same way `$parallel.off` does. `laptop()` runs the program at 2 cores, `server()` runs it at 8, and a later call does not keep the earlier cap. No new syntax.

```dewy
$program.max_cores = 2
laptop = () => run()

$program.max_cores = 8
server = () => run()

main = (argv:array<string>) => {
    if (argv.get(0) ?? "laptop") =? "laptop" laptop() else server()
}
```

`run` sees the cap of whichever function was called. After that call returns, the cap is gone. A task started inside the call keeps the cap it was started with. A setting whose value is not a literal is the same mechanism, written where the value exists:

```dewy
play = (cores:int) => {
    $program.max_cores = cores
    run()
}
```

## Classes

A setting is in exactly one class. The class decides whether a call can choose it, what the compiler emits, and when it warns. Names already in the language and names already proposed are both here; a rename that is still open (`$time.zone` / `$program.time_zone`, and the rules and source beside them) does not change the class.

| Setting | Class | What a call does with it |
|---|---|---|
| `$program.max_cores`, `$program.max_memory`, `$program.max_tasks` | Resource cap | The construct's dynamic extent runs under that cap. See the cap rules. |
| `$parallel.max_cores`, `$parallel.max_concurrent`, `$parallel.chunk_size`, `$placement.cores` | Ceiling | "At most this." The active value is the tightest ceiling in force. One body. |
| `$parallel.off`, `$parallel.scheduler`, `$placement.device` | Schedule | The work this construct runs is scheduled that way, including work it calls and tasks it starts. One body; the scheduler reads the frame. |
| `$time.zone`, `$program.time_zone`, `$time.rules`, `$program.time_zone_rules`, `$time.zone_source`, `$program.time_zone_source`, `$time.gap`, `$time.fold` | Policy | Innermost frame wins. Read when a zone or a calendar arithmetic needs it. One body. |
| `$runtime_checks`, `$prototype`, `$fast_math`, `$no_nan`, `$no_inf`, `$finite_floats`, `$no_assumed_bounds`, `$no_hidden_costs`, `$explicit_copies`, `$explicit_cancellation`, `$confine_external_paths`, `$assume_local_asserts`, `$no_deadlocks`, `$time.strict`, `$time.only_strict_today`, `$time.no_assumed_*`, `$time.require_range` | Code | The compiler emits a body per vector that actually reaches the function. A vector that is illegal (an unproved index with checks off, an implicit copy under `$explicit_copies`, a deadlock under `$no_deadlocks`) does not get a body: the call that needed it is a compile error naming the obligation and the setting. |
| `$target`, `$build.mode`, `$dewy.version`, `$supported_targets` | Build | Fixed for the build. A prefix that would choose one at run time is a compile error. Separate entry files, or `--target` / `--release`, remain the way to build two of them. |
| `$explicit_allocation_failure`, `$default_row`, `$bulletproof` (because it includes the allocation policy) | Module signature | Unchanged. They change result types or the effect row of functions declared in the module, so they stay a module header. A prefix on a function is an error that points at the header. |
| `$memory.layout`, `$unsafe`, `$extern`, `$intrinsic`, `$audited_wait`, `$send`, `$sync`, `$export`, `$shadowable`, `$test`, `$named`, `$dewy.version` on a module | Declaration or marker | Unchanged. Not a call policy. `$dewy.version` is also build-fixed per module. |

Bundles expand to their members and each member follows its own class. `$no_hidden_costs` on a function is the code-class members it already has. `$bulletproof` does not become a per-call switch.

`$parallel.off` does not need a second copy of the function. Parallel work is already required to be correct when it runs one item at a time. The frame tells the scheduler to do that. `$runtime_checks` does need another copy when an unproved operation is actually reached: the checked body contains the test, and the plain body must not.

## Rules

**Attachment.** A prefix binds to the next construct. Comments and blank lines do not split a prefix list, and several settings in a row share one construct. This is the placement already proposed for every tag.

- The next construct is a function, and the settings sit immediately above it: they govern calls to that function. David's idiom is this case, including the first function in the file.
- The settings are at file start, or immediately after the opening imports, and the next declaration is not a function (a type, a value, or an import between the settings and the code): they are the module header.
- Inside a body, the prefix governs the next statement. A call, a loop, a `parallel`, or a block is enough. Two statements under one policy sit in a block, because the prefix never reaches backward and never covers a later sibling.
- A setting whose target cannot carry it (`$runtime_checks` immediately above a type, `$memory.layout` above a function) is an error that names a legal target.

The header of the entry file is the outermost frame. It is in force for top-level statements and for every call that does not set its own. The header of any other file is installed only when that file is the entry, which is the existing rule for a library's test `main`. Importing a file never installs its header.

A prefix on an ordinary function is installed when that function is called, whether or not its file is the entry. That is the change that makes `laptop` / `server` work, and it is why a library function can carry a cap without picking the zone of every importer.

**Dynamic extent.** Entering the construct evaluates the prefix (literals are already checked), pushes a frame, runs the construct, and pops the frame on every exit. Arguments of a prefixed call are inside the frame. The frame covers:

- the construct's own code;
- functions it calls, directly or not;
- tasks it starts. The task keeps the frame's resource and policy values after the caller returns, until the task itself finishes. Its code is the variant of the spawn site.

A function value does not capture a frame. The caller's frame is the one that applies. If that caller needs a code variant the function does not have, the indirect call is a compile error naming the missing variant.

**Caps.** `$program.max_cores`, `$program.max_memory`, and `$program.max_tasks` are the cap for that extent, not a hint.

- No enclosing program cap: the call runs at what it wrote.
- An enclosing program cap that is higher: the inner cap wins. `server` at 8 may call a handler whose program cap is 2; the handler runs at 2.
- An enclosing program cap that is lower, and both numbers are literals: compile error at the call, naming both lines. A function that says its cap is 8 cannot be called from a function whose cap is 2. Fix it by lowering the inner cap, raising the outer one, or deleting the inner program cap and using a `$parallel` ceiling.
- The outer cap is a runtime value, so the compiler cannot compare: entering the inner construct checks. If the inner cap is within the outer one, it wins. If it is higher, the construct does not start. The failure is an ordinary obligation failure: a literal that is already too big is a compile error, and an unproved dynamic value follows `$runtime_checks` like any other unproved bound. After `if cores <? 1 exit(2)`, the value is proved and the push is free.
- Memory is accounted to the extent, not to the whole process. Allocations made while the frame is current, and allocations of tasks that frame started, count against it. A fresh call starts at zero even if the caller is holding a large cache. A copy into the call counts at entry; if that copy is already over the new cap, the call does not start. That is the "already exceeded" case. Bytes a task keeps allocating still count against the budget it captured and against any outer entry-file ceiling, so two overlapping handlers cannot each spend the process ceiling.
- Going past a memory or task cap follows the allocation policy that already exists. With nothing else set, it is an environmental failure and the program ends. Under `$explicit_allocation_failure` it is `OutOfMemory`, because that module policy already changed allocation's type. This design does not add a second switch.
- `$parallel.*` ceilings and `$placement.cores` are maximums. The tightest one wins, and a loop maximum above the program cap stays legal: "at most 8" is still true when the program allows 2. The compiler warns, once, at that loop.
- A thread blocked in a system call does not consume a core, as already specified. `available_cores`, read inside an extent, is the minimum of the hardware, the affinity mask, and the caps and ceilings in force there.

**Policies.** A zone, a rule pack, a zone source, a gap policy, or a fold policy on an inner construct replaces the outer one for that extent. It does not change the caller's frame, and a library header still cannot set the importer's default. A literal zone name is checked while compiling. A runtime zone is a `Zone` already parsed with `zone(text)`, so a bad name is the caller's `ValidationError` and not a new failure of the setting. A `zoned` literal whose zone frame is a literal is checked while compiling, as a constant is today. A `zoned` literal whose zone frame is chosen at run time is parsed when the construct runs, and a wall time that does not exist is the same failure as `zoned(text)`. Rule data beyond the pack shipped with Dewy is linked when a prefix names it; a call that needs the host database says so with `$time.zone_source = 'host'`.

**Code variants.** The compiler walks the call graph from each prefix. Two calls that agree on every code-class setting share a body. A function reached under two vectors is compiled twice, and only if the instructions differ are both copies kept. Direct calls are static: `checked()` calls the checked body, `plain()` calls the plain one, and the branch in `main` is the only runtime choice. An unproved index in a plain vector is a compile error at the index, with a note pointing at the prefix that required the plain body. That is the same obligation rule as today. It is not possible to execute an unproved index with checks off, including from a test harness.

A runtime value for a code-class setting (`$runtime_checks = flag` above a call) asks for every value the flag can take. Each of those bodies must be legal, and the call picks one. The compiler warns at that call.

**Build settings stay fixed.** `$target` and `$build.mode` are the binary. Choosing them from `argv` is a compile error whose fix is a second entry file or the existing command-line override. `$dewy.version` stays per module.

**One setting, one construct.** The duplicate-setting error stays, per construct rather than per file. `laptop` and `server` may each set `$program.max_cores` because they are different constructs. The module header may also set it: that is the outer frame, not a second setting on `laptop`.

## Costs and warnings

Pushing a frame is one write on the running task. An allocation consults the memory frames above it, a core-admission consults the core frames, and `today` consults the zone frame. Nothing else pays. Depth is the number of active frames on that task, which is the nesting of these prefixes, not the depth of ordinary calls.

Code variants are demand-driven. A setting nobody prefixes does not create a vector. The walk is a fixed point over functions and direct calls, indexed by function and by the settings in the vector: O(V · (F + E)) where V is the number of distinct vectors that actually reach a function. In the harness and the `fast_math` kernel V is 2. Indirect calls and function values are compiled for the vectors of the calls the compiler can see; a call it cannot tie to a variant is the error above, not a guess.

Warnings, each once at the site that caused it:

- A `$parallel` ceiling, a chunk size, or a placement is looser than the program cap in force. The tighter one is used.
- A `parallel` loop or a `today` is reached under more than one value, so the compiler did not constant-fold that value into the loop or the call.
- A function was emitted twice and the copies differ, naming the settings. Identical copies are merged and do not warn.
- A prefix value is computed at run time and selects a code variant.
- `$parallel.off` will also order `parallel` inside functions this construct calls.
- A task with one core cap is still running when another extent with a different core cap starts. Each extent keeps its own cap; the process can use the sum.
- A second zone rule pack is linked, or a prefix reads the host zone database.

No warning for a program cap that is simply doing what its line says. `laptop` at 2 is not a performance accident.

## What changes from earlier decisions

- **Entry points** (batch 4). Program settings may prefix any function, block, loop, or call, not only the top of the entry file and `main`. A header on a non-entry file still applies only when that file is the entry. A prefix on a function applies whenever the function is called. Considered: keeping the header as the only legal place, which is Q7 and which makes the idiom illegal.
- **Calling another file's `main`** (batch 4). Withdrawn for resource, ceiling, schedule, policy, and code settings. `lib.main()` runs under `lib.main`'s prefixes for that call and then restores. The compile error remains for a non-entry file setting `$target` or `$build.mode`. Considered: a call-site override that ignores the callee's tags, which hides the disagreement instead of running it.
- **D4 Q6**, still open, keeps prefix placement and the header position after imports. It loses "program settings are fixed when compiling" and "a program tag on an ordinary function is an error." A list in header position whose next declaration is a function is that function's prefix, not a module header. Otherwise the first function of the idiom would silently become the process default and the second would be the only real prefix.
- **D4 Q7** is rejected. Separate entry files stay legal and stay the right tool for a different target or build mode. They are not required for a different core cap.
- **D31 Q2**, still open, keeps "a library header does not pick the importer's zone." It loses "a zone setting anywhere but the header or `main` is an error." A zone prefix on a call is the way a report runs in that user's zone.
- **v4's error** when `$parallel.max_cores` is above `$program.max_cores` becomes the ceiling warning above. Two `$program` caps where the inner number is higher stay an error.
- **LANGUAGE.md's** "a setting holds for the whole scope no matter where in the scope it sits" gives way, for these settings, to "a prefix governs the next construct." A runtime value has to have a construct in front of it, and one attachment rule covers literals too. An inner scope may still set the same setting the outer scope set; that is a nested frame, not a duplicate.

`$explicit_allocation_failure` stays the one tag that changes a result type, and it stays a module policy. No environment variable is added. `DEWY_MAX_CORES` stays deleted.

## Considered and rejected

- **The process is sealed by the first call.** That was the startup-profile reading. It makes `laptop()` then `server()` a compile error, and it gives a prefix on a function a different meaning from a prefix on `main`. The consistency failure is the reason that reading was withdrawn; the fix is to make the call ordinary, not to forbid the call.
- **Silent minimum of two `$program` caps.** `inner` saying 8 and `outer` saying 2 would run at 2, and the inner line would be a lie. A compile error keeps both lines true or absent.
- **Lexical only.** The prefix would cover `parallel` written inside `laptop` and not the `run()` it calls. The idiom would not do what it says.
- **A new `with` or `using` form.** The prefix list is that form. Another keyword would be a second way to spell the same attachment.
- **Fat binaries** so `$target` could follow `argv`. Two targets are two builds. The compiler already refuses to pretend otherwise.
- **Per-operation tests** of `$runtime_checks` instead of a second body. Every index would branch, including in the plain program, which is the cost the plain program exists to avoid.
- **Memory as a process high-water mark.** A handler capped at 32MiB would fail because the server's cache is larger than 32MiB. The cap is the handler's own allocations.
- **Popping a task's cap when its parent returns.** The brief's outliving task would spend the caller's cores. The task keeps the frame it was started with.
