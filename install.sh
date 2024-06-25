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

INSTALLDIR=/opt/NeoSectional
DATADIR=$INSTALLDIR/data
TEMPLATEDIR=$INSTALLDIR/templates
STATICDIR=$INSTALLDIR/static
LOGDIR=$INSTALLDIR/logs

INSTALL=/usr/bin/install

# Copy the correct files into /NeoSectional

# Create directories
mkdir -p $INSTALLDIR
mkdir -p $DATADIR
mkdir -p $TEMPLATEDIR
mkdir -p $STATICDIR
mkdir -p $LOGDIR

# Install files
$INSTALL -D ./*.py $INSTALLDIR/
$INSTALL -D config.ini $INSTALLDIR/
$INSTALL -D requirements.txt $INSTALLDIR/
$INSTALL -D data/airports.json $DATADIR/
$INSTALL -D templates/*.html $TEMPLATEDIR/

rsync -rav --relative static/ $INSTALLDIR/

cp livemap.service /etc/systemd/system/livemap.service
systemctl daemon-reload
#systemctl restart livemap

echo -e "Try\nsystemctl restart livemap ; systemctl status livemap"
