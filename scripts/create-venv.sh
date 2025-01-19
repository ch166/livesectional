#!/usr/bin/env bash

# Enable xtrace if the DEBUG environment variable is set
if [[ ${DEBUG-} =~ ^1|yes|true$ ]]; then
    set -o xtrace       # Trace the execution of the script (debug)
fi

# Only enable these shell behaviours if we're not being sourced
# Approach via: https://stackoverflow.com/a/28776166/8787985
if ! (return 0 2> /dev/null); then
    # A better class of script...
    set -o errexit      # Exit on most errors (see the manual)
    set -o nounset      # Disallow expansion of unset variables
    set -o pipefail     # Use last non-zero exit code in a pipeline
fi

# Enable errtrace or the error trap handler will not work as expected
set -o errtrace         # Ensure the error trap handler is inherited

export INSTALLDIR=/opt/NeoSectional
export VENVDIR=/opt/venv/livemap

mkdir -p $VENVDIR

if test -f $VENVDIR/bin/activate; then
    echo "Environment appears to already exist"
    echo "Trying pip3 install --upgrade of requirements.txt"
    $VENVDIR/bin/pip3 install --upgrade -r $INSTALLDIR/requirements.txt
    echo "Complete."
else
    echo "Creating Environment"
    python3 -m venv $VENVDIR
    echo "Install packages in environment"
    $VENVDIR/bin/pip3 install -r $INSTALLDIR/requirements.txt
fi
