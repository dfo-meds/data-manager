#! /usr/bin/env sh
set -e

PYTHONBUFFERED=TRUE
export PYTHONUNBUFFERED

cd /srv/metadb/app || exit

# Handle prometheus directory
if [ -e "/srv/metadb/_prometheus" ] ; then
  rm -r /srv/metadb/_prometheus/*
else
  mkdir /srv/metadb/_prometheus
fi

# Handle setup, if requested
if [ "$1" = "-with-install" ] ; then
  shift 1
  python -m alembic upgrade head
  python cli.py core setup
fi

# If there's a prestart.sh script in the /app directory, run it before starting
PRE_START_PATH=/srv/metadb/prestart.sh
echo "Checking for script in $PRE_START_PATH"
if [ -f $PRE_START_PATH ] ; then
    echo "Running script $PRE_START_PATH"
    . "$PRE_START_PATH"
else
    echo "There is no script $PRE_START_PATH"
fi

# Start Gunicorn or Flask
if [ -z "$USE_FLASK" ]; then
  exec gunicorn --chdir /srv/metadb -c "$GUNICORN_CONF" "$APP_MODULE" "$@"
else
  python -m flask run --host="0.0.0.0" --port=80
fi


