#include "scanner.hpp"
#include "utilities.cpp"
#include "token.cpp"


#include <iostream>
using namespace std;

//To-Do:
// - parse units, keywords, separators, all other operators
// - combine loop keyword with previous or following block based on whitespace
// - write an eat_string() method (both single and double quoted strings)
// - write peek functions (or no_eat/peek bool that can be passed in) so that you can check if the next token is a certain type without eating it
// - make it so that numbers don't store the _ unless it's a digit. (i.e. the digits strings in the headers shouldn't include _)
// - look into making the scanner class/operations static

Scanner::Scanner() {}

void Scanner::interpreter()
{
    //run an interactive interpreter for the scanner

    string input;
    vector<Token> output;
    
    //run the interpreter
    cout << "dewy0alpha C++ Scanner" << endl << "Type \"help\" for more information" << endl;
    while (true) 
    {
        //to make proper interpreter: https://stackoverflow.com/questions/7469139/what-is-equivalent-to-getch-getche-in-linux
        //up recalls previous commands (saved to file for multiple session persistence)
        //ctrl-d quits the interpreter
        //ctrl-c does what? python emit keyboard interrupt? quit program? something else?
        cout << ">>> ";
        getline(cin, input);
        
        //handle EOF signal
        if (cin.eof()) { cout << endl; break; }
        
        //scan the tokens
        try
        {
            output = scan(input);
            //cout << tokens << endl; //alternate display all tokens
            for (Token t : output)
            {
                cout << t << endl;
            }
        }
        catch (int e) {} //do nothing, just start over
    }
}

vector<Token> Scanner::scan(string input) 
{
    //cout << to_scan << endl;
    text = input;               //set current text being operated on
    tokens = vector<Token>();   //reset the tokens vector

    //initial pass with scanner
    while (text.length() > 0) //scan until there is no more input text
    {
        //Note that it is very important what order tokens are eaten in. In general, longer more specific tokens should be eaten first, while shorter or more generic tokens should be eaten last especially if their contained in any of the longer tokens

        //currently commented are not critical for the skeleton implementation
        if (eat_single_comment()) continue;
        if (eat_multi_comment()) continue;
        if (eat_string()) continue;
        if (eat_whitespace()) continue;
        if (eat_number()) continue;
        if (eat_boolean()) continue;
        //if (eat_unit()) continue; //requires a semi-complicated implementation. perhaps this will be moved to the parser, and units become identifiers in this step
        if (eat_brackets()) continue;
        if (eat_operator()) continue;
        if (eat_keyword()) continue;
        if (eat_identifier()) continue;

        //nothing was eaten this loop
        //this should probably throw an exception rather than just print out the error
        if (text.length() > 0)
        {
            cout << "Error, no recognized tokens on pass.\nRemaining input: \"" << text << "\"" << endl;
            return tokens;//NULL;//throw 10; //currently codes don't mean anything
        }
        break; //does this need to be here? it should never be reached...
    }

    //merge any whitespace based delimits (namely loop{do} vs {do}loop vs {do}loop{do})
    //delimit_whitespace();

    remove_generic_token(Token::whitespace);    //remove whitespace tokens
    remove_generic_token(Token::comment);       //remove comment tokens

    return tokens;
}


bool Scanner::eat_single_comment()
{
    if (left("//", text))
    {
        int i=2;
        while (text.length() > i && text[i++] != '\n');
        tokens.push_back(Token(Token::comment, text.substr(0, i-1))); //don't include the newline in the comment
        text = text.substr(i, text.length()-i);
        return true;
    }
    else
    {
        return false;
    }
}

bool Scanner::eat_multi_comment()
{
    //allow nesting of multiline comments
    if (left("/{", text))
    {
        int count=1; //number of opening multiline comments
        int i=2;
        while (count!=0 && i<text.length()) //while not all parenthesis have been matched
        {
            if (left("/{", text.substr(i, text.length()-i))) 
            {
                count++;
                i+=2;
            }
            else if (left("}/", text.substr(i, text.length()-i))) 
            {
                count--;
                i+=2;
            }
            else
            {
                i++;
            }
            //currently doesn't place nice with escaped /{ inside of strings. To-Do: write method to scan to the end of a string literal
        }
        if (count!=0)
        {
            cout << "Error: multiline comment has no matching closing delimiter" << endl;
            return false;
            //throw 10;
        }
        else
        {
            tokens.push_back(Token(Token::comment, text.substr(0, i)));
            text = text.substr(i, text.length()-i);
            return true;
        }
    }
    else
    {
        return false;
    }
    // cout << "eat_multi_comment is not implemented yet" << endl;
    // return false;
}

bool Scanner::eat_whitespace()
{
    return eat_generic_whitespace("\n")    //newline
        || eat_generic_whitespace(" ")     //space
        || eat_generic_whitespace("\t")    //tab
        || eat_generic_whitespace("\r");   //carriage return
 }

bool Scanner::eat_generic_whitespace(string space)
{
    int i=0;
    while(left(space, text))
    {
        tokens.push_back(Token(Token::whitespace, space));
        text = text.substr(1, text.length()-1);
        i++;
    }
    return i > 0;
}


bool Scanner::eat_number()
{
    return eat_generic_number(binary_digits, "0b", binary_prefixed)
        || eat_generic_number(quaternary_digits, "0q", quaternary_prefixed)
        || eat_generic_number(seximal_digits, "0s", seximal_prefixed)
        || eat_generic_number(octal_digits, "0o", octal_prefixed)
        || eat_generic_number(decimal_digits, "0d", decimal_prefixed)
        || eat_generic_number(dozenal_digits, "0z", dozenal_prefixed)
        || eat_generic_number(hexadecimal_digits, "0x", hexadecimal_prefixed)
        || eat_generic_number(tetrasexagesimal_digits, "0t", tetrasexagesimal_prefixed);
}


bool can_ignore_case(string digits)
{
    //helper function for Scanner::eat_generic_number()
    //check if there are any occurances of both upper and lower case versions of letters. If so, case cannot be ignored
    for (int i=0; i<digits.length(); i++)
        for (int j=i+1; j<digits.length(); j++)
            if (toupper(digits[i]) == toupper(digits[j]))
                return false;
    return true;
}


int scan_digits(string text, string &num, int &i, string digits)
{
    bool ignore_case = can_ignore_case(digits); //base 64 cannot ignore case. Unless otherwise set, all others can ignore case.
    if (i<text.length() && !in(text[i], digits, ignore_case)) return false; //numbers must start with one of their digits. no underscores unless base 64
    
    //find the end index of all digits in the given text, starting at index i
    //append each digit (non '_') onto the string num
    while (i < text.length() && (in(text[i], digits, ignore_case) || text[i] == '_')) //underscores allowed as separators
    {
        if (text[i] != '_' || digits.length() == 64) //normally _ is a number separater (e.g. 0010_1010_1110_0110) but tetrasexagesimal uses them as digits 
            num += ((ignore_case)? toupper(text[i]) : text[i]);
        i++;
    }
}


// EBNF:    number = [prefix], { digits | "_" }, [ ".", { digits | "_" } ], [("e" | "E" | " e " | " E "), ["+" | "-"], { digits | "_" } ]
//          prefix = "0b" | "0q" | "0s" | "0o" | "0d" | "0z" | "0x" | "0t"
//          digits are the digits of that base, e.g. 01, 0123, 012345, 01234567, 0123456789, 01234567890XE, 0123456789ABCDEF, etc.
//          digits are matched to the prefix, or if no prefix then the default
//          the exponential notation e/E must be space delimited if either e or E appear in digits (i.e. dozenal, hexadecimal, and tetrasexagesimal), otherwise space delimiting is optional
// examples of binary numbers: 0b011011001e11011, and 0b0010_1010_0011_1111 E 1011_1011_0010_0000, 0b01101_0011.1011e-1110_1001
bool Scanner::eat_generic_number(string digits, string prefix, bool prefixed)
{
    //check for a number (base is specified by the digits string) in the current text. 
    //If prefixed is true, then the number must start with the prefix specified with prefix, otherwise it may be just a free number

    int i;      //keep track of the current character being checked in text (current text being parsed by scanner)
    string num; //store the number without any separaters '_'

    //check if the current text starts with a prefix. prefix may be optional, depending on the default base
    if (!left(prefix, text))
        if (prefixed) return false; //current text is not a number
        else i=0;                   //scanning for number without prefix
    else i=2;                       //scanning for number with prefix

    num.append(prefix);             //all number tokens begin with their proper prefix

    //check for number before decimal point
    //this updates num and i by reference
    scan_digits(text, num, i, digits);

    //check for decimal point and fractional component
    if (i < text.length() && text[i] == '.')
    {
        int temp_i = i;
        temp_i++;
        string tentative = "."; //string for holding the possible additions to the number
        scan_digits(text, tentative, temp_i, digits);
        if (temp_i > i+1)
        {
            //add the new section onto the num string
            num.append(tentative);
            i = temp_i;
        }
        //else not actually a decimal number (don't commit the changes). The period might be some other operator
    }


    // check for scientific notation number E or e. note that if either e or E are in the list of digits, spaces are required between the number and E/e
    {
        bool space_optional = !in("e", digits) && !in("E", digits);
        if ((i+2 < text.length() && text[i] == ' ' && in(text[i+1], "eE") && text[i+2] == ' ') ||   //spaces between E, e.g. 12345 E 12 vs 12345E12
            (space_optional && i < text.length() && in(text[i], "eE")) )
        {
            bool has_space = text[i] == ' ';
            int temp_i = i;
            temp_i += (has_space)? 3 : 1; //add the width of e with or without spaces
            string tentative = (space_optional)? "e" : " e ";   //string for holding the possible additions to the number

            //check for +/-
            if (temp_i < text.length() && (text[temp_i] == '+' || text[temp_i] == '-') )
            {
                tentative += text[temp_i];
                temp_i++;
            }

            scan_digits(text, tentative, temp_i, digits);

            //check for decimal point and fractional component in the exponent of the number
            if (temp_i < text.length() && text[temp_i] == '.')
            {
                //even more tentative decimal section after exponent section
                int temp_temp_i = temp_i;
                temp_temp_i++;
                string tentative_tentative = "."; //string for holding the possible additions to the number
                scan_digits(text, tentative_tentative, temp_temp_i, digits);
                if (temp_temp_i > temp_i+1)
                {
                    //add the new section onto the tentative string
                    tentative.append(tentative_tentative);
                    temp_i = temp_temp_i;
                } //else don't commit changes
            }


            if (temp_i > (i + (has_space? 3 : 1))) //is actually scientific notation 
            {
                //commit the tentative changes
                num.append(tentative);
                i = temp_i;

                
            }
        }
    }

    //if we actually have a number (i.e. scanned more than 0 digits, and the following text is not alphanumeric)
    if ((i > (prefixed? 2 : 0)) && (i >= text.length() || !in(text[i], alphanumeric_characters)))
    {
        tokens.push_back(Token(Token::number, num));
        text = text.substr(i, text.length()-i);
        return true;
    }
    else
    {
        return false;
    }
}


bool Scanner::eat_boolean()
{
    for (string b : boolean_literals)
    {
        if (left(b, text, true)) //ignore boolean case
        {
            tokens.push_back(Token(Token::boolean, b));
            text = text.substr(b.length(), text.length()-b.length());
            return true;
        }
    }
    return false;
}


bool Scanner::eat_unit()
{
    //this requires the units class to be implemented
    cout << "eat_unit is not implemented yet" << endl;
    return false;
}


bool Scanner::eat_brackets()
{
    return eat_generic_bracket("()", Token::parenthesis)
        || eat_generic_bracket("[]", Token::bracket) 
        || eat_generic_bracket("{}", Token::brace);
        // eat_generic_bracket("<>", Token::chevron); //possible chevron brackets may be added to language. maybe for inner products
}


bool Scanner::eat_generic_bracket(string brackets, Token::token_type type)
{
    if (in(text[0], brackets))
    {
        string s(1, text[0]); //create string from character
        tokens.push_back(Token(type, s));
        text = text.substr(1, text.length()-1);
        return true;
    }
    else
    {
        return false;
    }
}


bool Scanner::eat_operator()
{
    return eat_generic_operator(question_operators)
        || eat_generic_operator(logical_operators)
        || eat_generic_operator(shift_operators)
        || eat_generic_operator(assignment_operators)
        || eat_generic_operator(dictionary_operators)
        || eat_generic_operator(handle_operators)
        || eat_generic_operator(list_operators)
        || eat_generic_operator(separators, Token::separator) //not technically an operator
        || eat_generic_operator(dot_operators)
        || eat_generic_operator(matrix_operators)
        || eat_generic_operator(math_operators); //last because these are the shortest
}


bool Scanner::eat_generic_operator(vector<string> operators, Token::token_type type)
{
    for (string op : operators)
    {
        if (left(op, text, true)) //operators (namely the word ones) are case insensitive
        {
            tokens.push_back(Token(type, op));
            text = text.substr(op.length(), text.length()-op.length());
            return true;
        }
    }
    return false;
}


bool Scanner::eat_identifier()
{
    if (in(text[0], alpha_characters))
    {
        int i=1;
        while (i<text.length() && in(text[i], alphanumeric_characters)) { i++; }
        tokens.push_back(Token(Token::identifier, text.substr(0, i)));
        text = text.substr(i, text.length()-i);
        return true;
    }
    else
    {
        return false;
    }
}

bool Scanner::eat_string()
{
    bool single_quote; //true for single quote type, false for double quote type
    if (text[0] == '\'' || text[0] == '\"')
    {
        single_quote = text[0] == '\'';
        int i=1;
        bool closed = false;
        while (!closed && i<text.length())
        {
            if (text[i] == ((single_quote)? '\'' : '\"')) { closed = true; }
            else if (text[i] == '\\') { i++; } //escape character. skip the character after it
            else if (text[i] == '{') //beginning of an expression block. skip to the close of the block
            {
                int stack = 1;
                while(++i<text.length() && stack != 0)
                {
                    if (text[i] == '{') stack++;
                    else if (text[i] == '}') stack--;
                }
            }
            i++;
        }

        if (!closed)
        {
            cout << "Error: unclosed string literal." << endl;
            return false;
            //throw 10;
        }

        //good string
        tokens.push_back(Token(Token::str_literal, text.substr(0, i)));
        text = text.substr(i, text.length()-i);
        return true;
    }
    else
    {
        return false;
    }

}

bool Scanner::eat_keyword()
{
    for (string keyword : keywords)
    {
        if (left(keyword, text))
        {
            tokens.push_back(Token(Token::keyword, keyword));
            text = text.substr(keyword.length(), text.length()-keyword.length());
            return true;
        }
    }
    return false;

}

void Scanner::remove_generic_token(Token::token_type type)
{
    //remove all whitespace tokens from the list of tokens
    int i=0;
    while (i<tokens.size())
    {
        if (tokens[i].type == type)
            tokens.erase(tokens.begin() + i);
        else
            i++;
    }
}