#!/bin/sh
set -eu

if [ -d /data ]; then
    mkdir -p /data/chroma /data/reports
    chown -R app:app /data/chroma /data/reports
fi

exec runuser -u app -- "$@"
