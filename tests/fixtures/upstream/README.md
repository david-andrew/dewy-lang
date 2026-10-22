Focused regression fixtures.

These are baseline behavior tests for shared arrays, copies, bounds, loop
lowering, unions and match dispatch. `.expected` files
are the original `.out` files, renamed to distinguish them from build artifacts.
Run through `tests/test_core_upstream.py`; no reference
checkout or network access is needed.
