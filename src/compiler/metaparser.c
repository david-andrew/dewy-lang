#ifndef METAPARSER_C
#define METAPARSER_C

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <inttypes.h>

#include "vector.h"
#include "set.h"
#include "charset.h"
#include "metatoken.h"
#include "metascanner.h"
#include "metaparser.h"
#include "metaast.h"
#include "utilities.h"
#include "ustring.h"


/**
 * Global data structures used to manage all meta grammar rules.
 * body vects are a sequence of uint indices refering to either heads or charsets.
 * heads are referred to by odd indices, while charsets are referred to by even indices.
 * i.e. real_head_idx = head_idx / 2 <=> real_head_idx * 2 + 1 = head_idx
 * i.e. real_body_idx = body_idx / 2 <=> real_body_idx * 2 + 1 = body_idx
 */
dict* metaparser_heads;     //map of all production nonterminals to a set of corresponding bodies 
dict* metaparser_bodies;    //map of all production strings to a set of all corresponding heads
set* metaparser_charsets;   //set of all terminals (i.e. charsets) in all productions


/**
 * Initialize all global data structures used by metaparser.
 */
void initialize_metaparser()
{
    metaparser_heads = new_dict();
    metaparser_bodies = new_dict();
    metaparser_charsets = new_set();
}


/**
 * Free up all global data structures used by metaparser.
 */
void release_metaparser()
{
    dict_free(metaparser_heads);
    dict_free(metaparser_bodies);
    set_free(metaparser_charsets);
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
obj* metaparser_get_anonymous_rule_head()
{
    //determine the string width of the number
    size_t width = ceil(log10(metaparser_anonymous_rule_count + 1));
    width += 4; //room for `#__` at start and null terminator at end
    
    //create a normal char* that will be the head
    char* num_str = malloc(width * sizeof(char));
    sprintf(num_str, "#__%"PRIu64, metaparser_anonymous_rule_count);

    //convert to unicode string (wrapped in obj*), and cleanup char* version
    obj* head = new_unicode_string_obj(ustring_utf8_substr(num_str, 0, width-1));
    free(num_str);

    //increment the counter. Increment by 2 so it matches indices in metaparser_bodies.
    metaparser_anonymous_rule_count += 2;
    
    return head;
}


/**
 * Try to scan for a rule in the current list of tokens. 
 * Returns `true` if a rule was successfully parsed.
 * Assumes that tokens may contain comments or whitespace.
 */
bool parse_next_meta_rule(vect* tokens)
{
    //check for head, equals sign, and semicolon
    if (!metaparser_is_valid_rule(tokens)) { return false; }

    //construct head and body for the rule
    obj* head = metaparser_get_rule_head(tokens);
    vect* body_tokens = metaparser_get_rule_body(tokens);
    metaast* body_ast = metaast_parse_expr(body_tokens);

    //failed to parse body into ast
    if (body_ast == NULL)
    {
        vect_free(body_tokens);
        obj_free(head);
        return false;
    }

    //reduce any constant expressions in the ast (e.g. charset operations)
    while (metaast_fold_constant(&body_ast));

    //recursively convert to sentences + insert into grammar table
    // return metaparser_insert_rule(head, body_ast); 
    return true;

    // //TEMPORARY
    // if (body_ast != NULL)
    // {
    //     obj_print(head);
    //     printf(" = ");
    //     metaast_str(body_ast);
    //     printf("\n");
    //     metaast_free(body_ast);
    // }
    // else
    // {   
    //     obj_print(head);
    //     printf(" body tokens returned NULL\n");
    //     vect_free(body_tokens);
    // }

    // obj_free(head);
    // return true;
}

/**
 * Verify that the stream of tokens is valid syntax for a rule
 * #rule = #identifier #ws '=' #ws #expr #ws ';';
 */
bool metaparser_is_valid_rule(vect* tokens)
{
    //shortest rule is 4 tokens: #id '=' <expr> ;
    if (vect_size(tokens) == 0) 
    { 
        printf("ERROR: cannot parse rule from empty tokens list\n");
        return false; 
    }
    
    //scan for head
    int i = metatoken_get_next_real_token(tokens, 0);
    if (i < 0 || !metatoken_is_i_of_type(tokens, i, hashtag))
    {
        printf("ERROR: no identifier found at start of meta rule\n");
        return false;
    }
    
    //scan for equals sign
    i = metatoken_get_next_real_token(tokens, i+1);
    if (i < 0 || !metatoken_is_i_of_type(tokens, i, meta_equals_sign))
    {
        printf("ERROR: no equals sign found following identifier in meta rule\n");
        return false;
    }

    //scan for ending semicolon
    i = metatoken_get_next_token_of_type(tokens, meta_semicolon, i+1);
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
        obj* t_obj = vect_dequeue(tokens);
        metatoken* t = t_obj->data;
        if (t->type == whitespace || t->type == comment)
        {
            obj_free(t_obj);
        }
        else if (t->type == hashtag)
        {
            return t_obj;
        }
        else //this should never occur if metaparser_is_valid_rule() was called first
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

        //skip all whitespace
        if (t->type == whitespace || t->type == comment)
        {
            obj_free(t_obj);
        }
        //semicolon means finished collecting body tokens
        else if (t->type == meta_semicolon)
        {
            obj_free(vect_dequeue(body_tokens));    // equals sign at start
            obj_free(t_obj);                        // semicolon
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



// /**
//  * Recursively construct the grammar symbol string from the given a meta-ast.
//  * all heads, bodies, and charsets are inserted into their respective metaparser set.
//  * additionally, corresponding join table entries are also created.
//  * Calls vect_free(rule_body_tokens) at the end of the func.
//  * `head` is the identifier being used for the rule body being constructed.
//  * `head` may optionally be NULL, in which case the compiler will come up with a name for the rule
//  */
// vect* metaparser_create_body(obj* head, metaast* body_ast)
// {
//     return NULL;
// }



size_t metaparser_add_head(obj* head){}
obj* metaparser_get_head(size_t i){}

size_t metaparser_add_body(obj* body){}
vect* metaparser_get_body(size_t i){}

void metaparser_join(size_t head_idx, size_t body_idx){}



#endif