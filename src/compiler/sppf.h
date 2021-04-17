#ifndef SPPF_H
#define SPPF_H

//shared packed parse forest data structure for storing the parse trees generated

#include "object.h"
#include "vector.h"
#include "slice.h"
#include "dictionary.h"
#include "set.h"


typedef struct {
    set* nodes;             //set<sppf_node>
    dict* edges;            //map<node_idx, children_idx | vect<children_idx>>
    set* children;          //set<vect<node_idx>>
    // dict* gss_sppf_map;     //map<gss_edge, sppf_node_idx> from GSS edges to nodes in the SPPF
} sppf;

typedef enum {
    sppf_leaf,
    sppf_nullable,
    sppf_inner,             //includes both normal and packed nodes
 } sppf_node_type;

typedef union {
    uint64_t leaf;                      //index in source of the terminal character
    vect* nullable;              //string containing the symbol indices of the nullable parts
    struct {
        uint64_t head_idx;              //symbol index of the rule head being reduced
        // uint64_t production_idx?;    //for future use
        uint64_t source_start_idx; 
        uint64_t source_end_idx;
    } inner;
} sppf_node_union;

typedef struct {
    sppf_node_type type;
    sppf_node_union node;
} sppf_node;


sppf* new_sppf();
uint64_t sppf_add_node(sppf* s, sppf_node* node);
void sppf_add_node_with_children(sppf* s, sppf_node* node, vect* children);
uint64_t sppf_add_children(sppf* s, vect* children);
void sppf_connect_node_to_children(sppf* s, uint64_t node_idx, uint64_t children_idx);
uint64_t sppf_add_leaf_node(sppf* s, uint64_t source_idx);
// uint64_t sppf_get_leaf_node_idx(sppf* s, uint64_t source_idx);
uint64_t sppf_add_nullable_symbol_node(sppf* s, uint64_t symbol_idx);
// uint64_t sppf_get_nullable_symbol_node_idx(sppf* s, uint64_t symbol_idx);
uint64_t sppf_add_nullable_string_node(sppf* s, slice* nullable_part);
// uint64_t sppf_get_nullable_string_node_idx(sppf* s, slice* nullable_part);
void sppf_add_root_epsilon(sppf* s);
uint64_t sppf_add_inner_node(sppf* s, uint64_t head_idx, uint64_t source_start_idx, uint64_t source_end_idx, vect* children_indices);
// uint64_t sppf_get_inner_node_idx(sppf* s, uint64_t head_idx, uint64_t source_start_idx, uint64_t source_end_idx);
void sppf_free(sppf* s);
void sppf_str(sppf* s);

sppf_node sppf_node_struct(sppf_node_type type, sppf_node_union node);
sppf_node* new_sppf_leaf_node(uint64_t source_idx);
sppf_node* new_sppf_nullable_symbol_node(uint64_t symbol_idx);
sppf_node* new_sppf_nullable_string_node(slice* nullable_part);
sppf_node* new_sppf_inner_node(uint64_t head_idx, uint64_t source_start_idx, uint64_t source_end_idx);
obj* new_sppf_node_obj(sppf_node* n);
uint64_t sppf_node_hash(sppf_node* n);
sppf_node* sppf_node_copy(sppf_node* n);
bool sppf_node_equals(sppf_node* left, sppf_node* right);
void sppf_node_str(sppf_node* n);
void sppf_node_repr(sppf_node* n);
void sppf_node_free(sppf_node* n);




#endif