from typing import Any, Dict, Optional


# Used from https://stackoverflow.com/a/52081812 and modified
def flatten_dict(
    dictionary: Dict[str, Any],
    round_the_float: bool = True,
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
        elif isinstance(val, float) and round_the_float:
            out[key] = format(val, float_round_format_str)
        else:
            out[key] = val
    return out


def obj_to_markdown(
    obj: Any,
    level: int = 1,
    str_enclose_start: Optional[str] = None,
    str_enclose_end: Optional[str] = None
) -> str:
    key_prefix = "*"*level

    markdowns = []
    if is_collection(obj):
        add_key = True
        if hasattr(obj, '__dict__'):
            item_view = obj.__dict__.items()
        elif isinstance(obj, dict):
            item_view = obj.items()
        else:
            add_key = False
            item_view = enumerate(obj)

        for key, val in item_view:
            if add_key:
                header = f'{key_prefix} {key}'
            else:
                header = key_prefix
            if is_collection(val):
                child_markdown = obj_to_markdown(
                    obj=val,
                    level=level + 1,
                    str_enclose_start=str_enclose_start,
                    str_enclose_end=str_enclose_end
                )
                markdowns.append(f'{header}\n{child_markdown}')
            elif str_enclose_start is not None and isinstance(val, str):
                markdowns.append(f'{header}:\n{str_enclose_start}{val}{str_enclose_end}')
            else:
                markdowns.append(f'{header}: {val}')
    elif str_enclose_start is not None and isinstance(obj, str):
        markdowns.append(f'{key_prefix}:\n{str_enclose_start}{obj}{str_enclose_end}')
    else:
        markdowns.append(f'{key_prefix}: {obj}')

    return "\n".join(markdowns)


def is_collection(obj: Any):
    return isinstance(obj, (dict, list)) or hasattr(obj, '__dict__')