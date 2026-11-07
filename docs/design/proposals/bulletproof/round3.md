# Safety defaults and tag names, round 3 (D10, D11c, library results)

Programs: `~/dev/tmp/rev-1107/safety/` (`s01`–`s16` use the revised design; `*_today.dewy` compile on master d0f9714ef; `probe/` holds the one-line checks quoted below). Every name this round adds or changes is provisional until the cold read (table at the end).

## BLUF

- **Joined paths become a compile error by default (Q3 a), and the common safe loop still needs nothing.**
  - `dir.list` gives `FileName`s: one component, no `/`, never `.`, `..` or empty. Joining one to its folder is safe by construction, and so are `glob` and `walk` results.
  - What still needs confinement is text from outside: archive entries, uploads, typed input, network and config data. `base.confine(text) or_throw` or `FileName(text) or_throw` fixes it in one call.
- **No tag changes a result type.** The strict time tag now makes `today` a compile error that points to `strict_today` (`$time.no_unchecked_today`). Five more tags that change types are listed with their fixes. `$explicit_allocation_failure` stays the one flagged exception.
- **`$bulletproof` restated with the tested names.** It compiles `printl(1)`: printing scalars doesn't allocate, and an `OutOfMemory` in a result counts as declaring the allocation.
- **Randomness:** there is no bare `random_bytes` to pick by habit. Use `fast_random_bytes` or `secure_random_bytes`, the latter a `secret`. Add `secure_token`. `=?` on secrets is constant-time. `crypto.random_bytes` is removed. `random([lo..hi))` replaces `random_int`, and takes float ranges too.
- **Useful results without `;` noise:** a `$discardable_result` contract on library calls (`make_dirs`, `write_text`, `append_text`, `Atomic.add`, …). It changes the multi-expression rules, so the owner decides; recommended.
- **`@(m.lock)` means `@(m.lock())`.** Inside a group, zero-argument calls happen as they do everywhere else. Bare `@m.lock` stays the handle.
- **Library names:** `starts_with`/`ends_with`, one file-operation name for both the method and function forms, `start_process` for the process call, `find_last`, `append_text`, `set_permissions`.

## 1. Findings and what this round does

| Finding (source) | Resolution | § |
|---|---|---|
| Q3 (a) breaks the `dir.list` loop (dogfood 02, must-fix 6) | `FileName` from listings; the fix-it names the real base | 3 |
| Restate `$bulletproof` with tested names (must-fix 5, dogfood 11) | Restated; `printl(1)` compiles | 4 |
| `$panic_on_unproven` in D11c (must-fix 5, audit 11) | Replacement text | 10 |
| Constant-time `=?`, remove `crypto.random_bytes` (must-fix 7) | Both; no bare `random_bytes` | 6 |
| Missing `$allow_unproven_narrowing` | Added | 4 |
| `$count_local_asserts_as_panics` read only "roughly, 2/3" | Replaced by `$prove_local_asserts` | 4 |
| No tag owns parallel ranges ≥ 2^63 or array sizes | `$prove_no_counter_overflow` owns all three | 4 |
| `make_dirs` gives `true`, `write_text` a count (should 12) | Both give back the path, plus the `;` rule | 7 |
| `endswith` (should 13) | `starts_with`/`ends_with` and a naming pass | 8 |
| No float random; `random_int` breaks D15d (should 14) | `random(range)` | 6 |
| `$finite_floats` unusable on records (should 15) | Fields declared in scope are finite; guard on locals | 5 |
| `float64.min` fix-it, rational-literal error, `is_finite` in the example (should 16) | Error texts; example uses `x.is_finite` | 5 |
| `printl` of scalars under `$bulletproof` (should 21) | Doesn't allocate | 4 |
| `to_float("nan")` succeeds; file errors without a path (should 11) | Rejected by default; errors carry `path` | 8 |
| `read_line` gives `none`, `input` gives `EndOfInput`; no stdin iterator (nice 23) | `EndOfInput`; `stdin_lines` | 8 |
| Secure bytes aren't secret; no URL-safe token; `rng` seed (nice 22) | `secret`; `secure_token`; `rng` with no argument | 6 |
| `is_close` (nice 24) | Added | 5 |
| Library obligations: can the caller fix them? (audit 11) | Argument-dependent ones propagate; internal ones don't | 4 |
| Audit 1: tags never change result types | Rule applied to every tag | 2 |
| Audit 6: `@(m.lock)` vs `@(acct.lock())` | Rule for `@(x.f)` | 9 |
| Audit 11: proposals still using old names | Inventory and current names | 11 |
| Parallel reviser: `;` after useful results | `$discardable_result` | 7 |
| Parallel reviser: process `spawn` vs `group.spawn` | `start_process` | 8 |
| Parallel reviser: `Atomic.add` traps | Counter rule, any proven-bounded step | 4 |

Not fixed here, on purpose: the HTTP client, `select`, Ctrl-C and `max_cores` (parallel topic); `10min`, formatting and time literals (time and UI topics).

## 2. A metatag never changes a result type

**Rule.** A stricter tag makes the lax call a compile error whose fix-it names a stricter function, with a type that never changes. A looser tag (`$allow_…`) turns compile errors into run-time checks and never changes a type either. A refinement a tag adds (§5) is a subtype: code written for plain `float64` accepts it, so it is not a type fork.

**Sweep of every tag that changes a type today, or did in a proposal:**

| Tag | Changes today | Under the rule |
|---|---|---|
| `$time.handle_uncertain_today` (D10; v5's `require_clock_accuracy`) | `today` becomes `Date \| AmbiguousToday \| UnknownToday` | `today` stays `Date`. Under **`$time.no_unchecked_today`**, `today` (and `age`'s default `on=today`) is a compile error naming `strict_today` (decided, D15e). `s11_today.dewy` |
| `$time.require_clock_domain` (v5 row 5) | `reading - reading` becomes `Duration \| ClockDiscontinuity \| DomainMismatch` | `-` stays `Duration`. The tag makes it an error naming a strict companion (provisional `strict_elapsed(start end)`, for the time reviser) |
| `$time.require_range` (time.md, Overflow) | Removes the overflow assumption, so `t + d` is in question | `+` stays `Instant`. The tag makes an unproven `+` an error naming `checked_add`, which exists (`lib/time/core.dewy:520`). See the prefix question in §12 |
| `$time.require_resources` (v5 row 17) | "exposed … fallibility", i.e. loaders gain error members | Each loader keeps its type. The tag names a strict companion per call (time reviser) |
| `$time.gap`, `$time.fold` (time.md, Scope defaults) | Without them, `zoned + 1day` is `ZonedDateTime \| Gap \| Ambiguous`; with them, plain | Recommend: `+` always gives `ZonedDateTime`, defaulting to `'preserve_displacement'`/`'earlier'` (Temporal's "compatible"). The tags only pick other values. The careful union comes from explicit arguments, `z.add(1day gap='reject' fold='reject')`, and `$time.require_profile` makes an unstated policy an error. *Changes a time.md rule; the time reviser decides* |
| `in_zone` gives `OutsideCoverage` "only under a tag" (time-ui finding) | Proposed there | Total `in_zone` and a strict companion; the tag errors. Passed to the time reviser |
| `$explicit_allocation_failure` | Allocating calls return `T \| OutOfMemory` | **Kept, flagged:** David's earlier decision, and the only exception. Its module-top placement keeps one module's API consistent |

Checked and conforming: `$allow_unproven*`, `$prototype`, `$finite_floats`/`$no_nan`/`$no_inf`, `$no_hidden_costs`, `$no_hidden_copies`, `$no_deadlocks`, `$no_unverified_extern_waits`, `$prove_*`, `$no_trusted_library`, `$args.prove_finite_floats`, `$parallel.*`, `$program.*`, `$memory.layout`, `$time.zone`, `$time.require_loss` (display already returns text plus losses). `$dewy.version` selects a language version, not a mode, so it is outside the rule.

## 3. Q3: joined paths

### What the user sees

Turn on nothing, and joining text from outside the program to a folder is a compile error. Joining names that came from listing that folder is not.

```dewy
let input = p"in"
loop name in input.list or_throw {                 # name:FileName
    printl(p"{input}/{name}".size or_throw)        # fine: a FileName stays in its folder
}
loop file in input.glob"*.csv" or_throw printl(file.size or_throw)   # SafePaths

let typed = input("file? ") or_throw
p"{input}/{typed}".read_text
# error: `typed` comes from outside the program and may escape `input` ("../../etc/passwd"):
#        `input.confine(typed) or_throw`, or check it is one name, `FileName(typed) or_throw`
```

### Semantics taken (both tests pass)

- **`FileName`** is `string<shape=@file_name_error>` (the one validation mechanism, string shapes): one component, no `/` and no NUL, not empty, `.` or `..`. On Windows targets it also excludes `\`, `:` and drive prefixes. POSIX's "filename" means exactly this, which is why it's the recommended name.
- **Safe by construction** (no confinement needed):
  - literals, integers, other `SafePath`s, and literal unions of safe components (as today);
  - `FileName` values, wherever they came from;
  - `dir.list` gives `array<FileName>`, since the OS never returns a name with `/`, and `list` already drops `.` and `..`;
  - `dir.glob"…"` and `dir.walk` give `SafePath`s under `dir`, when the pattern is a literal with no `..` part;
  - `with_suffix` and `with_stem` on a `SafePath`; `with_name(n)` when `n` is safe; `.parent` of a `SafePath` deeper than its base.
- **Needs confinement:** any other text joined to a base, i.e. typed input, file and archive contents, network data, environment and arguments joined to a base. A whole path (`p(args[1])`) still has no base, so it needs nothing.
- **Fixes, each one call:**
  - `base.confine(x)` gives `SafePath | PathEscape`. It now also takes text, resolved under `base` (D10's own example already used that form): `saves.confine("{slot}.sav")`.
  - `FileName(text)` gives `FileName | ShapeError`, for "must be one plain name".
  - `to_file_name(text)` gives a `FileName` and never fails: it replaces `/`, `\` and NUL with `_`, and empty, `.` or `..` with `_`. It is the upload case (werkzeug's `secure_filename`).
  - The `if base.contains(p)` guard, as today.
- **Helpers:** a function that joins its own parameter to a base compiles. Each call that passes unproven text is the error, and the error names the helper's base and line (`s14_helper.dewy`). The fix-it names the base expression actually written, never a generic `root` (today's helper warning says `root.confine(file)` where the base is `input`; see the bugs).
- **Opting out:** `$allow_unconfined_paths` in a scope (`s13_quick_script.dewy`). `$prove_confined_paths` additionally demands a base for whole paths.
- **Limit, unchanged:** the test is textual; a link inside the base that points outside isn't detected yet.

### Re-recommendation

**(a): a compile error by default.** The loops people write most (`list`, `glob`, `walk`, literals, numbered files) need nothing. The cases that error are the ones that ship zip-slip and upload bugs, and each is fixed by one call the editor inserts. Under (b), the dangerous case stays a warning, which is how this bug ships today.

## 4. Tags: the restated table and `$bulletproof`

### Changes to the tested set

- **`$allow_unproven_narrowing`** joins `_indexing` and `_division`. The bare `$allow_unproven` also covers refined arguments, such as D11c's stale body.
- **`$prove_local_asserts`** replaces `$count_local_asserts_as_panics` (2/3, below the bar). It mirrors the tested `$prove_library_asserts`: a call that reaches a `$runtime_assert` in your own module must prove its condition (a guard at the call) or carry the `panics` effect.
- **`$prove_no_counter_overflow`** owns every "a 64-bit count can't overflow in practice" trust:
  - counters and accumulators growing by a bounded step;
  - `Atomic<int64>.add`;
  - array sizes up to 2^56 bytes;
  - `parallel` ranges of 2^63 or more values (batch 2 gave those to `$no_assumed_bounds`, which this replaces).

  Keep the tested name and re-test it against the wider meaning. Fallback: `$prove_no_count_overflow`.
- **The counter rule: a step is bounded when it is proven to fit a machine word**, however it is computed. `total += i*2` with `i` in `[0..4)` qualifies; today it doesn't (`probe/counter_mul.dewy` fails, and so does the atomic form). `Atomic.add` follows the same rule, and traps only under `$allow_unproven` when the step is unbounded (`s16_process_atomic.dewy`).
- **`$time.no_unchecked_today`** replaces `$time.handle_uncertain_today` (§2). The other strict time tags follow the same rule: they make the convenient call a compile error and never change a type.

### Library obligations (audit 11)

- An obligation in library code that depends on the caller's arguments, for example a library index computed from a parameter, propagates to the call as a precondition. A guard at the call discharges it, as it does for a user helper.
- One that depends only on library internals (an `assert` deep in `graphemes`) can't be fixed by the caller. Only a library proof clears it, or `$no_trusted_library = false` on the block. Hover on a library function says which of the two it is.
- The library gate keeps a list of which functions are proven, so `$bulletproof` users can see in advance what compiles.

### `$bulletproof`, restated

```dewy
$bulletproof = {
    $no_hidden_costs                  # no hidden allocation, detach, costly copy or panic; includes $no_hidden_copies
    $finite_floats                    # $no_nan and $no_inf
    $no_deadlocks
    $no_unverified_extern_waits
    $prove_confined_paths
    $prove_local_asserts
    $prove_no_counter_overflow
    $no_trusted_library               # the four $prove_library_* tags
    $explicit_allocation_failure      # module policy: the bundle goes at the top of a module
    $time.strict                      # every strict time tag
}
```

- **Rejected inside it:** `$allow_unproven` and its narrower forms, `$prototype`, `$allow_unconfined_paths`, `$assume_extern_never_waits_on_tasks`. `$unsafe` stays, as the written boundary a certifier audits.
- **`printl(1)` compiles:**
  - `printl` of literals, scalars, and interpolations of them writes the pieces in order without building a string, so it doesn't allocate.
  - Under `$explicit_allocation_failure`, a function whose result already includes `OutOfMemory` counts as declaring `allocates`, so its allocation isn't hidden and needs no second annotation.

  See `s09_bulletproof.dewy`.
- **Acceptance gate when built:** `s09`, a file copy, a CSV sum and a TCP echo compile under `$bulletproof` with only the library list above.

## 5. Floats

- **`$finite_floats` on records** (dogfood 10 scored C2):
  - A float field, parameter or result declared in the scope is finite: whoever writes or passes one proves it, and every reader relies on it.
  - Arithmetic between locals may go non-finite. The obligation sits where a value leaves arithmetic: stored, passed, returned, compared, converted or printed. One `x.is_finite` guard on a local discharges everything it was computed from.
  - Welford becomes compute, guard once, commit (`s08_numeric.dewy`). The floor is C4: one guard per state update is the price of the tag, and nothing cheaper is sound.
- **`x.is_finite` is the example guard.** It already works (ran in dogfood). It replaces `float64.most_negative <=? x <=? float64.max same(x)` in D10.
- **Errors:**
  - `float64.min` is an error whose fix-it names both meanings: C's `DBL_MIN` is `smallest_normal`, and the most negative finite value is `most_negative`.
  - `let x = 1.5; x.next_up` says "`x` is an exact rational because 1.5 is exact: write `let x:float64 = 1.5`".
- **`a.is_close(b rel=1e-9 abs=0.0)`**, with Python's `math.isclose` defaults.
- **`to_float(text)`** gives `none` for `nan`, `inf` and out-of-range text by default. `to_float(text allow_nonfinite=true)` accepts them, and `input_float` follows the same rule (`s01`).

## 6. Random numbers and secrets

```dewy
let roll = random([1..6])                          # int64, both ends included
let x = random([-50.0..50.0))                      # float64
let p = random                                     # float64 in [0, 1), unchanged
let gen = rng                                      # own seed from the OS; gen.seed shows it
let again = rng(gen.seed)                          # repeatable
let card = deck[gen.random([0..deck.length))]      # proven index
let noise = fast_random_bytes(1024)                # array<uint8>, never fails, not for secrets
let key = secure_random_bytes(32) or_throw         # secret<array<uint8>> | NoEntropy
let token = secure_token or_throw                  # secret<string> | NoEntropy: 32 bytes, URL-safe base64
let pin = secure_random([0..1_000_000)) or_throw   # secret<int64> | NoEntropy
```

- **`random(range)`** replaces `random_int(lo hi)`, `next_int(@r lo hi)` and `next_float(@r)`. This applies D15d ("anything taking an interval uses range syntax"), and the same name works on a generator. An empty range is a compile error, as today.
- **No bare `random_bytes`** (`s06_reset_token.dewy`). Habits disagree on what it means: PHP's `random_bytes` and Node's `crypto.randomBytes` are secure, while Python's `random.randbytes` is not. Writing it is a compile error that names both choices; both names were already tested and read clearly.
- **Secure values are secrets:** `.reveal` is the one visible step to a nonce or a URL. The library's own nonces (`rtc`, `net`) reveal once, internally.
- **Secret comparisons are constant-time:**
  - `=?`, `not=?` and ordering with a secret operand take time that depends only on the operands' lengths. Lengths stay public, as in `hmac.compare_digest`.
  - The LANGUAGE.md sentence "compiles to the same machine code" gains "except comparisons, which become constant-time".
  - Arithmetic on an arbitrary-precision secret `int` isn't constant-time; the docs say so.
- **`crypto.random_bytes` is removed** in the same commit that adds the new names, with a habits entry naming `secure_random_bytes`.
- `seed_random(n)` stays: it reseeds the shared generator, which is a different job from `rng(seed)`.

## 7. Useful results, and the `;` they force today

**Problem (dogfood 02, parallel reviser).** Under the rules decided on 2026-10-23, a statement's value is part of its body's result. So `out.make_dirs or_throw` before the end of a body is an error ("this expresses a value before the function's end … attach `;`", `probe/makedirs_stmt.dewy`). On main's last line it is "main returns void or the errors that reach it, found int64" (`probe/main_last_write.dewy`; this already happens today with `write_text`'s count). Returning the path makes the most common file line need `;`.

**Recommendation (changes multi-expressions, so it is the owner's):** a contract tag, `$discardable_result`, on the line above a function, like `$warn_if`.

- The value of a call to a marked function is dropped exactly where keeping it would be an error:
  - before the end of a body;
  - in a written `:>void` body;
  - on main's last line.
- Everywhere else it is an ordinary value: a binding, an argument, a collector, or the last line of an inferred function (`s15_discardable.dewy`).
- Any library or program can use it, so it isn't compiler magic, and it never changes a type.
- The library marks:
  - `make_dir`, `make_dirs`, `write_text`, `write_bytes`, `append_text`, `append_bytes`, `copy_to`, `rename` and `set_permissions`, which give back a `Path`;
  - `Atomic.add` (the new value);
  - `group.spawn` (the `Task`; this also covers it outside `tasks`).
- Not marked: `xs.pop`, `window(…)`, `d.pop(k)`, `to_int`, and anything else where dropping the value is a likely bug.
- **Considered:**
  - A written `:>void` discarding everything: this reopens the decided rule and loses the check on `xs.pop`.
  - Inferring "gives back its receiver": it doesn't cover `Atomic.add` or `group.spawn`, and it's invisible at the declaration.
  - `void` results: these fail the "results carry something useful" rule for `make_dirs`.
- **Fallback if declined:** `write_text`, `write_bytes` and `append_text` give `void`, since the caller already holds the path; `make_dirs` gives the `Path` and statements write `;`.

## 8. Library names and results

**One name per operation, for the method and the function form alike.** Methods and functions are the same thing (`p.f(x)` is `f(p x)`), but the file API has two vocabularies today (LANGUAGE.md "Files, paths and processes"):

| Operation | Today | Recommended |
|---|---|---|
| Starts or ends with | `startswith`, `endswith` (`starts_with` is rejected) | `starts_with`, `ends_with`: every other name is snake_case (`trim_start`, `with_suffix`, `read_text`). *The 2026-10-20 commit chose `startswith` from the old reference, so this one is David's* |
| Last match | `rfind` | `find_last` (`find` stays) |
| Make one folder | `mkdir` / `make_directory` | `make_dir`, giving the `Path` |
| Make a folder and its parents | `make_dirs` (gives `true`) | `make_dirs`, giving the `Path` |
| Remove a folder | `rmdir` / `remove_directory` | `remove_dir` |
| Remove a file | `unlink` / `remove_file` | `remove_file` |
| Is a folder | `is_dir` / `is_directory` | `is_dir` |
| Exists | `exists` / `file_exists` | `exists` |
| List | `list` / `list_directory` | `list`, giving `array<FileName>` |
| Permissions | `chmod(0o644)` | `set_permissions(0o644)`, with a habits entry for `chmod` |
| Append | `append_file(path text)` | `append_text`, beside `write_text` and `append_bytes` |
| Start a process without waiting | `spawn(program args)` gives a `Child` | `start_process(program args)`. `start` alone would collide with `let start = now`; Go pairs `Run` and `Start` the same way |
| Random | `random_int`, `next_int`, `next_float` | `random(range)` (§6) |
| Secure bytes | `crypto.random_bytes` | `secure_random_bytes` (§6) |

- `run`, `run_silent`, `capture`, `upper`, `lower`, `read_text`, `with_suffix` and the rest stay. Numeric names from numpy and C math (`linspace`, `randn`, `eye`, `hypot`, `divmod`) are kept on purpose, because they are what numeric users search for.
- **Results:**
  - File errors carry `path`, and the report from `main` prints it: `error: FileNotFound: data.txt`.
  - `read_line` gives `EndOfInput` at the end, as `input` does.
  - `loop line in stdin_lines` streams standard input, with the same failure rules as a channel loop (`s01`).
- **`or_throw` before `{`:** `loop name in input.list or_throw {` binds `or_throw` to the iterable (parallel reviser, same rule), so `s02` needs no parentheses.

## 9. `@(x.f)` with zero-argument calls

**Rule:**

- `@` directly on a name route takes that route: `@m.lock` is a handle to the method, as `@f` is to a function, and a field route is the field's place.
- `@( … )` takes the place the grouped expression gives. Inside the group, the expression is ordinary, so a zero-argument method is called as it is everywhere else: `@(m.lock)` is `@(m.lock())`.
- The idiom becomes `@(m.lock)`; `@(m.lock())` stays legal, as `f()` is.

**Why:**

- The group already means "evaluate this", which is the ownership doc's own reason for the parentheses ("grouping makes the call happen").
- The owner's no-parentheses style then holds everywhere, with no exception for places.
- The handle form is unchanged, so nothing that compiles changes meaning.
- Today `@(acct.lock)` is rejected with "take it with `let name = @(x.lock())`" (`probe/lock_noparen.dewy`). That error becomes the accepted form.
- `ownership.md`'s idiom line ("write the optional parentheses") is replaced. D10's `@(m.lock)` example is then correct as written (`s10_mutex_bump.dewy`).

## 10. D11c, corrected text

| You want | Write | Tag |
|---|---|---|
| The thing or `none` | `w.get(ball)`, giving `BodyState \| none` | None |
| Proven | `w.pos(ball)` right after `add`, or inside `if w.has(ball)` | None |
| Panic if stale | `w.pos(ball)` | `$allow_unproven` in that scope |

- `w.remove(ball); w.pos(ball)` becomes a compile error even under `$allow_unproven`.
- `if w.has(ball)` only proves `w.pos` after a later compiler stage; until then, the error points to `w.get`.
- Rec: add `w.get` and `w.has`. `w.has` replaces `alive` and `joint_alive`. Considered and rejected: silently returning a default (a removed ball draws at the origin); handles consumed by `remove` (they're usually aliased in module globals).

## 11. Linked documents still using removed or renamed tags (audit 11)

**Rule:** proposals stay historical (AGENTS.md: never rewrite old ones), and this file carries the current inventory. The current documents and `lib/directives.dewy` change in the implementing rename commit.

| Old | Current | Still in current docs | Still in proposals |
|---|---|---|---|
| `$runtime_checks` (2,622 uses in 2,205 files) | `$allow_unproven` | GOALS, LANGUAGE, assumptions, effects, multi_expressions, no_traps, precision_inference, refinement, self_hosting, semantic_contracts, tensors, value_semantics, `lib/directives.dewy` | string-shapes/round1 (11), ui/round1 (2) |
| `$panic_on_unproven` | `$allow_unproven` | open_decisions D11c (§10) | bulletproof/round2 |
| `$prototype_warnings` | `$prototype` | LANGUAGE | bulletproof/round2 |
| `$explicit_copies` | `$no_hidden_copies` | GOALS, LANGUAGE, assumptions, effects, ownership, value_semantics, `lib/directives.dewy` | bulletproof |
| `$confine_external_paths`, `$no_unconfined_paths` | `$prove_confined_paths` | LANGUAGE, assumptions, contained_paths, `lib/directives.dewy` | bulletproof |
| `$audited_wait`, `$assume_external_wait` | `$assume_extern_never_waits_on_tasks` | LANGUAGE, assumptions, safety_and_concurrency | bulletproof |
| `$no_assumed_waits` | `$no_unverified_extern_waits` | none | bulletproof |
| `$assume_local_asserts=false`, `$explicit_local_panics`, `$count_local_asserts_as_panics` | `$prove_local_asserts` | LANGUAGE, assumptions, `lib/directives.dewy` | bulletproof |
| `$no_assumed_bounds`, `$prove_size_bounds` | `$prove_no_counter_overflow` | LANGUAGE, assumptions, `lib/directives.dewy` | bulletproof, time/astra-review |
| `$no_nan_or_inf` | `$finite_floats` (kept by David) | none | bulletproof |
| `$explicit_graphics_failure`, `$explicit_environment_failure`, `$verify_protocols`, `$prove_finite_inputs` | Removed (batch 3) | none outside decisions.md | bulletproof |
| `$prove_library`, `_obligations`, `_cleanup` | `$no_trusted_library`, `$prove_library_runtime_checks`, `$prove_library_drop_cannot_fail` | none | bulletproof |
| `$prove_finite_float_args` | `$args.prove_finite_floats` | none | bulletproof |
| `$time.require_*`, `$time.explicit_*`, `$time.handle_uncertain_today` | `$time.no_unchecked_today`, plus the time reviser's rows under §2's rule | time.md, assumptions | time v2–v6, bulletproof |

- Also stale in current text:
  - LANGUAGE.md "Secrets" ("constant-time comparison is planned");
  - LANGUAGE.md "Random numbers", which teaches `crypto.random_bytes`;
  - LANGUAGE.md atomics (line ~3287 says `add` panics, while line ~907 says it uses the counter axiom);
  - `docs/LANGUAGE.md:4605` `startswith`;
  - `lib/core/math.jo:845`.
- `lib/directives.dewy` ships the old bundle; its replacement is §4's block.

## 12. Dogfood, re-run

O = obvious, D = discoverable, C = concise, S = safe by default, X = complete. "Was" is the original program's grade.

| # | Program | Was | Now O D C S X | Floor, and why |
|---|---|---|---|---|
| s01 | Sum stdin and a file (dogfood 01) | 4 4 4 3 3 | 5 5 5 5 5 | |
| s02 | Folder of CSVs (02) | 3 4 3 4 3 | 5 5 5 5 5 | Depends on §7; without it C4 (`;` after `make_dirs`) |
| s03 | Unzip (new: archive entries) | | 5 5 5 5 5 | |
| s04 | Save an upload (new) | | 5 4 5 5 5 | D4: `FileName`/`to_file_name` are found through the fix-it, not by browsing. Nothing better: every language hides this helper (werkzeug, Go's `filepath.Base`) |
| s05 | Game save slots from typed names (new) | | 5 5 5 5 5 | |
| s06 | Reset token (09) | 4 4 3 3 3 | 5 5 5 5 5 | |
| s07 | Dice, cards, particles (08's random) | | 5 5 5 5 5 | |
| s08 | Numeric (10) | 3 3 2 5 3 | 5 5 4 5 5 | C4: one finiteness guard per state update is what `$finite_floats` asks for |
| s09 | `$bulletproof` loader (11) | 3 2 3 5 2 | 4 5 4 5 5 | O4/C4: `OutOfMemory` in two signatures, the flagged allocation exception |
| s10 | Mutex counter (audit 6) | | 5 5 5 5 5 | |
| s11 | Daily log, strict `today` (audit 1) | | 5 5 5 5 5 | |
| s12 | Physics, stale body (D11c) | | 5 5 5 5 5 | |
| s13 | Throwaway script, two permissions | | 5 5 5 4 5 | S4 by the script's choice, visible in two lines |
| s14 | Helper joining its parameter | | 5 5 5 5 5 | |
| s15 | Discardable results (§7) | | 5 5 5 5 5 | |
| s16 | Background process, atomic counter | | 5 5 5 5 5 | |

**Compiled on master** (today's names, the revised logic):

- `s02_folder_report_today` ran, with a `glob` loop and no warning;
- `s06_reset_token_today` ran;
- `s07_dice_today` ran, with `deck[next_int(@gen 0 deck.length)]` proven;
- `probe/mutex_paren` ran;
- `probe/atomic_add_step1` ran.

The revised programs are paper-only: they use `FileName`, `fmt`, `random(range)`, `secure_token` and `$discardable_result`, none of which exists yet.

## 13. Replacement text for open_decisions.md

### D10. Safety defaults and tag names (#108)
- **BLUF:** turn on nothing, and a program can't crash or silently go wrong on anything it can reasonably meet; each permission or stricter check is one tag line. This round adds no semantics questions: joined paths become an error without breaking the common loops, no tag changes a type, and `$bulletproof` compiles hello world. Only names are below. Full design: `docs/design/proposals/bulletproof/round3.md`.
- **Example** (every identifier declared or from the prelude):

```dewy
Reset:type = [user:string token:secret<string>]
let saves = p"saves"

issue = (user:string) => Reset[user secure_token or_throw]       # secret<string> | NoEntropy

save = (slot:string data:string) => {
    let file = saves.confine("{slot}.sav") or_throw  # SafePath, or PathEscape back to the caller
    file.write_text(data) or_throw                   # the result: the Path written
}

main = () => {
    saves.make_dirs or_throw                         # gives back the path; a statement drops it
    loop name in saves.list or_throw printl(p"{saves}/{name}".size or_throw)   # FileName: confined
    let slot = input("save name? ") or_throw
    let f = save(slot "level=3") ?? { printl"pick a plain name"; return }      # "../x" is a PathEscape
    let r = issue("ann") or_throw
    printl"{f} {r} {r.token =? "guess"}"           # token=<redacted>; =? is constant-time
    let m = mutex<int64>(0)
    let v = @(m.lock)                                # the locked place, called like any zero-argument method
    v += random([1..6])
}
```

- **Common path:** nothing to write. Listing a folder, globbing, literals and numbered files need no confinement, and secrets stay out of output.
- **To adjust:** one tag line or one call. `$allow_unproven` (run-time checks), `$allow_unconfined_paths`, `base.confine(text) or_throw` or `FileName(text)`, and `.reveal`.
- **Semantics taken:**
  - Joining outside text to a folder is a compile error; `list` gives `FileName`s, and `glob`/`walk` give `SafePath`s.
  - No tag changes a result type: strict tags point to strict functions, like `today` → `strict_today`. `$explicit_allocation_failure` stays the flagged exception.
  - Secret comparisons are constant-time, and secure random values are secrets.
  - `$finite_floats` covers fields declared in its scope, and a guard on a local discharges its arithmetic.
  - The counter rule takes any proven-bounded step, including `Atomic.add`.
  - `printl` of scalars doesn't allocate.
  - `@(x.f)` calls `f`, as in any other expression; `@x.f` is the handle.
  - File errors carry their path; `read_line` ends with `EndOfInput`; `to_float` rejects `nan` and `inf`.
- **Names: turn this on, and…** (new ones are marked; all were or will be read cold)

| Tag | …this happens |
|---|---|
| `$allow_unproven` | An unproven index, division, narrowing or refined argument compiles; if it fails, the program ends with a report. Narrower: `$allow_unproven_indexing`, `$allow_unproven_division`, `$allow_unproven_narrowing` (*new*) |
| `$prototype` | The same, with a warning at each site |
| `$allow_unconfined_paths` | Outside text joined to a folder needs no confinement |
| `$prove_confined_paths` | Whole paths must be proven inside a base too |
| `$assume_extern_never_waits_on_tasks` / `$no_unverified_extern_waits` | Your unchecked claim on a C-call wrapper / such claims are errors |
| `$finite_floats` | Producing NaN or infinity without a proof is an error; float fields, parameters and results declared here are finite |
| `$no_hidden_copies` | `let b = a` on an array is an error; write `.copy` |
| `$explicit_allocation_failure` | Allocating returns `T \| OutOfMemory` (the one tag that changes types; flagged) |
| `$prove_local_asserts` (*new*, replaces `$count_local_asserts_as_panics`) | A call reaching a `$runtime_assert` in your module must prove its condition |
| `$prove_no_counter_overflow` (*wider*) | Counters, atomic counters, array sizes and huge `parallel` ranges need real overflow proofs |
| `$args.prove_finite_floats` | Above a function: callers prove float arguments finite |
| `$time.no_unchecked_today` (*new*) | `today` is an error that names `strict_today` |
| `$prove_library_asserts`, `_runtime_checks`, `_arena_safety`, `_drop_cannot_fail`; `$no_trusted_library` (all four) | Library code reached must be proven; argument-dependent cases take a guard at your call |
| `$bulletproof` | All of the strict tags above, plus `$no_hidden_costs`, `$no_deadlocks` and `$time.strict`; the permissions are rejected inside it |

- **Q1. Take these tag names?** Rec: yes, after the cold read of the three new ones.
- **Q2. Random and secure names:** `random(range)` for ints and floats (replacing `random_int`); `fast_random_bytes` and `secure_random_bytes`, with no bare `random_bytes`; `secure_token`; `secure_random(range)`; `rng` with no argument and `.seed`. Rec: yes. Considered: a bare `random_bytes` meaning the fast one (PHP's and Node's habits read it as secure).
- **Q3. Path names:** `FileName` (one plain name), `to_file_name` (always gives one), and `confine` taking text. Rec: yes. Considered: `PathPart` and `PathComponent` (cold read pending).
- **Q4. `@(m.lock)` as the idiom** for the place a zero-argument method gives. Rec: yes; `@(m.lock())` stays legal.
- **Q5. `$discardable_result`** above a function: its value is dropped where keeping it would be an error, so `out.make_dirs or_throw` needs no `;`. This changes the multi-expression rules. Rec: yes. Fallback: write calls give `void`.
- **Q6. Library renames:** `starts_with`/`ends_with` (replacing your earlier `startswith`), `find_last`, `make_dir`, `remove_dir`, `set_permissions`, `append_text`, `start_process`, and one name for each file operation's method and function forms. Rec: yes.
- **Q7. Float extras:** `a.is_close(b rel= abs=)` and `to_float(text allow_nonfinite=true)`. Rec: yes.
- **Float constants:** as before, with `x.is_finite` as the guard and a `float64.min` fix-it. Ready.

### D11c
Replace the table's last row with `| Panic if stale | w.pos(ball) | $allow_unproven in that scope |` and the next bullet with "`w.remove(ball); w.pos(ball)` becomes a compile error even under `$allow_unproven`." (§10 has the full text.)

## 14. New or changed names, for the cold read

Don't present these to David as final.

| Name | Intended meaning | Candidates to test beside it |
|---|---|---|
| `$allow_unproven_narrowing` | Narrowing an integer without proof compiles and checks at run time | |
| `$prove_local_asserts` | A call reaching a run-time assert in your own module must prove its condition | `$count_local_asserts_as_panics` (2/3) |
| `$prove_no_counter_overflow` (wider meaning) | Counters, atomic counters, array byte sizes and huge parallel ranges need overflow proofs | `$prove_no_count_overflow` |
| `$time.no_unchecked_today` | `today` is an error; use `strict_today` | `$time.strict_today_only` |
| `$discardable_result` | Above a function: its result may be ignored in statement position without `;` | `$optional_result`, `$may_ignore_result` |
| `FileName` | Text proven to be one plain file or folder name: no `/`, not `.` or `..` | `PathPart`, `PathComponent` |
| `to_file_name(text)` | Turns any text into a safe single name, replacing bad characters | `sanitize_file_name`, `safe_file_name` |
| `base.confine(text)` | `base/text` if it stays inside `base`, else `PathEscape` | |
| `fast_random_bytes(n)` | Random bytes, quick, never fail, not for secrets | (tested: "also clear") |
| `secure_random_bytes(n)` | Unpredictable bytes for keys; a secret; may give `NoEntropy` | (tested 3/3) |
| `secure_token` (`bytes=32`) | A URL-safe random secret string for links and API keys | `secure_token_urlsafe`, `random_token` |
| `secure_random(range)` | An unpredictable whole number in a range, as a secret | |
| `random(range)` | A random int or float in a range (not for secrets) | `random_in` |
| `rng` (no argument), `.seed` | A generator seeded from the OS, whose seed can be shown and reused | |
| `stdin_lines` | Standard input, one line at a time | `input_lines`, `stdin.lines` |
| `a.is_close(b rel= abs=)` | Floats equal within a tolerance | `approx_equal` |
| `allow_nonfinite=true` (on `to_float`) | Accept "nan" and "inf" | `allow_nan_inf` |
| `starts_with`, `ends_with` | Text begins / ends with a part | |
| `find_last` | Position of the last match | `rfind` |
| `make_dir`, `make_dirs` | Make one folder / a folder and missing parents; give the path | |
| `remove_dir`, `remove_file`, `is_dir`, `exists`, `list` | One name each, for the method and function forms | |
| `set_permissions(mode)` | Set a file's permission bits | `chmod` |
| `append_text` | Add text to the end of a file | `append_file` |
| `start_process(program args)` | Start a program and return without waiting; gives a `Child` | `launch`, `spawn_process` |
| `strict_elapsed(start end)` (for the time reviser) | Elapsed time that reports a broken clock as a value | |
| `strict_` vs `checked_` prefix | One prefix for "the same call, with its failures as values" (`strict_today` is decided; `checked_add` exists in time) | Rec: one prefix, `strict_`, renaming `checked_add` |

## 15. Out-of-scope bugs in today's compiler

1. **The helper confinement warning names `root`, not the actual base.** `~/dev/tmp/dogfood-1107/a/02_folder_report.dewy` warns "`root.confine(file) or_throw`" where the base is `input`. The direct join names it right (`probe/list_join.dewy`).
2. **The counter axiom rejects bounded products:** `total += i*2` with `i` in `[0..4)` can't prove the upper bound (`probe/counter_mul.dewy`). The same happens for `hits.add(i*2)` on an atomic (`probe/atomic_add.dewy` with `i*2`), which asks for `$runtime_checks`.
3. **`$finite_floats`:** `float64(v)` of a rational literal element isn't proven non-NaN (`probe/float_conv_nan.dewy`: `loop v in [1.0 2.0 4.0] add(@s float64(v))`).
4. **`{x:.2f}` still compiles** (`s02_folder_report_today.dewy`), although the owner has now ruled it out. Expected until the formatting change lands.
5. **LANGUAGE.md contradicts itself on `Atomic.add`** (lines ~907 and ~3287).

Checked and already fixed: round 2's "`T | OutOfMemory` used as `T` compiles" (`probe/oom_gap.dewy` now errors correctly).

## 16. Dependencies on other revisers

- **Time:** apply §2's rule to `require_clock_domain`, `require_range`, `require_resources`, `$time.gap`/`$time.fold` and `in_zone` coverage, and decide the `strict_`/`checked_` prefix with §14.
- **Parallel:** `$prove_no_counter_overflow` now owns huge `parallel` ranges and `Atomic.add`. `group.spawn` gets `$discardable_result` if Q5 passes; the parallel reviser's context-typed `tasks` rule still holds without it. The process call is renamed `start_process`.
- **Multi-expressions:** Q5 is a change to the decided 2026-10-23 rules, and needs the owner.
