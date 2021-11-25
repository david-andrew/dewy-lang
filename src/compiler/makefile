all: dewy_compiler_compiler.o  utilities.o object.o metatoken.o dictionary.o vector.o  set.o metaast.o metascanner.o metaparser.o charset.o slot.o fset.o slice.o crf.o bsr.o


#current completed step is simple lexer
dewy: dewy_compiler_compiler.o  utilities.o object.o metatoken.o dictionary.o vector.o set.o ustring.o charset.o metaast.o metascanner.o metaparser.o slot.o fset.o slice.o parser.o bsr.o crf.o
	clang -O3 -o dewy dewy_compiler_compiler.o utilities.o object.o metatoken.o dictionary.o vector.o set.o ustring.o charset.o metaast.o metascanner.o metaparser.o slot.o fset.o slice.o parser.o bsr.o crf.o -lm

debug:
	clang -o dewy dewy_compiler_compiler.c utilities.c object.c metatoken.c dictionary.c vector.c set.c ustring.c charset.c metaast.c metascanner.c metaparser.c slot.c fset.c parser.c bsr.c crf.c slice.c -lm -g

profile:
	clang -O3 -o dewy dewy_compiler_compiler.c utilities.c object.c metatoken.c dictionary.c vector.c set.c ustring.c charset.c metaast.c metascanner.c metaparser.c slot.c fset.c parser.c bsr.c crf.c slice.c -lm -pg
	./dewy -i -r ../../tests/11.grammar ../../tests/11.source
	gprof dewy gmon.out > gmon.txt

bsr.o: bsr.c bsr.h slice.h
	clang -O3 -c -o bsr.o bsr.c

charset.o: charset.c charset.h object.h ustring.h utilities.h
	clang -O3 -c -o charset.o charset.c

crf.o: crf.c crf.h object.h set.h slice.h slot.h metaparser.h parser.h utilities.h
	clang -O3 -c -o crf.o crf.c

dewy_compiler_compiler.o: dewy_compiler_compiler.c metaast.h metaparser.h metascanner.h metatoken.h object.h parser.h set.h slot.h ustring.h utilities.h vector.h
	clang -O3 -c -o dewy_compiler_compiler.o dewy_compiler_compiler.c

dictionary.o: dictionary.c dictionary.h object.h utilities.h
	clang -O3 -c -o dictionary.o dictionary.c

fset.o: fset.c fset.h charset.h object.h set.h metaparser.h
	clang -O3 -c -o fset.o fset.c

metaast.o: metaast.c metaast.h charset.h metatoken.h object.h set.h vector.h ustring.h utilities.h
	clang -O3 -c -o metaast.o metaast.c

metaparser.o: metaparser.c metaparser.h charset.h fset.h metaast.h metascanner.h metatoken.h set.h slice.h ustring.h utilities.h vector.h
	clang -O3 -c -o metaparser.o metaparser.c

metascanner.o: metascanner.c metascanner.h metatoken.h object.h utilities.h ustring.h vector.h
	clang -O3 -c -o metascanner.o metascanner.c

metatoken.o: metatoken.c metatoken.h object.h vector.h utilities.h ustring.h
	clang -O3 -c -o metatoken.o metatoken.c

object.o: object.c object.h charset.h crf.h dictionary.h fset.h metaast.h metatoken.h set.h slice.h slot.h ustring.h utilities.h vector.h
	clang -O3 -c -o object.o object.c

parser.o: parser.c parser.h bsr.h charset.h crf.h metaparser.h object.h set.h slice.h slot.h vector.h
	clang -O3 -c -o parser.o parser.c
	
set.o: set.c set.h object.h utilities.h
	clang -O3 -c -o set.o set.c

slice.o: slice.c slice.h vector.h utilities.h
	clang -O3 -c -o slice.o slice.c

slot.o: slot.c slot.h object.h fset.h metaparser.h parser.h slice.h utilities.h
	clang -O3 -c -o slot.o slot.c

ustring.o: ustring.c ustring.h metascanner.h object.h utilities.h
	clang -O3 -c -o ustring.o ustring.c

utilities.o: utilities.c utilities.h ustring.h
	clang -O3 -c -o utilities.o utilities.c

vector.o: vector.c vector.h dictionary.h object.h utilities.h
	clang -O3 -c -o vector.o vector.c

unit_test.o: unit_test.c charset.o crf.o dictionary.o fset.o metaparser.o metascanner.o metatoken.o object.o parser.o set.o slice.o slot.o utilities.o vector.o metaast.o ustring.o
	clang -o unit_test.o unit_test.c charset.o crf.o dictionary.o fset.o metaparser.o metascanner.o metatoken.o object.o parser.o set.o slice.o slot.o utilities.o vector.o metaast.o ustring.o -lm

test: unit_test.o
	./unit_test.o
	rm unit_test.o

valgrind_test: unit_test.o
	valgrind ./unit_test.o
	rm unit_test.o

# scratch:
# 	clang scratch.c ustring.c charset.c utilities.c metatoken.c metascanner.c metaparser.c vector.c object.c set.c dictionary.c metaast.c -lm -g

clean:
	rm -rf *.o unit_test dewy a.out