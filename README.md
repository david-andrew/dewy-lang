# Clustered Nonterminal Parsing
Archive of the C implementation of CNP (Clustered Nonterminal Parsing) for the Dewy language. This is largely a reimplementation of [C SRNGLR Parser](https://github.com/david-andrew/dewy-lang/tree/C_SRNGLR_Parser/), with a more modern parser approach.

## Try it out
To run the parser

    $ cd src
    $ make dewy #alternatively `make debug`
    $ ./dewy path/to/grammar/file path/to/source/file

The project includes several test grammar/source file pairs in DewySpeak/tests/. e.g. a simple expression grammar/source could be run like so

    $ ./dewy ../tests/8.grammar ../tests/8.source

Note that the parser can/will crash on incorrect grammar specifications (better error handling coming soon™), though source files shouldn't be able to cause crashes.

To run source text directly, you can use here strings like so

    $ ./dewy /path/to/grammar/file /dev/stdin <<< 'source text'

note that this will always add a newline to the end of the source text