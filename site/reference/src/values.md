# Arrays, objects, and strings

## Arrays

Implemented arrays are homogeneous. Exact-length arrays carry a length
refinement, expose `.length`, and support constant or flow-proven indexing.
Some non-escaping local literals and module constants lower directly to raw
storage. General dynamic-length and escaping arrays remain incomplete.

## Objects

Object literals contain named fields in source order and have structural types.
Fields can be read and mutated when the originating binding permits it. Function
fields can read sibling fields, and zero-argument function fields are called by
ordinary member access.

## Strings

Strings are immutable sequences of Unicode extended grapheme clusters. Length,
indexing, slicing, iteration, exact equality, grapheme ranges, UTF-8 byte views,
Unicode scalar views, and grapheme-array conversion are implemented. Equality
currently preserves exact scalar spelling rather than normalizing text. Slice
endpoints may be computed at runtime when flow-sensitive bounds analysis proves
their effective open or closed boundaries stay within the string.
