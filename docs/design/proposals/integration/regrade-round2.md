# Dogfood3 re-check against the round-2 design (2026-11-07)

The 16 dogfood3 programs, rewritten against the updated design, are in `dogfood3-fixed/`. Each file's header lists its grades, what was fixed and its floor. None of the 16 reached 5 on every axis before this round, so all 16 were redone. Everything is paper, as before.

Axes: O obvious, D discoverable, C concise, S safe by default, X complete, Y consistent.

| # | Program | O | D | C | S | X | Y | Before | Remaining floor |
|---|---|---|---|---|---|---|---|---|---|
| 01 | File sync | 5 | 5 | 5 | 5 | **4** | 5 | 5 4 4 5 3 3 | No file-change notification (library) |
| 02 | Adventure | 5 | **4** | 5 | 5 | 5 | 5 | 5 4 4 5 5 5 | A key proof through a literal-union key type: no error message points a beginner to it yet (a checker fix-it) |
| 03 | Budget | 5 | 5 | **4** | **4** | **4** | 5 | 4 4 4 3 3 3 | Money until user-declared base dimensions (named next item); hand-wrapping each reader error with its line number (deferred error-context item) |
| 04 | Rhythm | 5 | 5 | 5 | 5 | 5 | 5 | 4 4 5 5 3 4 | |
| 05 | Job API | 5 | 5 | 5 | 5 | **4** | 5 | 4 4 4 5 3 5 | No HTTP server (library) |
| 06 | Markdown | 5 | **4** | **4** | **4** | **4** | 5 | 5 4 4 4 4 5 | Regex replace with groups; HTML-safe text and URL escaping (library and the injection-safety design); the decided `$capture` on a local helper |
| 07 | Sensor logger | 5 | 5 | 5 | 5 | **4** | 5 | 4 3 4 4 3 3 | No serial-port API (library) |
| 08 | Tower defense | 5 | 5 | 5 | 5 | **4** | 5 | 5 5 5 5 4 5 | No deque or priority queue (library) |
| 09 | Shell | 5 | 5 | **4** | 5 | **4** | 5 | 3 3 4 4 2 4 | No string builder; no library `which`; terminal hand-off for `fg`/`bg` (library; semantics stated) |
| 10 | iCalendar | 5 | 5 | 5 | 5 | **4** | 5 | 3 3 3 5 2 3 | Char boundary at or before n bytes; VTIMEZONE emission (library) |
| 11 | Prime sieve | 5 | 5 | 5 | 5 | 5 | 5 | 5 4 5 5 5 4 | (`isqrt` is assumed in the math prelude) |
| 12 | Settings form | 5 | 5 | 5 | 5 | 5 | 5 | 4 3 4 4 3 3 | |
| 13 | Countdown | 5 | 5 | 5 | 5 | 5 | 5 | 4 4 4 5 4 4 | |
| 14 | Dice bot | 5 | 5 | 5 | 5 | **4** | 5 | 4 3 4 4 4 3 | Regex capture groups (library) |
| 15 | Thumbnailer | 5 | 5 | 5 | 5 | **4** | 5 | 4 4 4 5 4 4 | Image decoding and resizing (library) |
| 16 | Unit CLI | 5 | 5 | 5 | 5 | 5 | 5 | 3 3 4 5 2 3 | |

**Averages, before → after:**

| Axis | Before | After |
|---|---|---|
| O | 4.1 | 5.0 |
| D | 3.7 | 4.9 |
| C | 4.1 | 4.8 |
| S | 4.6 | 4.9 |
| X | 3.4 | 4.4 |
| Y | 3.8 | 5.0 |

**What's left below 5:**
- Every remaining X is a library that doesn't exist yet: HTTP, file-change notification, serial ports, images, regex groups, a deque, a string builder, `which`, VTIMEZONE and byte boundaries.
- The other points below 5 are two deferred cross-cutting items, a checker fix-it, and money as the named next item.
- No design problem from dogfood3 remains open.

**Deferred on purpose:** these are listed in `changes-2.md` and weren't requested as must-fixes.
- error context, `x or_throw Bad[line=n]` or a library `with_context` (03);
- binding a `??` fallback's failure, `?? (e) => …` (02, 01);
- the literal-union fix-it for dictionary keys (02);
- a member call on `T?` (15 now narrows instead).
