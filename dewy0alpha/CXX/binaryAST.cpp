#ifndef BINARYAST_CPP
#define BINARYAST_CPP


#include "ast.hpp"
#include "utilities.cpp"
#include <string>


using namespace std;



class BinaryAST : public AST
{
public:
	//public members
	BinaryAST(AST* lhs, string op, AST* rhs)
	{
		this->lhs = lhs;
		this->op = op;
		this->rhs = rhs;
	}

	string str()
	{
		//return the string for the binary ast
		return "(" + op + ")\n" + tab_multiline_string(lhs->str()) + "\n" + tab_multiline_string(rhs->str()) + "\n";
	}


public:
	//private members
	AST* lhs;
	AST* rhs;
	string op;



};



#endif