# Independent review: Dewy-native database, rounds 1–3

**Verdict: revise before presenting this as a settled standard-library design. There are three must-fix findings.** The ordinary-value model, explicit publication, reference validation, migration intent and SQL binding contracts are promising. The author correctly reports that the brief's indexed ordinary-lambda/comprehension requirement has not been achieved. That honest blocker does not account for every remaining defect: the concurrency lane and tuple sort spellings have local corrections available now, and a common relation-shaped read remains needlessly awkward.

Scope: read `brief.md`, rounds 1–3, summary, names, all final programs including the CSV helper, batch 9 and D40, relevant LANGUAGE.md sections, the reflection design and existing compiler/sort regression sources. I fixed the independent scores in `regrade-round3.md` before reading the author's `dogfood.md`, then compared the 70 matched scores. This is a paper/API review, not a compiler run, engine audit, benchmark or cold naming study. No source files were changed.

## Must-fix findings

### M1 — The concurrent inventory uses the nonblocking CPU lane for database waits

**Severity:** must-fix. **Locations:** `programs/05_inventory_tasks.dewy:15,32–37`; `round1.md:179–181`; `docs/LANGUAGE.md:3521–3527`.

**Scenario:** two orders compete for the same SQLite writer. `reserve` begins an immediate serializable transaction with a two-second writer-admission timeout and performs storage operations. These operations may block. The caller invokes it from `parallel order in orders`, whose body must be proven nonblocking, including through calls. The example is invalid under the documented language contract. Fixing `problem or_throw` in round 2 did not fix this separate error. A finite timeout does not turn a blocking database call into CPU-only work.

**Suggested fix:** use the accepted waiting-task lane, with a task-local transaction per request and one shared store handle. Forward/handle the task-group result as well as each reservation result. Keep expected OutOfStock handling inside the task; demonstrate that an unexpected failure cancels and joins siblings without undoing another sibling's already published reservation. Do not weaken database `blocks` summaries to make the current loop pass. No new database API or metaprogramming mechanism is needed for this correction.

**Acceptance:** the rewritten specimen conforms to the waiting-task syntax and ownership/effect rules; each request can wait for admission; no tx crosses tasks; two available units yield at most two committed reservations. The other task-group failure outcomes must be explicit rather than described as an all-or-nothing batch.

### M2 — Compound sort callbacks return arrays where ordinary sorting requires tuples

**Severity:** must-fix. **Locations:** `programs/01_todo.dewy:20`; `programs/13_paging_backup.dewy:10`; related compound descriptors at `01:7`, `04:6`, `13:6`; `round3.md:30`.

**Scenario:** execute the proposed reference evaluator on an ordinary array. `key=(t) => [t.priority t.id]` and `key=(e) => [e.recorded e.id]` have no explicit tuple result context. The existing sorter diagnoses an array key rather than comparing it lexicographically. This is already covered by `tests/cases/sort/array_key_hint.dewy:4` and its `.err`; `tests/cases/sort/tuple_key.dewy:4` shows the valid typed form. The compiler's array-comparison diagnostic in `compiler/expr.jo:5704–5713` gives that same remedy. Providing a special comparator only on a database query would violate the proposal's own ordinary-expression equivalence requirement.

**Suggested fix:** use `key=(t):>[int string] => [t.priority t.id]` and `key=(e):>[int string] => [e.recorded e.id]`. Likewise state/annotate the tuple result of compound key/index selectors, rather than assuming an unconstrained array literal means a tuple. Existing tuple sorting supplies the ordinary capability; this is not a reason to design new array comparison semantics. Keep the descriptor's codec comparator separate and require proven agreement with the ordinary tuple comparator, including reverse ordering and stable ties.

**Acceptance:** all compound selectors have an unambiguous typed representation; the same sort expression is legal on an ordinary collection; adding/removing the index yields the identical ordered result. The paper can cite existing fixtures without claiming the proposed database programs were compiled.

### M3 — Common combined relation reads lack an ergonomic native composition

**Severity:** must-fix for the common-case design, not a claim that the sample's existing output is wrong. **Locations:** `round1.md:74,134,161`; `round2.md:19`; `programs/03_blog.dewy:23–30`.

**Scenario:** render a blog feed of `{post title, author name, tag labels}`, or select posts whose author's email matches a filter. A loaded Post contains a Ref, not a loaded author. Query callbacks cannot perform `get` I/O. `follow(author)` yields authors, dropping posts; `follow(tags)` flattens all tag edges, dropping per-post group boundaries. The specimen avoids this by printing posts, repeated tags, and one already-known writer separately. That is less than the normal blog page.

A legal fallback exists for a scalar relation: materialize posts and the same recipe's ordered scalar follow under one explicit snapshot, then pair them positionally using ordinary combined iteration. This is better than N+1 reads, but it makes the caller reconstruct a join, and does not directly recover set-relation grouping. Loading all related collections into dictionaries or issuing one get per post is also possible and also loses the intended ergonomic advantage. I am not claiming the model cannot represent the data.

**Suggested fix:** design and dogfood a source-preserving, batched relation projection/composition contract, returning ordinary nested records/arrays and preserving one snapshot. Reuse ordinary collection composition where possible. Show the feed above, filtering by a related field, an absent optional link and an empty/multi-tag set. Specify multiplicity, ordering, cardinality and query count. Any new member spelling is provisional and needs the project's naming/approval process; this review does not choose one. At minimum, publish the existing two-query scalar workaround and grade its ceremony instead of treating the current three separate printouts as coverage of relation reads.

**Acceptance:** the common feed/read shape is expressible concisely without callback I/O, application-visible association rows, manual positional joins or hidden N+1 fetching. Django already offers related loading, Prisma offers related reads, and Diesel/GRDB offer associations/joins; these are real comparison targets, not optional advanced SQL features. See [Django related loading](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-related), [Prisma reading](https://www.prisma.io/docs/orm/fundamentals/reading-data), [Diesel relations](https://diesel.rs/guides/relations.html) and [GRDB associations](https://raw.githubusercontent.com/groue/GRDB.swift/master/README.md#associations).

## Should-fix findings

### S1 — Define which recipes can mutate and how repeated origins behave

**Severity:** should-fix. **Locations:** `round1.md:134–136,175–177`; `round2.md:19,29,70,92`.

**Scenario:** two posts share a tag. Their followed query contains the same Tag twice. Does `.update((tag) => ...)` update that stored tag once, twice, or fail? What does update/delete mean after `.map` drops the key, after grouping, or after following an optional link? Hidden origin metadata for pagination does not settle mutation target semantics. Current examples only mutate an identity-preserving filtered collection, but the public query-operation table does not restrict receivers.

**Suggested fix:** initially expose mutation only on clearly defined entity selections retaining the original collection identity; reject projections/groups and unsupported follow shapes statically. If followed entity queries may mutate, specify identity deduplication, callback invocation count, snapshot selection and changed-row counts. Preserve the existing fixed-candidate/Halloween protection and whole-operation constraint checks. Add one duplicate-target example before broadening the surface.

### S2 — A scan warning and a page size are not a general work bound

**Severity:** should-fix. **Locations:** `round1.md:161–169`; `round2.md:31`; `programs/09_interactive_cli.dewy:1,12–17`; `14_untranslated_predicate.dewy:11–14`.

**Scenario:** a title fragment matches no rows in a very large store. The interactive CLI's first 20 results require a whole scan despite its “bounded” header; a once-only warning is easy to miss on later inputs. Separately, 1,000 candidates can contain enormous blobs or an expensive terminating pure callback, or require backend sorting/decoding. `max_scanned` does not bound CPU, bytes or I/O in general.

**Suggested fix:** retain the default warned fallback required by David's brief, but distinguish output, candidate-count, byte/memory and execution limits. Add the existing `max_scanned` to any example advertised as work-bounded, and describe honest failure handling. Define the counter precisely for indexes, repeated follow edges, sort/group input, local stages and lookahead; say whether the same record seen at two stages counts once or twice. Explain/resource contracts must account for work outside that counter. Provide a way to require a budget for server endpoints without inventing a global language “must use index” tag.

The warning is useful for local trusted code; it is not enough to support a bounded-service claim. This is a known practical hazard: [EF Core documents](https://learn.microsoft.com/en-us/ef/core/querying/client-eval) that its older warning-based filter fallback could hide large client evaluations, while its current policy rejects unsupported non-projection evaluation. That is a comparison, not a demand that Dewy adopt EF's rejection policy.

### S3 — Spell out unique constraints on optional values

**Severity:** should-fix. **Locations:** `round1.md:120,130`; `round3.md:32`; `names.txt` unique/index usages.

**Scenario:** an optional email field defaults to none, with a unique email descriptor. Can two newly created users both have no email? Ordinary `none =? none` is true, whereas copying a backend's SQL UNIQUE/NULL behavior may admit both. The proposal promises ordinary equality but never explicitly states the unique-optional case or shows how to request “unique among present values.”

**Suggested fix:** state the behavior and test it; ensure index eligibility never changes it. If uniqueness literally follows ordinary equality, only one none is allowed, and the useful present-only variant needs an explicit, typed contract (possibly a constrained/partial descriptor) rather than an undocumented backend exception. Diagnose unsupported variants. Do not silently inherit SQL NULL semantics.

### S4 — Migration workflows need a runner and a reference-identity story

**Severity:** should-fix. **Locations:** `round1.md:120,200–206`; `round2.md:99–100`; `programs/06_schema_change.dewy:6–20`.

**Scenario:** rerun deployment after migration succeeded but the process died before the new open: the old-schema open now rejects it. Retry after backup succeeded but migration failed: the fixed backup path refuses overwrite. More structurally, change a key or target record type while nested Ref<T> values still point at that collection. Whole-prospective-state validation is necessary but does not say how reference incarnations, target IDs and transformed reference types map. Collection rename/removal is also not specified by the field-level `.contacts.rename/remove` surface.

**Suggested fix:** separate migration-plan construction from a version-aware apply runner that recognizes already-applied identical history, chooses collision-safe backup destinations and clearly reports resume/recovery states. Preserve explicit destructive intent. Specify whether key/target changes rewrite references atomically, retain identity, deliberately create new incarnations, or are rejected in v1. A refusal is a legitimate initial contract; do not leave it to adapter interpretation. Do not claim online migration is needed to fix these basic one-shot deployment cases.

### S5 — Backup identity needs a clear writable-fork boundary

**Severity:** should-fix. **Locations:** `round1.md:116,173,206,212`; `programs/13_paging_backup.dewy:18–20`.

**Scenario:** a backup preserves logical database identity and reference incarnations, as required for restore. Open both the original and the copied backup as writable stores and let them diverge. A reference minted before the backup can now resolve in both files to different record versions; it passes persistent identity checks although the files no longer form one coordinated store. The read-only backup example avoids this, but the general open contract does not explain the boundary.

**Suggested fix:** distinguish reference identity of a database lineage from identity/coordination of an active store instance. Specify supported restore/takeover and explicit fork behavior, including reference remapping and continuation invalidation, and what happens when a backup is opened writable. If v1 supports backup inspection and exclusive recovery only, state that restriction and the enforcement/assumptions. This does not require a distributed engine; it requires an honest rule for copied local files. Preserving reference identity for recovery is reasonable and is not itself the bug.

### S6 — Required fetch and routine optimistic updates are overly verbose

**Severity:** should-fix. **Locations:** `programs/02_bank_ledger.dewy:25–31`; `03_blog.dewy:29`; `05_inventory_tasks.dewy:22`; `08_memory_test.dewy:12–13`; `12_game_saves.dewy:12–20`.

**Scenario:** ordinary required lookup repeatedly spells `or_throw<error | Canceled> ??<none> return database.RecordMissing`; a disconnected save implements its own read/revision-check/upsert protocol. These are frequent operations, not exotic ledger requirements. The rejection of a second required-fetch spelling in round2.md:48 is premature when the current form degrades both application and test clarity.

**Suggested fix:** demonstrate an ordinary reusable helper for required lookup and a typed atomic compare-and-replace/version operation or helper, then compare the entire calling program against peers. Keep optional `get` semantics, explicit conflict handling and ordinary domain fields. Any public names need cold testing; the helper can remain application code during the next design round. Do not remove necessary journal/idempotency logic just to reduce line count.

### S7 — Search capability and ranking need a reproducible adapter contract

**Severity:** should-fix. **Locations:** `round1.md:243`; `programs/07_full_text.dewy:6,12–17`; `names.txt:language,score` usages.

**Scenario:** `language='en'` could mean Unicode token splitting, English stemming, stop words or a combination. Two adapters return different matches or ordering. SQLite FTS5 provides distinct tokenizer choices rather than one universal language selector. The proposal allows backend-specific ranking but needs a specific match/tokenizer contract for a given persisted schema.

**Suggested fix:** pin tokenizer/version/options and state the English mapping, stop-word/accent/stemming behavior, score direction, tie ordering and unsupported-feature behavior. Native literal-term escaping remains mandatory. No phrase/boolean mini-language is needed to settle these initial rules. See [SQLite's FTS5 tokenizer documentation](https://www.sqlite.org/fts5.html#tokenizers).

## Checks that passed, and important notes

### N1 — Indexes do not change valid-store query results under the final rules

**Severity:** note. **Locations:** `round1.md:130,136–138,165,245`; `round2.md:70–76`; `round3.md:22–32`.

The final text requires primary-key source order, stable sorts, source-position-preserving scalar/optional follow, explicitly flattened set follow with multiplicity, ordinary equality/hashing for groups, exact int arithmetic and explicit optional handling. Moving a predicate or aggregate must preserve failure behavior as well as values. Residual filtering precedes paging. Snapshot-bound continuation fixes live-data drift. A balance index may still need a key reorder; grouping can retain O(N) records. Those are sound obligations, subject to fixing M2 and implementing conformance tests.

No contradictory valid-data index-selection rule was established. Latent corrupt bytes outside a selected candidate set may be encountered by one plan but not another; round2.md:76 explicitly limits the equality-of-results promise to a valid logical store. That is a defensible distinction, provided every yielded value is validated and corruption is never converted into none. Float sort must use the documented IEEE totalOrder (LANGUAGE.md:1039–1055); grouping equality and sorting are different contracts. Round 3 forbids inventing SQL NULL/approximate-number behavior to close a codec gap.

### N2 — Transaction publication, replay and task sharing are mostly sound contracts

**Severity:** note. **Locations:** `round1.md:173–196`; `round2.md:70,78`; `programs/02_bank_ledger.dewy:16–35`; `05_inventory_tasks.dewy:13–26`.

The assigned `$__abandon__ = () => ...` hook matches batch 9. Rollback never publishes, `commit()` is explicit and consuming, failed mutations poison tx, and references/unique constraints are maintained transactionally. Request IDs include full payload comparison. Retrying an identical request through the serializable request-record check can reconcile an ambiguous response without duplicating the local mutation; it must not blindly repeat an external effect. Known no-publication, durable success and CommitUnknown remain distinct outcomes. The author correctly avoids automatic callback retries and uses separate transactions per task.

SQLite immediate writer admission before reads is a credible serializable strategy; it trades concurrency for clarity. See [SQLite isolation](https://www.sqlite.org/isolation.html) and [transaction modes](https://www.sqlite.org/lang_transaction.html). Pending D40 timing/multi-error/cleanup exits remain explicit dependencies, not contradictions to be silently resolved here. A successful sibling's commit survives another sibling's task-group failure; callers must reconcile every request rather than retry the whole group with new IDs. Add a late-write-failure test: program 08's insufficient-funds check runs before any write and therefore does not test rollback of a changed prefix.

### N3 — Migration intent avoids silent field-loss; transforms still need review

**Severity:** note. **Locations:** `round1.md:200–206`; `round2.md:48,107`; `programs/06_schema_change.dewy:10–19`.

Open does not infer migrations or initialize a mismatched store. Rename is explicit, preserves stable field IDs, and is distinct from remove-plus-add; field removal requires a separate declaration. A transform omitting an old field still needs rename/removal intent. These rules prevent silent loss from a source rename or dropped field. An explicitly approved transform can intentionally produce lossy values; no type system proves business correctness, and a backup is still necessary. S4 concerns missing workflows/identity mappings rather than an established automatic-field-deletion bug. The backup is a separate consistent snapshot, not atomic with the migration/save; [SQLite's backup API](https://www.sqlite.org/backup.html) is the right backend foundation.

### N4 — SQL data injection is prevented by construction at the stated interface

**Severity:** note. **Locations:** `round1.md:264–268`; `programs/11_existing_sqlite.dewy:4–14`.

Constant one-statement SQL plus a separate checked parameter record keeps runtime values out of statement structure; checked structured identifiers/whitelists remain a separate future builder. Prepared values use the backend bind API, not escaping/concatenation. The input artist name cannot introduce SQL syntax. Typed rows are not unchecked assertions: names/shape are checked and each value must pass nullability, range, text and refinement validation. Preparation alone cannot establish an arbitrary external file's value types. These are credible contracts; parameter/statement shape and decode failures must stay visible. See [SQLite binding parameters](https://www.sqlite.org/c3ref/bind_blob.html).

This prevents injection of data in this path, not intentionally destructive constant program source or someone opening native files with an unrelated external tool. The native store's API does not expose writable raw connections, which is the appropriate library boundary. No injection hole was established in the shown code.

## Is the common experience better than SQL plus an ORM?

**Not established yet.** Ordinary values, exact numbers, no dirty tracking, explicit fallible execution and typed references improve local reasoning. Several mature peers already provide typed composition, safe parameters, associations and migration tools, so avoiding SQL vocabulary alone does not establish superiority.

| Common task | Advantage of the proposed native design | Remaining disadvantage |
|---|---|---|
| Todo | Record plus declarative collection; simple predicate/update | continuation draining and explicit schema/index knowledge; current tuple-sort defect; efficient lambdas unresolved |
| Ledger | Exact int, rollback by default, explicit commit, checked request replay | Required-fetch/reference ceremony; cleanup/ambiguous response recovery still needs a worked durable example |
| Blog/tags | Ordinary stored set and automatic reverse membership indexing | Follow drops source/grouping; combined feeds and related-field filters need manual composition or more design |
| Analytics | Ordinary grouping/projection and exact arithmetic | Group arrays plus inner comprehension are more verbose than direct aggregate operators and may retain all rows |

Against Django and ActiveRecord, CRUD and aggregation are not shorter enough to offset the added continuation/reference/strict-lookup vocabulary. Against LINQ, Dewy's lambda spelling is familiar, but its expression/delegate translation boundary is still undecided. Against Prisma, it removes a separate domain schema only if the descriptor/codec/migration machinery really stays ordinary and discoverable; it has not matched the related-read workflow yet. These are ergonomic judgments from the specimens. [Django aggregation](https://docs.djangoproject.com/en/5.2/topics/db/aggregation/), [ActiveRecord's query interface](https://guides.rubyonrails.org/active_record_querying.html), [Prisma filtering](https://docs.prisma.io/docs/orm/v7/prisma-client/queries/filtering-and-sorting) and [EF's translation boundary](https://learn.microsoft.com/en-us/ef/core/querying/client-eval) supply the comparison contracts.

### Concept count for a first useful program

For someone already able to read Dewy records, lambdas, paths and errors, the round-1 create/insert/read/filter examples introduce **eight database concepts** under this explicit counting scheme:

1. A collection descriptor inside a constant schema record.
2. A mandatory key selector, separate from the ordinary record definition.
3. Opening a resource handle with shared external identity.
4. Insert returning a Ref rather than the inserted record.
5. Optional lookup versus storage failure and required lookup.
6. A composable deferred recipe rather than an array.
7. A terminal operation that executes and can fail.
8. Declaring a persistent index separately from using a query.

The actual todo specimen adds a ninth: snapshot-owning continuation pages. A transactional blog adds publication/abandonment, reference integrity and follow cardinality. Existing Dewy knowledge is reused effectively, but this is not concept-free storage and not demonstrably simpler to learn than a small ORM. Descriptor field projections and an ordinary page iterator/helper could reduce the first path's burden.

## Callable inspection: diagnosis and a smaller alternative

The narrow diagnosis is correct. A library receiving `(a:Account) => a.balance <? threshold` as an ordinary executable function cannot recover the comparison, field identity or arbitrary branches from its type or captures. `fields(T)` and `$field(name)` describe fields, not a function body; compile-time execution computes outputs for known inputs, not a symbolic program for all rows. Existing LANGUAGE.md:5043–5070 additionally rejects indirect/capturing comptime calls. Lifting that evaluator restriction helps descriptor construction but does not create code inspection. Executing callbacks on sampled fake Account values is not a sound way to infer a query. Comparisons must return bool, so overloading `<?` on a proxy does not create a predicate AST while preserving the accepted bool/control-flow contract.

The eager comprehension is a second issue: its filter/projection belong to the caller. A library iterator cannot inspect that caller merely because it can yield Account values. Efficiently pushing the filter into an index therefore needs some general compiler-visible staging/iteration optimization contract. Callable inspection alone does not do it. Read-only typed expression representation is one possible language design; it has not been proved the smallest or only suitable design, and must not be treated as approved by David's database direction. `docs/design/argparse_and_reflection.md:98–108` deliberately excludes AST/source-generation macros; a typed inspection interface needs a separate explicit decision even if it generates plan values rather than source.

**A smaller library contract can cover the common indexed cases without arbitrary callable inspection.** Reflection can build a record of typed field references for Account. A field reference can construct a typed comparison node by an ordinary method, and typed nodes can compose conjunction/disjunction, ordering, membership, projection and aggregate descriptors. The library owns both the data plan and its executable evaluation. Key/index/migration selectors can take these explicit field descriptors too. For example, in descriptive pseudocode only, `account_fields.balance.less_than(0)` constructs a predicate value accepted by an overload of `where`. No public name is approved by that illustration. A field node is not a fake Account, and no user callback needs to execute to discover its body.

Two qualifications matter. First, `account_fields.balance <? 0` still cannot yield a predicate object under today's bool-returning comparison protocol; preserving that exact spelling would need a language change. Second, this is a different contract from the brief's exact ordinary Account lambda/comprehension, and still depends on the existing generic/reflection construction infrastructure and its current implementation limits. It must be presented as a scoped alternative, not as completion of the brief. Opaque ordinary pure callbacks can remain an explicitly explained residual path. Most simple todo/ledger/blog predicates do not need arbitrary callable inspection in such an API; cross-relation composition still needs M3.

**Recommended next technical experiment:** a small non-database pilot comparing (a) a typed explicit-field predicate library with (b) the smallest general typed callable/iteration representation able to support one captured comparison. Define acceptance before building: exact int/optional semantics; literal and captured thresholds; ordinary fallback; tuple order; honest diagnostics; bounded compiler specialization. Do not launch a broad “inspect every callable” language project merely because it was described as the only prerequisite. David should choose the desired expression contract with the smaller alternative visible.

## Names and presentation

`names.txt` is an inventory with usage context, not the required shuffled names-only cold test. No name should be advertised as cold-tested or put into a naming decision on the strength of this review. I did not spawn readers or coin an approved API.

- `where` versus the existing array `filter` imposes receiver-specific vocabulary; decide whether the difference earns its discoverability cost.
- `follow` is the strongest misleading candidate: it changes shape, flattens sets and preserves cross-parent duplicates. Readers may expect source-preserving traversal or a set of distinct targets. Test scalar/set/optional expectations, not just recognition of the English verb.
- `max_scanned` can be read as a cap on all work or all examined rows. Settle the exact counter and teach its limits (S2).
- `language='en'` can overpromise stemming and linguistic behavior (S7); `.score` needs a stated direction, since backend ranks are not universally “higher is better.”
- `reference(key)` is checked existence lookup, not an unchecked identity constructor, a borrow or authorization. `put` is intentional upsert. These can be reasonable names, but documentation/independent tests must establish that reading.
- Do not infer a naming failure from unfamiliarity alone. CommitUnknown, CursorMismatch and RecordMissing communicate useful distinctions; no evidence here justifies replacing them with new spellings.

Round3.md:38 should stop claiming all local corrections are complete. The two straightforward language mismatches in M1/M2 and the common-read omission in M3 can be addressed on paper before engine implementation. The independent grading floor is **2**: completeness for **01, 03, 04, 05, 13, 14**, and concision for **10 and csv_products**. No matched grade differs from the author's by two or more points; the severity of a concrete defect does not depend on a large numerical disagreement.
