#!/usr/bin/env bash
# Common utilities

function error_exit () {
    #   ----------------------------------------------------------------
    #   Function for exit due to fatal program error
    #       Accepts 1 argument:
    #           string containing descriptive error message
    #   ----------------------------------------------------------------

    echo "${PROGNAME}: ${1:-"Unknown Error"}" 1>&2
    exit 1
}

error_check() {
	[ "$1" != 0 ] && {
		echo "error; exiting"
		exit 1
	}
}

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
export DATADIR=$INSTALLDIR/data
export GITSRC=/opt/git/livesectional/

# Sync filesystems
sync
