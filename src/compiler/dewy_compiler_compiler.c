#include <inttypes.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "crf.h"
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
        printf("Usage: ./dewy [-s] [-m] [-p] [-g] [-l] [-f] [-a] [--verbose] /grammar/file/path /input/file/path\n"
               " -s scanner\n"
               " -m (meta)ast\n"
               " -g Context Free Grammar\n"
               " -f first/follow sets\n"
               " -l grammar labels\n"
               " -i input string\n"
               " -c Call Return Forest\n"
               " -d Descriptor & Action sets\n"
               " -b Binary Subtree Representation\n"
               " -r results BSR\n"
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
    match_argv(grammar, -g);
    match_argv(fsets, -f);
    match_argv(labels, -l);
    match_argv(input, -i);
    match_argv(crf, -c);
    match_argv(descriptors, -d);
    match_argv(bsr, -b);
    match_argv(result, -r);
    match_argv(ast, -a);
    match_argv(verbose, --verbose);

    // if no sections specified, run all of them
    if (!(scanner || mast || grammar || fsets || labels || input || crf || descriptors || bsr || result || ast))
    {
        scanner = true;
        mast = true;
        grammar = true;
        fsets = true;
        labels = true;
        input = true;
        crf = true;
        descriptors = true;
        bsr = true;
        result = true;
        ast = true;
    }

    // set up structures for the sequence of scanning/parsing
    allocate_metascanner();
    allocate_metaparser();
    allocate_parser();

    if (!run_compiler_compiler(grammar_source, verbose, scanner, mast, grammar)) { goto cleanup; }

    initialize_parser();
    if (!run_compiler(input_source, input_size, fsets, labels, input, crf, descriptors, bsr, result, ast, verbose))
    {
        goto cleanup;
    }

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
bool run_compiler_compiler(char* source, bool verbose, bool scanner, bool mast, bool grammar)
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

    if (grammar)
    {
        printf("METAPARSER OUTPUT:\n");
        print_parser(verbose);
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
bool run_compiler(uint32_t* source, size_t length, bool fsets, bool labels, bool input, bool crf, bool descriptors,
                  bool bsr, bool result, bool ast, bool verbose)
{
    // GRAMMAR FIRST/FOLLOW SET STEP
    if (fsets)
    {
        printf("GRAMMAR FIRST SETS:\n");
        print_grammar_first_sets();
        printf("GRAMMAR FOLLOW SETS:\n");
        print_grammar_follow_sets();
        printf("\n\n");
    }

    parser_generate_labels();

    if (labels)
    {
        printf("CNP LABELS:\n");
        vect* labels = parser_get_labels();

        for (size_t i = 0; i < vect_size(labels); i++)
        {
            slot* label = vect_get(labels, i)->data;
            parser_print_label(label);
        }
        printf("\n\n");
    }

    // parse the input
    uint64_t start_symbol_idx = metaparser_get_start_symbol_idx();
    parser_context context = parser_context_struct(source, length, start_symbol_idx, true, false);
    if (input)
    {

        printf("PARSING INPUT:\n```\n");
        ustring_str(source);
        printf("\n```\n(length = %" PRIu64 ")\n\n", length);
    }

    bool success = parser_parse(&context);

    // print out the results of compilation
    if (crf)
    {
        printf("CRF OUTPUT:\n");
        crf_str(context.CRF);
        printf("\n\n");
    }

    if (descriptors)
    {
        printf("DESCRIPTOR SET:\n");
        set_str(context.U);
        printf("\n\n");
        printf("ACTION SET:\n");
        crf_action_P_str(context.P);
        printf("\n\n");
    }

    if (bsr)
    {
        printf("BSR OUTPUT:\n");
        printf("{");
        for (size_t i = 0; i < dict_size(context.Y); i++)
        {
            obj k, v;
            dict_get_at_index(context.Y, i, &k, &v);
            bsr_head* head = k.data;
            set* j_set = v.data;
            for (size_t k = 0; k < set_size(j_set); k++)
            {
                uint64_t* j = set_get_at_index(j_set, k)->data;
                if (i > 0 || k > 0) printf(", ");
                bsr_str(head, *j);
            }
        }
        printf("}\n\n");
    }
    if (result)
    {
        printf("RESULTS BSRs:\n");
        printf("{");
        bool first = true;

        // get the production bodies of the start symbol
        set* bodies = metaparser_get_production_bodies(start_symbol_idx);
        for (size_t i = 0; i < set_size(bodies); i++)
        {
            // get the j-set associated with the body
            bsr_head head = new_prod_bsr_head_struct(start_symbol_idx, i, 0, length);
            obj* j_set_obj = dict_get(context.Y, &(obj){.type = BSRHead_t, .data = &head});
            if (j_set_obj != NULL)
            {
                set* j_set = j_set_obj->data;
                for (size_t k = 0; k < set_size(j_set); k++)
                {
                    printf(!first ? ", " : "");
                    first = false;
                    uint64_t* j = set_get_at_index(j_set, k)->data;
                    bsr_str(&head, *j);
                }
            }
        }
        printf("}\n\n");
    }

    if (ast)
    {
        // printf("AST OUTPUT:\n");
        // print_sppf_from_bsr(context.BSR);
        // printf("\n\n");
    }

    release_parser_context(&context);

    printf(success ? "PARSE SUCCEEDED\n\n" : "PARSE FAILED\n\n");

    return success;
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
void print_parser(bool verbose) { verbose ? metaparser_rules_repr() : metaparser_rules_str(); }

/**
 * Print out the first sets generated by the grammar.
 */
void print_grammar_first_sets()
{
    vect* firsts = parser_get_symbol_firsts();
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
    vect* follows = parser_get_symbol_follows();
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
