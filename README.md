<h2 align="center">
    obsei: OBserve, SEgment and Inform
</h2>

<p align="center">
    <a href="https://github.com/lalitpagaria/obsei/actions">
        <img alt="CI" src="https://github.com/lalitpagaria/obsei/workflows/CI/badge.svg?branch=master">
    </a>
    <a href="https://github.com/lalitpagaria/obsei/releases">
        <img alt="Release" src="https://img.shields.io/github/v/release/lalitpagaria/obsei?include_prereleases">
    </a>
    <a href="https://github.com/lalitpagaria/obsei/blob/master/LICENSE">
        <img alt="License" src="https://img.shields.io/github/license/lalitpagaria/obsei?color=blue">
    </a>
    <a href="https://github.com/lalitpagaria/obsei/commits/master">
        <img alt="Last commit" src="https://img.shields.io/github/last-commit/lalitpagaria/obsei">
    </a>
</p>

Obsei is intended to be a workflow automation tool for text segmentation need. Obsei consist of -
 - **OBserver**, observes platform like Twitter, Facebook, App Stores, Google reviews, Amazon reviews and feed that information to,
 - **SEgmenter**, which perform text classification and sentiment analysis and feed that information to,
 - **Informer**, which send it to ticketing system, data store or other places for further action and analysis.

## Installation

### Use as SDK
You use `obsei` as SDK to further extend/customize it for your own use case as follows -

~~Install via PyPi:~~

~~pip install obsei~~

Install from master branch (if you wanna try the latest features):

    git clone https://github.com/lalitpagaria/obsei.git
    cd obsei
    pip install --editable .

To update your installation, just do a `git pull`. The `--editable` flag
will update changes immediately.

### Use as API interface
You can use `obsei` restful interface to directly run and customize via it's rest interface as follows -

Start docker with default configuration file:

    docker run -d --name obesi -p 9898:9898 lalitpagaria/obsei:latest

Start docker with custom configuration file (Assuming you have configfile `config.yaml` at `/home/user/obsei/config` at host machine):

    docker run -d --name obesi -v "/home/user/obsei/config:/home/user/config" -e "OBSEI_CONFIG_PATH=/home/user/config" -e "OBSEI_CONFIG_FILENAME=config.yaml" -p 9898:9898 lalitpagaria/obsei:latest

Start docker locally with custom code:

    docker-compose up --build

Following environment variables can useful to customization purpose -
- `OBSEI_CONFIG_PATH`: Configuration file path (default: ../config)
- `OBSEI_CONFIG_FILENAME`: Configuration file name (default: rest.yaml)
- `OBSEI_NUM_OF_WORKERS`: Number of workers for rest API server (default: 1)
- `OBSEI_WORKER_TIMEOUT`: Worker idle timeout in seconds (default: 180)
- `OBSEI_SERVER_PORT`: Rest API server port (default: 9898)
- `OBSEI_WORKER_TYPE`: Gunicorn worker type (default: uvicorn.workers.UvicornWorker)

## Use cases
Obsei use cases are following, but not limited to -
- Automatic customer complaint ticketing based on sentiment
- Proper re-tagging of tickets like login issue, signup issue, delivery issue etc for faster disposal
- Checking effectiveness of social media marketing campaign
- Deeper product insight from customer feedback on various platforms
- Research purpose

## Components

- **Source**: Twitter (Facebook, Instagram, Google reviews, Amazon reviews, App Store reviews, Slack, Microsoft Team, Chatbots etc in future)
- **Analyzer**: Sentiment and Text classification (QA, Natural Search, FAQ, Summarization etc in future)
- **Sink**: API, ElasticSearch, and Jira (Salesforce, Zendesk, Hubspot, Slack, Microsoft Team, etc in future)
- **Processor**: Simple integration between Source, Analyser and Sink (Rich workflows using rule engine)

## Examples
Please refer [example](https://github.com/lalitpagaria/obsei/tree/master/example) folder for various examples to use obsei for various use case.

## Attribution
This could not have been possible without following open source work -
- [searchtweets-v2](https://github.com/twitterdev/search-tweets-python): For Twitter's API v2 wrapper
- [vaderSentiment](https://github.com/cjhutto/vaderSentiment): For rule-based sentiment analysis
- [transformers](https://github.com/huggingface/transformers): For text-classification pipeline
- [tweet-preprocessor](https://github.com/s/preprocessor): For tweets preprocessing and cleaning
- [atlassian-python-api](https://github.com/atlassian-api/atlassian-python-api): To interact with Jira
- [elasticsearch](https://github.com/elastic/elasticsearch-py): To interact with Elasticsearch
- [hydra](https://github.com/facebookresearch/hydra.git): To elegantly configuring Obsei
- [apscheduler](https://github.com/agronholm/apscheduler): To schedule task to execute desired workflow
- [pydantic](https://github.com/samuelcolvin/pydantic): For data validation
- [fastapi](https://fastapi.tiangolo.com/) and [gunicorn](https://gunicorn.org/): For HTTP server

## Citing Obsei
If you use Obsei in your research please use the following BibTeX entry:
```text
@Misc{Pagaria2020Obsei,
  author =       {Lalit Pagaria},
  title =        {Obsei - A workflow automation tool for text segmentation need},
  howpublished = {Github},
  year =         {2020},
  url =          {https://github.com/lalitpagaria/obsei}
}
```
