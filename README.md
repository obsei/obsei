
<p align="center">
    <table style="border-collapse: collapse; border: none;">
        <tr style="border-collapse: collapse; border: none;">
            <th style="border-collapse: collapse; border: none;">
                <img src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/obsei_200x200.png" width="100" height="100" />
            </th>
            <th style="border-collapse: collapse; border: none;">
                <h1>Obsei: OBserve, SEgment and Inform</h1>
            </th>
        </tr>
    </table>
</p>

<p align="center">
    <a href="https://github.com/lalitpagaria/obsei/actions">
        <img alt="CI" src="https://github.com/lalitpagaria/obsei/workflows/CI/badge.svg?branch=master">
    </a>
    <a href="https://github.com/lalitpagaria/obsei/blob/master/LICENSE">
        <img alt="License" src="https://img.shields.io/github/license/lalitpagaria/obsei?color=blue">
    </a>
    <a href="https://pypi.org/project/obsei">
        <img src="https://img.shields.io/pypi/pyversions/obsei" alt="PyPI - Python Version" />
    </a>
    <a href="https://pypi.org/project/obsei/">
        <img alt="Release" src="https://img.shields.io/pypi/v/obsei">
    </a>
    <a href="https://github.com/lalitpagaria/obsei/commits/master">
        <img alt="Last commit" src="https://img.shields.io/github/last-commit/lalitpagaria/obsei">
    </a>
    <a href="https://github.com/lalitpagaria/obsei/issues">
        <img alt="Open Issues" src="https://img.shields.io/github/issues/lalitpagaria/obsei">
    </a>
</p>


**Obsei** is intended to be a workflow automation tool for text segmentation need. *Obsei* consist of -
 - **Observer**, observes platform like Twitter, Facebook, App Stores, Google reviews, Amazon reviews and feed that information to,
 - **Segmenter**, which perform text classification and sentiment analysis and feed that information to,
 - **Informer**, which send it to ticketing system, data store or other places for further action and analysis.

Current flow -

![](https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/Obsei-flow-diagram.png)

A future concept (Coming Soon! :slightly_smiling_face:)

![](https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/Obsei-future-concept.png)


## Documentation
For detailed installation instructions, usages and example refer [documentation](https://lalitpagaria.github.io/obsei/).

## How to use

To try in Colab Notebook click: [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/lalitpagaria/obsei/blob/master/example/Obsei_playstore_classification_logger_example.ipynb)

To try in Binder click: [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/lalitpagaria/obsei/HEAD?filepath=example%2FObsei_playstore_classification_logger_example.ipynb)

Expend following steps and create your workflow -

<details><summary><b>Step 1: Prerequisite</b></summary>

Install following if system do not have -
 - Install [Python 3.7+](https://www.python.org/downloads/)
 - Install [PIP](https://pip.pypa.io/en/stable/installing/)
</details>

<details><summary><b>Step 2: Install Obsei</b></summary>

Install via PyPi:
```shell
pip install obsei
```
Install from master branch (if you want to try the latest features):
```shell
git clone https://github.com/lalitpagaria/obsei.git
cd obsei
pip install --editable .
```
</details>
<details><summary><b>Step 3: Configure Source/Observer</b></summary>

<table ><tbody ><tr></tr><tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/twitter.png" width="20" height="20"><b>Twitter</b></summary><hr>

 ```python
from obsei.source.twitter_source import TwitterCredentials, TwitterSource, TwitterSourceConfig

# initialize twitter source config
source_config = TwitterSourceConfig(
    keywords=["issue"], # Keywords, @user or #hashtags
    lookup_period="1h", # Lookup period from current time, format: `<number><d|h|m>` (day|hour|minute)
    credential=TwitterCredentials(
        # Enter your twitter consumer key and secret. Get it from https://developer.twitter.com/en/apply-for-access
        consumer_key="<twitter_consumer_key>",
        consumer_secret="<twitter_consumer_secret>"
    )
)

# initialize tweets retriever
source = TwitterSource()
```
</details>
</td>
</tr>
<tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/gmail.png" width="20" height="20"><b>Email</b></summary><hr>

 ```python
from obsei.source.email_source import EmailConfig, EmailCredInfo, EmailSource

# initialize email source config
source_config = EmailConfig(
    # List of IMAP servers for most commonly used email providers
    # https://www.systoolsgroup.com/imap/
    # Also, if you're using a Gmail account then make sure you allow less secure apps on your account -
    # https://myaccount.google.com/lesssecureapps?pli=1
    # Also enable IMAP access -
    # https://mail.google.com/mail/u/0/#settings/fwdandpop
    imap_server="imap.gmail.com", # Enter IMAP server
    cred_info=EmailCredInfo(
        # Enter your email account username and password
        username="<email_username>",
        password="<email_password>"
    ),
    lookup_period="1h" # Lookup period from current time, format: `<number><d|h|m>` (day|hour|minute)
)

# initialize email retriever
source = EmailSource()
```
</details>
</td>
</tr>
<tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/appstore.png" width="20" height="20"><b>AppStore Reviews Scrapper</b></summary><hr>

 ```python
from obsei.source.appstore_scrapper import AppStoreScrapperConfig, AppStoreScrapperSource

# initialize app store source config
source_config = AppStoreScrapperConfig(
    # Need two parameters app_id and country. 
    # `app_id` can be found at the end of the url of app in app store. 
    # For example - https://apps.apple.com/us/app/xcode/id497799835
    # `310633997` is the app_id for xcode and `us` is country.
    countries=["us"],
    app_id="310633997",
    lookup_period="1h" # Lookup period from current time, format: `<number><d|h|m>` (day|hour|minute)
)


# initialize app store reviews retriever
source = AppStoreScrapperSource()
```
</details>
</td>
</tr>
<tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/playstore.png" width="20" height="20"><b>Play Store Reviews Scrapper</b></summary><hr>

 ```python
from obsei.source.playstore_scrapper import PlayStoreScrapperConfig, PlayStoreScrapperSource

# initialize play store source config
source_config = PlayStoreScrapperConfig(
    # Need two parameters package_name and country. 
    # `package_name` can be found at the end of the url of app in play store. 
    # For example - https://play.google.com/store/apps/details?id=com.google.android.gm&hl=en&gl=US
    # `com.google.android.gm` is the package_name for xcode and `us` is country.
    countries=["us"],
    package_name="com.google.android.gm",
    lookup_period="1h" # Lookup period from current time, format: `<number><d|h|m>` (day|hour|minute)
)

# initialize play store reviews retriever
source = PlayStoreScrapperSource()
```
</details>
</td>
</tr>
<tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/reddit.png" width="20" height="20"><b>Reddit</b></summary><hr>

 ```python
from obsei.source.reddit_source import RedditConfig, RedditSource, RedditCredInfo

# initialize reddit source config
# Credentials will be fetched from env variable named reddit_client_id and reddit_client_secret
source_config = RedditConfig(
    subreddits=["wallstreetbets"], # List of subreddits
    # Reddit account username and password
    # You can also enter reddit client_id and client_secret or refresh_token
    # Create credential at https://www.reddit.com/prefs/apps
    # Also refer https://praw.readthedocs.io/en/latest/getting_started/authentication.html
    # Currently Password Flow, Read Only Mode and Saved Refresh Token Mode are supported
    cred_info=RedditCredInfo(
        username="<reddit_username>",
        password="<reddit_password>"
    ),
    lookup_period="1h" # Lookup period from current time, format: `<number><d|h|m>` (day|hour|minute)
)

# initialize reddit retriever
source = RedditSource()
```
</details>
</td>
</tr>
<tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/reddit.png" width="20" height="20"><b>Reddit Scrapper</b></summary><hr>

<i>Note: Reddit heavily rate limit scrappers, hence use it to fetch small data during long period</i>

 ```python
from obsei.source.reddit_scrapper import RedditScrapperConfig, RedditScrapperSource

# initialize reddit scrapper source config
source_config = RedditScrapperConfig(
    # Reddit subreddit, search etc rss url. For proper url refer following link -
    # Refer https://www.reddit.com/r/pathogendavid/comments/tv8m9/pathogendavids_guide_to_rss_and_reddit/
    url="https://www.reddit.com/r/wallstreetbets/comments/.rss?sort=new",
    lookup_period="1h" # Lookup period from current time, format: `<number><d|h|m>` (day|hour|minute)
)

# initialize reddit retriever
source = RedditScrapperSource()
```
</details>
</td>
</tr>
</tbody>
</table>

</details>

<details><summary><b>Step 4: Configure Analyzer/Segmenter</b></summary>

<table ><tbody ><tr></tr><tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/classification.png" width="20" height="20"><b>Text Classification</b></summary><hr>

Text classification, classify text into user provided categories.
 ```python
from obsei.analyzer.classification_analyzer import ClassificationAnalyzerConfig, ZeroShotClassificationAnalyzer

# initialize classification analyzer config
# It can also detect sentiments if "positive" and "negative" labels are added.
analyzer_config=ClassificationAnalyzerConfig(
    labels=["service", "delay", "performance"],
)

# initialize classification analyzer
# For supported models refer https://huggingface.co/models?filter=zero-shot-classification
text_analyzer = ZeroShotClassificationAnalyzer(
    model_name_or_path="joeddav/bart-large-mnli-yahoo-answers"
)
```
</details>
</td>
</tr>
<tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/sentiment.png" width="20" height="20"><b>Sentiment Analyzer</b></summary><hr>

Sentiment Analyzer, detect the sentiment of the text. Text classification can also perform sentiment analysis but if you don't want to use heavy-duty NLP model then use less resource hungry dictionary based Vader Sentiment detector.
 ```python
from obsei.analyzer.sentiment_analyzer import VaderSentimentAnalyzer

# Vader does not need any configuration settings
analyzer_config=None

# initialize vader sentiment analyzer
text_analyzer = VaderSentimentAnalyzer()
```
</details>
</td>
</tr>
<tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/ner.png" width="20" height="20"><b>NER Analyzer</b></summary><hr>

NER (Named-Entity Recognition) Analyzer, extract information and classify named entities mentioned in text into pre-defined categories such as person names, organizations, locations, medical codes, time expressions, quantities, monetary values, percentages, etc
 ```python
from obsei.analyzer.ner_analyzer import NERAnalyzer

# NER analyzer does not need configuration settings
analyzer_config=None

# initialize ner analyzer
# For supported models refer https://huggingface.co/models?filter=token-classification
text_analyzer = NERAnalyzer(
    model_name_or_path="elastic/distilbert-base-cased-finetuned-conll03-english"
)
```
</details>
</td>
</tr>
<tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/dummy.png" width="20" height="20"><b>Dummy Analyzer</b></summary><hr>

Dummy Analyzer, do nothing it simply used for transforming input (AnalyzerRequest) to output (AnalyzerResponse) also adding user supplied dummy data.
 ```python
from obsei.analyzer.dummy_analyzer import DummyAnalyzer, DummyAnalyzerConfig

# initialize dummy analyzer's configuration settings
analyzer_config = DummyAnalyzerConfig()

# initialize dummy analyzer
analyzer = DummyAnalyzer()
```
</details>
</td>
</tr>
</tbody>
</table>

</details>

<details><summary><b>Step 5: Configure Sink/Informer</b></summary>

<table ><tbody ><tr></tr><tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/slack.png" width="20" height="20"><b>Slack</b></summary><hr>

 ```python
from obsei.sink.slack_sink import SlackSink, SlackSinkConfig

# initialize slack sink config
sink_config = SlackSinkConfig(
    # Provide slack bot/app token
    # For more detail refer https://slack.com/intl/en-de/help/articles/215770388-Create-and-regenerate-API-tokens
    slack_token="<Slack_app_token>",
    # To get channel id refer https://stackoverflow.com/questions/40940327/what-is-the-simplest-way-to-find-a-slack-team-id-and-a-channel-id
    channel_id="C01LRS6CT9Q"
)

# initialize slack sink
sink = SlackSink()
```
</details>
</td>
</tr>
<tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/zendesk.png" width="20" height="20"><b>Zendesk</b></summary><hr>

 ```python
from obsei.sink.zendesk_sink import ZendeskSink, ZendeskSinkConfig, ZendeskCredInfo

# initialize zendesk sink config
sink_config = ZendeskSinkConfig(
    # For custom domain refer http://docs.facetoe.com.au/zenpy.html#custom-domains
    # Mainly you can do this by setting the environment variables:
    # ZENPY_FORCE_NETLOC
    # ZENPY_FORCE_SCHEME (default to https)
    # when set it will force request on:
    # {scheme}://{netloc}/endpoint
    # provide zendesk domain
    domain="zendesk.com",
    # provide subdomain if you have one
    subdomain=None,
    # Enter zendesk user details
    cred_info=ZendeskCredInfo(
        email="<zendesk_user_email>",
        password="<zendesk_password>"
    )
)

# initialize zendesk sink
sink = ZendeskSink()
```
</details>
</td>
</tr>
<tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/jira.png" width="20" height="20"><b>Jira</b></summary><hr>

 ```python
from obsei.sink.jira_sink import JiraSink, JiraSinkConfig

# For testing purpose you can start jira server locally
# Refer https://developer.atlassian.com/server/framework/atlassian-sdk/atlas-run-standalone/

# initialize Jira sink config
sink_config = JiraSinkConfig(
    url="http://localhost:2990/jira", # Jira server url
     # Jira username & password for user who have permission to create issue
    username="<username>",
    password="<password>",
    # Which type of issue to be created
    # For more information refer https://support.atlassian.com/jira-cloud-administration/docs/what-are-issue-types/
    issue_type={"name": "Task"},
    # Under which project issue to be created
    # For more information refer https://support.atlassian.com/jira-software-cloud/docs/what-is-a-jira-software-project/
    project={"key": "CUS"},
)

# initialize Jira sink
sink = JiraSink()
```
</details>
</td>
</tr>
<tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/elastic.png" width="20" height="20"><b>ElasticSearch</b></summary><hr>

 ```python
from obsei.sink.elasticsearch_sink import ElasticSearchSink, ElasticSearchSinkConfig

# For testing purpose you can start Elasticsearch server locally via docker
# `docker run -d --name elasticsearch -p 9200:9200 -e "discovery.type=single-node" elasticsearch:7.9.2`

# initialize Elasticsearch sink config
sink_config = ElasticSearchSinkConfig(
    # Elasticsearch server hostname
    host="localhost",
    # Elasticsearch server port
    port=9200,
    # Index name, it will create if not exist
    index_name="test",
)

# initialize Elasticsearch sink
sink = ElasticSearchSink()
```
</details>
</td>
</tr>
<tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/http_api.png" width="20" height="20"><b>Http</b></summary><hr>

 ```python
from obsei.sink.http_sink import HttpSink, HttpSinkConfig

# For testing purpose you can create mock http server via postman
# For more details refer https://learning.postman.com/docs/designing-and-developing-your-api/mocking-data/setting-up-mock/

# initialize http sink config (Currently only POST call is supported)
sink_config = HttpSinkConfig(
    # provide http server uri
    url="https://localhost:8080/api/path",
    # Here you can add headers you would like to pass with request
    headers={
        "Content-type": "application/json"
    }
)

# To modify or converting the payload, create convertor class
# Refer obsei.sink.dailyget_sink.PayloadConvertor for example

# initialize http sink
sink = HttpSink()
```
</details>
</td>
</tr>
<tr>
<td><details ><summary><img style="vertical-align:middle;margin:2px 10px" src="https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/logger.png" width="20" height="20"><b>Logger</b></summary><hr>

This is useful for testing and dry run checking of pipeline.
 ```python
from obsei.sink.logger_sink import LoggerSink, LoggerSinkConfig
import logging
import sys

logger = logging.getLogger("Obsei")
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# initialize logger sink config
sink_config = LoggerSinkConfig(
    logger=logger,
    level=logging.INFO
)

# initialize logger sink
sink = LoggerSink()
```
</details>
</td>
</tr>
</tbody>
</table>

</details>

<details><summary><b>Step 6: Join and create workflow</b></summary>

`source` will fetch data from selected the source, then feed that to `analyzer` for processing, whose output we feed into `sink` to get notified at that sink.
```python
# Uncomment if you want logger
# import logging
# import sys
# logger = logging.getLogger(__name__)
# logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# This will fetch information from configured source ie twitter, app store etc
source_response_list = source.lookup(source_config)

# Uncomment if you want to log source response
# for idx, source_response in enumerate(source_response_list):
#     logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")

# This will execute analyzer (Sentiment, classification etc) on source data with provided analyzer_config
analyzer_response_list = text_analyzer.analyze_input(
    source_response_list=source_response_list,
    analyzer_config=analyzer_config
)

# Uncomment if you want to log analyzer response
# for idx, an_response in enumerate(analyzer_response_list):
#    logger.info(f"analyzer_response#'{idx}'='{an_response.__dict__}'")

# This will send analyzed output to configure sink ie Slack, Zendesk etc
sink_response_list = sink.send_data(analyzer_response_list, sink_config)

# Uncomment if you want to log sink response
# for sink_response in sink_response_list:
#     if sink_response is not None:
#         logger.info(f"sink_response='{sink_response}'")
```
</details>

<details><summary><b>Step 7: Execute workflow</b></summary>
Copy code snippets from <b>Step 3</b> to <b>Step 6</b> into python file for example <code>example.py</code> and execute following command -

```shell
python example.py
```
</details>

## Upcoming Release
Upcoming release plan and progress can be tracked at [link](https://github.com/lalitpagaria/obsei/projects) (Suggestions are welcome).


## Discussion Forum
Discussion about *Obsei* can be done at [community forum](https://github.com/lalitpagaria/obsei/discussions)

## Use cases
`Obsei` use cases are following, but not limited to -
- Automatic customer issue ticketing based on sentiment analysis
- Proper tagging of ticket like login issue, signup issue, delivery issue etc for faster disposal
- Checking effectiveness of social media marketing campaign
- Extraction of deeper insight from feedbacks on various platforms
- Research purpose

## Attribution
Refer [link](ATTRIBUTION.md) for attribution.

## Contribution
Currently, as project is very early stages, we are not accepting any pull requests. 
We would love community's active contribution after few releases, first we want to shape the project with suggestion and feedback. If you want a feature or something doesn't work, please create an issue.

## Changelog
Refer [releases](https://github.com/lalitpagaria/obsei/releases) and [projects](https://github.com/lalitpagaria/obsei/projects).

## Citing Obsei
If you use `obsei` in your research please use the following BibTeX entry:
```text
@Misc{Pagaria2020Obsei,
  author =       {Lalit Pagaria},
  title =        {Obsei - A workflow automation tool for text segmentation need},
  howpublished = {Github},
  year =         {2020},
  url =          {https://github.com/lalitpagaria/obsei}
}
```

## Stargazers over time

[![Stargazers over time](https://starchart.cc/lalitpagaria/obsei.svg)](https://starchart.cc/lalitpagaria/obsei)

## Acknowledgement

We would like to thank [DailyGet](https://dailyget.in/) for continuous support and encouragement.
Please check [DailyGet](https://dailyget.in/) out. it is a platform which can easily be configured to solve any business process automation requirements.
