#  Copyright (c) 2020. Lalit Kumar Pagaria.
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/
import os

import requests


class TweetLookup():
    def __init__(
        self,
        bearer_token: str = os.environ.get("bearer_token")
    ):
        self.url = "https://api.twitter.com/2/tweets/sample/stream"
        self.headers = {"Authorization": "Bearer {}".format(bearer_token)}

        response = requests.request("GET", self.url, headers=self.headers, stream=True)
        if response.status_code != 200:
            raise Exception(
                "Request returned an error: {} {}".format(
                    response.status_code, response.text
                )
            )