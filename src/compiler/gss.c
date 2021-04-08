#ifndef GSS_C
#define GSS_C

#include <stdio.h>

#include "gss.h"
#include "utilities.h"


/**
 * Create a new Graph Structured Stack (GSS) structure.
 */
gss* new_gss(size_t size_hint)
{
    if (size_hint == 0) { size_hint = 8; }
    gss* g = malloc(sizeof(gss));
    *g = (gss){
        .nodes = new_vect_with_capacity(size_hint),
        .edges = new_dict()
    };
    return g;
}

/**
 * Get a specific set of nodes from the GSS.
 * Handles allocating empty sets if they do not exist yet.
 */
set* gss_get_nodes_set(gss* g, size_t nodes_idx)
{
    //create empty sets up to the requested one, if they don't exist yet.
    while (vect_size(g->nodes) <= nodes_idx)
    {
        vect_append(g->nodes, new_set_obj(NULL));
    }

    //return the requested set.
    return vect_get(g->nodes, nodes_idx)->data;
}


/**
 * Return the state label of the node at the given coordinates.
 */
uint64_t gss_get_node_state(gss* g, size_t nodes_idx, size_t node_idx)
{
    set* nodes = gss_get_nodes_set(g, nodes_idx);
    if (node_idx >= set_size(nodes))
    {
        printf("ERROR: no GSS node at index (%zu, %zu)\n", nodes_idx, node_idx);
        exit(1);
    }
    return *(uint64_t*)nodes->entries[node_idx].item->data;
}


/**
 * Check Ui in the GSS for a node with the given state label.
 * i.e. is there a node in the set at `nodes_idx` with label `state_idx`.
 * If none found, returns NULL.
 */
gss_idx* gss_get_node_with_label(gss* g, size_t nodes_idx, uint64_t state_idx)
{
    set* nodes = gss_get_nodes_set(g, nodes_idx);
    obj state_idx_obj = (obj){.type=UInteger_t, .data=&state_idx};
    size_t node_idx = set_get_entries_index(nodes, &state_idx_obj);
    if (!set_is_index_empty(node_idx))
    {
        return new_gss_idx(nodes_idx, node_idx);
    }
    return NULL;
}


/**
 * Check if there is an edge in the GSS between the given indices.
 */
bool gss_does_edge_exist(gss* g, gss_idx* parent, gss_idx* child)
{
    obj parent_obj = (obj){.type=GSSIndex_t, .data=parent};
    obj* children = dict_get(g->edges, &parent_obj);
    if (children != NULL)
    {
        obj child_obj = (obj){.type=GSSIndex_t, .data=child};
        return set_contains(children->data, &child_obj);
    }
    return false;
}


/**
 * Perform a breadth first search from the root to find all nodes
 * that are the specified length away from the root.
 */
vect* gss_get_reachable(gss* g, gss_idx* root_idx, size_t length)
{
    //BFS data structures. Queue will contain desired nodes at the end of search.
    vect* queue = new_vect();
    set* discovered = new_set();

    //initialize the BFS structures with the root
    set_add(discovered, new_gss_idx_obj(gss_idx_copy(root_idx)));
    vect_enqueue(queue, new_gss_idx_obj(gss_idx_copy(root_idx)));

    //keep track of current depth + number of nodes at that depth
    uint64_t current_depth = 0;
    uint64_t current_nodes = 1;

    while (vect_size(queue) > 0 && current_depth < length)
    {
        //get the next node, and it's children
        obj* idx = vect_dequeue(queue);
        set* children = dict_get(g->edges, idx)->data;

        for (size_t i = 0; i < set_size(children); i++)
        {
            obj* child_idx = set_get_at_index(children, i);
            if (!set_contains(discovered, child_idx))
            {
                set_add(discovered, obj_copy(child_idx));
                vect_enqueue(queue, obj_copy(child_idx));
            }
        }

        //done with this node
        obj_free(idx);

        //keep track of how many nodes still at the current depth
        current_nodes--;
        if (current_nodes == 0)
        {
            //increase depth and reset current nodes
            current_depth++;
            current_nodes = vect_size(queue);
        }
    }

    //cleanup 
    set_free(discovered);

    //queue should contain all nodes at the desired length from root
    printf("BFS RESULTS: "); gss_idx_str(root_idx); printf(", l=%zu\n", length);  
    gss_str(g); printf("queue: "); vect_str(queue); printf("\n\n");
    return queue;
}


/**
 * Insert a node into the GSS.
 */
gss_idx* gss_add_node(gss* g, size_t nodes_idx, uint64_t state)
{
    set* U = gss_get_nodes_set(g, nodes_idx);
    obj* v = new_uint_obj(state);
    size_t node_idx = set_add_return_index(U, v);
    return new_gss_idx(nodes_idx, node_idx);
}


/**
 * Add a new edge to the GSS.
 * `parent` and `child` are not modified by this function.
 */
void gss_add_edge(gss* g, gss_idx* parent, gss_idx* child)
{
    //edges dictionary key
    // obj* parent_obj = new_gss_idx_obj(parent);
    obj parent_obj = (obj){.type=GSSIndex_t, .data=parent};

    //create an empty set for children if none exists yet
    if (!dict_contains(g->edges, &parent_obj))
    {
        dict_set(g->edges, obj_copy(&parent_obj), new_set_obj(NULL));
    }

    //get the children indices set, and insert the child index
    set* children_idxs = dict_get(g->edges, &parent_obj)->data;
    set_add(children_idxs, new_gss_idx_obj(gss_idx_copy(child)));
}


/**
 * Print out a string representation of the GSS.
 */
void gss_str(gss* g)
{
    printf("GSS Nodes:\n");
    vect_str(g->nodes);
    printf("\nGSS Edges:\n");
    dict_str(g->edges);
    printf("\n");
}


/**
 * Free the GSS's allocated memory. 
 */
void gss_free(gss* g)
{
    vect_free(g->nodes);
    dict_free(g->edges);
    free(g);
}


/**
 * Return a GSS index structure.
 */
gss_idx* new_gss_idx(size_t nodes_idx, size_t node_idx)
{
    gss_idx* i = malloc(sizeof(gss_idx));
    *i = (gss_idx){.nodes_idx=nodes_idx, .node_idx=node_idx};
    return i;
}


/**
 * Return an allocated copy of the gss_idx.
 */
gss_idx* gss_idx_copy(gss_idx* i)
{
    return new_gss_idx(i->nodes_idx, i->node_idx);
}


/**
 * Return a GSS index wrapped in an object.
 */
obj* new_gss_idx_obj(gss_idx* i)
{
    obj* I = malloc(sizeof(obj));
    *I = (obj){.type=GSSIndex_t, .data=i};
    return I;
}


/**
 * Free the GSS edge structure.
 */
void gss_idx_free(gss_idx* i)
{
    free(i);
}


/**
 * Hash the data contained in the gss edge
 */
uint64_t gss_idx_hash(gss_idx* i)
{
    uint64_t data[] = {i->nodes_idx, i->node_idx};
    return hash_uint_sequence(data, sizeof(data) / sizeof(uint64_t));
}


/**
 * Determine if two GSS edges are equal.
 */
bool gss_idx_equals(gss_idx* left, gss_idx* right)
{
    return left->nodes_idx == right->nodes_idx && left->node_idx == right->node_idx;
}


// /**
//  * Print out a string representation of the GSS edge.
//  */
// void gss_edge_str(gss_edge* e)
// {
//     printf("["); gss_idx_str(&e->parent); printf(" -> "); gss_idx_str(&e->child); printf("]");
// }


/**
 * Print out a string representation of the GSS node index.
 */
void gss_idx_str(gss_idx* i)
{
    printf("(%zu, %zu)", i->nodes_idx, i->node_idx);
}


#endif