#ifndef SPPF_H
#define SPPF_H

//shared packed parse forest data structure for storing the parse trees generated

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

    //normal and packed nodes have same node, just different children (handled by dict* nodes pointing to either a uint, or a vect<uint>)
    //leaf nodes 

    //Depends on if metaast works with union version or not
    // void* node;
    // union {
    //     uint64_t leaf;       //index in source of the terminal character
    //     uint64_t nullable;   //index in the sppf_nodes dict of the specific nullable node
    //     struct {
    //         uint64_t head_idx, 
    //         // uint64_t production_idx?,    //for future use
    //         uint64_t source_start_idx, 
    //         uint64_t source_end_idx
    //     } inner;
    // } node;
} sppf_node;


#endif