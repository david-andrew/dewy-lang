//run the dewy project based on the provided input
//command line arguments can specify scanner (-s), parser (-p), interpreter (-i), compiler (-c)
//if none of the above are specified, the default is the furthest progress on the project (i.e. at the moment it would be the scanner)
//command line can also specify a filename which contains source dewy code to operate on
//other optional command line arguments (to be determined)
#include <fstream>
#include "scanner.cpp"
//#include "parser.cpp"
//#include "interpreter.cpp"
//#include "compiler.cpp"
#include "utilities.cpp"

using namespace std;

int main(int argc, char* argv[])
{
	//dewy [-s | -p | -i | -c] [file] [-t] [-v]
	// -s runs the scanner
	// -p runs the parser
	// -i runs the interpreter
	// -c runs the compiler
	// none of these runs the most recent (currently the scanner)
	// [file] is an optional source file to run through the program.
	// if no file is specified, the program enters interpreter mode
	// -t will print out the parse tree
	// -v indicates verbose mode (does nothing at the moment)

	//default settings
	int mode=0; // 0:scanner, 1:parser, 2:interpreter, 3:compiler
	char* filename = NULL;
	string contents = "";
	bool tree = false;
	bool verbose = false;

	if (argc > 1) //then assign options based on the arguments
	{
	    for (int i=1; i<argc; i++)
	    {
	    	string arg(argv[i]);
	        if (equals(arg, "-s"))
	        	mode=0;
	        else if (equals(arg, "-p"))
	        	mode=1;
	        else if (equals(arg, "-i"))
	        	mode=2;
	        else if (equals(arg, "-c"))
	        	mode=3;
	        else if (equals(arg, "-t"))
	        	tree = true;
	        else if (equals(arg, "-v"))
	        	verbose = true;
	        else
	        	filename = argv[i]; //filename is the only other possible option
	    }

	    if (filename != NULL)
	    {
	    	ifstream f(filename);
	    	stringstream buffer;
	    	buffer << f.rdbuf();
	    	contents = buffer.str();
	    }
	}


	switch (mode)
	{
		case 0:	//scanner mode 
		{
			Scanner s = Scanner();
			if (contents.length() != 0)
			{
				//run file through scanner
			    vector<Token> tokens;
			    try
			    {
			    	tokens = s.scan(contents);
			    }
			    catch (int e) {} //don't do anything about errors
			    for (Token t : tokens) //print out tokens returned
			            cout << t << endl;
			}
			else
			{
				//run interpreter mode
				s.interpreter();
			}
			break;
		}

		
		case 1: //parser mode
		{
			//To-Do: implement the parser
			break;
		}

		
		case 2: //interpreter mode
		{
			//To-Do: implement the interpreter
			break;
		}

		
		case 3: //compiler mode
		{
			//To-Do: implement the compiler
			break;
		}
	}




}