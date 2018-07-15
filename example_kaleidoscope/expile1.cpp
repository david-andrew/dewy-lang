//example compiler for the kaleidoscope toy language using the LLVM
//#include "llvm/ADT/STLExtras.h"
#include <algorithm>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <memory>
#include <string>
#include <vector>




// Lexer
enum Token
{
  tok_eof = -1,

  //commands
  tok_def = -2,
  tok_extern = -3,

  // primary
  tok_identifier = -4,
  tok_number = -5
};

//bad practice, using globals for variables holding values
static std::string IdentifierStr; //stored if tok_identifier
static double NumVal;             //stored if tok_number


//return the next token from standard input
static int gettok()
{
  static int LastChar = ' ';

  //skip whitespace
  while (isspace(LastChar))
    LastChar = getchar();

  //check for "def" or "extern" keywords or identifiers
  if (isalpha(LastChar))
  {
    IdentifierStr = LastChar;

    //get characters until the next space
    while (isalnum(LastChar = getchar()))
      IdentifierStr += LastChar;

    if (IdentifierStr == "def")
      return tok_def;
    if (IdentifierStr == "extern")
      return tok_extern;
    return tok_identifier;
  }

  // check for numbers/floats
  if (isdigit(LastChar) || LastChar == '.')
  {
    std::string NumStr;
    do
    {
      NumStr += LastChar;
      LastChar = getchar();
    } while (isdigit(LastChar) || LastChar == '.');

    NumVal = strtod(NumStr.c_str(), 0);
    return tok_number;
  }


  //check for strings
  if (LastChar == '#')
  {
    //comment until the end of the line
    do
      LastChar = getchar();
    while (LastChar != EOF && LastChar != '\n' && LastChar != '\r');

    //no token for strings, so return next token
    if (LastChar != EOF)
      return gettok();
  }


  //check for End Of File
  if (LastChar == EOF)
    return tok_eof;


  //anything else, return the ASCII value of the character
  int ThisChar = LastChar;
  LastChar = getchar();
  return ThisChar;

 
}



//base class for all experssion nodes
class ExprAST
{
public:
  virtual ~ExprAST(){}
};

//Expression class for all numeric literals e.g. "1.0"
class NumberExprAST : public ExprAST
{
  double Val;

public:
  NumberExprAST(double Val) : Val(Val) {}
};


//expression class for referencing a variable, e.g. "a"
class VariableExprAST : public ExprAST
{
  std::string Name;

public:
  VariableExprAST(const std::string &Name) : Name(Name) {}
};


//expression class for binary operator, e.g. "+"
class BinaryExprAST : public ExprAST
{
  char Op;
  std::unique_ptr<ExprAST> LHS, RHS;

public:
  BinaryExprAST(char op, std::unique_ptr<ExprAST> LHS, std::unique_ptr<ExprAST> RHS) : Op(op), LHS(std::move(LHS)), RHS(std::move(RHS)) {}
};


//expression class for function calls
class CallExprAST : ExprAST
{
  std::string Callee;
  std::vector<std::unique_ptr<ExprAST>> Args;

public:
  CallExprAST(const std::string &Callee, std::vector<std::unique_ptr<ExprAST>> Args) : Callee(Callee), Args(std::move(Args)) {}
};


//prototype for a function which captures the function name, and the argument names
class PrototypeAST
{
  std::string Name;
  std::vector<std::string> Args;

public:
  PrototypeAST(const std::string &name, std::vector<std::string> Args) : Name(name), Args(std::move(Args)) {}

  const std::string &getName() const { return Name; }
};


//actual function definition class
class FunctionAST
{
  std::unique_ptr<PrototypeAST> Proto;
  std::unique_ptr<ExprAST> Body;

public:
  FunctionAST(std::unique_ptr<PrototypeAST> Proto, std::unique_ptr<ExprAST> Body) : Proto(std::move(Proto)), Body(std::move(Body)) {}
};



//simple token buffer. CurTok is the current token. getNextToken reads the next token into the buffer and stores it to CurTok
static int CurTok;
static int getNextToken()
{
  return CurTok = gettok();
}


//helper function for handling errors
std::unique_ptr<ExprAST> LogError(const char *Str)
{
  fprintf(stderr, "LogError: %s\n", Str);
  return nullptr;
}
std::unique_ptr<PrototypeAST> LogErrorP(const char *Str)
{
  LogError(Str);
  return nullptr;
}



int main(){return 0;}
