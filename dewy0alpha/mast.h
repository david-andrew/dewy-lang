#ifndef MAST_H
#define MAST_H

#include <stdint.h>

#include "object.h"
#include "set.h"

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

#endif