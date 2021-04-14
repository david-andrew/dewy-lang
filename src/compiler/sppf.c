#ifndef SPPF_C
#define SPPF_C

#include <stdlib.h>
#include <stdio.h>
#include <inttypes.h>

#include "sppf.h"
#include "utilities.h"
#include "ustring.h"
#include "srnglr.h"
#include "metaparser.h"


/**
 * Create a new Shared Packed Parse Forest.
 */
sppf* new_sppf()
{
    sppf* s = malloc(sizeof(sppf));
    *s = (sppf){.nodes=new_dict(), .children=new_set(), .gss_sppf_map=new_dict()};
    return s;
}


/**
 * Release allocated resources for the SPPF.
 */
void sppf_free(sppf* s)
{
    dict_free(s->nodes);
    set_free(s->children);
    dict_free(s->gss_sppf_map);
    free(s);
}


/**
 * Create a new SPPF node that points to a specific source character.
 */
sppf_node* new_sppf_leaf_node(uint64_t source_idx)
{
    sppf_node* n = malloc(sizeof(sppf_node));
    *n = (sppf_node){.type=sppf_leaf, .node.leaf=source_idx};
    return n;
}


/**
 * Create a new SPPF node that points to a nullable part of a production.
 */
sppf_node* new_sppf_nullable_node(uint64_t nullable_idx)
{
    sppf_node* n = malloc(sizeof(sppf_node));
    *n = (sppf_node){.type=sppf_leaf, .node.nullable=nullable_idx};
    return n;
}


/**
 * Create a new SPPF node that will point to a list of children nodes,
 * or a packed list of lists of children nodes.
 * (inner nodes themselves don't contain the children, just header info)
 */
sppf_node* new_sppf_inner_node(uint64_t head_idx, uint64_t source_start_idx, uint64_t source_end_idx)
{
    sppf_node* n = malloc(sizeof(sppf_node));
    *n = (sppf_node){
        .type=sppf_leaf, 
        .node.inner={
            .head_idx=head_idx, 
            .source_start_idx=source_start_idx, 
            .source_end_idx=source_end_idx
        }
    };
    return n;
}


/**
 * Create a new SPPF node wrapped in an object.
 */
obj* net_sppf_node_obj(sppf_node* n)
{
    obj* N = malloc(sizeof(obj));
    *N = (obj){.type=SPPFNode_t, .data=n};
    return N;
}


/**
 * Return a hash of the SPPF node's contained data.
 * Hash does not account for possible children of the SPPF node.
 */
uint64_t sppf_node_hash(sppf_node* n)
{
    switch (n->type)
    {
        case sppf_leaf: return hash_uint(n->node.leaf);
        case sppf_nullable: return hash_uint(n->node.nullable);
        case sppf_inner:
            uint64_t seq[] = {n->node.inner.head_idx, n->node.inner.source_start_idx, n->node.inner.source_end_idx};
            return hash_uint_sequence(seq, sizeof(seq) / sizeof(uint64_t));
    }
}


/**
 * Determine if two sppf_nodes are equal.
 * Does not account for possible children of the SPPF nodes.
 */
bool sppf_node_equals(sppf_node* left, sppf_node* right)
{
    if (left->type != right->type) { return false; }
    switch (left->type)
    {
        case sppf_leaf: return left->node.leaf == right->node.leaf;
        case sppf_nullable: return left->node.nullable == right->node.nullable;
        case sppf_inner: 
            return left->node.inner.head_idx == right->node.inner.head_idx
                && left->node.inner.source_start_idx == right->node.inner.source_start_idx
                && left->node.inner.source_end_idx == right->node.inner.source_end_idx;
    }
}


/**
 * Print out a representation of the SPPF node.
 */
void sppf_node_str(sppf_node* n)
{
    printf("(");
    switch (n->type)
    {
        case sppf_leaf: 
            unicode_str(srnglr_get_input_source()[n->node.leaf]);
            printf(", %"PRIu64, n->node.leaf); 
            break;

        case sppf_nullable: 
            printf("ϵ%"PRIu64, n->node.nullable); 
            break;
        
        case sppf_inner:
            obj_str(metaparser_get_symbol(n->node.inner.head_idx));
            printf(", %"PRIu64", %"PRIu64, n->node.inner.source_start_idx, n->node.inner.source_end_idx);
            break;
    }
    printf(")");
}


/**
 * Print out the internal representation of the SPPF node.
 */
void sppf_node_repr(sppf_node* n)
{
    switch (n->type)
    {
        case sppf_leaf: printf("sppf_leaf{%"PRIu64"}", n->node.leaf); break;
        case sppf_nullable: printf("sppf_nullable{ϵ%"PRIu64"}", n->node.nullable); break;
        case sppf_inner:
            printf("sppf_inner{%"PRIu64", %"PRIu64", %"PRIu64"}", 
                n->node.inner.head_idx, 
                n->node.inner.source_start_idx, 
                n->node.inner.source_end_idx
            );
            break;
    }
}


/**
 * Release allocated resources for the SPPF node.
 */
void sppf_node_free(sppf_node* n)
{
    free(n);
}




#endif