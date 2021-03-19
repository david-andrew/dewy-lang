#ifndef UTILITIES_H
#define UTILITIES_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

//mostly string functions
int clamp(int x, int min, int max);
size_t dewy_index(int index, int length);
char* substr(char* str, int start, int stop);
char* clone(char* string);
char* concatenate(char* left, char* right);
char* read_file(char* filename);

void repeat_str(char* str, size_t times);

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
uint64_t parse_hex(char* str);
uint64_t dec_digit_to_value(char c);
uint64_t hex_digit_to_value(char c);

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


#endif