enum EBNF_state
{
    first_quote,
    second_quote,
    group,
    option,
    repeat,
    special,
};


//possible token types
enum EBNF_token_types
{
    EBNF_identifier,
    single_quote_string,
    double_quote_string,
    comma,
    semicolon,
    vertical_bar,
    minus,
    equals_sign,
    parenthesis,
    bracket,
    brace,
    whitespace,
};

//individual tokens that appear in an EBNF rule
typedef struct EBNF_tokens
{
    enum EBNF_token_types type;
    char* content;
} EBNF_token;



int resize_token_array(EBNF_token** current, int* size)
{
    EBNF_token* new = realloc(*current, *size);
    if (!new)
    {
        return 1;
    }
    else
    {
        *current = new;
        return 0;
    }
}