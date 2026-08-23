<!-- TODO, shouldn't this be way earlier? -->

# General Concepts

A few ideas show up in every chapter.

## Everything Is an Expression

Declarations, assignments, blocks, `if`, and `loop` are expressions. Declarations and ordinary assignments produce `void`. A block produces the values it expresses. That is why Dewy does not need a special `?:` form or a separate list-building syntax.

## One Grammar, Many Uses

`[]` is an array, a dictionary, an object, or an index, depending on what is inside. `{ }` is a scoped block and a generator. `=>` is a function. The same pieces combine instead of each feature inventing punctuation.

## Compile Time and Runtime

Types, units, and import paths are decided when you compile. They are gone from the running program once the compiler has used them. Values that must exist while the program runs keep whatever storage the compiler picks from how they are used.

## Comments and Names

`#` starts a line comment. `#{ ... }#` is a block comment. Identifiers are case-sensitive and allow a wider set of letters and decorations than most C-family languages.
