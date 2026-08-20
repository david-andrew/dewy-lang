# Learning Dewy

This directory is the narrative, example-oriented Dewy guide published
under `/learn/` on the language website.

## Editorial Policy

Write the guide as if Dewy is complete. Only the introduction should
mention that the compiler is early and some examples may not run yet.
Don't track implemented vs planned behavior on every page.

- Settled features are written in the present tense, whether they compile
  today or not.
- Constructs that are still TBD keep an entry. Say the feature is not
  yet determined. Don't invent syntax.
- Don't invent standard-library APIs, CLI flags, or packages that were
  never designed.

Comments are `#` for a line and `#{ ... }#` for a block. Prefer `=?` /
`not=?`, juxtaposition calls such as `printl"Hello"`, `let` / `const` /
implicit `let`, and `:>` return types.

The [language reference](../reference/) is the implemented-semantics
companion. This guide teaches the intended language.

## Build the Complete Site

From the repository root:

```sh
python site/scripts/build.py
```

The generated website is written to `site/dist/`.

### Local Development

When working only on the guide, mdBook can provide live reload:

```sh
cd site/learn
mdbook serve
```
