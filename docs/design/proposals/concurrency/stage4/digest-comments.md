# Comments on the stage-4 decision digest

## Disagreements and risks

- **#114: the name says the opposite of the contract.** `$parallel_safe apply` reads as "apply is safe to call in parallel". What it actually means is "callbacks passed to apply get checked". The digest also infers the per-parameter requirements, so the tag only opts in to a fact the analysis already holds ("proofs from facts, not incantations"). Suggestion: infer forwarding by default, as the round-1 design proposes. Keep a tag only to pin the contract on exported APIs, so a body edit can't silently loosen it. Also reject the tag on declarations that have no callback parameter: `$parallel_safe myfn = () => 42` is a silent no-op.
- **#118 admission.** "Admission cannot wait behind children needing unadmitted siblings" means that, without a proof, every item gets a live task, so memory grows as O(len xs). Say so explicitly. Bounded-width admission should apply only when children are proven not to wait on siblings.
- **#1/B migration.** Handlers such as `??<Closed>` written against the old `void | Closed | Canceled` must become compile errors after the switch to `Unsent<T>`, not dead branches. State "a typed catch on an absent alternative is an error" as part of B.
- **Scope (Rule 1).** Stage 4 bundles six primitives, each with its own lifetime protocol and verification load. Suggestion: land SPSC, MPMC, `select` and B first, since they share verbs and `Unsent`. Add Sequencer, SeqLock and Snapshot when a named workload (game loop, config reload) needs them.
- **#5 late subscribers.** "Require initial subscribers" and "last reader departure closes" rule out dynamic fan-out, such as game systems that come and go. Mark late subscription as a planned additive extension, or point users to Channel-per-subscriber.

## Confusing to a reader

- **#11 vs #12.** #12 binds the ordinary outcome, so `item` in #11 is `Message | Closed | Canceled`, and `describe(item)` then receives a union. Show `describe(item or_throw)` or a `match`, and say what the trailing `or_throw` actually catches.
- **#4/#15 examples** use `try_send(...) or_throw`. `Full`/`Busy` are routine on a try path, and throwing them also throws away the payload. Show a `match` or `??<Full>` instead.
- **BLUF line 3.** "Serial execution… can deadlock waiting siblings" reads as a present bug. Reword to "would deadlock if waiting callbacks were admitted".
- **#3.** "Sender close/drop drains" should say "the receiver may drain remaining items, then sees `Closed`".
- **#2 vs #4.** `spsc<Message 64>()` takes capacity as a type argument, while `mpmc<Message>(64)` takes it at runtime. Add one sentence explaining why the two differ.
- **#7.** `previous` is undefined, and calling the result `old` is misleading. Use `current = position.try_read() ??<Busy> fallback`.

## Syntax

The syntax otherwise follows Dewy conventions: space-separated arguments, `=?`, `??<T>`, `@square`, tags on the same line or the line before, and `$runtime_assert` all exist.

## Verdict

The digest is sound and well-staged on semantics. Approve #1–#15, A and #118 broadly. Push back on #114 (prefer inference and a better name), and fix the #11 example before David reads it.
