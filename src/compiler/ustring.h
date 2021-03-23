#ifndef USTRING_H
#define USTRING_H

#include <stddef.h>
#include <stdint.h>

#include "object.h"


obj* new_ustring_obj(uint32_t* s);
uint32_t* ustring_charstar_substr(char* str, int start, int stop);
uint32_t* ustring_utf8_substr(char* str, int start, int stop);
size_t ustring_len(uint32_t* string);
int64_t ustring_cmp(uint32_t* left, uint32_t* right);
uint32_t* ustring_clone(uint32_t* string);
uint64_t ustring_hash(uint32_t* str);
uint64_t dec_digit_to_value(char c);
uint64_t hex_digit_to_value(char c);
uint64_t ustring_parse_hex(uint32_t* str);
uint64_t ustring_parse_dec(uint32_t* str);
uint64_t ustring_parse_base(uint32_t* str, uint64_t base, uint64_t (*base_digit_to_value)(char));
bool is_printable_unicode(uint32_t c);
void put_unicode(uint32_t c);
uint32_t eat_utf8(char** str_ptr);
uint32_t peek_unicode(char** str_ptr, size_t index, size_t* delta);
size_t utf8_length(char* str);
uint32_t* ustring_from_unicode(uint32_t c);
void printable_unicode_or_hex_str(uint32_t c);
void unicode_ascii_or_hex_str(uint32_t c);
void unicode_str(uint32_t c);
void ustring_str(uint32_t* s);
uint32_t escape_to_unicode(uint32_t c);


#endif