#include <stdio.h>
#include <string.h>
#include <assert.h>

#include "vector.c"
#include "dictionary.c"
#include "set.c"
#include "token.c"
#include "mast.c"

//TODO->set up alias to run this with valgrind?

//forward declare methods for each collection of tests
int vect_tests();
int dict_tests();
int set_tests();
int misc_tests();

int main(int argc, char* argv[])
{
    bool test_sets = false, 
        test_dicts = false, 
        test_vects = false,
        test_misc = false;

    for (int i = 0; i < argc; i++)
    {
        if (strcmp(argv[i], "-s") == 0 ) test_sets = true;
        if (strcmp(argv[i], "-d") == 0 ) test_dicts = true;
        if (strcmp(argv[i], "-v") == 0 ) test_vects = true;
        if (strcmp(argv[i], "-m") == 0 ) test_misc = true;
    }

    //if none indicated, test everything
    if (!(test_vects || test_dicts || test_sets))
    {
        test_vects = true;
        test_dicts = true;
        test_sets = true;
        test_misc = true;
    }

    printf("Beginning test suit...\n\n");
    if (test_vects)
    {
        printf("Running vect tests...\n");
        vect_tests();
        printf("Done\n\n");

    }
    if (test_dicts)
    {
        printf("Running dict tests...\n");
        dict_tests();
        printf("Done\n\n");

    }
    if (test_sets)
    {
        printf("Running set tests...\n");
        set_tests();
        printf("Done\n\n");

    }
    if (test_misc)
    {
        printf("Running misc. tests...\n");
        misc_tests();
        printf("Done\n\n");
    }
    printf("Completed test suit.\n");
}



int vect_tests()
{
    vect* v0 = new_vect();
    return 0;
}

int dict_tests()
{
    dict* d0 = new_dict();
    return 0;
}

int set_tests()
{    
    set* S0 = new_set();

    set_add(S0, new_uint(5));
    set_add(S0, new_uint(4738));
    set_add(S0, new_uint(10));
    set_add(S0, new_uint(13));

    obj* i0 = new_uint(5);
    obj* i1 = new_uint(4738);
    obj* i2 = new_uint(10);
    obj* i3 = new_uint(13);
    obj* i4 = new_uint(42);

    //check that all members added are in the set
    assert(set_contains(S0, i0));
    assert(set_contains(S0, i1));
    assert(set_contains(S0, i2));
    assert(set_contains(S0, i3));
    assert(!set_contains(S0, i4));

    set* S1 = new_set();
    set_add(S1, new_uint(10));
    set_add(S1, new_uint(13));
    set_add(S1, new_uint(42));
    set_add(S1, new_uint(546876));
    obj* i5 = new_uint(546876);

    //check new set contains correct values
    assert(!set_contains(S1, i0));
    assert(!set_contains(S1, i1));
    assert(set_contains(S1, i2));
    assert(set_contains(S1, i3));
    assert(set_contains(S1, i4));
    assert(set_contains(S1, i5));

    //S0 should be different from S1
    assert(!set_equals(S0, S1));

    //create intersect and union objects
    set* S2 = set_intersect(S0, S1);
    set* S3 = set_union(S0, S1);

    //check the values from the intersect
    assert(!set_contains(S2, i0));
    assert(!set_contains(S2, i1));
    assert(set_contains(S2, i2));
    assert(set_contains(S2, i3));
    assert(!set_contains(S2, i4));
    assert(!set_contains(S2, i5));

    //check the values from the union
    assert(set_contains(S3, i0));
    assert(set_contains(S3, i1));
    assert(set_contains(S3, i2));
    assert(set_contains(S3, i3));
    assert(set_contains(S3, i4));
    assert(set_contains(S3, i5));

    //create a set identical to S0, and check equality
    set* S4 = new_set();
    set_add(S4, i0);
    set_add(S4, i1);
    set_add(S4, i2);
    set_add(S4, i3);

    assert(set_equals(S0, S4));

    //try adding a value again
    set_add(S4, i2);
    assert(set_contains(S4, i2));

    //print out all the sets we made
    set_str(S0); printf("\n");
    set_str(S1); printf("\n");
    set_str(S2); printf("\n");
    set_str(S3); printf("\n");
    set_str(S4); printf("\n");

    set* S5 = new_set(); //empty set

    printf("Testing set hash:\n");
    printf("hash("); set_str(S0); printf(") = %lu\n", set_hash(S0));
    printf("hash("); set_str(S1); printf(") = %lu\n", set_hash(S1));
    printf("hash("); set_str(S2); printf(") = %lu\n", set_hash(S2));
    printf("hash("); set_str(S3); printf(") = %lu\n", set_hash(S3));
    printf("hash("); set_str(S4); printf(") = %lu\n", set_hash(S4));
    printf("hash("); set_str(S5); printf(") = %lu\n", set_hash(S5));



    //TODO->free all variables
    //may need to modify dict delete to check if key and value are the same pointer

    return 0;
}

int misc_tests()
{
    //check fnv1a zero hash. zero hash comes from http://www.isthe.com/chongo/tech/comp/fnv/
    printf("fnv1a hash tests:\n");
    uint64_t zero_hash = 15378589119836260406lu;
    printf("  fnv1a(%lu) = %lu\n", zero_hash, hash_uint(zero_hash));
    printf("  fnv1a(true) = %lu\n", hash_bool(true));
    printf("  fnv1a(false) = %lu\n", hash_bool(false));
    printf("  fnv1a(42) = %lu\n", hash_uint(42));

    printf("\nunicode print test\n  ");
    put_unicode(0x24);  //$
    printf(", ");
    
    put_unicode(0xA2);  //¢
    printf(", ");

    put_unicode(0x0939);  //ह
    printf(", ");

    put_unicode(0x20AC);  //€
    printf(", ");

    put_unicode(0xD55C);  //한
    printf(", ");

    put_unicode(0x10348);  //𐍈
    printf("\n");

    //Other tests

    printf("\n");

    return 0;
}