#ifndef METAAST_C
#define METAAST_C

#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <inttypes.h>
#include <string.h>

#include "metatoken.h"
#include "metaast.h"
#include "utilities.h"
#include "ustring.h"

#define METAAST_NO_PARENT_TYPE (metaast_type)12345

/**
 * Set to true when an error occurs during a parse, so the rest of the parse can abort.
 */
bool metaast_parse_error_occurred = false;

//functions for all scannable rules 
metaast_parse_fn metaast_all_rule_funcs[] = {
    metaast_parse_eps,
    metaast_parse_char,
    metaast_parse_caseless_char,
    metaast_parse_string,
    metaast_parse_caseless_string,
    metaast_parse_charset,
    metaast_parse_anyset,
    metaast_parse_hex,
    metaast_parse_identifier,
    metaast_parse_star,
    metaast_parse_plus,
    metaast_parse_option,
    metaast_parse_count,
    metaast_parse_compliment,
    metaast_parse_cat,
    metaast_parse_or,
    metaast_parse_intersect,
    metaast_parse_group,
    metaast_parse_capture,

    //special expressions for srnglr filters
    metaast_parse_greaterthan,
    metaast_parse_lessthan,
    metaast_parse_reject,
    metaast_parse_nofollow,
};

//functions for scanning rules that can be operands in a binary op
metaast_parse_fn metaast_single_unit_rule_funcs[] = {
    metaast_parse_eps,
    metaast_parse_char,
    metaast_parse_caseless_char,
    metaast_parse_string,
    metaast_parse_caseless_string,
    metaast_parse_charset,
    metaast_parse_anyset,
    metaast_parse_hex,
    metaast_parse_identifier,
    metaast_parse_star,
    metaast_parse_plus,
    metaast_parse_option,
    metaast_parse_count,
    metaast_parse_compliment,
    metaast_parse_group,
    metaast_parse_capture,
};


/**
 * Create a new meta-ast of `type` containing `node`
 * Node may be either a pointer to a metaast_<type>_node, or NULL
 */
metaast* new_metaast(metaast_type type, void* node)
{
    metaast* ast = malloc(sizeof(metaast));
    *ast = (metaast){.type=type, .node=node};
    return ast;
}


/**
 * Create a new meta-ast node with no node content.
 * Used for eps nodes.
 */
metaast* new_metaast_null_node(metaast_type type)
{
    return new_metaast(type, NULL);
}


/**
 * Create new meta-ast node containing a unicode string.
 * used for string and hashtags nodes.
 */
metaast* new_metaast_string_node(metaast_type type, uint32_t* string)
{
    metaast_string_node* node = malloc(sizeof(metaast_string_node));
    *node = (metaast_string_node){.string=string};
    return new_metaast(type, node);
}


/**
 * Create a new meta-ast node for repeating an inner ast.
 * Used for star, plus, and repeat nodes.
 */
metaast* new_metaast_repeat_node(metaast_type type, uint64_t count, metaast* inner)
{
    metaast_repeat_node* node = malloc(sizeof(metaast_repeat_node));
    *node = (metaast_repeat_node){.count=count, .inner=inner};
    return new_metaast(type, node);
}


/**
 * Create a new meta-ast node for applying a unary op to an inner ast.
 * Used for option and compliment nodes.
 */
metaast* new_metaast_unary_op_node(metaast_type type, metaast* inner)
{
    metaast_unary_op_node* node = malloc(sizeof(metaast_unary_op_node));
    *node = (metaast_unary_op_node){.inner=inner};
    return new_metaast(type, node);
}


/**
 * Create a new sequence of meta-ast nodes.
 * Used for either a sequence of node concatenations, or "|" alternates.
 * If sequence is NULL, creates an empty sequence.
 */
metaast* new_metaast_sequence_node(metaast_type type, size_t size,/* size_t capacity,*/ metaast** sequence)
{
    metaast_sequence_node* node = malloc(sizeof(metaast_sequence_node));
    *node = (metaast_sequence_node){.size=size, /*.capacity=capacity,*/ .sequence=sequence};
    return new_metaast(type, node);
}


/**
 * Create a new meta-ast node representing a binary opration.
 * Used for reject, nofollow, greaterthan, and lessthan.
 */
metaast* new_metaast_binary_op_node(metaast_type type, metaast* left, metaast* right)
{
    metaast_binary_op_node* node = malloc(sizeof(metaast_binary_op_node));
    *node = (metaast_binary_op_node){.left=left, .right=right};
    return new_metaast(type, node);
}


/**
 * Create a new meta-ast containing a charset.
 * Represents normal charsets, hex literals, length 1 strings, and the anyset.
 */
metaast* new_metaast_charset_node(metaast_type type, charset* c)
{
    metaast_charset_node* node = malloc(sizeof(metaast_charset_node));
    *node = (metaast_charset_node){.c=c};
    return new_metaast(type, node);
}


/**
 * Attempt to parse a meta expression from all possible expression types
 * If matches, `tokens` will be freed, else returns NULL. 
 */
metaast* metaast_parse_expr(vect* tokens)
{
    return metaast_parse_expr_restricted(tokens, NULL);
}

/**
 * Attempt to parse a meta expression from all possible expression types, excluding `skip`
 * If matches, `tokens` will be freed, else returns NULL. 
 */
metaast* metaast_parse_expr_restricted(vect* tokens, metaast_parse_fn skip)
{
    //search for matching inner rule
    metaast* expr = NULL;
    metaast_parse_error_occurred = false;
    for (size_t i = 0; i < metaast_parse_fn_len(metaast_all_rule_funcs); i++)
    {
        //if specified, skip the matching rule when it comes up
        if (metaast_all_rule_funcs[i] == skip) { continue; }

        //if the current rule returns an ast, then success
        if ((expr = metaast_all_rule_funcs[i](tokens)))
        {
            return expr;
        }

        //stop attempting to parse more rules if an error definitely occurred
        if (metaast_parse_error_occurred){ break; }
    }

    //otherwise the parse failed
    printf("ERROR: no valid expression for "); vect_str(tokens); printf("\n");
    metaast_parse_error();
    return NULL;
}


/**
 * Called when an error occurs during parsing.
 * TODO->add more functionality, e.g. displaying where in source the error was detected.
 */
void metaast_parse_error(/*more args to be added*/)
{
    metaast_parse_error_occurred = true;
}


/**
 * Attempt to parse an epsilone from the tokens list.
 * If matches, tokens will be freed, else returns NULL.
 * 
 * #eps = 'ϵ' | '\\e' | "''" | '""';
 */
metaast* metaast_parse_eps(vect* tokens)
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
metaast* metaast_parse_char(vect* tokens)
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
                uint32_t c = metatoken_extract_char_from_token(t1);
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
 * Attempt to parse a caseless char (i.e. length 1 caseless) from the tokens list.
 * If matches, tokens will be freed, else returns NULL.
 * 
 * #caseless_char = "{" (ξ - [{}] | #escape | #hex) "}";
 */
metaast* metaast_parse_caseless_char(vect* tokens)
{
    if (vect_size(tokens) == 3)
    {
        metatoken* t0 = vect_get(tokens, 0)->data; 
        metatoken* t1 = vect_get(tokens, 1)->data; 
        metatoken* t2 = vect_get(tokens, 2)->data;
        if (t0->type == meta_left_bracket && t2->type == meta_right_bracket)
        {
            if (t1->type == meta_char || t1->type == meta_escape || t1->type == meta_hex_number)
            {
                //get the codepoint saved in the token
                uint32_t c = metatoken_extract_char_from_token(t1);

                //get the uppercase and lowercase for the codepoint
                //TODO->should probably cache upper and lower?
                uint32_t lower, upper;
                unicode_upper_and_lower(c, &upper, &lower);

                //create a charset containing upper and lower
                charset* cs = new_charset();
                charset_add_char(cs, upper);
                charset_add_char(cs, lower);
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
metaast* metaast_parse_string(vect* tokens)
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
                uint32_t c = metatoken_extract_char_from_token(t);
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
 * Attempt to parse a caseless string from the tokens list.
 * If matches, tokens will be freed, else returns NULL.
 * 
 * 
 */
metaast* metaast_parse_caseless_string(vect* tokens)
{
    const size_t size = vect_size(tokens);
    if (size >= 4) //strings must have at least 2 inner characters (and 2 quotes)
    {
        //if starts & ends with a quote
        metatoken* t0 = vect_get(tokens, 0)->data;
        metatoken* tf = vect_get(tokens, size-1)->data;
        if (t0->type == meta_left_bracket && tf->type == meta_right_bracket)
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
                uint32_t c = metatoken_extract_char_from_token(t);
                string[i] = c;
            }
            string[len] = 0; //null terminator at the end
            
            vect_free(tokens);
            return new_metaast_string_node(metaast_caseless, string);
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
metaast* metaast_parse_charset(vect* tokens)
{
    if (vect_size(tokens) > 1)
    {
        metatoken* t = vect_get(tokens, 0)->data;
        if (t->type == meta_left_brace)
        {
            if (metaast_find_matching_pair(tokens, meta_left_brace, 0) == vect_size(tokens) - 1)
            {
                charset* cs = new_charset();

                //sequentially scan through the tokens in the charset body
                size_t idx = 1;
                while (idx < vect_size(tokens) - 1)
                {
                    uint32_t c0 = metatoken_extract_char_from_token(vect_get(tokens, idx)->data);
                    idx++;
                    
                    //minus indicates a range, otherwise a single character
                    if (((metatoken*)vect_get(tokens, idx)->data)->type != meta_minus)
                    {
                        charset_add_char(cs, c0);
                    }
                    else
                    {
                        idx++;
                        uint32_t cf = metatoken_extract_char_from_token(vect_get(tokens, idx)->data);
                        idx++;
                        charset_add_range(cs, (urange){.start=c0, .stop=cf});
                    }
                } 

                if (charset_size(cs) == 0)
                {
                    printf("ERROR: charset must contain at least 1 item\n.");
                    metaast_parse_error();
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
metaast* metaast_parse_anyset(vect* tokens)
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
metaast* metaast_parse_hex(vect* tokens)
{
    if (vect_size(tokens) == 1)
    {
        metatoken* t = vect_get(tokens, 0)->data;
        if (t->type == meta_hex_number)
        {
            uint32_t c = metatoken_extract_char_from_token(t);
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
metaast* metaast_parse_identifier(vect* tokens)
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
metaast* metaast_parse_star(vect* tokens)
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
                    count = ustring_parse_dec(t1->content);
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
            for (size_t i = 0; i < metaast_parse_fn_len(metaast_single_unit_rule_funcs); i++)
            {
                if ((inner = metaast_single_unit_rule_funcs[i](tokens)))
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
metaast* metaast_parse_plus(vect* tokens)
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
                    count = ustring_parse_dec(t1->content);
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
            for (size_t i = 0; i < metaast_parse_fn_len(metaast_single_unit_rule_funcs); i++)
            {
                if ((inner = metaast_single_unit_rule_funcs[i](tokens)))
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
 * Attempt to match a capture group expression from the tokens list.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #capture = #expr #ws '.';
 */
metaast* metaast_parse_capture(vect* tokens)
{
    //check ends with a period
    size_t size = vect_size(tokens);
    if (size > 1)
    {
        metatoken* t0 = vect_get(tokens, size - 1)->data;
        if (t0->type == meta_period)
        {
            //store the tokens for the star expression, in case inner match fails
            obj* period_token_obj = vect_pop(tokens);

            //attempt to parse the inner expression
            metaast* inner = NULL;
            for (size_t i = 0; i < metaast_parse_fn_len(metaast_single_unit_rule_funcs); i++)
            {
                if ((inner = metaast_single_unit_rule_funcs[i](tokens)))
                {
                    //matched an option expression
                    obj_free(period_token_obj);
                    return new_metaast_unary_op_node(metaast_capture, inner);
                }
            }
            
            //restore the tokens vector with the question mark token
            vect_push(tokens, period_token_obj);
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
metaast* metaast_parse_option(vect* tokens)
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
            for (size_t i = 0; i < metaast_parse_fn_len(metaast_single_unit_rule_funcs); i++)
            {
                if ((inner = metaast_single_unit_rule_funcs[i](tokens)))
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
metaast* metaast_parse_count(vect* tokens)
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
            for (size_t i = 0; i < metaast_parse_fn_len(metaast_single_unit_rule_funcs); i++)
            {
                if ((inner = metaast_single_unit_rule_funcs[i](tokens)))
                {
                    //matched a count expression
                    metatoken* t = number_token_obj->data;
                    uint64_t count = ustring_parse_dec(t->content);
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
metaast* metaast_parse_compliment(vect* tokens)
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
            for (size_t i = 0; i < metaast_parse_fn_len(metaast_single_unit_rule_funcs); i++)
            {
                if ((inner = metaast_single_unit_rule_funcs[i](tokens)))
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
metaast* metaast_parse_cat(vect* tokens)
{
    // verify top level expression contains no lower precedence operators
    int idx = 0;
    int count = 0;
    while (idx < vect_size(tokens))
    {
        idx = metaast_scan_to_end_of_unit(tokens, idx);
        if (idx < 0) { return NULL; }
        
        //check if token at end of expression is a binary operator
        //all bin ops have lower precedence than cat, so we parse them first
        if (idx < vect_size(tokens))
        {
            metatoken* t = vect_get(tokens, idx)->data;
            if (metatoken_is_type_bin_op(t->type))            {
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
            idx = metaast_scan_to_end_of_unit(tokens, 0);
            vect* expr_tokens = new_vect(); //will be freed by metaast_parse_expr()
            for (int j = 0; j < idx; j++)
            {
                vect_enqueue(expr_tokens, vect_dequeue(tokens));
            }
            metaast* expr = metaast_parse_expr_restricted(expr_tokens, metaast_parse_cat);
            sequence[i] = expr;
        }

        vect_free(tokens); //should be empty
        return new_metaast_sequence_node(metaast_cat, count, sequence);
    }
    return NULL;
}


/**
 * Attempt to parse an or binary op expression from the list of tokens.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #or = (#expr #ws '|' #ws #expr) - #union;
 * #set #ws '|' #ws #set;
 */
metaast* metaast_parse_or(vect* tokens)
{
    return metaast_parse_binary_op(tokens, meta_vertical_bar);
}


/**
 * Attempt to match a group expression from the tokens list.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #group = '(' #ws #expr #ws ')';
 */
metaast* metaast_parse_group(vect* tokens)
{
    size_t size = vect_size(tokens);
    if (size > 2)
    {
        metatoken* t = vect_get(tokens, 0)->data;
        if (t->type == meta_left_parenthesis)
        {
            //if last token is matching parenthesis, then this is a group expression
            if (metaast_find_matching_pair(tokens, meta_left_parenthesis, 0) == size - 1)
            {
                obj_free(vect_dequeue(tokens)); //free left parenthesis
                obj_free(vect_pop(tokens));     //free right parenthesis
                
                return metaast_parse_expr(tokens);
            }
        }
    }
    return NULL;
}


/**
 * Attempt to parse a greaterthan binary op expression from the list of tokens.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #greaterthan = #expr #ws '>' #ws #expr;
 */
metaast* metaast_parse_greaterthan(vect* tokens)
{
    return metaast_parse_binary_op(tokens, meta_greater_than);
}


/**
 * Attempt to parse a lessthan binary op expression from the list of tokens.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #lessthan = #expr #ws '<' #ws #expr;
 */
metaast* metaast_parse_lessthan(vect* tokens)
{
    return metaast_parse_binary_op(tokens, meta_less_than);
}


/**
 * Attempt to parse a reject/diff binary op expression from the list of tokens.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #reject = (#expr #ws '-' #ws #expr) - #diff;
 * #diff = #set #ws '-' #ws #set;
 */
metaast* metaast_parse_reject(vect* tokens)
{
    return metaast_parse_binary_op(tokens, meta_minus);
}


/**
 * Attempt to parse a nofollow binary op expression from the list of tokens.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #nofollow = #expr #ws '/' #ws #expr;
 */
metaast* metaast_parse_nofollow(vect* tokens)
{
    return metaast_parse_binary_op(tokens, meta_forward_slash);
}

/**
 * Attempt to parse an intersect binary op expression from the list of tokens.
 * if matches, tokens will be freed, else returns NULL.
 * 
 * #intersect = #set #ws '&' #ws #set;
 */
metaast* metaast_parse_intersect(vect* tokens)
{
    return metaast_parse_binary_op(tokens, meta_ampersand);
}


/**
 * Process for matching a single binary operator expression.
 */
metaast* metaast_parse_binary_op(vect* tokens, metatoken_type optype)
{
    metaast_type asttype = metaast_get_token_ast_type(optype);

    // verify top level expression contains no lower precedence operators
    int idx = 0;
    const uint64_t op_precedence = metaast_get_type_precedence_level(asttype);
    
    //keep track of location of the `|` which will split the tokens list
    int split_idx = -1;

    while (idx < vect_size(tokens))
    {
        idx = metaast_scan_to_end_of_unit(tokens, idx);
        if (idx < 0) { return NULL; }
        
        //check if token at end of expression is a binary operator, and has equal or higher precedence than this one
        if (idx < vect_size(tokens))
        {
            metatoken* t = vect_get(tokens, idx)->data;
            if (metatoken_is_type_bin_op(t->type))
            {
                uint64_t level = metaast_get_type_precedence_level(metaast_get_token_ast_type(t->type));
                if (level == op_precedence)
                {
                    split_idx = idx;
                }
                else if (level > op_precedence)
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
        if (t->type == optype)
        {
            vect* left_tokens = new_vect();
            for (int i = 0; i < split_idx; i++)
            {
                vect_enqueue(left_tokens, vect_dequeue(tokens));
            }
            obj_free(vect_dequeue(tokens)); //free the split operator token

            metaast* left = metaast_parse_expr(left_tokens);
            if (left != NULL)
            {
                metaast* right = metaast_parse_expr(tokens);
                if (right != NULL)
                {
                    return new_metaast_binary_op_node(asttype, left, right);
                }
                else
                {
                    printf("ERROR: binary op right AST returned NULL\n");
                    metaast_parse_error();
                    metaast_free(left);
                    return NULL;
                }
            }
            else
            {
                printf("ERROR: binary op left AST returned NULL\n");
                metaast_parse_error();
                return NULL;
            }
        }
    }
    return NULL;
}


/**
 * Return the index of the matching pair token in the token string.
 * e.g. used to find a matching closing parenthesis, starting at an opening parenthesis.
 * Starts scanning from start_idx, which must be of type `left`.
 * Function is formulated so that left/right can be the same type.
 * 
 * If no match is found, returns -1
 */
int metaast_find_matching_pair(vect* tokens, metatoken_type left, size_t start_idx)
{
    metatoken_type right = metatoken_get_matching_pair_type(left);
    if (start_idx >= vect_size(tokens))
    {
        printf("BUG ERROR: specified start_idx past the end of tokens in find_matching_pair()\n");
        exit(1);
    }
    metatoken* t0 = vect_get(tokens, start_idx)->data;
    if (t0->type != left)
    {
        printf("BUG ERROR: expected token at start_idx to be of type %u but found %u\n", left, t0->type);
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
 * Determine if the given meta-ast type is a single unit
 */
bool metaast_is_type_single_unit(metaast_type type)
{
    switch (type)
    {
        case metaast_eps:
        case metaast_string:
        case metaast_charset:
        case metaast_identifier:
        case metaast_star:
        case metaast_plus:
        case metaast_option:
        case metaast_count:
        case metaast_compliment:
        case metaast_capture:
            return true;    
    
        default: return false;
    }
}


/**
 * Return the first index after the end of the expression starting at the given start index.
 * Returns -1 if unable to scan past expression.
 */
int metaast_scan_to_end_of_unit(vect* tokens, size_t start_idx)
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
            idx = metaast_find_matching_pair(tokens, t->type, start_idx);
            if (idx < 0) 
            { 
                printf("ERROR: unpaired left-most token: ");
                metatoken_repr(t);
                printf("\n");
                metaast_parse_error();
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
        metaast_parse_error();
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
        if (t->type == meta_period) { idx++; continue; }
        if (t->type == meta_question_mark) { idx++; continue; }
        if (t->type == meta_tilde) { idx++; continue; } 
        
        // non-suffix type encountered
        break;
    }
    return idx;
}


/**
 * Return the corresponding meta-ast type for the given separater token type.
 * type is expcted to be a binary operator separator.
 */
metaast_type metaast_get_token_ast_type(metatoken_type type)
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
uint64_t metaast_get_type_precedence_level(metaast_type type)
{
    switch (type)
    {
        /*metaast_group would be level 0*/
        /*technically not operators*/
        case metaast_identifier:
        case metaast_charset:
        case metaast_string:
        case metaast_caseless:
        case metaast_eps:
            return 0;

        case metaast_star:
        case metaast_plus:
        case metaast_count:
        case metaast_capture:
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
 * Free all allocated resources in the metaast.
 */
void metaast_free(metaast* ast)
{

    switch (ast->type)
    {
        // free specific inner components of nodes
        
        case metaast_string:
        case metaast_caseless:
        case metaast_identifier:
        {
            metaast_string_node* node = ast->node;
            free(node->string);
            break;
        }
        
        case metaast_charset:
        {
            metaast_charset_node* node = ast->node;
            charset_free(node->c);
            break;
        }
        
        case metaast_star:
        case metaast_plus:
        case metaast_count:
        {
            metaast_repeat_node* node = ast->node;
            metaast_free(node->inner);
            break;
        }
        
        case metaast_option:
        case metaast_compliment:
        case metaast_capture:
        {
            metaast_unary_op_node* node = ast->node;
            metaast_free(node->inner);
            break;
        }
        
        case metaast_or:
        case metaast_greaterthan:
        case metaast_lessthan:
        case metaast_reject:
        case metaast_nofollow:
        case metaast_intersect:
        {
            metaast_binary_op_node* node = ast->node;
            metaast_free(node->left);
            metaast_free(node->right);
            break;
        }
        
        case metaast_cat:
        {
            metaast_sequence_node* node = ast->node;
            for (size_t i = 0; i < node->size; i++)
            {
                metaast_free(node->sequence[i]);
            }
            free(node->sequence);
            break;
        }

        //free container only
        case metaast_eps: break;
    }

    //NULL indicates eps node, which allocated no node
    if (ast->node != NULL)
    { 
        free(ast->node); 
    }
    
    free(ast);
}


/**
 * Sequentially attempt to combine constant expressions in the meta-ast.
 * Returns `true` if folding occurred, else `false`.
 * Repeat until returns `false` to ensure all constants are folded. 
 */
bool metaast_fold_constant(metaast** ast_ptr)
{
    if (metaast_fold_charsets(ast_ptr)) { return true; }
    if (metaast_fold_strings(ast_ptr)) { return true; }
    /*
        any other constant folding here...
        e.g. if something is idempotent, e.g. if option node's inner is option, remove a layer
        
    */


    return false;
}


/**
 * Runs a single pass of combining charset expressions in the meta-ast.
 * This includes charset union, intersect, diff, and compliment.
 * Returns `true` if any folding occurred, else `false`.
 * Repeat until returns `false` to ensure all charsets are folded.
 */
bool metaast_fold_charsets(metaast** ast_ptr)
{
    metaast* ast = *ast_ptr;

    //recursively descend down the tree looking for charset expressions to fold
    switch (ast->type)
    {
        //single expressions that can't be reduced
        case metaast_eps:
        case metaast_string:
        case metaast_caseless:
        case metaast_identifier:
        case metaast_charset:
            return false;

        //non-charset operator nodes that we recurse further into
        case metaast_star:
        case metaast_plus:
        case metaast_count:
        {
            metaast_repeat_node* node = ast->node;
            return metaast_fold_charsets(&node->inner);
        }
        case metaast_option:
        case metaast_capture:
        {
            metaast_unary_op_node* node = ast->node;
            return metaast_fold_charsets(&node->inner);
        }
        case metaast_greaterthan:
        case metaast_lessthan:
        case metaast_nofollow:
        {
            metaast_binary_op_node* node = ast->node;
            bool left = metaast_fold_charsets(&node->left);
            bool right = metaast_fold_charsets(&node->right);
            return left || right;
        }
        case metaast_cat:
        {
            bool folded = false;
            metaast_sequence_node* node = ast->node;
            for (size_t i = 0; i < node->size; i++)
            {
                folded = metaast_fold_charsets(&node->sequence[i]) || folded;
            }
            return folded;
        }

        //possible charset operator nodes (but may not be charset at top level)
        case metaast_compliment:
        {
            metaast_unary_op_node* node = ast->node;
            if (node->inner->type == metaast_charset)
            {
                metaast_charset_node* inner_node = node->inner->node;
                
                //apply the compliment operator
                charset* compliment = charset_compliment(inner_node->c);

                //free the old node and replace with the new node
                metaast_free(ast);
                *ast_ptr = new_metaast_charset_node(metaast_charset, compliment);

                return true;
            }
            else
            {   
                //normal recurse further down the tree
                return metaast_fold_charsets(&node->inner);
            }
        }
        case metaast_intersect:
        case metaast_or:
        case metaast_reject:
        {
            metaast_binary_op_node* node = ast->node;
            if (node->left->type == metaast_charset && node->right->type == metaast_charset)
            {
                metaast_charset_node* left_node = node->left->node;
                metaast_charset_node* right_node = node->right->node;
                charset* result;
                
                //apply the specific operator to the left and right charset
                if (ast->type == metaast_intersect) { result = charset_intersect(left_node->c, right_node->c); }
                else if (ast->type == metaast_or) { result = charset_union(left_node->c, right_node->c); }
                else /*(ast->type == metaast_reject)*/ { result = charset_diff(left_node->c, right_node->c); }

                //free the old node and replace with a new charset node
                metaast_free(ast);
                *ast_ptr = new_metaast_charset_node(metaast_charset, result);
                
                return true;
            }
            else
            {
                //normal recurse further down the tree
                bool left = metaast_fold_charsets(&node->left);
                bool right = metaast_fold_charsets(&node->right);
                return left || right;
            }
        }
    }
}




/**
 * Runs a single pass of combining string expressions in the meta-ast.
 * This is mainly for cat of sequential strings (or charsets of size 1).
 * Returns `true` if any folding occurred, else `false`.
 * Repeat until returns `false` to ensure all strings are folded.
 */
bool metaast_fold_strings(metaast** ast_ptr)
{
    //things to fold:
    //- strings contained within cat sequences
    //- cat sequences contained within cat sequences
    
    return false;
}



void metaast_type_repr(metaast_type type)
{
    #define printenum(A) case A: printf(&#A[8]); break; //+8 to skip "metaast_" in enum name

    switch (type)
    {
        printenum(metaast_eps)
        printenum(metaast_capture)
        printenum(metaast_string)
        printenum(metaast_caseless)
        printenum(metaast_star)
        printenum(metaast_plus)
        printenum(metaast_option)
        printenum(metaast_count)
        printenum(metaast_cat)
        printenum(metaast_or)
        printenum(metaast_greaterthan)
        printenum(metaast_lessthan)
        printenum(metaast_reject)
        printenum(metaast_nofollow)
        printenum(metaast_identifier)
        printenum(metaast_charset)
        printenum(metaast_compliment)
        printenum(metaast_intersect)
    }   
}


/**
 * Print out a string for the given meta-ast
 */
void metaast_str(metaast* ast) { metaast_str_inner(ast, METAAST_NO_PARENT_TYPE); }


/**
 * Inner recursive function for printing out the meta-ast string.
 */
void metaast_str_inner(metaast* ast, metaast_type parent)
{
    //wrap a print statement in left/right symbols. 
    //this version allows for alternate on condition == false
    #define wrap_print_alt(condition, inner, alt, left_str, right_str)   \
    if (condition)                                              \
    {                                                           \
        printf(left_str); inner; printf(right_str);             \
    }                                                           \
    else                                                        \
    {                                                           \
        alt;                                                    \
    }

    //normal version where the same inner is either wrapped or not
    #define wrap_print(condition, inner, left_str, right_str)   \
        wrap_print_alt(condition, inner, inner, left_str, right_str)

    switch (ast->type)
    {

        case metaast_string:
        case metaast_caseless:
        case metaast_identifier:
        {
            metaast_string_node* node = ast->node;
            //if string, wrap in quotes, else if caseless, wrap in brackets, else print without
            wrap_print_alt(ast->type == metaast_string,
                ustring_str(node->string),
                wrap_print(ast->type == metaast_caseless, ustring_str(node->string), "{", "}"),
                "\"", "\""
            )
            // char* left = ast->type == metaast_string ? "\"" : "{";
            // char* right = ast->type == metaast_string ? "\"" : "}";
            // wrap_print(ast->type == metaast_string, ustring_str(node->string), left, right)
            break;
        }
        
        case metaast_charset:
        {
            metaast_charset_node* node = ast->node;
            
            //print special character for the anyset
            if (charset_is_anyset(node->c))
                put_unicode(0x3BE);
            else
                charset_str(node->c);
            break;
        }
        
        case metaast_star:
        case metaast_plus:
        case metaast_count:
        {
            metaast_repeat_node* node = ast->node;
            
            //check if inner needs to be wrapped in parenthesis
            wrap_print(metaast_str_inner_check_needs_parenthesis(ast->type, node->inner->type), 
                metaast_str_inner(node->inner, ast->type),
                "(", ")"
            )

            //repeat symbol(s) after the expression
            if (ast->type == metaast_star)
            {
                //star shows count iff > 0
                if (node->count > 0) { printf("%"PRIu64, node->count); }
                printf("*");
            }
            else if (ast->type == metaast_plus)
            {
                //plus shows count iff > 1
                if (node->count > 1) { printf("%"PRIu64, node->count); }
                printf("+");
            }
            else
            {
                printf("%"PRIu64, node->count);
            }
            break;
        }
        
        case metaast_option:
        case metaast_compliment:
        case metaast_capture:
        {
            metaast_unary_op_node* node = ast->node;
            
            //check if the inner expression needs to be wrapped in parenthesis.
            //alternatively capture nodes are wrapped in their own brackets
            wrap_print(metaast_str_inner_check_needs_parenthesis(ast->type, node->inner->type), 
                metaast_str_inner(node->inner, ast->type), 
                "(", ")"
            )
            
            // wrap_print_alt(metaast_str_inner_check_needs_parenthesis(ast->type, node->inner->type),
            //     metaast_str_inner(node->inner, ast->type),
            //     wrap_print(ast->type == metaast_capture, metaast_str_inner(node->inner, ast->type), "{", "}"),
            //     "(", ")"
            // )
            if (ast->type == metaast_option) { printf("?"); }
            else if (ast->type == metaast_compliment) { printf("~"); }
            else if (ast->type == metaast_capture) { printf("."); }
            break;
        }
        
        case metaast_or:
        case metaast_greaterthan:
        case metaast_lessthan:
        case metaast_reject:
        case metaast_nofollow:
        case metaast_intersect:
        {
            metaast_binary_op_node* node = ast->node;

            //print left node (wrap in parenthesis if needed)
            wrap_print(metaast_str_inner_check_needs_parenthesis(ast->type, node->left->type),
                metaast_str_inner(node->left, ast->type),
                "(", ")"
            )

            //print operator
            if (ast->type == metaast_or) printf(" | ");
            else if (ast->type == metaast_greaterthan) printf(" > ");
            else if (ast->type == metaast_lessthan) printf(" < ");
            else if (ast->type == metaast_reject) printf(" - ");
            else if (ast->type == metaast_nofollow) printf(" / ");
            else if (ast->type == metaast_intersect) printf(" & ");
            
            //print right node (wrap in parenthesis if needed)
            wrap_print(metaast_str_inner_check_needs_parenthesis(ast->type, node->right->type),
                metaast_str_inner(node->right, ast->type),
                "(", ")"
            )

            break;
        }
        
        case metaast_cat:
        {
            metaast_sequence_node* node = ast->node;
            
            //print the cat sequence, and wrap in parenthesis if needed
            wrap_print(
                metaast_str_inner_check_needs_parenthesis(ast->type, metaast_cat),
                for (size_t i = 0; i < node->size; i++)
                {
                    metaast* inner = node->sequence[i];
                    
                    //check if the inner expression needs to be wrapped in parenthesis
                    wrap_print(metaast_str_inner_check_needs_parenthesis(metaast_cat, inner->type),
                        metaast_str_inner(inner, ast->type),
                        "(", ")"
                    )

                    //print a space between elements (skip last since no elements follow)
                    if (i < node->size - 1) { printf(" "); }
                },
                "(", ")"
            )
            break;
        }

        //free container only
        case metaast_eps:
        {
            put_unicode(0x03F5);
            break;
        }
    }
}

bool metaast_str_inner_check_needs_parenthesis(metaast_type parent, metaast_type inner)
{
    //top level doesn't need parenthesis
    if (parent == METAAST_NO_PARENT_TYPE) return false;
    
    //special cases that need them
    if ((parent == metaast_star || parent == metaast_plus) && inner == metaast_count) return true;
    if ((parent == metaast_option || parent == metaast_compliment) && inner == metaast_identifier) return true;
    if (parent == metaast_count && (inner == metaast_count || inner == metaast_identifier)) return true;

    if (metaast_is_type_single_unit(inner)) return false;
    if (metaast_get_type_precedence_level(parent) >= metaast_get_type_precedence_level(inner)) return false;
    return true;
}


/**
 * Print out a representation of the given meta-ast
 */
void metaast_repr(metaast* ast) { metaast_repr_inner(ast, 0); }


/**
 * Inner recursive function for printing out the meta-ast representation.
 */
void metaast_repr_inner(metaast* ast, int level)
{
    repeat_str("  ", level);  //print level # tabs
    metaast_type_repr(ast->type);
    switch (ast->type)
    {

        case metaast_string:
        case metaast_caseless:
        case metaast_identifier:
        {
            metaast_string_node* node = ast->node;
            printf("(`"); ustring_str(node->string); printf("`)\n");
            break;
        }
        
        case metaast_charset:
        {
            metaast_charset_node* node = ast->node;
            charset_str(node->c); printf("\n");
            break;
        }
        
        case metaast_star:
        case metaast_plus:
        case metaast_count:
        {
            metaast_repeat_node* node = ast->node;
            printf("{\n");
            repeat_str("  ", level + 1); printf("count=%"PRIu64"\n", node->count);
            metaast_repr_inner(node->inner, level + 1);
            repeat_str("  ", level); printf("}\n");
            break;
        }
        
        case metaast_option:
        case metaast_compliment:
        case metaast_capture:
        {
            metaast_unary_op_node* node = ast->node;
            printf("{\n");
            metaast_repr_inner(node->inner, level + 1);
            repeat_str("  ", level); printf("}\n");
            break;
        }
        
        case metaast_or:
        case metaast_greaterthan:
        case metaast_lessthan:
        case metaast_reject:
        case metaast_nofollow:
        case metaast_intersect:
        {
            metaast_binary_op_node* node = ast->node;
            printf("{\n");
            metaast_repr_inner(node->left, level + 1);
            metaast_repr_inner(node->right, level + 1);
            repeat_str("  ", level); printf("}\n");
            break;
        }
        
        case metaast_cat:
        {
            metaast_sequence_node* node = ast->node;
            printf("{\n");
            for (size_t i = 0; i < node->size; i++)
            {
                metaast_repr_inner(node->sequence[i], level + 1);
            }
            repeat_str("  ", level); printf("}\n");
            break;
        }

        //free container only
        case metaast_eps:
        {
            printf("("); put_unicode(0x03F5); printf(")\n");
            break;
        }
    }
}

#endif