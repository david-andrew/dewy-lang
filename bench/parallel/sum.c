#include "../harness.h"
#include <omp.h>
int main(int argc,char **argv){int64_t n=size_argument(argc,argv,16777216),blocks=(n+4095)/4096;
int64_t *a=malloc(n*sizeof(*a)),*parts=malloc(blocks*sizeof(*parts));for(int64_t i=0;i<n;i++)a[i]=i%1024;
int64_t t=clock_now();
#pragma omp parallel for if(argc<=2) schedule(dynamic,1)
for(int64_t b=0;b<blocks;b++){int64_t s=0,end=(b+1)*4096;if(end>n)end=n;for(int64_t i=b*4096;i<end;i++)s+=a[i];parts[b]=s;}
int64_t r=0;for(int64_t b=0;b<blocks;b++)r+=parts[b];report(r,clock_now()-t);free(a);free(parts);}
