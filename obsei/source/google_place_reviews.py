from typing import Any, List, Optional
from pydantic import PrivateAttr

import googlemaps

from obsei.payload import TextPayload
from obsei.source.base_source import BaseSource, BaseSourceConfig

"""
    Google Maps Client Library
    https://github.com/googlemaps/google-maps-services-python
    
    Place id finder:
    https://developers.google.com/maps/documentation/places/web-service/place-id
    
    API details: 
    https://developers.google.com/maps/documentation/places/web-service/details
"""


class GooglePlaceConfig(BaseSourceConfig):
    TYPE: str = "GooglePlace"
    latest_first: bool = True  # By default latest is first
    start_index: Optional[int] = None
    max_results: int = 1000
    num_retries: int = 1
    place_id: Optional[str] = None
    api_key: Optional[str] = None
    language: Optional[str] = "en"
    _gmaps_client: googlemaps.Client = PrivateAttr()

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._gmaps_client = googlemaps.Client(key=self.api_key)

    def get_gmaps_client(self):
        return self._gmaps_client


class GooglePlaceSource(BaseSource):
    NAME: str = "GooglePlace"

    def lookup(self, config: GooglePlaceConfig, **kwargs) -> List[TextPayload]:  # type: ignore[override]

        place_details = config.get_gmaps_client().place(
            place_id=config.place_id,
            fields=["place_id", "review"],
            language=config.language
        )

        # Refer response:
        # https://developers.google.com/maps/documentation/places/web-service/details#PlaceDetailsResponses
        reviews = place_details['result']['reviews']

        reviews = list(filter(lambda review: 'text' in review, reviews))
        reviews.sort(key=lambda r: r['time'], reverse=config.latest_first)
        reviews = reviews[slice(config.start_index, config.max_results)]

        source_responses: List[TextPayload] = list(map(
            lambda review: TextPayload(processed_text=review['text'], meta=review, source_name=self.NAME),
            reviews))

        return source_responses
