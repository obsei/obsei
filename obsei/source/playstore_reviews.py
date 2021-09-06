import os
from typing import Any, Dict, List, Optional

from google.auth.credentials import Credentials  # type: ignore
from google.oauth2 import service_account  # type: ignore
from googleapiclient.discovery import build
from pydantic import BaseModel, Field, SecretStr

from obsei.payload import TextPayload
from obsei.source.base_source import BaseSource, BaseSourceConfig


class GoogleCredInfo(BaseModel):
    # Currently only service_account_file type credential supported
    # Refer: https://developers.google.com/identity/protocols/oauth2/service-account
    service_cred_file: str = Field(os.environ.get("google_service_cred_file", None))
    developer_key: SecretStr = Field(os.environ.get("google_developer_key", None))
    scopes: List[str] = ["https://www.googleapis.com/auth/androidpublisher"]


class PlayStoreConfig(BaseSourceConfig):
    TYPE: str = "PlayStore"
    package_name: str
    start_index: Optional[int] = None
    max_results: int = 10
    num_retries: int = 1
    with_quota_project_id: Optional[str] = None
    with_subject: Optional[str] = None
    cred_info: GoogleCredInfo = Field(GoogleCredInfo())

    def get_google_credentials(self) -> Credentials:
        credentials = service_account.Credentials.from_service_account_file(
            filename=self.cred_info.service_cred_file, scopes=self.cred_info.scopes
        )

        if self.with_quota_project_id is not None:
            credentials = credentials.with_quota_project(self.with_quota_project_id)

        if self.with_subject is not None:
            credentials = credentials.with_subject(self.with_subject)

        return credentials


class PlayStoreSource(BaseSource):
    NAME: str = "PlayStore"

    def lookup(self, config: PlayStoreConfig, **kwargs) -> List[TextPayload]:  # type: ignore[override]
        source_responses: List[TextPayload] = []
        # Refer https://github.com/googleapis/google-api-python-client/blob/master/docs/start.md
        with build(
            serviceName="androidpublisher",
            version="v3",
            credentials=config.get_google_credentials(),
            developerKey=config.cred_info.developer_key.get_secret_value(),
        ) as service:
            reviews = service.reviews()
            pagination_token: Optional[str] = None

            # Get data from state
            id: str = kwargs.get("id", None)
            state: Optional[Dict[str, Any]] = (
                None
                if id is None or self.store is None
                else self.store.get_source_state(id)
            )
            start_index: Optional[int] = (
                config.start_index or None
                if state is None
                else state.get("start_index", None)
            )
            update_state: bool = True if id else False
            state = state or dict()
            review_id = start_index

            while True:
                # Refer following link -
                # https://googleapis.github.io/google-api-python-client/docs/dyn/androidpublisher_v3.reviews.html#list
                responses = reviews.list(
                    package_name=config.package_name,
                    max_results=config.max_results,
                    start_index=start_index,
                    token=pagination_token,
                )

                if "reviews" in responses:
                    reviews = responses["responses"]
                    for review in reviews:
                        if "comments" not in review:
                            continue

                        review_id = review["reviewId"]

                        # Currently only one user comment is supported
                        text = review["comments"][0]["userComment"]["text"]
                        source_responses.append(
                            TextPayload(
                                processed_text=text, meta=review, source_name=self.NAME
                            )
                        )

                pagination_token = None
                if "tokenPagination" in responses:
                    if "nextPageToken" in responses["tokenPagination"]:
                        pagination_token = responses["tokenPagination"]["nextPageToken"]

                if pagination_token is None:
                    break

        if update_state and self.store is not None:
            state["start_index"] = review_id
            self.store.update_source_state(workflow_id=id, state=state)

        return source_responses
