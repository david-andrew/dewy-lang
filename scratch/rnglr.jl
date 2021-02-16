#simple attempt at an RNGLR parser in python

#syntax definition formatting notes
#each rule must be on a single line
#no parenthesis in rules. parenthesis must be implied by nested sub rules
#literals are single characters/numbers



txt1 = """
#decimal_digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9';
#decimal_prefix = '0D' | '0d';
#decimal_digit_string = #decimal_digit, {#decimal_digit | '_'};
#decimal_natural = [#decimal_prefix], #decimal_digit_string;
#decimal_rational = #decimal_natural, '.', #decimal_digit_string;
#decimal_floating_point = (#decimal_rational | #decimal_natural), [('e'|'E'), ['-'|'+'], (#decimal_rational | #decimal_natural)];

#decimal_number = #decimal_natural | #decimal_rational | #decimal_floating_point;

#yotta_symbol = 'Y'; #yotta_name = 'yotta';
#zetta_symbol = 'Z'; #zetta_name = 'zetta';
#exa_symbol   = 'E'; #exa_name   = 'exa';
#peta_symbol  = 'P'; #peta_name  = 'peta';
#tera_symbol  = 'T'; #tera_name  = 'tera';
#giga_symbol  = 'G'; #giga_name  = 'giga';
#mega_symbol  = 'M'; #mega_name  = 'mega'; 
#kilo_symbol  = 'k'; #kilo_name  = 'kilo';
#centi_symbol = 'c'; #centi_name = 'centi';
#milli_symbol = 'm'; #milli_name = 'milli';
#micro_symbol = 'u' | 'μ'; #micro_name = 'micro';
#nano_symbol  = 'n'; #nano_name  = 'nano';
#pico_symbol  = 'p'; #pico_name  = 'pico';
#femto_symbol = 'f'; #femto_name = 'femto';
#atto_symbol  = 'a'; #atto_name  = 'atto';
#zepto_symbol = 'z'; #zepto_name = 'zepto';
#yocto_symbol = 'y'; #yocto_name = 'yocto';
#prefix_symbol = #yotta_symbol | #zetta_symbol | #exa_symbol | #peta_symbol | #tera_symbol | #giga_symbol | #mega_symbol | #kilo_symbol | #centi_symbol | #milli_symbol | #micro_symbol | #nano_symbol | #pico_symbol | #femto_symbol | #atto_symbol | #zepto_symbol | #yocto_symbol;
#prefix_name = #yotta_name | #zetta_name | #exa_name | #peta_name | #tera_name | #giga_name | #mega_name | #kilo_name | #centi_name | #milli_name | #micro_name | #nano_name | #pico_name | #femto_name | #atto_name | #zepto_name | #yocto_name;
#gram_symbol    = 'g';   #gram_name    = 'gram';             #gram_plural    = 'grams';
#metre_symbol   = 'm';   #metre_name   = 'meter' | 'metre';  #metre_plural   = 'meters' | 'metres';
#second_symbol  = 's';   #second_name  = 'second';           #second_plural  = 'seconds';
#ampere_symbol  = 'A';   #ampere_name  = 'ampere' | 'amp';   #ampere_plural  = 'amperes' | 'amps';
#kelvin_symbol  = 'K';   #kelvin_name  = 'kelvin';
#mole_symbol    = 'mol'; #mole_name    = 'mole' | 'mol';     #mole_plural    = 'moles' | 'mols';
#candela_symbol = 'cd';  #candela_name = 'candela';          #candela_plural = 'candelas';
#unit_symbol = #gram_symbol | #metre_symbol | #second_symbol | #ampere_symbol | #kelvin_symbol | #mole_symbol | #candela_symbol;
#unit_name = #gram_name | #metre_name | #second_name | #ampere_name | #kelvin_name | #mole_name | #candela_name;
#unit_plural = #gram_plural | #metre_plural | #second_plural | #ampere_plural | #mole_plural | #candela_plural;
#unit = ([#prefix_symbol], #unit_symbol) | ([#prefix_name], (#unit_name | #unit_plural));


#lowercase_letter = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' 
    | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z';
#uppercase_letter = 'A'| 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J' | 'K' | 'L' 
    | 'M' | 'N' | 'O' | 'P' | 'Q' | 'R' | 'S' | 'T' | 'U' | 'V' | 'W' | 'X' | 'Y' | 'Z';
#symbols = '~' | '!' | '@' | '#' | '\$' | '&' | '_' | '?'; 
#identifier = (#uppercase_letter | #lowercase_letter | '_'), {#uppercase_letter | #lowercase_letter | #decimal_digit | #symbols };

#hashtag = '#', #identifier;

#reserved_word = 'loop' | 'if' | 'else' | 'return' | 'in' | 'as' | 'transmute' | 'continue' | 'break' | 'exit' | 'quit' | 'yield' | 'constant' | 'symbol';

#whitespace = ' ';
#string_content = { #lowercase_letter | #uppercase_letter | #symbols | #decimal_digit | #whitespace };
#string = ('"', #string_content, '"') | ("'", #string_content, "'");

#number_range = #decimal_number, {#whitespace}, ':', {#whitespace}, #decimal_number;
#string_range = #string, {#whitespace}, ':', {#whitespace}, #string;
#range_body = #number_range | #string_range;
#range = (('(' | '['), {#whitespace}, #range_body, {#whitespace}, (')' | ']')) | #range_body;


#lex(#identifier)
#lex(#unit)
#lex(#reserved_word)
#lex(#decimal_number)
#lex(#string)
#lex(#range)
#lex(#function)

"""


txt2 = """
#expr = #expr '+' #expr | #expr '*' #expr | #number;
#number = #digit {#digit | '_'};
#digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9';
"""

#select rules text to read
txt = txt2


abstract type Body end

struct Rule
    name::AbstractString
    body::Body
end

struct Or <: Body
    options::Vector{Body}
end
struct Cat <: Body
    sequence::Vector{Body}
end
struct Repeat <: Body
    inner::Body
    #count::Integer
end
struct Option <: Body
    inner::Body
end
struct Nonterminal <: Body
    name::AbstractString
end
struct Terminal <: Body
    char::Char
end
function Terminal(s::AbstractString)::Cat
    Cat([Terminal(c) for c in s]::Vector{<:Body})  
end

function newrule(str::AbstractString)::Rule
    middle = findfirst("=", str).start
    left = str[1:middle-1] |> strip
    right = str[middle+1:end] |> strip
    @assert(left[1] == '#')

    return Rule(left, newruleinner(right))
end

const pairs = [
    ('(', ')', s->true, s -> newruleinner),
    ('[', ']', s->true, s -> newruleinner |> Option),
    ('{', '}', s->true, s -> newruleinner |> Repeat),
    ('\'', '\'', s->findall("'", s) |> length == 2, s -> Terminal(s)),
    ('"', '"', s->findall("\"", s) |> length == 2, s -> Terminal(s)),
]

function newruleinner(str::AbstractString)::Body
    #handle outermost parenthesis/brackets
    #recusively call on inner
    #split top level OR
    #for each in split, recursively call on
    #handle direct sequencing
    
    str = strip(str)
    println(str)
    
    if length(str) == 0 || length(str) == 1
        throw("cannot construct rule from string \"$str\"")
    else
        #check each rule with outer grouping
        for (l, r, cond, constructor) in pairs
            if str[1] == l && str[end] == r && cond(str)
                return constructor(str[2:end-1])
            end
        end

        #check if Or is top level
        orlist = split(str, '|')
        if length(orlist) > 1
            return Or([optstr |> newruleinner for optstr in orlist]::Vector{<:Body})
        end

        #check if Cat is top level
        catlist = split(str, (' ', ','))
        if length(catlist) > 1
            return Cat([itemstr |> newruleinner for itemstr in catlist]::Vector{<:Body})
        end

        #check if reference is top level
        if str[1] == '#'
            return Nonterminal(str)
        end
    end

    throw("Could not process rule string $str")

end



function readrules()::Vector{Rule}
    rules = Vector{Rule}()
    rulelines = filter(s -> s |> length > 0, split(replace(txt, "\n"=>""), ';'))
    for line in rulelines
        push!(rules, newrule(line))
    end

    return rules
end


myrules = readrules()
for rule in myrules
    println(rule)
end