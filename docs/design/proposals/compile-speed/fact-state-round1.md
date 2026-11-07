# Fact state representation, round 1: measured cost and candidates

Question: can a cheaper fact-state representation make each copy and join at branches and loop
rounds cost much less? The diagnosis this round follows said that 100_rtos_kernel needs every
transfer step to cost about 40% less, by redesigning how `FactState` is copied and joined.

Answer: no. Measured on 100, copying the state costs about 1.5M instructions and joining it about
3.7M, out of 31.0M for facts and 174.7M for the whole compile. A representation that made both
free would give 3.0% on 100 and at most about 0.07% on 99, 96, hello and the self-build (whose
fact transfer outside `exact_prepare` is under 8M). The best realistic design, a delta join,
gives about 1.2% on 100. Under rule 4 this idea family ends at the bound: nothing was built.

## How it was measured

- Host desktop-msi-redfox, base 795559eb7, each compiler at its own fixed point, one emission
  worker (`build --time`, perf user instructions).
- Inside facts: scratch perf probes around functions (inclusive, recursion counted once), per-join
  and per-`if` shape logs, and a phase split of `fact_join`. Probes add about 3.5% overall.
- Function self costs come from callgrind with per-instruction costs. Each `rep movs`/`rep stos`
  is counted once per execution, as perf counts it. Corrected, callgrind totals 173.5M against
  perf's 174.7M, so its self costs are usable directly.
- Nothing of the probes is in the tree.

## The state today

`FactState` (compiler/facts.jo) holds seven value-semantics arrays: `ids`, `bounds` (one
`FactBound` per value), `bindings`, `projections`, `differences` (rows `a - b <= limit`) and
`conditional`. Its hash indexes sit in a one-element `index` box. Arrays are reference counted
and copied on write, so:

- **A branch** copies the struct: 8 reference-count increments (`__h_copy`, 85 instructions).
- **The first write in an arm** clones that one array: allocation plus one `mem_copy`, about
  150 instructions whatever the length under perf.
- **The join** (`fact_join`, compiler/facts_joins.dewy) already keeps shared prefixes: values,
  projections and rows the two arms inherited unchanged keep the first arm's arrays and indexes.
  It hulls bounds in place, merges differing bindings into fresh values, matches the projections
  of merged values, and re-proves rows on the other arm with `fact_distance`.
- **A loop** walks its body once per speculative round (`fact_while`, `fact_iterate`), builds
  each new header with `fact_loop_header` and compares with `fact_loop_stable`. A non-speculative
  final walk then publishes the answers.

## What 100 does (perf unless marked)

Shapes:

| point | count | values | bindings | projections | rows |
|---|---|---|---|---|---|
| `if` entry | 178 (41 speculative) | median 24, p90 51, max 68 | | | |
| join with both arms live | 192 of 373 | mean 28, median 25, max 76 | mean 6.3, max 16 | mean 7.5, max 41 | mean 4.8, max 20 |
| `while` header | 28 rounds | median 10, max 33 | | | |

What the arms change before a join: new values per arm have median 0 and 3 (means 7.5 and 5.4)
over a common prefix of 20.6. Of 6.3 aligned bindings, 0.7 differ. Conditional evidence lists hold
0 to 2 entries. The other 181 joins have a dead arm and cost nothing.

Cost:

| item | instructions | per unit | share of 100 |
|---|---|---|---|
| all facts | 31.0M | | 17.7% |
| struct copies and drops of `FactState` | 1.0M (3,846 copies, 4,793 drops incl. frees) | 85 to 140 | 0.57% |
| copy-on-write clones in facts | ~0.6M (3,919 clones) | ~150 | 0.34% |
| `fact_join`, all callers | 3.7M (373 calls) | `if` 31k, `and`/`or` 7.5k, loop 26k | 2.1% |
| lookups: `fact_slot`, `fact_bound`, `fact_binding`, projection and row finds | ~3.5M | `fact_slot` 55 | 2.0% |
| conditions (`fact_condition`, incl. their captures) | 7.6M (421) | 18k | 4.3% |
| of which `fact_assume` | 2.2M (744) | 2.8k | 1.3% |
| loop headers and stability | 1.7M (42 headers) | 35k per header | 0.9% |
| outermost loop-body walks | 15.8M (56 walks) | | 9.0% |
| of which speculative rounds | 6.4M (30 walks) | | 3.7% |
| return summaries | 7.3M (29) | 250k | 4.1% |
| slice preparation | 6.1M (55) | 110k | 3.5% |

`while` loops took 1, 2, 2, 2, 3, 3, 3, 3 and 3 speculative rounds. Each round re-walks the
whole body. Copying is cheap because a whole-array copy is one instruction under perf: the cost
of a clone is the allocation, not the length.

The join, phase by phase (3.9M with ~0.2M of probe overhead):

| phase | instructions | what scales with unchanged state |
|---|---|---|
| rows: keep shared prefix, re-prove the rest on the peer, rename | 1.14M | re-adding the common prefix; `fact_slot` endpoint checks. The peer queries for changed rows (`fact_distance`, 0.43M) are inherent |
| values: identity checks, prefix, `fact_hull_all` | 0.76M | all of it except hulls of changed bounds |
| matching projections of merged values | 0.68M | pairs whose binding did not change |
| merging bindings | 0.48M | aligned unchanged bindings |
| projections: prefix or intersection | 0.46M | all of it except added projections |
| shared-bindings path and shared rows | 0.25M | most of it |
| payloads, dead-arm returns | 0.15M | |

The other workloads:

| workload | total | facts | `fact_join` | joins |
|---|---|---|---|---|
| 99_dewy_frontend | 252.9M | 9.4M | 0.12M | 18 |
| 96_ct_crypto | 162.3M | 7.2M | 0.03M | 16 |
| hello | 44.8M | 0.03M | 0 | 0 |
| self-build | 12.60G | 170M (162M of it `exact_prepare`) | 2.2M | 207 |

On 99, fact-state copies, drops and clones together are about 0.06M (286 copies, 473 drops,
185 clones).

## Candidates

The bound for every candidate is the state work it can remove, measured above. "100" means
instructions saved on 100_rtos_kernel.

### 1. Persistent maps with structural sharing (HAMT or RRB vectors)

- **Branch:** O(1), as now.
- **Write:** path copying, 1 to 2 node allocations, so about 150 to 300 instructions. Today's
  first write clones an array of at most 76 elements for about 150.
- **Lookup:** a hash and a trie walk, 40 to 80 instructions, against 55 for `fact_slot` today.
- **Join:** pointer equality on shared subtrees would replace the prefix scans: at most the
  values and projections phases, 1.2M.
- **Net on 100:** about 0, possibly worse, since writes and lookups get dearer.
- **Invasiveness:** every `s.ids`/`s.bounds`/`s.bindings` access in about 25 leaves.
- **Proofs:** unaffected if iteration order is kept, but tries do not keep insertion order. Rows
  and projections are scanned in insertion order today, and budgets depend on that order.
- **Verdict:** rejected.

### 2. An undo trail with rollback at branches (as SAT solvers do)

- **Branch:** O(1), a trail height. **Restore:** O(writes in the arm).
- **Join:** the join needs both arms' final states at once. Each arm's changes must be kept as a
  delta before rolling back, so this becomes candidate 3 plus a trail.
- **Bound on 100:** the copies a trail removes, the struct copies at forks and the clones, at
  most 0.9M (0.5%). A trail push per write adds back about 0.15M (~10k writes). Net at most
  ~0.6M (0.35%).
- **Conflicts:** loops hold entry, header, next, back and exits at once. Summaries run nested
  states. `$assert` diagnostics keep `FactPaths.entry`. Push frames and fork entries keep entry
  states. A single mutable state plus a trail cannot hold these without materializing copies,
  which is today's representation.
- **Invasiveness:** the state becomes a global; every `@s` function changes.
- **Verdict:** rejected. This is the pilot the brief suggested (save and restore in the `if`
  transfer). Its slice bound is the 1,860 copies and 1,733 drops in `fact_condition` plus the
  clones its arms make: under 0.5% of 100 before the trail's own cost.

### 3. Delta states, joined by walking the deltas

Each state records, since its fork, which bounds it wrote and which values, bindings, rows and
projections it added or tightened. The join hulls only the written slots, merges only changed
bindings, re-proves only changed rows, and matches projections only for merged pairs.

- **Bound on 100:** values 0.76 → ~0.1M, projections 0.46 → ~0.1M, merged projections
  0.68 → ~0.2M, bindings 0.48 → ~0.2M, rows 1.14 → ~0.6M (the peer queries stay), shared path
  0.25 → ~0.05M. About 2.3M saved, minus ~0.15M for the log. **Net ≈2.1M, 1.2%.**
- **Other workloads:** 99 ≈0.08M (0.03%), 96 ≈0.02M, hello 0, self-build ≈1.4M (0.01%).
- **Proofs:** the join must produce the same state in the same order: values in slot order,
  rows and projections in today's order. Feasible, because changed slots can be visited in
  index order.
- **Risk:** soundness depends on every writer logging: `fact_set_bound`, `fact_bind`,
  `fact_rebind`, an in-place row tightening in `fact_difference`, `fact_add_*`, `fact_compact`,
  `fact_reindex`, the forget paths, and loop materialization. One missed writer gives a join that
  keeps a stale bound, an unsound proof. Tests would catch only some of these.
- **Invasiveness:** medium-high: facts_joins.dewy (fact_join, fact_join_payload,
  fact_join_shared_rows) plus every writer.
- **Verdict:** the most promising candidate, below the 3% bar.

### 4. A sparse representation keyed by the values live at that point

- **Size:** states are already small: median 24 values at an `if`, 10 at a loop header. Scope
  ends already drop dead values (`fact_collect`).
- **Lookups:** a dense value-indexed table with generation stamps would bring `fact_slot` plus
  `fact_bound` from about 93 to about 10 instructions: ≈1.0 to 1.3M on 100 (0.6 to 0.7%).
- **Cost:** a table per state must be copied at each branch, and a global table cannot serve
  several live states.
- **Verdict:** rejected.

### 5. Generation counters instead of clears

Clears are `rep stos`, one instruction under perf. `fact_mark_begin` costs 1.3M under
uncorrected callgrind and 2.3k under perf. Nothing to gain.

### Summary

| candidate | 100 | 99 | invasive | verdict |
|---|---|---|---|---|
| everything at zero cost (bound) | 5.2M, 3.0% | ≈0.2M, 0.07% | | |
| persistent maps | ≈0 or worse | ≈0 | high | rejected |
| trail | ≤0.6M, 0.35% | ≈0 | very high | rejected |
| delta join | ≈2.1M, 1.2% | ≈0.08M | medium-high, soundness-critical | below the bar |
| dense keyed lookups | ≈1.1M, 0.6% | small | high | rejected |
| generation counters | 0 | 0 | | rejected |

## Pilot

None built. Rule 4 asks for the upper bound before building. The whole family's bound on 100,
copies and joins at zero cost, is 3.0%, and the best realistic design gives 1.2% on 100 and
0.03% on 99. The suggested pilot slice, a trail for the `if` transfer, is bounded below 0.5%.
The bound also answers the capability question: 100 needs about 26M out of facts and effects,
and all state-shaped work there (copies 1.5M, joins 3.7M, lookups ~3.5M, headers 1.7M) is about
10M even at zero cost.

## Where facts on 100 go instead

The transfer is many small analyses, each costing hundreds of instructions, plus repeated walks:

- **Slice preparation:** 6.1M. `fact_slice_prepare`'s own body is 2.6M (47k per slice). The rest
  is marking (`fact_mark_begin`), membership (`fact_slice_member`, 1.1M) and index building.
- **Return summaries:** 7.3M, of which 4.6M on summaries that end unknown.
- **Speculative loop rounds:** 6.4M. About 1.25M of it is in loops whose final publishing walk
  repeats a settled round.
- **Conditions:** 7.6M, of which `fact_assume` 2.2M.

A next step should start from one of these, with its own bound measured first.
