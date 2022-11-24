from .system import System, load_dynamic_class
from .errors import TranslatableError, UserInputError
from .dict import deep_update


def caps_to_snake(txt: str, separator: str = "_") -> str:
    new_s = txt[0].lower()
    for x in txt[1:]:
        if x.isupper():
            new_s += separator
        new_s += x.lower()
    return new_s
