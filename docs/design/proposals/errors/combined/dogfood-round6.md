# Dogfood, round 6

These are author regrades of the programs that round 6 changes, starting from round 4's grades
(`dogfood-round4.md`). Peer-language grades are unchanged. Nothing was compiled.
O/D/C/S/K stand for obvious, discoverable, concise, safe by default and complete.

| Program | R4 | R6 | Why |
|---|---|---|---|
| 06 two files fail to close | 4/3/5/5/5 | 4/4/5/5/5 | D17 (a): the shape follows the failure count, the rule `and` already teaches, and it no longer depends on which owners are live or on D40 Q2 ([06:11-12](programs-r6/06_two_files_fail_to_close.dewy)). One loop over `$parts` sees a bare failure and a stack's entries alike ([06:20-24](programs-r6/06_two_files_fail_to_close.dewy)). |
| 09 CLI locations | 4/4/5/5/5 | 4/4/5/5/5 | Only the comment changes, listing both shapes ([09:8-10](programs-r6/09_cli_locations.dewy)). The program already printed `$parts`. |

**What stays below 5 in 06.** O4/D4: the reader must know that two failures of one kind come
back as a stack, and that `$parts` opens it. A handler written as `??<FileCloseFailed>` takes one
failed close and forwards two ([round6.md](round6.md) D17). That is safe, but it has to be
taught. The floor is now 3 only in program 15 (wrapping), which round 6 leaves alone.

**No other program changes.** Under the narrow D1, every program already handles, forwards or
matches what it holds, so dropping the held rule changes no program's behavior. Program 01's
line 23 comment ("`result` was handled by the match") is still true, though under the narrow rule
it is no longer needed. Under D5, the type comments that write `FileError` mean the family, which
remains correct. No program used D14's `replaced` member.
