#ifndef MAST_C
#define MAST_C

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

#include "utilities.c"
#include "object.c"
#include "set.c"

#include <assert.h>

//Meta Abstract Syntax Tree (MAST) definitions

//represents a leaf node in the AST
//- c, i.e. an occurance of a single unicode character
typedef struct node_ast_struct
{
    uint32_t codepoint; //any unicode character can be a leaf
    uint64_t id;        //keep track of the node ID. TODO->probably keep a dict that maps from ID to the AST obj...
    bool* nullable;
    set* firstpos;
    set* lastpos;
    set* followpos;
} node_ast;

//represents a unary node in the AST
//- (body), i.e. 1 occurance of body
//- [body], i.e. 1 or more occurance of body. (note) that actually this will probably be represented by (body | e)
//- {body}, i.e. 0 or more occurances of body
typedef struct unary_ast_struct
{
    obj* body;
    bool* nullable;
    set* firstpos;
    set* lastpos;
    set* followpos;
} unary_ast;

//represents a binary node in the AST
//- left | right, i.e. left or right
//- left,right, i.e. left followed by right
typedef struct binary_ast_struct
{
    obj* left;
    obj* right;
    bool* nullable;
    set* firstpos;
    set* lastpos;
    set* followpos;
} binary_ast;

node_ast* new_node_ast(uint32_t c);
unary_ast* new_unary_ast(obj* body);
binary_ast* new_binary_ast(obj* left, obj* right);
obj* new_ast_leaf_obj(uint32_t c);
obj* new_ast_star_obj(obj* body);
obj* new_ast_or_obj(obj* left, obj* right);
obj* new_ast_cat_obj(obj* left, obj* right);
void ast_repr(obj* root);
void ast_repr_inner(obj* node, int indent);
void ast_str(obj* node);
bool ast_nullable(obj* node);
set* ast_firstpos(obj* node);
set* ast_lastpos(obj* node);
set* ast_get_followpos(obj* node);
void ast_set_followpos(obj* node, set* followpos);
void ast_compute_followpos(obj* root);
void ast_compute_followpos_cat(obj* cat_node, dict* id_to_node);
void ast_compute_followpos_star(obj* star_node, dict* id_to_node);
void ast_get_nodes_list(obj* node, vect* nodes);
obj* ast_copy(obj* node);
void ast_uniqueify_ids(vect* nodes_list);


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
            put_unicode(A->codepoint ? A->codepoint : 0x2300); //print the character, or the ⌀ symbol
            printf(" [id: %lu, fp: ", A->id); 
            // set_str(ast_firstpos(node)); printf(", lastpos: ");
            // set_str(ast_lastpos(node)); printf(", followpos: ");
            set_str(A->followpos); printf("]\n");
            // printf(" [id: %lu]\n", A->id);
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
            put_unicode(A->codepoint ? A->codepoint : 0x2300); //print the character, or the ⌀ (0x2300) symbol
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
void ast_compute_followpos(obj* root)
{
    //get all nodes in the AST in list form
    vect* nodes_list = new_vect();
    ast_get_nodes_list(root, nodes_list);

    //ensure that every node has a unique id
    ast_uniqueify_ids(nodes_list);

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

    vect_free_list_only(nodes_list);

    //instead, set each obj value to NULL,
    //and then regular dict_free(id_to_node);
    // dict_free_except_values(id_to_node);
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
void ast_get_nodes_list(obj* node, vect* nodes_list)
{
    assert(node != NULL);
    assert(node->type == ASTCat_t
        || node->type == ASTOr_t
        || node->type == ASTStar_t
        || node->type == ASTLeaf_t);

    //add this node to the list
    vect_append(nodes_list, node);

    switch (node->type)
    {
        case ASTLeaf_t: 
        {
            //no further nodes to add
            return;
        }
        case ASTCat_t:
        case ASTOr_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            ast_get_nodes_list(A->left, nodes_list);
            ast_get_nodes_list(A->right, nodes_list);
            return;
        }
        case ASTStar_t:
        {
            unary_ast* A = *(unary_ast**)node->data;
            ast_get_nodes_list(A->body, nodes_list);
            return;
        }
        default:
        {
            printf("ERROR reached end of ast_get_nodes_list_inner() function, which should be impossible\n");
        }
    }
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




#endif