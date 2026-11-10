# Dogfood, round 4

Scores are obvious, discoverable, concise, safe by default, complete. Only the programs this round changed are graded. The others keep their round-3 scores, with `do` and bare `with` replaced by `inline` and `inline with`. Three of six cold readers had read `do { }` as a callback. All three readers of `inline` read the brace as the caller's code.

Floor of this set is **4**.

| Program | Dewy |
|---|---|
| 02 shell | 5 4 5 5 4 |
| 03 save on Ctrl-C | 4 4 4 5 5 |
| 04 early return | 4 4 5 5 5 |
| 07 server flush | 4 4 4 5 5 |
| 08 CLI throw | 4 4 5 4 5 |
| 09 break | 4 4 5 5 5 |
| 13 expressions | 5 4 4 5 5 |
| 14 comprehension | 4 4 4 5 5 |
| 16 return replaced | 4 4 5 4 5 |
| 17 failing close | 4 4 5 4 5 |

## Lines under 5

**02, discoverable 4 and complete 4, line 2.** The child gets SIGINT only because that comment says it is in the foreground process group. There is still no spelling for the group. Line 19 reads the queued press with `ctrl_c.next(timeout=0s)`, so the press is a `<CtrlC>` here and not the next `input`. That half is no longer only a comment.

**03, obvious 4, discoverable 4, and concise 4, line 27.** `<Timeout>` on line 26 is the shield's deadline, and it runs even though Ctrl-C already canceled the search: the shield hides that parent cancel, so the cancel does not reach the brace. `<Canceled>` stays because `save` can still return one, and the type is not narrowed. The line does not say which arm is the deadline. `problem:error` on line 28 is every file error in LANGUAGE.md:3984. `save` leaves its result inferred, so the list is not a subset.

**04, obvious 4 and discoverable 4, line 29.** `Canceled or_throw` reads as `find` returning `Canceled`. The group's state rewrites it to `WalkError` as the exit leaves the brace, before `join`. The parent has not reached the brace, so the defer then keeps `WalkError`. The token does not show that order. The signature still lists `Canceled` for a parent cancel that did reach the brace.

**07, obvious 4 and discoverable 4, line 34. Concise 4, line 31.** `return` leaves `serve` and stops `accept` before the join. The stop is not on the line. Lines 31–34 are the catcher, the group, and the deadline, which is the server. `serve` leaves its result inferred, so `write_text` forwards every file error plus `Canceled`. The deadline is the `??<Timeout>` on line 33. A file error on line 32 leaves `serve`.

**08, obvious 4, discoverable 4, and safe 4, line 23.** `if done is? error return Missing` keeps `Missing` and drops `warm`'s error. A failure is an `error` or `Canceled`, so this arm is the whole error family, not only `FileNotFound`. `none` would not take it. Line 24 is `Canceled`. What remains is the void success, so there is no `<void>` arm. The dropped cause is the one-failure rule.

**09, obvious 4 and discoverable 4, line 16.** `probe(port) or_throw` adds every file error and `Canceled` to `serve_until`. The shield's deadline becomes `Timeout` on line 19, and that path continues the port loop. A file error leaves. `??<Timeout>` does not warn: `protect_from_cancel`'s defer cannot fail, and the `continue` inside the brace is not a lie about a failing defer.

**13, discoverable 4, line 20. Concise 4, line 19.** The `or_throw` targets `total_size`. The `??<Timeout>` on line 21 sees only the shield's call. `inline` on line 19 is what attaches the brace. Line 24 is `inline with` on its own line. `touch` and `total_size` leave file errors inferred.

**14, obvious 4 and discoverable 4, line 17. Concise 4, line 16.** `continue` inside the shield and `??<Timeout> continue` on line 18 both skip the element. Line 26 is the positive case: a blocking shield inside `parallel`, and that block does not return. Line 35 is the rejected case, a `return` inside `inline` inside `parallel`: "return cannot leave a parallel body." The `??<Timeout>` does not warn.

**16, obvious 4 and discoverable 4, line 19. Safe 4, line 30.** `return 0` does not leave `replaced` when the join fails. Line 22 warns, because `tasks` has a defer that can fail and the brace's `return` carries no failure, and `code` becomes `-1`. The child this wait is blocked on wakes the waiter with `WalkError` first, so line 19 is not a race. Line 30 returns `Missing`, which is kept, and the same `WalkError` is dropped. After the `is?` tests, line 21 and line 32 are the void success.

**17, obvious 4 and discoverable 4, line 31. Safe 4, line 39.** `append_file(...) or_throw` leaves `replaced` with a file error or `Canceled`. Line 33's `??<Trailer>` does not catch it. `Trailer` is only the close, so the two routes are different types, and hover on line 33 says the handler sees only the call's failures. Line 32's `return 1` is dropped when the close fails, and `code` is `-1`. That warning fires because `bracket`'s `close` can fail. Line 39's `return Missing` is kept, and `Trailer` is dropped.
