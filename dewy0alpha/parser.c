#ifndef PARSER_C
#define PARSER_C

#include <stdio.h>
#include <string.h>

#include "object.c"
#include "vector.c"
#include "dictionary.c"
#include "set.c"

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

//returns the index of the next non-whitespace and non-comment token.
//returns -1 if none are present in the vector
int get_next_real_token(vect* tokens, int i)
{
    //the current token in the stream
    token* t;

    //while we haven't reached the end of the token stream
    //and the current token is whitespace or a comment
    while (i < vect_size(tokens) && (t = (token*)vect_get(tokens, i)->data) && (t->type == whitespace || t->type == comment))
    {
        i++;
    }

    if (i < vect_size(tokens))
    {
        return i;
    }
    else //reached end without finding a real token
    {
        return -1;
    }
}

//return the index of the first occurance of the specified token type.
//returns -1 if not present in the vector
int get_next_token_type(vect* tokens, token_type type, int i)
{
    //the current token in the stream
    token* t;

    //while we haven't reached the end of the tokens stream
    //and the current token isn't the desired type
    while (i < vect_size(tokens) && (t = (token*)vect_get(tokens, i)->data) && (t->type != type))
    {
        i++;
    }

    if (i < vect_size(tokens))
    {
        return i;
    }
    else //reached end without finding token of desired type
    {
        return -1;
    }
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
    token* rule_identifier = (token*)vect_dequeue(tokens)->data;

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
    printf("%s -> ", rule_identifier->content);
    vect_str(rule_body);
    printf("\n");
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
    if (tail->type != meta_meta_parenthesis || strcmp(tail->content, "(") != 0) 
    { 
        printf("ERROR: #lex keyword followed by non-parenthesis token [");
        token_str(tail);
        printf("]\n");
        return; 
    }

    //get the index of the closing parenthesis
    tail_idx = get_next_token_type(tokens, meta_meta_parenthesis, tail_idx+1);
    if (tail_idx < 0) { return; }

    //verify that it is a closing parenthesis
    tail = (token*)vect_get(tokens, tail_idx)->data;
    if (strcmp(tail->content, ")") != 0)
    {
        printf("ERROR: #lex function encountered an opening parenthesis \"(\" in the body\n");
        return;
    }

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
    printf("\n");
}

#endif