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
#include "ustring.h"

#define NULL_SYMBOL_INDEX (uint64_t)-1


/**
 * Global data structures used to manage all meta grammar rules.
 * body vects are a sequence of uint indices refering to either heads or charsets.
 * heads are referred to by odd indices, while charsets are referred to by even indices.
 * i.e. real_head_idx = head_idx / 2 <=> real_head_idx * 2 + 1 = head_idx
 * i.e. real_body_idx = body_idx / 2 <=> real_body_idx * 2 + 1 = body_idx
 */
// dict* metaparser_heads;     //map of all production nonterminals to a set of corresponding bodies 
// dict* metaparser_bodies;    //map of all production strings to a set of all corresponding heads
// set* metaparser_charsets;   //set of all terminals (i.e. charsets) in all productions

dict* metaparser_ast_cache; //map from metaast to identifiers for the sentence that matches that ast

// vect* metaparser_heads;
// vect* metaparser_bodies;

set* metaparser_symbols;
set* metaparser_bodies;
vect* metaparser_production_heads;
vect* metaparser_production_bodies;
uint64_t metaparser_eps_body_idx = NULL_SYMBOL_INDEX;



/**
 * Initialize all global data structures used by metaparser.
 */
void initialize_metaparser()
{
    metaparser_symbols = new_set();
    metaparser_bodies = new_set();
    metaparser_production_heads = new_vect();
    metaparser_production_bodies = new_vect();
}


/**
 * Free up all global data structures used by metaparser.
 */
void release_metaparser()
{
    set_free(metaparser_symbols);
    set_free(metaparser_bodies);
    vect_free(metaparser_production_heads);
    vect_free(metaparser_production_bodies);
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
uint64_t metaparser_get_anonymous_rule_head()
{
    //determine the string width of the number
    size_t width = ceil(log10(metaparser_anonymous_rule_count + 1));
    width += 4; //room for `#__` at start and null terminator at end
    
    //create a normal char* that will be the head
    char* num_str = malloc(width * sizeof(char));
    sprintf(num_str, "#__%"PRIu64, metaparser_anonymous_rule_count);

    //convert to unicode string (wrapped in obj*), and cleanup char* version
    obj* head = new_ustring_obj(ustring_utf8_substr(num_str, 0, width-1));
    free(num_str);

    //increment the counter
    metaparser_anonymous_rule_count++;
    
    //insert head into metaparser_symbols, and return its index
    uint64_t head_idx = metaparser_add_symbol(head);

    return head_idx;
}


/**
 * Try to scan for a rule in the current list of tokens. 
 * Returns `true` if a rule was successfully parsed.
 * Assumes that tokens may contain comments or whitespace.
 */
bool parse_next_meta_rule(vect* tokens)
{
    //check for head, equals sign, and semicolon
    if (!metaparser_is_valid_rule(tokens)) { return false; }

    //construct head and body for the rule
    obj* head = metaparser_get_rule_head(tokens);
    vect* body_tokens = metaparser_get_rule_body(tokens);
    metaast* body_ast = metaast_parse_expr(body_tokens);

    //failed to parse body into ast
    if (body_ast == NULL)
    {
        vect_free(body_tokens);
        obj_free(head);
        return false;
    }

    //reduce any constant expressions in the ast (e.g. charset operations)
    while (metaast_fold_constant(&body_ast));

    //recursively convert to sentences + insert into grammar table

    uint64_t head_idx = metaparser_add_symbol(head);
    metaparser_insert_rule_ast(head_idx, body_ast); 
    return true;
}


/**
 * 
 */
//TODO->convert this to indexing into the symbols & bodies sets
void print_grammar_tables()
{
    //print out all symbols
    printf("symbols:\n"); 
    for (uint64_t i = 0; i < set_size(metaparser_symbols); i++)
    {
        printf("%"PRIu64": ", i); obj_print(metaparser_get_symbol(i)); printf("\n");
    }

    //print out the table of rules TODO->have this directly print out the whole head/production properly instead of printing out the indices
    if (vect_size(metaparser_production_bodies) != vect_size(metaparser_production_heads)){ printf("ERROR heads and bodies should be the same size!\n"); exit(1); }
    for (size_t i = 0; i < vect_size(metaparser_production_bodies); i++)
    {
        obj* head = vect_get(metaparser_production_heads, i);
        obj_print(head);
        printf(" = ");
        vect* sentence = vect_get(metaparser_production_bodies, i)->data;
        for (size_t j = 0; j < vect_size(sentence); j++)
        {
            obj_print(vect_get(sentence, j));
            if (j < vect_size(sentence) - 1) { printf(" "); }
        }
        printf("\n");
    }
}

/**
 * Verify that the stream of tokens is valid syntax for a rule
 * #rule = #identifier #ws '=' #ws #expr #ws ';';
 */
bool metaparser_is_valid_rule(vect* tokens)
{
    //shortest rule is 4 tokens: #id '=' <expr> ;
    if (vect_size(tokens) == 0) 
    { 
        printf("ERROR: cannot parse rule from empty tokens list\n");
        return false; 
    }
    
    //scan for head
    int i = metatoken_get_next_real_token(tokens, 0);
    if (i < 0 || !metatoken_is_i_of_type(tokens, i, hashtag))
    {
        printf("ERROR: no identifier found at start of meta rule\n");
        return false;
    }
    
    //scan for equals sign
    i = metatoken_get_next_real_token(tokens, i+1);
    if (i < 0 || !metatoken_is_i_of_type(tokens, i, meta_equals_sign))
    {
        printf("ERROR: no equals sign found following identifier in meta rule\n");
        return false;
    }

    //scan for ending semicolon
    i = metatoken_get_next_token_of_type(tokens, meta_semicolon, i+1);
    if (i < 0)
    {
        printf("ERROR: no semicolon found to close meta rule\n");
        return false;
    }

    return true;
}


/**
 * Return the identifier starting the meta rule.
 * Frees any whitespace/comment tokens before the identifier.
 * Expects metaparser_is_valid_rule() to have been called first.
 */
obj* metaparser_get_rule_head(vect* tokens)
{
    while (vect_size(tokens) > 0)
    {
        // obj* t_obj = vect_dequeue(tokens);
        // metatoken* t = t_obj->data;
        metatoken* t = obj_free_keep_inner(vect_dequeue(tokens), MetaToken_t);
        if (t->type == whitespace || t->type == comment)
        {
            metatoken_free(t);
        }
        else if (t->type == hashtag)
        {
            obj* head = new_ustring_obj(ustring_clone(t->content));
            metatoken_free(t);
            return head;
        }
        else //this should never occur if metaparser_is_valid_rule() was called first
        {
            printf("BUG ERROR: expecting identifier at start of rule, when found: "); 
            metatoken_repr(t); 
            printf("\nEnsure metaparser_is_valid_rule() was called before this function\n");
            exit(1);
        }
    }
    printf("BUG ERROR: tokens list contains no real tokens\n");
    printf("Ensure metaparser_is_valid_rule() was called before this function\n");
    exit(1);
}


/**
 * returns the body tokens for the meta rule.
 * Frees any whitespace/comment tokens before the identifier.
 * Expects metaparser_is_valid_rule(), and then metaparser_get_rule_head()
 * to have been called first.
 */
vect* metaparser_get_rule_body(vect* tokens)
{
    vect* body_tokens = new_vect();
    while (vect_size(tokens) > 0)
    {
        obj* t_obj = vect_dequeue(tokens);
        metatoken* t = t_obj->data;

        //skip all whitespace
        if (t->type == whitespace || t->type == comment)
        {
            obj_free(t_obj);
        }
        //semicolon means finished collecting body tokens
        else if (t->type == meta_semicolon)
        {
            obj_free(vect_dequeue(body_tokens));    // equals sign at start
            obj_free(t_obj);                        // semicolon
            return body_tokens;
        }
        else 
        {
            vect_enqueue(body_tokens, t_obj);
        }
    }
    printf("BUG ERROR: expected semicolon at end of rule\n");
    printf("Ensure metaparser_is_valid_rule() was called before this function\n");
    exit(1);
}


/**
 * Recursively construct the grammar symbol string from the given a meta-ast.
 * all heads, bodies, and charsets are inserted into the metaparser grammar table.
 * `head` may optionally be NULL, (e.g. for when the parser is handling anonymous expressions)
 * in which case the compiler will come up with a name for the rule.
 * Returns the identifier for the rule inserted. Note that the returned identifier is owned by the 
 * grammar table, and must be copied if it is to be used by another process (e.g. other rule sentences).
 */


//FOR NOW WE'LL JUST PRINT OUT WHAT WE WOULD DO...
uint64_t metaparser_insert_rule_ast(uint64_t head_idx, metaast* body_ast)
{   
    // //check if an equivalent ast has already been inserted into the grammar table
    // obj* body_ast_obj = new_metaast_obj(body_ast);
    // if (dict_contains(metaparser_ast_cache, body_ast_obj))
    // {
    //     obj* body_id = dict_get(metaparser_ast_cache, body_ast_obj);
    //     vect* sentence = new_vect();
    //     vect_append(sentence, obj_copy(body_id));
    //     vect_append(bodies, new_vect_obj(sentence));
    // }
    // else

    switch (body_ast->type)
    {
        // Base case (non-recursive) rules
        case metaast_eps:
        {
            //crete an anonymous head if it wasn't provided
            head_idx = head_idx == NULL_SYMBOL_INDEX ? metaparser_get_anonymous_rule_head() : head_idx;

            //create a production for the head index pointing to the epsilon body index
            metaparser_add_production(head_idx, metaparser_get_eps_body_idx());
            break;
        }
        case metaast_identifier:
        {
            //get the symbol index of the identifier
            metaast_string_node* node = body_ast->node;
            obj* nonterminal = new_ustring_obj(ustring_clone(node->string));
            uint64_t nonterminal_idx = metaparser_add_symbol(nonterminal);
            
            //if head is defined, then create a whole production with a sentence containing just the identifier
            //otherwise this is an inner expression reference to the identifier where we can skip the redundant sentence
            if (head_idx != NULL_SYMBOL_INDEX)
            {
                //create a sentence with the identifier in it
                vect* sentence = new_vect();
                vect_append(sentence, new_uint_obj(nonterminal_idx));

                //add the sentence to the grammar
                uint64_t body_idx = metaparser_add_body(sentence);
                
                //insert the production
                metaparser_add_production(head_idx, body_idx);
            }
            else
            {
                //assign this identifier the null head
                head_idx = nonterminal_idx;
            }
            break;
        }
        case metaast_charset:
        {
            //crete an anonymous head if it wasn't provided
            head_idx = head_idx == NULL_SYMBOL_INDEX ? metaparser_get_anonymous_rule_head() : head_idx;

            //create a sentence containing just the charset
            vect* sentence = new_vect();

            //insert the terminal into the sentence
            metaast_charset_node* node = body_ast->node;
            obj* terminal = new_charset_obj(charset_clone(node->c));
            uint64_t terminal_idx = metaparser_add_symbol(terminal);
            vect_append(sentence, new_uint_obj(terminal_idx));

            //add the sentence to the grammar
            uint64_t body_idx = metaparser_add_body(sentence);
            
            //insert the production into the grammar
            metaparser_add_production(head_idx, body_idx);
            break;
        }
        case metaast_string:
        {
            //crete an anonymous head if it wasn't provided
            head_idx = head_idx == NULL_SYMBOL_INDEX ? metaparser_get_anonymous_rule_head() : head_idx;

            //create a sentence for the string
            vect* sentence = new_vect();

            //insert each character from the string into the sentence
            metaast_string_node* node = body_ast->node;
            uint32_t* s = node->string;
            uint32_t c;
            while ((c = *s++))
            {
                obj* cs_obj = new_charset_obj(new_charset());
                charset_add_char(cs_obj->data, c);
                uint64_t terminal_idx = metaparser_add_symbol(cs_obj);
                vect_append(sentence, new_uint_obj(terminal_idx));
            }
            
            //insert the sentence into the bodies set
            uint64_t body_idx = metaparser_add_body(sentence);

            //push this sentence to the list of all sentences for this rule
            metaparser_add_production(head_idx, body_idx);
            break;
        }

        // Recursive rules that need to compute the nested sentences
        case metaast_star:
        case metaast_plus:
        {
            //crete an anonymous head if it wasn't provided
            head_idx = head_idx == NULL_SYMBOL_INDEX ? metaparser_get_anonymous_rule_head() : head_idx;

            metaast_repeat_node* node = body_ast->node;
            
            //get the identifier for the inner node
            uint64_t inner_head_idx = metaparser_get_symbol_or_anonymous(head_idx, body_ast->type, node->inner);

            //build the sentence
            if (node->count == 0 || (node->count == 1 && body_ast->type == metaast_star))
            {
                //simple star
                //#head = #A* | (#A)0* | (#A)1* | (#A)0+ =>
                //  #head = #A #head;
                //  #head = ϵ;

                //#head = #A #head
                vect* sentence0 = new_vect();
                vect_append(sentence0, new_uint_obj(inner_head_idx));
                vect_append(sentence0, new_uint_obj(head_idx));
                uint64_t sentence0_idx = metaparser_add_body(sentence0);
                metaparser_add_production(head_idx, sentence0_idx);

                //#head = ϵ
                metaparser_add_production(head_idx, metaparser_get_eps_body_idx());
            }
            else
            {
                //complex plus
                //#head = (#A)N+ =>
                //  #__0 = #A #__0;
                //  #__0 = ϵ;
                //  #head = #A #A #A ... #A #__0; //... N times
                
                //complex star
                //#head = (#A)N* =>
                //  #__0 = #A #__0;
                //  #__0 = ϵ;
                //  #head = #A #A #A ... #A #__0; //... N times
                //  #head = ϵ;

                //  #__0 = #A #__0
                uint64_t anonymous0_idx = metaparser_get_anonymous_rule_head();
                vect* sentence0 = new_vect();
                vect_append(sentence0, new_uint_obj(inner_head_idx));
                vect_append(sentence0, new_uint_obj(anonymous0_idx));
                uint64_t sentence0_idx = metaparser_add_body(sentence0);
                metaparser_add_production(anonymous0_idx, sentence0_idx);

                //  #__0 = ϵ;
                metaparser_add_production(anonymous0_idx, metaparser_get_eps_body_idx());

                //  #head = #A #A #A ... #A #__0; //... N times
                vect* sentence2 = new_vect();
                for (int i = 0; i < node->count; i++)
                {
                    vect_append(sentence2, new_uint_obj(inner_head_idx));
                }
                vect_append(sentence2, new_uint_obj(anonymous0_idx));
                uint64_t sentence2_idx = metaparser_add_body(sentence2);
                metaparser_add_production(head_idx, sentence2_idx);

                //convert from plus to star by making the last rule optional
                if (body_ast->type == metaast_star)
                {
                    //  #head = ϵ;
                    metaparser_add_production(head_idx, metaparser_get_eps_body_idx());
                }
            }
            break;
        }
        case metaast_count:
        {
            //crete an anonymous head if it wasn't provided
            head_idx = head_idx == NULL_SYMBOL_INDEX ? metaparser_get_anonymous_rule_head() : head_idx;

            metaast_repeat_node* node = body_ast->node;
            uint64_t inner_head_idx = metaparser_get_symbol_or_anonymous(head_idx, body_ast->type, node->inner);

            if (node->count == 0)
            {
                //#head = (#A)0 => ϵ;  //this is probably a typo on the user's part...
                printf("WARNING: ("); metaast_str(body_ast); printf(")0 is equivalent to ϵ\n"
                "Did you mean `("); metaast_str(body_ast); printf(")*`"
                " or `("); metaast_str(body_ast); printf(")+`"
                " or `("); metaast_str(body_ast); printf(")N` where N > 1 ?\n");
                metaparser_add_production(head_idx, metaparser_get_eps_body_idx());
            }
            else
            {
                //#head = (#A)N =>
                //  #head = #A #A #A ... #A; //... N times
                vect* sentence = new_vect();
                for (int i = 0; i < node->count; i++)
                {
                    vect_append(sentence, new_uint_obj(inner_head_idx));
                }
                uint64_t body_idx = metaparser_add_body(sentence);
                metaparser_add_production(head_idx, body_idx);
            }
            break;
        }
        case metaast_option:
        {
            //crete an anonymous head if it wasn't provided
            head_idx = head_idx == NULL_SYMBOL_INDEX ? metaparser_get_anonymous_rule_head() : head_idx;

            metaast_unary_op_node* node = body_ast->node;
            uint64_t inner_head_idx = metaparser_get_symbol_or_anonymous(head_idx, body_ast->type, node->inner);

            //#head = #A ? =>
            //  #head = #A
            //  #head = ϵ
            
            //  #head = #A
            vect* sentence0 = new_vect();
            vect_append(sentence0, new_uint_obj(inner_head_idx));
            uint64_t sentence0_idx = metaparser_add_body(sentence0);
            metaparser_add_production(head_idx, sentence0_idx);

            //  #head = ϵ
            metaparser_add_production(head_idx, metaparser_get_eps_body_idx());

            break;
        }
        case metaast_cat:
        {
            //crete an anonymous head if it wasn't provided
            head_idx = head_idx == NULL_SYMBOL_INDEX ? metaparser_get_anonymous_rule_head() : head_idx;

            //#head = #A #B => #A #B  //cat is already in CFG format. TODO->handle cat with strings/charsets/identifiers/epsilon...
            metaast_sequence_node* node = body_ast->node;
            vect* sentence = new_vect();
            for (size_t i = 0; i < node->size; i++)
            {
                metaast* inner_i_ast = node->sequence[i];
                switch (inner_i_ast->type)
                {
                    //insert each char of the string into the parent sentence
                    case metaast_string: 
                    { 
                        metaast_string_node* inner_i_node = inner_i_ast->node;
                        uint32_t* s = inner_i_node->string;
                        uint32_t c;
                        while ((c = *s++))
                        {
                            obj* cs_obj = new_charset_obj(new_charset());
                            charset_add_char(cs_obj->data, c);
                            uint64_t terminal_idx = metaparser_add_symbol(cs_obj);
                            vect_append(sentence, new_uint_obj(terminal_idx));
                        }
                        break;
                    }

                    //insert the charset into the parent sentence
                    case metaast_charset: 
                    {
                        metaast_charset_node* inner_i_node = inner_i_ast->node;
                        obj* cs_obj = new_charset_obj(charset_clone(inner_i_node->c));
                        uint64_t terminal_idx = metaparser_add_symbol(cs_obj);
                        vect_append(sentence, new_uint_obj(terminal_idx));
                        break;
                    }
                    
                    //insert the identifier into the parent sentence
                    case metaast_identifier:
                    {
                        metaast_string_node* inner_i_node = inner_i_ast->node;
                        obj* identifier = new_ustring_obj(ustring_clone(inner_i_node->string));
                        uint64_t identifier_idx = metaparser_add_symbol(identifier);
                        vect_append(sentence, new_uint_obj(identifier_idx));
                        break;
                    }
                    
                    //literal epsilons are skipped in a cat node
                    case metaast_eps: { break; }
                    
                    //all other types of ast are represented by an anonymous identifier
                    default: 
                    {
                        uint64_t head_i_idx = metaparser_get_symbol_or_anonymous(head_idx, body_ast->type, node->sequence[i]);
                        vect_append(sentence, new_uint_obj(head_i_idx));
                        break;
                    }
                }

                
            }
            uint64_t body_idx = metaparser_add_body(sentence);
            metaparser_add_production(head_idx, body_idx);
            break;
        }
        case metaast_or:
        {
            //crete an anonymous head if it wasn't provided
            head_idx = head_idx == NULL_SYMBOL_INDEX ? metaparser_get_anonymous_rule_head() : head_idx;

            //#rule = #A | #B =>
            //  #rule = #A
            //  #rule = #B

            metaast_binary_op_node* node = body_ast->node;
            uint64_t left_head_idx = metaparser_get_symbol_or_anonymous(head_idx, body_ast->type, node->left);
            uint64_t right_head_idx = metaparser_get_symbol_or_anonymous(head_idx, body_ast->type, node->right);

            //only insert the heads into the production if they are not also or nodes
            //or nodes return the parent head, which we don't want to insert into the body for nested or nodes
            if (node->left->type != metaast_or)
            {
                vect* sentence0 = new_vect();
                vect_append(sentence0, new_uint_obj(left_head_idx));
                uint64_t sentence0_idx = metaparser_add_body(sentence0);
                metaparser_add_production(head_idx, sentence0_idx);
            }
            if (node->right->type != metaast_or)
            {
                vect* sentence1 = new_vect();
                vect_append(sentence1, new_uint_obj(right_head_idx));
                uint64_t sentence1_idx = metaparser_add_body(sentence1);
                metaparser_add_production(head_idx, sentence1_idx);
            }
            break;
        }
        
        
        //TODO->filters/other extensions of the parser
        case metaast_greaterthan:
        case metaast_lessthan:
        case metaast_reject:
        case metaast_nofollow:
        case metaast_capture:
            printf("ERROR: < > - / and {} have not yet been implemented\n");
            break;

        //ERROR->should not allow, or come up with semantics for
        //e.g. (#A)~ => ξ* - #A
        //should be an error since this only makes sense for charsets
        case metaast_compliment:
        case metaast_intersect:
            printf("ERROR: compliment/intersect is only applicable to charsets. There are (currently) no semantics for what compliment means for a regular grammar production");
            break;

    }

    return head_idx;
}


/**
 * For a nested ast rule, if the nested rule is an identifier/charset,
 * return that, otherwise return the generated anonymous name of the nested rule.
 * If ast is not a symbol node (i.e. identifier or charset), then the ast will be inserted
 * into the grammar tables.
 */
uint64_t metaparser_get_symbol_or_anonymous(uint64_t parent_head_idx, metaast_type parent_type, metaast* ast)
{
    //TODO->can we take this one out too? also handled by the general case...
    if (ast->type == metaast_identifier)
    {    
        metaast_string_node* node = ast->node;
        obj* nonterminal = new_ustring_obj(ustring_clone(node->string));
        return metaparser_add_symbol(nonterminal);
    }
    //TODO->can we take this one out? shouldn't it be handled correctly by the general case?
    else if (ast->type == metaast_charset)
    {
        metaast_charset_node* node = ast->node;
        obj* terminal = new_charset_obj(charset_clone(node->c));
        return metaparser_add_symbol(terminal);
    }
    else if (parent_type == metaast_or)
    {   
        //special case, all nested or nodes use the same head
        return metaparser_insert_rule_ast(parent_head_idx, ast);
    }
    else
    {
        //all other cases, insert an anonymous expression
        return metaparser_insert_rule_ast(NULL_SYMBOL_INDEX, ast);
    }
}




/**
 * Return the index of the epsilon rule.
 */
uint64_t metaparser_get_eps_body_idx()
{
    //If no epsilon body has been added yet, create one
    if (metaparser_eps_body_idx == NULL_SYMBOL_INDEX)
    {
        //epsilon is represented by an empty vector
        vect* epsilon = new_vect();
        metaparser_eps_body_idx = metaparser_add_body(epsilon);
    }
    return metaparser_eps_body_idx;
}


/**
 * Insert the symbol into the symbol set, and return its index.
 * Symbols already in the set are freed.
 */
uint64_t metaparser_add_symbol(obj* symbol)
{
    uint64_t symbol_idx = set_add_return_index(metaparser_symbols, symbol);
    return symbol_idx;
}



/**
 * Return the symbol at index i of the symbol set.
 */
obj* metaparser_get_symbol(uint64_t i)
{
    return set_get_at_index(metaparser_symbols, i);
}


/**
 * Insert the body into the bodies set, and return its index.
 * Bodies already in the set are freed.
 */
uint64_t metaparser_add_body(vect* body)
{
    obj* body_obj = new_vect_obj(body);
    uint64_t body_idx = set_add_return_index(metaparser_bodies, body_obj);
    return body_idx;
}


/**
 * Return the body at index i of the bodies set.
 */
vect* metaparser_get_body(uint64_t i)
{
    obj* body_obj = set_get_at_index(metaparser_bodies, i);
    return body_obj->data; //TODO->add error checking... could be null, could also be not a vect...
}


/**
 * Create a production entry for the grammer in the production heads and bodies vectors.
 */
void metaparser_add_production(uint64_t head_idx, uint64_t body_idx)
{
    vect_append(metaparser_production_heads, new_uint_obj(head_idx));
    vect_append(metaparser_production_bodies, new_uint_obj(body_idx));
}



#endif