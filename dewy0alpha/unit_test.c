#include "stdio.h"
#include "string.h"
#include "assert.h"
#include "vect.c"
#include "dict.c"
#include "set.c"

#include "scanner.c" //so that obj.c has access to EBNF_string().
//TODO->make it so this isn't necessary? consider making a third file with common stuff?

//TODO->set up alias to run this with valgrind?

//forward declare methods for each collection of tests
int vect_tests();
int dict_tests();
int set_tests();

int main(int argc, char* argv[])
{
    bool test_sets = false, 
        test_dicts = false, 
        test_vects = false;

    for (int i = 0; i < argc; i++)
    {
        if (strcmp(argv[i], "-s") == 0 ) test_sets = true;
        if (strcmp(argv[i], "-d") == 0 ) test_dicts = true;
        if (strcmp(argv[i], "-v") == 0 ) test_vects = true;
    }

    printf("Beginning test suit...\n\n");
    if (test_vects) vect_tests();
    if (test_dicts) dict_tests();
    if (test_sets) set_tests();
    printf("Completed test suit.\n");
    
}

int vect_tests()
{
    printf("Running vect tests...\n");
    vect* v0 = new_vect();
    printf("Done\n\n");
    return 0;
}

int dict_tests()
{
    printf("Running dict tests...\n");
    dict* d0 = new_dict();
    printf("Done\n\n");
    return 0;
}

int set_tests()
{
    printf("Running set tests...\n");
    set* s0 = new_set();
    printf("Done\n");
    return 0;
}