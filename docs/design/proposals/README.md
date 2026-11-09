# Design proposals and their provenance

These folders record, for each design decision, what was considered and why one option won.

1. **Open questions** for David are in [../open_decisions.md](../open_decisions.md).
   - It is self-contained, with examples, and sorted by priority.
   - It lists only open items: an answered item is removed in the same commit that records the decision.
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
| [time/](time/) | Time, dates, clocks and calendars | v5 drafted; core accepted 2026-11-06 (decisions.md); v6 applies it and `../time.md` is the current spec. `units-and-format-round1.md` is the latest round. Open: D29, D31, D32, D34–D37. |
| [concurrency/stage4/](concurrency/stage4/) | Queues, `select`, failed sends | `Unsent`, `spsc` and `mpmc` accepted 2026-11-01. `select` and `[concurrent …]` are superseded by `unified/`. |
| [concurrency/unified/](concurrency/unified/) | One `parallel` surface | Proposals v3–v5, names, and `select` v6 (type-matched arms, source-qualified members, `$named`, `race`, `merged`): round 7 and round 11 texts, dogfood, and six reviews. Open (D4). |
| [concurrency/big-picture/](concurrency/big-picture/) | The 80/20 performance ladder and prior art | Synthesis and reviews. Open (D4). |
| [packages/](packages/) | Vendoring and package metadata | Synthesis and reviews. Open: D21a–b. |
| [string-shapes/](string-shapes/) | Compile-time string shapes, action names, stale handles, UI | Round 1; round 2 is shared with UI (`ui/round2-with-string-shapes.md`). Open (D11). |
| [ui/](ui/) | Clay-style declarative UI | Rounds 1 and 2 (`round2-with-string-shapes.md`, shared with D11). Open (D28). |
| [bulletproof/](bulletproof/) | Opt-out tags for `$bulletproof` | Rounds 2–3: unsafety is opted into; round 3 is current. Open (D10). |
| [compile-speed/](compile-speed/) | Compile-speed redesigns | Fact state round 1: measured bound below the bar; nothing adopted. |
| [integration/](integration/) | Cross-design conventions, dogfood passes, consistency audits, name tests (2026-11-07) | Shared rules for D4, D10, D11, D22, D28, D29, D31, D33–D37 |
| [naming-style/](naming-style/) | snake_case vs Julia-style joined names | Study, second opinion, guessability tests. Open (D38). |

The earliest time-design inputs were built from David's private notes and are kept outside the repo.
