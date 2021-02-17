#ifndef UTILITIES_H
#define UTILITIES_H

#include "types.h"

#define AUGMENT_CHAR 0x200000 //first invalid codepoint (2^21)

//mostly string functions
int clamp(int x, int min, int max);
size_t dewy_index(int index, int length);
char* substr(char* string, int start, int stop);
char* clone(char* string);
char* concatenate(char* left, char* right);
char* read_file(char* filename);

//parsing helper functions
bool is_identifier_char(char c);
bool is_identifier_symbol_char(char c);
bool is_alpha_char(char c);
bool is_num_char(char c);
bool is_alphanum_char(char c);
bool is_upper_hex_letter(char c);
bool is_lower_hex_letter(char c);
bool is_hex_digit(char c);
bool is_whitespace_char(char c);

//hash functions
uint64_t djb2(char* str);
uint64_t djb2a(char* str);
uint64_t fnv1a(char* str);
uint64_t hash_uint(uint64_t val);
uint64_t hash_int(int64_t val);
uint64_t hash_bool(bool val);

//rng functions
uint64_t lfsr64_next(uint64_t curr);
uint64_t lfsr64_prev(uint64_t curr);

//scanning/printing functions
uint64_t parse_hex(char* str);
uint64_t hex_digit_to_value(char c);
void put_unicode(uint32_t c);
uint32_t eat_utf8(char** str_ptr);
void unicode_str(uint32_t c);


#endif