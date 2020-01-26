#ifndef PARSER_C
#define PARSER_C

#include <stdio.h>

#include "object.c"
#include "vector.c"
#include "dictionary.c"
#include "set.c"

#include "scanner.c"


//definitions for the AST

//forward declarations
void update_meta_symbols(dict* meta_symbols, vect* tokens);





void update_meta_symbols(dict* meta_symbols, vect* tokens)
{
    /*
        TODO
        - check if the end of a meta rule has been reached.
        ---> if so, eat all tokens from the tokens list, and store them into the symbol table
        - handle #lex(rule)?
    */
}

#endif