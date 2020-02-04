#ifndef MAST_C
#define MAST_C

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

#include "mast.h"
#include "utilities.h"
#include "object.h"
#include "set.h"

//Meta Abstract Syntax Tree (MAST) definitions


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