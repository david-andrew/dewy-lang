#include "../harness.h"
#include <omp.h>
int main(int argc,char **argv){int64_t n=size_argument(argc,argv,1024);double *a=malloc(n*n*8),*b=malloc(n*n*8);for(int64_t i=0;i<n;i++)for(int64_t j=0;j<n;j++)a[i*n+j]=(i+j)%17;int64_t t=clock_now();
for(int step=0;step<20;step++){
#pragma omp parallel for if(argc<=2) schedule(dynamic,1)
for(int64_t i=0;i<n;i++)for(int64_t j=0;j<n;j++)b[i*n+j]=(i==0||i==n-1||j==0||j==n-1)?a[i*n+j]:(a[(i-1)*n+j]+a[(i+1)*n+j]+a[i*n+j-1]+a[i*n+j+1])*0.25;
double *p=a;a=b;b=p;}
int64_t elapsed=clock_now()-t,r=0;for(int64_t i=0;i<n*n;i++)r+=(int64_t)(a[i]*1024);report(r,elapsed);free(a);free(b);}
