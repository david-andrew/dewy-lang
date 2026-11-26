# 02. A temporary file renamed into place (round 10)

The code is as in [round 9](../programs-r9/02_temp_rename.md). Two things change.

**A missing `defer` is an error, not a warning.** A failed removal of the temporary is
`TempRemoveFailed`, an `UndoFailed`: the unpublished text stays on disk.

```text
error: tmp (TempFile, line 2) is removed if tmp.write_text fails (line 3), and removing it can
       fail with TempRemoveFailed, leaving the temporary file and its text on disk.
       Remove it on every exit:  defer tmp.discard() or_throw
```

**No leftover tier.** Round 9 made this a warning and needed a name for "warning-only cleanup";
both names tried failed the cold read, and with removals classed as undos no standard type needs
the tier.

## Scores

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 4 | 5 | 4 | 5 | 5 |

Obvious 4: `defer tmp.discard()` sits above a `persist` that turns it off. Concise 4: the early
success exit says `discard` beside the `defer` that also says it (rule 5).
