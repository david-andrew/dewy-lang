# Dogfood: final, line-cited grades

This is an author walkthrough of **14 realistic design programs**, with one local CSV support file. It is not an independent reader study, compiler run, benchmark, engine implementation, or proof of database safety. Every 1–5 score below cites a concrete final program line; 5s cite evidence too. The grades assess this proposed interface against the stated scenario, not a fictitious completed library.

**Rubric:** 5 = the paper scenario has no identified issue in that dimension; 4 = a real concept, ceremony, verification gap or restricted contract remains; 3 = substantial missing workflow/coverage; 2 = a core requirement depends on an undecided language facility; 1 = the design contradicts or cannot express the scenario. A safety 5 means the written API use has the intended safe contract, **not** that the implementation is proven. Completeness includes feasibility of the claimed ordinary-language interface; unimplemented but conventional storage work is distinguished from an undecided language mechanism.

The initial artifacts are preserved in `programs-r1/` and `round1.md`. Corrections are documented in [round2.md](round2.md) and [round3.md](round3.md). Current grades are deliberately not all 5. In particular, the comprehension/lambda blocker is not graded away as an implementation detail.

## Scores and the evidence behind them

### 01. Todo CLI

Acceptance: Add, complete, list every page, and bulk-prune completed todos.

| Dimension | Score and line | Evidence / remaining issue |
|---|---|---|
| Obvious | [5 — L13](programs/01_todo.dewy) | The verbs and explicit changed-row check explain normal CRUD without SQL. |
| Discoverable | [4 — L5](programs/01_todo.dewy) | Indexes are separate schema knowledge; completion cannot yet demonstrate that it teaches the right compound index. |
| Concise | [4 — L21](programs/01_todo.dewy) | Following pages costs an explicit loop; it bounds memory and is justified, but is longer than a typical ORM list for small data. |
| Safe by default | [4 — L36](programs/01_todo.dewy) | Deletion and failures are explicit, but the paper cannot yet substantiate atomic failure/cleanup behavior against an engine. |
| Complete | [2 — L19](programs/01_todo.dewy) | The desired efficient plain-lambda filter still needs an undecided general callable-inspection facility. |

### 02. Bank ledger

Acceptance: Preserve money, journal both legs, reject invalid transfers, deduplicate identical requests.

| Dimension | Score and line | Evidence / remaining issue |
|---|---|---|
| Obvious | [4 — L19](programs/02_bank_ledger.dewy) | Selective propagation plus optional matching is correct but requires knowing none is also an exception. |
| Discoverable | [4 — L18](programs/02_bank_ledger.dewy) | begin does not itself teach single-writer admission, uncertain commit recovery, or the need for request IDs. |
| Concise | [4 — L30](programs/02_bank_ledger.dewy) | Typed references and two journal entries require ceremony beyond a two-row transfer; removing it would weaken this ledger. |
| Safe by default | [4 — L35](programs/02_bank_ledger.dewy) | Explicit commit and idempotency protect the intended paths; D40 simultaneous rollback/cancellation failures remain unsettled. |
| Complete | [3 — L32](programs/02_bank_ledger.dewy) | Covers the stated transfer protocol, but durable ambiguous-commit reconciliation and the supporting lifecycle contract are not demonstrated. |

### 03. Blog and tags

Acceptance: Create posts with authors/tags, reverse-query both relationships, batch-follow tag references.

| Dimension | Score and line | Evidence / remaining issue |
|---|---|---|
| Obvious | [4 — L27](programs/03_blog.dewy) | follow of a set flattens edges and preserves cross-post duplicates; that cardinality must be learned. |
| Discoverable | [4 — L7](programs/03_blog.dewy) | Automatic reverse membership indexes remove work but their existence and cost are not evident from the field alone. |
| Concise | [5 — L25](programs/03_blog.dewy) | A normal set membership expression replaces an application-visible join collection. |
| Safe by default | [4 — L29](programs/03_blog.dewy) | Required lookup is explicit; reference integrity and rejection of cross-store/incarnation mismatches are still unimplemented contracts. |
| Complete | [3 — L6](programs/03_blog.dewy) | One-to-many and many-to-many are covered; ambiguous same-type targets and required cyclic construction remain unsupported. |

### 04. Grouped analytics

Acceptance: Filter by day, group by region, count orders and sum signed exact cents.

| Dimension | Score and line | Evidence / remaining issue |
|---|---|---|
| Obvious | [4 — L9](programs/04_analytics.dewy) | Group records and an aggregate map are composable, but the shape of key/items is a concept to discover. |
| Discoverable | [4 — L11](programs/04_analytics.dewy) | Readers cannot tell from this expression whether group arrays are eliminated or retained; explain/tooling is necessary. |
| Concise | [5 — L10](programs/04_analytics.dewy) | Count and sum now use ordinary array operations inside an ordinary record projection. |
| Safe by default | [4 — L4](programs/04_analytics.dewy) | Exact int prevents intentional overflow, but SQLite lowering must still prove it does not substitute int64/double SUM. |
| Complete | [2 — L11](programs/04_analytics.dewy) | Efficient lowering of a nested comprehension inside a grouped callback is not supplied by the existing language contract. |

### 05. Concurrent inventory

Acceptance: Concurrent requests never oversell; repeated IDs must carry identical payloads.

| Dimension | Score and line | Evidence / remaining issue |
|---|---|---|
| Obvious | [4 — L32](programs/05_inventory_tasks.dewy) | Straight parallel syntax is clear; it does not reveal that SQLite serializes the writer transactions. |
| Discoverable | [4 — L15](programs/05_inventory_tasks.dewy) | A finite timeout is visible, but correct response to contention versus CommitUnknown needs documentation and application policy. |
| Concise | [4 — L16](programs/05_inventory_tasks.dewy) | The deduplication check repeats the ledger pattern; it is necessary application protocol, not incidental library boilerplate. |
| Safe by default | [4 — L26](programs/05_inventory_tasks.dewy) | The algorithm is serializable under the proposed contract; cancellation and rollback-error outcomes await D40 and fault tests. |
| Complete | [3 — L29](programs/05_inventory_tasks.dewy) | The memory example does not establish multi-process admission, native-engine predicate validation or disk recovery. |

### 06. Schema evolution

Acceptance: Explicitly add an optional field, rename a field, remove one, and preserve data through a transform.

| Dimension | Score and line | Evidence / remaining issue |
|---|---|---|
| Obvious | [4 — L14](programs/06_schema_change.dewy) | The distinction between stable-identity rename metadata and value transformation needs teaching. |
| Discoverable | [4 — L13](programs/06_schema_change.dewy) | The plan is inspectable, but migration generation, deployment locking and stale-client diagnosis have no working tool yet. |
| Concise | [4 — L4](programs/06_schema_change.dewy) | Keeping old and new definitions plus a mapping is longer than automatic migration tools; that history is needed for deliberate changes. |
| Safe by default | [4 — L19](programs/06_schema_change.dewy) | Backup/no-auto-create/removal intent are explicit; atomic schema publication and combined cleanup failures are not implemented or fault-tested. |
| Complete | [3 — L19](programs/06_schema_change.dewy) | A writer-pausing migration is specified; online evolution and coordination with old binaries are not complete. |

### 07. Full-text notes

Acceptance: Literal-word search over indexed title/body, ranked hits with excerpts.

| Dimension | Score and line | Evidence / remaining issue |
|---|---|---|
| Obvious | [4 — L12](programs/07_full_text.dewy) | Literal input is safe, but all-words matching, tokenization and empty-input behavior are invisible in this short call. |
| Discoverable | [4 — L6](programs/07_full_text.dewy) | The language option is recognizable; exact stemming/tokenization and index rebuild behavior need docs and capability reporting. |
| Concise | [5 — L12](programs/07_full_text.dewy) | One search/page operation returns a typed hit rather than a backend query expression. |
| Safe by default | [4 — L12](programs/07_full_text.dewy) | No native SQL string is accepted, but literal-term escaping and tokenizer behavior still require adapter adversarial tests. |
| Complete | [3 — L14](programs/07_full_text.dewy) | Ranking is backend-specific; portable relevance and multilingual segmentation are deliberately not solved. |

### 08. In-memory tests

Acceptance: Check insufficient-funds rollback, repeated-request idempotency, and abandonment.

| Dimension | Score and line | Evidence / remaining issue |
|---|---|---|
| Obvious | [5 — L6](programs/08_memory_test.dewy) | Named tests and explicit before/after facts state exactly what is expected. |
| Discoverable | [4 — L7](programs/08_memory_test.dewy) | It is not apparent that this uses a keeper connection/shared adapter rather than a dictionary mock; that distinction matters. |
| Concise | [4 — L8](programs/08_memory_test.dewy) | Fixtures repeat setup; a test helper could shorten this but would hide the small examples' independent starting states. |
| Safe by default | [5 — L38](programs/08_memory_test.dewy) | Only absence passes the abandonment test; storage/cancellation errors are forwarded before the assertion. |
| Complete | [3 — L7](programs/08_memory_test.dewy) | Memory cannot validate power-loss durability, busy multi-process scheduling, or uncertain commits; these are acceptance specimens, not executed tests. |

### 09. Interactive query tool

Acceptance: Read title filters from stdin, show plans, execute bounded output without evaluating user source.

| Dimension | Score and line | Evidence / remaining issue |
|---|---|---|
| Obvious | [5 — L7](programs/09_interactive_cli.dewy) | The prompt states the filter behavior, exit command and output bound. |
| Discoverable | [4 — L14](programs/09_interactive_cli.dewy) | A novice still needs to interpret why a substring predicate is a scan; no working editor diagnostic was tested. |
| Concise | [5 — L12](programs/09_interactive_cli.dewy) | An ordinary closure captures the entered string without constructing a query language. |
| Safe by default | [4 — L15](programs/09_interactive_cli.dewy) | This limits returned rows, not scan cost; a trusted local CLI permits that cost but an untrusted server would need a scan/resource cap. |
| Complete | [3 — L9](programs/09_interactive_cli.dewy) | This is a bounded application prompt, not the complete typed database REPL; long-lived REPL resource ownership remains a separate gap. |

### 10. CSV ingestion

Acceptance: Reject malformed data before writes and atomically insert a validated batch.

| Dimension | Score and line | Evidence / remaining issue |
|---|---|---|
| Obvious | [4 — L8](programs/10_csv_import.dewy) | The local parser hides substantial validation policy; users must read its exact-header contract. |
| Discoverable | [3 — L8](programs/10_csv_import.dewy) | No standard strict typed CSV path currently fulfills this contract; readers must find the 73-line support specimen. |
| Concise | [3 — L8](programs/10_csv_import.dewy) | The short importer is not the whole cost: a schema-specific strict parser is included, not silently omitted. |
| Safe by default | [4 — L14](programs/10_csv_import.dewy) | Validation precedes writes and any duplicate aborts tx, but neither parser correctness nor atomic engine failure paths have been executed here. |
| Complete | [3 — L7](programs/10_csv_import.dewy) | Whole-file parsing needs memory proportional to input; resumable/streamed imports and rich row diagnostics are out of scope. |

The support cost is part of this program’s grade: [csv_products.dewy:13](programs/csv_products.dewy) scans bytes, [csv_products.dewy:49](programs/csv_products.dewy) rejects incomplete quoting, [csv_products.dewy:59](programs/csv_products.dewy) restricts header order, and [csv_products.dewy:65](programs/csv_products.dewy) parses numbers. The importer is not honestly a 16-line complete CSV solution.

### 11. Existing SQLite via SQL

Acceptance: Query a pre-existing Chinook file with checked row decoding and separately bound parameters.

| Dimension | Score and line | Evidence / remaining issue |
|---|---|---|
| Obvious | [4 — L8](programs/11_existing_sqlite.dewy) | SQL joins and aliases remain unavoidable vocabulary in the explicitly secondary interop path. |
| Discoverable | [4 — L7](programs/11_existing_sqlite.dewy) | A type argument alone does not tell readers that external shape/value validation is runtime, not proof of the live schema. |
| Concise | [4 — L4](programs/11_existing_sqlite.dewy) | The explicit record and long SQL statement duplicate column naming, unlike a generated ORM model. |
| Safe by default | [5 — L11](programs/11_existing_sqlite.dewy) | User data goes only into bound parameters and the handle is read-only; no interpolation or unchecked result cast is requested. |
| Complete | [4 — L7](programs/11_existing_sqlite.dewy) | The read scenario has a complete contract; a working adapter, statement diagnostics and D40 owner cleanup are still absent. |

### 12. Game save store

Acceptance: Persist nested values, reject stale edits, distinguish missing saves from corruption, then make a backup.

| Dimension | Score and line | Evidence / remaining issue |
|---|---|---|
| Obvious | [4 — L15](programs/12_game_saves.dewy) | The application revision/none convention is additional knowledge; it prevents a real stale-save bug. |
| Discoverable | [4 — L29](programs/12_game_saves.dewy) | A backup captures a separate later snapshot; save success does not imply backup success or an identical generation. |
| Concise | [4 — L14](programs/12_game_saves.dewy) | Optimistic revision checking takes several lines; the explicit application field avoids silently adding database fields to every record. |
| Safe by default | [4 — L19](programs/12_game_saves.dewy) | The modeled lost-update path is fixed, but crash recovery, backup durability and multi-error cleanup remain unverified. |
| Complete | [3 — L5](programs/12_game_saves.dewy) | Nested codecs and backups are specified; deletion/recreation ABA and complete crash-recovery evidence are not provided. |

### 13. Stable pages and backup

Acceptance: Read all pages from one view, release it, back up and read the backup.

| Dimension | Score and line | Evidence / remaining issue |
|---|---|---|
| Obvious | [4 — L9](programs/13_paging_backup.dewy) | Why the snapshot is pinned until explicit close, and why the backup is later, requires a lifetime explanation. |
| Discoverable | [4 — L15](programs/13_paging_backup.dewy) | The token remembers order, query and snapshot; none of its validation contract is apparent from the name alone. |
| Concise | [4 — L12](programs/13_paging_backup.dewy) | An explicit paging loop is longer than an unbounded all; it is useful control over memory and retention. |
| Safe by default | [4 — L17](programs/13_paging_backup.dewy) | Deterministic token leases and explicit close prevent drift by contract; ownership/cleanup integration still depends on D40. |
| Complete | [3 — L15](programs/13_paging_backup.dewy) | In-process paging is covered; a resumable continuation across process restarts and schema changes is explicitly unsupported. |

### 14. Opaque predicate fallback

Acceptance: Keep a pure callback, narrow through an index, bound residual work and report the plan.

| Dimension | Score and line | Evidence / remaining issue |
|---|---|---|
| Obvious | [4 — L9](programs/14_untranslated_predicate.dewy) | The same bool callback can become an indexed predicate or a local filter; the user cannot infer cost from spelling alone. |
| Discoverable | [4 — L11](programs/14_untranslated_predicate.dewy) | The name suggests a bound but not that lookahead/group stages count or that no partial page is returned. |
| Concise | [5 — L11](programs/14_untranslated_predicate.dewy) | One explicit limit contains fallback cost without requiring a second query DSL. |
| Safe by default | [4 — L8](programs/14_untranslated_predicate.dewy) | Purity/totality requirements must propagate through callable parameters; the current signature alone is not a proven effect contract. |
| Complete | [2 — L9](programs/14_untranslated_predicate.dewy) | Neither generic callable inspection nor all effect/iteration lowering needed here has a decided implementation contract. |

## Comparison with each requested peer

These are **qualitative comparisons of equivalent API tasks**, not numerical grades for translations that were never written or run. The per-program numerical grades above use those peers as the ergonomic baseline. Nothing here claims Dewy beats every peer. In particular, established migration tooling and SQLite integrations are more complete than this proposal. Python is considered twice: direct sqlite3 and a real ORM (Django). Go uses database/sql, Rust uses Diesel (SeaORM offers another entity/async approach), TypeScript uses Prisma, and Swift uses GRDB.

The comparison contracts come from primary documentation: [Python sqlite3](https://docs.python.org/3/library/sqlite3.html); Django [querying](https://docs.djangoproject.com/en/5.2/topics/db/queries/), [transactions](https://docs.djangoproject.com/en/5.2/topics/db/transactions/) and [migrations](https://docs.djangoproject.com/en/5.2/topics/migrations/); Go [queries](https://go.dev/doc/database/querying) and [transactions](https://go.dev/doc/database/execute-transactions); Diesel [setup](https://diesel.rs/guides/getting-started) and [relations](https://diesel.rs/guides/relations.html); Prisma [transactions](https://www.prisma.io/docs/orm/fundamentals/transactions) and [reading](https://www.prisma.io/docs/orm/fundamentals/reading-data); [GRDB’s own documentation](https://raw.githubusercontent.com/groue/GRDB.swift/master/README.md). These short judgments are my design assessment of the cited surfaces, not reported user-study results.

| Scenario | Python sqlite3 | Python Django | Go database/sql | Rust Diesel | TypeScript Prisma | Swift GRDB |
|---|---|---|---|---|---|---|
| Todo CLI | SQL+row mapping | Model/queryset CRUD | SQL+Scan boilerplate | Typed query/schema setup | Typed model queries | Record+query interface |
| Bank ledger | Manual request protocol | Atomic block; dedupe remains | Tx+explicit errors | Typed tx; protocol remains | Transaction callback; dedupe remains | Transaction; protocol remains |
| Blog and tags | Manual association SQL | Built-in relationships | Joins+manual mapping | Typed associations | Typed relation API | Associations+records |
| Grouped analytics | Direct GROUP BY SQL | Aggregate expression vocabulary | SQL+typed Scan | Typed aggregates | Aggregate/query surface | SQL/query expressions |
| Concurrent inventory | Connection/tx coordination | Backend transaction policy | Context+Tx boundary | Explicit connection/tx ownership | Transaction callback | Documented concurrency tools |
| Schema evolution | Manual migration scripts | Recorded migration tooling | External migration tooling | Migration setup | Contract migration workflow | Built-in migration support |
| Full-text notes | FTS5 SQL | Backend-specific search tooling | FTS5 SQL+Scan | Backend-specific extension | Backend-specific search support | FTS5 support |
| In-memory tests | SQLite memory database | Database test framework | SQLite driver needed | Real database fixtures | Database fixtures | SQLite memory database |
| Interactive query tool | Python prompt+SQL | Framework shell | Compile command tool | Compile command tool | Typed script/REPL tooling | Typed command tool |
| CSV ingestion | CSV module+executemany | CSV parse+bulk insert | CSV package+Tx | CSV crate+tx | Parser+transaction | Parser+transaction |
| Existing SQLite via SQL | Natural existing-file fit | Raw query path | Natural database/sql fit | Raw query decoding | SQL escape path | Natural SQLite fit |
| Game save store | Encode nested state | Models or encoded values | Codec+Tx | Serde/model decisions | Structured model/JSON choice | Codable record support |
| Stable pages and backup | Snapshot/backup APIs | Backend-aware paging | Explicit tx/continuation | Typed query+tx | continuation+transaction choices | Snapshot/backup tools |
| Opaque predicate fallback | Local filter is explicit | Materialize unsupported predicate | Loop after Scan | Typed DSL boundary | Supported query vocabulary | Query-interface expression boundary |

Dewy's proposed advantages are ordinary values, precise error unions, typed reference values, one schema described in Dewy, and explicit publication. Those advantages are not exclusive: typed query construction, relationships, migration histories, concurrency helpers and safe parameter binding already exist in several peers. The chief unresolved Dewy disadvantage is a mechanism that could deliver its promised native expression translation at all. LINQ explicitly has expression trees, and Pony explicitly has query translation; neither is evidence that an ordinary Dewy iterator can inspect a caller's comprehension.

## Iteration log: genuine fixes, not score inflation

| Finding in first specimens | Correction | Remaining floor |
|---|---|---|
| An unpaged todo list could silently omit later results | Program 01 now follows continuations until none | Explicit paging loop still has a concision cost |
| get(... ) or_throw could forward none into main/tests | Required paths explicitly convert absence to RecordMissing | Selective error/optional syntax still takes learning |
| PostTag repeated membership identity and exposed a join collection | Ordinary set<Ref<Tag>> field; composite-key record only for relationship payloads | follow cardinality and ambiguous targets still need clear teaching |
| A live-store next-page call could drift into a new snapshot | The continuation itself retains the view lease | Restartable external cursors are not provided |
| A stale game value was atomically overwriting newer state | Compare application revision inside tx, then publish revision+1 | Slot deletion/recreation needs incarnation policy if added |
| The CSV comment demanded validation the existing parser did not perform | Explicit local strict parser, with its code counted | Missing reusable strict typed CSV tooling is not hidden |
| g.items aggregates were not clearly ordinary array operations | Plain array length and sum(comprehension), with optimization conditional | General query/iteration mechanism remains undecided |
| CLI counted the executable name as a command | Strip args[0] using an explicit clamped slice | No remaining issue from that finding |
| Parallel error arm used an ordinary return | Forward with problem or_throw | Waiting-capable parallel and D40 implementation still required |
| Positional negative numbers could look like subtraction | Named negative-valued fields | No remaining issue from that finding |

## Floors and how they could actually rise

1. **Native expression completeness: 2 at the sharpest cases.** No documented general facility lets the library inspect an actual bool callable; ordinary eager comprehensions add a separate access problem. Needs a reviewed language mechanism/pilot, not another pretty query example. The exact filter requested by the brief is discussed explicitly in round1 rule 4.
2. **Cleanup/concurrency safety: mostly 4 in transactional scenarios.** Explicit commit and abandonment are accepted; D40 timing, multi-error representation, visible cleanup exits and cancellation grace are not all settled. Engine fault tests and a settled lifecycle contract can raise these grades. Suppressing that caveat would not.
3. **Discoverability: 3–4.** No cold readers used the names or editor completions. Descriptors, references, grouped shapes and tokens contain real concepts. A tested explanation/completion experience may justify 5; this author cannot award it in advance.
4. **Migration/search/remote-continuation completeness: 3.** Blocking rebuilds, backend ranking and in-process snapshot leases are deliberate initial limits. The appropriate next work is separate implementations/designs, not hiding those differences behind a universal 'database' promise.
5. **CSV concision/discoverability: 3.** The standard boundary is missing; the local parser demonstrates exactly the work a library must absorb. A robust strict typed CSV library could raise both, but changing an unrelated existing parser is outside this read-only design brief.
6. **Concision floors: mostly 4 where explicit protocol is necessary.** Idempotency, stable pagination and stale-edit detection are observable requirements, not decoration. A future reusable helper must preserve explicit publication and never replay external effects. Removing required lines solely to get a 5 would make the examples worse.

No unresolved local defect is knowingly labeled an unavoidable floor. The remaining gaps need a scope expansion (general language/runtime or library implementation), independent evidence, or a policy decision outside this scratch-only subtask. None of these scores makes the design ready for open_decisions.md: names were not cold-tested and the library-only expression requirement remains open.

## Validation performed

Read the requested language sections, all decision batches, cleanup round 5 and current D40/D41; searched the author's discussion notes before proposing names; read the reflection design; inspected the existing CSV boundary; consulted primary prior-art documentation; walked every specimen's success/failure/cleanup paths; checked artifact links, line references and naming inventory mechanically. No Dewy program was compiled or executed because the proposed database/SQL library and necessary language facilities do not exist. No repository files were written and no commits were made.
