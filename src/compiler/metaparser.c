#ifndef METAPARSER_C
#define METAPARSER_C

#include <stdio.h>
#include <stdlib.h>
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

//used to mark unsigned integer indices as NULL.
#define NULL_SYMBOL_INDEX (uint64_t)-1


/**
 * Global data structures used to manage all meta grammar rules.
 * Symbols are either an identifier or a charset. 
 * Bodies are vects of uint indices indicating symbols from the symbols list.
 * Productions are a map from the head index (in the symbols list) to a list of 
 * indices indicating which body vectors apply to that head.
 */
set* metaparser_symbols;        //list of all symbols used in production bodies.
set* metaparser_bodies;         //list of each production body.
dict* metaparser_productions;   //map from head to production bodies.

//convenience variables for the frequently used epsilon production body, and $ endmarker terminal.
uint64_t metaparser_eps_body_idx = NULL_SYMBOL_INDEX;
uint64_t metaparser_endmarker_symbol_idx = NULL_SYMBOL_INDEX;
uint64_t metaparser_start_symbol_idx = NULL_SYMBOL_INDEX;



/**
 * Initialize all global data structures used by metaparser.
 */
void initialize_metaparser()
{
    metaparser_symbols = new_set();
    metaparser_bodies = new_set();
    metaparser_productions = new_dict();
}


/**
 * functions to finalize the state of the metaparser before continuing to later steps of parsing.
 */
void complete_metaparser()
{
    metaparser_get_eps_body_idx();
    metaparser_get_endmarker_symbol_idx();
    metaparser_get_start_symbol_idx();
}


/**
 * Free up all global data structures used by metaparser.
 */
void release_metaparser()
{
    set_free(metaparser_symbols);
    set_free(metaparser_bodies);
    dict_free(metaparser_productions);
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
    size_t width = dec_num_digits(metaparser_anonymous_rule_count);
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
 * Print out the raw contents of the grammar tables. 
 * i.e. prints the symbols list with each symbols indices,
 * Prints the bodies list with each body containing indices of symbols
 * Prints the productions dictionary which contains head symbol indices
 * pointing to the list of indices of bodies for that head.
 */
void metaparser_productions_repr()
{
    //print out all symbols, bodies
    printf("symbols:\n"); 
    for (uint64_t i = 0; i < set_size(metaparser_symbols); i++)
    {
        printf("%"PRIu64": ", i); obj_str(metaparser_get_symbol(i)); printf("\n");
    }
    printf("\nbodies:\n");
    for (uint64_t i = 0; i < set_size(metaparser_bodies); i++)
    {
        printf("%"PRIu64": ", i); vect_str(metaparser_get_body(i)); printf("\n");
    }
    printf("\nproductions:\n");
    dict_str(metaparser_productions);
    printf("\n\n");
}

/**
 * Print out the contents of the grammar tables, converting indices to their corresponding values
 */
void metaparser_productions_str()
{       
    for (size_t i = 0; i < dict_size(metaparser_productions); i++)
    {
        //get head string
        uint64_t* head_idx = metaparser_productions->entries[i].key->data;
        obj* head = metaparser_get_symbol(*head_idx);

        //get bodies indices set, and print a production line for each body 
        set* bodies = metaparser_productions->entries[i].value->data;
        for (size_t j = 0; j < set_size(bodies); j++)
        {
            //print head
            obj_str(head);
            printf(" -> ");
            
            //get the body for this production
            uint64_t* body_idx = bodies->entries[j].item->data;
            vect* sentence = metaparser_get_body(*body_idx);
            
            //print out the contents of this body
            if (vect_size(sentence) == 0) 
            {
                //length 0 sentence is just epsilon
                printf("ϵ");
            }
            for (size_t k = 0; k < vect_size(sentence); k++)
            {
                //normal print out each symbol in the sentence
                uint64_t* symbol_idx = vect_get(sentence, k)->data;
                obj* symbol = metaparser_get_symbol(*symbol_idx);
                obj_str(symbol);
                if (k < vect_size(sentence) - 1) { printf(" "); }
            }
            printf("\n");
        }
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
uint64_t metaparser_insert_rule_ast(uint64_t head_idx, metaast* body_ast)
{   
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
            obj* nonterminal = new_ustring_obj(ustring_clone(body_ast->node.string));
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
            obj* terminal = new_charset_obj(charset_clone(body_ast->node.cs));
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
            uint32_t* s = body_ast->node.string;
            uint32_t c;
            while ((c = *s++))
            {
                obj* cs_obj = new_charset_obj(NULL);
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
        case metaast_caseless:
        {
            //crete an anonymous head if it wasn't provided
            head_idx = head_idx == NULL_SYMBOL_INDEX ? metaparser_get_anonymous_rule_head() : head_idx;

            //create a sentence for the string
            vect* sentence = new_vect();

            //insert upper and lowercase versions of each character from the string into the sentence
            uint32_t* s = body_ast->node.string;
            uint32_t c;
            while ((c = *s++))
            {
                uint32_t upper, lower;
                unicode_upper_and_lower(c, &upper, &lower);
                obj* cs_obj = new_charset_obj(NULL);
                charset_add_char(cs_obj->data, upper);
                charset_add_char(cs_obj->data, lower);
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
            
            //get the identifier for the inner node
            uint64_t inner_head_idx = metaparser_get_symbol_or_anonymous(body_ast->node.repeat.inner);

            //build the sentence
            if (body_ast->node.repeat.count == 0 || (body_ast->node.repeat.count == 1 && body_ast->type == metaast_star))
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
                for (int i = 0; i < body_ast->node.repeat.count; i++)
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

            uint64_t inner_head_idx = metaparser_get_symbol_or_anonymous(body_ast->node.repeat.inner);

            if (body_ast->node.repeat.count == 0)
            {
                //#head = (#A)0 => ϵ;  //this is probably a typo on the user's part...
                printf("WARNING: "); metaast_str(body_ast); printf(" is equivalent to ϵ\n"
                "Did you mean `("); metaast_str(body_ast->node.repeat.inner); printf(")*`"
                " or `("); metaast_str(body_ast->node.repeat.inner); printf(")+`"
                " or `("); metaast_str(body_ast->node.repeat.inner); printf(")N` where N > 1 ?\n");
                metaparser_add_production(head_idx, metaparser_get_eps_body_idx());
            }
            else
            {
                //#head = (#A)N =>
                //  #head = #A #A #A ... #A; //... N times
                vect* sentence = new_vect();
                for (int i = 0; i < body_ast->node.repeat.count; i++)
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

            uint64_t inner_head_idx = metaparser_get_symbol_or_anonymous(body_ast->node.unary.inner);

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
            vect* sentence = new_vect();
            for (size_t i = 0; i < body_ast->node.sequence.size; i++)
            {
                metaast* inner_i_ast = body_ast->node.sequence.elements[i];
                switch (inner_i_ast->type)
                {
                    //insert each char of the string into the parent sentence
                    case metaast_string: 
                    { 
                        uint32_t* s = inner_i_ast->node.string;
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
                    
                    case metaast_caseless: 
                    { 
                        uint32_t* s = inner_i_ast->node.string;
                        uint32_t c;
                        while ((c = *s++))
                        {                            
                            uint32_t upper, lower;
                            unicode_upper_and_lower(c, &upper, &lower);
                            obj* cs_obj = new_charset_obj(new_charset());
                            charset_add_char(cs_obj->data, upper);
                            charset_add_char(cs_obj->data, lower);                            
                            uint64_t terminal_idx = metaparser_add_symbol(cs_obj);
                            vect_append(sentence, new_uint_obj(terminal_idx));
                        }
                        break;
                    }

                    //insert the charset into the parent sentence
                    case metaast_charset: 
                    {
                        obj* cs_obj = new_charset_obj(charset_clone(inner_i_ast->node.cs));
                        uint64_t terminal_idx = metaparser_add_symbol(cs_obj);
                        vect_append(sentence, new_uint_obj(terminal_idx));
                        break;
                    }
                    
                    //insert the identifier into the parent sentence
                    case metaast_identifier:
                    {
                        obj* identifier = new_ustring_obj(ustring_clone(inner_i_ast->node.string));
                        uint64_t identifier_idx = metaparser_add_symbol(identifier);
                        vect_append(sentence, new_uint_obj(identifier_idx));
                        break;
                    }
                    
                    //literal epsilons are skipped in a cat node
                    case metaast_eps: { break; }
                    
                    //all other types of ast are represented by an anonymous identifier
                    default: 
                    {
                        uint64_t head_i_idx = metaparser_get_symbol_or_anonymous(body_ast->node.sequence.elements[i]);
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

            metaparser_insert_or_inner_rule_ast(head_idx, body_ast->node.binary.left);
            metaparser_insert_or_inner_rule_ast(head_idx, body_ast->node.binary.right);

            break;
        }
        
        
        //TODO->filters/other extensions of the parser
        case metaast_greaterthan:
            printf("ERROR: Cannot generate CFG sentence as greater than `>` operator has not yet been implemented\n");
            break;
        case metaast_lessthan:
            printf("ERROR: Cannot generate CFG sentence as less than `<` operator has not yet been implemented\n");
            break;
        case metaast_reject:
            printf("ERROR: Cannot generate CFG sentence as reject `-` operator has not yet been implemented\n");
            break;
        case metaast_nofollow:
            printf("ERROR: Cannot generate CFG sentence as no follow `/` operator has not yet been implemented\n");
            break;
        case metaast_capture:
            printf("ERROR: Cannot generate CFG sentence as capture `.` operator has not yet been implemented\n");
            break;

        //ERROR->should not allow, or come up with semantics for
        //e.g. (#A)~ => ξ* - #A
        //should be an error since this only makes sense for charsets
        case metaast_compliment:
        case metaast_intersect:
            printf("ERROR: compliment/intersect is only applicable to charsets. There are (currently) no semantics for what they mean for a regular grammar production");
            break;

    }

    return head_idx;
}


/**
 * For a nested ast rule, if the nested rule is a symbol (i.e. identifier or charset), 
 * return its symbol index. Otherwise generate an anonymous identifier by inserting the ast
 * with a NULL parent head, and then return the index of the anonymous identifier.
 */
uint64_t metaparser_get_symbol_or_anonymous(metaast* ast)
{
    if (ast->type == metaast_identifier)
    {    
        obj* nonterminal = new_ustring_obj(ustring_clone(ast->node.string));
        return metaparser_add_symbol(nonterminal);
    }
    else if (ast->type == metaast_charset)
    {
        obj* terminal = new_charset_obj(charset_clone(ast->node.cs));
        return metaparser_add_symbol(terminal);
    }
    else
    {
        //all other cases, insert an anonymous expression, and return its head
        return metaparser_insert_rule_ast(NULL_SYMBOL_INDEX, ast);
    }
}


/**
 * Insert the ast at the same level as the parent ast.
 * e.g. or nodes insert children with the same head as the parent.
 * If the inner node needs an anonymous head, that head is returned,
 * else NULL_SYMBOL_INDEX is returned. This means the ast reused the parents head, and does not need to
 * ruther be inserted into the grammar tables
 * 
 * NOTE: Parent is expected to be an or node (as no other node types insert children at the same level)
 */
void metaparser_insert_or_inner_rule_ast(uint64_t parent_head_idx, metaast* ast)
{
    //case where the inner node reuses the parent index
    if (ast->type == metaast_or || ast->type == metaast_eps || ast->type == metaast_identifier 
    || ast->type == metaast_charset || ast->type == metaast_string || ast->type == metaast_cat)
    {
        //insert the inner as itself, using the parent's head
        metaparser_insert_rule_ast(parent_head_idx, ast);
    }
    else //inner node needs to create an anonymous head which the parent adds as a sentence
    {
        uint64_t anonymous_idx = metaparser_insert_rule_ast(NULL_SYMBOL_INDEX, ast);
        
        //create a sentence containing just the anonymous rule
        vect* sentence = new_vect();
        vect_append(sentence, new_uint_obj(anonymous_idx));
        uint64_t body_idx = metaparser_add_body(sentence);

        //create the production by adding the sentence to the parent head
        metaparser_add_production(parent_head_idx, body_idx);
    }
}


/**
 * Return the set that stores all symbols generated by the metaparser.
 */
set* metaparser_get_symbols()
{
    return metaparser_symbols;
}


/**
 * Return the set that stores all bodies generated by the metaparser.
 */
set* metaparser_get_bodies()
{
    return metaparser_bodies;
}


/**
 * Return the map containing all productions generated by the metaparser.
 */
dict* metaparser_get_productions()
{
    return metaparser_productions;
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
 * Return the symbol index of the endmarker terminal $.
 */
uint64_t metaparser_get_endmarker_symbol_idx()
{
    if (metaparser_endmarker_symbol_idx == NULL_SYMBOL_INDEX)
    {
        //endmarker terminal is represented as a special charset containing 0x200000
        charset* endmarker = charset_get_endmarker();
        metaparser_endmarker_symbol_idx = metaparser_add_symbol(new_charset_obj(endmarker));
    }
    return metaparser_endmarker_symbol_idx;
}


/**
 * Get the index of the augmented start symbol for the grammar. 
 * If no symbol has been set as the start symbol, use the first
 * non-terminal in metaparser_symbols and create the augmented rule
 * from that.
 */
uint64_t metaparser_get_start_symbol_idx()
{
    //check if start symbol not set yet
    if (metaparser_start_symbol_idx == NULL_SYMBOL_INDEX)
    {
        //if can't find a start symbol, tell parser to use the first non-terminal.
        uint64_t start_symbol_idx = NULL_SYMBOL_INDEX;

        //check for any rules labelled exactly `#start`
        set* symbols = metaparser_get_symbols();
        for (size_t symbol_idx = 0; symbol_idx < set_size(symbols); symbol_idx++)
        {
            if (metaparser_is_symbol_terminal(symbol_idx)) { continue; }
            uint32_t* terminal = metaparser_get_symbol(symbol_idx)->data;

            //found #start non-terminal
            if (ustring_charstar_cmp(terminal, "#start") == 0)
            {
                start_symbol_idx = symbol_idx;
                break;
            }
        }

        //set the start symbol using either the found #start rule, or NULL
        metaparser_set_start_symbol(start_symbol_idx);
    }
    return metaparser_start_symbol_idx;
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
 * Determine whether the symbol at the given index is a terminal or non-terminal.
 * Charsets are terminals, while identifiers (UnicodeString_t) are non-terminals.
 */
bool metaparser_is_symbol_terminal(uint64_t symbol_idx)
{
    obj* symbol = metaparser_get_symbol(symbol_idx);
    return symbol->type == CharSet_t;
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
    //create a new entry containing the head if it doesn't exist
    if (!dict_contains_uint_key(metaparser_productions, head_idx))
    {
        dict_set(metaparser_productions, new_uint_obj(head_idx), new_set_obj(NULL));
    }

    //get the set containing the list of bodies for this head
    obj* bodies_obj = dict_get_uint_key(metaparser_productions, head_idx);
    if (bodies_obj->type != Set_t)
    {
        printf("ERROR: metaparser_productions should only point to vectors. Instead found type %d\n", bodies_obj->type);
        exit(1);
    }
    set* bodies = bodies_obj->data;

    //insert the production body into the set
    set_add(bodies, new_uint_obj(body_idx));
}


/**
 * Return the set of production bodies for the given head index.
 */
set* metaparser_get_production_bodies(uint64_t head_idx)
{
    obj* bodies_obj = dict_get_uint_key(metaparser_productions, head_idx);
    if (bodies_obj == NULL)
    {
        //print out the head symbol too...
        printf("ERROR: no production bodies exist for head "); obj_str(metaparser_get_symbol(head_idx)); printf("\n");
        return NULL;
    }
    return bodies_obj->data;
}


/**
 * Return a specific production body for the given head and body indices.
 */
vect* metaparser_get_production_body(uint64_t head_idx, uint64_t production_idx)
{
    set* bodies = metaparser_get_production_bodies(head_idx);
    if (bodies == NULL) { return NULL; }
    uint64_t* body_idx = bodies->entries[production_idx].item->data;
    return metaparser_bodies->entries[*body_idx].item->data;
}


/**
 * Create an augmented production to be used by the grammar during parsing.
 * start_symbol_idx may be NULL_SYMBOL_INDEX, in which case, the first non-terminal
 * in metaparser_symbols will be used as the start rule.
 * If provided `start_symbol_idx` is a suitable augmented start symbol, then use that as is.
 */
void metaparser_set_start_symbol(uint64_t start_symbol_idx)
{
    //if not given an index, select the first non-terminal as the start symbol
    if (start_symbol_idx == NULL_SYMBOL_INDEX)
    {
        if (set_size(metaparser_symbols) == 0)
        {
            printf("ERROR: Could not create start symbol, symbol table is empty\n");
            return;
        }
        
        //find the first non-terminal, and use that as the start symbol. This will likely always be 0...
        for (start_symbol_idx = 0; start_symbol_idx < set_size(metaparser_symbols); start_symbol_idx++)
        {
            if (!metaparser_is_symbol_terminal(start_symbol_idx)) { break; }
        }
    }

    //check if we need an augmented head, or we can just use the start rule
    set* bodies = metaparser_get_production_bodies(start_symbol_idx);
    if (set_size(bodies) == 1)
    {
        vect* body = metaparser_get_production_body(start_symbol_idx, 0);
        if (vect_size(body) == 1)
        {
            uint64_t* symbol_idx = vect_get(body, 0)->data;
            if (!metaparser_is_symbol_terminal(*symbol_idx))
            {
                metaparser_start_symbol_idx = start_symbol_idx;
                return;
            }
        }
    }
    
    //Otherwise, create a new production S' -> S for the augmented grammar
    uint64_t augmented_head_idx = metaparser_get_anonymous_rule_head();
    vect* augmented_body = new_vect();
    vect_append(augmented_body, new_uint_obj(start_symbol_idx));
    uint64_t augmented_body_idx = metaparser_add_body(augmented_body);
    metaparser_add_production(augmented_head_idx, augmented_body_idx);
    metaparser_start_symbol_idx = augmented_head_idx;
}




#endif