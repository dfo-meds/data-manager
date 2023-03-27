#! /usr/bin/env sh
set -e

PIPEMAN_CONFIG_DIR=/metadb-config
export PIPEMAN_CONFIG_DIR

cd /srv/metadb/app || exit

cp -nr /srv/metadb/app/docker/default_config /metadb-config
