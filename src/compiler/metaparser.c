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
    obj* head = new_unicode_string_obj(utf8_substr(num_str, 0, width-1));
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
    //get index of first non-whitespace/comment token, and check if hashtag
    int start_idx = metatoken_get_next_real_token(tokens, 0);
    if (!metatoken_is_token_i_of_type(tokens, start_idx, hashtag)) { return false; }

    //get index of next real token, and check if meta_equals_sign
    int stop_idx = metatoken_get_next_real_token(tokens, start_idx+1);
    if (!metatoken_is_token_i_of_type(tokens, stop_idx, meta_equals_sign)) { return false; }

    //search for the first occurance of a semicolon
    stop_idx = metatoken_get_next_token_of_type(tokens, meta_semicolon, stop_idx+1);
    if (stop_idx < 0) { return false; }

    //free all tokens up to the start of the rule (as they should be whitespace and comments)
    for (int i = 0; i < start_idx; i++) { obj_free(vect_dequeue(tokens)); }

    //first token in the tokens stream is the meta_identifier
    metatoken* rule_identifier_token = obj_free_keep_inner(vect_dequeue(tokens), MetaToken_t);

    //collect all tokens after identifier to tail that form the production body
    vect* body_tokens = new_vect();
    for (int i = start_idx+1; i <= stop_idx; i++)
    {
        //keep token only if non-whitespace/comment
        obj* t = vect_dequeue(tokens);
        metatoken_type type = ((metatoken*)t->data)->type;
        if (type != whitespace && type != comment) { vect_enqueue(body_tokens, t); }
        else { obj_free(t); }
    }

    //free delimiter tokens from body
    obj_free(vect_dequeue(body_tokens));    // equals sign at start
    obj_free(vect_pop(body_tokens));        // semicolon at end
    
    // printf("tokens: "); vect_str(body_tokens); printf("\n");

    //create the head from the rule_identifier_token
    obj* head = new_unicode_string_obj(rule_identifier_token->content);
    free(rule_identifier_token);

    // printf("Rule\n");
    // for (int i = 0; i < vect_size(body_tokens); i++) { metatoken_repr(vect_get(body_tokens, i)->data); }

    //create an AST from the tokens, and combine all charset expressions
    metaast* body_ast = metaast_parse_expr(body_tokens);
    while (metaast_fold_constant(body_ast));

    obj_print(head);
    printf(" = ");
    if (body_ast == NULL) { printf("NULL"); vect_free(body_tokens); } 
    else { metaast_str(body_ast); }
    printf("\n");
    obj_free(head);

    //recursively translate the AST into CFG production bodies
    // metaparser_create_body(head, body_ast);
    if (body_ast) //TODO->take out later
    metaast_free(body_ast);

    return true;
}


/**
 * Recursively construct the grammar symbol string from the given a meta-ast.
 * all heads, bodies, and charsets are inserted into their respective metaparser set.
 * additionally, corresponding join table entries are also created.
 * Calls vect_free(rule_body_tokens) at the end of the func.
 * `head` is the identifier being used for the rule body being constructed.
 * `head` may optionally be NULL, in which case the compiler will come up with a name for the rule
 */
vect* metaparser_create_body(obj* head, metaast* body_ast)
{
    return NULL;
}



size_t metaparser_add_head(obj* head){}
obj* metaparser_get_head(size_t i){}

size_t metaparser_add_body(obj* body){}
vect* metaparser_get_body(size_t i){}

void metaparser_join(size_t head_idx, size_t body_idx){}



#endif