# Register allocation, round 1: what splitting live ranges can recover

## Decision proposed

Do not build live-range splitting at loop boundaries. Measured on the compiler's
own code, it can remove at most 0.45% of the flagship panel's instructions, far
below the 6.5 points of stack traffic that the codegen plan
([codegen-gap-round1.md](codegen-gap-round1.md), item 2) hoped it would
recover. The traffic does not come from loops that have free registers. It
comes from values that stay live across calls, competing for five callee-saved
registers. A sixth one (rbp, in frames addressed from rsp) was tried as the
retry and saved 0.58% of panel instructions, so it was not kept either.

This note is a measurement. It changes no compiler source.

## Method

- Base `5c3c774a4`, desktop i7-6700. Instruction counts come from Callgrind
  with per-instruction costs, over the seven flagships compiled by a release
  compiler at its fixed point (2.21G instructions in all).
- An instrumented emitter (scratch only) logs every frame access it encodes,
  together with its IR position. An access counts as spill traffic when its
  frame offset is the spill slot of a vreg the allocator left in memory, or a
  caller-saved register's save slot around a call. Each access is then
  classified by the innermost IR loop that contains it, and by whether that
  vreg is defined anywhere inside that loop. Joining these logs with the
  Callgrind costs gives dynamic counts.
- **Loop bound:** for each innermost loop, the registers that a split could
  give its spilled vregs. These are the pool registers with no interval
  overlapping the loop, plus registers whose holder is not mentioned anywhere
  in the loop (as if every idle holder could be evicted for free). When the
  loop contains a call, only callee-saved registers count. They are assigned
  greedily to the spilled vregs with the most static accesses in that loop.
  This is an upper bound: evictions, entry loads and exit stores are not
  charged.
- **Register oracle:** the release allocator is rerun with rbp as a sixth
  callee-saved register, and the dynamic accesses of each spilled vreg that
  then gets a register are summed. Vregs it displaces carry 1.1% of the
  weight the gaining vregs carry.

## Measurements

Dynamic spill traffic, as a share of the panel's 2.21G instructions:

| Class | Share | Loop bound: has a register |
|---|---:|---:|
| Inside a loop, vreg defined in that loop | 2.31% (1.66 reads, 0.65 stores) | 0.16% |
| Inside a loop, vreg invariant in that loop | 0.99% | 0.29% |
| Outside any loop | 2.07% | — |
| Saves of caller-saved registers around calls | 0.39% | — |
| **Total** | **6.2%** (about 137M accesses) | **0.45%** |

- Splitting at loop boundaries is bounded at **0.45%**, even with evictions
  and boundary moves left uncharged. Loops that spill have no idle register:
  their registers are held by values the loop itself uses, mostly values live
  across the loop's calls. The heaviest functions are `opt_rewrite`,
  `opt_cleanup`, `o_sra`, `dx_lex` and `backend_analyze`. In `opt_rewrite`,
  for example, each spilled vreg crosses 13 to 291 calls.
- An IR prepass that copies each loop-invariant value into a fresh vreg at
  loop entry (round 1's scratch pilot) costs +2.5% on 99. The current
  allocator does not reuse those copies; it pays for them.
- The callbacks_literal specimen (+10% when entry zeroing removed a local copy
  that happened to split a range) shows the mechanism, not its size: a split
  pays only where a register is free inside the hot region.
- **A sixth callee-saved register (rbp)**, oracle: 1.19% of the panel; 1.00%
  of that is in functions that keep an rbp frame today. Implemented, it
  requires:
  - a frame-base pseudo-register in the encoder, so that rbp can hold a value;
  - rsp-addressed frames wherever rbp is allocated;
  - frame-table rows that record where rbp is saved, with the Linux backtrace
    walker restoring it from there;
  - no rbp allocation on Windows, in debug builds, at C boundaries, or in
    watch and repl images.

  Measured result:
  - panel −0.58% and self-build −0.73% in instructions. 99's stack accesses
    fell only 0.26%: rbp's own save and restore in small hot functions, and
    longer rsp-relative encodings, take back much of the oracle's gain.
  - kernels: callbacks_literal default +1.53%, over the 1% gate. On its hot
    loop, nine stack accesses per iteration were removed, but three padding
    NOPs and eight other instructions were added.

  - redfox cycles (15 interleaved runs, CPU 2): self-build −0.40%, but
    flagships +0.44% to +1.74% and ladder 84 +1.71%. The longer encodings cost
    more cycles than the removed accesses save.

  The patch is kept as scratch only.

## Where the 6.5 points actually are

GCC, given the same IR, executes 58M stack accesses where the native host
executes 172M. Measured here, the native excess is call-crossing pressure in
large functions, plus straight-line traffic: 2.07% of the panel is spilled
values accessed outside any loop. Splitting regions cannot recover either:
there is no free register to split into. What is left is reducing the number
of values that live across calls:

1. **Rematerialize** cheap values (addresses, compares, loads of
   loop-invariant fields) at their uses instead of keeping them live across
   calls. Values that are defined by a single instruction from operands
   available at the use would no longer need a register across the call.
2. **Shrink the IR's live values** before allocation: sink definitions to
   their first use, and stop the lowering from producing long-lived copies.
   The callbacks_literal specimen is one such copy.
3. **Inline helper fast paths** (plan item 7): every call that is removed
   frees the callee-saved pressure around it.

Each of these needs its own bound before any pilot. None is a splitting
allocator.
