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
| [scope-blocks/](scope-blocks/) | Ctrl-C, task groups and protection as blocks that are the caller's code (`inline`, `inline with`) | Rounds 1–4, dogfood per round, three regrades, three reviews, marker cold reads; summary.md is the final rules. Not taken (batch 8): Ctrl-C is redesigned as an event source handled in parallel. |
| [signals/](signals/) | Ctrl-C and other signals as event sources handled in parallel with the work | Rounds 1–4, two regrades, a review, a cold read; summary.md is the final rules. Open (D4 Q4). |
| [runtime-settings/](runtime-settings/) | Settings chosen by a run-time value (one entry file, a function per environment) | Rounds 1–6, dogfood per round, independent regrades and a review; summary.md is the final rules. Open (D4 Q7). |
| [array-literals/](array-literals/) | `;`, separator levels, nested literals vs n-D arrays | Rounds 1–2 and a review; separators decided (batch 6). Open (D39). |
| [cleanup/](cleanup/) | Cleanup timing, visible function exits and whether `defer` stays | Rounds 1–7 and reviews; `summary-round7.md` is current. Explicit consuming close / inner block alternatives and competing `defer` recommendations are in D40; failure combination is D42. |
| [errors/](errors/) | Combining failures and where they came from | Rounds 1–4: the earlier `ErrorGroup` proposal (superseded). `combined/`: David's design (`e1 and e2` typed `E1 & E2`, `as`, the error stack), rounds 1–4, two independent reviews, cold read. Open (D42). |
| [database/](database/) | Native typed storage, selectors, transactions and SQL interoperability | Round 4 is current; descriptor v1 and future-lambda comparison. Core cold read flags `related` for renaming. Open (D43). |
| [function-inspection/](function-inspection/) | Compile-time typed function descriptions with original execution as fallback | Rounds 1–3 and review; database-filter pilot only, broader consumers deferred. Shared-budget must-fix recorded; names have not been cold-read. Open (D43 Q2). |

The earliest time-design inputs were built from David's private notes and are kept outside the repo.
