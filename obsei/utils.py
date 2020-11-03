from typing import Any, Dict


# Used from https://stackoverflow.com/a/52081812 and modified
def flatten_dict(
    dictionary: Dict[str, Any],
    round_of_float: bool = True,
    float_round_format_str: str = '.2f',
    separator: str = "_",
):
    out: Dict[str, Any] = {}
    for key, val in dictionary.items():
        if isinstance(val, dict):
            val = [val]
        if isinstance(val, list):
            for sub_dict in val:
                deeper = flatten_dict(sub_dict).items()
                out.update({key + separator + key2: val2 for key2, val2 in deeper})
        elif isinstance(val, float) and round_of_float:
            out[key] = format(val, float_round_format_str)
        else:
            out[key] = val
    return out