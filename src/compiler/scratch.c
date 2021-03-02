
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

int test_charset()
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