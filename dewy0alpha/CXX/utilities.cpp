#ifndef UTILITIES_CPP
#define UTILITIES_CPP

//utilities function.
//mostly for quality of life function like pythons 'in' check
#include <string>

using namespace std;

bool in(string sub, string whole)
{
	//return whether or not the string sub is somewhere in the string whole
	if (sub.length() > whole.length()) return false;

	int offset=0;
	int difference = whole.length() - sub.length();
	
	while (offset <= difference)
	{
		int i=0;
		while (i < sub.length() && sub[i] == whole[offset+i]) { i++; }
		if (i == sub.length()) { return true; } else { offset++; }
	}

	return false;
}

bool left(string sub, string whole)
{
	//return whether or not the string sub is at the start of the string whole
	if (sub.length() > whole.length()) return false;
	for (int i=0; i<sub.length(); i++)
	{
		if (sub[i] != whole[i]) return false;
	}
	return true;
}

bool right(string sub, string whole)
{
	//return whether or not the string sub is at the end of the string whole
	if (sub.length() > whole.length()) return false;
	
	int offset = whole.length() - sub.length();
	for(int i=sub.length()-1; i>=0; i--)
	{
		if (sub[i] != whole[i+offset]) return false;
	}
	return true;
}


#endif