# Golden-file cases

One program per file: `tests/cases/<area>/<name>.dewy`. Add a case by adding
files; never grow a shared test module.

- `<name>.out`: the exact expected stdout. Missing means no output.
- `<name>.err`: the program must fail to compile, and each line must occur in
  the diagnostics (`/regex/` lines are searched as regular expressions). With an
  `exit:` header the program must instead build and fail at run time with that
  code, the lines matching its stdout+stderr (panics exit 101).

Optional header lines, at the very top:

```dewy
# exit: 42                     expected exit code (default 0)
# modes: native web-release    of native native-release web web-release (default: all four)
# args: one "two words"        program arguments, shell-quoted
# stdin: first\nsecond\n       standard input, with \n \t \r \0 \\ escapes (native only)
# quick                        also part of `test --quick`
```

```sh
python3 -m tools.core cases                      # all cases, all their modes
python3 -m tools.core cases -k 'closure and not copy'
python3 -m tools.core cases -k string/new_case --update   # record a new case's output
python3 -m tools.core cases --update             # re-record changed outputs of existing .out files
```

`--update` only rewrites stdout; exit codes and diagnostics stay hand-written.
Check the recorded output before committing it. Ordinary cases of one mode
compile together as modules of one program, so a case keeps its own module
scope but shares the process; a case that exits or panics is rerun alone.
Programs that need extra files, networking, timing or compiler inspection belong
in pytest (`tests/test_core_*.py`, helpers in `tests/support.py`).
