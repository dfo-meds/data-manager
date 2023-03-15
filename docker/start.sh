#! /usr/bin/env sh
set -e

cd /srv/metadb/app || exit

python cli.py setup

python cli.py user create "${METADB_USERNAME:-admin}" "${METADB_EMAIL:-meds.erddap@gmail.com}" --display "Administrator" --no-error --password "${METADB_PASSWORD:-modernmajorgeneral}"

# If there's a prestart.sh script in the /app directory, run it before starting
PRE_START_PATH=/srv/metadb/prestart.sh
echo "Checking for script in $PRE_START_PATH"
if [ -f $PRE_START_PATH ] ; then
    echo "Running script $PRE_START_PATH"
    . "$PRE_START_PATH"
else
    echo "There is no script $PRE_START_PATH"
fi

# Start Gunicorn
exec gunicorn --chdir /srv/metadb -k gevent -c "$GUNICORN_CONF" "$APP_MODULE"
