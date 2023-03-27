#! /usr/bin/env sh
set -e

PYTHONBUFFERED=TRUE
export PYTHONUNBUFFERED

PIPEMAN_CONFIG_DIR=/metadb-config
export PIPEMAN_CONFIG_DIR

cd /srv/metadb/app || exit

rsync -a -v --ignore-existing /srv/metadb/app/docker/default_config /metadb-config

python -m alembic upgrade head

python cli.py core setup

python cli.py user create --display "Administrator" --no-error --password "${METADB_PASSWORD:-modernmajorgeneral}" "${METADB_USERNAME:-admin}" "${METADB_EMAIL:-meds.erddap@gmail.com}"

python cli.py user group assign --no-error "${METADB_USERNAME:-admin}" superadmin

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


