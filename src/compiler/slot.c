#ifndef SLOT_C
#define SLOT_C

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

#include "fset.h"
#include "metaparser.h"
#include "slice.h"
#include "slot.h"
#include "utilities.h"

/**
 * return the struct for a slot
 */
slot slot_struct(uint64_t head_idx, uint64_t production_idx, uint64_t position)
{
    return (slot){.head_idx = head_idx, .production_idx = production_idx, .position = position};
}

/**
 * Create a new slot.
 */
slot* new_slot(uint64_t head_idx, uint64_t production_idx, uint64_t position)
{
    slot* s = malloc(sizeof(slot));
    *s = slot_struct(head_idx, production_idx, position);
    return s;
}

/**
 * Create a new slot obj from an existing slot.
 * s is expected to be non-null.
 */
obj* new_slot_obj(slot* s)
{
    obj* S = malloc(sizeof(obj));
    *S = (obj){.type = Slot_t, .data = s};
    return S;
}

/**
 * Returns whether the slot is in an accepting state,
 * i.e. if the position is at the end of the list of body symbols.
 * Additionally, an item is accepting if the remaining string is nullable.
 */
bool slot_is_accept(slot* s)
{
    // get the body for this item
    vect* body = metaparser_get_production_body(s->head_idx, s->production_idx);

    if (s->position == vect_size(body))
    {
        // normal accept, when position is at end of body
        return true;
    }
    else
    {
        // check if the remaining portion of the string is nullable
        slice remaining = slice_struct(body, s->position, vect_size(body), NULL);
        fset* first = metaparser_first_of_string(&remaining);
        bool nullable = first->special;
        fset_free(first);
        return nullable;
    }
}

/**
 * Print out a string displaying the slot.
 */
void slot_str(slot* s)
{
    obj* head = metaparser_get_symbol(s->head_idx);
    vect* body = metaparser_get_production_body(s->head_idx, s->production_idx);

    printf("[");
    obj_str(head);
    printf(" -> ");
    for (size_t i = 0; i <= vect_size(body); i++)
    {
        if (i == s->position) { printf("•"); }
        if (i == vect_size(body)) { break; };
        uint64_t* symbol_idx = vect_get(body, i)->data;
        obj* symbol = metaparser_get_symbol(*symbol_idx);
        obj_str(symbol);
        if (i < vect_size(body) - 1) { printf(" "); }
    }
    printf("]");
}

/**
 * Print out the internal representation of a slot.
 */
void slot_repr(slot* s)
{
    printf("slot{head_idx: %" PRIu64 ", production_idx: %" PRIu64 ", position: %" PRIu64 "}", s->head_idx,
           s->production_idx, s->position);
}

/**
 * Free an allocated slot.
 */
void slot_free(slot* s) { free(s); }

/**
 * return a copy of the given slot
 */
slot* slot_copy(slot* s)
{
    slot* copy = malloc(sizeof(slot));
    *copy = *s;
    return copy;
}

/**
 * Compute the hash of the slot with a modified version of fnv1a.
 */
uint64_t slot_hash(slot* s)
{
    uint64_t components[] = {s->head_idx, s->production_idx, s->position};

    return hash_uint_sequence(components, sizeof(components) / sizeof(uint64_t));
}

/**
 * Determine whether two slots are equal.
 */
bool slot_equals(slot* left, slot* right)
{
    return left->head_idx == right->head_idx && left->production_idx == right->production_idx &&
           left->position == right->position;
}

#endif