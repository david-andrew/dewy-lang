# Meta Programming
> Note: This will probably not be relevant until the current handwritten parser is replaced with a parser generator (probably GLL)

Eventually, the goal is for the language to be completely described via some sort of syntax description, such as a context-free grammar. There was work on this in the past, but it was paused in favor of building a usable version of the language first. When there is a suitable parser-generator implementation of the language, one of the planned features is to include the syntax description language within Dewy itself for metaprogramming purposes. Users could describe new syntax features via the metalanguage, and then be able to use them in their programs.

Here's an example of the previous work on the metalanguage:

```
% This is a description of the metalanguage written in the metalanguage itself

#eps = 'ϵ' | '\\e' | "''" | '""' | "{}";                    % ϵ, \e, '', "", or {} indicates empty element, i.e. nullable
#wschar = [\n\x20];                                         % ascii whitespace characters (restrict to newlines and spaces).
#line_comment = '/\/' '\n'~* / '\n'~;                       % single line comment
#block_string = ξ* - ξ* '}/';                               % inside of a block comment. Cannot end with block comment delimiter
#block_comment = '/\{' (#block_comment | #block_string)* '}/';       % block comment, with allowed nested block comments
#ws = (#wschar | #line_comment | #block_comment)*;          % optional whitespace sequence
#anyset = '\\' [uUxX] | [VUξ];                              % V, U, ξ, \U, \u, \X, or \x used to indicate any unicode character
#hex = '\\' [uUxX] [0-9a-fA-F]+ / [0-9a-fA-F];              % hex number literal. Basically skipping the number part makes it #any
#number = [0-9]+ / [0-9];                                   % decimal number literal. Used to indicate # of repetitions
#charsetchar = ξ - [\-\[\]] - #wschar;                      % characters allowed in a set are any unicode excluding '-', '[', or ']', and whitespace
#item = #charsetchar | #escape | #hex;                      % items that make up character sets, i.e. raw chars, escape chars, or hex chars
#charset = '[' (#ws #item (#ws '-' #ws #item)? #ws)+ ']';   % set of chars specified literally. Whitespace is ignored, and must be escaped.

%paired grouping operators
#group = '(' #ws #expr #ws ')';                             % group together/force precedence
#char = '"' (ξ - '"' | #escape | #hex) '"';                 % "" single character
#char = "'" (ξ - "'" | #escape | #hex) "'";                 % '' single character
#caseless_char = "{" (ξ - [{}] | #escape | #hex) "}";       % {} single character where case is ignored
#string = '"' (ξ - '"' | #escape | #hex)2+ '"';             % "" string of 2+ characters
#string = "'" (ξ - "'" | #escape | #hex)2+ "'";             % '' string of 2+ characters
#caseless_string = "{" (ξ - [{}] | #escape | #hex)2+ "}";   % {} string of 2+ characters where case is ignored for each character
#escape = '\\' ξ;                                           % an escape character. Recognized escaped characters are \n \r \t \v \b \f \a.
                                                            % all others just put the second character literally. Common literals include \\ \' \" \[ \] \-

%post operators
#capture = #expr #ws '.';                                   % group to capture
#star = #expr #ws (#number)? #ws '*';                       % zero or (number or more)
#plus = #expr #ws (#number)? #ws '+';                       % (number or one) or more
#option = #expr #ws '?';                                    % optional
#count = #expr #ws #number;                                 % exactly number of
#compliment = #set #ws '~';                                 % compliment of. equivalent to #any - #set

%implicit operators
#cat = #expr (#ws #expr)+;                                  % concatenate left and right

%binary expr operators
#or = (#expr #ws '|' #ws #expr) - #union;                   % left or right expression
#reject = (#expr #ws '-' #ws #expr) - #diff;                % reduce left expression only if it is not also the right expression
#nofollow = #expr #ws '/' #ws #expr;                        % reduce left expression only if not followed by right expression
#greaterthan = #expr #ws '>' #ws #expr;                     % left expression has higher precedence than right expression

%binary set operators
#diff = #set #ws '-' #ws #set;                              % everything in left that is not in right
#intersect = #set #ws '&' #ws #set;                         % intersect of left and right
#union = #set #ws '|' #ws #set;                             % union of left and right

%syntax constructs
#set = #anyset | #char | #caseless_char | #hex | #charset | #compliment | #diff | #intersect | #union;
#expr = #eps | #set | #group | #capture | #string | #caseless_string | #star | #plus | #option | #count | #cat | #or | #greaterthan | #lessthan | #reject | #nofollow | #hashtag;
#hashtag = '#' [a-zA-Z] [a-zA-Z0-9_]* / [a-zA-Z0-9_];
#rule = #hashtag #ws '=' #ws #expr #ws ';';
#grammar = (#ws #rule)* #ws;
#start = #grammar;
```


If/when a metalanguage is added to Dewy, it will likely look much different than this. Current drawbacks of this syntax are:
- difficulties describing expression precedence and associativity
- difficulties handling ambiguity that may arise from the grammar
- verbosity of handling whitespace/comments
- some incompatibility of the metalanguage with Dewy syntax. Ideally metalanguage expressions would be valid Dewy expressions
- currently no process for the semantic results of parsed rules

Something more ideal may make use of string prefix functions

```dewy
(meta)r'''
    #rule = #hashtag '=' #expr ';' => { /{semantics for handling the rule}/ };
'''
```

Or perhaps a syntax constructed explicitly from valid Dewy expressions

```dewy
#rule = #hashtag, '=', #expr, ';' => { /{semantics for handling the rule}/ }
```
