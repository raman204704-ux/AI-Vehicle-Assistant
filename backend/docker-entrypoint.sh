#!/bin/sh
set -eu

for directory in /app/storage/chroma /app/storage/celery; do
    mkdir -p "$directory"
    if [ "$(stat -c '%u' "$directory")" != "$APP_UID" ]; then
        chown -R app:app "$directory"
    fi
done

exec gosu app "$@"
