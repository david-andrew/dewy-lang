#ifndef UTILITIES_H
#define UTILITIES_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#define AUGMENT_CHAR 0x200000 //first invalid codepoint (2^21)

//mostly string functions
int clamp(int x, int min, int max);
size_t dewy_index(int index, int length);
char* substr(char* str, int start, int stop);
uint32_t* unicode_substr(char* str, int start, int stop);
uint32_t* utf8_substr(char* str, int start, int stop);
char* clone(char* string);
size_t unicode_strlen(uint32_t* string);
int64_t unicode_strcmp(uint32_t* left, uint32_t* right);
uint32_t* clone_unicode(uint32_t* string);
char* concatenate(char* left, char* right);
char* read_file(char* filename);

//parsing helper functions
bool is_identifier_char(char c);
bool is_identifier_symbol_char(char c);
bool is_alpha_char(char c);
bool is_dec_digit(char c);
bool is_alphanum_char(char c);
bool is_upper_hex_letter(char c);
bool is_lower_hex_letter(char c);
bool is_hex_digit(char c);
bool is_hex_escape(char c);
bool is_whitespace_char(char c);
bool is_charset_char(uint32_t c);

//hash functions
uint64_t djb2(char* str);
uint64_t djb2a(char* str);
uint64_t fnv1a(char* str);
uint64_t unicode_fnv1a(uint32_t* str);
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
uint32_t peek_unicode(char** str_ptr, size_t index, size_t* delta);
size_t utf8_length(char* str);
uint32_t* unicode_char_to_str(uint32_t c);
void unicode_char_str(uint32_t c);
void ascii_or_hex_str(uint32_t c);
void unicode_string_str(uint32_t* s);

#endif