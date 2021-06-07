from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

GOOGLE_SEARCH_URL = "https://www.google.com/search"


# Code is influenced from https://github.com/cowboy-bebug/app-store-scraper
def perform_search(
    request_url: str,
    query: str,
    search_url: str = GOOGLE_SEARCH_URL,
    search_country: Optional[str] = None,
    headers: Optional[Dict[str, Any]] = None,
    total: int = 3,
    backoff_factor: int = 3,
    status_force_list: Optional[List[int]] = None,
) -> requests.Response:

    params = {"q": query}
    if search_country:
        params["cr"] = search_country

    if not status_force_list:
        status_force_list = [404, 429]
    retries = Retry(
        total=total,
        backoff_factor=backoff_factor,
        status_forcelist=status_force_list,
    )
    with requests.Session() as s:
        s.mount(request_url, HTTPAdapter(max_retries=retries))
        return s.get(search_url, headers=headers, params=params)
