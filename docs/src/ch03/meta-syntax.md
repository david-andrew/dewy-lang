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
