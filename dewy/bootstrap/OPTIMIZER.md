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

## Placement

The optimizer runs in the native compiler between statement normalization
and µDewy emission. Its input and output are the same lowered program:
- functions are statement lists over word values;
- control flow is structured (if/loop/break/continue);
- memory is explicit `__load_*`/`__store_*` intrinsics;
- ownership operations are explicit calls.

Emission and the µDewy toolchain are unchanged. Every target benefits,
including C, and the Python µDewy compiler needs no parity work.

The hosted compiler stays the reference and does not optimize. Behavioral
parity is unaffected. Debug builds (`debug_names`) skip the optimizer, so
every source function stays a frame.

## Constraints

- **Compile time is the benchmark.** The optimizer runs on every function of
  every compile, including the self-build it speeds up. Each pass is linear
  or near linear in function size, with explicit budgets: inlining depth,
  inlined size and growth per caller.
- **µDewy semantics only.**
  - Loads and stores may alias unless their addresses are provably distinct.
  - A call clobbers memory unless the callee is known not to write it.
  - Evaluation order and the effects of `__syscall*` stay as written.
- **Measured stages.** Each stage lands only with a self-build timing that
  shows its gain, and its output is checked by the existing gates.

## Stages

1. **Inlining with cleanup.** Expand small callees (renamed locals,
   parameters bound in order, early returns as exits from an enclosing block).
   Then, within the caller:
   - *copy and constant propagation* of single-assignment locals;
   - *constant folding*, and *branch folding* on decided conditions;
   - *dead-code removal* of unused pure values and unreachable arms.

   Inlined helpers' checks (null handles, owner counts, capacity) often
   decide at the call site.
2. **Redundancy.** Local value numbering of pure expressions and loads
   within straight-line segments, killed by stores to possibly aliasing
   addresses and by calls. Hoisting loop-invariant loads where the loop
   provably stores nothing that aliases them.
3. **Allocation.** Larger inlined bodies hold more live values. If the µDewy
   backend's five allocatable registers then limit the gain, widen its
   budget, or emit x86-64 from an SSA form of this program directly. That is
   decided by the stage 2 measurements, not in advance.

Stage 0 is the scaffolding: the pass boundary, counters (inlined sites,
folded branches, removed statements) and timing under `lowering.optimize`.

## Stage 1 measurements (2026-10-03)

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
about 8%. The next step is therefore stage 3 rather than more stage 1 tuning:
an SSA form of the lowered program with register allocation over all
general registers. That is a substantial new code generator. Whether it
emits machine code from the Dewy compiler, or replaces the µDewy backend's
single-pass emitter, is open for David. The inliner prototype is kept outside
the tree until a code generator can use it.
