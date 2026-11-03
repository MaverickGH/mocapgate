#!/bin/sh
set -eu
cd "$(dirname "$0")"
export PATH="$PWD:$PATH"
export PYTHONDONTWRITEBYTECODE=1
exec ./python/bin/python3.12 ./mocapgate.py studio "$@"
