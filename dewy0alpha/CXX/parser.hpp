#ifndef PARSER_HPP
#define PARSER_HPP

#include "token.hpp"
#include "ast.hpp"
#include <string>
#include <vector>
#include <map>

using namespace std;

class Parser
{
private:
	vector<Token> tokens;
	//AST ast; //abstract syntax tree

	//internal methods
	bool match_all_parenthesis();
	void insert_explicit_unit_ops();
	void fold_logical_not_operators();
	void tokanize_operation_chains();
	void raise_unit_precedence();
	//void parse_physical_numbers();
	static AST create_ast(vector<Token> tvec);
	static vector<AST> create_ast_vec(vector<Token> tvec);

public:
	Parser();
	vector<AST> parse(vector<Token> input);
	void interpreter(); //uses Scanner.cpp


	map<int, vector<string>> op_class
	{
		{0, {"="}},
		{1, {"=?", "not?", ">?", ">=?", "<?", "<=?", "in?"}},
		{2, {":"}}, //not sure if this is the best level of precedence. maybe slightly higher
		{3, {"and", "or", "xor", "not", "nand", "nor", "xnor"}},
		{4, {"!>>>", "<<<!", ">>>", "<<<", ">>", "<<"}},
		{5, {"+", "-"}},
		{6, {"*", "/", "%"}},
		{7, {"m", "d"}},
		{8, {"^"}},
		{9, {"!"}},
		//{10, {}}, attribute access or call, e.g. a.b, a(b), a[b]. Not an actual precedence split, but these go here
		{11, {"@"}},
		//{12, {}}, ternary if else if else
		//{13, {}}, parenthesis grouping ()
		//{14, {}}, block grouping {}
	};


#define left_to_right true
#define right_to_left false

	map<int, bool> op_class_associativity
	{
		{0, left_to_right},
		{1, left_to_right},
		{2, left_to_right},
		{3, left_to_right},
		{4, right_to_left},
		{5, left_to_right},
		{6, left_to_right},
		{7, left_to_right},
		{8, right_to_left},
		{9, left_to_right}, //not sure if this makes sense for unary only operators
		//{10, },
		{11, right_to_left}, //again not sure if this makes sense for unary only operators
		//{12, },
		//{13, },
		//{14, },
	};

	map<string, int> precedence; //instantiated in Parser() constructor

	map<string, string> default_val
	{
		{"+", "0d0"}, {"-", "0d0"}, {"*", "0d1"}, {"/", "0d1"}, {"m", "0d1"}, {"d", "0d1"}
	};

	map<string, string> unit_op_encode { {"*", "m"}, {"/", "d"} };
	map<string, string> unit_op_decode { {"m", "*"}, {"d", "/"} };


};


#endif