# Obsei: OBserve, SEgment and Inform

<p align="center">
    <a href="https://github.com/lalitpagaria/obsei/actions">
        <img alt="CI" src="https://github.com/lalitpagaria/obsei/workflows/CI/badge.svg?branch=master">
    </a>
    <a href="https://github.com/lalitpagaria/obsei/blob/master/LICENSE">
        <img alt="License" src="https://img.shields.io/github/license/lalitpagaria/obsei?color=blue">
    </a>
    <a href="#">
        <img src="https://img.shields.io/pypi/pyversions/obsei" alt="PyPI - Python Version" />
    </a>
    <a href="#">
        <img alt="Release" src="https://img.shields.io/pypi/v/obsei">
    </a>
    <a href="#">
        <img src="https://img.shields.io/pypi/dm/obsei" alt="Downloads" />
    </a>
    <a href="#">
        <img src="https://img.shields.io/docker/pulls/lalitpagaria/obsei" alt="Docker Pulls" />
    </a>
    <a href="https://github.com/lalitpagaria/obsei/commits/master">
        <img alt="Last commit" src="https://img.shields.io/github/last-commit/lalitpagaria/obsei">
    </a>
</p>

`Obsei` is intended to be a workflow automation tool for text segmentation need. `Obsei` consist of -
 - **OBserver**, observes platform like Twitter, Facebook, App Stores, Google reviews, Amazon reviews and feed that information to,
 - **SEgmenter**, which perform text classification and sentiment analysis and feed that information to,
 - **Informer**, which send it to ticketing system, data store or other places for further action and analysis.

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

## Components

- **Source**: Twitter (Facebook, Instagram, Google reviews, Amazon reviews, App Store reviews, Slack, Microsoft Team, Chat-bots etc planned in future)
- **Analyzer**: Sentiment and Text classification (QA, Natural Search, FAQ, Summarization etc planned in future)
- **Sink**: HTTP API, ElasticSearch, DailyGet, and Jira (Salesforce, Zendesk, Hubspot, Slack, Microsoft Team, etc planned in future)
- **Processor**: Simple integration between Source, Analyser and Sink (Rich workflows using rule engine planned in future)

## Examples
Refer [example](https://github.com/lalitpagaria/obsei/tree/master/example) folder for `obsei` usage examples.

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
- [fastapi](https://fastapi.tiangolo.com/) & [gunicorn](https://gunicorn.org/): For HTTP server and API interface

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
