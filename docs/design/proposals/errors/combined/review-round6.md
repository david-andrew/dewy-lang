# Independent review: combined failures, round 6

1. Round 6 fixes MF1–MF3 under both answers to D1. It replaces the `$trace` call-entry reservation and gives the analysis that would ship a stated bound: linear for the narrow check (C3-N), polynomial for the held one (C3-H). D17 now shows its caller under both D40 Q2 answers, and its recommendation (a) is right.
2. One must-fix is new, and the narrow rule introduces it. An implicit projection from a temporary (an argument, or a declared `let`, per round 6's N2 change) silently drops the unselected parts. No single failure can disappear through a type annotation. This is the parameter twin of the declared-result case that D1 says can't happen.
3. D1 is recommended on the claim that both of David's batch-10 concerns are still met. That is not shown. The `careless` match rewritten as an `if … is?` chain compiles under narrow, and an arm that leaves through another failure drops its unnamed part. David needs to see both before choosing.
4. His sketch does compile under narrow. I checked the original batch-10 text, both halves. It keeps compiling with the must-fix repaired, because `result` is a variable.
5. Ready now: D6, D8. Ready after short edits: D4, D17. Not ready: D1 (the must-fix and two disclosures), and D5 (cold read not yet run; one contradiction with C5.3). D2, D3 and D7 were not reviewed, as asked.

Scope: I read round6.md in full, names-r6.txt, dogfood-round6.md and programs-r6/ 06 and 09; I also re-read round5.md and review-round5.md, the batch-10 sketch in brief.md, LANGUAGE.md's `??` precedence (4781) and docs/design/precedence.md §4. Line numbers refer to round6.md. The programs are paper counterexamples. Nothing was compiled, and nothing in the repository was touched.

## 1. Earlier must-fixes and partial fixes

| Item | Status | Strongest remaining counterexample |
|---|---|---|
| MF1 withheld success | **Resolved.** Under narrow it is plain data, which D40 Q1 already drops (521–522, D1 table row at 100). Under held it is a reachable drop with fix-its (455–457). | None. The cost is disclosed in D1's table. |
| MF2 refusal exit | **Resolved.** Under narrow the local is dropped like any local. Under held, refusal edges are exits, a held combination joins `OutOfMemory & A & B` through a reserved link, and a held array is rejected (458–464). | None. |
| MF3 parent beside child | **Resolved for the library.** Families are never returned bare, `FileOpenFailed`/`SocketAcceptFailed` fill the gaps, and fault tests check leaves (196–216, 528–531). | Residual note: a user-made bare parent still gets packed into `ErrorStack<FileError>` (taken item 335–337). That moves peers into one stack, so a stack opaque under D17 (a) slips past `??<FileCloseFailed \| ErrorStack<FileCloseFailed>>`. This is an edge case, and nothing is lost. |
| SF1 D10's policy | **Resolved in structure.** Narrow vs held is D1's question, and it shows the sketch. | See §2: the narrow rule's costs are not all shown. |
| SF2 D17 | **Resolved** (266–313). | See §3. |
| SF3 D14 | **Resolved, apart from one contradiction** (S2 below). | The temporary's failed close stays `FileCloseFailed`. |
| SF4 / M8 `$trace` | **Resolved for effects** (495–510): no per-call work, no allocation. | S3: the per-type inline buffer and per-creation frame walk hit hot `?? 0` sites, and WebAssembly can't walk frames. |
| SF5 / M4 bound | **Resolved.** C3-N is O(arm size) with a boolean must-lattice. C3-H's merged abstraction gives a sound monotone bound (468–489). C2's four fast-path forms check out, including the single-parentage argument for intersections and complements holding on every subset (389–398). The budget is a fixed work count. | Note N1: a multi-field structural atom needs a definition before C2's row 1 is correct. |
| SF6 `@sink` | **Resolved under held** (465–467); moot under narrow. | None. |
| N1–N8 | **Resolved.** | N2's change causes M1 below under narrow. |

## 2. D1's narrow rule

**The sketch compiles under it.** I checked the original sketch in brief.md, not only D1's shortened version:
- In the `match` half, each arm names every part that reaches it, because `<E1 & E2>` comes first.
- In the variable half, `log_error(result)` projects from a variable, and `result as E1, result as E2` are explicit reads.
- `combined_fn`'s `r1 & r2` returns after narrowing, so its inferred type is `int | E1 | E2 | E1 & E2`.
- Under narrow, nothing owes.

### M1 (must-fix): implicit projection from a temporary drops parts silently

**Location:** the D1 narrow bullet (71–76), the taken item at 342–344 and C1 at 370–373 (a declared `let` projects like a parameter), and round 5's C1.3 ("implicit argument conversion … with provenance retained (C3)"). Under narrow, nothing retains that provenance any more.

```dewy
E1:type = type of error
E2:type = type of error
both = ():>E1 | E1 & E2 => E1 and E2
log_error = (e:E1):>void => printl(e)
main = () => {
    log_error(both)          # the pair converts to E1 at the parameter; E2 dies with the temporary
    let first:E1 = both      # a declared let projects too (round 6, N2); E2 dies the same way
    printl(first)
}   # compiles under narrow; nothing tests, reads or names E2
```

In this program, E2 is never kept in any variable at all. A type annotation removes it. No single failure can disappear through a conversion, so here a combination is held to a weaker standard than a single failure. It is exactly the parameter version of "a declared result can't hide a part", which D1's recommendation (109–114) gives as met.

**Fix:** a projection whose source is a temporary that dies at the projection, and whose unselected parts include a failure, is a compile error: bind the value first, or handle the rest. This is a local, syntactic check with no flow analysis. Projecting from a named place (a variable, a binder, a field) stays allowed, so David's sketch still compiles. Add the two lines above to C3-N's gate, and correct the recommendation's claim. Under held, C3-H already catches this.

### S1 (should-fix): D1 doesn't show two other ways the narrow rule loses a part

**Location:** the D1 table (96–103) and the recommendation (109–114); C3-N 428–432.

```dewy
careless_if = ():>void => {
    let r = total_bytes                              # int | QuotaExceeded | Offline | QuotaExceeded & Offline
    if r is? QuotaExceeded printl"quota: {(r as QuotaExceeded).message}"
    else if r is? Offline printl"network: {(r as Offline).message}"
    else printl"{r} bytes"
}   # narrow: compiles, and the pair's Offline goes unnamed; `careless` (the same, as a match) is an error
notify_quota = ():>void | SendFailed => {
    match total_bytes {
        both:QuotaExceeded & Offline => { send_alert(both) or_throw; both; }
        quota:QuotaExceeded => { send_alert(quota) or_throw; quota; }   # never reached by the pair
        _ => void
    }
}
```

- **First, the `if` chain.** The arm rule is avoided simply by writing `if … is?` instead of `match`. This is coherent, since narrow treats `r` as a variable, and it is cheap. But the protection depends on the spelling, and David should see that before choosing narrow.
- **Second, exiting through another failure.** C3-N (428–432) lets an arm leave through another failure (`log(x) or_throw` failing) and drops its binder's unnamed parts with the frame. That is stated only in Part 2. (The second function above shows the safe form for contrast: the pair arm comes first.)

**Fix:** add two rows to D1's table, "`careless` written with `if … is?`" and "an arm that leaves through another failure", each with narrow and held. In the recommendation, say "a combination in a variable, or one leaving through another failure, is lost silently, as a single failure is." Narrow is still my recommendation: it matches David's sketch, has fewer exceptions, and is linear in cost. It just needs these rows to be honest.

### Notes on C3-N

- **N1: arms without binders.** Take `match combined_fn() { <QuotaExceeded> => printl"quota" … }`. C3-N's members start from "the arm's binder" (414), so an owing arm with no binder has nothing it can dispose. The fix-its (433–434) assume a binder. Say that the subject's `as` name, or an introduced binder, is the member, or require a binder on owing arms.
- **N2: subject forwarded after the match.** In `match result { c:FileCloseFailed => printl(c.path) … }` followed by `result or_throw`, the arm owes even though nothing is lost. The fix (`c;`) is easy, so this passes test (2), but put it in C3-N's gate as a known false positive.
- **N3: the arm's value.** An arm whose value is its binder whole (`let failure = match r { q:QuotaExceeded => q … }`) isn't in the disposal list (419–424). Add it, as "storing it whole in an outer variable".

## 3. D17

**Recommendation (a) is right.**
- Shape follows count: one failed close comes back bare and two come back as a stack, the same rule `and` already teaches. The table at 284–287 is correct for both D40 Q2 answers. I checked the last-use column: a's failed close ends `save_two` at its write, and b closes on the way out.
- The common handler works for one failure: `??<FileCloseFailed>` takes it.
- The double failure is safe: forwarded, never swallowed, and caught at compile time. If `main` had no `or_throw`, the existing rule for a statement's value would force handling.
- No exception for one library type is needed, and arms keep their type.

**The question is shown with its caller** (`main`, 276–278), with both shapes and both D40 Q2 answers.

**Edits before it goes to open_decisions:**
- Cut the "Withdrawn" paragraph (304–306). David never saw round 5's rule, so it is history, not part of the decision.
- Add one line saying that `loop part in result.$parts` sees a bare failure and a stack's entries alike, as program 06 does at lines 20–24. That is the 80% "report every close failure" path, and it strengthens (a).

## 4. Readiness of each Part 1 question

| Question | Verdict | What's missing |
|---|---|---|
| D1 | **Not ready** | Fix M1 and correct the recommendation's "both concerns met" claim. Add S1's two rows. Drop the review labels "(MF1)" and "(MF2)" from the table (100–101): they are process trivia. Consider removing `poll` (41–46): it shows `~Canceled`, which the cancellation round is replacing, and C2 already gives `~`'s meaning. The base rule and the narrow choice should read as one question ("take D1 with the narrow rule?"). |
| D4 | **Ready after two edits** | Add "Reversible: before release". Cut the "Changed from round 5" paragraph (170–172). `Closed<Job>` is an exception and not an `error`, so `as error` still keeps exactly the two close failures, and the example works. |
| D5 | **Not ready** | The four names in names-r6.txt haven't been cold-read (rule 6 requires that before open_decisions). Cut the history sentences ("Round 5's 'the family's generic failure' would have done exactly that", "This replaces round 5's D14 `replaced` member"). Fix S2. `publish`'s `?? … or_throw;` parses as intended (`??` binds tighter than `or`, and `or_throw` sits below `as`). |
| D6 | **Ready** | Unchanged names question. |
| D8 | **Ready** | Unchanged names question. S3 affects cost only, not the names. |
| D17 | **Ready after two edits** | See §3. |
| D2, D3, D7 | Not reviewed | Left for the cancellation round. |

## Other findings

### S2 (should-fix): an atomic write's temporary close contradicts D5

**Location:** D5 at 208–211 ("`FileWriteFailed` until the new file is in place and `FileSyncFailed` after it"), and C5.3 at 546, which keeps round 5's pre-rename rows. Round 5's line 1046 gives a failed temporary close as `FileCloseFailed`, and a failed directory close after the sync is also `FileCloseFailed` (554).

**Scenario:** a caller of `path.write_text(text)` who gets `FileCloseFailed` can't tell from the type whether the new contents are installed. Only the `path` tells, and that undercuts C5.3's closing promise (559–561). It also contradicts D5's one-sentence rule.

**Fix:** inside an atomic write, the temporary's failed close is a `FileWriteFailed`, since its buffered data may not have reached the file. Then `FileWriteFailed` means not installed, `FileSyncFailed` means installed but unconfirmed, and `FileCloseFailed` (with the directory's path) means installed and durable.

### S3 (should-fix): trace storage cost is per type, and WebAssembly is not covered

**Location:** C4 at 497–510.

**Scenario:**
- **The cost is per type, not per flow.** The buffer belongs to "each value of a type that some `$trace` read can see", and it is filled by a frame walk when the failure is made. One `$trace` read on `exception` (a CLI's top-level report, or a debug report) then gives every failure type a buffer of about 264 bytes. That includes `to_int`'s failure in a parse loop written `to_int(x) ?? 0`. Every such union grows, and every defaulted failure pays an O(depth) walk, although none of those values can reach the read.
- **WebAssembly is not covered.** It can't walk native frames, so the no-per-call-cost promise doesn't hold there without a shadow stack.

**Fix:**
- Fill traces per creation site, and only where that site's value can flow to a read (round 3's flow-based demand), even if the layout stays per type.
- Measure the union size in the gate, and consider a small out-of-line, per-thread ring that the union refers to with a 4-byte handle.
- Say what `$trace` gives on WebAssembly: unavailable or truncated, or a shadow stack with a per-call cost that is disclosed as an effect.

### Notes

- **N4: a multi-field structural atom** (367–369). Define whether `is? [path:string message:string]` needs one facet providing both fields, or lets each field come from any facet. Under the second reading, a minimal witness can be two facets, so C2's row 1 ("the witnesses are the matching singletons") would be wrong for it. One facet providing all the fields is the reading that keeps the fast path correct.
- **N5: the dogfood regrade.** Program 06's discoverability 3→4 is fair. The `$parts` loop is the teachable path, and the sub-5 reason given (a `??<FileCloseFailed>` handler takes one failure and forwards two) is honest.

## Summary

**Must-fix: 1** (M1).

**Top three:**
1. **M1:** implicit projection from a temporary drops parts silently under the narrow rule.
2. **S1:** D1 doesn't show that the `careless` match compiles when written with `if … is?`, or that an arm leaving through another failure drops its unnamed part.
3. **S2:** an atomic write's temporary close stays `FileCloseFailed`, so the caller can't tell installed from not installed, contradicting D5.

**Readiness:** D1 not ready; D4 ready after two edits; D5 not ready; D6 ready; D8 ready; D17 ready after two edits. D2, D3 and D7 were not reviewed.
