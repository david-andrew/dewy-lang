# Move the hot compiler without a throughput tax

## Decision proposed

Finish milestone 1 by moving coherent hot execution groups through the existing
mixed-language ABI. Preserve the algorithms, indexed state and storage ownership
at each cutover. Do not introduce a host callback for a scalar read. Use explicit
wrapping words for machine arithmetic; use proved array operations where possible
and narrowly justified raw reads where the compiler already maintains the bounds.
General improvements to Dewy's generated code are preferable to compiler-only
adapters, but are separate, measured changes, not prerequisites invented for every
remaining function.

Scope is compiler subsystem execution, including the Jo compatibility reader
implemented in Dewy. Retaining frozen Jo twins for bootstrap is intentional.
Library migration, new language surface, a replacement frontend, parallel
compilation and retiring the seed/twins are not part of this milestone. This
round owns this proposal, one parser leaf, its twin, direct imports and focused
tests; its investigation budget is 3.5 hours.

The planning base is `f7e6ea4e8`, after round 79. Recounting with round 79's
exclusion rules gives **1,029** live Jo functions in 41 nonempty modules, not
1,028: facts now has 140. Frozen twins and `dewy_reader_seed.jo` are excluded.
This count is migration scope, not a capability metric. The baseline throughput
is 145k processed lines/s versus 200–250k. A migration must not consume that gap.

## What the measurements distinguish

Measurements below use the desktop whose reported hostname is `redfox`, Intel
Core i7-6700, x86-64. This is **not** the i5-8350U quiet laptop. Callgrind 3.26.0
counts instructions; no desktop wall-clock performance claim is made. Both
variants are compiled by the same current compiler with the same compiler/library
graph and Jo driver. The table below uses explicit `--release`, matching the
compiler executable; default-build probes were measured separately as controls.
Only the selected functions switch to Dewy. Copies, scripts, binaries and raw profiles
are scratch artifacts under `~/dev/tmp/hotplan`, not repository evidence files.

Each row is the inclusive cost on the driver's call edge, divided by 1,024 calls.
Thus recursive descendants and allocation are included, while setup, the caller
loop and printing are excluded. Results agree between Jo and Dewy. The source
translation preserves control flow, mutation and return values. The initial
translation already uses wrapping parameters/counters where explicitly declared
and raw node arena access; it is not an intentionally naive `int` rewrite.

| Real routine and exercised path | Jo Ir/call | Initial Dewy | Source-adjusted Dewy | Final delta |
|---|---:|---:|---:|---:|
| `fact_set_bound`: nonzero interval endpoint transfer, existing slot | 179 | 179 | 179 | 0 |
| `fact_index_get`: 24 populated keys, 32 rotating hit/miss queries | 53.75 | 96.50 | 49.25 | −4.50 |
| `partner`: uncached five-token nested bracket scan and cache write | 95 | 95 | 95 | 0 |
| `lx_skip_str`: 64-byte quoted token, ordinary-byte scan | 1,173 | 1,173 | 1,173 | 0 |
| `exact_pure_float_tree`: uncached 31-node binary tree | 2,836 | 2,562 | 2,562 | −274 |
| `word_in`: eighth string in an eight-element keyword list | 189 | 189 | 189 | 0 |
| `o_copy_forward`: five IR instructions, three slots, successful copy-chain rewrite | 2,076 | 2,915 | 2,078 | +2 |

`fact_index_hash` is translated with its lookup as a supporting leaf. It inlines
into the driver; its whole-loop comparison has zero delta, rather than a
fabricated standalone call cost. The residual +2 in copy forwarding is +0.096%
of that invocation, not worth a separate micro-optimization. Default-build controls gave 2,986 → 3,646 → 2,986
for that pass and 53.75 → 98.50 → 49.25 for lookup. These are representative
paths, not a claim that every branch of a function has that cost. In particular the scanner's
interpolation/error paths, exact cache hits/growth, and optimizer no-op exits
need coverage in their own eventual cutovers. Whole-compiler gates decide
whether the boundary is affordable.

An eighth real routine, `is_keyword_tok`, needs an explicit mapping from the
literal-union members to the frozen table indices. A faithful exhaustive `match`
compiles and returns identical results, but adds **17.4697 Ir/invocation** over
1,024 rotating token queries. That difference uses process totals with zero-call
setup subtracted: Jo inlines the original, while Dewy retains a call, whose
inclusive edge is 30.8496 Ir. Disassembly shows a jump table followed by a
constant assignment per arm. There is no string comparison. This is an actual
representation/inlining boundary, so it is excluded from the pilot. No numeric
conversion of a literal union or new surface syntax is proposed.

Supplementary construct controls use small identical Jo wrappers, explicitly
`@noinline`, with their inner operations allowed to inline. Their results are
inclusive instructions per wrapper invocation; they are not additional claims
about production call distributions. Pin the dictionary hash seed to
`0x6A09E667F3BCC909` on both sides before inserting 24 keys; unpinned hashing
changes probe lengths even when the lookup machine code is identical.

| Construct control, release mode | Jo | Dewy | Interpretation |
|---|---:|---:|---|
| Return two scalar words and consume both fields | 8 | 8 | Positional-record return simplifies equally. |
| Dictionary `get ?? -1`, 24 keys and 32 rotating hit/miss queries | 76.875 | 76.875 | Same generated lookup and optional-result code with the same hash seed. |
| Sum 32 words through an array of records containing arrays | 382 | 382 | Ordinary indexing preserves the cheap read path. |
| Same sum, repeated `boxes.ptr[which].values.ptr[i]` | 382 | 665 | +283, with one outer-array uniqueness clone (173 Ir) and release (102 Ir) per invocation. |
| Same sum, cache the derived pointer once | 382 | 416 | Saves 249 versus repeated raw access, but still clones; +34 remains. |

A control changing only the exact walk's `nodes.ptr[n]` back to `nodes[n]`
restores **2,836** Ir, exactly the Jo cost. Thus its −274 result is attributable
to that access choice, rather than to a different traversal. Simple scalar-array
raw reads and nested managed-array raw reads have materially different costs.

### Per-construct consequences

| Cost source | Controlled observation | Source rule and general fix |
|---|---|---|
| Exact intermediates and overflow checks | Wrapping `mask`, `slot`, index and loaded decrement changes lookup 96.50 → 58.75 Ir/call (−37.75). Wrapping parameters alone was insufficient: ordinary return values and `.length` reintroduced exact arithmetic. | Keep all hot offset intermediates in `int64<overflow='wrap'>`, including conversions from globals/lengths. General improvement: preserve or prove machine-width ranges through local expressions and casts; never change the exact semantics of ordinary `int`. |
| Bounds and array-header access | On the same wrapping lookup, bounded `.ptr` reads change 58.75 → 49.25 (−9.50). The algorithm guarantees power-of-two slots and `1 + 2*slot` within the allocation. | Keep that invariant at the scan boundary. Prefer a proof that removes checks; otherwise scope `$unsafe` reads to the established arena contract. General improvement: reuse dominating bounds/length facts and lower equivalent proven accesses to the same address sequence. |
| Inferred element representation and destruction | Typing four `fill` workspaces removes 837 of the +839 release instructions (all 660 in the default build). Explicit wrapping element types reach 2,078 Ir/call. Allocation count and algorithm stay unchanged. | Type machine-word workspaces, not just loop variables. General improvement: infer and specialize bounded exact-integer storage/cleanup where all writes prove immediate values. Do not silently turn a public `array<int>` into a wrapping array. |
| Arena field access and repeated `.ptr` chains | Node arena access saves 274; changing only its access spelling restores the Jo cost. In the nested managed-array control, ordinary indexing is 382, repeated raw reads 665, and a cached raw view 416. Callgrind identifies a 173-instruction uniqueness clone plus 102-instruction release. | Use ordinary indexed reads for nested managed arrays unless measured otherwise. Cache a raw view only across operations proved not to grow its owner; reacquire after relevant calls. General improvement: track derived-pointer reads sufficiently to avoid falsely treating the outer array as writable, while preserving COW whenever writes or escape are possible. |
| Literal-union mapping | The eighth probe adds 17.4697 Ir/invocation; a numeric identity map becomes a jump table and stops inlining. | Preserve the member-to-index mapping in ordinary source. General improvement: recognize pure scalar-result matches and lower their arms to a value table or proven affine map; judge inlining after simplification. No public ordinal API is needed. |
| Frames and host calls | Direct-import parser and lexer functions are exactly neutral, as is the facts transfer including its existing call. No new host call is introduced. | Move the group without wrappers; keep the current ABI. The earlier approximately 20-instruction call/frame cost is a boundary budget, not a universal measured surcharge here. Broad frame/inlining work remains below the established payoff bar. |
| Globals | The parser/lexer globals and transfer's state accesses are neutral on these paths. Global arithmetic still needs wrapping conversions. | Keep global storage in place during a function cutover. Move storage later with its writers; do not add accessor calls or copied context records. |
| Strings and reference counts | `word_in` is 189 in both languages. The optimizer's extra cleanup is caused by inferred mathematical-integer elements, not an unavoidable language-boundary retain. | Keep interned identifiers as IDs. Preserve string semantics on actual text; do not replace library byte search with a hand loop. Audit retains and snapshots around managed mutations. |
| Dictionary operations and tuple returns | Supplementary controls are neutral: dictionary lookup 76.875 in both; scalar pair return/consumption 8 in both. Dictionary seeds must match before comparing probes. | Preserve dictionary ownership/COW and positional-record ABI. Add mutation, shared snapshots and managed-return fixtures before moving groups that exercise those paths. No blanket dictionary or tuple rewrite is justified. |

The concrete source idiom is small; its type must cover the workspaces and the
intermediates, not only the public parameters:

```dewy
Word:type=int64<overflow='wrap'>
let slot:Word=fact_index_hash(key mask)
let ndef:array<Word>=fill(Word(0) nv)
```

Use the declared machine contract only where it preserves the Jo algorithm.
Keep semantic arithmetic exact elsewhere. `$unsafe` is a permission boundary,
not a request to remove ordinary array bounds checks; the raw view needs its
own documented length/lifetime invariant.

A trial changing the lookup to take a mutable array borrow fails to type-check
its existing read-only `FactState` callers. Do not “fix” that by copying their
state or making all callers mutable. The measured read-only pointer expression
already works without a clone. This is why changing service signatures is not
a default performance technique.

## General compiler work, ranked by demonstrated opportunity

These are proposed investigations, not changes implemented by this round. Their
order uses measured local opportunity; call-weighted production payoff may
change it. Their numbers bound only the fixtures above. Before implementation, multiply the
avoidable instructions by fresh production call/path counts and compare against
the flagship phase denominator. A new analysis must be demand-driven, indexed,
state its complexity, and include its own compile-time cost in the speed gate.

1. **Bounded integer representation through workspace construction and writes.**
   Largest measured local gap: 839 per successful copy-forwarding invocation;
   explicit element types remove 837 in release and all 660 in the default build.
   Recognize the same bounded writes already tracked for ordinary code, so exact
   integer counters that cannot outgrow a word do not pay generic storage and
   cleanup costs. Start with the existing range/fact information, not a new
   whole-program pass. Explicit word element types make this migration possible
   now; general inference earns a separate slot only with a measured net saving.
2. **Read-only derived-pointer ownership.** The nested `.ptr` control adds 283
   instructions per 32-element read. Its uniqueness clone and release consume
   275 instructions; eliminating those calls is at most a 1.71× improvement on
   that raw-access kernel, not a measured whole-compiler gain. Trace pointer
   reads/writes/escape through the existing effects machinery before uniquifying
   the outer place. Preserve COW for any possible mutation or escape. This
   should work for general arrays of managed records, not special compiler types.
   Until it earns a production bound, ordinary indexed reads already match Jo.
   Caching alone is insufficient and must respect arena-growth boundaries.
3. **Use existing range proofs at arithmetic and indexing lowering.** The lookup
   exposes 37.75 instructions of avoidable intermediate work and another 9.50
   from checked access/header sequences. Test loss of policy/range facts at a
   returned integer, `.length`, and compound expression. Check overflow corner
   cases and invalidated lengths; this must improve safe general programs, not
   disable checks or apply a compiler-file exemption.
4. **Compact pure matches on literal unions.** The keyword-table probe has a
   concrete +17.4697 instruction boundary and inflated IR that prevents inlining.
   Simplify pure scalar-result arms into a value table, or an affine function
   when the exhaustive mapping permits it. Reuse known discriminants internally;
   keep the language's text/union semantics. This is local lowering, not a new
   global analysis. Gate its benefit across other enum/table consumers before
   treating it as a general speed project.
5. **ABI, frames, small-call handling.** Defer unless a new group supplies a fresh
   bound. Current direct calls are neutral. ROADMAP item 2 already rejects broad
   allocator/frame/non-leaf-inlining families at under 1%; this proposal does
   not reopen those experiments under a self-hosting name.

Compiler-only tooling should make these decisions cheap: extend the existing
count/trace scripts to emit executed call/path counts, assemble original/twin
and translated drivers from one fixture, and extract Callgrind call-edge costs
plus normalized disassembly. Flag untyped numeric workspaces, nested raw views,
managed copies before writes, and callbacks inside scans for review. These are
review hints, not proof, and are not another runtime pass. Freeze the input and
compiler revision in scratch so a changed source cannot masquerade as a win.

## Cutover order and group contracts

Move 10–20 related functions per round initially, increasing group size only
when a shared recursive owner makes the larger boundary simpler. Low-cost
helpers travel with their callers; do not build dozens of tiny wrapper leaves.
Jo storage can remain temporarily shared without blocking execution ownership.

| Order | Remaining modules at the planning base | Risk/reward and boundary |
|---|---|---|
| 1 | `parse` 101, `lex` 23, `dewy_fast` 17, `dewy_direct` 8 | Start with the parser cursor pilot, then complete recursive parser/scanner groups. Raw token streams and wrapping byte offsets can match Jo today. Risk: byte strings, token lifetime, reentrant source parsing and arbitrary-byte cuts. No callback per token. |
| 2 | `opt` 36, `loops` 35, `inline` 9, `exact` 75, `exact_loop` 6, `exact_reset_loop` 6 | Whole IR passes and their workspaces, followed by demanded exact walks. Preserve COW snapshots, recursion and budgets. Explicit machine-word workspaces remove the measured optimizer gap. Shared builders stay direct. |
| 3 | `facts` 140, `refine` 53, `nd_contracts` 11 | Indexed transfer/query groups, then state transitions. Highest risk is duplicated frame/dictionary ownership or per-value callbacks. Preserve ordered witness records, caps and branch snapshots. A read-only query must not acquire a mutable API merely for speed. |
| 4 | `expr` 253, `check` 140, `types` 18, `ast` 22 | Largest remaining execution cluster. Move recursive checker groups with their current direct calls and stable IDs; layouts/readers move alongside relevant users. Reentrant field/body resolution must reacquire arena elements. No translated checker context per expression. |
| 5 | Other live modules, 76 functions | Close residual entry points, builders and frontend ownership; many are tiny but heavily called. Trace each boundary and remove now-unnecessary adapters. The Jo reader remains a supported subsystem implemented in Dewy. |

This order is about boundary risk, not a claim that parser work dominates total
compile cost. A general codegen fix that pays on the flagship panel can precede
any group it unblocks. New syntax is not required.

Working estimate: **65–90 execution cutover rounds**, plus **4–8 bounded codegen
rounds** if profiling justifies them and **2–4 completion/bootstrap rounds**:
approximately **71–102 rounds** to milestone 1. The arithmetic-only span for
1,029 functions at 10–20 per round is 52–103 rounds. Recursive groups may reduce
that count; a repeatedly rejected boundary increases it. Re-estimate after the
first three hot groups using accepted functions per round and source-cost drift.
Do not translate this estimate into a claim about dates or quota consumption.

## Gate for every round

1. Pin the base, count actual calls on the flagship panel and timed self-build,
   and measure the proposed boundary before expanding it. Inspect worst-path
   behavior, retained snapshots and arena growth, not only average microcost.
2. Every flagship phase must be **≤ +0.3%**, the self-build source-cost row
   **≤ +1%**, and each flagship's total instructions flat. The phase allowance
   is a measurement/boundary ceiling, not permission for a persistent throughput
   tax. Report unrounded flagship deltas as well as the gate's two-decimal
   display, so a rounded zero cannot conceal accumulating regressions.
   Apply the limits against both the round base and the start of the hot series
   so repeated small increases do not compound unnoticed. The aggregate speed
   tool's looser default is not sufficient.
3. Preserve exact output: focused twin tests and relevant semantic cases,
   quick tests, `speed --base origin/master`, `same_output`, scoped twins and
   golden cases. No source-drift acceptance or changed benchmark input.
4. Build each committed source state independently with
   `build.py --bootstrap --fixed-point`. Stage0 must accept the frozen twins;
   numerical byte literals and seed-compatible control flow remain necessary.
5. Update leaf homes, audit standalone Jo test callers, mirror API changes in
   all affected twins and keep `dewy_reader_seed.jo` imports consistent. Leave
   performance logs in scratch; commit the design and a passing group separately.

The pilot uses two test workers and headless/no-audio settings. It does not run
full-suite shards or `--bootstrap test`. A rejected pilot leaves only this
proposal; it is not a reason to weaken the gate.

## Pilot: parser cursor group

Selected twelve functions: `pk`, `pkn`, `cur_pos`, `advance`, `accept`,
`dotop_prec`, `space_before`, `partner`, `is_soft_kw`, `skip_newlines`,
`word_assign_ahead`, `is_assign_op`. They form the existing token cursor/query
boundary and retain their direct ABI and global stream. An EOF-terminated
stream and its zero spare slots remain owned by the parser. This group adds no
allocation, callbacks, context records, passes, syntax or semantic changes.

A fresh counter-instrumented compiler at the planning base calls all twelve on
at least one flagship. On the frozen planning-base compiler source, `pk` runs
1,775,928 times, `cur_pos` 569,242, `advance` 391,720, `accept` 121,294 and `pkn`
119,052. The group includes the rarely reached `dotop_prec`, which runs twice
on three flagships. The raw pointer bodies need scoped `$unsafe`; arithmetic
on imported ordinary-word globals needs an explicit wrapping conversion at the
operation. Token comparisons use enum IDs. Normalized disassembly of the
out-of-line `space_before`, `partner` and `skip_newlines` bodies matches Jo;
the smallest cursor operations inline in both compilers.

The pilot moves these twelve functions into `parser_cursor.dewy` with a frozen
`parser_cursor.jo` twin. Direct users, the compatibility reader imports and the
reader leaf-home map follow the move. A focused twin driver exercises EOF
saturation, lookahead clamping, accept/reject, quote spacing, cached/fallback and
unclosed bracket partners, all token kinds for assignments/soft keywords, and
dotted operator precedence. The standalone Jo-driver audit found no additional
existing callers requiring an import change. Live Jo functions fall from
**1,029 to 1,017**; parser functions fall from 101 to 89.

The seven individual flagship measurements preserve processed lines and nodes.
Total instruction deltas range from **−0.000651% to +0.002504%**, all displayed
as 0.00% by the existing speed gate. The largest lex/parse-phase increase is
**+0.013071%**, on `100_rtos_kernel`, well below +0.3%. These are small nonzero
changes, not a claim of identical instruction traces. Every other flagship
phase is within 0.0001%. The aggregate lex/parse change displays +0.01%.
The source-cost row improves **0.20%**, within the +1% limit.

A grouped-match-arm spelling of `is_assign_op` did not improve the panel and
was discarded. The retained cutover uses the measured individual-arm spelling.
The numeric keyword-map probe remains in scratch; it needs the compact-match
improvement before joining a later hot group.

Validation on the desktop uses the two-worker wrapper for test/case commands;
`same_output` uses two build workers and speed uses one emission worker (those
commands are not supported by the wrapper).

| Pilot gate | Result |
|---|---|
| Focused cursor/adjacent-leaf/inventory tests | 9 passed. |
| `test --quick` | 120 cases passed, 0 failed (441 case runs, 355 builds); 181 tests passed. |
| `same_output --base origin/master --jobs 2` | 684 builds identical, 798 files; 0 different, 0 built by neither. |
| `test -k twins --base origin/master` | 387 passed; the existing scope selector leaves 20 tests in 12 of 419 twin files in the nightly tier. |
| Golden `cases` | 6,028 passed, 0 failed; 21,791 case runs and 17,672 builds. |
| Independent `build.py --bootstrap --fixed-point --output ~/dev/tmp/hotplan/fp` | Five successful stages; the final two generations are byte-identical. The unchanged compiler source for the proposal-only commit also passes all five stages in `base-fp`. |
| `speed --base origin/master` | Passed against `5d9bbda54`: self-build +0.00%, source cost −0.20%, all seven flagships +0.00%; aggregate lex/parse +0.01%, every other phase +0.00%. The stricter +0.3% phase and +1% source limits pass. |

No full-suite shards or `--bootstrap test` were run. Raw measurements and exact
reproduction commands remain in `~/dev/tmp/hotplan/README.md`. Origin advanced
from the planning base to `5d9bbda54` with ladder tests/tooling and documentation;
compiler, library, bootstrap, stage0 and measured inputs are identical between
those bases, so the planning measurements also apply to that rebase.

**Pilot decision:** retain the twelve-function cutover. It meets the phase/source
budgets, remains flat at the flagship gate precision, and preserves output bytes.
Use the same frozen-input and unrounded-phase checks for subsequent hot groups.
