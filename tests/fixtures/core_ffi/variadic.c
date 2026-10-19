#include <stdarg.h>
#include <stdint.h>
int64_t check_mix(float fixed, int64_t tag, ...) {
    va_list ap; va_start(ap, tag);
    double a=va_arg(ap,double), b=va_arg(ap,double);
    int c=va_arg(ap,int), d=va_arg(ap,int);
    va_end(ap);
    return fixed==2.5f && tag==7 && a==1.25 && b==3.75 && c==-7 && d==250 ? 42 : 1;
}
int64_t check_many(int64_t tag, ...) {
    va_list ap; va_start(ap,tag); double total=0;
    for(int i=0;i<10;i++) total+=va_arg(ap,double);
    va_end(ap); return tag==10 && total==55.0 ? 42 : 2;
}
int64_t check_empty(int64_t tag, ...) { return tag==42 ? 42 : 3; }
