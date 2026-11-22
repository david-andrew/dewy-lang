# Release notes

- The parser now reports the line AND column of every error.
- Roads, paths and files: the path module learned `with_suffix`.
- Fixed: a long line no longer wraps the report; the report's columns align.

Known issue: the tally of "the" counts The and THE alike only with --ignore-case.
