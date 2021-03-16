//helper functions for managing strings and so forth in compiler compiler
#ifndef UTILITIES_C
#define UTILITIES_C

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

#include "utilities.h"


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
 * Return a unicode substring converted from the given utf8 string.
 * Indices index the unicode output string, not the utf8 input string.
 * Does not use Dewy slicing rules, only positive in bounds indices.
 * `stop` and `start` bounds are inclusive
 */
uint32_t* unicode_substr(char* str, int start, int stop)
{
    //unicode string length (includes chars at start and stop)
    size_t length = stop - start + 1;

    //allocate uint32_t string with room for null terminator at the end
    uint32_t* substr = malloc((length + 1) * sizeof(uint32_t));

    //copy pointer for assigning each character
    uint32_t* ptr = substr;

    //throw away everything up to the start of the substring
    for (int i = 0; i < start; i++)
    {
        eat_utf8(&str);
    }
    //copy the substring to our unicode array
    for (int i = 0; i < length; i++)
    {
        *ptr++ = eat_utf8(&str);
    }
    *ptr = 0; //null terminator at the end of the string

    return substr;
}


/**
 * Return a unicode string converted from the given utf8 string.
 * Indices index the utf8 input string, not unicode output string.
 * Does not use Dewy slicing rules, only positive in bounds indices.
 * `stop` and `start` bounds are inclusive
 */
uint32_t* utf8_substr(char* str, int start, int stop)
{
    //get the utf8 substring
    char* raw_str = substr(str, start, stop);

    //compute number of unicode characters in string
    size_t length = utf8_length(raw_str);

    //get the unicode version of the string by taking a unicode substring of the whole length
    uint32_t* s = unicode_substr(raw_str, 0, length-1);
    
    //free the temporary raw string
    free(raw_str);

    return s;
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

size_t unicode_strlen(uint32_t* string)
{
    size_t length = 0;
    while (string[length]) { length++; }
    return length;
}


/**
 * Compare two unicode strings. 
 * Identical algorithm to normal char* strcmp.
 */
int64_t unicode_strcmp(uint32_t* left, uint32_t* right)
{
    uint32_t l, r;
    do
    {
        l = *left++;
        r = *right++;
        if (l == 0) break;
    }
    while (l == r);
    return l - r;
}


/**
 * Clone a null terminated unicode string.
 */
uint32_t* clone_unicode(uint32_t* string)
{
    //get length of string
    size_t length = unicode_strlen(string);

    //perform copy
    uint32_t* copy = malloc((length + 1) * sizeof(uint32_t));
    uint32_t* ptr = copy;
    while ((*ptr++ = *string++));
    return copy;
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


// /**
//  * Convert the contents of a file to a unicode (uint32_t) string.
//  * See: https://stackoverflow.com/questions/14002954/c-programming-how-to-read-the-whole-file-contents-into-a-buffer
//  * TODO->make more efficient such that `unicode` is exactly the size of the number of unicode characters instead of ascii characters.
//  */
// uint32_t* read_unicode_file(char* filename)
// {
//     //open the file
//     FILE *f = fopen(filename, "rb");
//     fseek(f, 0, SEEK_END);
//     long fsize = ftell(f);
//     fseek(f, 0, SEEK_SET);  /* same as rewind(f); */

//     //copy file to normal char* string
//     char* string = malloc(fsize + 1);
//     fread(string, fsize, 1, f);
//     fclose(f);

//     //put null terminator at the end
//     string[fsize] = 0;

//     //create a uint32_t string to hold unicode characters
//     uint32_t* unicode = malloc(fsize + 1 * sizeof(uint32_t));

//     //copy the string into the unicode array
//     uint32_t* c = unicode;          //pointer to current unicode character
//     char* s = string;               //pointer to current char character
//     while (*c++ = eat_utf8(&s));    //copy until null terminator reached

//     //free the original string
//     free(string);

//     return unicode;
// }


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
    return c == '~' || c == '!' || c == '@' || c == '#' || c == '$' || c == '&' || c == '_' || c == '?';
}

bool is_alpha_char(char c)
{
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
}

bool is_dec_digit(char c)
{
    return c >= '0' && c <= '9';
}

bool is_alphanum_char(char c)
{
    return is_alpha_char(c) || is_dec_digit(c);
}


bool is_upper_hex_letter(char c)
{
    return c >= 'A' && c <= 'F';
}

bool is_lower_hex_letter(char c)
{
    return c >= 'a' && c <= 'f';
}

// returns true if character is a hexidecimal digit (both uppercase or lowercase valid)
bool is_hex_digit(char c)
{
    return is_dec_digit(c) || is_upper_hex_letter(c) || is_lower_hex_letter(c);
}

/**
 * Determines if the character is the escape char for starting hex numbers
 * Hex numbers can be \x#, \X#, \u#, or \U#.
 */
bool is_hex_escape(char c)
{
    return c == 'x' || c == 'X' || c == 'u' || c == 'U';
}


bool is_whitespace_char(char c)
{
    //whitespace includes tab (0x09), line feed (0x0A), line tab (0x0B), form feed (0x0C), carriage return (0x0D), and space (0x20)
    return c == 0x09 || c == 0x0A || c == 0x0B || c == 0x0C || c == 0x0D || c == 0x20;
}


/**
 * Determine if the character is a legal charset character
 * #charsetchar = \U - [\-\[\]] - #ws;
 */
bool is_charset_char(uint32_t c)
{
    return !(c == 0) && !is_whitespace_char((char)c) && !(c == '-' || c == '[' || c == ']');
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

//TODO->consider converting back to utf8 for hash?
uint64_t unicode_fnv1a(uint32_t* str)
{
    uint64_t hash = 14695981039346656037lu;
    uint32_t codepoint;
    while ((codepoint = *str++))
    {
        //reinterpret the codepoint as 4 bytes
        uint8_t* c = (uint8_t*)&codepoint; 
        for (int i = 3; i >= 0; i--)    //loop from least to most significant
        {
            hash ^= *(c + i);
            hash *= 1099511628211;
        }
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
    Read a hex string and convert to an unsigned integer
*/
uint64_t parse_hex(char* str)
{
    size_t len = strlen(str);
    uint64_t pow = 1;
    uint64_t val = 0;
    for (size_t i = len - 1; i >= 0; i--)
    {
        val += hex_digit_to_value(str[i]) * pow;
        pow *= 16;
    }
    return val;
}


/**
 * Read a hex string and convert to an unsigned integer
 */
uint64_t parse_unicode_hex(uint32_t* str)
{
    size_t len = unicode_strlen(str);
    uint64_t pow = 1;
    uint64_t val = 0;
    for (int64_t i = len - 1; i >= 0; i--)
    {
        val += hex_digit_to_value(str[i]) * pow;
        pow *= 16;
    }
    return val;
}



uint64_t hex_digit_to_value(char c)
{
    if (is_dec_digit(c)) 
    { 
        return c - '0'; 
    }
    else if (is_upper_hex_letter(c))
    {
        return c - 'A' + 10;
    }
    else if (is_lower_hex_letter(c))
    {
        return c - 'a' + 10;
    }
    printf("ERROR: character %c is not a hex digit\n", c);
    return 0;
}


/**
 * Read a decimal string, and convert to an unsigned integer.
 */
uint64_t parse_unicode_dec(uint32_t* str)
{
    size_t len = unicode_strlen(str);
    uint64_t pow = 1;
    uint64_t val = 0;
    for (int64_t i = len - 1; i >= 0; i--)
    {
        val += dec_digit_to_value(str[i]) * pow;
        pow *= 10;
    }
    return val;
}


/**
 * Convert a decimal digit to its numerical value
 */
uint64_t dec_digit_to_value(char c)
{
    if (is_dec_digit(c))
    {
        return c - '0';
    }
    printf("ERROR: character %c is not a decimal digit\n", c);
    return 0;
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
    else if (c <= 0x001FFFFF)                    //11110xxx 10xxxxxx 10xxxxxx 10xxxxxx
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
 * Return an allocated null terminated unicode string containing the given character.
 */
uint32_t* unicode_char_to_str(uint32_t c)
{
    uint32_t* str = malloc(2*sizeof(uint32_t));
    str[0] = c;
    str[1] = 0;
    return str;
}


/**
 * Return the unicode character at the given index in the utf8 string. `str_ptr` is not modified.
 */
uint32_t peek_unicode(char** str_ptr, size_t index, size_t* delta)
{
    char* str = *str_ptr;
    char** str_ptr_copy = &str;
    uint32_t c;
    for (size_t i = 0; i <= index; i++)
    {
        c = eat_utf8(str_ptr_copy);
    }
    if (delta != NULL) *delta = *str_ptr_copy - *str_ptr;
    return c;
}

/**
 * Compute the unicode length of the given utf8 string.
 */
size_t utf8_length(char* str)
{
    size_t i = 0;
    while (eat_utf8(&str)) { i++; };
    return i;
}

/**
    print the unicode character, or a special character for some special inputs
*/
void unicode_char_str(uint32_t c)
{
    if (c == 0)                 //null character. represents an empty string/set
    {
        put_unicode(0x2300);    // ⌀ (diameter symbol)
    }
    else if (c == AUGMENT_CHAR) // represents the end of a meta-rule
    {
        put_unicode(0x1F596);    // 🖖 (vulcan salute). easy to spot character
    }
    else                        //any other unicode character
    {
        put_unicode(c);
    }
}

/**
 * Print out the character or hex value of the given char.
 */
void ascii_or_hex_str(uint32_t c)
{
    if (0x21 <= c && c <= 0x7E) put_unicode(c);
    else printf("\\x%X", c);
}

void unicode_string_str(uint32_t* s)
{
    uint32_t c;
    while ((c = *s++)) put_unicode(c);
}

void unicode_string_repr(uint32_t* s)
{    
    // putchar('"');
    printf("U\"");
    unicode_string_str(s);
    putchar('"');
}


/**
 * Return the literal unicode represented by the escape char
 * Recognized escaped characters are \n \r \t \v \b \f and \a
 * all others just put the second character literally 
 * Common such literals include \\ \' \" \[ \] and \-
 */
uint32_t escape_to_unicode(uint32_t c)
{
    switch (c)
    {
        // recognized escape characters
        case 'a': return 0x7;   // bell
        case 'b': return 0x8;   // backspace
        case 't': return 0x9;   // tab
        case 'n': return 0xA;   // new line
        case 'v': return 0xB;   // vertical tab
        case 'f': return 0xC;   // form feed
        case 'r': return 0xD;   // carriage return
        
        // non-recognized escapes return the literal character
        default: return c;
    }
}

#endif