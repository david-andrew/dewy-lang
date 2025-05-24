# Syntax Highlighting
General ideas around how to do syntax highlighting for the language

## highlighting library
Syntax highlighting initially will be in tree sitter. When the language is self hosted, we can look at replacing the tree sitter highlighter with the language's parser itself, having a backend for generating AST generators that can be used by whatever syntax highlighters worked with tree-sitter (perhaps just a C backend with some special wrappers)

## Default Theme colors
I decently like the theme I came up with already on my website:
- identifiers are green
- operators are white
- keywords are blue
- parenthesis/braces/brackets are blue
- bools are blue
- string literals are orange
- number literals are light green
- comments are grey

probably could be more in depth highlighting with e.g. tree sitter. such as highlighting type annotations differently. and like below highlighting captured values vs uncaptured values. want highlighting to be richly related to the types present to, so tbd

## Marking expressed vs suppressed values that are captured by some higher context
basically I think there should be some indicator, perhaps a highlight or something, which tells you when a value is being expressed (rather than void/suppressed), and it is being captured in the higher context.
I think this will mainly be useful when making list comprehensions since any expressed value gets captured
```dewy
apple = 5
my_gen = [
    1         % literal values are highlighted as expressed
    apple     % expressed variables are highlighted as expressed
    some_fn   % if some_fn returns a value, it gets captured. if it doesn't it would be shown as suppressed
    loop i in 10..20 {
        some_side_effect();   % we wouldn't want to capture some_side_effect, so if it was highlighted, we'd know to suppress it
        i^2                   % we do want to capture the expression here
    }
]

% some regular uncaptured scope
{
    % none of these are captured, so all get highlighted as such
    1
    apple
    some_fn
    loop i in 10..20 {
        some_side_effect();
        i^2
    }
}
```