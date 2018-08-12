#ifndef UTILITIES_CPP
#define UTILITIES_CPP

//utilities function.
//mostly for quality of life function like pythons 'in' check
#include <string>

using namespace std;

//I think these should eventually be overloaded to take a string and compare it to a list of strings
//e.g. python's ability to do: 'car' in ['plane', 'train', 'automobile']

bool equals(char c1, char c2, bool ignore_case=false)
{
	//determine if two characters are equal. If ignore case is true, then both chars are set to uppercase
	return (ignore_case)? (toupper(c1)==toupper(c2)) : (c1==c2);
}

bool equals(string s1, string s2, bool ignore_case=false)
{
	if (s1.length() != s2.length()) return false;
	for (int i=0; i<s1.length(); i++)
		if (!equals(s1[i], s2[i], ignore_case))
			return false;

	return true;
}

bool in(string sub, string whole, bool ignore_case=false)
{
	//return whether or not the string sub is somewhere in the string whole
	if (sub.length() > whole.length()) return false;

	int offset=0;
	int difference = whole.length() - sub.length();
	
	while (offset <= difference)
	{
		int i=0;
		while (i < sub.length() && equals(sub[i], whole[offset+i], ignore_case)) { i++; }
		if (i == sub.length()) { return true; } else { offset++; }
	}

	return false;
}

bool in(char sub, string whole, bool ignore_case=false)
{ 
	//wrappers for chars as the substring
	string s(1, sub);
	return in(s, whole, ignore_case);
}



bool left(string sub, string whole, bool ignore_case=false)
{
	//return whether or not the string sub is at the start of the string whole
	if (sub.length() > whole.length()) return false;
	for (int i=0; i<sub.length(); i++)
	{
		if (!equals(sub[i], whole[i], ignore_case)) return false;
	}
	return true;
}

bool left(char sub, string whole, bool ignore_case=false) 
{ 
	//wrapper for chars as the substring
	string s(1,sub);
	return left(s, whole, ignore_case); 
}


bool right(string sub, string whole, bool ignore_case=false)
{
	//return whether or not the string sub is at the end of the string whole
	if (sub.length() > whole.length()) return false;
	
	int offset = whole.length() - sub.length();
	for(int i=sub.length()-1; i>=0; i--)
	{
		if (!equals(sub[i], whole[i+offset], ignore_case)) return false;
	}
	return true;
}

bool right(char sub, string whole, bool ignore_case=false)
{
	//wrapper for chars as the substring
	string s(1, sub);
	return right(s, whole, ignore_case);
}



// bool isalnum(string str, int index)
// {
// 	//check if the character at i is alpha numeric
// 	return i >= str.length() || isalnum(str[i]); //call c++ al
// }

#endif