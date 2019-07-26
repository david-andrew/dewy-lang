//Dewy Compiler Compiler written in C. Should compile to dcc

//This is an attempt to begin implementing the compiler compiler for Dewy in C
//Initially this program is tasked with scanning the grammar specified, and creating a list of rules for said grammars
//The scanning sequence is to scan for all macro rules first, and then scan for hardcoded rules

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <limits.h>

#include "utilities.c"
#include "scanner.c"
#include "obj.c"
#include "dict.c"
#include "vect.c"


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
    
    //test to see if we can read the command line args
    // for (int i = 0; i < argc; i++)
    // {
    //     printf("Argument %d is %s\n", i, argv[i]);
    // }

    //print error if no file specified for parsing
    if (argc < 2) 
    {
        printf("Error: you must specify a file to read\n");
        return 1;
    }

    char* source = read_file(argv[1]); //fopen(argv[1], "r");
    // source = remove_comments(source);
    // source = remove_whitespace(source);
    // printf("Contents of source file:\n%s\n",source);
    // printf("length of string: %lu\n", strlen(source));
    // printf("Substring test: %s\n", substr(source, START, END));


    char* head = source; //keep track of the head of the file

    vect* tokens = new_vect();

    while (*source) //while we haven't reached the null terminator
    {
        // printf("source on pass: %s\n", source);
        obj* token = scan(&source);
        if (token != NULL)
        {
            vect_append(tokens, token);
        }
        else
        {
            break;
        }
    }

    if (!*source) printf("successfully scanned source text\n");

    // vect_str(tokens);
    remove_whitespace(tokens);
    vect_str(tokens);
    // vect_free(tokens);

    free(head);
}