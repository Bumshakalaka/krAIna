#!/bin/bash
function err_trap () {
    echo "$0: line $1: exit status of last command: $2"
    exit 1
}

set -E
trap 'err_trap ${LINENO} ${$?}' ERR

CURRENT_DIR=$(dirname "$0")
CURRENT_DIR=$(realpath "${CURRENT_DIR}")
cd "${CURRENT_DIR}"
if [ -z "$VIRTUAL_ENV" ]; then
    source .venv/bin/activate
fi
A=$1
B=$2
if [ "$B" == "" ]; then
  RET=$(python kraina.py --file "${A}")
else
  RET=$(python kraina.py --snippet "${A}" --text "${B}")
fi
echo "${RET}"