import logging

from obsei._version import __version__

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s -   %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
    level=logging.INFO,
)

init_logger: logging.Logger = logging.getLogger(__name__)

installation_message: str = """
By default `pip install obsei` will only install core dependencies.
To install all required dependencies use `pip install obsei[all]`.
Refer https://obsei.com/#install-obsei for more options.
"""

init_logger.warning(installation_message)
