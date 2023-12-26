import requests

from .exceptions import *

import re


def extract_tag_contents(html):
    next_json = re.search(
        r"id=\"__NEXT_DATA__\"\s+type=\"application\/json\"\s*[^>]+>\s*(?P<next_data>[^<]+)",
        html,
    )
    if next_json:
        nonce_start = '<head nonce="'
        nonce_end = '">'
        nonce = html.split(nonce_start)[1].split(nonce_end)[0]
        j_raw = html.split(
            '<script id="__NEXT_DATA__" type="application/json" nonce="%s" crossorigin="anonymous">'
            % nonce
        )[1].split("</script>")[0]
        return j_raw
    else:
        sigi_json = re.search('<script id="SIGI_STATE" type="application\/json">(.*?)<\/script>', html)
        # sigi_json = re.search(
        # r'>\s*window\[[\'"]SIGI_STATE[\'"]\]\s*=\s*(?P<sigi_state>{.+});', html
        # )
        if sigi_json:
            return sigi_json.group(1)
        else:
            raise Exception("Could not find __NEXT_DATA__ or SIGI_STATE")
            # not a reliable way to check for captchas
            # raise CaptchaException(
            #    "TikTok blocks this request displaying a Captcha \nTip: Consider using a proxy or a custom_verify_fp as method parameters"
            # )


def extract_video_id_from_url(url):
    url = requests.head(url=url, allow_redirects=True).url
    if "@" in url and "/video/" in url:
        return url.split("/video/")[1].split("?")[0]
    else:
        raise TypeError(
            "URL format not supported. Below is an example of a supported url.\n"
            "https://www.tiktok.com/@therock/video/6829267836783971589"
        )


def extract_user_id_from_url(url):
    url = requests.head(url=url, allow_redirects=True).url
    if "@" in url and "/video/" in url:
        return url.split("/video/")[0].split("@")[1]
    else:
        raise TypeError(
            "URL format not supported. Below is an example of a supported url.\n"
            "https://www.tiktok.com/@therock/video/6829267836783971589"
        )


def add_if_not_replace(text, pat, replace, add):
    if re.search(pat, text):
        return re.sub(pat, replace, text)
    else:
        text += add
        return text
