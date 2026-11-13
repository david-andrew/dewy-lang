# Independent review: combined failures, round 5

1. Round 5 is a real repair. M1, M5, M6 and M7 are resolved, and M4 is resolved for finiteness and soundness, though its only stated bound is for a reference implementation that is not meant to ship.
2. Three must-fix remain. Under round 5's own obligation rule, two paths lose parts: a cleanup failure that withholds a success carrying failures, and an allocation-refusal exit that drops held combinations. The third is D5's new "family's generic failure", which makes cleanup build a parent-plus-child combination that C1.2 forbids.
3. The rule behind the first two (D10: a held combination must be acknowledged, while a single failure needn't be) goes beyond D42 Q1 as David reads it. It breaks his own sketch, and it is the only reason C3 needs whole-program provenance. It belongs in D1, beside the narrower arm-only reading, which would also remove MF1 and MF2.
4. Of D9–D17, one question should reach David: D17's stack shape, with D16's selector clause merged in and the alternative it leaves out. D14 is not ready and fits better as a D5 name. The other seven are report only.
5. There is no conflict with D40, except that D17's shapes silently assume block-end cleanup. D4's `wrap` example (an existing open question) treats `Canceled` as data in a parameter type, which will conflict if the cancellation round makes `Canceled` control only.

Scope: read round5.md in full, audit-round4.md, round4.md, brief.md, brief-round5.md, round 1/3 stack sections, programs-r4 03/04/06, decisions.md batches 9–10, D40/D42/D43 in open_decisions.md, and LANGUAGE.md's conversion, intersection, allocation-failure and file sections. Line numbers refer to round5.md unless another file is named. The programs are paper counterexamples under the proposed rules. Nothing was compiled, and nothing in the repository was touched.

## M1–M8: resolved?

| Audit item | Status | Strongest remaining counterexample |
|---|---|---|
| M1 coverage definitions | **Resolved.** There is now one definition (inclusion-minimal witnesses, 200–206, 592–603). The table rows check out, including negation (`A \| ~B` leaves B unconsumed) and witnesses of different sizes. | None unsound. N1 (structural selectors) and SF5 (budget determinism) are residual. |
| M2 transport ≠ discharge | **Resolved for blocks and nesting** (662–677, 696–699). Both audit programs now fail. | **MF1**: a success holding failures is withheld at a failed cleanup (850–853). SF6: writes through `@param` are unspecified. |
| M3 refusal transport | **Resolved for owners, inline pending failures and the unwind record** (837–940). | **MF2**: a held, unacknowledged combination dies on the implicit refusal exit. N6: repeated `OutOfMemory`. SF4: trace reservation. |
| M4 finite analysis | **Resolved for finiteness and soundness** (701–822): tokens/buckets, valuation-set joins, relational summaries, demand from productions. | No leak found. Precision limits are disclosed under D11 (see the program below). The bound is for a reference implementation only (SF5). |
| M5 guard ≠ projection | **Resolved** (D9, 532–558). An existential `is?` is kept, and `as`/`as T?` need uniqueness. | None. N2 (binding vs parameter) is a consistency note. |
| M6 ordered defaults | **Resolved** (C1.1 495–502). LR/RL give 2/1, and membership commutes. | None. N8 (an ill-fitting later default) is pre-existing. |
| M7 read-close suppression | **Resolved** (990–996, taken 466–467). | None. |
| M8 hidden policy | **Largely resolved**: projection, acknowledgment, decode order, commit, replacement, refusal and the stack move to D9–D17. | SF4: demanded traces reserve storage as calls enter, which changes effect rows out of sight. MF3 is a contradiction in the new D5 text, not a hidden policy. |

The M4 precision limit, shown so that David's D11 wording can be checked against it:

```dewy
A:type = type of error
B:type = type of error
pair = ():>A & B => A and B
twice = (quiet:bool):>void => {
    let p = pair
    if quiet p ??<A | B> void
    if not quiet { printl(p); p; }
}   # safe on every feasible path; valuations without branch facts, and any merged-state
    # checker, report p owing A and B on quiet=false then quiet=true. The fix is if/else.
```

## Must-fix

### MF1: Cleanup failure withholds a success that carries transported failures

**Location:** C4.1 850–853 ("a pending success is withheld … released if the handoff fails … a failed cleanup replaces success"), compared with D10 272–277 and the C3.1 table at 669–670 (return/handoff transfers the duty).

**Scenario:** D10 says returning a value transfers its outstanding parts to the caller. D40 Q1 (decided) makes a cleanup failure the function's result, and C4.1 then releases the withheld success. When that success contains combinations, their parts vanish with no action naming them, which is exactly what D1 forbids. This is the realistic batch shape: collect failures, write a log, return the collection.

```dewy
import p"@lib/std/files.dewy" as files
A:type = type of error
B:type = type of error
pair = ():>A & B => A and B
Found:type = [items:array<A & B>]
gather = (log:Path) => {
    let out = files.open(log 'w') or_throw
    let found = Found[[pair]]              # D10: this duty goes to whoever receives found
    out.write_text("gathered\n") or_throw;
    return found
}   # out's close fails: the result is FileCloseFailed, found is withheld and released (C4.1),
    # and its A and B leave without any action naming them
main = () => {
    let found = gather(p"log.txt") or_throw
    loop item in found.items { item ??<A | B> void }
}
```

**Fix:** under round 5's rule, the checker must treat a fallible cleanup after a success that holds outstanding duties as a reachable drop. It should report it, with a fix-it to finish the owner before returning (`out.close() or_throw`, D40 Q6 form A) or to handle the duties first. Add this case to C3's required negatives. Under SF1's narrower reading this stops being a leak: the withheld value is plain data, and D40 Q1 already decides that it is dropped.

### MF2: An allocation-refusal exit drops held combinations

**Location:** D15 384–408, C4.2 876–903, LANGUAGE.md 5223–5236 (in an `$explicit_allocation_failure` module, any refusal makes the function return `OutOfMemory` and drops its owners). C3 never says whether these implicit exits are CFG edges.

**Scenario:** C4 carries owners' cleanup failures and an already pending result across the jump. It does nothing for a local that merely holds an unacknowledged combination. If refusal edges are not in C3's graph, the combination is lost. If they are, nearly every program that holds a combination across an interpolation is rejected. Round 5 specifies neither.

```dewy
$explicit_allocation_failure
A:type = type of error
B:type = type of error
pair = ():>A & B => A and B
describe = (n:int) => {
    let p = pair
    let text = "{n} items"       # refused: describe returns OutOfMemory here
    p ??<A | B> void             # not reached on that path; p's A and B leave with the frame
    return text
}
```

**Fix:** state that refusal edges are exits for C3, and that on such an exit every held, unacknowledged combination joins the returned result exactly as a cleanup failure does (`OutOfMemory & A & B`). The unwind record retains them by reference, with a link reserved in the capsule; that cost goes in C4.3. This is D15's own principle applied to held values, so it is report only. Rejecting instead is too noisy. Under SF1's reading the problem disappears.

### MF3: D5's "family's generic failure" produces a forbidden ancestor/descendant combination

**Location:** D5 139–140 and C5.1 998–1001 ("an otherwise unmapped acquisition failure uses the family's generic failure"), with `FileError` becoming the parent (133); C1.2 506–513 and the taken item at 464–465 (overlapping supplied identities, ancestor/descendant included, are rejected); D17 (only same-kind collisions are packaged).

**Scenario:** today `FileError` is the concrete "any other failure" leaf. Once it becomes the parent, either the generic failure is the parent itself, or the name is undefined. If it is the parent, automatic cleanup builds a combination that the type rules forbid, and no packaging rule covers it:

```dewy
import p"@lib/std/files.dewy" as files
copy_into = (source:Path target:Path) => {
    let out = files.open(target 'w') or_throw
    let input = files.open(source 'r') or_throw   # unmapped open failure: "the generic failure"
    out.write_text(input.read_text or_throw) or_throw;
}   # out's close also fails: FileError & FileCloseFailed, a parent beside its own child
```

`NetError`, `ProcessError` and `DbError` have the same gap.

**Fix:** give each family a concrete leaf for unmapped failures (for example `FileOpenFailed`, which also fits one-type-per-operation, since opening is an operation; sockets already have `SocketConnectFailed`) and keep the parents abstract, so they are never values. Add the new leaves to D5's list and cold-read them. This is a names-only addition to an existing question.

## Should-fix

### SF1: D10 hides the real policy: only combinations must be acknowledged

**Location:** D10 252–279; C3.1 653 ("each dynamic production of a **compound** failure … creates one occurrence"); D42 Q1 in open_decisions.md, which constrains handlers and match arms only.

**Scenario:** D10 is framed as "shared acknowledgment for copies", which is trivia. The choice inside it is that a combination held in a variable is a compile error if it ends unhandled, while a single failure held the same way is dropped as today. David has not seen this. It goes beyond the D42 Q1 text he is answering, and it breaks his own batch-10 sketch:

```dewy
E1:type = type of error
E2:type = type of error
combined_fn = ():>int | E1 | E2 | E1 & E2 => E1 and E2
log_error = (e:E1):>void => printl(e)
main = () => {
    let result = combined_fn
    if result is? E1 log_error(result)      # the sketch: "works if E1 or E1 & E2 was returned"
    if result is? E1 & E2 {
        let e1 = result as E1
        let e2 = result as E2
        printl("{e1} {e2}")
    }
}   # D10: error here, result's E1 and E2 were only observed and projected. The same main
    # compiles if combined_fn can return only E1.
```

The rule makes combinations stricter than single failures. That is an exception to the general rule, and it is what forces C3's whole-program provenance analysis, its exponential reference bound and its D11 false positives. It also causes MF1, MF2 and D16's extra `xs;`.

**Fix:** put the choice in D1 (already a question) as one sentence, using David's sketch and the `result;` fix. Show the narrower alternative beside it. Under that alternative, only an action that names a part creates a duty: a selected arm must forward, handle or `;` its binder on every path in the arm, and `??<E>` consumes only covered values (C2 unchanged). A whole value dropped without any naming action is dropped as a single failure is today. David's two concerns from batch 10 remain covered: the handler can't swallow (C2), and the declared result can't hide a part (holding rule). C3 then shrinks to a local check per arm. My recommendation is the narrower reading unless David wants must-use for all failures. Either way, D10 as written should become report only.

### SF2: D17's recommendation rests on a false premise, and D16's selector clause belongs with it

**Location:** D17 436–455 ("a stable stack shape at each cleanup boundary"), D16 410–434 ("stack selectors inspect the stack's type, not its contents"), C1.3 529–530. The last two quietly carry over round 3's withdrawal of round 1's leaf-aware handler (round1.md 438–441, round3.md 437–444).

**Scenario:** the shape is stable per boundary, not per function, so callers still face both shapes. Program 06 (programs-r4) already lists both. With opaque stacks, the handler anyone would write first never applies:

```dewy
import p"@lib/std/files.dewy" as files
save_two = (left:Path right:Path) => {
    let a = files.open(left 'w') or_throw
    let b = files.open(right 'w') or_throw   # fails with only a live: FileNotFound & FileCloseFailed
}                                            # block end: ErrorStack<FileCloseFailed>, even for one failure
main = () => {
    save_two(p"a.txt" p"b.txt") ??<FileCloseFailed> void or_throw   # consumes neither shape
}
```

This is the lowest-graded point in the dogfood (discoverability 3), so it fails test (1). It also depends on D40 Q2: under last-use timing, the two owners rarely end together, and the shapes change.

**Fix:** keep it as David's one question, with D16's selector clause merged in, and lead with the caller. Give two alternatives:
- (a) Dynamic shape: bare for one failure, a stack for two or more. There is no selector exception, and the natural handler covers the common one-failure case.
- (b) Stack-transparent selection: `is?`, arms and `or_throw<E>` existential over elements; `??<E>` consumes when every element is covered; `as E` on a stack is rejected, so you iterate. This is one exception for one library type, but a single handler covers every shape.

I lean towards (a). Say that the shapes assume block-end cleanup (D40 Q2).

### SF3: D14 is not ready, and its shape invents a failure

**Location:** D14 353–382, C5.3 1052 and 1058–1063.

**Scenario:** when the directory's close fails after a successful sync, C5.3 reports `FileWriteFailed[replaced=true]` as an "operation-incomplete marker" next to the real `FileCloseFailed`. Nothing failed to write; the marker is a synthetic failure. The member is untested, and D14 itself says it can't go to open_decisions yet.

**Fix:** follow D5's own rule of one type per operation: a post-rename `FileSyncFailed` means "installed, durability not confirmed", and a directory-close failure is a `FileCloseFailed` on the directory's path. That removes the bool member and the marker. Cold-read `FileSyncFailed` with D5's names and fold it into D5. If the member is kept, it needs a cold read and dogfood first.

### SF4: Demanded traces reserve storage as calls enter, a residual M8

**Location:** C4.1 870–874, C7 1119–1121.

**Scenario:** "a stable frame-chain representation reserved as calls enter" means that one `$trace` read anywhere makes every frame in its demand closure allocate on entry. Under `$explicit_allocation_failure`, those functions also gain `OutOfMemory` in their results. A callback typed `no allocates` (as in D40's `RestoreAction`) can stop fitting because of a distant read. That is an observable change to effect rows, and Part 1 doesn't mention it.

**Fix:** reserve a fixed-capacity trace buffer in the failure slot that is already reserved at acquisition. Round 1 capped `$trace` at 64 entries; compact site ids keep that small. Fill the buffer at completion by walking frames, which allocates nothing and costs nothing per call. Truncation is reported in the trace. If entry reservation is kept, it goes in D8 or D15 as a disclosed effect.

### SF5: The landing analysis has no stated bound, and acceptance must be deterministic

**Location:** C3.4 794–822, C2 635–642, D11 309–313.

**Scenario:** the only stated bound is O(H·E·K⁵·B²) with K ≤ 2^B, which is exponential in function size. That bound belongs to the reference procedure, and the text says it is not the shipped strategy. The merged-state implementation that would actually land (750–755) has no bound. Acceptance also depends on a "configured budget". If that budget is measured in time or memory, the same program compiles on one host and fails on another. Rule 4 asks for the complexity of the pass that lands.

**Fix:** specify the merged abstraction (may facts as union, must facts as intersection, widened counts) with its polynomial bound, roughly O(I·E·(T·P + A)) with I bounded by the lattice height. Make valuation sets an optional local precision step. Define the budget as a deterministic count of work units, fixed per compiler version and not a setting. Give C2 a linear fast path for the common selector forms (one nominal, a union of nominals, `~Canceled`, an intersection of distinct nominals), so that 2^f search is reserved for unusual selectors. If SF1's narrower reading is taken, most of C3 goes away.

### SF6: Writes through a mutable borrowed parameter are unspecified

**Location:** C3.1 688–694 ("may not export an unacknowledged locally created occurrence without an actual result/owning handoff") and 679–686.

```dewy
A:type = type of error
B:type = type of error
pair = ():>A & B => A and B
collect = (@sink:array<A & B>):>void => sink.push(pair)   # is the caller's array an owning destination?
main = () => {
    let found:array<A & B> = []
    collect(@found)
    loop f in found { f ??<A | B> void }
}
```

Either `collect` is rejected, which breaks the ordinary collector helper (D3 even says "collectors need nothing"), or it is accepted under a rule nobody wrote down.

**Fix:** a write through a mutable borrowed parameter transfers the duty to the caller's place, and the summary exports it to that parameter. Add this case to the gate.

## Notes

- **N1: structural selectors break C1.3's own principle** (524–528). Selection is meant to be existential and not to read fields, yet a structural atom requires a unique provider. So `both ??<error> 1` consumes `Quota & Offline`, while `both ??<[message:string]> 2` does not, even though each part has a `message`. Make structural atoms existential for selection, and keep uniqueness for reads and projection.
- **N2: a declared binding and a parameter disagree** (D9 245–247, C1.3 576–578). `log_error(result)` projects, but `let e:E1 = result` is rejected. LANGUAGE.md says "parent-typed storage preserves the child's identity". With C3 tracking the duty that stays with the source, a local `let` can project exactly as a parameter does. Reject only declared results and owning fields, or say why lets differ.
- **N3: D4's `wrap`** (105–107, also in open_decisions D42 Q4) takes `result:Canceled & FileCloseFailed & SocketCloseFailed` as a parameter and rebuilds `Canceled` with `and`. If the cancellation round restricts `Canceled` to control, this example breaks. Switch to another exception, or mark it as pending that round. D1's `poll` is fine, because `sensor.read(timeout=1s)` waits.
- **N4: D13 overlaps D43.** D43 Q1 owns the transaction API, and `rollback` is in its core names. Hand the commit-consumption contract to the database round, so the two can't diverge.
- **N5: hook payloads** (868–869). "Precompute the message at acquisition" can't include native error text (strerror, driver messages), which is only known at failure time. A fixed-capacity inline text field in the reserved slot (truncated) or a static code-to-message table keeps D40 Q4's `$__abandon__ = ():>void | DbError => db_rollback(handle)` useful.
- **N6: a repeated OutOfMemory has no reserved stack node** (886–890). An inner boundary returns `OutOfMemory & FileCloseFailed` as a value, then the outer function's allocation is refused. Under D17 the collision needs a stack link that nothing reserved. Reserve one in the unwind record.
- **N7: example details.** D11 writes `xs.pop`, while LANGUAGE.md writes `xs.pop()` (lines 307 and 819). D16's `if xs is? A printl("unreachable…")` (416) is a test that is always false; drop it rather than show a dead branch. "D1, clarified" (186–208) is the precise reading of an open question and changes only the outcome for redundant selectors, so it should be report only and not a new question for David.
- **N8: M6 residual, pre-existing.** With `Left=[x:int64|string="none"]` and `Right=[x:int64=0]`, the later default decides whether `Right & Left` is constructible at all. Say whether an ill-fitting later default makes the declaration an error or only its constructor. LANGUAGE.md 4226–4231 is silent.

## Question 3: format of what stays

Only D17 (with D16's selector clause) stays.
- **What it has:** it leads with `save_two` in its enclosing function, then the question, a recommendation and reversibility.
- **The example:** it leaves out the caller, which is where the cost lands. Lead with a caller handling the result (SF2).
- **The recommendation:** "stable shape" is wrong at the function level, and the alternatives (a) and (b) are missing.
- **The text:** too much internal detail ("accumulated kind", "logically extended without mutating its storage", "cleanup boundary") is on the decision path. Cut it to the observable rule.

If the others were kept, D9, D11 and D16 have the same problem of a question buried in internals, and D14 says itself that it isn't ready.

## Question 4: D40 and cancellation

- **D40 block end:** compatible, apart from MF1 (D40 Q1 against D10) and D17's unstated dependence on D40 Q2 (SF2). D15 is a clean extension of D40 Q1. C5's explicit consuming closes fit D40's early completion.
- **Cancellation round:** D2, D3 and D7 are byte-identical to round 4, which I checked. The C5 rows say "already permitted interruption", and D14's clause defers. The only conflict is D4's `wrap` (N3). D16's rule that elements fit whole in `error`, and the holding rule, are compatible with `Canceled` becoming control only.

## D9–D17

| Item | Keep / take | Reason |
|---|---|---|
| D9 projection ambiguity | Take | Rejecting ambiguity at compile time, with `T?` meaning absence only, is the existing safe meaning. The fix is to name the leaf, and there is no new syntax. The union-target and complement detail is trivia. |
| D10 acknowledgment and transport | Take, and move the real choice into D1 | Copies and transport follow from "only a naming action removes a part". The observable choice (combinations must be acknowledged, singles needn't be) belongs in D1 with David's sketch (SF1). |
| D11 conservative diagnostic | Take | It is the only rule consistent with D1 (no silent pass-through), and the fix is easy. Determinism is internal (SF5). |
| D12 close before decode | Take | A library implementation order. The common path is unchanged; only a rare double failure changes shape. |
| D13 commit consumes | Take, and hand to D43 | Consuming commit is the Go and Rust norm, and `commit() or_throw` is unchanged. The database round owns it (N4). |
| D14 replacement state | Not ready; fold into D5 | It is new surface (a member) that hasn't been cold-read or dogfooded. Prefer a `FileSyncFailed` name in D5 (SF3). |
| D15 refusal carries cleanup | Take | A direct extension of D40 Q1 and the existing allocation policy. Add held values (MF2). |
| D16 stack contracts | Take, except the selector clause, which moves into D17 | Nonempty, ordered, error-only, nested and costs are natural. Selector opacity is a real choice David asked about, and it only bites through D17. |
| D17 repeated-kind stack shape | **Keep**, with D16's selector clause | Fails test (1): lowest graded (discoverability 3), and the "stable" shape still varies by exit. Show alternatives (a) and (b) (SF2). |

**One of D9–D17 stays as a question for David** (D17, absorbing D16's selector clause). D14 returns later as a D5 name once it has been cold-read.
