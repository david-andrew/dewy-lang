# Settings and Safety Levels

> [Generated coverage](/status/#ref-settings) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

Settings are metatags written in the source. There are no compiler flags for them and no environment variables: the command line sets only the build mode and the target. A setting applies to a file, a function or a block, and the program's entry file holds the settings for the whole program.

## Writing a Setting

A setting is a metatag on a line of its own.

| Form | Meaning |
|---|---|
| `$name` | a boolean setting, turned on |
| `$name = true` | the same |
| `$name = false` | turned off, for example to opt a nested scope out |
| `$name = 'value'` | a valued setting; the value is a name in quotes |
| `$name.member = …` | a member of a setting group: `$time.zone`, `$build.mode`, `$program.max_cores` |

Where it goes decides what it covers:

- **File:** at the top of the file, before declarations (optionally after the initial imports). It covers the whole file.
- **Function:** at the top of the function's body.
- **Block:** inside the block, before its statements.

A scope sets each setting at most once. A file setting written below a declaration is an error that says where it belongs.

<!-- dewy-example: {"mode":"run","stdout":"1.0\n"} -->
```dewy
$runtime_checks
half = (x:float64):>float64 => {
    $no_nan
    x*0.5
}
main = () => {
    $runtime_checks = false
    printl(half(2.0))
}
```

<!-- dewy-example: {"mode":"reject","diagnostic":"a file setting belongs at the top of the file"} -->
```dewy
first = (xs:array<int>):>int => xs.get(0) ?? 0
$runtime_checks
pick = (xs:array<int> i:int64):>int => xs[i]
```

Construct tags are different: `$extern`, `$export`, `$intrinsic`, `$test` and a loop label go immediately before the construct they mark, and `$unsafe` covers only the next expression or declaration. See [Compile-Time Facilities and Metatags](compile-time.md#metatags).

### Inheritance

Runtime settings, such as `$time.zone` or `$program.max_cores`, govern the scope's calls, everything those calls reach, and the tasks they start. Leaving the scope restores the caller's settings, and a task keeps the settings it inherited. Code settings, such as `$runtime_checks` and the float settings, are inherited by direct calls too, unless the callee sets its own: a `pick` with no settings, called from a `$runtime_checks` scope, compiles with runtime checks. A concrete function in another module keeps its own numeric settings, with a warning when the caller asks for different ones.

A setting read as an expression gives its value. Read in a parameter's default, it is read where the function is called, so a library can take the caller's setting:

<!-- dewy-example: {"mode":"run","stdout":"UTC\nnone\n"} -->
```dewy
zone_name = (zone:string|none=$time.zone) => zone ?? "none"
show = () => {
    $time.zone = 'UTC'
    printl(zone_name())
}
show()
printl(zone_name())
```

## The Safety Ladder

An *obligation* is a fact an operation needs: an index in bounds, a nonzero divisor, a value that fits a narrower integer, an argument meeting a refined parameter. A proven obligation costs nothing. The safety settings decide what happens to an unproven one, and how much else the code must make explicit. From loosest to strictest:

| Setting | Unproven obligations | Also |
|---|---|---|
| `$prototype` | checked at run time | a `prototype: …` warning at each site; `$prototype_warnings = false` silences them |
| `$runtime_checks` | checked at run time, silently | a failed check reports and exits with status 101 |
| (default) | compile errors with the reason and a fix | no hidden traps |
| `$explicit_copies` | compile errors | an implicit costly copy is an error: write `.copy` |
| `$no_hidden_costs` | compile errors | `$explicit_copies`, no runtime checks, and functions default to `no allocates & no panics` |
| `$explicit_allocation_failure` | compile errors | a function that may allocate returns `T \| OutOfMemory` |

`$runtime_checks = false` is the default. `$runtime_checks` takes a literal Boolean, never a runtime flag. Obligations of `$assert` and of `$proof` functions are never deferred to run time.

### Default: proven or rejected

<!-- dewy-example: {"mode":"reject","diagnostic":"cannot prove index is in bounds: missing lower and upper bounds"} -->
```dewy
pick = (xs:array<int> i:int64):>int => xs[i]
printl(pick([1 2 3] 1))
```

The error names the missing relation and shows the bounds it knows. Handle the case as a value (`xs.get(i) ?? 0`), add a guard (`if 0 <=? i <? xs.length`), refine the parameter, or check it explicitly with `$runtime_assert`. See [Refinements, Effects, and Safety](refinements-and-effects.md).

### `$runtime_checks` and `$prototype`

The same function compiles under `$runtime_checks`. A failing check names the requirement and the values it saw:

<!-- dewy-example: {"mode":"run","stdout":"2\n","exit":101,"runtime_checks":true} -->
```dewy
pick = (xs:array<int> i:int64):>int => xs[i]
main = () => {
    printl(pick([1 2 3] 1))
    printl(pick([1 2 3] 5))     # panic: index 5 out of bounds (length 3)
}
```

`$prototype` compiles the same way and warns at each site while compiling, for development. `dewy check --obligations file.dewy` lists every obligation that compiles to a runtime check, with the setting responsible.

### `$explicit_copies`

An implicit copy of runtime-sized mutable storage (a dynamic array, a record or container with a mutable heap payload, a closure environment) is an error. Write `.copy`, borrow with a view, or transfer the value at its last use.

<!-- dewy-example: {"mode":"reject","diagnostic":"implicit costly copy of array<int>"} -->
```dewy
$explicit_copies
main = () => {
    let a = [1 2 3]
    let b = a
    b.push(4)
    printl(a b)
}
```

<!-- dewy-example: {"mode":"run","stdout":"[1 2 3] [1 2 3 4]\n"} -->
```dewy
$explicit_copies
main = () => {
    let a = [1 2 3]
    let b = a.copy
    b.push(4)
    printl(a b)
}
```

### `$no_hidden_costs`

The strict lane, a library bundle (`lib/directives.dewy`): `$explicit_copies`, `$runtime_checks = false`, `$prototype = false`, and a default effect row of `no allocates & no panics` for each function without a row of its own. Code in it has no hidden allocation, costly copy or runtime check, and calls no code that may panic. `$runtime_checks` and `$prototype` are errors inside it. A function that needs more opts out with `$no_hidden_costs = false` at the top of its body, or declares its own row. Allocation is made explicit with a fixed arena:

<!-- dewy-example: {"mode":"run","stdout":"3\n"} -->
```dewy
$no_hidden_costs

count = ():>int64 | OutOfMemory => {
    let a = arena(4096) or_throw
    let n = $allocator(@a) {
        let xs:array<int64> = [1 2 3]
        xs.length
    }
    n
}
main = ():>void => {
    $no_hidden_costs = false
    printl(count())
}
```

<!-- dewy-example: {"mode":"reject","diagnostic":"allocation exceeds the contract"} -->
```dewy
$no_hidden_costs
gather = (xs:array<int64>):>int64 => {
    let out:array<int64> = []
    loop x in xs { out.push(x) }
    out.length
}
```

### `$explicit_allocation_failure`

A module policy, written alone at the top of a module. Each function in it that may allocate returns `T | OutOfMemory` instead of ending the program when memory is refused. A value that may be `OutOfMemory` must be handled before use: pass it on with `or_throw`, test it, or fall back with `??`.

<!-- dewy-example: {"mode":"reject","diagnostic":"this value may be OutOfMemory"} -->
```dewy
$explicit_allocation_failure
build = (n:int64):>array<int64> => [loop i in [0..n) i]
main = () => {
    let xs = build(3)
    printl(xs.length)
}
```

<!-- dewy-example: {"mode":"run","stdout":"[0 1 2]\n"} -->
```dewy
$explicit_allocation_failure
build = (n:int64):>array<int64> => [loop i in [0..n) i]
main = () => {
    let xs = build(3) or_throw
    printl(xs)
}
```

### `$bulletproof`

The strictest bundle, at the top of a module: `$no_hidden_costs`, `$explicit_allocation_failure`, `$explicit_cancellation`, `$finite_floats`, `$no_deadlocks`, and each assumption the compiler can be told not to make (`$no_assumed_bounds`, `$assume_local_asserts = false`, `$confine_external_paths`).

## Other Code Settings

| Setting | Effect |
|---|---|
| `$no_nan` | each float operation that could produce a NaN is an obligation |
| `$no_inf` | each float operation that could produce an infinity is an obligation |
| `$finite_floats` | a bundle of `$no_nan` and `$no_inf` |
| `$fast_math` | permits reassociation and contraction (the backends do neither yet) |
| `$no_deadlocks` | the program's channel waits must be proven free of deadlock (see [Concurrency](concurrency.md)) |
| `$explicit_cancellation` | `Canceled` may not pass through a `??` or collector silently (see [Concurrency](concurrency.md)) |

Values entering a `$no_nan` or `$no_inf` scope are not assumed to obey it. Guards prove the obligations; an unproven one follows the safety settings like any other.

<!-- dewy-example: {"mode":"reject","diagnostic":"cannot prove `/` produces no NaN under `$no_nan`"} -->
```dewy
$finite_floats

ratio = (a:float64 b:float64):>float64 => {
    if 1.0 <=? b and float64.min <=? a <=? float64.max return a/b   # proven
    return 0.0
}
average = (total:float64 n:float64):>float64 => total/n           # unproven
```

<!-- dewy-example: {"mode":"run","stdout":"3.0\n","exit":101,"runtime_checks":true} -->
```dewy
$finite_floats
average = (total:float64 n:float64):>float64 => total/n
main = () => {
    printl(average(9.0 3.0))
    printl(average(1.0 0.0))    # panic: produced an infinity under `$no_inf`
}
```

`$fast_math = flag` permits selection at run time; identical bodies are merged.

## Bundles

A bundle is one metatag for several settings, defined at module level. Writing it at the top of a scope holds every setting in it throughout that scope. A setting inside that contradicts the bundle is an error; `$name = false` opts a nested scope out of the whole bundle first.

<!-- dewy-example: {"mode":"reject","diagnostic":"`$runtime_checks` is not allowed inside `$careful`"} -->
```dewy
$careful = {
    $explicit_copies
    $runtime_checks = false
}
$careful
first = (xs:array<int>):>int => {
    $runtime_checks
    xs[0]
}
```

A bundle may include other bundles by naming them, before or after its own definition. `$default_row = <effect row>` in a bundle gives that row to each function in its scope without a row of its own. Members that disagree, two default rows, a bundle that includes itself and an unknown member are errors. No bundle may hold `$unsafe`.

## Program Settings

`$target` and `$build.mode` may be set only by the program's main file; a module states the targets it accepts with `$supported_targets`. `$program.max_cores` and `$time.zone` in another module's header apply only when that module runs as the entry. `$dewy.version` is per module.

| Setting | Meaning |
|---|---|
| `$target = 'aarch64-linux'` | the target; `$target.arch` and `$target.os` are read from it |
| `$build.mode = 'release'` | `'debug'` (the default) or `'release'` |
| `$program.max_cores = 2` | the default number of cores parallel work may use, the caller included |
| `$time.zone = 'America/New_York'` | the default zone (see [Time and Dates](time-and-dates.md#the-scopes-zone)) |
| `$dewy.version = '0.1.0'` | which Dewy the module's bare names mean; per module, not inherited |

### Target and build mode

`$target`, `$target.arch`, `$target.os` and `$build.mode` read as constants. A condition comparing them with string literals is decided while compiling, and its `if` compiles only the live arm (see [Modules and Imports](modules-and-imports.md#conditional-imports)). `$supported_targets` lists the targets a module accepts.

<!-- dewy-example: {"mode":"run","stdout":"[0 1 4 9]\nrelease build\n"} -->
```dewy
$program.max_cores = 2
$build.mode = 'release'
main = () => {
    printl([parallel i in [0..4) i*i])
    if $build.mode =? 'release' { printl("release build") } else { printl("debug build") }
}
```

`--release`, `--debug` and `--target` on the command line override the file, with a warning naming both when they differ. Any other setting given on the command line is an error.

`$program.max_cores` at the top of a function or block caps that dynamic extent instead; a nested cap only tightens the one already in force. `$program.max_cores = 1` runs parallel work on the caller.

## Per-Environment Settings

Settings are part of the source, so an environment is chosen in the source too: either a separate entry file per environment that sets its tags and then imports and calls the program, or one entry file with a function per environment, which `main` chooses between at run time.

<!-- dewy-example: {"mode":"run","stdout":"UTC\n","args":["utc"]} -->
```dewy
run = ():>void => printl($time.zone ?? "no zone")
local = ():>void => {
    $time.zone = 'America/New_York'
    run()
}
universal = ():>void => {
    $time.zone = 'UTC'
    run()
}
main = (argv:array<string>):>void => {
    if (argv.get(1) ?? 'local') =? 'utc' {universal()} else {local()}
}
```

Project flags are ordinary constants in a build module that the entry module overrides.
