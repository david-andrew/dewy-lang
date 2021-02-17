#ifndef TOKEN_H
#define TOKEN_H

#include "types.h"

obj* new_token(token_type type, char* content); //TODO->replace with below versions
//token* new_token(token_type, char* content)
//obj* new_token_obj(token* t);
void token_str(token* t);
void token_free(token* t);

#endif