#ifndef SCANNER_HPP
#define SCANNER_HPP

#include "token.hpp"
#include <string>
#include <vector>

using namespace std;

//Scanner class for dewy0alpha interpreter
class Scanner
{
private:
    string text;
    vector<Token> tokens;

    //methods for scanning different allowed tokens in the language
    bool eat_single_comment();
    bool eat_multi_comment();
    
    bool eat_whitespace();
    bool eat_generic_whitespace(string space);
    bool eat_newline();
    bool eat_space();
    bool eat_tab();
    bool eat_carriage_return();
    
    bool eat_number(); //calls all of the above eat_<base>_number();
    bool eat_generic_number(string digits, string prefix, bool prefixed);
    
    bool eat_boolean();
    bool eat_unit();
    
    bool eat_brackets(); // (), {}, [], and maybe <>
    bool eat_generic_bracket(string brackets, Token::token_type type);

    bool eat_operator(); //calls all of the above eat_<type>_operator();
    bool eat_generic_operator(vector<string> operators, Token::token_type type = Token::operation);

    bool eat_identifier();

    bool eat_string();

    bool eat_keyword();

    bool eat_hashtag();

    //others to be added
    //bool eat_conditional();
    //bool eat_separator(); //e.g. ',' and ';'
    //bool eat_handle(); //e.g. @some_func, but really just the @-sign
    //bool eat_assignment(); //probably just =-sign. any compound assignment (+=, <?=, xor=, etc.) are combined later
    //bool eat_elementwise_dot(); // as in [1 2 3 4] .+ 4, though what about member access: foo.bar?
    //bool eat_string(); //eats the whole string. any special expressions in an escape {} block are scanned/parsed later

    //...

    void remove_generic_token(Token::token_type type);

    

public:
    Scanner();
    vector<Token> scan(string input);
    void interpreter();


    string alpha_characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_";
    string alphanumeric_characters = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_";

    //note that these are not const because a program can update them at compile time with settings
    //e.g. set dozenal_digits = "0123456789AB" would change the digits that dozenal uses
    //also set default_base = dozenal would set the prefixed variables so dozenal is false, and all others are true
    string binary_digits = "01";
    bool binary_prefixed = true;
    string quaternary_digits = "0123";
    bool quaternary_prefixed = true;
    string seximal_digits = "012345";
    bool seximal_prefixed = true;
    string octal_digits = "01234567";
    bool octal_prefixed = true;
    string decimal_digits = "0123456789";
    bool decimal_prefixed = false;
    string dozenal_digits = "1234567890XE";  //including lower and upper case letters
    bool dozenal_prefixed = true;
    string hexadecimal_digits = "0123456789ABCDEF"; // including lower and upper case letters
    bool hexadecimal_prefixed = true;
    string tetrasexagesimal_digits = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ@_";
    const bool tetrasexagesimal_prefixed = true; //not allowed to be non-prefixed, because it would be impossible to create identifiers then

    //All of these are case insensitive
    vector<string> math_operators = {"+", "-", "*", "/", "%", "^", "!"};
    vector<string> logical_operators = {"and", "or", "xor", "not", "nand", "nor", "xnor"};
    vector<string> shift_operators = {"<<<!", "!>>>", "<<<", ">>>", "<<", ">>"};
    vector<string> question_operators = {"=?", "not?", ">?", ">=?", "<?", "<=?", "in?" , "?"};
    vector<string> assignment_operators = {"="};
    vector<string> dictionary_operators = {"<->", "->", "<-"};
    vector<string> handle_operators = {"@"};//, "#"}; //reference handles, and hashtags. hashtags come with the identifier, while handles are an operation on an identifier
    vector<string> list_operators = {":", "..."};
    vector<string> separators = {",", ";"};
    vector<string> dot_operators = {"."};
    vector<string> matrix_operators = {"`"}; //transpose operator

    vector<string> boolean_literals = {"true", "false"};
    vector<string> keywords = {"if", "else", "loop", "continue", "break", "match", "return", "in", "as", "transmute", "set", "settings", "yield", "pass", "run", "exit", "const"}; //others to be added
    vector<string> datatypes = {"int", "uint", "real", "complex", "quaternion", "bool", "dec"};
    vector<string> datasizes = {"1", "2", "4", "8", "16", "32", "64", "128", "256"}; //note that not all sizes can match all datatypes. arbitrary precision is gained by not specifying a size
    //vector<string> short_base_units = {}; //this should go in the units class
    //vector<string> builtin_functions = {"ln", "sin", "cos", };    //these belong in the parser
    //vector<string> builtin_identifiers = {"_", "pi", "e" };       //these belong in the parser

};




#endif