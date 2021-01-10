import json
from datetime import datetime
from typing import Any, Dict, Optional

from dateutil.relativedelta import relativedelta

DATETIME_STRING_PATTERN = "%Y-%m-%dT%H:%M:%SZ"


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


def obj_to_json(obj: Any):
    if obj is None:
        return None
    return json.dumps(obj, default=lambda o: o.__dict__, sort_keys=True, indent=4)


def obj_to_markdown(
    obj: Any,
    level: int = 1,
    str_enclose_start: Optional[str] = None,
    str_enclose_end: Optional[str] = None
) -> str:
    key_prefix = "*" * level

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


# Copied from searchtweets-v2 and bit modified
def convert_utc_time(datetime_str):
    """
    Handles datetime argument conversion to the Labs API format, which is
    `YYYY-MM-DDTHH:mm:ssZ`.
    Flexible passing of date formats in the following types::

        - YYYYmmDDHHMM
        - YYYY-mm-DD
        - YYYY-mm-DD HH:MM
        - YYYY-mm-DDTHH:MM
        - 3d (set start_time to three days ago)
        - 12h (set start_time to twelve hours ago)
        - 15m (set start_time to fifteen minutes ago)

    Args:
        datetime_str (str): valid formats are listed above.

    Returns:
        string of ISO formatted date.
    """

    if not datetime_str:
        return None
    try:
        if len(datetime_str) <= 5:
            _date = datetime.utcnow()
            # parse out numeric character.
            num = int(datetime_str[:-1])
            if 'd' in datetime_str:
                _date = (_date + relativedelta(days=-num))
            elif 'h' in datetime_str:
                _date = (_date + relativedelta(hours=-num))
            elif 'm' in datetime_str:
                _date = (_date + relativedelta(minutes=-num))
        elif not {'-', ':'} & set(datetime_str):
            _date = datetime.strptime(datetime_str, "%Y%m%d%H%M")
        elif 'T' in datetime_str:
            _date = datetime.strptime(datetime_str, DATETIME_STRING_PATTERN)
        else:
            _date = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")

    except ValueError:
        _date = datetime.strptime(datetime_str, "%Y-%m-%d")

    return _date.strftime(DATETIME_STRING_PATTERN)
