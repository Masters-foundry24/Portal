def format_de(number):
    """
    In this function we format decimals so that they can be displayed properly
    in tables.

    Todo:
        -> Add full stops at each three digits for very large numbers.
        -> Round numbers with more decimals rather than truncate them.
    """
    number = str(number)
    number = number.replace(".", ",")
    if "," in number:
        pos = len(number) - number.index(",")
        if pos == 2: # One digit behind the decimal point.
            number = number + "0"
        elif pos == 3: # Two digits behind the decimal point.
            pass
        else: # cut off excess digits (rather than round them).
            number = number[:len(number) - (pos - 3)]
    else:
        number = number + ",00"
    return number

def check_IBAN(IBAN: str):
    """
    This function runs the mod-97 operation to provide an initial check of IBAN
    validity. Returns a boolean depending on whether the IBAN passes this check.

    Inputs:
        -> IBAN: str
    """
    letter_codes = {
        "A": "10", "B": "11", "C": "12", "D": "13", "E": "14", "F": "15", 
        "G": "16", "H": "17", "I": "18", "J": "19", "K": "20", "L": "21", 
        "M": "22", "N": "23", "O": "24", "P": "25", "Q": "26", "R": "27", 
        "S": "28", "T": "29", "U": "30", "V": "31", "W": "32", "X": "33", 
        "Y": "34", "Z": "35",

        "a": "10", "b": "11", "c": "12", "d": "13", "e": "14", "f": "15", 
        "g": "16", "h": "17", "i": "18", "j": "19", "k": "20", "l": "21", 
        "m": "22", "n": "23", "o": "24", "p": "25", "q": "26", "r": "27", 
        "s": "28", "t": "29", "u": "30", "v": "31", "w": "32", "x": "33", 
        "y": "34", "z": "35",
    }
    iban_0 = IBAN.replace(" ", "") # remove spaces.
    iban_1 = iban_0[4:] + iban_0[:4]
    iban_2 = iban_1
    for k, v in letter_codes.items():
        iban_2 = iban_2.replace(k, v)
    try:
        iban_3 = int(iban_2)
    except: # The user must have given us a string with special characters.
        return False
    modulus = iban_3 % 97
    if modulus == 1:
        return True
    else:
        return False