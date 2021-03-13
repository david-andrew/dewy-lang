#ifndef METAPARSER_C
#define METAPARSER_C

#include <stdio.h>

#include "vector.h"
#include "set.h"
#include "metatoken.h"
#include "metascanner.h"
#include "metaparser.h"
#include "utilities.h"


set* metaparser_heads;      //set of all production nonterminals 
set* metaparser_bodies;     //set of all production strings
set* metaparser_charsets;   //set of all terminals (i.e. charsets) in all productions

//join table
vect* metaparser_join_table;


/**
 * Initialize any internal objects used by the metaparser.
 */
void initialize_metaparser()
{
    metaparser_heads = new_set();
    metaparser_bodies = new_set();
    metaparser_charsets = new_set();
    metaparser_join_table = new_vect();
}


/**
 * Free any initialized objects used by the metaparser.
 */
void release_metaparser()
{
    set_free(metaparser_heads);
    set_free(metaparser_bodies);
    set_free(metaparser_charsets);
    vect_free(metaparser_join_table);
}


/**
 * Try to scan for a rule in the current list of tokens. 
 * Returns `true` if a rule was successfully parsed.
 * Assumes that tokens may contain comments or whitespace.
 */
bool parse_next_meta_rule(vect* tokens)
{
    //get index of first non-whitespace/comment token, and check if hashtag
    int start_idx = get_next_real_metatoken(tokens, 0);
    if (!is_metatoken_i_type(tokens, start_idx, hashtag)) { return false; }

    //get index of next real token, and check if meta_equals_sign
    int stop_idx = get_next_real_metatoken(tokens, start_idx+1);
    if (!is_metatoken_i_type(tokens, stop_idx, meta_equals_sign)) { return false; }

    //search for the first occurance of a semicolon
    stop_idx = get_next_metatoken_type(tokens, meta_semicolon, stop_idx+1);
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

    //TODO->uncomment when the following are implemented
    // metaparser_create_body(body_tokens)
    // metaparser_add_head(head)
    // metaparser_add_body(body)
    // metaparser_join(head_idx, body_idx)
    /*
    //create the head from the rule_identifier_token
    obj* head = new_unicode_string_obj(rule_identifier_token->content);
    free(rule_identifier_token);

    //recursively create the rule body for this production
    obj* body = metaparser_create_body(body_tokens);
    vect_free(body_tokens);

    //insert the head and body into their respective sets
    size_t head_idx = metaparser_add_head(head);
    size_t body_idx = metaparser_add_body(body);

    //link the head to the body in the join table
    metaparser_join(head_idx, body_idx);

    return true;
    */

    //for now just print out the rule head + body
    unicode_string_str(rule_identifier_token->content);
    printf(" = ");
    for (size_t i = 0; i < vect_size(body_tokens); i++)
    {
        metatoken* t = vect_get(body_tokens, i)->data;
        metatoken_str(t);
    }

    printf(";\n");

    metatoken_free(rule_identifier_token);
    vect_free(body_tokens);

    return true;
}


obj* metaparser_create_body(vect* rule_body_tokens){}


/**
 * Return the index of the next non whitespace/comment token
 */
int get_next_real_metatoken(vect* tokens, int i)
{
    //while we haven't reached the end of the token stream
    //if the current token isn't whitespace or a comment, return its index
    while (i < vect_size(tokens))
    {
        metatoken* t = (metatoken*)vect_get(tokens, i)->data;
        if (t->type != whitespace && t->type != comment) { return i; }
        i++;
    }

    //reached end without finding a real token
    return -1;
}


/**
 * return the index of the first occurance of the specified token type.
 * returns -1 if not present in the vector
 */
int get_next_metatoken_type(vect* tokens, metatoken_type type, int i)
{
    //while we haven't reached the end of the tokens stream
    //if the current token is the desired type, return its index
    while (i < vect_size(tokens))
    {
        metatoken* t = (metatoken*)vect_get(tokens, i)->data;
        if (t->type == type) { return i; }
        i++;
    }

    //reached end without finding token of desired type
    return -1;
}

bool is_metatoken_i_type(vect* tokens, int i, metatoken_type type)
{
    if (i < 0 || vect_size(tokens) < i){ return false; }
    metatoken* t = vect_get(tokens, i)->data;
    return t->type == type;
}


// /**
//  * Return the index of the end of the next rule in the tokens vector
//  */
// size_t get_next_rule_boundary(vect* tokens, size_t start)
// {

// }


size_t metaparser_add_head(obj* head){}
obj* metaparser_get_head(size_t i){}

size_t metaparser_add_body(obj* body){}
vect* metaparser_get_body(size_t i){}

void metaparser_join(size_t head_idx, size_t body_idx){}



#endif