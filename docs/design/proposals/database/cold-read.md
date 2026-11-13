# Cold read: database

Three readers saw the shuffled usage lines without the proposal. Confidence is on a 1–5 scale. The full lines and original guesses follow; reader labels are A, B and C.

## Lines shown

```dewy
related_field = () => database.related(P.author A.email)
reference_record = <S>(store:S id:string) => store.accounts.reference(id)
indexed = () => database.collection<Account>(key=A.id indexes=[database.index(A.balance)])
select_rows = <S>(store:S) => store.accounts.where(A.balance.lt(0))
read_view = <S>(store:S) => store.snapshot
read_rows = <Q>(query:Q) => query.all
remove_rows = <Q>(query:Q) => query.delete()
discard = <T>(tx:T) => tx.rollback()
publish = <T>(tx:T) => tx.commit()
at_least = (balance:int) => A.balance.ge(balance)
related_values = <R>(row:R) => row.related
open_readonly = () => database.open(schema p"app.db" read_only=true)
limited_page = <Q>(query:Q) => query.page(size=20 max_scanned=1000 max_bytes=8000000 timeout=2s)
equal = (id:string) => A.id.eq(id)
open_file = () => database.open(schema p"app.db")
field_record = () => database.fields_of<Account>
reference_type = (value:database.Ref<Account>) => value
source_record = <R>(row:R) => row.record
substring = (text:string) => N.title.contains(text)
compound_three = () => database.tuple(A.enabled A.balance A.id)
page_rows = <P>(page:P) => page.items
open_existing = () => database.open(schema p"app.db" create=false)
unique_value = () => database.unique(A.email)
close_store = <S>(store:S) => store.close()
page_continuation = <P>(page:P) => page.next
transaction = <S>(store:S) => store.begin(timeout=2s)
definition = () => database.collection<Account>(key=A.id)
count_rows = <Q>(query:Q) => query.count
compound_two = () => database.tuple(S.day S.id)
required_record = <S>(store:S id:string) => store.accounts.require(id)
optional_record = <S>(store:S id:string) => store.accounts.get(id)
next_page = <Q R>(query:Q page:R) => query.page(size=20 after=page.next)
put_record = <T>(tx:T account:Account) => tx.accounts.put(account)
open_memory = () => database.memory(schema)
conjunction = (lo:int hi:int) => database.all_of([A.balance.ge(lo) A.balance.lt(hi)])
plan = <Q>(query:Q) => query.explain
add_record = <S>(store:S account:Account) => store.accounts.insert(account)
patch_rows = <Q>(query:Q) => query.update([done=true])
first_page = <Q>(query:Q) => query.page(size=20)
close_view = <S>(view:S) => view.close()
replace_record = <T>(tx:T account:Account) => tx.accounts.replace(account)
related_records = <Q>(query:Q) => query.include([author=P.author tags=P.tags editor=P.editor])
order_rows = <Q>(query:Q) => query.sorted(key=A.balance reverse=true)
less = (balance:int) => A.balance.lt(balance)
unique_present = () => database.unique(A.email present_only=true)
```

## Reader A

1 | Declares or describes a relationship between Post’s author field and Account’s email (e.g. for joins or referential links). It defines metadata only; it does not read or write stored rows by itself. It can fail if the fields are not a valid relation pairing. | 3
2 | Looks up an account in the store by string id and returns a lightweight reference to that row rather than loading the full record. It reads the database. It can fail if no row exists for that id. | 4
3 | Defines the accounts collection for type Account with primary key id and a secondary index on balance. It is schema configuration; it does not read or write user data. It can fail if the key or index specification is invalid. | 5
4 | Builds a read query over accounts filtered to rows whose balance is less than zero. It prepares a read; actual I/O happens when the query is run. It can fail when executed (e.g. store closed or I/O error). | 5
5 | Opens a consistent read-only snapshot (view) of the current store state for queries that should not see later writes. It reads metadata and may read data when used. It can fail if the store is not open or snapshot creation fails. | 4
6 | Runs the query and returns every matching row in one result (no paging). It reads the database. It can fail on I/O, limits, or timeouts depending on query and store settings. | 5
7 | Deletes all rows that match the query. It writes the database. It can fail on constraints, I/O, or if the query cannot be applied. | 5
8 | Aborts the transaction and discards all uncommitted changes in it. It affects transactional state (a kind of write to session state, not committed data). It can fail if the transaction is already finished or invalid. | 5
9 | Commits the transaction so its changes become durable in the store. It writes the database. It can fail on validation, conflicts, I/O, or timeout. | 5
10 | Builds a filter expression meaning “account balance is greater than or equal to the given integer.” It does not touch the database until used in a query. Ordinary comparison issues might surface when evaluated. | 5
11 | Accesses related records or nested relation data attached to this row (e.g. loaded associations). It reads when the relation is resolved. It can fail if the relation is missing, not loaded, or broken. | 3
12 | Opens the on-disk database at app.db with the given schema in read-only mode. Subsequent operations through it are reads only. It can fail if the file is missing, corrupt, locked, or schema mismatch. | 5
13 | Fetches one page of query results with size 20 and explicit scan/byte/time limits. It reads the database. It can fail or stop early when limits or timeout are hit. | 5
14 | Builds a filter expression meaning “account id equals the given string.” It does not read or write the database by itself. Failure is only when used in an invalid context. | 5
15 | Opens the on-disk database at app.db with the schema for normal read-write use. It enables both reads and writes. It can fail on file, lock, or schema errors. | 5
16 | Returns metadata describing the fields of the Account record type (names, types, selectors). It introspects schema; it does not read stored rows. It can fail if Account is not a known record type. | 4
17 | Returns the reference value unchanged (identity on a Ref<Account>). It does not read or write the database. It does not fail under ordinary use. | 3
18 | Extracts the underlying Account (or generic record) from a row wrapper that may carry extra query state. It uses already-loaded or resolvable row data (read). It can fail if the record cannot be materialized. | 4
19 | Builds a filter expression meaning “note title contains the given text substring.” It does not access the database until used in a query. | 5
20 | Forms a composite key or multi-field descriptor from enabled, balance, and id (e.g. for indexes or tuple comparisons). It is a schema/expression helper; no direct I/O. Invalid field combinations could fail at definition time. | 4
21 | Returns the list of rows (items) in an already-fetched result page. It reads from in-memory page data, not a new full scan. It can fail if the page handle is invalid. | 5
22 | Opens app.db only if it already exists (does not create a new file). It allows reads and writes on an existing store. It can fail if the file does not exist or cannot be opened. | 5
23 | Declares a unique constraint or unique index on the email field. It is schema metadata; no row read/write by itself. It can fail if the constraint conflicts with the collection definition. | 4
24 | Closes the store and releases resources; no further operations on it. It does not commit data changes by itself. It can fail if already closed or cleanup errors occur. | 5
25 | Returns a continuation continuation or token from the current page used to request the next page. It is derived from prior read results. It can fail if the page is invalid or there is no next page. | 4
26 | Starts a new read-write transaction on the store with a two-second timeout. It sets up for writes (and reads within the tx). It can fail if a tx cannot be started or timeout elapses during begin. | 5
27 | Defines the accounts collection for Account with id as the key, without extra indexes. Schema only; no data read/write. Can fail on invalid collection definition. | 5
28 | Counts how many rows match the query without returning the rows themselves. It reads the database. It can fail on I/O or query errors. | 5
29 | Forms a two-field tuple from Sale’s day and id fields (composite key or ordering). Expression/schema helper; no direct database I/O. | 4
30 | Loads the account with the given id and requires it to exist. It reads the database. It fails (as an ordinary failure value) if the id is not found. | 5
31 | Loads the account by id if present, otherwise returns an optional or failure-valued absence. It reads the database. It can represent “not found” as a failure/optional without throwing. | 5
32 | Requests the next page of query results (size 20) starting after the continuation from a previous page. It reads the database. It can fail on I/O, invalid continuation, or limits. | 5
33 | Inserts or puts an account record inside the transaction (upsert-like put semantics). It writes pending until commit. It can fail on constraint violations or invalid record. | 4
34 | Creates or opens an in-memory database with the given schema (no file). It supports reads and writes in RAM. It can fail on invalid schema or resource limits. | 5
35 | Combines multiple predicates with logical AND (all must hold). Filter composition only until used in a query. | 5
36 | Returns a human- or machine-readable explanation of how the query would be executed (plan). It reads planner/metadata; may touch catalog. It can fail if the query cannot be planned. | 5
37 | Inserts a new account record into the store immediately (outside an explicit transaction wrapper). It writes the database. It can fail on duplicate key, constraints, or I/O. | 5
38 | Updates all rows matching the query, setting field done to true (bulk patch). It writes the database. It can fail on constraints, I/O, or invalid updates. | 5
39 | Fetches the first page of query results with page size 20. It reads the database. It can fail on I/O or query errors. | 5
40 | Closes a snapshot or read view and releases its resources. It does not write user data. It can fail if already closed. | 5
41 | Replaces an existing account row (by key) with the provided record inside the transaction. It writes (pending until commit). It can fail if the row does not exist or constraints fail. | 4
42 | Extends the query to eagerly load or join related author, tags, and editor records via Post field links. It reads additional related data when the query runs. It can fail if relations or ids are invalid. | 4
43 | Reorders the query results by balance descending. It affects read order when executed. It can fail if the sort key is invalid for the collection. | 5
44 | Builds a filter expression meaning “balance is less than the given integer.” No direct database access until used in a query. | 5
45 | Declares uniqueness on email but only among rows where email is present (e.g. ignore null/missing for uniqueness). Schema constraint definition. It can fail if incompatible with other indexes or the collection. | 3

## Reader B

related_field = () => database.related(P.author A.email) | Declares a relationship joining Post.author to Account.email so related records can be looked up along that pair of fields. Schema/query setup, not a database read or write; should not fail. | confidence 3
reference_record = <S>(store:S id:string) => store.accounts.reference(id) | Builds a typed reference to the Account with that id without loading the row. Does not read or write the database; missing ids probably do not fail here. | confidence 3
indexed = () => database.collection<Account>(key=A.id indexes=[database.index(A.balance)]) | Defines an Account collection keyed by id with a secondary index on balance. Schema description, not a read or write; should not fail. | confidence 4
select_rows = <S>(store:S) => store.accounts.where(A.balance.lt(0)) | Builds a query for accounts whose balance is less than zero. Query construction only, no read or write yet; should not fail. | confidence 4
read_view = <S>(store:S) => store.snapshot | Opens a consistent read-only snapshot of the store. Reads (pins a view); does not write; can fail if the store is closed or unavailable. | confidence 4
read_rows = <Q>(query:Q) => query.all | Executes the query and returns every matching row. Reads; does not write; can fail on database or resource errors. | confidence 5
remove_rows = <Q>(query:Q) => query.delete() | Deletes every row matching the query. Writes; can fail on constraints, permissions, or database errors. | confidence 5
discard = <T>(tx:T) => tx.rollback() | Aborts the transaction and undoes its uncommitted changes. Writes in the sense of discarding a write set; can fail if the transaction is already finished. | confidence 4
publish = <T>(tx:T) => tx.commit() | Commits the transaction so its changes become durable and visible. Writes; can fail on conflicts, constraints, or timeout. | confidence 5
at_least = (balance:int) => A.balance.ge(balance) | Builds a predicate that Account.balance is greater than or equal to the given value. No database read or write; should not fail. | confidence 5
related_values = <R>(row:R) => row.related | Returns the related/joined values attached to this row. Reads already-fetched related data (or lazy-loads); can fail if related data is missing or unloaded. | confidence 3
open_readonly = () => database.open(schema p"app.db" read_only=true) | Opens the database file at app.db for reading only. Opens a store (neither mutating data nor querying rows); can fail if the file is missing or unreadable. | confidence 5
limited_page = <Q>(query:Q) => query.page(size=20 max_scanned=1000 max_bytes=8000000 timeout=2s) | Fetches one page of up to 20 rows, aborting if scan/byte/time limits are exceeded. Reads; does not write; can fail or stop early on those limits. | confidence 4
equal = (id:string) => A.id.eq(id) | Builds a predicate that Account.id equals the given string. No database read or write; should not fail. | confidence 5
open_file = () => database.open(schema p"app.db") | Opens (or creates) the database file at app.db with the given schema. Opens a store; can fail on I/O or schema mismatch. | confidence 5
field_record = () => database.fields_of<Account> | Returns the field-selector bundle for the Account type (the analog of A). No database read or write; should not fail. | confidence 4
reference_type = (value:database.Ref<Account>) => value | The library type Ref<Account> is a handle to an Account row by identity, not the loaded record. Typing only; no read or write; does not fail. | confidence 4
source_record = <R>(row:R) => row.record | Returns the stored record value wrapped by this result row. No extra database access if the row is already loaded; should not fail. | confidence 4
substring = (text:string) => N.title.contains(text) | Builds a predicate that Note.title contains the given substring. No database read or write; should not fail. | confidence 5
compound_three = () => database.tuple(A.enabled A.balance A.id) | Builds a three-field compound (enabled, balance, id) for keys, indexes, or ordering. Schema/query helper; no read or write; should not fail. | confidence 4
page_rows = <P>(page:P) => page.items | Returns the records on this result page. Data already read with the page; no further read or write; should not fail. | confidence 5
open_existing = () => database.open(schema p"app.db" create=false) | Opens the existing database file at app.db and will not create it. Opens a store; can fail if the file does not exist. | confidence 5
unique_value = () => database.unique(A.email) | Declares a uniqueness constraint or unique index on Account.email. Schema; no read or write of rows; should not fail at this call. | confidence 4
close_store = <S>(store:S) => store.close() | Closes the open database so it can no longer be used. Neither a row read nor a row write; can fail if already closed or on flush errors. | confidence 4
page_continuation = <P>(page:P) => page.next | Returns the continuation token or continuation for the next page of results. No extra read or write; may be empty at the end rather than failing. | confidence 4
transaction = <S>(store:S) => store.begin(timeout=2s) | Starts a transaction that must finish within two seconds. Neither a row read nor write yet; can fail if the store cannot begin a transaction. | confidence 5
definition = () => database.collection<Account>(key=A.id) | Defines an Account collection whose primary key is id. Schema; no read or write; should not fail. | confidence 5
count_rows = <Q>(query:Q) => query.count | Returns how many rows match the query. Reads; does not write; can fail on database errors. | confidence 5
compound_two = () => database.tuple(S.day S.id) | Builds a two-field compound (day, id), likely a composite key. Schema/query helper; no read or write; should not fail. | confidence 4
required_record = <S>(store:S id:string) => store.accounts.require(id) | Loads the Account with that id and treats absence as failure. Reads; does not write; fails (as a value) if not found or on database errors. | confidence 5
optional_record = <S>(store:S id:string) => store.accounts.get(id) | Loads the Account with that id, returning a missing/optional result if it is not there. Reads; does not write; not-found is a value, other database errors can still fail. | confidence 5
next_page = <Q R>(query:Q page:R) => query.page(size=20 after=page.next) | Fetches the next page of up to 20 rows after the given page’s continuation. Reads; does not write; can fail on database errors. | confidence 5
put_record = <T>(tx:T account:Account) => tx.accounts.put(account) | Writes the account into the collection, inserting or replacing by key. Writes; can fail on constraints or transaction errors. | confidence 4
open_memory = () => database.memory(schema) | Opens an in-memory database with the given schema. Opens a store; should rarely fail except on invalid schema. | confidence 5
conjunction = (lo:int hi:int) => database.all_of([A.balance.ge(lo) A.balance.lt(hi)]) | Combines predicates with AND: balance in [lo, hi). No database read or write; should not fail. | confidence 5
plan = <Q>(query:Q) => query.explain | Returns the query plan (how the database would execute the query) without fetching rows. Reads planner metadata; does not write; can fail if the query is invalid. | confidence 4
add_record = <S>(store:S account:Account) => store.accounts.insert(account) | Inserts a new Account; does not replace an existing key. Writes; can fail on duplicate key or constraints. | confidence 5
patch_rows = <Q>(query:Q) => query.update([done=true]) | Updates matching rows, setting done to true. Writes; can fail on constraints or database errors. | confidence 5
first_page = <Q>(query:Q) => query.page(size=20) | Fetches the first page of up to 20 matching rows. Reads; does not write; can fail on database errors. | confidence 5
close_view = <S>(view:S) => view.close() | Closes a snapshot/view so it no longer pins storage. Neither a row read nor write; can fail if already closed. | confidence 4
replace_record = <T>(tx:T account:Account) => tx.accounts.replace(account) | Replaces an existing Account with this one by key; does not insert if missing. Writes; can fail if the row is absent or on constraints. | confidence 4
related_records = <Q>(query:Q) => query.include([author=P.author tags=P.tags editor=P.editor]) | Extends the query to also load related author, tags, and editor along those fields. Query construction (related reads happen when executed); should not fail here. | confidence 4
order_rows = <Q>(query:Q) => query.sorted(key=A.balance reverse=true) | Orders the query by balance descending. Query construction; no read or write yet; should not fail. | confidence 5
less = (balance:int) => A.balance.lt(balance) | Builds a predicate that Account.balance is less than the given value. No database read or write; should not fail. | confidence 5
unique_present = () => database.unique(A.email present_only=true) | Declares uniqueness on Account.email only among rows where email is present (nulls/absent excluded). Schema; no row read or write; should not fail at this call. | confidence 4

## Reader C

related_field | Returns the record related through the author reference on a post, using the author's email; reads the database and can fail if the relation cannot be followed. | 3
reference_record | Returns a reference to the account with the given id without loading it; does not read the database and cannot fail on a missing row. | 3
indexed | Defines a collection of accounts keyed by id with an index on balance; a schema declaration, neither reads nor writes data, and can fail only if the definition is invalid. | 4
select_rows | Returns the accounts whose balance is below zero, as a query; reads the database when run, and the query itself cannot fail. | 4
read_view | Returns a snapshot of the store, a consistent read-only view; reads the database and cannot fail. | 3
read_rows | Returns all rows of the query, reading them from the database; can fail on a read error. | 4
remove_rows | Deletes every row matched by the query; writes the database and can fail. | 4
discard | Rolls back the transaction, discarding its changes; writes (undoes) and can fail. | 4
publish | Commits the transaction, making its changes durable; writes the database and can fail, for example on a conflict. | 5
at_least | Builds a condition that the balance is at least the given amount; neither reads nor writes, cannot fail. | 4
related_values | Returns the related record of a row, a value looked up through the row's relation; reads the database and can fail. | 3
open_readonly | Opens the app.db file in read-only mode; reads the file, cannot write, and can fail if the file is missing or unreadable. | 5
limited_page | Returns one page of at most 20 rows, with limits on scanned rows, bytes and a 2 second timeout; reads the database and can fail on timeout or limit. | 4
equal | Builds a condition that the id equals the given value; neither reads nor writes, cannot fail. | 5
open_file | Opens the app.db file, creating it if needed; reads and possibly writes the file, and can fail. | 4
field_record | Returns the field metadata of the Account type; no database access, cannot fail. | 3
reference_type | Identity function on a value of type reference to Account; no database access. | 3
source_record | Returns the underlying record of a row; reads the database and can fail. | 2
substring | Builds a condition that a note's title contains the given text; neither reads nor writes, cannot fail. | 5
compound_three | Builds a tuple of the enabled, balance and id fields for use as a compound key or index; no database access, cannot fail. | 4
page_rows | Returns the items of a page of results; no database access, cannot fail. | 4
open_existing | Opens the app.db file, failing if it does not exist; reads the file, cannot create it, and can fail. | 5
unique_value | Declares a uniqueness constraint on the email field; a schema declaration, neither reads nor writes data, can fail if invalid. | 3
close_store | Closes the open store; releases the database and can fail. | 4
page_continuation | Returns the continuation for the next page after this page; no database access, cannot fail. | 4
transaction | Starts a transaction on the store with a 2 second timeout; writes or locks the database and can fail, for example on timeout. | 5
definition | Defines the collection of accounts keyed by id; a schema declaration, neither reads nor writes data. | 4
count_rows | Returns the number of rows matched by the query; reads the database and can fail. | 5
compound_two | Builds a tuple of the day and id fields; no database access, cannot fail. | 4
required_record | Returns the account with the given id, failing if none exists; reads the database and can fail on a missing row. | 4
optional_record | Returns the account with the given id if present, otherwise nothing; reads the database and can fail on a read error. | 4
next_page | Returns the page of results after the given page's continuation, 20 rows at a time; reads the database and can fail. | 4
put_record | Stores the account in the transaction, inserting or replacing it by key; writes and can fail. | 4
open_memory | Opens an in-memory database with the schema; writes nothing to disk and can fail. | 4
conjunction | Builds a condition that the balance is at least lo and below hi; neither reads nor writes, cannot fail. | 5
plan | Returns the query's execution plan without running it; no data read or write, can fail. | 4
add_record | Inserts a new account into the store, failing if the key already exists; writes and can fail. | 5
patch_rows | Sets done to true on every row matched by the query; writes and can fail. | 4
first_page | Returns the first page of up to 20 rows from the query; reads the database and can fail. | 5
close_view | Closes the snapshot view; releases it and cannot fail on the database. | 3
replace_record | Overwrites the stored account with this one in the transaction, failing if none exists; writes and can fail. | 4
related_records | Returns the query with the author, tags and editor relations loaded alongside each row; reads the database and can fail. | 3
order_rows | Sorts the query's rows by balance, highest first; neither reads nor writes until run, cannot fail itself. | 4
less | Builds a condition that the balance is below the given amount; neither reads nor writes, cannot fail. | 5
unique_present | Declares a uniqueness constraint on email that only applies to present values; a schema declaration, neither reads nor writes data, can fail if invalid. | 3

## Result and current scope

The 45 core lines conveyed their broad role except database.related(P.author A.email): readers A and B took it as defining a relationship or join; C expected a related-record fetch. The intended operation builds a field selector through an existing reference without I/O. No replacement spelling has been cold-read. unique(... present_only=true) and store.accounts.reference(id) drew low-confidence readings; B and C also missed the latter's existence check. Guesses about hidden reads in row.record / row.related and the meaning of timeout are not confirmations of those contracts. The read covers these 45 lines, not the additional release modules or every error name in names.txt.
