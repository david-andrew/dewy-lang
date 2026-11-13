# Round 4 dogfood and regrade

**Author regrade, not a second independent review. Floor: 3.** Program 08 still needs substantial knowledge of cancellation selectors; program 13 must teach that the value operator does not return a type intersection; program 01 still lacks lossless cleanup construction under explicit allocation exhaustion. Program 10 also gets K3 against its original domain-cause workload: that optional feature is deferred, not solved by transparent context. These are deductions, not footnotes beneath an all-5 verdict.

There are thirteen enclosing paper programs in `programs-r4/`. None was compiled or executed. Only `semantics_model_r4.py` was run. The scores assume the specified API is implemented correctly, as the independent round-3 rubric did; they do not certify a compiler, allocator, scheduler, or ownership representation. O/D/C/S/K = obvious/discoverable/concise/safe by default/complete. 5 = direct and adequately covered for the stated workload; 4 = a local cost or limitation; 3 = substantial protocol knowledge or an unresolved material subcase; 2 = a conspicuous main-path weakness; 1 = failure of the scenario.

The r22 cold reads support broad vocabulary, not full semantics. They did not distinguish the two group families. R4 removes one family, but does not infer D5 from that change. Neither `errors.recover` nor the new value-operator usage was cold-read. The reviewers also did not consistently infer construction-time origin or the direction of cause attachment from names alone. [round4.md:227](round4.md)

## Comparison with the independent baseline

Peer scores below are adopted **unchanged** from the independent regrade, not the more generous earlier author matrix. Each peer row links to its original line-cited rationale, including every sub-5 component. No new claim about current peer libraries or toolchains is made; the original source and execution limits continue to apply. [regrade-round3.md:151](regrade-round3.md)

Rows 06 and 10 are deliberately not equivalent scope: the v1 CLI has no stack trace, and program 10 has no domain cause. Their completeness scores account for this cut against the old workloads. Peer baselines still describe the original workloads. Row 13 is a Dewy-specific operator conformance example, not a meaningful new cross-language ranking.

| Program | R3 independent Dewy | R4 Dewy | Python | Go | Rust | TypeScript | Swift | Peer evidence |
|---|---|---|---|---|---|---|---|---|
| 01 Cleanup pair | 4/4/5/4/3 | 4/4/5/4/3 | 4/4/3/4/4 | 5/4/5/4/4 | 4/4/3/4/4 | 4/4/5/4/4 | 4/4/3/4/4 | [regrade-round3.md:33](regrade-round3.md) |
| 02 Form validation | 5/4/4/4/5 | 5/4/4/5/5 | 5/4/4/4/4 | 5/4/5/4/4 | 5/4/4/5/4 | 5/4/5/4/4 | 5/4/4/4/4 | [regrade-round3.md:42](regrade-round3.md) |
| 03 Batch files | 4/4/4/5/5 | 4/4/4/5/5 | 4/4/4/4/5 | 4/4/4/4/5 | 4/4/3/4/5 | 4/4/4/4/5 | 4/4/4/4/5 | [regrade-round3.md:51](regrade-round3.md) |
| 04 Parallel CPU items | 5/4/5/5/5 | 5/4/5/5/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/5/5 | 5/5/5/4/5 | 4/4/3/5/5 | [regrade-round3.md:60](regrade-round3.md) |
| 05 Library context | 5/4/5/5/5 | 5/4/5/5/5 | 5/4/5/3/4 | 4/4/5/4/4 | 4/4/3/5/4 | 4/4/5/4/4 | 4/4/4/4/4 | [regrade-round3.md:69](regrade-round3.md) |
| 06 CLI diagnostics (v1 cut) | 5/4/5/5/4 | 5/4/5/5/4 | 5/5/5/4/4 | 4/3/2/4/3 | 4/3/2/4/3 | 4/3/2/4/3 | 4/3/2/4/3 | [regrade-round3.md:78](regrade-round3.md) |
| 07 Retry history | 4/4/4/5/4 | 4/4/4/5/4 | 4/4/4/4/4 | 4/4/4/4/4 | 4/4/3/4/4 | 4/4/4/4/4 | 4/4/4/4/4 | [regrade-round3.md:87](regrade-round3.md) |
| 08 Cancellation boundary | 3/2/4/5/4 | 3/3/4/5/5 | 4/4/4/4/4 | 4/4/4/3/4 | 4/3/3/4/4 | 4/3/3/3/4 | 4/3/3/3/4 | [regrade-round3.md:96](regrade-round3.md) |
| 09 Selective recovery | 3/3/2/3/3 | 4/4/5/5/4 | 5/4/5/5/4 | 3/3/2/3/3 | 4/3/2/4/3 | 3/3/2/3/3 | 4/3/2/3/3 | [regrade-round3.md:105](regrade-round3.md) |
| 10 Domain cause (deferred; context shown) | 5/4/5/5/5 | 5/4/5/5/3 | 5/5/5/5/5 | 4/4/4/4/4 | 5/4/4/5/5 | 5/5/5/4/5 | 4/4/4/4/4 | [regrade-round3.md:114](regrade-round3.md) |
| 11 Occurrence origins | 4/4/5/5/5 | 4/4/5/5/5 | 4/4/3/4/3 | 4/3/3/4/4 | 4/4/4/5/4 | 4/3/4/4/3 | 4/4/4/5/4 | [regrade-round3.md:123](regrade-round3.md) |
| 12 Bounded validation | 5/4/5/4/4 | 5/4/5/4/4 | 5/4/4/4/4 | 5/4/4/4/4 | 5/4/4/5/4 | 5/4/4/4/4 | 5/4/4/4/4 | [regrade-round3.md:132](regrade-round3.md) |
| 13 Operator contract | — | 4/3/5/4/4 | — | — | — | — | — | Dewy-specific |

## Evidence for every R4 grade

### 01 — Cleanup pair: 4/4/5/4/3

- **O4:** returning WriteFailed acquires completion failures at the closing brace; the written return is not the whole result. [01_cleanup_pair.dewy:18](programs-r4/01_cleanup_pair.dewy)
- **D4:** the fallible assigned destructor and its join protocol need discovery. Removing ExceptionGroup does not remove that owner contract. [01_cleanup_pair.dewy:9](programs-r4/01_cleanup_pair.dewy)
- **C5:** flush and close are each performed once, both failures are retained, and a direct pair is a single operator expression. [01_cleanup_pair.dewy:11](programs-r4/01_cleanup_pair.dewy) [01_cleanup_pair.dewy:25](programs-r4/01_cleanup_pair.dewy)
- **S4:** preserving both failures cannot undo the partial write; safe reporting does not imply transactional output. [01_cleanup_pair.dewy:33](programs-r4/01_cleanup_pair.dewy)
- **K3:** there is still no concrete lossless allocation-refusal contract for arbitrary owning failures, including foreign acquisition and transfer. The code expressly retains this gate. [01_cleanup_pair.dewy:34](programs-r4/01_cleanup_pair.dewy) [round4.md:231](round4.md)

The body-first code 41 and Canceled-plus-close code 43 are now distinguished; neither is presented as an already accepted cleanup precedence rule. [01_cleanup_pair.dewy:30](programs-r4/01_cleanup_pair.dewy)

### 02 — Form validation: 5/4/4/5/5

- **O5:** the checks append typed field issues in UI order; invalid age text has an explicit user-facing message. [02_form_validation.dewy:7](programs-r4/02_form_validation.dewy) [02_form_validation.dewy:11](programs-r4/02_form_validation.dewy)
- **D4:** callers must learn that the folded group is exception but not error, and use leaf inspection for typed fields. [02_form_validation.dewy:20](programs-r4/02_form_validation.dewy) [02_form_validation.dewy:28](programs-r4/02_form_validation.dewy)
- **C4:** the array, staged age, and final propagation add ceremony to a small validator. [02_form_validation.dewy:6](programs-r4/02_form_validation.dewy) [02_form_validation.dewy:17](programs-r4/02_form_validation.dewy)
- **S5:** the final join prevents invalid User construction, and the display helper now reports unexpected leaves instead of dropping them. This is the concrete change from S4. [02_form_validation.dewy:17](programs-r4/02_form_validation.dewy) [02_form_validation.dewy:23](programs-r4/02_form_validation.dewy)
- **K5:** the scenario covers empty name, malformed text and age bounds, with either a valid User or all typed issues. A parse cause is deliberately translated, not retained; this grade covers validation/UI behavior, not domain-cause history. [02_form_validation.dewy:7](programs-r4/02_form_validation.dewy) [02_form_validation.dewy:14](programs-r4/02_form_validation.dewy) [02_form_validation.dewy:18](programs-r4/02_form_validation.dewy) [02_form_validation.dewy:35](programs-r4/02_form_validation.dewy)

### 03 — Batch files: 4/4/4/5/5

- **O4:** accumulation still needs a separate decision to stop when a retained result carries cancellation. [03_batch_files.dewy:8](programs-r4/03_batch_files.dewy)
- **D4:** learn type-preserving context and the ordered leaf walk, including groups returned by a single read. [03_batch_files.dewy:9](programs-r4/03_batch_files.dewy)
- **C4:** explicit storage and the cancellation loop surround an otherwise simple read loop. [03_batch_files.dewy:4](programs-r4/03_batch_files.dewy) [03_batch_files.dewy:10](programs-r4/03_batch_files.dewy)
- **S5:** a carrying read is appended whole, then returned before another read; successful byte counting is outside the failure branch. No prefix is repeatedly rejoined while checking the current read. [03_batch_files.dewy:9](programs-r4/03_batch_files.dewy) [03_batch_files.dewy:14](programs-r4/03_batch_files.dewy) [03_batch_files.dewy:25](programs-r4/03_batch_files.dewy)
- **K5:** earlier failures, nested cleanup groups, operation context and input order survive the return; later task cancellation is the next read operation's cancellation-point responsibility. [03_batch_files.dewy:24](programs-r4/03_batch_files.dewy) [03_batch_files.dewy:27](programs-r4/03_batch_files.dewy)

### 04 — Parallel CPU items: 5/4/5/5/5

- **D4:** connecting partition_failures to a zero/one/many join remains a library idiom to discover. [04_parallel_items.dewy:13](programs-r4/04_parallel_items.dewy)
- **O5/C5:** the per-row checker is direct; the parallel result partition and fold need three expressions. [04_parallel_items.dewy:5](programs-r4/04_parallel_items.dewy) [04_parallel_items.dewy:12](programs-r4/04_parallel_items.dewy)
- **S5/K5:** this deliberately nonwaiting CPU workload retains item outcomes as values, preserves input order, and returns quantities only when the fold succeeds. It makes no claim about canceled waiting collect-all. [04_parallel_items.dewy:12](programs-r4/04_parallel_items.dewy) [04_parallel_items.dewy:22](programs-r4/04_parallel_items.dewy) [04_parallel_items.dewy:24](programs-r4/04_parallel_items.dewy)

### 05 — Library context: 5/4/5/5/5

- **D4:** transparent persistent context must be distinguished from making a new nominal wrapper; many existing languages do the latter. [05_library_context.dewy:6](programs-r4/05_library_context.dewy) [05_library_context.dewy:18](programs-r4/05_library_context.dewy)
- **O5/C5:** each boundary explains the operation in a single returned expression. [05_library_context.dewy:6](programs-r4/05_library_context.dewy) [05_library_context.dewy:9](programs-r4/05_library_context.dewy)
- **S5/K5:** file identity, cancellation and the original source site survive, with a separate context site; no broad error-to-domain conversion is hiding cancellation. [05_library_context.dewy:18](programs-r4/05_library_context.dewy) [05_library_context.dewy:20](programs-r4/05_library_context.dewy) [round4.md:211](round4.md)

### 06 — CLI diagnostics: 5/4/5/5/4

- **D4:** requested location display and construction-origin availability remain separate concepts. [06_cli_diagnostics.dewy:7](programs-r4/06_cli_diagnostics.dewy) [06_cli_diagnostics.dewy:13](programs-r4/06_cli_diagnostics.dewy)
- **K4:** the old trace portion of this workload is deferred. Full v1 context/group reporting is not a full stack or domain-cause chain; simplifying the example does not earn a completeness increase. [06_cli_diagnostics.dewy:14](programs-r4/06_cli_diagnostics.dewy) [round4.md:223](round4.md)
- **O5/C5:** one report call followed by the explicit CLI exit policy covers the whole returned diagnostic tree. [06_cli_diagnostics.dewy:6](programs-r4/06_cli_diagnostics.dewy)
- **S5:** terminal controls are escaped, no arbitrary payload dump occurs, and the CLI deliberately ends rather than falling back to a successful result after cancellation. Caller-written messages can still contain sensitive text; the program's location display is intentional. [06_cli_diagnostics.dewy:8](programs-r4/06_cli_diagnostics.dewy) [06_cli_diagnostics.dewy:13](programs-r4/06_cli_diagnostics.dewy) [round4.md:221](round4.md)

### 07 — Retry history: 4/4/4/5/4

- **O4/D4/C4:** checkpointing, history, cancellation-bearing groups and backoff exits are still a manual retry protocol, even though they use the same general composition primitives. [07_retry_history.dewy:10](programs-r4/07_retry_history.dewy) [07_retry_history.dewy:19](programs-r4/07_retry_history.dewy) [07_retry_history.dewy:27](programs-r4/07_retry_history.dewy)
- **S5:** both a canceled operation and canceled wait retain the observed history and stop before a further attempt. This is cooperative cancellation, not rollback of an admitted operation. [07_retry_history.dewy:21](programs-r4/07_retry_history.dewy) [07_retry_history.dewy:28](programs-r4/07_retry_history.dewy)
- **K4:** unlike R3, grouped operation results and cancellation during a fixed backoff are covered. The explicit entry checkpoint still depends on D41 integration, and the supplied helper fixes its wait to 10ms rather than exposing a retry policy. This is an improvement within a still limited retry helper, not K5. [07_retry_history.dewy:6](programs-r4/07_retry_history.dewy) [07_retry_history.dewy:27](programs-r4/07_retry_history.dewy) [07_retry_history.dewy:42](programs-r4/07_retry_history.dewy)

### 08 — Cancellation boundary: 3/3/4/5/5

- **O3/D3:** nominal `is? Canceled` is false while the selected propagation operator forwards that same group. Explicit defaulting also names both the carried cancellation and the outer group. This remains substantial protocol knowledge. D rises from 2 only because the second group family and separate-push packaging are gone; this is an author judgment, not observed usability evidence. [08_cancellation_boundary.dewy:17](programs-r4/08_cancellation_boundary.dewy) [08_cancellation_boundary.dewy:33](programs-r4/08_cancellation_boundary.dewy) [round4.md:175](round4.md)
- **C4:** a safe explicit fallback still requires a forwarding statement before the typed default; the direct pair itself is shorter. [08_cancellation_boundary.dewy:13](programs-r4/08_cancellation_boundary.dewy) [08_cancellation_boundary.dewy:5](programs-r4/08_cancellation_boundary.dewy)
- **S5:** bare fallback forwards the whole canceled pair; the checked path retains the same group; swallowing both cancellation and close failure requires the named acknowledgment. [08_cancellation_boundary.dewy:8](programs-r4/08_cancellation_boundary.dewy) [08_cancellation_boundary.dewy:13](programs-r4/08_cancellation_boundary.dewy) [08_cancellation_boundary.dewy:17](programs-r4/08_cancellation_boundary.dewy)
- **K5:** ordinary-group continuation, carrying-group propagation, and explicit acknowledgment now occur in the program's live main path. The former K4 case is no longer only a comment. The algebra checks both ordinary and carrying defaults; the compiler flow-refinement implementation is still unverified. [08_cancellation_boundary.dewy:23](programs-r4/08_cancellation_boundary.dewy) [08_cancellation_boundary.dewy:26](programs-r4/08_cancellation_boundary.dewy) [semantics_model_r4.py:244](semantics_model_r4.py)

### 09 — Selective recovery: 4/4/5/5/4

- **O4:** the compact call has a nontrivial contract: failed repair retains the original, ordinary repair failures do not stop unrelated work, and cancellation stops later starts. Hiding this in a helper makes correct use easier but does not make the policy self-evident. [09_selective_recovery.dewy:9](programs-r4/09_selective_recovery.dewy) [round4.md:201](round4.md)
- **D4:** `recover<E>` is a new, untested name; copyable payload and callback-admission rules also need documentation. It is explicitly not described as cold-read. [09_selective_recovery.dewy:34](programs-r4/09_selective_recovery.dewy) [round4.md:196](round4.md)
- **C5:** the reusable ordinary-library operation owns all unmatched and unattempted values. Application code is one call plus the actual regeneration callback, replacing the old nested loops, stop flag and rest accumulator. A typed callback is not invented control-flow syntax. [09_selective_recovery.dewy:5](programs-r4/09_selective_recovery.dewy) [09_selective_recovery.dewy:8](programs-r4/09_selective_recovery.dewy)
- **S5:** incoming transported cancellation returns the exact original before callbacks, including through erased storage; new cancellation blocks the next callback admission. Unmatched values, original failed repairs and unattempted matches remain. This grade concerns the specified helper and modeled ordering, not a claim that an atomic runtime gate has shipped. [09_selective_recovery.dewy:21](programs-r4/09_selective_recovery.dewy) [round4.md:200](round4.md) [semantics_model_r4.py:285](semantics_model_r4.py) [semantics_model_r4.py:298](semantics_model_r4.py) [semantics_model_r4.py:309](semantics_model_r4.py)
- **K4:** v1 rejects move-only selected errors; physical reconstruction under exhaustion and D41/runtime admission are still integration work. The ordinary Path/string case and M1 input are covered, but this is not unrestricted recovery for every owning payload. [09_selective_recovery.dewy:34](programs-r4/09_selective_recovery.dewy) [round4.md:205](round4.md) [round4.md:207](round4.md)

The model asserts zero callback and gate invocations for 72 incoming-cancellation arrangements. The explicit variant shows the same pre-guard under `$explicit_cancellation`; Python storage erasure is only an algebra stand-in, not ABI proof. [09_selective_recovery.dewy:11](programs-r4/09_selective_recovery.dewy) [semantics_model_r4.py:289](semantics_model_r4.py)

### 10 — Domain cause deferred; layered context: 5/4/5/5/3

- **D4:** transparent context still needs its meaning taught; it does not mint ConfigError. [10_domain_cause.dewy:5](programs-r4/10_domain_cause.dewy) [10_domain_cause.dewy:24](programs-r4/10_domain_cause.dewy)
- **K3:** the original domain-identity-plus-cause workload is **not delivered in v1**. The replacement demonstrates the useful smaller context feature; it cannot substitute for an abstraction that deliberately exposes a new domain error while retaining a typed cause. This is why the original K5 drops rather than staying 5 after scope reduction. [10_domain_cause.dewy:1](programs-r4/10_domain_cause.dewy) [10_domain_cause.dewy:24](programs-r4/10_domain_cause.dewy) [round4.md:223](round4.md)
- **O5/C5:** for the narrower delivered context behavior, each layer simply returns a contextualized result and one reporter displays it. [10_domain_cause.dewy:5](programs-r4/10_domain_cause.dewy) [10_domain_cause.dewy:12](programs-r4/10_domain_cause.dewy) [10_domain_cause.dewy:18](programs-r4/10_domain_cause.dewy)
- **S5:** adding context leaves cancellation and failure identity intact, avoiding the old repeated-cause overwrite question by leaving that API out of v1. This does not grade a nonexistent domain-translation operation safe. [10_domain_cause.dewy:25](programs-r4/10_domain_cause.dewy) [10_domain_cause.dewy:26](programs-r4/10_domain_cause.dewy)

### 11 — Occurrence origins: 4/4/5/5/5

- **O4:** origin means construction, not the last propagation or report boundary; cached constants keep their older site. [11_occurrence_origins.dewy:24](programs-r4/11_occurrence_origins.dewy) [11_occurrence_origins.dewy:27](programs-r4/11_occurrence_origins.dewy)
- **D4:** the metadata member and none/unknown-origin branch require discovery; the broad cold read did not establish exact capture timing. [11_occurrence_origins.dewy:15](programs-r4/11_occurrence_origins.dewy) [round4.md:227](round4.md)
- **C5:** read one optional site and print it; no capture wrapper at each producer. [11_occurrence_origins.dewy:14](programs-r4/11_occurrence_origins.dewy)
- **S5:** metadata does not affect payload equality, and persistent annotation leaves the original unchanged. These are proposed value semantics, with context nonmutation modeled separately. [11_occurrence_origins.dewy:8](programs-r4/11_occurrence_origins.dewy) [11_occurrence_origins.dewy:10](programs-r4/11_occurrence_origins.dewy) [semantics_model_r4.py:331](semantics_model_r4.py)
- **K5:** this two-occurrence example distinguishes the two error sites and handles none honestly. It does not promise an origin for every absence, a retroactive stack, or unknown foreign sites. Its completeness score is not a representation-cost certificate. [11_occurrence_origins.dewy:21](programs-r4/11_occurrence_origins.dewy) [11_occurrence_origins.dewy:24](programs-r4/11_occurrence_origins.dewy) [round4.md:215](round4.md)

Default capture is still provisional pending success-union ABI, optional, binary-table and instruction-count measurements. Exempting none does not remove error-bearing success-path layout costs. [11_occurrence_origins.dewy:25](programs-r4/11_occurrence_origins.dewy) [round4.md:217](round4.md)

### 12 — Bounded validation: 5/4/5/4/4

- **D4:** the application defines its own omission-summary kind and retention boundary. [12_bounded_validation.dewy:4](programs-r4/12_bounded_validation.dewy)
- **S4/K4:** a diagnostic-count cap does not bound retained input memory or guarantee physical allocation, and the explicit allocation-failure lane remains open. [12_bounded_validation.dewy:27](programs-r4/12_bounded_validation.dewy)
- **O5/C5:** append until the stated count, then add one typed omitted-count summary; no new accumulator class. [12_bounded_validation.dewy:11](programs-r4/12_bounded_validation.dewy) [12_bounded_validation.dewy:18](programs-r4/12_bounded_validation.dewy)

### 13 — Operator contract: 4/3/5/4/4

- **O4/D3:** a value expression using `&` produces ErrorGroup even when its operands' type intersection is empty. Learning the type/value distinction is a real cost; neither the existing conjunction spelling nor the old cold read proves readers will infer it. [13_operator_contract.dewy:3](programs-r4/13_operator_contract.dewy) [13_operator_contract.dewy:30](programs-r4/13_operator_contract.dewy) [round4.md:137](round4.md)
- **C5:** a pair and a seeded fold are each one operator expression; repeated occurrences need no special wrapper. [13_operator_contract.dewy:8](programs-r4/13_operator_contract.dewy) [13_operator_contract.dewy:12](programs-r4/13_operator_contract.dewy) [13_operator_contract.dewy:23](programs-r4/13_operator_contract.dewy)
- **S4:** eager evaluation means `f() & g()` can start g after f yields cancellation. The proposal explicitly limits the preferred idiom to already obtained failures and requires ordinary fail-fast calls to use or_throw; the spelling alone does not enforce that usage. [round4.md:145](round4.md) [13_operator_contract.dewy:8](programs-r4/13_operator_contract.dewy) [semantics_model_r4.py:272](semantics_model_r4.py)
- **K4:** order, duplicates, incompatible child payloads, group projection, direct extraction and seeded accumulation are covered, but this does **not** satisfy the requested literal `A & B` return-type promise. The true-intersection candidate needs a broader field/nominal/handler redesign to be universal. [13_operator_contract.dewy:17](programs-r4/13_operator_contract.dewy) [13_operator_contract.dewy:20](programs-r4/13_operator_contract.dewy) [13_operator_contract.dewy:30](programs-r4/13_operator_contract.dewy) [round4.md:88](round4.md) [round4.md:118](round4.md)

## What the revision fixes, and what is still a choice

M1 is fixed in the proposed recovery contract and the executable algebra, including incoming values from another task, nested/contextual trees, an explicit propagation guard, cancellation between repairs, canceled callback results, and cancellation after the last successful repair. Physical callback-start ordering remains an implementation acceptance gate. A successful repair is not rolled back when cancellation arrives afterward. [round4.md:200](round4.md) [round4.md:202](round4.md) [semantics_model_r4.py:278](semantics_model_r4.py)

M2 is addressed by withdrawing the storage argument and specifying candidate I's canonical projection, nominal tests, selected handlers, cancellation, exact parts and accumulator. Order and duplicates are preserved in every candidate. The real objections are incompatible shared-field constraints, siblings consumed by ordinary A handlers, and Canceled intersected with an ordinary-error subtype satisfying error. The recommended operator is an overload returning the one group, **not** a disguised true intersection. [round4.md:79](round4.md) [round4.md:87](round4.md) [round4.md:114](round4.md)

S1: one exception-derived group, with the loss of all-error family compatibility disclosed. S2: ordinary-library recovery owns the remainder. S3/S5: cause and trace surfaces deferred; no repeated-cause policy is silently preserved. S4: none explicitly exempted, successful-union/ABI and binary disclosure costs stated. Additional fixes: unexpected form leaves are reported; retry accepts grouped operation failures and canceled backoff; the ordinary explicit-cancellation continuation is exercised; body+cleanup and cancellation+cleanup exit priorities are distinguished. [round4.md:141](round4.md) [round4.md:205](round4.md) [round4.md:213](round4.md) [round4.md:221](round4.md)

## Verification and limits

`python3 -B semantics_model_r4.py` reported:

```text
PASS: 10885 partitions; 72 incoming-cancellation cases; 6 admission schedules; operator/recovery/context/deep-tree checks
```

Partition checks cover ordered occurrences, default/forward behavior and inherited context. Operator checks cover zero/one/many joins, exact children, generic message projection, duplicate operands, invalid successful operands, a seeded fold and eager evaluation. Recovery checks cover unchanged incoming cancellation, all named admission boundaries, failed repair, callback-returned cancellation, unmatched values, all-success, and last-callback cancellation. The deep tree has 2,001 leaves. [semantics_model_r4.py:219](semantics_model_r4.py) [semantics_model_r4.py:254](semantics_model_r4.py) [semantics_model_r4.py:278](semantics_model_r4.py) [semantics_model_r4.py:335](semantics_model_r4.py)

Unlike the old model, the cancellation flag is cached on construction from immediate children's cached flags. Python tuples remain a correctness representation, not a shared-path or owner-safe implementation; no linear-time or ABI claim follows from these runs. The synthetic Gate serializes named boundaries, not concurrent task delivery. No Dewy programs, negative type examples, peer programs, trace capture, allocator paths or metadata costs were executed. No new independent review or name test was performed. Historical proposals, programs, reviews and the original model were left unchanged. [semantics_model_r4.py:1](semantics_model_r4.py) [semantics_model_r4.py:27](semantics_model_r4.py) [semantics_model_r4.py:145](semantics_model_r4.py)
