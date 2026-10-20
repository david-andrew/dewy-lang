# Legacy corpus

Dewy programs from the pre-restart compiler's test suite, kept as a record of
intended language behavior. Top-level files and module directories were that
suite's fixtures; `e2e/` holds its end-to-end programs.

They are untested backlog material: no gate runs them, and many use features
the current compiler does not support yet. Their expected results live in the
old test files, in git tag `archive/master-pre-restart`.
