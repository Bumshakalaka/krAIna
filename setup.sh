#!/bin/bash
ASK=$1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env
cp config.yaml.template config.yaml

if [ "$ASK" == "" ]; then

    echo "*************************************************"
    echo "REMEMBER to edit .env file and add your API keys"
    echo "*************************************************"

    read -r -p "Would you like to run krAIna Chat? [press n to exit]: " user_input
    if [ "$user_input" == "n" ]; then
        exit
    fi
    ./chat.sh    
fi
deactivate