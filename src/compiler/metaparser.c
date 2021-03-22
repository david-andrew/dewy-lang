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

dict* metaparser_ast_cache; //map from metaast to identifiers for the sentence that matches that ast


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
    obj* head = new_ustring_obj(ustring_utf8_substr(num_str, 0, width-1));
    free(num_str);

    //increment the counter
    metaparser_anonymous_rule_count++;
    
    return head;
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
    return metaparser_insert_rule_ast(head, body_ast); 
    return true;

    // //TEMPORARY
    // if (body_ast != NULL)
    // {
    //     obj_print(head);
    //     printf(" = ");
    //     metaast_str(body_ast);
    //     printf("\n");
    //     metaast_free(body_ast);
    // }
    // else
    // {   
    //     obj_print(head);
    //     printf(" body tokens returned NULL\n");
    //     vect_free(body_tokens);
    // }

    // obj_free(head);
    // return true;
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
        obj* t_obj = vect_dequeue(tokens);
        metatoken* t = t_obj->data;
        if (t->type == whitespace || t->type == comment)
        {
            obj_free(t_obj);
        }
        else if (t->type == hashtag)
        {
            return t_obj;
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
obj* metaparser_insert_rule_ast(obj* head, metaast* body_ast)
{
    //list of sentences for this rule
    vect* heads = new_vect();
    vect* bodies = new_vect();
    
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

    if (head == NULL)
    {
        head = metaparser_get_anonymous_rule_head();
    }
    
    switch (body_ast->type)
    {
        // Base case (non-recursive) rules
        case metaast_eps:
        {
            //create a length 1 sentence (vector) containing only epsilon
            vect* sentence = new_vect();
            vect_append(sentence, new_epsilon_obj());

            //push this sentence to the list of all sentences for this rule
            vect_append(heads, head);
            vect_append(bodies, new_vect_obj(sentence));
            break;
        }
        case metaast_identifier:
        {
            metaast_string_node* node = body_ast->node;
            vect* sentence = new_vect();
            vect_append(sentence, new_ustring_obj(ustring_clone(node->string)));
            vect_append(heads, head);
            vect_append(bodies, new_vect_obj(sentence));
            break;
        }
        case metaast_charset:
        {
            metaast_charset_node* node = body_ast->node;
            vect* sentence = new_vect();
            vect_append(sentence, new_charset_obj(charset_clone(node->c)));
            
            vect_append(heads, head);
            vect_append(bodies, new_vect_obj(sentence));
            break;
        }
        case metaast_string:
        {
            metaast_string_node* node = body_ast->node;
            vect* sentence = new_vect();
            uint32_t* s = node->string;
            uint32_t c;
            while ((c = *s++))
            {
                charset* cs = new_charset();
                charset_add_char(cs, c);
                vect_append(sentence, new_charset_obj(cs));
            }
            
            //push this sentence to the list of all sentences for this rule
            vect_append(heads, head);
            vect_append(bodies, new_vect_obj(sentence));
            break;
        }

        // Recursive rules that need to compute the nested sentences
        case metaast_star:
        case metaast_plus:
        {
            metaast_repeat_node* node = body_ast->node;
            
            //get the identifier for the inner node
            obj* inner_head = obj_copy(metaparser_insert_rule_ast(NULL, node->inner));

            //build the sentence
            if (node->count == 0 || (node->count == 1 && body_ast->type == metaast_star))
            {
                //simple star
                //#A* => 
                //(#A)0* =>
                //(#A)1* =>
                //(#A)0+ =>
                //  #A 
                //  #__0 = #A #__0;
                //  #__0 = ϵ;
                

                //#__0 = #A #__0
                vect* sentence0 = new_vect();
                vect_append(sentence0, inner_head);
                vect_append(sentence0, head);

                //#__0 = ϵ
                vect* sentence1 = new_vect();
                vect_append(sentence1, new_epsilon_obj());

                //save everything to the heads & bodies lists
                vect_append(heads, head);
                vect_append(bodies, new_vect_obj(sentence0));
                
                vect_append(heads, head);
                vect_append(bodies, new_vect_obj(sentence1));
            }
            else
            {
                //complex plus
                //(#A)N+ =>
                //  #A;
                //  #__0 = #A #__0;
                //  #__0 = ϵ;
                //  #__1 = #A #A #A ... #A #__0; //... N times
                
                //complex star
                //(#A)N* =>
                //  #A;
                //  #__0 = #A #__0;
                //  #__0 = ϵ;
                //  #__1 = #A #A #A ... #A #__0; //... N times
                //  #__1 = ϵ;


                //  #__0 = #A #__0
                obj* head1 = metaparser_get_anonymous_rule_head();
                vect* sentence0 = new_vect();
                vect_append(sentence0, inner_head);
                vect_append(sentence0, head1);

                //  #__0 = ϵ;
                vect* sentence1 = new_vect();
                vect_append(sentence1, new_epsilon_obj());

                //  #__1 = #A #A #A ... #A #__0; //... N times
                vect* sentence2 = new_vect();
                for (int i = 0; i < node->count; i++)
                {
                    vect_append(sentence2, inner_head);
                }
                vect_append(sentence2, head1);


                vect_append(heads, head1);
                vect_append(bodies, new_vect_obj(sentence0));

                vect_append(heads, head1);
                vect_append(bodies, new_vect_obj(sentence1));

                vect_append(heads, head);
                vect_append(bodies, new_vect_obj(sentence2));


                //create complex plus
                if (body_ast->type == metaast_star)
                {
                    vect* sentence3 = new_vect();
                    vect_append(sentence3, new_epsilon_obj());
                    vect_append(heads, head);
                    vect_append(bodies, new_vect_obj(sentence3));
                }
            }
            break;
        }
        case metaast_count:
        {
            metaast_repeat_node* node = body_ast->node;
            obj* inner_head = obj_copy(metaparser_insert_rule_ast(NULL, node->inner));

            if (node->count == 0)
            {
                //(#A)0 => ϵ;
                printf("WARNING: ("); obj_print(inner_head); printf(")0 is equivalent to ϵ\n"
                "Did you mean `("); obj_print(inner_head); printf(")*` ?\n");
                vect* sentence = new_vect();
                vect_append(sentence, new_epsilon_obj());
                vect_append(heads, head);
                vect_append(bodies, new_vect_obj(sentence));
            }
            else
            {
                //(#A)N =>
                //  #__0 = #A #A #A ... #A; //... N times
                vect* sentence = new_vect();
                for (int i = 0; i < node->count; i++)
                {
                    vect_append(sentence, inner_head);
                }
                vect_append(heads, head);
                vect_append(bodies, new_vect_obj(sentence));
            }
            break;
        }
        // case metaast_option:
        // case metaast_cat:
        // case metaast_or:
        
        
        //TODO->filters/other extensions of the parser
        // case metaast_greaterthan:
        // case metaast_lessthan:
        // case metaast_reject:
        // case metaast_nofollow:
        // case metaast_capture:


        //ERROR->should not allow, or come up with semantics for
        //e.g. (#A)~ => ξ* - #A
        // case metaast_compliment:


        //should be an error since this only makes sense for charsets
        // metaast_intersect,
    }

    // obj_free_keep_inner(body_ast_obj, MetaAST_t);
    
    //insert the list of body sentences for this head into the grammar table
    //if head == NULL, the parser will create an anonymous identifier for the rule
    // head = metaparser_insert_rule_sentences(head, bodies);


    //print out the meta rule
    if (vect_size(bodies) != vect_size(heads)){ printf("ERROR heads and bodies should be the same size!\n"); exit(1); }
    for (size_t i = 0; i < vect_size(bodies); i++)
    {
        obj* head = vect_get(heads, i);
        obj_print(head);
        printf(" = ");
        vect* sentence = vect_get(bodies, i)->data;
        for (size_t j = 0; j < vect_size(sentence); j++)
        {
            obj_print(vect_get(sentence, j));
            if (j < vect_size(sentence) - 1) { printf(" "); }
        }
        printf("\n");
    }

    return head;
}


/**
 * Insert the rule into the metaparser grammar table if it does not already exist.
 * Otherwise make use of the existing definition of the rule.
 */
bool metaparser_insert_rule_sentences(obj* head, vect* bodies)
{

}




size_t metaparser_add_head(obj* head){}
obj* metaparser_get_head(size_t i){}

size_t metaparser_add_body(obj* body){}
vect* metaparser_get_body(size_t i){}

void metaparser_join(size_t head_idx, size_t body_idx){}


/**
 * Create a new object representing an epsilon
 */
obj* new_epsilon_obj()
{
    obj* e = malloc(sizeof(obj));
    *e = (obj){.type=Epsilon_t, .data=NULL};
    return e;
}


#endif