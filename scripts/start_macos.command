#!/bin/bash
cd "$(dirname "$0")/.." || exit 4
if [ ! -f scripts/setup_macos.sh ] || [ ! -f mocapgate.py ]; then
  echo '[X] Пакет распакован не полностью. Распакуйте ZIP заново целиком. / The package is incomplete. Extract the whole ZIP again.' >&2
  exit 4
fi
exec bash scripts/setup_macos.sh "$@"
