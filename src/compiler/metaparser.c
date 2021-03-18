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
    metaast* body_ast = metaast_parse_expr(body_tokens);
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




size_t metaparser_add_head(obj* head){}
obj* metaparser_get_head(size_t i){}

size_t metaparser_add_body(obj* body){}
vect* metaparser_get_body(size_t i){}

void metaparser_join(size_t head_idx, size_t body_idx){}



#endif