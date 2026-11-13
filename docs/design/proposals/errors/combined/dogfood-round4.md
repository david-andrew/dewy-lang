# Dogfood, round 4

**Author regrade of `programs-r4/`, starting from the independent round-3 grades
(`review-round3.md`, "Independent grades").** A grade changes only where round 4 changed the design
or the program, and each change says why. Peer grades are the independent round-2 ones
(`regrade-round2.md`), unchanged; program 15's are the round-3 author grades, made the same way.
Nothing was compiled. O/D/C/S/K = obvious, discoverable, concise, safe by default, complete.

| Program | Independent R3 | Dewy R4 | Python | Go | Rust | TypeScript | Swift |
|---|---|---|---|---|---|---|---|
| 01 combine and match | 5/4/5/5/5 | 5/4/5/5/5 | 4/4/4/5/5 | 4/4/3/5/5 | 4/4/3/5/5 | 4/4/3/4/5 | 4/4/3/5/5 |
| 02 handler does not swallow | 5/4/5/5/5 | 5/4/5/5/5 | 4/4/4/5/5 | 4/3/3/4/5 | 4/4/3/5/5 | 4/4/3/4/5 | 4/4/3/4/5 |
| 03 form validation | 5/4/5/5/5 | 5/4/5/5/5 | 5/5/5/5/5 | 5/5/4/5/5 | 5/5/4/5/5 | 5/5/5/5/5 | 5/5/4/5/5 |
| 04 batch files | 4/4/5/4/4 | 5/4/5/5/5 | 5/4/4/5/5 | 5/4/4/4/5 | 5/4/4/5/5 | 5/4/4/4/5 | 5/4/4/4/5 |
| 05 cleanup written file | 4/4/5/5/5 | 4/4/5/5/5 | 4/4/4/4/5 | 4/4/4/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 |
| 06 two files fail to close | 4/3/5/5/5 | 4/3/5/5/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 |
| 07 parallel failures | 4/4/5/4/4 | 4/4/5/5/4 | 4/4/4/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/4/4/5 | 4/4/3/4/5 |
| 08 library context | 5/4/5/4/4 | 5/4/5/5/5 | 5/5/5/5/5 | 5/5/4/5/5 | 4/4/4/5/5 | 4/4/4/4/5 | 4/4/4/5/5 |
| 09 CLI locations | 4/4/5/4/4 | 4/4/5/5/5 | 5/4/4/5/5 | 4/3/3/4/5 | 4/3/3/5/5 | 4/3/3/4/5 | 4/3/3/4/5 |
| 10 retry | 5/4/5/5/5 | 5/4/5/5/5 | 5/4/4/5/5 | 5/4/4/4/5 | 5/4/4/5/5 | 5/4/4/4/5 | 5/4/4/4/5 |
| 11 combined records | 4/3/5/5/3 | 4/4/5/5/5 | 5/5/4/5/5 | 5/5/4/5/5 | 5/5/4/5/5 | 5/5/4/5/5 | 5/5/4/5/5 |
| 12 cancel during cleanup | 4/4/5/5/5 | 4/4/5/5/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 |
| 13 generic pair | 4/4/4/5/5 | 4/4/4/5/5 | 4/4/4/4/5 | 4/4/3/4/5 | 4/4/3/5/5 | 4/4/3/4/5 | 4/4/3/5/5 |
| 14 transaction rollback | 4/4/5/5/4 | 4/4/5/5/5 | 4/4/4/4/5 | 4/4/4/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 |
| 15 upload boundary | 4/3/4/5/4 | 4/3/4/5/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/5/5 | 4/4/3/4/5 | 4/4/3/4/5 |

**Floor 3, in 06 and 15, both discoverable.** In 06, whether a close failure comes back bare or as
a stack depends on how many owners are live at that exit, and only hover shows it
([06:11-16](programs-r4/06_two_files_fail_to_close.dewy)). In 15, wrapping at a library boundary
needs two learned projections, `as error` and `as Canceled`
([15:22-29](programs-r4/15_upload_boundary.dewy)). Neither is a contradiction between rules: both
are rules to teach, with diagnostics that name them, and fixing either would take new surface (a
wrapping helper, or a different cleanup shape). The round-3 floor at 11 (completeness) is fixed by
C1.

## Changes, with evidence

- **04: 4/4/5/4/4 → 5/4/5/5/5.** The independent deductions were the read-close suppression and a
  comment saying close can't fail. Round 4 drops the suppression (C5): `read_text` reports its own
  close, the comment says so ([04:5-6](programs-r4/04_batch_files.dewy)), and the skipped list is
  `array<error>`, which holds a combination whole ([04:8](programs-r4/04_batch_files.dewy)). D4
  remains: forwarding cancellation before testing for errors ([04:11](programs-r4/04_batch_files.dewy))
  and knowing `error` holds combinations.
- **07: 4/4/5/4/4 → 4/4/5/5/4.** S: the read policy is no longer assumed
  ([07:8](programs-r4/07_parallel_failures.dewy)). K4 stays: the `parallel` block half
  ([07:16-24](programs-r4/07_parallel_failures.dewy)) needs the undecided extension.
- **08: 5/4/5/4/4 → 5/4/5/5/5.** No read-close assumption; the helper's result lists decoding and
  close failures separately, including `InvalidUtf8 & FileCloseFailed`, since this hand-written
  helper closes after decoding ([08:9-10](programs-r4/08_library_context.dewy)); `cause:error`
  holds any of them whole ([08:4](programs-r4/08_library_context.dewy)).
- **09: 4/4/5/4/4 → 4/4/5/5/5.** No read-close claim: both owners' closes can fail, giving
  `FileWriteFailed & ErrorStack<FileCloseFailed>` ([09:8-9](programs-r4/09_cli_locations.dewy)),
  each part printed with its origin ([09:14](programs-r4/09_cli_locations.dewy),
  [09:18-21](programs-r4/09_cli_locations.dewy)). O4/D4 remain: one line hides flattening, demand
  and caller attribution.
- **11: 4/3/5/5/3 → 4/4/5/5/5.** C1 gives one law for every `&`: minted operands are facets, plain
  records merge, a field from several sources needs `as`, and grouping can't matter. The "mint one"
  repair now works and is shown: a minted `Marker` beside a plain `Place`, two `x`s
  ([11:17-20](programs-r4/11_combined_records.dewy), [11:26-27](programs-r4/11_combined_records.dewy)).
  O4/D4: the reader must know that minting is what keeps a second facet.
- **14: 4/4/5/5/4 → 4/4/5/5/5.** `commit()` consumes the transaction on every outcome and rolls
  back itself on failure, so ownership after it never depends on the run
  ([14:12-16](programs-r4/14_transaction_rollback.dewy)).
- **15: 4/3/4/5/4 → 4/3/4/5/5.** It now holds four resources, including a helper process stopped
  if abandoned ([15:10](programs-r4/15_upload_boundary.dewy), [15:18](programs-r4/15_upload_boundary.dewy)).
  O4/D3/C4 remain for the wrapping policy ([15:22-29](programs-r4/15_upload_boundary.dewy)).
- **Unchanged:** 01, 02, 03, 05, 06, 10, 12, 13, with the independent reasons (whole-value arm
  binding; the all-parts rule now semantic but the same in these programs; the stack constructor;
  cleanup by hover; live-owner stack shape; the separate stack helper in 13).

## What stays below 5

- **Discoverability 3** in 06 and 15, above.
- **Discoverability 4** almost everywhere: whole-value arms, consume-all handlers, `ErrorStack`,
  `error` holding combinations, facets versus merged records. Taught rules.
- **Cleanup shown by hover** (O4 in 05, 06, 12, 14): D40 Q1's accepted design.
- **Concision 4** in 13 (a second helper for repeats) and 15 (wrapping).
- **The `parallel` block extension** (K4 in 07).
- **Gates, not grades:** the obligation analysis's cost; slot reservation and linking tested with
  allocation refused (C4's list); origin and trace sizes.
