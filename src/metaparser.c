#ifndef METAPARSER_C
#define METAPARSER_C

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

#include "charset.h"
#include "fset.h"
#include "metaast.h"
#include "metaparser.h"
#include "metascanner.h"
#include "metatoken.h"
#include "set.h"
#include "slice.h"
#include "ustring.h"
#include "utilities.h"
#include "vector.h"

// used to mark unsigned integer indices as NULL.
#define NULL_SYMBOL_INDEX (uint64_t) - 1

/**
 * Global data structures used to manage all meta grammar rules.
 * Symbols are either an identifier or a charset.
 * Bodies are vects of uint indices indicating symbols from the symbols list.
 * Productions are a map from the head index (in the symbols list) to a list of
 * indices indicating which body vectors apply to that head.
 */
set* metaparser_symbols;           // list of all symbols used in production bodies.
set* metaparser_bodies;            // list of each production body.
dict* metaparser_productions;      // map from head to production bodies.
dict* metaparser_ast_cache;        // map<metaast*, body_idx>. care must be taken while freeing this object.
vect* metaparser_unused_ast_cache; // vect containing all ASTs not inserted into the cache

// For parsing filters, create tables indicating which rules to apply filters to.
// #rule = #A / #B; indicates that #B may not follow #A when parsing #rule
// #rule = #A - #B; indicates that the string matching #A may not also match #B when parsing #rule
// #rule = #A > #B; indicates that when parsing #rule, if #A and #B are both matched, #A is preferred
dict* metaparser_nofollow_table;    // map<head_idx, charset | ustring | vect<charset> | head_idx>>
dict* metaparser_reject_table;      // map<head_idx, charset | ustring | vect<charset> | head_idx>>
dict* metaparser_precedence_tables; // map<head_idx, map<production_idx, level>>. lower level means higher precedence

// Captured rules are used to indicate which portion of the parsed input should be recorded for later retrieval.
// #rule = #A.; indicates that when reconstructing the AST for a parse, the #A portion should be recorded.
// By default, if no capture is specified, the entire rule is captured.
set* metaparser_capture_set; // set<head_idx>

// convenience variables for the frequently used epsilon production body, and $ endmarker terminal.
uint64_t metaparser_eps_body_idx = NULL_SYMBOL_INDEX;
uint64_t metaparser_start_symbol_idx = NULL_SYMBOL_INDEX;

/**
 * Initialize all global data structures used by metaparser.
 */
void allocate_metaparser()
{
    metaparser_symbols = new_set();
    metaparser_bodies = new_set();
    metaparser_productions = new_dict();
    metaparser_ast_cache = new_dict();
    metaparser_unused_ast_cache = new_vect();

    metaparser_nofollow_table = new_dict();
    metaparser_reject_table = new_dict();
    metaparser_precedence_tables = new_dict();

    metaparser_capture_set = new_set();
}

/**
 * functions to finalize the state of the metaparser before continuing to later steps of parsing.
 */
void complete_metaparser()
{
    metaparser_get_eps_body_idx();
    metaparser_get_start_symbol_idx();
    metaparser_finalize_precedence_tables();

    // TODO->check to ensure that every identifier has at least 1 body, and return error if not...
}

/**
 * Free up all global data structures used by metaparser.
 */
void release_metaparser()
{
    set_free(metaparser_symbols);
    set_free(metaparser_bodies);
    dict_free(metaparser_productions);
    dict_free(metaparser_nofollow_table);
    dict_free(metaparser_reject_table);
    dict_free(metaparser_precedence_tables);
    set_free(metaparser_capture_set);

    metaparser_free_ast_cache();
}

/**
 * Special process to free the ast cache since trees may share children
 */
void metaparser_free_ast_cache()
{
    // free all the ASTs, maintaining a reference set to ensure nodes aren't double freed
    set* refs = new_set();
    for (size_t i = 0; i < dict_size(metaparser_ast_cache); i++)
    {
        metaast* ast = obj_free_keep_inner(metaparser_ast_cache->entries[i].key, MetaAST_t);
        metaast_free_with_refs(ast, refs);
    }
    while (vect_size(metaparser_unused_ast_cache) > 0)
    {
        metaast* ast = obj_free_keep_inner(vect_pop(metaparser_unused_ast_cache), MetaAST_t);
        metaast_free_with_refs(ast, refs);
    }

    set_free(refs);

    dict_free_values_only(metaparser_ast_cache);
    dict_free_table_only(metaparser_ast_cache);
    vect_free(metaparser_unused_ast_cache);
}

/**
 * Keep track of anonymous rule heads created by the metaparser.
 * Start at 1 so that we don't have to deal with log(0) = -inf.
 */
uint64_t metaparser_anonymous_rule_count = 1;

/**
 * Get an anonymous identifier for internally created sub productions
 * Identifiers are of the form #__i where i is the current `metaparser_anonymous_rule_count`
 */
uint64_t metaparser_get_anonymous_rule_head()
{
    // determine the string width of the number
    size_t width = dec_num_digits(metaparser_anonymous_rule_count);
    width += 4; // room for `#__` at start and null terminator at end

    // create a normal char* that will be the head
    char* num_str = malloc(width * sizeof(char));
    sprintf(num_str, "#__%" PRIu64, metaparser_anonymous_rule_count);

    // convert to unicode string (wrapped in obj*), and cleanup char* version
    obj* head = new_ustring_obj(ustring_utf8_substr(num_str, 0, width - 1));
    free(num_str);

    // increment the counter
    metaparser_anonymous_rule_count++;

    // insert head into metaparser_symbols, and return its index
    uint64_t head_idx = metaparser_add_symbol(head);

    return head_idx;
}

/**
 * Try to scan for a rule in the current list of tokens.
 * Returns `true` if a rule was successfully parsed.
 * Assumes that tokens may contain comments or whitespace.
 */
bool parse_next_meta_rule(vect* tokens)
{
    // check for head, equals sign, and semicolon
    if (!metaparser_is_valid_rule(tokens)) { return false; }

    // construct head and body for the rule
    obj* head = metaparser_get_rule_head(tokens);
    vect* body_tokens = metaparser_get_rule_body(tokens);
    metaast* body_ast = metaast_parse_expr(body_tokens);

    // failed to parse body into ast
    if (body_ast == NULL)
    {
        vect_free(body_tokens);
        obj_free(head);
        return false;
    }

    // reduce any constant expressions in the ast (e.g. charset operations)
    while (metaast_fold_constant(&body_ast))
        ;

    // recursively convert to sentences + insert into grammar table
    uint64_t head_idx = metaparser_add_symbol(head);
    metaparser_insert_rule_ast(head_idx, body_ast);
    return true;
}

/**
 * Print out the raw contents of the grammar tables.
 * i.e. prints the symbols list with each symbols indices,
 * Prints the bodies list with each body containing indices of symbols
 * Prints the productions dictionary which contains head symbol indices
 * pointing to the list of indices of bodies for that head.
 */
void metaparser_rules_repr()
{
    // print out all symbols, bodies
    printf("symbols:\n");
    for (uint64_t i = 0; i < set_size(metaparser_symbols); i++)
    {
        printf("%" PRIu64 ": ", i);
        obj_str(metaparser_get_symbol(i));
        printf("\n");
    }
    printf("\nbodies:\n");
    for (uint64_t i = 0; i < set_size(metaparser_bodies); i++)
    {
        printf("%" PRIu64 ": ", i);
        vect_str(metaparser_get_body(i));
        printf("\n");
    }
    printf("\nproductions:\n");
    dict_str(metaparser_productions);
    printf("\n\n");
}

/**
 * Print out the contents of the grammar tables, converting indices to their corresponding values
 */
void metaparser_rules_str()
{
    for (size_t i = 0; i < dict_size(metaparser_productions); i++)
    {
        // get head string
        uint64_t* head_idx = metaparser_productions->entries[i].key->data;
        obj* head = metaparser_get_symbol(*head_idx);

        // get bodies indices set, and print a production line for each body
        set* bodies = metaparser_productions->entries[i].value->data;
        for (size_t j = 0; j < set_size(bodies); j++)
        {
            // get the body for this production
            uint64_t* body_idx = bodies->entries[j].item->data;

            vect* body = metaparser_get_body(*body_idx);
            metaparser_rule_str(head, body);
            printf("\n");
        }

        // if head_idx is in in one of the filter tables, print out the filter rule
        obj* result = dict_get(metaparser_nofollow_table, &(obj){.type = UInteger_t, .data = head_idx});
        if (result != NULL)
        {
            printf(">>>> ");
            obj_str(head);
            printf(" / ");
            metaparser_filter_str(result);
            printf("\n");
        }
        result = dict_get(metaparser_reject_table, &(obj){.type = UInteger_t, .data = head_idx});
        if (result != NULL)
        {
            printf(">>>> ");
            obj_str(head);
            printf(" - ");
            metaparser_filter_str(result);
            printf("\n");
        }
        result = dict_get(metaparser_precedence_tables, &(obj){.type = UInteger_t, .data = head_idx});
        if (result != NULL)
        {
            printf(">>>> precedence: [\n");
            metaparser_precedence_table_str(result->data, bodies);
            printf("]\n");
        }
        if (set_contains(metaparser_capture_set, &(obj){.type = UInteger_t, .data = head_idx}))
        {
            printf(">>>> capture: ");
            obj_str(head);
            printf("\n");
        }
    }
}

/**
 * Print out a single production rule, given the actual head and body objects
 */
void metaparser_rule_str(obj* head, vect* body)
{
    // print head ->
    obj_str(head);
    printf(" -> ");
    metaparser_body_str(body);
}

/**
 * Print out the grammar string for the given rule body
 */
void metaparser_body_str(vect* body)
{
    // print out the contents of this body
    if (vect_size(body) == 0)
    {
        // length 0 sentence is just epsilon
        printf("ϵ");
    }
    for (size_t k = 0; k < vect_size(body); k++)
    {
        // normal print out each symbol in the sentence
        if (k > 0) printf(" ");
        uint64_t* symbol_idx = vect_get(body, k)->data;
        obj* symbol = metaparser_get_symbol(*symbol_idx);
        obj_str(symbol);
    }
}

/**
 * Print ouf a single production rule given the head index and it's corresponding production index
 */
void metaparser_production_str(uint64_t head_idx, uint64_t production_idx)
{
    // get the head symbol
    obj* head = metaparser_get_symbol(head_idx);

    // get the body set
    vect* body = metaparser_get_production_body(head_idx, production_idx);
    // set* bodies = metaparser_productions->entries[production_idx].value->data;

    metaparser_rule_str(head, body);
}

/**
 * Print out the given nofollow/reject object. filter objects can be charsets, strings, or head_idx ints.
 */
void metaparser_filter_str(obj* right)
{
    if (right->type == UnicodeString_t || right->type == CharSet_t) { obj_str(right); }
    else if (right->type == UInteger_t)
    {
        obj_str(metaparser_get_symbol(*(uint64_t*)(right->data)));
    }
    else
    {
        printf("ERROR: unknown filter right expression type: %d\n", right->type);
        exit(1);
    }
}

/**
 * Print out the contents of the given precedence table.
 */
void metaparser_precedence_table_str(dict* table, set* bodies)
{
    uint64_t level = 0;
    printf("  0: ");
    for (size_t i = 0; i < set_size(bodies); i++)
    {
        uint64_t* body_idx = set_get_at_index(bodies, i)->data;
        vect* body = metaparser_get_body(*body_idx);

        if (i > 0)
        {
            uint64_t* body_level = dict_get_uint_key(table, i)->data;
            if (*body_level != level)
            {
                printf("\n  %" PRIu64 ": ", *body_level);
                level = *body_level;
            }
            else
            {
                printf(", ");
            }
        }
        metaparser_body_str(body);
    }
    printf("\n");
}

/**
 * Verify that the stream of tokens is valid syntax for a rule
 * #rule = #identifier #ws '=' #ws #expr #ws ';';
 */
bool metaparser_is_valid_rule(vect* tokens)
{
    // shortest rule is 4 tokens: #id '=' <expr> ;
    if (vect_size(tokens) == 0)
    {
        printf("ERROR: cannot parse rule from empty tokens list\n");
        return false;
    }

    // scan for head
    int i = metatoken_get_next_real_token(tokens, 0);
    if (i < 0 || !metatoken_is_i_of_type(tokens, i, hashtag))
    {
        printf("ERROR: no identifier found at start of meta rule\n");
        return false;
    }

    // scan for equals sign
    i = metatoken_get_next_real_token(tokens, i + 1);
    if (i < 0 || !metatoken_is_i_of_type(tokens, i, meta_equals_sign))
    {
        printf("ERROR: no equals sign found following identifier in meta rule\n");
        return false;
    }

    // scan for ending semicolon
    i = metatoken_get_next_token_of_type(tokens, meta_semicolon, i + 1);
    if (i < 0)
    {
        printf("ERROR: no semicolon found to close meta rule\n");
        return false;
    }

    return true;
}

/**
 * Return the identifier starting the meta rule.
 * Frees any whitespace/comment tokens before the identifier.
 * Expects metaparser_is_valid_rule() to have been called first.
 */
obj* metaparser_get_rule_head(vect* tokens)
{
    while (vect_size(tokens) > 0)
    {
        // obj* t_obj = vect_dequeue(tokens);
        // metatoken* t = t_obj->data;
        metatoken* t = obj_free_keep_inner(vect_dequeue(tokens), MetaToken_t);
        if (t->type == whitespace || t->type == comment) { metatoken_free(t); }
        else if (t->type == hashtag)
        {
            obj* head = new_ustring_obj(ustring_clone(t->content));
            metatoken_free(t);
            return head;
        }
        else // this should never occur if metaparser_is_valid_rule() was called first
        {
            printf("BUG ERROR: expecting identifier at start of rule, when found: ");
            metatoken_repr(t);
            printf("\nEnsure metaparser_is_valid_rule() was called before this function\n");
            exit(1);
        }
    }
    printf("BUG ERROR: tokens list contains no real tokens\n");
    printf("Ensure metaparser_is_valid_rule() was called before this function\n");
    exit(1);
}

/**
 * returns the body tokens for the meta rule.
 * Frees any whitespace/comment tokens before the identifier.
 * Expects metaparser_is_valid_rule(), and then metaparser_get_rule_head()
 * to have been called first.
 */
vect* metaparser_get_rule_body(vect* tokens)
{
    vect* body_tokens = new_vect();
    while (vect_size(tokens) > 0)
    {
        obj* t_obj = vect_dequeue(tokens);
        metatoken* t = t_obj->data;

        // skip all whitespace
        if (t->type == whitespace || t->type == comment) { obj_free(t_obj); }
        // semicolon means finished collecting body tokens
        else if (t->type == meta_semicolon)
        {
            obj_free(vect_dequeue(body_tokens)); // equals sign at start
            obj_free(t_obj);                     // semicolon
            return body_tokens;
        }
        else
        {
            vect_enqueue(body_tokens, t_obj);
        }
    }
    printf("BUG ERROR: expected semicolon at end of rule\n");
    printf("Ensure metaparser_is_valid_rule() was called before this function\n");
    exit(1);
}

/**
 * Recursively construct the grammar symbol string from the given a meta-ast.
 * all heads, bodies, and charsets are inserted into the metaparser grammar table.
 * `head` may optionally be NULL, (e.g. for when the parser is handling anonymous expressions)
 * in which case the compiler will come up with a name for the rule.
 * Returns the identifier for the rule inserted. Note that the returned identifier is owned by the
 * grammar table, and must be copied if it is to be used by another process (e.g. other rule sentences).
 */
uint64_t metaparser_insert_rule_ast(uint64_t head_idx, metaast* body_ast)
{
    // determine if this is an anonymous rule, or user named rule
    bool anonymous = head_idx == NULL_SYMBOL_INDEX;

    // check if this AST is in the cache already
    obj* cache_key_obj = new_metaast_obj(body_ast);
    obj* cache_value_obj = dict_get(metaparser_ast_cache, cache_key_obj);
    if (cache_value_obj != NULL)
    {
        // save the unused key obj to be freed later
        vect_append(metaparser_unused_ast_cache, cache_key_obj);

        // get the cached body index
        uint64_t body_idx = *(uint64_t*)cache_value_obj->data;

        // if not an anonymous expression, create a production using the precached body
        if (!anonymous) { metaparser_add_production(head_idx, body_idx); }

        return body_idx;
    }

    switch (body_ast->type)
    {
        // Base case (non-recursive) rules
        case metaast_eps:
        {
            // crete an anonymous head if it wasn't provided
            head_idx = anonymous ? metaparser_get_anonymous_rule_head() : head_idx;

            // create a production for the head index pointing to the epsilon body index
            metaparser_add_production(head_idx, metaparser_get_eps_body_idx());
            break;
        }
        case metaast_identifier:
        {
            // get the symbol index of the identifier
            obj* nonterminal = new_ustring_obj(ustring_clone(body_ast->node.string));
            uint64_t nonterminal_idx = metaparser_add_symbol(nonterminal);

            // if head is defined, then create a whole production with a sentence containing just the identifier
            // otherwise this is an inner expression reference to the identifier where we can skip the redundant
            // sentence
            if (!anonymous)
            {
                // create a sentence with the identifier in it
                vect* sentence = new_vect();
                vect_append(sentence, new_uint_obj(nonterminal_idx));

                // add the sentence to the grammar
                uint64_t body_idx = metaparser_add_body(sentence);

                // insert the production
                metaparser_add_production(head_idx, body_idx);
            }
            else
            {
                // assign this identifier the null head
                head_idx = nonterminal_idx;
            }
            break;
        }
        case metaast_charset:
        {
            // crete an anonymous head if it wasn't provided
            head_idx = anonymous ? metaparser_get_anonymous_rule_head() : head_idx;

            // create a sentence containing just the charset
            vect* sentence = new_vect();

            // insert the terminal into the sentence
            obj* terminal = new_charset_obj(charset_clone(body_ast->node.cs));
            uint64_t terminal_idx = metaparser_add_symbol(terminal);
            vect_append(sentence, new_uint_obj(terminal_idx));

            // add the sentence to the grammar
            uint64_t body_idx = metaparser_add_body(sentence);

            // insert the production into the grammar
            metaparser_add_production(head_idx, body_idx);
            break;
        }
        case metaast_string:
        {
            // crete an anonymous head if it wasn't provided
            head_idx = anonymous ? metaparser_get_anonymous_rule_head() : head_idx;

            // create a sentence for the string
            vect* sentence = new_vect();

            // insert each character from the string into the sentence
            uint32_t* s = body_ast->node.string;
            uint32_t c;
            while ((c = *s++))
            {
                obj* cs_obj = new_charset_obj(NULL);
                charset_add_char(cs_obj->data, c);
                uint64_t terminal_idx = metaparser_add_symbol(cs_obj);
                vect_append(sentence, new_uint_obj(terminal_idx));
            }

            // insert the sentence into the bodies set
            uint64_t body_idx = metaparser_add_body(sentence);

            // push this sentence to the list of all sentences for this rule
            metaparser_add_production(head_idx, body_idx);
            break;
        }
        case metaast_caseless:
        {
            // crete an anonymous head if it wasn't provided
            head_idx = anonymous ? metaparser_get_anonymous_rule_head() : head_idx;

            // create a sentence for the string
            vect* sentence = new_vect();

            // insert upper and lowercase versions of each character from the string into the sentence
            uint32_t* s = body_ast->node.string;
            uint32_t c;
            while ((c = *s++))
            {
                uint32_t upper, lower;
                obj* cs_obj = new_charset_obj(NULL);
                if (unicode_upper_and_lower(c, &upper, &lower))
                {
                    charset_add_char(cs_obj->data, upper);
                    charset_add_char(cs_obj->data, lower);
                }
                else // character doesn't have upper/lowercase version, so add character as is
                {
                    charset_add_char(cs_obj->data, c);
                }
                uint64_t terminal_idx = metaparser_add_symbol(cs_obj);
                vect_append(sentence, new_uint_obj(terminal_idx));
            }

            // insert the sentence into the bodies set
            uint64_t body_idx = metaparser_add_body(sentence);

            // push this sentence to the list of all sentences for this rule
            metaparser_add_production(head_idx, body_idx);
            break;
        }

        // Recursive rules that need to compute the nested sentences
        case metaast_star:
        case metaast_plus:
        {
            // crete an anonymous head if it wasn't provided
            head_idx = anonymous ? metaparser_get_anonymous_rule_head() : head_idx;

            // get the identifier for the inner node
            uint64_t inner_head_idx = metaparser_get_symbol_or_anonymous(body_ast->node.repeat.inner);

            // build the sentence
            if (body_ast->node.repeat.count == 0 ||
                (body_ast->node.repeat.count == 1 && body_ast->type == metaast_star))
            {
                // simple star
                //#head = #A* | (#A)0* | (#A)1* | (#A)0+ =>
                //  #head = #A #head;
                //  #head = ϵ;

                //#head = #A #head
                vect* sentence0 = new_vect();
                vect_append(sentence0, new_uint_obj(inner_head_idx));
                vect_append(sentence0, new_uint_obj(head_idx));
                uint64_t sentence0_idx = metaparser_add_body(sentence0);
                metaparser_add_production(head_idx, sentence0_idx);

                //#head = ϵ
                metaparser_add_production(head_idx, metaparser_get_eps_body_idx());
            }
            else
            {
                // complex plus
                //#head = (#A)N+ =>
                //  #__0 = #A #__0;
                //  #__0 = ϵ;
                //  #head = #A #A #A ... #A #__0; //... N times

                // complex star
                //#head = (#A)N* =>
                //  #__0 = #A #__0;
                //  #__0 = ϵ;
                //  #head = #A #A #A ... #A #__0; //... N times
                //  #head = ϵ;

                //  #__0 = #A #__0
                uint64_t anonymous0_idx = metaparser_get_anonymous_rule_head();
                vect* sentence0 = new_vect();
                vect_append(sentence0, new_uint_obj(inner_head_idx));
                vect_append(sentence0, new_uint_obj(anonymous0_idx));
                uint64_t sentence0_idx = metaparser_add_body(sentence0);
                metaparser_add_production(anonymous0_idx, sentence0_idx);

                //  #__0 = ϵ;
                metaparser_add_production(anonymous0_idx, metaparser_get_eps_body_idx());

                //  #head = #A #A #A ... #A #__0; //... N times
                vect* sentence2 = new_vect();
                for (int i = 0; i < body_ast->node.repeat.count; i++)
                {
                    vect_append(sentence2, new_uint_obj(inner_head_idx));
                }
                vect_append(sentence2, new_uint_obj(anonymous0_idx));
                uint64_t sentence2_idx = metaparser_add_body(sentence2);
                metaparser_add_production(head_idx, sentence2_idx);

                // convert from plus to star by making the last rule optional
                if (body_ast->type == metaast_star)
                {
                    //  #head = ϵ;
                    metaparser_add_production(head_idx, metaparser_get_eps_body_idx());
                }
            }
            break;
        }
        case metaast_count:
        {
            // crete an anonymous head if it wasn't provided
            head_idx = anonymous ? metaparser_get_anonymous_rule_head() : head_idx;

            uint64_t inner_head_idx = metaparser_get_symbol_or_anonymous(body_ast->node.repeat.inner);

            if (body_ast->node.repeat.count == 0)
            {
                //#head = (#A)0 => ϵ;  //this is probably a typo on the user's part...
                printf("WARNING: ");
                metaast_str(body_ast);
                printf(" is equivalent to ϵ\n"
                       "Did you mean `(");
                metaast_str(body_ast->node.repeat.inner);
                printf(")*`"
                       " or `(");
                metaast_str(body_ast->node.repeat.inner);
                printf(")+`"
                       " or `(");
                metaast_str(body_ast->node.repeat.inner);
                printf(")N` where N > 1 ?\n");
                metaparser_add_production(head_idx, metaparser_get_eps_body_idx());
            }
            else
            {
                //#head = (#A)N =>
                //  #head = #A #A #A ... #A; //... N times
                vect* sentence = new_vect();
                for (int i = 0; i < body_ast->node.repeat.count; i++)
                {
                    vect_append(sentence, new_uint_obj(inner_head_idx));
                }
                uint64_t body_idx = metaparser_add_body(sentence);
                metaparser_add_production(head_idx, body_idx);
            }
            break;
        }
        case metaast_option:
        {
            // crete an anonymous head if it wasn't provided
            head_idx = anonymous ? metaparser_get_anonymous_rule_head() : head_idx;

            uint64_t inner_head_idx = metaparser_get_symbol_or_anonymous(body_ast->node.unary.inner);

            //#head = #A ? =>
            //  #head = #A
            //  #head = ϵ

            //  #head = #A
            vect* sentence0 = new_vect();
            vect_append(sentence0, new_uint_obj(inner_head_idx));
            uint64_t sentence0_idx = metaparser_add_body(sentence0);
            metaparser_add_production(head_idx, sentence0_idx);

            //  #head = ϵ
            metaparser_add_production(head_idx, metaparser_get_eps_body_idx());

            break;
        }
        case metaast_cat:
        {
            // crete an anonymous head if it wasn't provided
            head_idx = anonymous ? metaparser_get_anonymous_rule_head() : head_idx;

            //#head = #A #B => #A #B  //cat is already in CFG format.
            // TODO->handle cat with strings/charsets/identifiers/epsilon...
            vect* sentence = new_vect();
            for (size_t i = 0; i < body_ast->node.sequence.size; i++)
            {
                metaast* inner_i_ast = body_ast->node.sequence.elements[i];
                switch (inner_i_ast->type)
                {
                    // insert each char of the string into the parent sentence
                    case metaast_string:
                    {
                        uint32_t* s = inner_i_ast->node.string;
                        uint32_t c;
                        while ((c = *s++))
                        {
                            obj* cs_obj = new_charset_obj(new_charset());
                            charset_add_char(cs_obj->data, c);
                            uint64_t terminal_idx = metaparser_add_symbol(cs_obj);
                            vect_append(sentence, new_uint_obj(terminal_idx));
                        }
                        break;
                    }

                    case metaast_caseless:
                    {
                        uint32_t* s = inner_i_ast->node.string;
                        uint32_t c;
                        while ((c = *s++))
                        {
                            uint32_t upper, lower;
                            unicode_upper_and_lower(c, &upper, &lower);
                            obj* cs_obj = new_charset_obj(new_charset());
                            charset_add_char(cs_obj->data, upper);
                            charset_add_char(cs_obj->data, lower);
                            uint64_t terminal_idx = metaparser_add_symbol(cs_obj);
                            vect_append(sentence, new_uint_obj(terminal_idx));
                        }
                        break;
                    }

                    // insert the charset into the parent sentence
                    case metaast_charset:
                    {
                        obj* cs_obj = new_charset_obj(charset_clone(inner_i_ast->node.cs));
                        uint64_t terminal_idx = metaparser_add_symbol(cs_obj);
                        vect_append(sentence, new_uint_obj(terminal_idx));
                        break;
                    }

                    // insert the identifier into the parent sentence
                    case metaast_identifier:
                    {
                        obj* identifier = new_ustring_obj(ustring_clone(inner_i_ast->node.string));
                        uint64_t identifier_idx = metaparser_add_symbol(identifier);
                        vect_append(sentence, new_uint_obj(identifier_idx));
                        break;
                    }

                    // literal epsilons are skipped in a cat node
                    case metaast_eps:
                    {
                        break;
                    }

                    // all other types of ast are represented by an anonymous identifier
                    default:
                    {
                        uint64_t head_i_idx = metaparser_get_symbol_or_anonymous(body_ast->node.sequence.elements[i]);
                        vect_append(sentence, new_uint_obj(head_i_idx));
                        break;
                    }
                }
            }
            uint64_t body_idx = metaparser_add_body(sentence);
            metaparser_add_production(head_idx, body_idx);
            break;
        }
        case metaast_or:
        case metaast_greaterthan:
        {
            // crete an anonymous head if it wasn't provided
            head_idx = anonymous ? metaparser_get_anonymous_rule_head() : head_idx;

            //#rule = #A | #B =>
            //  #rule = #A
            //  #rule = #B

            metaparser_insert_or_inner_rule_ast(head_idx, body_ast->node.binary.left);
            if (body_ast->type == metaast_greaterthan) { metaparser_add_precedence_split(head_idx); }
            metaparser_insert_or_inner_rule_ast(head_idx, body_ast->node.binary.right);

            break;
        }

        // TODO->filters/other extensions of the parser
        case metaast_nofollow:
        case metaast_reject:
        {
            // crete an anonymous head if it wasn't provided
            head_idx = anonymous ? metaparser_get_anonymous_rule_head() : head_idx;

            // nofollow filter
            //#rule = #A / #B =>
            //  #rule = #__0
            //  #__0 = #A
            //  nofollow_table[#__A] = #B

            // reject filter
            //#rule = #A - #B =>
            //  #rule = #__0
            //  #__0 = #A
            //  reject_table[#__A] = #B

            // get the identifier for the left node
            uint64_t left_idx = metaparser_get_symbol_or_anonymous(body_ast->node.binary.left);

            // #__0 = #A
            uint64_t anonymous_head_idx = metaparser_get_anonymous_rule_head();
            vect* sentence0 = new_vect();
            vect_append(sentence0, new_uint_obj(left_idx));
            uint64_t sentence0_idx = metaparser_add_body(sentence0);
            metaparser_add_production(anonymous_head_idx, sentence0_idx);

            // #rule = #__0
            vect* sentence1 = new_vect();
            vect_append(sentence1, new_uint_obj(anonymous_head_idx));
            uint64_t sentence1_idx = metaparser_add_body(sentence1);
            metaparser_add_production(head_idx, sentence1_idx);

            // nofollow_table[#__A] = #B
            // check if the nofollow ast is a single charset, or a regular ustring
            obj* right;
            if (body_ast->node.binary.right->type == metaast_charset)
            {
                // nofollow is a single charset
                right = new_charset_obj(charset_clone(body_ast->node.binary.right->node.cs));
            }
            else if (body_ast->node.binary.right->type == metaast_string)
            {
                // nofollow is a regular ustring
                right = new_ustring_obj(ustring_clone(body_ast->node.binary.right->node.string));
            }
            else // harder case of non charset/string match, so filter will run a full sub-parse on input following #A
            {
                // nofollow is a full parse of the right hand side
                right = new_uint_obj(metaparser_get_symbol_or_anonymous(body_ast->node.binary.right));
            }

            // insert the restriction according to the filter type
            if (body_ast->type == metaast_nofollow)
            {
                // add the restriction to the nofollow table
                metaparser_add_nofollow(anonymous_head_idx, right);
            }
            else // if (type == metaast_reject)
            {
                // add the restriction to the reject table
                metaparser_add_reject(anonymous_head_idx, right);
            }

            break;
        }
        case metaast_capture:
        {
            // crete an anonymous head if it wasn't provided
            head_idx = anonymous ? metaparser_get_anonymous_rule_head() : head_idx;

            // capture node
            //#rule = #A. =>
            //  #rule = #__0
            //  #__0 = #A
            //  #__0 in capture_set = true

            // get the identifier for the inner node
            uint64_t inner_idx = metaparser_get_symbol_or_anonymous(body_ast->node.unary.inner);

            // #__0 = #A
            uint64_t anonymous_head_idx = metaparser_get_anonymous_rule_head();
            vect* sentence0 = new_vect();
            vect_append(sentence0, new_uint_obj(inner_idx));
            uint64_t sentence0_idx = metaparser_add_body(sentence0);
            metaparser_add_production(anonymous_head_idx, sentence0_idx);

            // #rule = #__0
            vect* sentence1 = new_vect();
            vect_append(sentence1, new_uint_obj(anonymous_head_idx));
            uint64_t sentence1_idx = metaparser_add_body(sentence1);
            metaparser_add_production(head_idx, sentence1_idx);

            // #__0 in capture_set = true
            metaparser_add_capture(anonymous_head_idx);

            break;
        }

        // ERROR->should not allow, or come up with semantics for
        // e.g. (#A)~ => ξ* - #A
        // should be an error since this only makes sense for charsets
        case metaast_compliment:
        case metaast_intersect:
            printf("ERROR: compliment/intersect is only applicable to charsets. There are (currently) no semantics for "
                   "what they mean for a regular grammar production");
            break;
    }

    // if anonymous rule, save this AST to the cache, else save the cache_key for later deletion
    if (anonymous) { dict_set(metaparser_ast_cache, cache_key_obj, new_uint_obj(head_idx)); }
    else
    {
        vect_append(metaparser_unused_ast_cache, cache_key_obj);
    }
    return head_idx;
}

/**
 * For a nested ast rule, if the nested rule is a symbol (i.e. identifier or charset),
 * return its symbol index. Otherwise generate an anonymous identifier by inserting the ast
 * with a NULL parent head, and then return the index of the anonymous identifier.
 */
uint64_t metaparser_get_symbol_or_anonymous(metaast* ast)
{
    if (ast->type == metaast_identifier)
    {
        obj* nonterminal = new_ustring_obj(ustring_clone(ast->node.string));
        return metaparser_add_symbol(nonterminal);
    }
    else if (ast->type == metaast_charset)
    {
        obj* terminal = new_charset_obj(charset_clone(ast->node.cs));
        return metaparser_add_symbol(terminal);
    }
    else
    {
        // all other cases, insert an anonymous expression, and return its head
        return metaparser_insert_rule_ast(NULL_SYMBOL_INDEX, ast);
    }
}

/**
 * Indicate which types of AST nodes do not create sub rules.
 * e.g. or nodes do not nest, and instead are all flattened into the parent rule.
 * Additionally, atomic types (i.e. identifier, charset, string, etc.) also follow this pattern.
 */
inline bool metaparser_ast_uses_parent_level(metaast_type type)
{
    switch (type)
    {
        case metaast_or:
        case metaast_greaterthan:
        case metaast_eps:
        case metaast_identifier:
        case metaast_charset:
        case metaast_string:
        case metaast_cat: return true;
        default: return false;
    }
}

/**
 * Insert the ast at the same level as the parent ast.
 * e.g. or nodes insert children with the same head as the parent.
 * If the inner node needs an anonymous head, that head is returned,
 * else NULL_SYMBOL_INDEX is returned. This means the ast reused the parents head, and does not need to
 * ruther be inserted into the grammar tables
 *
 * NOTE: Parent is expected to be an or node (as no other node types insert children at the same level)
 */
void metaparser_insert_or_inner_rule_ast(uint64_t parent_head_idx, metaast* ast)
{
    // case where the inner node reuses the parent index
    if (metaparser_ast_uses_parent_level(ast->type))
    {
        // insert the inner as itself, using the parent's head
        metaparser_insert_rule_ast(parent_head_idx, ast);
    }
    else // inner node needs to create an anonymous head which the parent adds as a sentence
    {
        uint64_t anonymous_idx = metaparser_insert_rule_ast(NULL_SYMBOL_INDEX, ast);

        // create a sentence containing just the anonymous rule
        vect* sentence = new_vect();
        vect_append(sentence, new_uint_obj(anonymous_idx));
        uint64_t body_idx = metaparser_add_body(sentence);

        // create the production by adding the sentence to the parent head
        metaparser_add_production(parent_head_idx, body_idx);
    }
}

/**
 * Return the set that stores all symbols generated by the metaparser.
 */
set* metaparser_get_symbols() { return metaparser_symbols; }

/**
 * Return the set that stores all bodies generated by the metaparser.
 */
set* metaparser_get_bodies() { return metaparser_bodies; }

/**
 * Return the map containing all productions generated by the metaparser.
 */
dict* metaparser_get_productions() { return metaparser_productions; }

/**
 * Return the index of the epsilon rule.
 */
uint64_t metaparser_get_eps_body_idx()
{
    // If no epsilon body has been added yet, create one
    if (metaparser_eps_body_idx == NULL_SYMBOL_INDEX)
    {
        // epsilon is represented by an empty vector
        vect* epsilon = new_vect();
        metaparser_eps_body_idx = metaparser_add_body(epsilon);
    }
    return metaparser_eps_body_idx;
}

/**
 * Get the index of the augmented start symbol for the grammar.
 * If no symbol has been set as the start symbol, use the first
 * non-terminal in metaparser_symbols and create the augmented rule
 * from that.
 */
uint64_t metaparser_get_start_symbol_idx()
{
    // check if start symbol not set yet
    if (metaparser_start_symbol_idx == NULL_SYMBOL_INDEX)
    {
        // if can't find a start symbol, tell parser to use the first non-terminal.
        uint64_t start_symbol_idx = NULL_SYMBOL_INDEX;

        // check for any rules labelled exactly `#start`
        set* symbols = metaparser_get_symbols();
        for (size_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
        {
            if (metaparser_is_symbol_terminal(symbol_idx)) { continue; }
            uint32_t* terminal = metaparser_get_symbol(symbol_idx)->data;

            // found #start non-terminal
            if (ustring_charstar_cmp(terminal, "#start") == 0)
            {
                start_symbol_idx = symbol_idx;
                break;
            }
        }

        // set the start symbol using either the found #start rule, or NULL
        metaparser_set_start_symbol(start_symbol_idx);
    }
    return metaparser_start_symbol_idx;
}

/**
 * Insert the symbol into the symbol set, and return its index.
 * Symbols already in the set are freed.
 */
uint64_t metaparser_add_symbol(obj* symbol)
{
    uint64_t symbol_idx = set_add(metaparser_symbols, symbol);
    return symbol_idx;
}

/**
 * Return the symbol at index i of the symbol set.
 */
obj* metaparser_get_symbol(uint64_t i) { return set_get_at_index(metaparser_symbols, i); }

/**
 * Determine whether the symbol at the given index is a terminal or non-terminal.
 * Charsets are terminals, while identifiers (UnicodeString_t) are non-terminals.
 */
bool metaparser_is_symbol_terminal(uint64_t symbol_idx)
{
    obj* symbol = metaparser_get_symbol(symbol_idx);
    return symbol->type == CharSet_t;
}

/**
 * Insert the body into the bodies set, and return its index.
 * Bodies already in the set are freed.
 */
uint64_t metaparser_add_body(vect* body)
{
    obj* body_obj = new_vect_obj(body);
    uint64_t body_idx = set_add(metaparser_bodies, body_obj);
    return body_idx;
}

/**
 * Return the body at index i of the bodies set.
 */
vect* metaparser_get_body(uint64_t i)
{
    obj* body_obj = set_get_at_index(metaparser_bodies, i);
    return body_obj->data; // TODO->add error checking... could be null, could also be not a vect...
}

/**
 * Create a production entry for the grammer in the production heads and bodies vectors.
 */
void metaparser_add_production(uint64_t head_idx, uint64_t body_idx)
{
    // create a new entry containing the head if it doesn't exist
    if (!dict_contains_uint_key(metaparser_productions, head_idx))
    {
        dict_set(metaparser_productions, new_uint_obj(head_idx), new_set_obj(NULL));
    }

    // get the set containing the list of bodies for this head
    obj* bodies_obj = dict_get_uint_key(metaparser_productions, head_idx);
    if (bodies_obj->type != Set_t)
    {
        printf("ERROR: metaparser_productions should only point to vectors. Instead found type %d\n", bodies_obj->type);
        exit(1);
    }
    set* bodies = bodies_obj->data;

    // insert the production body into the set
    set_add(bodies, new_uint_obj(body_idx));
}

/**
 * Return the set of production bodies for the given head index.
 * Returns null if no bodies are found.
 */
set* metaparser_get_production_bodies(uint64_t head_idx)
{
    obj* bodies_obj = dict_get_uint_key(metaparser_productions, head_idx);
    if (bodies_obj == NULL)
    {
        // print out the head symbol too...
        printf("ERROR: no production bodies exist for head ");
        obj_str(metaparser_get_symbol(head_idx));
        printf("\n");
        exit(1);
        return NULL;
    }
    return bodies_obj->data;
}

/**
 * Return the number of productions for a given head index.
 */
size_t metaparser_get_num_production_bodies(uint64_t head_idx)
{
    return set_size(metaparser_get_production_bodies(head_idx));
}

/**
 * Return a specific production body for the given head and body indices.
 */
vect* metaparser_get_production_body(uint64_t head_idx, uint64_t production_idx)
{
    set* bodies = metaparser_get_production_bodies(head_idx);
    if (bodies == NULL) { return NULL; }
    uint64_t* body_idx = bodies->entries[production_idx].item->data;
    return metaparser_bodies->entries[*body_idx].item->data;
}

/**
 * Create an augmented production to be used by the grammar during parsing.
 * start_symbol_idx may be NULL_SYMBOL_INDEX, in which case, the first non-terminal
 * in metaparser_symbols will be used as the start rule.
 * If provided `start_symbol_idx` is a suitable augmented start symbol, then use that as is.
 */
void metaparser_set_start_symbol(uint64_t start_symbol_idx)
{
    // if not given an index, select the first non-terminal as the start symbol
    if (start_symbol_idx == NULL_SYMBOL_INDEX)
    {
        if (set_size(metaparser_symbols) == 0)
        {
            printf("ERROR: Could not create start symbol, symbol table is empty\n");
            return;
        }

        // find the first non-terminal, and use that as the start symbol. This will likely always be 0...
        for (start_symbol_idx = 0; start_symbol_idx < set_size(metaparser_symbols); start_symbol_idx++)
        {
            if (!metaparser_is_symbol_terminal(start_symbol_idx)) { break; }
        }
    }

    // new CNP algorithm doesn't require start symbol to have only a single body
    metaparser_start_symbol_idx = start_symbol_idx;
    // // check if we need an augmented head, or we can just use the start rule
    // set* bodies = metaparser_get_production_bodies(start_symbol_idx);
    // if (set_size(bodies) == 1)
    // {
    //     vect* body = metaparser_get_production_body(start_symbol_idx, 0);
    //     if (vect_size(body) == 1)
    //     {
    //         uint64_t* symbol_idx = vect_get(body, 0)->data;
    //         if (!metaparser_is_symbol_terminal(*symbol_idx))
    //         {
    //             metaparser_start_symbol_idx = start_symbol_idx;
    //             return;
    //         }
    //     }
    // }

    // // Otherwise, create a new production S' -> S for the augmented grammar
    // uint64_t augmented_head_idx = metaparser_get_anonymous_rule_head();
    // vect* augmented_body = new_vect();
    // vect_append(augmented_body, new_uint_obj(start_symbol_idx));
    // uint64_t augmented_body_idx = metaparser_add_body(augmented_body);
    // metaparser_add_production(augmented_head_idx, augmented_body_idx);
    // metaparser_start_symbol_idx = augmented_head_idx;
}

/**
 * Insert a nofollow restriction that says the right expression may not follow the left expression.
 */
void metaparser_add_nofollow(uint64_t left_idx, obj* right)
{
    // verify that the left_idx is not already in the nofollow set (this should always be true)
    if (dict_contains_uint_key(metaparser_nofollow_table, left_idx))
    {
        printf("ERROR: metaparser_nofollow already contains left_idx %" PRIu64 "\n", left_idx);
        obj_str(metaparser_get_symbol(left_idx));
        printf(" / ");
        obj_str(right);
        printf("\n");
        exit(1);
    }

    // map from left_idx to right in the nofollow table
    dict_set(metaparser_nofollow_table, new_uint_obj(left_idx), right);
}

/**
 * Return the entry in the nofollow table for the given rule.
 * returns NULL if there are no restrictions.
 */
obj* metaparser_get_nofollow_entry(uint64_t head_idx) { return dict_get_uint_key(metaparser_nofollow_table, head_idx); }

/**
 * Insert a reject restriction that says the left expression may not derive a sequence also derivable by the right
 * expression.
 */
void metaparser_add_reject(uint64_t left_idx, obj* right)
{
    // verify that the left_idx is not already in the nofollow set (this should always be true)
    if (dict_contains_uint_key(metaparser_reject_table, left_idx))
    {
        printf("ERROR: metaparser_reject already contains left_idx %" PRIu64 "\n", left_idx);
        obj_str(metaparser_get_symbol(left_idx));
        printf(" - ");
        obj_str(right);
        printf("\n");
        exit(1);
    }

    // map from left_idx to right in the nofollow table
    dict_set(metaparser_reject_table, new_uint_obj(left_idx), right);
}

/**
 * Return the entry in the reject table for the given rule.
 * returns NULL if there are no restrictions.
 */
obj* metaparser_get_reject_entry(uint64_t head_idx) { return dict_get_uint_key(metaparser_reject_table, head_idx); }

/**
 * Insert an entry into the precedence table for the given head_idx, indicating that all following bodies are at the
 * next precedence level.
 *
 * Note that the table needs to be finalized after all entries have been added.
 */
void metaparser_add_precedence_split(uint64_t head_idx)
{
    set* bodies = metaparser_get_production_bodies(head_idx);
    obj* precedence_table_obj = dict_get_uint_key(metaparser_precedence_tables, head_idx);
    if (precedence_table_obj == NULL)
    {
        precedence_table_obj = new_dict_obj(NULL);
        dict_set(metaparser_precedence_tables, new_uint_obj(head_idx), precedence_table_obj);
    }
    dict_set(precedence_table_obj->data, new_uint_obj(set_size(bodies)),
             new_uint_obj(dict_size(precedence_table_obj->data) + 1));
}

/**
 * Return the body precedence table for the given head. Returns NULL if there is no precedence table.
 */
dict* metaparser_get_precedence_table(uint64_t head_idx)
{
    obj* result = dict_get_uint_key(metaparser_precedence_tables, head_idx);
    return result == NULL ? NULL : result->data;
}

/**
 * Fill out each individual precedence table with entries for the precedence levels that are not yet filled out.
 */
void metaparser_finalize_precedence_tables()
{
    for (size_t i = 0; i < dict_size(metaparser_precedence_tables); i++)
    {
        obj k, v;
        dict_get_at_index(metaparser_precedence_tables, i, &k, &v);
        uint64_t* head_idx = k.data;
        set* bodies = metaparser_get_production_bodies(*head_idx);

        dict* precedence_table = v.data;
        uint64_t prev_split_idx = 0;
        uint64_t prev_level = 0;
        size_t num_kernels = dict_size(precedence_table);
        for (size_t j = 0; j < num_kernels; j++)
        {
            obj k, v;
            dict_get_at_index(precedence_table, j, &k, &v);
            uint64_t* split_idx = k.data;
            uint64_t* level = v.data;
            for (uint64_t body_idx = prev_split_idx; body_idx < *split_idx; body_idx++)
            {
                dict_set(precedence_table, new_uint_obj(body_idx), new_uint_obj(*level - 1));
            }
            prev_split_idx = *split_idx + 1;
            prev_level = *level;
        }

        // insert all bodies after the last split into the last level
        for (size_t j = prev_split_idx; j < set_size(bodies); j++)
        {
            dict_set(precedence_table, new_uint_obj(j), new_uint_obj(prev_level));
        }
    }
}

/**
 * Add a production head to the list of catpure heads.
 * Catpure is used to indicate which parts of the rule are to be recorded from the input stream.
 * e.g. for a rule like #sum = #expr '+' #expr;, the #expr components ought to be captured when constructing an AST,
 * while the '+' is not necessary.
 */
void metaparser_add_capture(uint64_t head_idx)
{
    if (!set_contains(metaparser_capture_set, &(obj){.type = UInteger_t, .data = &head_idx}))
    {
        set_add(metaparser_capture_set, new_uint_obj(head_idx));
    }
}

/**
 * Check if a given head is a capture head.
 */
bool metaparser_is_capture(uint64_t head_idx)
{
    return set_contains(metaparser_capture_set, &(obj){.type = UInteger_t, .data = &head_idx});
}

#endif