# Cancellation round 1: `Canceled` only where something can cancel

You are designing part of the Dewy language for its owner, David. You may only write in `~/dev/tmp/par13/cancel/`. Everything else, including the repo `~/dev/dewy-lang`, is read-only. Write `round1.md`, `programs-r1/` with one `.dewy` file per program, and `dogfood-round1.md`. Commit nothing.

## Background: what David said in conversation (2026-11-13), binding

David asked why `sleep` or `receive` would ever return `Canceled`. He compared hidden control flow to Jonathan Blow's objection to exceptions: code that looks straight-line but can be left anywhere demands vigilance, and Dewy avoids that by returning everything as values. The explanation he accepted has three parts:

1. **Cancellation is a value.** A wait that is told to stop returns `Canceled`. The function then leaves only where the programmer wrote `or_throw`, `return` or `break`, and between waits code runs straight through. Example:

   ```dewy
   slow = () => {
       printl"slow: start"
       let slept = sleep(5s)
       if slept is? Canceled printl"slow: woken early"
       printl"slow: done"
       "slow"
   }
   fast = () => { sleep(1s) or_throw; "fast" }
   main = () => { let winner = race(@slow @fast) or_throw; printl"winner: {winner}" }
   ```

   This prints start, woken early, done, then `winner: fast`.

2. **A proposed formal rule, which he liked.** Every task has a cancel request that behaves like a channel only its group can close. The group closes it for each unfinished task when the group ends early:
   - `race` gets a winner, or `first_ok` gets its first success;
   - a `parallel` item leaves the enclosing function through `or_throw`, `return` or `break`;
   - a `within` deadline passes.

   Every standard wait waits on its own event or the closed request, whichever comes first. "Every later wait returns `Canceled` again" then follows from a closed channel staying closed; today it is the level-triggered rule in LANGUAGE.md around line 3634, which David never explicitly approved. Two exceptions to Dewy's general rules must be stated and justified as unavoidable:
   - the request travels implicitly through calls, rather than as an explicit parameter like Go's `ctx`;
   - cleanup (`defer` and drop hooks) is shielded from it.

   He liked three levels for user code:
   - anything that calls a standard wait is already cancellable;
   - `check_cancel()` is a checkpoint for CPU loops with no waits (D41 Q1);
   - a custom wait can wait on its own event or the request, through `select` on a nameable request. `select`'s signature is still undecided, so keep that example honest about it.

3. **His own proposal, the core of this round.** `Canceled` should appear in a result type only where something can cancel. It should be inferred like Dewy's inferred waiting (no async colouring), the way his D4 decision gave a signal source that can't fire no `SignalUnavailable`:

   ```dewy
   main = () => {
       let res = sleep(10s)       # res is void: nothing here can cancel
       printl"late hello"
   }
   ```

   With no Ctrl-C handler, Ctrl-C kills the process: the OS default, which LANGUAGE.md around line 3833 already describes. `res` is never `Canceled`. The cancellable contexts are the items of `race`, `first_ok`, `within` and `parallel`, plus everything they call. **Every `parallel` item counts**, whether or not a sibling can leave early (David agreed). Otherwise adding an `or_throw` in one item would change the types inside another. In that case hover gives `void | Canceled` with a note that nothing in this block can trigger it. A function called from both kinds of context is compiled once per context. Its hover shows both behaviours and lists which call sites are cancellable and which are not.

   An `or_throw` on a call whose result has no error should warn. In this example `count_lines` handles everything itself, so `main`'s `or_throw` does nothing:

   ```dewy
   count_lines = (path:Path) => { let text = read_text(path) ?? ""; printl"{text.lines.length} lines" }
   main = () => parallel { show_progress(); count_lines(p"big.txt") or_throw }
   ```

4. **New idea from David: incidental work.** A `show_progress` loop that runs forever should not keep its `parallel` alive once the real work is done. Programmers may want to mark some work as keeping the group alive and other work as incidental: when only incidental items remain, the group cancels them. One precedent exists in decisions.md batch 9 and LANGUAGE.md around lines 3838-3842: a group's signal sources close once only signal waits remain. Design the general mechanism so that the signal rule becomes an instance of it rather than a special case. Weigh what form the marking takes:
   - a metatag prefixing the item, since metatags prefix what they attach to (decisions.md batch 8);
   - a library call;
   - something else built from existing constructs.

   Only new syntax or new spellings need David. Any proposed name must go through the cold-read kit (see Process). Also decide whether a separate "is the real work done?" check is needed, or whether `check_cancel()` covers incidental CPU loops.

## What to settle

- **Inference.** State the rule precisely. Cover:
  - function handles stored and called later (do they carry both compiled versions, or a runtime flag?);
  - recursion and mutual recursion;
  - library modules;
  - `parallel x in xs` loops and comprehensions;
  - `task.tasks` from D41 Q3;
  - `select`;
  - a `within` nested in a `race`.

  Say what the programmer sees in hover and diagnostics. Estimate the compile cost: the analysis must be demand-driven and state its complexity (AGENTS.md rule 4). Also estimate the code-size cost of compiling twice, and when to warn about it.
- **Where `Canceled` goes.** Check this claim and correct it if wrong: every `Canceled` is consumed by the group that caused it, so it never escapes into code that started no group and never reaches `main`.
  - `race` and `first_ok` drop the losers' results;
  - `within` turns its own cancel into `Timeout`;
  - a `parallel` leaving early drops its siblings' `Canceled`.

  Handle a cancelled sibling whose cleanup fails: D42 combines `Canceled & FlushError`. Say what the group keeps.
- **Knock-on effects on open items.** Read D41 and D42 in `docs/design/open_decisions.md`, and D40 for its Ctrl-C examples. List each place that changes, with the proposed new text in short form:
  - D42 Q2's spin warning can probably be dropped;
  - D42 Q3 `$explicit_cancellation`;
  - D42 Q7 exit 130 from Ctrl-C;
  - D41's description of Ctrl-C and `protect_from_cancel`'s "after Ctrl-C";
  - D40's "Ctrl-C cancels `save`" example.

  David's preferred Ctrl-C default is the OS default when nothing handles it. A program that wants cleanup writes `loop _ in signals.ctrl_c { …; return }` as a `parallel` item, which ends the group. Treat the current LANGUAGE.md rule as up for removal: an attached `.observe` with no interceptor requests root cancellation, which is a hidden source of `Canceled`.
- **The cancel request's name** for level 3. Give candidates for the cold read, and say whether `check_cancel` still reads right next to it.

## Binding context to read first

- `docs/design/decisions.md`: batches 3–10, especially:
  - batch 3, the D4 parallel surface, C1 and C3;
  - batch 9, signals and `()`/`{}` scoping;
  - batch 10, `&`/`and`, `Canceled` no longer special in `??`, and David's error-combination design.
- `docs/design/open_decisions.md`: D40, D41, D42.
- `docs/LANGUAGE.md`: roughly lines 3600–3860 (tasks, cancellation, channels, signals) and 270–282 (collectors).
- `docs/design/proposals/signals/summary.md`, and `docs/design/proposals/concurrency/` as needed.

## David's standing rules, binding

- **Exceptions and special cases.** Every exception to Dewy's general rules must earn its keep and be unavoidable. No context sensitivity without good reason; this round's inference is the justified case, so argue it.
- **Constructs and syntax.** Use existing constructs before inventing syntax. `()` is an unscoped block and `{}` a scoped one.
- **Friction and defaults.** Remove friction even if the compiler works harder, but warn about performance cost. Unsafety is opt-in.
- **Operators.** `&`/`and`, `|`/`or` and `~`/`not` are each one operator: symbols in type expressions, words in value expressions.
- **Spelling conventions:**
  - arguments are space-separated, and `=?` is equality;
  - `@f` is a function handle, and `$name` is a metatag that prefixes what it attaches to;
  - `or_throw` forwards an error and `??` substitutes a default; `??<~Canceled>` excludes a type;
  - zero-argument calls that return a value drop `()`, and void ones keep it;
  - strings are formatted only with `fmt`, and imports use `.dewy` files.
- **No model or tool names** in any file.

## Process

- **Dogfood: ten or more realistic programs.** Include:
  - your crawler (a feeder plus several workers sharing a channel);
  - a CLI with a Ctrl-C handler that saves on exit;
  - `race` and `first_ok` lookups;
  - `within`;
  - a progress spinner that is incidental work;
  - a function used in both kinds of context;
  - a long CPU loop with `check_cancel`;
  - a custom wait at level 3;
  - a server loop;
  - a library function whose callers differ.

  Grade each program 1–5 on obvious, discoverable, concise, safe by default and complete, against Python, Go, Rust, TypeScript and Swift. Cite the line for every score under 5. Grade honestly; an independent regrader will check.
- **Cold-read the names you propose.** Prepare the kit, but don't run it: list the candidate names in `names.txt`, shuffled, names only, and the coordinator runs the readers.

## Output

`round1.md`, in this order:
1. **The verdict, with minimal before/after examples** of 5–10 lines each, no history: Dewy's design leads with a minimal example, then the question.
2. **The rules.**
3. **The knock-on edits.**
4. **Questions for David.** Each has a minimal example, the question, a recommendation, and whether it can be reversed. Only genuinely new syntax, spellings or changed established semantics go here.

Final message: the round1 path, the lowest grade and why, and the questions for David. Budget: about two and a half hours.
