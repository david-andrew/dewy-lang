import sys
from scanner import Scanner
from scanner import Token
from unit import *
import readline

#for debugging in the interprestor mode output
import traceback

#it is correct to have all of these static methods, because they are generally recursive, and thus need to be static


class Parser:

    precedence = {'+':1, '-':1, '*':2, '/':2, '%':2, '^':4, 'm':3, 'd':3} #m, d, e are unit precedent level multiply/divide/exponent
    default_val = {' ':-1, '+':0, '-':0, '*':1, '/':1, '%':0, '^':-1, 'm':1, 'd':1} #-1 indicates it returns itself
    op_class = { 1:('+', '-'), 2:('*', '/', '%'), 4:('^', 'log'), 3:('m','d')}
    unit_op_encode = {'*':'m', '/':'d'}#, '%':'o', '^':'p'} #for the higher precedence of unit operations
    unit_op_decode = {'m':'*', 'd':'/'}#, 'o':'%', 'p':'^'}
    #don't need a defualt class, as it is just the firt op in the list of op classes
	
    #m/d indicates unit multiply/divide

    def __init__(self, tokens):
        self.tokens = tokens
        self.ast = None

    def __str__(self):
        return str(self.ast)

    
    def __repr__(self):
        pass

    
    #currently 
    def parse(self):
        #clean up passes on the tokens
        #combine multi-operations into a single token (probably not operation type?, or have all the ops be separate from the first one
        self.tokens = Parser.combine_multi_ops(self.tokens)


        #ensure that every parenthesis has a matching pair
        Parser.match_all_parenthesis(self.tokens)

        #make a units parsing passes
        self.tokens = Parser.insert_explicit_unit_ops(self.tokens) #any occurrentces of num unit or unit unit become explicitely num*unit and unit*unit
        self.tokens = Parser.raise_unit_precedence(self.tokens) #convert all multiply and divides between units to higher precedence versions of each operation. This ensures that units will be combined before general math is done on surrounding numbers
        #selfcombine_units() #convert any strings of unit tokens into a single token with a proper unit #Don't need anymore because units operations have proper precedence
        #selfcombine_numbers_with_units() #combine all numbers and adjacent units into physical numbers #also don't need because this is handled during the normal ast generation
        self.parse_physical_numbers() #any occurrences of numbers (esp in scientific notation) into physical numbers

        #self.parse_units() #convert all units into the class unit

        #parse by passing tokens through the split by precedence function
        self.ast = Parser.split_by_lowest_precedence(self.tokens)


    def parse_physical_numbers(self):
        #look into handling scientific notation, if not already handled in the 
        #also need to be able to handle all of the special numbers I had from before
        for token in self.tokens:
            if token.type == Scanner.number:
                if token.format == 'INT':
                    value = int(token.value)
                elif token.format == 'REAL':
                    value = float(token.value)
                elif token.format == 'HEX':
                    value = int(token.value, 0)
                elif token.format == 'BIN':
                    value = int(token.value, 0)
                else:
                    raise ValueError('Parser Error: Unable to parse value for token with format "' + str(v.format) + '"')
              
                #modify the token reference to contain the correct physical number in its place
                token.value = PhysicalNumber(value, 0, Unit(None,None))
                token.format = 'PhysicalNumber'
            
            #FOR TESTING?
            #don't have any unit types, only physical numbers
            elif token.type == Scanner.unit:
                token.value = Unit(token.value[0], token.value[1])



    def parse_units(self):
        for token in self.tokens:
            if token.type == Scanner.unit:
                token.value = Unit(token.value[0], token.value[1])


    def evaluate(self):
        return self.ast.evaluate()

    
    @staticmethod
    def split_by_lowest_precedence(tokens):
        #split the list of tokens into a node with an op type and a list of nodes or terminal values

        # if len(tokens) == 0:
        #     raise ValueError('No tokens found in current tokens stream')

        #remove (potentially multiple) layers of parenthesis enclosing the entire function
        tokens = Parser.remove_outer_parenthesis(tokens)

        # #these should only be hit when the input is exactly a single token, or a token list without any operations for splitting
        if len(tokens) == 1 or Parser.check_for_operations(tokens) == False:
            n = Node(operands=tokens, op_list=['+'])
            #print(n) #temporary
            return n



        #after removing parenthesis, find the lowest precedent operator
        delimit = Parser.find_lowest_precedence(tokens)

        split_list = []
        op_list = []

        cur_op = ' '

        start = 0
        end = 0

        while end < len(tokens):
            #check if the current tokens are a list of operations
            # if tokens[end].type == Scanner.operation:
            #     i = end + 1
            #     #count how many s

            #     while i < len(tokens) and tokens[i].type == Scanner.operation:
            #         #add surrounding parenthesis
            #         #Token(Scanner.parenthesis, self.text[0])


            if tokens[end].type == Scanner.operation and Parser.precedence[tokens[end].value[0]] == delimit:
                split_list.append(tokens[start:end])
                op_list.append(cur_op)
                cur_op = tokens[end].value
                start = end + 1

            if tokens[end].type == Scanner.parenthesis and tokens[end].value == '(':
                end += Parser.find_matching_pair(tokens[end:])

            end += 1

        split_list.append(tokens[start:end])
        op_list.append(cur_op)




        if len(split_list[0]) == 0 and op_list[0] == ' ':
            del split_list[0]
            del op_list[0]


        #  #print out the state of the list
        # print('before trying to fold multi-operations')
        # for op, val in zip(op_list, split_list):
        #     print(str(op) + '  ' + str(val))
        # print('')


        #unfold any multi-operations into their adjacent split_list
        for ops, i in zip(op_list, list(range(len(op_list)))):
            if len(ops) > 1:
                for op in reversed(ops[1:]):
                    split_list[i].insert(0, Token(Scanner.operation, op))
                    split_list[i].insert(0, Token(Scanner.parenthesis, '('))
                    split_list[i].append(Token(Scanner.parenthesis, ')'))
                    op_list[i] = ops[0]


        operands = []
        for val in split_list:
            if Parser.check_for_operations(val):
                operands.append(Parser.split_by_lowest_precedence(val))
            else:
                val = Parser.remove_outer_parenthesis(val)
                assert(len(val) == 1) #there should be only a single value here
                operands.append(val[0])

        return Node(Parser.op_class[delimit], operands, op_list)

        #for l, o in zip(split_lists, op_list):
        #    print(str(o) + ' ' + str(l))

        
        #collapse multi ops into a single op
        # 5--2 = 5+2
        # 5//2 = 5*2
        # 5%%2 = invalid?

    
    @staticmethod
    def find_lowest_precedence(tokens):
        """Find the operator that is the lowest precedence in the given list of tokens"""
        i = 0
        lowest_precedence = 1000 #infinity
        while i < len(tokens):
            cur = tokens[i]
            if cur.type == Scanner.operation and Parser.precedence[cur.value[0]] < lowest_precedence:
                lowest_precedence = Parser.precedence[cur.value[0]]
            elif cur.type == Scanner.parenthesis and cur.value == '(': #skip to matching close parenthesis
                i += Parser.find_matching_pair(tokens[i:])
            i+=1

        if lowest_precedence == 1000:
            raise SyntaxError('Parser Error: No operation found in current precedence layer')

        return lowest_precedence



    @staticmethod
    def find_matching_pair(tokens, match='()', match_type=Scanner.parenthesis):
        match_left = match[0]
        match_right = match[1]

        if not (tokens[0].type == match_type and tokens[0].value == match_left):
            raise ValueError('Parser Error: Expected first token to be ' + str(Token(match_type, match_left)) + '. Found: ' + str(tokens[0]))

        count = 1
        i = 0
        while count > 0:
            i += 1

            if i == len(tokens):
                print(tokens)
                raise ValueError('Parser Error: No matching symbol found in token stream')

            cur = tokens[i]
            if cur.type == match_type:
                if cur.value == match_left:
                    count += 1
                elif cur.value == match_right:
                    count -= 1
                else:
                    raise ValueError('Parser Error: parenthesis token doesn\'t contain parenthesis value. found:"' + str(cur.value) + '"')

        return i #index of the matching closing parenthesis

    
    @staticmethod
    def match_all_parenthesis(tokens):
        #ensure that every opening parenthesis has a matching closing parenthesis
        count = 0
        for t in tokens:
            if t.type == Scanner.parenthesis:
                if t.value == '(':
                    count += 1
                elif t.value == ')':
                    count -= 1
                else:
                    raise ValueError('Parser Error: parenthesis token doesn\'t contain parenthesis value. found:"' + str(cur.value) + '"')

                if count < 0:
                    raise SyntaxError('Parser Error: unmatched closing parenthesis in expression') #refactor out into a parse error function that says where the error occurred

        if count > 0:
            raise SyntaxError('Parser Error: unmatched opening parenthesis in expression')

    @staticmethod
    def remove_outer_parenthesis(tokens):
        #remove (potentially multiple) layers of parenthesis enclosing the entire function
        while len(tokens) > 0 and tokens[0].type == Scanner.parenthesis and tokens[0].value == '(' and Parser.find_matching_pair(tokens) == len(tokens) - 1:
            tokens = tokens[1:-1]
            if len(tokens) == 0:
                #maybe throw a warning about an empty, non-terminal chain
                break

        return tokens

    
    @staticmethod
    def check_for_operations(tokens):
        has_ops = False
        for t in tokens:
            if t.type == Scanner.operation:
                has_ops = True
        return has_ops


    @staticmethod
    def combine_multi_ops(tokens):
        i = 0
        while i < len(tokens):
            if tokens[i].type == Scanner.operation:
                j = i
                op = ''
                while j < len(tokens) and tokens[j].type == Scanner.operation:
                    op += tokens[j].value
                    j+=1
                
                if j > i:
                    #multi-op combine
                    t = Token(Scanner.operation, op)
                    #t.multi_op = op
                    tokens = tokens[:i] + [t] + tokens[j:]
            i+=1

        return tokens

    
    @staticmethod
    def insert_explicit_unit_ops(tokens):
        #replaces any instances of a unit next to a number as the unit times that number. e.g. 10 kg becomes 10 * kg
        i = 0
        while i + 1 < len(tokens):
            if tokens[i].type == Scanner.number or tokens[i].type == Scanner.unit:
                if tokens[i+1].type == Scanner.unit:
                    tokens.insert(i+1, Token(Scanner.operation, '*'))
                    i+=1
            i+=1

        return tokens


    @staticmethod
    def raise_unit_precedence(tokens):
        #convert any multiply and divide ops between units into higher precedence versions of the operations
        i = 0
        while i + 1 < len(tokens):
            t = tokens[i]
            if t.type == Scanner.operation and t.value in Parser.unit_op_encode:                #check if current value is either the * or / operation
                if tokens[i-1].type == Scanner.unit or tokens[i-1].type == Scanner.number:      #previous item must be either a unit or number
                    if tokens[i+1].type == Scanner.unit:                                        #confirm that the next item is a unit
                        tokens[i] = Token(Scanner.operation, Parser.unit_op_encode[t.value])    #replace with a higher precedent version of the operation
            i+=1

        return tokens

            

    # @staticmethod
    # def WIP_insert_explicit_unit_ops(tokens):
    #     i = 0
    #     while i + 1 < len(tokens):
    #         if tokens[i].type == Scanner.number or tokens[i].type == Scanner.unit:
    #             if tokens[i+1].type == Scanner.unit:
    #                 tokens.insert(i+1, Token(Scanner.operation, 'm')) #was "*" but "u" indicates higher precedence multiply for units
    #                 i+=1
    #             elif i+2 < len(tokens) and tokens[i+1] == Scanner.operation and tokens[i+1].value in Parser.unit_op_encode and tokens[i+2].type == Scanner.unit:                    
    #                 tokens[i+1].value = Parser.unit_op_encode[tokens[i+1].value]
    #                 i+=2
    #         i+=1

    #     return tokens



class Node:

    def __init__(self, op_class=('+', '-'), operands=[], op_list=[]):
        self.op_class = op_class      #class of operations, e.g. (+-) (*/%) (^)
        self.operands = operands    #list of elements in this particular node.
                                    #e.g. [('+', 10 kg), ('-', 5 kg), ('-', 3 kg), ('+', 4 kg)]
                                    #all operations from the chain must be in the operation class
        self.op_list = op_list

        if len(operands) != len(op_list):
            print('Op list: ' + str(op_list))
            print('Operands: ' + str(operands))
            print(operands[0])
            raise ValueError('Parser Error: Operation and Operand lists are not the same length')

        for op, i in zip(op_list, list(range(0,len(op_list)))):
            # if op == ' ':
            #     op_list[i] = op_class[0]
            #     op = op_class[0]

            if op not in op_class and op != ' ':
                raise ValueError('Parser Error: Unexpected operation in op list. expected from class ' + str(op_class) + '. Found: (' + op + ')')

    def __str__(self):
        tab = 4 # how many spaces make a tab 

        #header of the string
        s = '('
        for op in self.op_class:
            s = s + op
        s = s + ')\n'

        for val, op in zip(self.operands, self.op_list):
            s = s + op + ' ' #s.append('(' + op + ') ')
            if type(val) == Node:
                temp = str(val) #potentially insert a tab at the start
                i = 0
                while i < len(temp):
                    if temp[i] == '\n':
                        temp = temp[:i+1] + ' ' * tab + temp[i+1:] #insert a tab
                    i+=1
                s += temp
            else:
                s = s + str(val) #val should be a single value/token

            s = s + '\n'

        return s[:-1]


    def evaluate(self):
        result = Parser.default_val[self.op_list[0]]

        if len(self.operands) == 1:
            op = self.op_list[0]
            v = self.operands[0]
            if type(v) == Node:
                v = v.evaluate()
            elif type(v) == Token and (v.type == Scanner.number or v.type == Scanner.unit):
                v = v.value
            else:
                raise ValueError('Evaluation Error: unknown type for evaluation: ' + repr(v) + 'with operation ' + op)

            if op in Parser.unit_op_decode:
                op = Parser.unit_op_decode[op]

            if op == ' ' or op == '+' or op == '*':
                return v
            elif op == '-':
                return -v
            elif op == '/':
                return 1/v
            elif op == '%' or op == '^':
                raise ValueError('Evaluation Error: cannot apply operation ' + op + ' to ' + str(v) + ' without a left hand side')
            else:
                raise ValueError('Evaluation error: Unrecognized operation in class ' + str(self.op_class) + '. Found: ' + op)


        for op, v in zip(self.op_list, self.operands):
            if type(v) == Node:
                v = v.evaluate()
            elif type(v) == Token and (v.type == Scanner.number or v.type == Scanner.unit):
                v = v.value
            else:
                raise ValueError('Evaluation Error: unknown type for evaluation: ' + repr(v) + 'with operation ' + op)


            if op in Parser.unit_op_decode:
                op = Parser.unit_op_decode[op]

            #     if v.format == 'INT':
            #         v = int(v.value)
            #     elif v.format == 'REAL':
            #         v = float(v.value)
            #     elif v.format == 'HEX':
            #         v = int(v.value, 0)
            #     elif v.format == 'BIN':
            #         v = int(v.value, 0)
            #     elif v.format == 'PhysicalNumber':
            #         pass #already in an addable format
            #     else:
            #         raise ValueError('Parser Error: Unable to parse value for token with format "' + str(v.format) + '"')


            if op == ' ':
                result = v #space indicates the first value is the result
            elif op == '+':
                result += v
            elif op == '-':
                result -= v
            elif op == '*' or op == 'm':
                result *= v
            elif op == '/' or op == 'd':
                result /= v
            elif op == '%':
                result %= v
            elif op == '^':
                result **= v
            else:
                raise ValueError('Evaluation error: Unrecognized operation in class ' + str(self.op_class) + '. Found: ' + op)

        return result


    #CURRENTLY BROKEN. want to be able to operate on physical numbers, not regular numbers
    #should be basically identical to the regular evaluate function
    def physical_evaluate(self):

        #set up default values
        num_result = Parser.default_val[self.op_list[0]]
        unit_result = None #(maybe?) different from "no units" which is it's own representation. although now that everything 
        #needs_init = True if result == -1 else False
        numeric_op = False #type of op, numeric, or unit

        for op, val in zip(self.op_list, self.operands):
                
            #unpack the current value
            if type(val) == Node:
                v = val.evaluate()
            else:
                if len(val) > 1:
                    raise ValueError('Parser Error: expected a single value for current item in expression. Found: ' +str(val))

                v = val[0] #get the token
                
                #consider setting up a dictionary of functions here where the key is the format string
                if v.type == Scanner.number:
                    numeric_op = True

                    if v.format == 'INT':
                        v = int(v.value)
                    elif v.format == 'REAL':
                        v = float(v.value)
                    elif v.format == 'HEX':
                        v = int(v.value, 0)
                    elif v.format == 'BIN':
                        v = int(v.value, 0)
                    else:
                        raise ValueError('Parser Error: Unable to parse value for token with format "' + str(v.format) + '"')
                elif v.type == Scanner.unit:
                    numeric_op = False
                    v = v.value


            # if needs_init:
            #     result = v
            #     needs_init = False
            # else:

            #apply the current value based on the correct operation
            #in each of these, we would check the units
            if numeric_op: #current operationg on numbers
                result = num_result
            else:
                result = unit_result

            if op == ' ':
                result = v #space indicates the first value is the result
            elif op == '+':
                result += v
            elif op == '-':
                result -= v
            elif op == '*':
                result *= v
            elif op == '/':
                result /= v
            elif op == '%':
                result %= v
            elif op == '^':
                result **= v
            else:
                raise ValueError('Evaluation error: Unrecognized operation in class ' + str(self.op_class) + '. Found: ' + op)



        return result
        


if __name__ == "__main__":
    if len(sys.argv) > 1 and '-' not in sys.argv[1]: #input file mode

        filename = sys.argv[1]
        with open(filename, 'r') as file:
            lines = [s for s in file.readlines() if s != '\n'] #handle any blank lines
            for line in lines:
                tokens = Scanner(line).scan()
                p = Parser(tokens)
                p.parse()
                print(str(p))

        # tokens = Scanner(open(filename, 'r').read()).scan()
        # p = Parser(tokens)
        # p.parse()
        # print(str(p))

    else:  #interpretor mode
        print('dewy0alpha Interpretor')
        print('Type "help" for more information')

        while True:
            try:
                string = input('>>> ')
                p = Parser(Scanner(string).scan())
                p.parse()

                if '-t' in sys.argv: #print the parse tree
                    print(str(p) + '\n')
                if '-v' in sys.argv: 
                    print(string + ' = ' + str(p.evaluate())) #print the verbose result
                else:
                    print(str(p.evaluate())) #print the regular result

            # except KeyboardInterrupt:
            #     raise
            except KeyboardInterrupt:
                print('\nKeyboardInterrupt')
            except EOFError:
                print()
                break
            except Exception as e:
                if 'raise' in str(traceback.format_exc()):
                    print(e)
                    #print(traceback.format_exc()) #uncomment for bugs in lines with my custom raise message
                else:
                    print(traceback.format_exc())  


            
            #print(str(p))