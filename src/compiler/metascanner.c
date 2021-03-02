#ifndef METASCANNER_C
#define METASCANNER_C

#include <stdio.h>

#include "utilities.h"
#include "object.h"
#include "vector.h"
#include "metatoken.h"
#include "metascanner.h"


//function pointer type for token scan functions
typedef obj* (*scan_fn)(char**);

//macro to get the length of each of the function arrays
#define len(A) sizeof(A) / sizeof(scan_fn)

//tokens to scan for before entering any meta syntax context
scan_fn root_funcs[] = {
    match_hashtag,
    match_whitespace,
    match_line_comment,
    match_block_comment,
};

//rules to scan while reading a meta rule
scan_fn rule_funcs[] = {
    match_whitespace,
    match_line_comment,
    match_block_comment,
    match_hashtag,
    match_meta_char,
    match_meta_single_quote,
    match_meta_double_quote,
    match_meta_hex_number,
    match_meta_dec_number,
    match_meta_anyset,
    match_meta_epsilon,
    match_meta_ampersand,
    match_meta_star,
    match_meta_plus,
    match_meta_question_mark,
    match_meta_tilde,
    match_meta_semicolon,
    match_meta_vertical_bar,
    match_meta_minus,
    match_meta_equals_sign,
    match_meta_left_parenthesis,
    match_meta_right_parenthesis,
    match_meta_left_bracket, 
    /*right bracket only matched inside charset_body*/
    match_meta_left_brace,
    match_meta_right_brace,
};

//rules to scan in the body of a charset
scan_fn charset_funcs[] = {
    match_whitespace,
    match_line_comment,
    match_block_comment,
    match_meta_hex_number,
    match_meta_escape,
    match_meta_minus,
    match_meta_charset_char,
    match_meta_right_bracket,
};

//rules for the body of a single quote '' string
scan_fn single_quote_string_funcs[] = {
    match_line_comment,
    match_block_comment,
    match_meta_escape,
    match_meta_single_quote,
    match_meta_single_quote_char,
};

//rules for the body of a double quote "" string
scan_fn double_quote_string_funcs[] = {
    match_line_comment,
    match_block_comment,
    match_meta_escape,
    match_meta_double_quote_char,
    match_meta_double_quote,
};

//rules to scan inside meta function calls
scan_fn metafunc_body_funcs[] = {
    //TBD what exactly is allowed inside of a meta function call. for now we are only allowing meta-identifiers
    //potentially allow {} blocks, inside of which, normal dewy expressions can be called, just like string interpolation    
    match_whitespace,
    match_line_comment,
    match_block_comment,
    match_meta_left_parenthesis,
    match_meta_right_parenthesis,
    match_hashtag,
};

//rules that are read (and ignored) while scanning for the next character
scan_fn scan_peek_funcs[] = {
    match_whitespace,
    match_line_comment,
    match_block_comment,
};



//Singleton stack for storing the state of the metascanner
vect* metascanner_state_stack = NULL;


/**
 * Initialize (if needed) and return the state stack singleton
 */
vect* get_metascanner_state_stack()
{
    if (!metascanner_state_stack)
    {
        metascanner_state_stack = new_vect();
        vect_push(metascanner_state_stack, new_uint((uint64_t)scan_root));
    }
    return metascanner_state_stack;
}


/**
 * Get the top state on the stack, without modifying the stack.
 */
metascanner_state peek_metascanner_state()
{
    vect* stack = get_metascanner_state_stack();
    obj* o = vect_peek(stack);
    return (metascanner_state)*(uint64_t*)o->data;
}


/**
 * Push a new state to the top of the stack.
 */
void push_metascanner_state(metascanner_state state)
{
    vect* stack = get_metascanner_state_stack();
    vect_push(stack, new_uint((uint64_t)state));
}


/**
 * Remove and return the top state on the stack.
 */
metascanner_state pop_metascanner_state()
{
    vect* stack = get_metascanner_state_stack();
    obj* o = vect_pop(stack);
    metascanner_state state = (metascanner_state)*(uint64_t*)o->data;
    obj_free(o);
    return state;
}


/**
 * Free the singleton metascanner state stack.
 */
void free_metascanner_state_stack()
{
    if (metascanner_state_stack) //ensure not NULL
    {
        vect_free(metascanner_state_stack);
        metascanner_state_stack = NULL;
    }
}


/**
 * Scan for a single token based on the state on top of the stack.
 */
obj* scan(char** src)
{
    if (*src) //check if any string left to scan
    {
        //for each possible state, scan for the corresponding tokens
        metascanner_state state = peek_metascanner_state();
        obj* t;

        if (state == scan_root)
            for (size_t i = 0; i < len(root_funcs); i++)
                if ((t = root_funcs[i](src)))
                    return t;
        
        if (state == scan_meta_rule)
            for (size_t i = 0; i < len(rule_funcs); i++)
                if ((t = rule_funcs[i](src))) 
                    return t;

        if (state == scan_charset_body)
            for (size_t i = 0; i < len(charset_funcs); i++)
                if ((t = charset_funcs[i](src))) 
                    return t;
                
        if (state == scan_single_quote_string_body)
            for (size_t i = 0; i < len(single_quote_string_funcs); i++)
                if ((t = single_quote_string_funcs[i](src)))
                    return t;
        
        if (state == scan_double_quote_string_body)
            for (size_t i = 0; i < len(double_quote_string_funcs); i++)
                if ((t = double_quote_string_funcs[i](src)))
                    return t;
       
        if (state == scan_metafunc_body)
            for (size_t i = 0; i < len(metafunc_body_funcs); i++)
                if ((t = metafunc_body_funcs[i](src)))
                    return t;

        //Scan until run out of whitespace and comments.
        //if all peek functions fail, that means the next char should be non-ignorable
        if (state == scan_peek)
        {
            for (size_t i = 0; i < len(scan_peek_funcs); i++)
                if ((t = scan_peek_funcs[i](src)))
                    return t;
            
            return NULL;
        }
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
        metascanner_state state = peek_metascanner_state();
        if (state == scan_root)
        {
            // uint32_t c = get_peek_char(src);
            if (get_peek_char(src) == '=') //if the next char (allowing spaces and comments) is an equals, this is the definition of a meta rule
            {
                push_metascanner_state(scan_meta_rule);
            }
            else if ((*src)[0] == '(') //if the next char (no spaces or comments) is a parenthesis, this is a meta-function call
            {
                push_metascanner_state(scan_metafunc_body);
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
 * Match a single quote character (initializing/ending a single quote string body)
 * Implicitely don't match for meta_char (i.e. length 1 string) by calling match_meta_char() first
 * 
 * #single_quote = '\'';
 */
obj* match_meta_single_quote(char** src)
{
    obj* t = *src[0] == '\'' ? new_metatoken(meta_single_quote, unicode_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL)
    {
        metascanner_state state = peek_metascanner_state();
        if (state == scan_meta_rule) { push_metascanner_state(scan_single_quote_string_body); }
        else if (state == scan_single_quote_string_body) { pop_metascanner_state(); }
        //else peek (or error?)
    }
    return t;
}


/**
 * Match single char contained in a single quote string.
 * Implicetly don't match for comments or escapes by matching those rules first.
 * 
 * #single_quote_char = \U - '\'';
 */
obj* match_meta_single_quote_char(char** src)
{
    //any single char except for '\''. Also implicitly exclude '\\' "//" "/{"
    if ((*src)[0] != 0 && (*src)[0] != '\'')
    {
        uint32_t c = eat_utf8(src);
        obj* t = new_metatoken(meta_single_quote_char, unicode_char_to_str(eat_utf8(src)));
        return t;
    }
    return NULL;
}



/**
 * Match a double quote character (initializing/ending a double quote string body)
 * 
 * #double_quote = '"';
 */
obj* match_meta_double_quote(char** src)
{
    obj* t = *src[0] == '"' ? new_metatoken(meta_double_quote, unicode_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL)
    {
        metascanner_state state = peek_metascanner_state();
        if (state == scan_meta_rule) { push_metascanner_state(scan_double_quote_string_body); }
        else if (state == scan_double_quote_string_body) { pop_metascanner_state(); }
        //else peek (or error?)
    }
    return t;
}


/**
 * Match single char contained in a double quote string.
 * Implicetly don't match for comments or escapes by matching those rules first.
 * 
 * #double_quote_char = \U - '"';
 */
obj* match_meta_double_quote_char(char** src)
{
    //any single char except for '"'. Also implicitly exclude '\\' "//" "/{"
    if ((*src)[0] != 0 && (*src)[0] != '"')
    {
        uint32_t c = eat_utf8(src);
        obj* t = new_metatoken(meta_double_quote_char, unicode_char_to_str(eat_utf8(src)));
        return t;
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
        *src += i + 1;
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
        *src += i + 1;
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
        obj* t = new_metatoken(meta_escape, unicode_char_to_str(eat_utf8(src)));
        return t;
    }
    return NULL;
}


/**
 * Match a character inside a charset.
 * Implicitly exclude escapes, hex and whitespace by scanning for them first.
 * 
 * #charsetchar = \U - [\-\[\]] - #wschar; 
 */
obj* match_meta_charset_char(char** src)
{
    //even though (*src)[0] is ascii while charset_char is unicode, is_charset_char works by excluding only certain ascii.
    return (is_charset_char((*src)[0])) ? new_metatoken(meta_charset_char, unicode_char_to_str(eat_utf8(src))) : NULL;
}


/**
 * `ϵ` or `\e` indicates empty element, i.e. nullable
 * 
 * #eps = \x3f5 | '\\e';
 */
obj* match_meta_epsilon(char** src)
{
    if (peek_unicode(src, 0, NULL) == 0x3f5) //0x3f5 = 'ϵ'
    {
        obj* t = new_metatoken(meta_epsilon, unicode_char_to_str(eat_utf8(src)));
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
 * Match for an ampersand '&' used to take the intersect of charsets.
 * 
 * #ampersand = '&';
 */
obj* match_meta_ampersand(char** src)
{
    return *src[0] == '&' ? new_metatoken(meta_ampersand, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * Match for a star '*' used to indicate 0 or more elements.
 * 
 * #star = '*';
 */
obj* match_meta_star(char** src)
{
    return *src[0] == '*' ? new_metatoken(meta_star, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * Match for a plus '+' used to indicate 1 or more elements.
 * 
 * #plus = '+';
 */
obj* match_meta_plus(char** src)
{
    return *src[0] == '+' ? new_metatoken(meta_plus, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * Match for a question mark '?' used to indicate an optional element.
 * 
 * #question_mark = '?';
 */
obj* match_meta_question_mark(char** src)
{
    return *src[0] == '?' ? new_metatoken(meta_question_mark, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * Match for a tiled '~' used to indicate the compliment of a charset.
 * 
 * #tiled = '~';
 */
obj* match_meta_tilde(char** src)
{
    return *src[0] == '~' ? new_metatoken(meta_tilde, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * Match for a semicolon ';' used to delimit the end of a meta rule;
 * 
 * #semicolon = ';';
 */
obj* match_meta_semicolon(char** src) 
{
    obj* t = *src[0] == ';' ? new_metatoken(meta_semicolon, unicode_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL && peek_metascanner_state() == scan_meta_rule) 
    {
        pop_metascanner_state();
        //peek_metascanner_state should == scan_root...
    }
    return t;
}


/**
 * Match for vertical bar '|' used to indicate charset union, or choice between left and right expression.
 * 
 * #vertical_bar = '|';
 */
obj* match_meta_vertical_bar(char** src) 
{
    return *src[0] == '|' ? new_metatoken(meta_vertical_bar, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * Match for minus '-' used to indicate charset difference (or potentially expression exclusions).
 * 
 * #minus = '-';
 */
obj* match_meta_minus(char** src) 
{
    return *src[0] == '-' ? new_metatoken(meta_minus, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * Match for equals sign '=' used to bind a meta rule to a hashtag identifier.
 * 
 * #equals_sign = '=';
 */
obj* match_meta_equals_sign(char** src) 
{
    return *src[0] == '=' ? new_metatoken(meta_equals_sign, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * Match for left parenthesis '(' used to group an expression, or start a meta function call.
 * 
 * #left_parenthesis = '(';
 */
obj* match_meta_left_parenthesis(char** src) 
{
    return *src[0] == '(' ? new_metatoken(meta_left_parenthesis, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * Match for right parenthesis ')' used to group an expression, or end a meta function call.
 * 
 * #right_parenthesis = ')';
 */
obj* match_meta_right_parenthesis(char** src) 
{
    obj* t = *src[0] == ')' ? new_metatoken(meta_right_parenthesis, unicode_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL && peek_metascanner_state() == scan_metafunc_body)
    { 
        pop_metascanner_state();  //return to previous context (scan_root) after meta function call closed
    }
    return t;
}


/**
 * Match for left bracket '{' used to create expression capture groups.
 * 
 * #left_bracket = '{';
 */
obj* match_meta_left_bracket(char** src) 
{
    return *src[0] == '{' ? new_metatoken(meta_left_bracket, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * Match for right bracket '}' used to close capture groups.
 * 
 * #right_bracket = '}';
 */
obj* match_meta_right_bracket(char** src) 
{
    return *src[0] == '}' ? new_metatoken(meta_right_bracket, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * Match for left brace '[' used to start a new charset literal.
 * 
 * #left_brace = '[';
 */
obj* match_meta_left_brace(char** src) 
{
    obj* t = *src[0] == '[' ? new_metatoken(meta_left_brace, unicode_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL && peek_metascanner_state() == scan_meta_rule)
    { 
        push_metascanner_state(scan_charset_body); //enter charset context for body
    }
    return t;
}


/**
 * Match for right brace ']' used to close a charset literal.
 * 
 * #right_brace = ']';
 */
obj* match_meta_right_brace(char** src) 
{
    obj* t = *src[0] == ']' ? new_metatoken(meta_right_brace, unicode_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL && peek_metascanner_state() == scan_charset_body)
    { 
        pop_metascanner_state(); //switch back to previous context (scan_meta_rule) after charset closed.
    }
    return t;
}


/**
 * Match ascii whitespace characters which will be ignored by the meta scanner/parser.
 * 
 * #wschars = [\x9-\xD\x20];
 */
obj* match_whitespace(char** src) 
{
    return is_whitespace_char(*src[0]) ? new_metatoken(whitespace, unicode_substr((*src)++, 0, 0)) : NULL;
}


/**
 * Match for a single line comment, which will be ignored by the meta scanner/parser
 * 
 * #line_comment = '//' \U* '\n';
 */
obj* match_line_comment(char** src)
{
    if ((*src)[0] == '/' && (*src)[1] == '/') //match for single line comments
    {
        //scan through comment to either a newline or null terminator character
        int i = 2;
        while ((*src)[i] != 0 && (*src)[i] != '\n') { i++; }
        // i -= 1; //remove newline or null terminator at the end
        // if ((*src)[i] == 0) { i -= 1; } //if null terminator, don't include in comment token
        obj* t = new_metatoken(comment, utf8_substr(*src, 0, i-1));
        *src += i + 1;
        return t;
    }
    return NULL;
}


/**
 * Match for a block comment, which will be ignored by the meta scanner/parser
 * Block comments allow for properly nested block comments, such that the comment
 * only closes onces a matching closing '}/' exists for every opening '/{'.
 * 
 * #block_comment = '/{' (#block_comment | \U)* '}/';
 */
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



/**
 * Remove the specified type of token from the vector of tokens.
 */
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


/**
 * Peek at the next character after whitespace and comments
 */
//check if the next non-whitespace and non-comment character matches the specified character
uint32_t get_peek_char(char** src)
{
    //separate pointers from src so peek doesn't modify it
    char* head = *src;
    char** head_ptr = &head;

    //set context to peek
    push_metascanner_state(scan_peek);

    //capture each scanned object since they need to be freed
    obj* o;

    //scan through until no more comment/whitespace tokens are returned
    while ((*head_ptr)[0] != 0 && (o = scan(head_ptr))) { obj_free(o); }

    //return to the previous context
    pop_metascanner_state();

    return peek_unicode(head_ptr, 0, NULL);
}





#endif