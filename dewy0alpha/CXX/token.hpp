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
        comment,        // '//'
        whitespace,     // ' '
        number,         // '5'
        boolean,        // 'true'
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
        {number, "number"},
        {boolean, "boolean"},
        {operation, "operation"},
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



private:
    token_type type;
    string value;

};


//ostream & operator<<(ostream &Str, Token const &v);


#endif