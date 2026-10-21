# Working on Dewy

Dewy is a general-purpose language: Python-like ease, C-like speed, safe by
default with danger opt-in. [docs/GOALS.md](docs/GOALS.md) is the contract;
[docs/design/](docs/design/) holds the detailed design; [ROADMAP.md](ROADMAP.md)
is the single work queue. This file is how we work. Keep it short.

## Layout

| Path | What |
|---|---|
| `compiler/` | The compiler (Jo for now; Dewy will self-host later) |
| `lib/` | Standard and game libraries |
| `stage0/`, `bootstrap/` | C seed compiler and the seed frontend |
| `tests/` | Test suites |
| `examples/`, `bench/` | Example programs; runtime benchmark kernels with C counterparts |
| `tools/` | `tools/core.py` (build/test CLI), `tools/dewy` (launcher), `tools/compiler/` (build, gates, fuzz) |
| `docs/` | Goals, language guide, development guide, design specs |
| `editors/vscode/`, `site/` | Editor extension; website (still describes the old implementation) |

## Commands

```sh
python3 -m tools.core test --quick        # ~25 s smoke: every compiler edit
python3 -m tools.core test -k WORDS        # focused tests
python3 -m tools.core test                 # full suite (~3 min): end of a batch
python3 -m tools.core --bootstrap test     # independent C bootstrap + full suite
./tools/dewy FILE.dewy                     # run a program (rebuilds the compiler if needed)
```

## Rules

1. **Progress means capability toward GOALS**, measured by the acceptance
   ladder and the north-star numbers in ROADMAP.md. Commit counts, test counts and
   evidence volume are not progress.
2. **Gates are automated; prose is not a gate.**
   - Per commit: focused tests plus the quick suite when the compiler or
     libraries change, and the speed gate (once it exists). Doc-only commits
     need nothing.
   - Per batch, before merging to the main line: the full suite, the
     independent bootstrap and a fixed-point check.
   - Don't land on a red master CI unless the landing is the fix.
   - Nightly: fuzzing and cross-target runs.
3. **The commit message is the record.**
   - Never add evidence JSON, timing logs, audit reports or status paragraphs
     to the tree.
   - Update `docs/LANGUAGE.md` only when user-visible behavior changes, and
     only the section concerned.
   - Report rejected experiments in one line to the coordinator. Don't
     commit them.
4. **Performance work must earn its slot.**
   - Target an item near the top of a fresh profile, with a plausible gain of
     ≥3% on a north-star workload (or ≥1.5× on a named kernel), or a
     simplification.
   - Measure the upper bound before building anything.
   - Time-box it. One failed pilot ends the idea family.
   - Do not polish sub-percent wins.
   - Gate compile speed on load-independent critical-path instructions; take
     wall-clock numbers only on a quiet pinned machine or a CI runner.
5. **Stay in scope.**
   - Every task states its acceptance criteria, owned files, non-goals and
     budget.
   - Put discoveries outside the scope in your final report; don't act on
     them.
   - If the budget runs out, stop and report what you learned.
6. **Surface and semantics belong to David.**
   - Implementing what the design docs already specify (docs/design, and
     `git show archive/master-pre-restart:site/reference/src/...`) is not a new
     decision: just do it. Accepted designs live in docs/design (design is not
     evidence).
   - Only genuinely new syntax, spellings, keywords, members, or changes to
     established semantics need his approval. Note them in your report; the
     coordinator batches them. Each question carries a recommended answer,
     what it unblocks, and whether it's reversible; reversible ones are
     implemented provisionally and flagged.
   - Natural extensions clearly implied by the design proceed, and get
     reported.
   - Internal representations are ours to choose.
7. **Avoid shared hot files.**
   - Add tests in their own files, never by growing giant ones.
   - ROADMAP.md, README.md and AGENTS.md are owned by the coordinator.
8. **Sloppy** (`~/dev/slop-lang`) is an idea source, not an upstream.
   - Port anything useful, adapted to Dewy semantics.
   - No provenance ledgers, and no compatibility with Sloppy changes.
9. **Housekeeping.**
   - Commit messages are terse and imperative, with no trailers or
     attribution.
   - Commit work in progress to your task branch often (squash before
     handing off). Agents get interrupted by quotas and capacity errors;
     uncommitted work is easily lost.
   - Scratch work goes in `~/dev/tmp/<task>`, never `/tmp` (tiny quota).
   - Use at most 4 parallel test workers; the machine is shared.
   - Plain `grep` here is ugrep and skips `.dewy` files when recursive; use
     `/usr/bin/grep` or `git grep`.
   - Remove your worktrees, branches and scratch when done.
