# Correctness review: scope blocks, round 1

I checked `round1.md` against the repository, and checked three parse and `return` behaviors with the current compiler. Round 1 picks the right direction: the block belongs to the caller, the scope function is an ordinary library function, and nothing escapes the braces. But the round leaves out the parse rule. Two of its rules cannot be written in the library shape it gives. One rule changes the types of every cancelable operation. And one program hangs. The 5/5 dogfood floor isn't credible while those stand.

Abbreviations: **R1** `round1.md`, **L** `docs/LANGUAGE.md`, **DEC** `docs/design/decisions.md`, **OD** `docs/design/open_decisions.md`, **DP** `resources/discussion_points.md`, **V5** `docs/design/proposals/concurrency/unified/proposal-v5.md`, **P/NN** `programs/NN_*.dewy`.

## Checked with the current compiler

- `f{1}` is an error ("'f' needs arguments"), so `{` is not a delimited argument today.
- `h() { printl"block" }` calls `h` and then runs the block as a separate statement. `if false h() { printl"after" }` prints `after`, because the block is not the `if` body.
- `let x:int = { if c return 1; 5 }` returns 1 from the enclosing function, so an assignment does not catch `return`.
- `defer` is not recognized by the Dewy front end ("unknown name 'defer'"). The rules about how `defer` fails therefore have no implemented precedent.

## Must-fix

### M1. The parse rule is missing, and the one sentence there is circular

R1:32 says "a `{` that opens the next statement is an ordinary block". But whether the `{` opens the next statement is exactly the question. L:1373 says "Whitespace always separates expressions: `a b` is two values", and statements need no separator (L:515 `{ let value:int64 = 41 bump(@value) printl(value) }`). So today `task.catch_ctrl_c { … }` is the expression `task.catch_ctrl_c` followed by a block, as checked above. R1 only works if the callee's declaration decides whether the brace is its argument. That is a parse directed by name and type, and R1 doesn't say so.

**Is it justified?** Mostly yes, if it is stated. Scope functions are second class (R1:34): they can't be values, so the head is always a statically resolved name, and resolution never depends on run-time types. DP:590 ("rely on type safety to determine what happens") and DP:806–810 already settle call versus multiply by the head's type. The difference is that this rule changes where statements end, and juxtaposition does not. The parser can still emit the same tree shape (call, then block) and let the resolver re-attach the block, just as juxtaposition is resolved after parsing. DEC:485 (batch 4: no context sensitivity without good reason) is met only if the round states the reason.

These cases are unspecified:
- **`if c g() { … }`.** Today the block is a separate statement that runs unconditionally. Under R1 it is `g`'s block when `g` has a scope parameter, and still a separate statement when it doesn't, so the same text runs conditionally or unconditionally depending on a declaration elsewhere.
- **A scope call in an `if`, `loop` or `match` head.** `match retry(3) { page:string => … }` gives the arms to `retry`. P/03:20 and P/07:28–30 work only because the scope call takes the first brace and the match's brace comes after `or_throw<Canceled>`. Swift bans trailing closures in statement conditions for this reason.
- **A scope call at the end of a line with `{` on the next.** In Allman style (`task.catch_ctrl_c` on one line, `{` on the next), does the brace attach? Since newlines don't end statements, R1 can't say "no" without a new rule.
- **`g() { … }` with an empty argument list**, **overloads** (`&`-combined functions where one variant has a scope parameter and one doesn't), and **methods** with scope parameters (`m.locked with v { … }`).
- **`with` as a keyword.** It is safe, since it is not used as an identifier in the tree and isn't in `juxt_keywords` (`compiler/juxtapose.dewy:16`). It must be reserved.

**Simplest fix.** State one rule: "A `{` on the same line right after a call to a scope function, or after `with pattern`, is that call's block. The callee is always a statically named function, so name resolution decides. Anywhere else a `{` is a block, as today." Add four corollaries:
1. A scope call takes the nearest brace, including in `if`, `loop` and `match` heads. If the head is then left with no body, report "these braces are `retry`'s block; parenthesize the call or bind it first".
2. `g() { … }` is the same as `g { … }`.
3. An overload set can't mix scope and non-scope variants of the same arity.
4. A same-line `{` after a call to a non-scope function warns ("this block is a separate statement; put it on its own line"). That closes today's `if c h() { … }` trap.

DP:601 lists `inc{10}`, an attached block, as a call with the block's value. That reconciles cleanly: a block argument to a `scope` parameter runs as part of the caller, and one passed to a value parameter is evaluated first. Say so in one line.

### M2. The protection `Timeout` change makes operation types depend on dynamic context

R1:68 says that while a shield is up, "an operation canceled by that shield's deadline returns `Timeout`, not `Canceled`". `check_cancel = ():>void | Canceled` (V5:166), `sleep`, file, stdin and process waits (L:3457–3459) all declare `Canceled`, not `Timeout`. Either every cancelable operation gains `Timeout` in its type everywhere, or its result type depends on where it is called. V5:192 explicitly rejects the second ("function types do not change based on an ambient metatag or dynamic call context"). The rule is unsound as written. For example, `search:>void | Canceled` (P/03:5) called inside a shield would return a `Timeout` its type lacks. P/09:5 already shows the pressure: `probe` declares `Timeout`, which nothing in its body can produce, and omits `Canceled`, which `read_text` can. The rule also breaks the parallel with `within` (L:3465: inner operations see `Canceled`, and the scope reports `Timeout`) and with "level-triggered per scope" (L:3457).

R1's reason is that a `Canceled` forwarded by `or_throw` from inside the braces would leave without translation. That case is real, but it is narrow, and M4 handles it at the scope boundary.

**Simplest fix.** Revert to V5:211. Operations inside see `Canceled`. The block's value is translated by provenance into `Timeout` when the shield's deadline caused it. A pending exit that carries that same `Canceled` is handled by M4(b). The common `{ save(best) }` case needs no rule beyond V5. Fix P/09:5 back to a plain file signature.

### M3. An early exit from a `tasks` block doesn't stop the children, so P/07 hangs

R1:65 says `tasks` "joins … before a `return` or `break` from the block leaves". V5:263 says "normal body completion joins its children. Stop persistent children explicitly before that join." Under V5 a callback `return` was local, so the rule was tolerable. Now `return` from the braces is the natural way to leave on Ctrl-C, and the rule turns that into a deadlock. P/07:35 `return`s from the `tasks` block while the `accept` child (P/07:9–17) is in `loop true { net.tcp_accept … }`. The join waits forever, so "Ctrl-C flushes the log … then returns from serve" never happens. The language already settled this for the construct `tasks` replaced: L:3445–3446, "Returning early from the body cancels and joins its children".

**Simplest fix.** A non-normal exit from a `tasks` block (`return`, `break`, `continue`, a forwarded failure) stops the group and then joins it. A normal result joins, as in V5. The library shape needs only a flag:

```dewy
tasks = (body:scope(group:Tasks)) => {
    let group = open_group()
    let finished = false
    defer { if not finished group.stop(); join(group) or_throw }
    let result = body(group)
    finished = true
    result
}
```

This is a semantic change, and it needs a sentence under R1's "If a semantic change is genuinely needed" clause. P/04:23's `group.stop()` then becomes unnecessary.

### M4. The library shape can't implement R1's own exit rules

There are three problems:
- **(a) `join` can't tell which `Canceled` is pending.** R1:51 has `join`'s failure replace a pending fail-fast `Canceled`, while "any other `or_throw` the block already started is kept". `defer join(group) or_throw` (R1:81) can't see the pending exit, so it can't distinguish the two. That makes the rule compiler magic for `tasks` alone, against the brief's "userspace could replicate".
- **(b) Shield translation has nowhere to happen.** The same gap blocks M2's translation of a pending shield `Canceled`.
- **(c) `join` in a `defer` is cut off by the cleanup grace.** L:3472 and `docs/design/safety_and_concurrency.md:249`: "Cleanup (`defer`, drop hooks) runs shielded, with a 100 ms grace deadline." Under parent cancellation, a join placed in a `defer` is cut off at 100 ms and returns with children still running. That breaks "groups join before returning" (R1:65, V5:274).

**Simplest fix: two general rules, one of them value-based.**
1. **A defer's failure replaces a pending exit that carries no failure, and never a pending failure.** This is decided by the value, so `return Missing` and `Missing or_throw`, which give the same function result in Dewy (L:3743 "Errors as values"), behave the same. R1:51 currently treats them differently, because it calls `return` "successful" whatever it returns.
2. **When a cancel scope opened by a scope function closes, a pending `Canceled` that this scope originated is replaced by the scope's reason** (`Timeout` for a deadline, the first child failure for a fail-fast group), and that reason becomes the call's result. Provenance already exists (V5:211). The rule belongs to cancel scopes, so `within`, `race`, `tasks` and `protect_from_cancel` share it, and the replacement value is already in each call's declared result type (`R | Timeout`, `R | E | Canceled`).

For (c), state that waiting for children in `join` isn't bounded by the cleanup grace. The children's own cleanup is.

### M5. A `scope` parameter has no result type, so scope functions are templates

`scope(ctrl_c:CtrlCListener)` writes parameters but no result. P/11:19–27 `retry` is declared `:>string | Attempts` and matches `page:string` on `body()`, which assumes the block returns a string. It can only be checked against a particular block, at a particular call site. That makes scope functions C++-style templates, re-checked per site. It contradicts R1:21 ("ordinary functions") and R1:102–104. It costs O(sites × body) of checking, when compile speed is a north-star goal, and recursion through a scope function would expand without end.

**Simplest fix.**
- **Type.** Give `scope` the function-type result spelling it already mirrors: `body:scope(group:Tasks :>R)`. It is generic in `R`, and `R` is inferred from the block. `retry = <T>(times:int body:scope(:>T | error)):>T | Attempts`. This is a natural extension of `(x:int:>int)`, not a new spelling.
- **Check once.** The scope function is checked once, generically.
- **Compile.** The block compiles as a non-escaping local function that returns its exit (normal value, `return v`, `break`/`continue` with a label, or a forwarded failure). `body(…)` either returns the value or starts that exit through the scope function's defers, and the call site then dispatches it.
- **Cost.** Inlining is an optimization, not the semantics. The per-site cost is then the block alone, which also settles the "specialization cost" question.

### M6. The caller's flow analysis doesn't know how often the block runs

R1:47 makes the block part of the enclosing function for borrow checking. But the enclosing function can't tell whether the block runs zero times, once (`catch_ctrl_c`), or up to N times (`retry`, R1:28). That matters for several analyses:
- definite initialization: `let x` … `task.tasks { x = 1 }` … `use(x)`;
- moves: `let s = owned` … `retry(3) { consume(s) }` is a use after move on the second run;
- the integer-domain rule that a `+= literal` runs "at most once … outside any loop" (L:335–337).

R1's only answer is to analyze the scope function's body at each site, which M5 removes.

**Simplest fix.** A `scope` parameter is invoked at most once, and the check is in the scope function: no path invokes it twice, and a path that doesn't invoke it returns a failure, as setup failures do. The caller then treats the braces as straight-line code on the success path. Drop repeated invocation from this round. `retry` is a demo, not one of the three scopes. If it comes back later, it needs a marked repeatable form, checked at the caller like a loop body (zero or more runs), and that marker is a new spelling for the cold-read test.

## Should-fix

### S1. `return` semantics: state the reading and cite it

DP:455 says `return` goes "up until the nearest thing that catches it, which could be an assignment, or it could be a function boundary". Here is what `let x = task.tasks with g { return 1 }` means under each reading:

- **Reading A** (R1, the implemented language, and the checks above): the group joins, the enclosing function returns 1, and `x` is never bound. The enclosing result must accept `1`.
- **Reading B** (the assignment catches): the `return` unwinds through `tasks`, the defers run, the code after `body()` is skipped, and `x = 1`. The function goes on.

Reading B makes `return` mean "leave the function" in statement position and "give the call a value" under `let`. That is context sensitivity, and it is the callback semantics David rejected, in the exact shape V5:283 used (`let answer = task.tasks(…)`).

**Reconciliation.** DP's own later text settles it the other way. DP:465's `return` inside a `[loop …]` collector "breaks out of function", and DP:502 names the boundaries as functions and generators ("`returns` stop at certain boundaries"). The compiler already implements "an assignment is not a boundary" for plain blocks. So: `return` targets the nearest function, or generator once generators exist. A scope block is neither, whether or not its call is bound. Giving a value from the middle of a block is DP:481's `express`/`yield` question, which is out of scope. Add the `let x = …` example and these citations to R1, and add a line that a future `yield` in a scope block belongs to the enclosing generator, as `return` does.

### S2. Defer-failure semantics are a new general rule, and the fall-through needs saying

R1:51 lets a `defer` `or_throw` and replace a pending exit. That is a rule about `defer` in general, which the language doesn't specify (L has no `defer` section, and the front end has no `defer`). The round says it isn't deciding cleanup (brief, constraint 4). Say that it applies to every `defer`, not only in scope functions (orthogonality, DEC:484), and use the value-based form from M4.1.

State the consequence: a dropped `return` or `break` resumes after the call with the failure as its value. So `bracket(…) with f { …; return x } ?? fallback` falls through into code the author thought was unreachable. Dewy's mandatory failure handling keeps this visible, but a hover note on `??` after a call whose block contains `return` would help.

### S3. The dogfood doesn't test what the brief asked for, and one program is broken

- No program sends `break` or `continue` from inside the braces to a loop outside them.
  - P/09's header (P/09:1) claims "break inside the shield", but the `break` and `continue` are in the match arms (P/09:11–12), outside `{ probe(port) }`.
  - In P/01, P/02 and P/05 the loop is inside the braces.
  - Add a program like `loop port in ports { task.protect_from_cancel(2s) { if probe(port) =? "ready" { chosen = port; break } } }`.
- P/07 hangs (M3). P/09:5's signature is wrong (M2). P/11 is untyped (M5).
- Every row is "5 5 5 5 5". After this review, the dogfood should be regraded before David sees it.

### S4. Cite David's code-snippet note: this mechanism is a restricted form of it

DP:2760–2790 ("Code Snippets as first class citizens") proposes a jai-style `Code` type with `#expand`/`#insert body(break=…)`. That is the same idea as a `scope` parameter: a library function that runs a caller's code, with the caller's `break` and `return`. R1 doesn't mention it, though the brief asks for DP to be searched before any spelling is proposed. Say that `scope` is a typed, hygienic, non-escaping, run-at-most-once special case of that idea. Explain why it is restricted (it is checked once and never re-scoped, and the block's names stay the caller's). Raise whether `scope` and DP's `Code` should share a name. Jai's `#insert body(break=…)` also shows the future extension point for a repeatable form (M6). R1:222's cleanup sketch should cite DP:1193 ("Coupling variable lifetimes with resources", `#on_cleanup`) as the binding-shaped answer it leaves room for.

### S5. "Spawned task" is too narrow

R1:28 forbids invoking the block "from a spawned task". It should forbid any other task: `group.spawn`, `parallel` items and loop bodies, `race`/`within` thunks, and a `@` handle to anything that captures `body`. The rule is "runs on the scope function's own task, synchronously". Say it that way.

### S6. Compare with the `parallel` keyword

DEC:434 already gives `parallel { … }` items the caller's `or_throw`. R1:233 rejects "three keywords", but it should say why `parallel` stays a keyword and is not a scope function: its items aren't one synchronous invocation on the caller. Otherwise readers will ask why two block forms exist.

## Nits

- The word `scope` is overloaded: cancel scopes (L:3457–3465), metatag scopes (L:701, 1021), and a parameter named `scope` (`lib/prelude/time.dewy:63`, `scope:string|none`). Cold-read it next to an alternative before it goes to `open_decisions.md`.
- R1:57 forbids storing *any* value the block receives past the brace. That is right for `CtrlCListener` and `Tasks`, and stricter than needed for a plain record (`Log[path]` in P/10). It's fine to keep for simplicity, but say it's deliberate. Passing `ctrl_c` to a helper parameter (`serve(lines ctrl_c)`, the v6 shape) must stay legal. Say so.
- R1:34: "one specialization per block type at that site, including a call in a loop" is unclear, and M5 makes it moot.
- R1:28: "It can be passed on to another scope parameter". Give the syntax (`inner(body)` or `inner { body() }`). The second follows from the rules already.
- `bracket`'s `<T E>` with `open:():>T | E` needs the inference to bind `E` to the error alternatives. Otherwise `T = Log | FileError, E = never` also fits. One sentence.
- P/07:28: inside `catch_ctrl_c` the parent isn't canceled by Ctrl-C, so the shield only adds a deadline. That's fine, but the comment should say the deadline is the point.
- R1:30: omitting `with` silently discards the passed values. That's fine, since these are parameters, not results, but contrast it with DEC batch 4's `;` rule in one line so nobody files it as an exception.

## Is one general mechanism the right size?

Yes, with M5 and M6 applied: a typed, checked-once, run-at-most-once, non-escaping `scope` parameter. It costs one parameter kind, one keyword (`with`), and one stated attachment rule.

The smaller alternative is ordinary lambdas whose control flow becomes the caller's when passed to a marked parameter (Kotlin `inline`). It saves `with` and M1, but it needs the same non-escaping, count and typing machinery. And it makes `=>` mean "my own `return`" or "my caller's `return`" depending on a declaration the reader can't see. That is worse context sensitivity than M1's, and it is the callback look David rejected (brief, quoting him: "like a block … it just works like usual").

The real cut is elsewhere: drop repeated invocation (M6) and the type-directed `Timeout` rewrite (M2). That leaves exactly the three scopes plus `bracket`.

## Summary of fixes

| # | Fix | Size |
|---|---|---|
| M1 | State the attachment rule: same line, static scope-function head, nearest brace, head diagnostic, no mixed overloads; warn on a same-line block after a non-scope call | rule text |
| M2 | Revert to V5 provenance translation of the block's value; restore operation types | delete one rule |
| M3 | A non-normal exit from `tasks` stops, then joins | one sentence, flag in the library shape |
| M4 | A defer failure replaces only a failure-free pending exit; a closing cancel scope replaces its own `Canceled` with its reason; `join` isn't bounded by the cleanup grace | two general rules |
| M5 | `scope(… :>R)` result typing; check once; block compiles to a non-escaping local function with an exit code | type rule, implementation note |
| M6 | At most one invocation, checked in the scope function; drop `retry` this round | one rule |
