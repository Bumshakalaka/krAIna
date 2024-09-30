#!/bin/bash
function err_trap () {
    echo "$0: line $1: exit status of last command: $2"
    exit 1
}

set -E
trap 'err_trap ${LINENO} ${$?}' ERR

# ALWAYS CURRENT_DIR == kraina
CURRENT_DIR=$(realpath "$(dirname "$0")"/.. )

cd ${CURRENT_DIR}

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt --upgrade
if [ ! -f .env ]; then
  cp setup_scripts/.env.template .env
fi
if [ ! -f config.yaml ]; then
  cp setup_scripts/config.yaml.template config.yaml
fi

echo "*************************************************"
echo "REMEMBER to edit .env file and add your API keys"
echo "*************************************************"

deactivate