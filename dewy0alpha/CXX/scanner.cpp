#include "scanner.hpp"
#include "utilities.cpp"
#include "token.cpp"


#include <iostream>
using namespace std;

Scanner::Scanner() {}

vector<Token> Scanner::scan(string to_scan) 
{
	//cout << to_scan << endl;
	tokens = vector<Token>();

	//compute the tokens list
	tokens.push_back(Token(Token::identifier, to_scan));
	tokens.push_back(Token(Token::identifier, "banana"));
	tokens.push_back(Token(Token::identifier, "peach"));
	tokens.push_back(Token(Token::identifier, "pear"));
	return tokens;
}

// #include <iostream>
// using namespace std;

int main() //maybe make this a member function of scanner, so that in the future, whatever program can select between the correct main to run based on selection of scanner, parser, interpreter, compiler, etc.
{
	string line;
	vector<Token> tokens = vector<Token>();
	Scanner s = Scanner();
	
	//run the interpreter
	cout << "dewy0alpha C++ Scanner" << endl << "Type \"help\" for more information" << endl;
	while (true) 
	{
		//to make proper interpreter: https://stackoverflow.com/questions/7469139/what-is-equivalent-to-getch-getche-in-linux
		cout << ">>> ";
		getline(cin, line);
		
		//handle EOF signal
		if (cin.eof()) { cout << endl; break; }
		
		//scan the tokens
		tokens = s.scan(line);
		cout << tokens << endl;
		// for (Token t : tokens)
		// {
		// 	cout << t << endl;
		// }

	}

	return 0;
}