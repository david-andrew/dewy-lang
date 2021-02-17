#ifndef TYPES_H
#define TYPES_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

/**
    Enum/type declaration for each of the different types object types that exist
*/
typedef enum obj_types 
{ 
    Boolean_t,
    Character_t,
    Integer_t, 
    UInteger_t,
    String_t,
    Token_t,
    Vector_t,
    Dictionary_t,
    Set_t,
    ASTCat_t,
    ASTOr_t,
    ASTStar_t,
    ASTLeaf_t,
} obj_type;

/**
    Struct/type declaration for generic objects
*/
typedef struct obj_struct
{
    obj_type type;  //integer specifying what type of object.
    size_t size;    //size of the data allocated for this object
    void* data;     //data allocated for this object
} obj;

/**
    Struct/type declaration for 1D lists of objects. Implemented as an ArrayDeque. 
    see: http://opendatastructures.org/ods-java/2_4_ArrayDeque_Fast_Deque_O.html
*/
typedef struct vect_struct 
{
    size_t head;
    size_t size;
    size_t capacity;
    obj** list;
} vect;

/**
    Struct/type declaration for (hash,key,value) tuples, i.e. a single entry in a dictionary
*/
typedef struct dict_entry_struct 
{
    uint64_t hash;
    obj* key;
    obj* value;
} dict_entry;


/**
    Struct/type declaration for dictionary
*/
typedef struct dict_struct
{
    size_t size;
    size_t icapacity;
    size_t ecapacity;
    size_t* indices;
    dict_entry* entries;
} dict;

/**
    Struct/type declaration for sets. Currently just wraps dictionary. TODO->have dedicated type
*/
typedef struct set_struct
{
    dict* d; //a set is just a wrapper around a dict
} set;


/**
    Enum/type declaration for each possible token type for reading syntax rules
*/
typedef enum token_types
{
    hashtag,
    meta_string,
    meta_hex_number,
    meta_comma,
    meta_semicolon,
    meta_vertical_bar,
    // meta_minus,
    meta_equals_sign,
    meta_left_parenthesis,
    meta_right_parenthesis,
    meta_left_bracket,
    meta_right_bracket,
    meta_left_brace,
    meta_right_brace,
    whitespace,
    comment,
} token_type;

/**
    Struct/type declaration for tokens for lexer/parser
*/
typedef struct tokens
{
    token_type type;
    char* content;
} token;


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


#endif