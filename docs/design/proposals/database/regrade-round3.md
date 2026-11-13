# Independent regrade of the final database programs

These scores and their reasons were fixed before reading `dogfood.md`. Round 3 overrides round 2, which overrides round 1. This grades the proposed contracts and the actual specimens, not an engine claimed to exist. I did not run the specimens: the database modules are proposals, and building the checkout would violate this review's read-only scope. Existing compiler source and regression fixtures were inspected where they settle a language question.

O = obvious, D = discoverable, C = concise, S = safe by default, K = complete. 5 means no material disadvantage for this task against the reference peers; 4 means a local friction or an explicit unresolved guarantee; 3 means substantial ceremony or missing workflow; 2 means a central promise is blocked or the specimen needs redesign; 1 would mean the task is effectively unserved. These are reviewer judgments, not usability measurements. A correct rejecting compiler does not become unsafe because a specimen is invalid; that primarily reduces K.

## Scores fixed before seeing the author's grades

| Program | O | D | C | S | K |
|---|---:|---:|---:|---:|---:|
| 01_todo | 4 | 4 | 4 | 4 | 2 |
| 02_bank_ledger | 4 | 3 | 3 | 4 | 4 |
| 03_blog | 4 | 3 | 4 | 4 | 2 |
| 04_analytics | 4 | 3 | 4 | 4 | 2 |
| 05_inventory_tasks | 4 | 3 | 4 | 4 | 2 |
| 06_schema_change | 4 | 3 | 3 | 4 | 3 |
| 07_full_text | 4 | 4 | 5 | 4 | 3 |
| 08_memory_test | 5 | 4 | 4 | 4 | 3 |
| 09_interactive_cli | 4 | 4 | 5 | 4 | 3 |
| 10_csv_import | 4 | 3 | 2 | 4 | 3 |
| 11_existing_sqlite | 5 | 4 | 4 | 5 | 4 |
| 12_game_saves | 4 | 4 | 4 | 4 | 3 |
| 13_paging_backup | 4 | 3 | 4 | 4 | 2 |
| 14_untranslated_predicate | 4 | 3 | 4 | 4 | 2 |
| csv_products (support program) | 3 | 3 | 2 | 4 | 3 |

All file/line references below are relative to `programs/`. Every score below 5 has a line citation. Missing implementation evidence is distinguished from a missing contract; I do not subtract the same general “not implemented” point from every dimension.

### 01_todo.dewy

- **O4, lines 19–25:** a short listing introduces an unevaluated recipe, a terminal page and a snapshot-owning continuation. `size=20` means neither 20 records read nor a bounded sort.
- **D4, lines 5–8 and 19–25:** the developer must discover compound index order and continuation lifetime as well as ordinary CRUD; existing arrays use `filter`, while the new receiver uses `where`.
- **C4, lines 21–26:** six lines implement page draining. A reusable ordinary iterator/paging helper could remove this without changing the database model.
- **S4, lines 19–25:** default scan/sort warnings do not bound work; the page can inspect/sort the whole matching set. This is a cost-safety limitation, not evidence of wrong results.
- **K2, lines 7 and 20:** the indexed callback mechanism remains absent, and the sort callback returns an untyped array literal rather than an explicitly typed tuple. Existing `tests/cases/sort/array_key_hint.*` diagnoses this exact ordinary-collection mistake; use `(t):>[int string] => [t.priority t.id]`. The descriptor's compound selector also needs a defined tuple type/context.

**Peers:** Python/sqlite3 and Go/sql need SQL and decoding; Django and Prisma express this CRUD/listing with less continuation ceremony; Diesel provides typed ordering with more setup; Swift/GRDB has explicit record requests and fetching. Dewy's ordinary values and visible writes help, but this is not yet the easiest complete todo implementation among them.

### 02_bank_ledger.dewy

- **O4, lines 19–26:** distinguishing an absent optional from real failures is correct but hard to read at the first required account lookup.
- **D3, lines 18–35:** move-only transaction consumption, abandonment, required lookup, reference creation, idempotency and uncertain publication form a large first financial-workflow vocabulary.
- **C3, lines 19–34:** two-stage required lookups, separate reference lookups, two journal records and request persistence are substantial. The journal/idempotency work is necessary across languages; the lookup noise is avoidable API friction.
- **S4, lines 22 and 35:** explicit rollback/commit and full request comparison are good. Cleanup-error composition and commit/cancellation fault behavior still depend on D40 and engine gates; the specimen demonstrates neither uncertain publication nor recovery.
- **K4, lines 35 and 38–43:** the replay path is sound under the stated serializable contract, but a memory-only two-call demonstration omits restart and CommitUnknown reconciliation. It is a transfer example, not yet a complete durable ledger workflow.

**Peers:** Python/sqlite3, Go/sql and GRDB also need explicit balanced entries and durable request IDs; Django/Prisma transaction wrappers shorten setup but do not supply idempotency automatically; Diesel gives transactional typed access but still needs the same business protocol. Dewy improves rollback defaults and exact money arithmetic; it does not eliminate application ledger design.

### 03_blog.dewy

- **O4, lines 27–28:** `follow(tags)` returns repeated target tags and discards the source post. That is consistent with the amended contract but surprising for someone expecting a set of tags.
- **D3, lines 6–12 and 23–29:** reverse indexes, typed reference provenance, flattening, duplicate preservation and an explicit snapshot must all be learned. Same-type target ambiguity and required reference cycles remain acknowledged gaps.
- **C4, line 29:** fetching one known author still requires the two-stage failure/absence expression.
- **S4, lines 17–21:** constraints and explicit publication are well specified, but rollback/commit cleanup evidence is still pending D40. Restrict-on-delete is safe but needs an ergonomic explicit unlink workflow (line 31).
- **K2, lines 23–30:** this never produces the common feed row containing a post title and its author's name, or filters posts by an author field. `map` cannot perform `get` I/O, while `follow` loses the post. A two-query scalar-follow plus positional pairing under the same explicit snapshot can be written from current primitives, but is manual join ceremony; set-valued follow also loses grouping boundaries. The central ordinary-lambda indexing prerequisite is still unresolved.

**Peers:** Django's `select_related`/`prefetch_related`, Prisma's related reads, Diesel joins and GRDB associations serve combined parent/related results; Python/sqlite3 and Go/sql express them with joins and row decoding. Dewy's stored set is attractive for membership, but it has not matched those common read shapes ergonomically.

### 04_analytics.dewy

- **O4, lines 9–11:** a grouped row visibly contains a full array of items; a reader must distinguish that logical value from an optimizer's possible accumulator implementation.
- **D3, lines 8–12:** discovering which ordinary callbacks/comprehensions fuse, which need retained arrays and which exact operators can run in SQLite is substantial provider knowledge.
- **C4, lines 10–11:** counting group items and constructing an inner array before summing is wordier than a direct count/sum aggregation, even if the optimizer might erase it.
- **S4, lines 9–12:** exact arithmetic is specified, but an unfused group retains O(N) rows plus inner projection storage without a bound here. Round 3 correctly excludes an unsupported strict allocation-failure lane.
- **K2, lines 8–12:** callable inspection and nested iteration/aggregate fusion have no designed mechanism yet. The reference evaluator can produce the requested values; the promised efficient native analytic pipeline remains conditional.

**Peers:** Python/sqlite3, Go/sql and GRDB can issue one grouped SQL query; Django, Prisma and Diesel have aggregate query surfaces. Dewy removes aggregate string names and preserves exact int semantics, but its current spelling and retained-group risk do not establish a common-case advantage.

### 05_inventory_tasks.dewy

- **O4, lines 32–37:** this looks like a CPU parallel loop despite performing writer admission and storage operations that may wait.
- **D3, lines 15 and 32–37:** a newcomer needs the distinction between CPU work and waiting tasks; the specimen teaches the wrong choice. It also requires the idempotency vocabulary from program 02.
- **C4, lines 16–25:** correct request validation/replay and required lookup are longer than the reservation's two data changes; some is necessary business protocol, but the lookup friction is reusable.
- **S4, lines 15 and 26:** serialization, atomic decrement and payload-checked request IDs are safe contracts; D40/fault evidence and task-group cancellation outcomes remain unexercised. Do not “fix” the loop by falsely certifying database calls as nonblocking.
- **K2, lines 32–37:** `parallel` bodies must be nonblocking, including through calls (LANGUAGE.md, Parallel CPU work). `begin(timeout=2s)` expressly waits for SQLite writer admission. This example cannot demonstrate legal concurrent database tasks until it uses the accepted waiting-task lane and forwards the group result.

**Peers:** Go goroutines, Rust tasks/threads and Swift tasks, Python workers and Prisma's concurrent callers can share a database pool while owning separate transactions. All face SQLite's single writer. Dewy's ownership story is good; the shown scheduling construct is incompatible with its own language rules.

### 06_schema_change.dewy

- **O4, lines 8 and 14–16:** rename intent and the value transform both spell the same field mapping. Their respective responsibilities need explanation.
- **D3, lines 6–19:** old/new types, descriptors, stable IDs, rename/remove intent, transformation and migration publication are a sizeable workflow with no generator shown.
- **C3, lines 8 and 14–16:** preserving old schemas is necessary, but this simple rename/removal repeats field mappings and hand-writes what migration tools normally generate for review.
- **S4, lines 11–19:** no silent migration and deliberate removal are strong. Backup and migration are separate snapshots/operations; writer exclusivity and crash atomicity are promises awaiting evidence, not established by this program.
- **K3, lines 10–20:** the one-shot path has no already-applied check or migration runner; rerunning fails at the v1 open (or at the fixed backup path after an earlier failure). Recovery/resume and transformations of typed references to changed targets need more specification.

**Peers:** Django, Prisma, Diesel and GRDB offer versioned migration workflows; Python/sqlite3 and Go/sql generally need a library or custom runner. Dewy's explicit deletion intent is safer than blind schema synchronization, but the operational workflow and duplicated mapping are behind mature tools.

### 07_full_text.dewy

- **O4, lines 12–17:** `search` looks general, while the contract is literal token intersection with backend-dependent ranking, rather than substring, phrase or boolean search.
- **D4, lines 6 and 12:** tokenizer capability, language behavior and ranking portability are not discoverable from `language='en'` alone.
- **S4, lines 12–15:** injection-safe literal terms and plain-text excerpts are good; ten returned hits do not bound search/ranking effort. No query-work bound is requested.
- **K3, lines 6 and 17:** the design deliberately defers multilingual, phrase and boolean behavior, and has not pinned the language/tokenizer mapping or fallback capabilities sufficiently to reproduce a search experience across engines.

**Peers:** Python/sqlite3, Go/sql and Diesel can use SQLite FTS with more explicit adapter work; Django and Prisma search support depends on backend/features; GRDB supports SQLite-oriented search. This is a concise literal-search common case, not a replacement for those fuller search workflows.

### 08_memory_test.dewy

- **D4, lines 12–13 and 24:** assertions over required lookups expose optional/error protocol noise; the reader must also know the memory backend has a keeper connection.
- **C4, lines 12–14 and 24–25:** asserting a fetched balance is much more verbose than a required-fetch assertion helper in any peer's tests.
- **S4, lines 28–38:** abandonment is explicitly tested as an intention, but the lifecycle implementation and D40 failure representation are not present. Correctly handling none no longer hides a missing required account.
- **K3, lines 10–14 and 28–38:** insufficient funds fails before any write, so it does not test rollback of a changed prefix. There is no late uniqueness/reference failure, poisoned commit, concurrent race or commit fault test. Memory tests alone cannot validate crash durability.

**Peers:** Python/Django, Go/sql, Diesel, Prisma and GRDB all support isolated test stores or test transactions with differing setup costs. Dewy's schema reuse and memory opening are good; the acceptance suite still omits the failures that distinguish this transaction contract.

### 09_interactive_cli.dewy

- **O4, lines 1 and 7–15:** “bounded interactive inspection” and 20 results can suggest bounded work, yet arbitrary title substring search may visit every row.
- **D4, lines 12–17:** the user must interpret explain output and a once-only warning to understand each new input's potentially unbounded scan.
- **S4, lines 12–15:** read-only typed access and treating input as data are strong; no `max_scanned` prevents an unexpectedly expensive input. This is a local resource issue, not injection.
- **K3, lines 7–17:** this is a useful narrow CLI, not the required general trusted developer REPL/resource-ownership workflow. It also omits the advertised runtime work bound.

**Peers:** Python/sqlite3, Django shells, Go/sql tools, Diesel tools, Prisma tooling and Swift/GRDB apps can all provide narrow parameterized inspection. Dewy's native predicates help, but this file does not demonstrate general REPL lifecycle or a bounded search.

### 10_csv_import.dewy

- **O4, lines 3 and 7–8:** the safe boundary is a substantial local parser rather than the expected standard CSV reader; readers must inspect its exact subset.
- **D3, lines 3 and 8; csv_products.dewy:56–68:** header, quoting and numeric acceptance are scattered between the local decoder and numeric library functions.
- **C2, lines 3 and 8; csv_products.dewy:6–73:** a 73-line handwritten parser dominates a 16-line database importer. Counting only the importer hides the real cost.
- **S4, lines 8–14:** validating before beginning tx and poisoning failed mutations are sound; the handwritten parser and its boundary cases have no executed tests. It materializes the entire input and product list before writing.
- **K3, lines 7–14; csv_products.dewy:59–65:** no streaming, row diagnostics, BOM/header flexibility, replay/resume or duplicate policy beyond whole-import failure. Those may be appropriate scope cuts but are material compared with existing CSV tooling.

**Peers:** Python's CSV library, Go encoding/csv, Rust's csv ecosystem, TypeScript CSV libraries plus Prisma, and Swift CSV tooling plus GRDB avoid hand-writing this scanner. Dewy's transaction wrapper is competitive; the complete import experience is not.

### 11_existing_sqlite.dewy

- **D4, lines 4 and 7–13:** users must learn named-column mapping, strict value decoding, constant-only statement text and a separate parameter shape. These are justified contracts but remain distinct concepts.
- **C4, lines 4 and 7–11:** row declaration, aliases and statement preparation repeat shape information for a small query; equivalent dynamic Python rows are shorter, though less checked.
- **K4, lines 7–13:** the safe typed-row contract is adequately specified, but this demonstrates only one read query. The proposed SQL transaction/execute surface, external schema drift/reprepare and hostile row-decoding cases are not exercised.

**Peers:** Python/sqlite3 is shorter but dynamic; Go/sql scans manually; Diesel usually requires schema/query setup or a typed raw-row mapping; Prisma offers typed/raw SQL paths; GRDB offers typed row decoding. Dewy's constants plus separately bound values and checked rows are a credible safe design. SQL syntax remains because this is intentionally the SQL path.

### 12_game_saves.dewy

- **O4, lines 14–20 and 28–30:** optimistic revision checking is application code, and a backup taken after a successful save is a different operation/snapshot.
- **D4, lines 15–18:** lifted optional member access, a zero-as-new-slot convention and stale revision rejection are subtle even though legal Dewy.
- **C4, lines 12–20:** nine lines implement a reusable optimistic save protocol, rather than a library compare-and-replace operation.
- **S4, lines 19–20 and 29:** stale overwrites are rejected; commit ambiguity and failure after durable save still need an application reconciliation story. A backup failure after the printed success must not be retried as a fresh gameplay mutation.
- **K3, lines 5 and 15–18:** revision 0 is safe under this program's no-deletion assumption. Slot delete/recreate, disconnected-save reconciliation, CommitUnknown recovery and restore are not supplied.

**Peers:** Python/Django, Go/sql, Diesel, Prisma and GRDB can implement compare-and-swap/version predicates; all still need an application conflict policy. Dewy's nested values and exact rationals help. The example is safer than blind upsert but not a complete save lifecycle.

### 13_paging_backup.dewy

- **O4, lines 9–17:** both view and continuation own a pinned snapshot, and cleanup/last-use reasoning determines when explicit close is legal.
- **D3, lines 10–19:** tuple sort typing, recipe identity, snapshot leases, token lifetime, fixed backup destination and read-only restore are substantial discovery costs.
- **C4, lines 11–17:** the page-draining loop repeats program 01, followed by explicit view close before a separate backup.
- **S4, lines 9–18:** stable snapshots are good, but retained WAL/storage and sort work are unbounded here, and backup publication/cleanup behavior needs engine/D40 evidence.
- **K2, line 10:** the unannotated compound sort returns an ordinary array where the existing sorter needs a typed tuple `(e):>[int string] => [e.recorded e.id]`. Local-only continuation tokens and a fixed non-overwriting backup name also limit reuse (lines 15 and 18). Snapshot correctness is otherwise substantially improved in round 2.

**Peers:** Python/sqlite3, Go/sql, Diesel and GRDB can hold a read transaction/continuation and use SQLite backup; Django/Prisma expose query pagination but cross-request stable snapshots require extra work. Dewy's automatic page lease is valuable in-process; it does not serve a stateless web continuation or eliminate lifecycle costs.

### 14_untranslated_predicate.dewy

- **O4, lines 8–14:** a function-typed callback may look like another indexed filter but actually runs locally, and a page may fail without returning any of its first 20 matches.
- **D3, lines 8–11:** purity/totality requirements propagate outside the printed callback type; explain, source diagnostics and the exact candidate counter must make this visible.
- **C4, lines 9–11:** the example needs explain plus a work cap to make the otherwise simple predicate operationally predictable.
- **S4, lines 9–14:** max_scanned prevents unlimited candidate evaluation, not arbitrary callback CPU, encoded bytes or all backend work. The balance-index path may still need key-order restoration.
- **K2, lines 9–11:** the first indexed lambda still depends on a language mechanism not designed here. The opaque-callback residual path is correctly specified in principle; it cannot demonstrate the indexed half of its claim today.

**Peers:** Python/sqlite3 and Go/sql require explicit postprocessing; Diesel and GRDB builders separate supported expressions from host callbacks; Django/Prisma similarly expose defined query operators. LINQ/EF also distinguishes executable delegates and translatable expressions. Dewy is more permissive, but a warning plus optional cap is not by itself a performance guarantee.

### csv_products.dewy (support file, counted separately)

- **O3, lines 10–49:** quote, post-quote and pending-CR state transitions are parser machinery far removed from the importer's purpose.
- **D3, lines 59–68:** exact header order, default numeric-parser grammar and the restricted CSV dialect require reading implementation rather than discovering a documented parser contract.
- **C2, lines 6–73:** handwritten lexical and typed validation code duplicates a mature CSV library role.
- **S4, lines 13–53 and 65–70:** byte-wise separator recognition and pre-write validation address real hazards. The paper scanner has no executed tests for quoting, CRLF, Unicode boundaries or numeric grammar; unbounded materialization is also explicit.
- **K3, lines 59–65:** no BOM/header reordering, record/column diagnostics, streaming or importer checkpoints. No concrete byte-state-machine defect was established in this review; missing validation evidence is not a claim that this parser accepts malformed quotes.

**Peers:** Python csv and Go encoding/csv already implement the lexical layer; Rust, TypeScript and Swift have mature CSV packages to combine with their database libraries. Dewy's typed conversion can still be valuable, but replacing a missing strict parser with application code should not receive full concision/completeness credit.

## Basis for peer comparisons

The comparisons use Python sqlite3 and Django ORM, Go database/sql, Rust Diesel, TypeScript Prisma and Swift GRDB. They compare contracts and source burden, not measured speed or proof that all peers are equally safe. Primary references consulted: [Python sqlite3](https://docs.python.org/3/library/sqlite3.html), [Django QuerySets and related loading](https://docs.djangoproject.com/en/5.2/ref/models/querysets/), [Django aggregation](https://docs.djangoproject.com/en/5.2/topics/db/aggregation/), [Go transactions](https://go.dev/doc/database/execute-transactions), [Diesel relations](https://diesel.rs/guides/relations.html), [Prisma filtering](https://docs.prisma.io/docs/orm/v7/prisma-client/queries/filtering-and-sorting), [GRDB](https://github.com/groue/GRDB.swift), and [EF client evaluation](https://learn.microsoft.com/en-us/ef/core/querying/client-eval). These document the referenced capabilities; the numerical grades and ergonomic judgments are this reviewer's inference.

## Independent floor

The floor is **2**: K for programs **01, 03, 04, 05, 13 and 14**; C for **10 and csv_products**. This is not an all-5 design. The code-inspection gap is real, but several lower scores arise from local API/program issues that do not require solving metaprogramming first.

## Differences from the author of two or more points

After fixing the scores above, I read `dogfood.md` and compared all 70 matched cells. **There are no differences of two or more points.** The author has no separate five-score row for `csv_products`; its cost is folded into program 10, so it has no independent numerical comparison.

The largest differences are all one point. The consequential downward differences are K3 → K2 for blog (03), concurrent inventory (05) and paging (13), reflecting the common relation-projection gap, wrong concurrency lane and tuple-sort defect. CSV concision is C3 → C2 because the support parser is part of the whole task. Discoverability is also one point lower on several multi-concept workflows. Ledger completeness is one point higher (K3 → K4): its written protocol is largely coherent, although recovery evidence remains absent. The SQL example's obviousness is one point higher because SQL vocabulary is expected in this explicitly SQL task, rather than a defect in the native database surface.

Agreement within one point does not vindicate the author's claim in round3.md:38 that all local corrections are complete: the scheduling and sort-key defects are concrete local corrections still available without a new language facility.
