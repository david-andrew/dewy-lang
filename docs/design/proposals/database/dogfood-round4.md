# Round-4 dogfood and regrade

**Full-corpus floor: 2 (CSV concision). Database-focused floor: 3.** No grade assumes callable inspection, comprehension interception or a future language feature. The new query objects are explicit library data; the ordinary local function path is explicit materialization.

This is a paper design/source assessment, not an engine run, benchmark, cold naming study or independent review. The independent round-3 review/regrade is preserved. I regraded the actual files in programs-r4/, not the nicer future-lambda column in round4.md. Criteria: **O** obvious, **D** discoverable, **C** concise, **S** safe by default, **K** complete for the stated task. 5 means no material deficiency found for that dimension in this bounded specimen; 4 a concrete cost or omission, 3 a substantial limitation, 2 a major burden, 1 unusable. Lack of an implementation is disclosed, not used as a universal reason to give every safety cell 4.

| Program | O | D | C | S | K |
|---|---:|---:|---:|---:|---:|
| 01_todo.dewy | 4 | 3 | 4 | 4 | 4 |
| 02_bank_ledger.dewy | 4 | 3 | 4 | 4 | 4 |
| 03_blog.dewy | 4 | 3 | 4 | 4 | 4 |
| 04_analytics.dewy | 4 | 3 | 4 | 4 | 4 |
| 05_inventory_tasks.dewy | 4 | 3 | 4 | 4 | 4 |
| 06_schema_change.dewy | 4 | 3 | 4 | 4 | 3 |
| 07_full_text.dewy | 4 | 4 | 5 | 4 | 3 |
| 08_memory_test.dewy | 5 | 4 | 5 | 4 | 4 |
| 09_interactive_cli.dewy | 4 | 4 | 5 | 4 | 3 |
| 10_csv_import.dewy | 4 | 3 | 2 | 4 | 3 |
| 11_existing_sqlite.dewy | 5 | 4 | 4 | 5 | 4 |
| 12_game_saves.dewy | 4 | 4 | 4 | 4 | 3 |
| 13_paging_backup.dewy | 4 | 3 | 4 | 4 | 3 |
| 14_untranslated_predicate.dewy | 4 | 4 | 4 | 4 | 4 |
| 15_optional_unique.dewy | 4 | 4 | 5 | 4 | 4 |
| csv_products.dewy | 3 | 3 | 2 | 4 | 3 |

Programs 01/03/04/05/13/14 no longer have the review's completeness-2 defects: descriptor planning is library-only; tuples have types; tasks use the waiting-group contract; the blog keeps source records. This does **not** make them all 5. Program 13 remains K3 for deliberate recovery/continuation limits. Program 10 and its support parser remain C2; excluding the helper from the denominator would be misleading.

## Line-level reasons, including every score below 5

All links point to the revised programs. A cited range identifies the concrete code that incurs the cost (or supplies the capability), not a claim of executed validation.

### 01_todo.dewy

- **O4**, [L5–7](programs-r4/01_todo.dewy): A second field-descriptor namespace must be learned alongside the record.
- **D3**, [L16–22](programs-r4/01_todo.dewy): Descriptor tuple ordering, persistent order, per-page budgets and continuation leases are several concepts for a small CLI.
- **C4**, [L18–23](programs-r4/01_todo.dewy): Manual page draining remains repetitive; no streaming iterator is supplied.
- **S4**, [L18–22](programs-r4/01_todo.dewy): Record visits are bounded per call, but neither large record bytes nor total drain duration is bounded here.
- **K4**, [L32–39](programs-r4/01_todo.dewy): Add, finish and prune work on paper; renaming/editing todos and a reusable page iterator remain application work.

### 02_bank_ledger.dewy

- **O4**, [L22–26](programs-r4/02_bank_ledger.dewy): Successful request replay uses optional get plus explicit rollback, unlike a fresh transfer.
- **D3**, [L21–38](programs-r4/02_bank_ledger.dewy): Serializable admission, durable request IDs, references and uncertain commit are necessary concepts that the small money operation cannot hide.
- **C4**, [L28–38](programs-r4/02_bank_ledger.dewy): Required lookups are fixed, but two balances, two references, two entries and the request record still require explicit assembly.
- **S4**, [L23–38](programs-r4/02_bank_ledger.dewy): Payload equality and balanced entries are strong; the caller still needs reconciliation when commit outcome is unknown.
- **K4**, [L40–49](programs-r4/02_bank_ledger.dewy): Two memory calls demonstrate replay intent, not restart reconciliation or a durable outbox workflow.

### 03_blog.dewy

- **O4**, [L17–23](programs-r4/03_blog.dewy): Source preservation is clear in the result, but record/related nesting adds vocabulary.
- **D3**, [L8–19](programs-r4/03_blog.dewy): The user learns Ref fields, schema descriptors, related selectors and include aliases together.
- **C4**, [L17–22](programs-r4/03_blog.dewy): The common feed is three recipe lines, yet related-field construction and nested output are longer than direct field navigation.
- **S4**, [L19–25](programs-r4/03_blog.dewy): One snapshot and a visit cap prevent inconsistent reads; extreme fanout still needs a byte policy, and printed strings need escaping in a real HTML renderer.
- **K4**, [L34–42](programs-r4/03_blog.dewy): Empty/multiple/shared tags and absent/present editor are covered. Explicit unlink/delete and relation cycles are not exercised.

### 04_analytics.dewy

- **O4**, [L9–13](programs-r4/04_analytics.dewy): Group keys and named values are separate nested records; count is an aggregate descriptor here, unlike an executing collection count.
- **D3**, [L5–11](programs-r4/04_analytics.dewy): Field factories, conjunction and summarize form a second expression vocabulary.
- **C4**, [L9–10](programs-r4/04_analytics.dewy): Direct count/sum removes retained-item comprehensions but still requires all_of plus aggregate constructors.
- **S4**, [L11–15](programs-r4/04_analytics.dewy): Visit limits do not bound many large exact sums or group allocation; no max_bytes is supplied in this offline report.
- **K4**, [L9–15](programs-r4/04_analytics.dewy): The concrete count/sum report is fully expressible without inspection; richer aggregate expressions and conditional aggregates require local code or later descriptors.

### 05_inventory_tasks.dewy

- **O4**, [L35–47](programs-r4/05_inventory_tasks.dewy): Scoped child failures are correctly forwarded but partial batch success is a policy the reader must notice.
- **D3**, [L3–45](programs-r4/05_inventory_tasks.dewy): The waiting-task library, scoped group, task-local error handling and database ownership rules all need discovery; D41 spelling remains provisional.
- **C4**, [L19–29](programs-r4/05_inventory_tasks.dewy): require removes lookup boilerplate; request replay and payload checking still dominate the two state changes.
- **S4**, [L18–47](programs-r4/05_inventory_tasks.dewy): Serial transactions prevent overselling, but cancellation can leave earlier sibling commits published; retries need the stable request ID.
- **K4**, [L34–49](programs-r4/05_inventory_tasks.dewy): The normal three-order race and unexpected-failure policy are specified; cancellation and admission-timeout races are not exercised by this specimen.

### 06_schema_change.dewy

- **O4**, [L11–17](programs-r4/06_schema_change.dewy): Explicit rename/remove and a rerunnable apply are understandable, but schema construction and applying a migration remain separate steps.
- **D3**, [L4–16](programs-r4/06_schema_change.dewy): Two types, two field records, two schemas and a migration history runner must all be learned.
- **C4**, [L4–14](programs-r4/06_schema_change.dewy): The duplicate transform is gone; preserving both schema versions still costs source.
- **S4**, [L12–20](programs-r4/06_schema_change.dewy): Destructive intent and backup are explicit; operators must arrange writer exclusion and enough rebuild storage.
- **K3**, [L20](programs-r4/06_schema_change.dewy): Key changes, collection rename/removal and arbitrary type conversions are deliberately unsupported in v1. This is a complete simple rename, not complete schema evolution.

### 07_full_text.dewy

- **O4**, [L7–18](programs-r4/07_full_text.dewy): search means literal token intersection, not substring, phrase or boolean query language.
- **D4**, [L7–19](programs-r4/07_full_text.dewy): The explicit tokenizer is better than language=en, but its version and rank direction still require documentation.
- **C5**, [L12–16](programs-r4/07_full_text.dewy): A query, bounded page and two output fields express the requested literal-search UI compactly.
- **S4**, [L13–16](programs-r4/07_full_text.dewy): The visit cap does not bound huge note buffers; plain text excerpts still need presentation-specific escaping.
- **K3**, [L18–19](programs-r4/07_full_text.dewy): No stemming, phrase search, language choice or portable relevance scoring; the new contract pins the available subset instead of claiming all search use cases.

### 08_memory_test.dewy

- **O5**, [L6–14](programs-r4/08_memory_test.dewy): Setup, transfer, and direct required-value assertions read as the intended test without optional-error scaffolding.
- **D4**, [L27–38](programs-r4/08_memory_test.dewy): Testing abandonment still requires understanding that a returned none is a result distinct from a storage error.
- **C5**, [L42–51](programs-r4/08_memory_test.dewy): The added late failure test states a changed prefix, duplicate failure, poisoned publication and unchanged live result in ten lines.
- **S4**, [L47–51](programs-r4/08_memory_test.dewy): The test handles the original write error and checks poisoned commit; assertions remain paper acceptance tests, and cleanup-error combinations are not modeled here.
- **K4**, [L42–51](programs-r4/08_memory_test.dewy): A changed-prefix rollback is now covered. Disk crash, commit ambiguity, cross-process races and cancellation still require a separate engine suite.

### 09_interactive_cli.dewy

- **O4**, [L7–20](programs-r4/09_interactive_cli.dewy): Output count and visit count are distinguished, but cooperative timeout and charged-byte scope remain less obvious than a simple search box.
- **D4**, [L12–19](programs-r4/09_interactive_cli.dewy): Users must interpret explain and the difference between a warned scan and budget failure.
- **C5**, [L12–17](programs-r4/09_interactive_cli.dewy): One descriptor and one match express filtering, diagnostics, capped execution and recovery without parsing user code.
- **S4**, [L14–20](programs-r4/09_interactive_cli.dewy): Requested budgets are meaningful; the deadline can overrun a storage call, and an adapter that cannot meter scratch may refuse this mode.
- **K3**, [L5–21](programs-r4/09_interactive_cli.dewy): This is a fragment-search CLI, not the broader trusted developer REPL and resource-owner interaction from the original use-case list.

### 10_csv_import.dewy

- **O4**, [L3–9](programs-r4/10_csv_import.dewy): The actual input contract is hidden behind a local parser import rather than a familiar standard reader.
- **D3**, [L8–9](programs-r4/10_csv_import.dewy): Exact header order, quoting, numeric rules and errors require opening csv_products.dewy:56–70.
- **C2**, [L3–9](programs-r4/10_csv_import.dewy): The 17-line importer depends on the unchanged 73-line handwritten parser, especially csv_products.dewy:6–73. Moving it into another file does not remove that burden.
- **S4**, [L8–15](programs-r4/10_csv_import.dewy): Validation precedes publication and tx is explicit, but both full text and products are materialized without a byte cap; parser tests have not run.
- **K3**, [L8–16](programs-r4/10_csv_import.dewy): No streaming, resume, row/column diagnostics or duplicate merge policy. A second import fails atomically on existing keys.

### 11_existing_sqlite.dewy

- **O5**, [L6–12](programs-r4/11_existing_sqlite.dewy): For an explicitly SQL task, prepare, bound artist and iteration say exactly what the code does.
- **D4**, [L4–13](programs-r4/11_existing_sqlite.dewy): Strict named-column/NULL decoding and constant-only query text are additional contracts to learn.
- **C4**, [L4–11](programs-r4/11_existing_sqlite.dewy): Row type and aliases repeat a small result shape; this is more explicit than dynamic Python rows.
- **S5**, [L6–14](programs-r4/11_existing_sqlite.dewy): Read-only connection, constant statement and separately bound input provide the intended safe default for this read example.
- **K4**, [L7–14](programs-r4/11_existing_sqlite.dewy): One read does not exercise execute, SQL transactions, hostile decoding or external schema-change reprepare.

### 12_game_saves.dewy

- **O4**, [L15–20](programs-r4/12_game_saves.dewy): A read/compare/write protocol is visible application code rather than one optimistic-update operation.
- **D4**, [L10–17](programs-r4/12_game_saves.dewy): Optional lifting and zero-as-new-slot convention need understanding; errors must not become an empty save.
- **C4**, [L13–21](programs-r4/12_game_saves.dewy): Nine lines still implement the routine optimistic save helper; this round consciously defers compare-and-replace.
- **S4**, [L29–35](programs-r4/12_game_saves.dewy): A backup error follows a successful save and must not trigger a fresh gameplay mutation; versioning assumes no delete/recreate.
- **K3**, [L34–35](programs-r4/12_game_saves.dewy): No delete/recreate-safe token, conflict merge or CommitUnknown reconciliation is provided; restore requires reacquiring keys under the documented new lineage.

### 13_paging_backup.dewy

- **O4**, [L13–21](programs-r4/13_paging_backup.dewy): The view and continuation retain a snapshot until draining finishes; this ownership is not obvious from ordinary arrays.
- **D3**, [L22–29](programs-r4/13_paging_backup.dewy): Read-only backup versus fresh-lineage writable restore and invalid old refs require explicit operational knowledge.
- **C4**, [L15–21](programs-r4/13_paging_backup.dewy): The repeated manual page loop and explicit view close remain boilerplate.
- **S4**, [L15–28](programs-r4/13_paging_backup.dewy): Visit limits and new-path restore are safe choices, but long-lived snapshots retain storage and fixed destinations deliberately fail on rerun.
- **K3**, [L22–30](programs-r4/13_paging_backup.dewy): Inspection and writable restore are now explicit; identity-preserving recovery, overwrite policy and stateless web cursors remain outside v1.

### 14_untranslated_predicate.dewy

- **O4**, [L10–16](programs-r4/14_untranslated_predicate.dewy): The materialization boundary makes local execution visible, but users must understand why an apparently similar predicate has a different placement.
- **D4**, [L10–14](programs-r4/14_untranslated_predicate.dewy): Indexed descriptors and ordinary function-valued code are two APIs; future inspection would reduce this distinction.
- **C4**, [L10–14](programs-r4/14_untranslated_predicate.dewy): Two filtering stages plus materialization are more ceremony than one ordinary compound predicate.
- **S4**, [L12–16](programs-r4/14_untranslated_predicate.dewy): The database work is capped; the supplied application function has no CPU bound and is deliberately trusted.
- **K4**, [L12–16](programs-r4/14_untranslated_predicate.dewy): Common indexed prefilter plus arbitrary local behavior works without new language features. It cannot lazily scan until twenty local matches or offer bounded arbitrary user code.

### 15_optional_unique.dewy

- **O4**, [L5–13](programs-r4/15_optional_unique.dewy): Ordinary none equality makes sense, but users from SQL may expect several missing emails under a unique constraint.
- **D4**, [L5–7](programs-r4/15_optional_unique.dewy): present_only is an extra option that must be found for a common optional-email schema.
- **C5**, [L16–22](programs-r4/15_optional_unique.dewy): Two absent inserts and two equal present values state the alternate policy compactly.
- **S4**, [L18–22](programs-r4/15_optional_unique.dewy): The constraint intent is explicit and typed, but no competing-writer or rollback failure is exercised.
- **K4**, [L9–22](programs-r4/15_optional_unique.dewy): Both optional modes have concrete assertions; cross-backend index/no-index equivalence still needs implementation tests.

### csv_products.dewy

- **O3**, [L10–49](programs-r4/csv_products.dewy): Three parser states and quote/CR transitions obscure the importing task.
- **D3**, [L56–68](programs-r4/csv_products.dewy): Header order and numeric acceptance require reading handwritten implementation, not just a parser signature.
- **C2**, [L6–73](programs-r4/csv_products.dewy): Seventy-three lines of CSV support duplicate a mature library role; this is the full-corpus floor.
- **S4**, [L13–53](programs-r4/csv_products.dewy): Byte-wise separators and UTF-8 field validation address known boundaries, but the state machine and numeric boundary cases have not been executed.
- **K3**, [L59–70](programs-r4/csv_products.dewy): No header reordering/BOM handling, streaming, row diagnostics or checkpointing; no concrete scanner defect is asserted by this grade.

## Peer comparison used for these grades

The five baselines are Python sqlite3 plus Django ORM, Go database/sql, Rust Diesel, TypeScript Prisma, and Swift GRDB. They are not presumed to have identical semantics or portability. Comparisons below are design judgments about source burden and scope, not measured performance or benchmark rankings. They explain why concise native syntax does not by itself justify a 5.

| Specimen/task | Python | Go | Rust | TypeScript | Swift |
|---|---|---|---|---|---|
| 01 todo | ORM queries are shorter than field factories | SQL plus row mapping is more explicit | Typed builder is a similar tradeoff | Model query objects are comparable | Typed requests are comparable |
| 02 ledger | Request replay remains application logic | Explicit Tx maps closely | Transaction closure shortens ownership | Transaction wrapper does not supply replay | Transaction closure does not supply replay |
| 03 blog | Related loading sets the ergonomic bar | Joined rows need reconstruction | Associations provide typed composition | Nested includes are a direct competitor | Associations preserve related structure |
| 04 analytics | ORM count/sum is concise | SQL grouping is concise | Typed aggregates are the comparison | Grouping vocabulary is comparable | SQL/request aggregates are the comparison |
| 05 inventory | Needs concurrent callers plus transactions | Goroutine/Tx split is familiar | Task/thread owns its transaction | Concurrent callers still contend for writer | Task plus transaction has similar separation |
| 06 migration | Mature tooling sets a higher completeness bar | Needs runner/library | Versioned migrations are the comparison | Migration workflow is the comparison | Versioned migrator is the comparison |
| 07 search | Backend-specific facilities remain relevant | SQL adapter work remains | Backend-specific facilities remain | Backend-dependent search scope | SQLite-focused search is a closer target |
| 08 tests | Test-store setup is similarly small | More error plumbing | Typed setup is comparable | Test-store setup is comparable | Memory/test database is comparable |
| 09 CLI | A shell ecosystem is broader | A narrow query tool is comparable | A narrow query tool is comparable | Developer tooling is broader | A narrow query tool is comparable |
| 10 CSV | Standard reader avoids handwritten scanner | CSV package avoids scanner | CSV ecosystem avoids scanner | CSV package needed alongside ORM | CSV package needed alongside DB |
| 11 SQL read | Dynamic rows are shorter, less checked | Manual Scan is explicit | Typed raw-row mapping is comparable | Typed/raw SQL path is comparable | Typed decoding is comparable |
| 12 save | Revision/conflict policy remains application work | Same business protocol | Same business protocol | Same business protocol | Same business protocol |
| 13 restore | SQLite APIs still need identity policy | SQLite driver still needs policy | Backend tooling still needs policy | ORM alone does not settle snapshot leases | SQLite backup does not settle fork identity |
| 14 opaque code | Explicit local postprocessing is familiar | Explicit local postprocessing is familiar | Host functions differ from query expressions | Host functions differ from query objects | Host functions differ from query expressions |
| 15 optional unique | Must distinguish backend NULL policy | Must distinguish backend NULL policy | Must distinguish backend NULL policy | Must distinguish backend NULL policy | Must distinguish backend NULL policy |

Primary reference anchors: [Python CSV](https://docs.python.org/3/library/csv.html), [Go encoding/csv](https://pkg.go.dev/encoding/csv) and [Rust csv](https://docs.rs/csv/latest/csv/) document reusable lexical layers absent from program 10; [Go transactions](https://go.dev/doc/database/execute-transactions) documents Tx/commit/rollback; [Diesel relations](https://diesel.rs/guides/relations.html), [Prisma relations](https://www.prisma.io/docs/orm/fundamentals/relations-and-joins) and [GRDB](https://github.com/groue/GRDB.swift) are the related-read/typed-storage comparison targets. [Django QuerySets](https://docs.djangoproject.com/en/5.2/ref/models/querysets/) supplies the Python ORM baseline. These sources establish comparison features, not numerical grades or proof of the proposed API's implementation.

## What remains below 5, and why it was not hidden

The first-release surface deliberately omits general migration transforms, OR/NOT descriptor combinators, arbitrary aggregate expressions, compare-and-replace, nested relations, direct query iteration and stateless web cursors. Several are routine later library extensions; none requires inventing a language mechanism. Adding every feature now would defeat the requested surface cut. Structural migration and ordinary post-materialization code make the supported paths complete, with explicit rejection outside them.

The CSV parser is retained and charged rather than replaced with a fictional standard CSV module. Improving that whole task needs a real reusable CSV library and its own validation; this database design round does not implement or approve one. Its floor therefore stays 2. The database-focused floor is 3 due to concrete discoverability and operational coverage costs listed above, not callable inspection. D40 lifecycle and D41 task-function spelling remain accurately labeled existing design-process dependencies; no new database-specific language construct is required.

Validation performed for this round: read the independent findings and local language/reflection/concurrency/sort sources; inspected all revised files; checked the old query-lambda/CPU-parallel/untyped-sort forms are absent from v1; checked relative imports and all cited line numbers exist; checked deliverables and preserved historical programs. No database tests were run because the library is a proposal. Cold naming and independent round-4 review remain outstanding; this document does not self-certify either.
