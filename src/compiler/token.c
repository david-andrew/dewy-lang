#ifndef TOKEN_C
#define TOKEN_C

#include <stdio.h>
#include <stdlib.h>

#include "types.h"
#include "token.h"




obj* new_token(token_type type, char* content)
{
    obj* T = malloc(sizeof(obj));
    T->type = Token_t;
    T->size = sizeof(token);
    token* t_ptr = malloc(sizeof(token));
    token t = {type, content};
    *t_ptr = t;
    T->data = (void*)t_ptr;
    return T;
}

//print out a string for each token type
void token_str(token* t)
{
    switch (t->type)
    {
        case hashtag: printf("hashtag"); break; //hashtag not allowed in this state
        case meta_string: printf("meta_string"); break;
        case meta_hex_number: printf("meta_hex_number"); break;
        case meta_comma: printf("meta_comma"); break;
        case meta_semicolon: printf("meta_semicolon"); break;
        case meta_vertical_bar: printf("meta_vertical_bar"); break;
        // case meta_minus: printf("meta_minus"); break;
        case meta_equals_sign: printf("meta_equals"); break;
        case meta_left_parenthesis: printf("meta_left_parenthesis"); break;
        case meta_right_parenthesis: printf("meta_right_parenthesis"); break;
        case meta_left_bracket: printf("meta_left_bracket"); break;
        case meta_right_bracket: printf("meta_right_bracket"); break;
        case meta_left_brace: printf("meta_left_brace"); break;
        case meta_right_brace: printf("meta_right_brace"); break;
        case whitespace: printf("whitespace"); break;
        case comment: printf("comment"); break;
    }
    printf(" `%s`", t->content);
}

void token_free(token* t)
{
    free(t->content);
    free(t);
}



#endif