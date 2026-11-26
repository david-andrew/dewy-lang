# Cold read 1126 (round 10): `ErrorList` vs `ErrorStack`, `TempRemoveFailed`, `finish`

Readers: three fresh readers labeled `a`, `b`, and `c` ([guesses-r10-a.md], [guesses-r10-b.md], [guesses-r10-c.md]).
Brief: [brief-r10.md]. Source: `docs/design/proposals/cleanup/round10.md`.

| Spelling | a | b | c | Verdict |
|---|---|---|---|---|
| `ErrorList` | right (multiple errors reported together), 4 | right (multiple errors reported at once), 4 | right (list of multiple accumulated errors), 4 | **pass (3/3, 4/4/4)** — clear winner over `ErrorStack` |
| `ErrorStack` | wrong (call-stack trace / wrapped cause chain), 3 | wrong (nested LIFO chain / call stack), 3 | partial (layered errors or call-stack trace), 3 | **fail (0/3 clean, 3/3/3)** — consistently read as traceback, cause chain, or LIFO |
| `TempRemoveFailed` | right (removing temp file/dir failed on cleanup), 3 | right (deleting temp file/resource failed), 4 | right (removing temp file/dir failed on cleanup), 4 | **pass (3/3, 3/4/4)** |
| `x.finish()` | right (completes pending work, finalizes so not used further), 3 | right (completes/finalizes, flushes/closes/seals), 3 | right (completes/finalizes in-progress object, returns completion error), 3 | **pass (3/3, 3/3/3)** — moderate confidence reflects generality of the bare name without a receiver type |

## Notes

- **`ErrorList` vs `ErrorStack`**: decisive split. All three readers read `ErrorList` as a flat collection of separate failures reported together (confidence 4/4/4), and all three read `ErrorStack` as a call-stack trace, wrapped cause chain, or LIFO stack (confidence 3/3/3).
- **`TempRemoveFailed`**: unambiguous across all three readers; no replacement needed.
- **`finish`**: all three readers understood completion/finalization of pending work and ending use of `x`; no replacement needed.
