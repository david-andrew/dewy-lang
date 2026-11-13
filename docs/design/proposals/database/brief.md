# Design round: a Dewy-native database interface

You are designing one piece of the Dewy language's standard library. Read-only everywhere except `~/dev/tmp/par10/db/`. The checkout is `~/dev/dewy-lang`.

## The direction (David, who owns the language, 2026-11-12)

> I've always hated SQL syntax for doing things, and honestly I'd love it if dewy had its own straightforward interface into databases, using just pure functions/methods/dewy features, and not inheriting any of the cruft from SQL/relational-databases. Perhaps to start it could be backed by sqlite, but honestly I think the long term goal would be for a pure dewy-based database solution, supporting the major use cases of databases, all in one unified language/interface, plugging into dewy's safety and interface and typing flexibility, and so forth. The blissful "leaves programmers wanting for nothing" version of databases if you will.

> I'm not saying we can't also support using SQL style databases in dewy in a first-class way ... I think the dewy version would be emphasized over any SQL support (and the dewy version would be considered idiomatic), but yes both would exist.

## Read first

- `docs/LANGUAGE.md`: "Records and collections", "Errors as values", "Loops, text and optional values" (comprehensions, `loop … in`), "Files, paths and processes", "Parallel CPU work" and channels, "Directives".
- `docs/design/decisions.md` (all batches; batch 9 has the database direction, `$__abandon__ = () => …` for values whose cleanup discards work such as a transaction rolling back, dunder metatags as assigned functions, `()` unscoped vs `{}` scoped blocks).
- `docs/design/proposals/cleanup/round5.md` (transactions: rollback on drop, explicit `tx.commit()`), D40/D41 in `docs/design/open_decisions.md`.
- Before proposing any name, search `resources/discussion_points.md` (David's notes; use `/usr/bin/grep`).

## What to settle in round 1

- **The use cases** a database must cover, as a checklist: storing and loading typed records; lookup by key; filtering, sorting, paging; indexes (unique, secondary); relations between records (one-to-many, many-to-many) and following them; aggregates (count, sum, group by); updates and deletes in bulk; transactions and isolation; concurrency from tasks; schema evolution when a record type changes (migrations); durability and backups; full-text search; querying from a REPL or tool; testing with an in-memory store.
- **Prior art**, briefly, for what each gets right and wrong: SQLite, Datomic/XTDB, EdgeDB, Prisma, LINQ, Django ORM, ActiveRecord, Rust Diesel/SeaORM, Kotlin Exposed, IndexedDB, Firebase, MongoDB, Pony ORM, Redis.
- **The design:** records are ordinary Dewy types; queries are ordinary Dewy expressions (comprehensions, `loop`, methods, lambdas) that the library (comptime-backed, no compiler magic) turns into efficient plans, with indexes used automatically and a warning when a query can't use one (David: remove friction even if the compiler works harder; warn on performance cost). Show how a filter like `[loop a in db.accounts if a.balance <? 0 a]` or `db.accounts.where((a) => a.balance <? 0)` becomes an indexed query, and what happens with a lambda the planner can't translate. Typed results, no stringly-typed queries, no injection possible. Schema changes: what happens when a field is added, renamed or removed. Transactions: `$__abandon__` rollback with explicit commit.
- **SQL interop:** how a first-class SQL connection looks (typed rows, parameters never interpolated) as the secondary path.
- **Backends:** SQLite-backed first; what a pure-Dewy engine later needs; what is portable between them.

## Deliverables (under `~/dev/tmp/par10/db/`)

1. `round1.md`: lead with five minimal examples (define and open; insert and load; query with an index; relation; transaction), each in its enclosing function, then the rules, then each use case, then SQL interop, then what you considered and rejected.
2. `programs/NN_name.dewy`: at least 12 realistic programs (a todo app; a bank ledger with transfers; a blog with posts, authors and tags; analytics with group-by; an inventory with concurrent tasks; a schema change; full-text search; a test with an in-memory store; a CLI that queries interactively; an import from CSV; reading an existing SQLite file through the SQL path; a game save store).
3. `dogfood.md`: grade each program 1–5 on obvious, discoverable, concise, safe by default and complete, against Python (sqlite3 and an ORM), Go, Rust, TypeScript (Prisma) and Swift, citing the line for every score under 5. Be honest; independent graders will check. Iterate (`round2.md`, `round3.md`, new files) while anything under 5 is fixable.
4. `names.txt`: every new name as a short usage line, for a cold read.
5. `summary.md`: the final rules on one page, floors and why, new names.

Dewy conventions: arguments are space-separated, `=?` is equality, `@f` is a function handle, `$name` is a metatag, `or_throw` forwards an error, `??` substitutes a default; value-returning zero-argument calls drop `()`, void ones keep it; strings are formatted only with `fmt` (`printl'total {fmt'.2f'x}'`); imports use `.dewy` files; dunder metatags are assigned functions (`$__drop__ = () => …`). Unsafety is opt-in. No model names in files. Budget: about three hours.
