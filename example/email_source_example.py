import logging
import os
import sys
from datetime import datetime, timedelta

import pytz

from obsei.misc.utils import DATETIME_STRING_PATTERN
from obsei.source.email_source import EmailConfig, EmailCredInfo, EmailSource

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

since_time = datetime.utcnow().astimezone(pytz.utc) + timedelta(hours=-10)

# List of IMAP servers for most commonly used email providers
# https://www.systoolsgroup.com/imap/
# Also, if you're using a Gmail account then make sure you allow less secure apps on your account -
# https://myaccount.google.com/lesssecureapps?pli=1
# Also enable IMAP access -
# https://mail.google.com/mail/u/0/#settings/fwdandpop
source_config = EmailConfig(
    imap_server="imap.gmail.com",
    cred_info=EmailCredInfo(
        # It will fetch username and password from environment variable
        username=os.environ.get("email_username"),
        password=os.environ.get("email_password")
    ),
    lookup_period=since_time.strftime(DATETIME_STRING_PATTERN)
)

source = EmailSource()
source_response_list = source.lookup(source_config)

for source_response in source_response_list:
    logger.info(source_response.__dict__)

