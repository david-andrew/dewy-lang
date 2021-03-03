#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#include "utilities.h"
#include "object.h"
#include "vector.h"
#include "dictionary.h"
#include "set.h"
#include "metatoken.h"
#include "charset.h"
#include "mast.h"
#include "metascanner.h"

//TODO->set up alias to run this with valgrind?


//macro to make it easy to run any test functions
#define test(ID, cmd) {                     \
    bool test_##ID = false;                 \
    if (argc < 2) test_##ID = true;         \
    for (int i = 0; i < argc; i++)          \
        if (strcmp(argv[i], #cmd) == 0)     \
            test_##ID = true;               \
    if (test_##ID) {                        \
        printf("Running "#ID" tests...\n"); \
        ID##_tests();                       \
        printf("Done\n\n");                 \
    }                                       \
}

//forward declare methods for each collection of tests
int vect_tests();
int dict_tests();
int set_tests();
int misc_tests();
int charset_tests();
int metascanner_tests();

int main(int argc, char* argv[])
{
    printf("Beginning test suit...\n\n");
    test(vect, -v)
    test(dict, -d)
    test(set, -s)
    test(misc, --misc)
    test(charset, -c)
    test(metascanner, -m)
    printf("Completed test suit.\n");

    return 0;
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
    #define I(v) new_int(v)

    set* S0 = new_set();

    set_add(S0, I(5));
    set_add(S0, I(4738));
    set_add(S0, I(10));
    set_add(S0, I(13));

    //check that all members added are in the set
    #define assert_contains(S, v, r) {      \
        obj* i = I(v);                      \
        assert(set_contains(S, i) == r);    \
        obj_free(i);                        \
    }

    assert_contains(S0, 5, true)
    assert_contains(S0, 4738, true)
    assert_contains(S0, 10, true)
    assert_contains(S0, 13, true)
    assert_contains(S0, 42, false)

    set* S1 = new_set();
    set_add(S1, I(10));
    set_add(S1, I(13));
    set_add(S1, I(42));
    set_add(S1, I(546876));

    //check new set contains correct values
    assert_contains(S1, 5, false)
    assert_contains(S1, 4738, false)
    assert_contains(S1, 10, true)
    assert_contains(S1, 13, true)
    assert_contains(S1, 42, true)
    assert_contains(S1, 546876, true)

    //S0 should be different from S1
    assert(!set_equals(S0, S1));

    //create intersect and union objects
    set* S2 = set_intersect(S0, S1);
    set* S3 = set_union(S0, S1);

    //check the values from the intersect
    assert_contains(S2, 5, false)
    assert_contains(S2, 4738, false)
    assert_contains(S2, 10, true)
    assert_contains(S2, 13, true)
    assert_contains(S2, 42, false)
    assert_contains(S2, 546876, false)

    //check the values from the union
    assert_contains(S3, 5, true)
    assert_contains(S3, 4738, true)
    assert_contains(S3, 10, true)
    assert_contains(S3, 13, true)
    assert_contains(S3, 42, true)
    assert_contains(S3, 546876, true)

    //create a set identical to S0, and check equality
    set* S4 = new_set();
    set_add(S4, I(10));
    set_add(S4, I(5));
    set_add(S4, I(13));
    set_add(S4, I(4738));

    assert(set_equals(S0, S4));

    //try adding a value again
    obj* i10 = I(10);
    set_add(S4, i10);
    assert_contains(S4, 10, true);
    // obj_free(i10); //free the object that wasn't added
    //TODO->can't free i10 b/c it gets inserted, and the original is removed...

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

    //free all the sets + objects they contain
    set_free(S0);
    set_free(S1);
    set_free(S2);
    set_free(S3);
    set_free(S4);
    set_free(S5);

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


int metascanner_tests()
{
    //load the source file into a string, and keep a copy of the head of the file
    char* source = read_file("../../tests/test_syntax.dewy");
    char* head = source;

    //set up structures for the sequence of scanning/parsing
    // vect* tokens = new_vect();

    obj* t;

    while (*head != 0 && (t = scan(&head)) != NULL)
    {
        metatoken_str((metatoken*)t->data);
        obj_free(t);
    }

    free(source);
    free_metascanner_state_stack();

    return 0;
}

int charset_tests()
{
    charset* s0 = new_charset();
    charset_add_range(s0, (urange){'5', '7'});
    charset_add_range(s0, (urange){'0', '9'});
    charset_add_range(s0, (urange){'A', 'F'});
    charset_add_range(s0, (urange){'a', 'f'});
    charset_add_range(s0, (urange){'g', 'i'});
    charset_add_range(s0, (urange){'a', 'f'});
    charset_add_range(s0, (urange){'g', 'g'});
    charset_add_range(s0, (urange){'i', 'k'});
    charset_add_range(s0, (urange){'l', 'p'});
    
    charset_add_range(s0, (urange){'n', 's'});
    charset_add_range(s0, (urange){'v', 'v'});
    charset_add_range(s0, (urange){'u', 'w'});

    charset_add_range(s0, (urange){'w', 'w'});
    charset_add_range(s0, (urange){'y', 'y'});
    charset_add_range(s0, (urange){'y', 'y'});
    charset_add_range(s0, (urange){'z', 'z'});
    charset_add_range(s0, (urange){'H', 'H'});
    charset_add_range(s0, (urange){'J', 'J'});
    charset_add_range(s0, (urange){'L', 'L'});
    charset_add_range(s0, (urange){'N', 'N'});
    
    charset_add_range(s0, (urange){'P', 'S'});
    charset_add_range(s0, (urange){'P', 'S'});
    charset_add_range(s0, (urange){'P', 'S'});
    charset_add_range(s0, (urange){'U', 'W'});
    printf("\n\nstr s0:\n");
    charset_str(s0);

    charset* s0_compliment = charset_compliment(s0);
    printf("\n\nstr s0_compliment:\n");
    charset_str(s0_compliment);

    charset* s0_compliment_compliment = charset_compliment(s0_compliment);
    printf("\n\nstr s0_compliment_compliment:\n");
    charset_str(s0_compliment_compliment);

    bool ceq0 = charset_equals(s0, s0_compliment_compliment);
    bool ceq1 = charset_equals(s0, s0_compliment);
    printf("\n\ns0 =? s0_compliment = %s\n", ceq1 ? "true" : "false");
    printf("\ns0 =? s0_compliment_compliment = %s\n", ceq0 ? "true" : "false");

    charset* onion = charset_union(s0, s0_compliment);
    printf("\n\nstr s0 U s0_compliment:\n");
    charset_str(onion);

    charset* s1 = new_charset();
    charset_add_range(s1, (urange){'0', '9'});
    charset_add_range(s1, (urange){'A', 'Z'});
    charset_add_range(s1, (urange){'a', 'z'});
    charset_add_range(s1, (urange){0x1f600, 0x1f650});
    charset_add_range(s1, (urange){0x1F596, 0x1F596});
    printf("\n\nstr s1:\n");
    charset_str(s1);

    charset* s2 = new_charset();
    charset_add_range(s2, (urange){'A', 'F'});
    charset_add_range(s2, (urange){'a', 'f'});
    printf("\n\nstr s2:\n");
    charset_str(s2);

    charset* s3 = new_charset();
    charset_add_range(s3, (urange){'g', 'g'});
    charset_add_range(s3, (urange){')', '('});
    printf("\n\nstr s3:\n");
    charset_str(s3);

    charset* s0_s1 = charset_union(s0, s1);
    printf("\n\nstr s0 U s1:\n");
    charset_str(s0_s1);

    charset* s2_s3 = charset_union(s2, s3);
    printf("\n\nstr s2 U s3:\n");
    charset_str(s2_s3);


    charset* d_s0_s1 = charset_diff(s0, s1);
    printf("\n\nstr s0 - s1:\n");
    charset_str(d_s0_s1);
    
    charset* d_s1_s0 = charset_diff(s1, s0);
    printf("\n\nstr s1 - s0:\n");
    charset_str(d_s1_s0);

    charset* i_s0_s1 = charset_intersect(s0, s1);
    printf("\n\nstr s0 & s1:\n");
    charset_str(i_s0_s1);

    printf("\n");

    charset_free(s0_compliment_compliment);
    charset_free(s0);
    charset_free(s0_compliment);
    charset_free(onion);
    charset_free(s1);
    charset_free(s2);
    charset_free(s0_s1);
    charset_free(s3);
    charset_free(s2_s3);
    charset_free(d_s0_s1);
    charset_free(d_s1_s0);
    charset_free(i_s0_s1);

    return 0;
}


