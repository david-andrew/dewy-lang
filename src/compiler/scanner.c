#ifndef SCANNER_C
#define SCANNER_C

#include <stdio.h>

#include "utilities.h"
#include "object.h"
#include "vector.h"
#include "set.h"
#include "metatoken.h"
#include "scanner.h"

/* 
TODO stuff

Possible EBNF/meta extensions
- literal hex characters instead of strings, e.g. #special_chars = 0x00 | 0x01 | 0x02 | ... | 0x10; //etc.
- flag for making a repeated section require at least 1 occurance. probably + added to end of a repeat
- flags for making strings case insensitive
- look into other conveniences from regex

Break out Token struct into a separate file along with meta_str(),

*/


//TODO->convert this to a stack for the scanner state
scanner_state scan_state = scan_root;

//scan for a single token
obj* scan(char** src)
{
    if (*src) //check if any string left to scan
    {
        obj* t;
        
        if (scan_state == scan_meta_rule || scan_state == scan_peek)
        {
            t = match_hashtag(src);                     if (t != NULL) return t;
            t = match_meta_char(src);                   if (t != NULL) return t;
            t = match_meta_string(src);                 if (t != NULL) return t;
            t = match_meta_hex_number(src);             if (t != NULL) return t;
            t = match_meta_escape(src);                 if (t != NULL) return t;
            t = match_meta_charsetchar(src);            if (t != NULL) return t;
            t = match_meta_anyset(src);                 if (t != NULL) return t;
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


obj* match_hashtag(char** src)
{
    if ((*src)[0] == '#' && is_alpha_char((*src)[1]))
    {
        //scan to end of identifier
        int i = 2;
        while (is_identifier_char((*src)[i])) { i++; }
        obj* t = new_token(hashtag, substr(*src, 0, i-1));
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

obj* match_meta_char(char** src)
{
    char quote; //store the type of quote, single (') or double (")
    if ((quote = (*src)[0]) == '\'' || quote == '"')
    {
        if ((*src)[1] == '\\')
        {
            uint32_t c = peek_unicode(src, 2);
            if (peek_unicode(src, 3) == quote)
            {
                obj* t = new_metatoken(meta_char, unicode_substr(*src, 1, 2));
                eat_utf8(src);
                eat_utf8(src);
                eat_utf8(src);
                eat_utf8(src);
                return t;
            }
        }
        else
        {

        }
        //check for escape characters
        //check for quote immediately after

        //check for normal characters
        //check for quote immediately after
    }
}

//TODO->need to update to handle escape characters as well as unicode inputs
obj* match_meta_string(char** src) 
{
    char quote; //store the type of quote, single (') or double (")
    if ((quote = (*src)[0]) == '\'' || (quote = (*src)[0]) == '"')
    {
        //scan for matching \' or \" to close the string, or null terminator, which indicates unclosed string
        int i = 1;
        while ((*src)[i] != 0 && (*src)[i] != quote) { i++; }
        if ((*src)[i] == quote) 
        {
            obj* t = new_token(meta_string, substr(*src, 1, i-1)); //ignore string quotes in string content
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

obj* match_meta_hex_number(char** src)
{
    //if the sequence starts with 0x or 0X followed by at least 1 hex digit
    if ((*src)[0] == '0' && ((*src)[1] == 'x' || (*src)[1] == 'X') && is_hex_digit((*src)[2]))
    {
        int i = 2;
        while(is_hex_digit((*src)[i++]));
        obj* t = new_token(meta_hex_number, substr((*src), 2, i-2)); //skip the 0x prefix, and stop before the end of the number
        *src += i - 1;
        return t;
    }
    return NULL;
}

// obj* match_meta_comma(char** src) 
// {
//     return *src[0] == ',' ? new_token(meta_comma, substr((*src)++, 0, 0)) : NULL;
// }

obj* match_meta_semicolon(char** src) 
{
    obj* t = *src[0] == ';' ? new_token(meta_semicolon, substr((*src)++, 0, 0)) : NULL;
    if (t != NULL) { scan_state = scan_root; } //update current scanner state for end of meta rule
    return t;
}

obj* match_meta_vertical_bar(char** src) 
{
    return *src[0] == '|' ? new_token(meta_vertical_bar, substr((*src)++, 0, 0)) : NULL;
}

// obj* match_meta_minus(char** src) 
// {
//     return *src[0] == '-' ? new_token(meta_minus, substr((*src)++, 0, 0)) : NULL;
// }

obj* match_meta_equals_sign(char** src) 
{
    return *src[0] == '=' ? new_token(meta_equals_sign, substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_left_parenthesis(char** src) 
{
    return *src[0] == '(' ? new_token(meta_left_parenthesis, substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_right_parenthesis(char** src) 
{
    obj* t = *src[0] == ')' ? new_token(meta_right_parenthesis, substr((*src)++, 0, 0)) : NULL;
    if (t != NULL && scan_state == scan_meta_func) { scan_state = scan_root; } //update current scanner state if the end of a meta_function was reached
    return t;
}

obj* match_meta_left_bracket(char** src) 
{
    return *src[0] == '{' ? new_token(meta_left_bracket, substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_right_bracket(char** src) 
{
    return *src[0] == '}' ? new_token(meta_right_bracket, substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_left_brace(char** src) 
{
    return *src[0] == '[' ? new_token(meta_left_brace, substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_right_brace(char** src) 
{
    return *src[0] == ']' ? new_token(meta_right_brace, substr((*src)++, 0, 0)) : NULL;
}

obj* match_whitespace(char** src) 
{
    return is_whitespace_char(*src[0]) ? new_token(whitespace, substr((*src)++, 0, 0)) : NULL;
}

obj* match_line_comment(char** src)
{
    if ((*src)[0] == '/' && (*src)[1] == '/') //match for single line comments
    {
        //scan through comment to either a newline or null terminator character
        int i = 2;
        while ((*src)[i] != 0 && (*src)[i] != '\n') { i++; }
        if ((*src)[i] == 0) { i -= 1; } //if null terminator, don't include in comment token
        obj* t = new_token(comment, substr(*src, 0, i));
        *src += i + 1;
        return t;
    }
    return NULL;
}

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
            obj* t = new_token(comment, substr(*src, 0, i));
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
//     return *src[0] == '(' || *src[0] == ')' ? new_token(meta_meta_parenthesis, substr((*src)++, 0, 0)) : NULL;
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
bool peek_char(char** src, char c)
{
    char* head = *src;       //pointer to the head of the src string
    char** head_ptr = &head; //new pointer to the pointer to the head of the string. so that peek() doesn't modify src
    obj* o;
    scanner_state saved_scan_state = scan_state; //save a copy of the current scanner state

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


#endif