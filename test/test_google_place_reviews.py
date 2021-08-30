import importlib.resources as pkg_resources
import json
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from obsei.source.google_place_reviews import GooglePlaceSource
import test_data


class MyTestCase(unittest.TestCase):
    source = GooglePlaceSource()

    @patch('obsei.source.google_place_reviews.GooglePlaceConfig')
    @patch('googlemaps.Client')
    def test_something(self, source_config_mock, gmaps_client_mock):
        source_config_mock.get_gmaps_client = MagicMock(return_value=gmaps_client_mock)
        source_config_mock.latest_first = True
        source_config_mock.start_index = 0
        source_config_mock.max_results = 1000

        reviews_json = pkg_resources.read_text(test_data, 'reviews_sample1.json')
        gmaps_client_mock.place = MagicMock(return_value=json.loads(reviews_json))

        # method under test
        source_response_list = self.source.lookup(source_config_mock)

        self.assertEqual(5, len(source_response_list))

        reviews_text = pkg_resources.read_text(test_data, 'reviews_sample1_text.json')
        self.assertEqual(
            json.loads(reviews_text)['texts'],
            list(map(lambda response: response.processed_text, source_response_list)))


if __name__ == '__main__':
    unittest.main()
