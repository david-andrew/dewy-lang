import sys
from scanner import Scanner
from scanner import Token


#TODO:
#  1. parser convert tokens to a better (probably still intermediate) representation (e.g. units, numbers)
#  2. combine all unit appended to a number into a single token "united_number"
#     i.e. run a parsing pass on all unit expressions that occur after numbers, convert to unit expr from #1
#  3. other combinations?
#  4. parsing pass for all current tokens (what? is this just run the parser as in lang0 mode?) 



class Parser:
    """Class for constructing the Abstract Synatax Tree from a list of tokens"""

    #define precedence levels for operators here
    precedence = {'+':1, '-':1, '*':2, '/':2, '%':2, '^':3}
    level_ops = {1:'+-', 2:'*/%', 3:'^log'} # list of all operations on a given precedence level
    default_op = {1:'+', 2:'*', 3:'^'}      # what is the default operation for a given precedence level
    
    
    def __init__(self, tokens):
        self.tokens = tokens
        self.ast = [] #list of lists, where each successive dimension indicates how manay layers deep the element is in the tree

        #might construct multiple ASTs that are then linked together
        #e.g. self.ast_sequence = [] #list of ASTs in sequence of the program

    def __str__(self):

        if len(self.ast) > 0:
            #nice AST printout according to below
            return Parser.print_tree2(self.ast)
        else:
            return 'RAW TOKENS LIST:\n' + str(self.tokens)


                
    @staticmethod
    def print_tree2(ast, level=0, string=''):
        #first thing in an AST has to be an op token
        if type(ast[0]) != Token:
            raise ValueError('AST requires first element to be an operation')

        string += '(' + Parser.level_ops[Parser.precedence[ast[0].value]] + ')\n'

        #if type(ast[1]) == list or ast[1].type == Scanner.number:
        #    ast.insert(1, Token(Scanner.operation, '#'))

        if ast[0].value not in Parser.precedence:
            ast.insert(1, Token(Scanner.operation, '_'))
        else:
            ast.insert(0, Parser.level_ops[Parser.precedence[ast[0].value]])
            
        #print(ast)
            
        if type(ast[1]) != list:
            i=1
            while i < len(ast):
                string += '  ' * (level + 1) + ast[i].value + ' '
                if type(ast[i+1]) == list:
                    string += Parser.print_tree2(ast[i+1], level+1)
                else:
                    string += str(ast[i+1].value) + '\n'
                    
                i+=2
            
        else: #it is a list
            string += Parser.print_tree2(ast, level + 1)

        return string

    

    def __repr__(self):
        if len(self.ast) > 0:
            return 'ABSTRACT SYNTAX TREE:\n' + str(self.ast)
        else:
            return 'RAW TOKENS LIST:\n' + str(self.tokens)
            

    def parse(self):
        self.ast = Parser.split_by_lowest_precedence(self.tokens)
        #self.tokens = None

        #other parsing steps

        return self.ast
        pass




    #currently operating only on numbers and operations. units will be done when they have a finalized representation
    @staticmethod #maybe refactor into find_lowest_precedence(tokens), and split_by_precedence(tokens, precedence_level)
    def split_by_lowest_precedence(tokens):
        #split tokens list into lists of lists of tokens, delimited by the operator with the lowest precedence

        #ensure that all parenthesis have a proper match
        Parser.match_all_parenthesis_pairs(tokens)            


        #check for (potentially multiple layers of) parenthesis wrapping whole thing
        while tokens[0].type == Scanner.parenthesis and tokens[0].value == '(' and Parser.find_matching_paren(tokens) == len(tokens) - 1:
            tokens = tokens[1:-1]
            #print('parenthesis reduction!')

            
        #this may change depending on how the recursive call should work
        if len(tokens) == 1:
            return tokens[0]
            
        #find lowest precedence operation in token list
        i = 0;
        lowest_precedence = 1000
        while i < len(tokens):
            cur = tokens[i]
            if cur.type == Scanner.operation:
                if Parser.precedence[cur.value] < lowest_precedence:
                    lowest_precedence = Parser.precedence[cur.value]

            elif cur.type == Scanner.parenthesis and cur.value == '(':
                #skip to next matching closed parenthesis
                i += Parser.find_matching_paren(tokens[i:])
                
            i+=1

        if lowest_precedence == 1000:
            raise SyntaxError('No operation found in current precedence layer')
        
        #print('lowest precedence: level '+ str(lowest_precedence) + ' (' + Parser.level_ops[lowest_precedence] + ')')


        

        start = 0
        end = 1
        split_tokens = []

        
        if tokens[0].type != Scanner.operation:
            tokens = [Token(Scanner.operation, Parser.default_op[lowest_precedence])] + tokens
        
        elif Parser.precedence[tokens[0].value] != lowest_precedence:
            raise SyntaxError('operation of wrong precedence found in current token stream. Expecting only level ' + str(lowest_precedence) + ' (' + Parser.level_ops[lowest_precedence] + '). Found ' + tokens[0].value)

        #tokens = [Token(Scanner.operation, Parser.level_ops[lowest_precedence])] + tokens

        
        while end < len(tokens):

            #run through as normal
            cur_op = tokens[start]
            while end < len(tokens) and not (tokens[end].type == Scanner.operation and Parser.precedence[tokens[end].value] == lowest_precedence):
                if tokens[end].type == Scanner.parenthesis and cur.value == '(': #probably don't need the second part since we check that all parenthesis matches are correct
                    end += Parser.find_matching_paren(tokens[end:])
                end += 1

            split_tokens += [cur_op, Parser.split_by_lowest_precedence(tokens[start+1:end])]
            #print('split block: (' + cur_op + ', ' + str(tokens[start+1:end]) + ')')

            #reset for potentially next block
            start = end
            end += 1
        


        return split_tokens
        #construct the list of delimited tokens
        #if token[0] != op in lowest precedence, insert 1st the default op

        #record op at current location
        #loop until next op
        #insert containing with first op
        #update i and j to start from next op



        #Essentially this can recursively break an expression into the AST
        

        #var lowest_precedence = infinity
        #read list sequentially
        #skip from open parenthesis to closing parenthesis (unless list is just a parenthesis group, then ignore)
        #if see an operator in the token list, if precedence is lower than lowest, set lowest to current

        #after reading through the list and getting the lowest level
        #split the list using operators of the lowsest level found as delimiters
        
        pass


    @staticmethod
    def find_matching_paren(tokens):
        if not (tokens[0].type == Scanner.parenthesis and tokens[0].value == '('):
            raise ValueError('Expected first token to be open parenthesis. Found: ' + str(tokens[0]))

        count = 1
        i = 0
        while count > 0:
            i += 1

            if i == len(tokens):
                raise ValueError('No matching parenthesis found in token stream')

            cur = tokens[i]
            if cur.type == Scanner.parenthesis:
                if cur.value == '(':
                    count += 1
                elif cur.value == ')':
                    count -= 1
                else:
                    raise ValueError('parenthesis token doesn\'t contain parenthesis value. found:"' + str(cur.value) + '"')

        return i #index of the matching closing parenthesis


    @staticmethod
    def match_all_parenthesis_pairs(tokens):
        #assert that all parenthesis have a match, and their are no closing parenthesis that come first
        count = 0
        for t in tokens:
            if t.type == Scanner.parenthesis:
                if t.value == '(':
                    count += 1
                elif t.value == ')':
                    count -= 1
                else:
                    raise ValueError('parenthesis token doesn\'t contain parenthesis value. found:"' + str(cur.value) + '"')

                if count < 0:
                    raise SyntaxError('unmatched closing parenthesis in expression') #refactor out into a parse error function that says where the error occurred

        if count > 0:
            raise SyntaxError('unmatched opening parenthesis in expression')



if __name__ == "__main__":
    if len(sys.argv) > 1: #input file mode
        
        filename = sys.argv[1]
        tokens = Scanner(open(filename, 'r').read).scan()
        p = Parser(tokens)
        p.parse()
        print(str(p))

    else:  #interpretor mode

        while True:
            string = input('>>> ')
            p = Parser(Scanner(string).scan())
            p.parse()
            print(str(p))
            
