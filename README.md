# The Dewy Programming Language
Dewy is a general purpose programming language with a focus on engineering. 

For now, the main goal is to make my ideal language.

## Try it out
Thus far, only the compiler-compiler is even runnable. To run the compiler compiler

    $ cd src/compiler
    $ make dewy #alternatively `make debug`
    $ ./dewy path/to/grammar/file path/to/source/file

The project includes several test grammar/source file pairs in DewySpeak/tests/. e.g. an simple expression grammar/source could be run like so

    $ ./dewy ../../tests/grammar8.dewy ../../tests/source8.dewy

Note that the compiler-compiler is still in development, and can/will crash on incorrect grammar specifications (better error handling coming soon™), though source files shouldn't be able to cause crashes.

To run source text directly, you can use here strings like so

    $ ./dewy /path/to/grammar/file /dev/stdin <<< 'source text'

note that this will always add a newline to the end of the source text

## Language Documentation
Currently incomplete documentation is available at: https://david-andrew.github.io/dewy-compiler-compiler/

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
    * Once version 1 is released, If it runs on some version, it will run on all future versions
* (planned) simple unified package management system akin to ckan
* (probably) lots of other things...

## Language Examples
An out of date example of the language can be found in [language_benchmark.dewy](resources/language_ideas/example_programs/language_benchmark.dewy)

TODO->write better examples.

## Trello Project
For more information about the current state of the project, see the DewySpeak Trello: https://trello.com/b/YYsedENy/dewyspeak
