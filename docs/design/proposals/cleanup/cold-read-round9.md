# Cold read 1126: Cleanup round 9 names and compile-error messages

Readers: three fresh readers with no context, labelled a, b and c.

Brief: [brief.md]. Source: `docs/design/proposals/cleanup/round9.md` and `programs-r9/{01,05,08}_*.md`.

Note on "leftover": `round9.md` did not pick a single spelling yet ("a way for a failure type to mark itself a leftover (one option is a family, as `UndoFailed` is)"), so we tested two natural family candidates: `Leftover` and `CleanupLeftover`.

## Part 1: Names

| Spelling | a | b | c | Verdict |
|---|---|---|---|---|
| `FileReader` | right, 5 | right, 5 | right, 5 | **pass** |
| `FileWriter` | right, 5 | right, 5 | right, 5 | **pass** |
| `SocketReader` | right, 5 | right, 5 | right, 5 | **pass** |
| `finish_sending` | right, 4 | right, 4 | right, 4 | **pass** |
| `drop(x)` | right, 4 | right, 4 | right, 4 | **pass** (note: readers expect cleanup/destruction, not necessarily a return value; clear once paired with `or_throw`) |
| `ErrorStack` | partial (unwind trace), 3 | partial (cause chain), 4 | right (multi-error/cleanup), 4 | **borderline** (2/3 read as nested cause-chain/traceback rather than flat sibling failures; order unclear) |
| `Leftover` | partial (unreleased resource), 3 | wrong (unread buffer), 2 | wrong (unconsumed stream/parser bytes), 3 | **fail** |
| `CleanupLeftover` | partial (failed/undone cleanup), 2 | partial (owed cleanup work), 2 | partial (secondary cleanup error), 3 | **fail** (low confidence, none read "warning-only/discardable stray artifact") |

## Part 2: Compile-error messages

| Message | a | b | c | Verdict |
|---|---|---|---|---|
| Error 1 (`FileWriter` open on `write_bytes` failure) | right, 5 | right, 5 | right, 5 | **pass** (all 3 diagnosed skipped flush/close on error path and replaced trailing close with `defer out.close() or_throw`) |
| Error 2 (`Socket` unfinished sending side) | right, 4 | right, 4 | right, 4 | **pass** (all 3 got it; `b` & `c` wrote exact `let replies = conn.finish_sending() or_throw` + `replies.read_line()`, though `c` wondered if `conn` still needed `close()`) |
| Error 3 (generator dropped mid-stream holding `FileWriter`) | right, 4 | right, 4 | right, 5 | **pass** (all 3 diagnosed mid-stream drop of frame's `FileWriter` and wrote `defer drop(rows) or_throw`) |

## Suggested replacements / tweaks

- **Leftover failure family** (`Leftover` and `CleanupLeftover` both failed): bare `Leftover` reads as unconsumed parser/buffer bytes; `CleanupLeftover` reads ambiguously as any secondary cleanup failure. Candidates for a follow-up cold read:
  - `BestEffortCleanup` or `OptionalCleanup` (signals warning-only / discardable)
  - `StrayArtifact` or `ResidualArtifact` (signals a stray temp file/dir left behind)
  - `MinorCleanupFailed` or `DiscardableCleanup` (signals severity/checker behavior directly, parallel to `UndoFailed`)
- **`ErrorStack`** (borderline, consistent with D42 Q4): if flat sibling-error ordering matters more than matching David's term, `ErrorList` or `ErrorBundle` avoids the "nested traceback / LIFO stack" reading.
- **Error 2 wording tweak** (optional): adding `(consumes conn)` to `let replies = conn.finish_sending() or_throw` prevents readers from wondering whether `conn.close()` is still needed afterward.
