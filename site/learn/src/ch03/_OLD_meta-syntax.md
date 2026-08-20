# Defining a parser in dewy with types

```dewy
# Based on https://github.com/david-andrew/turtles/blob/master/turtles/examples/csv.py
from p'turtles.dewy' import Rule, repeat, at_least, separator, cc
# Rule = (rule:type|Rule) => [
#    let rule = rule
#    longest_match:bool = false
#    # etc. meta settings
# ] | <Rule | Rule>

# CSV grammar as defined by RFC 4180.
# Supports all CSV features: quoted fields, unquoted fields, empty fields, multiple record separators, etc.

BOM = <"\ufeff">  # UTF-8 BOM if present

# --- Record separators (accept CRLF, LF, or CR) ---
CRLF = <"\r\n">
LF = <"\n">
CR = <"\r">

RecordSep = Rule(CRLF | LF | CR)
RecordSep.longest_match = True

# --- Delimiter (default comma) ---
Delim = <",">


# Optional: allow whitespace after delimiter before *next field*
# This mimics a common "skipinitialspace" behavior.
DelimSkipInitialSpace = <["," <'\x20'|'\x09'>...]>  # swallow spaces (0x20) and tabs (0x09) after delimiter


# --- Quoting ---
EscapedQuote = <'""'>  # doubled quote inside a quoted field


# Any char except a double quote. Includes CR/LF, commas, etc.
# (that’s what allows multiline quoted fields)
QuotedChar = <ch:cc"\x00-\x21\x23-\U0010FFFF">   #TBD about this syntax (named literal types)
# capture named value `ch` which is a character class [\x00-\x21\x23-\U0010FFFF]


QuotedField = Rule<['"' content:QuotedFieldContent '"']>
# QuotedField.longest_match = True  # TBD why this was commented out

QuotedFieldContent = Rule<[(EscapedQuote | QuotedChar)...]>
# QuotedFieldContent.longest_match = True  # TBD why this was commented out 
QuotedFieldContent.postconvert = x => x as string

# --- Unquoted fields ---
# Typical CSV: unquoted fields end at delimiter or record separator.
# Also disallow raw quotes in unquoted fields (common strict-ish behavior).
# 
# UnquotedChar matches any character except: comma, newline, CR, and quote.
# This ensures the field naturally stops at delimiters and record separators.
UnquotedChar = <
    ch:<
        cc"\x00-\x09"         # include tabs and control chars except LF/CR       # noqa
        + "\x0B-\x0C"
        + "\x0E-\x21"         # up to '!' (0x21), excludes '"'(0x22)
        + "\x23-\x2B"         # '#'..'+'
        + "\x2D-\U0010FFFF"   # '-'..unicode max (excludes ',' 0x2C)
    >


# UnquotedField: one or more UnquotedChar characters.
# This will naturally stop when it encounters a comma, newline, CR, or quote
# because UnquotedChar excludes those characters.
# Note: we require at_least[1] so that truly empty fields return None from optional[Field]
UnquotedField = <value: [UnquotedChar UnquotedChar...]>
# UnquotedField.longest_match = True
UnquotedField.postconvert = x => x as string

Field = QuotedField | UnquotedField

# --- Records (this is the key part to support empty fields cleanly) ---
# record := [field] (delim [field])*
#
# That means:
#   ""         -> one empty unquoted field (Field present but length 0)
#   ,a,        -> first optional[Field] is missing => leading empty field
#                then ",a" then "," with missing field => trailing empty
#
# We structure this as: first field (optional), then zero or more delimiter+field pairs
Record = <fields: repeat<Field? separator=Delim>>



# --- Top-level file ---
# Structured so separators are required between records, making the grammar unambiguous.
# First record has no leading separator; subsequent records require a separator before them.
# This prevents trailing newlines from creating spurious empty records.

CSV = <
    BOM?
    records: repeat<Record separator=RecordSep>
    RecordSep?  # trailing separator
>

# Variant that allows spaces/tabs after commas (like skipinitialspace):
RecordSkipInitialSpace = <fields: repeat<Field separator=DelimSkipInitialSpace>


CSVSkipInitialSpace = <
    BOM?
    records: repeat<RecordSkipInitialSpace separator=RecordSep>
    RecordSep?  # trailing separator
>
```

----------

> NOTE: below is old and out of date
# Meta Syntax

One of the interesting features of Dewy is that all regular features of the language are bootstrapped out of a much simpler meta language. Using the meta language, you can do anything from define new operators, to (more stuff...), to modifying the syntax rules of the language.

Meta-Dewy as it is called, is basically a modified version of [Extended Backus-Naur Form](https://en.wikipedia.org/wiki/Extended_Backus%E2%80%93Naur_form), with some added features

## Hashtags and Lex Rules

The simplest aspect of Meta-Dewy is the concept of a hashtag

```dewy
$my_hashtag
```

Hashtags are used as identifiers for meta rules, which are used to describe the syntax of the language

```dewy
$digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9';
```

This rule defines how a single digit is any of the numbers from `0-9`. Note that all rules must end with a semicolon. Because the meta language is simpler than Dewy itself, it doesn't contain as many quality of life features.

Lets say we want to define a new number system, say using chinese character. we would build up the rules for numbers like so

```dewy
$ch_digit = '零' | '一' | '二' | '三' | '四' | '五' | '六' | '七' | '八' | '九';
$ch_digit_string = $ch_digit, {$ch_digit};
```

The first rule defines the individual digits to be used, and then the second rule defines a digit string as a sequence of at least 1 digit, concatenated together with a sequence of zero or more digits after it.

Now if we want to be able to write out chinese numbers in our code, we need to the the compiler to include this new rule in the list of rules it uses to define the language. this is accomplished by using the reserved `$lex` hashtag function. Note that the hashtag function does not end with a semicolon.

```dewy
$lex( $ch_digit_string )
```

From now on, the compiler will recognize any sequences of chinese digits as a digit string, and store them in a token which can be used later.

### More Examples of Rules

These examples come directly from the rules used to build the syntax of Dewy up from nothing

#### Decimal Number Rules

```dewy
$decimal_digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9';
$decimal_prefix = '0D' | '0d'; #obviously optional
$decimal_digit_string = $decimal_digit, {$decimal_digit | '_'};
$decimal_natural = [$decimal_prefix], $decimal_digit_string;
$decimal_rational = $decimal_natural, '.', $decimal_digit_string;
$decimal_floating_point = ($decimal_rational | $decimal_natural), [('e'|'E'), ['-'|'+'], ($decimal_rational | $decimal_natural)];

#combine all into a single rule. This is actually not necessary, and will probably make parsing slightly more verbose...
$decimal_number = $decimal_natural | $decimal_rational | $decimal_floating_point;
```

These will identifier numbers like

```dewy
#TODO->examples of numbers that can be scanned by these rules
```

#### Identifiers and Hashtags

```dewy
$lowercase_letter = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l'
    | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z';
$uppercase_letter = 'A'| 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J' | 'K' | 'L'
    | 'M' | 'N' | 'O' | 'P' | 'Q' | 'R' | 'S' | 'T' | 'U' | 'V' | 'W' | 'X' | 'Y' | 'Z';
$symbols = '~' | '!' | '@' | '#' | '$' | '&' | '_' | '?';

$identifier = ($uppercase_letter | $lowercase_letter | '_'), {$uppercase_letter | $lowercase_letter | $decimal_digit | $symbols };

$hashtag = '$', $identifier;
```

and some examples

```dewy
#TODO
```


#### Reserved Words

```dewy
$reserved_word = 'loop' | 'if' | 'else' | 'return' | 'in' | 'as' | 'transmute' | 'continue' | 'break' | 'exit' | 'quit' | 'yield' | 'constant' | 'symbol';
```

which match those words exactly. (TODO->note syntax for case insensitive)

#### Simple Strings

These are strings that ignore any string interpolation

```dewy
$whitespace = ' '; #TODO->other whitespace via hex codes
$string_content = { $lowercase_letter | $uppercase_letter | $symbols | $decimal_digit | $whitespace };
$string = ('"', $string_content, '"') | ("'", $string_content, "'");
```

### Calling $lex with Multiple Rules

The `$lex` hashtag can be called with multiple rules at a time, so that it is easy to add many rules to the compiler all at once. For example, to tell the compiler to scan for each of the rules we just described

```dewy
$lex($identifier $reserved_word $decimal_number $string)
```

Each rule must simply be separated with whitespace. And the body of the `$lex` function call must only contain hashtags

## Parsing Rules

TODO->how is meaning derived from defined rules...
- Parse rule syntax
- action backends, e.g. interpreter, llvm, C source, etc.
- writing backends in C
