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
#include "metatoken.h"
#include "metascanner.h"
#include "metaparser.h"
#include "metaitem.h"
#include "srnglr.h"
#include "dewy_compiler_compiler.h"

#define USE_JULIA_PRETTY_TABLE_PRINT 0 //0 for false, 1 for true

#define match_argv(var, val)            \
{                                       \
    var = false;                        \
    for (size_t i = 0; i < argc; i++)   \
        if (strcmp(argv[i], #val) == 0) \
            var = true;                 \
}

char* grammar_file; //save a reference to the grammar file
// char* input_file; //future stuff

int main(int argc, char* argv[])
{
    if (argc < 2)
    {
        printf("Error: you must specify a file to read\n");
        return 1;
    }

    //load the source file into a string
    grammar_file = argv[argc-1];
    char* source = read_file(grammar_file);

    bool scanner, ast, parser, grammar, table, raw_table, verbose;
    match_argv(scanner, -s)
    match_argv(ast, -a)
    match_argv(parser, -p)
    match_argv(grammar, -g)
    match_argv(table, -t)
    match_argv(raw_table, --raw-table)
    match_argv(verbose, --verbose)

    //if no sections specified, run all of them
    if (!(scanner || ast || parser || grammar || table))
    {
        scanner = true;
        ast = true;
        parser = true;
        grammar = true;
        table = true;
    }
    
    //raw table should be the only one when run
    if (raw_table)
    {
        scanner = false;
        ast = false;
        parser = false;
        grammar = false;
        table = false;
    }

    run_compiler(source, verbose, scanner, ast, parser, grammar, table, raw_table);

    free(source);

    return 0;
}


/**
 * Run all steps in the compiler, and print out the intermediate results if the 
 * corresponding bool is true. If verbose is true, print out more structure info.
 */
void run_compiler(char* source, bool verbose, bool scanner, bool ast, bool parser, bool grammar, bool table, bool raw_table)
{
    //set up structures for the sequence of scanning/parsing
    initialize_metascanner();
    initialize_metaparser();
    initialize_srnglr();

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
    }
    if (ast) { printf("\n\n"); }

    if (parser)
    {
        printf("METAPARSER OUTPUT:\n");
        print_parser();
        printf("\n\n");
    }

    //GRAMMAR ITEMSET STEP: generate the itemsets for the grammar
    srnglr_generate_grammar_itemsets();
    if (grammar)
    {
        printf("GRAMMAR ITEMSETS:\n");
        print_grammar();
        printf("\n\n");
    }

    //SRNGLR TABLE: print out the generated srnglr table for the grammar
    if (table)
    {
        printf("SRNGLR TABLE:\n");
        print_table();
        printf("\n\n");
    }
    else if (raw_table) { print_raw_table(); }


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
    release_srnglr();
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
        if (t->type == comment && t->content[1] == '/') { printf("\n"); } //print a newline after singleline comments. TODO->maybe have single line comments include the newline?
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


/**
 * Print out the itemsets generated by the grammar.
 */
void print_grammar()
{
    set* itemsets = srnglr_get_itemsets();
    for (size_t i = 0; i < set_size(itemsets); i++)
    {
        set* itemset = itemsets->entries[i].item->data;
        printf("I%zu:\n", i);
        for (size_t j = 0; j < set_size(itemset); j++)
        {
            metaitem* item = itemset->entries[j].item->data;
            printf("  "); metaitem_str(item); printf("\n");
        }
        printf("\n");
    }

    // set_str(itemsets); //lazy print all
}


/**
 * Print out the raw SRNGLR table generated by the grammar.
 * used as input to tableformatter.jl to pretty print the table
 * as a proper grid in the terminal.
 */
void print_raw_table()
{
    dict* srnglr_table = srnglr_get_table();
    dict_str(srnglr_table);
}


#if USE_JULIA_PRETTY_TABLE_PRINT
/**
 * Call julia subroutine to pretty print the table.
 * Runs the command 
 *      ./dewy --raw-table $grammar_file | julia tableformatter.jl
 * where $grammar_file is expanded out to be the path of the string passed in.
 */
void print_table(set* itemsets)
{
    //create strings for each part of the command
    char cmd0[] = "./dewy --raw-table ";
    char cmd1[] = " | julia tableformatter.jl";
    size_t grammar_file_strlen = strlen(grammar_file);

    //allocate space for the whole command string
    size_t cmdlen = sizeof(cmd0) + grammar_file_strlen + sizeof(cmd1) - 2; //remove 2 null terminators from length
    char* cmd = malloc(sizeof(char) * (cmdlen + 1));

    //copy all of the components of the command into the allocated string
    cmd[0] = 0; //start as empty string
    strcat(cmd, cmd0);
    strcat(cmd, grammar_file);
    strcat(cmd, cmd1);
    
    //run the command
    system(cmd);
    
    //free the allocated string holding the command
    free(cmd);
}

#else
/**
 * Print out the parser table generated by the grammar. 
 * Completely portable version/doesn't use julia to print table
 */
//TODO->move this function to srnglr.c
#include "gotokey.h"
#include "reduction.h"
#include "ustring.h"
#include <inttypes.h>
void print_table()
{
    set* itemsets = srnglr_get_itemsets();
    dict* srnglr_table = srnglr_get_table();
    set* symbols = metaparser_get_symbols();

    //compute number of rows in table. this doesn't include the header row
    size_t num_rows = set_size(itemsets);

    //compute the number of columns in the table
    size_t num_columns = 0;
    bool* symbols_used = calloc(set_size(symbols), sizeof(bool)); //track whether we've seen a given symbol
    for (size_t i = 0; i < dict_size(srnglr_table); i++)
    {
        gotokey* key = srnglr_table->entries[i].key->data;
        
        //check if we haven't seen this symbol yet
        if (!symbols_used[key->symbol_idx])
        {
            symbols_used[key->symbol_idx] = true;
            num_columns++;
        }
    }

    //allocate grid to keep track of the print width of each cell (including headers) in the table
    uint64_t* cell_widths = calloc((num_rows + 1) * (num_columns + 1), sizeof(uint64_t));
    
    //check the widths of each column header
    {
        size_t column_idx = 0;
        for (size_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
        {
            if (!symbols_used[symbol_idx]) continue;

            obj* symbol = metaparser_get_symbol(symbol_idx);
            uint64_t width = symbol->type == CharSet_t ? charset_strlen(symbol->data) : ustring_len(symbol->data);

            //save the width into the widths matrix
            cell_widths[column_idx + 1] = width;

            column_idx++;
        }
    }

    //check the widths of each state number
    for (uint64_t state_idx = 0; state_idx < num_rows; state_idx++)
    {
        cell_widths[(num_columns + 1) * (state_idx + 1)] = snprintf("", 0, "%"PRIu64, state_idx);
    }

    //check the widths of each cell in that column
    {
        size_t column_idx = 0;
        for (size_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
        {
            if (!symbols_used[symbol_idx]) continue;

            for (size_t state_idx = 0; state_idx < set_size(itemsets); state_idx++)
            {
                //get the set of actions for this coordinate in the table
                gotokey key = (gotokey){.state_idx=state_idx, .symbol_idx=symbol_idx};
                obj key_obj = (obj){.type=GotoKey_t, .data=&key};
                if (dict_contains(srnglr_table, &key_obj))
                {
                    set* actions = dict_get(srnglr_table, &key_obj)->data;
                    uint64_t width = 0;
                    for (size_t i = 0; i < set_size(actions); i++)
                    {
                        obj* action = actions->entries[i].item;
                        if (action->type == Push_t){ width += push_strlen(*(uint64_t*)action->data); }
                        else if (action->type == Reduction_t) { width += reduction_strlen(action->data); }
                        else if (action->type == Accept_t) { width += accept_strlen(); }
                        else { printf("ERROR: unknown action object type %u\n", action->type); }

                        if (i < set_size(actions) - 1) { width += 2; } //space for ", " between elements
                    }

                    // if (column_widths[column_idx] < width) { column_widths[column_idx] = width; }
                    cell_widths[(num_columns + 1) * (state_idx + 1) + column_idx + 1] = width;
                }
            }
            column_idx++;
        }
    }


    //using the cell widths, compute the max column widths
    uint64_t* column_widths = calloc((num_columns + 1), sizeof(uint64_t));
    for (size_t i = 0; i < num_rows + 1; i++)
    {
        for (size_t j = 0; j < num_columns + 1; j++)
        {
            if (column_widths[j] < cell_widths[(num_columns + 1) * i + j])
            {
                column_widths[j] = cell_widths[(num_columns + 1) * i + j];
            } 
        }
    }


    //print the table header
    for (int i = 0; i < column_widths[0] + 2; i++) { putchar(' '); }
    printf("│");    
    {
        size_t column_idx = 0;
        for (size_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
        {
            if (!symbols_used[symbol_idx]) continue;

            obj* symbol = metaparser_get_symbol(symbol_idx);
            putchar(' '); 
            obj_print(symbol);
            putchar(' ');

            uint64_t remaining = column_widths[1 + column_idx] - cell_widths[1 + column_idx];
            for (int i = 0; i < remaining; i++) { putchar(' '); }

            column_idx++;
        }
    }
    printf("\n");

    //print the divider row
    for (int i = 0; i < column_widths[0] + 2; i++) { printf("─"); }
    printf("┼");
    for (size_t j = 1; j < num_columns + 1; j++)
        for (int i = 0; i < column_widths[j] + 2; i++)
            printf("─"); 
    
    printf("\n");
    
    //print the body of the table    
    for (size_t state_idx = 0; state_idx < set_size(itemsets); state_idx++)
    {
        //print out the state number
        putchar(' ');
        printf("%zu", state_idx);
        putchar(' ');
        uint64_t remaining = column_widths[0] - cell_widths[(num_columns + 1) * (state_idx + 1)];
        for (int i = 0; i < remaining; i++) { putchar(' '); }
        printf("│");

        //print out the contents of each column in this row
        size_t column_idx = 0;
        for (size_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
        {
            if (!symbols_used[symbol_idx]) continue;

            putchar(' ');

            //get the set of actions for this coordinate in the table
            gotokey key = (gotokey){.state_idx=state_idx, .symbol_idx=symbol_idx};
            obj key_obj = (obj){.type=GotoKey_t, .data=&key};
            if (dict_contains(srnglr_table, &key_obj))
            {
                set* actions = dict_get(srnglr_table, &key_obj)->data;                
                
                for (size_t i = 0; i < set_size(actions); i++)
                {
                    obj* action = actions->entries[i].item;
                    obj_print(action);
                    if (i < set_size(actions) - 1) { printf(", "); }
                }
            }

            putchar(' ');

            uint64_t remaining = column_widths[column_idx + 1] - cell_widths[(num_columns + 1) * (state_idx + 1) + column_idx + 1];
            for (int i = 0; i < remaining; i++) { putchar(' '); }

            column_idx++;
        }
        printf("\n");
    }
    printf("\n");


    free(symbols_used);
    free(cell_widths);
    free(column_widths);

}

#endif