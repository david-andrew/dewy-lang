#include "../harness.h"
#include <stdatomic.h>
#include <omp.h>
int main(int argc,char **argv){int64_t n=size_argument(argc,argv,1000000);int stride=argc>2?16:1;
_Atomic int64_t *cells=calloc(4*stride,sizeof(*cells));int64_t t=clock_now();
#pragma omp parallel for schedule(static,1)
for(int i=0;i<4;i++)for(int64_t j=0;j<n;j++)atomic_fetch_add_explicit(cells+i*stride,1,memory_order_seq_cst);
int64_t sum=0;for(int i=0;i<4;i++)sum+=atomic_load(cells+i*stride);report(sum,clock_now()-t);free(cells);}
