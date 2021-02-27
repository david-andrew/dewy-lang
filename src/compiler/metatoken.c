#ifndef METATOKEN_C
#define METATOKEN_C

#include <stdio.h>
#include <stdlib.h>

#include "metatoken.h"

/**
 * 
 */
obj* new_metatoken(metatoken_type type, char* content)
{
    obj* T = malloc(sizeof(obj));
    T->type = MetaToken_t;
    T->size = sizeof(metatoken);
    metatoken* t_ptr = malloc(sizeof(metatoken));
    metatoken t = {type, content};
    *t_ptr = t;
    T->data = (void*)t_ptr;
    return T;
}

/**
 * Print out a string for each token type.
 */
void token_str(metatoken* t)
{
    switch (t->type)
    {
        case hashtag: printf("hashtag"); break; //hashtag not allowed in this state
        case meta_char: printf("meta_char"); break;
        case meta_string: printf("meta_string"); break;
        case meta_hex_number: printf("meta_hex_number"); break;
        case meta_escape: printf("meta_escape"); break;
        case meta_charsetchar: printf("meta_charsetchar"); break;
        case meta_anyset: printf("meta_anyset"); break;
        case meta_epsilon: printf("meta_epsilon"); break;
        case meta_ampersand: printf("meta_ampersand"); break;
        case meta_star: printf("meta_star"); break;
        case meta_plus: printf("meta_plus"); break;
        case meta_question_mark: printf("meta_question_mark"); break;
        case meta_tilde: printf("meta_tilde"); break;
        case meta_semicolon: printf("meta_semicolon"); break;
        case meta_vertical_bar: printf("meta_vertical_bar"); break;
        case meta_minus: printf("meta_minus"); break;
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

void token_free(metatoken* t)
{
    free(t->content);
    free(t);
}



#endif