import requests


def count_words_at_url(url, abc):
    print(
        url
    )
    resp = requests.get(abc)
    return len(resp.text.split())
