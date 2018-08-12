#ifndef TOKEN_HPP
#define TOKEN_HPP

#include <iostream>
#include <sstream>
#include <string>
#include <map>

using namespace std;

class Token
{

public:
    enum token_type 
    {                   // Examples
        comment,        // '//' or '/{ }/'
        whitespace,     // ' '
        keyword,        // 'loop', 'set', 'transmute', etc.
        number,         // '5'
        boolean,        // 'true' 'false'
        str_literal,    // "string example" or 'string example'
        operation,      // '+'
        opchain,        // '^/'
        unit,           // 'kg'
        separator,      // ';' or ',' 
        parenthesis,    // '()'
        bracket,        // '{}'
        brace,          // '[]'
        identifier,     // 'var_name'
        eof,
    };

        //to print the name of the token out
    map<token_type, string> token_to_string
    {
        {comment, "comment"},
        {whitespace, "whitespace"},
        {keyword, "keyword"},
        {number, "number"},
        {boolean, "boolean"},
        {str_literal, "string"},
        {operation, "operation"}, //should be operator, but that is a C++ reserved word
        {opchain, "opchain"},
        {unit, "unit"},
        {separator, "separator"},
        {parenthesis, "parenthesis"},
        {bracket, "bracket"},
        {brace, "brace"},
        {identifier, "identifier"},
        {eof, "eof"}
    };
    
    Token(token_type type, string value);
    token_type get_type();
    string get_value();
    string str();
    //To-Do: write a method for getting a string from the token i.e. cout << Token() works properly. see: https://stackoverflow.com/questions/5171739/tostring-override-in-c

    //public so anything working with tokens can see what's inside
    token_type type;
    string value;

//private: //nothing is private
    

};


//ostream & operator<<(ostream &Str, Token const &v);


#endif