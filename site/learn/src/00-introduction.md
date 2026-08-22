# Welcome to Dewy

This book is an example-led walk through The Dewy Programming Language, covering the syntax, programming model, and overall ideas behind it.

> **Development edition.** Dewy is an early language and the compiler is still catching up. Many examples in this guide may not run yet, nor be performant. For exact current behavior, see the [language reference](../reference/) and [implementation status](../status/).

## What Is Dewy

Dewy is a compiled, strongly typed general-purpose language with a focus on ergonomics and safety. Think the ease of Python or MATLAB but with static guarantees and performance.

Programs are ordinary source files. Top-level code runs in order. Everything is an expression. Common features that require special syntax rules (like functions, ternaries, list/dict comprehensions, zip/enumerate, classes, etc.) all fall out of Dewy's expression syntax.

## Who Dewy Is For

Dewy is for the **everyday programmer**: easy to pick up for small programs, but designed to scale to serious work. It aims to feel at home in scripts, numerical and scientific computing, systems programming, engineering, and general application code—you needn't choose a different language just because the problem got bigger, faster, or more technical.

## What's in This Book

- [Dewy at a Glance](pitch.md) for a quick look at the language
- [Features index](01-features-list.md) that links into the chapters
- [Getting Started](ch01/00-getting-started.md). Install and print hello
- [Hello, Many Worlds!](ch02/00-hello-many-worlds.md). Short sketches across many domains
- [Language Features Chapter](ch03/00-features.md). The main tutorial
- Later chapters on the standard library, general concepts, and case studies

## A Few Ideas Behind Dewy

Dewy tries to get more mileage out of fewer concepts. Blocks, conditionals, loops, and functions are expressions, and functions are ordinary values. Features that often need their own special syntax can instead emerge from combining those pieces.

There is one `loop`. Infinite loops, while-style loops, for-each loops, and walking several iterators together are variations of the same construct.

Dewy is statically typed, but you usually don't need to write the types the compiler can infer. Types can also carry additional facts through refinements, giving the compiler more information for both safety and optimization.

Technical computing is ordinary computing. Numbers can carry physical units, and arrays, broadcasting, complex numbers, and quaternions are built into the language's model rather than living in a separate world. `10kg * (30m/s)^2` is energy; `2kg + 3m` is a type error.

Strings are sequences of grapheme clusters. Indexing, slicing, and iteration operate on user-visible characters rather than bytes.

Dewy also avoids a tracing garbage collector. How a value is stored depends on how it is used, with the compiler responsible for keeping those choices safe.
