#define _GNU_SOURCE
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <fcntl.h>

static int64_t now(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (int64_t)t.tv_sec*1000000000 + t.tv_nsec;
}
typedef struct {
    _Atomic int canceled;
    _Atomic int64_t found, signaled;
    int64_t *values, n, deadline;
} Scope;
typedef struct { Scope *scope; int64_t first, last; const char *path; } Work;
static void *scan(void *arg) {
    Work *w=arg; Scope *s=w->scope;
    for (int64_t i=w->first;i<w->last;i++) {
        if (s->values[i]==s->n/4*17) {
            atomic_store(&s->found,i); atomic_store(&s->signaled,now());
            atomic_store(&s->canceled,1); break;
        }
        if (i%1024==0 && atomic_load(&s->canceled)) break;
    }
    return NULL;
}
static void *lookup(void *arg) {
    Work *w=arg; char text[8]={0};
    if (!atomic_load(&w->scope->canceled)) {
        int fd=open(w->path,O_RDONLY);
        if (fd>=0) { ssize_t n=read(fd,text,sizeof(text)); close(fd);
            if (n==5 && !memcmp(text,"found",5)) atomic_store(&w->scope->found,1);
        }
        atomic_store(&w->scope->canceled,1);
    }
    return NULL;
}
static void *idle(void *arg) {
    Scope *s=arg; int64_t end=now()+1000000;
    while (!atomic_load(&s->canceled) && now()<end) {
        struct timespec t={0,100000}; nanosleep(&t,NULL);
    }
    return NULL;
}
static int start_thread(pthread_t *thread, void *(*fn)(void *), void *arg) {
    int e=pthread_create(thread,NULL,fn,arg);
    if (e) {fprintf(stderr,"pthread_create: %s\n",strerror(e)); return 0;}
    return 1;
}
int main(int argc,char **argv) {
    if (argc<2) return 2;
    int64_t n=argc>2?atoll(argv[2]):10000;
    Scope s={.found=-1,.n=n}; int64_t start,elapsed,latency=0,checksum=n;
    if (!strcmp(argv[1],"find_first")) {
        s.values=malloc((size_t)n*sizeof(int64_t));
        for(int64_t i=0;i<n;i++) s.values[i]=i*17;
        Work work[2]={{&s,0,n/2,NULL},{&s,n/2,n,NULL}}; pthread_t threads[2];
        start=now();
        for(int i=0;i<2;i++) if(!start_thread(&threads[i],scan,&work[i])) return 2;
        for(int i=0;i<2;i++) pthread_join(threads[i],NULL);
        elapsed=now()-start; latency=now()-atomic_load(&s.signaled);
        checksum=atomic_load(&s.found); free(s.values);
        if(checksum!=n/4) return 3;
    } else if (!strcmp(argv[1],"race")) {
        const char *paths[]={"lookup-left.txt","lookup-right.txt"};
        for(int i=0;i<2;i++){int fd=open(paths[i],O_CREAT|O_TRUNC|O_WRONLY,0600); if(fd<0)return 2; if(write(fd,"found",5)!=5)return 2;close(fd);}
        Work work[2]={{.scope=&s,.path=paths[0]},{.scope=&s,.path=paths[1]}};
        start=now();
        for(int64_t j=0;j<n;j++) {
            atomic_store(&s.canceled,0);atomic_store(&s.found,0);pthread_t threads[2];
            for(int i=0;i<2;i++) if(!start_thread(&threads[i],lookup,&work[i])) return 2;
            for(int i=0;i<2;i++) pthread_join(threads[i],NULL);
            if(!atomic_load(&s.found))return 3;
        }
        elapsed=now()-start;for(int i=0;i<2;i++)unlink(paths[i]);
    } else if (!strcmp(argv[1],"fanout")) {
        pthread_t *threads=calloc((size_t)n,sizeof(pthread_t));int64_t live=0;
        start=now();s.deadline=start+20000000;
        for(int64_t i=0;i<n;i++) {
            if(now()>=s.deadline)atomic_store(&s.canceled,1);
            if(!atomic_load(&s.canceled)) {
                if(!start_thread(&threads[live],idle,&s))return 2;
                live++;
            }
        }
        while(now()<s.deadline){struct timespec t={0,100000};nanosleep(&t,NULL);}
        atomic_store(&s.canceled,1);
        for(int64_t i=0;i<live;i++)pthread_join(threads[i],NULL);
        elapsed=now()-start;latency=elapsed-20000000;free(threads);
    } else return 2;
    printf("%lld %lld %lld\n",(long long)checksum,(long long)elapsed,(long long)latency);
    return 0;
}
