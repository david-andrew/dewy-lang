#ifndef SCANNER_C
#define SCANNER_C

#include <stdio.h>

#include "object.c"
#include "vector.c"
#include "set.c"
#include "token.c"

/* 
TODO stuff

Possible EBNF/meta extensions
- literal hex characters instead of strings, e.g. #special_chars = 0x00 | 0x01 | 0x02 | ... | 0x10; //etc.
- flag for making a repeated section require at least 1 occurance. probably + added to end of a repeat
- flags for making strings case insensitive
- look into other conveniences from regex

Break out Token struct into a separate file along with meta_str(),

*/


typedef enum scanner_states 
{
    scan_root,
    scan_meta_rule,
    scan_meta_func,
    scan_peek,
} scanner_state;

//TODO->convert this to a stack for the scanner state
scanner_state scan_state = scan_root;


//forward declare functions for meta parsing
obj* scan(char** src);
obj* match_hashtag(char** src);
obj* match_meta_single_quote_string(char** src);
obj* match_meta_double_quote_string(char** src);
obj* match_meta_comma(char** src);
obj* match_meta_semicolon(char** src);
obj* match_meta_vertical_bar(char** src);
obj* match_meta_minus(char** src);
obj* match_meta_equals_sign(char** src);
obj* match_meta_parenthesis(char** src);
obj* match_meta_bracket(char** src);
obj* match_meta_brace(char** src);
obj* match_whitespace(char** src);
obj* match_line_comment(char** src);
obj* match_block_comment(char** src);
obj* match_meta_meta_parenthesis(char** src);
bool peek_char(char** src, char c);
// void remove_whitespace(vect* v);
// void remove_comments(vect* v);
void remove_token_type(vect* v, token_type type);


//scan for a single token
obj* scan(char** src)
{
    if (*src) //check if any string left to scan
    {
        obj* t;
        
        if (scan_state == scan_meta_rule || scan_state == scan_peek)
        {
            // t = match_meta_identifier(src);             if (t != NULL) return t;
            t = match_hashtag(src);                     if (t != NULL) return t;
            t = match_meta_single_quote_string(src);    if (t != NULL) return t;
            t = match_meta_double_quote_string(src);    if (t != NULL) return t;
            t = match_meta_comma(src);                  if (t != NULL) return t;
            t = match_meta_semicolon(src);              if (t != NULL) return t;
            t = match_meta_vertical_bar(src);           if (t != NULL) return t;
            t = match_meta_minus(src);                  if (t != NULL) return t;
            t = match_meta_equals_sign(src);            if (t != NULL) return t;
            t = match_meta_parenthesis(src);            if (t != NULL) return t;
            t = match_meta_bracket(src);                if (t != NULL) return t;
            t = match_meta_brace(src);                  if (t != NULL) return t;
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
            t = match_meta_meta_parenthesis(src);            if (t != NULL) return t;
            t = match_hashtag(src);                     if (t != NULL) return t;
        }
        
        //in all cases, match for whitespace or comments
        t = match_whitespace(src);                      if (t != NULL) return t;
        t = match_line_comment(src);                    if (t != NULL) return t;
        t = match_block_comment(src);                   if (t != NULL) return t;
    }

    printf("ERROR: no token was recognized on input `%s`\n", *src);
    return NULL;
}

// obj* peek()

obj* match_hashtag(char** src)
{
    if ((*src)[0] == '#' && is_alpha_char((*src)[1]))
    {
        //scan to end of identifier
        int i = 2;
        while (is_identifier_char((*src)[i])) { i++; }
        obj* t = new_token(hashtag, substr(*src, 0, i-1));
        *src += i;

        if (peek_char(src, '='))   //if the next char (allowing spaces and comments) is an equals, this is the definition of a meta rule
        {
            scan_state = scan_meta_rule;
        }
        else if ((*src)[0] == '(') //if the next char (no spaces or comments) is a parenthesis, this is a meta-function call
        {
            scan_state = scan_meta_func;
        }
        return t;
    }
    return NULL;
}

obj* match_meta_single_quote_string(char** src) 
{
    if ((*src)[0] == '\'')
    {
        //scan for matching \' to close the string, or null terminator, which indicates unclosed string
        int i = 1;
        while ((*src)[i] != 0 && (*src)[i] != '\'') { i++; }
        if ((*src)[i] == '\'') 
        {
            obj* t = new_token(meta_single_quote_string, substr(*src, 0, i));
            *src += i + 1;
            return t;
        }
        else 
        {
            printf("ERROR: reached the end of input while scanning 'single-quote string'\n");
        }
    }
    return NULL;
}

obj* match_meta_double_quote_string(char** src) 
{
        if ((*src)[0] == '"')
    {
        //scan for matching \' to close the string, or null terminator, which indicates unclosed string
        int i = 1;
        while ((*src)[i] != 0 && (*src)[i] != '"') { i++; }
        if ((*src)[i] == '"') 
        {
            obj* t = new_token(meta_double_quote_string, substr(*src, 0, i));
            *src += i + 1;
            return t;
        }
        else 
        {
            printf("ERROR: reached the end of input while scanning 'double-quote string'\n");
        }
    }
    return NULL;
}

obj* match_meta_comma(char** src) 
{
    return *src[0] == ',' ? new_token(meta_comma, substr((*src)++, 0, 0)) : NULL;
}

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

obj* match_meta_minus(char** src) 
{
    return *src[0] == '-' ? new_token(meta_minus, substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_equals_sign(char** src) 
{
    return *src[0] == '=' ? new_token(meta_equals_sign, substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_parenthesis(char** src) 
{
    return *src[0] == '(' || *src[0] == ')' ? new_token(meta_parenthesis, substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_bracket(char** src) 
{
    return *src[0] == '{' || *src[0] == '}' ? new_token(meta_bracket, substr((*src)++, 0, 0)) : NULL;
}

obj* match_meta_brace(char** src) 
{
    return *src[0] == '[' || *src[0] == ']' ? new_token(meta_brace, substr((*src)++, 0, 0)) : NULL;
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
obj* match_meta_meta_parenthesis(char** src)
{
    return *src[0] == '(' || *src[0] == ')' ? new_token(meta_meta_parenthesis, substr((*src)++, 0, 0)) : NULL;
}

//remove all instances of a specific token type from a vector of tokens
void remove_token_type(vect* v, token_type type)
{
    int i = 0;
    while (i < v->size)
    {
        token* t = (token*)vect_get(v, i)->data;
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
            token* t = (token*)o->data;
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