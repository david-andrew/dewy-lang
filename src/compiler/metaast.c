#ifndef METAAST_C
#define METAAST_C

#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <inttypes.h>

#include "metaast.h"
#include "utilities.h"


/**
 * Create a new meta-ast of `type` containing `node`
 * Node may be either a pointer to a metaast_<type>_node, or NULL
 */
metaast* new_metaast(metaast_type type, void* node)
{
    metaast* ast = malloc(sizeof(metaast));
    *ast = (metaast){.type=type, .node=node};
    return ast;
}


/**
 * Create a new meta-ast node with no node content.
 * Used for eps nodes.
 */
metaast* new_metaast_null_node(metaast_type type)
{
    return new_metaast(type, NULL);
}


/**
 * Create new meta-ast node containing a unicode string.
 * used for string and hashtags nodes.
 */
metaast* new_metaast_string_node(metaast_type type, uint32_t* string)
{
    metaast_string_node* node = malloc(sizeof(metaast_string_node));
    *node = (metaast_string_node){.string=string};
    return new_metaast(type, node);
}


/**
 * Create a new meta-ast node for repeating an inner ast.
 * Used for star, plus, and repeat nodes.
 */
metaast* new_metaast_repeat_node(metaast_type type, uint64_t count, metaast* inner)
{
    metaast_repeat_node* node = malloc(sizeof(metaast_repeat_node));
    *node = (metaast_repeat_node){.count=count, .inner=inner};
    return new_metaast(type, node);
}


/**
 * Create a new meta-ast node for applying a unary op to an inner ast.
 * Used for option and compliment nodes.
 */
metaast* new_metaast_unary_op_node(metaast_type type, metaast* inner)
{
    metaast_unary_op_node* node = malloc(sizeof(metaast_unary_op_node));
    *node = (metaast_unary_op_node){.inner=inner};
    return new_metaast(type, node);
}


/**
 * Create a new sequence of meta-ast nodes.
 * Used for either a sequence of node concatenations, or "|" alternates.
 */
metaast* new_metaast_sequence_node(metaast_type type, size_t size, metaast* sequence)
{
    metaast_sequence_node* node = malloc(sizeof(metaast_sequence_node));
    *node = (metaast_sequence_node){.size=size, .sequence=sequence};
    return new_metaast(type, node);
}


/**
 * Create a new meta-ast node representing a binary opration.
 * Used for reject, nofollow, greaterthan, and lessthan.
 */
metaast* new_metaast_binary_op_node(metaast_type type, metaast* left, metaast* right)
{
    metaast_binary_op_node* node = malloc(sizeof(metaast_binary_op_node));
    *node = (metaast_binary_op_node){.left=left, .right=right};
    return new_metaast(type, node);
}


/**
 * Create a new meta-ast containing a charset.
 * Represents normal charsets, hex literals, length 1 strings, and the anyset.
 */
metaast* new_metaast_charset_node(metaast_type type, charset* c)
{
    metaast_charset_node* node = malloc(sizeof(metaast_charset_node));
    *node = (metaast_charset_node){.c=c};
    return new_metaast(type, node);
}


/**
 * Free all allocated resources in the metaast.
 */
void metaast_free(metaast* ast)
{

    switch (ast->type)
    {
        // free specific inner components of nodes
        
        case metaast_string:
        case metaast_identifier:
        {
            metaast_string_node* node = ast->node;
            free(node->string);
            break;
        }
        
        case metaast_charset:
        {
            metaast_charset_node* node = ast->node;
            charset_free(node->c);
            break;
        }
        
        case metaast_star:
        case metaast_plus:
        case metaast_count:
        {
            metaast_repeat_node* node = ast->node;
            metaast_free(node->inner);
            break;
        }
        
        case metaast_option:
        case metaast_compliment:
        {
            metaast_unary_op_node* node = ast->node;
            metaast_free(node->inner);
            break;
        }
        
        case metaast_greaterthan:
        case metaast_lessthan:
        case metaast_reject:
        case metaast_nofollow:
        case metaast_intersect:
        {
            metaast_binary_op_node* node = ast->node;
            metaast_free(node->left);
            metaast_free(node->right);
            break;
        }
        
        case metaast_cat:
        case metaast_or:
        {
            metaast_sequence_node* node = ast->node;
            free(node->sequence);
            break;
        }

        //free container only
        case metaast_eps: break;
    }

    //NULL indicates eps node, which allocated no node
    if (ast->node != NULL)
    { 
        free(ast->node); 
    }
    
    free(ast);
}


/**
 * Sequentially attempt to combine constant expressions in the meta-ast.
 * Returns `true` if folding occurred, else `false`.
 * Repeat until returns `false` to ensure all constants are folded. 
 */
bool metaast_fold_constant(metaast* ast)
{
    if (metaast_fold_charsets(ast)) { return true; }
    if (metaast_fold_strings(ast)) { return true; }
    /*any other constant folding here...*/

    return false;
}


/**
 * Runs a single pass of combining charset expressions in the meta-ast.
 * This includes charset union, intersect, diff, and compliment.
 * Returns `true` if any folding occurred, else `false`.
 * Repeat until returns `false` to ensure all charsets are folded.
 */
bool metaast_fold_charsets(metaast* ast)
{
    return false;
}


/**
 * Runs a single pass of combining string expressions in the meta-ast.
 * This is mainly for cat of sequential strings (or charsets of size 1).
 * Returns `true` if any folding occurred, else `false`.
 * Repeat until returns `false` to ensure all strings are folded.
 */
bool metaast_fold_strings(metaast* ast)
{
    return false;
}



void metaast_type_repr(metaast_type type)
{
    #define printenum(A) case A: printf(#A); break;

    switch (type)
    {
        printenum(metaast_eps)
        // printenum(metaast_capture)     //FUTURE USE
        printenum(metaast_string)
        printenum(metaast_star)
        printenum(metaast_plus)
        printenum(metaast_option)
        printenum(metaast_count)
        printenum(metaast_cat)
        printenum(metaast_or)
        printenum(metaast_greaterthan)
        printenum(metaast_lessthan)
        printenum(metaast_reject)
        printenum(metaast_nofollow)
        printenum(metaast_identifier)
        printenum(metaast_charset)
        printenum(metaast_compliment)
        printenum(metaast_intersect)
    }   
}


/**
 * Print out a string for the given meta-ast
 */
void metaast_str(metaast* ast) { metaast_str_inner(ast, 0); }


/**
 * Inner recursive function for printing out the meta-ast string.
 */
void metaast_str_inner(metaast* ast, int level)
{

}


/**
 * Print out a representation of the given meta-ast
 */
void metaast_repr(metaast* ast) { metaast_repr_inner(ast, 0); }


/**
 * Inner recursive function for printing out the meta-ast representation.
 */
void metaast_repr_inner(metaast* ast, int level)
{
    repeat_str("  ", level);  //print level # tabs
    metaast_type_repr(ast->type);
    switch (ast->type)
    {

        case metaast_string: 
        case metaast_identifier:
        {
            metaast_string_node* node = ast->node;
            printf("(`"); unicode_string_str(node->string); printf("`)\n");
            break;
        }
        
        case metaast_charset:
        {
            metaast_charset_node* node = ast->node;
            charset_str(node->c); printf("\n");
            break;
        }
        
        case metaast_star:
        case metaast_plus:
        case metaast_count:
        {
            metaast_repeat_node* node = ast->node;
            printf("{\n");
            repeat_str("  ", level + 1); printf("count=%"PRIu64"\n", node->count);
            metaast_repr_inner(node->inner, level + 1);
            repeat_str("  ", level); printf("}\n");
            break;
        }
        
        case metaast_option:
        case metaast_compliment:
        {
            metaast_unary_op_node* node = ast->node;
            printf("{\n");
            metaast_repr_inner(node->inner, level + 1);
            repeat_str("  ", level); printf("}\n");
            break;
        }
        
        case metaast_greaterthan:
        case metaast_lessthan:
        case metaast_reject:
        case metaast_nofollow:
        case metaast_intersect:
        {
            metaast_binary_op_node* node = ast->node;
            printf("{\n");
            metaast_repr_inner(node->left, level + 1);
            metaast_repr_inner(node->right, level + 1);
            repeat_str("  ", level); printf("}\n");
            break;
        }
        
        case metaast_cat:
        case metaast_or:
        {
            metaast_sequence_node* node = ast->node;
            printf("{\n");
            for (size_t i = 0; i < node->size; i++)
            {
                metaast_repr_inner(node->sequence + i, level + 1);
            }
            repeat_str("  ", level); printf("}\n");
            break;
        }

        //free container only
        case metaast_eps:
        {
            printf("("); put_unicode(0x03F5); printf(")\n");
            break;
        }
    }
}

#endif