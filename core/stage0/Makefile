CFLAGS = -O2 -g -Wall -Wno-unused-function -Wno-sign-compare -std=gnu11
SRC = util.c lex.c parse.c types.c check.c expr.c gen.c main.c
sloppy0: $(SRC) sloppy0.h check.h
	$(CC) $(CFLAGS) -o sloppy0 $(SRC)
clean:
	rm -f sloppy0
