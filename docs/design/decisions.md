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
