# Decisions

David's standing decisions on Dewy's surface and semantics. This file is the
ledger: a decision that has an owning design doc keeps one or two lines here
(the decision, its date, a link), and the full rule lives in that doc, in the
section linked. ROADMAP.md lists them in one line each.

## Owned by a design doc

- No traps by default (2026-10-21; supersedes "ordinary code keeps runtime
  checks"): every partial operation is proven, handled as a value, or checked
  with `$runtime_assert`; `$runtime_checks` is the production opt-in; runtime
  failures leak no data (2026-10-23).
  [no_traps.md](no_traps.md#decided-rules)
- Safety configuration (2026-10-21, 2026-10-23): orthogonal boolean metatags and
  library bundles on a loosest-to-strictest ladder; `$no_hidden_costs` is the
  strict lane; `$bulletproof` is the strictest bundle; the counter progress
  axiom and `$no_nan`. [assumptions.md](assumptions.md#decided-rules)
- The `panics` effect (2026-10-23): inferred, visible in rows, forbidden by
  `& no panics`. [effects.md](effects.md#decided-rules)
- Concurrency (2026-10-21; spellings provisional), `Send`/`Sync`, `secret<T>`
  and the multi-lock spelling (2026-10-23):
  [safety_and_concurrency.md](safety_and_concurrency.md#decided-rules).
  Deadlock freedom (adopted direction, 2026-10-23):
  [safety_and_concurrency.md](safety_and_concurrency.md#deadlock-freedom-adopted-direction-2026-10-23).
- Tensors (Q7, 2026-10-21): one `array` type with shape in the type, dot
  broadcasting, contiguous N-d literals; `end`/`new` reserved; `\` continues a
  line (2026-10-23); GPU placement is explicit and mixing devices is an error.
  [tensors.md](tensors.md#decided-rules)
- Allocation (Q4) and resources: an implicit context allocator, infallible
  unless `$explicit_allocation_failure`; no blanket exhaustion guarantee.
  [resource_exhaustion.md](resource_exhaustion.md#decided-rules)
- Fixed-width integers (2026-10-22; supersedes "`intN`/`uintN` wrap"):
  arithmetic is exact, storing is the proven narrowing, overflow policy is a
  type parameter; `transmute` for reinterpretation.
  [precision_inference.md](precision_inference.md#fixed-width-integers-2026-10-22)
- Inference precision: decimal literals adapt to context, exact rationals stay
  the default (2026-10-23), unannotated bindings keep the covering type
  (uniform precision, common parent).
  [precision_inference.md](precision_inference.md#decided-rules)
- Multi-expressions (2026-10-23; restores the reference), substitution
  invariance, unpacking, parameter patterns, `:>(int64 int64)`.
  [multi_expressions.md](multi_expressions.md)
- Juxtaposition multiplication (2026-10-23; restricted, type-directed rule,
  replaces the reference's general one; no spaced units).
  [juxtaposition.md](juxtaposition.md)
- Contained paths (2026-10-23): `SafePath`, `root.confine(p)` and the bool
  guard `root.contains(p)`, traversal warnings scoped by construction, no
  source/sink markers. [contained_paths.md](contained_paths.md)
- Refinements and invariants: partial operators are the idiom (2026-10-23);
  index-typed refinements deferred. [refinement.md](refinement.md#decided-rules)
- Ownership, places and closures: lifecycle hooks, places from handles
  (round 6), place-returning methods `:>@T`, closure capture writes
  (`$capture`). [ownership.md](ownership.md#decided-rules)
- FFI (`$extern`, `$export`, `$unsafe`), `$target` names and the `$build`
  namespace (2026-10-23). [self_hosting.md](self_hosting.md#decided-rules)
- Compiler architecture: lazy loading with no library image, and the compile
  speed framing (A: strangler-fig migration, tracks A to C).
  [compiler_architecture.md](compiler_architecture.md#decided-rules)
- Time: `month`/`year` combine only with real dates; long-term direction in
  [time.md](time.md).

## Standing decisions without a design doc


- `int`: arbitrary precision with word storage where proven. `intN`/`uintN` arithmetic is exact (see Fixed-width integers above).
- Zero-argument calls may omit or include the parentheses.
- A bare function name calls; `@fn` is the handle.
- Boolean metatags accept `$tag`, `$tag = true`, `$tag = false`.
- Follow the reference: `+` never concatenates (strings use interpolation or
  `join`; containers `[xs... ys...]`; array `+` is reserved for elementwise
  math); bindings must be initialized before reads; `d.keys` is an
  insertion-ordered set; conversions preserve value (`uint64(x)` proven, or
  checked under `$runtime_checks`; raw bits need an explicit spelling); declared
  effect rows are contracts callers see.
- `$shadowable const` (module top level): inner scopes and importers may shadow
  it, and a plain `max = 3` there makes a new binding. The prelude uses it (no
  special prelude rule). Shadowing replaces the whole overload family; other
  consts can't be shadowed (the error suggests `let`).
- Loops: `loop x in xs` iterates the entry value (mutating `xs` is allowed and
  unseen); `loop x in @xs` iterates the place live (worklists). Changing the
  length of a by-value iterated container is a compile error with both fix-its.
  Steerable traversal belongs in the iterator protocol.
- Floats (Q8): strict IEEE 754 by default (NaN, ±Inf, signed zero and
  subnormals are values; no reassociation or FMA contraction; deterministic
  reduction order; value-preserving float→int; sorting by totalOrder).
  Orthogonal opt-ins: `$fast_math`, `$no_nan`, `$no_inf`, and the bundle
  `$finite_floats`.
- Imports (Q24, following the reference): `import p"x.dewy"` with no selection
  splats the module's top-level bindings (collisions are errors);
  `import p"x.dewy" as name` gives a namespace; selective imports pick names.
- Spelling policy (round 4): Dewy does not religiously enforce one spelling per
  operation. An extra spelling is allowed when it is well justified (e.g. a short
  form for a very common operation); unjustified aliases are avoided.
- Search results: `index_of` and `find` return `int | Missing`. `Missing` is a
  specific exception value, not `none` or -1.
- `main` returns `void | errors`. The error set is inferred unless annotated (an
  annotation fixes the order and documents it); no main special case. Scripts
  needing a code call `exit(n)`. Success exits 0. An error reaching `main` is
  printed and exits with a code assigned 1, 2, 3, … in the declaration order of
  the error kinds, up to 100 (101 is a failed runtime check). An error type may pin its code with an `exit_code`
  member. `dewy build --exit-codes` prints the table.
- Console: the prelude `console` object has `print`/`printl` and `info`
  (stdout), `warn`/`error` (stderr, coloured on a terminal) and `debug`
  (stderr, compiled out of release). Prelude `print`/`printl` are `$shadowable
  const` aliases of `console.print`/`console.printl`. The general form is
  `print(x file=stream)`, with `stdout`/`stderr` in the prelude; no
  `eprint`/`eprintl`. Colour only when the stream is a TTY; respect `NO_COLOR`
  and `FORCE_COLOR`/`CLICOLOR_FORCE`; program override, e.g.
  `console.color='auto'|'always'|'never'`.
- Slices follow no-traps: `xs[a..b)` must be proven in bounds. Explicit clamping
  is an in-index metatag, `xs[$clamp a..b)` (Python-style truncation).
- Helpers: adopt `is_empty`, prefix/suffix removal, graphemes as the default
  `chars`, `count(value)`, `lines`, `trim_start`/`trim_end`. `any`/`all` without
  a predicate apply only to `array<bool>` (idiom: `all(xs .>? 0)`). Drop `zip`
  (compound loops and `[A B]` cover it).
- `T?` fields default to `none` implicitly.
- Comparing a union with one of its members (`back =? n`) is plain true/false.
- No separate tuple concept: `[int64 string]` is an array type with per-position
  element types; a const array is a "tuple".
- Byte literals: `b'a'` is a `uint8`, `b"abc"` a byte array.
- `%` stays floored, with no mode metatag; alternatives are explicit: `mod(a b kind=…)` (below).
- Rounding: human-oriented types (rational, decimal, int division results)
  round half away from zero (`round(2.5)=3`, `round(-2.5)=-3`); floats follow
  IEEE ties-to-even. Both take `ties=` to override.
- Units (round 5): display is automatic, picking a sensible unit per kind, with
  likely display units chosen for derived expressions; `x as unit` overrides
  and converts (`l as inches`). Offset units do what people expect: `20°C` is a
  point, but read as a delta when added to or subtracted from a point
  (`start + 20°C`); point − point = delta; scaling works in the value's own
  unit. `(20°C as °F)` converts as a point (68°F), but as a delta (36°F) when
  used as a delta: infer delta-ness from use, or document the rule. Rational
  dimension exponents are allowed (V/√Hz), so `sqrt` of odd powers is valid.
- Offset units (amends round 5's "infer delta-ness from use"): a temperature
  written directly as an operand next to a point is a difference
  (`t + 20°C`). Computed and input values (readings, parsed or loaded
  values, results involving points) are points; adding two, comparing a
  point with a difference, and scaling a point are compile errors with
  fix-its (for averages: `mean[t1 t2]`; or subtract to form a difference).
  Point versus difference lives in the type, so `as °F` converts each
  correctly (a 20° difference is 36°F). Named differences have no dedicated
  spelling (no `Δ`): a difference is a subtraction of two points
  (`25°C - 5°C`) or plain kelvin (`5K`).
- Literal-only temperature bindings (amended 2026-10-23): a binding holding
  only temperature literals (`let rise = 20°C`) takes its kind from all of its
  uses, decided once per binding as in precision inference, so a use site
  never reinterprets it. A use only a difference allows (`t + rise`,
  `t -= rise`, `rise*2`, comparing with a difference) makes it a difference
  when no use needs a point (`rise <? t`, `rise - t`); uses either kind
  allows (`t - rise`) don't decide, and an undecided binding is a point.
  Conflicting uses warn, naming both; the binding stays a point (what a
  temperature written in a unit is, and what an undecided one is) and each
  difference use reads it as a difference, as it would the literal.
- Quantities print without a space: `1500m`, `20°C`.
- Iterator control: bind the iterator and loop over its place:
  `let w = tree.walk` then `loop node in @w { if skip?(node) w.skip_children }`;
  also `w.seek(i)`. A one-line binding form may come later (`as` is conversion).
- `mod(a b)` is a free function with `kind='floor'` (default, same as `%`),
  `'euclid'` or `'trunc'`. Not `rem`, not a method.
- Indexed iteration is always `loop i in 0.. and x in xs`: no `enumerate`, no
  `indexed`.
- File helpers are `Path` methods: `p.copy_to(q)`, `p.rename(q)`, `p.make_dirs`,
  `p.walk`, `p.glob"*.dewy"`, `p.size`, `p.modified`, `p.chmod(...)`; `env`
  stays in the prelude.
- An ambiguous partial application of an overloaded function is a compile error
  asking for an annotation.
- Printing details: approved as provisionally implemented.
- Tests: one process per `$test`; `--json` stays provisional.
- Escapes: an unknown escape of a letter or digit (`\N`) is an error; any ASCII
  punctuation may be escaped to itself (`\}`, `\{`, `\'`, `\"`, `\\`).
- `and=`/`or=` short-circuit: `a and= f()` means `a = a and f()`.
- `main` is optional: without it a file runs top to bottom as a script; with it,
  `main` runs automatically exactly once; an explicit top-level `main()` call is
  an error (recursion inside `main` is fine).
- A splat import that shadows a prelude name warns, naming both sources; the
  warning goes away when the name is selected explicitly or the module is
  imported `as`. Splat imports stay.
- Big-int parsing limit: `to_int(s max_digits=…)`, default about 1M digits,
  returns an error value beyond it (as Python did for CVE-2020-10735);
  conversion in both directions is subquadratic.
- The current compiler's implementation language is Sloppy (`.jo` is its file
  extension); docs and diagnostics name it accurately, never "Jo".
- Follow-ups (decided 2026-10-23): the site tagline is "Python-like ease.
  C-like speed. Safer than Rust.", backed by a page of concrete differences. The
  game library's vector magnitude is `v.norm` (MATLAB/Julia/NumPy term;
  extends to `v.norm(p=1)` and matrix norms); the free `length(v)` is removed,
  and `.length` means element count everywhere.
- Decided 2026-10-23 (answers, corrections, batch 13 and the small batch; the
  multi-expression, juxtaposition, path, place, metatag and fixed-width rules are
  in the owning docs above):
  - `regex(p)` returns `Regex | RegexError`; literal patterns are checked at
    compile time.
  - `s.byte_slice(a b)` (proven char boundaries) and `b.read<uint64>(i)`
    (proven in bounds, no `$unsafe`).
  - The float and net provisional sets are approved.
  - Delimited-argument calls `f[…]` and `printl'…'` are approved.
  - `to_int` returns a specific error kind saying why it failed (unparsable, too
    many digits, …) instead of `none`.
  - `??` defaults any exception value as well as `none` (`to_int(s) ?? 0`); the
    editor hover shows which failures a `??` covers.
  - Defaulting specific errors: `x ??<Missing|ParseError> 0` defaults only the
    listed exception types (and `none` if listed); other errors pass through.
    Plain `x ?? 0` defaults any exception and `none`.
  - Loops have exactly one form, `loop <condition> <body>`, and are not
    whitespace sensitive; an infinite loop is `loop true <body>`. The
    provisional "`loop { … }` loops forever" rule is removed.
  - No local precedence exception for `loop c in s as array<uint8>`. Operator
    precedence starts from the archived Python implementation's table, adjusted
    only where it would confuse; deviations are reported to David.
  - Precedence of `as` versus `in` is exactly the archived Python parser's; no
    special case for `loop c in s as …` (write `loop c in (s as array<uint8>)`).
  - Enums: string-literal unions are unordered from the user's perspective;
    internal numbering is a representation detail and must not leak across
    subset/superset unions.

## Ledger


- Bulletproof principle (David, 2026-10-23): "I want to be able to write an
  actually bulletproof program that accounts for every eventuality, with the
  compiler enforcing it." Every convenience axiom or assumption has a metatag
  that turns it off and demands the proof instead. They are tracked in one list
  ([assumptions.md](assumptions.md)) so the strictest configuration can be a
  library bundle.
- Compile speed: 250k lines/s single-threaded in the default build (200k
  minimum), on representative code. Parallelism is a bonus.
- Compile-speed metric (decided 2026-10-22): the goal stands at 200–250k lines/s
  single-threaded, default build, for every flagship (dunes and 101 included).
  Throughput counts EVERY source line the compiler processes for the build: the
  user's lines, plus the library lines it reaches after lazy pruning, plus
  generic-instance work charged to the lines that cause it (as Jai counts).
  Companion numbers: library fan-out (reached library lines and instantiated
  bodies per program), pushed down by the closure diet (pay-as-you-go runtime
  pieces, instances shared by representation); and hello-world latency ≤20 ms
  (tightened from ~50 ms). A user-only column may be reported, but the gated
  number counts all lines. Rejected: a per-machine library index (a precomputed
  cache) and making the game prelude an explicit import (it stays implicit and
  is made cheap by laziness). The library index scan must be near-free
  (memchr-class, no tokenizing what isn't reached).
- License and trademarks (decided 2026-10-22): the whole project (compiler,
  tools, standard library and runtime, docs, examples, VS Code extension) is
  Apache-2.0 WITH LLVM-exception (SPDX `Apache-2.0 WITH LLVM-exception`; the
  text is LLVM's LICENSE.TXT verbatim, in `LICENSE`). Why: the explicit patent
  grant with patent retaliation; one license, not a dual license, so there is
  no election gap; no attribution burden on compiled Dewy programs, since the
  LLVM exception covers the runtime and library portions embedded in object
  code; GPLv2 compatibility through the exception. No NOTICE file, so
  redistributors' section 4(d) obligations stay minimal, and no per-file
  headers. Toolchain packages ship the root `LICENSE` (never a NOTICE), plus
  `lib/std/unicode/LICENSE.txt` and `lib/game/assets/OFL.txt`. Trademark policy
  ([TRADEMARKS.md](../../TRADEMARKS.md)): "Dewy" and its logos are David
  Samson's trademarks. Accurate references, "written in Dewy"/"for Dewy" and
  redistributing unmodified official releases are free. Modified versions and
  forks need a different name and logo, must not imply official status, and
  may say "based on Dewy". "Dewy-compatible" requires passing the official
  conformance suite (acceptance ladder and test suite) for a stated version,
  named in the claim. Use in the name or branding of another language,
  implementation, distribution or product needs written permission.
- Versions: the language stays 0.0.0; the extension gets patch bumps only, at
  most one release a day.
- The open-question pass is complete (2026-10-21). Anything not covered follows
  the provisional-default rule: a recommendation plus reversibility,
  implemented provisionally and flagged.
- Approved provisional calls (2026-10-21): bundle definitions
  `$name = { $setting … }` with `$default_row` inside bundles; every failed
  runtime check (`$runtime_checks` and `$prototype`) exits 101, and `main`'s
  sequential error exit codes are capped at 100 so they never collide; `sorted`
  on sets returns an array; module-level `let x:T` with no value is allowed when
  `main` provably assigns it before any read; forbid-only rows check the body
  while callers see the inferred effects; distinct `@` parameters are disjoint
  for the solver; regex `find` returns `Match | Missing`.
- David's decisions of 2026-11-01 (batch 1; questions D1–D5 in
  [open_decisions.md](open_decisions.md)):
  - Import cycles (#140): allowed, under the rule "as if everything were one
    big file": a program that would work as one file must not break when split
    into modules, for declarations and module-level code alike. Initialization
    is ordered by dependency, as in one file; the only error is one a single
    file would also have (a genuine value cycle, or a use before
    initialization), and it names the chain. Considered: keep rejecting cycles
    that contain a `.dewy` module; allow cycles of declarations only. Reasons:
    maximum ergonomics, and splitting a file must never change its meaning.
    Design: [modules.md](modules.md).
  - Compile-speed target (#126c): every flagship reaches at least 200k
    lines/s. Considered: the panel aggregate reaching 200k with the worst
    flagship only tracked. Reasons: it is the honest reading of the goal, and
    the slowest flagships (the compiler itself, a systems program) are the
    workloads that matter.
  - Failed sends and new queues (#105 D3a–c), from
    [proposals/concurrency/stage4/](proposals/concurrency/stage4/):
    - D3a: a failed send returns `void | Unsent<T>`, with `.value` (the exact
      payload offered) and `.reason` (`Full`, `Closed`, `Busy` or
      `Canceled`); `Channel.send` returns this too. Considered: keeping
      `void | Closed | Canceled`. Reason: a failed send must never lose the
      value.
    - D3b: `spsc<T N>` with a consuming `.split` (no parentheses: zero-argument
      calls drop them everywhere) and the channel verbs.
    - D3c: `mpmc<T>(capacity)`; a non-waiting attempt that collides with
      another task returns `Busy`, rather than a misleading `Empty`.
  - Callbacks passed into parallel code (#114): inferred. A function that
    passes a callback parameter into parallel code gets "this argument must be
    parallel-safe" in its signature, checked at call sites like effects. An
    optional `$parallel_safe` only enforces the contract on exported APIs and
    is rejected on a function that takes no callback. Considered: requiring a
    tag before a function may pass a callback into `parallel`. Reason: no
    colored-function-style requirements on ordinary code.
  - On hold for one cohesive parallel/concurrent surface proposal
    ([proposals/concurrency/unified/](proposals/concurrency/unified/)):
    `select` (#105 D3d), `[concurrent x in xs …]` (#118), and any new loop- or
    capture-shaped concurrency construct. Reason: these should be designed
    together, not one construct at a time.
  - No legacy: Dewy has no users yet, so a design change keeps no
    compatibility shims, deprecation paths or old-form-to-new-form
    diagnostics; change it and update the tests and docs. "Use X instead"
    errors for spellings that never shipped are removed. Fix-its that teach
    Dewy over Python or C habits stay. Reason: there is nothing to migrate.
- Batch 2 from [open_decisions.md](open_decisions.md) (David, 2026-11-06):
  - **How questions are asked** (standing): a semantic question reaches David
    only if it fails one of two tests: (1) the common 80% path is easy,
    ergonomic and fast; (2) when the common path doesn't fit, adjusting it is
    straightforward. If both pass, the semantics are good and only the syntax is
    his to review. Reason: most questions asked him to arbitrate semantics that
    these tests already settle.
  - **Safety default direction** (standing, #108): vanilla Dewy doesn't need to
    be near `$bulletproof`, but a lot or all unsafety is opted into, not opted
    out of, unless there are strong, stated reasons for the reverse. Every tag's
    name must say what it does (safer or less safe, more or less proof, assume
    or ensure). Common crashes aren't possible unless opted in. Considered: the
    8 `$library.require_*`/`$prove_*` opt-outs as proposed; rejected as unclear
    and as requiring you to remember to opt out. Redesign:
    [proposals/bulletproof/](proposals/bulletproof/). Very large `parallel`
    ranges (D10h): `$no_assumed_bounds` rejects an unproven range of 2^63 or more
    values, with no new tag.
  - **Time core**, from [proposals/time/](proposals/time/):
    - `Instant` and `Duration` are 128-bit nanoseconds (D6). Considered: 64-bit,
      which covers only 1685–2269. Reasons: the 10,000-year priority;
      `width=64` stays available for compact columns.
    - `now` is a `ClockReading`: `now - start` is monotonic, `now + 5s` is a
      monotonic deadline, `.nominal` is the wall `Instant` (D7). Considered:
      subtraction on the wall clock, which lies when the wall clock is adjusted.
    - Time literals are checked at compile time and can't fail (D8).
    - `1day` and `1week` are calendar periods (D9), with good errors pointing to
      the right form. Considered: durations, which would make `1day` equal
      `24hour` and break substitution invariance.
    - `Gregorian` names the default calendar, since Dewy converts nothing
      implicitly. Considered: `ProlepticGregorian`.
    - Relative waits count actual time, with active/awake time opt-in.
    - Default rule data is pinned to the Dewy version, not a year. Considered:
      `rules_2026`.
    - If a zone-dependent operation has no explicit zone, the compiler warns which
      zone it assumed; `$time.zone = 'America/New_York'` is the explicit form.
    - `age` is explicit about which date is which, and `date - date` is a natural
      spelling. Considered: `birthdate.age(on=…)`, which relies on remembering an
      arbitrary order.
    - Separate `Appointment`, `Occurrence`, `Event` and `Observation` records,
      and v5's new names: provisional.
  - **Language version instead of editions:** a program declares the version it
    was written for, e.g. `$dewy.version = '0.1.0'`. Any current or later compiler
    compiles it as that version, warnings may mention later changes, and modules
    with different versions interoperate. Reason: "I want to be able to compile
    my old programs 100 years later." Considered: `$edition = 2026` and
    `$build.edition`.
  - **Loop copies stay writable** (D12, #139): writing to the copy in `loop x in xs`
    isn't an error, since changing the local copy can be exactly what's wanted, as
    when looping over integers. Considered: an error naming `loop @x in xs`.
  - **`[]` is an underspecified literal** (D13, #141): like `1`, it takes its type
    from context (an empty dict, array or possibly object). Considered: an array
    always, with a dict special case.
  - **`?? return x`, `?? break` and `?? continue`** (D14, #142), including with
    `??<E>` for narrower errors.
  - **Writing to a tuple slot at a runtime index** (D16, #137) is allowed whenever
    the operation is valid for every position it could reach, e.g. `t[i] += 1` on
    `[int64 int64|float64]` is fine and on `[int64 int64|string]` is an error.
    Considered: only when every position has the same type.
  - **Self-length refinements** (D17, #138): wanted, e.g.
    `array<int64<(<? parent.length)>>`.
  - **`from` stays a reserved keyword everywhere** (D18, #144). Considered: a
    contextual keyword.
  - **Formatting** (D19): `pad_center` is added (#134). Nested `"{x:<{w}}"` is
    rejected as brand-new syntax not patterned after anything in Dewy; dynamic
    formats use a higher-order format function
    (`resources/discussion_points.md`, "Format string specifiers") (#135). Width-only
    formats add no digits, so a rational `120` under `{x:>7}` prints `    120`
    (#136). `rational("19.99")` prints `19.99`.
  - **No `if let`** (D20, #143).
  - **Function types are idiomatically grouped with `()`** (D22 note): e.g.
    `f:(int:>int)` and `report:(array<int> :>void)`. `<>` stays valid: it is `()`
    that also constrains the inside to be types.
  - **`spsc` details** (D23, #146): `let [tx rx] = spsc<Message 64>.split`, without
    the redundant `()`. `$__consume__` is fine. The other calls are implementation
    choices, made for ergonomics, least surprise and fewest bugs.
  - **A program function hiding a library method warns, naming both** (D24).
    Considered: changing lookup; staying silent.
  - **Start-up reads** (D25): the first call to a function requires every value in
    its body to be defined by that point, or it's a compile error, even on a branch
    that wouldn't run. The exception would be a future compile-time exclusion (for
    OS or environment code). Considered: discarding proven-dead branches; a run-time
    check.
  - **Directions:** insulation R-values and anything computed with them must be
    effortless in units and interoperate with all other units. Metatags direct
    allowed resource use at a high level (e.g. single core).
  - Taken under the two-question test, without David's review (either can be
    overturned): `$capture @x` of an outer variable inside a task is a compile
    error (D26); `spawn` bodies infer their result so `or_throw` works (D27).
  - **Time zone with none given** (D15a): chosen at compile time, so you can say
    exactly the behavior you want. `$time.zone = 'America/New_York'` pins the whole
    program to one zone; `$time.zone = 'system'` uses the zone of the machine running
    the program; `$time.zone = 'build'` pins the build machine's zone. Rules are pinned
    at build unless `$time.zone_source = 'host'`. Unspecified means the running
    machine, with a warning naming the assumption. Considered: only pinning the name
    at build, which would make a binary built in New York report New York's date in Tokyo.
  - **What `$dewy.version` promises** (D15b): once Dewy has settled and has a first
    release, a program tagged with a compiler version always compiles with that
    version or any later compiler; all future compilers know how all past versions
    worked. Before that, the no-legacy rule stays. If an old version turns out to have
    a serious security problem, the program still compiles, with a very obvious warning
    and the steps to fix it. Considered: rare breaking changes for security, as in some
    other languages. No declaration compiles as the current version, with a warning and
    a fix-it that inserts one.
  - **Anything taking an interval uses range syntax** (D15d), so the bounds are
    unambiguous: `[a..b)`. Considered: `interval(a b)`, with a default to remember.
  - **UI direction:** a declarative layout interface like
    [Clay](https://github.com/nicbarker/clay). Nothing is built yet.
- Batch 3 from [open_decisions.md](open_decisions.md) (David, 2026-11-07):
  - **Names are tested cold** (standing): a proposed tag or member name is shown to
    models with no context, which guess what it does; names they read wrongly are
    replaced. Reason: names that need explaining fail their job.
  - **Parallel surface** (D4, partial; [proposals/concurrency/](proposals/concurrency/)):
    - Accepted: the three shapes, i.e. the loop `parallel x in xs { … }`, the
      comprehension `[parallel x in xs f(x)]` and the block `parallel { … }`;
      `tasks`; and the removals (`concurrent`, `spawn`, `concurrent g`,
      `spawn(g)`, `cancel(g)`, `TaskGroup`, `parallel_map`, `parallel_range`,
      `parallel_update`, the `select { … }` grammar).
    - Accepted: items may wait, including on each other, with the strategy
      inferred (C1). `or_throw` in an item leaves the enclosing function as it
      does anywhere, canceling the siblings; errors otherwise stay per-item
      values (C3).
    - Accepted: `select` is a library call paired with `match` (C5). Its
      signature is still being designed.
    - Directions, being designed in a v3 proposal:
      - metatags go in namespaces with unambiguous names (`$window` is too common
        a word), e.g. `$parallel.window = 8`;
      - `tree` in `sum` is a keyword-only argument;
      - an easy way to filter out error cases in general, e.g.
        `[parallel n in ns check(n) ?? void]`, only where dropping a value is coherent;
      - block items may depend on earlier ones, with the dependency graph worked
        out;
      - compute-only work runs to completion by default, and opting into
        cancellation is easy;
      - ranges should work wherever a sequence is enough;
      - no callback-style `op.then(f)`.
  - **Dates** (D15c): `age(born on=today)`, with `on` defaulting to today, and
    `Date - Date` gives a `Period`.
  - **`strict_today`** (D15e) is the careful form of `today`, returning
    `Date | AmbiguousToday | UnknownToday`; the separate `today_support` query is
    gone. Considered: `possible_todays`, `today_range`, `pedantic_today`.
  - **Safety defaults** (D10, partial; [proposals/bulletproof/](proposals/bulletproof/)):
    - Accepted: with no tags, ordinary failures (end of input, no display, bad
      files, no entropy) are values, not crashes. On success `window` should give a
      handle. Random bytes for non-security use should be separate from
      cryptographic ones that can fail.
    - `$no_deadlocks` means what it says (Q4). `serve` and `pipeline` lose their
      trusted status until a library gate proves them.
    - Names that stay: `$finite_floats`, `$prototype`, `$unsafe`, `$bulletproof`.
    - Removed: `$verify_protocols`, `$explicit_environment_failure`,
      `$explicit_graphics_failure`, `$prove_finite_inputs`.
    - Directions: permissions use the word `allow`, and should say what they
      allow (instead of `$panic_on_unproven`). Tags about a function's
      arguments go in an `$args.` namespace. Float constants should be intuitive
      for newer programmers.
- **Formatting** (D19e, David, 2026-11-07): `fmt` is the only formatter, a higher-order
  function taking a single pattern string (`f` is too common a name). The pattern narrows
  the input type the result accepts, so `fmt'.2f'` formats numbers and a mismatch is a
  compile error. It is used in interpolation as `printl'result is {fmt'.2f'x}'`, and
  idiomatically pre-built: `f0 = fmt'.2f'`. `{x:.2f}` is not valid Dewy, and
  `format(x spec)` goes too. Considered: keeping `{x:spec}` as shorthand.
  ([resources/discussion_points.md](../../resources/discussion_points.md), "Format
  string specifiers".)
- **D26 and D27 closed** (2026-11-07): the parallel v4 design carries both
  ([proposals/concurrency/unified/](proposals/concurrency/unified/)). A
  `group.spawn` task can't write outer variables, and `or_throw` in a spawned lambda
  forwards to its inferred result.
- Batch 4 from [open_decisions.md](open_decisions.md) (David, 2026-11-07):
  - **Orthogonality and context** (standing):
    - Spellings should be orthogonal unless there is a good reason not to be. "In general we should be striving for orthogonality where we can unless there's good reason to not be orthogonal."
    - Behavior should not depend on context unless there is a good reason. "In general I don't want to be introducing context sensitivity unless there's a good reason for it."
  - **`;` is the way to drop a value** (D10 Q2). Calls keep returning useful values (a handle from a call that starts something, the path from a write), and a statement that ignores one writes `;`, as the multi-expression rules already say. The earlier decision that a callback whose result is `void` only by context drops its values stands.
    - Considered: a `$discardable_result` contract on functions (receipts) whose results a statement could drop silently; and making writes return `void`.
    - Reason: "I don't want to allow there to be some special case just to skip `;` if `;` is the obvious way to suppress the value." Receipts would make the meaning of a statement depend on which function it calls.
    - [proposals/bulletproof/](proposals/bulletproof/), [proposals/integration/](proposals/integration/)
  - **`@(m.lock)` is the idiom** for the place a zero-argument method gives (D10 Q1). Inside `@( … )` the expression is ordinary, so a zero-argument method is called as it is everywhere else. `@(m.lock())` stays legal, and `@m.lock` is the method handle.
    - Considered: keeping the ownership doc's "write the optional parentheses".
    - Reason: the no-parentheses style then holds everywhere, with no exception for places.
    - [proposals/bulletproof/](proposals/bulletproof/)
  - **Narrowing never panics at run time** (D11 Q1). `let a:Action = s`, `s as Action`, and passing or returning text where a literal union or shaped type is expected are proven obligations, like `x as uint8`. `Action(s)` reads text and gives the failure as a value (`Action | ValidationError`).
    - This replaces LANGUAGE.md's "any other string is checked when the program runs".
    - Considered: keeping the run-time check.
    - Reason: "If that's just making some value fit within some narrower type, absolutely yes there should never be a runtime panic."
    - [proposals/string-shapes/](proposals/string-shapes/)
  - **`$parallel_safe` is deleted** (D22). Whether a callback is parallel-safe is inferred, shown in hover, printed signatures and generated docs, and checked at each call.
    - Considered: keeping it as an optional contract on exported functions (2026-11-01), or renaming it `$race_free`.
    - Reason: since items may wait, the tag means only race-free, and inference already enforces that with no tag.
    - [proposals/concurrency/unified/](proposals/concurrency/unified/)
  - **One rounding keyword, `rounding=`** (D31 Q3). It replaces `ties=` on `round`, and `round`, `quantize`, time's `round` and `fmt` share it.
    - Values: `'nearest_away'`, `'nearest_even'`, `'nearest_toward_zero'`, `'nearest_up'`, `'nearest_down'`, `'floor'`, `'ceil'`, `'toward_zero'` and `'away_from_zero'`.
    - The per-type defaults are unchanged: exact values round half away from zero and floats half to even, and `fmt` follows them.
    - `ties=` keeps only `select`'s fairness.
    - Considered: keeping `ties=` on `round` and using `rounding=` only for directed modes; and the spelling `half_up`, which cold readers read both as "toward +∞" and as "away from zero".
    - Reason: directed modes aren't tie rules, and one keyword with one meaning is easier to find.
    - [proposals/time/](proposals/time/)
  - **`x or_throw<E>` forwards only the failures matched by `E`** and leaves the rest in the value (D4 Q2), mirroring `??<E>`.
    - Considered: `or_throw_only<E>`, which cold readers read correctly, where all three read `or_throw<E>` as "throw an `E`".
    - Reason: orthogonality with `??<E>`. The docs teach the two together.
    - [proposals/concurrency/unified/](proposals/concurrency/unified/)
  - **`Canceled` passes through `??`** (D4 Q1). `??`, `?? void`, `?? return/break/continue` and `??<E>` (unless `E` names `Canceled`) don't default it, and a collector never holds it; it leaves the function as `or_throw` would. A program that wants Ctrl-C for itself catches it explicitly (`catch_ctrl_c`, D4 Q4).
    - Considered: `??` defaulting `Canceled` like any other failure, which turns Ctrl-C into a default value and lets a receive loop spin after cancellation.
    - Reason: Ctrl-C must never become a default value or a silent exit 0.
    - **Follow-up requested by David:** a metatag in `$bulletproof` that makes this explicit. The proposal is `$explicit_cancellation` (D4 Q1, open, name not yet cold-read).
    - [proposals/concurrency/unified/](proposals/concurrency/unified/)
  - **Entry points** (direction; it reshapes D31 Q2):
    - Only the `main` of the file given to the `dewy` command runs: `dewy somefile.dewy` runs `somefile.dewy`'s `main`, even if it imports files that define their own `main`. So any library file can carry a `main` as a local test script, like Python's `if __name__ == '__main__'` without the guard.
    - Program-wide settings (`$program.*`, the time-zone settings included) may be set at the top of the entry file, or inside a `main` function in any file. Inside a non-entry file's `main`, they apply only when that file is the entry, so a library can set up its own test configuration.
    - Considered: settings only at the top of the main file (the earlier `$program.*` rule); and D15a's freedom for modules and scopes to set their own zone when the main file sets none.
    - Reason: a library's own test run should need no separate file, and a library should never pick the zone of a program that imports it.
    - [proposals/integration/](proposals/integration/), [proposals/time/](proposals/time/)
  - **Naming style is studied separately** (D10 Q3): snake_case or Julia-style joined words. The proposed renames (`starts_with`/`ends_with` for `startswith`/`endswith`, `set_permissions` for `chmod`, `int(text)` and `float64(text)` for `to_int` and `to_float`) wait for that study. [proposals/bulletproof/](proposals/bulletproof/)

---
  - **Supersedes in this file:** "`??` defaults any exception value" gains "except
    `Canceled`, which passes through unless named"; `??<E>` covers `Canceled` only when
    `E` names it; D14's `?? return/break/continue` and batch 3's C3 follow the same rule;
    rounding's `ties=` becomes `rounding=`; the optional `$parallel_safe` sentence
    (2026-11-01) goes; D15a's module and scope clause gives way to the entry-point rule.
  - **Calling another file's `main`** (David, 2026-11-07): `main` is an ordinary
    function, so it can be imported and called. If a running `main` reaches, possibly
    transitively, another `main` that sets a program-wide `$program.*` tag differently,
    that is a compile error naming both settings. No way to ignore conflicting inner tags
    is added: calling another file's `main` is unidiomatic outside rare cases such as test
    libraries. Considered: a call-site override that ignores the callee's tags.
