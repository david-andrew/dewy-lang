# Cold read, cancellation round 1 (kit r25)

Three readers with no context; lines and brief in `~/dev/tmp/naming-1107/r25/`. Confidence is reader a / b / c.

## Incidental-work marker (`$x show_progress()` beside `download_all(urls) or_throw`)

The behaviour to convey: the item is cancelled once only such items remain.

| Name | Read the behaviour? | Confidence |
|---|---|---|
| `$until_others_finish` | yes, 3/3 ("keeps running until the other statements complete, then ends") | 4/4/4 |
| `$stop_when_alone` | yes, 3/3 | 4/4/2 |
| `$incidental` | role only ("side work, not the point"); no reader said it stops | 4/3/2 |
| `$auxiliary`, `$sidecar`, `$nonessential` | role only | 2–4 |
| `$daemon` | "background, not waited on"; one said "ends with the program" | 3/3/3 |

`$incidental` fails: readers get the role but not the behaviour. `$until_others_finish` is the strongest.

## Cancel request passed to another task (`jobs.send([image task.X])`)

| Name | Read correctly | Confidence |
|---|---|---|
| `task.cancel_request` | 3/3 | 4/4/4 |
| `task.stop_request` | 3/3 | 4/4/3 |
| `task.cancel_token` | 3/3 | 3/4/3 |
| `task.cancel_signal` | 3/3 | 4/4/3 |
| `task.cancellation` | 3/3, vaguer | 4/3/3 |
| type `task.CancelRequest` | 3/3 | 4/4/2 |
| `check_cancel()` | 3/3 | 5/4/4 |

## Cleanup failure of a cancelled loser (`<X<FileCloseFailed>> => …`)

`AfterCancel` (3/3/2), `CanceledWith` (3/3/3), `StoppedFailure` (3/3/3) and `LoserFailed` (3/3/2) were all read as "a failure tied to a cancellation, carrying `FileCloseFailed`". `LoserFailed` was read as race-specific. Confidence is low throughout: no name clearly wins.

# Round 2 (kit r26), in-context readings

- **`$until_others_finish`** on a heartbeat block beside `process_queue() or_throw`: all 3 readers said it runs until its siblings finish and is then stopped. Confidence 3/4/3. All 3 judged it safer.
- **`<Closed<task.CancelRequest>>` vs `<Canceled>`** in one `select`:
  - All 3 read `Reply` and the two failure arms correctly in outline.
  - Only one reader (b) stated the distinction plainly: "cancel landed via close" vs "the wait itself was canceled". The other two described the first arm as "a closed channel carrying a cancel request" and said nothing of why it differs from `<Canceled>`.
  - Confidence 4/3/3.
  - The arm pair is readable, but the difference is not obvious cold. It needs a hover or doc line.

# Round 3 (kit r27): strict tag that forbids discards

| Name | Read correctly | Confidence | Safer |
|---|---|---|---|
| `$no_discarded_failures` | 3/3 ("no failure may be silently dropped; handle or forward each") | 3/4/4 | 3/3 |
| `$explicit_discards` | 3/3 ("a discard must be written out") | 4/3/3 | 3/3 |
| `$keep_all_failures` | 2/3: "keeps" was read as "stores and surfaces the losers' failures", which is a different behaviour | 3/4/2 | 2/3 |

`$no_discarded_failures` is the strongest. `$explicit_discards` is a close second. `$keep_all_failures` misleads.

# Round 5 (kit r29): `UndoFailed`

- **`UndoFailed`:** 3/3 read it as "an undo or revert could not put earlier changes back", confidence 4/4/4. Only one reader said unprompted that it is a family covering more specific failures. The family role needs a doc line.
- **`RollbackFailed`:** read correctly 3/3, confidence 4/4/4.
