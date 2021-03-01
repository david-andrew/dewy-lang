#ifndef METASCANNER_C
#define METASCANNER_C

#include <stdio.h>

#include "utilities.h"
#include "object.h"
#include "vector.h"
#include "metatoken.h"
#include "metascanner.h"



//inital state is root of source code
metascanner_state scan_state = scan_root;


/**
 * Scan for a single token based on the current `scan_state`.
 */
obj* scan(char** src)
{
    if (*src) //check if any string left to scan
    {
        obj* t;

        //TODO->reorder these to make sure everything gets hit correctly
        if (scan_state == scan_meta_rule || scan_state == scan_peek)
        {
            t = match_hashtag(src);                     if (t != NULL) return t;
            t = match_meta_char(src);                   if (t != NULL) return t;
            t = match_meta_string(src);                 if (t != NULL) return t;
            t = match_meta_hex_number(src);             if (t != NULL) return t;
            t = match_meta_dec_number(src);             if (t != NULL) return t;
            t = match_meta_anyset(src);                 if (t != NULL) return t;
            t = match_meta_escape(src);                 if (t != NULL) return t;
            t = match_meta_charsetchar(src);            if (t != NULL) return t;
            t = match_meta_epsilon(src);                if (t != NULL) return t;
            t = match_meta_ampersand(src);              if (t != NULL) return t;
            t = match_meta_star(src);                   if (t != NULL) return t;
            t = match_meta_plus(src);                   if (t != NULL) return t;
            t = match_meta_question_mark(src);          if (t != NULL) return t;
            t = match_meta_tilde(src);                  if (t != NULL) return t;
            t = match_meta_semicolon(src);              if (t != NULL) return t;
            t = match_meta_vertical_bar(src);           if (t != NULL) return t;
            t = match_meta_minus(src);                  if (t != NULL) return t;
            t = match_meta_equals_sign(src);            if (t != NULL) return t;
            t = match_meta_left_parenthesis(src);       if (t != NULL) return t;
            t = match_meta_right_parenthesis(src);      if (t != NULL) return t;
            t = match_meta_left_bracket(src);           if (t != NULL) return t;
            t = match_meta_right_bracket(src);          if (t != NULL) return t;
            t = match_meta_left_brace(src);             if (t != NULL) return t;
            t = match_meta_right_brace(src);            if (t != NULL) return t;
        }
        if (scan_state == scan_root || scan_state == scan_peek)
        {
            t = match_hashtag(src);                     if (t != NULL) return t;
    
            //TODO->match constructed rules here
        }
        if (scan_state == scan_meta_func || scan_state == scan_peek)
        {
            //TBD what exactly is allowed inside of a meta function call. for now we are only allowing meta-identifiers
            //potentially allow {} blocks, inside of which, normal dewy expressions can be called, just like string interpolation
            t = match_meta_left_parenthesis(src);       if (t != NULL) return t;
            t = match_meta_right_parenthesis(src);      if (t != NULL) return t;
            t = match_hashtag(src);                     if (t != NULL) return t;
        }
        
        //in all cases, match for whitespace or comments
        t = match_whitespace(src);                      if (t != NULL) return t;
        t = match_line_comment(src);                    if (t != NULL) return t;
        t = match_block_comment(src);                   if (t != NULL) return t;
    }

    printf("ERROR: no token was recognized on input:\n```\n%s\n```\n", *src);
    return NULL;
}


/**
 * Used as identifiers in meta syntax rules.
 * 
 * #hashtag = '#' [a-zA-Z] [a-zA-Z0-9~!@#$&_?]*;
 */
obj* match_hashtag(char** src)
{
    if ((*src)[0] == '#' && is_alpha_char((*src)[1]))
    {
        //scan to end of identifier
        int i = 2;
        while (is_identifier_char((*src)[i])) { i++; }
        obj* t = new_metatoken(hashtag, unicode_substr(*src, 0, i-1));
        *src += i;

        //if we were scanning root, change the state based on the type of character following the hashtag
        if (scan_state == scan_root)
        {
            if (peek_char(src, '=')) //if the next char (allowing spaces and comments) is an equals, this is the definition of a meta rule
            {
                scan_state = scan_meta_rule;
            }
            else if ((*src)[0] == '(') //if the next char (no spaces or comments) is a parenthesis, this is a meta-function call
            {
                scan_state = scan_meta_func;
            }
        }
        return t;
    }
    return NULL;
}


/**
 * A single character (or escaped character) enclosed in "" or ''
 * 
 * #char = '"' (\U - '"' | #escape) '"';
 * #char = "'" (\U - "'" | #escape) "'";
 */
obj* match_meta_char(char** src)
{
    char quote; //store the type of quote, single (') or double (")
    if ((quote = (*src)[0]) == '\'' || quote == '"')
    {
        if ((*src)[1] == '\\') //indicates an escape char
        {
            size_t delta;
            if (peek_unicode(src, 3, &delta) == quote)
            {
                obj* t = new_metatoken(meta_char, unicode_substr(*src, 1, 2));
                *src += delta;
                return t;
            }
        }
        else
        {
            size_t delta;
            if (peek_unicode(src, 2, &delta) == quote)
            {
                obj* t = new_metatoken(meta_char, unicode_substr(*src, 1, 1));
                *src += delta;
                return t;
            }
        }
    }
    return NULL;
}


/**
 * A string of 0, or 2 or more characters enclosed in '' or "".
 * Strings of length 1 are implicitly ignored by calling match_meta_char() first.
 * 
 * #string = '"' (\U - '"' | #escape)2* '"';
 * #string = "'" (\U - "'" | #escape)2* "'";
 */
obj* match_meta_string(char** src) 
{
    char quote; //store the type of quote, single (') or double (")
    if ((quote = (*src)[0]) == '\'' || quote == '"')
    {
        //scan for matching \' or \" to close the string, or null terminator, which indicates unclosed string
        //also continue scan if the character before closing quote is a '\\' which indicates escape char
        int i = 1;
        while ((*src)[i] != 0 && ((*src)[i] != quote || (*src)[i-1] == '\\')) { i++; }
        if ((*src)[i] == quote)
        {
            //since string needs to be in unicode, but we scanned chars, use utf8_substr to convert
            obj* t = new_metatoken(meta_string, utf8_substr(*src, 1, i-1)); //ignore string quotes in string content
            *src += i + 1;
            return t;
        }
        else 
        {
            printf("ERROR: reached the end of input while scanning 'meta string'\n");
        }
    }
    return NULL;
}


/**
 * Hex number literal.
 * 
 * #hex = '\\' [uUxX] [0-9a-fA-F]+;
 */
obj* match_meta_hex_number(char** src)
{
    //if the sequence starts with \u, \U, \x, or \X followed by at least 1 hex digit
    if ((*src)[0] == '\\' && is_hex_escape((*src)[1]) && is_hex_digit((*src)[2]))
    {
        //count out index of the last hex digit in the sequence
        int i = 2;
        while(is_hex_digit((*src)[i+1])) { i++; }

        //Because hex is only ascii, can take unicode_substr directly. Skip prefix of hex number
        obj* t = new_metatoken(meta_hex_number, unicode_substr((*src), 2, i));
        *src += i;
        return t;
    }
    return NULL;
}


/**
 * Decimal number literal. Used to indicate # of repetitions.
 * 
 * #number = [0-9]+;
 */
obj* match_meta_dec_number(char** src)
{
    //if the sequence starts with 0x or 0X followed by at least 1 hex digit
    if (is_dec_digit((*src)[0]))
    {
        //count out index of last decimal digit
        int i = 0;
        while(is_dec_digit((*src)[i+1])) { i++; }

        //Because decimal number is ascii only, can take unicode_substr directly
        obj* t = new_metatoken(meta_dec_number, unicode_substr((*src), 0, i));
        *src += i;
        return t;
    }
    return NULL;
}


/**
 * `\U`, `\u`, `\X`, or `\x` used to indicate any unicode character.
 * 
 * #anyset = '\\' [uUxX];
 */
obj* match_meta_anyset(char** src)
{
    if ((*src)[0] == '\\' && is_hex_escape((*src)[1]))
    {
        obj* t = new_metatoken(meta_anyset, unicode_substr((*src), 0, 1));
        *src += 2;
        return t;
    }
    return NULL;
}


/**
 * An escape character. Recognized escaped characters are \n \r \t \v \b \f \a. 
 * All others just put the second character literally. Common literals include \\ \' \" \[ \] \-
 * This function is mainly used for the body of charsets
 * 
 * #escape = '\\' \U;
 */
obj* match_meta_escape(char** src)
{
    if ((*src)[0] == '\\' && (*src)[1] != 0)
    {
        size_t delta;
        peek_unicode(src, 1, &delta);
        obj* t = new_metatoken(meta_escape, unicode_substr(*src, 0, 1));
        src += delta;
        return t;
    }
    return NULL;
}


/**
 * Match characters allowed in a set, i.e. any unicode excluding '-', '[', or ']', and whitespace
 * 
 * #charsetchar = \U - [\-\[\]] - #ws;
 */
obj* match_meta_charsetchar(char** src)
{
    size_t delta;
    if (is_charset_char(peek_unicode(src, 0, &delta)))
    {
        obj* t = new_metatoken(meta_charsetchar, unicode_substr(*src, 0, 1));
        *src += delta;
        return t;
    }
    return NULL;
}


/**
 * `ϵ` or `\e` indicates empty element, i.e. nullable
 * 
 * #eps = \x3f5 | '\\e';
 */
obj* match_meta_epsilon(char** src)
{
    size_t delta;
    if (peek_unicode(src, 0, NULL) == 0x3f5) //0x3f5 = 'ϵ'
    {
        obj* t = new_metatoken(meta_epsilon, unicode_substr(*src, 0, 1));
        *src += delta;
        return t;
    }
    else if ((*src)[0] == '\\' && (*src)[1] == 'e')
    {
        obj* t = new_metatoken(meta_epsilon, unicode_substr(*src, 0, 2));
        *src += 1;
        return t;
    }
    return NULL;
}


/**
 * Main usage of ampersand is as intersect operator
 * 
 * #intersect = #set #ws '&' #ws #set;
 */
obj* match_meta_ampersand(char** src)
{
    return *src[0] == '&' ? new_metatoken(meta_ampersand, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * 
 */
obj* match_meta_star(char** src)
{
    return *src[0] == '*' ? new_metatoken(meta_star, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * 
 */
obj* match_meta_plus(char** src)
{
    return *src[0] == '+' ? new_metatoken(meta_plus, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * 
 */
obj* match_meta_question_mark(char** src)
{
    return *src[0] == '?' ? new_metatoken(meta_question_mark, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * 
 */
obj* match_meta_tilde(char** src)
{
    return *src[0] == '~' ? new_metatoken(meta_tilde, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * 
 */
obj* match_meta_semicolon(char** src) 
{
    obj* t = *src[0] == ';' ? new_metatoken(meta_semicolon, unicode_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL) { scan_state = scan_root; } //update current scanner state for end of meta rule
    return t;
}

obj* match_meta_vertical_bar(char** src) 
{
    return *src[0] == '|' ? new_metatoken(meta_vertical_bar, unicode_substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_minus(char** src) 
{
    return *src[0] == '-' ? new_metatoken(meta_minus, unicode_substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_equals_sign(char** src) 
{
    return *src[0] == '=' ? new_metatoken(meta_equals_sign, unicode_substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_left_parenthesis(char** src) 
{
    return *src[0] == '(' ? new_metatoken(meta_left_parenthesis, unicode_substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_right_parenthesis(char** src) 
{
    obj* t = *src[0] == ')' ? new_metatoken(meta_right_parenthesis, unicode_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL && scan_state == scan_meta_func) { scan_state = scan_root; } //update current scanner state if the end of a meta_function was reached
    return t;
}

obj* match_meta_left_bracket(char** src) 
{
    return *src[0] == '{' ? new_metatoken(meta_left_bracket, unicode_substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_right_bracket(char** src) 
{
    return *src[0] == '}' ? new_metatoken(meta_right_bracket, unicode_substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_left_brace(char** src) 
{
    return *src[0] == '[' ? new_metatoken(meta_left_brace, unicode_substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_right_brace(char** src) 
{
    return *src[0] == ']' ? new_metatoken(meta_right_brace, unicode_substr((*src)++, 0, 0)) : NULL;
}

obj* match_whitespace(char** src) 
{
    return is_whitespace_char(*src[0]) ? new_metatoken(whitespace, unicode_substr((*src)++, 0, 0)) : NULL;
}

obj* match_line_comment(char** src)
{
    if ((*src)[0] == '/' && (*src)[1] == '/') //match for single line comments
    {
        //scan through comment to either a newline or null terminator character
        int i = 2;
        while ((*src)[i] != 0 && (*src)[i] != '\n') { i++; }
        if ((*src)[i] == 0) { i -= 1; } //if null terminator, don't include in comment token
        obj* t = new_metatoken(comment, utf8_substr(*src, 0, i));
        *src += i + 1;
        return t;
    }
    return NULL;
}

//TODO->need to redo b/c we are tracking instances of nested brackets.
//  basically, need to iterate through escape chars / normal chars 1 at a time, so that
//  if we see a `/{` we know that the `/` belongs to the `{` and not something before, e.g. a `\\`
obj* match_block_comment(char** src) 
{
    if ((*src)[0] == '/' && (*src)[1] == '{') //match for multiline comment
    {
        int stack = 1; //keep track of nesting of comments. should be 0 if all opened comments are closed
        int i = 2;
        while ((*src)[i] != 0 && stack != 0) //while not end of input, and not all comments have been closed
        {
            //search for opening and closing comment symbols
            if ((*src)[i] == '}' && (*src)[i+1] == '/') //closing comment
            {
                stack -= 1;
                i += 2;
            }
            else if ((*src)[i] == '/' && (*src)[i+1] == '{') //opening comment
            {
                stack += 1;
                i += 2;
            }
            else { i++; } //regular character skip
        }
        
        if (stack == 0) //check to make sure all nested comments were closed
        {
            //return token
            obj* t = new_metatoken(comment, utf8_substr(*src, 0, i));
            *src += i + 1;
            return t;
        }
        else //reached null terminator without closing all nested comments
        {
            printf("ERROR: reached the end of input while scanning 'multiline comment\n");
        }
    }
    return NULL;
}

//meta-meta parenthesis follow a meta-identifier and indicate a meta-function call
//could this potentially be combined with the regular meta parenthesis, that matches inside of meta rules?
// obj* match_meta_meta_parenthesis(char** src)
// {
//     return *src[0] == '(' || *src[0] == ')' ? new_metatoken(meta_meta_parenthesis, substr((*src)++, 0, 0)) : NULL;
// }

//remove all instances of a specific token type from a vector of tokens
void remove_token_type(vect* v, metatoken_type type)
{
    int i = 0;
    while (i < v->size)
    {
        metatoken* t = (metatoken*)vect_get(v, i)->data;
        t->type == type ? vect_delete(v, i) : i++;
    }
}

//check if the next non-whitespace and non-comment character matches the specified character
bool peek_char(char** src, uint32_t c)
{
    char* head = *src;       //pointer to the head of the src string
    char** head_ptr = &head; //new pointer to the pointer to the head of the string. so that peek() doesn't modify src
    obj* o;
    metascanner_state saved_scan_state = scan_state; //save a copy of the current scanner state

    scan_state = scan_peek;

    while ((*head_ptr)[0] != 0)
    {
        if ((o = scan(head_ptr)))
        {
            metatoken* t = (metatoken*)o->data;
            if (t->type != whitespace && t->type != comment)
            {
                scan_state = saved_scan_state;
                return t->content[0] == c;
            }
        }
    }
    return false;
}


//check if the next non-whitespace and non-comment character matches the specified character
bool peek_type(char** src, metatoken_type type)
{
    char* head = *src;       //pointer to the head of the src string
    char** head_ptr = &head; //new pointer to the pointer to the head of the string. so that peek() doesn't modify src
    obj* o;
    metascanner_state saved_scan_state = scan_state; //save a copy of the current scanner state

    scan_state = scan_peek;

    while ((*head_ptr)[0] != 0)
    {
        if ((o = scan(head_ptr)))
        {
            metatoken* t = (metatoken*)o->data;
            if (t->type != whitespace && t->type != comment)
            {
                scan_state = saved_scan_state;
                return t->type == type;
            }
        }
    }
    return false;
}



#endif