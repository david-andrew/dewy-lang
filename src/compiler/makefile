all: dewy_compiler_compiler.o  utilities.o object.o metatoken.o dictionary.o vector.o  set.o mast.o metascanner.o metaparser.o charset.o item.o
 

#current completed step is simple lexer
dewy: dewy_compiler_compiler.o  utilities.o object.o metatoken.o dictionary.o vector.o  set.o mast.o metascanner.o parser.o
	clang -o dewy dewy_compiler_compiler.o utilities.o object.o metatoken.o dictionary.o vector.o  set.o mast.o metascanner.o parser.o


utilities.o: utilities.c utilities.h
	clang -c -o utilities.o utilities.c

object.o: object.c object.h
	clang -c -o object.o object.c

metatoken.o: metatoken.c metatoken.h
	clang -c -o metatoken.o metatoken.c

dictionary.o: dictionary.c dictionary.h
	clang -c -o dictionary.o dictionary.c

vector.o: vector.c vector.h
	clang -c -o vector.o vector.c
	
set.o: set.c set.h
	clang -c -o set.o set.c

charset.o: charset.c charset.h
	clang -c -o charset.o charset.c

item.o: item.c item.h
	clang -c -o item.o item.c

mast.o: mast.c mast.h
	clang -c -o mast.o mast.c

metascanner.o: metascanner.c metascanner.h
	clang -c -o metascanner.o metascanner.c

metaparser.o: metaparser.c metaparser.h
	clang -c -o metaparser.o metaparser.c

unit_test.o: unit_test.c utilities.o object.o vector.o dictionary.o set.o metatoken.o mast.o charset.o metascanner.o
	clang -o unit_test.o unit_test.c utilities.o object.o vector.o dictionary.o set.o metatoken.o mast.o charset.o metascanner.o

test: unit_test.o
	./unit_test.o
	rm unit_test.o

valgrind_test: unit_test.o
	valgrind ./unit_test.o
	rm unit_test.o

scratch:
	clang scratch.c charset.c utilities.c metatoken.c metascanner.c metaparser.c vector.c object.c set.c dictionary.c mast.c

dewy_compiler_compiler.o: dewy_compiler_compiler.c
	clang -c -o dewy_compiler_compiler.o dewy_compiler_compiler.c

clean:
	rm -rf *.o unit_test dewy a.out