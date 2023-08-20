#ifndef UTILITIES_H
#define UTILITIES_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// mostly string functions
int clamp(int x, int min, int max);
size_t dewy_index(int index, int length);
char* substr(char* str, int start, int stop);
char* clone(char* string);
char* concatenate(char* left, char* right);
size_t read_file(char* filename, char** destination);
size_t read_unicode_file(char* filename, uint32_t** destination);
void repeat_str(char* str, size_t times);

bool is_system_little_endian();

// hash functions
uint64_t djb2(char* str);
uint64_t djb2a(char* str);
uint64_t fnv1a(char* str);
uint64_t hash_uint(uint64_t val);
uint64_t hash_int(int64_t val);
uint64_t hash_uint_sequence(uint64_t* seq, size_t n);
uint64_t hash_uint_lambda_sequence(void* seq, size_t n, uint64_t (*getval)(void*, size_t));
uint64_t hash_bool(bool val);

// rng functions
uint64_t lfsr64_next(uint64_t curr);
uint64_t lfsr64_prev(uint64_t curr);

#endif