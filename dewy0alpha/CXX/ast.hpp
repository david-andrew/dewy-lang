#ifndef AST_HPP
#define AST_HPP

class AST
{
public:
	//public functions and members
	AST() {}
	virtual string str() { return "{Base AST Class}"; }
	//string evaluate(); //return the string of the result evaluated. This should probably actually return a custom class that is values (or a base class of values) in Dewy

//private:
	//private functions and members
};

ostream & operator<<(ostream &Str, AST &a)
{
	Str << a.str();
	return Str;
}

#endif