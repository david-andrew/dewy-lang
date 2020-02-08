#ifndef PARSER_C
#define PARSER_C

#include <stdio.h>
#include <string.h>

#include "object.c"
#include "token.c"
#include "vector.c"
#include "dictionary.c"
#include "set.c"
#include "mast.c"
#include "scanner.c"


//TODO
// typedef struct parser_context_struct
// {
//     dict* meta_symbols;
//     dict* meta_rules;
//     //other context stuff
// } parser_context;


//definitions for the AST

//rules for AST rule construction
//everytime you see a rule, immediately put it in the symbol table under that name (allow overwrites)
//if a #rule comes up, point to that rule's AST directly in the new AST being made
//if a #rule comes up, and it isn't in the symbol table, it's an error. This prevents recursion


//forward declarations
int get_next_real_token(vect* tokens, int i);
int get_next_token_type(vect* tokens, token_type type, int i);
int get_level_first_token_type(vect* tokens, token_type type);
void update_meta_symbols(dict* meta_symbols, vect* tokens);
void create_lex_rule(dict* meta_rules, vect* tokens);
bool expand_rules(vect* tokens, dict* meta_rules);
obj* build_ast(vect* tokens, dict* meta_symbols);
size_t get_lowest_precedence_index(vect* tokens);
int find_closing_pair(vect* tokens, int start);
obj* build_string_ast_obj(token* t);

//returns the index of the next non-whitespace and non-comment token.
//returns -1 if none are present in the vector
int get_next_real_token(vect* tokens, int i)
{
    //while we haven't reached the end of the token stream
    //if the current token isn't whitespace or a comment, return its index
    while (i < vect_size(tokens))
    {
        token* t = (token*)vect_get(tokens, i)->data;
        if (t->type != whitespace && t->type != comment) { return i; }
        i++;
    }

    //reached end without finding a real token
    return -1;
}

//return the index of the first occurance of the specified token type.
//returns -1 if not present in the vector
int get_next_token_type(vect* tokens, token_type type, int i)
{
    //while we haven't reached the end of the tokens stream
    //if the current token is the desired type, return its index
    while (i < vect_size(tokens))
    {
        token* t = (token*)vect_get(tokens, i)->data;
        if (t->type == type) { return i; }
        i++;
    }

    //reached end without finding token of desired type
    return -1;
}

/**
    return the leftmost instance of the specified token type
    skips over any (), {}, or [] groups contained in the vector
*/
int get_level_first_token_type(vect* tokens, token_type type)
{
    int i = 0;
    while (i < vect_size(tokens))
    {
        token* t = (token*)vect_get(tokens, i)->data;
        if (t->type == type) { return i; }
        else if (t->type == meta_left_parenthesis || t->type == meta_left_bracket || t->type == meta_left_brace)
        {
            int j = find_closing_pair(tokens, i);
            if (j > i) 
            { 
                i = j + 1; 
            }
            else 
            { 
                printf("ERROR: get_level_first_token_type() encountered an unpaired ");
                obj_print(vect_get(tokens, i));
                printf("\n");
                return -1; 
            }
        }
        else { i++; }
    }
    return -1;
}


void update_meta_symbols(dict* meta_symbols, vect* tokens)
{
    //get the index of the first non-whitespace/comment token
    int head_idx = get_next_real_token(tokens, 0);
    if (head_idx < 0) { return; }
 
    //if the first token isn't a hashtag then this isn't a meta-rule
    token* head = (token*)vect_get(tokens, head_idx)->data;
    if (head->type != hashtag) { return; }
        
    //get the index of the next real token
    int tail_idx = get_next_real_token(tokens, head_idx+1);
    if (tail_idx < 0) { return; }

    //if the next token isn't a meta_equals_sign this isn't a meta-rule
    token* tail = (token*)vect_get(tokens, tail_idx)->data;
    if (tail->type != meta_equals_sign) { return; }

    //search for the first occurance of a semicolon
    tail_idx = get_next_token_type(tokens, meta_semicolon, tail_idx+1);
    if (tail_idx < 0) { return; }
    tail = (token*)vect_get(tokens, tail_idx)->data;
    // assert(tail->type == meta_semicolon);

    //free all tokens up to the start of the rule (as they should be whitespace and comments)
    for (int i = 0; i < head_idx; i++)
    {
        obj_free(vect_dequeue(tokens));
    }

    //first token in the tokens stream should be the meta_identifier
    token* rule_identifier_token = (token*)vect_dequeue(tokens)->data;

    //collect together all tokens from head to tail and store in the symbol table, as a vect
    vect* rule_body = new_vect();
    
    //store all the tokens for the rule into the rule_body vector
    for (int i = head_idx+1; i < tail_idx; i++) //skip identifier and stop before semicolon
    {
        vect_enqueue(rule_body, vect_dequeue(tokens));
    }

    //free the semicolon at the end of the rule
    obj_free(vect_dequeue(tokens));

    //remove whitespace and comments from the rule
    remove_token_type(rule_body, whitespace);
    remove_token_type(rule_body, comment);

    //free the meta_equals sign at the start of the rule body
    obj_free(vect_dequeue(rule_body));


    //store the rule_identifier and the rule_body into the symbol table
    //TODO->need to set up obj* for string, or ability to hash tokens
    //TODO->for now, should probably check if the rule is alredy present, as it will be overwritten. in the future, you should be able to update rules, by inserting the original into anywhere it's referenced in the new one


    // printf("%s -> ", rule_identifier_token->content);
    // vect_str(rule_body);
    // printf("\n");

    char* rule_identifier = clone(rule_identifier_token->content);
    obj* id = new_string(rule_identifier);
    free(rule_identifier_token);

    //build an AST out of the tokens list
    obj* rule_ast = build_ast(rule_body, meta_symbols);
    printf("Adding rule: "); obj_print(id); printf(":\n");
    ast_str(rule_ast);

    dict_set(meta_symbols, id, rule_ast);

    // obj* rule = vect_obj_wrap(rule_body);
    // obj_print(id);
    // printf("%s", *((char**)id->data));
    // printf(" -> ");
    // obj_print(rule);
    // printf("\n");

    //TODO->probably construct AST for rule here, and then store the AST in the meta symbol table
    // dict_set(meta_symbols, id, rule);
    // printf("returned from dict_set\n");
    // dict_str(meta_symbols);
    // printf("\n");
    //TODO->store the rule_identifier and the rule_body into the symbol table






}

//check if the token stream starts with #lex(#rule1 #rule2 ...), and create an (AST?) rule
void create_lex_rule(dict* meta_rules, vect* tokens)
{
    //get the index of the first non-whitespace/comment token
    int head_idx = get_next_real_token(tokens, 0);
    if (head_idx < 0) { return; }

    //if the first token isn't the #lex hashtag then this isn't a call to #lex()
    token* head = (token*)vect_get(tokens, head_idx)->data;
    if (head->type != hashtag) { return; }
    if (strcmp(head->content, "#lex") != 0) { return; }

    //if the next token isn't an opening "(" meta_meta_parenthesis this isn't a call to #lex()
    int tail_idx = head_idx + 1;
    if (tail_idx >= vect_size(tokens)) { return; }
    token* tail = (token*)vect_get(tokens, tail_idx)->data;
    if (tail->type != meta_left_parenthesis) 
    { 
        printf("ERROR: #lex keyword followed by non-parenthesis token [");
        token_str(tail);
        printf("]\n");
        return; 
    }

    //get the index of the closing parenthesis
    tail_idx = get_next_token_type(tokens, meta_right_parenthesis, tail_idx+1);
    if (tail_idx < 0) { return; }

    //free all tokens up to the start of the rule (as they should be whitespace and comments)
    for (int i = 0; i < head_idx; i++)
    {
        obj_free(vect_dequeue(tokens));
    }
    //free the #lex keyword and the opening parenthesis
    obj_free(vect_dequeue(tokens));
    obj_free(vect_dequeue(tokens));

    vect* lex_rules = new_vect();
    for (int i = head_idx + 2; i < tail_idx; i++)
    {
        vect_enqueue(lex_rules, vect_dequeue(tokens));
    }

    //free the closing parenthesis
    obj_free(vect_dequeue(tokens));

    //remove whitespace and comments from the function arguments
    remove_token_type(lex_rules, whitespace);
    remove_token_type(lex_rules, comment);

    //TODO->construct ASTs for the rules
    //TODO->conversion/algorithm for scanning the rules
    //TODO->send the rules into the scanner
    //for now simply print out the rules to be lexed
    printf("Adding scanner rules: ");
    vect_str(lex_rules);

    //TODO->determine if we expand rules greedily or lazily 
    //for rule in lex_rules
    //  create ast from expanded rule

    printf("\n");
}


/**
    replace any instances of #rule with the 
*/
bool expand_rules(vect* tokens, dict* meta_rules)
{
    return false;
}

/**
    Recursively construct an AST out of 
*/
obj* build_ast(vect* tokens, dict* meta_symbols)
{
    //precedence levels. There is no left/right associativity, so default to right
    //groups: []  ()  {}
    //concatenation: ,
    //alternation: |

    //note that groups should always have the opening at index 0, and closing at the last index in the token list

    //perhaps check if tokens[0] is an opening, and then if closing pair is at vect_size(tokens)-1
    //--->create ast from body tokens[1:#end-1], and wrap in ast of correct type
    //   --->for (), call make_AST() on tokens[1:#end-1], and return that directly.
    //   --->for {}, body is make_AST() on tokens[1:#end-1], wrap in an ASTStar_t, and return
    //   --->for [], left is ASTLeaf_t epslilon, right is make_AST() on tokens[1:#end-1], wrap in ASTOr_t, and return

    //if whole isn't wrapped by group, search for left-most | (or) operator, and build an ASTOr_t splitting left and right sides of the token vector
    //if no | (or) operator, search for left-most , (cat) operator, and build ASTCat_t splitting left and right sides of the token vector
    //if no , (cat) operator, we should have a single string?. construct a cat sequence from the string

    //if tokens is empty (tbd if that is correct? I think it could be) return an empty node
    if (vect_size(tokens) == 0) 
    {
        printf("ERROR?: build_ast() encountered empty tokens list. Returned empty leaf node...\n");
        return new_ast_leaf_obj(0);  //an empty leaf node
    }

    //check for group wrap
    if (find_closing_pair(tokens, 0) == vect_size(tokens) - 1)
    {
        token* t = (token*)vect_get(tokens, 0)->data;
        if (t->type == meta_left_parenthesis)
        {
            //since parenthesis do nothing, simply construct a rule from their contents
            obj_free(vect_dequeue(tokens)); //free first token (opening parenthesis)
            obj_free(vect_pop(tokens));     //free last token (closing parenthesis)
            return build_ast(tokens, meta_symbols);       //return an ast of the body
        }
        else if (t->type == meta_left_bracket)
        {
            obj_free(vect_dequeue(tokens)); //free first token (opening brace)
            obj_free(vect_pop(tokens));     //free last token (closing brace)
            return new_ast_star_obj(build_ast(tokens, meta_symbols));
        }
        else if (t->type == meta_left_brace)
        {
            obj_free(vect_dequeue(tokens)); //free first token (opening bracket)
            obj_free(vect_pop(tokens));     //free last token (closing bracket)
            return new_ast_or_obj(new_ast_leaf_obj(0), build_ast(tokens, meta_symbols));
        }
    }

    int split_idx;
    if ((split_idx = get_level_first_token_type(tokens, meta_vertical_bar)) != -1)
    {
        //split into or node of left and right tokens lists
        vect* left_tokens = new_vect();

        //remove all tokens up to split_idx from tokens and push into left_tokens
        for (int i = 0; i < split_idx; i++) { vect_enqueue(left_tokens, vect_dequeue(tokens)); }
        
        //free the | (or) token
        obj_free(vect_dequeue(tokens));
        
        //recursively build the left and right side of the ast
        return new_ast_or_obj(build_ast(left_tokens, meta_symbols), build_ast(tokens, meta_symbols));
    }
    else if ((split_idx = get_level_first_token_type(tokens, meta_comma)) != -1)
    {
        //split into or node of left and right tokens lists
        vect* left_tokens = new_vect();
        
        //remove all tokens up to split_idx from tokens and push into left_tokens
        for (int i = 0; i < split_idx; i++) { vect_enqueue(left_tokens, vect_dequeue(tokens)); }

        //free the , (cat) token
        obj_free(vect_dequeue(tokens));

        //recursively build the left and right side of the ast
        return new_ast_cat_obj(build_ast(left_tokens, meta_symbols), build_ast(tokens, meta_symbols));
    }

    // assert(vect_size(tokens) == 1);
    //else assert should have a single string, or #rule
    //build cat sequence from string
    if (vect_size(tokens) == 1)
    {
        token* t = (token*)vect_get(tokens, 0)->data;
        switch (t->type)
        {
            case meta_string: return build_string_ast_obj(t);
            case hashtag: 
            {
                obj* id = new_string(clone(t->content));   
                obj* ast = dict_get(meta_symbols, id); //reference to the hashtag's ast if it exists
                obj_free(id);
                if (ast != NULL)
                {
                    obj_free(vect_dequeue(tokens)); //free the token with the id
                    return ast;
                }
                printf("ERROR: hashtag (%s) does not exist in the meta-symbol-table\n", t->content);
                obj_free(vect_dequeue(tokens)); //free the token with the id
                return new_ast_leaf_obj(0);
            }
            default: 
            {
                printf("ERROR: unrecognized token type (%d) when there should only be #rules and \"strings\"\n", t->type);
                return new_ast_leaf_obj(0);
            }
        }
    }


    return NULL; 
}

/**
    return the index of the token with the lowest precedence
    if least precedence operator is a pair, e.g. [], {}, (), return the index of the left side
*/
size_t get_lowest_precedence_index(vect* tokens)
{
    //this function might be unnecessary? based on direct checks described above.
    //instead this might change into: int find_leftmost_token(vect* tokens, token_type type){}
    //--->returns the index of the rightmost occurance of the specified token, or -1 if not found
    return 0;
}

/**
    return the index of the matching token pair for [], {}, ()
    will return 0 if no matching pair found
*/
int find_closing_pair(vect* tokens, int start)
{
    obj* t = vect_get(tokens, start);
    token_type opening = ((token*)t->data)->type;
    token_type closing;
    switch (opening) //determine matching closing type based on opening type
    {
        case meta_left_brace: { closing = meta_right_brace; break; }
        case meta_left_bracket: { closing = meta_right_bracket; break; }
        case meta_left_parenthesis: { closing = meta_right_parenthesis; break; }
        default: { return -1; } //non-pair object called, has no "closing pair"
    }
    int stack = -1;
    int stop = start + 1;
    while (stop < vect_size(tokens))
    {
        obj* t_obj = vect_get(tokens, stop);
        token* t = (token*)t_obj->data;
        if (t->type == opening) { stack--; }
        else if (t->type == closing) { stack++; }
        if (stack == 0) { return stop; }
        stop++;
    }
    
    printf("ERROR: no matching pair found for token type (%d) in vector: ", opening);
    vect_str(tokens);
    printf("\n");
    return -1;
}


/**
    construct a series of cat nodes representing a string of characters
*/
obj* build_string_ast_obj(token* t)
{
    char* str = t->content;
    
    //handle empty strings
    if (!*str) { return new_ast_leaf_obj(0); }
    
    uint32_t cur_c = eat_utf8(&str);
    uint32_t prev_c = cur_c;
    if (!(cur_c = eat_utf8(&str))) { return new_ast_leaf_obj(prev_c); }

    obj* root = new_ast_cat_obj(new_ast_leaf_obj(prev_c), NULL);
    obj* cur_obj = root;
    binary_ast* cur_ast;
    prev_c = cur_c;
    while ((cur_c = eat_utf8(&str)))
    {
        cur_ast = *(binary_ast**)cur_obj->data;
        cur_ast->right = new_ast_cat_obj(new_ast_leaf_obj(prev_c), NULL);
        prev_c = cur_c;
        cur_obj = cur_ast->right;
    }
    //make the final leaf node the remaining character
    cur_ast = *(binary_ast**)cur_obj->data;
    cur_ast->right = new_ast_leaf_obj(prev_c);
    return root;
}



#endif