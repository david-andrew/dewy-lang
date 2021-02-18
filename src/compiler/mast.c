#ifndef MAST_C
#define MAST_C

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <assert.h>

#include "utilities.h"
#include "object.h"
#include "dictionary.h"
#include "vector.h"
#include "set.h"
#include "mast.h"


//Meta Abstract Syntax Tree (MAST) definitions






//global int to give each leaf node a unique identifier
// uint64_t _ast_node_id_counter = 0;

node_ast* new_node_ast(uint32_t c)
{
    node_ast* A = malloc(sizeof(node_ast));
    A->codepoint = c;
    A->id = 0;  //this will be uniqueified later //_ast_node_id_counter++; //assign a unique identifier

    if (c != 0) //if codepoint is not 0, then it is a non-null leaf
    {
        A->nullable = new_bool_ptr(false);
    }
    else        //otherwise this is an ϵ (epsilon), i.e. null leaf
    {
        A->nullable = new_bool_ptr(true);       //the null char is by definition nullable
    }

    //firstpos, lastpos, and followpos will all be calculated when the rule tree is complete
    A->firstpos = NULL;
    A->lastpos = NULL;
    A->followpos = NULL;
    return A;
}

unary_ast* new_unary_ast(obj* body)
{
    unary_ast* A = malloc(sizeof(unary_ast));
    A->body = body;         //may or may not be NULL
    A->nullable = NULL;     //these will be computed when the tree is completed
    A->firstpos = NULL;
    A->lastpos = NULL;
    A->followpos = NULL;
    return A;
}

binary_ast* new_binary_ast(obj* left, obj* right)
{
    binary_ast* A = malloc(sizeof(binary_ast));
    A->left = left;         //may or may not be NULL
    A->right = right;       //may of may not be NULL
    A->nullable = NULL;     //these will be computed when the tree is complete
    A->firstpos = NULL;
    A->lastpos = NULL;
    A->followpos = NULL;
    return A;
}


obj* new_ast_leaf_obj(uint32_t c)
{
    obj* A = malloc(sizeof(obj));
    A->type = ASTLeaf_t;
    A->size = sizeof(uint32_t); //TODO->maybe this should be the number of utf-8 bytes?
    node_ast** a_ptr = malloc(sizeof(node_ast*));
    *a_ptr = new_node_ast(c);
    A->data = (void*)a_ptr;
    return A;
}

obj* new_ast_star_obj(obj* body)
{
    obj* A = malloc(sizeof(obj));
    A->type = ASTStar_t;
    A->size = 0; //this will be computed based on size of body
    unary_ast** a_ptr = malloc(sizeof(unary_ast*));
    *a_ptr = new_unary_ast(body);
    A->data = (void*)a_ptr;
    return A;
}

obj* new_ast_or_obj(obj* left, obj* right)
{
    obj* A = malloc(sizeof(obj));
    A->type = ASTOr_t;
    A->size = 0; //this will be computed based on size of body
    binary_ast** a_ptr = malloc(sizeof(binary_ast*));
    *a_ptr = new_binary_ast(left, right);
    A->data = (void*)a_ptr;
    return A;
}

obj* new_ast_cat_obj(obj* left, obj* right)
{
    //basically identical to an AST-Or node, just with type AST-Cat instead
    obj* A = new_ast_or_obj(left, right);
    A->type = ASTCat_t;
    return A;
}


void ast_repr(obj* root){ ast_repr_inner(root, 0); }

void ast_repr_inner(obj* node, int indent)
{
    // if (!node) { return; }

    assert(node != NULL);
    assert(node->type == ASTCat_t
        || node->type == ASTOr_t
        || node->type == ASTStar_t
        || node->type == ASTLeaf_t);

    for (int i=0; i<indent; i++) { printf(" - "); }
    switch (node->type)
    {
        case ASTCat_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            printf("(+)\n");
            // printf("(+) [fp: "); set_str(A->followpos); printf("]\n");
            ast_repr_inner(A->left, indent+1);
            ast_repr_inner(A->right, indent+1);
            return;
        }
        case ASTOr_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            printf("(|)\n");
            // printf("(|) [fp: "); set_str(A->followpos); printf("]\n");
            ast_repr_inner(A->left, indent+1);
            ast_repr_inner(A->right, indent+1);
            return;
        }
        case ASTStar_t:
        {
            unary_ast* A = *(unary_ast**)node->data;
            printf("(*)\n");
            // printf("(*) [fp: "); set_str(A->followpos); printf("]\n");
            ast_repr_inner(A->body, indent+1);
            return;
        }
        case ASTLeaf_t:
        {
            node_ast* A = *(node_ast**)node->data;
            printf(" ");
            unicode_str(A->codepoint ? A->codepoint : 0x2300); //print the character, or the ⌀ symbol
            if (A->codepoint) 
            {
                printf(" [id: %lu, fp: ", A->id); 
                // set_str(ast_firstpos(node)); printf(", lastpos: ");
                // set_str(ast_lastpos(node)); printf(", followpos: ");
                set_str(ast_get_followpos(node)); printf("]");
                // printf(" [id: %lu]\n", A->id);
            }
            printf("\n");
            return;
        }
        default: { printf("ERROR: not an AST type (%d)\n", node->type); return; }
    }
}

void ast_str(obj* node)
{
    assert(node != NULL);
    assert(node->type == ASTCat_t
        || node->type == ASTOr_t
        || node->type == ASTStar_t
        || node->type == ASTLeaf_t);

    switch (node->type)
    {
        case ASTCat_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            if (A->left->type != ASTOr_t)
            {
                ast_str(A->left);
            }
            else
            {
                printf("("); ast_str(A->left); printf(")");
            }

            if (A->right->type != ASTOr_t)
            {
                ast_str(A->right);
            }
            else
            {
                printf("("); ast_str(A->right); printf(")");
            }
            return;
        }
        case ASTOr_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            ast_str(A->left);
            printf(" | ");
            ast_str(A->right);
            return;
        }
        case ASTStar_t:
        {
            unary_ast* A = *(unary_ast**)node->data;
            if (A->body->type == ASTCat_t || A->body->type == ASTOr_t)
            {
                printf("("); ast_str(A->body); printf(")*");
            }
            else if (A->body->type == ASTLeaf_t)
            {
                ast_str(A->body); printf("*");
            }
            else //ASTStar_t is idempotent, i.e. A** = A*
            {
                ast_str(A->body);
            }
            return;
        }
        case ASTLeaf_t:
        {
            node_ast* A = *(node_ast**)node->data;
            // put_unicode(A->codepoint ? A->codepoint : 0x2300); //print the character, or the ⌀ (0x2300) symbol
            unicode_str(A->codepoint);
            return;
        }
        default: { printf("ERROR: not an AST type (%d)\n", node->type); return; }
    }
}

//print out the regex form of the ast
// void ast_compact_str(obj* root){}
// void ast_compact_print()

bool ast_nullable(obj* node)
{
    assert(node != NULL);
    assert(node->type == ASTCat_t
        || node->type == ASTOr_t
        || node->type == ASTStar_t
        || node->type == ASTLeaf_t);

    switch (node->type)
    {
        case ASTLeaf_t:
        {
            //nullable(A) = A->codepoint != 0. This was preset when A was made
            node_ast* A = *(node_ast**)node->data;
            return *A->nullable;
        }
        
        case ASTCat_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            if (A->nullable == NULL)
            {
                //nullable(A) = nullable(left) and nullable(right)
                bool nullable = ast_nullable(A->left) && ast_nullable(A->right);
                A->nullable = new_bool_ptr(nullable);
            }
            return *A->nullable;
        }
        
        case ASTOr_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            if (A->nullable == NULL)
            {
                //nullable(A) = nullable(left) or nullable(right)
                bool nullable = ast_nullable(A->left) || ast_nullable(A->right);
                A->nullable = new_bool_ptr(nullable);
            }
            return *A->nullable;
        }
        
        case ASTStar_t:
        {
            unary_ast* A = *(unary_ast**)node->data;
            if (A->nullable == NULL)
            {
                //star nodes are nullable by definition
                bool nullable = true;
                A->nullable = new_bool_ptr(nullable);
                return nullable;
            }
            return *A->nullable;
        }
        
        default:
        {
            printf("ERROR reached end of nullable function, which should be impossible\n");
            return true;
        }
    }
}

set* ast_firstpos(obj* node)
{
    assert(node != NULL);
    assert(node->type == ASTCat_t
        || node->type == ASTOr_t
        || node->type == ASTStar_t
        || node->type == ASTLeaf_t);

    switch (node->type)
    {
        case ASTLeaf_t:
        {
            node_ast* A = *(node_ast**)node->data;
            if (A->firstpos == NULL)
            {
                A->firstpos = new_set();
                if (A->codepoint != 0) //if not empty character, firspos will contain only c
                {
                    set_add(A->firstpos, new_uint(A->id));
                }
                //else firstpos will be the empty set
            }
            return A->firstpos;
        }
        
        case ASTCat_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            if (A->firstpos == NULL)
            {
                if (ast_nullable(A->left))
                {
                    //firstpos(A) = firstpos(left) U firstpos(right)
                    A->firstpos = set_union(ast_firstpos(A->left), ast_firstpos(A->right));
                }
                else 
                {
                    //firstpos(A) = firstpos(left)
                    A->firstpos = set_copy(ast_firstpos(A->left));
                }
            }
            return A->firstpos;
        }
        
        case ASTOr_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            if (A->firstpos == NULL)
            {
                //firstpos(A) = firstpos(left) U firstpos(right)
                A->firstpos = set_union(ast_firstpos(A->left), ast_firstpos(A->right));
            }
            return A->firstpos;
        }
        
        case ASTStar_t:
        {
            unary_ast* A = *(unary_ast**)node->data;
            if (A->firstpos == NULL)
            {
                //firstpos(A) = firstpos(left)
                A->firstpos = set_copy(ast_firstpos(A->body));
            }
            return A->firstpos;
        }
        
        default:
        {
            printf("ERROR reached end of firstpos function, which should be impossible\n");
            return NULL;
        }
    }
}

//lastpos is firstpos with left and right swapped
set* ast_lastpos(obj* node)
{
    assert(node != NULL);
    assert(node->type == ASTCat_t
        || node->type == ASTOr_t
        || node->type == ASTStar_t
        || node->type == ASTLeaf_t);

    switch (node->type)
    {
        case ASTLeaf_t:
        {
            node_ast* A = *(node_ast**)node->data;
            if (A->lastpos == NULL)
            {
                A->lastpos = new_set();
                if (A->codepoint != 0)
                {
                    set_add(A->lastpos, new_uint(A->id));
                }
            }
            return A->lastpos;
        }
        
        case ASTCat_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            if (A->lastpos == NULL)
            {
                if (ast_nullable(A->right))
                {
                    //lastpos(A) = lastpos(left) U lastpos(right)
                    A->lastpos = set_union(ast_lastpos(A->left), ast_lastpos(A->right));
                }
                else 
                {
                    //lastpos(A) = lastpos(right)
                    A->lastpos = set_copy(ast_lastpos(A->right));
                }
            }
            return A->lastpos;
        }
        
        case ASTOr_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            if (A->lastpos == NULL)
            {
                //lastpos(A) = lastpos(left) U lastpos(right)
                A->lastpos = set_union(ast_lastpos(A->left), ast_lastpos(A->right));
            }
            return A->lastpos;
        }
        
        case ASTStar_t:
        {
            unary_ast* A = *(unary_ast**)node->data;
            if (A->lastpos == NULL)
            {
                //lastpos(A) = lastpos(left)
                A->lastpos = set_copy(ast_lastpos(A->body));
            }
            return A->lastpos;
        }
        
        default:
        {
            printf("ERROR reached end of lastpos function, which should be impossible\n");
            return NULL;
        }
    }
}

/**
    return the followpos set of the current node. 
    
    ensure that ast_compute_followpos() has been called before this, otherwise these may be incomplete
    (unless in currently constructing followpos, which calls this in intermediate states)
*/
set* ast_get_followpos(obj* node)
{
    assert(node != NULL);
    assert(node->type == ASTCat_t
        || node->type == ASTOr_t
        || node->type == ASTStar_t
        || node->type == ASTLeaf_t);

    switch (node->type)
    {
        case ASTCat_t:
        case ASTOr_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            if (A->followpos == NULL) 
            { 
                A->followpos = new_set(); 
            }
            return A->followpos;
        }
        case ASTStar_t:
        {
            unary_ast* A = *(unary_ast**)node->data;
            if (A->followpos == NULL) 
            { 
                A->followpos = new_set(); 
            }
            return A->followpos;
        }
        case ASTLeaf_t:
        {
            node_ast* A = *(node_ast**)node->data;
            if (A->followpos == NULL) 
            { 
                A->followpos = new_set(); 
            }
            return A->followpos;
        }
        default: 
        { 
            printf("ERROR: ast_get_followpos() should not reach this point\n");
            return NULL;
        }
    }
}

/**
    set followpos in the ast node to point to the new value
*/
void ast_set_followpos(obj* node, set* followpos)
{
    assert(node != NULL);
    assert(node->type == ASTCat_t
        || node->type == ASTOr_t
        || node->type == ASTStar_t
        || node->type == ASTLeaf_t);

    switch (node->type)
    {
        case ASTCat_t:
        case ASTOr_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            A->followpos = followpos;
            return;
        }
        case ASTStar_t:
        {
            unary_ast* A = *(unary_ast**)node->data;
            A->followpos = followpos;
            return;
        }
        case ASTLeaf_t:
        {
            node_ast* A = *(node_ast**)node->data;
            A->followpos = followpos;
            return;
        }
        default: 
        { 
            printf("ERROR: ast_get_followpos() should not reach this point\n");
            return;
        }
    }
}

/**
    compute the followpos set for every node in the ast
*/
void ast_compute_followpos(obj* root, vect* nodes_list, dict* id_to_node)
{
    //for every node in the list of nodes, handle computing followpos
    for (int i = 0; i < vect_size(nodes_list); i++)
    {
        obj* node = vect_get(nodes_list, i);
        switch (node->type)
        {
            case ASTCat_t:
            {
                binary_ast* A = *(binary_ast**)node->data;
                if (A->followpos == NULL) 
                { 
                    A->followpos = new_set(); 
                }
                ast_compute_followpos_cat(node, id_to_node);
                break;
            }
            case ASTStar_t:
            {
                unary_ast* A = *(unary_ast**)node->data;
                if (A->followpos == NULL) 
                { 
                    A->followpos = new_set(); 
                }
                ast_compute_followpos_star(node, id_to_node);
                break;
            }
            case ASTOr_t:
            {
                binary_ast* A = *(binary_ast**)node->data;
                if (A->followpos == NULL) 
                { 
                    A->followpos = new_set(); 
                }
                break;
            }
            case ASTLeaf_t: 
            {
                node_ast* A = *(node_ast**)node->data;
                if (A->followpos == NULL) 
                { 
                    A->followpos = new_set(); 
                }
                break;
            }
            default:
            {
                printf("ERROR reached end of ast_compute_followpos() function, which should be impossible\n");
                break;
            }
        }
    }
}


/**
    Compute followpos for each element in the cat node.
    
    "If n is a cat-node with left child c1 and right child c2 , 
    then for every position i in lastpos(c1), all positions in firstpos(c2) are in followpos(i)"
*/
void ast_compute_followpos_cat(obj* cat_node, dict* id_to_node)
{
    assert(cat_node->type == ASTCat_t);
    binary_ast* A = *(binary_ast**)cat_node->data;
    obj* left = A->left;
    obj* right = A->right;
    set* lastpos_left = ast_lastpos(left);
    set* firstpos_right = ast_firstpos(right);

    for (int i = 0; i < set_size(lastpos_left); i++)
    {
        obj* node_i = dict_get(id_to_node, lastpos_left->d->entries[i].key);
        set* followpos_i = ast_get_followpos(node_i);
        ast_set_followpos(node_i, set_union(followpos_i, firstpos_right));
        set_free(followpos_i); //free the now unused set
    }
}

/**
    Compute followpos for each element in the star node.

    "If n is a star-node, and i is a position in lastpos(n), 
    then all positions in firstpos(n) are in followpos(i)"
*/
void ast_compute_followpos_star(obj* star_node, dict* id_to_node)
{
    assert(star_node->type == ASTStar_t);
    set* lastpos_n = ast_lastpos(star_node);
    set* firstpos_n = ast_firstpos(star_node);

    for (int i = 0; i < set_size(lastpos_n); i++)
    {
        obj* node_i = dict_get(id_to_node, lastpos_n->d->entries[i].key);
        set* followpos_i = ast_get_followpos(node_i);
        ast_set_followpos(node_i, set_union(followpos_i, firstpos_n));
        set_free(followpos_i); //free the now unused set
    }
}


/**
    Recursively compute a list of all nodes in the AST.

    @param node is the current node in the tree
    @param nodes_list is the list to store a reference to all nodes in
*/
vect* ast_get_nodes_list(obj* node, vect* nodes_list)
{
    assert(node != NULL);
    assert(node->type == ASTCat_t
        || node->type == ASTOr_t
        || node->type == ASTStar_t
        || node->type == ASTLeaf_t);

    if (nodes_list == NULL) //if this is the first call, create the nodeslist vector
    {
        nodes_list = new_vect();
    }

    //add this node to the list
    vect_append(nodes_list, node);

    switch (node->type)
    {
        case ASTLeaf_t: 
        {
            //no further nodes to add
            return nodes_list;
        }
        case ASTCat_t:
        case ASTOr_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            ast_get_nodes_list(A->left, nodes_list);
            ast_get_nodes_list(A->right, nodes_list);
            return nodes_list;
        }
        case ASTStar_t:
        {
            unary_ast* A = *(unary_ast**)node->data;
            ast_get_nodes_list(A->body, nodes_list);
            return nodes_list;
        }
        default:
        {
            printf("ERROR reached end of ast_get_nodes_list_inner() function, which should be impossible\n");
            return NULL;
        }
    }
}


/**
    Create a map from each node's id to its reference in the AST
*/
dict* ast_get_ids_to_nodes(vect* nodes_list)
{
    //set up a map from each node's id to its own reference
    dict* id_to_node = new_dict();
    for (int i = 0; i < vect_size(nodes_list); i++)
    {
        obj* node = vect_get(nodes_list, i);
        if (node->type == ASTLeaf_t)
        {
            node_ast* A = *(node_ast**)node->data;
            dict_set(id_to_node, new_uint(A->id), node);
        }
    }
    return id_to_node;
}


obj* ast_copy(obj* node)
{
    assert(node != NULL);
    assert(node->type == ASTCat_t
        || node->type == ASTOr_t
        || node->type == ASTStar_t
        || node->type == ASTLeaf_t);

    switch (node->type)
    {
        case ASTLeaf_t: 
        {
            node_ast* A = *(node_ast**)node->data;
            return new_ast_leaf_obj(A->codepoint);
        }
        case ASTCat_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            return new_ast_cat_obj(ast_copy(A->left), ast_copy(A->right));
        }
        case ASTOr_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            return new_ast_or_obj(ast_copy(A->left), ast_copy(A->right));
        }
        case ASTStar_t:
        {
            unary_ast* A = *(unary_ast**)node->data;
            return new_ast_star_obj(ast_copy(A->body));
        }
        default:
        {
            printf("ERROR reached end of ast_get_nodes_list_inner() function, which should be impossible\n");
            return NULL;
        }
    }
}

void ast_uniqueify_ids(vect* nodes_list)
{
    for (uint64_t i = 0; i < vect_size(nodes_list); i++)
    {
        obj* node = vect_get(nodes_list, i);

        assert(node != NULL);
        assert(node->type == ASTCat_t
            || node->type == ASTOr_t
            || node->type == ASTStar_t
            || node->type == ASTLeaf_t);

        //only leaf nodes have IDs. Reassign so that ID is unique
        if (node->type == ASTLeaf_t)
        {
            node_ast* A = *(node_ast**)node->data;
            A->id = i;
        }
    }
}


/**
    Create a rule table consisting of state-character pairs mapping to next states
*/
void ast_generate_trans_table(obj* root, set** ret_accepting_states, dict** ret_trans_table)
{
    //augment the AST with the special AUGMENT_CHAR delimiter
    obj* goal_node = new_ast_leaf_obj(AUGMENT_CHAR);
    obj* augment = new_ast_cat_obj(root, goal_node);
    // printf("\naugmented rule: ");
    // obj_print(augment);
    // printf("\n");


    //ensure nodes have unique id's and compute followpos. 
    //also get copies of 1) a list of all nodes (nodes_list) and 2) a map from node ids to their reference (id_to_node)
    vect* nodes_list = ast_get_nodes_list(augment, NULL);             
    ast_uniqueify_ids(nodes_list);                          
    dict* id_to_node = ast_get_ids_to_nodes(nodes_list);
    ast_compute_followpos(augment, nodes_list, id_to_node);

    // ast_repr(augment); printf("\n");
    // set* firstpos = ast_firstpos(augment);
    // printf("rule firstpos: "); set_str(firstpos); printf("\n");

    //Dstates is represented by a dict with an index marker for identifying which states have been "marked"
    dict* states = new_dict();
    int marker = 0;

    //Dtran is represented by a dict that maps from id-codepoint pairs to the following state id
    dict* trans_table = new_dict();

    //add the set firstpos(augment) to states
    dict_set(states, new_set_obj(ast_firstpos(augment)), new_uint(0));

    while (marker < dict_size(states))
    {
        //get the set S from our dict of sets, at index [marker], and its S_id
        obj* S_obj = states->entries[marker].key;
        obj* S_id_obj = dict_get(states, S_obj);
        set* S = *(set**)S_obj->data;
        uint64_t S_id = *(uint64_t*)S_id_obj->data;
        marker++;

        //create a dict* symbol_to_nodes that maps from every codepoint in S to a vect of the nodes in S that have that codepoint
        dict* symbol_to_ids = ast_get_symbol_to_ids(S, id_to_node);

        //for every input symbol a in symbol_to_ids
        for (int i = 0; i < dict_size(symbol_to_ids); i++)
        {
            //U is the union of follopos of all states in symbol_to_ids[a]
            set* U = new_set();

            vect* ids_list = *(vect**)symbol_to_ids->entries[i].value->data;
            uint32_t codepoint = *(uint32_t*)symbol_to_ids->entries[i].key->data;
            
            if (codepoint == AUGMENT_CHAR) //skip all AUGMENT_CHAR instances, as we don't actually want them in the transition table
            {
                set_free(U);
                continue;
            }

            for (int j = 0; j < vect_size(ids_list); j++) 
            {
                // for each id, U = U union followpos(id) 
                obj* id_obj = vect_get(ids_list, j);
                obj* node_obj = dict_get(id_to_node, id_obj);
                U = set_union_equals(U, ast_get_followpos(node_obj));
            }
            // printf("next states on \""); unicode_str(codepoint); printf("\" -> "); set_str(U); printf("\n");


            // if U not in states, create a new entry for it
            obj* U_obj = new_set_obj(U);
            if (!dict_contains(states, U_obj))
            {
                dict_set(states, U_obj, new_uint(dict_size(states))); //automatically unmarked since it's added to the end
            }
            obj* U_id_obj = dict_get(states, U_obj);
            uint64_t U_id = *(uint64_t*)U_id_obj->data;
            dict_set(trans_table, ast_get_transition_key(S_id, codepoint), U_id_obj);
        }

    }

    //compute the goal states based on which sets of node ids contain the goal's id
    set* accepting_states = new_set();
    obj* goal_id_obj = new_uint((*(node_ast**)goal_node->data)->id);
    for (int i = 0; i < dict_size(states); i++)
    {
        set* state_ids = *(set**)states->entries[i].key->data;
        if (set_contains(state_ids, goal_id_obj))
        {
            obj* state_id_obj = states->entries[i].value;
            set_add(accepting_states, obj_copy(state_id_obj));
        }
    }


    vect_free_list_only(nodes_list);

    //instead, set each obj value to NULL,
    //and then regular dict_free(id_to_node);
    // dict_free_except_values(id_to_node);

    // printf("\n");
    // printf("goal node id: %lu\n", (*(node_ast**)goal_node->data)->id);
    // printf("goal states: "); set_str(accepting_states); printf("\n");
    // printf("states: "); dict_str(states); printf("\n");
    // printf("trans table: "); ast_print_trans_table(trans_table); printf("\n");
    // printf("\n\n");

    //set the return values to the table and accepting states generated
    *ret_trans_table = trans_table;
    *ret_accepting_states = accepting_states;
}


/**
    create a unique integer from a set ID and a char codepoint

    Note that codepoints are by definition up to 2^21 - 1
    So the codepoint will take 21 bits of the 64-bit key
    and the id will take the remaining 43 bits
    (this restricts ids to be less than 2^43, or 8,796,093,022,208)
*/
obj* ast_get_transition_key(uint64_t id, uint32_t codepoint)
{
    uint64_t key = (id << 21) | (codepoint & 0x001FFFFF);
    // printf("id: %lu, char: '", id); unicode_str(codepoint); printf("', key: %lu\n", key);
    return new_uint(key);
}

/**
    print out the transition table in a more readable format
*/
void ast_print_trans_table(dict* trans_table)
{
    printf("[");
    for (int i = 0; i < dict_size(trans_table); i++)
    {
        if (i != 0) printf(", ");
        uint64_t key = *(uint64_t*)trans_table->entries[i].key->data;
        uint64_t id = key >> 21;
        uint32_t codepoint = (key & 0x001FFFFF);
        printf("(%lu, '", id); unicode_str(codepoint); printf("')");
        printf(" -> ");
        obj_print(trans_table->entries[i].value);
    }
    printf("]");
}

/**
    return a map from every codepoint to the nodes that have that codepoint
*/
dict* ast_get_symbol_to_ids(set* S, dict* id_to_node)
{
    dict* symbol_to_ids = new_dict();

    for (int i = 0; i < set_size(S); i++)
    {
        //get the id of the current node
        obj* id_obj = S->d->entries[i].key;
        assert(id_obj != NULL);
        assert(id_obj->type == UInteger_t);
        uint64_t id = *(uint64_t*)id_obj->data;

        //get the actual node based on its id
        obj* node_obj = dict_get(id_to_node, id_obj);        
        assert(node_obj->type == ASTLeaf_t);
        node_ast* node = *(node_ast**)node_obj->data;
        
        //create a codepoint key based on the node's codepoint
        obj* codepoint = new_char(node->codepoint);
        
        //if this codepoint isn't in symbol_to_ids, create an empty vect at that codepoint
        obj* id_list = dict_get(symbol_to_ids, codepoint);
        if (id_list == NULL)
        {
            id_list = new_vect_obj(NULL);
            dict_set(symbol_to_ids, codepoint, id_list);
            //don't free codepoint here because it's being used as the key in the dict
        } 
        else 
        {
            obj_free(codepoint); //the vect already exists, so free the key that is no longer being used
        }

        //add this node's id into the list mapped by to by the codepoint
        vect_append(*(vect**)id_list->data, new_uint(id));
    }

    // printf("symbol_to_ids: "); dict_str(symbol_to_ids); printf("\n");
    return symbol_to_ids;
}



#endif