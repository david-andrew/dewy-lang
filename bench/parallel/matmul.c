#include "../harness.h"
#include <omp.h>
int main(int argc,char **argv){int64_t n=size_argument(argc,argv,1024),tiles=(n+31)/32,count=tiles*tiles;
double *a=malloc(n*n*8),*b=malloc(n*n*8),*out=calloc(count*1024,8);for(int64_t i=0;i<n*n;i++){a[i]=i%7;b[i]=i%5;}int64_t t=clock_now();
#pragma omp parallel for if(argc<=2) schedule(dynamic,1)
for(int64_t id=0;id<count;id++){int64_t row=id/tiles*32,col=id%tiles*32;double *o=out+id*1024;
for(int64_t kk=0;kk<tiles;kk++)for(int64_t i=0;i<32&&row+i<n;i++)for(int64_t k=kk*32;k<(kk+1)*32&&k<n;k++){double v=a[(row+i)*n+k];for(int64_t j=0;j<32&&col+j<n;j++)o[i*32+j]+=v*b[k*n+col+j];}}
int64_t elapsed=clock_now()-t,r=0;for(int64_t i=0;i<count*1024;i++)r+=(int64_t)out[i];report(r,elapsed);free(a);free(b);free(out);}
