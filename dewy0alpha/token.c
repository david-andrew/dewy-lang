#ifndef TOKEN_C
#define TOKEN_C

#include <stdio.h>
#include "object.c"

//possible token types
typedef enum token_types
{
    hashtag,
    meta_identifier,
    meta_single_quote_string,
    meta_double_quote_string,
    meta_comma,
    meta_semicolon,
    meta_vertical_bar,
    meta_minus,
    meta_equals_sign,
    meta_parenthesis,
    meta_bracket,
    meta_brace,
    whitespace,
    comment,
    meta_meta_parenthesis,
} token_type;

//individual tokens that appear in a meta rule
typedef struct tokens
{
    token_type type;
    char* content;
} token;

obj* new_token(token_type type, char* content);
void token_str(token* t);


obj* new_token(token_type type, char* content)
{
    obj* T = malloc(sizeof(obj));
    T->type = 5;
    T->size = sizeof(token);
    token* t_ptr = malloc(sizeof(token));
    token t = {type, content};
    *t_ptr = t;
    T->data = (void*)t_ptr;
    return T;
}

//print out a string for each token type
//perhaps we could require that this passes a token* instead of an obj*
void token_str(token* t)//(obj* o)
{
    // token* t = (token*)o->data;
    switch (t->type)
    {
        case hashtag: printf("hashtag"); break; //hashtag not allowed in this state
        case meta_identifier: printf("meta_identifier"); break;
        case meta_single_quote_string: printf("meta_single-string"); break;
        case meta_double_quote_string: printf("meta_double-string"); break;
        case meta_comma: printf("meta_comma"); break;
        case meta_semicolon: printf("meta_semicolon"); break;
        case meta_vertical_bar: printf("meta_vertical-bar"); break;
        case meta_minus: printf("meta_minus"); break;
        case meta_equals_sign: printf("meta_equals"); break;
        case meta_parenthesis: printf("meta_parenthesis"); break;
        case meta_bracket: printf("meta_bracket"); break;
        case meta_brace: printf("meta_brace"); break;
        case whitespace: printf("whitespace"); break;
        case comment: printf("comment"); break;
        case meta_meta_parenthesis: printf("meta_meta_parenthesis"); break;
    }
    printf(": `%s`", t->content);
}



#endif