import json
import math
import time

import dateparser
from datetime import datetime, timezone
from importlib import import_module
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup
from bs4.element import Comment
from dateutil.relativedelta import relativedelta

DATETIME_STRING_PATTERN = "%Y-%m-%dT%H:%M:%SZ"
DEFAULT_LOOKUP_PERIOD = "1h"


# Used from https://stackoverflow.com/a/52081812 and modified
def flatten_dict(
    dictionary: Dict[str, Any],
    round_the_float: bool = True,
    float_round_format_str: str = ".2f",
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


def obj_to_json(obj: Any, sort_keys=False, indent=None):
    if obj is None:
        return None
    return json.dumps(
        obj,
        default=datetime_handler,
        ensure_ascii=False,
        sort_keys=sort_keys,
        indent=indent,
    ).encode("utf8")


def obj_to_markdown(
    obj: Any,
    level: int = 1,
    str_enclose_start: Optional[str] = None,
    str_enclose_end: Optional[str] = None,
) -> str:
    key_prefix = "*" * level

    markdowns = []
    if is_collection(obj):
        add_key = True
        if hasattr(obj, "__dict__"):
            item_view = obj.__dict__.items()
        elif isinstance(obj, dict):
            item_view = obj.items()
        else:
            add_key = False
            item_view = enumerate(obj)

        for key, val in item_view:
            if add_key:
                header = f"{key_prefix} {key}"
            else:
                header = key_prefix
            if is_collection(val):
                child_markdown = obj_to_markdown(
                    obj=val,
                    level=level + 1,
                    str_enclose_start=str_enclose_start,
                    str_enclose_end=str_enclose_end,
                )
                markdowns.append(f"{header}\n{child_markdown}")
            elif str_enclose_start is not None and isinstance(val, str):
                markdowns.append(
                    f"{header}:\n{str_enclose_start}{val}{str_enclose_end}"
                )
            else:
                markdowns.append(f"{header}: {val}")
    elif str_enclose_start is not None and isinstance(obj, str):
        markdowns.append(f"{key_prefix}:\n{str_enclose_start}{obj}{str_enclose_end}")
    else:
        markdowns.append(f"{key_prefix}: {obj}")

    return "\n".join(markdowns)


def is_collection(obj: Any):
    return isinstance(obj, (dict, list)) or hasattr(obj, "__dict__")


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
        - 2m (set start_time to two months ago)
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
            if "d" in datetime_str:
                _date = _date + relativedelta(days=-num)
            elif "h" in datetime_str:
                _date = _date + relativedelta(hours=-num)
            elif "m" in datetime_str:
                _date = _date + relativedelta(minutes=-num)
            elif "M" in datetime_str:
                _date = _date + relativedelta(months=-num)
            elif "Y" in datetime_str:
                _date = _date + relativedelta(years=-num)
        elif not {"-", ":"} & set(datetime_str):
            _date = datetime.strptime(datetime_str, "%Y%m%d%H%M")
        elif "T" in datetime_str:
            _date = datetime.strptime(datetime_str, DATETIME_STRING_PATTERN)
        else:
            _date = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")

    except ValueError:
        _date = datetime.strptime(datetime_str, "%Y-%m-%d")

    return _date.replace(tzinfo=timezone.utc)


def convert_datetime_str_to_epoch(datetime_str):
    if not datetime_str:
        return None
    parsed_datetime = dateparser.parse(datetime_str)
    unix_timestamp = time.mktime(parsed_datetime.timetuple())
    return math.trunc(unix_timestamp)


def tag_visible(element):
    if element.parent.name in [
        "style",
        "script",
        "head",
        "title",
        "meta",
        "[document]",
    ]:
        return False
    if isinstance(element, Comment):
        return False
    return True


def text_from_html(body):
    soup = BeautifulSoup(body, "html.parser")
    texts = soup.findAll(text=True)
    visible_texts = filter(tag_visible, texts)
    return " ".join(t.strip() for t in visible_texts)


def dict_to_object(
    dictionary: Dict[str, Any],
    class_name_key: Optional[str] = "_target_",
    full_class_name: Optional[str] = None,
) -> Any:
    new_dict: Dict[str, Any] = dict()
    for k, v in dictionary.items():
        if k == class_name_key:
            full_class_name = v
        elif isinstance(v, Dict):
            new_dict[k] = dict_to_object(dictionary=v, class_name_key=class_name_key)
        else:
            new_dict[k] = v

    if full_class_name is None:
        return new_dict

    module_name, class_name = tuple(full_class_name.rsplit(".", 1))
    module = import_module(module_name)
    class_ref = getattr(module, class_name)
    return class_ref(**new_dict)


def datetime_handler(x):
    if x is None:
        return None
    elif isinstance(x, datetime):
        return x.isoformat()
    return vars(x) if hasattr(x, "__dict__") else x
