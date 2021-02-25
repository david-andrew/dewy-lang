#current completed step is simple lexer
dewy: dewy_compiler_compiler.o  utilities.o object.o token.o dictionary.o vector.o  set.o mast.o scanner.o parser.o
	clang -o dewy dewy_compiler_compiler.o utilities.o object.o token.o dictionary.o vector.o  set.o mast.o scanner.o parser.o


utilities.o: utilities.c utilities.h
	clang -c -o utilities.o utilities.c

object.o: object.c object.h
	clang -c -o object.o object.c

token.o: token.c token.h
	clang -c -o token.o token.c

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

scanner.o: scanner.c scanner.h
	clang -c -o scanner.o scanner.c

parser.o: parser.c parser.h
	clang -c -o parser.o parser.c

test: unit_test.c utilities.o object.o vector.o dictionary.o set.o token.o mast.o
	clang -o unit_test unit_test.c utilities.o object.o vector.o dictionary.o set.o token.o mast.o
	./unit_test
	rm unit_test

dewy_compiler_compiler.o: dewy_compiler_compiler.c
	clang -c -o dewy_compiler_compiler.o dewy_compiler_compiler.c

clean:
	rm -rf *.o unit_test dewy