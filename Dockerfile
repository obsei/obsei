FROM python:3.8-slim-buster

RUN useradd --create-home user
WORKDIR /home/user

# env variable
ENV OBSEI_NUM_OF_WORKERS 1
ENV OBSEI_WORKER_TIMEOUT 180
ENV OBSEI_SERVER_PORT 9898
ENV OBSEI_WORKER_TYPE uvicorn.workers.UvicornWorker

# Hack to install jre on debian
RUN mkdir -p /usr/share/man/man1

# install few required tools
RUN apt-get update && apt-get upgrade -y && apt-get install -y curl git pkg-config cmake default-jre build-essential g++
RUN apt-get clean autoclean && apt-get autoremove -y
RUN rm -rf /var/lib/{apt,dpkg,cache,log}/

# install as a package
COPY setup.py requirements.txt README.md /home/user/
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# copy README and config
COPY README.md /home/user/
# hack to fix CI builds
RUN true
COPY config /home/user/config
# hack to fix CI builds
RUN true
# Copy REST API code
COPY rest_api /home/user/rest_api

# copy code
COPY obsei /home/user/obsei
RUN pip install -e .


USER user

# cmd for running the API
CMD ["gunicorn", "rest_api.application:app",  "-b", "0.0.0.0:${OBSEI_SERVER_PORT}", "-k", "${OBSEI_GUNVICORN_WORKER_TYPE}", "--workers", "${OBSEI_NUM_OF_WORKERS}", "--timeout", "${OBSEI_WORKER_TIMEOUT}"]
