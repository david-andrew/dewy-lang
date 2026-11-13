# Native database, round 4 — a complete library-only first version

These five minimal examples show the proposed v1. They are design specimens, not claims that a database library exists today. New library names remain provisional. This round supersedes conflicting contracts in rounds 1–3; the earlier files remain historical.

**1. Define and open typed storage.**

```dewy
import p"@lib/std/database.dewy" as database
Account:type = [id:string balance:int]
const A = database.fields_of<Account>
const accounts = [accounts=database.collection<Account>(key=A.id
    indexes=[database.index(A.balance)])]
open_accounts = () => {
    return database.open(accounts p"accounts.db") or_throw
}
```

**2. Insert and load; distinguish optional from required lookup.** Uses the declarations above. Insert returns a validated reference; required lookup reports absence as `RecordMissing`.

```dewy
insert_and_load = () => {
    let store = database.memory(accounts) or_throw
    store.accounts.insert(Account["ada" 100]) or_throw;
    return store.accounts.require("ada") or_throw
}
```

**3. An indexed query with no lambda inspection.** The selector owns a record type and a field type. `lt` builds a predicate value, not a bool pretending to be a query.

```dewy
overdrawn = <S>(store:S) => {
    return store.accounts.where(A.balance.lt(0)).page(size=20 max_scanned=1000) or_throw
}
```

**4. A post and its related author in the same row.** Every returned row is an ordinary record with `record:Post` and `related:[author:Author]`.

```dewy
Author:type = [id:string name:string email:string]
Post:type = [id:string title:string author:database.Ref<Author>]
const W = database.fields_of<Author>
const P = database.fields_of<Post>
const blog = [authors=database.collection<Author>(key=W.id)
              posts=database.collection<Post>(key=P.id)]
read_feed = () => {
    let store = database.open(blog p"minimal-blog.db") or_throw
    return store.posts.include([author=P.author]).page(size=20) or_throw
}
```

**5. Explicit commit; every other exit abandons unpublished work.** This short example shows the transaction boundary; program 02 adds request validation, replay protection and balanced ledger entries.

```dewy
move_one = <S>(store:S) => {
    let tx = store.begin(timeout=2s) or_throw
    let a = tx.accounts.require("ada") or_throw
    let b = tx.accounts.require("bea") or_throw
    tx.accounts.replace([a... balance=a.balance-1]) or_throw
    tx.accounts.replace([b... balance=b.balance+1]) or_throw
    tx.commit() or_throw
}
```

## 1. Decision and scope

Ship typed descriptors first. Ordinary records, generic functions, reflection over record fields, record construction, type checking and ordinary runtime plan values suffice. **No v1 query, index, aggregate, relation or migration depends on inspecting a function body, intercepting caller control flow, executing arbitrary code at comptime, compiler plugins or new syntax.** Deferred lambda translation is optional sugar/expressiveness, not a prerequisite for v1 correctness or the grades below.

The original brief wanted exact lambdas and eager comprehensions. The new instruction explicitly permits a descriptor v1; this round does not pretend that the original spellings were implemented. Method-shaped recipes execute at explicit `all`, `page`, `count` or mutation boundaries. There is no direct database iteration protocol in v1: loop over the resulting array/page. This also removes the earlier dependency on a new fallible-iterator protocol.

Read the native direction in `resources/discussion_points.md:2525–2578` before choosing these names: data and types belong together, using existing language constructs. `require` also appears in unrelated notes at `:3408`; no database-specific mandated spelling was found. Names here have **not** been cold-tested. This is a revision for review, not an accepted decision or an entry in open_decisions.md.

### Library construction, concretely

`fields_of<T>` returns an ordinary record with one `Selector<T,V>` per persisted field, where V is that field's type. These generic labels describe internal types; callers need no new exported type names or annotations. Each selector contains checked field-path metadata and a typed reference evaluator. The library builds that record by unrolling `fields(T)` and using constant `$field(f.name)`. Existing support: `docs/design/argparse_and_reflection.md:98–124`; `tests/cases/comptime/reflection.dewy:4–8,39–47`; `tests/cases/frontend/m_directives_direct_directives_identity_1.dewy:25`. It does not ask reflection for the body of a user function. The constructor can initialize descriptor data at runtime; a const binding is not a requirement to interpret arbitrary capturing functions at compile time.

An implementation sketch of the *field factory only*, with its enclosing function, is below. `make_field` is an internal ordinary generic constructor, not a compiler facility or public name. It accepts a constant schema field name and a compiled getter; the getter executes only in the reference evaluator. The compiler already specializes the field loop. This sketch is not a claim that the database types were compiled.

```dewy
fields_of = <T>() => {
    return [loop f in fields(T)
        $field(f.name)=make_field<T f.type>(f.name (row:T) => row.$field(f.name))]
}
```

`Selector<T,V>.eq(value:V)` and `.lt/.ge(value:V)` produce `Predicate<T>`. A predicate is a closed, validated graph of library-defined nodes with copied parameter values. `contains` is overloaded for a string substring and collection membership; it uses ordinary Dewy semantics. `all_of(array<Predicate<T>>)` conjoins predicates of the same input type; the empty conjunction is true. Arbitrary comparison overloads still return bool. The library does not symbolically run a lambda on fake records.

`where` accepts `Predicate<T>` only. Supplying `(a)=>a.balance <? 0` to a v1 recipe is a type error, with a suggested descriptor spelling. Ordinary functions remain fully usable *after materialization*: program 14 shows an indexed prefilter followed by a local comprehension calling a runtime function. Such local code may have ordinary effects; the planner neither moves nor replays it. There is no hidden purity/totality proof required to use that example.

Descriptors cannot authorize arbitrary SQL. Field metadata is resolved against a registered schema and checked at execution; values go into bound slots. Descriptors from the wrong record type fail type checking. An unrelated instance of a matching schema still gets runtime reference/provenance checks. Ref targets must be unique by named record type within a schema; otherwise schema construction rejects the ambiguity. Collection-qualified references and automatic cycle construction are deferred.

### Indexes, order and exact values

Keys are required immutable scalar fields or typed tuples of fields. Supported key components start with string, bool, exact integer and Ref; optional values may appear in secondary indexes, not primary keys. Ordinary nested values remain persisted values, not separate entities. Decoding validates type, UTF-8, tags, refinements, lengths and reference structure before returning T. Functions, resources and places cannot be persisted.

`database.tuple(x y)` and its three-argument overload return selectors whose **declared** result types are `[X Y]` and `[X Y Z]`. This is two ordinary generic overloads, not a variadic type facility. Program 01's index has result `[bool int string]`; its order key is `[int string]`. Program 04's index is `[int string]`; program 13's is `[int string]`. A longer key can use a nested typed pair, or a later overload; no untyped array is called a tuple.

The same tuples work in the ordinary reference evaluator with `(t):>[int string] => [t.priority t.id]`, shown in programs 01 and 13. Existing correct/incorrect fixtures are `tests/cases/sort/tuple_key.dewy:4` and `tests/cases/sort/array_key_hint.dewy:4`; the diagnostic is in `compiler/expr.jo:5704–5713`. These were inspected, **not rerun**, and the new database programs were not compiled.

Bare entities are ordered by primary key. Filtering preserves that order. Sorting is stable relative to it; reverse reverses the requested key comparator and preserves source order for equal keys. Adding/removing an index never changes values, ordering or tie behavior. An index on balance may filter K records in O(log N + K) but restoring primary-key order can cost O(K log K); `explain` says so. Tuple index codecs must agree with the ordinary comparator component by component. SQLite int64/double coercion is not an implementation of exact Dewy int/rational. Exact codecs/operators, or a warned local evaluator, are required; otherwise fail `UnsupportedFeature`.

Uniqueness follows Dewy equality, including `none =? none`: default optional uniqueness admits **one** absent value. `unique(U.email present_only=true)` omits absent values from the constraint; present duplicates still fail. This is a descriptor contract, not inherited SQL NULL behavior. Program 15 covers both. NaN/noncanonical equality and unsupported key domains are rejected, not mapped approximately.

## 2. Relations that keep their source records

`related(P.author A.email)` is a typed selector path through a stored Ref; it does no I/O when constructed. Applied to a required Ref it has result string; applied to an optional Ref it lifts absence to optional string under ordinary optional rules. A set of refs produces an array of selected values in stored set insertion order; membership uses `contains`, not a fabricated scalar equality. Nested optional unions preserve the language's existing distinctions. V1 supports one reference hop per related selector; arbitrary-depth traversals can wait.

`include([author=P.author tags=P.tags editor=P.editor])` is a read projection whose aliases are ordinary user-chosen record fields. Program 03 returns:

- `record:Post`, the original post, unchanged;
- `related.author:Author`, the required author;
- `related.tags:array<Tag>`, with zero, one or many entries, grouped by that post;
- `related.editor:Author?`, none when no editor is linked.

It yields exactly one row per selected post, preserving parent order and cardinality. Shared tags repeat in separate parents' arrays, never duplicate parent rows. Set insertion order is persistent and preserved; a present but dangling Ref is corruption/reference failure, never silently an absent optional. Callers can sort loaded tag arrays normally if they want label order. Restrict-on-delete remains the safe default; callers explicitly unlink then delete in one transaction.

A page selects parents, resolves all selected aliases and decodes them under **one snapshot**. It collects unique target identities per collection across all aliases, fetches each batch once, then scatters values into parent-associated arrays. Author and editor targets are combined into one author batch. Reference fields/sets are part of the parent value; there is no application association-table ceremony. Reverse-edge indexes are maintained atomically for `related` filters and referential checks, including set edges.

For B distinct target keys per backend batch, a completed page requires **at most 1 + ceil(Uauthors/B) + ceil(Utags/B) data-fetch statements** (omit empty batches). Snapshot establishment/transaction bookkeeping and plan preparation are separate fixed operations. Root related-field predicates are compiled into the root statement using target and reverse-edge indexes, or evaluated in a reported batched scan, never one statement per post. For a backend unable to compose that predicate in one statement, explain must give the additional batched scan bound; it cannot advertise the one-root bound. SQLite's initial supported related operators must meet the one-root bound. Program 03 has 3 parents, 2 distinct authors and 2 tags: with B≥2, **3 data-fetch statements**. Lookahead reads a parent identity only; it must not eagerly include a fourth parent's graph. Buffer and edge budgets can terminate a large fanout with QueryLimit.

No hidden fetches occur on `row.related.author.name`; these are already materialized ordinary values. `.include` produces a read-only query type, so update/delete are not offered on these rows. The old `.follow` loses parent context and is removed from v1, rather than retaining two competing relation APIs. Application postprocessing uses ordinary array comprehensions. This meets the feed use case served by [Django related loading](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-related), [Diesel associations](https://diesel.rs/guides/relations.html) and [GRDB associations](https://github.com/groue/GRDB.swift#associations); these are comparison targets, not evidence that this proposal is implemented.

## 3. Aggregates and writes without callable inspection

`group_by(S.region).summarize([orders=database.count cents=database.sum(S.net_cents)])` takes typed aggregate descriptors and returns ordinary `[key:string values:[orders:int cents:int]]` records. Count counts rows; sum has exact Dewy arithmetic. No group contains an `items` array. A native accumulator needs O(G) groups plus exact-number storage, rather than O(N) retained source rows. SQLite may group encoded keys but must use exact aggregate functions or the local accumulator. Group output is canonical key order; program 04 additionally shows ordinary array sorting. Empty grouped input gives no groups; entity `.count` gives zero. Custom aggregates, min/max/average and arbitrary projection recipes can wait; they are not needed to execute the specimen's report.

Mutations are restricted to **entity selections from one collection**, before include/group/summarize/search. `where` and `sorted` retain entity identity; there is no API to mutate a page token or an included/projected row. `update([done=true])` takes a typed constant patch, with fields a subset of the entity's mutable fields. It cannot change a primary key or call application code. `delete()` requires an explicit filtered entity selection; whole-collection delete remains deferred. A trivially true explicit filter is still a deliberate whole selection, with cost diagnostics.

Selection is fixed against the transaction snapshot before writing; each selected entity is considered once. Return counts mean **matched distinct entities**, even if a patch writes an equal value. No callback invocation count is hidden. Whole-operation constraints are validated and the operation is atomic; failed mutation poisons an explicit transaction. Updating a field used by the predicate cannot revisit it. Read-dependent transforms use a transaction's `require`, ordinary code and `replace`, as the bank and stock examples do. Multiple rows sharing a related tag cannot accidentally update that tag twice: their included read query has no mutation methods. A future traversal mutation must design deduplication separately.

`get` returns T/none/errors; `require` returns T/RecordMissing/errors and serves key or typed-Ref lookup. `reference` verifies an existing row and returns its Ref; insert returns its newly minted Ref. `replace` requires an existing key; `put` inserts or replaces. Both remain transaction-only so a stale live-store read does not silently overwrite through a convenience call. Optimistic disconnected edits still need a revision check (program 12); a general compare-and-replace/token API is deferred, and the concision grade reflects that choice.

## 4. Transactions and waiting tasks

Transactions are serializable, task-owned, and rollback by abandonment; commit is explicit. SQLite writer admission is an immediate, cancellable finite wait before user reads. Store handles can be shared; transaction handles cannot cross tasks. No nested begin/savepoint fiction and no automatic replay of callbacks. The lifecycle uses the accepted assigned-function `$__abandon__` hook; commit cannot be a drop action. A failed write poisons tx even if the caller handles its error. `commit()` consumes tx on success **or failure**; a failed commit releases/rolls back any unpublished state. Program 08 no longer tries to reuse a consumed transaction.

Known prepublication failure means no publication; a storage failure with uncertain outcome is CommitUnknown. Never advise blindly retrying a transfer without its durable request identity. D40 still owns cleanup timing and multiple-failure representation: this design can implement rollback ownership with existing resource machinery and an explicit commit, but must conform to that decision before shipping. No new language feature is required by the descriptor planner; that is separate from completing engine/lifecycle validation. Do not claim to have settled D40 here.

Program 05 imports `@lib/std/tasks.dewy` as task and calls `task.tasks((group:Tasks)=>{...}) or_throw`. Each spawned callback begins/ends its own transaction; expected OutOfStock is handled inside it. An unexpected child error fails the scoped group, cancels siblings and **joins before returning**; a sibling that already committed stays committed. Each order is captured as a value, with no writes to outer variables. With two initial units and quantity-one orders, at most two distinct reservations commit; a third valid attempt reports OutOfStock if no unrelated failure interrupts it. The example does not claim a whole-batch transaction.

Source alignment: accepted D4 decisions in `docs/design/decisions.md` batches 7–9 govern `.dewy` imports, ordinary calls and cancellation/resource context; `docs/design/proposals/concurrency/unified/proposal-v5.md:263–276` defines this scoped-group lifecycle. The **`task.tasks` spelling remains D41 Q3**, `docs/design/open_decisions.md:102–115`; it is a proposed ordinary library function, not approved new syntax. Earlier accepted unified concurrency also allows waiting work; the current LANGUAGE.md CPU-only text is stale relative to that direction. The repair therefore does not assert that every future `parallel` form must be nonblocking: it deliberately uses the scoped waiting-task contract asked for in this review. Database effects remain honestly blocking.

## 5. Execution, costs and default diagnostics

Every terminal query binds a snapshot; continuations retain that same snapshot, schema, recipe, parameters and order. They are opaque in-process capabilities, not serializable web tokens. A query using an existing snapshot borrows it; close is legal only after its outstanding operations/continuations end. Program 13 drains to next=none before closing. Long snapshots can retain WAL/pages; no automatic lease expiry silently changes results. Expired/mismatched continuations fail explicitly.

The library planner recognizes its own descriptor nodes; ordinary record reflection suffices. It reports usable and chosen indexes separately, residual local descriptor operations, ordering work, aggregate state, includes, batches and estimated cardinalities (unknown if unknown). Missing indexes or local fallback **warn by default**. In v1 these are library runtime planning diagnostics, deduplicated by store/schema/plan shape, not a promise of compiler source warnings. A string `.contains` scan remains legal and warned. An unavailable exact operation may use the library's ordinary reference evaluator; unavailable semantics with no exact implementation yield UnsupportedFeature. No callback-source introspection is smuggled in for diagnostics.

Resource meanings are deliberately separate:

| Setting | Contract |
|---|---|
| `size` | Output rows per page, not work. |
| `max_scanned` | Logical visits across operators in that execution. One candidate index entry costs one; decoding its entity costs another. A record entering each residual filter, sort or grouping stage costs one again. A related target fetched once costs one, and each traversed/scattered relation edge costs one. Repeated edges count repeatedly. Lookahead counts too. Physical B-tree internal pages, bytes and elapsed CPU are not this counter. Fused stages must debit their logical stages; backend index elimination changes the actual work and may change whether a budget succeeds. |
| `max_bytes` | Peak charged query allocation: decoded values, retained output, parameter copies, sort/group/include state and backend query scratch, including spill bytes. Existing wider memory caps still apply. Cache pages already owned by the shared store, total device I/O and database file size are outside this per-query charge. An adapter unable to meter its required scratch must reject this requested bound with UnsupportedFeature before executing, not silently ignore it. |
| `timeout` | Cooperative deadline including admission, backend execution and decoding, checked at bounded engine progress intervals; QueryLimit for query deadline exhaustion. An OS/storage call can overrun before control returns. This is not a hard wall-clock or CPU quota. |

The SQLite adapter must meter the stated logical events, or use equivalent metered library execution stages. Reading a row count only after execution does not enforce a bound. An adapter unable to enforce a requested bound rejects it before executing; it must never quietly treat it as a hint. Nonpositive page sizes/budgets are ValidationError.

Every page call has a fresh execution budget, including continuation calls; callers needing a request-wide budget must account across them. Limit exhaustion yields QueryLimit with no partial page/array. The snapshot/continuation remains valid unless another failure invalidates it; raising a budget is an explicit new call, not implicit unlimited retry. Terminal `all` accepts the same work options. Counts do not bound enormous values or arbitrary postprocessing functions; program 14 says this explicitly. Acceptance-test instrumentation must expose measured stage counters and allocation high-water marks. Public `query.explain` remains a side-effect-free planning report; no implicit execution or profiling API is added. Default warnings do not expose user data.

A service can require budgets through an ordinary wrapper (the type parameters are existing generic syntax). This is a policy boundary, not a new global “must use an index” tag; callers must choose finite positive values. It bounds the documented resources only, not every physical I/O operation.

```dewy
serve_page = <Q>(query:Q visits:int bytes:int) => {
    return query.page(size=20 max_scanned=visits max_bytes=bytes timeout=2s) or_throw
}
```

Program 09 catches QueryLimit and continues the interactive session. It is a narrow trusted CLI, not a language REPL. General developer-REPL resource ownership remains outside this first library slice.

## 6. Repeatable migrations, backups and restore identity

V1 migration plans are **structural data**: old/new schemas plus explicit typed rename/remove descriptors, constant defaults, and optional additions defaulting to none. Rename preserves field ID; removal retires it. No transform callback is fingerprinted by pretending the library can inspect its code. Required additions without a serializable constant default, arbitrary type conversion, key changes, collection rename/removal and reference target remapping are rejected before writes with UnsupportedFeature. These are real v1 exclusions, not claims that every schema evolution is solved.

`migrate(path change backup_dir=...)` opens its own metadata runner rather than requiring an old-schema application handle. Under exclusive migration coordination it checks history and schemas:

1. Expected old schema and unused plan identity: generate/verify a backup, apply the plan, validate the complete prospective state and atomically publish schema+data+history.
2. Expected new schema **and the same recorded structural plan hash**: already complete, return success without another backup/migration. A coincidentally matching schema with different history is MigrationConflict.
3. Backup completed but schema still old after failure: reuse only a verified backup matching the locked source snapshot, otherwise allocate a new destination. Collision-safe filenames use exclusive create, never overwrite. A crash during publication leaves either old or new data/history; reopening determines which, rather than guessing from a filename.
4. Unexpected source/history or inability to exclude stale handles: explicit failure, no application access under a fabricated schema.

The descriptor hash covers schema fingerprints, stable IDs, literal defaults and all operations, with a versioned canonical encoding. Plan object addresses, callback identities and source text are not fingerprints. This is an offline migration; large rebuilds may require space and pause writers. Program 06's second identical deploy is a no-op, unlike the old-schema-open example it replaces.

A collection's stable identity and row incarnations survive supported field migrations. Renaming a record type in source alone does not change its stored collection identity. All typed Ref fields are decoded/validated against the new schema's target type while retaining that target collection+row incarnation; stale application handles are invalidated. Changing *which* collection is targeted, deleting a collection, or rewriting keys is refused in v1. This explicitly bounds typed-reference evolution without claiming arbitrary migrations are safe.

Separate **persistent lineage** from **active store instance**. A Ref carries persistent lineage/collection/incarnation and an active-instance binding when decoded/minted; that binding is not serialized into the database. Handles for the same coordinated file share an instance identity; a different file gets a different binding. Passing a source Ref to a backup inspection handle yields ReferenceMismatch, even when the stored lineage matches. Loading the corresponding Ref from the backup binds it to the inspection instance. Reusing a user key never resurrects an old incarnation.

`backup(path)` creates a verified consistent snapshot, marks it as a backup, syncs and publishes without overwriting; partial output is not success-named. Its stored lineage is retained for provenance, but the backup **cannot be opened writable**. V1 `restore(backup new_path)` creates a fresh writable lineage at a new path, remaps every internal nested Ref atomically, validates, syncs and publishes without overwrite. External pre-restore refs and continuations fail; applications reacquire records by stable user keys. It is an explicit fork/restore, not transparent identity-preserving takeover. Program 13 exercises inspection and this new-path restore. A backup taken after commit is its own snapshot, not necessarily that transaction's exact state (program 12).

V1 has no identity-preserving recovery/takeover of an active path, no merging divergent stores, and no supported “copy the live file and open both writers” workflow. Instance bindings prevent accidental mixing of live handles in one runtime; no library can globally detect arbitrary out-of-band file copying across isolated processes. The native durable format is library-owned, not a portable interchange promise. Backup metadata is an integrity convention, not authorization against hostile editors. The initial adapter uses coordinated SQLite backups, durable settings and file locks; a pure-Dewy engine must separately earn crash/recovery/locking conformance.

## 7. Search and SQL

The v1 full-text descriptor is `full_text([N.title N.body] tokenizer='unicode61_v1')`. The profile pins Unicode 6.1 word categories L*/N*/Co, case folding, Latin diacritic removal mode 2, no extra token characters, no stemming and no stop words. Literal query tokens are deduplicated and ANDed; an empty token list returns zero hits. Quotes/operators never become backend query syntax. Reject document/query tokens exceeding 32768 encoded bytes with ValidationError instead of inheriting FTS5's silent truncation. A provider missing this exact tokenizer profile returns UnsupportedFeature at schema/open time; changing profile requires rebuilding the index explicitly. These choices use documented [SQLite FTS5 behavior](https://www.sqlite.org/fts5.html#unicode61_tokenizer); the proposed profile and oversize rejection are library contracts.

SQLite v1 uses equal-weight BM25, **lower scores first**, then canonical primary-key ties. Scores and excerpts are backend/version-specific, not portable relevance numbers; the tokenizer/matching contract is portable. Excerpts are plain text from stored content, not HTML. Paging pins the corpus snapshot as well as hits. Phrase queries, boolean search, multilingual analyzers, relevance tuning and portable cross-engine ranking can wait. Program 07 is honestly literal word search, not general web search. The score direction follows [FTS5 BM25](https://www.sqlite.org/fts5.html#the_bm25_function).

SQL remains a distinct first-class adapter, illustrated by unchanged program 11: constant single-statement prepared text, separately bound parameters with an exact checked parameter shape, typed named rows, checked NULL/range decoding, and read-only open where requested. External SQLite files are not silently adopted into native metadata. `sql.sqlite`, `prepare`, statement `all` and `execute` are the initial SQL names; SQL transaction ownership follows the same explicit-commit rule. Native migrations never operate on an arbitrary external SQL schema. SQL dialect/plan behavior and binary backups are adapter-specific.

## 8. Three common queries: descriptors now, exact lambdas later

Each cell below is a complete enclosing function. Declarations/imports are the same as programs 14, 04 and 03 respectively; left and right are alternatives, not two competing functions in one module. Right-hand APIs are **future illustrations**, conditional on a separately approved function-inspection design. They are not used by any v1 program or grade.

| Query | Library-only v1 | With exact-lambda translation |
|---|---|---|
| Negative balances | `negative = <S>(store:S) => {`<br>` return store.accounts.where(A.balance.lt(0)).all or_throw`<br>`}` | `negative = <S>(store:S) => {`<br>` return store.accounts.where((a) => a.balance <? 0).all or_throw`<br>`}` |
| Date range, compound order | `by_day = <DB>(store:DB lo:int hi:int) => {`<br>` return store.sales.where(database.all_of([S.day.ge(lo) S.day.lt(hi)]))`<br>`  .sorted(key=database.tuple(S.day S.id)).all or_throw`<br>`}` | `by_day = <DB>(store:DB lo:int hi:int) => {`<br>` return store.sales.where((s) => lo <=? s.day and s.day <? hi)`<br>`  .sorted(key=(s):>[int string] => [s.day s.id]).all or_throw`<br>`}` |
| Author email + posts/authors/tags | `by_author = <S>(store:S email:string) => {`<br>` return store.posts.where(database.related(P.author A.email).eq(email))`<br>`  .include([author=P.author tags=P.tags]).all or_throw`<br>`}` | `by_author = <S>(store:S email:string) => {`<br>` return store.posts.include([author=P.author tags=P.tags])`<br>`  .where((row) => row.related.author.email =? email).all or_throw`<br>`}` |

The third future example deliberately filters an **included row**: a stored Ref does not magically expose author.email. Inspection could recognize the included-value path and push its pure predicate into the root plan, retaining one snapshot and parent cardinality. Supporting `p.author.email` directly would change reference semantics and is **not** an incidental benefit of function inspection.

Exact inspection would expose a callable's resolved typed body, captures and effect/control-flow information as data. The database library could recognize field projections, comparisons, boolean combinations, typed tuple keys and pure projections/aggregates, construct the **same** descriptor graph, and retain source locations for diagnostics. Captures become copied parameter values. Ordinary operators and helpers would be reusable without spelling `eq/lt/ge/all_of/tuple`; recognized pure record projections could avoid decoding unused fields. Typed aggregates already avoid retaining all group items in v1; lambda syntax is not required for that optimization.

Inspection alone does **not** prove purity/termination, make arbitrary helpers translatable, justify SQL coercions, override optional/short-circuit behavior, infer I/O through Ref, or permit capturing mutable places. Unknown calls need an explicit ordinary local path or a separately specified warned residual policy. Any transformation must preserve values, errors, ordering and observable effects. The generic inspection design owns body visibility, module privacy, specialization limits and diagnostics; this database round proposes no names for it.

An **unwrapped eager comprehension** is a distinct boundary. In `[loop a in store.accounts if a.balance <? 0 a]`, the filter belongs to the caller; a library iterator cannot see it. Future function inspection could translate a comprehension *inside a callable explicitly handed to the library*, provided the inspection representation includes loop/filter/yield/control-flow nodes. That wrapper/API and how it executes eagerly would need design. Making the exact **unwrapped** spelling indexed additionally requires general compiler iteration lowering/optimization or a general way to pass the enclosing expression to a library. Function inspection by itself does not intercept that syntax. Neither mechanism may turn eager arrays lazy or reorder side effects/errors.

Today the fully legal eager spelling is simply explicit materialization; its enclosing function is shown so the boundary is visible:

```dewy
local_negative = <S>(store:S) => {
    let rows = store.accounts.all(max_scanned=1000) or_throw
    return [loop a in rows if a.balance <? 0 a]
}
```

That form scans/materializes before filtering. Its descriptor counterpart filters before materialization and can use an index. The potential future gain is writing ordinary language while retaining that planned execution, **not** making the current descriptor version correct for the first time.

## 9. Surface cuts and first-version names

All public proposals, including options, result fields and errors, are inventoried in [names.txt](names.txt). Names there are short cold-read usages; it is not a claim of a completed cold study. No database keyword, metatag, AST API or query quotation syntax is proposed.

| Tier | Names and justification |
|---|---|
| Essential storage + transaction core | `collection`, `fields_of`, `Ref`, `open`, `memory`, `get`, `require`, `insert`, `reference`, `replace`, `put`, `begin`, `commit`, `rollback`, `snapshot`, `close`. Required lookup earns its extra name by removing repeated error/absence ceremony. |
| Essential query + relation core | `index`, `unique`, `tuple`, `eq`, `lt`, `ge`, `contains`, `all_of`, `where`, `sorted`, `all`, `count`, `page`, `explain`, `related`, `include`, `update`, `delete`. Explicit objects keep v1 independent of language inspection; include replaces follow. |
| Needed for the brief's complete first release, separable library modules | `group_by`, `summarize`, `sum`; `migration`, `rename`, `remove`, `describe`, `migrate`; `backup`, `restore`; `full_text`, `search`; SQL `sqlite`, `prepare`, `all`, `execute`. A smaller storage MVP can ship first, but cannot claim the brief's aggregates/evolution/backup/search/interop coverage until these land. |
| Can wait; absent from v1 | Planned `map`, `follow`, mutation lambdas, generic transform migrations, arbitrary custom aggregates, collection-qualified Ref, compare-and-replace, savepoints, `.where(lambda)`/`.sorted(key=lambda)` on queries, direct query iteration/comprehension lowering, nested include paths, independent projection DSL, index hints, automatic retries, global must-index tags, OR/NOT builders, identity-preserving takeover, online migration, stateless web cursors, advanced full-text grammar. Ordinary array map/sort/comprehensions still work. |

OR/NOT do not earn dedicated v1 names in these programs; boolean equality, conjunction and materialized ordinary code cover this bounded first release. This intentionally limits native query expressiveness and is counted in completeness, not hidden behind “complete.” A later `any_of`/negation descriptor is a library extension and does not require callable inspection.

## 10. Review disposition and acceptance gates

| Finding | Round-4 resolution and specimen |
|---|---|
| M1 waiting DB work | Program 05 scoped tasks; transaction per child; expected and unexpected outcomes stated. D41 spelling status explicit. |
| M2 compound sort types | Programs 01/04/13 typed selector tuples; 01/13 ordinary typed sort references. No array comparator invented. |
| M3 common blog reads | Program 03 post+author+grouped tags+optional editor, related-field filter, deterministic batching and row cardinality. |
| S1 mutation origins | Only entity selection mutates; matched distinct-row counts, constant patches, fixed candidates. |
| S2 resource bounds | Defined visit/byte/deadline/output distinctions; programs 09/14 honest caps and local execution. |
| S3 optional unique | Explicit present_only; program 15 covers both modes. |
| S4 migration rerun | Structural data runner, idempotent recorded history, collision-safe backup; unsupported reference/key evolution refused. |
| S5 backup forks | Runtime instance binding, read-only backups, new-lineage remapping restore. |
| S6 lookup/optimistic ceremony | require added; optimistic helper still application code, marked down. |
| S7 full-text contract | Pinned tokenizer, term-length rejection, literal matching, explicit rank direction and tie key. |

Before implementation is called complete: compile the specimens; compare every descriptor evaluator with backend execution with/without indexes; validate optional uniqueness, exact arithmetic and tuple order; assert blog output/cardinality and measured statement counts; test task cancellation and writer contention; fault-inject late mutation/commit/cleanup, backup and every migration recovery boundary; test reference remapping and wrong-instance failures; meter budgets including backend scratch. Program 08/15 are intended acceptance tests, not executed test evidence. No benchmark or durability claim follows from this paper.

The regrade is [dogfood-round4.md](dogfood-round4.md): **whole-corpus floor 2**, because the CSV importer still needs a 73-line local parser; **database-focused floor 3**, from remaining discoverability/operational/completeness costs. No score is contingent on future callable inspection. The earlier floor-2 language dependency, incorrect tuple callbacks and inventory lane are removed from the v1 designs; the honest remaining deficiencies are named rather than upgraded to 5.
