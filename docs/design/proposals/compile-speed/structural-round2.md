# Structural compile speed, round 2

**Pilot a proof rule for guarded, unit-stride cursor loops on flagship 99.** Seven source
loops account for 69 widening rounds. A scratch compiler replaced those rounds with a
range summary, kept the normal body validation, and raised processed lines/s by **5.82%**.
Flagship 100 has a separate opportunity in fixed-array index proofs. All three witnesses
below preserve every processed line.

| Rank | Design | Target | Upper bound on throughput gain | Measured witness | Estimated build cost |
|---|---|---|---:|---:|---|
| 1 | Summarize a guarded cursor loop | 99 | 6.60% for seven loops, 7.31% for eight | 5.82% for seven, 6.40% for eight | 1–2 engineer-days |
| 2 | Prove fixed-array indexes during the existing checker walk | 100 | About 5.70% for all 158 proved sites | 5.60% for 141 identifier indexes, using recorded answers | 3–5 engineer-days |
| 3 | Reuse the converged loop transfer for final validation | 99 | 7.05% for the eligible validation walks | 6.67% with advance knowledge of convergence | 1–2 engineer-weeks |

## Measurement and attribution

Base `67559b36b3`, after both round 1 landings. Every number below comes from the **x86-64
desktop, Intel Core i7-6700** (local hostname `redfox`). The release fixed-point compiler
built each program from source with default settings and `DEWY_EMIT_WORKERS=1`.
`python3 -m tools.core speed --base HEAD --counter perf` measured 1.6394G retired user
instructions for the seven flagships and 13.4033G for self-build. Rates use the gate's
6.3G instructions/s reference. [Throughput contract](../../compiler_architecture.md)

| Fresh gate build | Root lines | Library lines | Instance lines | Instructions | Processed lines/s | Instruction cut needed for 200k / 250k at these lines |
|---|---:|---:|---:|---:|---:|---:|
| 99, Dewy frontend | 982 | 3,622 | 513 | 257.3M | 125,296 | 37.4% / 49.9% |
| 100, RTOS kernel | 853 | 2,576 | 5 | 148.3M | 145,925 | 27.0% / 41.6% |
| Seven flagships | 6,669 | 30,885 | 3,696 | 1,639.4M | 158,514 | 20.7% / 36.6% |

Each witness used a scratch copy of the compiler, library and ladder. For a matched pair,
toggle the rule in the same compiler executable, point `DEWY_CORE_LIB` at the scratch
library, and wrap `build <flagship>/design.dewy -o <same-path>` in the gate's
`count-instructions` helper. Take the median of three whole-process counts with equal
enabled and running counter times. Separate `build --time` runs supplied line counts and
hardware phase counters. Scratch paths affect the count, so each comparison uses its own
control. For old/new processed lines L and instructions I, a 5% win requires
`I_new / I_old ≤ (L_new / L_old) / 1.05`. Removing library or instance lines tightens
that limit. Each ranked experiment keeps 99 at 5,117 lines or 100 at 3,434.

The seven- and eight-loop summaries, the identifier-only and full fixed-array oracles, the
converged-transfer oracle and the combined eight-loop witness produced byte-identical
executables to the unmodified compiler on their target. Build diagnostics and
`check --obligations` output matched byte for byte. The binaries reproduced the ladder's
expected output, including 100's scripted stdin. These checks cover the witness inputs.
Production eligibility and its cost remain to be measured.

### Where the instructions go

| Hardware phase counts, millions | Load | Check | Facts | Effects | Ownership | Lower | Optimize | Codegen | Other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 99 | 38.89 | 43.72 | 67.11 | 4.29 | 2.15 | 36.10 | 33.22 | 28.51 | 4.02 |
| 100 | 30.87 | 25.10 | 24.49 | 8.74 | 5.24 | 20.51 | 16.53 | 14.91 | 2.39 |

A scratch counter tracked function instance and phase, restoring the parent bucket after
nested work. On 99, 64.63M fact instructions belong to root code. The flagship's `lex`
alone costs 26.45M, followed by `interpolation_end` at 9.12M, `continue_expression` at
8.73M and `string_node` at 5.21M. On 100, root facts cost 19.38M, including 3.38M in
`parse_script`, 2.58M in `step` and 1.70M in `expire`. Library integer conversion adds
2.60M in `_mag_from_chunks` and 0.92M in `_mag_from_digits`. Shared effects work costs
8.42M on 100. The index witness below measures how much of that work an earlier proof
actually avoids.

Generic reuse has a smaller ceiling on these two programs. Grouping instances with type
arguments by declaration and charging every body after the first at its full measured
check-through-codegen cost gives 8.41M on 99 and 0.12M on 100. That is at most 3.39% and
0.08% throughput gain at fixed lines. Map insertion, compaction and rehashing contribute
4.60M of 99's total. The entire lambda-body bucket costs 0.10M and 0.12M respectively
before any eligibility test. A persistent library proof image would reach a much larger
bucket (library load plus check costs 57.11M and 39.45M), but the fresh-source contract
requires each compile to pay for the library it reaches. [Compile-speed decision](../../decisions.md)

On the panel, lex and parse cost **942 instructions per processed node** against a budget of
375, or 7.4k per processed line. The optimizer costs **705 per node** against 125, or 5.5k
per line. Callgrind counted 837 and 620 calls to the Jo lexer entry `p_lex_unit` on 99
and 100, and 389 and 286 top-level optimizer calls. Different spans and different bodies
contribute to those counts. They identify where a future span- or IR-specific witness
must demonstrate equivalent work. All bounds below use retired hardware instructions.

## 1. Summarize guarded, unit-stride cursor loops

In the flagship lexer, lines 70, 192, 204, 222, 237, 242 and 250 have the form
`loop i <? stop and predicate(source[i]) { i += 1 }`. The entry cursor can already be
past the limit, and a failing byte predicate can stop the loop early. A sound header
keeps the entry lower bound and an upper bound of `max(entry_i, stop)`. When entry facts
establish `entry_i <= stop`, the header also keeps `i <= stop`. The strict comparison
makes the admitted increment representable even when `stop` is the maximum signed word.
Line 174 also conditionally sets a newline flag. [Lexer source](../../../../tests/ladder/99_dewy_frontend/lexer.dewy)

To bound the saving, bracket `fact_while` from entry through speculative header
iteration, stability testing and narrowing. The seven leaf sites do not enclose each
other. The compiler visits them 23 times during nested proofs and executes three rounds
on every visit. Those rounds and setup cost 15.902M instructions, a 6.60% throughput ceiling if that work were free. Including line 174 gives 26 visits, 78 rounds and 17.482M. [Loop transfer](../../../../compiler/facts_loops.dewy)

The source-selected witness reads the entry cursor and limit, calls `fact_changes` to
invalidate writes, binds a fresh cursor with the range and relations above, then runs
the existing condition, body and exit join. The seven sites took 242.663M against
256.791M control. Including line 174 took 241.335M. Simply forgetting the changed
cursor loses a bounds proof on this input.

**First pilot.** Give the typed recognizer two engineer-days and start with the seven
single-write bodies. Require a stable local limit, the resolved strict integer comparison
and unit increment, a read-only predicate, and exactly one increment on every continuing
edge. Reject aliases, hidden writes and control flow the recognizer cannot establish.
Cache the structural result by checked loop in its instance. Matching costs O(body size)
once per candidate. Each application still pays for invalidation and the normal validation
walk. The witness leaves **1.90M instructions** on 99 for recognition and other overhead
before the gain drops below 5%.

Accept at **≥5% higher processed lines/s on unchanged 99**, with the same 5,117 lines,
binary, diagnostics and obligation listing, and a passing full-panel and self-build speed
gate. Exercise zero iterations, early predicate failure and the maximum word, plus fallback
for an inclusive guard, a larger step, a mutated limit and a captured write. Run focused
and quick tests, then the full suite, independent bootstrap and fixed point before landing.
End the pilot if the measured gain misses the bar.

## 2. Use dominating guards to prove fixed-array indexes early

On 100, `step` rejects an out-of-range task number at entry. Other functions use
bounded counted loops or reject an index inside the loop. For example, `inherit` ranges
over `[0..NTASK)` and checks a mutex number against `NMUTEX` before using it. The
extent is fixed in the resolved type. Each such subscript that acquires `NF_INBOUNDS`
during checking can avoid creating later proof work. [Kernel](../../../../tests/ladder/100_rtos_kernel/kernel.dewy)
[Scheduler](../../../../tests/ladder/100_rtos_kernel/sched.dewy)

To bound the available work, record root fixed-array index nodes that the ordinary
`directives_after_facts` marks proven and that did not already carry `NF_INBOUNDS`.
Replay each flag using the node ID, kind and source position immediately before the
first effects solve and again before facts. All 158 sites took 139.865M versus 147.822M
control. Installing the flags twice cost about 0.017M in a bracketed run. Giving that
installation for free puts this channel's optimistic ceiling at **5.70%**. Applying
the oracle only to the 141 bare identifier indexes took 139.988M, or **+5.60%**.
Facts fell from 24.50M to 16.88M, and effects from 8.74M to 8.53M.

A narrower replay selected 79 sites whose function's first statement contained the
matching rejecting guard. These reached only **+2.43%**. A 136-site replay that omitted
five loop-carried cursor uses in `expire` still reached **+5.57%**. These sets quantify
the coverage needed. An identifier by itself supplies no range proof.

A production pilot would carry scoped scalar bounds along the checker's existing
structured control edges, including short-circuit operands, rejected branches and
counted loops. Key bounds by local definition, use them only for a resolved fixed extent
and require coverage on every incoming path. Invalidate on assignment, address escape
or a call that can write the local. Fall back to the existing solver on uncertainty.
Index state by relevant declaration and keep work linear in relevant guard events and
index uses. Budget 3–5 engineer-days, starting with a coverage and cost check. The
141-site witness permits only **0.80M** additional instructions at the 5% bar. The
136-site witness permits **0.76M**. Extra whole-program scans can spend that margin.

## 3. Reuse a converged loop transfer for final validation

A settled speculative round has already evaluated the condition, body and exits.
`fact_while` can reuse that result inside outer speculation when narrowing leaves the
header stable. At an ordinary validation site it walks the body again to publish answers.
On 99, 16 settled, non-speculative loop visits with no additional bound demands took
44 widening rounds. Bracketing just the final condition through exit join, with a depth
guard to count nested validations once, gives **16.905M** on 99 and **0.390M** on 100.
The deletion ceilings are 7.05% and 0.26% respectively.

The optimistic oracle records the final stable round number by source site, enables
ordinary proof publication during that round, then reuses its false edge and exits on
convergence. It took 240.712M versus 256.758M on 99 (**+6.67%**). Restricting the
oracle to headers unchanged by narrowing yielded only **+2.95%**. The five sites at
lexer lines 61 and 170 and parser lines 181, 283 and 440 alone yielded **+5.75%**. A production design therefore
has to handle some headers that change under narrowing.

This is the highest-risk pilot. Buffer the trial's diagnostics, proof decisions and
side effects until convergence. Track which facts its answers and outgoing states
depend on. Commit only when narrowing preserves them and publication agrees with
normal validation. Failed proofs, newly unreachable paths, nested proofs, summary
updates and the shared step budget all require an exact fallback. Charge O(trial events)
to record and O(recorded dependencies) to validate, including discarded trials. The
oracle pays neither cost. Allow 1–2 engineer-weeks only after a shadow run demonstrates
sufficient reusable work.

The two loop designs overlap. In one compiler, the eight cursor summaries alone took
241.339M, final-transfer reuse alone took 240.737M, and both together took 230.492M
against 256.796M control. That is **+11.41% combined**, or **+4.71% incremental**
after the eight summaries. After the seven-site pilot, the measured incremental
opportunity was **+4.90%**. Measure the remaining bound on the new base before scheduling this design.
