#ifndef SPPF_C
#define SPPF_C

#include "sppf.h"


/**
 * 
 */
sppf* new_sppf()
{

}


/**
 * 
 */
void sppf_free(sppf* s)
{

}


/**
 * 
 */
sppf_node* new_sppf_leaf_node(uint64_t source_idx)
{

}


/**
 * 
 */
sppf_node* new_sppf_nullable_node(uint64_t nullable_idx)
{

}


/**
 * 
 */
sppf_node* new_sppf_inner_node(uint64_t head_idx, uint64_t source_start_idx, uint64_t source_end_idx)
{

}


/**
 * 
 */
obj* net_sppf_node_obj(sppf_node* n)
{

}


/**
 * 
 */
uint64_t sppf_node_hash(sppf_node* n)
{

}


/**
 * 
 */
bool sppf_node_equals(sppf_node* left, sppf_node* right)
{

}


/**
 * 
 */
void sppf_node_str(sppf_node* n)
{

}


/**
 * 
 */
void sppf_node_repr(sppf_node* n)
{

}


/**
 * 
 */
void sppf_node_free(sppf_node* n)
{

}




#endif