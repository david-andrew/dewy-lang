#TODO->tailor this more specifically. this was mostly copied from S.O. https://stackoverflow.com/questions/1484817/how-do-i-make-a-simple-makefile-for-gcc-on-linux

# TARGET = dcc
# LIBS = -lm
# CC = clang
# CFLAGS = -g -Wall

# .PHONY: default all clean

# default: $(TARGET)
# all: default

# OBJECTS = $(patsubst %.c, %.o, $(wildcard *.c))
# HEADERS = $(wildcard *.h)

# %.o: %.c $(HEADERS)
# 	$(CC) $(CFLAGS) -c $< -o $@ 

# .PRECIOUS: $(TARGET) $(OBJECTS)

# $(TARGET): $(OBJECTS)
# 	$(CC) $(OBJECTS) -Wall $(LIBS) -o $@

# clean:
# 	-rm -f *.o
# 	-rm -f $(TARGET)


# objects = dewy_compiler_compiler.o dictionary.o vector.o set.o token.o parser.o scanner.o utilities.o 

# dcc: $(objects)
# 	clang -o dcc $(objects)

dewy_compiler_compiler_objs = utilities.o scanner.o parser.o object.o dictionary.o vector.o
unit_test_objs = vector.o dictionary.o set.o token.o utilities.o
dictionary_objs = utilities.h object.h
vector_objs = utilities.o object.o dictionary.o
set_objs = utilities.o object.o dictionary.o
object_objs = utilities.o dictionary.o vector.o set.o token.o
token_objs = object.o

main: dewy_compiler_compiler.o
	./dewy_compiler_compiler

test: unit_test.o
	./unit_test

dewy_compiler_compiler.o: dewy_compiler_compiler.c $(dewy_compiler_compiler_objs)
	clang dewy_compiler_compiler.c -o dewy_compiler_compiler $(dewy_compiler_compiler_objs)

unit_test.o: unit_test.c $(unit_test_objs)
	clang unit_test.c -o unit_test $(unit_test_objs)

dictionary.o: dictionary.c $(dictionary_objs)
	clang -c dictionary.c

vector.o: vector.c $(vector_objs)
	clang -c vector.c

set.o: set.c $(set_objs)
	clang -c set.c

object.o: object.c $(object_objs)
	clang -c object.c

token.o: token.c $(token_objs)
	clang -c token.c

utilities.o: utilities.c
	clang -c utilities.c

clean:
	rm dewy_compiler_compiler unit_test *.o
