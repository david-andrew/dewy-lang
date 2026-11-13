# Cleanup round 7 summary

Current packet: [round7.md](round7.md), [27 programs](programs-r7/README.md), and [dogfood-round7.md](dogfood-round7.md). Round 6, its programs, and both review/regrade files are preserved.

**Recommend block-end observable cleanup, explicit grouped scope acknowledgement with ordered propagation, and drop defer using the functional and concrete owner rewrites, with local callback lifetime/effect validation required before implementation removal. Floor: 3.** All recommendations lead with full-function before/after examples in round7.md.

## Review fixes

- **M1:** One parse rule: suffix attaches to the complete operand expression, independent of types. Group an iteration/arm as `({ … } or_throw)` to mark its block; an outer loop/if/match suffix does not cover nested scopes. `parallel { … }` owns a scope, `parallel ( … )` does not. All seven traces (a)–(g) are supplied with full functions.
- **M1 order:** select ordinary failure values first, then clean up. Pending E plus cleanup F returns `errors.join(E F)`; lone F remains F. Do not re-test the joined group's kind. Unselected exceptions remain data; records/arrays are not scanned. Selective markers must cover all possible direct cleanup failures. Selector-possibility checking includes those direct cleanup alternatives. No new pair type or per-iteration buffering.
- **M2:** reject fallible or unknown inline kept guards, even in return expressions, with a named-place/marked-block fix. Infallible inline mutex guards retain statement lifetime. No outer marker silently authorizes a hidden statement-end failure.
- **S1:** added Batch whose observable hook requires a large owned buffer, plus short-scope repair and hook-free control. The tally now favors last-use: raw L/M/B **6/7/7**, severity **15/15/17**. Block-end remains a source-predictability preference, not the numerical winner or an empirical finding.
- **S2:** a real three-line internal SavedDiagnostics type matches the foreign defer's unwind coverage and restore-before-unlock order; owner call site is one statement shorter, first use two lines longer including definition. Defer has no remaining capability case in the tested set: the shared-channel owner also matches it, and program 27 supplies a concrete explicitly shared callback held in a local owner for a borrowed bool place. Its return/escape is rejected. Validate preservation of that borrow/effect contract before removing implementation support; a copied bool or unsafe pointer is not an equivalent substitute. The callback owner adds real ceremony.
- **S3:** marker checking is conservative. Consume/move on every continuing path removes the obligation; maybe-live, unknown and budget-widened states do not. Generic instantiations preserve summaries and report missing coverage; unsupported effect contracts reject rather than guess.
- **S4:** lock arithmetic uses exact int, without a fabricated int64 bound. Normal allocation policy still applies.

The supplied errors design (round2.md amended by round3.md) now also supports real leaf splitting and remainder forwarding in program 12, preserving cancellation. Owning failure payloads are moved/borrowed under that design, never cloned by the cleanup rules.

## Remaining costs and approval

O/D3 remains for grouping, skipped-exit acknowledgement, and selected errors versus error data. Foreign contracts remain K3; callback-owner compiler validation remains K4; manual shared-channel coordination remains S3. The supplied errors design's explicit-allocation-exhaustion grouping gate is also still K3. These are paper grades with line evidence, not compiler results or independent reader scores.

David must approve uniform observable lifetime; exact postfix/body/arm attachment and all-exit acknowledgement; value-before-cleanup selection with conservative selective coverage and errors.join integration; rejection of fallible/unknown inline/implicit short-lived duties; and replacement of the provisional defer decision with drop, gated on local callback-owner lifetime/effect validation. No incidental new borrowed-place/capture facility, error type, keyword or public resource name is approved here.

Checked local links, cited line ranges, score reasons, hook forms, program counts, tally arithmetic and preservation hashes. No compiler/runtime/native adapter was executed. All writes stayed under `~/dev/tmp/par10/cleanup6/`; the Dewy checkout and sibling errors design were read-only; no commits or delegates.
