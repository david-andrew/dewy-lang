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

#define match_argv(var, val)            \
{                                       \
    var = false;                        \
    for (size_t i = 0; i < argc; i++)   \
        if (strcmp(argv[i], #val) == 0) \
            var = true;                 \
}

//forward declare functions
void run_compiler(char* source, bool verbose, bool scanner, bool ast, bool parser);
void print_scanner(vect* tokens, bool verbose);
void print_ast(uint64_t head_idx, metaast* body_ast, bool verbose);
void print_parser();


int main(int argc, char* argv[])
{
    if (argc < 2)
    {
        printf("Error: you must specify a file to read\n");
        return 1;
    }

    //load the source file into a string
    char* source = read_file(argv[argc-1]);

    bool scanner, ast, parser, verbose;
    match_argv(scanner, -s)
    match_argv(ast, -a)
    match_argv(parser, -p)
    match_argv(verbose, --verbose)

    //if no sections specified, run all of them
    if (!(scanner || ast || parser))
    {
        scanner = true;
        ast = true;
        parser = true;
    }

    run_compiler(source, verbose, scanner, ast, parser);

    free(source);

    return 0;
}


/**
 * Run all steps in the compiler, and print out the intermediate results if the 
 * corresponding bool is true. If verbose is true, print out more structure info.
 */
void run_compiler(char* source, bool verbose, bool scanner, bool ast, bool parser)
{
    //set up structures for the sequence of scanning/parsing
    initialize_metascanner();
    initialize_metaparser();
    vect* tokens = new_vect();
    obj* t = NULL;

    //SCANNER STEP: collect all tokens from raw text
    while (*source != 0 && (t = scan(&source)) != NULL)
    {
        vect_push(tokens, t);
    }
    if (scanner) 
    {
        printf("METASCANNER OUTPUT:\n");
        print_scanner(tokens, verbose);
        printf("\n\n");
    }

    //AST & PARSER STEP: build ASTs from tokens, and then convert to CFG sentences
    if (ast) { printf("METAAST OUTPUT:\n"); }
    while (metatoken_get_next_real_token(tokens, 0) >= 0)
    {
        if (!metaparser_is_valid_rule(tokens)) { break; }

        obj* head = metaparser_get_rule_head(tokens);
        uint64_t head_idx = metaparser_add_symbol(head);
        vect* body_tokens = metaparser_get_rule_body(tokens);
        metaast* body_ast = metaast_parse_expr(body_tokens);
        if (ast) { print_ast(head_idx, body_ast, verbose); }

        //apply ast reductions if possible
        if (body_ast != NULL)
        {
            //count if any reductions were performed
            int reductions = 0;
            while ((metaast_fold_constant(&body_ast)) && ++reductions);

            if (ast && reductions > 0)
            {
                printf("Reduced AST: ");
                print_ast(head_idx, body_ast, verbose);
            }
        
            //attempt to convert metaast into sentential form
            metaparser_insert_rule_ast(head_idx, body_ast); 
        }

        //free up ast objects
        body_ast == NULL ? vect_free(body_tokens) : metaast_free(body_ast);
        // obj_free(head);
    }
    if (ast) { printf("\n\n"); }

    if (parser)
    {
        printf("METAPARSER OUTPUT:\n");
        print_parser();
        printf("\n\n");
    }

    //print out any unparsed input and tokens
    if (*source != 0) 
    { 
        printf("UNSCANNED SOURCE:\n```\n%s\n```\n\n", source);
    }
    if (metatoken_get_next_real_token(tokens, 0) >= 0)
    {
        printf("UNPARSED TOKENS:\n");
        print_scanner(tokens, verbose);
        printf("\n\n");
    }

    vect_free(tokens);
    release_metascanner();
    release_metaparser();
}


/**
 * Print the output of the scanner step
 */
void print_scanner(vect* tokens, bool verbose)
{
    for (size_t i = 0; i < vect_size(tokens); i++)
    {
        metatoken* t = vect_get(tokens, i)->data;
        verbose ? metatoken_repr(t) : metatoken_str(t);
        if (verbose && i < vect_size(tokens) - 1) { printf(" "); } //space after each verbose token
    }
}


/**
 * Print the output of a single ast from the ast parse step.
 */
void print_ast(uint64_t head_idx, metaast* body_ast, bool verbose)
{
    obj* head = metaparser_get_symbol(head_idx);
    obj_print(head);
    if (body_ast != NULL)
    {
        printf(" = ");
        if (verbose) { metaast_repr(body_ast); } 
        else { metaast_str(body_ast); printf("\n"); }
    }
    else { printf(" = NULL\n"); }
}


/**
 * Print the output of the CFG covnersion step
 */
void print_parser()
{
    print_grammar_tables();
}