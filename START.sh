#!/bin/sh
set -eu
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
if [ "$(uname -s)-$(uname -m)" = Darwin-arm64 ]; then
    export PATH="$PWD:$PATH"
    exec ./python/bin/python3.12 ./mocapgate.py studio "$@"
fi
exec python3.12 ./mocapgate.py studio "$@"
