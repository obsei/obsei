FROM python:3.8-slim-buster

RUN useradd --create-home user
WORKDIR /home/user
USER user

# RUN apt-get update && apt-get upgrade -y && apt-get install -y curl git pkg-config cmake
# RUN apt-get clean autoclean && apt-get autoremove -y
# RUN rm -rf /var/lib/{apt,dpkg,cache,log}/


# install as a package
COPY setup.py requirements.txt README.md /home/user/
RUN pip install --upgrade pip
RUN pip install --quiet --no-cache-dir -r requirements.txt

# copy README and config
COPY README.md /home/user/
COPY config /home/user/config

# copy downloaded model
# COPY models /home/user/models

# copy code
COPY obsei /home/user/obsei
RUN pip install --no-cache-dir -e .

# Copy REST API code
COPY rest_api /home/user/rest_api

EXPOSE 9898

# cmd for running the API
CMD ["gunicorn", "rest_api.application:app",  "-b", "0.0.0.0:9898", "-k", "uvicorn.workers.UvicornWorker", "--workers", "1", "--timeout", "180"]
