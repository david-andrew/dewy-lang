# Dewy language reference

`src/` preserves the normative language design. Example fences are explicitly
design-only; fresh compiler evidence comes from declarative section associations
in `site/coverage-map.json`, generated into `site/dist/coverage/` on every build.
Do not weaken a language rule to fit the compiler or commit generated `book/`.

Build through `python3 site/scripts/build.py` from the repository root so links,
legacy anchors, coverage and highlighting are validated together.
