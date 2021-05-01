# DewySpeak
Dewy is a general purpose programming language with a focus on engineering. For now, the main goal is to make my ideal language.

## Try it out
Thus far, only the compiler-compiler is even runnable. To run the compiler compiler

    $ cd src/compiler
    $ make dewy
    $ ./dewy path/to/grammar/file path/to/source/file

The project includes several test grammar/source file pairs in DewySpeak/tests/. e.g. an simple expression grammar/source could be run like so

    $ ./dewy ../../tests/grammar3.dewy ../../tests/source3.dewy

Note that the compiler-compiler is still buggy, and can/will crash on incorrect grammar specifications. Additionally, the parse-forest build step of the parse is still in development, so at the moment, the parser only outputs whether or not a given input source is valid for the given grammar (accept/reject).

## Language Documentation
Currently incomplete documentation is available at: https://david-andrew.github.io/DewySpeak/

## Language Features
* first class physical units (e.g. length, time, mass, temperature, etc.)
* first class functions (as well as many concepts borrowed from functional programming)
    * partial function evalutation
    * unified lambda vs regular function declaration
* simple, easty-to-read, elegant syntax
* optional type system with type inference
* rust-style memory safety gurantees
    * suitable for realtime applications
* powerful meta-programming capabilities 
    * ability to arbitrily add or modify language syntax
    * compiler-compiler uses meta-programming to add all features of the language (meaning compiler implementations are extremely simple/lightweight)
* (planned) extremely fast
* (planned) batteries included, i.e. common data structures, algorithms, libraries, etc. (will be) included
* guranteed syntax stability, backwards compatibility, etc.
    * Once version 0 is released, If it runs on version 0, it will run on the latest version
* (planned) simple unified package management system akin to ckan
* (probably) lots of other things...

## Language Examples
An out of date example of the language can be found at [DewySpeak/resources/example_programs/language_benchmark.dewy](https://github.com/david-andrew/DewySpeak/blob/master/resources/language_ideas/example_programs/language_benchmark.dewy)

TODO->write better examples.

## Trello Project
For more information about the current state of the project, see the DewySpeak Trello: https://trello.com/b/YYsedENy/dewyspeak
