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
    *s = (sppf){.nodes=new_set(), .edges=new_dict(), .children=new_set()};
    return s;
}


// /**
//  * Add a node and its (possibly NULL) children to the sppf.
//  * Does not modify `node` or `children_indices`
//  */
// uint64_t sppf_add_node(sppf* s, sppf_node* node, vect* children_indices)
// {
//     //get the index of the children list from the set of children lists
//     obj children_indices_obj = (obj){.type=Vector_t, .data=children_indices};
//     uint64_t children_idx = !set_contains(s->children, &children_indices_obj) ? 
//         set_add_return_index(s->children, obj_copy(&children_indices_obj)) :
//         set_get_entries_index(s->children, &children_indices_obj);
//     obj children_idx_obj = (obj){.type=UInteger_t, .data=&children_idx};

//     //if the node doesn't exist in the dictionary, add it.
//     obj node_obj = (obj){.type=SPPFNode_t, .data=node};
//     if (!dict_contains(s->nodes, &node_obj))
//     {
//         return dict_set_return_index(s->nodes, obj_copy(&node_obj), obj_copy(&children_idx_obj));
//     }
//     else
//     {
//         uint64_t index = 
//     }
// }



/**
 * Add a node to the SPPF. If the node exists already, the new one is freed.
 * Returns the index of the node in the nodes set.
 */
uint64_t sppf_add_node(sppf* s, sppf_node* node)
{
    //check if the object is in the set already
    obj node_obj = (obj){.type=SPPFNode_t, .data=node};
    uint64_t index = set_get_entries_index(s->nodes, &node_obj);
    
    //if the object is not in the set, add it, and update the index
    if (set_is_index_empty(index))
    {
        index = set_add_return_index(s->nodes, new_sppf_node_obj(node));
    }
    else
    {
        sppf_node_free(node);
    }

    return index;
}


/**
 * Add a node + children to the SPPF. If the node already exists with children,
 * a packed node is create.
 */
void sppf_add_node_with_children(sppf* s, sppf_node* node, vect* children)
{
    uint64_t node_idx = sppf_add_node(s, node);
    uint64_t children_idx = sppf_add_children(s, children);
    sppf_connect_node_to_children(s, node_idx, children_idx);
}


/**
 * Add the vector of children node indices to the set of children vectors.
 * Returns the index of the vector in the set.
 */
uint64_t sppf_add_children(sppf* s, vect* children)
{
    //check if the object is in the set already
    obj children_obj = (obj){.type=Vector_t, .data=children};
    uint64_t index = set_get_entries_index(s->children, &children_obj);
    
    //if the object is not in the set, add it, and update the index
    if (set_is_index_empty(index))
    {
        index = set_add_return_index(s->children, new_vect_obj(children));
    }
    else
    {
        vect_free(children);
    }

    return index;
}


/**
 * Indicate in the SPPF that the given node has the given children.
 * If the node already has children, then a packed node is created.
 */
void sppf_connect_node_to_children(sppf* s, uint64_t node_idx, uint64_t children_idx)
{
    obj node_idx_obj = (obj){.type=UInteger_t, .data=&node_idx};
    obj children_idx_obj = (obj){.type=UInteger_t, .data=&children_idx};

    if (!dict_contains(s->edges, &node_idx_obj))
    {
        dict_set(s->edges, obj_copy(&node_idx_obj), obj_copy(&children_idx_obj));
        return;
    }

    //an entry exists already
    obj* children_obj = dict_get(s->edges, &node_idx_obj);
    
    //for vector simply append the children_idx_obj to the vector
    if (children_obj->type == Vector_t)
    {
        vect* packed_node = children_obj->data;
        vect_append(packed_node, obj_copy(&children_idx_obj));
        return;
    }

    //otherwise, need to replace the current UInteger_t type with a vector
    size_t index = dict_get_entries_index(s->edges, &node_idx_obj);
    vect* packed_node = new_vect();
    vect_append(packed_node, children_obj);
    vect_append(packed_node, obj_copy(&children_idx_obj));
    s->edges->entries[index].value = new_vect_obj(packed_node);    
}


/**
 * 
 */
uint64_t sppf_add_leaf_node(sppf* s, uint64_t source_idx)
{

}


/**
 * 
 */
uint64_t sppf_add_nullable_symbol_node(sppf* s, uint64_t symbol_idx)
{

}


/**
 * 
 */
uint64_t sppf_add_nullable_string_node(sppf* s, slice* nullable_part)
{

}


/**
 * 
 */
uint64_t sppf_add_inner_node(sppf* s, uint64_t head_idx, uint64_t source_start_idx, uint64_t source_end_idx, vect* children_indices)
{

}


/**
 * Release allocated resources for the SPPF.
 */
void sppf_free(sppf* s)
{
    set_free(s->nodes);
    dict_free(s->edges);
    set_free(s->children);
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
 * Create a new SPPF node that points to a nullable symbol.
 */
sppf_node* new_sppf_nullable_symbol_node(uint64_t symbol_idx)
{
    sppf_node* n = malloc(sizeof(sppf_node));
    *n = (sppf_node){.type=sppf_nullable_symbol, .node.nullable_symbol=symbol_idx};
    return n;
}

/**
 * Create a new SPPF node that points to a nullable part of a production.
 * nullable_part is not modified by this function.
 */
sppf_node* new_sppf_nullable_string_node(slice* nullable_part)
{
    sppf_node* n = malloc(sizeof(sppf_node));
    *n = (sppf_node){.type=sppf_nullable_string, .node.nullable_string=slice_copy_to_vect(nullable_part)};
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
obj* new_sppf_node_obj(sppf_node* n)
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
        case sppf_nullable_symbol: return hash_uint(n->node.nullable_symbol);
        case sppf_nullable_string: return vect_hash(n->node.nullable_string);
        case sppf_inner:
        {
            uint64_t seq[] = {n->node.inner.head_idx, n->node.inner.source_start_idx, n->node.inner.source_end_idx};
            return hash_uint_sequence(seq, sizeof(seq) / sizeof(uint64_t));
        }
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
        case sppf_nullable_symbol: return left->node.nullable_symbol == right->node.nullable_symbol;
        case sppf_nullable_string: return vect_equals(left->node.nullable_string, right->node.nullable_string);
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
        {
            unicode_str(srnglr_get_input_source()[n->node.leaf]);
            printf(", %"PRIu64, n->node.leaf); 
            break;
        }
        case sppf_nullable_symbol:
        {
            obj* symbol = metaparser_get_symbol(n->node.nullable_symbol); 
            printf("ϵ: "); obj_str(symbol); 
            break;
        }
        case sppf_nullable_string:
        {
            printf("ϵ: ");
            for (size_t i = 0; i < vect_size(n->node.nullable_string); i++)
            {
                uint64_t* symbol_idx = vect_get(n->node.nullable_string, i)->data;
                obj* symbol = metaparser_get_symbol(*symbol_idx);
                obj_str(symbol);
                if (i < vect_size(n->node.nullable_string) - 1){ printf(", "); }
            }
            break;
        }
        case sppf_inner:
        {
            obj_str(metaparser_get_symbol(n->node.inner.head_idx));
            printf(", %"PRIu64", %"PRIu64, n->node.inner.source_start_idx, n->node.inner.source_end_idx);
            break;
        }
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
        case sppf_nullable_symbol: printf("sppf_nullable_symbol{ϵ%"PRIu64"}", n->node.nullable_symbol); break;
        case sppf_nullable_string: printf("sppf_nullable_string{ϵ"); vect_str(n->node.nullable_string); printf("}"); break;
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
    //only potential inner allocation is for nullable strings
    if (n->type == sppf_nullable_string)
    {
        vect_free(n->node.nullable_string);
    }

    //free the node container
    free(n);
}




#endif