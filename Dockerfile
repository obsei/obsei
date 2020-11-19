FROM python:3.8-slim

WORKDIR /home/user

RUN apt-get update && apt-get upgrade -y && apt-get install -y curl git pkg-config cmake
RUN apt-get clean autoclean && apt-get autoremove -y
RUN rm -rf /var/lib/{apt,dpkg,cache,log}/

# copy code
COPY obsei /home/user/obsei

# install as a package
COPY setup.py requirements.txt README.md /home/user/
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -e .

# copy saved models
COPY README.md /home/user/
COPY models /home/user/models
COPY config /home/user/config

# Copy REST API code
COPY rest_api /home/user/rest_api

# optional : copy sqlite db if needed for testing
#COPY qa.db /home/user/

# optional: copy data directory containing docs for ingestion
#COPY data /home/user/data

EXPOSE 9898

# cmd for running the API
CMD ["gunicorn", "rest_api.application:app",  "-b", "0.0.0.0:9898", "-k", "uvicorn.workers.UvicornWorker", "--workers", "1", "--timeout", "180"]
