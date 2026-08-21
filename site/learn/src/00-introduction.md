# Welcome to Dewy

This book is an example-led walk through The Dewy Programming Language, covering the syntax,
programming model, and overall ideas behind it.

> **Development edition.** Dewy is an early language and the compiler is
> still catching up. Many examples in this guide may not run yet. For
> exact current behavior, see the [language reference](../reference/) and
> [implementation status](../status/).

## What Is Dewy

Dewy is a compiled, strongly typed general-purpose language aimed at
engineering. Think the ease of Python or MATLAB with the speed of C or
Rust.

Programs are ordinary source files. Top-level code runs in order.
Everything is an expression, so `if`, `loop`, and blocks produce values
instead of living in a separate statement language.

## Who Dewy Is For

Dewy is meant to be easy to start and strong enough for real work.
Scripts, numerical code, systems programs, and engineering problems that
care about units, arrays, and precise types.

## What's in This Book

- [Dewy at a Glance](pitch.md) for a quick look at the language
- A [feature index](01-features-list.md) that links into the chapters
- [Getting Started](ch01/00-getting-started.md). Install and print hello
- [Hello, Many Worlds!](ch02/00-hello-many-worlds.md). Short domain
  sketches, still stubbed
- [Language Features](ch03/00-features.md). The main tutorial
- Later chapters on the standard library, general concepts, and case
  studies

## Features

Dewy is ordinary step-by-step code, and functions are values you can
pass around when you want them.

`if`, `loop`, and `{ }` blocks are values. Many familiar features fall
out of that, rather than needing extra syntax.

There is one `loop`. Infinite, while, for-each, and walking several
lists together are the same construct with different conditions.

Types are checked when you compile, and you can leave them out. Write
one when you want it. Types can carry extra facts, called refinements.

Numbers can have units. `10kg * (30m/s)^2` is energy, and `2kg + 3m` is
a type error.

Strings are grapheme sequences. Indexing, slicing, and iteration walk
clusters, not bytes.

Complex numbers, quaternions, arrays, and broadcasting are part of the
language, not a separate package.

There is no garbage collector walking memory later. How a value is
stored depends on how you use it, and the compiler is meant to keep
that safe.
