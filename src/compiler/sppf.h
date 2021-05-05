#ifndef SPPF_H
#define SPPF_H

//shared packed parse forest data structure for storing the parse trees generated

#include "object.h"
#include "vector.h"
#include "slice.h"
#include "dictionary.h"
#include "set.h"
#include "gss.h"
#include "parray.h"


typedef struct {
    set* nodes;             //set<sppf_node>
    dict* edges;            //map<node_idx, children_idx | set<children_idx>>
    set* children;          //set<vect<node_idx>>
    dict* gss_sppf_map;     //map<gss_edge, sppf_node_idx> from GSS edges to nodes in the SPPF
    uint64_t root_idx;      //index of the root node in the SPPF
} sppf;

typedef enum {
    sppf_leaf,
    sppf_nullable,
    sppf_inner,             //includes both normal and packed nodes
 } sppf_node_type;

typedef union {
    uint64_t leaf;                      //index in source of the terminal character
    vect* nullable;                     //string containing the symbol indices of the nullable parts
    struct {
        uint64_t head_idx;              //symbol index of the rule head being reduced
        uint64_t body_idx;              //for future use. index of the rule body being reduced
        uint64_t source_start_idx; 
        uint64_t source_end_idx;
    } inner;
} sppf_node_union;

typedef struct {
    sppf_node_type type;
    sppf_node_union node;
    //bool alive;   //future. probably used to mark nodes that have been filtered by the SPPF algorithm
} sppf_node;


sppf* new_sppf();
uint64_t sppf_add_node(sppf* s, sppf_node* node);
void sppf_label_gss_edge(sppf* s, gss_idx* parent, gss_idx* child, uint64_t node_idx);
vect* sppf_get_path_labels(sppf* s, vect* path);
void sppf_add_node_with_children(sppf* s, sppf_node* node, vect* children);
uint64_t sppf_add_children(sppf* s, vect* children);
void sppf_connect_node_to_children(sppf* s, uint64_t node_idx, uint64_t children_idx);
uint64_t sppf_add_nullable_symbol_node(sppf* s, uint64_t symbol_idx);
uint64_t sppf_add_nullable_string_node(sppf* s, slice* nullable_part);
void sppf_add_root_epsilon(sppf* s);
void sppf_free(sppf* s);

void sppf_repr(sppf* s);
void sppf_str(sppf* s);
void sppf_str_visit_nodes(sppf* s, bool* cyclic, uint64_t* num_lines);
void sppf_str_visit_nodes_inner(sppf* s, uint64_t node_idx, bool* cyclic, uint64_t* num_lines, set* visited);
void sppf_str_cyclic_inner(sppf* s, uint64_t node_idx, bool_array* open_levels, uint64_t* line_num, uint64_t line_num_width, dict* refs);
void sppf_str_noncyclic_inner(sppf* s, uint64_t node_idx, bool_array* open_levels);
void sppf_str_print_tree_lines(bool_array* open_levels);
void sppf_str_print_line_num(uint64_t line_num, uint64_t line_num_width);

sppf_node sppf_node_struct(sppf_node_type type, sppf_node_union node);
sppf_node* new_sppf_leaf_node(uint64_t source_idx);
sppf_node* new_sppf_nullable_symbol_node(uint64_t symbol_idx);
sppf_node* new_sppf_nullable_string_node(slice* nullable_part);
sppf_node* new_sppf_inner_node(uint64_t head_idx, uint64_t body_idx, uint64_t source_start_idx, uint64_t source_end_idx);
sppf_node sppf_inner_node_struct(uint64_t head_idx, uint64_t body_idx, uint64_t source_start_idx, uint64_t source_end_idx);
obj* new_sppf_node_obj(sppf_node* n);
uint64_t sppf_node_hash(sppf_node* n);
sppf_node* sppf_node_copy(sppf_node* n);
bool sppf_node_equals(sppf_node* left, sppf_node* right);
void sppf_node_str(sppf_node* n);
void sppf_node_str2(sppf_node* n);
void sppf_node_repr(sppf_node* n);
void sppf_node_free(sppf_node* n);




#endif