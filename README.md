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

Obsei is intended to be an automation workflow tool to -
 - **OBserve**, Platforms like Twitter, Facebook, App Stores, Google reviews, Amazon reviews and,
 - **SEgment**, them using AI-based text classification and sentiment analysis and,
 - **Inform**, to customer centric ticketing system, data store or other places for action.

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

~~Start docker with default configuration file:~~

~~docker run -d --name obesi -p 9898:9898 lalitpagaria/obsei:latest~~

~~Start docker with custom configuration file (Assuming you have configfile `config.yaml` at `/home/user/obsei/config` at host machine):~~

~~docker run -d --name obesi -v "/home/user/obsei/config:/home/user/config" -e "OBSEI_CONFIG_PATH=/home/user/config" -e "OBSEI_CONFIG_FILENAME=config.yaml" -p 9898:9898 lalitpagaria/obsei:latest~~

Start docker locally with custom code:

    docker-compose up --build

Following environment variables can useful to customization purpose -
- OBSEI_CONFIG_PATH: Configuration file path (default: ../config)
- OBSEI_CONFIG_FILENAME: Configuration file name (default: rest.yaml)
- OBSEI_NUM_OF_WORKERS: Number of workers for rest API server (default: 1)
- OBSEI_WORKER_TIMEOUT: Worker idle timeout in seconds (default: 180)
- OBSEI_SERVER_PORT: Rest API server port (default: 9898)
- OBSEI_WORKER_TYPE: Gunicorn worker type (default: uvicorn.workers.UvicornWorker)

## Components

- **Source**
- **Analyzer**
- **Sink**
- **Processor**

## Examples
Please refer [example](https://github.com/lalitpagaria/obsei/tree/master/example) folder for various examples to use obsei for various use case.
