//This is an attempt to begin implementing the compiler compiler for Dewy in C
//Initially this program is tasked with scanning the grammar specified, and creating a list of rules for said grammars
//The scanning sequence is to scan for all macro rules first, and then scan for hardcoded rules

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

//for rule in macro_rules:
//  attempt to match
//for rule in hard_rules:
//  attempt to match


char* read_file(char* filename)
{
    //see: https://stackoverflow.com/questions/14002954/c-programming-how-to-read-the-whole-file-contents-into-a-buffer
    FILE *f = fopen(filename, "rb");
    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);  /* same as rewind(f); */

    char *string = malloc(fsize + 1);
    fread(string, fsize, 1, f);
    fclose(f);

    string[fsize] = 0;

    return string;
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
    printf("Contents of source file:\n%s\n",source);
    printf("length of string: %lu\n", strlen(source));

}