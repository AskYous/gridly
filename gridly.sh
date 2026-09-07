#!/bin/sh
# Launcher: ./gridly.sh [FILE]
DIR=$(cd "$(dirname "$0")" && pwd)
exec "$DIR/.venv/bin/python" -m gridly "$@"
