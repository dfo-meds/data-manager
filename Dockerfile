# syntax=docker/dockerfile:1

# Note that 3.9 is required for greenlet to work (as of July 21/2022), 3.10 fails to compile
FROM python:3.9.13-slim-bullseye

# Get the required libraries to compile psycopg
RUN apt-get update
RUN apt-get install libpq-dev build-essential -y

WORKDIR /srv/metadb

ENV PYTHONPATH=/srv/metadb/app
ENV MODULE_NAME=main
ENV VARIABLE_NAME=app
ENV APP_MODULE=main:app
ENV GUNICORN_CONF=/srv/metadb/gunicorn_conf.py

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY docker/start.sh start.sh
RUN chmod +x start.sh

COPY docker/gunicorn_conf.py gunicorn_conf.py

COPY . app

EXPOSE 80

WORKDIR /srv/metadb/app

CMD ["/srv/metadb/start.sh"]
