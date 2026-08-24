# Welcome to Dewy

Dewy is a general-purpose programming language designed to make everyday programs direct to write, clear to read, and safe to grow.

The same language should feel comfortable for a short script, a command-line tool, a graphical application, a server, a game, numerical work, or systems software. Dewy starts with convenience rather than ceremony, then uses static types and compile-time reasoning to keep larger programs dependable.

This book teaches Dewy through examples. It begins with the small set of ideas that organize the language, then develops functions, control flow, data, types, modules, and larger programming patterns in an order that lets each chapter build on the last.

## What Dewy Feels Like

Dewy favors ordinary expressions that compose instead of a separate syntax feature for every task:

```dewy
let label = if unread_count =? 0
    "Inbox"
else
    "Inbox ({unread_count})"

let visible = [
    loop message in messages
        if not message.archived
            message
]
```

The conditional produces a string. The loop produces the messages that pass its condition, and `[]` collects them into an array. These are not special “conditional expression” and “list comprehension” sublanguages; they are the same `if`, `loop`, and block expressions used everywhere else.

Several principles recur throughout Dewy:

- values copy by meaning, while `@` makes intentional shared mutation visible;
- functions, objects, and control flow use the same expression grammar;
- strings operate on user-perceived characters rather than exposing UTF-8 bytes by accident;
- ranges state their bounds directly;
- types can express useful facts and guide efficient representations without turning routine code into proof notation;
- domain features such as physical units build on the ordinary type and operator model.

## How to Read This Book

Start with [Dewy at a Glance](pitch.md) for a compact tour, then follow [Getting Started](ch01/00-getting-started.md) if you want to run code. The core chapters are intended to be read in order. Later sections can be used independently once you know the basics.

This book describes the intended Dewy language. When the current compiler has not yet reached a described feature, an unobtrusive note points to [Language Design and Compiler Support](appendices/language-and-compiler.md). Exact syntax and semantic rules live in the [Dewy Language Reference](../reference/).
