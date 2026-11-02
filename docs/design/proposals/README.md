# Design proposals and their provenance

How a language-design question becomes a decision:

1. **Open questions** for David live in [../open_decisions.md](../open_decisions.md).
   - It is self-contained, uses examples, and is sorted by priority.
   - Answered items get an inline `> Answered <date>: …` note until the next cleanup.
2. **Proposals and reviews** behind each question live here, one folder per topic.
   - Every file names the model or person who wrote it, and files are never rewritten after the fact.
   - A newer round is a new file, so the history shows how the design moved.
3. **Accepted decisions** go into [../decisions.md](../decisions.md), or into the topic's design doc, with the date.
   - Each accepted entry links back to the proposal folder it came from.

| Folder | Topic | Status |
|---|---|---|
| [time/](time/) | Time, dates, clocks and calendars | v5 drafted. David settled the 1977 epoch, integer ticks and `now` without parentheses. The rest is open (open_decisions D6–D9, D15). |
| [concurrency/stage4/](concurrency/stage4/) | Queues, `select`, failed sends (round 1) | `Unsent`, `spsc` and `mpmc` accepted 2026-11-01. `select` and `[concurrent …]` are superseded by `unified/`. |
| [concurrency/unified/](concurrency/unified/) | One `parallel` surface | Proposal v2 plus reviews. Open (D4, C1–C11). |
| [concurrency/big-picture/](concurrency/big-picture/) | The 80/20 performance ladder and prior art | Synthesis plus the three reviews. Open (D4, B1–B8). |
| [bulletproof/](bulletproof/) | Opt-out tags for `$bulletproof` | Open (D10). |

Authors, by file name:
- `astra*` is GPT Astra;
- `sol*` is GPT Sol;
- `grok*` is Grok;
- `claude*`, `opus*`, `synthesis*`, `proposal*` and `time-design-v4/v5` are Claude Opus;
- `decision-digest` is Sol plus a light Opus pass.

The earliest time-design inputs (`astra-design`, `sol-analysis`) worked directly from David's private notes. They are kept outside the repo.
