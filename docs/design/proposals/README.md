# Design proposals and their provenance

These folders record, for each design decision, what was considered and why one option won.

1. **Open questions** for David are in [../open_decisions.md](../open_decisions.md).
   - It is self-contained, with examples, and sorted by priority.
   - Answers are marked inline until the next cleanup.
2. **Proposals and reviews** behind each question live here, one folder per topic.
   - They hold the options considered, the arguments for and against each, the prior art, and the reasoning.
   - Old rounds are kept, never rewritten; a new round gets a new file. That way the history shows how the design moved.
3. **Accepted decisions** go into [../decisions.md](../decisions.md), or into the topic's design doc. Each is recorded as David's decision, with:
   - the date;
   - the alternatives considered;
   - the deciding reasons;
   - a link to the proposal folder.

| Folder | Topic | Status |
|---|---|---|
| [time/](time/) | Time, dates, clocks and calendars | v5 drafted. Settled: the 1977 epoch, integer ticks and `now` without parentheses. The rest is open (open_decisions D6–D9, D15). |
| [concurrency/stage4/](concurrency/stage4/) | Queues, `select`, failed sends | `Unsent`, `spsc` and `mpmc` accepted 2026-11-01. `select` and `[concurrent …]` are superseded by `unified/`. |
| [concurrency/unified/](concurrency/unified/) | One `parallel` surface | Proposal v2 and reviews. Open (D4, C1–C11). |
| [concurrency/big-picture/](concurrency/big-picture/) | The 80/20 performance ladder and prior art | Synthesis and reviews. Open (D4, B1–B8). |
| [bulletproof/](bulletproof/) | Opt-out tags for `$bulletproof` | Open (D10). |

The earliest time-design inputs were built from David's private notes and are kept outside the repo.
