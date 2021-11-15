all: dewy_compiler_compiler.o  utilities.o object.o metatoken.o dictionary.o vector.o  set.o metaast.o metascanner.o metaparser.o charset.o metaitem.o fset.o slice.o


#current completed step is simple lexer
dewy: dewy_compiler_compiler.o  utilities.o object.o metatoken.o dictionary.o vector.o set.o ustring.o charset.o metaast.o metascanner.o metaparser.o slot.o fset.o slice.o parser.o
	clang -o dewy dewy_compiler_compiler.o utilities.o object.o metatoken.o dictionary.o vector.o set.o ustring.o charset.o metaast.o metascanner.o metaparser.o slot.o fset.o slice.o parser.o -lm

debug:
	clang -o dewy dewy_compiler_compiler.c utilities.c object.c tuple.c metatoken.c dictionary.c vector.c set.c ustring.c charset.c metaast.c metascanner.c metaparser.c metaitem.c fset.c slice.c gotokey.c reduction.c gss.c sppf.c srnglr.c -lm -g

utilities.o: utilities.c utilities.h ustring.h
	clang -c -o utilities.o utilities.c

object.o: object.c object.h utilities.h ustring.h vector.h dictionary.h set.h metatoken.h charset.h slot.h
	clang -c -o object.o object.c

metatoken.o: metatoken.c metatoken.h object.h vector.h utilities.h ustring.h
	clang -c -o metatoken.o metatoken.c

dictionary.o: dictionary.c dictionary.h object.h utilities.h
	clang -c -o dictionary.o dictionary.c

vector.o: vector.c vector.h object.h dictionary.h utilities.h
	clang -c -o vector.o vector.c
	
set.o: set.c set.h object.h utilities.h
	clang -c -o set.o set.c

charset.o: charset.c charset.h object.h utilities.h ustring.h
	clang -c -o charset.o charset.c

ustring.o: ustring.c ustring.h object.h utilities.h metascanner.h
	clang -c -o ustring.o ustring.c

slot.o: slot.c slot.h object.h set.h metaparser.h slice.h fset.h utilities.h
	clang -c -o slot.o slot.c

metaast.o: metaast.c metaast.h vector.h charset.h metatoken.h utilities.h ustring.h
	clang -c -o metaast.o metaast.c

metascanner.o: metascanner.c metascanner.h object.h vector.h metatoken.h utilities.h ustring.h 
	clang -c -o metascanner.o metascanner.c

metaparser.o: metaparser.c metaparser.h vector.h set.h metaast.h charset.h metatoken.h metascanner.h utilities.h ustring.h
	clang -c -o metaparser.o metaparser.c

fset.o: fset.c fset.h object.h set.h metaparser.h
	clang -c -o fset.o fset.c

parser.o: parser.c parser.h object.h slot.h metaparser.h set.h vector.h
	clang -c -o parser.o parser.c

slice.o: slice.c slice.h vector.h utilities.h
	clang -c -o slice.o slice.c

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