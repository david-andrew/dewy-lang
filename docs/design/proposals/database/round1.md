# A Dewy-native database: round 1

## Five small examples

These are **proposed library contracts**, not executable examples of an existing database library. Each operation is inside its enclosing function. Ordinary record declarations stay at module scope, as Dewy currently requires. `database.dewy` and `sql.dewy` below are proposed modules. The query-translation dependency is explicit in rule 4; comptime alone does not supply it.

### 1. Define a record and open its store

```dewy
import p"@lib/std/database.dewy" as database
Account:type = [id:string name:string balance:int]
const schema = [accounts=database.collection<Account>(key=(a) => a.id)]
main = () => {
    let db = database.open(schema p"accounts.db") or_throw
    printl(db.accounts.count or_throw)
}
```

A fresh file is initialized atomically. An existing file must match this schema; opening never silently migrates it. `Account` is also usable in an array, an argument, or a message, with no database parent type.

### 2. Insert and load an ordinary value

```dewy
import p"@lib/std/database.dewy" as database
Account:type = [id:string name:string balance:int]
const schema = [accounts=database.collection<Account>(key=(a) => a.id)]
main = () => {
    let db = database.memory(schema) or_throw
    let account = db.accounts.insert(Account["ada" "Ada" 10000]) or_throw
    let saved = db.accounts.get(account) or_throw
    printl"{saved.name}: {saved.balance} cents"
}
```

`insert` returns a typed reference. `get` accepts the reference or the collection's key type. It returns `Account | none | errors`; this example forwards absence too. Reading returns a value, not an object whose assignments secretly write to disk.

### 3. Filter using an index

```dewy
import p"@lib/std/database.dewy" as database
Account:type = [id:string name:string balance:int]
const schema = [accounts=database.collection<Account>(key=(a) => a.id
    indexes=[database.index((a) => a.balance)])]
main = () => {
    let db = database.open(schema p"accounts.db") or_throw
    let query = db.accounts.where((a) => a.balance <? 0)
    printl(query.explain)
    let overdrawn = query.all or_throw
    loop account in overdrawn { printl(account.name) }
}
```

The intended plan is a range seek on the balance index, decoding only matching records, then restoring the specified result order if necessary. Index selection is automatic; index *creation* is an explicit persistent schema choice. This is a target contract pending general callable inspection, not a claim that today's compiler can produce it.

### 4. Connect records without implicit fetching

```dewy
import p"@lib/std/database.dewy" as database
Author:type = [id:string name:string]
Post:type = [id:string author:database.Ref<Author> title:string]
const schema = [authors=database.collection<Author>(key=(a) => a.id)
    posts=database.collection<Post>(key=(p) => p.id)]
main = () => {
    let db = database.memory(schema) or_throw
    let tx = db.begin or_throw
    let author = tx.authors.insert(Author["ada" "Ada"]) or_throw
    tx.posts.insert(Post["intro" author "First post"]) or_throw;
    tx.commit() or_throw
    let posts = db.posts.where((p) => p.author =? author).all or_throw
    loop post in posts { printl(post.title) }
}
```

Reference fields get reverse indexes automatically. Loading the author is `db.authors.get(author)`, an explicit operation. A query can follow many references in one operation with `.follow((p) => p.author).all`; it does not issue one hidden fetch per field access.

### 5. Change several records or change nothing

```dewy
import p"@lib/std/database.dewy" as database
Account:type = [id:string balance:int]
InsufficientFunds:type = type of error
InvalidTransfer:type = type of error
const schema = [accounts=database.collection<Account>(key=(a) => a.id)]
transfer = <S>(db:S source:string target:string amount:int) => {
    if amount <=? 0 or source =? target return InvalidTransfer
    let tx = db.begin or_throw
    let debit = tx.accounts.get(source) or_throw
    let credit = tx.accounts.get(target) or_throw
    if debit.balance <? amount return InsufficientFunds
    tx.accounts.replace([debit... balance=debit.balance-amount]) or_throw
    tx.accounts.replace([credit... balance=credit.balance+amount]) or_throw
    tx.commit() or_throw
}
main = () => {
    let db = database.memory(schema) or_throw
    db.accounts.insert(Account["a" 100]) or_throw;
    db.accounts.insert(Account["b" 0]) or_throw;
    transfer(db "a" "b" 20) or_throw
}
```

The transaction's `$__abandon__ = () => …` rolls back. Only `commit()` publishes. The realistic ledger in program 02 adds balanced journal entries and a request key so an uncertain caller can safely check/repeat the same request.

## Scope and acceptance

Owned files: this scratch directory only. Non-goals: compiler or engine implementation, changes to accepted syntax, new consensus/distributed-storage guarantees, a visual UI, benchmarks, and repository decisions. Budget: approximately three hours. Acceptance: five minimal examples; all requested use cases with concrete semantics; 12 or more whole design programs; primary-source prior art; line-cited honest dogfood; a cold-read name inventory; a one-page summary. No compilation, performance measurement, independent reader study, or fault-injection run is claimed.

The governing input is David's database direction in `docs/design/decisions.md:703–711`. `docs/LANGUAGE.md` describes an older implemented subset in several places; the later decisions take precedence. In particular, batch 9 changes dunder declarations and block scope. D40 still leaves cleanup timing, multiple-error representation and the visibility of an exit caused by cleanup unresolved. D41's helper names remain open; the programs do not require them.

## Rules

### 1. Values, storage handles, and schema

A stored record is an ordinary Dewy value. Editing a loaded record edits that local value. Persist through `insert`, a query's `update`, or a transaction's `replace`/`put`. There is no identity map, dirty tracking, inherited model class, lazy property read, SQL NULL, or database-owned object lifetime in a loaded record.

A store is an explicitly acquired shared external-resource handle, like a channel or mutex. Copying it shares one database, not a copy-on-write clone of persistent storage. Its generated collection members carry the same identity. Docs and hover must say this; ordinary records do not silently acquire shared semantics. A transaction is move-only and cannot be shared across tasks. A query is an immutable recipe with captured parameter values and a store/snapshot handle. A snapshot is a read-only resource owner; copying its lightweight views shares the same pinned snapshot, never a newer one. Closing the snapshot invalidates such views only when the ownership checker proves no later use; otherwise it is an error.

`collection<T>(key=… indexes=…)` describes one collection. A schema is an ordinary constant record of these descriptors. Opening returns a record with correspondingly named typed collection handles, generated via `fields(S)` and `$field`, as in the decided argparse design. That part needs ordinary generic record construction, not a database builtin. Descriptors also record storage codecs, constraints and schema identity. The existing restriction on capturing/indirect comptime calls must be lifted before every shown descriptor is implementable as written.

The key is an immutable, required ordinary field or composite of fields, selected by a total pure function. In v1, index and key selectors must be projections of fields or tuples of projections, not arbitrary business code. Stable key types: strings, bools, exact integers and composites of these; typed references are also valid index components. No NaN keys. A type does not silently inherit a property named `id`: every descriptor selects its key. Changing a key requires a migration; `replace` cannot relocate a row.

The same record type may be stored in several collections when it is not the target of an ambiguous `Ref<T>`. In this first design a reference target must resolve to one collection of T in the schema. An ambiguous schema is rejected, not resolved by a pluralized name or declaration order. Distinct named domain types resolve that case. A collection-qualified generic reference remains a later ergonomic question, not an invented syntax in these examples.

### 2. Representation and validation

The native logical model includes scalars, optional values, literal unions, tagged unions, nested records and finite arrays/dictionaries/sets. Nesting stores values; only `Ref<T>` denotes another record's identity. Recursive finite values use a bounded validating decoder. Resource owners, function handles, places, pointers and secrets without an explicit encryption codec cannot be persisted. A type's methods are behavior and are not serialized.

Schema-derived decoding validates values, tags, UTF-8, refinements and length bounds before yielding T. Corrupt or externally incompatible bytes are `DecodeError`/`CorruptStore`, never a cast to trusted T. Write validation is also required at the backend boundary. A user-defined refinement that is not executable as a checked validator cannot be promised on external data; diagnose it instead of asserting it. Arbitrary user callbacks are not stored as constraints in SQLite.

SQLite storage uses library-owned metadata, scalar columns where exact semantics are supported, and canonical value encoding for nested/exact values. Internal stable field IDs are recorded on disk, so a source rename does not become a new unrelated field after an explicit rename migration. Arbitrary-precision `int` and `rational` cannot be silently coerced into SQLite int64/double. Their ordering, sum, equality and index encoding need audited exact implementations or a local evaluator; say which in `explain`. No promise of C-like speed for a blob-decoded numeric aggregate. Unicode comparisons and optional equality follow Dewy, not a backend's locale or three-valued logic. `none =? none` is true; optional filters have two-valued Dewy results.

### 3. Execution and ordering

`where`, `map`, `sorted`, `group_by` and `follow` construct recipes; they do no I/O. `get`, `all`, `count`, `sum`, `page`, and mutation methods execute. A database iterator can stream with `loop row in query or_throw`; it binds a snapshot once at loop entry, reports per-step failures, and releases its continuation on every exit. This depends on completing the general fallible iterator protocol; examples mostly materialize at a visible `.all or_throw` boundary. Ordinary array comprehensions remain eager. Ordinary array `.sorted` still materializes an array; the database recipe's `.sorted` returns another recipe, visible in the type.

A bare collection's deterministic iteration order is its canonical primary key order. Filtering preserves it. `sorted(key=)` is stable; equal sort keys retain input order. Thus the account index on balance can select rows efficiently but may need a final key sort. A planner cannot make the observable order depend on which index exists. `reverse=true` reverses the selected ordering as ordinary stable sort specifies. The explain output includes any required reorder. Arrays and keyed page results preserve duplicates; `follow` preserves one output per input reference. Optional links can produce optional outputs; following an absent optional does not drop the source row implicitly.

Execution on a live store chooses a fresh snapshot each time; saving a query does not save its results. `store.snapshot` pins one view for related reads. A transaction sees its own earlier writes. A query cannot escape a consumed transaction. The default read boundary is a whole query execution, not one fetched row. Local filtering, grouping and follow operations share that same snapshot.

### 4. Exactly how a predicate becomes a plan—and the missing prerequisite

Target: `db.accounts.where((a) => a.balance <? 0).all` type-checks the lambda against **Account**, not an expression proxy. Its ordinary return type is bool. The desired library pipeline is:

1. Receive a compiler-provided, typed, read-only description of this callable's operations plus its ordinary executable callable and capture layout. This is a **missing general language facility**, not implemented by `fields(T)` and not currently decided.
2. At comptime, library code recognizes `field(balance) < parameter(0)` with exact Dewy semantics. It builds an ordinary typed plan value: source collection, comparison, captured parameter slot, result projection and order. It does not run the callback on invented data.
3. At execution, resolve the schema's balance index, verify index/collation/codec compatibility, and choose a range scan. Data values go into bound parameters or engine value slots. Query structure and identifiers come exclusively from checked schema/plan nodes.
4. Decode candidates, apply any residual predicate, restore primary-key order, and produce `array<Account> | errors`. The asymptotic access cost is O(log N + K); preserving key order may add O(K log K). Explain must not conceal that term.

**Why operator overloading is insufficient:** `docs/LANGUAGE.md:2440–2458` requires comparisons to return bool; a real `if` branches on that bool. Running a generic lambda against an overloaded symbolic record cannot capture both branches, built-in short circuit, ordinary typed helpers, or arbitrary control flow. Reflection over fields describes Account, not the lambda. Full comptime execution of a function is not reflection over its code. Current `docs/design/argparse_and_reflection.md:98–108` deliberately excludes AST/source-generation macros. This round must not claim otherwise.

**Required expression:** `[loop a in db.accounts if a.balance <? 0 a]` is an eager array comprehension under the accepted language. Its filter belongs to the caller, not the collection's iterator. A collection library cannot see that filter today. There are two distinct missing facilities: callable inspection for `.where`, and a general way for ordinary comprehensions to lower to inspectable iteration/filter/map combinators or for libraries to participate in optimizing typed iteration. Only the first solves the method example.

The *desired* comprehension lowering is the same source/filter/project plan as the method form, executed immediately. It must preserve eager execution, exception forwarding, snapshot acquisition, row order, short circuit, side effects and `break`/`continue`. A standalone `loop` with printing streams rows and prints in ordinary order; it cannot be freely turned into a set-at-a-time operation. No new database-specific grammar is proposed.

**Recommendation:** use methods as the first indexed native surface, conditional on a separately designed general callable-inspection contract. Keep the exact comprehension semantically usable as a warned scan until a general iteration-optimization contract is approved and proved. If the requirement is that both be indexed using *only today's documented library capabilities*, that requirement is blocked. Do not conceal the blocker in a fake `$query` tag or a function named `comptime`. No all-5 grade is possible here.

No public name for the general code-inspection API is put on the database naming ballot. The facility needs its own design, privacy/module rules, source attribution, bounded specialization and metaprogramming review. Reading a typed body and producing plan data need not generate source or new syntax, but that distinction still requires a decision; this paper does not approve it.

### 5. Unsupported lambdas and query costs

A callback proven pure, deterministic and total but not translatable runs as ordinary compiled Dewy over the candidate rows, with a source warning. An opaque callable without a trustworthy purity/effect summary cannot be assumed pure. State-changing, I/O, random/time-reading, or possibly failing predicates must first materialize rows and use an ordinary loop; those effects must not be duplicated, reordered or erased by a planner. The methods' static callable requirements propagate through wrappers just as task callback requirements do.

A captured value is copied at recipe construction. Capturing a mutable shared place in a planned query is rejected. A dynamic pure callable stays legal with a generic local-filter plan and an execution cost warning. Translation failure is not a runtime syntax error after deployment. A finite union of known callable implementations may specialize to multiple plans, within a stated budget; reaching the budget selects the residual path with a warning.

For `where(balance < 0).where(check)`, the first indexed filter bounds the local callback. For `where(check and balance < 0)`, moving the second test before the first is only sound if check is total and effect-free; otherwise do not move it. A local residual is evaluated before limit/paging/aggregation where the original expression places it. Never apply LIMIT first and return too few matching rows. Do not push partial arithmetic, overflow, optional unwraps or different collation semantics into SQL.

Warnings name: source expression; absent usable index; candidate-row bound if known; residual callback; local sort/grouping or decode; expected complexity; an actionable fix. An index **available** is not an index **used**: SQLite may choose a scan for tiny or unselective data. Static diagnostics report structural index eligibility; execution explain reports the actual chosen plan and statistics, without promising unavailable cardinalities. Runtime warnings are once per source site/schema-plan revision, never for every row. A `.page(size=20)` limits output, not rows scanned. Program 14 requests `max_scanned=1000`; failure is `QueryLimit`, not a partial result mislabeled complete.

There is no new global performance tag. Existing resource caps/effect contracts remain in force. `$no_hidden_costs` does not mean 'must use an index'; do not repurpose it. Ordinary default warnings are appropriate for scans, even correct useful analytics scans. Dynamic plans still need runtime budgets if the application requires bounded cost.

### 6. Updates, transactions and cancellation

`insert(record)` fails on a duplicate key/unique value. `get(key)` returns none only for absence. `reference(key)` validates existence and produces a `Ref<T>`. A reference encodes store identity, collection identity and an incarnation token, so deleting then reusing a user key never makes an old reference point at a new row. A reference is not authorization and cannot fetch by itself.

`where(predicate).update((old) => [old... field=value])` is an atomic transform over the matching snapshot, returning the changed-row count. Callback requirements are the same as query callbacks. Unique/reference/validation errors abort the whole operation. Selection is fixed before writes so changing an indexed field cannot revisit or miss rows. `delete()` on a filtered recipe is all-or-nothing and returns its count; a dangling reference yields `Referenced`. Unfiltered whole-collection destruction needs an explicitly named whole-collection operation, intentionally absent from everyday completion until separately designed. A full-collection update is allowed but warns for its cost.

`replace(record)` and `put(record)` are transaction methods in this proposal. The former requires the key to exist; the latter explicitly inserts or replaces and returns the resulting typed reference. Keeping them on a transaction avoids accidentally overwriting a value read from a stale live-store snapshot. It does not prove the application made a sensible edit: use the transaction's own read or an atomic transform. A future compare-and-replace operation would serve disconnected editors without weakening this rule.

`begin(timeout=5s)` starts a serializable read/write transaction, including a coherent initial snapshot. SQLite uses an immediate writer reservation before user reads, separate reader connections, foreign checks, no shared-cache dirty reads, and a finite cancellable wait. Only one SQLite writer progresses at a time. A native engine must either serialize writers or detect all conflicts including read predicates/phantoms. Snapshot isolation alone is insufficient for this contract. A snapshot is read-only; there is no implicit read-to-write upgrade. An isolation mode is a typed option, but v1 only exposes the safe default; do not add a weakening knob without a real use case.

Every successful single live-store mutation is its own transaction. Several calls require an explicit tx. The transaction cannot escape to a task; a store can be shared safely, and each task begins its own tx. Waiting for a sibling or external channel while holding a writer transaction can deadlock; integrate the handle into existing wait diagnostics, and reject uncertified waits under `$no_deadlocks`. Neither a timeout nor a lock-free host API is a proof. A nested begin against the same store is not a savepoint; diagnose known self-deadlock and return a bounded wait failure where identity cannot be proven. Savepoints require a separate explicit nested-transaction design.

`commit()` consumes tx. On a known failure before publication its owned work rolls back. On uncertain publication it returns `CommitUnknown`; never automatically repeat the callback or claim rollback undid a committed transaction. `rollback()` consumes tx explicitly. All unconsumed exits—including none, early success, loop exit, cancellation and panic—abandon work, never commit. Suppressing an error with `??` is not permission to commit. Business logic should not swallow write failures; a failed mutation marks the transaction failed, so `commit()` thereafter returns `TransactionFailed` even if the caller defaulted the first error.

Conceptual lifecycle implementation, using accepted dunder assignment syntax:

```dewy
Transaction:type = [
    handle:DbHandle
    $__abandon__ = ():>void | DbError => rollback_unfinished(handle)
]
```

`DbHandle`, `DbError` and `rollback_unfinished` here are internal illustrative names, not a complete public implementation. The hook cannot publish. A committed transaction's internal state makes abandonment a no-op; consuming it does not mean rollback a committed handle. Rollback failure quarantines the connection; it is not returned to the pool as clean. Timing and combining simultaneous failures follow the eventual D40 decision. Do not bake round5's withdrawn `CleanupError` representation into this API.

Cancellation before the commit boundary yields Canceled with no publication; after durable publication commit reports success. An ambiguous I/O failure yields CommitUnknown. The critical publication phase cannot detach into an unowned task. D40's eventual grace rule must reconcile a noninterruptible backend call with honest completion reporting; this remains an implementation gate. External effects such as charging a card or sending mail are not atomic with a local transaction. Store a durable outbox record in tx, then deliver after commit with an idempotency key.

### 7. Schema evolution

An open compares persistent schema fingerprints, stable logical IDs, format versions and required feature support. A mismatch is `SchemaMismatch` with a readable diff, never a fresh empty database. Editing a source type changes the desired schema, not stored bytes. A type-name rename alone does not change persistent collection/field identity.

`migration(old new)` builds an ordinary plan. Safe field additions with constant defaults or optional none can be generated, but applying even a safe plan is explicit and recorded. Adding a required field without a default needs a total `transform`. Rename maps old and new field selectors; never infer a rename from similar names or positions. Removing a field requires an explicit `.remove(selector)` in the migration; removing it from the type is insufficient. A transform that omits an old field must also declare its removal or rename. Type changes require checked conversion for every old value. Failed conversion names the record key and leaves the old database intact.

Migration validates unique/reference/refinement constraints over the complete prospective state. Renames preserve stable field IDs; removals retire IDs rather than reuse them. The migration chain records old/new schema hashes and a hash of the immutable plan/transform artifact; replayed or edited history is refused. Old definitions and applied migration programs stay versioned with the application. Application version and storage-schema version are separate.

SQLite v1 applies a migration under exclusive schema coordination in one transaction, with a rebuilt shadow collection/index when required, then atomically records the new schema. Large rebuilds require space and can pause writers for a long time. Other processes must close stale handles; failed exclusivity is a typed error. Online dual-schema expansion/backfill/cutover is future work, not a false promise that arbitrary renames are zero downtime. Back up first; a down-migration is not automatically possible after information loss. Restoring a verified backup to a *new path* is recovery; it never overwrites an active file.

### 8. Portability and storage durability

SQLite is the first adapter, not the semantic definition. Enable WAL where supported and durable synchronous settings; do not silently choose a lossy durability mode for speed. Commit success means the configured durable boundary completed, subject to the storage device/filesystem honoring it. Detect unsupported environments; do not claim power-loss guarantees in a browser's memory store or on unreliable network filesystem locking. `memory(schema)` is explicitly volatile and uses the same SQLite adapter with a single keeper connection and serialized access; independent `:memory:` connections would accidentally create different stores.

`backup(path)` produces a consistent database snapshot through the backend backup mechanism, validates it, syncs the file and containing directory as appropriate, and publishes it atomically without overwriting an existing backup. It returns void or a failure. Never copy a live SQLite main file without its WAL coordination. Cancellation/failure leaves no success-named partial backup. Record the backup's schema, logical database identity, backend format and snapshot marker in its metadata. A backup preserves reference identity; a deliberate fork into a new identity requires an export/import policy.

A pure-Dewy engine later needs crash recovery, a transaction log or shadow paging, checksums, page allocation/freeing, a buffer/cache policy, ordered indexes, codecs and collation versions, MVCC or equivalent snapshots, serializable validation/locking, process coordination, a costed planner, exact operators, transactional reference/unique enforcement, compaction, online consistent backup, corruption handling and fault-injection tests. Full-text needs tokenization, postings, scoring and transactional maintenance. This is an engine project; changing the adapter does not supply those parts.

Portable: record encodings at the logical export boundary, query results and ordering, reference and unique semantics, transaction outcomes, schema transformations, and the accepted native operator subset. Not portable: SQLite binary backups, query-plan text, physical index layout, extension SQL, execution speed, backend search ranking, process-count limits or undocumented collation. Exact semantic mismatch means a local implementation or UnsupportedFeature, never a close-enough result. A native implementation first earns backend conformance against a reference evaluator before becoming the default.

## Use-case checklist

| Required case | Concrete surface and contract | Specimen / acceptance scenario |
|---|---|---|
| Typed storage/loading | Ordinary T; insert returns Ref<T>; get returns T/none/errors; nested values decoded with validation | 01, 12; malformed disk value cannot become T |
| Lookup by key | Selected required key; indexed exact lookup; reference checks identity/incarnation | 02; wrong store reference fails, reused key never resurrects old reference |
| Filtering | Actual Dewy bool lambdas; indexed supported subset, warned residual path | 03, 14; compare interpreter and planned results |
| Sorting | Stable ordinary key functions; ties retain deterministic source order | 01, 13; adding an index must not change output order |
| Paging | page(size= after=), typed opaque continuation bound to query parameters, schema, order and snapshot identity | 13; equal sort keys, deletions and concurrent inserts |
| Unique and secondary indexes | unique/index descriptors; compound projections; no implicit index creation on a hot query | 03, 04; competing inserts yield one winner |
| One-to-many | Ref<Author> field, reverse index, ordinary equality filter | 03; referenced author cannot disappear |
| Many-to-many | Link record holding two typed refs; composite unique membership key | 03; one membership cannot be duplicated |
| Following relations | get(ref) or batched follow(selector), one explicit snapshot; no I/O member access | 03; explain proves no N+1 round trips |
| Count/sum/grouping | count; exact sum(selector); group_by then map key/items aggregates | 04; empty sum=0, empty min/max=none, nullable values explicit |
| Bulk update/delete | Atomic selection + pure transform, count; filtered delete refuses dangling refs | 01; late constraint error changes nothing |
| Transactions/isolation | begin, explicit commit, abandonment rollback; serializable writes | 02; transfer failure, write skew, phantom conflict |
| Concurrency/tasks | Shared store; task-local transactions; bounded writer admission; no automatic retries | 05; two units reserved at most twice |
| Migrations | Old/new schemas, explicit rename/remove, typed transform and atomic application | 06; failed uniqueness validation preserves old schema/data |
| Durability/backup | Durable success; consistent backend backup, no existing-target overwrite | 12, 13; kill around each publication boundary |
| Full-text | Full-text descriptor; search(text) treats input as literal words; typed result | 07; quotes/operators are data, no grammar injection |
| Interactive tools | Native REPL imports same schema and library; read-only default tool; explain before execution | 09; typo reported as ordinary type/member error |
| Tests | memory(schema), same codecs/constraints/planner; separate durable fault tests | 08; rollback/idempotency/abandonment assertions |

`page.next` is an opaque typed continuation, not a row number or an SQL fragment. The query's order has a unique primary-key tie breaker. Offset paging remains expressible as ordinary skipping but warns about O(offset) work and live-data drift; it is not the default. Unbound live-store continuation semantics need careful revision: a query execution has a snapshot but a subsequent call otherwise gets a fresh one. Program 13 avoids ambiguity with an explicit pinned snapshot. Serialized tokens are untrusted; validate identity, version, bounds and integrity before use, and reject an expired snapshot instead of quietly continuing from newer data.

Full-text returns records containing `.record`, `.score`, `.excerpt`; excerpts are text, not trusted HTML. Default semantics are intersection of literal tokenized terms; empty input returns no hits. A selected language/tokenizer is part of schema and changing it rebuilds the index. SQLite FTS5 is the initial implementation, with library tokenization/escaping and bound query values. Full-text operators and search-specific errors must not become SQL injection routes. Score/ranking portability is explicitly backend-specific; exact parity needs a pinned shared tokenizer and ranker. Multilingual segmentation, stemming, accent matching and future phrase/boolean search require typed options or constructors, not a new text mini-language.

Grouping keys use ordinary equality and hashing. Group iteration order is the first occurrence of each key in the input order. Group items preserve their input order; aggregate pushdown is valid only when it preserves exact values and ordering where observable. `sum` over int is exact, count is int, empty groups are absent, empty input yields zero groups. Float reductions use Dewy's fixed order unless the user opts into a permitted relaxation; SQL SUM may not replace them blindly. Grouping/aggregation may require a full scan despite an index; that warning is useful, not a reason to reject the query.

The CLI in 09 is intentionally a narrow safe search tool. The full trusted developer REPL uses ordinary imports and the same queries, not a new database language: `:type query`, `query.explain`, `query.all`. The current REPL cannot safely claim long-lived resource ownership it has not implemented; until that gap closes, use a whole helper function per input. A REPL undo restores bindings, never undoes a committed external write. Read-only handles have no mutation members; a writable REPL handle is an explicit acquisition. Never run a remote user's Dewy source to implement an admin filter.

## SQL interop: first-class, secondary

```dewy
import p"@lib/std/sql.dewy" as sql
Balance:type = [name:string balance:int64]
main = () => {
    let conn = sql.sqlite(p"legacy.sqlite" read_only=true) or_throw
    let statement = conn.prepare<Balance>(
        "SELECT name, balance FROM accounts WHERE balance < :ceiling ORDER BY name"
    ) or_throw
    let rows = statement.all([ceiling=0]) or_throw
    loop row in rows { printl"{row.name}: {row.balance}" }
}
```

SQL connection, statement, continuation and transaction are ordinary typed resource owners. SQL tx uses the same explicit commit/abandonment rules; it offers prepare/execute on its connection rather than native collections. Parameters are a separately supplied record. Missing/extra bindings are errors; an SQL value cannot be pasted into query structure. `prepare<T>` accepts compile-time constant SQL only. An interpolated runtime string does not become a statement just because it is called SQL. Constant text and parameter shapes can be checked without opening a database at compile time; the actual existing schema and data are checked at prepare/decode time. Claiming compile-time verification of an arbitrary live file would be false.

Rows map named columns to ordinary record fields. NULL requires optional fields; integers must fit, blobs remain bytes, invalid text is rejected. An unexpected column shape gives StatementShapeError; an invalid value gives RowDecodeError. No annotation is an unchecked assertion of the server schema. The parameter API binds via SQLite's prepared statement interface; identifiers cannot be parameters. Dynamic identifiers are selected from checked schema descriptors or a closed whitelist assembled as structured SQL nodes, not through string concatenation. This advanced builder is future surface, not necessary for program 11.

`prepare` supports one statement; DDL or statements with no row shape use `prepare`'s void-result form and `execute(params)`, returning affected-row information where the backend supplies it. SQL transactions can issue backend-specific operations explicitly. Native collections are library-owned; writing their physical tables through the SQL path can bypass native invariants, so a native store does not expose a writable raw connection. An arbitrary legacy file stays a legacy file until explicit validated import. Parameters prevent injection of data; they do not make malicious *program source* or intentionally destructive constant SQL safe.

## What the alternatives teach us

This is a design comparison, not a performance benchmark. Strengths/limitations below are my assessment of the linked documented contracts; no claim of independent user testing. Sources consulted for this round on 2026-11-12.

| Prior art | Keep | Avoid / mismatch with this brief | Primary source |
|---|---|---|---|
| SQLite | Embedded deployment, transactional file, mature planner, consistent backup | SQL and backend storage typing should stay below the native API; single-writer contention remains real | [Isolation](https://sqlite.org/isolation.html), [planning](https://sqlite.org/queryplanner.html), [backup](https://sqlite.org/backup.html) |
| Datomic | Immutable database values and explicit history; automatic index choice | Fact/Datalog thinking and mandatory history are extra concepts for a tiny game save; history is not free | [Overview](https://docs.datomic.com/), [filters](https://docs.datomic.com/reference/filters.html) |
| XTDB | Distinguishes valid time from recorded time; handles changing document shapes | Bitemporal semantics deserve an explicit feature, not an unexplained timestamp on every row; another query language does not meet native-only ergonomics | [Time](https://docs.xtdb.com/about/time-in-xtdb.html), [SQL quickstart](https://docs.xtdb.com/quickstart/sql-overview.html) |
| EdgeDB / Gel | Typed links, composable data selection, recorded migrations | EdgeQL and a separate schema language are still languages to learn; generated removal plans require scrutiny | [EdgeQL](https://docs.geldata.com/learn/edgeql), [migrations](https://docs.geldata.com/reference/datamodel/migrations) |
| Prisma | Typed generated client and explicit grouped transactions | Generated client/contracts add a workflow; callback success publication differs from explicit commit; plain domain values are preferable | [Transactions](https://www.prisma.io/docs/orm/fundamentals/transactions) |
| LINQ | One host language for query composition; expression representation makes translation possible | Expression-tree-supported operations differ from executable delegates; provider restrictions surface late unless checked | [LINQ](https://learn.microsoft.com/en-us/dotnet/csharp/linq/), [expression trees](https://learn.microsoft.com/en-us/dotnet/csharp/advanced-topics/expression-trees/), [EF client evaluation](https://learn.microsoft.com/en-us/ef/core/querying/client-eval) |
| Django ORM | Excellent CRUD, relationships and application workflow | Model instances mix domain data with persistence; field lookup mini-strings and loading choices remain knowledge a user must acquire | [Queries](https://docs.djangoproject.com/en/5.2/topics/db/queries/) |
| ActiveRecord | Concise scopes, relations and common operations | Saveable model objects, implicit loading and string fragments make local value behavior less apparent | [Query interface](https://guides.rubyonrails.org/active_record_querying.html) |
| Rust Diesel | Static checking and explicit schema/query structure | Query type machinery and model/schema setup are substantial for tiny applications | [Getting started](https://diesel.rs/guides/getting-started) |
| Rust SeaORM | Typed entities, async access, relations and migration/test support | Separate entity/active-model concepts are more ceremony than ordinary values plus explicit transforms | [Documentation](https://www.sea-ql.org/SeaORM/docs/index/) |
| Kotlin Exposed | Type-safe host-language DSL with explicit transaction boundary | Its DSL intentionally mirrors SQL, and a second DAO surface complicates choosing the idiom | [About Exposed](https://www.jetbrains.com/help/exposed/about.html) |
| IndexedDB | Native structured values, keys, indexes, upgrade transactions | Low-level continuation/index selection and event-tied transaction lifecycle are burdens a Dewy facade should absorb | [Specification](https://w3c.github.io/IndexedDB/) |
| Firebase / Firestore | Convenient document query composition and indexed access | Access-pattern restrictions and index requirements are visible; native joins/ordinary host-language predicates are not its query model | [Queries](https://firebase.google.com/docs/firestore/query-data/queries) |
| MongoDB | Embedded/nested documents, optional schema validation, flexible evolution | Flexible stored shape is not a typed application's migration policy; embedding vs references still needs design | [Data modeling](https://www.mongodb.com/docs/manual/data-modeling/) |
| Pony ORM | Comprehensions and lambdas feel native; translates generator queries | Translation is an actual special facility, not normal Python generator execution; database entities differ from independent values | [Queries](https://docs.ponyorm.org/queries.html) |
| Redis | Direct data-structure operations; explicit optimistic coordination | Queued transactions do not offer ordinary rollback semantics; memory/durability tradeoffs cannot silently become the default | [Transactions](https://redis.io/docs/latest/develop/using-commands/transactions/) |

The reference peers in dogfood are Python sqlite3 **and** Django, Go database/sql, Rust Diesel (with SeaORM noted where it helps), TypeScript Prisma, and Swift GRDB. Swift is represented by a real SQLite toolkit rather than by a pretend language-standard ORM. [Python sqlite3](https://docs.python.org/3/library/sqlite3.html), [Go transactions](https://go.dev/doc/database/execute-transactions), [GRDB](https://github.com/groue/GRDB.swift).

## Considered and rejected

- **SQL with renamed keywords.** A Dewy-shaped SELECT builder still asks people to think in tables, column aliases and join clauses. Ordinary record transforms and typed references are the primary idiom; relational algebra can remain internal.
- **A database superclass or auto-saving records.** Violates the ordinary value story, hides I/O and makes independent copies surprising.
- **One JSON blob per record as the entire design.** Easy prototype but does not supply typed indexing, uniqueness, exact numeric queries or efficient relations. Nested encoding remains useful where appropriate.
- **All predicates overloaded on symbolic proxy fields.** Cannot preserve ordinary bool control flow; it is not a solution to the brief's exact expression.
- **Comprehension rewriting by an undocumented compiler pass.** Violates the no-magic requirement. General callable/iteration facilities need their own explicit contract first.
- **Reject every untranslatable pure predicate.** Unnecessarily blocks ordinary code. A correct local fallback plus actionable cost warning and optional runtime bound is useful.
- **Silently evaluate any callback locally.** Effects, errors, limits and ordering make that unsafe; purity and totality are required at planned boundaries.
- **Automatic indexes for every observed query.** Unbounded persistent storage/write amplification and schema changes caused by a read. Primary, unique and reference indexes are schema duties; other indexes are explicit, with suggested fixes.
- **Automatic schema sync on open.** A field rename can be data loss. Open reports a diff; migrations are concrete inspectable programs.
- **Automatic commit on success or callback retry.** Conflicts with accepted abandonment; cannot distinguish an intended early return or an external effect. Explicit commit and stable request IDs cover the application intent.
- **SQL snapshot isolation labeled serializable.** Read/write transactions need writer admission before reads or complete conflict validation. Two doctors going off call is the necessary counterexample.
- **Full-text query strings in the native path.** SQL injection prevention alone does not prevent search grammar injection. Literal input is literal; richer search needs typed composition.
- **Universal backend equivalence.** Port the logical contracts; identify ranking, physical plans and backup formats as backend-specific.
- **Everything immediately, including replicated offline databases.** Eventual consistency, replicated conflict resolution, temporal history, authorization policy, vector/geospatial indexes and distributed transactions are genuine later use cases. They need explicit contracts, not an 'all databases' marketing claim. The core keeps room for them without promising they exist.

## Implementation acceptance gates before this can be called complete

1. A non-database library demonstrates the general callable mechanism, including captured values, typed helpers, pure branches and unsupported operations. A separate test proves comprehension lowering or the documentation keeps it explicitly a scan.
2. A reference evaluator and each adapter agree on values, ordering, multiplicity, optionals, exact integers/rationals, Unicode and failure behavior. Test short circuit and callbacks with hidden effects; reject what is not safe to move.
3. Indexed predicate on N rows decodes K candidates rather than N; compare instruction counts and actual backend plans, not elapsed time on this desktop. A parameterized plan must not compile separately for every runtime threshold.
4. Transactions pass rollback on every exit, poisoned-tx refusal, cancellation/commit boundary, ambiguous commit, unique races, reference reuse, write-skew and phantom tests.
5. Migration crash/failure tests preserve either complete old or complete new state, including schema metadata and indexes. Backup recovery is tested by opening and checking a separately restored database.
6. Query planning is demand-driven. For a normalized expression of E nodes and I relevant indexes, use indexed field/prefix lookup rather than E×all-schema scans; target O(E + I) candidate construction plus bounded plan selection. No unbounded join-order search; capped dynamic programming or greedy planning reports its fallback. Index maintenance is O(log N) per affected entry plus encoded value cost. Compile-time cost must be measured on the flagship instruction-count panel before landing; nothing in this paper claims that gate passed.
