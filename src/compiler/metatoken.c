#ifndef METATOKEN_C
#define METATOKEN_C

#include <stdio.h>
#include <stdlib.h>

#include "metatoken.h"
#include "utilities.h"


/**
 * Create a metatoken with the given `type` and `content`
 */
metatoken* new_metatoken(metatoken_type type, uint32_t* content)
{
    metatoken* t = malloc(sizeof(metatoken));
    *t = (metatoken){.type=type, .content=content};
    return t;
}

/**
 * Create an object holding a token of the specified `type` and `content`
 */
obj* new_metatoken_obj(metatoken_type type, uint32_t* content)
{
    metatoken* t = new_metatoken(type, content);
    obj* T = malloc(sizeof(obj));
    *T = (obj){.type=MetaToken_t, .data=t};
    return T;
}


/**
 * Create a copy of the metatoken
 */
metatoken* metatoken_copy(metatoken* t)
{
    return new_metatoken(t->type, clone_unicode(t->content));
}


/**
 * Print out a string for each token type.
 */
void metatoken_str(metatoken* t)
{
    #define printenum(A) case A: printf(#A); break;

    switch (t->type)
    {
        printenum(hashtag)
        printenum(meta_char)
        printenum(meta_single_quote)
        printenum(meta_double_quote)
        printenum(meta_hex_number)
        printenum(meta_dec_number)
        printenum(meta_escape)
        printenum(meta_charset_char)
        printenum(meta_anyset)
        printenum(meta_epsilon)
        printenum(meta_ampersand)
        printenum(meta_star)
        printenum(meta_plus)
        printenum(meta_question_mark)
        printenum(meta_tilde)
        printenum(meta_semicolon)
        printenum(meta_vertical_bar)
        printenum(meta_minus)
        printenum(meta_forward_slash)
        printenum(meta_greater_than)
        printenum(meta_less_than)
        printenum(meta_equals_sign)
        printenum(meta_left_parenthesis)
        printenum(meta_right_parenthesis)
        printenum(meta_left_bracket)
        printenum(meta_right_bracket)
        printenum(meta_left_brace)
        printenum(meta_right_brace)
        printenum(whitespace)
        printenum(comment)
    }
    printf("(`");
    uint32_t c;
    uint32_t* c_ptr = t->content;
    while ((c = *c_ptr++)) { put_unicode(c); }
    printf("`)\n");
}

void metatoken_free(metatoken* t)
{
    if (t != NULL)
    {
        free(t->content);
        free(t);
    }
}



#endif