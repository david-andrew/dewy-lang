
#include <stdio.h>
#include <stdlib.h>

#include "charset.h"
#include "utilities.h"
#include "metatoken.h"
#include "metascanner.h"
#include "metaparser.h"

//should whitespace be automatically filtered from token sequences
#define FILTER_WHITESPACE 1 //1 for true, 0 for false

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
    initialize_metascanner();
    initialize_metaparser();
    vect* tokens = new_vect();
    obj* t = NULL;

    while (*head != 0 && (t = scan(&head)) != NULL)
    {
        #if FILTER_WHITESPACE
            metatoken_type type = ((metatoken*)t->data)->type;
            if (type != whitespace && type != comment)
            {
                vect_push(tokens, t);
            }
            else
            {
                obj_free(t);
            }
        #else
            vect_push(tokens, t);
        #endif
    }

    while (parse_next_meta_rule(tokens));

    if (vect_size(tokens) > 0)
    {
        printf("unparsed tokens:\n");
        for (size_t i = 0; i < vect_size(tokens); i++)
        {
            t = vect_get(tokens, i);
            metatoken_str((metatoken*)t->data);
        }
    }

    vect_free(tokens);
    free(source);
    release_metascanner();
    release_metaparser();
}
