#ifndef SPPF_H
#define SPPF_H

//shared packed parse forest data structure for storing the parse trees generated

#include "vector.h"
#include "dictionary.h"

//nodes are represented by two types of lists. 
//normal lists, list out the plain string that makes up the node, e.g. node1, node2, ... etc.
//packed lists, represent current ambiguity, so they are lists of the aforementioned normal list

//edges are mapped between tuples, since I think some node coordinates may be 1D while others may be 2D

typedef struct {
    vect* nodes; //vect<vect | pack>
    dict* edges; //map<tuple, tuple>
} sppf;


#endif