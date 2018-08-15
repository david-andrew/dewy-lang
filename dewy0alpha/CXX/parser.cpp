#ifndef PARSER_CPP
#define PARSER_CPP



#include "parser.hpp"
#include "scanner.cpp"
//#include "unaryAST.cpp"
#include "binaryAST.cpp"
//#include "booleanAST.cpp"
#include "integerAST.cpp"
//#include "stringAST.cpp"
//#include "realAST.cpp"
//#include "functionAST.cpp"


Parser::Parser()
{
	//create the precedence map from the op_class map
	for (auto& pair : op_class)
	{
		for (string op : pair.second)
		{
			precedence.insert({op, pair.first});
		}
	}

	// cout << "{";
	// for (auto& pair : precedence)
	// {
	// 	cout << "\'" << pair.first << "\':" << pair.second << ", ";
	// }
	// cout << "}" << endl;


	///////stuff for testing/////////
	vector<AST*> asts;

	// asts.push_back(new IntegerAST(7864876,32));
	// cout << "string: " << asts[0]->str() << endl;

	IntegerAST i1 = IntegerAST(836836,32);
	IntegerAST i2 = IntegerAST(465,16,true);
	IntegerAST i3 = IntegerAST(43453546, 64);
	BinaryAST bin1 = BinaryAST(&i1, "+", &i2);
	BinaryAST bin2 = BinaryAST(&i3, "*", &bin1);

	asts.push_back(&i1);
	asts.push_back(&i2);
	asts.push_back(&i3);
	asts.push_back(&bin1);
	asts.push_back(&bin2);

	
	for (AST* t : asts)
	{
		cout << *t << endl << endl;
	}



}

void Parser::interpreter()
{
	//Interactive interpreter for the parser


	string input;
	vector<Token> tokanized_input;
	vector<AST> output;

	Scanner s = Scanner();

	cout << "dewy0alpha C++ Parser" << endl << "Type \"help\" for more information" << endl;
	while (true)
	{
		cout << ">>> ";
		getline(cin, input);

		//handle eof signal
		if (cin.eof()) { cout << endl; break; }

		//try to scan the input
		try
		{
			tokanized_input = s.scan(input);
		}
		catch (int e) 
		{ 
			cout << "Error: unable to parse because input scan threw an error" << endl;
		}

		try
		{
			output = parse(tokanized_input);
			for (AST t : output)
			{
				cout << t << endl;
			}
		}
		catch (int e) {} //let the context display the error
	}
}

vector<AST> Parser::parse(vector<Token> tokens)
{
	vector<AST> trees = vector<AST>();
	return trees;
}



bool Parser::match_all_parenthesis()
{
	//check the tokens stream to make sure all parenthesis have matching pairs
	cout << "match_all_parenthesis() is not yet implemented" << endl; 
	return false;
}

void Parser::insert_explicit_unit_ops()
{
	//any instances of a unit next to a number become the unit*that number

	//may need to have the scanner insert a special token for newlines so that this function knows which tokens are actually adjacent to each other
	cout << "insert_explicit_unit_ops() is not yet implemented" << endl;
}


void Parser::fold_logical_not_operators()
{
	//any instance of not followed by a logical operator becomes the inverse version of that oeprator
	//e.g. 'not and' -> 'nand', 'not xor' -> 'xnor', etc.
	//also some comparison operators can be inverted
	//e.g. 'not >?' -> '<=?', 'not =?' -> 'not?', etc. (some don't do anything, e.g. 'not in?' has no single function inverse)

	cout << "fold_logical_not_operators() is not yet implemented" << endl;
}


void Parser::tokanize_operation_chains()
{
	//convert any strings of operation tokens into a single opchain token

	cout << "tokanize_operation_chains() is not yet implemented" << endl;
}


void Parser::raise_unit_precedence()
{
	//swap out multiplication and division between units with higher precedence versions of the operations
	//this is to ensure that units get combined first

	cout << "raise_unit_precedence() is not yet implemented" << endl;
}


//this may actually need a pair method. This one creates just ASTs, and the other one creates the vector of ASTs using this one
AST Parser::create_ast(vector<Token> tvec)
{
	//recursive function for generating an abstract syntax tree from a list of tokens
	cout << "create_ast() is not yet implemented" << endl;
}

#endif