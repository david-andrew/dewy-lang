import sys
from scanner import Scanner
from scanner import Token
from unit import *
import readline

#for debugging in the interprestor mode output
import traceback

#it is correct to have all of these static methods, because they are generally recursive, and thus need to be static


class Parser:

    op_class = { #all operations for each precedence level
        0:('=?', 'not?', '>?', '>=?', '>?', '>=?', 'in?'),
        1:('and', 'or', 'xor', 'not', 'nand', 'nor', 'xnor'),
        2:('!>>>', '<<<!', '>>>', '<<<', '>>', '<<'),
        3:('+', '-'),
        4:('*', '/', '%'),
        5:('m','d'), #unit versions of divide (d) and multiply (m), bind more tightly than normal arithmetic
        6:('^')
    }

    left_to_right = True; right_to_left = False #enums for associativity direction of operations
    
    op_class_associativity = {0:left_to_right, 1:left_to_right, 2:right_to_left, 3:left_to_right, 4:left_to_right, 5:left_to_right, 6:right_to_left}
    
    #precedence = {'+':3, '-':3, '*':4, '/':4, '%':4, '^':6, 'm':5, 'd':5,  #m, d, are unit precedent level multiply/divide
    #'!>>>':2, '<<<!':2, '>>>':2, '<<<':2, '>>':2, '<<':2, 
    #'and':1, 'or':1, 'xor':1, 'not':1, 'nand':1, 'nor':1, 'xnor':1} 
    
    precedence = {}; 
    for level in op_class:
        for op in op_class[level]:
            precedence[op] = level

    default_val = {'+':0, '-':0, '*':1, '/':1, 'm':1, 'd':1} #any operation that can be unary/chained (e.g. 5--2), what is the assumed value to the left of the op (5-(0-2))

    unit_op_encode = {'*':'m', '/':'d'}#, '%':'o', '^':'p'} #for the higher precedence of unit operations
    unit_op_decode = {'m':'*', 'd':'/'}#, 'o':'%', 'p':'^'}	
    #m/d indicates unit multiply/divide

    opchain = 'opchain' #parser enum for identifying chained operations (e.g. 5--2, 4^/2, 3----7, etc.)

    def __init__(self, tokens):
        self.tokens = tokens
        self.ast = None

    def __str__(self):
        return str(self.ast)

    
    def __repr__(self):
        pass

    
    #currently 
    def parse(self):
        """Parse the input tokens list into an abstract syntax tree, to allow for evaluation"""

        #clean up passes on the tokens
        #combine multi-operations into a single token (probably not operation type?, or have all the ops be separate from the first one
        #self.tokens = Parser.combine_multi_ops(self.tokens) ####NEED TO ADJUST -> instead of storing list into the single token, should figure out the equivalent operations and leave them as is
        ############----DO SOON---############## I think the way to handle this is as follows:
        # for every op sequence next to a number,
        # for the inner most op to the outer most op
        # insert default value, op, number and then wrap that part in parenthesis. 
        # e.g. 5----2 would become 5-(0-(0-(0-2))) =  -> though technically should collapse all of the -'s to a single +
        # e.g. 4/--/2 would become 4/(0-(0-(1/2)))
        # e.g. 3^-+-2 would become 3^(0-(0+(0-2)))
        # this way, we shouldn't have to handle cases where the left or right is an empty array from the split tokens (except for the unary 'not' case)

        #ensure that every parenthesis has a matching pair
        Parser.match_all_parenthesis(self.tokens)

        

        #make a units parsing passes
        self.tokens = Parser.insert_explicit_unit_ops(self.tokens) #any occurrentces of num unit or unit unit become explicitely num*unit and unit*unit

        # print('Tokens Before:')
        # for t in self.tokens: print(t)

        self.tokens = Parser.fold_logical_not_operators(self.tokens) #converts instances of e.g. 'not and' to 'nand', 'not or' to 'nor', etc. 


        # print('Tokens After:')
        # for t in self.tokens: print(t)


        # # make any instance of e.g. multiple math ops in a row have a single explicit token 
        # # (technically there will be 2 tokens, one for the chain of operations, and one regular operation that was the leftmost in the chain that defines the precedence of the overall operation)
        
        self.tokens = Parser.tokanize_operation_chains(self.tokens) #insert_explicit_math_vals(self.tokens)


        self.tokens = Parser.raise_unit_precedence(self.tokens) #convert all multiply and divides between units to higher precedence versions of each operation. This ensures that units will be combined before general math is done on surrounding numbers
        #selfcombine_units() #convert any strings of unit tokens into a single token with a proper unit #Don't need anymore because units operations have proper precedence
        #selfcombine_numbers_with_units() #combine all numbers and adjacent units into physical numbers #also don't need because this is handled during the normal ast generation
        self.parse_physical_numbers() #any occurrences of numbers (esp in scientific notation) into physical numbers

        #self.parse_units() #convert all units into the class unit

        #parse by passing tokens through the split by precedence function
        # print(self.tokens)
        self.ast = Parser.create_ast(self.tokens)  #Parser.old_split_by_lowest_precedence(self.tokens)

        # print(self.ast)


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
                #token.format = 'PhysicalNumber'
            
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
    def create_ast(tokens):
        #Turn the list of tokens into an abstract syntax tree.
        #returns a node containing the tree.
        #This should be recusively called to build up a full ast
        
        #remove (potentially multiple) layers of parenthesis enclosing the entire function
        tokens = Parser.remove_outer_parenthesis(tokens)

        if len(tokens) == 0: raise ValueError('encountered empty tokens list for AST') #this should never occur, cause everything should be preset to not have empty #return Leaf_Node(None)             #empty lhs
        if len(tokens) == 1: return Leaf_Node(tokens[0].value)  #single value lhs

        lhs, op, rhs = Parser.split_by_lowest_precedence(tokens)

        # print('\nlhs:\n' + str(lhs))
        # print('\nop: ' + str(op))
        # print('\nrhs:\n' + str(rhs))

        if len(lhs) == 0 and op.value in Left_Unary_Node.operators:
            return Left_Unary_Node(op=op, expr=Parser.create_ast(rhs))
        elif op.value in Binary_Node.operators:
            return Binary_Node(lhs=Parser.create_ast(lhs), op=op, rhs=Parser.create_ast(rhs))
        else:
            raise ValueError('Unknown operation encountered. Found: ' + str(op))
      

    @staticmethod
    def split_by_lowest_precedence(tokens):
        """Split the tokens list into left-hand-side, operation, and right-hand-side"""
        
        #special case when the first token is an opchain, operate on it first
        if tokens[0].type == Parser.opchain: #implies unary node creation
            opchain = tokens[0]
            op = opchain.value[0]
            opchain.value = opchain.value[1:]
            if len(opchain.value) == 0:
                return [], Token(Scanner.operation, op), tokens[1:]
            else:
                return [], Token(Scanner.operation, op), [opchain] + tokens[1:] 


        #regular split by lowest precedence
        precedence = Parser.find_lowest_precedence(tokens)
        associativity = Parser.op_class_associativity[precedence]

        #find the index of the operation that is the delimiter (right-most for left_to_right, and left-most for right_to_left)

        #reverse the list order if associativity is left to right, so that left and right versions can use the same algorithm
        if associativity == Parser.left_to_right:
            tokens.reverse()

        index = 0
        matched = False

        parens = 0

        #this should probably be refactored into a while loop, and use find matching pair to offset for parenthesis
        for t in tokens:
            #Check if in any set of parenthesis. Note that all outermost parethesis will have been removed already. hence a non-zero parens value indicates that we're inside of a parenthesis group
            if t.type == Scanner.parenthesis:
                if t.value == '(': parens += 1
                elif t.value == ')': parens -= 1
                else: raise ValueError('Encountered parenthesis of unknown type: ' + str(t))
            if parens == 0 and t.type == Scanner.operation and Parser.precedence[t.value] == precedence:
                matched = True
                break
            index += 1

        if not matched:
            raise ValueError('No operation with precedence (' + str(precedence) + ') in list of tokens.\nTokens: ' + str(tokens))

        # print('split index is: ' + str(index))

        #create the left and right-hand side token lists to return with the operation based on the associativity direction 
        if associativity == Parser.left_to_right:
            rhs = tokens[0:index]; rhs.reverse()
            op = tokens[index]
            lhs = tokens[index+1:]; lhs.reverse()
        else:
            lhs = tokens[0:index]
            op = tokens[index]
            rhs = tokens[index+1:]


        # print('lhs: ' + str(lhs))
        # print('op: ' + str(op))
        # print('rhs: ' + str(rhs) + '\n')

        return lhs, op, rhs


    # @staticmethod
    # def old_split_by_lowest_precedence(tokens):
    #     #split the list of tokens into a node with an op type and a list of nodes or terminal values

    #     # if len(tokens) == 0:
    #     #     raise ValueError('No tokens found in current tokens stream')

    #     #remove (potentially multiple) layers of parenthesis enclosing the entire function
    #     tokens = Parser.remove_outer_parenthesis(tokens)

    #     # #these should only be hit when the input is exactly a single token, or a token list without any operations for splitting
    #     if len(tokens) == 1 or Parser.check_for_operations(tokens) == False:
    #         n = Old_Chain_Node(operands=tokens, op_list=['+'])
    #         #print(n) #temporary
    #         return n



    #     #after removing parenthesis, find the lowest precedent operator
    #     delimit = Parser.find_lowest_precedence(tokens)

    #     split_list = []
    #     op_list = []

    #     cur_op = ' '

    #     start = 0
    #     end = 0

    #     while end < len(tokens):
    #         #check if the current tokens are a list of operations
    #         # if tokens[end].type == Scanner.operation:
    #         #     i = end + 1
    #         #     #count how many s

    #         #     while i < len(tokens) and tokens[i].type == Scanner.operation:
    #         #         #add surrounding parenthesis
    #         #         #Token(Scanner.parenthesis, self.text[0])


    #         if tokens[end].type == Scanner.operation and Parser.precedence[tokens[end].value] == delimit:
    #             split_list.append(tokens[start:end])
    #             op_list.append(cur_op)
    #             cur_op = tokens[end].value
    #             start = end + 1

    #         if tokens[end].type == Scanner.parenthesis and tokens[end].value == '(':
    #             end += Parser.find_matching_pair(tokens[end:])

    #         end += 1

    #     split_list.append(tokens[start:end])
    #     op_list.append(cur_op)




    #     if len(split_list[0]) == 0 and op_list[0] == ' ':
    #         del split_list[0]
    #         del op_list[0]


    #     #  #print out the state of the list
    #     # print('before trying to fold multi-operations')
    #     # for op, val in zip(op_list, split_list):
    #     #     print(str(op) + '  ' + str(val))
    #     # print('')


    #     #unfold any multi-operations into their adjacent split_list
    #     for ops, i in zip(op_list, list(range(len(op_list)))):
    #         if len(ops) > 1:
    #             for op in reversed(ops[1:]):
    #                 split_list[i].insert(0, Token(Scanner.operation, op))
    #                 split_list[i].insert(0, Token(Scanner.parenthesis, '('))
    #                 split_list[i].append(Token(Scanner.parenthesis, ')'))
    #                 op_list[i] = ops[0]


    #     operands = []
    #     for val in split_list:
    #         if Parser.check_for_operations(val):
    #             operands.append(Parser.old_split_by_lowest_precedence(val))
    #         else:
    #             val = Parser.remove_outer_parenthesis(val)
    #             assert(len(val) == 1) #there should be only a single value here
    #             operands.append(val[0])

    #     return Old_Chain_Node(Parser.op_class[delimit], operands, op_list)

    #     #for l, o in zip(split_lists, op_list):
    #     #    print(str(o) + ' ' + str(l))

        
    #     #collapse multi ops into a single op
    #     # 5--2 = 5+2
    #     # 5//2 = 5*2
    #     # 5%%2 = invalid?

    
    @staticmethod
    def find_lowest_precedence(tokens):
        """Find the operator that is the lowest precedence in the given list of tokens"""
        
        # if tokens[0].type == Parser.opchain:
        #     return -1 #no precedence level when dealing with opchains

        i = 0
        lowest_precedence = 1000 #infinity
        # print('tokens: ')
        # for t in tokens: print(t)
        while i < len(tokens):
            cur = tokens[i]
            if cur.type == Scanner.operation and Parser.precedence[cur.value] < lowest_precedence:
                lowest_precedence = Parser.precedence[cur.value]
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

    
    # @staticmethod
    # def check_for_operations(tokens):
    #     has_ops = False
    #     for t in tokens:
    #         if t.type == Scanner.operation:
    #             has_ops = True
    #     return has_ops


    # @staticmethod
    # def combine_multi_ops(tokens):
    #     i = 0
    #     while i < len(tokens):
    #         if tokens[i].type == Scanner.operation:
    #             j = i
    #             op = ''
    #             while j < len(tokens) and tokens[j].type == Scanner.operation:
    #                 op += tokens[j].value
    #                 j+=1
                
    #             if j > i:
    #                 #multi-op combine
    #                 t = Token(Scanner.operation, op)
    #                 #t.multi_op = op
    #                 tokens = tokens[:i] + [t] + tokens[j:]
    #         i+=1

    #     return tokens

    
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
    def fold_logical_not_operators(tokens):
        while True: #break out when no folds were made on given pass through the list 
            i = 0
            folds = 0 #number of folds made on a pass
            
            while i < len(tokens) - 1:
                t0 = tokens[i]
                t1 = tokens[i+1]
                if t0.type == Scanner.operation and t0.value == 'not' and t1.type == Scanner.operation and t1.value in ['and', 'or', 'xor', 'nand', 'nor', 'xnor']:
                    folded = {'and':'nand', 'or':'nor', 'xor':'xnor', 'nand':'and', 'nor':'or', 'xnor':'xor'}[t1.value]
                    tokens = tokens[:i] + [Token(Scanner.operation, folded)] + tokens[i+2:]
                    i+=1
                    folds+=1
                i+=1
            
            if folds == 0: 
                break
        return tokens


    # @staticmethod
    # def insert_explicit_math_vals(tokens):
    #     #delimit any instances of multiple math operations with explicit values to make the operations binary
        
    #     #check for if the first item is an operation (i.e. handle unary-like operators at the start of an expression)
    #     if tokens[0].type == Scanner.operation:
    #         tokens = [Scanner.Token(Scanner.number, default_val[tokens[0].val])] + tokens

    #     return NotImplemented

        # start=0
        # end=-1 
        # while start < len(tokens):
        #     if tokens[start].type == Scanner.operation:
        #         end = start
        #         while end+1 < len(tokens) and tokens[end+1].type == Scanner.operation: end+=1
        #         if end != start:
        #             tokens = tokens[:start] + some_func() + tokens[end:]

    @staticmethod
    def tokanize_operation_chains(tokens):
        #convert a sequence of chainable operation tokens into a single binary operation token followed by an opchian token which contains all of the proceeding tokens
        #the binary operation defines the precedence level for the whole chain 
        start=0
        while start<len(tokens):
            if tokens[start].type == Scanner.operation: #opchains start with an operation
                end = start
                oplist = []
                while end+1 < len(tokens) and tokens[end+1].type == Scanner.operation: #find the range of the current chain
                    if tokens[end+1].value not in Left_Unary_Node.operators:
                        raise ValueError('Encountered non-unary operation in chain of operations: ' + str(tokens[end+1].value))
                    end+=1
                    oplist += [tokens[end].value]
                if end != start: # if actually a chain then do the fold
                    tokens = tokens[:start+1] + [Token(Parser.opchain, oplist)] + tokens[end+1:] 
                    start = end #continue from the end of the chain
            start+=1

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



# class Old_Chain_Node:

#     operators = ['+', '-', '*', '/']

#     def __init__(self, op_class=('+', '-'), operands=[], op_list=[]):
#         self.op_class = op_class      #class of operations, e.g. (+-) (*/%) (^)
#         self.operands = operands    #list of elements in this particular node.
#                                     #e.g. [('+', 10 kg), ('-', 5 kg), ('-', 3 kg), ('+', 4 kg)]
#                                     #all operations from the chain must be in the operation class
#         self.op_list = op_list

#         if len(operands) != len(op_list):
#             print('Op list: ' + str(op_list))
#             print('Operands: ' + str(operands))
#             print(operands[0])
#             raise ValueError('Parser Error: Operation and Operand lists are not the same length')

#         for op, i in zip(op_list, list(range(0,len(op_list)))):
#             # if op == ' ':
#             #     op_list[i] = op_class[0]
#             #     op = op_class[0]

#             if op not in op_class and op != ' ':
#                 raise ValueError('Parser Error: Unexpected operation in op list. expected from class ' + str(op_class) + '. Found: (' + op + ')')

#     def __str__(self):
#         tab = 4 # how many spaces make a tab 

#         #header of the string
#         s = '('
#         for op in self.op_class:
#             s = s + op
#         s = s + ')\n'

#         for val, op in zip(self.operands, self.op_list):
#             s = s + op + ' ' #s.append('(' + op + ') ')
#             if type(val) == Old_Chain_Node:
#                 temp = str(val) #potentially insert a tab at the start
#                 i = 0
#                 while i < len(temp):
#                     if temp[i] == '\n':
#                         temp = temp[:i+1] + ' ' * tab + temp[i+1:] #insert a tab
#                     i+=1
#                 s += temp
#             else:
#                 s = s + str(val) #val should be a single value/token

#             s = s + '\n'

#         return s[:-1]


#     def evaluate(self):
#         result = Parser.default_val[self.op_list[0]]

#         if len(self.operands) == 1:
#             op = self.op_list[0]
#             v = self.operands[0]
#             if type(v) == Old_Chain_Node:
#                 v = v.evaluate()
#             elif type(v) == Token and (v.type == Scanner.number or v.type == Scanner.unit):
#                 v = v.value
#             else:
#                 raise ValueError('Evaluation Error: unknown type for evaluation: ' + repr(v) + 'with operation ' + op)

#             if op in Parser.unit_op_decode:
#                 op = Parser.unit_op_decode[op]

#             if op == ' ' or op == '+' or op == '*':
#                 return v
#             elif op == '-':
#                 return -v
#             elif op == '/':
#                 return 1/v
#             elif op == '%' or op == '^':
#                 raise ValueError('Evaluation Error: cannot apply operation ' + op + ' to ' + str(v) + ' without a left hand side')
#             else:
#                 raise ValueError('Evaluation error: Unrecognized operation in class ' + str(self.op_class) + '. Found: ' + op)


#         for op, v in zip(self.op_list, self.operands):
#             if type(v) == Old_Chain_Node:
#                 v = v.evaluate()
#             elif type(v) == Token and (v.type == Scanner.number or v.type == Scanner.unit):
#                 v = v.value
#             else:
#                 raise ValueError('Evaluation Error: unknown type for evaluation: ' + repr(v) + 'with operation ' + op)


#             if op in Parser.unit_op_decode:
#                 op = Parser.unit_op_decode[op]

#             #     if v.format == 'INT':
#             #         v = int(v.value)
#             #     elif v.format == 'REAL':
#             #         v = float(v.value)
#             #     elif v.format == 'HEX':
#             #         v = int(v.value, 0)
#             #     elif v.format == 'BIN':
#             #         v = int(v.value, 0)
#             #     elif v.format == 'PhysicalNumber':
#             #         pass #already in an addable format
#             #     else:
#             #         raise ValueError('Parser Error: Unable to parse value for token with format "' + str(v.format) + '"')


#             if op == ' ':
#                 result = v #space indicates the first value is the result
#             elif op == '+':
#                 result += v
#             elif op == '-':
#                 result -= v
#             elif op == '*' or op == 'm':
#                 result *= v
#             elif op == '/' or op == 'd':
#                 result /= v
#             elif op == '%':
#                 result %= v
#             elif op == '^':
#                 result **= v
#             else:
#                 raise ValueError('Evaluation error: Unrecognized operation in class ' + str(self.op_class) + '. Found: ' + op)

#         return result


#     #CURRENTLY BROKEN. want to be able to operate on physical numbers, not regular numbers
#     #should be basically identical to the regular evaluate function
#     def physical_evaluate(self):

#         #set up default values
#         num_result = Parser.default_val[self.op_list[0]]
#         unit_result = None #(maybe?) different from "no units" which is it's own representation. although now that everything 
#         #needs_init = True if result == -1 else False
#         numeric_op = False #type of op, numeric, or unit

#         for op, val in zip(self.op_list, self.operands):
                
#             #unpack the current value
#             if type(val) == Old_Chain_Node:
#                 v = val.evaluate()
#             else:
#                 if len(val) > 1:
#                     raise ValueError('Parser Error: expected a single value for current item in expression. Found: ' +str(val))

#                 v = val[0] #get the token
                
#                 #consider setting up a dictionary of functions here where the key is the format string
#                 if v.type == Scanner.number:
#                     numeric_op = True

#                     if v.format == 'INT':
#                         v = int(v.value)
#                     elif v.format == 'REAL':
#                         v = float(v.value)
#                     elif v.format == 'HEX':
#                         v = int(v.value, 0)
#                     elif v.format == 'BIN':
#                         v = int(v.value, 0)
#                     else:
#                         raise ValueError('Parser Error: Unable to parse value for token with format "' + str(v.format) + '"')
#                 elif v.type == Scanner.unit:
#                     numeric_op = False
#                     v = v.value


#             # if needs_init:
#             #     result = v
#             #     needs_init = False
#             # else:

#             #apply the current value based on the correct operation
#             #in each of these, we would check the units
#             if numeric_op: #current operationg on numbers
#                 result = num_result
#             else:
#                 result = unit_result

#             if op == ' ':
#                 result = v #space indicates the first value is the result
#             elif op == '+':
#                 result += v
#             elif op == '-':
#                 result -= v
#             elif op == '*':
#                 result *= v
#             elif op == '/':
#                 result /= v
#             elif op == '%':
#                 result %= v
#             elif op == '^':
#                 result **= v
#             else:
#                 raise ValueError('Evaluation error: Unrecognized operation in class ' + str(self.op_class) + '. Found: ' + op)



#         return result



class Left_Unary_Node:
    """Node in the AST for left unary operations (e.g. -5, /3, not false, etc)"""

    operators = ['not', '+', '-', '*', '/', 'm', 'd']
    #note that +,-,*,/ are only unary if the left-hand-side is not a number (e.g. it is an operator) 

    def __init__(self, op, expr):#, type, val=None, lhs=None, rhs=None):
        self.op = op
        self.expr = expr

    def __str__(self):
        return '(' + self.op.value + ')\n' + tab_multiline_string(str(self.expr)) + '\n'

    def __repr__(self):
        return '(' + self.op.value + ')\n' + tab_multiline_string(repr(self.expr)) + '\n'


    def evaluate(self):
        #only acceptable type for this is "not"
        op = self.op.value
        expr = self.expr


        if op == '+' or op == '*' or op == 'm':
            return expr.evaluate()

        elif op == '-':
            expr = expr.evaluate()
            if isinstance(expr, Unit):
                return PhysicalNumber(-1, exponent=0, unit=expr)
            else:
                return -expr
        
        elif op == '/' or op == 'd':
            expr = expr.evaluate()
            if isinstance(expr, Unit):
                return PhysicalNumber(1, exponent=0, unit=(Unit()/expr).unit)
            else:
                return 1/expr
        
        elif op == 'not':
            expr = expr.evaluate()
            if isinstance(expr, bool):
                return not expr
            else:
                return ~expr

class Right_Unary_Node:
    """Node in the AST for right unary opartions (e.g. [1 2 3 4 5]' )"""

    operators = ["'"] #so far, just the transpose operator

    def __init__(self, expr, op):
        return NotImplemented

    def __str__(self):
        return NotImplemented

    def __repr__(self):
        return NotImplemented

    def evaluate(self):
        return NotImplemented

# class Chain_Node:
#     """Node in the AST for chainable unary operations"""

#     operators = ['+', '-', '*', '/']

#     def __init__(self):
#         pass

#     def __str__(self):
#         pass

#     def __repr__(self):
#         pass

#     def evaluate(self):
#         pass


class Binary_Node:
    """Node in the AST for binary operations"""

    operators = ['%', '^', 'and', 'or', 'xor', 'nand', 'nor', 'xnor', '<<', '>>', '<<<', '>>>', '<<<!', '!>>>', '=?', 'not?', '>?', '>=?', '>?', '>=?', 'in?', '+', '-', '*', '/', 'd', 'm']

    def __init__(self, op, lhs, rhs):
        self.op = op
        self.lhs = lhs
        self.rhs = rhs

    def __str__(self):
        return '(' + self.op.value + ')\n' + tab_multiline_string(str(self.lhs)) + '\n' + tab_multiline_string(str(self.rhs)) + '\n'

    def __repr__(self):
        return '(' + self.op.value + ')\n' + tab_multiline_string(repr(self.lhs)) + '\n' + tab_multiline_string(repr(self.rhs)) + '\n'


    def evaluate(self):
        op = self.op.value
        lhs = self.lhs
        rhs = self.rhs

            # lhs_eval = lhs.evaluate()
            # rhs_eval = rhs.evaluate()
            # print('\nEvaluating: ' + repr(lhs_eval) + ' ' + op + ' ' + repr(rhs_eval) + '\n')
            # result = lhs_eval >> rhs_eval
            # print('result: ' + repr(result))
            # return result
        
        if op == '%': return lhs.evaluate() % rhs.evaluate()
        elif op == '^': return lhs.evaluate() ** rhs.evaluate()
        elif op == '+': return lhs.evaluate() + rhs.evaluate()
        elif op == '-': return lhs.evaluate() - rhs.evaluate()
        elif op == '*': return lhs.evaluate() * rhs.evaluate()
        elif op == '/': return lhs.evaluate() / rhs.evaluate()
        elif op == 'd': return lhs.evaluate() / rhs.evaluate()
        elif op == 'm': return lhs.evaluate() * rhs.evaluate()
        elif op == '<<': return lhs.evaluate() << rhs.evaluate()
        elif op == '>>': return lhs.evaluate() >> rhs.evaluate()
        elif op == '<<<': return NotImplemented #lhs.evaluate() ** rhs.evaluate()
        elif op == '>>>': return NotImplemented #lhs.evaluate() ** rhs.evaluate()
        elif op == '<<<!': return NotImplemented #lhs.evaluate() ** rhs.evaluate()        
        elif op == '!>>>': return NotImplemented #lhs.evaluate() ** rhs.evaluate()
        elif op == '=?': return lhs.evaluate() == rhs.evaluate()
        elif op == 'not?': return lhs.evaluate() != rhs.evaluate()
        elif op == '>?': return lhs.evaluate() > rhs.evaluate()
        elif op == '>=?': return lhs.evaluate() >= rhs.evaluate()
        elif op == '<?': return lhs.evaluate() < rhs.evaluate()
        elif op == '<=?': return lhs.evaluate() <= rhs.evaluate()
        elif op == 'in?': return lhs.evaluate() in rhs.evaluate()
        elif op in ['and', 'or', 'xor', 'nand', 'nor', 'xnor']: # for short circuiting, there should be checking for if the rhs returns a boolean as well
            lhs = lhs.evaluate()
            if isinstance(lhs, bool):
                #Short Circuit if possible
                #insert some sort of check to confirm the output width of rhs is also a boolean
                if op == 'and' and not lhs: return lhs
                elif op == 'or' and lhs: return lhs
                elif op == 'nand' and not lhs: return not lhs
                elif op == 'nor' and lhs: return not lhs

            #either the op couldn't short circuit, or lhs wasn't a bool
            rhs = rhs.evaluate()
            if isinstance(lhs, bool) and isinstance(rhs, bool):
                if op == 'and': return lhs and rhs
                elif op == 'or': return lhs or rhs
                elif op == 'xor': return lhs != rhs
                elif op == 'nand': return not (lhs and rhs)
                elif op == 'nor': return not (lhs or rhs)
                elif op == 'xnor': return not (lhs != rhs)

            #nither lhs nor rhs were booleans. requires python's bitwise operations
            #verify that we are operating on ints first -> real values should throw an error
            if isinstance(lhs, bool): lhs = int(lhs) #convert booleans to integers for bitwise operation
            if isinstance(rhs, bool): rhs = int(rhs)

            if op == 'and': return lhs & rhs
            elif op == 'or': return lhs | rhs
            elif op == 'xor': return lhs ^ rhs
            elif op == 'nand': return ~ (lhs & rhs)
            elif op == 'nor': return ~ (lhs | rhs)
            elif op == 'xnor': return ~ (lhs ^ rhs)

            raise ValueError('None of the booleans returned...\nlhs: ' + repr(lhs) + '\nrhs: ' + repr(rhs))





class Leaf_Node:
    """Single atomic values in the AST"""

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return repr(self.value)

    def evaluate(self):
        return self.value


def tab_multiline_string(string):
    insert = '|   '
    string = insert + string
    i = len(insert)
    while i < len(string):
        if string[i] == '\n':
            string = string[0:i+1] + insert + string[i+1:]
        i = i + 1
    return string


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
                    print(str(p))
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