#ifndef UTILITIES_H
#define UTILITIES_H

#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>

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
uint64_t hash_bool(bool val);

uint64_t lfsr64_next(uint64_t curr);
uint64_t lfsr64_prev(uint64_t curr);

void put_unicode(uint32_t c);

#endif