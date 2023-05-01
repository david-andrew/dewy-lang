



int_parsable_base_prefixes = {
    '0b':2,
    '0t':3,
    '0q':4,
    '0s':6,
    '0o':8,
    '0d':10,
    # '0z':12, #uses different digits Z/z and X/x (instead of A/a and B/b expected by int())
    '0x':16,
    '0u':32,
    '0r':36,
    # '0y':64, #more than int's max parsable base (36)
}


def based_number_to_int(src:str) -> int:
    """
    convert a number in a given base to an int
    """
    prefix, digits = src[:2], src[2:]
    if prefix in int_parsable_base_prefixes:
        return int(digits, int_parsable_base_prefixes[prefix])
    elif prefix == '0z':
        raise NotImplementedError(f"base {prefix} is not supported")
    elif prefix == '0y':
        raise NotImplementedError(f"base {prefix} is not supported")
    else:
        raise ValueError(f"INTERNAL ERROR: base {prefix} is not a valid base")