#!/usr/bin/env bash

source "$(dirname "$0")"/utils.sh

# Debugging
# set -x

# FIXME: Pull these destinations from a common config
GITSRC=/opt/git/livesectional/
FONTAWESOME=/opt/git/fontawesome
INSTALLDEST=/opt/NeoSectional
DATADEST=$INSTALLDEST/data
TEMPLATEDEST=$INSTALLDEST/templates/
STATICFILES=$INSTALLDEST/static
LOGDEST=$INSTALLDEST/logs/
SCRIPTSDEST=$INSTALLDEST/scripts/
CRONDAILY=/etc/cron.daily/
SYSTEMD=/etc/systemd/system/


INSTALL='/usr/bin/install -p -v -D'
INSTALLDIR='/usr/bin/install -d'

# Copy the correct files into destination directory

cd $GITSRC || error_exit "cd $GITSRC failed."

$INSTALL -t $INSTALLDEST ./*.py
error_check $?
$INSTALL -t $INSTALLDEST requirements.txt
error_check $?
$INSTALL -t $TEMPLATEDEST templates/*.html
error_check $?
$INSTALL -t $SCRIPTSDEST -m 755 scripts/*.sh
error_check $?
$INSTALL -m 755 scripts/livemap-daily.sh $CRONDAILY/livemap-daily
error_check $?
$INSTALL -t $SYSTEMD livemap.service
error_check $?

# Make required directories
$INSTALLDIR $LOGDEST
error_check $?
$INSTALLDIR $STATICFILES
error_check $?

# Installing initial configuration files
$INSTALL -t $INSTALLDEST config.ini
error_check $?
$INSTALL -t $DATADEST data/airports.json
error_check $?
$INSTALL -t $DATADEST data/oled_conf.json
error_check $?


echo -e "Copying static archive"
cd $STATICFILES || error_exit "cd $STATICFILES failed."
rsync -auhS --partial -B 16384 --info=progress2 --relative . $STATICFILES/
error_check $?

echo -e "Getting fontawesome"
# FIXME: Fragile hardcoded values
#
$INSTALLDIR $FONTAWESOME
cd $FONTAWESOME || error_exit "cd $FONTAWESOME failed."
wget -nc https://use.fontawesome.com/releases/v6.7.2/fontawesome-free-6.7.2-web.zip
unzip -uo fontawesome-free-6.7.2-web.zip
ln -sf $FONTAWESOME/fontawesome-free-6.7.2-web/ $STATICFILES/fontawesome


systemctl daemon-reload

echo -e "Install complete - try\n systemctl restart livemap ; systemctl status livemap"

# Sync filesystems
sync
