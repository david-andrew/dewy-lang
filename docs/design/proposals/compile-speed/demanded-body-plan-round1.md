# Demanded checked-body plans, round 1

## Decision proposed

Do not implement a shared checked-body discovery plan under this round's gate.
Even giving it every existing discovery operation for free saves at most 3.96%
on flagship 99 and 6.54% on 100; together, 4.89%. Its replacement construction,
storage and invalidation would reduce those ceilings. The required pilot bar
was at least 5% on 99/100. Four other structural alternatives also miss it.

This is a proposal for changing which compiler work exists, with a stopping
bound, not a change to language semantics or the processed-line definition.
No production implementation or performance improvement is claimed.

## Scope and acceptance

Planning base: `69e0da651399eefd47badaa094fed6d8e0ae4dd6` (`origin/master` when
the branch was created), 2026-11-12. Research owns this proposal and temporary
instruction-count probes. Non-goals: persistent caches, library images,
parallel compilation, changing proof budgets or obligations, self-hosting
cutovers, the time library, and reopening previously bounded allocator,
fixed-point or fact-state representation experiments. Budget: two hours for
hypotheses/bounds, five hours including any qualified pilot.

A production pilot would need byte-identical `same_output` results and identical
`check --obligations` results over the corpus, followed by focused, quick, twin,
speed, kernel-instruction, golden-case, ladder and fixed-point gates. No pilot
qualified, so none of those production-equivalence claims is made here.

## Five alternatives and their deletion oracles

An oracle retains the actual compiler results and measures the instructions
inside a precisely named set of operations. Its ceiling subtracts those
intervals from the uninstrumented compile, charging nothing for a replacement.
These are optimistic ceilings for the specified designs, not predicted savings
and not bounds on every imaginable implementation of the broader idea.

| Structural alternative | Work assumed free | Risk or limiting condition |
|---|---|---|
| Reuse a module's work within one compile | Repeated checking and lowering of the same function identity | Modules already have canonical path identities; checked bodies already have completion state. No repeated completed-body checks or duplicate nonzero module file identities occurred. The generous remaining allowance is repeated lowering of the initializer, whose global-discovery state actually changes. |
| Carry an empty-obligation certificate from checking | Entire outer `fact_obliged` calls returning false | A certificate must cover generated/replaced nodes, aliases, exact-width demands and policy changes. The final fact walk is already skipped for these bodies; its cost cannot be counted again. |
| Share checked-body discovery between facts and effects | Union of all outer obligation scouting, `fact_slice_prepare`, and effect-body discovery intervals | This includes graph construction and useful classification, not just traversal. Producing their answers still costs something. Callee footprints, demand modes, order-sensitive proof caps and late rewrites prevent unconditional reuse. |
| Emit directly from checked AST for simple functions | All lowering, optimization and emission for every function whose final IR is acyclic and call-free | No size or stack-slot cap in the final oracle. Includes loads, stores and branches. Calls, indirect calls, syscalls, intrinsics, loops and checked arithmetic with helper calls are excluded. Even instruction selection and register allocation are credited as free; a real implementation must preserve them and reproduce the optimizer's output. |
| Reuse relocatable lowering/codegen templates | Later matching pre/post-optimization IR shapes: lowering and optimization; later matching final shapes: emission | Preserve parameter/return types, vreg types, slots, arguments, constants, ABI and other represented IR flags. Normalize function/global/data relocations by first occurrence while retaining alias relationships. Source positions, names and function IDs are omitted. Key formation, relocation and diagnostic maps are charged zero. Context not encoded in IR could invalidate a match. |

The last oracle deliberately allows more sharing than literal IR equality.
Literal equality alone permits only 0.69% across the panel, 0.43% on 99 and
0.27% on 100. Allowing relocation templates still does not approach the gate.

## Measured ceilings

Host: desktop Intel Core i7-6700, x86-64, whose reported hostname is `redfox`;
this is **not** the quiet i5 laptop. All performance numbers below are retired
user-space instructions from hardware counters, one emission worker, default
program builds. There are no desktop wall-clock performance measurements.

`python3 -m tools.core speed --base origin/master` reproduced 145.2k processed
lines/s for the seven flagships. The compiler is unchanged at this point, so
the speed comparison is neutral. Oracle runs use two equal-length source
trees, `~/dev/tmp/speedidea/base` and `~/dev/tmp/speedidea/tree`, built by the
same base compiler into equal-length executable paths. Both executables then
run successively at the **same** `active/bin/dewy-core` path with identical
library, input and output paths. The compiler's own release build setting is
unchanged; the flagship programs use their default build.

Baselines below are medians of three uninstrumented whole-process counts.
Each deletion ceiling is the largest of three oracle runs, with overlapping
intervals counted once. Hooks use the existing `ic_read` hardware counter;
an empty bracket costs 244 instructions. That overhead is retained, making
the estimates more generous. IR serialization occurs outside the measured
lowering/optimizer/emitter intervals. Scratch changes have frozen twins; none
of the probes is part of this proposal's production changes.

All seven native output files were byte-identical between the original and
instrumented compiler, and all seven processed-line reports were identical.
This validates the measurement panel, not the full multi-target corpus.

Each ceiling cell is **instructions removed per processed line (percent of
the whole compile)**. Panel percentages use sums, not averages of percentages.

| Alternative | Seven-flagship panel | 99 | 100 |
|---|---:|---:|---:|
| Module reuse, generous initializer allowance | 12 (0.03%) | 11 (0.02%) | 19 (0.04%) |
| Empty-obligation certificate | 113 (0.26%) | 234 (0.39%) | 101 (0.21%) |
| Shared discovery plan | 1,415 (3.26%) | 2,387 (3.96%) | 3,124 (6.54%) |
| Direct emission, all acyclic call-free final bodies | 408 (0.94%) | 469 (0.78%) | 721 (1.51%) |
| Relocatable IR templates | 618 (1.43%) | 343 (0.57%) | 204 (0.43%) |

The strongest oracle across the complete flagship panel:

| Flagship | Processed lines | Baseline M instructions | Discovery-free ideal M instructions | Maximum reduction |
|---|---:|---:|---:|---:|
| 95 | 6,220 | 298.628 | 290.743 | 2.64% |
| 96 | 3,647 | 175.610 | 168.831 | 3.86% |
| 97 | 6,605 | 299.300 | 289.912 | 3.14% |
| 98 | 11,960 | 386.009 | 377.601 | 2.18% |
| 99 | 5,061 | 305.043 | 292.960 | 3.96% |
| 100 | 3,601 | 171.965 | 160.717 | 6.54% |
| 101 | 3,836 | 137.182 | 135.063 | 1.55% |
| **Sum** | **40,930** | **1,773.737** | **1,715.826** | **3.26%** |

The ideal column is subtraction, **not a measured candidate executable**.
The baseline differs slightly from the speed command's 1,775.9M sum because
the scratch measurement path differs from the speed panel path. Comparisons
within each experiment use identical paths; the two totals are not treated as
a performance change. At this base, 99 is about 104.5k processed lines/s and
needs roughly 48% fewer instructions to reach 200k; the roadmap's 33–35%
statement should not be used as this experiment's denominator.

## Design of a shared demanded body plan

If a future workload supplies sufficient headroom, give each checked function
body an indexed, versioned discovery plan. It records ordered child edges,
local/global definitions and writes, candidate obligations, calls, and the
syntax needed to describe their argument places. Facts and effects consume
that plan instead of rediscovering those relations independently.

Create the plan only when a fact or effect consumer requests the body. Do not
allocate a plan for every function merely because the checker sees it. If a
consumer has already demanded a body while it is being checked, the existing
checker traversal may populate stable plan entries; otherwise use one lazy
builder after the checked body is complete. Keep dynamic fact transfer,
effect propagation and proof decisions in their existing engines.

Use function/body-generation IDs for plan lookup and node IDs for entries and
adjacency lists. Construction is O(V + E) time and space for the demanded
body's syntax nodes and recorded edges, excluding the existing cost of type
and place queries. Discovery consumers visit the relevant indexed entries.
Effect SCC solving and fact demand-closure costs remain; they do not become
O(1) merely because syntax relations are shared.

Separate syntax-stable entries from callee-dependent answers. Preserve the
current fact-plan mode key and footprint/version checks; retain the old
ordering of roots, writers and events because proof limits and witness choice
depend on it. A completed mode must not silently refresh its proof budget
after effects settle. Invalidate or incrementally update entries for generated
nodes, checked-body replacements and alias changes before permitting reuse.
Reentrant checking must not expose a partially constructed plan.

Any new cold builder belongs in a Dewy leaf with its frozen twin. The
implementation would touch the facts/effects consumers only after a new
bound justifies it; it does not require changing the frontend migration,
time-library work, public syntax or library contracts.

## Recommendation

Stop these five implementation candidates at their bounds. The shared plan
is the strongest design, but even its impossible free-result oracle misses
the requested bar on 99 and on the combined 99/100 pair. A broader claim that
all fact transfer disappears through fusion is not justified: inference,
invalidation, joins and proof publication are useful work, not duplicate tree
walking. The next structural brief must identify additional removable work
outside these discovery intervals and measure that work before implementation.
