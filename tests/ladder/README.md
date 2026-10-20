# Acceptance ladder

To add a program, create `NN_name/` with `design.dewy` (the intended design surface) and `core.dewy` (today's accepted dialect, which must pass).
Add an independent stdlib-only oracle to `references.py` and run `python3 tests/ladder/references.py --write` to produce `expected.out`.
Map it to its ROADMAP.md milestone in `ladder.json`; `python3 -m tools.core ladder` prints the scoreboard and `--update-ratchet` records design passes.
