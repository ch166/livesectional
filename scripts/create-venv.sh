#!/usr/bin/env bash

source $(dirname "$0")/utils.sh

export VENVDIR=/opt/venv/livemap

mkdir -p $VENVDIR
error_check $?

if test -f $VENVDIR/bin/activate; then
    echo "Environment appears to already exist"
    echo "Trying pip3 install --upgrade of requirements.txt"
    $VENVDIR/bin/pip3 install --upgrade -r $INSTALLDIR/requirements.txt
    error_check $?
    echo "Complete."
else
    echo "Creating python Environment"
    python3 -m venv $VENVDIR
    error_check $?
    echo "Install packages in environment"
    $VENVDIR/bin/pip3 install -r $INSTALLDIR/requirements.txt
    error_check $?
fi

# Sync filesystems
sync
