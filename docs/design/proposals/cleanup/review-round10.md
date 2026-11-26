# Review: cleanup rounds 9–10, design (g) as amended

**Verdict.** The three blockers are fixed. (g) as amended is ready to take to David as the recommendation, including the nonlocality stated in round 10 §4 and §11. It is not a decision until `ErrorList` and `TempRemoveFailed` are cold-read, which round 10 already says. Nothing here needs another design round. Two sentences should be in the question before he sees it: the race rule is about a final-path flush, not the name `FileWriter`, and the warning-only tier is given up.

## 1. The three blockers

**An owing return dropped by a later defer.** Fixed by rejection, not by an implicit flush. `handoff_round9` is an error naming both values. The repair closes `receipt` before returning `body`, so a failed close is a failure exit and `body`'s own defer runs. The same check covers a block value and an item of a scope whose own defer can fail. A `Socket` may still be replaced only when its failure cleanup is an abort; an unfinished socket still owes, so it cannot be carried out either. A yield from a lazy body with an *outer* defer is not this hole: the item is moved at the suspension, and the defer runs later as the generator's cleanup, so the item is not dropped. None of programs 01–13 hit the new error, which matches the claim.

**Hooks that publish, and `first_ok` discarding a temp removal.** Fixed. `$__drop__` and `$__abandon__` may only end fields through their own cleanup; program 11's footer is a `$__consume__` `finish`, and that call decides the value so abandon does not run after it. `TempRemoveFailed` is `FileError & UndoFailed`, so `first_ok` rejects `defer tmp.discard() or_throw`. The handled form logs the failure inside `backup_to`. An owned `FileWriter` live across a cancellation point in a `race` or `first_ok` callee is an error. `parallel` is correctly left alone (D44 Q8 keeps the sibling's failure).

**Handlers over a mixed stack.** Fixed, and it matches the requested law except for one wording trap. `is?` is true when an element matches, at any depth. `??<E>` never takes a stack; `??<ErrorStack<A | B>>` takes it only when every element fits; an arm `c:E` never receives one, so `c.path` stays one path. `or_throw<RollbackFailed>` on `[Declined RollbackFailed]` forwards the whole stack (program 15), which does not drop the other element. A fold at an exit appends, so a callee's stack stays flat. The table's parenthesis "it selects, as `is?` does" must not be implemented as extracting the element. One case is unstated: `or_throw<E>` on `Canceled & ErrorStack[…]` has to forward that whole value too.

## 2. The new rules

The exit rule is sound. It is the conservative of the two fixes, and it keeps "nothing fallible is implicit." A defer that handles or discards (`??`, `;`) does not replace the value, so it does not drop the returned owner; only a defer that can fail the scope is banned. That is the right cut.

`$__consume__` already takes the receiver (LANGUAGE.md). The new piece, that this call is the decision `$__abandon__` waits for, is what makes `finish` and `commit` the same. `finish`'s body is checked like any body, so its fields are closed there; the method's trailing drop then sees them gone. A failed `finish` must count as decided too, or abandon would close the same files again. Round 10 says "doesn't run afterwards" and does not say "only on success." Read it as the commit rule.

`TempRemoveFailed` as an undo matches D44: the effect persists. `files.remove` staying `FileRemoveFailed` is the right split. The race bit, as written, is only "owns a `FileWriter`." A `File` opened `'rw'`, and a pipe writer that is not that type, are the same flush owed to a final path, and a borrowed `FileWriter` is allowed on purpose. Say "owes a flush of a final path" and keep the borrow exception for a log the race does not own. That is a sentence, not a new mechanism.

`is?` and `or_throw<E>` look inside; `??<E>` never takes a list. The one behavior that changes from `&` is real and documented: `??<Declined | RollbackFailed>` used to consume the pair and now forwards the list. The warning when the handler covers every element type is what makes that discoverable. A parent family needs the same warning: `??<FileError>` does not take `ErrorStack[FileWriteFailed FileCloseFailed]`, and "union" does not obviously include the parent D42 Q3 told people to write.

## 3. The regrade

The table sums to 50 of 65: eleven obvious 4s and four concise 4s (02, 04, 11, 12). Editor hints are not in the grades. The obvious 4s are the two rules round 10 admits: a return replaced by a close, and one `defer` spelling whose exits depend on a later move or `commit`. That is an honest regrade.

One cell disagrees with the iteration under it. "Tried `errdefer`" lists 04 with the move-cancel misses, but 04's obvious grade is 5. `defer tx.rollback()` above `commit` is the same pattern as `defer tmp.discard()` above `persist`, which is an obvious 4 on 02. If 04's obvious grade were 4, the count would be 49. Not enough to call 50 false. Programs 14 and 15 are outside the 65. 10's safe 5 and 11's complete 5 hold for the rules as they should be read, not for a check that only names `FileWriter`.

## 4. Dropping the leftover tier

Sound for the library they have. The only warning-only cases were temp-file and temp-dir removal, and a failed removal leaves the bytes, which is an undo. No standard type is left that needs a middle strength. David's "some types warn" is then unused, not contradicted by a type that can fail and is ignored. The For David box does not say he gives that middle strength up. Add it to "you give up." Keep the door he was offered: a later type can still be warning-only, with a cold-read name.

## 5. Round 9's citation repairs

Checked against the current Linux `close(2)` page, POSIX.1-2024 `close`, Well-Typed's "Exception Annotations" (8 May 2026), GHC 9.12's `WhileHandling`, errcheck issues 55 and 101, golangci-lint's EXC0001 / `std-error-handling` preset, restic/rest-server's `.golangci.yml`, Gitaly MR 4810, and Mojo 1.0 (11 Aug 2026).

They hold where they carry the design. Linux releases the fd and does not retry; it is non-conforming. `WhileHandling` is 9.12's `catch`, and the new exception is primary. errcheck's own defaults do not exclude `Close`; kisielk on issue 101 refused to ignore a deferred `Close` because a flush may have failed (the sample in the ticket is `os.Open`; the write-side argument is dominikh on issue 55). EXC0001 hides `.*Close` and `.*Flush` together. Python's `with` does not build an `ExceptionGroup`. Mojo's default is still implicit destruction, and `__deinit__` cannot raise.

Three overstatements, none of which change (g):

- POSIX.1-2024 does not simply standardize "EINTR means still open." That is one of three outcomes, and it is forbidden when `POSIX_CLOSE_RESTART` is 0. The man page's "HP-UX" sentence is what round 9 quotes.
- Gitaly did not start checking file closes. MR 4810 dropped the blanket regex and still excludes `(*os.File).Close`. restic/rest-server does set `exclude-use-default: false`.
- As of Mojo 1.0, `@explicit_destroy` no longer opts out of `Deinitable`. The opt-out is `not Deinitable`. The decorator still attaches a message. That is closer to (g), not further.

## What still blocks a decision, not the recommendation

Cold reads of `ErrorList` and `TempRemoveFailed`. In the question, before he answers: the race rule covers every final-path flush, and the warning-only tier is given up. State that `or_throw<E>` forwards `Canceled & ErrorStack[…]` whole, and that `??<FileError>` gets the same warning as a union that covers the stack.
