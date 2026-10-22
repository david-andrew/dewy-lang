#include "../harness.h"
#include <stdatomic.h>
#include <omp.h>
int main(int argc,char **argv){int64_t n=size_argument(argc,argv,1000000);int64_t *values=malloc(n*sizeof(*values));
_Atomic int64_t bins[64]={0};for(int64_t i=0;i<n;i++)values[i]=(i*17)%64;int64_t t=clock_now();
#pragma omp parallel for schedule(static)
for(int64_t i=0;i<n;i++)atomic_fetch_add_explicit(bins+values[i],1,memory_order_seq_cst);
int64_t sum=0;for(int i=0;i<64;i++)sum+=atomic_load(bins+i)*(i+1);report(sum,clock_now()-t);free(values);}
