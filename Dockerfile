# syntax=docker/dockerfile:1

# Note that 3.9 is required for greenlet to work (as of July 21/2022), 3.10 fails to compile
FROM python:3.9.13-slim-bullseye

# Get the required libraries to compile psycopg
RUN apt-get update
RUN apt-get install libpq-dev build-essential -y

WORKDIR /srv/metadb

VOLUME /metadb-config
VOLUME /metadb-data

ENV PIPEMAN_CONFIG_SEARCH_PATHS=/srv/metadb/app/docker/config;/metadb-config
ENV PYTHONPATH=/srv/metadb/app
ENV MODULE_NAME=app
ENV VARIABLE_NAME=app
ENV APP_MODULE=app:app
ENV GUNICORN_CONF=/srv/metadb/gunicorn_conf.py


RUN pip install --upgrade pip

COPY requirements-docker.txt requirements-docker.txt

RUN pip install -r requirements-docker.txt

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY docker/start.sh start.sh
RUN chmod +x start.sh

COPY docker/gunicorn_conf.py gunicorn_conf.py

COPY docker/pipeman /usr/local/bin/pipeman
RUN chmod +x /usr/local/bin/pipeman

COPY . app

EXPOSE 80

WORKDIR /srv/metadb/app

CMD ["/srv/metadb/start.sh"]
