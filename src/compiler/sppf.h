#ifndef SPPF_H
#define SPPF_H

//shared packed parse forest data structure for storing the parse trees generated

#include "vector.h"
// #include "dictionary.h"
#include "set.h"

//nodes are represented by two types of lists. 
//normal lists, list out the plain string that makes up the node, e.g. node1, node2, ... etc.
//packed lists, represent current ambiguity, so they are lists of the aforementioned normal list

//edges are mapped between tuples, since I think some node coordinates may be 1D while others may be 2D


// dict* edge_node_map; //map<gss_edge, sppf_node> from GSS edges to nodes in the SPPF

// typedef struct {
//     uint64_t head_idx;
//     uint64_t source_start_idx;
//     uint64_t source_end_idx;
//     vect* children;
//     bool packed;
// } sppf_node;

// typedef enum {
//     leaf,
//     nullable,
//     normal,
//     packed
//  } sppf_type;

// typedef struct {
//     sppf_type type;
//     union {
//         struct {} leaf;
//         struct {} nullable;
//         struct {} normal;
//         struct {} packed;
//     } node;
// } sppf_node;



dict* sppf_map; //map<sppf_node, sppf_child_idx | vect<sppf_child_idx>>

typedef struct {
    // set* nodes;     //set<tuple<uint64, uint64, uint64>>, where tuple is (head_idx, source_start_idx, source_end_idx)
    // vect* children; //vect<vect<uint64> | vect<vect<uint64>> | NULL>, where outer vect has a 1-to-1 match with nodes, and inner vect can be either a list of the children nodes, or a packed node containing a list of lists of children nodes
    //if children inner is null, then it is a leaf node, and the tuple in nodes contains the index of the input source terminal

    // vect* nodes; //vect<sentence | pack | leaf>
    // dict* edges; //map<tuple, tuple>
} sppf;


//sentence is a an obj SPPFSentence_t, containing a vect*
//pack is an obj SPPFPack_t, containing a vect*
//leaf is a SPPFLeaf_t, containing a uint64_t pointing to the corresponding char


// typedef struct {
//     vect* alternates;
// } pack;


#endif