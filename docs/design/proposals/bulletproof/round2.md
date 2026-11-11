# Safety defaults and tag names

All spellings below are proposals for David's approval. "Ran" means tried on master (13eee0f66). Examples use the proposed names, tested under today's names; those marked *new* can't run yet.

## 1. The rule

- **With no tags, nothing a program can reasonably meet crashes it or quietly gives a wrong answer.** It is a compile error or a value, and crashing takes one written word: `or_throw` in `main`, or `$panic_on_unproven`.
- **What mainly stays trusted is what would make every call or float operation fallible:** memory, stack, the GPU driver, IEEE floats. Each ends with a report or an IEEE value, and each has a tag.
- **A tag's first word gives its direction:** `$no_`, `$prove_`, `$explicit_` are safer and act at compile time; `$panic_on_`, `$assume_` are less safe.

## 2. Default inventory

### A: becomes a value, proof or compile error by default

| # | Example | Today (ran) | Proposed |
|---|---|---|---|
| A1 | `input_int("n? ")`, `input_float` at end of input | `fatal:`, exit 1, invisible to `panics` | `int \| EndOfInput \| FileError \| Canceled` |
| A2 | `input("name? ")` at end of input | Gives `""`, so a "wait for quit" loop spins forever | `string \| EndOfInput \| FileError \| Canceled` |
| A3 | `read_stdin` on a read error | Partial text, as if complete (from source) | Adds `FileError` |
| A4 | `window("x" 320 200)` with no display | Report, exit 1, inside the library | `void \| WindowError` |
| A5 | `crypto.random_bytes(16)` with no entropy | `fatal:`, exit 1 (from source) | `array<uint8> \| NoEntropy` |
| A6 | `load_wav(bytes)` on a bad file; netplay's busy port | `panics`, so a compile error whose usual repair is the module-wide opt-in | A named error value (with D11's game items) |
| A7 | `p"{root}/{name}".exists` | Warning, then runs | Compile error, same fix-it (changes a decided warning) |
| A8 | `printl` with `> /dev/full` | Output lost, exit 0 | Stays `void`; a failed write is remembered and the program exits 1 with `error: could not write standard output`. A closed pipe (`\| head`) exits quietly |

Already correct, no change: index, division, narrowing, `d[k]`, `xs.first`, `int64` overflow, float to int (compile errors); `to_int`, file calls (values); a lock-order cycle, a channel wait that can never end (compile errors).

### B: stays trusted by default

| # | Example | Today (ran) | Why it stays | What a program can do |
|---|---|---|---|---|
| B1 | `xs.push(1)` forever; `fill(0 huge)` | `fatal: out of memory`, exit 1 | Every allocating call would be fallible | Bound input sizes; arenas; `$explicit_allocation_failure` |
| B2 | `f = (n:int):>int => f(n+1)+1` | `panic: stack overflow`, trace, exit 101 | Every call would be fallible | Depth limits, tail calls; `$no_stack_overflow` (future) |
| B3 | `circle(...)` when the driver refuses or texture slots run out | `fatal:`, exit 1 | Every draw would be fallible, and a game can't recover mid-frame | `$explicit_graphics_failure` |
| B4 | `sqrt(-1.0)` is `nan`; `a/b` with `b=0.0` is `inf` | IEEE values, no crash | Proving every `a/b` would wreck game math. Conversion to int is already proven | `$no_nan_or_inf` |
| B5 | `panic("x")`, `$runtime_assert` in your own module | Panic, exit 101 | You wrote the crash. Other modules' callers must opt in | `$explicit_local_panics` |
| B6 | A channel wait with a non-literal capacity | Warning; may hang | Raw channels have no certificate, so this would reject ordinary channel code | `$no_deadlocks`, `within` |
| B7 | `p(args[0]).exists` | Accepted | The user named the file; there is no base to escape | `$no_unconfined_paths` |
| B8 | The monotonic clock loses continuity (VM migration) | Designed: report and end the task | Every reading would be fallible | `$time.explicit_clock_domain` |
| B9 | Tooling: no pipes in `dewy test`; the debug web build's 5 s loop watchdog | Report and exit | Not a release-program path | Nothing needed |

### C: only matters for certification

| # | Trusted | Tag |
|---|---|---|
| C1 | A 64-bit counter growing by a bounded step can't overflow; an array fits in 2^56 bytes; a `parallel` range of 2^63 or more is capped (about 292 years at 10^9 per second) | `$prove_size_bounds` |
| C2 | Library `assert`/`unreachable` (`lib/std/graphemes.jo` holds most of them) | `$prove_library_asserts` |
| C3 | Library code keeps hidden runtime checks | `$prove_library_obligations` |
| C4 | Library raw-memory code doesn't keep arena storage | `$prove_library_arena_safety` |
| C5 | Library cleanup can't fail | `$prove_library_cleanup` |
| C6 | `lib/core/rt.jo`, the compiler, the OS | No tag: stated as the trust base. A tag no program can satisfy would be theatre |
| C7 | `serve` and `pipeline` wait only as documented | No tag: a library gate (section 5) |
| C8 | `$assume_external_wait`; an extern's `& no_effects` | `$no_assumed_waits` |

### What the common script looks like

Each program below compiles today, because `input_int` already includes `Canceled`. The A1 flip therefore adds no words. Only the end-of-input report changes, from `fatal:` to `error: EndOfInput`.

```dewy
main = () => {
    let name = input("name? ") or_throw       # just crash: report, exit 1
    let age = input_int("age? ") or_throw
    printl"{name} is {age}"
}
```

```dewy
main = () => {
    let xs = [10 20 30]
    let i = input_int("index? ") ?? 0         # end of input becomes 0
    printl(xs.get(i) ?? 0)                    # off the end becomes 0
}
```

```dewy
$panic_on_unproven                            # one line: everything unproven crashes
main = () => {
    let xs = [10 20 30]
    let i = input_int("index? ") or_throw
    printl(xs[i])                             # 9: index 9 out of bounds (length 3), exit 101
}
```

- A function with no declared result infers its failures, so helpers stay short.
- One new alias, `InputFailure = EndOfInput | FileError | Canceled`, covers a function that does declare one.

## 3. Naming grammar

| Word | Meaning | Safer? | Proof | Assume or ensure | When |
|---|---|---|---|---|---|
| `$no_X` | X can't happen in this scope | Safer | More | Ensure | Compile error |
| `$prove_X` | The compiler normally trusts X; stop trusting it | Safer | More | Ensure | Compile error |
| `$explicit_X` | X stops being silent: the source or a type must spell it | Safer | More writing | Ensure | Compile error if omitted |
| `$panic_on_X` | X compiles; if it goes wrong, the program ends with a report | Less safe | Less | Check | Run time |
| `$assume_X` | A person's claim; nothing checks it | Less safe | Less | Assume | Never checked |

Rules:

- The bare tag does what its name says. `=false` only opts a nested scope out, and no tag's meaning relies on it.
- Bundles are named for their purpose: `$prototype` (loosest), `$no_hidden_costs`, `$bulletproof` (strictest).
- Banned because they don't give a direction: `require`, `checks`, `verify`, `trusted`, `audited`, `confine`.

Cold read of the old names:

| Old name | First guess | Truth | New name |
|---|---|---|---|
| `$runtime_checks` | Adds checks, so safer | Looser than the default: it permits crashes | `$panic_on_unproven` |
| `$finite_floats` | Assumes floats are finite | Ensures it | `$no_nan_or_inf` |
| `$confine_external_paths` | A run-time sandbox | A compile-time demand | `$no_unconfined_paths` |
| `$assume_local_asserts` | Asserts don't run | They run; it concerns who may call | `$explicit_local_panics` |
| `$library.require_asserts` | The library must contain asserts | Prove them | `$prove_library_asserts` |
| `$audited_wait` | Something audited this | A person's claim | `$assume_external_wait` |

## 4. Tag table

**Where tags go:** a setting applies to the scope it's written in (module, function body or block), unless noted. A contract goes on the line above one function and covers only it, like today's `$warn_if` and `$proof`.

### `$no_*`: safer, more proof, ensured, compile error

| Tag | Meaning |
|---|---|
| `$no_nan`, `$no_inf`, `$no_nan_or_inf` (bundle) | No operation here makes that value, and values entering are proven by callers |
| `$no_deadlocks` | Tasks here can't wait on each other forever (section 5) |
| `$no_hidden_costs` (bundle) | No hidden allocation, detach, costly copy or panic |
| `$no_unconfined_paths` | Every path a file operation gets is proven a `SafePath`, whole paths included |
| `$no_assumed_waits` | `$assume_external_wait` and an extern's `& no_effects` are rejected |
| `$no_stack_overflow` (future) | Stack depth is proven bounded |

```dewy
$no_nan_or_inf
average = (total:float64 n:float64):>float64 => total/n   # error: cannot prove `/` produces no NaN
main = () => printl(average(1.0 2.0))
```

```dewy
$no_deadlocks
main = () => {
    let c = channel<int>(4)
    concurrent {
        spawn { c.send(1); c.close }    # error: this waits to send into 'c' and no certificate covers it
        printl(c.receive)
    }
}
```

```dewy
$no_hidden_costs
grow = (@xs:array<int64>):>void => xs.push(1)   # error: allocation exceeds the contract
$no_hidden_costs = false
main = () => {
    let v:array<int64> = []
    grow(@v)
    printl(v)
}
```

```dewy
$no_unconfined_paths
main = () => {
    let a = args
    if a.length =? 0 return
    printl(p(a[0]).exists)              # new error: not proven inside a base; use root.confine(...) or_throw
}
```

```dewy
$no_assumed_waits

$extern
usleep = (us:uint32):>int32
$assume_external_wait               # new error: a person's claim, rejected here; use sleep(1ms)
nap = ():>int32 => {
    $unsafe usleep(1000)
}
main = () => printl(nap)
```

```dewy
$no_stack_overflow
f = (n:int):>int => f(n+1)+1            # new error: nothing bounds how deep `f` recurses
main = () => printl(f(0))
```

### `$prove_*`: safer, more proof, ensured, compile error

| Tag | Meaning | If the code does this, compile error |
|---|---|---|
| `$prove_size_bounds` | Counters, array lengths and range sizes need real proofs | `c += 1` in a loop with no bound; `parallel` over an unbounded range |
| `$prove_library_asserts` | Each library `assert` reached must be proven | The call reaches an unproven library assert |
| `$prove_library_obligations` | Each library index, division, narrowing or refinement reached must be proven, not checked at run time | The call reaches a library line relying on a hidden check |
| `$prove_library_arena_safety` | Library raw-memory code reached inside `$allocator` must be proven not to keep the storage | `printl(xs)` inside an arena block |
| `$prove_library_cleanup` | Each library drop hook reached must be proven unable to fail | `@(m.lock)`, until the release hook is proven |
| `$prove_library` (bundle) | All four library tags | |
| `$prove_finite_float_args` (contract, above a function) | Each caller proves every float argument finite; the body may rely on it | A call with an unguarded float |

The library tags are per-reach, and only a proven library or a different call clears them. Your code can't repair these errors itself.

```dewy
$prove_size_bounds
count = (xs:array<int>):>int64 => {
    let c:int64 = 0
    loop x in xs { c += 1 }             # error: cannot prove exact integer result fits int64
    c
}
main = () => printl(count([1 2]))
```

```dewy
$prove_library_asserts
labels = (text:string):>array<string> => graphemes(text)
# new error: `graphemes` reaches assert `next_byte >= 0` (lib/std/graphemes.jo), which is not proven
main = () => printl(labels("hi"))
```

```dewy
$prove_library_obligations
size = (text:string):>int64 => text.length
# new error: reaches a hidden index check in `__grapheme_page_lookup` (lib/std/graphemes.jo)
main = () => printl(size("hi"))
```

```dewy
$prove_library_arena_safety
main = () => {
    let scratch = arena(1024) or_throw
    let count = $allocator(@scratch) {
        let xs:array<int64> = [1 2 3]
        printl(xs)                      # new error: `printl` isn't proven not to keep arena storage
        xs.length
    }
    scratch.reset
    printl(count)
}
```

```dewy
$prove_library_cleanup
bump = (m:Mutex<int64>):>void => {
    let value = @(m.lock)             # new error: the drop of the guard isn't proven unable to fail
    value += 1
}
main = () => { bump(mutex<int64>(0)); printl("ok") }
```

`$prove_finite_inputs` is gone, because its premise is stale: on master, `$no_inf` already rejects `same(to_float(s) ?? 0.0)` (ran). What remains is the argument contract, above the declaration, with a name that says floats. It needs no float refinements, which don't exist yet.

```dewy
$prove_finite_float_args
ratio = (a:float64 b:float64):>float64 => a / (b*b + 1.0)
main = () => {
    let v = to_float(read_line ?? "") ?? 0.0
    printl(ratio(v 2.0))                # new error: cannot prove `v` is finite
    if float64.min <=? v <=? float64.max printl(ratio(v 2.0))   # fine
}
```

### `$explicit_*`: safer, more writing, compile error if omitted

| Tag | Meaning | Where |
|---|---|---|
| `$explicit_copies` | A costly copy must be spelled `.copy`, a view or a move | Any scope |
| `$explicit_allocation_failure` | Every allocating function returns `T \| OutOfMemory` | Module top |
| `$explicit_graphics_failure` | `texture(...)` and other creation calls return `T \| GraphicsFailure`; draw calls stay `void`, and a lost device comes back from the window call | Module top |
| `$explicit_local_panics` | Callers in your own module must opt in too | Any scope |
| `$time.explicit_*` (17 members), `$time.strict` (all) | A one-for-one rename of `$time.require_*`: context, calendar, bounds, profile, clock_domain, clock_accuracy, clock_trust, realization, history, future_rules, location, model, extrapolation, dependence, loss, protocol, resources | Any scope |

```dewy
$explicit_copies
main = () => {
    let a:array<int64> = [1 2 3]
    let b = a                           # error: implicit costly copy of array<int64>
    b[0] = 9
    printl(a)
    printl(b)
}
```

```dewy
$explicit_allocation_failure
make = (n:int64):>int64 => {
    let xs:array<int64> = [n]
    xs.length
}
main = () => {
    let k:int64 = make(3)               # error: expected int64, found int64 | OutOfMemory
    printl(k)
}
```

```dewy
$explicit_graphics_failure
main = () => {
    let t = texture(image(1 1))
    sprite(t vec2(0 0))                 # new error: `t` may hold GraphicsFailure; use or_throw
}
```

```dewy
$explicit_local_panics
pick = (a:int b:int):>int => {
    $runtime_assert b not=? 0
    a // b
}
main = () => printl(pick(1 2))          # error: calling `pick` may panic
```

```dewy
$time.explicit_clock_accuracy
main = () => printl(today.year)         # new error: `today` gives Date | AmbiguousToday | UnknownToday
```

### Less safe

| Tag | Meaning | Direction | Where |
|---|---|---|---|
| `$panic_on_unproven` | Unproven obligations become run-time checks; calling code that may panic is allowed. A failed check reports and exits 101 | Less safe, less proof, run time. Rejected inside `$no_hidden_costs` | Any scope |
| `$prototype` | The same, plus a warning at each site. `$prototype_warnings` goes away, since `$panic_on_unproven` is the silent form | Loosest; for development only | Any scope |
| `$assume_external_wait` | "This foreign call waits only on the outside world" | Assumed, unchecked | Adapter body only, never a bundle |
| `$unsafe` | Unchanged | Assumed, unchecked | The next expression |

### `$bulletproof` (module top, strictest)

Rejected inside it: `$panic_on_unproven`, `$prototype`, `$assume_external_wait`. `$unsafe` stays allowed, as the written boundary a certifier audits.

```dewy
$bulletproof = {
    $no_hidden_costs
    $no_nan_or_inf
    $no_deadlocks
    $no_assumed_waits
    $no_unconfined_paths
    $explicit_allocation_failure
    $explicit_graphics_failure
    $explicit_local_panics
    $prove_size_bounds
    $prove_library
    $time.strict
}
```

```dewy
$bulletproof
main = () => printl(1)                  # error: allocation exceeds the contract
```

### Old items with no tag

- D10c `$verify_protocols`: removed (section 5).
- D10d `$explicit_environment_failure`: removed; input failure is always a value (A1, A2), and graphics is B3.
- D10e `$explicit_runtime_failure`: stays dropped.

## 5. Does `$no_deadlocks` guarantee no deadlocks?

**Yes, for the meaning of the word: this scope's tasks can't end up waiting on each other forever.** Today the guarantee also rests on two claims the program can't check, so I'd change this:

- **`serve` and `pipeline`:** a user tag can't produce a proof the library lacks, so the tag goes. The library must earn the certificate through a model check in the nightly gate plus a written argument for any window size, because a few fixed capacities prove nothing about the rest. A protocol without that evidence isn't a certificate, so `$no_deadlocks` rejects it. **Until the gate exists, I'd withdraw their certificates:** 24 uses in 15 files would be affected, and the guarantee is honest at once.
- **`$audited_wait`:** renamed `$assume_external_wait`, so the claim is visible where it's made. `$no_deadlocks` accepts it and `$bulletproof` doesn't.
- **What stays outside, in plain words:** a spin loop, a C call that never returns and a server that never answers. These are hangs, not deadlocks. `within` handles a wait that can be canceled. The name stays, and its documentation says: "assuming a fair scheduler, and any `$assume_external_wait` claims in scope."

## 6. Named float constants

`float64.max` is a compile error today, and the `.max` idiom only exists for integers.

| Name | `float64` | `float32` |
|---|---|---|
| `.max` (largest finite) | 1.7976931348623157e308 | 3.4028235e38 |
| `.min` (most negative finite, as `int64.min`; not C's `DBL_MIN`) | -1.7976931348623157e308 | -3.4028235e38 |
| `.min_positive` (smallest normal) | 2.2250738585072014e-308 | 1.1754944e-38 |
| `.min_subnormal` (smallest above zero) | 5e-324 | 1e-45 |
| `.epsilon` (gap above 1.0) | 2.220446049250313e-16 | 1.1920929e-7 |
| `.max_exact_int` (every integer up to here is exact) | 2^53 | 2^24 |
| `.inf`, `.nan` | | |

`INF` and `NAN` go away (5 uses in 3 files).

```dewy
if float64.min <=? x <=? float64.max same(x)              # finite: rejects NaN and both infinities
if is_finite(x) same(x)                                   # the same fact
if float64(int64.min) <=? x <? float64(int64.max) int64(x)   # the top rounds to 2^63, so `<?` is exact
```

- The guard on the first line already proves `$no_nan` and `$no_inf` when written with literals (ran). Only the member lookup is new.
- `is_finite` isn't recognized as a guard today (ran), and should be.
- Fix-its stop suggesting `1e300` and `9.2e18`.

## 7. Cost

**Standard library:**

- `input`, `input_int`, `input_float`, `read_stdin`, `window`.
- `random_bytes` and its 23 callers in `crypto`, `invite`, `net` and `rtc`.
- 21 panics in audio, vorbis, image and netplay, plus D11.
- About 5 new error types.
- Of 25 `__environment_failure` sites, 3 go away, 1 stays for the test runner and 21 stay for graphics.

**Tests and examples:**

- `input*`: about 5 files, which already write `or_throw`.
- `window(`: 30 uses in 28 files gain `or_throw`.
- Joined paths: 3 mentions in `tests/test_contained_paths.py` flip; no example joins paths.

**Renames, one mechanical commit:**

- `$runtime_checks`: 2,403 uses in about 1,850 files, mostly tests and the compiler.
- `$no_assumed_bounds` 66, `$finite_floats` 30, `$assume_local_asserts` 29, `$confine_external_paths` 26, `$audited_wait` 24, `$prototype_warnings` 4.

**Compile speed:** I expect about zero by default; this is reasoning, not a measurement.

- No new analysis runs by default; the path check only changes severity.
- Implementers gate it on instruction counts for the flagship panel.
- `$prove_library_*` costs only when on, and can't be estimated until built.

**Risks to game code:**

- **21 of 29 examples say `$runtime_checks`.** With the name changed, that is 72% of programs saying `$panic_on_unproven`. I removed it and checked each one (first errors only):

  | Examples | What they hit |
  |---|---|
  | 6 | Compile already, so delete the tag |
  | 2 | `ui_begin` (D11a) |
  | 2 | `add_box`, whose panic on 4 fixed points should go |
  | 11 | Fixed-width proof gaps (10) and one broadcast shape, a separate proof job |

- **Avoided:** fallible draw calls (B3), float proofs by default (B4), allocation unions (B1).
- **Small:** one `window(...) or_throw` per game, one `or_throw` per asset load.

## 8. Approvals and discoveries

**Approvals (each is reversible):**

| Question | Recommendation | Unblocks |
|---|---|---|
| The grammar and renames in sections 3–4 | Accept | Rewriting D10 and `lib/directives.dewy` |
| `$panic_on_` or `$crash_on_` | `panic`, matching `panic` and `& no panics` | The rename commit |
| A7: joined paths become errors (changes a decided warning) | Yes | Closing a path escape by default |
| A4 and A8: `window` as a value; `printl` failure at exit | Yes | Honest default paths |
| Withdraw `serve`/`pipeline` certificates until the gate exists | Yes | An honest `$no_deadlocks` today |

**Found, not acted on:**

- `let r = grow(3); printl(r.length)` compiles under `$explicit_allocation_failure` in `main = ():>void`, even though `grow` now returns a union (ran). This looks like a gap.
- The `lib/directives.dewy` comment and D10b still describe `$no_inf` entry values as assumed. That is stale.
