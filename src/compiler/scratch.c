
#include <stdio.h>
#include <stdlib.h>

#include "charset.h"
#include "utilities.h"
#include "metatoken.h"
#include "metascanner.h"

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
    // vect* tokens = new_vect();

    obj* t = NULL;

    while (*head != 0 && (t = scan(&head)) != NULL)
    {
        metatoken_str((metatoken*)t->data);
        obj_free(t);
    }

    free(source);
    free_metascanner_state_stack();
}
