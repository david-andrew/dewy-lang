# Implementation compatibility

The defining compatibility goal for µDewy is:

> Every well-formed µDewy program should compile and exhibit the same visible
> behavior under both the µDewy compiler and the full Dewy compiler.

That parity is still in progress. The repository contains executable fixtures
and bootstrap-parity tests for the Python µDewy compiler and the compiler
implemented in µDewy.

The source suffix is conventional rather than semantic: Dewy's type checker
does not choose a weaker mode merely because a file ends in `.udewy`. µDewy's
own compiler accepts only the strict subset defined by its specification.

See the [µDewy specification](/udewy/reference/) for the definitive subset
language and backend contracts.
