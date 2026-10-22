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
- Boolean metatags accept `$tag`, `$tag=true`, `$tag=false`.
- Strict lane is `$no_hidden_costs`: a library-defined module bundle over
  function rows (`& no allocates`, …) plus `$explicit_copies` semantics; forbids
  hidden allocation, detach, implicit costly copies and `$runtime_checks`/
  `$prototype`; `$no_hidden_costs=false` opts a scope out. `$realtime` is
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
  `concurrent { let a=spawn f() … }` joins at the brace; `concurrent g {…}` with
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
  the error kinds, below 126. An error type may pin its code with an `exit_code`
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

