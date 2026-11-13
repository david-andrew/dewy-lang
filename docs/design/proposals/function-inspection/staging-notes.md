# Scope of this staged proposal

Read round3.md with review-round3.md. The review recommends a database-filter-only pilot of code.Function<F> against the typed-field-selector baseline. The older summary describes the broader design; it is not approval to ship collection interception, assertions, GPU kernels or automatic differentiation together.

The function-inspection names have not been cold-read. names.txt is a candidate inventory, not naming evidence. There is no cold-read.md in this folder.

Before the pilot, make the typed planner/fallback boundary concrete and account for graph extraction, planning, retained data and emitted code. Budget exhaustion must use the original checked predicate. Optional optimizer budgets must not consume the separate deterministic resources needed by a future demanded transformation with no semantic fallback; the review marks that shared-budget design as a must-fix for the broader design. Automatic differentiation and $__collect__ are deferred from the pilot.

These are paper designs. No implementation, performance gain or all-5 usability result is claimed.
