#ifndef CHARSET_C
#define CHARSET_C

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include "charset.h"
#include "object.h"
#include "utilities.h"

#define DEFAULT_CHARSET_CAPACITY 8

/**
 * 
 */
charset* new_charset()
{
    charset* s_ptr = malloc(sizeof(charset));
    charset s = {
        .ranges=calloc(DEFAULT_CHARSET_CAPACITY, sizeof(urange)), 
        .size=0, 
        .capacity=DEFAULT_CHARSET_CAPACITY
    };
    *s_ptr = s;
    return s_ptr;
}


/**
 * 
 */
obj* new_charset_obj(charset* s)
{
    obj* S = malloc(sizeof(obj));
    S->type = CharSet_t;
    S->size = 0;
    charset** s_ptr = malloc(sizeof(charset*));
    *s_ptr = s != NULL ? s : new_charset();
    S->data = (void*)s_ptr;
    return S;
}


/**
 * 
 */
bool charset_add_range(charset* s, urange r)
{
    //ensure range is well ordered
    r = r.start <= r.stop ? r : (urange){.start=r.stop, .stop=r.start};

    //if charset already has range, then we're done
    if (charset_contains_r(s, r)) { return true; }
    
    //check if r intersects any existing ranges, and if so, extend them
    int i;
    if ((i = charset_get_c_index(s, r.start)) >= 0)
    {
        s->ranges[i].stop = r.stop;
        return true;
    }
    else if ((i = charset_get_c_index(s, r.stop)) >= 0)
    {
        s->ranges[i].start = r.start;
        return true;
    }
    
    //resize if out of space
    if (s->size == s->capacity)
    {
        if (!(charset_resize(s, s->capacity * 2)))
        {
            return false;
        }
    }

    //append the range to the end of the charset, and then rectify
    s->ranges[s->size] = r;
    s->size++;
    charset_rectify(s);
    return true;
}


/**
 * returns the number of unicode ranges contained in the character set.
 */
size_t charset_size(charset* s)
{
    return s->size;
}


/**
 * returns the number of unicode ranges the character set can hold
 */
size_t charset_capacity(charset* s)
{
    return s->capacity;
}

/**
 * counts the total width of all unicode ranges contained in the character set.
 */
uint64_t charset_length(charset* s)
{
    uint64_t length = 0;
    for (int i = 0; i < s->size; i++)
    {
        length += s->ranges[i].stop - s->ranges[i].start + 1;
    }
    return length;
}


/**
 * 
 */
bool charset_resize(charset* s, size_t new_size)
{
    if (s->size > new_size)
    {
        printf("ERROR: charset resize failed. new size is not large enough to accomodate elements in charset\n");
        return false;
    }

    urange* new_ranges = malloc(new_size * sizeof(urange));
    if (new_ranges == NULL)
    {
        printf("ERROR: memory allocation for resized charset ranges failed\n");
        return false;
    }

    memcpy(new_ranges, s->ranges, s->size * sizeof(urange));
    free(s->ranges);
    s->ranges = new_ranges;
    s->capacity = new_size;
    return true;
}



/**
 * comparison function for use in qsort for sorting an array of unicode ranges.
 */
int urange_compare(const void* a, const void* b)
{
    const urange A = *(urange*)a;
    const urange B = *(urange*)b;
    return A.start != B.start ? A.start - B.start : A.stop - B.stop;
}


/**
 * return a charset with sorted and maximally combined ranges.
 */
void charset_rectify(charset* s)
{
    charset_sort(s);
    charset_condense(s);
}


/**
 * sort all of the unicode ranges in the character set.
 */
void charset_sort(charset* s)
{
    qsort(s->ranges, s->size, sizeof(urange), urange_compare);
}


/**
 * conbine any intesecting ranges so that we have the minimal number of ranges to represent the set.
 */
void charset_condense(charset* s)
{
    if (s->size <= 1) { return; }

    urange* new_ranges = malloc(s->size * sizeof(urange));
    int j = 0;
    new_ranges[j] = s->ranges[0];

    for (int i = 1; i < s->size; i++)
    {
        if (new_ranges[j].stop >= s->ranges[i].start)
        {
            new_ranges[j].stop = s->ranges[i].stop;
        }
        else
        {
            j++;
            new_ranges[j] = s->ranges[i];
        }
    }

    free(s->ranges);
    s->ranges = new_ranges;
    s->size = j + 1;

    // if (s->size < s->capacity / 2)
    // {
    //     charset_resize(s, s->capacity / 2);
    // }

}


/**
 * return a charset that is the compliment of s
 */
charset* charset_compliment(charset* s)
{

}


/**
 * 
 */
charset* charset_diff(charset* a, charset* b)
{

}


/**
 * 
 */
charset* charset_intersect(charset* a, charset* b)
{

}


/**
 * 
 */
charset* charset_union(charset* a, charset* b)
{

}


// /**
//  * Get the index of the charset ranges that contains unicode character `c`.
//  * If no range is found, return -1
//  */
// int charset_get_c_index(charset* s, uint32_t c)
// {
//     for (int i = 0; i < s->size; i++)
//     {
//         if (s->ranges[i].start <= c && c <= s->ranges[i].stop)
//         {
//             return i;
//         }
//     }
//     return -1;
// }


/**
 * Get the index of the charset ranges that contains unicode character `c`.
 * If no range is found, return -1.
 */
int charset_get_c_index(charset* s, uint32_t c)
{
    //perform binary search to find range
    int l = 0, r = s->size - 1;
    while (r - l >= 0)
    {
        int i = (r + l) / 2;
        if (s->ranges[i].start <= c && c <= s->ranges[i].stop)
        {
            return i;
        }
        else if (c < s->ranges[i].start)
        {
            r = i - 1;  //take left half of range
        }
        else
        {
            l = i + 1;  //take right half of range
        }
    }
    return -1;
}


/**
 * return whether or not the charset contains the 
 */
bool charset_contains_c(charset* s, uint32_t c)
{
    return charset_get_c_index(s, c) >= 0; 
}


/**
 * 
 */
bool charset_contains_r(charset* s, urange r)
{
    int i0 = charset_get_c_index(s, r.start);
    int i1 = charset_get_c_index(s, r.stop);
    return (i0 == i1 && i0 >= 0);
}


/**
 * 
 */
void charset_str(charset* s)
{
    printf("[");
    for (int i = 0; i < s->size; i++)
    {
        put_unicode(s->ranges[i].start);
        if (s->ranges[i].stop != s->ranges[i].start)
        {
            printf("-");
            put_unicode(s->ranges[i].stop);
        }
    }
    printf("]");
}


/**
 * 
 */
void charset_repr(charset* s)
{

}



#endif