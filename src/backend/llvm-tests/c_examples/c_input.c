#include "../metal.h"
#include <stdlib.h>

int main()
{
    __puts((uint8_t*)"What's your name? ");
    uint8_t* line;
    __getl(&line);
    __puts((uint8_t*)"Hello ");
    __puts(line);
    __puts((uint8_t*)"!\n");
    free(line);
}