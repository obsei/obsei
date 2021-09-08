import email
import imaplib
import logging
from datetime import datetime
from email.header import decode_header
from email.message import Message
from typing import Any, Dict, List, Optional

import pytz
from pydantic import BaseSettings, Field, PrivateAttr, SecretStr

from obsei.payload import TextPayload
from obsei.misc.utils import (
    DATETIME_STRING_PATTERN,
    DEFAULT_LOOKUP_PERIOD,
    convert_utc_time,
    text_from_html,
)
from obsei.source.base_source import BaseSource, BaseSourceConfig

logger = logging.getLogger(__name__)


class EmailCredInfo(BaseSettings):
    username: Optional[SecretStr] = Field(None, env="email_username")
    password: Optional[SecretStr] = Field(None, env="email_password")


class EmailConfig(BaseSourceConfig):
    # This is done to avoid exposing member to API response
    _imap_client: imaplib.IMAP4 = PrivateAttr()
    TYPE: str = "Email"
    # List of IMAP servers for most commonly used email providers
    # https://www.systoolsgroup.com/imap/
    # Also, if you're using a Gmail account then make sure you allow less secure apps on your account -
    # https://myaccount.google.com/lesssecureapps?pli=1
    # Also enable IMAP access -
    # https://mail.google.com/mail/u/0/#settings/fwdandpop
    imap_server: str
    imap_port: Optional[int] = None
    download_attachments: Optional[bool] = False
    mailboxes: List[str] = Field(["INBOX"])
    cred_info: Optional[EmailCredInfo] = Field(None)
    lookup_period: Optional[str] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        self.cred_info = self.cred_info or EmailCredInfo()

        if self.cred_info.password is None or self.cred_info.username is None:
            raise ValueError("Email account `username` and `password` is required")
        if self.imap_port:
            self._imap_client = imaplib.IMAP4_SSL(
                host=self.imap_server, port=self.imap_port
            )
        else:
            self._imap_client = imaplib.IMAP4_SSL(self.imap_server)

        self._imap_client.login(
            user=self.cred_info.username.get_secret_value(),
            password=self.cred_info.password.get_secret_value(),
        )

    def __del__(self):
        # self._imap_client.close()
        self._imap_client.logout()

    def get_client(self) -> imaplib.IMAP4:
        return self._imap_client


class EmailSource(BaseSource):
    NAME: str = "Email"

    @staticmethod
    def clean(text):
        # clean text for creating a folder
        return "".join(c if c.isalnum() else "_" for c in text)

    def lookup(self, config: EmailConfig, **kwargs) -> List[TextPayload]:  # type: ignore[override]
        source_responses: List[TextPayload] = []

        # Get data from state
        id: str = kwargs.get("id", None)
        state: Optional[Dict[str, Any]] = (
            None
            if id is None or self.store is None
            else self.store.get_source_state(id)
        )
        update_state: bool = True if id else False
        state = state or dict()

        imap_client = config.get_client()

        for mailbox in config.mailboxes:
            need_more_lookup = True

            status, messages = imap_client.select(mailbox=mailbox, readonly=True)
            if status != "OK":
                logger.warning(f"Not able to connect with {mailbox}: {status}")
                continue

            mailbox_stat: Dict[str, Any] = state.get(mailbox, dict())
            lookup_period: str = mailbox_stat.get(
                "since_time", config.lookup_period or DEFAULT_LOOKUP_PERIOD
            )
            if len(lookup_period) <= 5:
                since_time = convert_utc_time(lookup_period)
            else:
                since_time = datetime.strptime(lookup_period, DATETIME_STRING_PATTERN)

            if since_time.tzinfo is None:
                since_time = since_time.replace(tzinfo=pytz.utc)
            else:
                since_time = since_time.astimezone(pytz.utc)

            last_since_time: datetime = since_time
            since_id: Optional[int] = mailbox_stat.get("since_message_id", None)
            last_index = since_id

            state[mailbox] = mailbox_stat

            num_of_emails = int(str(messages[0]))

            # Read in reverse order means latest emails first
            # Most of code is borrowed from https://www.thepythoncode.com/article/reading-emails-in-python and
            # modified to suite here
            for index in range(num_of_emails, 0, -1):
                email_meta: Dict[str, Any] = dict()

                # fetch the email message by ID
                status, email_message = imap_client.fetch(str(index), "(RFC822)")

                email_content: str = ""

                for response in email_message:
                    if isinstance(response, tuple):
                        # parse a bytes email into a message object
                        msg = email.message_from_bytes(response[1])

                        email_meta["subject"] = self._parse_email_header(msg, "Subject")
                        email_meta["from_address"] = self._parse_email_header(
                            msg, "From"
                        )
                        email_meta["to_address"] = self._parse_email_header(msg, "To")
                        date_received_str = self._parse_email_header(msg, "Date")

                        try:
                            date_received = datetime.strptime(
                                date_received_str, "%a, %d %b %Y %H:%M:%S %Z"
                            )
                        except Exception:
                            try:
                                date_received = datetime.strptime(
                                    date_received_str, "%a, %d %b %Y %H:%M:%S %z"
                                )
                            except Exception:
                                date_received = datetime.strptime(
                                    date_received_str, "%a, %d %b %Y %H:%M:%S %z (%Z)"
                                )

                        if date_received.tzinfo is None:
                            date_received = date_received.replace(tzinfo=pytz.utc)
                        else:
                            date_received = date_received.astimezone(pytz.utc)
                        email_meta["date_received"] = date_received
                        email_meta["message_id"] = self._parse_email_header(
                            msg, "Message-ID"
                        )

                        part_id = 0
                        # if the email message is multipart
                        if msg.is_multipart():
                            # iterate over email parts
                            for part in msg.walk():
                                part_id_str = f"part_{part_id}"
                                # extract content type of email
                                content_type = part.get_content_type()
                                content_disposition = str(
                                    part.get("Content-Disposition")
                                )

                                email_meta[part_id_str] = dict()
                                email_meta[part_id_str]["content_type"] = content_type
                                email_meta[part_id_str][
                                    "content_disposition"
                                ] = content_disposition

                                if (
                                    "attachment" not in content_disposition
                                    and "text/" in content_type
                                ):
                                    try:
                                        # get the email body
                                        email_body = part.get_payload(
                                            decode=True
                                        ).decode()
                                        if content_type == "text/html":
                                            email_body = text_from_html(email_body)
                                        # append email body with existing
                                        email_meta[part_id_str][
                                            "email_body"
                                        ] = email_body
                                        email_content = (
                                            email_content + "\n" + email_body
                                        )
                                    except Exception:
                                        logger.error("Unable to parse email body")
                                elif "attachment" in content_disposition:
                                    logger.warning(
                                        "Email attachment download is not supported"
                                    )
                                    # Download attachment is commented currently
                                    # # download attachment
                                    # filename = part.get_filename()
                                    # if filename:
                                    #    folder_name = self.clean(subject)
                                    #    if not os.path.isdir(folder_name):
                                    #        # make a folder for this email (named after the subject)
                                    #        os.mkdir(folder_name)
                                    #    filepath = os.path.join(folder_name, filename)
                                    #    # download attachment and save it
                                    #    open(filepath, "wb").write(part.get_payload(decode=True))

                                part_id = part_id + 1
                        else:
                            part_id_str = f"part_{part_id}"
                            email_meta[part_id_str] = dict()
                            # extract content type of email
                            content_type = msg.get_content_type()
                            email_meta[part_id_str]["content_type"] = content_type

                            # get the email body
                            email_body = msg.get_payload(decode=True).decode()
                            if content_type == "text/html":
                                email_body = text_from_html(email_body)

                            email_meta[part_id_str]["email_body"] = email_body
                            email_content = email_content + "\n" + email_body

                        if date_received <= since_time:
                            need_more_lookup = False
                            break
                        if last_index and last_index == email_meta["message_id"]:
                            need_more_lookup = False
                            break
                        if last_since_time is None or last_since_time < date_received:
                            last_since_time = date_received
                        if last_index is None:
                            last_index = email_meta["message_id"]

                        source_responses.append(
                            TextPayload(
                                processed_text="\n".join(
                                    [email_meta.get("subject", ""), email_content]
                                ),
                                meta=email_meta,
                                source_name=self.NAME,
                            )
                        )

                if not need_more_lookup:
                    break

            mailbox_stat["since_time"] = last_since_time.strftime(
                DATETIME_STRING_PATTERN
            )
            mailbox_stat["since_comment_id"] = last_index

        if update_state and self.store is not None:
            self.store.update_source_state(workflow_id=id, state=state)

        return source_responses

    @staticmethod
    def _email_cleanup(content: str):
        # TODO: Implement the method to cleanup email contents
        pass

    @staticmethod
    def _parse_email_header(header: Message, key: str) -> str:
        value, encoding = decode_header(header[key])[0]
        if isinstance(value, bytes):
            # if it's a bytes, decode to str
            return "" if not encoding else value.decode(encoding)
        return value
