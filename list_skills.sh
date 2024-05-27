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
find . -name snippets -type d -exec find {} -maxdepth 1 ! \( -name "_*" -o -name "." \) -type d -printf "%f," \;