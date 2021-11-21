#ifndef METASCANNER_C
#define METASCANNER_C

#include <stdio.h>
#include <stdlib.h>

#include "metascanner.h"
#include "metatoken.h"
#include "object.h"
#include "ustring.h"
#include "utilities.h"
#include "vector.h"

// function pointer type for token scan functions
typedef obj* (*metascan_fn)(char**);

// tokens to scan for before entering any meta syntax context
metascan_fn root_funcs[] = {
    match_hashtag,
    match_whitespace,
    match_line_comment,
    match_block_comment,
};

// rules to scan while reading a meta rule
metascan_fn rule_funcs[] = {
    match_whitespace,
    match_line_comment,
    match_block_comment,
    match_meta_epsilon,
    match_hashtag,
    match_meta_single_quote,
    match_meta_double_quote,
    match_meta_hex_number,
    match_meta_dec_number,
    match_meta_anyset,
    match_meta_dollar,
    match_meta_ampersand,
    match_meta_period,
    match_meta_star,
    match_meta_plus,
    match_meta_question_mark,
    match_meta_tilde,
    match_meta_semicolon,
    match_meta_vertical_bar,
    match_meta_minus,
    match_meta_forward_slash,
    match_meta_greater_than,
    match_meta_less_than,
    match_meta_equals_sign,
    match_meta_left_parenthesis,
    match_meta_right_parenthesis,
    match_meta_left_bracket,
    match_meta_right_bracket,
    match_meta_left_brace,
    /*right brace only matched inside charset_body*/
};

// rules to scan in the body of a charset
metascan_fn charset_funcs[] = {
    match_whitespace,  match_line_comment, match_block_comment,     match_meta_hex_number,
    match_meta_escape, match_meta_minus,   match_meta_charset_char, match_meta_right_brace,
};

// rules for the body of a single quote '' string
metascan_fn single_quote_string_funcs[] = {
    match_line_comment, match_block_comment,     match_meta_hex_number,
    match_meta_escape,  match_meta_single_quote, match_meta_single_quote_char,
};

// rules for the body of a double quote "" string
metascan_fn double_quote_string_funcs[] = {
    match_line_comment, match_block_comment,          match_meta_hex_number,
    match_meta_escape,  match_meta_double_quote_char, match_meta_double_quote,
};

// rules for the body of a caseless {} string
metascan_fn caseless_string_funcs[] = {
    match_line_comment, match_block_comment,      match_meta_hex_number,
    match_meta_escape,  match_meta_caseless_char, match_meta_right_bracket,
};

// rules to scan inside meta function calls
metascan_fn metafunc_body_funcs[] = {
    // TBD what exactly is allowed inside of a meta function call. for now we are only allowing meta-identifiers
    // potentially allow {} blocks, inside of which, normal dewy expressions can be called, just like string
    // interpolation
    match_whitespace,
    match_line_comment,
    match_block_comment,
    match_meta_left_parenthesis,
    match_meta_right_parenthesis,
    match_hashtag,
};

// rules that are read (and ignored) while scanning for the next character
metascan_fn scan_peek_funcs[] = {
    match_whitespace,
    match_line_comment,
    match_block_comment,
};

// Singleton stack for storing the state of the metascanner
vect* metascanner_state_stack = NULL;

/**
 * Initialize any internal objects used in the metascanner
 */
void allocate_metascanner()
{
    metascanner_state_stack = new_vect();
    vect_push(metascanner_state_stack, new_uint_obj((uint64_t)scan_root));
}

/**
 * Free any initialized objects used in the metascanner
 */
void release_metascanner()
{
    if (metascanner_state_stack) // ensure not NULL
    {
        vect_free(metascanner_state_stack);
        metascanner_state_stack = NULL;
    }
}

/**
 * Get the top state on the stack, without modifying the stack.
 */
metascanner_state peek_metascanner_state()
{
    obj* o = vect_peek(metascanner_state_stack);
    return (metascanner_state) * (uint64_t*)o->data;
}

/**
 * Push a new state to the top of the stack.
 */
void push_metascanner_state(metascanner_state state)
{
    vect_push(metascanner_state_stack, new_uint_obj((uint64_t)state));
}

/**
 * Remove and return the top state on the stack.
 */
metascanner_state pop_metascanner_state()
{
    obj* o = vect_pop(metascanner_state_stack);
    metascanner_state state = (metascanner_state) * (uint64_t*)o->data;
    obj_free(o);
    return state;
}

bool is_identifier_char(char c)
{
    // valid identifier characters are
    // ABCDEFGHIJKLMNOPQRSTUVWXYZ
    // abcdefghijklmnopqrstuvwxyz
    // 1234567890
    //~!@#$&_?
    return is_alphanum_char(c) || is_identifier_symbol_char(c);
}

bool is_hashtag_identifier_char(char c) { return is_alphanum_char(c) || c == '_'; }

bool is_identifier_symbol_char(char c)
{
    return c == '~' || c == '!' || c == '@' || c == '#' || c == '$' || c == '&' || c == '_' || c == '?';
}

bool is_alpha_char(char c) { return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z'); }

bool is_dec_digit(char c) { return c >= '0' && c <= '9'; }

bool is_alphanum_char(char c) { return is_alpha_char(c) || is_dec_digit(c); }

bool is_upper_hex_letter(char c) { return c >= 'A' && c <= 'F'; }

bool is_lower_hex_letter(char c) { return c >= 'a' && c <= 'f'; }

// returns true if character is a hexidecimal digit (both uppercase or lowercase valid)
bool is_hex_digit(char c) { return is_dec_digit(c) || is_upper_hex_letter(c) || is_lower_hex_letter(c); }

/**
 * Determines if the character is the escape char for starting hex numbers
 * Hex numbers can be \x#, \X#, \u#, or \U#.
 */
bool is_hex_escape(char c) { return c == 'x' || c == 'X' || c == 'u' || c == 'U'; }

bool is_whitespace_char(char c)
{
    // whitespace includes tab (0x09), line feed (0x0A), line tab (0x0B), form feed (0x0C), carriage return (0x0D), and
    // space (0x20)
    return c == 0x09 || c == 0x0A || c == 0x0B || c == 0x0C || c == 0x0D || c == 0x20;
}

/**
 * Determine if the character is a legal charset character
 * #charsetchar = \U - [\-\[\]] - #ws;
 */
bool is_charset_char(uint32_t c)
{
    return !(c == 0) && !is_whitespace_char((char)c) && !(c == '-' || c == '[' || c == ']');
}

/**
 * Scan for a single token based on the state on top of the stack.
 */
obj* scan(char** src)
{
    if (*src) // check if any string left to scan
    {
        // for each possible state, scan for the corresponding tokens
        metascanner_state state = peek_metascanner_state();
        obj* t;

// macro to get the length of each of the function arrays
#define len(A) sizeof(A) / sizeof(metascan_fn)
#define scan_for(scan_state, funcs)                                                                                    \
    if (state == scan_state)                                                                                           \
        for (size_t i = 0; i < len(funcs); i++)                                                                        \
            if ((t = funcs[i](src))) return t;

        scan_for(scan_root, root_funcs);
        scan_for(scan_meta_rule, rule_funcs);
        scan_for(scan_charset_body, charset_funcs);
        scan_for(scan_single_quote_string_body, single_quote_string_funcs);
        scan_for(scan_double_quote_string_body, double_quote_string_funcs);
        scan_for(scan_caseless_string_body, caseless_string_funcs);
        scan_for(scan_metafunc_body, metafunc_body_funcs);

        // if (state == scan_root)
        //     for (size_t i = 0; i < len(root_funcs); i++)
        //         if ((t = root_funcs[i](src)))
        //             return t;

        // if (state == scan_meta_rule)
        //     for (size_t i = 0; i < len(rule_funcs); i++)
        //         if ((t = rule_funcs[i](src)))
        //             return t;

        // if (state == scan_charset_body)
        //     for (size_t i = 0; i < len(charset_funcs); i++)
        //         if ((t = charset_funcs[i](src)))
        //             return t;

        // if (state == scan_single_quote_string_body)
        //     for (size_t i = 0; i < len(single_quote_string_funcs); i++)
        //         if ((t = single_quote_string_funcs[i](src)))
        //             return t;

        // if (state == scan_double_quote_string_body)
        //     for (size_t i = 0; i < len(double_quote_string_funcs); i++)
        //         if ((t = double_quote_string_funcs[i](src)))
        //             return t;

        // if (state == scan_caseless_string_body)
        //     for (size_t i = 0; i < len(caseless_string_funcs); i++)
        //         if ((t = caseless_string_funcs[i](src)))
        //             return t;

        // if (state == scan_metafunc_body)
        //     for (size_t i = 0; i < len(metafunc_body_funcs); i++)
        //         if ((t = metafunc_body_funcs[i](src)))
        //             return t;

        // Scan until run out of whitespace and comments.
        // if all peek functions fail, that means the next char should be non-ignorable
        if (state == scan_peek)
        {
            for (size_t i = 0; i < len(scan_peek_funcs); i++)
                if ((t = scan_peek_funcs[i](src))) return t;

            return NULL;
        }
    }

    printf("ERROR: no token was recognized on input:\n```\n%s\n```\n", *src);
    exit(1);
    return NULL;
}

/**
 * Used as identifiers in meta syntax rules.
 *
 * #hashtag = '#' [a-zA-Z] [a-zA-Z0-9_]*;
 */
obj* match_hashtag(char** src)
{
    if ((*src)[0] == '#' && is_alpha_char((*src)[1]))
    {
        // scan to end of identifier
        int i = 2;
        while (is_hashtag_identifier_char((*src)[i])) { i++; }
        obj* t = new_metatoken_obj(hashtag, ustring_charstar_substr(*src, 0, i - 1));
        *src += i;

        // if we were scanning root, change the state based on the type of character following the hashtag
        metascanner_state state = peek_metascanner_state();
        if (state == scan_root)
        {
            // uint32_t c = get_peek_char(src);
            if (get_peek_char(src) == '=') // if the next char (allowing spaces and comments) is an equals, this is the
                                           // definition of a meta rule
            {
                push_metascanner_state(scan_meta_rule);
            }
            else if ((*src)[0] ==
                     '(') // if the next char (no spaces or comments) is a parenthesis, this is a meta-function call
            {
                push_metascanner_state(scan_metafunc_body);
            }
        }
        return t;
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
    obj* t = *src[0] == '\'' ? new_metatoken_obj(meta_single_quote, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL)
    {
        metascanner_state state = peek_metascanner_state();
        if (state == scan_meta_rule) { push_metascanner_state(scan_single_quote_string_body); }
        else if (state == scan_single_quote_string_body)
        {
            pop_metascanner_state();
        }
        // else peek (or error?)
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
    // any single char except for '\''. Also implicitly exclude '\\' "//" "/{"
    if ((*src)[0] != 0 && (*src)[0] != '\'')
    {
        obj* t = new_metatoken_obj(meta_char, ustring_from_unicode(eat_utf8(src)));
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
    obj* t = *src[0] == '"' ? new_metatoken_obj(meta_double_quote, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL)
    {
        metascanner_state state = peek_metascanner_state();
        if (state == scan_meta_rule) { push_metascanner_state(scan_double_quote_string_body); }
        else if (state == scan_double_quote_string_body)
        {
            pop_metascanner_state();
        }
        // else peek (or error?)
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
    // any single char except for '"'. Also implicitly exclude '\\' "//" "/{"
    if ((*src)[0] != 0 && (*src)[0] != '"')
    {
        obj* t = new_metatoken_obj(meta_char, ustring_from_unicode(eat_utf8(src)));
        return t;
    }
    return NULL;
}

/**
 * Match a single char contained in a caseless string.
 * Implicitely don't match for comments or escapes by matching those rules first.
 *
 * #caseless_char = \U - [{}];
 */
obj* match_meta_caseless_char(char** src)
{
    // any single char except for [{}]. Also implicitly exclude '\\' "//" "/{"
    if ((*src)[0] != 0 && (*src)[0] != '{' && (*src)[0] != '}')
    {
        obj* t = new_metatoken_obj(meta_char, ustring_from_unicode(eat_utf8(src)));
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
    // if the sequence starts with \u, \U, \x, or \X followed by at least 1 hex digit
    if ((*src)[0] == '\\' && is_hex_escape((*src)[1]) && is_hex_digit((*src)[2]))
    {
        // count out index of the last hex digit in the sequence
        int i = 2;
        while (is_hex_digit((*src)[i + 1])) { i++; }

        // Because hex is only ascii, can take ustring_charstar_substr directly. Skip prefix of hex number
        obj* t = new_metatoken_obj(meta_hex_number, ustring_charstar_substr((*src), 2, i));
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
    // if the sequence starts with 0x or 0X followed by at least 1 hex digit
    if (is_dec_digit((*src)[0]))
    {
        // count out index of last decimal digit
        int i = 0;
        while (is_dec_digit((*src)[i + 1])) { i++; }

        // Because decimal number is ascii only, can take ustring_charstar_substr directly
        obj* t = new_metatoken_obj(meta_dec_number, ustring_charstar_substr((*src), 0, i));
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
    uint32_t peek = peek_unicode(src, 0, NULL);
    if (peek == 'U' || peek == 'V' || peek == 0x3be) // 0x3be = 'ξ'
    {

        obj* t = new_metatoken_obj(meta_anyset, ustring_from_unicode(eat_utf8(src)));
        return t;
    }
    else if ((*src)[0] == '\\' && is_hex_escape((*src)[1]))
    {
        obj* t = new_metatoken_obj(meta_anyset, ustring_charstar_substr((*src), 0, 1));
        *src += 2;
        return t;
    }
    return NULL;
}

/**
 * #$ is a special character that matches for the end of the input.
 *
 * #dollar = '#$';
 */
obj* match_meta_dollar(char** src)
{
    if ((*src)[0] == '#' && (*src)[1] == '$')
    {
        obj* t = new_metatoken_obj(meta_dollar, ustring_charstar_substr((*src), 0, 1));
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
        (*src)++; // skip escape backslash
        obj* t = new_metatoken_obj(meta_escape, ustring_from_unicode(eat_utf8(src)));
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
    // even though (*src)[0] is ascii while charset_char is unicode, is_charset_char works by excluding only certain
    // ascii.
    return (is_charset_char((*src)[0])) ? new_metatoken_obj(meta_charset_char, ustring_from_unicode(eat_utf8(src)))
                                        : NULL;
}

/**
 * `ϵ` or `\e` indicates empty element, i.e. nullable
 *
 * #eps = \x3f5 | '\\e' | "''" | '""';
 */
obj* match_meta_epsilon(char** src)
{
    if (peek_unicode(src, 0, NULL) == 0x3f5) // 0x3f5 = 'ϵ'
    {
        obj* t = new_metatoken_obj(meta_epsilon, ustring_from_unicode(eat_utf8(src)));
        return t;
    }
    else if (((*src)[0] == '\\' && (*src)[1] == 'e') || ((*src)[0] == '"' && (*src)[1] == '"') ||
             ((*src)[0] == '\'' && (*src)[1] == '\'') || ((*src)[0] == '{' && (*src)[1] == '}'))
    {
        obj* t = new_metatoken_obj(meta_epsilon, ustring_charstar_substr(*src, 0, 1));
        *src += 2;
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
    return *src[0] == '&' ? new_metatoken_obj(meta_ampersand, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
}

/**
 * Match for a period '.' used to indicate capture of a rule.
 *
 * #period = '.';
 */
obj* match_meta_period(char** src)
{
    return *src[0] == '.' ? new_metatoken_obj(meta_period, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
}

/**
 * Match for a star '*' used to indicate 0 or more elements.
 *
 * #star = '*';
 */
obj* match_meta_star(char** src)
{
    return *src[0] == '*' ? new_metatoken_obj(meta_star, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
}

/**
 * Match for a plus '+' used to indicate 1 or more elements.
 *
 * #plus = '+';
 */
obj* match_meta_plus(char** src)
{
    return *src[0] == '+' ? new_metatoken_obj(meta_plus, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
}

/**
 * Match for a question mark '?' used to indicate an optional element.
 *
 * #question_mark = '?';
 */
obj* match_meta_question_mark(char** src)
{
    return *src[0] == '?' ? new_metatoken_obj(meta_question_mark, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
}

/**
 * Match for a tiled '~' used to indicate the compliment of a charset.
 *
 * #tiled = '~';
 */
obj* match_meta_tilde(char** src)
{
    return *src[0] == '~' ? new_metatoken_obj(meta_tilde, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
}

/**
 * Match for a semicolon ';' used to delimit the end of a meta rule;
 *
 * #semicolon = ';';
 */
obj* match_meta_semicolon(char** src)
{
    obj* t = *src[0] == ';' ? new_metatoken_obj(meta_semicolon, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL && peek_metascanner_state() == scan_meta_rule)
    {
        pop_metascanner_state();
        // peek_metascanner_state should == scan_root...
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
    return *src[0] == '|' ? new_metatoken_obj(meta_vertical_bar, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
}

/**
 * Match for minus '-' used to indicate charset difference (or potentially expression exclusions).
 *
 * #minus = '-';
 */
obj* match_meta_minus(char** src)
{
    return *src[0] == '-' ? new_metatoken_obj(meta_minus, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
}

/**
 * Match forward slash '/' used to indicate follow restriction, i.e. expressions that may not follow.
 *
 * #forward_slash = '/';
 */
obj* match_meta_forward_slash(char** src)
{
    return *src[0] == '/' ? new_metatoken_obj(meta_forward_slash, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
}

/**
 * Match greater than '>' used to indicate the left expression has higher precedence than the right expression.
 *
 * #greater_than = '>';
 */
obj* match_meta_greater_than(char** src)
{
    return *src[0] == '>' ? new_metatoken_obj(meta_greater_than, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
}

/**
 * Match less than '<' used to indicate the left expression has lower precedence than the right expressions.
 *
 * #less_than = '<';
 */
obj* match_meta_less_than(char** src)
{
    return *src[0] == '<' ? new_metatoken_obj(meta_less_than, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
}

/**
 * Match for equals sign '=' used to bind a meta rule to a hashtag identifier.
 *
 * #equals_sign = '=';
 */
obj* match_meta_equals_sign(char** src)
{
    return *src[0] == '=' ? new_metatoken_obj(meta_equals_sign, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
}

/**
 * Match for left parenthesis '(' used to group an expression, or start a meta function call.
 *
 * #left_parenthesis = '(';
 */
obj* match_meta_left_parenthesis(char** src)
{
    return *src[0] == '(' ? new_metatoken_obj(meta_left_parenthesis, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
}

/**
 * Match for right parenthesis ')' used to group an expression, or end a meta function call.
 *
 * #right_parenthesis = ')';
 */
obj* match_meta_right_parenthesis(char** src)
{
    obj* t = *src[0] == ')' ? new_metatoken_obj(meta_right_parenthesis, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL && peek_metascanner_state() == scan_metafunc_body)
    {
        pop_metascanner_state(); // return to previous context (scan_root) after meta function call closed
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
    obj* t = *src[0] == '{' ? new_metatoken_obj(meta_left_bracket, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL)
    {
        metascanner_state state = peek_metascanner_state();
        if (state == scan_meta_rule) { push_metascanner_state(scan_caseless_string_body); }
    }
    return t;
}

/**
 * Match for right bracket '}' used to close capture groups.
 *
 * #right_bracket = '}';
 */
obj* match_meta_right_bracket(char** src)
{
    obj* t = *src[0] == '}' ? new_metatoken_obj(meta_right_bracket, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL)
    {
        metascanner_state state = peek_metascanner_state();
        if (state == scan_caseless_string_body) { pop_metascanner_state(); }
    }
    return t;
}

/**
 * Match for left brace '[' used to start a new charset literal.
 *
 * #left_brace = '[';
 */
obj* match_meta_left_brace(char** src)
{
    obj* t = *src[0] == '[' ? new_metatoken_obj(meta_left_brace, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL && peek_metascanner_state() == scan_meta_rule)
    {
        push_metascanner_state(scan_charset_body); // enter charset context for body
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
    obj* t = *src[0] == ']' ? new_metatoken_obj(meta_right_brace, ustring_charstar_substr((*src)++, 0, 0)) : NULL;
    if (t != NULL && peek_metascanner_state() == scan_charset_body)
    {
        pop_metascanner_state(); // switch back to previous context (scan_meta_rule) after charset closed.
    }
    return t;
}

/**
 * Match ascii whitespace characters which will be ignored by the meta scanner/parser.
 *
 * #wschar = [\x9-\xD\x20];
 * #ws = #wschar*;
 */
obj* match_whitespace(char** src)
{
    size_t i = 0;
    while (is_whitespace_char((*src)[i])) { i++; }
    if (i > 0)
    {
        obj* t = new_metatoken_obj(whitespace, ustring_charstar_substr(*src, 0, i - 1));
        *src += i;
        return t;
    }
    return NULL;
}

/**
 * Match for a single line comment, which will be ignored by the meta scanner/parser
 *
 * #line_comment = '//' \U* '\n';
 */
obj* match_line_comment(char** src)
{
    if ((*src)[0] == '/' && (*src)[1] == '/') // match for single line comments
    {
        // scan through comment to either a newline or null terminator character
        int i = 2;
        while ((*src)[i] != 0 && (*src)[i] != '\n') { i++; }
        obj* t =
            new_metatoken_obj(comment, ustring_utf8_substr(*src, 0, i - 1)); // don't include null terminator or newline
        *src += i;
        if ((*src)[0] != 0) { (*src)++; } // if not at null terminator, progress past newline
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
    if ((*src)[0] == '/' && (*src)[1] == '{') // match for multiline comment
    {
        int stack = 1; // keep track of nesting of comments. should be 0 if all opened comments are closed
        int i = 2;
        while ((*src)[i] != 0 && stack != 0) // while not end of input, and not all comments have been closed
        {
            // search for opening and closing comment symbols
            if ((*src)[i] == '}' && (*src)[i + 1] == '/') // closing comment
            {
                stack -= 1;
                i += 2;
            }
            else if ((*src)[i] == '/' && (*src)[i + 1] == '{') // opening comment
            {
                stack += 1;
                i += 2;
            }
            else
            {
                i++;
            } // regular character skip
        }

        if (stack == 0) // check to make sure all nested comments were closed
        {
            // return token
            obj* t = new_metatoken_obj(comment, ustring_utf8_substr(*src, 0, i - 1));
            *src += i;
            return t;
        }
        else // reached null terminator without closing all nested comments
        {
            printf("ERROR: reached the end of input while scanning 'multiline comment\n");
        }
    }
    return NULL;
}

/**
 * Remove the specified type of token from the vector of tokens.
 */
// remove all instances of a specific token type from a vector of tokens
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
// check if the next non-whitespace and non-comment character matches the specified character
uint32_t get_peek_char(char** src)
{
    // separate pointers from src so peek doesn't modify it
    char* head = *src;
    char** head_ptr = &head;

    // set context to peek
    push_metascanner_state(scan_peek);

    // capture each scanned object since they need to be freed
    obj* o;

    // scan through until no more comment/whitespace tokens are returned
    while ((*head_ptr)[0] != 0 && (o = scan(head_ptr))) { obj_free(o); }

    // return to the previous context
    pop_metascanner_state();

    return peek_unicode(head_ptr, 0, NULL);
}

#endif