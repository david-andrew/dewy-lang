#include "token.hpp"

//To-Do: add support for tokens containing custom classes that the parser creates
// i.e. a bool + check methods for if the token was processed,
// and then a separate member for the parent class of such objects
// This might alternatively just become node classes on their own without tokens


Token::Token(token_type type, string value)
{
	this->type = type;
	this->value = value;
}

Token::token_type Token::get_type()
{
	return type;
}

string Token::get_value() 
{
	return value;
}

string Token::str()
{
	stringstream ss;
	//ss << "Token(" << token_to_string[type] << ", \"" << value << "\")"; //verbose method of printing
	ss << token_to_string[type]; for(int i=ss.str().length(); i<16; i++) ss << " "; ss << value;
	return ss.str();
}

ostream & operator<<(ostream &Str, Token &v)
{
	Str << v.str();
	return Str;
}

ostream & operator<<(ostream &Str, vector<Token> &v)
{
	Str << "[";
	for (Token t : v)
	{
		Str << t << ", " ;
	}
	Str << "]";
	return Str;
}