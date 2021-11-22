/*
// clean C fizzbuzz implementation

#include <assert.h>
#include <stdbool.h>
#include <stdio.h>

int main()
{
    int taps[] = {3, 5 /*, 7, 11* /};
    char* strings[] = {"Fizz", "Buzz" /*, "Bazz", "Bar"* /};
    assert(sizeof(taps) / sizeof(int) == sizeof(strings) / sizeof(char*));

    for (int i = 0; i < 100; i++)
    {
        bool printed_words = false;
        for (int j = 0; j < sizeof(taps) / sizeof(int); j++)
        {
            if (i % taps[j] == 0)
            {
                printf("%s", strings[j]);
                printed_words = true;
            }
        }
        if (!printed_words) { printf("%d", i); }
        printf("\n");
    }
    return 0;
}
*/