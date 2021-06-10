#!/bin/sh
set -e
echo "testing ${1}"
az group show -n "${1}" | python -c 'import json,sys; assert json.load(sys.stdin)["tags"] == {"terraform": "v1"}'
