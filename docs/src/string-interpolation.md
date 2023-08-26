# String Interpolation

Including variable values inside of a string is handled with string interpolation. 

```dewy
my_age = 24
my_string = 'I am {my_age} years old'
printl(my_string)
```

which will print the string `I am 24 years old`. Any arbitrary expression can be contained inside of the curly braces. For expressions that are not a string by default, the `.string()` method will be called on them to get the string version.