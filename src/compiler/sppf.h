#ifndef SPPF_H
#define SPPF_H

//shared packed parse forest data structure for storing the parse trees generated

#include "object.h"
#include "vector.h"
#include "dictionary.h"
#include "set.h"


typedef struct {
    dict* nodes;    //map<sppf_node, child_list_idx | vect<child_list_idx> | NULL>      //where child_list_idx is uint64_t. NULL is for leaf and nullable nodes
    set* children;  //set<vect<child_node_idx>>                                         //where child_node_idx is uint64_t
    // dict* edge_node_map; //map<gss_edge, sppf_node_idx> from GSS edges to nodes in the SPPF
} sppf;

typedef enum {
    leaf,
    nullable,
    inner,          //includes both normal and packed nodes
 } sppf_type;

typedef struct {
    sppf_type type;
    union {
        uint64_t leaf;       //index in source of the terminal character
        uint64_t nullable;   //index in the sppf_nodes dict of the specific nullable node
        struct {
            uint64_t head_idx;
            // uint64_t production_idx?;    //for future use
            uint64_t source_start_idx; 
            uint64_t source_end_idx;
        } inner;
    } node;
} sppf_node;


sppf* new_sppf();
void sppf_free(sppf* s);

sppf_node* new_sppf_leaf_node(uint64_t source_idx);
sppf_node* new_sppf_nullable_node(uint64_t nullable_idx);
sppf_node* new_sppf_inner_node(uint64_t head_idx, uint64_t source_start_idx, uint64_t source_end_idx);
obj* net_sppf_node_obj(sppf_node* n);
uint64_t sppf_node_hash(sppf_node* n);
bool sppf_node_equals(sppf_node* left, sppf_node* right);
void sppf_node_str(sppf_node* n);
void sppf_node_repr(sppf_node* n);
void sppf_node_free(sppf_node* n);




#endif