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
    

public:
    Scanner();
    vector<Token> scan(string to_scan);



};




#endif