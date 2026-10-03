# The optimizing tier

David approved this direction on 2026-10-02. Dewy compiles its own code well
on the direct route instead of leaning on a C compiler. The C route stays an
optional accelerator; it is not expanded.

## Evidence

Throughput batch 3 in [`PERFORMANCE.md`](PERFORMANCE.md) built the same
compiler source several ways. Every build does the same work:

| Build | Self-build |
|---|---|
| direct x86-64 backend | 49.6 s |
| C through GCC `-O2 -flto`, no cross-function inlining | 49.5 s |
| C through GCC `-O2 -flto` | 21.8 s |

The direct backend's code within one function is as fast as GCC's. The
2.3× gap is GCC inlining small callees and then optimizing across what it
inlined. Expanding calls without that follow-up gained nothing (49.6 →
49.5 s with leaf callees; no gain with wrappers).

## Decisions (David, 2026-10-03)

- The optimizer and code generator live in the Dewy compiler.
- The bootstrap sequence is unchanged. The µDewy compiler still builds the
  Dewy compiler from its µDewy output, and µDewy stays a complete, slower
  route to every target.
- No target is special. Development happens on x86-64 Linux, but every
  supported and planned backend and OS must be comfortable. Wasm is of
  particular interest and is developed alongside x86-64, not after it.
- Prefer the architecture that is best for the language long term over the
  smallest change.

## Architecture

```
lowered HIR ──► SSA form ──► optimizations ──┬─► µDewy (expression trees)   every µDewy target
  (statements.normalize                      ├─► wasm (expression trees)
   for debug builds)                         └─► x86-64, AArch64, RISC-V (shared register allocator)
```

- **One target-independent middle.** Inlining, propagation, folding,
  dead-code removal and redundancy elimination run on the SSA form. Every
  target gets them.
- **Thin emitters.**
  - µDewy and wasm both want expression trees, so they share one
    *tree-forming* step: a value with a single use moves into that use when
    nothing between them can change its meaning.
  - The register targets share one allocator over the same form.
  - Encoders are ported from the µDewy object writers.
- **Debug builds** (`debug_names`) keep the existing normalize-and-emit
  route, so every source function and local stays visible.
- **The hosted compiler** stays the unoptimized reference. Behavioral parity
  is unaffected.

## The SSA form

The form is structured: wasm requires structured control flow, the lowered
program already has it, and µDewy text needs it back.

- **Values.** Each value is defined once. Kinds:

  | Kind | Meaning |
  |---|---|
  | parameter | a function parameter |
  | constant | an integer or boolean word |
  | leaf | static data or a function reference: pure, movable, never duplicated |
  | operation | a pure word operation; narrow widths wrap as µDewy emission does |
  | load | reads memory; ordered against stores and calls |
  | call | direct, indirect or an effectful intrinsic (stores, syscalls, frame allocation) |
  | global read / write | ordered like loads and stores |
  | version | a variable's value after an assignment or a join |
  | snapshot | a variable's value, kept by a name bound once |

- **Regions.** A function body is a tree of regions. A region is a sequence
  of items: a value to evaluate, `if`, `loop`, `break`, `continue`, `return`,
  or a *copy* into a merge.
- **Variables are webs.** An assigned variable is one local with a sequence
  of versions. A version is defined by an assignment (a copy item) or at a
  join, where copy items on the joining paths record its sources. This is
  the form wasm locals, µDewy locals and a register allocator consume
  directly.
- **Loops** are unconditional with explicit exits. `loop c { body }` is
  `loop { if c { body } else { break } }`; emitters recognize that shape.
- **Conditions** keep µDewy's lazy `and`/`or`: a condition is a tree whose
  later leaves own the instructions that compute them, evaluated only when
  reached.
- **Scope is lexical.** A value is visible in its region after its
  definition and in nested regions. Optimizations reuse only visible values,
  so every emitter can bind a value where it is defined.

Memory model, as µDewy defines it:
- Loads and stores may alias unless their addresses are provably distinct.
- A call clobbers memory unless the callee is known not to write it.
- Evaluation order and the effects of `__syscall*` stay as written.

## Constraints

- **Compile time is the benchmark.** The optimizer runs on every function of
  every compile, including the self-build it speeds up. Each pass is linear
  or near linear in function size, with explicit budgets: inlining depth,
  inlined size and growth per caller.
- **Measured steps.** Each step lands with a self-build timing and the
  existing gates. Wasm gains are measured on a benchmark set under a wasm
  runtime, since the self-build runs only on x86-64 here.

## Steps

1. **SSA form through µDewy.** Build the form from the lowered program and
   write it back as µDewy through tree-forming. No new optimization yet:
   this proves the form, the builder and the writer on every existing target.
   Copy propagation and removal of unused pure values fall out of
   construction.
2. **Middle optimizations.** Inlining on the form (budgets as measured
   below), constant and branch folding, redundant-load elimination within
   straight-line code.
3. **Wasm and x86-64 emitters**, side by side: wasm from trees; x86-64 with
   the shared allocator. Each is checked against the µDewy route on the
   existing suites.
4. **AArch64 and RISC-V** on the same allocator.

## Emitters (step 3 design)

### x86-64

- **Output: a static ELF executable, written by the Dewy compiler.** No
  assembler and no linker run. Everything a Dewy program executes is Dewy
  code (the prelude makes its own system calls), so the compiler lays out
  code and data itself and resolves every address.
- **Fallback.** A program that needs what this emitter does not cover yet
  takes the µDewy route as a whole: foreign (`extern`) functions, which need
  the system linker; floating-point intrinsics; debug builds.
- **Calling convention.** Internal: the emitter chooses it, since no foreign
  code is called. The process entry reads `argc`/`argv` from the initial
  stack as µDewy's does.
- **Data**, as µDewy defines it:
  - a string literal is its bytes with the length in the word before them;
  - `__static_words__` is a block of words that may hold addresses of other
    static data and functions;
  - `__static_alloca__` is zeroed static storage;
  - globals are words with a constant initial value.
- **Register allocation.** One linear order over the region tree. A value's
  interval runs from its definition to its last use, extended to the end of
  every loop that contains a use but not the definition. A web is one
  interval covering all its versions. Intervals that cross a call take
  callee-saved registers or a frame slot.
- **Instruction selection** reads values directly: single-use values fold
  into address modes and immediates; tests feed branches without
  materializing a boolean.

### wasm32

- **Output: a wasm module from the same trees µDewy emission uses.** Webs and
  bound values are wasm locals; regions map to `block`/`loop`/`if`. No
  register allocation: the engine does it.
- **What limits wasm today is the prelude, not the emitter.** The Dewy
  prelude has no wasm32 layer yet (`ROADMAP.md` Phase 4, "full prelude on
  wasm32"): no allocator on linear memory and no output. The middle
  optimizations already apply to every wasm32 program Dewy can compile,
  through the µDewy route.
- **Measurement.** A benchmark set of prelude-free kernels run under Node,
  comparing the µDewy route with and without the optimizer, then the direct
  emitter.

## Step 1 and inlining, as landed (2026-10-03)

`backend/udewy/ssa.dewy` builds the form from each normalized function;
`backend/udewy/ssa_udewy.dewy` forms trees and writes normalized HIR back.
Every function of the compiler takes the route. A function with a loop
`else` arm keeps the existing route for now.

What construction settled:

- **Variables are webs.** The first version copied every joined variable
  into a new local at each `if` and loop, and µDewy output grew. An assigned
  variable now keeps one local. Its versions are SSA names for that local:
  a copy between two versions of one web writes nothing, so joins cost
  nothing and the output keeps the program's shape.
- **Snapshots.** A name bound once to a variable's value takes a snapshot.
  A value that reads a web's local never moves past an assignment or a
  control structure.
- **Tree forming** pulls operands last to first from the roots that must be
  statements, then from the remaining single-use values latest first. A
  value that has taken operands at its own place never moves afterwards.
- **Inlining happens during construction.** A call to a small function
  builds the callee's normalized body in place, with the callee's own names
  and the arguments as its parameters. No cloning or renaming pass exists.
  - Limits: 40 nodes per callee, 400 nodes gained per caller, depth 3, no
    recursion, no frame or static allocation in the callee.
  - Policy: a callee that calls nothing further is built in place anywhere;
    any other small callee only inside a loop.
  - Early returns run the body as a block that each return leaves. When
    folding leaves one path, the block disappears and the returned value is
    used directly.
- **Folding during construction.** A test of integer or boolean constants
  is decided, and a decided `if` builds only the path it selects. Constant
  arguments therefore specialize an inlined body.
- **Unread variables** are removed with their assignments.

Self-build, cold, interleaved, every compiler building the same source:

| Compiler | Wall | Frontend | Validation | Lowering | Binary |
|---|---|---|---|---|---|
| before the form (`8e004e44`) | 50.6 s | 15.7 | 14.9 | 12.5 | 12.9 MB |
| form, no inlining | 52.3 s | 15.6 | 15.0 | 14.2 | 13.0 MB |
| form with inlining | 50.8 s | 14.8 | 14.5 | 14.0 | 13.2 MB |

- The pass itself costs 2.1 s (`lowering.optimize`): building, forming trees
  and writing 8,200 functions.
- Through µDewy the inlined compiler runs about 5% faster, which pays for
  the pass and no more. This matches the measurements above: the gain needs
  the register-allocating emitters of step 3.
- µDewy text for the compiler is 10% smaller (22.3 MB against 24.7 MB).

Two defects found by the gate, both with regression cases in
`tests/python_misc/test_ssa_form.py`:
- A folded constant was marked by HIR node 0, which is a real literal in a
  program without the prelude.
- Single-use values left over were given their operands in definition
  order, so a later one could carry an earlier one's read of a variable
  past an assignment.

Gate: 6,398 passed.


## The x86-64 emitter, as landed (2026-10-03)

`backend/native/`: `x86.dewy` (instruction encoding), `image.dewy` (the static
ELF executable), `x86_64.dewy` (code for one function from its SSA form) and
`program.dewy` (globals, every function, startup, `main`, the process
entry). It began opt-in (`DEWY_EMIT=native`) and is now the default for
running and compiling on x86-64 (see below). A program it does not cover yet
(foreign functions, floating-point intrinsics, a loop `else` arm) takes the
µDewy route.

- **No assembler, no linker, no µDewy process.** The compiler writes the
  executable's bytes itself and resolves every reference when it places
  code and data.
- **Places by linear scan.** Items are numbered in the order they run. A
  place's span runs from where it is first set to where it is last needed;
  a place set before a loop and touched inside it lasts until that loop
  ends. A span that contains a call takes a register calls preserve (`rbx`,
  `r12`–`r15`); other spans take `rsi`, `rdi`, `r8`–`r10` first; the rest get
  frame slots. `rax`, `rcx`, `rdx` and `r11` are scratch.
- **Evaluated at the use**: a comparison right before its branch becomes
  `cmp` and a conditional jump; an address `base + offset` or
  `base + index * scale` right before its load or store becomes the memory
  operand.
- **Inlining is eager on this route**: every small callee is built in place.

Self-build, cold. The native rows build and are built by the native route:

| Route | Wall | Frontend | Validation | Lowering | Compiler size |
|---|---|---|---|---|---|
| µDewy route (`c13dae29`) | 50.8 s | 14.8 | 14.5 | 14.0 (+5.7 emission and backend) | 13.2 MB |
| native, every value in a frame slot | 99.8 s | 31.6 | 30.8 | 33.1 | 19.0 MB |
| native, registers | 45.8 s | 13.9 | 13.8 | 15.9 | 10.6 MB |
| + address operands, no write-back | 40.9 s | 13.1 | 12.7 | 13.2 | 9.7 MB |
| + eager inlining | 39.8 s | 12.6 | 12.4 | 12.9 | 10.7 MB |

The natively built compiler rebuilds itself to the identical executable.

Defects found on the way, each a liveness or allocation rule:
- A parameter nobody reads shared a register with a live one, and its
  arrival overwrote it. It now has no place.
- A place touched in two sibling loops was kept only to the end of the
  first. Every loop that touches a place set before it now keeps it.
- `[-1 -1 -1 -1 -1]` is one element (a subtraction chain), so each register
  pool held one register. Negative elements are parenthesized.

Still to do on this route:
- build the form straight from lowered HIR (statement normalization is
  5.3 s of the remaining lowering time and only feeds µDewy text);
- redundant-load elimination and values kept across more of a function
  (the C-built compiler is still about twice as fast in every phase);
- foreign functions and floating-point intrinsics; debug information;
- AArch64 and RISC-V on the same allocator; wasm from the tree form.

## After the application baseline (2026-10-03)

The application benchmarks ([`../benchmarks/apps/`](../benchmarks/apps/README.md))
showed where the first emitter's code lost to C; three changes followed.

- **Division by a constant.** The x86-64 emitter turns `//` and `%` by a
  constant of 2 to 2³¹ − 1 into a shift (a power of two) or a multiplication
  by a reciprocal (Hacker's Delight 10-1, computed in signed words), with no
  test for a zero divisor or the overflowing case. Unsigned 64-bit operands
  keep the division. `tests/python_misc/test_ssa_form.py` compares both
  forms against division by the same numbers met only at run time.
- **The test for sharing, in place.** `_unique_array` and `_unique_object`
  were one function each: a test of the owner count, then the copy. They
  are now a small function holding the test and a `_detach_…` function
  holding the copy, so the form builds the test where it is used and only a
  shared value pays a call. This is a change to the lowering, so both routes
  and any later emitter have it.
- **Value numbering.** While a body is built, an operation without effects
  (arithmetic, comparison, load) whose operands are the same values as an
  earlier one's is that earlier value, when the earlier one was computed on
  every path to here: entries made inside an arm, a lazy operand, a loop or
  a block built in place end with it. A load is reused only while no call
  has been made since (stores are calls here) and never across a loop's
  start.

Self-build, same source: 49.2 s on the µDewy route (52.2 s when built by the
previous compiler) and 36.9 s on the native route (39.8 s), executable
9.87 MB; both fixed points hold.

**Default on x86-64.** `dewy FILE` and `dewy -c FILE` for x86-64 now take the
native route. `DEWY_EMIT=bytecode` selects the µDewy route (`=udewy` its
text); a program the native route does not cover takes the µDewy route as a
whole, and `DEWY_EMIT=native` says why. `debug`, `test` and every other
target stay on the µDewy route. The µDewy route is unchanged: the natively
built compiler, asked for bytecode, produces the same compiler executable as
the µDewy-built one. The environment variable is interim; the setting
belongs in the language's build configuration.

Two smaller changes with it: `_reserve_array` is split like the sharing
tests (the capacity test in place, `_grow_array` out of line), and a divisor
that is a power of two up to 2⁶² is reduced, not only those below 2³¹.

What the benchmarks point at next: bounds checks and sharing tests that a
loop repeats without anything able to change their outcome; records stored
flat in arrays; the dictionary probe by key type; `push`.

## Inlining measurements before the SSA form (2026-10-03)

Each row is a cold self-build, interleaved, with every compiler building its
own source:

| Variant | Wall | Frontend | Validation | Lowering | Emission | Backend | Binary |
|---|---|---|---|---|---|---|---|
| no inlining | 49.6 s | 15.4 | 14.6 | 12.3 | 1.7 | 4.0 | 12.9 MB |
| any callee ≤ 40 nodes, separate pass | 50.2 s | 14.2 | 13.7 | 13.4 | 2.3 | 5.0 | 15.6 MB |
| leaf callees anywhere, others inside loops, during normalization | 49.7 s | 14.8 | 14.5 | 12.6 | 1.8 | 4.3 | 13.9 MB |

Broad inlining makes the compiler's own code about 8% faster (frontend and
validation). But the self-build compiles that larger compiler: lowering,
emission and the µDewy backend absorb the gain. Restricting inlining to hot
sites keeps the cost small and loses most of the gain.

Register budget in the µDewy x86-64 backend:
- Values live across calls can use only `rbx` and `r15`; `r12`–`r14` cache
  the expression stack.
- Moving `r13` and `r14` from the cache to locals made the build slower,
  51.7 s against 49.4 s: expression values then spill instead.

Conclusion: GCC's 2.3× needs both inlining and a code generator that keeps
an inlined body's values in registers across a large function. Without
inlining, calls dominate and code quality barely matters (GCC without
inlining ties the direct backend). Without good allocation, inlining buys
about 8%. The plan above follows from this: an SSA form of the lowered
program, with register allocation over all general registers on the register
targets. The inliner prototype is kept outside the tree until the SSA form
can host it.
