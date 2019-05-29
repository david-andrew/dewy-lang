//helper functions for managing strings and so forth in compiler compiler

#ifndef UTILITIES_C
#define UTILITIES_C

#include <string.h>

/**
    return a substring according to python string slicing rules
*/
char* substr(char* string, int start, int stop)
{
    size_t length = strlen(string);
    size_t start_idx = start, stop_idx = stop;
    
    //set up substring indices
    //TODO->handle case when start/stop are longer than length
    if (start < 0) start_idx = length - start;  //python end-relative indexing
    if (stop < 0) stop_idx = length - stop;     //python end-relative indexing
    if (start_idx > length) start_idx = length; //out of bounds copies up to length of string
    if (stop_idx > length) stop_idx = length;   //out of bounds copies up to length of string

    //compute length of substring
    size_t substr_length = stop_idx - start_idx;
    
    //if no substring length, return empty string
    if (substr_length == 0)
    {
        return "";
    }

    //otherwise perform copy
    char* substr = malloc((substr_length + 1) * sizeof(char));
    for (size_t i = start_idx; i < stop_idx; i++)
    {
        *substr++ = string[i];
    }
    *substr = 0; //add null terminator to end of string

    return substr;
}


#endif
