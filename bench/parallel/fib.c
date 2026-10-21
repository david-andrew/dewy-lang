#include "../harness.h"
#include <omp.h>
static int64_t fib(int64_t n) {return n<2?n:fib(n-1)+fib(n-2);}
static int64_t fork_fib(int64_t n) {
    /* OpenMP's task if-clause still allocates undeferred tasks: use the same
       serial leaf optimization a heartbeat runtime should supply itself. */
    if(n<20) return fib(n);
    int64_t a,b;
#pragma omp task shared(a) firstprivate(n)
    a=fork_fib(n-1);
    b=fork_fib(n-2);
#pragma omp taskwait
    return a+b;
}
int main(int argc,char **argv){int64_t n=size_argument(argc,argv,32),r=0,t=clock_now();
    if(argc>2)r=fib(n);else{
#pragma omp parallel
#pragma omp single
        r=fork_fib(n);
    }report(r,clock_now()-t);
}
