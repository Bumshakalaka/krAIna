#!/bin/bash
function err_trap () {
    echo "$0: line $1: exit status of last command: $2"
    exit 1
}

set -E
trap 'err_trap ${LINENO} ${$?}' ERR

cd ..
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp setup_scripts/.env.template .env
cp setup_scripts/config.yaml.template config.yaml

echo "*************************************************"
echo "REMEMBER to edit .env file and add your API keys"
echo "*************************************************"

deactivate