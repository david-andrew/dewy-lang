//helper functions for managing strings and so forth in compiler compiler
#ifndef UTILITIES_C
#define UTILITIES_C

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "utilities.h"
#include "ustring.h"


/**
    clamp an integer to a range
*/
int clamp(int x, int min, int max)
{
    if (x < min) x = min;
    else if (x > max) x = max;
    return x;
}

/**
    convert a Dewy style index to a size_t according to Dewy indexing rules for slicing
*/
size_t dewy_index(int index, int length)
{
    index = (index < 0) ? length + index : index;   //if negative, use end relative indexing 
    // printf("dewy index: %d\n", clamp(index, 0, length - 1));
    return (size_t) clamp(index, 0, length - 1);    //clamp the index to the range of the array length
}

/**
    return a substring according to dewy string slicing rules
*/
char* substr(char* str, int start, int stop)
{
    size_t length = strlen(str);
    size_t start_idx = dewy_index(start, length);
    size_t stop_idx = dewy_index(stop, length);

    //compute length of substring
    size_t substr_length = (start_idx < stop_idx) ? stop_idx - start_idx + 1 : 0;
    // printf("substring length: %d\n", substr_length);

    //perform copy. Leave room for null terminator at the end
    char* substr = malloc((substr_length + 1) * sizeof(char));
    char* ptr = substr;
    for (size_t i = start_idx; i <= stop_idx; i++)
    {
        *ptr++ = str[i];
    }
    *ptr = 0; //add null terminator to end of string
    return substr;
}


/**
    get a copy of a string
*/
char* clone(char* string)
{
    size_t size = (strlen(string) + 1) * sizeof(char);
    char* copy = malloc(size);
    memcpy((void*)copy, (void*)string, size);
    return copy;

    //slower version
    // char* copy = malloc((strlen(string) + 1) * sizeof(char));
    // char* ptr = copy;
    // while ((*ptr++ = *string++));
    // return copy;
}


/**
    concatenate 2 strings together
*/
char* concatenate(char* left, char* right)
{
    char* combined = malloc((strlen(left) + strlen(right)) * sizeof(char));
    char* ptr = combined;
    while ((*ptr++ = *left++));
    ptr--;  //remove null terminator from left string
    while ((*ptr++ = *right++));
    return combined;
}

//TODO->convert this to read file directly char by char, rather than copy into my own buffer
//what about multiple files though?
/*
    int c; // note: int, not char, required to handle EOF
    while ((c = fgetc(fp)) != EOF) { // standard C I/O file reading loop
       putchar(c);
    }
*/
size_t read_file(char* filename, char** destination)
{
    //see: https://stackoverflow.com/questions/14002954/c-programming-how-to-read-the-whole-file-contents-into-a-buffer
    FILE *f = fopen(filename, "rb");
    if (f == NULL)
    {
        printf("ERROR: could not open file at %s\n", filename);
        exit(1);
    }
    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);  /* same as rewind(f); */

    *destination = malloc(fsize + 1);
    fread(*destination, fsize, 1, f);
    fclose(f);

    (*destination)[fsize] = 0;

    return fsize;
}


/**
 * Convert the contents of a file to a unicode (uint32_t) string.
 */
size_t read_unicode_file(char* filename, uint32_t** destination)
{
    //get the normal char* version of the file content
    char* cstr;
    read_file(filename, &cstr);

    //count out the number of unicode characters in the file string
    size_t unicode_length = 0;
    char* c = cstr;
    while (eat_utf8(&c)) { unicode_length++; }

    //create a uint32_t string to hold unicode characters
    *destination = malloc(unicode_length + 1 * sizeof(uint32_t));

    //copy the string into the unicode array
    uint32_t* u = *destination;     //pointer to current unicode character
    c = cstr;                       //pointer to current char character
    while ((*u++ = eat_utf8(&c)));    //copy until null terminator reached

    //free the original file string
    free(cstr);

    return unicode_length;
}


/**
 * Print the given string `times` times.
 */
void repeat_str(char* str, size_t times)
{
    for (size_t i = 0; i < times; i++)
    {
        printf("%s", str);
    }
}


//For a discussion on hashes: https://softwareengineering.stackexchange.com/questions/49550/which-hashing-algorithm-is-best-for-uniqueness-and-speed

// http://www.cse.yorku.ca/~oz/hash.html
uint64_t djb2(char* str)
{
    uint64_t hash = 5381;
    uint8_t c;
    while ((c = *str++))
    {
        hash = (hash << 5) + hash + c;
    }
    return hash;
}

uint64_t djb2a(char* str)
{
    uint64_t hash = 5381;
    uint8_t c;
    while ((c = *str++)) 
    {
        hash = hash * 33 ^ c;
    }
    return hash;
}


//http://www.isthe.com/chongo/tech/comp/fnv/
uint64_t fnv1a(char* str)
{
    uint64_t hash = 14695981039346656037lu;
    uint8_t c;
    while ((c = *str++))
    {
        hash ^= c;
        hash *= 1099511628211;
    }
    return hash;
}


uint64_t hash_int(int64_t val)
{
    return hash_uint(*((uint64_t*)&val));
}
uint64_t hash_uint(uint64_t val)
{
    uint64_t hash = 14695981039346656037lu;
    uint8_t* v = (uint8_t*)&val;
    for (int i = 7; i >= 0; i--) //loop from least significant to most significant
    {
        hash ^= *(v + i);
        hash *= 1099511628211; 
    }
    return hash;
}


/**
 * Hash the sequence of uint64_t's using a modified version of fnv1a.
 */
uint64_t hash_uint_sequence(uint64_t* seq, size_t n)
{
    uint64_t hash = 14695981039346656037lu;

    //loop through each of the uint64_t's in the sequence
    for (size_t i = 0; i < n; i++)
    {
        //reinterpret the uint64_t as 8 bytes
        uint64_t val = seq[i];
        uint8_t* bytes = (uint8_t*)&val;

        //hash combine byte into the hash
        for (int j = 7; j >= 0; j--)
        {
            hash ^= bytes[j];
            hash *= 1099511628211;
        }
    }
    return hash;
}


uint64_t hash_bool(bool val)
{
    //cast the bool to a 64-bit 0 or 1, and return it's hash
    return hash_uint((uint64_t)val);
}


/**
    return the next value in the 64-bit lfsr sequence
*/
uint64_t lfsr64_next(uint64_t curr)
{
    return curr >> 1 | (curr ^ curr >> 1 ^ curr >> 3 ^ curr >> 4) << 63;
}

/**
    return the previous value in the 64-bit lfsr sequence
*/
uint64_t lfsr64_prev(uint64_t curr)
{
    return curr << 1 | ((curr >> 63 ^ curr ^ curr >> 2 ^ curr >> 3) & 0x1);
}



#endif