# Parsing

The standard library should make it straightforward to parse from a grammar, as easy as writing a regular expression for simple cases, and powerful enough for a full language.

Intended directions include generating tree-sitter compatible C parsers and hooks that language servers can use. The library surface is not yet determined.

Likely this can actually be modelled after the [turtles library](https://pypi.org/project/turtles/), adapted to use Dewy's type syntnax. Here's a sketch of what a parser for CSV files might look like

```dewy
# Based on https://github.com/david-andrew/turtles/blob/master/turtles/examples/csv.py
from p'turtles.dewy' import Rule, repeat, at_least, separator, cc
# Rule = (rule:type|Rule) => [
#    let rule = rule
#    longest_match:bool = false
#    # etc. meta settings
# ] | <Rule | Rule>

# CSV grammar as defined by RFC 4180.
# Supports all CSV features: quoted fields, unquoted fields,
#    empty fields, multiple record separators, etc.

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
# swallow spaces (0x20) and tabs (0x09) after delimiter
DelimSkipInitialSpace = <["," <'\x20'|'\x09'>...]>


# --- Quoting ---
EscapedQuote = <'""'>  # doubled quote inside a quoted field


# Any char except a double quote. Includes CR/LF, commas, etc.
# (that’s what allows multiline quoted fields)
# (TBD about this syntax (named literal types))
QuotedChar = <ch:cc"\x00-\x21\x23-\U0010FFFF">
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
        cc"\x00-\x09"         # include tabs and control chars except LF/CR
        + "\x0B-\x0C"
        + "\x0E-\x21"         # up to '!' (0x21), excludes '"'(0x22)
        + "\x23-\x2B"         # '#'..'+'
        + "\x2D-\U0010FFFF"   # '-'..unicode max (excludes ',' 0x2C)
    >


# UnquotedField: one or more UnquotedChar characters.
# This will naturally stop when it encounters a comma, newline, CR, or quote
# because UnquotedChar excludes those characters.
# Note: we require at_least[1] so that truly empty fields
#       return None from optional[Field]
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
# Structured as: first field (optional), then zero or more delimiter+field pairs
Record = <fields: repeat<Field? separator=Delim>>



# --- Top-level file ---
# Structured so separators are required between records, making grammar unambiguous.
# First record has no leading separator; subsequent records require one.
# This prevents trailing newlines from creating spurious empty records.

CSV = Rule<[
    BOM?
    records: repeat<Record separator=RecordSep>
    RecordSep?  # trailing separator
]>

# Variant that allows spaces/tabs after commas (like skipinitialspace):
RecordSkipInitialSpace = <fields: repeat<Field separator=DelimSkipInitialSpace>


CSVSkipInitialSpace = Rule<
    BOM?
    records: repeat<RecordSkipInitialSpace separator=RecordSep>
    RecordSep?  # trailing separator
>
```

Usage might look like

```dewy
csv_text = "\
a,b,c,d,,f
1,2,3,4,5,6
"

result = CSV.parse(csv_text)
result.records[0]   # get the first row
# etc.
```

Still much work needed on this
