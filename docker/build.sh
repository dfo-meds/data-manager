#! /usr/bin/env sh
set -e

cd /srv/metadb/app || exit

python -m alembic upgrade head

python cli.py core setup

python cli.py user create --display "Administrator" --no-error --password "${METADB_PASSWORD:-modernmajorgeneral}" "${METADB_USERNAME:-admin}" "${METADB_EMAIL:-meds.erddap@gmail.com}"

python cli.py user group assign --no-error "${METADB_USERNAME:-admin}" superadmin
