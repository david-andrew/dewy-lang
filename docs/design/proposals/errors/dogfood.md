# Dogfood: final paper grades

**No all-5 verdict.** The final floor is 3: discoverability of carrying cancellation, concise selective recovery, and completeness of cleanup under explicit allocation exhaustion. The ordinary application paths are mostly 4–5. A design can be worth taking forward without claiming every unresolved integration detail has disappeared.

Twelve complete enclosing Dewy examples are in programs/. They use proposed APIs and are **not compiled or run**. Program 01 injects device failures; program 07 injects connection outcomes; the remaining code uses existing library-style operations or pure validation. All peer snippets are also paper comparisons. Only semantics_model.py was executed. Scores assume the specified APIs are correctly implemented; they do not claim current compiler capability.

## Rubric

Order is **O/D/C/S/K**: obvious, discoverable, concise, safe by default, complete. 5 = no material issue for the stated scenario; 4 = a bounded surprise, extra ceremony or explicit limitation; 3 = substantial protocol knowledge or a material unresolved subcase; 2 = the main path has a serious hole; 1 = it fails the scenario. Safety includes likely edits and accidental loss of siblings/cancellation; it is not only memory safety. Completeness is scoped to each program, not every possible application.

Names are not independently cold-read, so no Dewy discoverability grade is 5. A chosen tradeoff remains a deduction even when its rule is documented. A peer's out-of-the-box library gaps are graded as such; third-party ecosystems may improve them. See comparisons.md for the exact peer idioms, primary references, and the rationale for **every** peer score below 5. No workload timing or user-study claims.

## Scorecard

| Program | Dewy | Python | Go | Rust | TypeScript | Swift |
|---|---|---|---|---|---|---|
| 01 Cleanup pair | [4/4/5/4/3](#dewy-01) | [4/4/3/4/5](comparisons.md#python-01) | [4/4/5/4/5](comparisons.md#go-01) | [4/4/3/4/4](comparisons.md#rust-01) | [4/4/5/4/4](comparisons.md#typescript-01) | [4/4/3/4/4](comparisons.md#swift-01) |
| 02 Form validation | [5/4/4/5/5](#dewy-02) | [5/5/4/4/5](comparisons.md#python-02) | [5/5/5/4/5](comparisons.md#go-02) | [5/4/4/5/5](comparisons.md#rust-02) | [5/5/4/4/5](comparisons.md#typescript-02) | [5/4/4/5/5](comparisons.md#swift-02) |
| 03 Batch files | [5/4/4/5/5](#dewy-03) | [5/4/4/4/5](comparisons.md#python-03) | [5/4/4/4/5](comparisons.md#go-03) | [5/4/3/4/5](comparisons.md#rust-03) | [5/4/4/4/5](comparisons.md#typescript-03) | [5/4/4/4/5](comparisons.md#swift-03) |
| 04 Parallel items | [5/4/5/5/5](#dewy-04) | [5/4/4/4/5](comparisons.md#python-04) | [4/4/3/4/5](comparisons.md#go-04) | [4/4/3/4/4](comparisons.md#rust-04) | [5/5/5/4/5](comparisons.md#typescript-04) | [4/4/3/4/5](comparisons.md#swift-04) |
| 05 Library context | [5/4/5/5/5](#dewy-05) | [5/5/5/4/5](comparisons.md#python-05) | [5/5/5/5/4](comparisons.md#go-05) | [5/4/4/5/4](comparisons.md#rust-05) | [5/5/5/4/4](comparisons.md#typescript-05) | [5/4/4/5/4](comparisons.md#swift-05) |
| 06 CLI diagnostics | [4/4/4/4/4](#dewy-06) | [5/5/5/4/4](comparisons.md#python-06) | [4/3/3/4/3](comparisons.md#go-06) | [4/3/3/4/3](comparisons.md#rust-06) | [4/3/3/4/4](comparisons.md#typescript-06) | [4/3/3/4/3](comparisons.md#swift-06) |
| 07 Retry history | [5/4/4/5/5](#dewy-07) | [5/4/4/4/5](comparisons.md#python-07) | [5/4/4/4/5](comparisons.md#go-07) | [5/4/4/4/5](comparisons.md#rust-07) | [5/4/4/4/5](comparisons.md#typescript-07) | [5/4/4/4/5](comparisons.md#swift-07) |
| 08 Cancellation boundary | [4/3/4/5/5](#dewy-08) | [4/4/4/4/5](comparisons.md#python-08) | [4/4/4/3/5](comparisons.md#go-08) | [4/3/3/3/4](comparisons.md#rust-08) | [4/3/3/3/4](comparisons.md#typescript-08) | [4/3/3/3/5](comparisons.md#swift-08) |
| 09 Selective recovery | [4/4/3/4/5](#dewy-09) | [4/4/5/5/5](comparisons.md#python-09) | [4/3/3/4/4](comparisons.md#go-09) | [4/3/3/4/4](comparisons.md#rust-09) | [4/3/3/4/4](comparisons.md#typescript-09) | [4/3/3/4/4](comparisons.md#swift-09) |
| 10 Domain cause | [5/4/5/5/5](#dewy-10) | [5/5/5/5/5](comparisons.md#python-10) | [5/5/5/4/5](comparisons.md#go-10) | [5/4/4/5/5](comparisons.md#rust-10) | [5/5/5/4/5](comparisons.md#typescript-10) | [5/4/4/5/5](comparisons.md#swift-10) |
| 11 Occurrence origins | [4/4/5/5/5](#dewy-11) | [4/4/4/4/3](comparisons.md#python-11) | [4/3/3/4/4](comparisons.md#go-11) | [4/4/4/5/4](comparisons.md#rust-11) | [4/4/4/4/4](comparisons.md#typescript-11) | [4/4/4/5/4](comparisons.md#swift-11) |
| 12 Bounded validation | [5/4/4/4/4](#dewy-12) | [5/5/4/4/4](comparisons.md#python-12) | [5/5/4/4/4](comparisons.md#go-12) | [5/4/4/4/4](comparisons.md#rust-12) | [5/5/4/4/4](comparisons.md#typescript-12) | [5/4/4/4/4](comparisons.md#swift-12) |

## Every Dewy deduction, and the evidence for the fives

<a id="dewy-01"></a>

### 01 Cleanup pair — 4/4/5/4/3

- **O4:** [01_cleanup_pair.dewy:19](programs/01_cleanup_pair.dewy). The return can acquire two completion failures at the closing brace; the source-level exit is concise but its result is not just the written WriteFailed.
- **D4:** [01_cleanup_pair.dewy:10](programs/01_cleanup_pair.dewy). A fallible $__drop__ must be discovered through the owner contract and the new join API.
- **S4:** [01_cleanup_pair.dewy:21](programs/01_cleanup_pair.dewy). Failures are retained, but a failed write is not a rollback; the modeled operation may have partially changed the device (line 30).
- **K3:** [01_cleanup_pair.dewy:31](programs/01_cleanup_pair.dewy). Lossless cleanup grouping under explicit allocation exhaustion has no implemented/pre-reserved representation yet.
- **C5:** [01_cleanup_pair.dewy:14](programs/01_cleanup_pair.dewy). Close still runs after flush fails; the two failures use the same join as ordinary code.

<a id="dewy-02"></a>

### 02 Form validation — 5/4/4/5/5

- **D4:** [02_form_validation.dewy:11](programs/02_form_validation.dewy). The cause/outer-field distinction and the new group API need documentation; names have not been cold-read.
- **C4:** [02_form_validation.dewy:6](programs/02_form_validation.dewy). An accumulator, age staging variable, and final propagation add ceremony to three checks.
- **O5:** [02_form_validation.dewy:7](programs/02_form_validation.dewy). Independent fields directly append issues in their displayed order.
- **S5:** [02_form_validation.dewy:17](programs/02_form_validation.dewy). An invalid field cannot escape as a User; cancellation is not in this synchronous parser contract.
- **K5:** [02_form_validation.dewy:20](programs/02_form_validation.dewy). Both field reporting and the original parse cause are retained; the successful path constructs the typed User.

<a id="dewy-03"></a>

### 03 Batch files — 5/4/4/5/5

- **D4:** [03_batch_files.dewy:9](programs/03_batch_files.dewy). Programmers must know when with_context preserves the original failure kind and when join produces a group.
- **C4:** [03_batch_files.dewy:4](programs/03_batch_files.dewy). The cancellation-first branch and accumulator are explicit overhead.
- **O5:** [03_batch_files.dewy:6](programs/03_batch_files.dewy). One ordinary loop attempts paths in input order.
- **S5:** [03_batch_files.dewy:10](programs/03_batch_files.dewy). Cancellation joins the failures already observed and exits before another read.
- **K5:** [03_batch_files.dewy:18](programs/03_batch_files.dewy). The all-or-failure result retains every observed failure and returns a byte count only when all reads succeeded.

<a id="dewy-04"></a>

### 04 Parallel items — 5/4/5/5/5

- **D4:** [04_parallel_items.dewy:13](programs/04_parallel_items.dewy). partition_failures is accepted, but connecting it to join and learning group result types still needs discovery.
- **O5:** [04_parallel_items.dewy:12](programs/04_parallel_items.dewy). The comprehension expresses per-row independent validation.
- **C5:** [04_parallel_items.dewy:14](programs/04_parallel_items.dewy). One partition and one propagation combine failures.
- **S5:** [04_parallel_items.dewy:7](programs/04_parallel_items.dewy). Bad rows are values; they do not cancel peers or disappear through defaulting.
- **K5:** [04_parallel_items.dewy:21](programs/04_parallel_items.dewy). Input order and the explicitly nonwaiting CPU-only scenario are covered; canceled waiting-work collection is not claimed.

<a id="dewy-05"></a>

### 05 Library context — 5/4/5/5/5

- **D4:** [05_library_context.dewy:6](programs/05_library_context.dewy). The type-preserving context operation is new and untested cold; ordinary error wrapping in other languages suggests a different expectation.
- **O5:** [05_library_context.dewy:6](programs/05_library_context.dewy). The operation text says which library boundary failed.
- **C5:** [05_library_context.dewy:9](programs/05_library_context.dewy). Each boundary adds one call.
- **S5:** [05_library_context.dewy:6](programs/05_library_context.dewy). The exception family including Canceled passes through unchanged.
- **K5:** [05_library_context.dewy:7](programs/05_library_context.dewy). Read, parse, validation and success paths are all represented without erasing the file failure kind.

<a id="dewy-06"></a>

### 06 CLI diagnostics — 4/4/4/4/4

- **O4:** [06_cli_diagnostics.dewy:16](programs/06_cli_diagnostics.dewy). Trace activation precedes construction and cannot repair traces of previously constructed values; this distinction is easy to miss.
- **D4:** [06_cli_diagnostics.dewy:19](programs/06_cli_diagnostics.dewy). The reporter, trace setting and per-read display switches are three surfaces to learn.
- **C4:** [06_cli_diagnostics.dewy:20](programs/06_cli_diagnostics.dewy). Manual reporting needs an explicit nonzero exit to avoid the default main reporter printing twice.
- **S4:** [06_cli_diagnostics.dewy:26](programs/06_cli_diagnostics.dewy). Message/context text is application-controlled; control escaping does not redact secrets placed there.
- **K4:** [06_cli_diagnostics.dewy:25](programs/06_cli_diagnostics.dewy). Unavailable target tracing is represented honestly, but a full logical/async historical trace is not supplied.

<a id="dewy-07"></a>

### 07 Retry history — 5/4/4/5/5

- **D4:** [07_retry_history.dewy:9](programs/07_retry_history.dewy). The positive bound and explicitly limited callback failure union are part of the API contract; joining history is a new idiom.
- **C4:** [07_retry_history.dewy:10](programs/07_retry_history.dewy). Attempt annotation, history and the cancellation branch take explicit code.
- **O5:** [07_retry_history.dewy:11](programs/07_retry_history.dewy). The bounded attempt loop states the retry policy.
- **S5:** [07_retry_history.dewy:15](programs/07_retry_history.dewy). Canceled exits with earlier attempts retained; success alone drops old failures intentionally.
- **K5:** [07_retry_history.dewy:23](programs/07_retry_history.dewy). Exhaustion, success, repeated same-kind failures and cancellation are covered within the declared callback contract.

<a id="dewy-08"></a>

### 08 Cancellation boundary — 4/3/4/5/5

- **O4:** [08_cancellation_boundary.dewy:4](programs/08_cancellation_boundary.dewy). The result contains Canceled but is an ExceptionGroup, so is? Canceled is false.
- **D3:** [08_cancellation_boundary.dewy:11](programs/08_cancellation_boundary.dewy). or_throw<Canceled> is descendant-aware while ordinary matching is not; the array-literal trap on line 35 is another distinct rule.
- **C4:** [08_cancellation_boundary.dewy:25](programs/08_cancellation_boundary.dewy). Deliberately storing cancellation requires explicit push; collectors cannot be used as inert packing syntax.
- **S5:** [08_cancellation_boundary.dewy:6](programs/08_cancellation_boundary.dewy). The default leaves the function with the whole group; the print is unreachable.
- **K5:** [08_cancellation_boundary.dewy:16](programs/08_cancellation_boundary.dewy). Explicit inspection, checked propagation and deliberate storage all cover the same payload without turning it into error.

<a id="dewy-09"></a>

### 09 Selective recovery — 4/4/3/4/5

- **O4:** [09_selective_recovery.dewy:7](programs/09_selective_recovery.dewy). Split preserves a tree, not just an array of already-narrowed MissingAsset values.
- **D4:** [09_selective_recovery.dewy:11](programs/09_selective_recovery.dewy). The caller needs both split and the context-preserving leaves traversal.
- **C3:** [09_selective_recovery.dewy:8](programs/09_selective_recovery.dewy). Selective recovery needs a rest accumulator, nested traversal and a stop flag; this is the most cumbersome example.
- **S4:** [09_selective_recovery.dewy:8](programs/09_selective_recovery.dewy). Rest is ordinary data. Deleting its use can lose unrelated failures; the type system does not force it to be forwarded.
- **K5:** [09_selective_recovery.dewy:14](programs/09_selective_recovery.dewy). Unattempted leaves are kept after cancellation; lines 18–19 keep failed recovery causes, and line 25 forwards all pending failures.

<a id="dewy-10"></a>

### 10 Domain cause — 5/4/5/5/5

- **D4:** [10_domain_cause.dewy:6](programs/10_domain_cause.dewy). The distinction between caused_by and transparent with_context must be taught; the new cause member is not cold-read.
- **O5:** [10_domain_cause.dewy:6](programs/10_domain_cause.dewy). A public ConfigError names the operation and explicitly keeps its cause.
- **C5:** [10_domain_cause.dewy:8](programs/10_domain_cause.dewy). Translation takes one construction and one call.
- **S5:** [10_domain_cause.dewy:5](programs/10_domain_cause.dewy). Cancellation is forwarded before it can be wrapped in an ordinary error.
- **K5:** [10_domain_cause.dewy:12](programs/10_domain_cause.dewy). The lower cause is inspectable while outer-kind matching stays ConfigError.

<a id="dewy-11"></a>

### 11 Occurrence origins — 4/4/5/5/5

- **O4:** [11_occurrence_origins.dewy:25](programs/11_occurrence_origins.dewy). An origin is a construction occurrence, not necessarily the user-facing call site; cached constants keep their old origin (line 28).
- **D4:** [11_occurrence_origins.dewy:14](programs/11_occurrence_origins.dewy). The new metatag members are not ordinary payload fields and must be discoverable in completion/docs.
- **C5:** [11_occurrence_origins.dewy:14](programs/11_occurrence_origins.dewy). Reading location needs one member plus an ordinary optional branch.
- **S5:** [11_occurrence_origins.dewy:8](programs/11_occurrence_origins.dewy). Equal payloads cannot alias one metadata slot; line 10 checks that decorating a copy leaves the original alone.
- **K5:** [11_occurrence_origins.dewy:6](programs/11_occurrence_origins.dewy). Two origins, value-local annotation, absent origins and disabled historical traces are covered by the scenario.

<a id="dewy-12"></a>

### 12 Bounded validation — 5/4/4/4/4

- **D4:** [12_bounded_validation.dewy:4](programs/12_bounded_validation.dewy). An explicit summary kind is a local application decision; grouping does not choose a retention policy automatically.
- **C4:** [12_bounded_validation.dewy:7](programs/12_bounded_validation.dewy). Count limiting and omission accounting are manual.
- **S4:** [12_bounded_validation.dewy:27](programs/12_bounded_validation.dewy). The count bound does not bound input memory or guarantee physical allocation.
- **K4:** [12_bounded_validation.dewy:28](programs/12_bounded_validation.dewy). The strict allocation-failure lane remains unproven, just as in the other languages' bounded-collection idioms.
- **O5:** [12_bounded_validation.dewy:11](programs/12_bounded_validation.dewy). The branch explicitly chooses whether to keep a row or count it as omitted.

## What actually changed during dogfood

- Round 1 used one error-family group. The broad-error-handler counterexample forced the two-type design in round 2. The S2 first-pass failure is not carried forward as S5 without a change: program 08 now produces ExceptionGroup, outside error, and the model checks that no cancellation-carrying generated tree is ordinary error.

- Round 1 left origin recording optional/undefined. Round 2 records the construction site, exposes unknown explicitly, and captures bounded traces only when enabled. Program 11 exercises the difference between original and context sites. No retroactive capture is claimed.

- Round 2's leaf extraction lost ancestor context. Round 3 gives leaves inherited diagnostic frames. The model compares contexts on every partition output, and program 09 retains that context when combining an original missing asset with a failed regeneration.

- Program 09 initially returned immediately when regeneration was canceled, dropping matched leaves not yet attempted. The final stop flag retains those leaves without performing more recovery. That is a real code correction; S stays 4 because an application can still ignore rest.

- The ownership pass removed any implication that snapshot/group splitting clones resource-owning payloads, and prohibited a group-valued outer cause wrapper that would duplicate an owned cause across split branches. The twelve copyable-payload examples do not pretend to test this compiler ownership contract.

## Executed verification

Ran `python3 -B /var/home/david/dev/tmp/par10/errors/semantics_model.py`. Result: **PASS: 10885 partition cases plus selection, origin, cause and deep-tree checks**. The model generates all ordered leaf-kind sequences of lengths 1–4 from FileError, ParseError, Canceled, none and Stop, including nested/contextual variants, then partitions each by seven selectors. See [case enumeration](semantics_model.py).

It also checks zero/one join, duplicate occurrences, preserved origins, cancellation default/forward selection, exclusion of causes from leaf splitting, rejected cancellation causes, inherited context, and iterative traversal/splitting of a 2,001-leaf tree ([additional checks](semantics_model.py)).

This is a reference algebra, not a compiler test. It does not validate parser/type inference, cleanup insertion, ownership modes, scheduling, origin ABI, source symbolization, allocation failure or advertised asymptotic costs of the production representation. No compiler build was started and the read-only checkout was not modified.

## Why iteration stops here

The fixable semantic holes found within this slice were changed in rounds 2–3. The remaining O/D costs are the explicit tradeoffs listed in round3.md: nominal outer matching versus descendant-aware cancellation, two failure families, and an explicit split remainder. Reducing those scores by changing the meaning of is?, adding a general linear error system or pretending names were tested would be dishonest. The remaining K3 is a concrete implementation/resource gate, not a wording problem. Cleanup timing, visible loop exits and canceled waiting-work collection belong to the neighboring designs.

Before this can be marked all-5 dogfooded: independent cold readers must test names; actual programmers must test the cancellation/split examples; and an implementation must demonstrate lossless bounded-resource cleanup and owning payload traversal. Those are outstanding gates, not work claimed done here.
