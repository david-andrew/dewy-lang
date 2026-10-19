#include "harness.h"

static int64_t dispatch(int64_t code, int64_t value) {
    switch (code) {
        case 0: return value+3;
        case 1: return value^10;
        case 2: return value*17;
        case 3: return (value>>1)+24;
        case 4: return value+31;
        case 5: return value^38;
        case 6: return value*45;
        case 7: return (value>>2)+52;
        case 8: return value+59;
        case 9: return value^66;
        case 10: return value*73;
        case 11: return (value>>3)+80;
        case 12: return value+87;
        case 13: return value^94;
        case 14: return value*101;
        case 15: return (value>>1)+108;
        case 16: return value+115;
        case 17: return value^122;
        case 18: return value*129;
        case 19: return (value>>2)+136;
        case 20: return value+143;
        case 21: return value^150;
        case 22: return value*157;
        case 23: return (value>>3)+164;
        default: return value-17;
    }
}

static int64_t kernel(int64_t count) {
    int64_t state=305419896, checksum=0;
    for (int64_t i=0; i<count; i++) {
        state=(state*1664525+1013904223)&2147483647;
        checksum+=dispatch((state>>16)&31, state&65535);
    }
    return checksum;
}
int main(int argc,char **argv) {
    int64_t count=size_argument(argc,argv,10000000);
    int64_t started=clock_now();
    int64_t result=kernel(count);
    report(result,clock_now()-started);
    return 0;
}
