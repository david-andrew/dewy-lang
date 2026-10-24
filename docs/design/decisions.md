# Decisions

David's standing decisions on Dewy's surface and semantics, newest last within
each topic. ROADMAP.md lists them in one line each; this is the full text.

- `int`: arbitrary precision with word storage where proven. `intN`/`uintN` wrap.
- Zero-argument calls may omit or include the parentheses.
- A bare function name calls; `@fn` is the handle.
- No traps by default (10-21; supersedes "ordinary code keeps runtime
  checks"): every partial operation is proven, handled as a value
  (`xs.get(i)` → `T | none`) or checked with `$runtime_assert`; unproven is a
  compile error with a fix-it. `$runtime_checks` (module/function/block) is the
  production opt-in: unproven obligations become reporting checks, listable via
  `check --obligations` and an LSP hint. `$prototype` keeps its archived
  semantics (runtime deferral with a `prototype:` warning per site).
- Boolean metatags accept `$tag`, `$tag = true`, `$tag = false`.
- Strict lane is `$no_hidden_costs`: a library-defined module bundle over
  function rows (`& no allocates`, …) plus `$explicit_copies` semantics; forbids
  hidden allocation, detach, implicit costly copies and `$runtime_checks`/
  `$prototype`; `$no_hidden_costs = false` opts a scope out. `$realtime` is
  reserved for a future stronger bundle (no blocks, bounded stack).
- Compile speed: 250k lines/s single-threaded in the default build (200k
  minimum), on representative code. Parallelism is a bonus.
- Concurrency direction (docs/design/safety_and_concurrency.md, "Adopted
  direction"): no coloured functions, groups-only spawn, level-triggered
  `Canceled`, first failure cancels siblings, two lanes, deterministic
  reductions, bounded channels, explicit atomic orders, no language actors.
  The parallel loop is the keyword `parallel` (`parallel i in [0..10) {…}`,
  `[parallel x in xs x*x]`).
- Concurrency spellings (provisional until seen in real programs):
  `concurrent { let a = spawn f() … }` joins at the brace; `concurrent g {…}` with
  `spawn(g) expr` for longer-lived groups. `blocks` is an inferred effect,
  written only as `& no blocks`. `Canceled` (US spelling; `Cancelled` gets a
  fix-it error, not an alias). `within(2s @get(url))` (tentative) and `race(…)`
  are library helpers. `Atomic<T>` ops take an optional compile-time
  `MemoryOrder` literal ('relaxed'|'acquire'|'release'|'acq_rel'|'seq_cst',
  default 'seq_cst').
- GPU: computation follows data with explicit placement (`x.to(dev)`,
  `.to('best')` or a pushed device context); mixing devices is a compile error,
  tracked as a device-equality fact. A `parallel` body with no blocks, allocates
  or syscalls over arrays and scalars is GPU-eligible. Designs stay
  device-agnostic; nothing to build yet.
- No library image: fresh compiles only. Hello-world is a ~50 ms guardrail.
  Library floor (confirmed 2026-10-21): lazy loading only. Parse and check only
  the declarations and the bodies a program reaches; no precomputed library
  summaries and no images.
- Decimal literals adapt to context: exact unless next to a float64 operand, in
  a float64 parameter or field, or the binding is later written a float; then
  float64 at compile time (`0.1+0.2 =? 0.3` stays true).
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
- Inference keeps the most precise type it knows; only an explicit wider
  annotation widens (literal unions; integers keep range facts).
- `end` and `new` are reserved: `end` is the last index inside an index; `new`
  inserts a singleton axis (NumPy `newaxis`): `xs[new ..]`, `xs[.. new]`.
- Versions: the language stays 0.0.0; the extension gets patch bumps only, at
  most one release a day.
- Tensors (Q7): one `array` type with shape in the type
  (`array<T length=[m n]>`, symbolic dims checked by the fact engine); no
  `.shape`, `.length` is the source of truth; Julia/MATLAB dot broadcasting
  (`a .* b`, `f.(xs)`) plus plain `a + b` (same shape) and `A * B` (matmul);
  NumPy broadcast rules; orientation-free 1-D; contiguous N-d literals
  (newline rows, blank-line blocks, standalone `;`); `m[i j]` indexing. Full
  text: [tensors.md](tensors.md). Queued after concurrency stage 1.
- Safety configuration: orthogonal boolean metatags plus purpose-named,
  library-defined bundles. Docs present a loosest-to-strictest ladder:
  `$prototype`, `$runtime_checks`, the default (no traps), `$explicit_copies`,
  `$no_hidden_costs`, `$explicit_allocation_failure`. No numbered levels.
- Allocation (Q4): an implicit pushed context allocator (Jai-style), heap by
  default. Ordinary allocation is infallible; true OOM ends the process with a
  report (an environmental failure, outside no-traps).
  `$explicit_allocation_failure` (top level) makes every allocating function
  return `T | OutOfMemory`. Under `$no_hidden_costs`, capacity is acquired
  explicitly (an arena returns `Arena | OutOfMemory`); use proven within
  acquired capacity can't fail (resource_exhaustion.md).
- Floats (Q8): strict IEEE 754 by default (NaN, ±Inf, signed zero and
  subnormals are values; no reassociation or FMA contraction; deterministic
  reduction order; value-preserving float→int; sorting by totalOrder).
  Orthogonal opt-ins: `$fast_math`, `$no_nan`, `$no_inf`, and the bundle
  `$finite_floats`.
- FFI (Q12/Q24): `$extern` is a body-position metatag with optional keyword
  arguments (`=> $extern`, `=> $extern(name='Sleep' lib='kernel32')`). It
  replaces the `extern` keyword, which is un-reserved. `$export` (provisional)
  makes a function callable from C, Rust and Python. Calling `$extern` or
  dereferencing a raw `ptr<T>` (provisional; `ptr<T>?` nullable) needs an
  unsafe boundary. The goal is batteries-included Dewy with seamless,
  bidirectional FFI (C, C++, Rust, Python, JS/wasm); header bindgen comes
  later. A blocking-style `net` module returns `| NetError | Canceled`, over
  FFI for now.
- `$target` keeps its spelling. Canonical names with only the fields they need
  (`x86_64`, `aarch64-linux`, `riscv64-freestanding`, `c-linux`, `aarch64-mac`,
  `x86_64-windows`, `wasm32`, …; not LLVM triples), per the archived
  status.md list. OS and arch are selected by compile-time conditions on
  `$target`.
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
- `%` stays floored, with no mode metatag; alternatives are explicit, e.g.
  `a.rem(b kind='euclid')` (exact spelling to propose).
- Rounding: human-oriented types (rational, decimal, int division results)
  round half away from zero (`round(2.5)=3`, `round(-2.5)=-3`); floats follow
  IEEE ties-to-even. Both take `ties=` to override.
- Lifecycle hooks: copy and move hooks preserve the abstract value; move hooks
  cannot fail. No explicit `move` syntax for now.
- Units (round 5): display is automatic, picking a sensible unit per kind, with
  likely display units chosen for derived expressions; `x as unit` overrides
  and converts (`l as inches`). Offset units do what people expect: `20°C` is a
  point, but read as a delta when added to or subtracted from a point
  (`start + 20°C`); point − point = delta; scaling works in the value's own
  unit. `(20°C as °F)` converts as a point (68°F), but as a delta (36°F) when
  used as a delta: infer delta-ness from use, or document the rule. Rational
  dimension exponents are allowed (V/√Hz), so `sqrt` of odd powers is valid.
- Time: `month`/`year` combine only with real dates. Long-term direction in
  [time.md](time.md).
- Invariants: types declare invariants; construction proves them (or checks
  them under `$runtime_checks`) and mutating methods re-establish them. Richer
  properties ("sorted", "validated") are brands minted only by trusted
  validators; later, user-defined validators via compile-time code. Public
  interfaces use written contracts; inferred facts stay private.
- Resources: no blanket guarantee; practical tools (size-limited input APIs,
  default parser depth limits, `within` deadlines, static stack bounds where
  provable) and specific error values for failures that can't be ruled out.
  Goal: the highest-safety configuration handles every resource-exhaustion case
  (heap and stack), as a future bundle on top of `$explicit_allocation_failure`.
- Index-typed refinements: deferred until real code needs them.
- `Send`/`Sync` are inferred structurally; `$send = false`/`$sync = false` on a type
  is a safe opt-out; claiming either for a type the compiler can't verify needs
  an unsafe boundary.
- Conversions: `uint8<overflow='wrap'>(x)` keeps the low bits; same-size reinterpretation
  is the infix word `f transmute uint64` (like `as`). No `.bitcast`/`.wrap`
  method spellings.
- Iterator control: bind the iterator and loop over its place:
  `let w = tree.walk` then `loop node in @w { if skip?(node) w.skip_children }`;
  also `w.seek(i)`. A one-line binding form may come later (`as` is conversion).
- `mod(a b)` is a free function with `kind='floor'` (default, same as `%`),
  `'euclid'` or `'trunc'`. Not `rem`, not a method.
- Indexed iteration is always `loop i in 0.. and x in xs`: no `enumerate`, no
  `indexed`.
- `$build`: a compile-time record like `$target` (`$build.mode =? 'release'`,
  `$build.debug`). Project flags (e.g. BOOTSTRAP) are ordinary consts in a build
  module the entry module overrides; no CLI `-D` flags.
- File helpers are `Path` methods: `p.copy_to(q)`, `p.rename(q)`, `p.make_dirs`,
  `p.walk`, `p.glob"*.dewy"`, `p.size`, `p.modified`, `p.chmod(...)`; `env`
  stays in the prelude.
- An ambiguous partial application of an overloaded function is a compile error
  asking for an annotation.
- A closure inside a method changes the object's fields only through an
  explicit `@` capture.
- Printing details: approved as provisionally implemented.
- Tests: one process per `$test`; `--json` stays provisional.
- Escapes: an unknown escape of a letter or digit (`\N`) is an error; any ASCII
  punctuation may be escaped to itself (`\}`, `\{`, `\'`, `\"`, `\\`).
- `and=`/`or=` short-circuit: `a and= f()` means `a = a and f()`.
- Places from handles (round 6): `lock` is a method; under the whole-route `@`
  rule `@shared.lock` is the method handle, and `@(m.method())` takes the place a
  method returns (grouping makes the call happen). Legal only when the method
  is declared to return a place; `@` of an ordinary temporary stays an error.
  Derived places are checked lexically (no lifetime annotations); replacing or
  releasing the handle while such a place is live is a compile error; the guard
  releases after the place's last use (`let a = @(shared.lock())`; `a.balance += 10`;
  `saved = @a` is an error).
- Common parent: literals of sibling types infer the most precise type:
  `[Circle[...] Square[...]]` is the positional `[Circle Square]`, accepted where
  `array<Shape>` is expected. After writes the binding's type becomes the
  covering element type `array<Circle|Square>`; flow-sensitive facts keep exact
  statically known contents and length (`shapes[2]` is a `Circle` after a known
  push) and fade when knowledge runs out (loops, a small position cap).
- Uniform precision: an unannotated binding's type covers every value written.
  Strings are discrete literal unions (`'quiet'|'normal'|'verbose'`); ints are
  ranges (`1..2`, which equals `1|2`); `n += 1` widens the covering set; an
  unbounded written set (loops, `count += 1`, `mode="{mode}!"`) widens to the base
  type. This supersedes "ints widen to the base type".
- `main` is optional: without it a file runs top to bottom as a script; with it,
  `main` runs automatically exactly once; an explicit top-level `main()` call is
  an error (recursion inside `main` is fine).
- `transmute` (`f transmute uint64`) is Dewy's original spelling, restored in
  place of `bitcast`.
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
- Compile speed framing (A, 2026-10-21): the north star is 200–250k lines/s
  single-threaded on real code (the flagships, not synthetic), default build;
  parallel workers are measured but secondary. It takes a different compiler
  architecture, not tuning, via a strangler-fig migration (not a rewrite).
  Track A: the five structural fixes (milestone: flagship median ≥ 50k lines/s
  single-thread). Track B: B0 per-phase per-node cost budgets gated on the
  flagship panel (~1.2k instructions/node total); B1 an architecture design
  (docs/design/compiler_architecture.md; Astra designs, Sol audits; internal
  architecture needs no sign-off, so B2 starts once the audit agrees the budgets
  can plausibly reach the goal); B2 phase-by-phase migration behind stable interfaces, most
  expensive first; B3 new import-cycle-leaf modules written in Dewy. Track C:
  capability work continues. No precomputed library summaries or images
  without David's explicit approval.
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
- Fixed-width integers (decided 2026-10-22; supersedes "`intN`/`uintN` wrap"):
  arithmetic on `intN`/`uintN` is exact, like `int`; the width is a storage
  property plus facts. Storing into an `intN`/`uintN` binding, field, parameter
  or return is the proven narrowing: free when proven, a compile error with
  fix-its (guard, overflow policy, `$runtime_checks`) when not, a runtime check
  under `$runtime_checks`, always an error under `$no_hidden_costs`.
  Intermediates never overflow spuriously; the compiler picks a wide enough
  machine width (widening multiply for `int64*int64`), never a bigint. The
  overflow policy is a keyword type parameter: `uint32<overflow='wrap'>` wraps
  modulo 2^N (hashes, RNGs, checksums, crypto), `uint8<overflow='saturate'>`
  clamps. Types are callable conversions: `uint8<overflow='wrap'>(x)` keeps the
  low bits and replaces `wrap<uint8>(x)` (removed, no alias);
  `uint8<overflow='saturate'>(x)` clamps; `transmute` stays for same-size
  reinterpretation. `//`, `%`, negation and `abs` follow the same rule
  (`int64.min // -1` is a narrowing obligation); plain `int` `MIN // -1`
  promotes.
- Safety-audit decisions (2026-10-23):
  - `panics` effect: "may fail a runtime check" (and any other possible panic)
    is an inferred effect visible in rows. A no-traps scope cannot call code
    that `panics` unless it opts in with `$runtime_checks`; `& no panics`
    forbids it outright; `$no_hidden_costs` includes `no panics`. A dependency
    built with `$runtime_checks` cannot crash inside a caller that did not opt
    in.
  - Closure capture writes: writing an implicitly captured variable is a
    compile error with two fix-its, `$capture name` (the closure's own private
    state) or `$capture @name` (share the outer variable).
  - A later assignment that changes a binding's initially inferred type (e.g. a
    decimal literal adapting to float64) is a warning plus an editor squiggle,
    not an error. For decimals the diagnostic focuses on exact equality checks
    (`=?`, `not=?`) whose result the adaptation affects. Idiomatic code states
    the representation; relying on implicit adaptation is unidiomatic.
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
  - A splat import that shadows a prelude name warns, naming both sources; the
    warning goes away when the name is selected explicitly or the module is
    imported `as`. Splat imports stay.
  - Big-int parsing limit: `to_int(s max_digits=…)`, default about 1M digits,
    returns an error value beyond it (as Python did for CVE-2020-10735);
    conversion in both directions is subquadratic.
  - `secret<T>`: a zero-cost compile-time wrapper (representation is just `T`)
    whose value cannot reach any output or formatting path (interpolation and
    printing, error messages and payloads, runtime-check reports, `main`'s error
    output, debugger and LSP hovers, where it shows `<redacted>`), except
    through one explicit, visible reveal operation (spelling pending David's
    approval). Later it can drive constant-time checks in crypto code.
  - Runtime failures don't leak data: a missing-key panic reports only that the
    key is missing (did-you-mean hints are compile-time only); an error reaching
    `main` prints its type and `message` (full payloads in debug builds only).
    Dictionaries hash with a per-process seeded keyed hash and iterate in
    insertion order. `min`/`max` follow IEEE 754-2019 minimum/maximum (NaN
    propagates); float sorting uses totalOrder; float dictionary keys carry a
    not-NaN obligation. `main`'s `exit_code` is constrained to 1–100.
- Path guard (decided 2026-10-23; amends contained paths): `root.contains(p)`
  returns `bool` and works as a guard; the solver narrows `p` to `SafePath` in
  the true branch (`if root.contains(f) { serve_file(f) }`), as
  `if i <? xs.length` proves an index. `root.contain(p)` stays the expression
  form returning `SafePath | PathEscape` for `or_throw`.
- Multi-expressions (decided 2026-10-23; restores the reference): an expression
  may produce one value, several values for a surrounding collector, `void`, or
  `never`. A block evaluates its expressions in source order and expresses each
  non-`void` result; a context requiring one value rejects a block that can
  produce an incompatible number of values. This holds in every construct
  (blocks, function bodies, `if`/`match`/`loop` arms, loop capture, collectors),
  so `pair = () => { 1 2 }; [pair()]` is `[1 2]`. Full semantics in
  [multi_expressions.md](multi_expressions.md).
- Refinements prefer partial operators (decided 2026-10-23): where a refinement
  is a single comparison or test against the value, the idiomatic spelling is
  the reference's partial operator (`b:int64<(>=? a)>`), not a lambda
  (`b:int64<v => a <=? v>`); docs, examples, diagnostics and fix-its use it.
- The current compiler's implementation language is Sloppy (`.jo` is its file
  extension); docs and diagnostics name it accurately, never "Jo".
- Follow-ups (decided 2026-10-23): the site tagline is "Python-like ease.
  C-like speed. Safer than Rust.", backed by a page of concrete differences. The
  game library's vector magnitude is `v.norm` (MATLAB/Julia/NumPy term;
  extends to `v.norm(p=1)` and matrix norms); the free `length(v)` is removed,
  and `.length` means element count everywhere. Type-directed juxtaposition
  multiplication (reference operators-and-precedence.md:24-35) is on hold pending
  David's review of its readability and safety; literal coefficients keep
  today's behavior and the docs stay neutral. The boolean path guard stays
  `root.contains(p)`; the value-returning validator is being renamed (too easy to
  confuse with `contains`), name pending.
- Decimal default (decided 2026-10-23): exact rationals stay the default; no
  decimal-float default. Principle: an expression's value never depends on
  whether the compiler folded it, so `a = 0.1 b = 0.2; a+b =? 0.3` and
  `x = 1/3; x*3 =? 1` are true everywhere. Costs addressed: an exact value carried
  around a loop through `*` or `/` (size can grow each iteration) gets a warning
  with a fix-it to annotate `float64` or another explicit representation, never
  an automatic switch; values print the way they were written (decimals as
  decimals, with a repeating marker when non-terminating; written fractions as
  fractions), with the exact display rule reported to David.
- Contained paths and untrusted input (decided 2026-10-23; design in
  [contained_paths.md](contained_paths.md)): `Path` stays the everyday type and
  flows freely. `SafePath` is a `Path` with a proven brand ("does not escape its
  base"); only trusted validators create brands, and the compiler applies it
  automatically to paths built from hardcoded text, other `SafePath`s, or
  components proven safe (one component, no `/`, not `.`/`..`, not empty).
  Untrusted is a tracked fact, not a kind of value: text from external input
  (network, stdin, file contents, environment, command line) carries an
  untrusted brand; a path built from it is a plain `Path`, not a `SafePath`, and
  passes through `Path` code freely (`UntrustedPath` may name it in signatures;
  it is not an exception type). `root.contain(p)` returns
  `SafePath | PathEscape`; functions that care take `SafePath`, and passing an
  unvalidated path is a compile error with a `root.contain(p) or_throw` fix-it.
  Safety net: a warning when an untrusted-derived path reaches a filesystem
  operation without `contain`. Later: `root.open_beneath(rel)` for symlink
  escapes (openat2 RESOLVE_BENEATH or equivalent); the same untrusted brand can
  guard process spawning, SQL and HTML sinks. This is the first user of the
  untrusted-input brand in safety_and_concurrency.md, built generally.
- Path validator name (decided 2026-10-23): `root.confine(p)` returns
  `SafePath | PathEscape`; `root.contains(p)` is the bool guard narrowing `p` to
  `SafePath`. The name `contain` is gone.
- Deadlock freedom (adopted direction, 2026-10-23; full text in
  [safety_and_concurrency.md](safety_and_concurrency.md#deadlock-freedom-adopted-direction-2026-10-23)):
  inferred lock order with no user-written ranks; compile errors only for
  demonstrated deadlocks, warnings for undecided cases; a multi-lock in canonical
  order (`DuplicateLock` on a repeated handle; spelling pending); `try_lock`
  returns a place or `Busy`; `$no_deadlocks` requires a compositional certificate
  for every wait, under stated assumptions (fair scheduler, terminating local
  computation, cooperating peers). Monitored `Deadlock` scopes and STM come later,
  only when needed. Timeouts are recovery, not proofs. Juxtaposition
  multiplication remains on hold.
- Juxtaposition multiplication (decided 2026-10-23; replaces the reference's
  fully general rule; full text in [juxtaposition.md](juxtaposition.md)): a
  restricted, type-directed rule with no whitespace between the parts. Eligible:
  a numeric literal before a name/member term or group (`2x`, `2sin(x)`,
  `3(a+b)`); a named numeric value or field route before a group (`a(x)`,
  `material.k(T)`); a parenthesized scalar before a group (`(a+1)(a-1)`). The
  left side must be a statically known, non-callable numeric scalar or quantity,
  and the group supplies exactly one value. The head is classified once, before
  any implicit zero-argument call; a failed call never falls back to
  multiplication. Precedence: member/call/index > `^` > juxtaposition >
  `* / // %` > unary `+ -` > `+ -` > comparisons. Whitespace products, call or
  index results as coefficients, tensors, numeric `@a(x)` and string-literal
  calls are excluded with diagnostics. No spaced units anywhere (`9.81m/s^2`;
  `9.81 m` is two expressions).
- Multi-lock spelling (decided 2026-10-23):
  `let [a b] = @(lock_all(from to)) or_throw` acquires in canonical order
  (`from == to` gives `DuplicateLock`); each lock is released after its place's
  last use. `try_lock` is a method returning a place or `Busy`
  (`match @(m.try_lock()) {...}`).
- Idiom: when taking the place returned by a zero-argument method, write the
  optional parentheses: `let a = @(acct.lock())`, not `@(acct.lock)`.
- Bulletproof principle (David, 2026-10-23): "I want to be able to write an
  actually bulletproof program that accounts for every eventuality, with the
  compiler enforcing it." Every convenience axiom or assumption has a metatag
  that turns it off and demands the proof instead. They are tracked in one list
  ([assumptions.md](assumptions.md)) so the strictest configuration can be a
  library bundle.
- Answers on pending items (decided 2026-10-23):
  - Counter progress axiom: default on. A 64-bit counter or accumulator that
    grows by a bounded amount per iteration or allocation cannot overflow;
    32-bit and narrower counters get no axiom. An opt-out metatag (spelling
    pending David) disables it and requires a real proof.
  - Multi-value function type: `:>(int64 int64)`; parentheses group several
    result values.
  - `secret<T>` reveal: `s.reveal`. Sealed secrets (reveal requiring a key or
    capability) may come later.
  - `$runtime_assert` makes its function `panics` for callers in other modules,
    not within its own module.
  - `regex(p)` returns `Regex | RegexError`; literal patterns are checked at
    compile time.
  - Quantities print without a space: `1500m`, `20°C`.
  - `s.byte_slice(a b)` (proven char boundaries) and `b.read<uint64>(i)`
    (proven in bounds, no `$unsafe`).
  - The float and net provisional sets are approved.
  - `$no_nan` does not assume incoming values: callers prove not-NaN, or it is
    checked under `$runtime_checks`.
  - Delimited-argument calls `f[…]` and `printl'…'` are approved.
  - `to_int` returns a specific error kind saying why it failed (unparsable, too
    many digits, …) instead of `none`.
  - Paths from command-line arguments or the environment do not warn at
    filesystem operations, but stay untrusted for other sinks.
- Corrections (decided 2026-10-23):
  - Loops have exactly one form, `loop <condition> <body>`, and are not
    whitespace sensitive; an infinite loop is `loop true <body>`. The
    provisional "`loop { … }` loops forever" rule is removed.
  - No local precedence exception for `loop c in s as array<uint8>`. Operator
    precedence starts from the archived Python implementation's table, adjusted
    only where it would confuse; deviations are reported to David.
  - Multi-expressions: a `:>void` function whose body expresses values is an
    error (attach `;` or change the return type). `void | E` expresses `E` when
    it fails and nothing on success. `[1 2; 3 4]` is valid (the attached `;`
    discards `2`, giving `[1 3 4]`), with a warning and a ` ; ` fix-it when it
    looks like a mistaken row separator.
  - Juxtaposition: `]x` stays a parse error. A parenthesized numeric expression
    followed by a name or number multiplies (`(5)x`, `(x)2`). A parenthesized
    callable followed by a delimited argument is a call (`(p)r"..."`,
    `(f)[1 2]`, `(f)(x)`). Any expression immediately followed by an empty
    `()` is a call. `a(x).abs()` and `a(x)[i]` are rejected only when `a` is
    numeric (idiomatic: `abs(a(x))`).
  - Unpacking: `[a b] = …` and `(a b) = …` both unpack whenever the right side
    provides a compatible number of values, including multi-valued calls, rest
    (`(a b ...c) = (1 2 3 4 5 6)`), nested patterns and renaming, following
    resources/discussion_points.md "Unpack syntax". Call-argument and signature
    destructuring is undecided.
  - Untrusted-input markers are metatags, not `@` (which means places):
    `$sink(path)` and `$guard(SafePath)` on library declarations, and a source
    marker in place of `__untrusted(x)` (exact forms proposed to David).
