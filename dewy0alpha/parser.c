#ifndef PARSER_C
#define PARSER_C

#include <stdio.h>
#include <string.h>

#include "object.c"
#include "token.c"
#include "vector.c"
#include "dictionary.c"
#include "set.c"
#include "mast.c"
#include "scanner.c"


//TODO
// typedef struct parser_context_struct
// {
//     dict* meta_symbols;
//     dict* meta_rules;
//     //other context stuff
// } parser_context;


//definitions for the AST


//forward declarations
int get_next_real_token(vect* tokens, int i);
int get_next_token_type(vect* tokens, token_type type, int i);
void update_meta_symbols(dict* meta_symbols, vect* tokens);
void create_lex_rule(dict* meta_rules, vect* tokens);
bool expand_rules(vect* tokens, dict* meta_rules);
obj* build_ast(vect* tokens);
size_t get_lowest_precedence_index(vect* tokens);
size_t find_closing_pair(vect* tokens, size_t start);

//returns the index of the next non-whitespace and non-comment token.
//returns -1 if none are present in the vector
int get_next_real_token(vect* tokens, int i)
{
    //while we haven't reached the end of the token stream
    //if the current token isn't whitespace or a comment, return its index
    while (i < vect_size(tokens))
    {
        token* t = (token*)vect_get(tokens, i)->data;
        if (t->type != whitespace && t->type != comment) { return i; }
        i++;
    }

    //reached end without finding a real token
    return -1;
}

//return the index of the first occurance of the specified token type.
//returns -1 if not present in the vector
int get_next_token_type(vect* tokens, token_type type, int i)
{
    //while we haven't reached the end of the tokens stream
    //if the current token is the desired type, return its index
    while (i < vect_size(tokens))
    {
        token* t = (token*)vect_get(tokens, i)->data;
        if (t->type == type) { return i; }
        i++;
    }

    //reached end without finding token of desired type
    return -1;
}


void update_meta_symbols(dict* meta_symbols, vect* tokens)
{
    //get the index of the first non-whitespace/comment token
    int head_idx = get_next_real_token(tokens, 0);
    if (head_idx < 0) { return; }
 
    //if the first token isn't a hashtag then this isn't a meta-rule
    token* head = (token*)vect_get(tokens, head_idx)->data;
    if (head->type != hashtag) { return; }
        
    //get the index of the next real token
    int tail_idx = get_next_real_token(tokens, head_idx+1);
    if (tail_idx < 0) { return; }

    //if the next token isn't a meta_equals_sign this isn't a meta-rule
    token* tail = (token*)vect_get(tokens, tail_idx)->data;
    if (tail->type != meta_equals_sign) { return; }

    //search for the first occurance of a semicolon
    tail_idx = get_next_token_type(tokens, meta_semicolon, tail_idx+1);
    if (tail_idx < 0) { return; }
    tail = (token*)vect_get(tokens, tail_idx)->data;
    // assert(tail->type == meta_semicolon);

    //free all tokens up to the start of the rule (as they should be whitespace and comments)
    for (int i = 0; i < head_idx; i++)
    {
        obj_free(vect_dequeue(tokens));
    }

    //first token in the tokens stream should be the meta_identifier
    token* rule_identifier_token = (token*)vect_dequeue(tokens)->data;

    //collect together all tokens from head to tail and store in the symbol table, as a vect
    vect* rule_body = new_vect();
    
    //store all the tokens for the rule into the rule_body vector
    for (int i = head_idx+1; i < tail_idx; i++) //skip identifier and stop before semicolon
    {
        vect_enqueue(rule_body, vect_dequeue(tokens));
    }

    //free the semicolon at the end of the rule
    obj_free(vect_dequeue(tokens));

    //remove whitespace and comments from the rule
    remove_token_type(rule_body, whitespace);
    remove_token_type(rule_body, comment);

    //free the meta_equals sign at the start of the rule body
    obj_free(vect_dequeue(rule_body));


    //store the rule_identifier and the rule_body into the symbol table
    //TODO->need to set up obj* for string, or ability to hash tokens
    //TODO->for now, should probably check if the rule is alredy present, as it will be overwritten. in the future, you should be able to update rules, by inserting the original into anywhere it's referenced in the new one


    // printf("%s -> ", rule_identifier_token->content);
    // vect_str(rule_body);
    // printf("\n");

    char* rule_identifier = clone(rule_identifier_token->content);
    free(rule_identifier_token);
    obj* id = new_string(rule_identifier);
    obj* rule = vect_obj_wrap(rule_body);
    // obj_print(id);
    // printf("%s", *((char**)id->data));
    // printf(" -> ");
    // obj_print(rule);
    // printf("\n");

    //TODO->probably construct AST for rule here, and then store the AST in the meta symbol table
    dict_set(meta_symbols, id, rule);
    // printf("returned from dict_set\n");
    // dict_str(meta_symbols);
    // printf("\n");
    //TODO->store the rule_identifier and the rule_body into the symbol table
}

//check if the token stream starts with #lex(#rule1 #rule2 ...), and create an (AST?) rule
void create_lex_rule(dict* meta_rules, vect* tokens)
{
    //get the index of the first non-whitespace/comment token
    int head_idx = get_next_real_token(tokens, 0);
    if (head_idx < 0) { return; }

    //if the first token isn't the #lex hashtag then this isn't a call to #lex()
    token* head = (token*)vect_get(tokens, head_idx)->data;
    if (head->type != hashtag) { return; }
    if (strcmp(head->content, "#lex") != 0) { return; }

    //if the next token isn't an opening "(" meta_meta_parenthesis this isn't a call to #lex()
    int tail_idx = head_idx + 1;
    if (tail_idx >= vect_size(tokens)) { return; }
    token* tail = (token*)vect_get(tokens, tail_idx)->data;
    if (tail->type != meta_left_parenthesis) 
    { 
        printf("ERROR: #lex keyword followed by non-parenthesis token [");
        token_str(tail);
        printf("]\n");
        return; 
    }

    //get the index of the closing parenthesis
    tail_idx = get_next_token_type(tokens, meta_right_parenthesis, tail_idx+1);
    if (tail_idx < 0) { return; }

    //verify that it is a closing parenthesis
    // tail = (token*)vect_get(tokens, tail_idx)->data;
    // if (strcmp(tail->content, ")") != 0)
    // {
    //     printf("ERROR: #lex function encountered an opening parenthesis \"(\" in the body\n");
    //     return;
    // }

    //free all tokens up to the start of the rule (as they should be whitespace and comments)
    for (int i = 0; i < head_idx; i++)
    {
        obj_free(vect_dequeue(tokens));
    }
    //free the #lex keyword and the opening parenthesis
    obj_free(vect_dequeue(tokens));
    obj_free(vect_dequeue(tokens));

    vect* lex_rules = new_vect();
    for (int i = head_idx + 2; i < tail_idx; i++)
    {
        vect_enqueue(lex_rules, vect_dequeue(tokens));
    }

    //free the closing parenthesis
    obj_free(vect_dequeue(tokens));

    //remove whitespace and comments from the function arguments
    remove_token_type(lex_rules, whitespace);
    remove_token_type(lex_rules, comment);

    //TODO->construct ASTs for the rules
    //TODO->conversion/algorithm for scanning the rules
    //TODO->send the rules into the scanner
    //for now simply print out the rules to be lexed
    printf("Adding scanner rules: ");
    vect_str(lex_rules);

    //TODO->determine if we expand rules greedily or lazily 
    //for rule in lex_rules
    //  create ast from expanded rule

    printf("\n");
}


/**
    replace any instances of #rule with the 
*/
bool expand_rules(vect* tokens, dict* meta_rules)
{
    return false;
}

/**
    Recursively construct an AST out of 
*/
obj* build_ast(vect* tokens)
{
    //if #rules in tokens, at current precedence level don't have memoized ASTs yet
    //while (expand_rules(rule)){}

    //get the index of the lowest precedence token
    //if type is binary operator, build left and right trees from left and right side splits
    //if type is unary group,
    return NULL; 
}

/**
    return the index of the token with the lowest precedence
    if least precedence operator is a pair, e.g. [], {}, (), return the index of the left side
*/
size_t get_lowest_precedence_index(vect* tokens)
{
    //precedence levels
    //groups: []  ()  {}
    //

    //keep var for level of precedence
    //scan through tokens, determine token with minimum precedence level.
    //need to skip paren/bracket/brace pairs (still note precedence level of opening)
    //once have min precedence level, determine if left or right associative
    //if left associative, find left-most? instance of operator with determined precedence level
    //else (right associative) find right-most? instance of operator with determined precedence level 
    return 0;
}

/**
    return the index of the matching token pair for [], {}, ()
    will return 0 if no matching pair found
*/
size_t find_closing_pair(vect* tokens, size_t start)
{
    obj* t = vect_get(tokens, start);
    token_type opening = ((token*)t->data)->type;
    token_type closing;
    switch (opening) //determine matching closing type based on opening type
    {
        case meta_left_brace: { closing = meta_right_brace; break; }
        case meta_left_bracket: { closing = meta_right_brace; break; }
        case meta_left_parenthesis: { closing = meta_right_brace; break; }
        default: { printf("ERROR: find_closing_pair() called with non-pair type token (%d)\n", opening); return 0; }
    }
    int stack = -1;
    size_t stop = start + 1;
    while (stop < vect_size(tokens))
    {
        obj* t_obj = vect_get(tokens, stop);
        token* t = (token*)t_obj->data;
        if (t->type == opening) { stack--; }
        else if (t->type == closing) { stack++; }
        if (stack == 0) { return stop; }
        stop++;
    }
    
    printf("ERROR: no matching pair found for token type (%d) in vector: ", opening);
    vect_str(tokens);
    printf("\n");
    return 0;
}



#endif