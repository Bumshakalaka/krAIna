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
ACTION=$1
TEXT=$2
RET=$(python kraina.py --skill "${ACTION}" --text "${TEXT}")
echo "${RET}"