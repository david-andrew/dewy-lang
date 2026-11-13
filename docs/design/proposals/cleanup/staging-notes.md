# Scope of the staged cleanup additions

These are new files alongside the existing rounds 1–5. brief.md was staged as brief-round6.md, review-brief.md as review-brief-round6.md, and summary.md as summary-round7.md to avoid overwriting existing files. The existing cold-read.md (sets 20/21) is left in the repository; it is not copied or changed here.

Read round7.md and review-round7.md together. D40 presents the review's consuming close for simple loops and directly marked inner block for complex bodies, alongside round 7's grouped-body alternative. Round 7 recommends dropping defer; the review prefers keeping it provisionally for one-off restorations.

References to errors rounds 2/3 describe the design available during those cleanup rounds. Errors round4.md is now current: body & close returns one ErrorGroup, a child of exception outside error; a lone cleanup failure stays itself. Earlier ExceptionGroup and split examples are historical, not the current v1 recommendation.

This packet contains paper programs and stated implementation gates, not successful compiler tests.
