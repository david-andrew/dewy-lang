# Correctness review: runtime-chosen settings, round 1

Reviewed `brief.md`, `round1.md`, every file in `programs/`, the requested language sections, decisions batches 3–7, D4/D31, and the relevant compiler/runtime. Repository access was read-only. Examples below are semantic counterexamples, not claims that the proposed feature already compiles. No compiler runs or wall-clock benchmarks were needed. Cost numbers are operation-count or size estimates, explicitly conditional on the implementation described.

The basic mechanism is viable: dynamically scoped resource/policy contexts plus demand-driven code specialization can implement the laptop/server idiom. Round 1 is not yet a consistent, complete specification. Six issues must be fixed before implementation; the remaining issues should be settled in the next design round.

## Must-fix

### M1. The attachment rules contradict each other and make ordinary module headers unavailable

**Evidence:** `round1.md:47–52`, `:38`, `:109`. D4 Q6 currently proposes a contiguous initial module header independently of whether the following declaration is a function (`docs/design/open_decisions.md:283`; fuller rule in `docs/design/proposals/concurrency/unified/proposal-v5.md:240`).

Consider this entire file:

```dewy
$explicit_allocation_failure
f = () => [1 2 3]
main = () => f() or_throw
```

The setting must remain a module header under line 38, but line 49 attaches it to `f`, where line 38 says it is an error. Blank lines cannot resolve this. A module containing only functions cannot express this header without inserting an unrelated value/type/import. A mixed initial list containing that module policy and a function cap also has no legal interpretation under “several settings ... share one construct.”

There is a direct contradiction even without module-only tags:

```dewy
$runtime_checks
Thing:type = [value:int]
```

Line 50 makes this a module header; line 52 calls precisely this placement an incompatible-target error. An ordinary reader would expect the leading tag to establish a module default, especially given today's `docs/LANGUAGE.md:5139–5145`. A header before a function instead becoming that function's prefix is deterministic once explicitly taught, but context-sensitive and surprising: adding/removing a preceding value declaration changes its meaning. This needs an explicit rationale under the binding orthogonality/context direction (`docs/design/decisions.md:483–485`).

**Smallest fix:** distinguish module-only tags from construct-affecting tags before attachment. Module-only tags retain module attachment regardless of the next declaration. Give initial dual-target tags exactly one documented precedence rule, remove the contradictory type example, and specify how a mixed header/function-prefix list separates. If all dual-target tags before the first function are deliberately function prefixes, explicitly address how a functions-only file expresses a genuine module default; do not require dummy declarations. This may require reconsidering the universal one-list/one-target claim.

### M2. “Unchanged” signature policies are silently changed by bundle expansion and entry-only header installation

**Evidence:** `round1.md:36–41`, `:54`, `:115`. `$no_hidden_costs` actually includes `$default_row = no allocates & no panics` (`lib/directives.dewy:9–14`; `docs/LANGUAGE.md:5294–5312`). `$explicit_allocation_failure` changes the functions of its declaring module, including library modules (`docs/LANGUAGE.md:4745–4758`), not only functions in the entry file.

Round 1 puts `$no_hidden_costs` in Code but `$default_row` in Module signature, then says a function prefix keeps its “code-class members.” Expanding the existing bundle produces a forbidden member. Dropping that member silently permits allocation that the existing strict lane forbids. Existing bundles support module, function and block scopes (`lib/directives.dewy:1–8`; `docs/LANGUAGE.md:5294–5312`), so making this bundle module-only would also be a real change.

Separately, “Importing a file never installs its header” is too broad. It correctly describes entry configuration such as the library's default zone; it cannot erase a library's declaration-time allocation/signature policy, `$supported_targets`, or `$dewy.version`. An imported allocating function must not lose `OutOfMemory` from its result merely because its file is no longer the entry. Per-module target checking is also explicit at `docs/LANGUAGE.md:5418–5419`.

**Smallest fix:** separate declaration-time module metadata from entry runtime frames. Preserve signature policies on every imported module. Define `$default_row` as a declaration default that can annotate a function where already supported, independently of any dynamic policy propagation. Preserve every member of `$no_hidden_costs`; say explicitly whether applying it to a call additionally demands a variant with a checked `no allocates & no panics` contract. Reclassify the bundle accordingly rather than truncating it.

### M3. Chunk size and affinity are not scalar ceilings, and the proposed minimum changes their meanings

**Evidence:** `round1.md:33`, `:74–75`, `:95`. The retained inventory defines `$parallel.chunk_size = 64` as a **minimum** number of items per chunk and `$placement.cores = [0 1]` as specific core IDs (`docs/design/proposals/concurrency/unified/proposal-v4.md:288–305`). V5 explicitly retains these value types (`proposal-v5.md:245`) and defines `available_cores` from core allowances (`:248`).

With an outer chunk size 64 and inner chunk size 8, the “tightest ceiling” is 8, but that violates the outer minimum if both remain in force. Clamping chunk size 64 to a two-core program cap compares items with cores. For affinity `[0 1]` nested inside `[2 3]`, taking a numerical minimum is undefined; taking the minimum of their cardinalities incorrectly reports two usable cores despite an empty intersection. The wording “caps and ceilings” would also make a chunk size constrain `available_cores`, despite chunk size having a different unit.

**Smallest fix:** give chunk size its own granularity rule (prefer innermost override, or explicitly combine lower bounds), combine affinity by set intersection, and define the empty-affinity outcome. Define `available_cores` as the cardinality of allowed hardware/affinity cores, limited by program and parallel **core** caps. State separately whether schedule mode affects this capacity query. Keep task/item counts out of the numerical core minimum.

### M4. Inherited resource values do not define shared budgets, descendant lifetime, or aggregate core admission

**Evidence:** `round1.md:58–75`, `:89`, `:100`, `:126`. The design says tasks retain resource “values,” each fresh call starts at zero, task allocations charge the captured budget and an outer entry-file ceiling, and overlapping extents can use the sum of their core caps. It does not define the shared budget identities necessary to reconcile these rules.

Concrete cases that need answers:

1. An entry with 128MiB calls an ordinary function capped at 48MiB. That function starts two tasks, returns, and each task allocates 32MiB. Both fit their own copied limit and the entry limit, but together violate the intermediate 48MiB extent. The wording explicitly mentions the entry ceiling; it must preserve **all** enclosing budgets, including one whose call returned.
2. A task started under that extent later spawns a grandchild after the original function has returned. The grandchild must inherit the same budget identity, not create another 48MiB allowance. The same issue applies to `max_tasks` and to repeated `app.spawn` through a longer-lived background owner.
3. An outer 64MiB function retains the results of three inner 32MiB calls, each allocating 24MiB. Fresh inner counters alone permit 72MiB. All those allocations must continue charging the outer budget. If a returned allocation is freed or resized later under another frame/task, which original counters change? Is usage live bytes, cumulative bytes, requested payload, rounded heap storage, or reserved arena pages? Round 1 does not choose.
4. A two-core `main` starts two differently capped child extents (1 and 2), both still running. Line 100 permits a sum of three, while the outer cap must restrict the complete descendant extent to two. Without an outer cap the sum can be intentional; with one it cannot. This is also an issue for two tasks carrying the *same* inherited cap, which the proposed different-cap warning misses.

**Smallest fix:** capture references to a persistent chain of shared budget objects, not copied counters or limits. Every task and descendant retains all ancestors. Charge allocations/admissions to every relevant ancestor, and define atomic reservation/rollback on rejection. State how allocation ownership survives return and how free/reallocation releases the original charges; define the measured byte quantity and the treatment of COW sharing and arena backing storage. Apply the same ancestor aggregation rule to runnable core permits and task admission. Qualify line 100: sums are allowed only within every common ancestor's remaining allowance. Preserve budget objects as long as tasks or charged allocations reference them.

This is specification work, not a claim that dynamic resource caps are impossible.

### M5. The one-body Policy class lacks a stable result-type rule

**Evidence:** `round1.md:35`, `:77`, `:115`; `docs/LANGUAGE.md:1674–1678`, `:1690–1695`. Today a successfully validated literal is a plain value, while parsing runtime-dependent local time can return failures; supplying gap/fold policies can also remove corresponding failure alternatives. D31's current proposal explicitly preserves the “no tag changes a result type” rule and asks strict tags to point to explicit functions (`docs/design/open_decisions.md:758–759`).

Round 1 says a `zoned` literal under a literal zone is checked at compile time, but the same literal under a runtime zone is parsed on entry and has the failure behavior of runtime `zoned(text)`. Consider a separately declared helper returning `zoned"2026-03-08T02:30"`, called once under literal UTC and once under a runtime user zone that may be New York. The latter can hit a gap; the former cannot. The function is promised one body because zone is Policy. Does its result always include failures, does its signature vary with the caller, or does the runtime case trap? None of these is specified. `const` use makes this distinction unavoidable. Runtime gap/fold selection similarly cannot silently alternate a function's result representation.

`programs/13_fold_call.dewy:5` uses a call rather than a `const` and prints the result directly, so it does not test this type boundary.

**Smallest fix:** give functions reached under runtime policy one stable result type/ABI, ordinarily the conservative failure union, with explicit handling. Require a compile-time policy for a `const` literal and diagnose a runtime-dependent constant. Alternatively classify the type-affecting specialization separately and define per-specialization signatures; that abandons the universal one-body claim. Whichever is chosen, identify the changed literal/type behavior in the earlier-decisions section and add a helper called under both kinds of zone.

### M6. The frame cost and “nothing else pays” claims omit mandatory allocator and scheduler work

**Evidence:** `round1.md:89`, `:93–103`; implementation in `lib/core/rt.jo:281–298`, `:322–365`, `lib/std/fork_join.jo:193–199`, `:267–275`, `:330–344`, and `lib/std/tasks.jo:99–109`, `:116–132`.

Today's ordinary small-allocation fast path uses a size class and thread-local free-list state. It has no budget-chain traversal or budget owner for a later free. Under the proposed rule an allocation at budget depth D takes O(D) ancestor visits, not O(1). Reclaiming live-byte charges generally takes a corresponding traversal of the allocation's original chain. With 100,000 allocations and D=32, this is 3.2 million allocation-side ancestor visits, plus another 3.2 million on frees. Shared descendant budgets require synchronization or a specified alternative reservation scheme. A straightforward shared-counter implementation can require one atomic reservation and one release per ancestor per allocation/free pair; retry/rollback adds work. These are operation counts, not measured instruction or elapsed-time claims.

Persisting frames for escaping tasks requires lifetime storage and retain/release, not just a task-pointer write. A straightforward per-allocation owner pointer costs eight bytes on a 64-bit host before alignment/other metadata (about 0.76MiB for 100,000 live blocks); a side table moves rather than removes the bookkeeping. This is an implementation estimate, not a universal representation lower bound.

The existing pool reads its cap once at startup (`fork_join.jo:267–275`). The compiler currently folds that read to a literal (`compiler/expr.jo:5499–5516`). A sequential 1-core then 4-core run therefore needs a different pool strategy: precreate capacity, or grow by as many as three workers, and enforce per-extent permits thereafter. Stolen jobs and join-helping must install/restore the **job's** context rather than use the helper's current context; `__fj_execute` currently just calls its entry. Task launch likewise needs captured settings in addition to its existing group and callback. Strict CPU admission across the waiting lane requires scheduling accounting too, including release/reacquisition around blocking. These are costs of the new design, not reasons to retain compile-time-only caps.

**Smallest fix:** replace “one write” with a scoped fast-path claim, describe persistent-context ownership and job/task context switching, and state O(D) allocation/free/admission cost for the simple implementation. Make the unused-settings path compile away. Warn where dynamic budgets, non-folded policy reads, or core-accounting instrumentation add work even when each function is reached under only one setting value; the current multi-value/duplicate-body warnings do not cover those costs. The specification need not predict a percentage slowdown before a pilot exists.

## Should-fix

### S1. Define the specialization state and qualify the graph complexity and binary-size bound

`round1.md:79–91` describes a reasonable fixed point, but “function” must mean a concrete generic/closure/effect instantiation, not a source declaration. The current compiler already indexes concrete generics by declaration plus type arguments (`compiler/checker_instances.dewy:14–16`, `:31–48`, `:63–101`); nongeneric bodies currently reuse their source node (`:92–95`). Differing settings variants must not destructively share mutable checked bodies.

A generic helper called with two types under two settings can require four states. Mutual recursion that sets checks on in A and off in B must revisit the appropriate settings states, while ordinary recursion under an unchanged vector must reuse its pending state rather than recursively generate bodies forever. Settings/effect inference must converge together, since checked bodies can carry `panics` (`docs/LANGUAGE.md:699–705`).

The stated O(V·(F+E)) is a possible **graph-discovery** bound if F/E describe a finite instantiated graph, V is a bound on settings states per instance, and each edge has a constant-cost deterministic settings transfer. It is not the total checking/proof/optimization cost, and runtime prefixes introduce set-valued transfers. State the general work in terms of actual product states S and transfer edges T: O(S+T) for indexed traversal with constant-cost edge handling, plus type substitution, proof and body compilation costs. Explain any caching/factoring used to avoid enumerating redundant fan-outs. No measured speed claim follows merely from indexing.

Even Boolean code settings can produce V=2^k reachable combinations. Ten independent runtime flags permit 1,024 vectors; twenty permit 1,048,576. Conditional on a shared reachable body set retaining 100KiB of differing code per vector, those are 100MiB and 100GiB respectively, excluding the rest of the program. Deduplicating identical machine code after compilation does not recover the compilation work. These are upper-envelope examples, not forecasts for the supplied two-vector programs.

**Fix:** key states by concrete instance plus normalized expanded code settings, insert pending SCC states before checking bodies, publish the discovery/compilation distinction, and warn with the number of retained variants and an estimated aggregate size/compile-work expansion. A threshold warning can preserve the owner's “make it work” direction without an arbitrary language rejection.

### S2. Give a concrete contract for function values and handler tables

The design **does** explicitly specify that a handle captures no frame and that an unresolved needed variant is a compile error (`round1.md:64`, `:91`). Thus “an arbitrary opaque indirect call may be rejected” is already an answer, not an omitted runtime fallback. It does not yet specify what counts as a resolvable function value or how legal variants are invoked through one handle.

Test a table containing `@f` and `@g`, selected by runtime index and called under plain and fast-math settings; also pass `@f` through a generic wrapper. If the table's possible targets are known and both variants legal, say explicitly whether it compiles. If so, use a logical-function handle plus variant entries/thunks or an equivalent proven target transformation, and account for the dispatch. If not, show the exact diagnostic and a practical way to write this normal handler-table program. A handle to a prefixed function must retain the declaration's prefix even though it captures no *ambient* frame.

**Fix:** add this case and state the finite-target analysis/ABI contract. Keep the explicit rejection for genuinely unknown target sets. Do not advertise all direct calls as dispatch-free if an intervening call to a settings-polymorphic function value still needs selection.

### S3. Specify prefix/argument/default evaluation order and failure ownership

`round1.md:58` places arguments of a prefixed call inside its frame, but function prefixes are installed “when that function is called” (`:56`). These are different syntactic sites. Define whether `f(expensive_copy())` evaluates the copy under a prefix declared on `f`; the present statement clearly covers a prefix at the call site, but does not resolve the declaration-prefix case. Also specify order among prefix expressions, argument evaluation, defaults, parameter validation and allocation-failure entry frames. Caller settings currently supply setting-valued parameter defaults (`docs/LANGUAGE.md:5179–5182`).

A copy exceeding a callee memory cap before the callee starts needs a defined `OutOfMemory` recipient when caller and callee modules use different allocation policies (`round1.md:72–73`; `docs/LANGUAGE.md:4745–4758`).

**Fix:** give one ordered call-entry procedure and name which module's signature/failure boundary owns each stage. Prefer ordinary caller evaluation for arguments unless deliberately changing that rule; call-site prefixes can still surround the entire call expression.

### S4. Complete dynamic-cap validation and its proof rule

`round1.md:71` discusses a runtime **outer** cap, but the primary example has a runtime **inner** cap. Under literal outer cap 4, a validated positive `cores` can still be 8. The guard `cores >= 1` proves positivity, not `cores <= outer`, so the claim that this makes the push free is only valid when there is no further outer-bound obligation. `programs/10_config_cores.dewy:1–10` also relies on caller facts reaching an unrefined helper parameter, which needs an explicit proof-summary/specialization rule rather than an assertion.

**Fix:** state obligations `value >= 1` and `value <= every enclosing same-resource cap` for all literal/runtime combinations, plus quantity/representability constraints where applicable. Show a checked rejection and a statically proved call under an outer cap. Use a refined parameter or document the interprocedural proof mechanism. Do not imply a positivity guard eliminates context storage/admission costs.

### S5. Preserve cooperative replay, and distinguish static warnings from runtime observations

`round1.md:43` describes `$parallel.off` as running one item at a time. The current proposal requires source-priority **cooperative** replay: a waiting item yields so a sibling can resolve its wait (`proposal-v5.md:246`). A producer waiting for its consumer must remain runnable under this mode. The supplied replay program contains no waits and cannot distinguish this from deadlocking strict serial execution.

The warning at `round1.md:100` depends on whether an earlier task is still running. Unless conservative static “may overlap” warnings are intended, issuing it needs a runtime observation, bookkeeping and a rule for warn-once state.

**Fix:** explicitly retain cooperative source-priority semantics, add a waiting producer/consumer example, and identify overlap warnings as either conservative compile warnings or runtime diagnostics with their costs.

## Nits

- `round1.md:28` promises exactly one class, but `$dewy.version` is listed in both Build and Declaration/marker (`:37`, `:39`). Its per-module fixed nature is otherwise clear. List it once.
- The inventory omits `$prototype_warnings`, which is an existing source setting (`docs/LANGUAGE.md:5163–5165`; `compiler/directive_queries.dewy:13`). Add a compile-diagnostic classification or explicitly limit the inventory's scope. Also distinguish retained current names from superseded proposals such as `$time.require_range` versus `$time.no_assumed_range` (the latter is the current proposal in `docs/design/proposals/time/units-and-format-round1.md:380`). This avoids accidentally treating historical aliases as simultaneously supported settings.

## Binding decisions and intentionally declared departures

- The requested runtime laptop/server idiom follows batch 5 (`docs/design/decisions.md:544–548`) and batch 7's runtime-settings direction (`:595–600`, `:636–638`). The review does not recommend reverting to separate entries for runtime resource policies.
- Broadening permitted program-setting sites changes batch 4's entry-only configuration (`decisions.md:519–524`). Round 1 **does disclose** this at `round1.md:107`.
- Allowing a differently configured imported `main` changes the binding transitive conflict error (`decisions.md:533–538`). Round 1 **does disclose** withdrawal at `round1.md:108`; for example, a 2-core `lib.main` inside an 8-core entry becomes legal where the existing rule rejects different settings. Runtime selection of ordinary environment functions does not by itself require withdrawing this special `main` rule. Either retain it or identify the independent owner decision being requested. “Withdrawn” in a proposal is not already an approved change to the ledger.
- The function-before-header precedence changes open D4 Q6; dynamic zone prefixes change open D31 Q2. These departures are disclosed at `round1.md:109–111`. Those items are proposals, not approvals to silently amend the binding rules. The broader dynamic propagation of lexical settings also supersedes v5's callee-isolation rule (`proposal-v5.md:236–237`), beyond attachment alone; say that explicitly.
- The scope-to-prefix change from today's guide is explicitly disclosed at `round1.md:113`. The undisclosed signature/bundle changes in M2 remain separate defects; acknowledging entrypoint changes does not cover them.

## Requested concrete-case results

| Case | Result of review |
|---|---|
| Two direct calls under different runtime policies | Intended restoration is specified; one body with dynamic reads is feasible. M3/M6 qualify meaning and cost. |
| Function value created in one code context, called in another | No frame capture and unresolved-variant compile error are explicit. Legal finite handler-table dispatch and prefix precedence need S2. |
| Generic helper under two vectors | Needs concrete type/effect/closure instantiation in the key; S1. |
| Recursion through two vectors | Finite indexed fixed point is feasible; pending states/SCC handling and per-vector effect checks need S1. |
| Task outlives call and spawns more tasks | Lifetime intent is explicit; shared ancestor resource identity is missing, M4. |
| Nested memory accounting across tasks and escaped results | No complete accounting/release model, M4; implementation cost M6. |
| `available_cores` inside one parallel helper called under caps 2 and 8 | With at least eight eligible hardware cores and no additional restriction, required answers are 2 then 8. Under an additional parallel core cap 1, both are 1. It is an allowance, not instantaneous idle workers. Current compiler/pool constants cannot implement this without the changes in M6; chunk size/affinity must follow M3. |
| Runtime code setting whose variants differ in legality | **Already settled:** `round1.md:81` requires every reachable variant to be legal. A runtime `$runtime_checks = flag` around an unproved index is rejected if false is possible; true-only does not require the false body. This is consistent with no-traps-by-default (`docs/LANGUAGE.md:5154–5166`). Do not replace rejection with unchecked execution. |

## Dogfood coverage

All supplied programs were read. They cover the nominal direct-call idiom, but do not exercise the counterexamples above: there is no handler table, generic settings wrapper, settings-changing recursion, grandchild after parent-frame exit, overlapping nested allocation budget, escaped allocated result, or runtime code flag with an illegal alternative. `programs/07_task_outlives.dewy` reports a task's core allowance but does not allocate against a retained budget or spawn a grandchild. Its task may send before `search` returns; the program does not synchronize the send after return, despite the stronger narrative in `dogfood.md:89`. `programs/04_request_memory.dewy` uses a tiny string, and its `cache` binding alone does not establish a large pre-existing allocation.

Add small design-only cases for those boundaries and regrade the affected programs. A floor of 5 (`dogfood.md:177–179`) is not supported until the unresolved behaviors and type/cost consequences are addressed. No fresh-reader or compiler-validation claim is inferred from these handwritten examples.
