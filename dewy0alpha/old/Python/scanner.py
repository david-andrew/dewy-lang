import sys
from unit import Unit
import readline

#for debugging
import traceback



#TODO   - Scientific notation check
#       - Make sure that multiline comments allow for nested comments inside (e.g. by using the same algorithm as in parser's match parenthesis)




class Scanner:

    #names for the token types
    #change these to all caps because they're constants
    comment = 'comment'
    whitespace = 'whitespace'
    number = 'number'
    boolean = 'boolean'
    operation = 'operation'
    unit = 'unit'
    parenthesis = 'parenthesis'
    bracket = 'bracket'
    brace = 'brace'
    identifier = 'identifier'
    EOF = 'EOF'

    
    def __init__(self, text):#filename):
        #self.text = open(filename, 'r').read() + '\a'   # ASCII bell so that it is guaranteed last token
                                                         # i.e. clearly the end of file if \a comes up
        self.text = text + '\a' * 10
        self.tokens = []

        self.tokanized = False

        
    def __str__(self):
        if not self.tokanized:
            return 'RAW INPUT:\n"' + self.text + '"'
        else:
            string = ''
            for t in self.tokens:
                string += t.type + ' ' * (14 - len(t.type))  + str(t.value) + '\n'
            return string
        
    
    def __repr__(self):
        string = ''
        if len(self.tokens) > 0:
            string += 'TOKANIZED INPUT:\n' + str(self.tokens)
            if len(self.text) > 0:
                string += '\n\n'

        if len(self.text) > 0:
            string += 'RAW INPUT:\n' + self.text
            
        return string


    def scan(self):
        self.scan0()    #convert raw text to only tokens
        #self.scan1()
        #self.scan2()
        #etc.

        #combine must be done in the parser
        #self.combine_units()
        
        # potentially skip this because whitespace might be important for some parsing decisions
        # i.e. are two pieces of code separated enough? For now, assume we aren't checking this
        # might need to insert multiply op in place of some spaces? can the parser figure it out?
        self.remove_whitespace()

        self.tokanized = True
        
        return self.tokens


    def remove_whitespace(self):
        tokens = []
        for t in self.tokens:
            if t.type != Scanner.whitespace:
                tokens.append(t)

        self.tokens = tokens

            
    def scan0(self):
        """Convert raw text to a series of tokens. No optimizations/combinations are made"""
        passes = 0
        
        while len(self.text) > 1:    # loop until all input is consumed
            passes += 1
            ate_tokens = False

            
            ##### MAKE SURE THIS IS THE FIRST TOKEN TO BE CHECKED FOR #####
            #EOF token -> array ends with the ASCII bell symbol
            if self.text[0] == '\a':    #ascii bell
                self.text = ''
                break


            #eat regular tokens in sequence of most specific to least specific
            if self.eat_single_comment():
                continue

            if self.eat_multi_comment():
                continue

            if self.eat_all_whitespace():
                continue
            
            if self.eat_hex_number():
                continue

            if self.eat_bin_number():
                continue

            if self.eat_number():
                continue

            if self.eat_boolean():
                continue

            if self.eat_unit():
                continue

            if self.eat_parenthesis():
                continue

            if self.eat_bracket():
                continue

            if self.eat_brace():
                continue

            if self.eat_comparison_operation():
                continue

            if self.eat_logical_operation():
                continue

            if self.eat_bitshift_operation():
                continue

            if self.eat_math_operation():
                continue

            if self.eat_identifier():
                continue

            #can probably factor out ate_tokens, since this part only runs if no tokens are recognized anyways
            #print('no recognized tokens on pass ' + str(passes) + '. exiting scanner')
            #print(self)
            raise ValueError('Scanner Error: No recognized tokens on pass ' + str(passes) + '. exiting scanner\nUnprocessed input: ' +self.text)
            return #potentially return the tokan_list, or maybe something to signify incomplete   


    #whitespace tokens
    def eat_all_whitespace(self):    #eat all possible whitespace tokens
        ate_tokens = False
        while self.eat_newline() or self.eat_space() or self.eat_tab() or self.eat_carriage_return():
            ate_tokens = True
        return ate_tokens
        
    
    def eat_newline(self):
        if self.text[0] == '\n':    #newline
            i=1
            while self.text[i] == '\n':
                i+=1
            self.tokens.append(Token(Scanner.whitespace, ('newline', i)))
            self.text = self.text[i:]
            return True
        return False

    
    def eat_space(self):
        if self.text[0] == ' ':     #space
            i=1
            while self.text[i] == ' ':
                i+=1
            self.tokens.append(Token(Scanner.whitespace, ('space', i)))
            self.text = self.text[i:]
            return True
        return False
    

    def eat_tab(self):
        if self.text[0] == '\t':    #tab
            i=1
            while self.text[1] == '\t':
                i+=1
            self.tokens.append(Token(Scanner.whitespace, ('tab', i)))
            self.text = self.text[i:]
            return True
        return False


    def eat_carriage_return(self):
        if self.text[0] == '\r':    #carriage return
            i=1
            while self.text[i] == '\r':
                i+=1
            self.tokens.append(Token(Scanner.whitespace, ('carriage return', i)))
            self.text = self.text[i:]
            return True
        return False
            

    def eat_single_comment(self):
        if self.text[:2] == '//':    #comment tokens (single line)
            i=2
            while self.text[i] not in '\n\a':
                i+=1
            self.tokens.append(Token(Scanner.comment, self.text[:i]))    # add comment to token list 
            self.tokens.append(Token(Scanner.whitespace, '\n'))          # add newline at the end to token list
            self.text = self.text[i+1:]                          # update string to exclude parsed token
            return True
        return False


    def eat_multi_comment(self):
        if self.text[:2] == '/{':    #comment tokens (multiline)
            i=2
            while self.text[i:i+2] != '}/':
                i+=1
            self.tokens.append(Token(Scanner.comment, self.text[:i+2]))
            self.text = self.text[i+2:]
            return True
        return False

        
    def eat_hex_number(self):
        if self.text[:2] == '0x':    #eat a hex number, e.g. 0x13DF45FC
            i=2
            while self.text[i] in "0123456789abcdefABCDEF":
                i+=1

            if i > 2 and (not self.text[i].isalnum() or Unit.match_units(self.text[i:])):
                self.tokens.append(Token(Scanner.number, self.text[:i], 'HEX'))
                self.text = self.text[i:]
                return True

        return False
            

    def eat_bin_number(self):
        if self.text[:2] == '0b':    #eat a binary number e.g. 0b110011101
            i=2
            while self.text[i] in "01":
                i+=1

            if i > 2 and (not self.text[i].isalnum() or Unit.match_units(self.text[i:])):
                self.tokens.append(Token(Scanner.number, self.text[:i], 'BIN'))
                self.text = self.text[i:]
                return True

        return False
    

    def eat_number(self):
        #number token
        real = False
        
        if self.text[0] == '.': #number that starts with a decimal
            real = True
            i = 1
            while self.text[i].isnumeric():
                i+=1
            if i == 1: #ensure that a number actually followed the decimal place
                return False

            if not self.text[i].isalnum() or Unit.match_units(self.text[i:]):
                self.tokens.append(Token(Scanner.number, self.text[:i], 'REAL' if real else 'INT'))
                self.text = self.text[i:]
                return True

        elif self.text[0].isnumeric(): #regular number that starts with a number, then optional decimal place
            i=1
            while self.text[i].isnumeric():
                i+=1
            if self.text[i] == ".":
                real = True
                i+=1
                while self.text[i].isnumeric():
                    i+=1

            if not self.text[i].isalnum() or Unit.match_units(self.text[i:]):
                self.tokens.append(Token(Scanner.number, self.text[:i], 'REAL' if real else 'INT'))
                self.text = self.text[i:]
                return True
        return False

    
    #only engineering scientific notation with E/e. *10^num has to be done at the parser 
    def eat_sci_notation(self):
        #scientific notation
        #if self.text[0] in 'Ee':
        #    if self.text[1] == '-':
        #        #check for number
        #        pass
        #    else:
        #        #check for number without
        #        pass
        pass

    def eat_boolean(self):
        bools = ['true', 'false']
        for word in bools:
            if self.text[:len(word)] == word and not self.text[len(word)].isalnum():
                self.tokens.append(Token(Scanner.boolean, True if word == 'true' else False))
                self.text = self.text[len(word):]
                return True
        return False


    def eat_unit(self):
        check = Unit.match_units(self.text)  #SI unit token
        if check is not None:
            (p, u) = check
            self.text = self.text[len(p)+len(u):] #eat text
                
            if p == '': #set prefix to none if empty
                p = None
            self.tokens.append(Token(Scanner.unit, (p, u)))
            return True
        return False
            

    def eat_parenthesis(self):  #parenthesis tokens
        if self.text[0] in '()':
            self.tokens.append(Token(Scanner.parenthesis, self.text[0]))
            self.text = self.text[1:]
            return True
        return False


    def eat_bracket(self):      #square bracket tokens
        if self.text[0] in '[]':
            self.tokens.append(Token(Scanner.bracket, self.text[0]))
            self.text = self.text[1:]
            return True
        return False


    def eat_brace(self):        #curly brace tokens
        if self.text[0] in '{}':
            self.tokens.append(Token(Scanner.brace, self.text[0]))
            self.text = self.text[1:]
            return True
        return False


    def eat_comparison_operation(self):
        for op in ['=?', 'not?', '>?', '>=?', '>?', '>=?', 'in?']:
            if op == self.text[:len(op)]:
                self.tokens.append(Token(Scanner.operation, self.text[:len(op)]))
                self.text = self.text[len(op):]
                return True
        return False


    def eat_logical_operation(self):
        for op in ['and', 'or', 'xor', 'not', 'nand', 'nor', 'xnor']:
            if op == self.text[0:len(op)] and not self.text[len(op)].isalnum():
                self.tokens.append(Token(Scanner.operation, self.text[0:len(op)]))
                self.text = self.text[len(op):]
                return True
        return False


    def eat_bitshift_operation(self):
        for op in ['<<<!', '!>>>', '<<<', '>>>', '<<', '>>']:
            if op == self.text[0:len(op)]:
                self.tokens.append(Token(Scanner.operation, self.text[0:len(op)]))
                self.text = self.text[len(op):]
                return True
        return False

    def eat_math_operation(self):    #math operations
        if self.text[0] in '+-*/%^!':
            self.tokens.append(Token(Scanner.operation, self.text[0]))
            self.text = self.text[1:]
            return True
        return False


    #this should be last, as it is probably the most general token    
    def eat_identifier(self):
        if self.text[0].isalpha():
            i=1
            while self.text[i].isalnum():
                i+=1
            self.tokens.append(Token(Scanner.identifier, self.text[:i]))
            self.text = self.text[i:]
            return True
        return False

    
    #other tokens
    #e.g. identifiers, boolean operations, etc.


    
class Token:
    """Class for collecting tokens from the input .dewy file in the Dewy compiler process chain."""

    def __init__(self, type, value, format=None): #also want to include some type of class for numbers...
        #do something to initialize the token
        self.type = type
        self.value = value
        self.format = format #what is this for?
        

    def __str__(self):
        #convert the token to a string representation
        if self.format is not None:
            return 'token({}, {}, {})'.format(self.type, str(self.value), self.format)
        else:
            return 'token({}, {})'.format(self.type, str(self.value))
        

    def __repr__(self):
        #return a representation of the token
        if self.format is not None:
            return 'token({}, {}, {})'.format(self.type, repr(self.value), self.format)
        else:
            return 'token({}, {})'.format(self.type, repr(self.value))

    


if __name__ == "__main__":
    
    if len(sys.argv) > 1: #input file mode

        filename = sys.argv[1]
        text = open(filename, 'r').read()
        s = Scanner(text)
        s.scan()
        print(str(s))
        
    else:  #interpretor mode
        print('dewy0alpha Scanner')
        print('Enter text to see the tokens it is split into')


        while True:
            try:
                string = input(">>> ")
                s = Scanner(string)
                s.scan()
                print(str(s))
            except KeyboardInterrupt:
                print('\nKeyboardInterrupt')
            except EOFError:
                print()
                break
            except Exception as e:
                if 'raise' in str(traceback.format_exc()):
                    print(e)
                else:
                    print(traceback.format_exc())