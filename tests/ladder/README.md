# Acceptance ladder

To add a program, create `NN_name/` with `design.dewy` (the intended design surface) and, where today's dialect can express it, `core.dewy` (which must pass).
Add an independent stdlib-only oracle to `references.py` (tier 1, programs 01–31), `references_tier2.py` (32–63), `references_tier3.py` (64–94) or `references_tier4.py` (95 onward, tier-4 flagships registered by directory name; their modules sit beside `design.dewy`) and run it with `--write` to produce `expected.out`.
Map it to its ROADMAP.md milestone in `ladder.json`, with a one-line acceptance statement as `note`; `python3 -m tools.core ladder` prints the scoreboard and `--update-ratchet` records design passes.

- **Input.** A `stdin.txt` beside the sources is fed to both versions; otherwise stdin is empty.
- **Programs that must be rejected.** Give the entry `"expect": {"kind": "compile-error", "diagnostic": REGEX, "line": N}` and mark the offending line with a `# REJECT` comment just above it.
  The design passes only when `check` fails with an error whose message matches REGEX (case-insensitive) at line N of `design.dewy` (`line` is optional).
  Unsupported-feature errors ("not implemented yet", "does not yet support", "unknown directive") and parse errors are not rejections, and a successful check is reported as wrongly accepted.
  Such programs have no `expected.out` and usually no `core.dewy`.
- **Test results.** `"expect": {"kind": "tests"}` also runs the design's `$test` functions with `dewy-core test --json` and compares each test's status, the counts, the exit status, a failed test's output (`failure_stdout`, `message_contains`) and main's output (`ordinary_stdout`) with `expected-tests.json`.
- **Open programs.** When acceptance depends on an unsettled design question, add `"open": QUESTION`.
  The program still runs and is listed with its question, but it is excluded from the design counts and can't enter `design_passing`; a passing open program is only an executable control.
  Remove `open` once the question is settled and the program exercises the answer.
- **Tiers.** `tiers` in `ladder.json` groups milestones for the scoreboard.
