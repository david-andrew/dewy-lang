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


//function pointer type for token scan functions
typedef metaast* (*metaparse_fn)(vect* body_tokens);

//tokens to scan for before entering any meta syntax context
metaparse_fn metaparser_match_funcs[] = {
    //TODO->include everything we're scanning for that creates a node...
    parse_meta_eps,
    parse_meta_char,
    parse_meta_string,
    parse_meta_charset,
    parse_meta_anyset,
    parse_meta_hex,
    // parse_meta_star,
    // parse_meta_plus,
    // parse_meta_option,
    // parse_meta_count,
    // parse_meta_compliment,
    // parse_meta_cat,
    
    //unimplemented
    // parse_meta_or,

    //implement when doing srnglr filters
    // parse_meta_greater_than,
    // parse_meta_less_than,
    // parse_meta_reject,
    // parse_meta_nofollow,
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
    
    printf("vect of body tokens: "); vect_str(body_tokens); printf("\n");

    //create the head from the rule_identifier_token
    obj* head = new_unicode_string_obj(rule_identifier_token->content);
    free(rule_identifier_token);

    // printf("Rule\n");
    // for (int i = 0; i < vect_size(body_tokens); i++) { metatoken_repr(vect_get(body_tokens, i)->data); }

    //create an AST from the tokens, and combine all charset expressions
    metaast* body_ast = metaparser_build_metaast(body_tokens);
    while (metaast_fold_constant(body_ast));

    obj_print(head);
    printf(" = ");
    if (body_ast == NULL) { printf("NULL"); } else { metaast_repr(body_ast); }
    printf("\n");
    obj_free(head);

    //recursively translate the AST into CFG production bodies
    // metaparser_create_body(head, body_ast);
    if (body_ast) //TODO->take out later
    metaast_free(body_ast);

    return true;
}


/**
 * Create a meta-ast from the list of tokens.
 * Body tokens will be freed by the matching rules.
 */
metaast* metaparser_build_metaast(vect* body_tokens)
{
    #define len(A) sizeof(A) / sizeof(metaparse_fn)
    metaast* match;
    for (size_t i = 0; i < len(metaparser_match_funcs); i++)
    {
        if ((match = metaparser_match_funcs[i](body_tokens)))
        {
            return match;
        }
    }
    printf("no matching rule...\n");
    return NULL;
}


/**
 * Recursively construct the grammar symbol string from the given vect* of tokens.
 * all heads, bodies, and charsets are inserted into their respective metaparser set.
 * additionally, corresponding join table entries are also created.
 * Calls vect_free(rule_body_tokens) at the end of the func.
 * `head` is the identifier being used for the rule body being constructed.
 * `head` may optionally be NULL, in which case the compiler will come up with a name for the rule
 */
vect* metaparser_create_body(obj* head, metaast* body_ast)
{
    

    // //determine what indices the parser may be split at
    // vect* split_idxs = metaparser_get_split_idxs(body_tokens);
    // vect* body;
    // if (vect_size(split_idxs) == 0)
    // {
    //     //recursively construct the body with all the tokens
    //     body = metaparser_parse_single_body(head, body_tokens);
    // }
    // else
    // {
        
    //     vect* delimiters = new_vect();
    //     int offset = 0;
    //     for (int i = 0; i < vect_size(split_idxs); i++)
    //     {

    //     }
    // }

    // vect_free(split_idxs);



    // //determine if the tokens can be split into sub components
    // int split_idx = metaparser_get_split_idx(body_tokens);

    // //a vector containing integers that map to the index of either charsets, or nonterminal identifiers.
    // vect* body;

    // //construct body for splitable vs non-splitable token sequences
    // if (split_idx < 0)
    // {
    //     //recursively construct the body with all the tokens
    //     body = metaparser_parse_single_body(head, body_tokens);
    // }
    // else
    // {
    //     //split the tokens at the delimiter
    //     vect* left_body_tokens = new_vect();
    //     for (int i = 0; i < split_idx - 1; i++) { vect_enqueue(left_body_tokens, vect_dequeue(body_tokens)); }
    //     metatoken* delimiter = obj_free_keep_inner(vect_dequeue(body_tokens), MetaToken_t);

    //     //TODO->depending on delimiter, obj* sub_head = NULL; //use instead of head for building

    //     //recursively build the bodies of the split left and right portions
    //     vect* left_body = metaparser_create_body(NULL, left_body_tokens);
    //     vect* right_body = metaparser_create_body(NULL, body_tokens);

    //     //merge the left and right bodies according to the delimiter
    //     body = metaparser_merge_left_right_body(head, left_body, right_body, delimiter);
    // }


    // //determine identifier that maps to this body. if this is a subcomponent of a rule, 
    // //then try to use an existing identifier for this exact single production.
    // //if no identical production exists, then generate a new anonymous identifier.
    // //if head is predefined (i.e. top level user specified rule), then use the given head, 
    // //regardless of if it may be duplicating an existing rule.
    // //this is so the user can correctly refer to it in other rules.
    // if (head == NULL)
    // {
    //     head = metaparser_get_production_head(body);
    //     if (head == NULL)
    //     {
    //         head = metaparser_get_anonymous_rule_head();
    //     }
    // }

    // size_t head_idx = metaparser_add_head(head);
    // size_t body_idx = metaparser_add_body(body);
    // metaparser_join(head_idx, body_idx);

    // //cleanup
    // vect_free(body_tokens);

    // return body;
}


// /**
//  * Find the indeces of the tokens that split the sub components of the rule body.
//  * If no delimiters are found at the lowest level of precedence, then -1 is returned.
//  * Delimiting tokens include `|`, `<`, `>`, `-`, '/' , '&'
//  */
// int metaparser_get_split_idxs(vect* rule_body_tokens)
// {
//     //skip parenthesis (), brackets {}, braces [], strings ""/'',  
// }


// /**
//  * Parse a single meta grammar object. this includes: 
//  * eps, string/char, charset, anyset, hex, number, star, plus, option, count, compliment, or cat
//  */
// vect* metaparser_parse_single_body(obj* head, vect* body_tokens)
// {
//     //macro to get the length of each of the function arrays
//     #define len(A) sizeof(A) / sizeof(metaparse_fn)

//     vect* body;
//     for (size_t i = 0; i < len(metaparser_match_funcs); i++)
//     {    
//         // if ((body = metaparser_match_funcs[i](body_tokens)))
//         // {
//         //     //check if body already exists in metaparser_bodies
//         //     //if yes, use existing version's index in bodies
//         //     //else create a new entry
//         //     //if head is null, create anonymous identifier for it (if no entry exists yet)
//         // }
//     }

//     printf("ERROR: reached end of parse single body with input:\n - head = ");
//     obj_print(head);
//     printf("\n - body = ");
//     vect_str(body);
//     printf("\n");
//     exit(1);
// }


// /**
//  * 
//  */
// vect* metaparser_merge_left_right_body(obj* head, vect* left_body, vect* right_body, metatoken* delimiter)
// {
//     //if left and right are both charsets, and the split delimiter is a charset operator, then merge both into a single charset
//     //TODO->this needs to create a body from the charset
//     if ((metaparser_is_body_charset(left_body) && metaparser_is_body_charset(right_body)) && 
//         (delimiter->type == meta_minus || delimiter->type == meta_ampersand || delimiter->type == meta_vertical_bar))
//     {
//         charset* left = vect_dequeue(left_body)->data;
//         charset* right = vect_dequeue(right_body)->data;
//         charset* merge;
//         switch (delimiter->type)
//         {
//             case meta_minus: merge = charset_diff(left, right); break;
//             case meta_ampersand: merge = charset_intersect(left, right); break;
//             case meta_vertical_bar: merge = charset_union(left, right); break;
//             default:
//                 printf("ERROR: unknown delimiter {"); 
//                 metatoken_str(delimiter); 
//                 printf("} for charset binary operation\n"); 
//                 exit(1);
//         }

//         //reuse vect for the combined charset output
//         vect* merge_vect = left_body;
//         vect_enqueue(merge_vect, new_charset_obj(merge));

//         //free up old objects
//         vect_free(right_body);
//         charset_free(left);
//         charset_free(right);

//         return merge_vect;
//     }

//     //otherwise handle normal merge
//     //TODO
// }


/**
 * Check if the body vect contains exactly one charset.
 */
bool metaparser_is_body_charset(vect* body)
{
    return vect_size(body) == 1 && vect_get(body, 0)->type == CharSet_t;
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
 * Attempt to parse an epsilone from the tokens list.
 * Returns `metaast*` if eps found, else `NULL`
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
 * 
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
                charset* C = new_charset();
                charset_add_char(C, c);
                vect_free(tokens);
                return new_metaast_charset_node(metaast_charset, C);
            }
        }
    }
    return NULL;
}


/**
 * 
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

            //allocate room for all characters + null terminater
            uint32_t* string = malloc((size - 1) * sizeof(uint32_t));
            
            //insert each char from the tokens list into the string
            for (size_t i = 1; i < size - 1; i++)
            {
                metatoken* t = vect_get(tokens, i)->data;
                uint32_t c = metaparser_extract_char_from_token(t);
                string[i-1] = c;
            }
            string[size-2] = 0; //null terminator at the end
            
            vect_free(tokens);
            return new_metaast_string_node(metaast_string, string);
        }
    }
    return NULL;
}


/**
 * 
 */
metaast* parse_meta_charset(vect* tokens)
{
    const size_t size = vect_size(tokens);
    return NULL;
}


/**
 * 
 */
metaast* parse_meta_anyset(vect* tokens)
{
    if (vect_size(tokens) == 1)
    {
        metatoken* t = vect_get(tokens, 0)->data;
        if (t->type == meta_anyset)
        {
            vect_free(tokens);

            //create anyset by taking compliment of an empty set
            charset* nullset = new_charset();
            charset* anyset = charset_compliment(nullset);
            charset_free(nullset);
            return new_metaast_charset_node(metaast_charset, anyset);
        }
    }
    return NULL;
}


/**
 * 
 */
metaast* parse_meta_hex(vect* tokens)
{
    return NULL;
}


/**
 * 
 */
metaast* parse_meta_star(vect* tokens)
{
    return NULL;
}


/**
 * 
 */
metaast* parse_meta_plus(vect* tokens)
{
    return NULL;
}


/**
 * 
 */
metaast* parse_meta_option(vect* tokens)
{
    return NULL;
}


/**
 * 
 */
metaast* parse_meta_count(vect* tokens)
{
    return NULL;
}


/**
 * 
 */
metaast* parse_meta_compliment(vect* tokens)
{
    return NULL;
}


/**
 * 
 */
metaast* parse_meta_cat(vect* tokens)
{
    return NULL;
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


// /**
//  * Return the index of the end of the next rule in the tokens vector
//  */
// size_t get_next_rule_boundary(vect* tokens, size_t start)
// {

// }


size_t metaparser_add_head(obj* head){}
obj* metaparser_get_head(size_t i){}

size_t metaparser_add_body(obj* body){}
vect* metaparser_get_body(size_t i){}

void metaparser_join(size_t head_idx, size_t body_idx){}



#endif