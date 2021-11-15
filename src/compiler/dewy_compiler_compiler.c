#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "dewy_compiler_compiler.h"
#include "metaparser.h"
#include "metascanner.h"
#include "metatoken.h"
#include "object.h"
#include "parser.h"
#include "slot.h"
#include "ustring.h"
#include "utilities.h"

// Terms:
//  BSR: Binary Subtree Representation
//  CRF: Call Return Format
//  CNP: Clustered Nonterminal Parser

#define match_argv(var, val)                                                                                           \
    bool var = false;                                                                                                  \
    for (size_t i = 0; i < argc - 2; i++)                                                                              \
        if (strcmp(argv[i], #val) == 0) var = true;

int main(int argc, char* argv[])
{
    if (argc < 3)
    {
        printf("Error: you must specify a grammar file and a source file\n");
        printf("Usage: ./dewy [-s] [-m] [-p] [-g] [-l] [-f] [-a] [--verbose] /grammar/file/path /input/file/path"
               " -s scanner\n"
               " -m (meta)ast\n"
               " -p parser CFG\n"
               " -g grammar first/follow sets\n"
               " -l grammar labels\n"
               //    " -b Binary Subtree Representation BSR\n"
               //    " -c Call Return Forest (CRF)\n"
               " -f parse forest\n"
               " -a ast\n"
               " --verbose prints out repr instead of str\n");
        return 1;
    }

    // load the grammar source file into a string
    char* grammar_file_path = argv[argc - 2];
    char* grammar_source;
    size_t grammar_size = read_file(grammar_file_path, &grammar_source);

    // load the input source file into a unicode string
    char* input_file_path = argv[argc - 1];
    uint32_t* input_source;
    size_t input_size = read_unicode_file(input_file_path, &input_source);

    // determine what parts of the compile process to print out
    match_argv(scanner, -s);
    match_argv(mast, -m);
    match_argv(parser, -p);
    match_argv(grammar, -g);
    match_argv(labels, -l);
    // match_argv(compile, -c);
    match_argv(forest, -f);
    match_argv(verbose, --verbose);

    // if no sections specified, run all of them
    if (!(scanner || mast || parser || grammar || labels || forest))
    {
        scanner = true;
        mast = true;
        parser = true;
        grammar = true;
        labels = true;
        forest = true;
    }

    // set up structures for the sequence of scanning/parsing
    initialize_metascanner();
    initialize_metaparser();
    initialize_parser();

    if (!run_compiler_compiler(grammar_source, verbose, scanner, mast, parser, grammar)) { goto cleanup; }
    if (!run_compiler(input_source, labels, forest)) { goto cleanup; }

cleanup:
    free(grammar_source);
    free(input_source);

    release_metascanner();
    release_metaparser();
    release_parser();

    printf("Completed running parser\n");

    return 0;
}

/**
 * Run all steps in the compiler, and print out the intermediate results if the
 * corresponding bool is true. If verbose is true, print out more structure info.
 * returns whether or not compiler_compiler step completed successfully
 */
bool run_compiler_compiler(char* source, bool verbose, bool scanner, bool mast, bool parser, bool grammar)
{
    vect* tokens = new_vect();
    obj* t = NULL;

    // SCANNER STEP: collect all tokens from raw text
    while (*source != 0 && (t = scan(&source)) != NULL) { vect_push(tokens, t); }
    if (scanner) // print scanning result
    {
        printf("METASCANNER OUTPUT:\n");
        print_scanner(tokens, verbose);
        printf("\n\n");
    }
    if (*source != 0) // check for errors scanning
    {
        printf("ERROR: metascanner failed\n");
        printf("unscanned source:\n```\n%s\n```\n\n", source);
        vect_free(tokens);
        return false;
    }

    // MAST & PARSER STEP: build MASTs from tokens, and then convert to CFG sentences
    if (mast) { printf("METAAST OUTPUT:\n"); }
    while (metatoken_get_next_real_token(tokens, 0) >= 0)
    {
        if (!metaparser_is_valid_rule(tokens)) { break; }

        obj* head = metaparser_get_rule_head(tokens);
        uint64_t head_idx = metaparser_add_symbol(head);
        vect* body_tokens = metaparser_get_rule_body(tokens);
        metaast* body_ast = metaast_parse_expr(body_tokens);
        if (mast) { print_ast(head_idx, body_ast, verbose); }

        // apply ast reductions if possible
        if (body_ast != NULL)
        {
            // count if any reductions were performed
            int reductions = 0;
            while ((metaast_fold_constant(&body_ast)) && ++reductions)
                ;

            if (mast && reductions > 0)
            {
                printf("Reduced AST: ");
                print_ast(head_idx, body_ast, verbose);
            }

            // attempt to convert metaast into sentential form
            metaparser_insert_rule_ast(head_idx, body_ast);
        }
        else // error while constructing tree
        {
            vect_free(tokens);
            return false;
        }
    }

    // error if any unparsed (non-whitespace/comment) meta tokens
    if (metatoken_get_next_real_token(tokens, 0) >= 0)
    {
        printf("ERROR: metaparser failed\n");
        printf("unparsed tokens:\n");
        print_scanner(tokens, verbose);
        printf("\n\n");
        vect_free(tokens);
        return false;
    }

    // finalize the metaparser before running the rnglr processes
    complete_metaparser();
    vect_free(tokens);

    if (mast) { printf("\n\n"); }

    if (parser)
    {
        printf("METAPARSER OUTPUT:\n");
        print_parser(verbose);
        printf("\n\n");
    }

    // GRAMMAR FIRST/FOLLOW SET STEP
    if (grammar)
    {
        printf("GRAMMAR FIRST SETS:\n");
        print_grammar_first_sets();
        printf("GRAMMAR FOLLOW SETS:\n");
        print_grammar_follow_sets();
        printf("\n\n");
    }

    // SRNGLR TABLE: print out the generated srnglr table for the grammar
    // if (table)
    // {
    //     printf("SRNGLR TABLE:\n");
    //     print_table();
    //     printf("\n\n");
    // }

    return true;
}

/**
 * Parse the input file according to the input grammar.
 */
bool run_compiler(uint32_t* source, bool labels, bool forest)
{
    parser_generate_labels();

    if (labels)
    {
        printf("CNP LABELS:\n");
        vect* labels = parser_get_labels();

        for (size_t i = 0; i < vect_size(labels); i++)
        {
            slot* label = vect_get(labels, i)->data;
            slot_str(label);
            printf("\n");
        }
        printf("\n\n");
    }

    return true;

    // print out the labels generated

    // bool result = srnglr_parser(source);

    // if (compile)
    // {
    //     printf("INPUT SOURCE:\n```\n");
    //     ustring_str(source);
    //     printf("\n```\n\n");

    //     printf("PARSE RESULT:\n%s\n\n", result ? "success" : "failure");
    //     print_compiler();
    //     printf("\n\n");
    // }

    // return result;
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
        if (verbose && i < vect_size(tokens) - 1) { printf(" "); } // space after each verbose token
        if (t->type == comment && t->content[1] == '/')
        {
            printf("\n");
        } // print a newline after singleline comments. TODO->maybe have single line comments include the newline?
    }
}

/**
 * Print the output of a single ast from the ast parse step.
 */
void print_ast(uint64_t head_idx, metaast* body_ast, bool verbose)
{
    obj* head = metaparser_get_symbol(head_idx);
    obj_str(head);
    if (body_ast != NULL)
    {
        printf(" = ");
        if (verbose) { metaast_repr(body_ast); }
        else
        {
            metaast_str(body_ast);
            printf("\n");
        }
    }
    else
    {
        printf(" = NULL\n");
    }
}

/**
 * Print the output of the CFG covnersion step
 */
void print_parser(bool verbose) { verbose ? metaparser_productions_repr() : metaparser_productions_str(); }

/**
 * Print out the first sets generated by the grammar.
 */
void print_grammar_first_sets()
{
    vect* firsts = metaparser_get_symbol_firsts();
    for (int symbol_idx = 0; symbol_idx < vect_size(firsts); symbol_idx++)
    {
        obj* symbol = metaparser_get_symbol(symbol_idx);
        fset* f = vect_get(firsts, symbol_idx)->data;
        obj_str(symbol);
        printf(" -> ");
        fset_first_str(f);
        printf("\n");
    }
}

/**
 * Print out the follow sets generated by the grammar.
 */
void print_grammar_follow_sets()
{
    vect* follows = metaparser_get_symbol_follows();
    for (int symbol_idx = 0; symbol_idx < vect_size(follows); symbol_idx++)
    {
        obj* symbol = metaparser_get_symbol(symbol_idx);
        fset* f = vect_get(follows, symbol_idx)->data;
        obj_str(symbol);
        printf(" -> ");
        fset_follow_str(f);
        printf("\n");
    }
}

/**
 * Print out the srnglr table generated by the grammar.
 */
// void print_table()
// {
//     srnglr_print_table();
// }

/**
 * Print out the GSS generated during parsing of the input.
 */
// void print_compiler()
// {
//     // srnglr_print_gss();
//     srnglr_print_sppf();
// }
