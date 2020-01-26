//Dewy Compiler Compiler written in C. Should compile to dcc

//This is an attempt to begin implementing the compiler compiler for Dewy in C
//Initially this program is tasked with scanning the grammar specified, and creating a list of rules for said grammars
//The scanning sequence is to scan for all macro rules first, and then scan for hardcoded rules

#include <stdio.h>
#include <stdlib.h>
// #include <stdint.h>
#include <string.h>
#include <limits.h>

#include "utilities.c"
#include "scanner.c"
#include "parser.c"
#include "object.c"
#include "dictionary.c"
#include "vector.c"


#define START 0     //start of an array
#define END INT_MAX //end of an array (when sanitized via dewy_index() or as a substring)


//string manipulation functions;
//strcpy(s1,s2); Copies string s2 into string s1.
//strcat(s1,s2); Concatenates string s2 onto the end of string s1.
//strlen(s1); Returns the length of string s1.
//strcmp(s1, s2); Returns 0 if s1 and s2 are the same; less than 0 if s1<s2; greater than 0 if s1>s2.
//strchr(s1, ch); Returns a pointer to the first occurrence of character ch in string s1.
//strstr(s1, s2); Returns a pointer to the first occurrence of string s2 in string s1.



//for rule in macro_rules:
//  attempt to match
//for rule in hard_rules:
//  attempt to match


int main(int argc, char* argv[])
{
    //print error if no file specified for parsing
    if (argc < 2) 
    {
        printf("Error: you must specify a file to read\n");
        return 1;
    }

    //load the source file into a string, and keep a copy of the head of the file
    char* source = read_file(argv[1]);
    char* head = source;

    //set up structures for the sequence of scanning/parsing
    vect* tokens = new_vect();
    //probably todo, make a context variable that holds symbol table + rules being lexed + other stuff
    dict* meta_symbols = new_dict();

    while (*source) //while we haven't reached the null terminator
    {
        //scan the source for the next token
        obj* token = scan(&source);

        //if no tokens were able to be read, exit the loop
        if (token == NULL) break;
        
        //save the token that was scanned
        vect_append(tokens, token);

        //if parsable sequence exists in current tokens vector
        update_meta_symbols(meta_symbols, tokens);

    }

    if (!*source) printf("successfully scanned source text\n");

    remove_token_type(tokens, whitespace);
    remove_token_type(tokens, comment);
    // remove_whitespace(tokens);
    // remove_comments(tokens);
    vect_str(tokens);
    // vect_free(tokens);
    // dict_free(symbols);

    free(head);
}