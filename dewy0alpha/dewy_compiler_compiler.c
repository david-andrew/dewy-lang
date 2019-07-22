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
#include "compile_tools.c"
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
    /*
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



    //testing vector
    vector* test = new_vector(sizeof(int));
    printf("size of vector is %zu\n", test->length);
    vector_print_int(test);

    for (int i = 0; i < 100; i++)
    {
        vector_append(test, itemize_int(i));
    }
    printf("size of vector is %zu\n", test->length);
    vector_print_int(test);

    vector_clear(test);
    printf("size of vector is %zu\n", test->length);
    vector_print_int(test);
    for (int i = 9; i >= 0; i--)
    {
        vector_append(test, itemize_int(i));
    }
    printf("size of vector is %zu\n", test->length);
    vector_print_int(test);

    Object* I = Integer(12);
    I->type=10;
    */

    // printf("Integer [type %d, size %zu, value %i]\n", I->type, I->size, *((int*)(I->data)));
    // print(I);
    // printf("\nsizeof(int) = %zu\n", sizeof(int));
    // printf("sizeof(unsigned long) = %zu\n", sizeof(unsigned long));
    // printf("sizeof(uint_fast32_t) = %zu\n", sizeof(uint_fast32_t));
    // char* str = "apple";
    // printf("hash of \"%s\" is %lu\n", str, djb2(str));
    // printf("xor hash of \"%s\" is %lu\n", str, djb2a(str));
    // printf("fnv hash of \"%s\" is %lu\n", str, fnv1a(str));


    // char* strings[] = {"apple", "banana", "peach", "pineapple", "pear", "\0"};
    // for (int i = 0; i < 6; i++) 
    // {
    //     // printf("djb2(%s) = %lu\n", strings[i], djb2(strings[i]));
    //     // printf("djb2a(%s) = %lu\n", strings[i], djb2a(strings[i]));
    //     printf("fnv1a(%s) = %lX\n", strings[i], fnv1a(strings[i]));


    // }

    // for (int64_t i = 0; i < 1000; i++)
    // {
    //     printf("fnv1a(%ld) = %lu\n", i, hash_int(i));
    // }

    printf("Dictionary Tests:\n");
    dict* d = new_dict();
    for (int i = -40; i < 40; i++)
    {
        dict_set(d, new_int(i), new_int(i));
    }
    // Object* apple = new_int(5);
    // // dict_insert(d, new_int(5), new_int(5));
    // dict_insert(d, new_int(5), new_int(8));    
    // printf("apple in dict? %s\n", dict_contains(d, apple) ? "true" : "false");
    // obj_print(apple);
    // printf("\n");
    dict_str(d);
    dict_reset(d);
    dict_free(d);

    printf("\nVector Tests:\n");
    vect* v = new_vect();
    for (int i = 0; i < 8; i++)
    {
        vect_append(v, new_int(i));
    }
    for (int i = 8; i < 16; i++)
    {
        vect_prepend(v, new_int(i));
    }
    vect_insert(v, new_int(-7), 8);
    vect_str(v);
}