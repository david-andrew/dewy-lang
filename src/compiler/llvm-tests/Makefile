
metal: metal.o
	

metal.o: metal.h metal.c
	clang -O3 -c -o metal.o metal.c

hello: hello.ll metal.o
	clang hello.ll metal.o

input: input.ll metal.o
	clang input.ll metal.o

rule110: rule110.ll metal.o
	clang rule110.ll metal.o

clean:
	rm -rf *.o a.out