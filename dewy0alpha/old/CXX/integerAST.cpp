#ifndef INTEGERAST_CPP
#define INTEGERAST_CPP

#include "ast.hpp"

#include <string>

using namespace std;

class IntegerAST : public AST
{
public:
	IntegerAST(int value, int width=-1, bool u=false)
	{
		this->value = value;
		this->width = width;
		this->u = u;
	}

	//string str() { return to_string(value); }

	string str()
	{
		return ((u)? "uint":"int") + ((width!=-1)?to_string(width):"") + "(" + to_string(value) + ")";
	}

protected:
	int value;
	int width;
	bool u;	//unsigned

};




#endif