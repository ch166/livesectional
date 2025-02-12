#!/usr/bin/env bash

source "$(dirname "$0")"/utils.sh

export VENVDIR=/opt/venv/livemap

mkdir -p $VENVDIR
error_check $?

if test -f $VENVDIR/bin/activate; then
    echo "Environment appears to already exist" | logger -t livemap-create-venv
    echo "Trying pip3 install --upgrade of requirements.txt" | logger -t livemap-create-venv
    $VENVDIR/bin/pip3 install --upgrade -r $GITSRC/requirements.txt
    error_check $? "pip3 install --upgrade problems"
    echo "Complete." | logger -t livemap-create-venv
else
    echo "Creating python Environment" | logger -t livemap-create-venv
    python3 -m venv $VENVDIR
    error_check $?
    echo "Install packages in environment" | logger -t livemap-create-venv
    $VENVDIR/bin/pip3 install -r $GITSRC/requirements.txt
    error_check $? "pip3 install new environment problems"
fi

# Sync filesystems
sync
