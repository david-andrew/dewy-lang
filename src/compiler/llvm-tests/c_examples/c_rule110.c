#include <stdlib.h>

int main()
{
    void* p = malloc(10);
    free(p);
}