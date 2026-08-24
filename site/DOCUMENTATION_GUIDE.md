# Dewy documentation guide

This file defines the editorial contract shared by the Learn and Reference books.

## Positioning

Dewy is a general-purpose programming language designed first for clear, convenient everyday programming. It should feel suitable for a small script, an application, a service, a game, a compiler, or systems software without asking the programmer to trade away strong static guarantees as the program grows.

Scientific computing, engineering, mathematics, robotics, and other STEM work are important applications of that general-purpose design. They should be highlighted when the subject calls for them, but they are not the default frame through which every language feature is explained.

## Responsibilities of the books

The **Learn** book teaches the language in a deliberate sequence. It introduces an idea once, uses it in increasingly substantial programs, and links to the Reference for exact rules.

The **Reference** book defines the intended language by construct. It records syntax, static constraints, evaluation behavior, resulting types, and relevant errors without adopting a tutorial sequence.

The main text of both books describes Dewy's intended language rather than narrating the state of the current compiler. Settled behavior uses direct language such as “Dewy evaluates” or “this expression produces.”

## Design and implementation maturity

Language design maturity and compiler support are separate questions:

- **Settled design:** document normally, even if the compiler has not caught up.
- **Provisional design:** describe only the parts that have been decided and include a concise provisional-design note.
- **Open design:** record requirements and open questions in the design addendum; do not present speculative syntax as established behavior.
- **Implemented:** examples may be checked by CI and listed in the implementation addendum.
- **Not yet implemented:** keep the intended semantics in the main text and record the compiler gap in the implementation addendum. Use a footnote in the main text only when a reader is particularly likely to encounter the gap immediately.

Avoid broad “planned” or “not implemented” interruptions in normal teaching prose. Avoid visible TODO notes in published chapters.

## Content ownership

Every semantic rule should have one canonical home in the Reference. Learn may explain and demonstrate the rule, but should link to the Reference instead of reproducing exhaustive tables or edge cases.

The books may share tested examples, terminology, and small syntax tables. They should not duplicate whole explanatory sections.

## Examples

Examples should be marked in source metadata as one of:

- compiler-checked;
- parser-checked;
- design-only.

That metadata need not be shown to readers. A design-only example must still follow settled syntax, or be placed under a clearly provisional design section.

## Unpublished project queue

Future domain introductions, case studies, and standard-library explorations are retained in [`DOCUMENTATION_PROJECTS.md`](DOCUMENTATION_PROJECTS.md). A project enters a book's navigation once it offers a substantive, useful walkthrough rather than a placeholder page.
