# DewySpeak
DewySpeak (Dewy for short) is a programming language that I am developing. The main goal I have for this language is to create a language that is the perfect language that I would want to use. Dewy is a general purpose programming language with a focus on engineering.

Important features of the language
* first class physical units (e.g. length, time, mass, temperature, etc.)
* first class functions (as well as many concepts borrowed from functional programming)
    * partial function evalutation
    * unified lambda vs regular function declaration
* simple, easty-to-read, elegant syntax
* optional type system with type inference
* rust-style memory safety gurantees
* powerful meta-programming capabilities 
    * ability to arbitrily add or modify language syntax
    * compiler-compiler uses meta-programming to add all features of the language (meaning compiler implementations are extremely simple/lightweight)
* (planned) extremely fast
* (planned) batteries included, i.e. common data structures, algorithms, libraries, etc. (will be) included
* guranteed syntax stability, backwards compatibility, etc.
    * Once version 0 is released, If it runs on version 0, it will run on the latest version
* (planned) simple unified package management system akin to ckan
* (probably) lots of other things...


To see a decent example of the language, see `/DewySpeak/language_ideas/example_programs/language_benchmark.dewy`. At the moment, this source file is a benchmark for the compiler to test that most of the features of the language work properly.

For more information about the current state of the project, see the DewySpeak Trello: https://trello.com/b/YYsedENy/dewyspeak
