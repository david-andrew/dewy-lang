# Independent review and regrade: Dewy-native database, rounds 1–3

You are checking a Dewy standard-library design before its owner, David, sees it. You did not write it. Read-only everywhere except your two output files in `~/dev/tmp/par10/db/`: `review-round3.md` and `regrade-round3.md`. The checkout is `~/dev/dewy-lang`.

The design: `round1.md`–`round3.md`, `summary.md`, `programs/` (the final versions; `programs-r1/` is history), `names.txt`, `dogfood.md` (read the author's grades only after fixing yours). The brief: `brief.md`. Binding context: `docs/design/decisions.md` (batch 9: the database direction, `$__abandon__`, dunder hooks as assigned functions, `()`/`{}` scoping), D40 in `docs/design/open_decisions.md`, `docs/LANGUAGE.md`.

## review-round3.md

Findings with severity (must-fix / should-fix / note), rule or program line, concrete scenario, suggested fix. Check in particular:
- Is it truly better than SQL plus an ORM for the common cases (a todo app, a ledger, a blog with tags, analytics)? Where is it more verbose or more surprising than Prisma, Django ORM, LINQ or ActiveRecord? Count the concepts a newcomer must learn for a first program.
- Query semantics: do index choices ever change results; are optionals, equality and ordering consistent with Dewy; what happens with an untranslatable lambda (silent full scan?), and is the warning enough?
- Transactions and concurrency: correct use of `$__abandon__` and `commit()`; retries; `CommitUnknown`; tasks sharing a store.
- Migrations: can data be lost silently; is a rename distinguishable from remove-plus-add?
- SQL path: is injection impossible by construction; are typed rows checked?
- The language dependency the author found (indexed lambdas and comprehensions need a general "inspect a callable as data" mechanism): is that the right diagnosis? Could existing comptime features or a smaller library contract get the common cases (e.g. selectors like `.balance <? 0` built from field references) without it?
- Names: any that will clearly mislead.

## regrade-round3.md

Grade each program in `programs/` 1–5 on obvious, discoverable, concise, safe by default and complete against Python (sqlite3 and an ORM), Go, Rust, TypeScript (Prisma) and Swift, citing the line for every score under 5. Then list differences of 2 or more from the author.

Final message: must-fix count with one line each, your floor and programs at it, and your verdict on the callable-inspection dependency in two sentences. Budget about 90 minutes.
