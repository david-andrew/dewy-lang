all: dewy_compiler_compiler.o  utilities.o object.o metatoken.o dictionary.o vector.o  set.o metaast.o metascanner.o metaparser.o charset.o metaitem.o fset.o slice.o gotokey.o reduction.o gss.o sppf.o srnglr.o
 

#current completed step is simple lexer
dewy: dewy_compiler_compiler.o  utilities.o object.o tuple.o metatoken.o dictionary.o vector.o parray.o set.o ustring.o charset.o metaast.o metascanner.o metaparser.o metaitem.o fset.o slice.o gotokey.o reduction.o gss.o sppf.o srnglr.o
	clang -o dewy dewy_compiler_compiler.o utilities.o object.o tuple.o metatoken.o dictionary.o vector.o parray.o set.o ustring.o charset.o metaast.o metascanner.o metaparser.o metaitem.o fset.o slice.o gotokey.o reduction.o gss.o sppf.o srnglr.o -lm

debug:
	clang -o dewy dewy_compiler_compiler.c utilities.c object.c tuple.c metatoken.c dictionary.c vector.c parray.c set.c ustring.c charset.c metaast.c metascanner.c metaparser.c metaitem.c fset.c slice.c gotokey.c reduction.c gss.c sppf.c srnglr.c -lm -g

utilities.o: utilities.c utilities.h ustring.h
	clang -c -o utilities.o utilities.c

object.o: object.c object.h tuple.h utilities.h ustring.h vector.h dictionary.h set.h metatoken.h charset.h metaitem.h gotokey.h reduction.h gss.h srnglr.h
	clang -c -o object.o object.c

tuple.o: tuple.c tuple.h object.h utilities.h
	clang -c -o tuple.o tuple.c

metatoken.o: metatoken.c metatoken.h object.h vector.h utilities.h ustring.h
	clang -c -o metatoken.o metatoken.c

dictionary.o: dictionary.c dictionary.h object.h utilities.h
	clang -c -o dictionary.o dictionary.c

vector.o: vector.c vector.h object.h dictionary.h utilities.h
	clang -c -o vector.o vector.c

parray.o: parray.c parray.h object.h utilities.h
	clang -c -o parray.o parray.c
	
set.o: set.c set.h object.h utilities.h
	clang -c -o set.o set.c

charset.o: charset.c charset.h object.h utilities.h ustring.h
	clang -c -o charset.o charset.c

ustring.o: ustring.c ustring.h object.h utilities.h metascanner.h
	clang -c -o ustring.o ustring.c

metaitem.o: metaitem.c metaitem.h object.h set.h metaparser.h slice.h fset.h srnglr.h utilities.h
	clang -c -o metaitem.o metaitem.c

metaast.o: metaast.c metaast.h vector.h charset.h metatoken.h utilities.h ustring.h
	clang -c -o metaast.o metaast.c

metascanner.o: metascanner.c metascanner.h object.h vector.h metatoken.h utilities.h ustring.h 
	clang -c -o metascanner.o metascanner.c

metaparser.o: metaparser.c metaparser.h vector.h set.h metaast.h charset.h metatoken.h metascanner.h utilities.h ustring.h
	clang -c -o metaparser.o metaparser.c

fset.o: fset.c fset.h object.h set.h metaparser.h
	clang -c -o fset.o fset.c

slice.o: slice.c slice.h vector.h utilities.h
	clang -c -o slice.o slice.c

gotokey.o: gotokey.c gotokey.h object.h metaparser.h utilities.h
	clang -c -o gotokey.o gotokey.c

reduction.o: reduction.c reduction.h object.h metaparser.h utilities.h ustring.h
	clang -c -o reduction.o reduction.c

gss.o: gss.c gss.h vector.h set.h utilities.h
	clang -c -o gss.o gss.c

sppf.o: sppf.c sppf.h
	clang -c -o sppf.o sppf.c

srnglr.o: srnglr.c srnglr.h set.h fset.h slice.h tuple.h dictionary.h ustring.h metaparser.h metaitem.h gotokey.h reduction.h gss.h
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