//This is an attempt to begin implementing the compiler compiler for Dewy in C
//Initially this program is tasked with scanning the grammar specified, and creating a list of rules for said grammars
//The scanning sequence is to scan for all macro rules first, and then scan for hardcoded rules

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "utilities.c"

#include <limits.h>
#define START 0     //start of an array
#define END INT_MAX //end of an array (when sanitized via dewy_index() or as a substring)


//string manipulation functions;
//strcpy(s1,s2); Copies string s2 into string s1.
//strcat(s1,s2); Concatenates string s2 onto the end of string s1.
//strlen(s1); Returns the length of string s1.
//strcmp(s1, s2); Returns 0 if s1 and s2 are the same; less than 0 if s1<s2; greater than 0 if s1>s2.
//strchr(s1, ch); Returns a pointer to the first occurrence of character ch in string s1.
//strstr(s1, s2); Returns a pointer to the first occurrence of string s2 in string s1.

enum EBNF_state
{
    first_quote,
    second_quote,
    group,
    option,
    repeat,
    special,
};


//possible token types
enum EBNF_token_types
{
    EBNF_identifier,
    single_quote_string,
    double_quote_string,
    comma,
    semicolon,
    vertical_bar,
    minus,
    equals_sign,
    parenthesis,
    bracket,
    brace,
    whitespace,
};

//individual tokens that appear in an EBNF rule
struct EBNF_token
{
    enum EBNF_token_types type;
    char* content;
};

//for rule in macro_rules:
//  attempt to match
//for rule in hard_rules:
//  attempt to match



char* remove_comments(char* source)
{    
    printf("Removing comments from source string...\n");

    size_t length = strlen(source);
    char* head = source;
    char* processed = malloc(length * sizeof(char));     //potentially entire space used
    size_t copied = 0;
    
    do
    {
        //check if start of line comment, and if so skip to end of line
        if (source - head + 1 < length && *source == '/' && *(source + 1) ==  '/')
        {
            while(*++source != '\n' && *source != 0); //scan until the line break (or end of string)
            source--;   //don't eat the newline
            continue;
        }

        // //check if start of block comment, and if so, skip to end of block (keeping track of internal block comments)
        // if (source - head + 1 < length && *cource == '/' && *(source + 1) == '{')
        // {
        //     int stack = 1;  //monitor internal opening and closing blocks.
        //     while (stack != 0)
        //     {

        //     }
        // }

        // putchar(*source);
        // printf("%d ", *source);
        processed[copied++] = *source; //copy the current character
    }
    while (*source++);

    // while(*processed++) putchar(*processed);
    processed[copied] = 0; //add final null-terminator to copied string
    return processed;
}

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
    source = remove_comments(source);
    // source = remove_whitespace(source);
    printf("Contents of source file:\n%s\n",source);
    printf("length of string: %lu\n", strlen(source));
    // printf("Substring test: %s\n", substr(source, START, END));

}