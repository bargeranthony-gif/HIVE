#!/bin/sh
set -eu

cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
    exec python3 install.py "$@"
fi

echo "Python 3.10 or newer is required."
exit 1
