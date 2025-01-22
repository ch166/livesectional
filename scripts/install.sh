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

# Debugging
# set -x

# FIXME: Pull these destinations from a common config
GITSRC=/opt/git/livesectional/
INSTALLDEST=/opt/NeoSectional/
DATADEST=$INSTALLDEST/data/
TEMPLATEDEST=$INSTALLDEST/templates/
STATICFILES=$INSTALLDEST/static/
LOGDEST=$INSTALLDEST/logs/
SCRIPTSDEST=$INSTALLDEST/scripts/
CRONDAILY=/etc/cron.daily/


INSTALL='/usr/bin/install -p -v -D'
INSTALLDIR='/usr/bin/install -d'

# Copy the correct files into destination directory

$INSTALL -t $INSTALLDEST ./*.py
$INSTALL -t $INSTALLDEST config.ini
$INSTALL -t $INSTALLDEST requirements.txt
$INSTALL -t $DATADEST data/airports.json
$INSTALL -t $TEMPLATEDEST templates/*.html
$INSTALL -t $SCRIPTSDEST -m 755 scripts/*.sh
$INSTALL -t $CRONDAILY -m 755 scripts/update.sh
$INSTALLDIR $LOGDEST
$INSTALLDIR $STATICFILES

echo -e "Copying static archive"
cd static/
rsync -auhS --partial -B 16384 --info=progress2 --relative . $STATICFILES/

cp livemap.service /etc/systemd/system/livemap.service
systemctl daemon-reload
#systemctl restart livemap

echo -e "Install complete - try\n systemctl restart livemap ; systemctl status livemap"
