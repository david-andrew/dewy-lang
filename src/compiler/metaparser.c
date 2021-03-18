#ifndef METAPARSER_C
#define METAPARSER_C

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <inttypes.h>

#include "vector.h"
#include "set.h"
#include "charset.h"
#include "metatoken.h"
#include "metascanner.h"
#include "metaparser.h"
#include "metaast.h"
#include "utilities.h"


/**
 * Global data structures used to manage all meta grammar rules.
 * body vects are a sequence of uint indices refering to either heads or charsets.
 * heads are referred to by odd indices, while charsets are referred to by even indices.
 * i.e. real_head_idx = head_idx / 2 <=> real_head_idx * 2 + 1 = head_idx
 * i.e. real_body_idx = body_idx / 2 <=> real_body_idx * 2 + 1 = body_idx
 */
dict* metaparser_heads;     //map of all production nonterminals to a set of corresponding bodies 
dict* metaparser_bodies;    //map of all production strings to a set of all corresponding heads
set* metaparser_charsets;   //set of all terminals (i.e. charsets) in all productions


/**
 * Initialize all global data structures used by metaparser.
 */
void initialize_metaparser()
{
    metaparser_heads = new_dict();
    metaparser_bodies = new_dict();
    metaparser_charsets = new_set();
}


/**
 * Free up all global data structures used by metaparser.
 */
void release_metaparser()
{
    dict_free(metaparser_heads);
    dict_free(metaparser_bodies);
    set_free(metaparser_charsets);
}


//tokens to scan for before entering any meta syntax context
metaparse_fn metaparser_match_all_funcs[] = {
    parse_meta_eps,
    parse_meta_char,
    parse_meta_string,
    parse_meta_charset,
    parse_meta_anyset,
    parse_meta_hex,
    parse_meta_identifier,
    parse_meta_star,
    parse_meta_plus,
    parse_meta_option,
    parse_meta_count,
    parse_meta_compliment,
    parse_meta_cat,
    parse_meta_or,
    parse_meta_group,
    parse_meta_capture,

    //special expressions for srnglr filters
    parse_meta_greaterthan,
    parse_meta_lessthan,
    parse_meta_reject,
    parse_meta_nofollow,
};

metaparse_fn metaparser_match_single_unit_funcs[] = {
    parse_meta_eps,
    parse_meta_char,
    parse_meta_string,
    parse_meta_charset,
    parse_meta_anyset,
    parse_meta_hex,
    parse_meta_identifier,
    parse_meta_star,
    parse_meta_plus,
    parse_meta_option,
    parse_meta_count,
    parse_meta_compliment,
    parse_meta_group,
    parse_meta_capture,
};


/**
 * Keep track of anonymous rule heads created by the metaparser.
 * Start at 1 so that we don't have to deal with log(0) = -inf.
 */
uint64_t metaparser_anonymous_rule_count = 1;


/**
 * Get an anonymous identifier for internally created sub productions
 * Identifiers are of the form #__i where i is the current `metaparser_anonymous_rule_count`
 */
obj* metaparser_get_anonymous_rule_head()
{
    //determine the string width of the number
    size_t width = ceil(log10(metaparser_anonymous_rule_count + 1));
    width += 4; //room for `#__` at start and null terminator at end
    
    //create a normal char* that will be the head
    char* num_str = malloc(width * sizeof(char));
    sprintf(num_str, "#__%"PRIu64, metaparser_anonymous_rule_count);

    //convert to unicode string (wrapped in obj*), and cleanup char* version
    obj* head = new_unicode_string_obj(utf8_substr(num_str, 0, width-1));
    free(num_str);

    //increment the counter. Increment by 2 so it matches indices in metaparser_bodies.
    metaparser_anonymous_rule_count += 2;
    
    return head;
}


/**
 * Try to scan for a rule in the current list of tokens. 
 * Returns `true` if a rule was successfully parsed.
 * Assumes that tokens may contain comments or whitespace.
 */
bool parse_next_meta_rule(vect* tokens)
{
    //get index of first non-whitespace/comment token, and check if hashtag
    int start_idx = get_next_real_metatoken(tokens, 0);
    if (!is_metatoken_i_type(tokens, start_idx, hashtag)) { return false; }

    //get index of next real token, and check if meta_equals_sign
    int stop_idx = get_next_real_metatoken(tokens, start_idx+1);
    if (!is_metatoken_i_type(tokens, stop_idx, meta_equals_sign)) { return false; }

    //search for the first occurance of a semicolon
    stop_idx = get_next_metatoken_type(tokens, meta_semicolon, stop_idx+1);
    if (stop_idx < 0) { return false; }

    //free all tokens up to the start of the rule (as they should be whitespace and comments)
    for (int i = 0; i < start_idx; i++) { obj_free(vect_dequeue(tokens)); }

    //first token in the tokens stream is the meta_identifier
    metatoken* rule_identifier_token = obj_free_keep_inner(vect_dequeue(tokens), MetaToken_t);

    //collect all tokens after identifier to tail that form the production body
    vect* body_tokens = new_vect();
    for (int i = start_idx+1; i <= stop_idx; i++)
    {
        //keep token only if non-whitespace/comment
        obj* t = vect_dequeue(tokens);
        metatoken_type type = ((metatoken*)t->data)->type;
        if (type != whitespace && type != comment) { vect_enqueue(body_tokens, t); }
        else { obj_free(t); }
    }

    //free delimiter tokens from body
    obj_free(vect_dequeue(body_tokens));    // equals sign at start
    obj_free(vect_pop(body_tokens));        // semicolon at end
    
    printf("tokens: "); vect_str(body_tokens); printf("\n");

    //create the head from the rule_identifier_token
    obj* head = new_unicode_string_obj(rule_identifier_token->content);
    free(rule_identifier_token);

    // printf("Rule\n");
    // for (int i = 0; i < vect_size(body_tokens); i++) { metatoken_repr(vect_get(body_tokens, i)->data); }

    //create an AST from the tokens, and combine all charset expressions
    metaast* body_ast = parse_meta_expr(body_tokens);
    while (metaast_fold_constant(body_ast));

    obj_print(head);
    printf(" = ");
    if (body_ast == NULL) { printf("NULL"); vect_free(body_tokens); } 
    else { metaast_repr(body_ast); }
    printf("\n");
    obj_free(head);

    //recursively translate the AST into CFG production bodies
    // metaparser_create_body(head, body_ast);
    if (body_ast) //TODO->take out later
    metaast_free(body_ast);

    return true;
}


/**
 * Attempt to parse a meta expression from all possible expression types
 * If matches, `tokens` will be freed, else returns NULL. 
 */
metaast* parse_meta_expr(vect* tokens)
{
    return parse_meta_expr_restricted(tokens, NULL);
}

/**
 * Attempt to parse a meta expression from all possible expression types, excluding `skip`
 * If matches, `tokens` will be freed, else returns NULL. 
 */
metaast* parse_meta_expr_restricted(vect* tokens, metaparse_fn skip)
{
    //search for matching inner rule
    metaast* expr = NULL;
    for (size_t i = 0; i < metaparse_fn_len(metaparser_match_all_funcs); i++)
    {
        if (metaparser_match_all_funcs[i] == skip) { continue; }
        if ((expr = metaparser_match_all_funcs[i](tokens)))
        {
            return expr;
        }
    }

    //otherwise the parse failed
    printf("ERROR: no valid expression for "); vect_str(tokens); printf("\n");
    return NULL;
}


/**
 * Recursively construct the grammar symbol string from the given a meta-ast.
 * all heads, bodies, and charsets are inserted into their respective metaparser set.
 * additionally, corresponding join table entries are also created.
 * Calls vect_free(rule_body_tokens) at the end of the func.
 * `head` is the identifier being used for the rule body being constructed.
 * `head` may optionally be NULL, in which case the compiler will come up with a name for the rule
 */
vect* metaparser_create_body(obj* head, metaast* body_ast)
{
    return NULL;
}


/**
 * Return the uint32_t codepoint specified by the token, depending on its type.
 * Token must be either a meta_char, meta_escape, or meta_hex_number
 */
uint32_t metaparser_extract_char_from_token(metatoken* t)
{
    switch (t->type)
    {
        case meta_char: return *t->content;
        case meta_charset_char: return *t->content;
        case meta_escape: return escape_to_unicode(*t->content);
        case meta_hex_number: return parse_unicode_hex(t->content);
        default: 
            printf("ERROR: attempted to extract char from non-char token: ");
            metatoken_repr(t);
            printf("\n");
            exit(1);
    }
}


/**
 * Return the index of the next non whitespace/comment token
 */
int get_next_real_metatoken(vect* tokens, int i)
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
int get_next_metatoken_type(vect* tokens, metatoken_type type, int i)
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

bool is_metatoken_i_type(vect* tokens, int i, metatoken_type type)
{
    if (i < 0 || vect_size(tokens) < i){ return false; }
    metatoken* t = vect_get(tokens, i)->data;
    return t->type == type;
}


/**
 * Return the type of metatoken that matches the given left pair token.
 * Pairs are '' "" () {} [].
 */
metatoken_type metaparser_get_matching_pair_type(metatoken_type left)
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
 * Return the index of the matching pair token in the token string.
 * e.g. used to find a matching closing parenthesis, starting at an opening parenthesis.
 * Starts scanning from start_idx, which must be of type `left`.
 * Function is formulated so that left/right can be the same type.
 * 
 * If no match is found, returns -1
 */
int metaparser_find_matching_pair(vect* tokens, metatoken_type left, size_t start_idx)
{
    metatoken_type right = metaparser_get_matching_pair_type(left);
    if (start_idx >= vect_size(tokens))
    {
        printf("ERROR: specified start_idx past the end of tokens in find_matching_pair()\n");
        exit(1);
    }
    metatoken* t0 = vect_get(tokens, start_idx)->data;
    if (t0->type != left)
    {
        printf("ERROR: expected token at start_idx to be of type %u but found %u\n", left, t0->type);
        exit(1);
    }

    //keep track of nested pairs. start with 1, i.e. already opened first pair.
    uint64_t stack = 1;

    //scan through for the matching pair
    int idx = start_idx + 1;
    while (idx < vect_size(tokens))
    {
        metatoken* t = vect_get(tokens, idx)->data;

        //check for right first, to correctly handle cases where left==right
        //e.g. for quote pairs (""), individual quotes (") cannot be nested, so first one found is the match
        if (t->type == right) { stack--; }
        else if (t->type == left) { stack++; }
        if (stack == 0)
        {
            return idx;
        }
        idx++;
    }
    return -1;
}


/**
 * Return the first index after the end of the expression starting at the given start index.
 * Returns -1 if unable to scan past expression.
 */
int metaparser_scan_to_end_of_unit(vect* tokens, size_t start_idx)
{
    if (vect_size(tokens) <= start_idx)
    {
        printf("ERROR: start index for scanning to end of unit is past the end of tokens array\n");
        exit(1);
    }
    int idx = start_idx;
    metatoken* t = vect_get(tokens, start_idx)->data;
    
    //scan through first part of the expression
    switch (t->type)
    {
        // length 1 expressions
        case hashtag:
        case meta_hex_number:
        case meta_anyset:
        case meta_epsilon:
        {
            idx += 1;
            break;
        }

        // matching pair expressions
        case meta_single_quote:
        case meta_double_quote:
        case meta_left_parenthesis:
        case meta_left_bracket:
        case meta_left_brace:
        {
            idx = metaparser_find_matching_pair(tokens, t->type, start_idx);
            if (idx < 0) 
            { 
                printf("ERROR: unpaired left-most token: ");
                metatoken_repr(t);
                printf("\n");
                return idx;
            }
            idx += 1;
            break;
        }

        // all other types not allowed to start an expression
        default: idx = -1;
    }

    if (idx < 0)
    {
        printf("ERROR: could not scan past expression because of illegal left-most token: ");
        metatoken_repr(t);
        printf("\n");
        return idx;
    }

    //scan optional suffixes to the expression
    while (idx < vect_size(tokens))
    {
        // get next token
        t = vect_get(tokens, idx)->data;
        
        // if any of the allowable suffixes, increment and start over
        if (t->type == meta_dec_number) { idx++; continue; } 
        if (t->type == meta_star) { idx++; continue; } 
        if (t->type == meta_plus) { idx++; continue; } 
        if (t->type == meta_question_mark) { idx++; continue; } 
        if (t->type == meta_tilde) { idx++; continue; } 
        
        // non-suffix type encountered
        break;
    }
    return idx;
}


/**
 * Determine whether the given token type is a binary operator separator.
 */
bool metaparser_is_token_bin_op(metatoken_type type)
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
 * Return the corresponding meta-ast type for the given separater token type.
 * type is expcted to be a binary operator separator.
 */
metaast_type metaparser_get_token_ast_type(metatoken_type type)
{
    switch (type)
    {
        case meta_minus: return metaast_reject;
        case meta_forward_slash: return metaast_nofollow;
        case meta_ampersand: return metaast_intersect;
        case meta_vertical_bar: return metaast_or;
        case meta_greater_than: return metaast_greaterthan;
        case meta_less_than: return metaast_lessthan;

        default:
            printf("ERROR: metatoken type %u is not a binary operator\n", type);
            exit(1);
    }
}


/**
 * Return the precedence level of the given meta-ast operator.
 * Lower value indicates higher precedence, i.e. tighter coupling.
 */
uint64_t metaparser_get_type_precedence_level(metaast_type type)
{
    switch (type)
    {
        /*metaast_group would be level 0*/
        case metaast_capture:
        /*technically not operators*/
        case metaast_identifier:
        case metaast_charset:
        case metaast_string:
        case metaast_eps:
            return 0;

        case metaast_star:
        case metaast_plus:
        case metaast_count:
        case metaast_option:
        case metaast_compliment:
            return 1;

        case metaast_cat:
            return 2;

        case metaast_reject:
        case metaast_nofollow:
        case metaast_intersect:
            return 3;

        case metaast_or:
        case metaast_greaterthan:
        case metaast_lessthan:
            return 4;
    }
}


/**
 * Attempt to parse an epsilone from the tokens list.
 * If matches, tokens will be freed, else returns NULL.
 * 
 * #eps = 'ϵ' | '\\e' | "''" | '""';
 */
metaast* parse_meta_eps(vect* tokens)
{
    if (vect_size(tokens) == 1)
    {
        metatoken* t = vect_get(tokens, 0)->data;
        if (t->type == meta_epsilon)
        {
            vect_free(tokens);
            return new_metaast_null_node(metaast_eps);
        }
    }
    return NULL;
}


/**
 * Attempt to parse a char (i.e. length 1 string) from the tokens list.
 * If matches, tokens will be freed, else returns NULL.
 * 
 * #char = '"' (\U - '"' | #escape | #hex) '"';
 * #char = "'" (\U - "'" | #escape | #hex) "'"; 
 */
metaast* parse_meta_char(vect* tokens)
{
    if (vect_size(tokens) == 3)
    {
        metatoken* t0 = vect_get(tokens, 0)->data; 
        metatoken* t1 = vect_get(tokens, 1)->data; 
        metatoken* t2 = vect_get(tokens, 2)->data;
        if ((t0->type == meta_single_quote && t2->type == meta_single_quote) 
        || (t0->type == meta_double_quote && t2->type == meta_double_quote))
        {
            if (t1->type == meta_char || t1->type == meta_escape || t1->type == meta_hex_number)
            {
                uint32_t c = metaparser_extract_char_from_token(t1);
                charset* cs = new_charset();
                charset_add_char(cs, c);
                vect_free(tokens);
                return new_metaast_charset_node(metaast_charset, cs);
            }
        }
    }
    return NULL;
}


/**
 * Attempt to parse a string from the tokens list.
 * If matches, tokens will be freed, else returns NULL.
 * 
 * #string = '"' (\U - '"' | #escape | #hex)2+ '"';
 * #string = "'" (\U - "'" | #escape | #hex)2+ "'";
 */
metaast* parse_meta_string(vect* tokens)
{
    const size_t size = vect_size(tokens);
    if (size >= 4) //strings must have at least 2 inner characters (and 2 quotes)
    {
        //if starts & ends with a quote
        metatoken* t0 = vect_get(tokens, 0)->data;
        metatoken* tf = vect_get(tokens, size-1)->data;
        if ((t0->type == meta_single_quote && tf->type == meta_single_quote) 
        || (t0->type == meta_double_quote && tf->type == meta_double_quote))
        {   
            //iterate through the characters in the string (stopping before the last is a quote)
            for (size_t i = 1; i < size - 1; i++)
            {
                //strings may only contain chars, hex numbers and escapes
                metatoken* t = vect_get(tokens, i)->data;
                if (t->type != meta_char && t->type != meta_hex_number && t->type != meta_escape)
                {
                    return NULL;
                }
            }

            //length of string is vect size - 2 quote tokens
            const size_t len = size - 2;

            //allocate room for all characters + null terminater
            uint32_t* string = malloc((len + 1) * sizeof(uint32_t));
            
            //insert each char from the tokens list into the string
            for (size_t i = 0; i < len; i++)
            {
                metatoken* t = vect_get(tokens, i+1)->data;
                uint32_t c = metaparser_extract_char_from_token(t);
                string[i] = c;
            }
            string[len] = 0; //null terminator at the end
            
            vect_free(tokens);
            return new_metaast_string_node(metaast_string, string);
        }
    }
    return NULL;
}


/**
 * Attempt to parse a charset from the tokens list.
 * If matches, tokens will be freed, else returns NULL.
 * 
 * #item = (\U - [\-\[\]] - #wschar) | #escape | #hex;
 * #charset = '[' (#ws #item (#ws '-' #ws #item)? #ws)+ ']';
 */
metaast* parse_meta_charset(vect* tokens)
{
    if (vect_size(tokens) > 1)
    {
        metatoken* t = vect_get(tokens, 0)->data;
        if (t->type == meta_left_brace)
        {
            if (metaparser_find_matching_pair(tokens, meta_left_brace, 0) == vect_size(tokens) - 1)
            {
                charset* cs = new_charset();

                //sequentially scan through the tokens in the charset body
                size_t idx = 1;
                while (idx < vect_size(tokens) - 1)
                {
                    uint32_t c0 = metaparser_extract_char_from_token(vect_get(tokens, idx)->data);
                    idx++;
                    
                    //minus indicates a range, otherwise a single character
                    if (((metatoken*)vect_get(tokens, idx)->data)->type != meta_minus)
                    {
                        charset_add_char(cs, c0);
                    }
                    else
                    {
                        idx++;
                        uint32_t cf = metaparser_extract_char_from_token(vect_get(tokens, idx)->data);
                        idx++;
                        charset_add_range(cs, (urange){.start=c0, .stop=cf});
                    }
                } 

                if (charset_size(cs) == 0)
                {
                    printf("ERROR: charset must contain at least 1 item\n.");
                    charset_free(cs);
                    return NULL;
                }

                vect_free(tokens);
                return new_metaast_charset_node(metaast_charset, cs);
            }
        }
    }
    return NULL;
}


/**
 * Attempt to parse an anyset from the tokens list
 * If matches, tokens will be freed, else returns NULL.
 * 
 * #anyset = '\\' [uUxX];
 */
metaast* parse_meta_anyset(vect* tokens)
{
    if (vect_size(tokens) == 1)
    {
        metatoken* t = vect_get(tokens, 0)->data;
        if (t->type == meta_anyset)
        {
            //create anyset by taking compliment of an empty set
            charset* nullset = new_charset();
            charset* anyset = charset_compliment(nullset);
            charset_free(nullset);
            vect_free(tokens);
            return new_metaast_charset_node(metaast_charset, anyset);
        }
    }
    return NULL;
}


/**
 * Attempt to parse a hex literal character from the tokens list.
 * If matches, tokens will be freed, else returns NULL.
 * 
 * #hex = '\\' [uUxX] [0-9a-fA-F]+ / [0-9a-fA-F];
 */
metaast* parse_meta_hex(vect* tokens)
{
    if (vect_size(tokens) == 1)
    {
        metatoken* t = vect_get(tokens, 0)->data;
        if (t->type == meta_hex_number)
        {
            uint32_t c = metaparser_extract_char_from_token(t);
            charset* cs = new_charset();
            charset_add_char(cs, c);
            vect_free(tokens);
            return new_metaast_charset_node(metaast_charset, cs);
        }
    }
    return NULL;
}


/**
 * Attempt to parse a hashtag expression from the tokens list.
 * If matches, tokens will be freed, else returns NULL.
 * 
 * #hashtag = '#' [a-zA-Z] [a-zA-Z0-9~!@#$&_?]* / [a-zA-Z0-9~!@#$&_?];
 */
metaast* parse_meta_identifier(vect* tokens)
{
    if (vect_size(tokens) == 1)
    {
        metatoken* t = vect_get(tokens, 0)->data;
        if (t->type == hashtag)
        {
            //free the token without touching the hashtag string
            t = obj_free_keep_inner(vect_pop(tokens), MetaToken_t);            
            uint32_t* tag = t->content;
            free(t);
            vect_free(tokens);
            return new_metaast_string_node(metaast_identifier, tag);
        }
    }
    return NULL;
}


/**
 * Attempt to parse a star expression from the tokens list.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #star = #expr #ws (#number)? #ws '*';
 */
metaast* parse_meta_star(vect* tokens)
{
    //check ends with a star
    size_t size = vect_size(tokens);
    if (size > 1)
    {
        metatoken* t0 = vect_get(tokens, size - 1)->data;
        if (t0->type == meta_star)
        {
            //keep track of the size of the inner expression
            size_t expr_size = size - 1;

            //check for optional count right before star. otherwise default is 0
            uint64_t count = 0;
            if (size > 2) 
            {
                metatoken* t1 = vect_get(tokens, size - 2)->data;
                if (t1->type == meta_dec_number)
                {
                    count = parse_unicode_dec(t1->content);
                    expr_size -= 1;
                }
            }

            //store the tokens for the star expression, in case inner match fails
            vect* star_tokens = new_vect();
            for (size_t i = 0; i < size - expr_size; i++)
            {
                vect_push(star_tokens, vect_pop(tokens));
            }

            //attempt to parse the inner expression
            metaast* inner = NULL;
            for (size_t i = 0; i < metaparse_fn_len(metaparser_match_single_unit_funcs); i++)
            {
                if ((inner = metaparser_match_single_unit_funcs[i](tokens)))
                {
                    //matched a star expression
                    vect_free(star_tokens);
                    return new_metaast_repeat_node(metaast_star, count, inner);
                }
            }
            
            //restore the tokens vector with the tokens from the star expression
            for (size_t i = 0; i < size - expr_size; i++) 
            { 
                vect_push(tokens, vect_pop(star_tokens));
            }
            vect_free(star_tokens);
            
        }
    }
    return NULL;
}


/**
 * Attempt to parse a plus expression from the tokens list.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #plus = #expr #ws (#number)? #ws '+';
 */
metaast* parse_meta_plus(vect* tokens)
{
    //check ends with a plus
    size_t size = vect_size(tokens);
    if (size > 1)
    {
        metatoken* t0 = vect_get(tokens, size - 1)->data;
        if (t0->type == meta_plus)
        {
            //keep track of the size of the inner expression
            size_t expr_size = size - 1;

            //check for optional count right before plus. otherwise default is 1
            uint64_t count = 1;
            if (size > 2) 
            {
                metatoken* t1 = vect_get(tokens, size - 2)->data;
                if (t1->type == meta_dec_number)
                {
                    count = parse_unicode_dec(t1->content);
                    expr_size -= 1;
                }
            }

            //store the tokens for the star expression, in case inner match fails
            vect* plus_tokens = new_vect();
            for (size_t i = 0; i < size - expr_size; i++)
            {
                vect_push(plus_tokens, vect_pop(tokens));
            }

            //attempt to parse the inner expression
            metaast* inner = NULL;
            for (size_t i = 0; i < metaparse_fn_len(metaparser_match_single_unit_funcs); i++)
            {
                if ((inner = metaparser_match_single_unit_funcs[i](tokens)))
                {
                    //matched a plus expression
                    vect_free(plus_tokens);
                    return new_metaast_repeat_node(metaast_plus, count, inner);
                }
            }
            
            //restore the tokens vector with the tokens from the plus expression
            for (size_t i = 0; i < size - expr_size; i++) 
            { 
                vect_push(tokens, vect_pop(plus_tokens));
            }
            vect_free(plus_tokens);
        }
    }
    return NULL;
}


/**
 * Attempt to parse an option expression from the tokens list.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #option = #expr #ws '?';
 */
metaast* parse_meta_option(vect* tokens)
{
    //check ends with a question mark
    size_t size = vect_size(tokens);
    if (size > 1)
    {
        metatoken* t0 = vect_get(tokens, size - 1)->data;
        if (t0->type == meta_question_mark)
        {
            //store the tokens for the star expression, in case inner match fails
            obj* question_mark_token_obj = vect_pop(tokens);

            //attempt to parse the inner expression
            metaast* inner = NULL;
            for (size_t i = 0; i < metaparse_fn_len(metaparser_match_single_unit_funcs); i++)
            {
                if ((inner = metaparser_match_single_unit_funcs[i](tokens)))
                {
                    //matched an option expression
                    obj_free(question_mark_token_obj);
                    return new_metaast_unary_op_node(metaast_option, inner);
                }
            }
            
            //restore the tokens vector with the question mark token
            vect_push(tokens, question_mark_token_obj);
        }
    }
    return NULL;
}


/**
 * Attempt to parse a count expression from the tokens list.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #count = #expr #ws #number;
 */
metaast* parse_meta_count(vect* tokens)
{
    //check ends with a number
    size_t size = vect_size(tokens);
    if (size > 1)
    {
        metatoken* t0 = vect_get(tokens, size - 1)->data;
        if (t0->type == meta_dec_number)
        {
            //store the tokens for the star expression, in case inner match fails
            obj* number_token_obj = vect_pop(tokens);

            //attempt to parse the inner expression
            metaast* inner = NULL;
            for (size_t i = 0; i < metaparse_fn_len(metaparser_match_single_unit_funcs); i++)
            {
                if ((inner = metaparser_match_single_unit_funcs[i](tokens)))
                {
                    //matched a count expression
                    metatoken* t = number_token_obj->data;
                    uint64_t count = parse_unicode_dec(t->content);
                    obj_free(number_token_obj);
                    return new_metaast_repeat_node(metaast_count, count, inner);
                }
            }
            
            //restore the tokens vector with the question mark token
            vect_push(tokens, number_token_obj);
        }
    }
    return NULL;
}


/**
 * Attempt to parse a compliment expression from the tokens list.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #compliment = #set #ws '~';
 */
metaast* parse_meta_compliment(vect* tokens)
{
    //check ends with a tilde
    size_t size = vect_size(tokens);
    if (size > 1)
    {
        metatoken* t0 = vect_get(tokens, size - 1)->data;
        if (t0->type == meta_tilde)
        {
            //store the tokens for the star expression, in case inner match fails
            obj* tilde_token_obj = vect_pop(tokens);

            //attempt to parse the inner expression
            metaast* inner = NULL;
            for (size_t i = 0; i < metaparse_fn_len(metaparser_match_single_unit_funcs); i++)
            {
                if ((inner = metaparser_match_single_unit_funcs[i](tokens)))
                {
                    //matched a compliment expression
                    obj_free(tilde_token_obj);
                    return new_metaast_unary_op_node(metaast_compliment, inner);
                }
            }
            
            //restore the tokens vector with the question mark token
            vect_push(tokens, tilde_token_obj);
        }
    }
    return NULL;
}


/**
 * Attempt to match a concatenation sequence expression from the tokens list.
 * if matches, tokens is freed, else returns NULL.
 * 
 * #cat = #expr (#ws #expr)+;
 */
metaast* parse_meta_cat(vect* tokens)
{
    // verify top level expression contains no lower precedence operators
    int idx = 0;
    int count = 0;
    while (idx < vect_size(tokens))
    {
        idx = metaparser_scan_to_end_of_unit(tokens, idx);
        if (idx < 0) { return NULL; }
        
        //check if token at end of expression is a binary operator
        //all bin ops have lower precedence than cat, so we parse them first
        if (idx < vect_size(tokens))
        {
            metatoken* t = vect_get(tokens, idx)->data;
            if (metaparser_is_token_bin_op(t->type))            {
                return NULL;
            }
        }
        count++;
    }

    if (count > 1)
    {
        //build the sequenc of expressions to cat
        metaast** sequence = malloc(count * sizeof(metaast*));
        idx = 0;
        for (int i = 0; i < count; i++)
        {
            idx = metaparser_scan_to_end_of_unit(tokens, 0);
            vect* expr_tokens = new_vect(); //will be freed by parse_meta_expr()
            for (int j = 0; j < idx; j++)
            {
                vect_enqueue(expr_tokens, vect_dequeue(tokens));
            }
            metaast* expr = parse_meta_expr_restricted(expr_tokens, parse_meta_cat);
            sequence[i] = expr;
        }

        vect_free(tokens); //should be empty
        return new_metaast_sequence_node(metaast_cat, count, sequence);
    }
    return NULL;
}

/**
 * Attempt to parse an or sequence expression from the list of tokens.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #or = (#expr #ws '|' #ws #expr) - #union;
 * #set #ws '|' #ws #set;
 */
metaast* parse_meta_or(vect* tokens)
{
    // verify top level expression contains no lower precedence operators
    int idx = 0;
    uint64_t cur_precedence = 0;
    const uint64_t or_precedence = metaparser_get_type_precedence_level(metaast_or);
    
    //keep track of location of the `|` which will split the tokens list
    int split_idx = -1;

    while (idx < vect_size(tokens))
    {
        idx = metaparser_scan_to_end_of_unit(tokens, idx);
        if (idx < 0) { return NULL; }
        
        //check if token at end of expression is a binary operator, and has equal or higher precedence than this one
        if (idx < vect_size(tokens))
        {
            metatoken* t = vect_get(tokens, idx)->data;
            if (metaparser_is_token_bin_op(t->type))
            {
                uint64_t level = metaparser_get_type_precedence_level(metaparser_get_token_ast_type(t->type));
                if (level >= cur_precedence)
                { 
                    cur_precedence = level;
                    split_idx = idx; 
                }

                //even lower precedence operator will be parsed first
                if (cur_precedence > or_precedence)
                {
                    return NULL;
                }

                idx++;
            }
        }
    }

    if (split_idx > 0)
    {
        //check if the token at the split index is the right operator
        metatoken* t = vect_get(tokens, split_idx)->data;
        
        //record the index if this is an operator of the correct level of precedence
        if (t->type == meta_vertical_bar)
        {
            vect* left_tokens = new_vect();
            for (int i = 0; i < split_idx; i++)
            {
                vect_enqueue(left_tokens, vect_dequeue(tokens));
            }
            obj_free(vect_dequeue(tokens)); //free the split operator token

            metaast* left = parse_meta_expr(left_tokens);
            if (left != NULL)
            {
                metaast* right = parse_meta_expr(tokens);
                if (right != NULL)
                {
                    return new_metaast_binary_op_node(metaast_or, left, right);
                }
                else
                {
                    printf("ERROR: binary op right AST returned NULL\n");
                    metaast_free(left);
                }
            }
            else
            {
                printf("ERROR: binary op left AST returned NULL\n");
            }
        }
    }
    return NULL;
}


/**
 * Attempt to match a group expression from the tokens list.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #group = '(' #ws #expr #ws ')';
 */
metaast* parse_meta_group(vect* tokens)
{
    size_t size = vect_size(tokens);
    if (size > 2)
    {
        metatoken* t = vect_get(tokens, 0)->data;
        if (t->type == meta_left_parenthesis)
        {
            //if last token is matching parenthesis, then this is a group expression
            if (metaparser_find_matching_pair(tokens, meta_left_parenthesis, 0) == size - 1)
            {
                obj_free(vect_dequeue(tokens)); //free left parenthesis
                obj_free(vect_pop(tokens));     //free right parenthesis
                
                return parse_meta_expr(tokens);
            }
        }
    }
    return NULL;
}


/**
 * Attempt to match a capture group expression from the tokens list.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #capture = '{' #ws #expr #ws '}';
 */
metaast* parse_meta_capture(vect* tokens)
{
    size_t size = vect_size(tokens);
    if (size > 2)
    {
        metatoken* t = vect_get(tokens, 0)->data;
        if (t->type == meta_left_bracket)
        {
            //if last token is matching parenthesis, then this is a capture group expression
            if (metaparser_find_matching_pair(tokens, meta_left_bracket, 0) == size - 1)
            {
                obj_free(vect_dequeue(tokens)); //free left bracket
                obj_free(vect_pop(tokens));     //free right bracket

                metaast* inner = parse_meta_expr(tokens);
                if (inner != NULL)
                {
                    return new_metaast_unary_op_node(metaast_capture, inner);
                }
            }
        }
    }
    return NULL;
}


/**
 * 
 */
metaast* parse_meta_greaterthan(vect* tokens)
{
    //determine that lowest precedence operator is greaterthan
    return NULL;
}


/**
 * 
 */
metaast* parse_meta_lessthan(vect* tokens)
{
    //determine that lowest precedence operator is lessthan
    return NULL;
}


/**
 * 
 */
metaast* parse_meta_reject(vect* tokens)
{
    //determine that lowest precedence operator is reject
    return NULL;
}


/**
 * 
 */
metaast* parse_meta_nofollow(vect* tokens)
{
    //determine that lowest precedence operator is nofollow
    return NULL;
}



size_t metaparser_add_head(obj* head){}
obj* metaparser_get_head(size_t i){}

size_t metaparser_add_body(obj* body){}
vect* metaparser_get_body(size_t i){}

void metaparser_join(size_t head_idx, size_t body_idx){}



#endif