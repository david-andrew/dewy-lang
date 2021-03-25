/**
 * How to use:
 * 
 * dewy [-s] [-a] [-p] [--verbose] infile
 * 
 * -s scanner
 * -a ast
 * -p parser
 * 
 * --verbose prints out repr instead of str
 * 
 */

#include <stdlib.h>
#include <stdio.h>
#include <stdbool.h>
#include <string.h>

#include "utilities.h"
#include "object.h"
#include "vector.h"
#include "metatoken.h"
#include "metascanner.h"
#include "metaast.h"
#include "metaparser.h"


#define run(ID, cmd, source, verbose) {     \
    bool display_##ID = false;              \
    /*if no run commands given, run all*/   \
    if (argc < 3 || (verbose && argc < 4))  \
        display_##ID = true;                \
    for (int i = 0; i < argc; i++)          \
        if (strcmp(argv[i], #cmd) == 0)     \
            display_##ID = true;            \
    if (display_##ID) {                     \
        printf(#ID" output:\n");            \
        run_##ID(source, verbose);          \
        printf("\n\n");                     \
    }                                       \
}

//forward declare run functions
void run_scanner(char* source, bool verbose);
void run_ast(char* source, bool verbose);
void run_parser(char* source, bool verbose);


int main(int argc, char* argv[])
{
    //determin if verbose option is set
    bool verbose = false;
    for (int i = 0; i < argc; i++)
        if (strcmp(argv[i], "--verbose") == 0) 
            verbose = true;

    if (argc < 2)
    {
        printf("Error: you must specify a file to read\n");
        return 1;
    }

    //load the source file into a string
    char* source = read_file(argv[argc-1]);

    run(scanner, -s, source, verbose)
    run(ast, -a, source, verbose)
    run(parser, -p, source, verbose)

    free(source);

    return 0;
}


/**
 * Run the input through the scanning process.
 */
void run_scanner(char* source, bool verbose)
{
    //set up structures for the sequence of scanning/parsing
    initialize_metascanner();
    vect* tokens = new_vect();
    obj* t = NULL;

    while (*source != 0 && (t = scan(&source)) != NULL)
    {
        vect_push(tokens, t);
    }

    for (size_t i = 0; i < vect_size(tokens); i++)
    {
        t = vect_get(tokens, i);
        verbose ? metatoken_repr((metatoken*)t->data) : metatoken_str((metatoken*)t->data);
    }

    vect_free(tokens);
    release_metascanner();
}


/**
 * Run the input through the ast building phase.
 */
void run_ast(char* source, bool verbose)
{
    //set up structures for the sequence of scanning/parsing
    initialize_metascanner();
    vect* tokens = new_vect();
    obj* t = NULL;

    while (*source != 0 && (t = scan(&source)) != NULL)
    {
        vect_push(tokens, t);
    }
    
    //while tokens still contains real tokens
    while (metatoken_get_next_real_token(tokens, 0) >= 0)
    {
        if (!metaparser_is_valid_rule(tokens)) { break; }

        obj* head = metaparser_get_rule_head(tokens);
        vect* body_tokens = metaparser_get_rule_body(tokens);
        metaast* body_ast = metaast_parse_expr(body_tokens);

        // printf("before node reductions\n");
        obj_print(head);
        if (body_ast != NULL)
        {
            printf(" = ");
            if (verbose) { metaast_repr(body_ast); } 
            else { metaast_str(body_ast); printf("\n"); }
        }
        else { printf(" = NULL\n"); }

        //apply ast reductions if possible
        if (body_ast != NULL)
        {
            //count if any reductions were performed
            int reductions = 0;
            while ((metaast_fold_constant(&body_ast)) && ++reductions);

            //if applied any reductions, print them out
            if (reductions > 0)
            {
                printf("REDUCED AST: ");
                obj_print(head);
                printf(" = ");
                if (verbose) { metaast_repr(body_ast); } 
                else { metaast_str(body_ast); printf("\n"); }
            }
        }

        //free up ast objects
        body_ast == NULL ? vect_free(body_tokens) : metaast_free(body_ast);
        obj_free(head);
    }

    //print out any unparsed input
    if (metatoken_get_next_real_token(tokens, 0) >= 0)
    {
        printf("unparsed tokens:\n");
        for (size_t i = 0; i < vect_size(tokens); i++)
        {
            t = vect_get(tokens, i);
            metatoken_str((metatoken*)t->data);
        }
    }

    vect_free(tokens);
    release_metascanner();
}


/**
 * Run the input through the parser item building phase.
 */
void run_parser(char* source, bool verbose)
{    
    //set up structures for the sequence of scanning/parsing
    initialize_metascanner();
    initialize_metaparser();
    vect* tokens = new_vect();
    obj* t = NULL;

    //get all tokens
    while (*source != 0 && (t = scan(&source)) != NULL)
    {
        vect_push(tokens, t);
    }
    
    //parse rules until we get stuck
    while (metatoken_get_next_real_token(tokens, 0) >= 0)
    {
        if (!metaparser_is_valid_rule(tokens)) { break; }

        obj* head = metaparser_get_rule_head(tokens);
        uint64_t head_idx = metaparser_add_symbol(head);
        vect* body_tokens = metaparser_get_rule_body(tokens);
        metaast* body_ast = metaast_parse_expr(body_tokens);

        //apply ast reductions if possible
        if (body_ast != NULL)
        {
            //count if any reductions were performed
            int reductions = 0;
            while ((metaast_fold_constant(&body_ast)) && ++reductions);
        
            //attempt to convert metaast into sentential form
            
            metaparser_insert_rule_ast(head_idx, body_ast); 
        }

        //free up ast objects
        body_ast == NULL ? vect_free(body_tokens) : metaast_free(body_ast);
        // obj_free(head);
    }

    print_grammar_tables();

    //print out any unparsed input
    if (metatoken_get_next_real_token(tokens, 0) >= 0)
    {
        printf("unparsed tokens:\n");
        for (size_t i = 0; i < vect_size(tokens); i++)
        {
            t = vect_get(tokens, i);
            metatoken_str((metatoken*)t->data);
        }
    }

    vect_free(tokens);
    release_metascanner();
    release_metaparser();
}