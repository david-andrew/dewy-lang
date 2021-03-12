#ifndef METAPARSER_C
#define METAPARSER_C

#include "vector.h"
#include "set.h"
#include "metatoken.h"
#include "metascanner.h"
#include "metaparser.h"


set* metaparser_heads;
set* metaparser_bodies;
set* metaparser_charsets;


/**
 * Initialize any internal objects used by the metaparser.
 */
void initialize_metaparser()
{
    metaparser_heads = new_set();
    metaparser_bodies = new_set();
    metaparser_charsets = new_set();
}


/**
 * Free any initialized objects used by the metaparser.
 */
void release_metaparser()
{
    #define safe_free(A) if(A) { set_free(A); A = NULL; }
    safe_free(metaparser_heads)
    safe_free(metaparser_bodies)
    safe_free(metaparser_charsets)
}


/**
 * Try to scan for a rule in the current list of tokens. 
 * Returns `true` if a rule was successfully parsed.
 * Assumes that tokens may contain comments or whitespace.
 */
bool parse_next_meta_rule(vect* tokens)
{
    return false;

    //get the index of the first non-whitespace/comment token. meta-rule expects a hashtag
    int head_idx = get_next_real_metatoken(tokens, 0);
    if (head_idx < 0){ return false; }
    metatoken* head = (metatoken*)vect_get(tokens, head_idx)->data;
    if (head->type != hashtag) { return false; }

    //get the index of the next real token. meta-rule expects a meta_equals_sign
    int tail_idx = get_next_real_metatoken(tokens, head_idx+1);
    if (tail_idx < 0) { return false; }
    metatoken* tail = (metatoken*)vect_get(tokens, tail_idx)->data;
    if (tail->type != meta_equals_sign) { return false; }

    //search for the first occurance of a semicolon
    tail_idx = get_next_metatoken_type(tokens, meta_semicolon, tail_idx+1);
    if (tail_idx < 0) { return false; }
    tail = (metatoken*)vect_get(tokens, tail_idx)->data;

    //free all tokens up to the start of the rule (as they should be whitespace and comments)
    for (int i = 0; i < head_idx; i++) { obj_free(vect_dequeue(tokens)); }

    //first token in the tokens stream should be the meta_identifier
    metatoken* rule_identifier_token = (metatoken*)obj_free_keep_inner(vect_dequeue(tokens), MetaToken_t);

    //collect together all tokens from head to tail and store in the symbol table, as a vect
    vect* rule_body = new_vect();
    
    //store all the tokens for the rule into the rule_body vector
    //dequeued identifier already. Skip all comments/whitespace and stop before semicolon
    for (int i = head_idx+1; i < tail_idx; i++)
    {
        obj* t = vect_dequeue(tokens);
        metatoken_type type = ((metatoken*)t->data)->type;
        if (type != whitespace && type != comment)
        {
            vect_enqueue(rule_body, t);
        }
        else
        {
            obj_free(t);
        }
    }

    //free the semicolon at the end of the rule
    obj_free(vect_dequeue(tokens));

    //free the meta_equals sign at the start of the rule body
    obj_free(vect_dequeue(rule_body));


    //TODO->add this rule to the parse table
    return false;

    // //create an entry in the symbol table that points to the AST for this rule
    // char* rule_identifier = clone(rule_identifier_token->content);
    // obj* id = new_string(rule_identifier);
    // free(rule_identifier_token);

    // //build an AST out of the tokens list
    // obj* rule_ast = build_ast(rule_body, meta_symbols);
    // dict_set(meta_symbols, id, rule_ast);

}


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


// /**
//  * Return the index of the end of the next rule in the tokens vector
//  */
// size_t get_next_rule_boundary(vect* tokens, size_t start)
// {

// }





#endif