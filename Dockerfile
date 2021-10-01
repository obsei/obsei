# This is Docker file to Obsei SDK with dependencies installed
FROM python:3.9-slim-buster

RUN useradd --create-home user
WORKDIR /home/user

# env variable
ENV PIP_DISABLE_PIP_VERSION_CHECK 1
ENV PIP_NO_CACHE_DIR 1
ENV WORKFLOW_SCRIPT '/home/user/obsei/process_workflow.py'
ENV OBSEI_CONFIG_PATH ""
ENV OBSEI_CONFIG_FILENAME ""


# Hack to install jre on debian
RUN mkdir -p /usr/share/man/man1

# install few required tools
RUN apt-get update && apt-get upgrade -y && apt-get install -y curl git pkg-config cmake libncurses5
RUN apt-get clean autoclean && apt-get autoremove -y
RUN rm -rf /var/lib/{apt,dpkg,cache,log}/

# install as a package
COPY setup.py requirements.txt README.md /home/user/
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# copy README
COPY README.md /home/user/

# copy code
COPY obsei /home/user/obsei
RUN pip install -e .


USER user

# cmd for running the API
CMD ["sh", "-c", "python ${WORKFLOW_SCRIPT}"]
