## unicode escape that doesn't consume adjacent number characters
* if you for some reason needed to do a unicode escape followed by a character that happens to be a hex digit, you could do:
`\u##{}#`, where the empty block {} breaks the hex digit sequence. Also you could do `\u##\#` (preferred style)
