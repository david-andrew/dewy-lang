#ifndef MAST_C
#define MAST_C

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

#include "utilities.c"
#include "object.c"
#include "set.c"

//Meta Abstract Syntax Tree (MAST) definitions

//represents a leaf node in the AST
//- c, i.e. an occurance of a single unicode character
typedef struct node_ast_struct
{
    uint32_t codepoint; //any unicode character can be a leaf
    uint64_t id;        //keep track of the node ID. TODO->probably keep a dict that maps from ID to the AST obj...
    obj* nullable;
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
    obj* nullable;
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
    obj* nullable;
    set* firstpos;
    set* lastpos;
    set* followpos;
} binary_ast;

node_ast* new_node_ast(uint32_t c);
unary_ast* new_unary_ast(obj* body);
binary_ast* new_binary_ast(obj* left, obj* right);
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
        A->nullable = new_bool(false);
        A->firstpos = new_set();
        set_add(A->firstpos, new_char(c));  //firstpos contains only c
        A->lastpos = new_set();
        set_add(A->lastpos, new_char(c));   //lastpos contains only c
        A->followpos = NULL;                //followpos will be computed later once the tree is complete
    }
    else    //otherwise this is an ϵ (epsilon), i.e. null leaf
    {
        A->nullable = new_bool(true);   //the null char is by definition nullable
        A->firstpos = new_set();        //firstpos is by definition an empty set
        A->lastpos = new_set();         //lastpos is by definition an empty set
        A->followpos = NULL;            //followpos will be computed later once the tree is complete
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


#endif