#ifndef COMPILE_TOOLS_C
#define COMPILE_TOOLS_C

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


//possible token types
typedef enum EBNF_token_types
{
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
    EBNF_whitespace,
    EBNF_comment,
} EBNF_token_type;

//individual tokens that appear in an EBNF rule
typedef struct EBNF_tokens
{
    EBNF_token_type type;
    char* content;
} EBNF_token;


//forward declare functions for ebnf parsing
obj* EBNF_scan(char** src);
void EBNF_str(obj* o);
obj* EBNF_match_identifier(char** src);
obj* EBNF_match_single_quote_string(char** src);
obj* EBNF_match_double_quote_string(char** src);
obj* EBNF_match_comma(char** src);
obj* EBNF_match_semicolon(char** src);
obj* EBNF_match_vertical_bar(char** src);
obj* EBNF_match_minus(char** src);
obj* EBNF_match_equals_sign(char** src);
obj* EBNF_match_parenthesis(char** src);
obj* EBNF_match_bracket(char** src);
obj* EBNF_match_brace(char** src);
obj* EBNF_match_whitespace(char** src);
obj* EBNF_match_comment(char** src);


// obj* new_EBNF_token(EBNF_token* t)
obj* new_EBNF_token(EBNF_token_type type, char* content)
{
    obj* T = malloc(sizeof(obj));
    T->type = 5;
    T->size = sizeof(EBNF_token);
    EBNF_token* t_ptr = malloc(sizeof(EBNF_token));
    EBNF_token t = {type, content};
    *t_ptr = t;
    T->data = (void*)t_ptr;
    return T;
}

void EBNF_str(obj* o)
{
    EBNF_token* t = (EBNF_token*)o->data;
    printf("EBNF_");
    switch (t->type)
    {
        case EBNF_identifier: printf("identifier"); break;
        case EBNF_single_quote_string: printf("single-string"); break;
        case EBNF_double_quote_string: printf("double-string"); break;
        case EBNF_comma: printf("comma"); break;
        case EBNF_semicolon: printf("semicolon"); break;
        case EBNF_vertical_bar: printf("vertical-bar"); break;
        case EBNF_minus: printf("minus"); break;
        case EBNF_equals_sign: printf("equals"); break;
        case EBNF_parenthesis: printf("parenthesis"); break;
        case EBNF_bracket: printf("bracket"); break;
        case EBNF_brace: printf("brace"); break;
        case EBNF_whitespace: printf("whitespace"); break;
        case EBNF_comment: printf("comment"); break;
    }
    printf(": `%s`", t->content);
}

//scan for a single token
obj* EBNF_scan(char** src)
{
    if (*src) //check if any string left to scan
    {
        obj* t;
        t = EBNF_match_identifier(src);             if (t != NULL) return t;
        t = EBNF_match_single_quote_string(src);    if (t != NULL) return t;
        t = EBNF_match_double_quote_string(src);    if (t != NULL) return t;
        t = EBNF_match_comma(src);                  if (t != NULL) return t;
        t = EBNF_match_semicolon(src);              if (t != NULL) return t;
        t = EBNF_match_vertical_bar(src);           if (t != NULL) return t;
        t = EBNF_match_minus(src);                  if (t != NULL) return t;
        t = EBNF_match_equals_sign(src);            if (t != NULL) return t;
        t = EBNF_match_parenthesis(src);            if (t != NULL) return t;
        t = EBNF_match_bracket(src);                if (t != NULL) return t;
        t = EBNF_match_brace(src);                  if (t != NULL) return t;
        t = EBNF_match_whitespace(src);             if (t != NULL) return t;
        t = EBNF_match_comment(src);                if (t != NULL) return t;
    }

    printf("ERROR: no token was recognized on input `%s`\n", *src);
    return NULL;
}

obj* EBNF_match_identifier(char** src)
{
    if ((*src)[0] == '#' && is_alpha_char((*src)[1]))
    {
        //scan to end of identifier
        int i = 2;
        while (is_identifier_char((*src)[i])) { i++; }
        obj* t = new_EBNF_token(EBNF_identifier, substr(*src, 0, i-1));
        *src += i;
        return t;        
    }
    return NULL;
}

obj* EBNF_match_single_quote_string(char** src) 
{
    if ((*src)[0] == '\'')
    {
        //scan for matching \' to close the string, or null terminator, which indicates unclosed string
        int i = 1;
        while ((*src)[i] != 0 && (*src)[i] != '\'') { i++; }
        if ((*src)[i] == '\'') 
        {
            obj* t = new_EBNF_token(EBNF_single_quote_string, substr(*src, 0, i));
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

obj* EBNF_match_double_quote_string(char** src) 
{
        if ((*src)[0] == '"')
    {
        //scan for matching \' to close the string, or null terminator, which indicates unclosed string
        int i = 1;
        while ((*src)[i] != 0 && (*src)[i] != '"') { i++; }
        if ((*src)[i] == '"') 
        {
            obj* t = new_EBNF_token(EBNF_double_quote_string, substr(*src, 0, i));
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

obj* EBNF_match_comma(char** src) 
{
    return *src[0] == ',' ? new_EBNF_token(EBNF_comma, substr((*src)++, 0, 0)) : NULL;
}

obj* EBNF_match_semicolon(char** src) 
{
    return *src[0] == ';' ? new_EBNF_token(EBNF_semicolon, substr((*src)++, 0, 0)) : NULL;
}

obj* EBNF_match_vertical_bar(char** src) 
{
    return *src[0] == '|' ? new_EBNF_token(EBNF_vertical_bar, substr((*src)++, 0, 0)) : NULL;
}

obj* EBNF_match_minus(char** src) 
{
    return *src[0] == '-' ? new_EBNF_token(EBNF_minus, substr((*src)++, 0, 0)) : NULL;
}

obj* EBNF_match_equals_sign(char** src) 
{
    return *src[0] == '=' ? new_EBNF_token(EBNF_equals_sign, substr((*src)++, 0, 0)) : NULL;
}

obj* EBNF_match_parenthesis(char** src) 
{
    return *src[0] == '(' || *src[0] == ')' ? new_EBNF_token(EBNF_parenthesis, substr((*src)++, 0, 0)) : NULL;
}

obj* EBNF_match_bracket(char** src) 
{
    return *src[0] == '{' || *src[0] == '}' ? new_EBNF_token(EBNF_bracket, substr((*src)++, 0, 0)) : NULL;
}

obj* EBNF_match_brace(char** src) 
{
    return *src[0] == '[' || *src[0] == ']' ? new_EBNF_token(EBNF_brace, substr((*src)++, 0, 0)) : NULL;
}

obj* EBNF_match_whitespace(char** src) 
{
    return is_whitespace_char(*src[0]) ? new_EBNF_token(EBNF_whitespace, substr((*src)++, 0, 0)) : NULL;
}

obj* EBNF_match_comment(char** src) 
{
    return NULL;
}

void remove_whitespace(vect* v)
{
    int i = 0;
    while (i < v->size)
    {
        EBNF_token* t = (EBNF_token*)vect_get(v, i)->data;
        if (t->type == EBNF_whitespace) 
        {
            vect_delete(v, i);
        }
        else
        {
            i++;
        }
    }
}

char* remove_comments(char* source)
{    
    //For now we assume that any instance of // or /{ }/ is a comment, regardless of context.
    //in the future, we need to be able to distinguish // inside of strings and other contexts
    printf("Removing comments from source string...\n");

    size_t length = strlen(source);
    char* head = source;
    char* processed = malloc(length * sizeof(char));     //potentially entire space used
    size_t copied = 0;
    
    do
    {
        //check if start of line comment, and if so skip to end of line
        if (source - head + 1 < length && *source == '/' && *(source + 1) ==  '/')
        {
            while(*++source != '\n' && *source != 0); //scan until the line break (or end of string)
            source--;   //don't eat the newline
            continue;
        }

        // //check if start of block comment, and if so, skip to end of block (keeping track of internal block comments)
        // if (source - head + 1 < length && *source == '/' && *(source + 1) == '{')
        // {
        //     int stack = 1;  //monitor internal opening and closing blocks.
        //     while (stack != 0)
        //     {

        //     }
        // }

        // putchar(*source);
        // printf("%d ", *source);
        processed[copied++] = *source; //copy the current character
    }
    while (*source++);

    // while(*processed++) putchar(*processed);
    processed[copied] = 0; //add final null-terminator to copied string
    free(head);            //release the no longer used version
    return processed;
}

#endif