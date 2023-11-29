# Scannerless Right-Nulled Generalized LR Parser
Archive of the C implementation of SRNGLR parsing

## Try it out
Run the SRNGLR parser on a grammar:

    $ cd src
    $ make dewy #alternatively `make debug`
    $ ./dewy path/to/grammar/file path/to/source/file

The project includes several test grammar/source file pairs in `tests/`. e.g. a simple expression grammar/source could be run like so

    $ ./dewy ../tests/grammar8.dewy ../tests/source8.dewy

Note that the parser can/will crash on incorrect grammar specifications (better error handling coming soon™), though source files shouldn't be able to cause crashes.

To run source text directly, you can use here strings like so

    $ ./dewy /path/to/grammar/file /dev/stdin <<< 'source text'

note that this will always add a newline to the end of the source text

## Papers
The relevant papers detailing SRNGLR parsing are:
- [Right Nulled GLR Parsers](resources/Right_Nulled_GLR_Parsers.pdf) by Elizabeth Scott and Adrian Johnstone
- [Faster Scannerless Parsing](resources/Faster_Scannerless_Parsing.pdf) by Giorgios Economopoulos, Paul Klint, and Jurgen Vinju