# Obsei: OBserve, SEgment and Inform

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
    <a href="https://pepy.tech/project/obsei">
        <img src="https://pepy.tech/badge/obsei/month" alt="Downloads" />
    </a>
    <a href="https://hub.docker.com/r/lalitpagaria/obsei">
        <img src="https://img.shields.io/docker/pulls/lalitpagaria/obsei" alt="Docker Pulls" />
    </a>
    <a href="https://github.com/lalitpagaria/obsei/commits/master">
        <img alt="Last commit" src="https://img.shields.io/github/last-commit/lalitpagaria/obsei">
    </a>
</p>

**Note: There are major breaking changes are on the way. Please use released version instead of master branch. To track progress of next release refer [Release Progress](#release-progress).**


`Obsei` is intended to be a workflow automation tool for text segmentation need. `Obsei` consist of -
 - **OBserver**, observes platform like Twitter, Facebook, App Stores, Google reviews, Amazon reviews and feed that information to,
 - **SEgmenter**, which perform text classification and sentiment analysis and feed that information to,
 - **Informer**, which send it to ticketing system, data store or other places for further action and analysis.

Current flow -

![](https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/Obsei-flow-diagram.png)

A future concept (Coming Soon! :slightly_smiling_face:)

![](https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/Obsei-future-concept.png)


## Release Progress
Following releases are on the way -
- [**v0.0.5**](https://github.com/lalitpagaria/obsei/projects/4): Documentation focused release  
- [**v0.1.0**](https://github.com/lalitpagaria/obsei/projects/3): DAG support, CI improvements and few more (suggestions are welcome)

## Installation

### To use as SDK
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

To update your installation, just do a `git pull`. The `--editable` flag
will update changes immediately.

### To use as Rest interface
Start docker with default configuration file:
```shell
docker run -d --name obesi -p 9898:9898 lalitpagaria/obsei:latest
```
Start docker with custom configuration file (Assuming you have configfile `config.yaml` at `/home/user/obsei/config` at host machine):
```shell
docker run -d --name obesi -v "/home/user/obsei/config:/home/user/config" -e "OBSEI_CONFIG_PATH=/home/user/config" -e "OBSEI_CONFIG_FILENAME=config.yaml" -p 9898:9898 lalitpagaria/obsei:latest
```
Start docker locally with `docker-compose`:
```shell
docker-compose up --build
```
Following environment variables are useful to customize various parameters -
- `OBSEI_CONFIG_PATH`: Configuration file path (default: ../config)
- `OBSEI_CONFIG_FILENAME`: Configuration file name (default: rest.yaml)
- `OBSEI_NUM_OF_WORKERS`: Number of workers for rest API server (default: 1)
- `OBSEI_WORKER_TIMEOUT`: Worker idle timeout in seconds (default: 180)
- `OBSEI_SERVER_PORT`: Rest API server port (default: 9898)
- `OBSEI_WORKER_TYPE`: Gunicorn worker type (default: uvicorn.workers.UvicornWorker)

## Use cases
`Obsei` use cases are following, but not limited to -
- Automatic customer issue ticketing based on sentiment analysis
- Proper tagging of ticket like login issue, signup issue, delivery issue etc for faster disposal
- Checking effectiveness of social media marketing campaign
- Extraction of deeper insight from feedbacks on various platforms
- Research purpose

## Components and Integrations

- **Source/Observer**: Twitter, Play Store Reviews, Apple App Store Reviews (Facebook, Instagram, Google reviews, Amazon reviews, Slack, Microsoft Team, Chat-bots etc planned in future)
- **Analyzer/Segmenter**: Sentiment and Text classification (QA, Natural Search, FAQ, Summarization etc planned in future)
- **Sink/Informer**: HTTP API, ElasticSearch, DailyGet, and Jira (Salesforce, Zendesk, Hubspot, Slack, Microsoft Team, etc planned in future)
- **Processor/WorkflowEngine**: Simple integration between Source, Analyser and Sink (Rich workflows using rule engine planned in future)
- **Convertor**: Very important part, which convert data from analyzer format to the format sink understand. It is very helpful in any customizations, refer `dailyget_sink.py` and `jira_sink.py`.

**Note:** In order to use some integrations you would need credentials, refer following list -
- [Twitter](https://twitter.com/): To make authorized API call, get access from [dev portal](https://developer.twitter.com/en/apply-for-access). Read about [search api](https://developer.twitter.com/en/docs/twitter-api/tweets/search/introduction) for more details. 
- [Play Store](https://play.google.com/): To make authorized API calls, get [service account's credentials](https://developers.google.com/identity/protocols/oauth2/service-account). Read about [review api](https://googleapis.github.io/google-api-python-client/docs/dyn/androidpublisher_v3.reviews.html) for more details.

## Examples and Screenshots
Refer [example](https://github.com/lalitpagaria/obsei/tree/master/example) and [config](https://github.com/lalitpagaria/obsei/tree/master/config) folders for `obsei` usage and configurations.

### Jira
![](https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/jira_screenshot.png)

## Attribution
This could not have been possible without following open source software -
- [searchtweets-v2](https://github.com/twitterdev/search-tweets-python): For Twitter's API v2 wrapper
- [vaderSentiment](https://github.com/cjhutto/vaderSentiment): For rule-based sentiment analysis
- [transformers](https://github.com/huggingface/transformers): For text-classification pipeline
- [tweet-preprocessor](https://github.com/s/preprocessor): For tweets preprocessing and cleaning
- [atlassian-python-api](https://github.com/atlassian-api/atlassian-python-api): To interact with Jira
- [elasticsearch](https://github.com/elastic/elasticsearch-py): To interact with Elasticsearch
- [hydra](https://github.com/facebookresearch/hydra.git): To elegantly configuring Obsei
- [apscheduler](https://github.com/agronholm/apscheduler): To schedule task to execute desired workflow
- [pydantic](https://github.com/samuelcolvin/pydantic): For data validation
- [sqlalchemy](https://github.com/sqlalchemy/sqlalchemy): As SQL toolkit to access DB storage
- [fastapi](https://fastapi.tiangolo.com/) & [gunicorn](https://gunicorn.org/): For HTTP server and API interface
- [feedparser](https://github.com/kurtmckee/feedparser): To parse rss feed to fetch app store reviews
- [google-play-scraper](https://github.com/JoMingyu/google-play-scraper): To fetch the Google Play Store review without authentication

## Contribution
Currently, we are not accepting any pull requests. If you want a feature or something doesn't work, please create an issue.

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

## Acknowledgement

We would like to thank [DailyGet](https://dailyget.in/) for continuous support and encouragement.
Please check [DailyGet](https://dailyget.in/) out. it is a platform which can easily be configured to solve any business process automation requirements.
