#ifndef CHARSET_C
#define CHARSET_C

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include "charset.h"
#include "object.h"
#include "utilities.h"
#include "ustring.h"

#define DEFAULT_CHARSET_CAPACITY 8

/**
 * Return a new (empty) unicode character set.
 */
charset* new_charset()
{
    charset* s = malloc(sizeof(charset));
    *s = (charset){
        .ranges = calloc(DEFAULT_CHARSET_CAPACITY, sizeof(urange)), 
        .size = 0, 
        .capacity = DEFAULT_CHARSET_CAPACITY
    };
    return s;
}


/**
 * Return a charset containing the special endmarker terminal `$` using 0x200000.
 * Care must be taken when dealing with this charset, as 0x200000 is not a valid 
 * unicode code point, and may cause undefined behavior.
 * Essentially the charset returned from this funciton should be treated as immutable.
 */
charset* charset_get_endmarker()
{
    charset* endmarker = new_charset();
    charset_add_char(endmarker, UNICODE_ENDMARKER_POINT);
    return endmarker;
}


/**
 * Construct an object wrapped unicode character set. If `s == NULL`, return an empty charset obj.
 */
obj* new_charset_obj(charset* s)
{
    if (s == NULL) s = new_charset();
    obj* S = malloc(sizeof(obj));
    *S = (obj){.type=CharSet_t, .data=s};
    return S;
}


/**
 * Insert the given unicode character into the charset.
 */
void charset_add_char(charset* s, uint32_t c)
{
    charset_add_range(s, (urange){.start=c, .stop=c});
}


/**
 * Insert the given unicode range into the character set.
 */
void charset_add_range(charset* s, urange r)
{
    //ensure range is well ordered
    r = r.start <= r.stop ? r : (urange){.start=r.stop, .stop=r.start};

    //append the range to the end of the charset, and then convert to reduced form
    charset_add_range_unchecked(s, r);
    charset_reduce(s);
}


/**
 * Push a unicode range to the charset without checking anything
 */
void charset_add_range_unchecked(charset* s, urange r)
{
    if (s->size == s->capacity)
    {
        charset_resize(s, s->size * 2);
    }
    s->ranges[s->size] = r;
    s->size++;
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
 * Expand or contract the size of the array holding the unicode ranges.
 */
void charset_resize(charset* s, size_t new_size)
{
    if (s->size > new_size)
    {
        printf("ERROR: charset resize failed. new size is not large enough to accomodate elements in charset\n");
        exit(1);
    }

    urange* new_ranges = malloc(new_size * sizeof(urange));
    if (new_ranges == NULL)
    {
        printf("ERROR: memory allocation for resized charset ranges failed\n");
        exit(1);
    }

    memcpy(new_ranges, s->ranges, s->size * sizeof(urange));
    free(s->ranges);
    s->ranges = new_ranges;
    s->capacity = new_size;
}


/**
 * Return a copy of the given charset.
 */
charset* charset_clone(charset* s)
{
    charset* copy = new_charset();
    for (int i = 0; i < s->size; i++)
    {
        charset_add_range_unchecked(copy, s->ranges[i]);
    }
    charset_reduce(copy); //TODO->probably can take out since s should already be reduced...
    return copy;
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
 * sort all of the unicode ranges in the character set.
 */
void charset_sort(charset* s)
{
    qsort(s->ranges, s->size, sizeof(urange), urange_compare);
}


/**
 * Sort and combine any intesecting ranges so that we have the minimal number of ranges to represent the set.
 */
void charset_reduce(charset* s)
{
    //if 1 or less ranges, then charset is already reduced
    if (s->size <= 1) { return; }

    //ensure the charset is sorted before redusing
    charset_sort(s);

    //create new range list for holding reduced ranges. Make large enough to hold up to same number of elements.
    size_t new_capacity = s->size;
    urange* new_ranges = malloc(new_capacity * sizeof(urange));

    //reducing algorithm
    int j = 0;
    new_ranges[j] = s->ranges[0];

    for (int i = 1; i < s->size; i++)
    {
        //if next range falls within current range being reduced
        if (s->ranges[i].start <= new_ranges[j].stop + 1)
        {
            //if next range is farther right than current range, replace right end
            if (new_ranges[j].stop < s->ranges[i].stop)
            {
                new_ranges[j].stop = s->ranges[i].stop; 
            }
        }
        else //set the next range as the range being reduced
        {
            j++;
            new_ranges[j] = s->ranges[i];
        }
    }

    //replace s->ranges with new_ranges
    free(s->ranges);
    s->ranges = new_ranges;
    s->size = j + 1;
    s->capacity = new_capacity;

    //if charset is small enough, resize to take up less space
    if (s->size < s->capacity / 2)
    {
        charset_resize(s, s->capacity / 2);
    }
}


/**
 * Return a charset that is the compliment of `s`.
 */
charset* charset_compliment(charset* s)
{
    //charset to hold compliment
    charset* compliment = new_charset();

    //compliment algorithm
    uint32_t left = 0;
    for (int i = 0; i < s->size; i++)
    {
        urange r = s->ranges[i];
        if (left < r.start)
        {
            //push range left-(r.start-1) to compliment
            charset_add_range_unchecked(compliment, (urange){.start=left, .stop=r.start-1});
        }
        left = r.stop + 1;
    }

    //if anything remaining in big range, push to charset
    if (left <= MAX_UNICODE_POINT)
    {
        charset_add_range_unchecked(compliment, (urange){.start=left, .stop=MAX_UNICODE_POINT});
    }

    return compliment;
}


/**
 * Return `a - b`, i.e. only elements in `a` and not in `b` will be kept.
 */
charset* charset_diff(charset* a, charset* b)
{
    //perform diff using set algebra: a - b => a & b~
    charset* b_prime = charset_compliment(b);
    charset* diff = charset_intersect(a, b_prime);
    
    //free intermediate charset
    charset_free(b_prime);

    return diff;
}


/**
 * Return `a & b`, i.e. only elements in both `a` and `b` are kept.
 */
charset* charset_intersect(charset* a, charset* b)
{
    //perform intersect using set algebra: a & b => (a~ | b~)~
    charset* a_prime = charset_compliment(a);
    charset* b_prime = charset_compliment(b);
    charset* prime_union = charset_union(a_prime, b_prime);
    charset* intersect = charset_compliment(prime_union);
    
    //free intermediate charsets
    charset_free(a_prime);
    charset_free(b_prime);
    charset_free(prime_union);

    return intersect;
}


/**
 * Create a new charset including all ranges from `a` and `b`.
 */
charset* charset_union(charset* a, charset* b)
{
    charset* onion = new_charset();

    for (int i = 0; i < a->size; i++)
    {
        charset_add_range_unchecked(onion, a->ranges[i]);
    }
    for (int i = 0; i < b->size; i++)
    {
        charset_add_range_unchecked(onion, b->ranges[i]);
    }

    charset_reduce(onion);

    return onion;
}


/**
 * Determine whether two charsets are equivalent. Assumes `a` and `b` are in reduced form.
 */
bool charset_equals(charset* a, charset* b)
{
    if (a->size != b->size)
    {
        return false;
    }
    for (int i = 0; i < a->size; i++)
    {
        if (a->ranges[i].start != b->ranges[i].start || a->ranges[i].stop != b->ranges[i].stop)
        {
            return false;
        }
    }
    return true;
}


/**
 * Determine if the given charset is the anyset, i.e. all unicode characters.
 */
bool charset_is_anyset(charset* s)
{
    return s->size == 1 && s->ranges[0].start == 0 && s->ranges[0].stop == MAX_UNICODE_POINT;
}


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
 * Return whether or not the charset contains the unicode character.
 */
bool charset_contains_c(charset* s, uint32_t c)
{
    return charset_get_c_index(s, c) >= 0; 
}


/**
 * Return whether or not the unicode range is contained within the charset.
 */
bool charset_contains_r(charset* s, urange r)
{
    int i0 = charset_get_c_index(s, r.start);
    int i1 = charset_get_c_index(s, r.stop);
    return (i0 == i1 && i0 >= 0);
}

/**
 * Determine if `superset` is an actual superset of the `subset` charset
 * i.e. does `superset` contain all unicode characters in `subset`
 */
bool charset_contains_charset(charset* superset, charset* subset)
{
    for (size_t i = 0; i < subset->size; i++)
    {
        if (!charset_contains_r(superset, subset->ranges[i]))
            return false;
    }
    return true;
}


/**
 * Check if the unicode character falls withing the given range.
 */
bool urange_contains_c(urange r, uint32_t c)
{
    return r.start <= c && c <= r.stop;
}


/**
 * Returns true if c is a character that needs to be escaped in a charset,
 * i.e. `[`, `-`, or `]`
 */
bool is_charset_escape(uint32_t c)
{
    return c == '[' || c == '-' || c == ']' || c == '\\'; 
}

/**
 * print out the given charset char as either a literal, an escape char or a hex value.
 */
void charset_char_str(uint32_t c, bool single_char)
{
    if (is_unicode_escape(c))
    { 
        printf("\\");
        put_unicode(unicode_to_escape(c));
    }
    else if (is_charset_escape(c))
    {
        if (!single_char) { printf("\\"); }
        put_unicode(c);
    }
    else if (is_printable_unicode(c))
    {
        put_unicode(c);
    }
    else if (c == UNICODE_ENDMARKER_POINT)
    {
        printf("#$");
    }
    else 
    {
        printf("\\x%X", c);
    }
}


/**
 * Return the print width of the charset char to be printed.
 */
int charset_char_strlen(uint32_t c, bool single_char)
{
    int width;
    if (is_unicode_escape(c) || c == UNICODE_ENDMARKER_POINT)
    { 
        //unicode character with an escape slash
        width = 2;
    }
    else if (is_charset_escape(c))
    {
        width = single_char ? 1 : 2;
    }
    else if (is_printable_unicode(c))
    {
        //single normal unicode character
        width = 1;
    }
    else 
    {
        //compute the width of the hex char to be printed
        width = snprintf("", 0, "\\x%X", c);
    }
    return width;
}


/**
 * Print out a string representation of the charset.
 */
void charset_str(charset* s)
{
    bool single_char = s->size == 1 && s->ranges[0].start == s->ranges[0].stop;
    if (!single_char) { printf("["); }
    for (int i = 0; i < s->size; i++)
    {
        charset_char_str(s->ranges[i].start, single_char);
        if (s->ranges[i].stop != s->ranges[i].start)
        {
            //only print dash on ranges larger than 2
            if (s->ranges[i].stop - s->ranges[i].start > 1) { printf("-"); }
            charset_char_str(s->ranges[i].stop, single_char);
        }
    }
    if (!single_char) { printf("]"); }
}


/**
 * Determine the number of characters that would be printed by the charset
 */
int charset_strlen(charset* s)
{
    int length = 0;
    bool single_char = s->size == 1 && s->ranges[0].start == s->ranges[0].stop;
    if (!single_char) { length += 2; } //for starting/ending []
    for (int i = 0; i < s->size; i++)
    {
        length += charset_char_strlen(s->ranges[i].start, single_char);
        if (s->ranges[i].stop != s->ranges[i].start)
        {
            //only print dash on ranges larger than 2
            if (s->ranges[i].stop - s->ranges[i].start > 1) { length += 1; } //for dash in range
            length += charset_char_strlen(s->ranges[i].stop, single_char);
        }
    }
    return length;
}


/**
 * Print a representation of the internal state of the charset.
 */
void charset_repr(charset* s)
{
    printf("charset = [");  
    if (s->size > 0) printf("\n");  
    for (int i = 0; i < s->size; i++)
    {
        urange r = s->ranges[i];
        printf("  \\x%X", r.start);
        if (r.start != r.stop)
        {
            printf("-\\x%X", r.stop);
        }
        if (i + 1 <= s->size - 1) printf(",");
        printf("\n");
    }
    printf("]\n");
}

/**
 * Free all of a charset object's memory allocations.
 */
void charset_free(charset* s)
{
    free(s->ranges);
    free(s);
}


/**
 * Hash the charset object with a modified version of fnv1a.
 */
uint64_t charset_hash(charset* s)
{
    //create a uint64_t list of data in the charset
    uint64_t* values = malloc(sizeof(uint64_t) * charset_size(s));
    for (size_t i = 0; i < charset_size(s); i++)
    {
        //merge start/stop uint32_t into a single uint64_t
        uint64_t val = 0;
        val += s->ranges[i].start;
        val <<= 32;
        val += s->ranges[i].stop;
        values[i] = val;
    }

    //hash the sequence and return the result
    uint64_t hash = hash_uint_sequence(values, charset_size(s));
    free(values);
    return hash;
}


#endif