# Revision round, 2026-11-07: shared context for the revisers

Dewy (repo /var/home/david/dev/dewy-lang) is a general-purpose language: Python-like ease, C-like speed, safe by default with danger opt-in. Read the repo's AGENTS.md and docs/GOALS.md.

## The bar (owner, verbatim)
"Dewy needs to be the gold standard for anything a programmer might be doing. It needs to leave nothing to be desired. It needs to cover all the bases. Programmers should never think 'it would be nice if the language let me do x', dewy should just already support doing x, and in the most intuitive/straightforward/easily discoverable way possible... if you're not getting full marks, the design needs more iteration before something can come to me for a decision."
Also his test: (1) is the common 80% path easy, ergonomic and fast? (2) when it doesn't fit, is adjusting straightforward? If both pass, decide the semantics yourself; only syntax and names go to him.

## Inputs, all in ~/dev/tmp/dogfood-1107/
- parallel-safety.md, with programs in a/ (dogfood: parallel and safety)
- time-ui.md, with programs in b/ (dogfood: time, units, UI and strings)
- consistency-audit.md (17 cross-design findings)
- parallel-v3-soundness.md (soundness of v3's block form, `?? void` and `select`)
Read every finding that touches your topic, in all four files.

## Cross-cutting rules every reviser follows (so parallel revisions don't diverge)
- **A metatag never changes a function's result type.** A stricter mode makes the lax call a compile error that points to a stricter function (e.g. `today` → `strict_today`). The only standing exception is `$explicit_allocation_failure`, which David decided earlier; keep it and flag it.
- **One literal-validation mechanism:** `string<shape=@f>` (string-shapes proposal), extended as needed. No `$check_constant`, `$error_if` or other parallel mechanism in user-facing design. If time or format literals need more than shapes give (several parameters, folding to a record), the UI/strings reviser extends shapes and the others use that.
- **No compiler-known naming conventions** (e.g. `Name<option=N>` meaning a type named `Name_option_N`). Use ordinary type parameters or values.
- **Keyword vocabulary:** numeric rounding is `rounding=` with values `'nearest_even' 'nearest_away' 'floor' 'ceil' 'toward_zero'` everywhere, `round` included. Program-wide settings are `$program.*`, set once in the main file. Scoped tuning is `$parallel.*`. Names already picked by cold reads (docs/design/open_decisions.md D4, D10, and proposals/*/names*.md) stand unless a dogfood finding breaks them.
- **Formatting (decided by the owner):** `{x:.2f}` is NOT valid Dewy. The only formatter is `fmt`, a higher-order function taking one pattern string; the pattern narrows the input type it accepts (a mismatch is a compile error). Write `printl'result is {fmt'.2f'x}'`, and pre-build it idiomatically: `f0 = fmt'.2f'`. `format(x spec)` is gone too.
- **Results carry something useful.** A call that creates or starts something returns a handle; a call that writes a file or folder returns its path; no `void` or `bool` where the caller will obviously need more.
- **No legacy:** Dewy has no users, so changes replace old forms, with no migration path.

## Required in every revision
1. Fix every must-fix and should-fix finding for your topic, or say plainly why it shouldn't be fixed.
2. Re-run the dogfood: rewrite the affected programs against your revised design (put them beside your output) and re-grade every axis. Iterate until each axis is 5, or state the floor and why nothing better exists. Compile what you can (AGENTS.md has the commands; nothing may open a window or play sound).
3. List every NEW or CHANGED name with its intended meaning, as a table at the end, so it can be cold-read tested before the owner sees it. Don't present those names to the owner as final.
4. Write the replacement text for your open_decisions.md items in the file's current style: BLUF, a complete example declaring every identifier, the common path, how to adjust, the semantics taken, and only syntax or name questions for the owner, each with a recommendation. Lead with what the proposal does ("turn this on, and…"). No today-vs-proposed tables.
5. Out-of-scope bugs in today's compiler: list them at the end with a repro path; don't fix them.

Conventions: arguments space-separated; zero-argument calls drop parentheses (`now`, `.split`); `@f` is a function handle; `$name` is a metatag; `or_throw` forwards an error; `??` substitutes a default; function types grouped with `()`, e.g. `f:(int:>int)`. Bullets over paragraphs. Don't name AI models. Change nothing in the repo and don't commit: write only your output file and its programs folder.
