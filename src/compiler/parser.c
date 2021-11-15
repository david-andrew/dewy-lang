#ifndef PARSER_C
#define PARSER_C

#include <stdio.h>
#include <stdlib.h>
// #include <inttypes.h> // for PRIu64

#include "metaparser.h"
#include "parser.h"
#include "vector.h"

/**
 * Global data structures used by the parser
 * Slots are a head ::= rule, with a dot starting the rule, or following a non-terminals)
 */

vect* parser_labels;

void initialize_parser() { parser_labels = new_vect(); }

void release_parser() { vect_free(parser_labels); }

void generate_labels()
{
    // for now just print that we are generating labels
    printf("Generating labels\n");
}

// P, Y, R, U, cI, cU

#endif