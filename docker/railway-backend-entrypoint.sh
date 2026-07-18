#!/bin/sh
set -eu

if [ -d /data ]; then
    mkdir -p /data/chroma /data/reports /data/hf-cache
    chown -R app:app /data/chroma /data/reports /data/hf-cache
    export HF_HOME="${HF_HOME:-/data/hf-cache}"
    export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/data/hf-cache/xdg}"
fi

exec runuser -u app -- "$@"
