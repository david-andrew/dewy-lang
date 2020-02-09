//helper functions for managing strings and so forth in compiler compiler
#ifndef UTILITIES_C
#define UTILITIES_C

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

#define AUGMENT_CHAR 0x200000 //first invalid codepoint (2^21)


//forward declare all functions
int clamp(int x, int min, int max);
size_t dewy_index(int index, int length);
char* substr(char* string, int start, int stop);
char* clone(char* string);
char* concatenate(char* left, char* right);
char* read_file(char* filename);

bool is_identifier_char(char c);
bool is_identifier_symbol_char(char c);
bool is_alpha_char(char c);
bool is_num_char(char c);
bool is_alphanum_char(char c);
bool is_whitespace_char(char c);

uint64_t djb2(char* str);
uint64_t djb2a(char* str);
uint64_t fnv1a(char* str);
uint64_t hash_uint(uint64_t val);
uint64_t hash_int(int64_t val);

uint64_t lfsr64_next(uint64_t curr);
uint64_t lfsr64_prev(uint64_t curr);

void put_unicode(uint32_t c);
uint32_t eat_utf8(char** str_ptr);
void unicode_str(uint32_t c);


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
char* substr(char* string, int start, int stop)
{
    size_t length = strlen(string);
    size_t start_idx = dewy_index(start, length);
    size_t stop_idx = dewy_index(stop, length);

    //compute length of substring
    size_t substr_length = (start_idx < stop_idx) ? stop_idx - start_idx : 0;
    // printf("substring length: %d\n", substr_length);

    //perform copy
    char* substr = malloc((substr_length + 1) * sizeof(char));
    char* ptr = substr;
    for (size_t i = start_idx; i <= stop_idx; i++)
    {
        *ptr++ = string[i];
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

char* read_file(char* filename)
{
    //see: https://stackoverflow.com/questions/14002954/c-programming-how-to-read-the-whole-file-contents-into-a-buffer
    FILE *f = fopen(filename, "rb");
    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);  /* same as rewind(f); */

    char *string = malloc(fsize + 1);
    fread(string, fsize, 1, f);
    fclose(f);

    string[fsize] = 0;

    return string;
}


bool is_identifier_char(char c)
{
    //valid identifier characters are
    //ABCDEFGHIJKLMNOPQRSTUVWXYZ
    //abcdefghijklmnopqrstuvwxyz
    //1234567890
    //~!@#$&_?
    return is_alphanum_char(c) || is_identifier_symbol_char(c);
}

bool is_identifier_symbol_char(char c)
{
    return c == '~' || c == '@' || c == '#' || c == '$' || c == '&' || c == '_' || c == '?';
}

bool is_alpha_char(char c)
{
    return (c >= 65 && c <= 90) || (c >= 97 && c <= 122);
}

bool is_num_char(char c)
{
    return c >= 48 && c <= 57;
}

bool is_alphanum_char(char c)
{
    return is_alpha_char(c) || is_num_char(c);
}

bool is_whitespace_char(char c)
{
    //whitespace includes tab (0x09), line feed (0x0A), line tab (0x0B), form feed (0x0C), carriage return (0x0D), and space (0x20)
    return c == 0x09 || c == 0x0A || c == 0x0B || c == 0x0C || c == 0x0D || c == 0x20;
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



//Implementation of dictionary
// https://stackoverflow.com/questions/327311/how-are-pythons-built-in-dictionaries-implemented

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



/**
    print the unicode character to the terminal as UTF-8

    This function uses int8_t instead of uint8_t since putchar expects a signed value
*/
void put_unicode(uint32_t c)
{
    if (c < 0x80)                               //0xxxxxxx
    {   
        int8_t b0 = c & 0x7F;                   //c & 0b01111111
        putchar(b0);
    }
    else if (c < 0x800)                         //110xxxxx 10xxxxxx
    {
        int8_t b0 = (c & 0x3F) | 0x80;          //c & 0b10111111
        int8_t b1 = (c >> 6 & 0xDF) | 0xC0;     //c >> 6 & 0b11011111
        putchar(b1);
        putchar(b0);
    } 
    else if (c < 0x10000)                       //1110xxxx 10xxxxxx 10xxxxxx
    {
        int8_t b0 = (c & 0x3F) | 0x80;          //c & 0b10111111
        int8_t b1 = (c >> 6 & 0x3F) | 0x80;     //c >> 6 & 0b10111111
        int8_t b2 = (c >> 12 & 0x0F) | 0xE0;    //c >> 12 & 0b11101111
        putchar(b2);
        putchar(b1);
        putchar(b0);
    }
    else if (c < 0x001FFFFF)                    //11110xxx 10xxxxxx 10xxxxxx 10xxxxxx
    {
        int8_t b0 = (c & 0x3F) | 0x80;          //c & 0b10111111
        int8_t b1 = (c >> 6 & 0x3F) | 0x80;     //c >> 6 & 0b10111111
        int8_t b2 = (c >> 12 & 0x3F) | 0x80;    //c >> 12 & 0b10111111
        int8_t b3 = (c >> 18 & 0x07) | 0xF0;    //c >> 18 & 0b11110111
        putchar(b3);
        putchar(b2);
        putchar(b1);
        putchar(b0);
    }
    else
    {
        printf("ERROR: invalid unicode codepoint \"%u\"\n", c);
    }
}

/**
    detect the next utf-8 character in str_ptr, and return it as a 32-bit codepoint.
    advance the str_ptr by the size of the detected utf-8 character
*/
uint32_t eat_utf8(char** str_ptr)
{
    uint8_t b0 = **str_ptr;
    (*str_ptr)++;

    if (!b0) //if this is a null terminator, return 0
    { 
        return 0; 
    }
    else if (b0 >> 7 == 0x00) //regular ascii character
    { 
        return b0; 
    }
    else if (b0 >> 5 == 0x06) //2 byte utf-8 character
    {   
        uint8_t b1 = **str_ptr;
        (*str_ptr)++;
        if (b1 >> 6 == 0x02)
        {
            return (b0 & 0x1F) << 6 | (b1 & 0x3F);
        }
    }
    else if (b0 >> 4 == 0x0E) //3 byte utf-8 character
    {
        uint8_t b1 = **str_ptr;
        (*str_ptr)++;
        if (b1 >> 6 == 0x02)
        {
            uint8_t b2 = **str_ptr;
            (*str_ptr)++;
            if (b2 >> 6 == 0x02)
            {
                return (b0 & 0x0F) << 12 | (b1 & 0x3F) << 6 | (b2 & 0x3F);
            }
        }
    }
    else if (b0 >> 3 == 0x1E) //4 byte utf-8 character
    {
        uint8_t b1 = **str_ptr;
        (*str_ptr)++;
        if (b1 >> 6 == 0x02)
        {
            uint8_t b2 = **str_ptr;
            (*str_ptr)++;
            if (b2 >> 6 == 0x02)
            {
                uint8_t b3 = **str_ptr;
                (*str_ptr)++;
                if (b3 >> 6 == 0x02)
                {
                    return (b0 & 0x07) << 18 | (b1 & 0x3F) << 12 | (b2 & 0x3F) << 6 | (b3 & 0x3F);
                }
            }
        }
    }
    
    printf("ERROR: eat_utf8() found ill-formed utf-8 character\n");
    return 0;
}

/**
    print the unicode character, or a special character for specific inputs
*/
void unicode_str(uint32_t c)
{
    if (c == 0)                 //null character. represents an empty string/set
    {
        put_unicode(0x2300);    // ⌀ (diameter symbol)
    }
    else if (c == AUGMENT_CHAR) // represents the end of a meta-rule
    {
        put_unicode(0x22D5);    // ⋕ (equal and parallel to)
    }
    else                        //any other unicode character
    {
        put_unicode(c);
    }
}


#endif