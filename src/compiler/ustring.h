#ifndef USTRING_H
#define USTRING_H

#include <stddef.h>
#include <stdint.h>


uint32_t* unicode_substr(char* str, int start, int stop);
uint32_t* utf8_substr(char* str, int start, int stop);
size_t unicode_strlen(uint32_t* string);
int64_t unicode_strcmp(uint32_t* left, uint32_t* right);
uint32_t* clone_unicode(uint32_t* string);
uint64_t parse_unicode_hex(uint32_t* str);
uint64_t parse_unicode_dec(uint32_t* str);
uint64_t parse_unicode_base(uint32_t* str, uint64_t base);
void put_unicode(uint32_t c);
uint32_t eat_utf8(char** str_ptr);
uint32_t peek_unicode(char** str_ptr, size_t index, size_t* delta);
size_t utf8_length(char* str);
uint32_t* unicode_char_to_str(uint32_t c);
void unicode_char_str(uint32_t c);
void ascii_or_hex_str(uint32_t c);
void unicode_string_str(uint32_t* s);
uint32_t escape_to_unicode(uint32_t c);


#endif