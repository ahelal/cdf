#!/bin/sh
set -e
echo "{{cdf.location}}" > "${1}"
echo "X_STDOUT"
>&2 echo "X_STDERR" 
