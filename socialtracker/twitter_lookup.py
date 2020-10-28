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
from typing import Optional

from searchtweets import collect_results, gen_request_parameters, load_credentials


class TwitterLookup:
    def __init__(
            self,
            consumer_key: str,
            consumer_secret: str,
            account_type: Optional[str] = None,
            bearer_token: Optional[str] = None,
            endpoint: Optional[str] = None,
    ):
        if consumer_key:
            os.environ["SEARCHTWEETS_CONSUMER_KEY"] = consumer_key
        if consumer_secret:
            os.environ["SEARCHTWEETS_CONSUMER_SECRET"] = consumer_secret
        if account_type:
            os.environ["SEARCHTWEETS_ACCOUNT_TYPE"] = account_type
        if bearer_token:
            os.environ["SEARCHTWEETS_BEARER_TOKEN"] = bearer_token
        if endpoint:
            os.environ["SEARCHTWEETS_ENDPOINT"] = endpoint

        self.search_args = load_credentials(env_overwrite=True)

    def fetch_tweets(self, query: str):
        search_query = gen_request_parameters(query, results_per_call=100)
        tweets = collect_results(search_query, max_tweets=100, result_stream_args=self.search_args)
        return tweets
