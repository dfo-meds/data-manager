#! /bin/sh
set -e

PYTHONBUFFERED=TRUE
export PYTHONUNBUFFERED

cd /srv/metadb/app || exit

# Run the daemon
if [ "$1" = "cron" ] ; then

  python cli.py core cron

# Upgrade or install
elif [ "$1" = "upgrade" ] ; then

  python -m alembic upgrade head

  python cli.py core setup

else

  # Check for the default name and remove it
  if [ "$1" = "webserver" ] ; then
    shift 1
  fi

  # Handle prometheus directory
  if [ -e "/srv/metadb/_prometheus" ] ; then
    rm -r /srv/metadb/_prometheus/*
  else
    mkdir /srv/metadb/_prometheus
  fi

  # Start Gunicorn or Flask
  if [ -z "$USE_FLASK" ]; then
    exec gunicorn --chdir /srv/metadb -c "$GUNICORN_CONF" "$APP_MODULE" "$@"
  else
    python -m flask run --host="0.0.0.0" --port=80
  fi

fi
