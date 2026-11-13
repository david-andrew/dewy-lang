# Round 2: corrections from writing the programs

This is the final contract delta to [round1.md](round1.md). The first round is preserved. `programs-r1/` preserves its initial specimens; `programs/` contains the corrected versions. These are paper programs, not compiler-verified claims. Dogfood scores refer to final program lines.

## 1. Make many-to-many an ordinary set

The original blog required `PostTag`, an extra collection and a duplicated composite key. That was unnecessary relational ceremony for a relationship with no payload. Final program 03 instead declares:

```dewy
Tag:type = [id:string label:string]
Post:type = [id:string author:database.Ref<Author> title:string body:string
    tags:set<database.Ref<Tag>>=set[]]
```

`where((p) => tag in? p.tags)` uses an automatically maintained reverse membership index. One post has many tags; a tag can belong to many posts. The set prevents duplicate memberships using its ordinary value semantics. This is a new **library storage contract**, not new syntax or a special database collection type. The SQLite adapter may implement the set in hidden edge rows, but user code never spells those rows or their joins.

For a relation with its own data, such as `Tagged[post:Ref<Post> tag:Ref<Tag> added_by:Ref<Author> added_at:Instant]`, an ordinary collection of those records is appropriate. Its key is `(m) => [m.post m.tag]`; it does not store the same key again in `id`. This replaces the first-round many-to-many checklist entry. No need for both a model framework and a join DSL.

`follow((p) => p.tags)` flattens a set of references into a query of Tag, in input-record order then the set's insertion order. A scalar reference gives one result per input; an optional reference gives T|none, retaining its source position. Cross-parent duplicates are preserved. Filtering does not remove duplicates and following is not implicitly `distinct`. Required links cannot become absent in a valid snapshot; corruption is an error. Nested reference indexes and all incarnation/target checks update in the *same transaction* as the owning value. Backends that store nested values as blobs need a transactional edge index; a SQLite FOREIGN KEY on one scalar column is insufficient.

References cannot point outside the store. The same type in two possible target collections still needs distinct domain types in this first design. Required cycles cannot be created from scratch through lookup-only references: a later identity-reservation design is needed. That real completeness limit remains, rather than adding an untested `reserve` API here.

## 2. A continuation pins the view it continues

A page from a live-store query now acquires a read snapshot; its `next` token retains a lease on that exact snapshot. Passing `after=page.next` to the same query continues that snapshot automatically. Without this rule, the first-round promise of stable default pagination was incomplete. It is not necessary to remember `snapshot` merely to get a second page. Explicit `snapshot` still groups several independent queries; program 13 exercises that use.

A token binds database identity, schema revision, recipe identity, captured values, result ordering and snapshot. A copied immutable recipe retains identity; an independently built recipe does not get to reuse an opaque token just because its printed predicate looks similar. Closed/expired snapshots produce CursorExpired; a different query/schema/store produces CursorMismatch. No silent restart and no offset disguised as a continuation. The token contains no SQL. A token received from outside the process is unsupported in v1; a durable authenticated continuation-service protocol is future work. This avoids pretending a pinned SQLite connection can survive a process restart.

For a given ordering, append unique source identities as tie breakers. After a one-to-many follow the identity is the source identity plus edge position/target incarnation. Grouping uses the group key identity. A projection keeps hidden origin identity even if it drops visible key fields. This is internal metadata, never an extra field on the user's record. If an operation cannot supply a stable identity/order, `page` is unavailable with a diagnostic; do not repeat or skip equal values.

Each page uses bounded lookahead to determine whether another page exists. `size` caps emitted items; `max_scanned` caps candidate records examined by *all* local stages, including lookahead. Exceeding it returns QueryLimit with no successful partial page and no mutation. Whole-query sorting/grouping may hit the cap before the first result. The planner cannot claim O(page size) for such plans. An expired-token policy can release abandoned long snapshots, but its timeout must be reported at acquisition; v1 local tokens live with their owners and have no secret time expiry. A deliberately closed view yields CursorExpired only at an untyped/external boundary; typed reachable later uses should be rejected by ownership checking.

Long-lived tokens retain old pages and can delay reclamation/checkpoints. Show that cost in docs/explain and release the lease when the token is no longer used. The exact lifetime/cleanup inlay depends on D40; do not promise last-use cleanup while that decision is open.

## 3. Absence is not a successful main result

`get` continues to return T|none|errors, preserving ordinary optional semantics. Required lookup uses existing operators:

```dewy
let account = tx.accounts.get(key) or_throw<error | Canceled>
    ??<none> return database.RecordMissing
```

This corrects initial programs 02, 03, 05 and the required lookups inside tests. Their callers no longer accidentally return none from `main` or mistake absence for passing an assertion. Optional reads in 12 and duplicate-request checks in 02/05 intentionally retain none. Display-only reads can print a legitimate none after forwarding real failures.

`RecordMissing` is a proposed database error, distinct from the prelude's `Missing` search exception. `reference(key)` and `replace(record)` use RecordMissing when the required row is absent. No `get` alias that panics, and no blanket `?? default` that would turn corruption into an empty account/save.

The second minimal example in round 1 should replace its `let saved` line with the required-lookup form above. The fifth example should use that form for both accounts. These are explicit corrections to the preserved examples, not a claim those initial snippets were compiled successfully. A library wrapper can express required lookup with this form; a second public lookup spelling is not necessary yet.

Program 01 now removes `args[0]`, the executable name, before parsing commands. The parallel match in 05 forwards `problem or_throw`; it does not use an ordinary return to leave a parallel body. Negative values following positional arguments were changed to named fields so juxtaposition cannot make subtraction eat an earlier argument.

## 4. A saved game must not overwrite another writer's progress

The first game-save example read state before entering tx and then blindly upserted it. A transaction around a stale value alone is not protection against lost updates. Final program 12 stores an ordinary revision field. Inside the serializable transaction it reads the current revision, rejects a mismatch with the application error StaleSave, writes revision+1, and commits. The helper returns the newly saved value so the caller retains the correct revision. A missing slot has revision 0 only at this explicit application boundary.

The program never deletes save slots; if deletion/recreation is added, a monotonic revision per slot or an incarnation must prevent ABA. A database Ref's incarnation protects references, not arbitrary application string lookups. This limit is stated, not solved by a pretend generic version field added to every domain type.

The save reports publication before requesting its separate backup. A revision-specific backup filename avoids the first draft's guaranteed existing-target failure on a second successful run. Backups and writes are separate effects: a backup failure does not imply the save rolled back. FileExists stays a real outcome, for example after restoring an older revision into a directory with its old backups.

## 5. Do not pretend an existing parser is strict

The first CSV program called `csv.from_csv<T>` and commented that it should reject malformed input. Inspection of `lib/std/csv.jo:31–79,113–115` shows a permissive quoted-field reader and header/default behavior. A comment was not validation. We do not silently change that existing API's semantics or invent a strict keyword without design.

Final program 10 imports the local [csv_products.dewy](programs/csv_products.dewy). That support program explicitly validates a strict CSV subset before beginning the database transaction: LF/CRLF, doubled quoted quotes and quoted newlines, exactly the declared header sequence, exactly four fields, nonempty ID, numeric parsing and nonnegative values. It scans bytes rather than grapheme clusters so an ASCII comma followed by a combining character is still a separator. A bare CR or unterminated quote fails. Errors have no committed prefix. Duplicate IDs are still a database uniqueness error and roll back the whole import.

The support code is a design specimen too, not a tested parser release. It deliberately does not solve huge streaming CSV imports, header aliases/reordering, a BOM, row-number diagnostics or resumable checkpoints. A strict typed CSV library would remove this ceremony. Existing permissive input can remain available explicitly; safety should not depend on mistaking it for validation. The importer is graded down on concision/discoverability/completeness, with the support lines cited. This is better than an invented 'already available' safe parser.

## 6. Clarify index and transaction invariants

Reference and uniqueness constraints are checked on every live-store mutation. Within tx, each mutating method is itself atomic; a failure poisons the whole tx and a later commit cannot publish a prefix. V1 enforces reference existence at each mutation, which explains the required-cycle construction limitation. Unique swaps that temporarily collide need one atomic bulk transform; sequential replace calls do not defer uniqueness. The transform checks the complete resulting set before publishing internally. Candidate identities are fixed at selection so changing indexed fields cannot create a Halloween-style revisit.

A query's default key order, a sorted query's stability and a follow's multiplicity are semantic obligations. An index on balance alone does not satisfy primary-key output order. If K matches need sorting, advertise O(log N + K log K), not merely O(log N + K). Competing backend plans must be tested against the same ordered reference results.

A descriptor's key selector can execute on an ordinary record to produce a key without knowing its source. But turning that selector into stable field identity for migration/optimized access needs the missing inspection facility or explicit descriptors. This is another place where claiming 'comptime handles it' would hide work. No existing compiler feature is assumed to supply callback bytecode inspection.

All stored values needed by an executed query are validated in its snapshot before being trusted. Semantic reference evaluation is over a **valid logical store**. Corrupt bytes outside a query's candidate set may remain undetected until integrity checking; a planner cannot promise identical corruption-discovery timing to a full-file scan. Both paths must refuse to yield invalid T, but index selection may change which latent corruption is encountered. State that boundary rather than pretending a read validates every disk page.

Commit outcomes are partitioned: known no publication, known durable publication, or unknown publication. A tx is consumed in all three. Only the first permits a retry without first resolving an idempotency record. The bank and inventory record request payloads as well as IDs, rejecting reuse of one ID for a different action. They do not automatically retry on Timeout/Canceled/CommitUnknown. Under a process crash, no error object is delivered; recovery checks the durable request record. This is not exactly-once delivery to an external service.

## 7. Public result contracts

Concrete error alternatives are inferred from used operations and adapter capabilities; do not replace them with an opaque 'database failed' string. The names below are proposed and untested. File I/O errors, Canceled and Timeout keep their existing language/library identities. There is no need to create database copies of them.

| Operation | Success | Additional domain failures |
|---|---|---|
| open(schema path) / memory(schema) | Typed shared store | SchemaMismatch, UnsupportedFeature, CorruptStore, DecodeError |
| get(key/ref) | T or none | ReferenceMismatch for wrong store/collection; storage/decode failures |
| reference(key) | Ref<T> | RecordMissing |
| insert(T) | Ref<T> | DuplicateKey, UniqueViolation, ReferenceMismatch, RecordMissing, invalid decoded/validated value |
| tx.replace(T) | void | RecordMissing, UniqueViolation, reference/validation failures |
| tx.put(T) | Ref<T> | Same checked constraints; insertion/replacement deliberate |
| query.update(transform) / query.delete() | int count | UniqueViolation, Referenced, reference/validation failures |
| query.all / count / sum | array<T> / int / exact accumulator type | QueryLimit when capped; decode/storage failures |
| query.page(size= after= max_scanned=) | Record with items and next | QueryLimit, CursorMismatch, CursorExpired |
| begin(timeout=) | Move-only tx | Timeout, Canceled, storage failures |
| tx.commit() / rollback() | void | TransactionFailed, CommitUnknown for commit only, storage failures; D40 combined failures unresolved |
| snapshot / close() | Read view / void | Storage failures; close never commits |
| backup(path) | void | FileExists, file/storage failures, Canceled |
| migration(old new) / describe | Typed migration plan / description string | Structural contradictions diagnosed at construction/checking |
| migrate(path plan) | void | SchemaMismatch, MigrationConflict, constraint/data/space/storage failures |
| search(text) then all/page | Hit records | UnsupportedFeature if required tokenizer/index unavailable; normal query failures |
| SQL prepare<T>(constant_text) | Typed statement | SqlError, StatementShapeError |
| SQL statement.all(params) | array<T> | SqlError, RowDecodeError; parameter mismatch diagnosed statically where possible |

This table defines operations, not an implemented closed error hierarchy. `DecodeError` covers a persisted value failing its schema validator; callers constructing T already satisfy language type obligations. Runtime external constraint violations get the specific database error. `DbError` in round 1's internal lifecycle sketch is deliberately not a new catch-all public alias.

`open` defaults to creating a missing file only for writable handles; `read_only=true` implies no creation, and `create=false` explicitly requires an existing file. Program 06 uses create=false so a migration typo cannot silently create and migrate an empty store. Opening a backup read-only cannot create it. In the first round these defaults were not fully stated.

## 8. Compilation and names remain real floors

The highest-priority unresolved issue is still the exact efficient comprehension. General typed callable inspection would make `.where` possible, but it does not expose a caller's loop body to an iterator. The compiler document rules out AST-generation macros; this proposal does not reverse it. Until a general mechanism is designed, the honest implementation has ordinary eager comprehensions as scans with performance warnings, and cannot pass the strict 'both forms indexed, library-only' acceptance condition.

A second round cannot turn that into a 5 by restating the ambition. The possible next technical task is a narrowly scoped general-language design/pilot that proves an ordinary library can inspect a typed callable and that separate iteration fusion preserves Dewy semantics. If that direction is rejected, the native API must expose explicit typed predicate objects or accept scanning. Both would revise the brief's ergonomics and should be reported to the coordinator, not slipped into implementation.

Names have been checked against `resources/discussion_points.md` (especially 2341–2355, 2400–2430 and 2525–2565); no database API vocabulary there decides these spellings. [names.txt](names.txt) is a usage-only cold-read inventory. It has **not** been judged by three independent readers. This design sub-agent did not delegate; no database name should enter open_decisions.md described as cold-tested. `where` vs existing collection `filter`, `follow`'s scalar/set cardinality, `reference`, `RecordMissing`, and `max_scanned` are particularly worth testing. No new grammar, keyword or metatag is proposed by the database surface itself.
