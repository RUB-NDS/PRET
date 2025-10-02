#!/usr/bin/env bash

create_venv() {
    command=$1
    echo "Attempting to create virtual environment with $command..."
    if $command -m venv .venv; then
        source .venv/bin/activate
        echo "Virtual environment created and activated with $command"
        return 0
    else
        echo "Failed to create virtual environment with $command"
        return 1
    fi
}

if create_venv python; then
    echo "Virtual environment created with python"
elif create_venv python3; then
    echo "Virtual environment created with python3"
else
    echo "Failed to create virtual environment with both python and python3"
    exit 1
fi

if [ -z "$VIRTUAL_ENV" ]; then
    echo "Not inside a virtual environment. Exiting..."
    exit 1
else
    echo "Inside a virtual environment. Proceeding..."
fi

pip install --upgrade pip

if [ -f requirements.txt ]; then
    pip install -r requirements.txt
else
    echo "requirements.txt not found"
    exit 1
fi
