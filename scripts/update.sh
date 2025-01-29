#!/usr/bin/env bash

source "$(dirname "$0")"/utils.sh

# FIXME: Pull these destinations from the config
GITSRC=/opt/git/livesectional/
INSTALLDEST=/opt/NeoSectional/
DATADEST=$INSTALLDEST/data/
TEMPLATEDEST=$INSTALLDEST/templates/
STATICFILES=$INSTALLDEST/static/
LOGDEST=$INSTALLDEST/logs/
SCRIPTSDEST=$INSTALLDEST/scripts/
CRONDAILY=/etc/cron.daily/
SYSTEMD=/etc/systemd/system/

INSTALL='/usr/bin/install -p -v -D'
INSTALLDIR='/usr/bin/install -d'

# Git update
cd $GITSRC || exit 1
error_check $?
git remote update
error_check $?

# NOT Overwriting these until we have a better plan
# $INSTALL -t $INSTALLDEST config.ini
# $INSTALL -t $INSTALLDEST config.ini

# Copy the correct files into destination directory
$INSTALL -t $INSTALLDEST ./*.py
error_check $?
$INSTALL -t $INSTALLDEST requirements.txt
error_check $?
$INSTALL -t $INSTALLDEST VERSION.txt
error_check $?
$INSTALL -t $TEMPLATEDEST templates/*.html
error_check $?
$INSTALL -t $SCRIPTSDEST -m 755 scripts/*.sh
error_check $?
$INSTALL -t $CRONDAILY -m 755 scripts/daily.sh
error_check $?
$INSTALL -t $SYSTEMD livemap.service
error_check $?

$INSTALLDIR $LOGDEST
error_check $?
$INSTALLDIR $STATICFILES
error_check $?

# FIXME: This would be better not hardcoded / only in the update script
# Need to be able to handle the situation where we add new configuration data files newer versions of the environment
if [ ! -f $DATADEST/airports.json ]; then
  $INSTALL -t $DATADEST data/airports.json
fi

if [ ! -f $DATADEST/oled_conf.json ]; then
  $INSTALL -t $DATADEST data/oled_conf.json
fi


# FIXME: Updates that include new or changed config.ini lines
# Need to be able to handle the scenario where we add additional configuration file lines


echo -e "Copying static archive"
cd $STATICFILES || exit 1
error_check $?
rsync -auhS --partial -B 16384 --info=progress2 --relative . $STATICFILES/
error_check $?

# Sync filesystems
sync
