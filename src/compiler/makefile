all: dewy_compiler_compiler.o  utilities.o object.o metatoken.o dictionary.o vector.o  set.o metaast.o metascanner.o metaparser.o charset.o metaitem.o fset.o slice.o gotokey.o reduction.o srnglr.o
 

#current completed step is simple lexer
dewy: dewy_compiler_compiler.o  utilities.o object.o metatoken.o dictionary.o vector.o set.o ustring.o charset.o metaast.o metascanner.o metaparser.o metaitem.o fset.o slice.o gotokey.o reduction.o srnglr.o
	clang -o dewy dewy_compiler_compiler.o utilities.o object.o metatoken.o dictionary.o vector.o set.o ustring.o charset.o metaast.o metascanner.o metaparser.o metaitem.o fset.o slice.o gotokey.o reduction.o srnglr.o -lm

debug:
	clang -o dewy dewy_compiler_compiler.c utilities.c object.c metatoken.c dictionary.c vector.c set.c ustring.c charset.c metaast.c metascanner.c metaparser.c metaitem.c fset.c slice.c gotokey.c reduction.c srnglr.c -lm -g

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

ustring.o: ustring.c ustring.h
	clang -c -o ustring.o ustring.c

metaitem.o: metaitem.c metaitem.h
	clang -c -o metaitem.o metaitem.c

metaast.o: metaast.c metaast.h
	clang -c -o metaast.o metaast.c

metascanner.o: metascanner.c metascanner.h
	clang -c -o metascanner.o metascanner.c

metaparser.o: metaparser.c metaparser.h
	clang -c -o metaparser.o metaparser.c

fset.o: fset.c fset.h
	clang -c -o fset.o fset.c

slice.o: slice.c slice.h
	clang -c -o slice.o slice.c

gotokey.o: gotokey.c gotokey.h
	clang -c -o gotokey.o gotokey.c

reduction.o:  reduction.c reduction.h
	clang -c -o reduction.o reduction.c

srnglr.o: srnglr.c srnglr.h
	clang -c -o srnglr.o srnglr.c

unit_test.o: unit_test.c utilities.o object.o vector.o dictionary.o set.o metatoken.o metaast.o charset.o ustring.o metascanner.o
	clang -o unit_test.o unit_test.c utilities.o object.o vector.o dictionary.o set.o metatoken.o metaast.o charset.o ustring.o metascanner.o -lm

test: unit_test.o
	./unit_test.o
	rm unit_test.o

valgrind_test: unit_test.o
	valgrind ./unit_test.o
	rm unit_test.o

scratch:
	clang scratch.c ustring.c charset.c utilities.c metatoken.c metascanner.c metaparser.c vector.c object.c set.c dictionary.c metaast.c -lm -g

dewy_compiler_compiler.o: dewy_compiler_compiler.c
	clang -c -o dewy_compiler_compiler.o dewy_compiler_compiler.c

clean:
	rm -rf *.o unit_test dewy a.out