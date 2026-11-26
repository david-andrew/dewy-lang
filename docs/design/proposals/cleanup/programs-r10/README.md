# Round-10 paper programs

Only the programs round 10 changes, plus two new ones. Everything else is as in
[programs-r9/](../programs-r9/README.md). The write-up is [../round10.md](../round10.md).

| File | What changed |
|---|---|
| [02_temp_rename.md](02_temp_rename.md) | a missing `defer` is an error: a failed removal is `TempRemoveFailed`, an undo |
| [10_parallel.md](10_parallel.md) | a loser's undo can't be discarded; a raced body can't hold a `FileWriter` |
| [11_wrapper_type.md](11_wrapper_type.md) | the footer moves from the hook to a `$__consume__` `finish`; `$__abandon__` closes without it |
| [12_process_scratch.md](12_process_scratch.md) | a child's stdin pipe; the scratch directory's removal is an undo |
| [14_handoff.md](14_handoff.md) | new: returning an owner while another close is pending; one `defer` spelling, three exit sets |
| [15_mixed_stack.md](15_mixed_stack.md) | new: every handler form on `ErrorStack[Declined RollbackFailed]` |

Program 05 changes only in its Error 2 text, which is in round10.md §7.
