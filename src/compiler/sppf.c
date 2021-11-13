#ifndef SPPF_C
#define SPPF_C

// #include <stdlib.h>
// #include <stdio.h>
// #include <inttypes.h>

// #include "sppf.h"
// #include "utilities.h"
// #include "ustring.h"
// #include "srnglr.h"
// #include "metaparser.h"


// uint64_t SPPF_ROOT_EPSILON_IDX;             //sppf->nodes[0] is the empty epsilon node
// uint64_t SPPF_ROOT_EPSILON_CHILDREN_IDX;    //index of the children vector that points to the epsilon vector


// /**
//  * Create a new Shared Packed Parse Forest.
//  * Adds an initial root epsilon node to the forest
//  */
// sppf* new_sppf()
// {
//     sppf* s = malloc(sizeof(sppf));
//     *s = (sppf){.nodes=new_set(), .edges=new_dict(), .children=new_set(), .gss_sppf_map=new_dict(), .root_idx=0};
    
//     //initialize the SPPF with a single root epsilone at index 0
//     sppf_add_root_epsilon(s);

//     return s;
// }


// /**
//  * Add a node to the SPPF. If the node exists already, the new one is freed.
//  * Returns the index of the node in the nodes set.
//  */
// uint64_t sppf_add_node(sppf* s, sppf_node* node)
// {
//     //check if the object is in the set already
//     obj node_obj = obj_struct(SPPFNode_t, node);
//     uint64_t index = set_get_entries_index(s->nodes, &node_obj);
    
//     //if the object is not in the set, add it, and update the index
//     if (set_is_index_empty(index))
//     {
//         index = set_add_return_index(s->nodes, new_sppf_node_obj(node));
//     }
//     else
//     {
//         sppf_node_free(node);
//     }

//     return index;
// }


// /**
//  * Label the GSS edge with the SPPF node, using the map in the SPPF.
//  * edge is not modified by this function.
//  */
// void sppf_label_gss_edge(sppf* s, gss_idx* parent, gss_idx* child, uint64_t node_idx)
// {
//     obj* edge_obj = new_gss_edge_obj(new_gss_edge(*parent, *child));
//     obj* node_idx_obj = new_uint_obj(node_idx);
//     dict_set(s->gss_sppf_map, edge_obj, node_idx_obj);
// }


// /**
//  * Return the list of SPPF nodes that make up the given path in the GSS
//  */
// vect* sppf_get_path_labels(sppf* s, vect* path)
// {
//     vect* labels = new_vect();
//     for (size_t i = vect_size(path) - 1; i > 0; i--)
//     {
//         gss_idx* parent = vect_get(path, i-1)->data;
//         gss_idx* child = vect_get(path, i)->data;
//         gss_edge edge = gss_edge_struct(*parent, *child);
//         obj edge_obj = obj_struct(GSSEdge_t, &edge);
//         obj* label = dict_get(s->gss_sppf_map, &edge_obj);
//         vect_append(labels, obj_copy(label));
//     }
//     // printf("labels for path ("); vect_str(path); printf("): "); vect_str(labels); printf("\n\n");
//     return labels;
// }


// /**
//  * Add a node + children to the SPPF. If the node already exists with children,
//  * a packed node is create.
//  */
// void sppf_add_node_with_children(sppf* s, sppf_node* node, vect* children)
// {
//     uint64_t node_idx = sppf_add_node(s, node);
//     uint64_t children_idx = sppf_add_children(s, children);
//     sppf_connect_node_to_children(s, node_idx, -1, children_idx);
// }


// /**
//  * Add the vector of children node indices to the set of children vectors.
//  * Returns the index of the vector in the set.
//  */
// uint64_t sppf_add_children(sppf* s, vect* children)
// {
//     //check if the object is in the set already
//     obj children_obj = obj_struct(Vector_t, children);
//     uint64_t index = set_get_entries_index(s->children, &children_obj);
    
//     //if the object is not in the set, add it, and update the index
//     if (set_is_index_empty(index))
//     {
//         index = set_add_return_index(s->children, new_vect_obj(children));
//     }
//     else
//     {
//         vect_free(children);
//     }

//     return index;
// }


// /**
//  * Indicate in the SPPF that the given node has the given children.
//  * If the node already has children, then a packed node is created.
//  * body_idx indicates which production this reduction node represents.
//  * For nullable nodes, body_idx may be set to (uint64_t)-1
//  */
// void sppf_connect_node_to_children(sppf* s, uint64_t node_idx, uint64_t body_idx, uint64_t children_idx)
// {
//     //get the (possibly NULL) children object for this node
//     obj node_idx_obj = obj_struct(UInteger_t, &node_idx);
//     obj* children = dict_get(s->edges, &node_idx_obj);    
    
//     //node has no children so far, so create a new non-packed entry
//     if (children == NULL)  
//     {
//         sppf_edge* edge = new_sppf_nonpacked_edge(body_idx, children_idx);
//         dict_set(s->edges, new_uint_obj(node_idx), new_sppf_edge_obj(edge));
//     }
//     else //handle edge object that already exists
//     {
//         sppf_edge* edge = children->data;

//         //if already packed, and simply insert the new children index
//         if (edge->packed)
//         {
//             set_add(edge->children.indices, new_uint_obj(children_idx));
//         }
//         else //handle non-packed node
//         {
//             //check if the non-packed node already has the children to be added
//             if (edge->children.index == children_idx) { return; }

//             //convert non-packed to a packed node
//             edge->packed = true;
//             set* children_set = new_set();
//             set_add(children_set, new_uint_obj(edge->children.index));
//             set_add(children_set, new_uint_obj(children_idx));
//             edge->children.indices = children_set;
//         }
//     } 
// }


// /**
//  * Insert a nullable node for a single non-terminal symbol.
//  */
// uint64_t sppf_add_nullable_symbol_node(sppf* s, uint64_t symbol_idx)
// {
//     //create a stack allocated vect with just the symbol idx, then create stack allocated node with vect
//     obj symbol_idx_obj = obj_struct(UInteger_t, &symbol_idx); obj* list_head_obj = &symbol_idx_obj;
//     vect nullable_string = (vect){.capacity=1, .head=0, .size=1, .list=&list_head_obj};
//     sppf_node symbol_node = sppf_node_struct(sppf_nullable, (sppf_node_union){.nullable=&nullable_string});
//     obj symbol_node_obj = obj_struct(SPPFNode_t, &symbol_node);

//     //check if the node already exists
//     if (set_contains(s->nodes, &symbol_node_obj))
//     {
//         return set_get_entries_index(s->nodes, &symbol_node_obj);
//     }

//     //add the node to the SPPF, and link with children list that points to just epsilon
//     uint64_t node_idx = set_add_return_index(s->nodes, obj_copy(&symbol_node_obj));
//     sppf_connect_node_to_children(s, node_idx, -1, SPPF_ROOT_EPSILON_CHILDREN_IDX);

//     return node_idx;
// }


// /**
//  * Insert a nullable node into the SPPF. 
//  * The nullable part is a vector if nullable non-terminal symbols.
//  * Connects this node to the corresponding nullable children node.
//  * Returns the index of the SPPF node created/found.
//  */
// uint64_t sppf_add_nullable_string_node(sppf* s, slice* nullable_part)
// {
//     vect nullable_part_vect = slice_vect_view_struct(nullable_part);
//     sppf_node nullable_node = sppf_node_struct(sppf_nullable, (sppf_node_union){.nullable=&nullable_part_vect});
//     obj nullable_node_obj = obj_struct(SPPFNode_t, &nullable_node);
    
//     //check if the node already exists
//     if (set_contains(s->nodes, &nullable_node_obj))
//     {
//         return set_get_entries_index(s->nodes, &nullable_node_obj);
//     }

//     //save the index of the node inserted
//     uint64_t node_idx = set_add_return_index(s->nodes, obj_copy(&nullable_node_obj));

//     //construct children
//     vect* children = new_vect();
//     for (size_t i = 0; i < slice_size(nullable_part); i++)
//     {
//         uint64_t* head_idx = slice_get(nullable_part, i)->data;

//         //create a stack allocated vect with just the symbol idx, then create stack allocated node with vect
//         obj head_idx_obj = obj_struct(UInteger_t, head_idx); obj* list_head_obj = &head_idx_obj;
//         vect nullable_string = (vect){.capacity=1, .head=0, .size=1, .list=&list_head_obj};
//         sppf_node nullable_head_node = sppf_node_struct(sppf_nullable, (sppf_node_union){.nullable=&nullable_string});
//         obj nullable_head_node_obj = obj_struct(SPPFNode_t, &nullable_head_node);

//         //add the idx of the child head to the list of children indices
//         uint64_t child_head_idx = set_get_entries_index(s->nodes, &nullable_head_node_obj);
//         vect_append(children, new_uint_obj(child_head_idx));
//     }

//     //add the children vect to the set of children, and connect to the node
//     uint64_t children_idx = sppf_add_children(s, children);
//     sppf_connect_node_to_children(s, node_idx, -1, children_idx);

//     return node_idx;    
// }


// /**
//  * Set the first node in the SPPF to be the root epsilon node.
//  */
// void sppf_add_root_epsilon(sppf* s)
// {
//     //manually create epsilon node, which contains an empty vector.
//     sppf_node* eps_node = malloc(sizeof(sppf_node));
//     *eps_node = (sppf_node){.type=sppf_nullable, .node.nullable=new_vect()};

//     //add the node to the nodes set, and update the index of the root epsilon
//     obj* eps_node_obj = new_sppf_node_obj(eps_node);
//     SPPF_ROOT_EPSILON_IDX = set_add_return_index(s->nodes, eps_node_obj);

//     //add a children entry that points to just the root epsilon node
//     vect* eps_children = new_vect();
//     vect_append(eps_children, new_uint_obj(SPPF_ROOT_EPSILON_IDX));
//     obj* eps_children_obj = new_vect_obj(eps_children);
//     SPPF_ROOT_EPSILON_CHILDREN_IDX = set_add_return_index(s->children, eps_children_obj);
// }


// /**
//  * Release allocated resources for the SPPF.
//  */
// void sppf_free(sppf* s)
// {
//     set_free(s->nodes);
//     dict_free(s->edges);
//     set_free(s->children);
//     dict_free(s->gss_sppf_map);
//     free(s);
// }


// /**
//  * Print out the full tree of the SPPF.
//  */
// void sppf_str(sppf* s)
// {
//     //determine if the sppf is cyclic, and count the number of lines to be used
//     bool cyclic; uint64_t num_lines;
//     sppf_str_visit_nodes(s, &cyclic, &num_lines);

//     //used to keep track of drawing lines in the tree
//     bool_array* open_levels = new_bool_array();
    
//     if (!cyclic)
//     {
//         // Print out a non-cyclic SPPF //
//         sppf_str_noncyclic_inner(s, s->root_idx, open_levels);
//     }
//     else
//     {
//         // Print out a cyclic SPPF //
//         uint64_t line_num = 0;                              //line number being printed to
//         size_t line_num_width = dec_num_digits(num_lines);  //amount of space needed to print the line numbers
//         dict* refs = new_dict();                            //map from SPPF nodes to the line they start on

//         //print the first line number
//         sppf_str_print_line_num(line_num, line_num_width);
        
//         //recursively print the SPPF, with line numbers, and reference pointers
//         sppf_str_cyclic_inner(s, s->root_idx, open_levels, &line_num, line_num_width, refs);

//         //free the dict/array. Don't touch the keys since they are owned by the SPPF.
//         dict_free_values_only(refs);
//         dict_free_table_only(refs);
//     }

//     //cleanup
//     bool_array_free(open_levels);
// }


// /**
//  * Determine if the SPPF has any cycles, and count how many lines to print
//  * Sets value at pointers to `cyclic` and `num_lines`
//  */
// void sppf_str_visit_nodes(sppf* s, bool* cyclic, uint64_t* num_lines)
// {
//     //set initial values for cyclic/num_lines
//     *cyclic = false;
//     *num_lines = 1; //start at 1 for line of root node (not counted by recursive algorithm)

//     //set of nodes visited already
//     set* visited = new_set();

//     //work down the tree, checking for cycles, and counting how many lines will be printed
//     sppf_str_visit_nodes_inner(s, s->root_idx, cyclic, num_lines, visited);
    
//     //free the set without touching the SPPF nodes (owned by the SPPF itself)
//     set_free_table_only(visited);
// }


// /**
//  * Inner helper function for determining if an SPPF contains cycles, and how many lines will be printed
//  */
// void sppf_str_visit_nodes_inner(sppf* s, uint64_t node_idx, bool* cyclic, uint64_t* num_lines, set* visited)
// {
//     //get the current node being looked at
//     obj* current_node_obj = set_get_at_index(s->nodes, node_idx);
//     sppf_node* current_node = current_node_obj->data;
    
//     //handle non-inner nodes
//     if (current_node->type == sppf_leaf || current_node->type == sppf_nullable) { return; }

//     // regular inner node //
//     //check if we already expanded this node
//     if (set_contains(visited, current_node_obj))
//     {
//         *cyclic = true;     //mark that we found a cycle
//         return;
//     }

//     //mark this node as visited
//     set_add(visited, current_node_obj);


//     // expand the children for this node //
//     obj node_idx_obj = obj_struct(UInteger_t, &node_idx);
    
//     obj* children = dict_get(s->edges, &node_idx_obj);
//     if (children == NULL)
//     {
//         return; //no children to expand for this node
//     }

//     //extract the edge object for the children
//     sppf_edge* edge = children->data;
    
//     //expand non-packed node
//     if (!edge->packed)
//     {
//         //expand each child normally
//         vect* children_vect = set_get_at_index(s->children, edge->children.index)->data;
//         for (size_t i = 0; i < vect_size(children_vect); i++)
//         {
//             *num_lines += 1; //line for printing the child's head
//             uint64_t child_idx = *(uint64_t*)vect_get(children_vect, i)->data;
//             sppf_str_visit_nodes_inner(s, child_idx, cyclic, num_lines, visited);
//         }
//     }
//     else //expand packed node
//     {
//         //for each list of children, expand each child
//         for (size_t i = 0; i < set_size(edge->children.indices); i++)
//         {
//             uint64_t children_idx = *(uint64_t*)set_get_at_index(edge->children.indices, i)->data;
//             vect* children_vect = set_get_at_index(s->children, children_idx)->data;
//             for (size_t j = 0; j < vect_size(children_vect); j++)
//             {
//                 *num_lines += 1; //line for printing the child's head
//                 uint64_t child_idx = *(uint64_t*)vect_get(children_vect, j)->data;
//                 sppf_str_visit_nodes_inner(s, child_idx, cyclic, num_lines, visited);
//             }
//         }
//     }
// }


// /**
//  * Inner helper function for printing out a cycle-containing SPPF.
//  * Takes the current node being printed, level of indentation, current line number,
//  * and a map of all nodes already printed and the line they occur on.
//  */
// void sppf_str_cyclic_inner(sppf* s, uint64_t node_idx, bool_array* open_levels, uint64_t* line_num, uint64_t line_num_width, dict* refs)
// {
//     //get the current node being looked at
//     obj* current_node_obj = set_get_at_index(s->nodes, node_idx);
//     sppf_node* current_node = current_node_obj->data;
    
//     //handle outer nodes
//     if (current_node->type == sppf_leaf || current_node->type == sppf_nullable)
//     { 
//         //print node on single line & continue
//         sppf_node_str2(current_node, -1); printf("\n");
//         return; 
//     }

//     // regular inner node //
//     //check if we already expanded this node
//     obj* ref_line_obj = dict_get(refs, current_node_obj);
//     if (ref_line_obj != NULL)
//     {
//         //print out the ref line
//         uint64_t ref_line = *(uint64_t*)ref_line_obj->data;
//         printf("@%"PRIu64"\n", ref_line);
//         return;
//     }

//     //mark this node as visited
//     dict_set(refs, current_node_obj, new_uint_obj(*line_num));

//     //expand the children for this node
//     obj node_idx_obj = obj_struct(UInteger_t, &node_idx);
//     obj* children = dict_get(s->edges, &node_idx_obj);
//     if (children == NULL)
//     {
//         return; //no children to expand for this node
//     }

//     //extract the edge for these children
//     sppf_edge* edge = children->data;

//     if (!edge->packed)
//     {
//         //print the node head
//         sppf_node_str2(current_node, edge->body_idx); printf("\n");

//         //expand each child normally
//         vect* children_vect = set_get_at_index(s->children, edge->children.index)->data;
//         const uint64_t num_children = vect_size(children_vect);
//         for (size_t i = 0; i < num_children; i++)
//         {
//             //update/print the line number
//             *line_num += 1;
//             sppf_str_print_line_num(*line_num, line_num_width);

//             //print lines for previous levels
//             sppf_str_print_tree_lines(open_levels);

//             //print the lines for the child + update open levels
//             printf("%s── ", i == num_children - 1 ? "└" : "├");
//             bool_array_push(open_levels, i != num_children - 1);

//             //expand the child
//             uint64_t child_idx = *(uint64_t*)vect_get(children_vect, i)->data;
//             sppf_str_cyclic_inner(s, child_idx, open_levels, line_num, line_num_width, refs);

//             //reset open levels from this child
//             bool_array_pop(open_levels);
//         }
//     }
//     else //type == Set_t  //node is a packed node
//     {
//         //print the node head inside packed braces
//         printf("["); sppf_node_str2(current_node, edge->body_idx); printf("]\n");

//         //for each list of children, expand each child (noting that the first child of each list has continue_line=true)
//         // set* packed_children_set = children->data;
//         const uint64_t num_packs = set_size(edge->children.indices);
//         for (size_t i = 0; i < num_packs; i++)
//         {
//             //update/print the line number
//             *line_num += 1;
//             sppf_str_print_line_num(*line_num, line_num_width);

//             //print lines for previous levels
//             sppf_str_print_tree_lines(open_levels);

//             //print the lines for the child + update open levels
//             printf("%s───", i == num_packs - 1 ? "└" : "├");
//             bool_array_push(open_levels, i != num_packs - 1);
                

//             uint64_t children_idx = *(uint64_t*)set_get_at_index(edge->children.indices, i)->data;
//             vect* children_vect = set_get_at_index(s->children, children_idx)->data;
//             const uint64_t num_children = vect_size(children_vect);
//             for (size_t j = 0; j < num_children; j++)
//             {
//                 if (j != 0)
//                 {
//                     //update/print the line number
//                     *line_num += 1;
//                     sppf_str_print_line_num(*line_num, line_num_width);

//                     //print lines for previous levels
//                     sppf_str_print_tree_lines(open_levels);
//                 }

//                 //options are first one ┬, middle one ├, last one └, only one ─
//                 //first if j == 0 && num_children > 1
//                 //only one if j == 0 && num_children == 1
//                 //middle if j > 0 && j < num_children - 1
//                 //last if j > 0 && j == num_children - 1
//                 char* branch_type;
//                 bool open_level;
//                 if (j == 0)
//                 {
//                     if (num_children == 1)
//                     {
//                         branch_type = "─";
//                         open_level = false;
//                     }
//                     else
//                     {
//                         branch_type = "┬";
//                         open_level = true;

//                     }
//                 }
//                 else
//                 {
//                     if (j == num_children - 1)
//                     {
//                         branch_type = "└";
//                         open_level = false;
//                     }
//                     else
//                     {
//                         branch_type = "├";
//                         open_level = true;
//                     }
//                 }

//                 printf("%s── ", branch_type);
//                 bool_array_push(open_levels, open_level);



//                 uint64_t child_idx = *(uint64_t*)vect_get(children_vect, j)->data;
//                 sppf_str_cyclic_inner(s, child_idx, open_levels, line_num, line_num_width, refs);

//                 //reset open levels from this child
//                 bool_array_pop(open_levels);
//             }

//             //reset open levels from this pack 
//             bool_array_pop(open_levels);
//         }
//     }
// }


// /**
//  * Inner helper function for printing out a non-cycle-containing SPPF.
//  * Prints starting from the given node, at the given indentation level.
//  */
// void sppf_str_noncyclic_inner(sppf* s, uint64_t node_idx, bool_array* open_levels)
// {
//     //get the current node being looked at
//     obj* current_node_obj = set_get_at_index(s->nodes, node_idx);
//     sppf_node* current_node = current_node_obj->data;
    
//     //handle outer nodes
//     if (current_node->type == sppf_leaf || current_node->type == sppf_nullable)
//     { 
//         //print node on single line & continue
//         sppf_node_str2(current_node, -1); printf("\n");
//         return; 
//     }

//     //expand the children for this node
//     obj node_idx_obj = obj_struct(UInteger_t, &node_idx);
//     obj* children = dict_get(s->edges, &node_idx_obj);
//     if (children == NULL)
//     {
//         return; //no children to expand for this node
//     }
//     sppf_edge* edge = children->data;

//     if (!edge->packed)  //node is a non-packed node
//     {
//         //print the node head
//         sppf_node_str2(current_node, edge->body_idx); printf("\n");

//         //expand each child normally
//         vect* children_vect = set_get_at_index(s->children, edge->children.index)->data;
//         const uint64_t num_children = vect_size(children_vect);
//         for (size_t i = 0; i < num_children; i++)
//         {
//             //print lines for previous levels
//             sppf_str_print_tree_lines(open_levels);

//             //print the lines for the child + update open levels
//             printf("%s── ", i == num_children - 1 ? "└" : "├");
//             bool_array_push(open_levels, i != num_children - 1);

//             //expand the child
//             uint64_t child_idx = *(uint64_t*)vect_get(children_vect, i)->data;
//             sppf_str_noncyclic_inner(s, child_idx, open_levels);

//             //reset open levels from this child
//             bool_array_pop(open_levels);
//         }
//     }
//     else //type == Set_t  //node is a packed node
//     {
//         //print the node head inside packed braces
//         printf("["); sppf_node_str2(current_node, edge->body_idx); printf("]\n");

//         //for each list of children, expand each child (noting that the first child of each list has continue_line=true)
//         const uint64_t num_packs = set_size(edge->children.indices);
//         for (size_t i = 0; i < num_packs; i++)
//         {
//             //print lines for previous levels
//             sppf_str_print_tree_lines(open_levels);

//             //print the lines for the child + update open levels
//             printf("%s───", i == num_packs - 1 ? "└" : "├");
//             bool_array_push(open_levels, i != num_packs - 1);

//             uint64_t children_idx = *(uint64_t*)set_get_at_index(edge->children.indices, i)->data;
//             vect* children_vect = set_get_at_index(s->children, children_idx)->data;
//             const uint64_t num_children = vect_size(children_vect);
//             for (size_t j = 0; j < num_children; j++)
//             {
//                 if (j != 0)
//                 {
//                     //print lines for previous levels
//                     sppf_str_print_tree_lines(open_levels);
//                 }

//                 //options are first one ┬, middle one ├, last one └, only one ─
//                 //first if j == 0 && num_children > 1
//                 //only one if j == 0 && num_children == 1
//                 //middle if j > 0 && j < num_children - 1
//                 //last if j > 0 && j == num_children - 1
//                 char* branch_type;
//                 bool open_level;
//                 if (j == 0)
//                 {
//                     if (num_children == 1)
//                     {
//                         branch_type = "─";
//                         open_level = false;
//                     }
//                     else
//                     {
//                         branch_type = "┬";
//                         open_level = true;

//                     }
//                 }
//                 else
//                 {
//                     if (j == num_children - 1)
//                     {
//                         branch_type = "└";
//                         open_level = false;
//                     }
//                     else
//                     {
//                         branch_type = "├";
//                         open_level = true;
//                     }
//                 }

//                 printf("%s── ", branch_type);
//                 bool_array_push(open_levels, open_level);

//                 //expand the current child
//                 uint64_t child_idx = *(uint64_t*)vect_get(children_vect, j)->data;
//                 sppf_str_noncyclic_inner(s, child_idx, open_levels);

//                 //reset open levels from this child
//                 bool_array_pop(open_levels);
//             }

//             //reset open levels from this pack 
//             bool_array_pop(open_levels);
//         }
//     }
// }


// /**
//  * Print out the lines in the tree based on which levels are currently being expanded.
//  */
// void sppf_str_print_tree_lines(bool_array* open_levels)
// {
//     for (size_t i = 0; i < bool_array_size(open_levels); i++)
//     {
//         printf(bool_array_get(open_levels, i) ? "│" : " ");
//         printf("   ");
//     }
// }


// /**
//  * Print out the line number + padding while printing an SPPF
//  */
// void sppf_str_print_line_num(uint64_t line_num, uint64_t line_num_width)
// {
//     //print line number with any padding needed
//     uint64_t padding = line_num_width - dec_num_digits(line_num);
//     for (size_t i = 0; i < padding; i++){ printf(" "); }
//     printf("%"PRIu64" ", line_num);
// }


// /**
//  * Print out a string representation for an SPPF edge object
//  */
// void sppf_edge_str(sppf_edge* e)
// {
//     printf("SPPF edge{body_idx: %"PRIu64", children: ", e->body_idx);
//     if (e->packed)
//     {
//         set_str(e->children.indices);
//     }
//     else
//     {
//         printf("{%"PRIu64"}", e->children.index);
//     }
//     printf("}");
// }


// /**
//  * Print out a string representation of the SPPF
//  */
// void sppf_repr(sppf* s)
// {
//     printf("SPPF Nodes:\n");
//     set_str(s->nodes);
//     printf("\nSPPF Children:\n");
//     set_str(s->children);
//     printf("\nSPPF edges:\n");
//     dict_str(s->edges);
//     printf("\nGSS-SPPF map:\n");
//     dict_str(s->gss_sppf_map);
//     printf("\nSPPF root node index: %"PRIu64"\n", s->root_idx);
// }


// /**
//  * Create a stack allocated SPPF node.
//  */
// inline sppf_node sppf_node_struct(sppf_node_type type, sppf_node_union node)
// {
//     return (sppf_node){.type=type, .node=node};
// }


// /**
//  * Create a new SPPF node that points to a specific source character.
//  */
// sppf_node* new_sppf_leaf_node(uint64_t source_idx)
// {
//     sppf_node* n = malloc(sizeof(sppf_node));
//     *n = (sppf_node){.type=sppf_leaf, .node.leaf=source_idx};
//     return n;
// }


// /**
//  * Create a new SPPF node that points to a nullable symbol.
//  */
// sppf_node* new_sppf_nullable_symbol_node(uint64_t symbol_idx)
// {
//     sppf_node* n = malloc(sizeof(sppf_node));
//     vect* string = new_vect();
//     vect_append(string, new_uint_obj(symbol_idx));
//     *n = (sppf_node){.type=sppf_nullable, .node.nullable=string};
//     return n;
// }

// /**
//  * Create a new SPPF node that points to a nullable part of a production.
//  * nullable_part is not modified by this function.
//  */
// sppf_node* new_sppf_nullable_string_node(slice* nullable_part)
// {
//     sppf_node* n = malloc(sizeof(sppf_node));
//     *n = (sppf_node){.type=sppf_nullable, .node.nullable=slice_copy_to_vect(nullable_part)};
//     return n;
// }


// /**
//  * Create a new SPPF node that will point to a list of children nodes,
//  * or a packed list of lists of children nodes.
//  * (inner nodes themselves don't contain the children, just header info)
//  */
// sppf_node* new_sppf_inner_node(uint64_t head_idx, uint64_t body_idx, uint64_t source_start_idx, uint64_t source_end_idx)
// {
//     sppf_node* n = malloc(sizeof(sppf_node));
//     *n = sppf_inner_node_struct(head_idx, body_idx, source_start_idx, source_end_idx);
//     return n;
// }


// /**
//  * Create the struct for the data of an SPPF inner node.
//  */
// sppf_node sppf_inner_node_struct(uint64_t head_idx, uint64_t body_idx, uint64_t source_start_idx, uint64_t source_end_idx)
// {
//     sppf_node n = (sppf_node){
//         .type=sppf_inner, 
//         .node.inner={
//             .head_idx=head_idx,
//             // .body_idx=body_idx,
//             .source_start_idx=source_start_idx, 
//             .source_end_idx=source_end_idx
//         }
//     };
//     return n;
// }


// /**
//  * Create a new SPPF node wrapped in an object.
//  */
// obj* new_sppf_node_obj(sppf_node* n)
// {
//     obj* N = malloc(sizeof(obj));
//     *N = obj_struct(SPPFNode_t, n);
//     return N;
// }


// /**
//  * Create a new non-packed SPPF edge object. Can later be transformed into a 
//  * packed node by changing edge->packed = true, and replacing child_idx with a
//  * set of indices for the children.
//  */
// sppf_edge* new_sppf_nonpacked_edge(uint64_t body_idx, uint64_t child_idx)
// {
//     sppf_edge* e = malloc(sizeof(sppf_edge));
//     *e = (sppf_edge){.packed=false, .body_idx=body_idx, .children.index=child_idx};
//     return e;
// }


// /**
//  * Create a new SPPF edge wrapped in an object
//  */
// obj* new_sppf_edge_obj(sppf_edge* e)
// {
//     obj* E = malloc(sizeof(obj));
//     *E = obj_struct(SPPFEdge_t, e);
//     return E;
// }


// /**
//  * Return a hash of the SPPF node's contained data.
//  * Hash does not account for possible children of the SPPF node.
//  */
// uint64_t sppf_node_hash(sppf_node* n)
// {
//     switch (n->type)
//     {
//         case sppf_leaf: return hash_uint(n->node.leaf);
//         case sppf_nullable: return vect_hash(n->node.nullable);
//         case sppf_inner:
//         {
//             //sequence of uints to hash
//             uint64_t seq[] = {n->node.inner.head_idx, /*n->node.inner.body_idx,*/ n->node.inner.source_start_idx, n->node.inner.source_end_idx};
//             return hash_uint_sequence(seq, sizeof(seq) / sizeof(uint64_t));
//         }
//     }
// }


// /**
//  * Return a copy of the SPPF node
//  */
// sppf_node* sppf_node_copy(sppf_node* n)
// {
//     switch (n->type)
//     {
//         case sppf_nullable:
//         {
//             slice nullable_part = slice_struct(n->node.nullable, 0, vect_size(n->node.nullable), NULL);
//             return new_sppf_nullable_string_node(&nullable_part);
//         }
//         case sppf_leaf: return new_sppf_leaf_node(n->node.leaf);
//         case sppf_inner: return new_sppf_inner_node(n->node.inner.head_idx, /*n->node.inner.body_idx,*/0, n->node.inner.source_start_idx, n->node.inner.source_end_idx);
//     }
// }


// /**
//  * Determine if two sppf_nodes are equal.
//  * Does not account for possible children of the SPPF nodes.
//  */
// bool sppf_node_equals(sppf_node* left, sppf_node* right)
// {
//     if (left->type != right->type) { return false; }
//     switch (left->type)
//     {
//         case sppf_leaf: return left->node.leaf == right->node.leaf;
//         case sppf_nullable: return vect_equals(left->node.nullable, right->node.nullable);
//         case sppf_inner: 
//             return left->node.inner.head_idx == right->node.inner.head_idx
//                 // && left->node.inner.body_idx == right->node.inner.body_idx 
//                 && left->node.inner.source_start_idx == right->node.inner.source_start_idx
//                 && left->node.inner.source_end_idx == right->node.inner.source_end_idx;
//     }
// }


// /**
//  * Print out a representation of the SPPF node.
//  */
// void sppf_node_str(sppf_node* n)
// {
//     printf("(");
//     switch (n->type)
//     {
//         case sppf_leaf: 
//         {
//             printf("`");
//             unicode_str(srnglr_get_input_source()[n->node.leaf]);
//             printf("`, %"PRIu64, n->node.leaf); 
//             break;
//         }
//         case sppf_nullable:
//         {
//             printf(vect_size(n->node.nullable) > 0 ? "ϵ: " : "ϵ");
//             for (size_t i = 0; i < vect_size(n->node.nullable); i++)
//             {
//                 uint64_t* symbol_idx = vect_get(n->node.nullable, i)->data;
//                 obj* symbol = metaparser_get_symbol(*symbol_idx);
//                 obj_str(symbol);
//                 if (i < vect_size(n->node.nullable) - 1){ printf(", "); }
//             }
//             break;
//         }
//         case sppf_inner:
//         {
//             obj_str(metaparser_get_symbol(n->node.inner.head_idx));
//             // printf(":%"PRIu64", %"PRIu64"-%"PRIu64, n->node.inner.body_idx, n->node.inner.source_start_idx, n->node.inner.source_end_idx);
//             printf(", %"PRIu64"-%"PRIu64, /*n->node.inner.body_idx,*/ n->node.inner.source_start_idx, n->node.inner.source_end_idx);
//             break;
//         }
//     }
//     printf(")");
// }


// /**
//  * version of sppf_node_str used for printing nodes when printing the whole SPPF tree.
//  * body_idx is only used for inner nodes, and may be (uint64_t)-1 otherwise
//  */
// void sppf_node_str2(sppf_node* n, uint64_t body_idx)
// {
//     switch (n->type)
//     {
//         case sppf_leaf: 
//         {
//             // printf("`");
//             unicode_str(srnglr_get_input_source()[n->node.leaf]);
//             // printf("`, %"PRIu64, n->node.leaf); 
//             break;
//         }
//         case sppf_nullable:
//         {
//             printf(vect_size(n->node.nullable) > 0 ? "ϵ: " : "ϵ");
//             for (size_t i = 0; i < vect_size(n->node.nullable); i++)
//             {
//                 uint64_t* symbol_idx = vect_get(n->node.nullable, i)->data;
//                 obj* symbol = metaparser_get_symbol(*symbol_idx);
//                 obj_str(symbol);
//                 if (i < vect_size(n->node.nullable) - 1){ printf(" "); }
//             }
//             break;
//         }
//         case sppf_inner:
//         {
//             obj_str(metaparser_get_symbol(n->node.inner.head_idx));
//             printf(":%"PRIu64, body_idx);
//             break;
//         }
//     }
// }


// /**
//  * Print out the internal representation of the SPPF node.
//  */
// void sppf_node_repr(sppf_node* n)
// {
//     switch (n->type)
//     {
//         case sppf_leaf: printf("sppf_leaf{%"PRIu64"}", n->node.leaf); break;
//         case sppf_nullable: printf("sppf_nullable{ϵ"); vect_str(n->node.nullable); printf("}"); break;
//         case sppf_inner:
//             // printf("sppf_inner{%"PRIu64", %"PRIu64", %"PRIu64", %"PRIu64"}", 
//             //     n->node.inner.head_idx,
//             //     n->node.inner.body_idx,
//             //     n->node.inner.source_start_idx, 
//             //     n->node.inner.source_end_idx
//             // );
//             printf("sppf_inner{%"PRIu64", %"PRIu64", %"PRIu64"}", 
//                 n->node.inner.head_idx,
//                 n->node.inner.source_start_idx, 
//                 n->node.inner.source_end_idx
//             );
//             break;
//     }
// }


// /**
//  * Release allocated resources for the SPPF node.
//  */
// void sppf_node_free(sppf_node* n)
// {
//     //only potential inner allocation is for nullable strings
//     if (n->type == sppf_nullable)
//     {
//         vect_free(n->node.nullable);
//     }

//     //free the node container
//     free(n);
// }


// /**
//  * Release allocated resources for the SPPF edge.
//  */
// void sppf_edge_free(sppf_edge* e)
// {
//     if (e->packed)
//     {
//         set_free(e->children.indices);
//     }
//     free(e);
// }



#endif