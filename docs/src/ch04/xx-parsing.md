# Parsing
TODO
- library methods for parsing given some grammar+ specification (probably base on GLL and/or formalize the existing dewy parsing process into a nice library)
- able to generate tree-sitter compatible parsers implemented in C
- probably also have easy hooks into language server protocol and common language features
- should be easy to do regex like things too (i.e. since parsers are necessarily more powerful than regex, I'm more referring to ease of creating a simple parser should be as easy as making a regex)
    - `id_matcher = parser'[a-zA-Z_][a-zA-Z0-9_]*'`
