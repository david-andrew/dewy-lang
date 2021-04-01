#ifndef METATOKEN_C
#define METATOKEN_C

#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>

#include "metatoken.h"
#include "utilities.h"
#include "ustring.h"


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
    return new_metatoken(t->type, ustring_clone(t->content));
}


/**
 * Return the index of the next non whitespace/comment token
 */
int metatoken_get_next_real_token(vect* tokens, int i)
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
int metatoken_get_next_token_of_type(vect* tokens, metatoken_type type, int i)
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

bool metatoken_is_i_of_type(vect* tokens, int i, metatoken_type type)
{
    if (i < 0 || vect_size(tokens) < i){ return false; }
    metatoken* t = vect_get(tokens, i)->data;
    return t->type == type;
}


/**
 * Return the type of metatoken that matches the given left pair token.
 * Pairs are '' "" () {} [].
 */
metatoken_type metatoken_get_matching_pair_type(metatoken_type left)
{
    switch (left)
    {
        case meta_single_quote: return meta_single_quote;
        case meta_double_quote: return meta_double_quote;
        case meta_left_parenthesis: return meta_right_parenthesis;
        case meta_left_bracket: return meta_right_bracket;
        case meta_left_brace: return meta_right_brace;
    
        default:
            printf("ERROR: token type %u has no matching pair type", left);
            exit(1);
    }
}


/**
 * Return the uint32_t codepoint specified by the token, depending on its type.
 * Token must be either a meta_char, meta_escape, or meta_hex_number
 */
uint32_t metatoken_extract_char_from_token(metatoken* t)
{
    switch (t->type)
    {
        case meta_char: return *t->content;
        case meta_charset_char: return *t->content;
        case meta_escape: return escape_to_unicode(*t->content);
        case meta_hex_number:
        {
            uint32_t c = ustring_parse_hex(t->content);
            if (c > MAX_UNICODE_POINT)
            {
                printf("ERROR: codepoint of %"PRIu32" is larger than the maximum unicode codepoint %"PRIu32"\n", c, MAX_UNICODE_POINT);
                return 0;
            }
            return c;
        }
        default: 
            printf("ERROR: attempted to extract char from non-char token: ");
            metatoken_repr(t);
            printf("\n");
            exit(1);
    }
}


/**
 * Determine whether the given token type is a binary operator separator.
 */
bool metatoken_is_type_bin_op(metatoken_type type)
{
    switch (type)
    {
        case meta_minus:
        case meta_forward_slash:
        case meta_ampersand:
        case meta_vertical_bar:
        case meta_greater_than:
        case meta_less_than:
            return true;

        default:
            return false;
    }
}


/**
 * Print out a string for each token type
 */
void metatoken_str(metatoken* t)
{
    switch (t->type)
    {
        case hashtag:
        case meta_char:
        case meta_single_quote:
        case meta_double_quote:
        case meta_dec_number:
        case meta_charset_char:
        case meta_ampersand:
        case meta_period:
        case meta_star:
        case meta_plus:
        case meta_question_mark:
        case meta_tilde:
        case meta_semicolon:
        case meta_left_parenthesis:
        case meta_right_parenthesis:
        case meta_left_bracket:
        case meta_right_bracket:
        case meta_left_brace:
        case meta_right_brace:
        case whitespace:
        case comment:
            ustring_str(t->content); break;

        //special cases for printing
        case meta_escape: printf("\\"); ustring_str(t->content); break;
        case meta_epsilon: printf("ϵ"); break;
        case meta_anyset: printf("ξ"); break;
        case meta_hex_number: printf("\\x"); ustring_str(t->content); break;
        case meta_vertical_bar: printf(" | "); break;
        case meta_minus: printf("-"); break;
        case meta_forward_slash: printf(" / "); break;
        case meta_greater_than: printf(" > "); break;
        case meta_less_than: printf(" < "); break;
        case meta_equals_sign: printf(" = "); break;
    }
}


/**
 * Print out a string representation for each token type
 */
void metatoken_repr(metatoken* t)
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
        printenum(meta_period)
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
    ustring_str(t->content);
    printf("`)");
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