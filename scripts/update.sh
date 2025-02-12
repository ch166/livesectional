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

INSTALL='/usr/bin/install -C -v -D'
INSTALLDIR='/usr/bin/install -d'
CRUDINI='crudini --verbose'

# Git update
cd $GITSRC || exit 1
error_check $? "cd GITSRC problems"
git remote update
error_check $? "git remote update problems"

# NOT Overwriting these until we have a better plan
# $INSTALL -t $INSTALLDEST config.ini
# $INSTALL -t $INSTALLDEST config.ini

# Copy the correct files into destination directory
$INSTALL -t $INSTALLDEST ./*.py
error_check $? "install *.py"
$INSTALL -t $INSTALLDEST requirements.txt
error_check $? "install requirements.txt"
$INSTALL -t $INSTALLDEST VERSION.txt
error_check $? "install VERSION.txt"
$INSTALL -t $TEMPLATEDEST templates/*.html
error_check $? "install templates"
$INSTALL -t $SCRIPTSDEST -m 755 scripts/*.sh
error_check $? "install scripts"
$INSTALL -m 755 scripts/livemap-daily.sh $CRONDAILY/livemap-daily
error_check $? "install cron.daily file"
$INSTALL -t $SYSTEMD livemap.service
error_check $? "install systemd service"

$INSTALLDIR $LOGDEST
error_check $? "Create LOGDEST directory"
$INSTALLDIR $STATICFILES
error_check $? "Create STATICFILES directory"

# FIXME: This would be better not hardcoded / only in the update script
# Need to be able to handle the situation where we add new configuration data files newer versions of the environment
if [ ! -f $DATADEST/airports.json ]; then
  $INSTALL -t $DATADEST data/airports.json
fi

if [ ! -f $DATADEST/oled_conf.json ]; then
  $INSTALL -t $DATADEST data/oled_conf.json
fi


# Using crudini ( https://github.com/pixelb/crudini ) to ensure that new .ini entries are created
#
# crudini provides a way to merge the existing configuration file into one that arrives via update
# crudini --merge new-file.ini < original.ini 
# will allow us to add new .ini file values, while keeping the local original.ini 
# This should allow us to safely do an ini update while keeping local modifications
# TODO: FIXME: to get access to the crudini installed in the environment
source /opt/venv/livemap/bin/activate


# Install repo config.ini to config-update.ini
$INSTALL config.ini $INSTALLDEST/config-update.ini
error_check $? "install config-update.ini"
# Modify freshly installed config-update.ini by merging in local config.ini
$CRUDINI --verbose --merge $INSTALLDEST/config-update.ini < $INSTALLDEST/config.ini
error_check $? "crudini merge files"
# Replace local config.ini with updated version
$INSTALL $INSTALLDEST/config-update.ini $INSTALLDEST/config.ini
error_check $? "update local config.ini"

# Intentionally change specific .ini file entries
$PYTHON crudini --set $INSTALLDEST/config.ini default min_update_ver unused
$PYTHON crudini --set $INSTALLDEST/config.ini schedule offhour unused
$PYTHON crudini --set $INSTALLDEST/config.ini schedule offminutes unused
$PYTHON crudini --set $INSTALLDEST/config.ini schedule onhour unused
$PYTHON crudini --set $INSTALLDEST/config.ini schedule onminutes unused

$PYTHON crudini --set $INSTALLDEST/config.ini logging loglevel info


echo -e "Copying static archive"
cd $STATICFILES || exit 1
error_check $? "cd STATICFILES"
rsync -v -auhS --partial -B 16384 --info=progress2 $GITSRC/static/ $STATICFILES
error_check $? "static files rsync"

# Let systemctl know something may have changed
systemctl daemon-reload


# Check to see if we need to create ssl-certificates
#
bash "$(dirname "$0")"/ssl-certificate.sh
error_check $? "execute ssl-certificates script"

# Sync filesystems
sync
