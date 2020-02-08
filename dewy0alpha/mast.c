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
set* ast_followpos(obj* node);
vect* ast_get_nodes_list(obj* root);
void ast_get_nodes_list_inner(obj* node, vect* nodes);

//rest of the AST functions


//global int to give each leaf node a unique identifier
uint64_t _ast_node_id_counter = 0;

node_ast* new_node_ast(uint32_t c)
{
    node_ast* A = malloc(sizeof(node_ast));
    A->codepoint = c;
    A->id = _ast_node_id_counter++; //assign a unique identifier
    if (c != 0) //if codepoint is not 0, then it is a non-null leaf
    {
        A->nullable = new_bool_ptr(false);
        A->firstpos = new_set();
        set_add(A->firstpos, new_uint(A->id));  //firstpos contains only c
        A->lastpos = new_set();
        set_add(A->lastpos, new_uint(A->id));   //lastpos contains only c
        A->followpos = NULL;                    //followpos will be computed later once the tree is complete
    }
    else    //otherwise this is an ϵ (epsilon), i.e. null leaf
    {
        A->nullable = new_bool_ptr(true);       //the null char is by definition nullable
        A->firstpos = new_set();                //firstpos is by definition an empty set
        A->lastpos = new_set();                 //lastpos is by definition an empty set
        A->followpos = NULL;                    //followpos will be computed later once the tree is complete
    }

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
            ast_repr_inner(A->left, indent+1);
            ast_repr_inner(A->right, indent+1);
            return;
        }
        case ASTOr_t:
        {
            binary_ast* A = *(binary_ast**)node->data;
            printf("(|)\n");
            ast_repr_inner(A->left, indent+1);
            ast_repr_inner(A->right, indent+1);
            return;
        }
        case ASTStar_t:
        {
            unary_ast* A = *(unary_ast**)node->data;
            printf("(*)\n");
            ast_repr_inner(A->body, indent+1);
            return;
        }
        case ASTLeaf_t:
        {
            node_ast* A = *(node_ast**)node->data;
            printf(" ");
            put_unicode(A->codepoint ? A->codepoint : 0x03F5); //print the character, or the ϵ symbol
            printf("\n");
            return;
        }
        default: { printf("ERROR: not an AST type (%d)\n", node->type); return; }
    }
}

void ast_str(obj* node)
{
    // if (!node) { return; }
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
            // printf("(");
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
            // printf("(");
            ast_str(A->left);
            printf(" | ");
            ast_str(A->right);
            // printf(")");
            return;
        }
        case ASTStar_t:
        {
            unary_ast* A = *(unary_ast**)node->data;
            printf("(");
            ast_str(A->body);
            printf(")*");
            return;
        }
        case ASTLeaf_t:
        {
            node_ast* A = *(node_ast**)node->data;
            put_unicode(A->codepoint ? A->codepoint : 0x03F5); //print the character, or the ϵ symbol
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
            //firstpos is preset for leaf nodes
            node_ast* A = *(node_ast**)node->data;
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
            //lastpos is preset for leaf nodes
            node_ast* A = *(node_ast**)node->data;
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

// set* ast_followpos(obj* node){}
// void ast_compute_followpos(obj* root){}

/**
    Return a list of all nodes in the AST
*/
vect* ast_get_nodes_list(obj* root)
{
    vect* nodes_list = new_vect();
    ast_get_nodes_list_inner(root, nodes_list);
    return nodes_list;
}

void ast_get_nodes_list_inner(obj* node, vect* nodes_list)
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
            ast_get_nodes_list_inner(A->left, nodes_list);
            ast_get_nodes_list_inner(A->right, nodes_list);
            return;
        }
        case ASTStar_t:
        {
            unary_ast* A = *(unary_ast**)node->data;
            ast_get_nodes_list_inner(A->body, nodes_list);
            return;
        }
        default:
        {
            printf("ERROR reached end of ast_get_nodes_list_inner() function, which should be impossible\n");
        }
    }
}




#endif