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

