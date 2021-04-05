#ifndef USTRING_C
#define USTRING_C

#include <stdlib.h>
#include <stdio.h>

#include "ustring.h"
#include "utilities.h"
#include "metascanner.h"


/**
 * Create a new unicode string object from an allocated uint32_t*.
 * free() will be called on the string at the end of its life.
 */
obj* new_ustring_obj(uint32_t* s)
{
    obj* S = malloc(sizeof(obj));
    *S = (obj){.type=UnicodeString_t, .data=s};
    return S;
}


/**
 * Return a unicode substring converted from the given utf8 string.
 * Indices index the unicode output string, not the utf8 input string.
 * Does not use Dewy slicing rules, only positive in bounds indices.
 * `stop` and `start` bounds are inclusive
 */
uint32_t* ustring_charstar_substr(char* str, int start, int stop)
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
uint32_t* ustring_utf8_substr(char* str, int start, int stop)
{
    //get the utf8 substring
    char* raw_str = substr(str, start, stop);

    //compute number of unicode characters in string
    size_t length = utf8_length(raw_str);

    //get the unicode version of the string by taking a unicode substring of the whole length
    uint32_t* s = ustring_charstar_substr(raw_str, 0, length-1);
    
    //free the temporary raw string
    free(raw_str);

    return s;
}


/**
 * Return the length of the unicode string (not including the null terminater)
 */
size_t ustring_len(uint32_t* string)
{
    size_t length = 0;
    while (string[length]) { length++; }
    return length;
}


/**
 * Compare two unicode strings. 
 * Identical algorithm to normal char* strcmp.
 */
int64_t ustring_cmp(uint32_t* left, uint32_t* right)
{
    uint32_t l, r;
    do
    {
        l = *left++; r = *right++;
        if (l == 0) break;
    }
    while (l == r);
    return l - r;
}


/**
 * Compare a unicode string to a char* string.
 * Identical to ustring_cmp(), just that it handles
 * `right` as a char*. This means that `left` would need to be 
 * ascii only for it to possibly match `right`
 */
int64_t ustring_charstar_cmp(uint32_t* left, char* right)
{
    uint32_t l; char r;
    do 
    {
        l = *left++; r = *right++;
        if (l == 0) break;
    } 
    while (l == r);
    return l - r;
}


/**
 * Clone a null terminated unicode string.
 */
uint32_t* ustring_clone(uint32_t* string)
{
    //get length of string
    size_t length = ustring_len(string);

    //perform copy
    uint32_t* copy = malloc((length + 1) * sizeof(uint32_t));
    uint32_t* ptr = copy;
    while ((*ptr++ = *string++));
    return copy;
}


//TODO->consider converting back to utf8 for hash?
/**
 * Hash the unicode string using an adapted version of fnv1a.
 */
uint64_t ustring_hash(uint32_t* str)
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


/**
 * Convert the hex digit to its numerical value
 */
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
 * Read a hex string and convert to an unsigned integer
 */
uint64_t ustring_parse_hex(uint32_t* str)
{
    return ustring_parse_base(str, 16, hex_digit_to_value);
}


/**
 * Read a decimal string, and convert to an unsigned integer.
 */
uint64_t ustring_parse_dec(uint32_t* str)
{
    return ustring_parse_base(str, 10, dec_digit_to_value);
}


/**
 * Generic number parser for arbitrary base.
 */
uint64_t ustring_parse_base(uint32_t* str, uint64_t base, uint64_t (*base_digit_to_value)(char))
{
    size_t len = ustring_len(str);
    uint64_t pow = 1;
    uint64_t val = 0;
    for (int64_t i = len - 1; i >= 0; i--)
    {
        val += base_digit_to_value(str[i]) * pow;
        pow *= base;
    }
    return val;
}


/**
 * Returns true if the codepoint is visually printable to the terminal.
 * Excludes whitespace and other unidentifiable characters, which should
 * instead be printed as escaped hex values.
 */
bool is_printable_unicode(uint32_t c)
{
    if (c < '!') return false;
    else if (c < 0x7F) return  true;
    else if (c < 0xA1) return false;
    else if (c < 0x250) return true;
    //TODO->more in these contiguous ranges...
    
    //specific known good ranges
    else if (c >= 0x370 && c <= 0x3FF) return true;

    //printable ranges
    //0x21-0x7E     printable ascii
    //0xA1-0xFF     latin-1
    //0x100-0x17f   latin extended
    //0x180-0x24f   pinyin
    

    //0x370-0x3ff   greek

    return false;
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
uint32_t* ustring_from_unicode(uint32_t c)
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
void unicode_str(uint32_t c)
{
    if (c == 0)                 //null character. represents an empty string/set
    {
        put_unicode(0x2300);    // ⌀ (diameter symbol)
    }
    else if (c == UNICODE_ENDMARKER_POINT) // represents the end of a meta-rule
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
void unicode_ascii_or_hex_str(uint32_t c)
{
    if (0x21 <= c && c <= 0x7E) put_unicode(c);
    else printf("\\x%X", c);
}


/**
 * Print out the unicode character if it is a printable character.
 */
void printable_unicode_or_hex_str(uint32_t c)
{
    if (is_printable_unicode(c))
    {
        put_unicode(c);
    }
    else if (is_unicode_escape(c))
    { 
        printf("\\");
        put_unicode(unicode_to_escape(c));
    }
    else 
    {
        printf("\\x%X", c);
    }
}


void ustring_str(uint32_t* s)
{
    uint32_t c;
    while ((c = *s++)) put_unicode(c);
}


void unicode_string_repr(uint32_t* s)
{    
    // putchar('"');
    printf("U\"");
    ustring_str(s);
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

/**
 * Return the escape char represented by the literal unicode.
 * Recognized escaped characters are \n \r \t \v \b \f and \a
 * all others are not escape chars, and their value is simply returned.
 */
uint32_t unicode_to_escape(uint32_t c)
{
    switch (c)
    {
        // recognized escape characters
        case 0x7: return 'a';   // bell
        case 0x8: return 'b';   // backspace
        case 0x9: return 't';   // tab
        case 0xA: return 'n';   // new line
        case 0xB: return 'v';   // vertical tab
        case 0xC: return 'f';   // form feed
        case 0xD: return 'r';   // carriage return
        
        // non-recognized escapes return the literal character
        default: return c;
    }
}


/**
 * Returns true if the given unicode character can be printed as an escape character.
 */
bool is_unicode_escape(uint32_t c)
{
    return unicode_to_escape(c) != c;
}


/**
 * If possible, convert the case of the unicode charcter from upper to lower, or vice versa
 * If no conversion is possible, returns the input character.
 * Makes use of UnicodeData.txt
 */
uint32_t unicode_to_upper(uint32_t c)
{
    uint32_t uppercase, _;
    if (unicode_upper_and_lower(c, &uppercase, &_))
    {
        return uppercase;
    }

    //default case, return original
    return c;
}

uint32_t unicode_to_lower(uint32_t c)
{
    uint32_t _, lowercase;
    if (unicode_upper_and_lower(c, &_, &lowercase))
    {
        return lowercase;
    }

    //default case, return original
    return c;
}


/**
 * Parse UnicodeData.txt to find the line for the given codepoint, for case conversion
 * Sets the corresponding lowercase and uppercase codepoint if they exist.
 * Otherwise upercase and lowercase are set to the input c.
 * Results returned from this function should be cached since they are expensive to parse.
 * Returns true if successfully found codepoint, else false.
 */
bool unicode_upper_and_lower(uint32_t c, uint32_t* uppercase, uint32_t* lowercase)
{
    //file pointer + var to hold each character read in
    FILE* f = fopen("unicode_cases.txt", "r");
    int ch;

    //arrays to hold hex digits read in. length 7 to fit maximum codepoint 10FFFF, + null terminator 
    uint32_t codepoint_arr[7];
    uint32_t lowercase_arr[7];
    uint32_t uppercase_arr[7];
    
    while (true)
    {

        //scan through the first hex number in the line
        size_t i = 0;
        while ((ch = fgetc(f)) != EOF && ch != ':')
        {
            codepoint_arr[i++] = ch;
        }
        if (ch == EOF) { break; }
        codepoint_arr[i] = 0; //null terminator at the end of the string
        uint32_t codepoint = ustring_parse_hex(codepoint_arr);

        //not the character we want, so scan till next line
        if (codepoint < c)
        {
            while ((ch = fgetc(f)) != EOF && ch != '\n');
            if (ch == EOF) { break; }
            continue;
        }
        else if (codepoint > c) { break; } //indicates no entry for the given codepoint


        //scan through the second codepoint which indicates the uppercase for this codepoint
        i = 0;
        while ((ch = fgetc(f)) != EOF && ch != ':')
        {
            uppercase_arr[i++] = ch;
        }
        if (ch == EOF) { break; }
        uppercase_arr[i] = 0; //null terminator
        *uppercase = ustring_parse_hex(uppercase_arr);

        //scan through the third codepoint which indicates the lowercase for this codepoint
        i = 0;
        while ((ch = fgetc(f)) != EOF && ch != '\n')
        {
            uppercase_arr[i++] = ch;
        }
        // if (ch == EOF) { break; }
        uppercase_arr[i] = 0; //null terminator
        *lowercase = ustring_parse_hex(uppercase_arr);

        fclose(f);
        return true;
    }

    //default case is set both upper and lower to the input char
    *uppercase = c;
    *lowercase = c;
    fclose(f);
    return false;
}


#endif