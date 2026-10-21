#include "../harness.h"
#include <omp.h>
static void sort(int64_t *a,int64_t *tmp,int64_t lo,int64_t hi,int threaded){if(hi-lo<=1)return;int64_t mid=lo+(hi-lo)/2;
if(threaded&&hi-lo>=2048){
#pragma omp task shared(a,tmp) firstprivate(lo,mid)
 sort(a,tmp,lo,mid,1);
 sort(a,tmp,mid,hi,1);
#pragma omp taskwait
}else{sort(a,tmp,lo,mid,0);sort(a,tmp,mid,hi,0);}
int64_t i=lo,j=mid,k=lo;while(i<mid&&j<hi)tmp[k++]=a[i]<=a[j]?a[i++]:a[j++];while(i<mid)tmp[k++]=a[i++];while(j<hi)tmp[k++]=a[j++];for(k=lo;k<hi;k++)a[k]=tmp[k];}
int main(int argc,char **argv){int64_t n=size_argument(argc,argv,262144),*a=malloc(n*8),*tmp=malloc(n*8);for(int64_t i=0;i<n;i++)a[i]=(i*1103515245+12345)%2147483648;int64_t t=clock_now();
if(argc>2)sort(a,tmp,0,n,0);else{
#pragma omp parallel
#pragma omp single
sort(a,tmp,0,n,1);
}int64_t elapsed=clock_now()-t,r=0;for(int64_t i=0;i<n;i++)r=(r+a[i]*(i%97))%1000000007;report(r,elapsed);free(a);free(tmp);}
