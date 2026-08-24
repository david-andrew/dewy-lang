# A Few Ideas That Organize Dewy

Dewy has a broad feature set, but a small number of ideas explain how those features fit together.

## Expressions Produce Values

Literals, calls, blocks, conditionals, and loops are expressions. An expression may produce one value, several values for a surrounding construct to collect, `void`, or no possible value at all.

This is why Dewy does not need a separate ternary operator, list-comprehension grammar, or statement-only form of control flow.

## One Grammar, Reused

The meaning of a construct comes from the expressions inside it and their types:

- `[]` can collect array elements, object fields, or key/value pairs;
- juxtaposition can call a function, index a value, or multiply compatible quantities;
- `{}` creates a scoped block wherever a block is needed;
- `=>` builds a function from a parameter contract and a body.

These uses are not chosen by textual guesswork alone. Parsing preserves meaningful alternatives and semantic analysis resolves them from context and types.

## Values by Default, Places by Request

An ordinary assignment or function argument supplies an independent value. The compiler may move or share storage when that cannot be observed, but source code does not accidentally create two mutable names for one value.

`@` requests a place when shared mutation is the point of the operation. Both the function signature and call site show that choice.

## Meaning and Representation Are Separate

A type describes what a value means. Its runtime representation is a compiler decision as long as the program cannot observe a difference.

An integer may have arbitrary-precision semantics while range analysis proves that a machine-width representation is sufficient. A physical unit may participate in type checking and then disappear entirely. An array descriptor may be omitted when its length and layout are already known.

## Compile Time Is Ordinary Language Territory

Types, import paths, dimensions, and other compile-time values use Dewy's expression model instead of separate mini-languages. Not every general compile-time operation is designed or implemented yet, but the organizing rule is that compile-time facilities should compose with the rest of Dewy rather than forming an unrelated macro language.

The next chapter starts with the first of these ideas: [expressions and the values they produce](../ch03/expressions-statements-blocks.md).
