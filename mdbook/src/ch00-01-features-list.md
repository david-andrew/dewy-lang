# Features List

This page lists (TODO and will link to) all (TODO currently non-exhaustive) of the features built into Dewy. (TODO order the list to match the book's chapters)

- string interpolation
- physical unit literals
- map literals (map implemented as Python map) (i.e. dictionaries)
- bidirectional maps (using `<->`)
- vector literals (vector implemented as double ended quite)
- sets (not sure if there's a good literal notation for sets) (implemented similarly to maps)
- matrix math
- function literals + first class functions
- partially evaluated functions
- multi-variable returns
- range literals with specifiable inclusive/exclusive bounds
- type inference
- rust-esque memory management (more permissive)
- explicit copy vs reference semantics
- (maybe) lazy evaluation
- plain English binary/Boolean operators
  - also binary and Boolean operators are the same keywords
- compiled via compiler compiler and language specification written in EBNF-like macro language
  - GLR parser generator to allow for easy language extension
- multi-scope break/continue
- well defined scope semantics
- enums
- token literals (may replace enums)
- c interoperation
- syntax blocks (e.g. you could have a block that is in C, or a block that allows for set notation to be used natively. Think like how you can have a JavaScript block in html) (wouldn't it be funny if you could run basically any other language in the syntax blocks, and have them interoperate)
- llvm and maybe direct to machine code compilation
- composite arithmetic operators (e.g. `n^/2 = n^(1/2)`)
- optional/named function parameters
- list/map/set comprehension or generators
- in general, highly unified syntax (e.g. ternary is a consequence of blocks and conditionals, or objects and functions and blocks are basically the same thing)
- transpose operator as `'` (probably)
- extremely permissive identifier names (allows `&$@?!` in an identifier along with normal identifier letters/numbers. Might also include `#` as well, but TBD)
- walrus operator (from python 3.8)
- positional-only and keyword-only arguments
- rational datatype
- multithreading (default safe using rust-like memory management)
- JavaScript style function generators (see mdn docs) (possible in regular functions using `yield` keyword. Probably also mix with hastags to enter functions at arbitrary points)
- all dewy versions are backwards compatible, OR if an incompatible change must be introduced, the language will automatically provide a converted version of the file to the user. None of this python2 vs python2 BS