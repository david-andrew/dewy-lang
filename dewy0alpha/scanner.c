#ifndef EBNF_C
#define EBNF_C

#include <stdio.h>

#include "obj.c"
#include "vect.c"

enum EBNF_state
{
    first_quote,
    second_quote,
    group,
    option,
    repeat,
    special,
};

typedef enum scanner_states 
{
    scan_root,
    scan_EBNF_rule,
    scan_meta_func,
    scan_peek,
} scanner_state;

//TODO->convert this to a stack for the scanner state
scanner_state scan_state = scan_root;

//possible token types
typedef enum token_types
{
    hashtag,
    EBNF_identifier,
    EBNF_single_quote_string,
    EBNF_double_quote_string,
    EBNF_comma,
    EBNF_semicolon,
    EBNF_vertical_bar,
    EBNF_minus,
    EBNF_equals_sign,
    EBNF_parenthesis,
    EBNF_bracket,
    EBNF_brace,
    whitespace,
    comment,
    meta_parenthesis,
} token_type;

//individual tokens that appear in an EBNF rule
typedef struct tokens
{
    token_type type;
    char* content;
} token;


//forward declare functions for ebnf parsing
obj* new_EBNF_token(token_type type, char* content);
obj* scan(char** src);
void EBNF_str(obj* o);
obj* match_hashtag(char** src);
obj* match_EBNF_single_quote_string(char** src);
obj* match_EBNF_double_quote_string(char** src);
obj* match_EBNF_comma(char** src);
obj* match_EBNF_semicolon(char** src);
obj* match_EBNF_vertical_bar(char** src);
obj* match_EBNF_minus(char** src);
obj* match_EBNF_equals_sign(char** src);
obj* match_EBNF_parenthesis(char** src);
obj* match_EBNF_bracket(char** src);
obj* match_EBNF_brace(char** src);

obj* match_whitespace(char** src);
obj* match_line_comment(char** src);
obj* match_block_comment(char** src);

obj* match_meta_parenthesis(char** src);

bool peek_char(char** src, char c);


// void remove_whitespace(vect* v);
// void remove_comments(vect* v);
void remove_token_type(vect* v, token_type type);


// obj* new_EBNF_token(EBNF_token* t)
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

void EBNF_str(obj* o)
{
    token* t = (token*)o->data;
    switch (t->type)
    {
        case hashtag: printf("hashtag"); break; //hashtag not allowed in this state
        case EBNF_identifier: printf("EBNF_identifier"); break;
        case EBNF_single_quote_string: printf("EBNF_single-string"); break;
        case EBNF_double_quote_string: printf("EBNF_double-string"); break;
        case EBNF_comma: printf("EBNF_comma"); break;
        case EBNF_semicolon: printf("EBNF_semicolon"); break;
        case EBNF_vertical_bar: printf("EBNF_vertical-bar"); break;
        case EBNF_minus: printf("EBNF_minus"); break;
        case EBNF_equals_sign: printf("EBNF_equals"); break;
        case EBNF_parenthesis: printf("EBNF_parenthesis"); break;
        case EBNF_bracket: printf("EBNF_bracket"); break;
        case EBNF_brace: printf("EBNF_brace"); break;
        case whitespace: printf("whitespace"); break;
        case comment: printf("comment"); break;
        case meta_parenthesis: printf("meta_parenthesis"); break;
    }
    printf(": `%s`", t->content);
}

//scan for a single token
obj* scan(char** src)
{
    if (*src) //check if any string left to scan
    {
        obj* t;
        
        if (scan_state == scan_EBNF_rule || scan_state == scan_peek)
        {
            // t = match_EBNF_identifier(src);             if (t != NULL) return t;
            t = match_hashtag(src);                     if (t != NULL) return t;
            t = match_EBNF_single_quote_string(src);    if (t != NULL) return t;
            t = match_EBNF_double_quote_string(src);    if (t != NULL) return t;
            t = match_EBNF_comma(src);                  if (t != NULL) return t;
            t = match_EBNF_semicolon(src);              if (t != NULL) return t;
            t = match_EBNF_vertical_bar(src);           if (t != NULL) return t;
            t = match_EBNF_minus(src);                  if (t != NULL) return t;
            t = match_EBNF_equals_sign(src);            if (t != NULL) return t;
            t = match_EBNF_parenthesis(src);            if (t != NULL) return t;
            t = match_EBNF_bracket(src);                if (t != NULL) return t;
            t = match_EBNF_brace(src);                  if (t != NULL) return t;
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
            t = match_meta_parenthesis(src);            if (t != NULL) return t;
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

        if (peek_char(src, '='))   //if the next char (allowing spaces and comments) is an equals, this is the definition of an ebnf rule
        {
            scan_state = scan_EBNF_rule;
        }
        else if ((*src)[0] == '(') //if the next char (no spaces or comments) is a parenthesis, this is a meta-function call
        {
            scan_state = scan_meta_func;
        }
        return t;
    }
    return NULL;
}

// obj* match_EBNF_identifier(char** src)
// {
//     if (is_alpha_char((*src)[0]))
//     {
//         //scan to end of identifier
//         int i = 1;
//         while (is_identifier_char((*src)[i])) { i++; }
//         obj* t = new_token(EBNF_identifier, substr(*src, 0, i-1));
//         *src += i;
//         return t;        
//     }
//     return NULL;
// }

obj* match_EBNF_single_quote_string(char** src) 
{
    if ((*src)[0] == '\'')
    {
        //scan for matching \' to close the string, or null terminator, which indicates unclosed string
        int i = 1;
        while ((*src)[i] != 0 && (*src)[i] != '\'') { i++; }
        if ((*src)[i] == '\'') 
        {
            obj* t = new_token(EBNF_single_quote_string, substr(*src, 0, i));
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

obj* match_EBNF_double_quote_string(char** src) 
{
        if ((*src)[0] == '"')
    {
        //scan for matching \' to close the string, or null terminator, which indicates unclosed string
        int i = 1;
        while ((*src)[i] != 0 && (*src)[i] != '"') { i++; }
        if ((*src)[i] == '"') 
        {
            obj* t = new_token(EBNF_double_quote_string, substr(*src, 0, i));
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

obj* match_EBNF_comma(char** src) 
{
    return *src[0] == ',' ? new_token(EBNF_comma, substr((*src)++, 0, 0)) : NULL;
}

obj* match_EBNF_semicolon(char** src) 
{
    obj* t = *src[0] == ';' ? new_token(EBNF_semicolon, substr((*src)++, 0, 0)) : NULL;
    if (t != NULL) { scan_state = scan_root; } //update current scanner state for end of ebnf rule
    return t;
}

obj* match_EBNF_vertical_bar(char** src) 
{
    return *src[0] == '|' ? new_token(EBNF_vertical_bar, substr((*src)++, 0, 0)) : NULL;
}

obj* match_EBNF_minus(char** src) 
{
    return *src[0] == '-' ? new_token(EBNF_minus, substr((*src)++, 0, 0)) : NULL;
}

obj* match_EBNF_equals_sign(char** src) 
{
    return *src[0] == '=' ? new_token(EBNF_equals_sign, substr((*src)++, 0, 0)) : NULL;
}

obj* match_EBNF_parenthesis(char** src) 
{
    return *src[0] == '(' || *src[0] == ')' ? new_token(EBNF_parenthesis, substr((*src)++, 0, 0)) : NULL;
}

obj* match_EBNF_bracket(char** src) 
{
    return *src[0] == '{' || *src[0] == '}' ? new_token(EBNF_bracket, substr((*src)++, 0, 0)) : NULL;
}

obj* match_EBNF_brace(char** src) 
{
    return *src[0] == '[' || *src[0] == ']' ? new_token(EBNF_brace, substr((*src)++, 0, 0)) : NULL;
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

//meta parenthesis follow a meta-identifier and indicate a meta-function call
obj* match_meta_parenthesis(char** src)
{
    return *src[0] == '(' || *src[0] == ')' ? new_token(meta_parenthesis, substr((*src)++, 0, 0)) : NULL;
}


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