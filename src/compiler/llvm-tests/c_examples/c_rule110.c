#include <stdint.h>
#include <stdlib.h>

// uint8_t* arr;

int main()
{
    // arr = malloc(8);
    int8_t arr[5];

    uint8_t a = arr[2];
    a = a | 0x01 << 3;
    arr[2] = a;

    // free(arr);
}