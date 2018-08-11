#include "token.hpp"


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
	ss << "Token(" << token_to_string[type] << ", \"" << value << "\")";
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